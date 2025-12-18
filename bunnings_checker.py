#!/usr/bin/env python3
"""
Bunnings URL Checker – Automatic Broken Link Finder
Finds your actual metafield structure and checks for broken links
"""

import time
import csv
import requests
import json
import re
from datetime import datetime
from requests.exceptions import RequestException, Timeout, SSLError, ConnectionError
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# =========================
# 🔐 SHOPIFY CONFIG (HARDCODED)
# =========================
SHOPIFY_STORE = "seydeltest"
SHOPIFY_TOKEN = "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"
SHOPIFY_API_VERSION = "2025-10"
# =========================

class AutoBunningsChecker:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.bunnings_urls_found = []
        self.metafield_patterns = {}
        
    def setup_driver(self):
        """Setup browser for Selenium tests"""
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f'user-agent={user_agent}')
        
        # Add more options to avoid detection
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-site-isolation-trials")
        
        self.driver = uc.Chrome(options=options, use_subprocess=True)
    
    def check_http_status(self, url):
        """
        Fast HTTP check for broken links
        Returns: (is_accessible: bool, status_code: int, error_message: str)
        """
        try:
            response = self.session.head(url, timeout=15, allow_redirects=True, verify=True)
            status_code = response.status_code
            
            if 200 <= status_code < 400:
                return True, status_code, None
            elif status_code == 404:
                return False, status_code, "Page not found (404)"
            elif status_code == 403:
                return False, status_code, "Access forbidden (403)"
            elif 500 <= status_code < 600:
                return False, status_code, f"Server error ({status_code})"
            else:
                return False, status_code, f"HTTP error ({status_code})"
                
        except Timeout:
            return False, None, "Request timeout (15s)"
        except (ConnectionError, SSLError):
            # Try with GET if HEAD fails
            try:
                response = self.session.get(url, timeout=15, allow_redirects=True, verify=True, stream=True)
                status_code = response.status_code
                
                if 200 <= status_code < 400:
                    return True, status_code, None
                else:
                    return False, status_code, f"HTTP error ({status_code})"
            except Exception as e:
                return False, None, f"Connection error: {str(e)[:100]}"
        except RequestException as e:
            return False, None, f"Request error: {str(e)[:100]}"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)[:100]}"
    
    def extract_clean_url(self, value):
        """Extract clean URL from various formats"""
        if not value:
            return ""
        
        value = str(value).strip()
        
        # Try JSON format
        try:
            data = json.loads(value)
            if isinstance(data, dict):
                for key in ['url', 'link', 'href', 'bunnings_url', 'source', 'reference']:
                    if key in data and data[key]:
                        url = str(data[key]).strip()
                        if "bunnings.com.au" in url.lower():
                            return url
        except:
            pass
        
        # Look for URL pattern
        url_pattern = r'https?://(?:www\.)?bunnings\.com\.au/[^\s<>"\']+'
        matches = re.findall(url_pattern, value, re.IGNORECASE)
        if matches:
            return matches[0]
        
        # General URL pattern if Bunnings specific not found
        url_pattern = r'https?://[^\s<>"\']+'
        matches = re.findall(url_pattern, value)
        for match in matches:
            if "bunnings.com.au" in match.lower():
                return match
        
        return value
    
    def discover_metafields(self, max_products=50):
        """
        Automatically discover how Bunnings URLs are stored
        """
        print("\n🔍 DISCOVERING METAFIELD STRUCTURE")
        print("="*60)
        
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        
        endpoint = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
        params = {"limit": 50, "fields": "id,title"}
        
        try:
            r = requests.get(endpoint, headers=headers, params=params)
            if r.status_code != 200:
                print(f"❌ API Error: {r.status_code}")
                return False
            
            products = r.json().get("products", [])
            print(f"📦 Examining {len(products)} products for Bunnings URLs...")
            
            for i, product in enumerate(products, 1):
                pid = product["id"]
                title = product.get("title", "N/A")
                
                # Get metafields for this product
                mf_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{pid}/metafields.json"
                mf_resp = requests.get(mf_url, headers=headers)
                
                if mf_resp.status_code == 200:
                    metafields = mf_resp.json().get("metafields", [])
                    
                    for mf in metafields:
                        namespace = mf.get("namespace", "")
                        key = mf.get("key", "")
                        value = str(mf.get("value", ""))
                        
                        # Track this metafield pattern
                        pattern = f"{namespace}.{key}"
                        self.metafield_patterns[pattern] = self.metafield_patterns.get(pattern, 0) + 1
                        
                        # Check for Bunnings URLs
                        if "bunnings.com.au" in value.lower():
                            clean_url = self.extract_clean_url(value)
                            if clean_url and "bunnings.com.au" in clean_url.lower():
                                self.bunnings_urls_found.append({
                                    "product_id": pid,
                                    "product_title": title,
                                    "namespace": namespace,
                                    "key": key,
                                    "url": clean_url,
                                    "original_value": value[:100] + "..." if len(value) > 100 else value
                                })
                
                # Progress indicator
                if i % 10 == 0:
                    print(f"   Processed {i}/{len(products)} products...")
                
                time.sleep(0.1)
            
            print(f"\n✅ Discovery complete!")
            print(f"   Products examined: {len(products)}")
            print(f"   Bunnings URLs found: {len(self.bunnings_urls_found)}")
            
            if self.metafield_patterns:
                print(f"\n📊 Metafield patterns discovered:")
                for pattern, count in sorted(self.metafield_patterns.items(), key=lambda x: x[1], reverse=True):
                    print(f"   {pattern}: {count} occurrences")
            
            return len(self.bunnings_urls_found) > 0
            
        except Exception as e:
            print(f"❌ Discovery error: {e}")
            return False
    
    def find_add_to_cart_button(self):
        """Find Add to Cart button on Bunnings page"""
        try:
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Look for Add to Cart button using multiple strategies
            button_selectors = [
                # Button with text
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add to cart')]",
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add to trolley')]",
                "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add to cart')]",
                "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add to trolley')]",
                # Button with specific classes
                "//button[contains(@class, 'add-to-cart')]",
                "//button[contains(@class, 'addToCart')]",
                "//button[contains(@class, 'btn-cart')]",
                "//button[@data-testid='add-to-cart-button']",
                # Input button
                "//input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add to cart')]",
            ]
            
            for selector in button_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                return True, element
                        except:
                            continue
                except:
                    continue
            
            # Also check for "Buy Online" button which might indicate availability
            buy_online_selectors = [
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'buy online')]",
                "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'buy online')]",
            ]
            
            for selector in buy_online_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                return True, element
                        except:
                            continue
                except:
                    continue
            
            return False, None
            
        except Exception as e:
            print(f"   Button search error: {str(e)[:50]}")
            return False, None
    
    def check_single_url(self, url_info):
        """
        Check if a Bunnings URL is broken
        """
        url = url_info["url"]
        
        result = {
            "product_id": url_info["product_id"],
            "product_title": url_info["product_title"],
            "url": url,
            "page_title": "",
            "status": "not_tested",
            "http_status": None,
            "http_error": None,
            "is_working": False,
            "add_to_cart_found": False,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }
        
        # STEP 1: Fast HTTP check
        print(f"   Checking: {url}")
        http_accessible, http_status, http_error = self.check_http_status(url)
        result["http_status"] = http_status
        result["http_error"] = http_error
        
        if not http_accessible:
            if http_status == 404:
                result["status"] = "BROKEN_404"
            elif http_status == 403:
                result["status"] = "BROKEN_403"
            elif http_status and 500 <= http_status < 600:
                result["status"] = f"BROKEN_SERVER_{http_status}"
            else:
                result["status"] = "BROKEN_HTTP_ERROR"
            return result
        
        # STEP 2: Browser verification
        try:
            if not self.driver:
                self.setup_driver()
            
            self.driver.get(url)
            time.sleep(8)  # Increased wait time for Bunnings page to load
            
            title = self.driver.title
            result["page_title"] = title
            
            # Check if it's actually a Bunnings page
            page_source = self.driver.page_source.lower()
            if "bunnings" not in page_source and "bunnings.com.au" not in title.lower():
                result["status"] = "NOT_BUNNINGS_PAGE"
                return result
            
            # Check for Add to Cart button
            cart_found, cart_element = self.find_add_to_cart_button()
            result["add_to_cart_found"] = cart_found
            
            # Check for out of stock indicators
            page_text = self.driver.page_source.lower()
            out_of_stock_indicators = [
                "out of stock",
                "out-of-stock",
                "sold out",
                "no longer available",
                "discontinued",
                "this product is unavailable",
                "currently unavailable",
                "unavailable online"
            ]
            
            out_of_stock_found = any(indicator in page_text for indicator in out_of_stock_indicators)
            
            # NEW LOGIC: Add to Cart button found = ACTIVE
            if cart_found:
                if out_of_stock_found:
                    result["status"] = "OUT_OF_STOCK"
                    result["is_working"] = False  # Page exists but product is out of stock
                else:
                    result["status"] = "ACTIVE"
                    result["is_working"] = True
            else:
                # No Add to Cart button found
                if out_of_stock_found:
                    result["status"] = "OUT_OF_STOCK"
                elif "404" in page_text or "page not found" in page_text:
                    result["status"] = "BROKEN_JS_404"
                elif "no results found" in page_text or "product not found" in page_text:
                    result["status"] = "PRODUCT_NOT_FOUND"
                else:
                    result["status"] = "NO_ADD_TO_CART"
        
        except Exception as e:
            result["status"] = "BROWSER_ERROR"
            result["error"] = str(e)[:100]
        
        return result
    
    def find_broken_links(self):
        """
        Main function: Find all Bunnings URLs and check which are broken
        """
        print("\n" + "="*60)
        print("🔗 AUTOMATIC BROKEN LINK FINDER")
        print("="*60)
        
        # Test API connection first
        if not self.test_api_connection():
            print("❌ Cannot connect to Shopify. Please check credentials.")
            return
        
        # Step 1: Discover metafield structure
        print("\n🔍 Step 1: Discovering metafield structure...")
        if not self.discover_metafields():
            print("❌ No Bunnings URLs found in products.")
            return
        
        # Step 2: Check all discovered URLs
        print(f"\n🔗 Step 2: Checking {len(self.bunnings_urls_found)} Bunnings URLs...")
        print("="*60)
        
        results = []
        broken_links = []
        active_links = []
        out_of_stock_links = []
        
        for i, url_info in enumerate(self.bunnings_urls_found, 1):
            product_title = url_info["product_title"]
            url = url_info["url"]
            
            print(f"[{i}/{len(self.bunnings_urls_found)}] Product: {product_title[:40]}...")
            
            result = self.check_single_url(url_info)
            results.append(result)
            
            # Classify result based on NEW LOGIC
            if "BROKEN" in result["status"]:
                broken_links.append(result)
                print(f"   ❌ {result['status']}")
            elif result["status"] == "ACTIVE":
                active_links.append(result)
                print(f"   ✅ ACTIVE (Add to Cart button found)")
            elif result["status"] == "OUT_OF_STOCK":
                out_of_stock_links.append(result)
                print(f"   ⚠️  OUT OF STOCK (Page exists but no stock)")
            else:
                print(f"   ⚠️  {result['status']}")
            
            # Small delay between requests
            if i < len(self.bunnings_urls_found):
                time.sleep(3)
        
        # Step 3: Save and display results
        print("\n" + "="*60)
        print("📊 RESULTS SUMMARY (NEW LOGIC)")
        print("="*60)
        
        total = len(results)
        broken = len(broken_links)
        active = len(active_links)
        out_of_stock = len(out_of_stock_links)
        other = total - broken - active - out_of_stock
        
        print(f"Total URLs checked: {total}")
        print(f"✅ Active links (Add to Cart found): {active}")
        print(f"⚠️  Out of stock: {out_of_stock}")
        print(f"❌ Broken links: {broken}")
        print(f"🔍 Other issues: {other}")
        
        # Save detailed results
        self.save_results(results)
        
        # Show broken links
        if broken_links:
            print(f"\n🔍 BROKEN LINKS FOUND ({broken}):")
            print("="*60)
            for link in broken_links[:10]:  # Show first 10
                print(f"\n📦 Product: {link['product_title'][:50]}...")
                print(f"   URL: {link['url']}")
                print(f"   Status: {link['status']}")
                if link['http_error']:
                    print(f"   Error: {link['http_error']}")
            
            if broken > 10:
                print(f"\n   ... and {broken - 10} more broken links")
        
        # Save broken links separately
        if broken_links:
            self.save_broken_links_csv(broken_links)
        
        # Save active links
        if active_links:
            self.save_active_links_csv(active_links)
        
        # Save out of stock links
        if out_of_stock_links:
            self.save_out_of_stock_csv(out_of_stock_links)
        
        return results
    
    def test_api_connection(self):
        """Test Shopify API connection"""
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        
        count_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/count.json"
        
        try:
            r = requests.get(count_url, headers=headers, timeout=10)
            if r.status_code == 200:
                count = r.json().get("count", 0)
                print(f"✅ Connected to: {SHOPIFY_STORE}")
                print(f"   Total products: {count}")
                return True
            else:
                print(f"❌ API Error: {r.status_code}")
                return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def save_results(self, results):
        """Save all results to CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bunnings_url_check_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Product_ID",
                "Product_Title",
                "Bunnings_URL",
                "Page_Title",
                "HTTP_Status",
                "Status",
                "Add_to_Cart_Found",
                "Error",
                "Test_Time"
            ])
            writer.writeheader()
            
            for r in results:
                writer.writerow({
                    "Product_ID": r["product_id"],
                    "Product_Title": r["product_title"][:100],
                    "Bunnings_URL": r["url"],  # Full URL, no truncation
                    "Page_Title": r["page_title"][:150] if r["page_title"] else "",
                    "HTTP_Status": r["http_status"] or "",
                    "Status": r["status"],
                    "Add_to_Cart_Found": "Yes" if r["add_to_cart_found"] else "No",
                    "Error": r["error"] or "",
                    "Test_Time": r["timestamp"]
                })
        
        print(f"\n💾 All results saved to: {filename}")
    
    def save_broken_links_csv(self, broken_links):
        """Save only broken links to a separate CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bunnings_broken_links_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Product_ID",
                "Product_Title",
                "Broken_URL",
                "HTTP_Status",
                "Status",
                "HTTP_Error",
                "Test_Time"
            ])
            writer.writeheader()
            
            for r in broken_links:
                writer.writerow({
                    "Product_ID": r["product_id"],
                    "Product_Title": r["product_title"][:100],
                    "Broken_URL": r["url"],  # Full URL
                    "HTTP_Status": r["http_status"] or "",
                    "Status": r["status"],
                    "HTTP_Error": r["http_error"] or "",
                    "Test_Time": r["timestamp"]
                })
        
        print(f"💾 Broken links saved to: {filename}")
    
    def save_active_links_csv(self, active_links):
        """Save active links to a separate CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bunnings_active_links_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Product_ID",
                "Product_Title",
                "URL",
                "Page_Title",
                "HTTP_Status",
                "Test_Time"
            ])
            writer.writeheader()
            
            for r in active_links:
                writer.writerow({
                    "Product_ID": r["product_id"],
                    "Product_Title": r["product_title"][:100],
                    "URL": r["url"],  # Full URL
                    "Page_Title": r["page_title"][:150] if r["page_title"] else "",
                    "HTTP_Status": r["http_status"] or "",
                    "Test_Time": r["timestamp"]
                })
        
        print(f"💾 Active links saved to: {filename}")
    
    def save_out_of_stock_csv(self, out_of_stock_links):
        """Save out of stock links to a separate CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bunnings_out_of_stock_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Product_ID",
                "Product_Title",
                "URL",
                "Page_Title",
                "HTTP_Status",
                "Test_Time"
            ])
            writer.writeheader()
            
            for r in out_of_stock_links:
                writer.writerow({
                    "Product_ID": r["product_id"],
                    "Product_Title": r["product_title"][:100],
                    "URL": r["url"],  # Full URL
                    "Page_Title": r["page_title"][:150] if r["page_title"] else "",
                    "HTTP_Status": r["http_status"] or "",
                    "Test_Time": r["timestamp"]
                })
        
        print(f"💾 Out of stock links saved to: {filename}")
    
    def close(self):
        """Cleanup"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔗 AUTOMATIC BUNNINGS BROKEN LINK FINDER")
    print("="*60)
    print("NEW LOGIC: Add to Cart button found = ACTIVE link")
    print("="*60)
    print("This script will:")
    print("1. Auto-discover your metafield structure")
    print("2. Find all Bunnings URLs")
    print("3. Check which links are active/broken/out-of-stock")
    print("="*60)
    
    checker = AutoBunningsChecker(headless=True)
    
    try:
        print("\n🚀 Starting automatic broken link check...")
        results = checker.find_broken_links()
        
        if results:
            # Final summary
            active_count = sum(1 for r in results if r["status"] == "ACTIVE")
            broken_count = sum(1 for r in results if "BROKEN" in r["status"])
            out_of_stock_count = sum(1 for r in results if r["status"] == "OUT_OF_STOCK")
            
            print(f"\n" + "="*60)
            print("🎯 FINAL SUMMARY")
            print("="*60)
            print(f"✅ ACTIVE (Add to Cart found): {active_count}")
            print(f"⚠️  OUT OF STOCK: {out_of_stock_count}")
            print(f"❌ BROKEN: {broken_count}")
            
            if broken_count > 0:
                print(f"\n⚠️  ACTION REQUIRED: Found {broken_count} broken Bunnings links!")
                print("   Check the CSV files for details.")
            else:
                print(f"\n✅ SUCCESS: No broken links found!")
        else:
            print("\n❌ No results to report.")
            
    except KeyboardInterrupt:
        print("\n⚠️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        checker.close()
        print("\n✨ Script completed!")
