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
import undetected_chromedriver as uc

# =========================
# 🔐 SHOPIFY CONFIG (HARDCODED)
# =========================
SHOPIFY_STORE = "seydeltest"
SHOPIFY_TOKEN = "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"
SHOPIFY_API_VERSION = "2024-10"
# =========================

class AutoBunningsChecker:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.session = requests.Session()
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
        
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f'user-agent={user_agent}')
        
        self.driver = uc.Chrome(options=options, use_subprocess=True)
    
    def check_http_status(self, url):
        """
        Fast HTTP check for broken links
        Returns: (is_accessible: bool, status_code: int, error_message: str)
        """
        try:
            try:
                response = self.session.head(url, timeout=15, allow_redirects=True, verify=True)
            except (ConnectionError, SSLError):
                response = self.session.get(url, timeout=15, allow_redirects=True, verify=True, stream=True)
            
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
        
        # STEP 2: Browser verification (only if HTTP check passed)
        try:
            if not self.driver:
                self.setup_driver()
            
            self.driver.get(url)
            time.sleep(5)
            
            title = self.driver.title
            result["page_title"] = title
            page_source = self.driver.page_source.lower()
            
            # Check if it's actually a Bunnings page
            if "bunnings" not in page_source and "bunnings.com.au" not in title.lower():
                result["status"] = "NOT_BUNNINGS_PAGE"
                return result
            
            # Look for Add to Cart button
            cart_found = False
            texts = ["add to cart", "add to trolley"]
            
            for t in texts:
                try:
                    elements = self.driver.find_elements(
                        By.XPATH,
                        f"//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{t}')]"
                    )
                    for element in elements:
                        try:
                            if element.is_displayed():
                                cart_found = True
                                break
                        except:
                            continue
                    if cart_found:
                        break
                except:
                    continue
            
            result["add_to_cart_found"] = cart_found
            
            if cart_found:
                result["status"] = "WORKING"
                result["is_working"] = True
            else:
                # Check for specific issues
                if "out of stock" in page_source:
                    result["status"] = "OUT_OF_STOCK"
                elif "no longer available" in page_source:
                    result["status"] = "DISCONTINUED"
                elif "404" in page_source or "not found" in page_source:
                    result["status"] = "BROKEN_JS_404"
                elif "sold out" in page_source:
                    result["status"] = "SOLD_OUT"
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
        working_links = []
        
        for i, url_info in enumerate(self.bunnings_urls_found, 1):
            product_title = url_info["product_title"]
            url = url_info["url"]
            
            print(f"[{i}/{len(self.bunnings_urls_found)}] Testing: {product_title[:40]}...")
            
            result = self.check_single_url(url_info)
            results.append(result)
            
            # Classify result
            if "BROKEN" in result["status"]:
                broken_links.append(result)
                print(f"   ❌ {result['status']}")
            elif result["is_working"]:
                working_links.append(result)
                print(f"   ✅ WORKING")
            else:
                print(f"   ⚠️ {result['status']}")
            
            # Small delay between requests
            if i < len(self.bunnings_urls_found):
                time.sleep(2)
        
        # Step 3: Save and display results
        print("\n" + "="*60)
        print("📊 RESULTS SUMMARY")
        print("="*60)
        
        total = len(results)
        broken = len(broken_links)
        working = len(working_links)
        other = total - broken - working
        
        print(f"Total URLs checked: {total}")
        print(f"✅ Working links: {working}")
        print(f"❌ Broken links: {broken}")
        print(f"⚠️  Other issues: {other}")
        
        # Save detailed results
        self.save_results(results)
        
        # Show broken links
        if broken_links:
            print(f"\n🔍 BROKEN LINKS FOUND ({broken}):")
            print("="*60)
            for link in broken_links[:10]:  # Show first 10
                print(f"\n📦 Product: {link['product_title'][:50]}...")
                print(f"   URL: {link['url'][:70]}...")
                print(f"   Status: {link['status']}")
                if link['http_error']:
                    print(f"   Error: {link['http_error']}")
            
            if broken > 10:
                print(f"\n   ... and {broken - 10} more broken links")
        
        # Save broken links separately
        if broken_links:
            self.save_broken_links_csv(broken_links)
        
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
        filename = f"bunnings_broken_links_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Product_ID",
                "Product_Title",
                "Bunnings_URL",
                "Page_Title",
                "HTTP_Status",
                "Status",
                "Working",
                "Add_to_Cart_Found",
                "Error",
                "Test_Time"
            ])
            writer.writeheader()
            
            for r in results:
                writer.writerow({
                    "Product_ID": r["product_id"],
                    "Product_Title": r["product_title"][:100],
                    "Bunnings_URL": r["url"],
                    "Page_Title": r["page_title"][:150] if r["page_title"] else "",
                    "HTTP_Status": r["http_status"] or "",
                    "Status": r["status"],
                    "Working": "Yes" if r["is_working"] else "No",
                    "Add_to_Cart_Found": "Yes" if r["add_to_cart_found"] else "No",
                    "Error": r["error"] or "",
                    "Test_Time": r["timestamp"]
                })
        
        print(f"\n💾 All results saved to: {filename}")
    
    def save_broken_links_csv(self, broken_links):
        """Save only broken links to a separate CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bunnings_broken_only_{timestamp}.csv"
        
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
                    "Broken_URL": r["url"],
                    "HTTP_Status": r["http_status"] or "",
                    "Status": r["status"],
                    "HTTP_Error": r["http_error"] or "",
                    "Test_Time": r["timestamp"]
                })
        
        print(f"💾 Broken links saved to: {filename}")
    
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
    print("This script will:")
    print("1. Auto-discover your metafield structure")
    print("2. Find all Bunnings URLs")
    print("3. Check which links are broken")
    print("="*60)
    
    checker = AutoBunningsChecker(headless=True)
    
    try:
        print("\n🚀 Starting automatic broken link check...")
        results = checker.find_broken_links()
        
        if results:
            # Final summary
            broken_count = sum(1 for r in results if "BROKEN" in r["status"])
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
