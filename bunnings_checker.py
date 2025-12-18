#!/usr/bin/env python3
"""
COMBINED BUNNINGS LINK CHECKER - FIXED VERSION
- Extracts Bunnings URLs from Shopify metafields (from File 1)
- Uses enhanced detection logic (from File 2) to check product availability
- FIXED: Removes ... from URLs before testing
"""

import time
import csv
import json
import re
import os
import requests
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

class CombinedBunningsChecker:
    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None
        self.session = requests.Session()
        self.bunnings_urls_found = []
        self.metafield_patterns = {}
        
    def setup_driver(self):
        """Setup browser with File 2's better configuration"""
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument('--headless=new')
            
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            
            # Block location and notifications (from File 2)
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.geolocation": 2,
                "profile.default_content_setting_values.notifications": 2,
            })
            
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options.add_argument(f'user-agent={user_agent}')
            
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            
            print("✅ Browser ready")
            
        except Exception as e:
            print(f"❌ Browser error: {e}")
            raise
    
    def clean_url(self, url):
        """
        Clean URL by removing ellipsis (...) and fixing common issues
        """
        if not url:
            return ""
        
        url = str(url).strip()
        
        # Remove trailing ellipsis (...)
        url = re.sub(r'\.\.\.+$', '', url)
        
        # Remove trailing dots that aren't part of domain
        if url.endswith('.') and not url.endswith('.com.au.'):
            url = url[:-1]
        
        # Remove any trailing spaces
        url = url.rstrip()
        
        # Ensure it starts with http:// or https://
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Remove any URL-encoded ellipsis
        url = url.replace('%2E%2E%2E', '')
        
        return url
    
    def extract_clean_url(self, value):
        """Extract clean URL from various formats (from File 1) - FIXED VERSION"""
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
                            return self.clean_url(url)
        except:
            pass
        
        # Look for URL pattern
        url_pattern = r'https?://[^\s<>"\']+'
        matches = re.findall(url_pattern, value)
        for match in matches:
            if "bunnings.com.au" in match.lower():
                return self.clean_url(match)
        
        # If no pattern found but contains bunnings.com.au, try to extract
        if "bunnings.com.au" in value.lower():
            # Find the URL part
            start = value.lower().find("bunnings.com.au")
            if start > 0:
                # Go back to find the start of URL
                http_start = value.rfind('http', 0, start)
                if http_start != -1:
                    url_part = value[http_start:]
                    # Take until next space or end
                    space_pos = url_part.find(' ')
                    if space_pos != -1:
                        url_part = url_part[:space_pos]
                    return self.clean_url(url_part)
        
        return self.clean_url(value)
    
    def check_http_status(self, url):
        """
        Fast HTTP check for broken links (from File 1)
        Returns: (is_accessible: bool, status_code: int, error_message: str)
        """
        try:
            # Clean the URL first
            url = self.clean_url(url)
            
            # Add headers to look more like a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
            
            try:
                response = self.session.head(url, timeout=15, allow_redirects=True, verify=True, headers=headers)
            except (ConnectionError, SSLError):
                response = self.session.get(url, timeout=15, allow_redirects=True, verify=True, stream=True, headers=headers)
            
            status_code = response.status_code
            
            if 200 <= status_code < 400:
                return True, status_code, None
            elif status_code == 404:
                return False, status_code, "Page not found (404)"
            elif status_code == 403:
                # Try with a GET request instead of HEAD
                try:
                    response = self.session.get(url, timeout=15, allow_redirects=True, verify=True, headers=headers)
                    if 200 <= response.status_code < 400:
                        return True, response.status_code, "Works with GET"
                    else:
                        return False, response.status_code, f"HTTP {response.status_code} with GET"
                except:
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
    
    def discover_metafields(self, max_products=50):
        """
        Automatically discover how Bunnings URLs are stored (from File 1)
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
                                # Clean the URL again to be sure
                                clean_url = self.clean_url(clean_url)
                                
                                print(f"   Found: {title[:30]}... -> {clean_url[:60]}...")
                                
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
            
            # Show first few URLs to verify they're clean
            if self.bunnings_urls_found:
                print(f"\n📋 Sample of cleaned URLs:")
                for i, url_info in enumerate(self.bunnings_urls_found[:5], 1):
                    print(f"   {i}. {url_info['url'][:80]}...")
            
            if self.metafield_patterns:
                print(f"\n📊 Metafield patterns discovered:")
                for pattern, count in sorted(self.metafield_patterns.items(), key=lambda x: x[1], reverse=True):
                    print(f"   {pattern}: {count} occurrences")
            
            return len(self.bunnings_urls_found) > 0
            
        except Exception as e:
            print(f"❌ Discovery error: {e}")
            return False
    
    def check_bunnings_url(self, url_info):
        """
        ENHANCED CHECK: Using File 2's better detection logic
        """
        url = url_info["url"]
        product_title = url_info["product_title"]
        
        # Clean URL one more time before testing
        url = self.clean_url(url)
        
        print(f"\n🔗 Testing: {product_title[:40]}...")
        print(f"   URL: {url[:80]}...")
        
        result = {
            'product_id': url_info['product_id'],
            'product_title': product_title,
            'url': url,
            'page_title': 'Not loaded',
            'status': 'not_tested',
            'is_working': False,
            'add_to_cart_found': False,
            'error': None,
            'http_status': None,
            'http_error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        # First, do a quick HTTP check (from File 1)
        http_accessible, http_status, http_error = self.check_http_status(url)
        result["http_status"] = http_status
        result["http_error"] = http_error
        
        if not http_accessible:
            if http_status == 404:
                result['status'] = 'BROKEN_404'
                print(f"   ❌ BROKEN_404")
            elif http_status == 403:
                # Try a different approach for 403 - sometimes it's a false positive
                print(f"   ⚠️  Got 403, trying browser check anyway...")
                # We'll continue to browser check
            elif http_status and 500 <= http_status < 600:
                result['status'] = f'BROKEN_SERVER_{http_status}'
                print(f"   ❌ BROKEN_SERVER_{http_status}")
                return result
            else:
                result['status'] = 'BROKEN_HTTP_ERROR'
                print(f"   ❌ BROKEN_HTTP_ERROR: {http_error}")
                return result
        
        # If HTTP check passed OR it was 403 (might be false positive), do browser verification
        try:
            if not self.driver:
                self.setup_driver()
            
            # 1. Load the URL
            print(f"   Loading in browser...")
            self.driver.get(url)
            time.sleep(8)  # Wait for initial load (File 2 timing)
            
            # 2. Get page title
            title = self.driver.title
            result['page_title'] = title
            print(f"   Title: {title[:60]}...")
            
            # 3. Check for Cloudflare (from File 2)
            if "Just a moment" in title:
                print("   ⚠️ Cloudflare, waiting...")
                time.sleep(10)
                title = self.driver.title
                
                if "Just a moment" in title:
                    result['status'] = 'cloudflare_blocked'
                    print("   ❌ Cloudflare blocked")
                    return result
            
            # 4. Check if it's a Bunnings page
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()
            if not ('bunnings' in page_source or 'bunnings.com.au' in title.lower() or 'bunnings.com.au' in current_url.lower()):
                result['status'] = 'NOT_BUNNINGS_PAGE'
                print("   ❌ Not a Bunnings page")
                print(f"   Current URL: {current_url[:80]}...")
                return result
            
            # 5. Look for Add to Cart button (File 2's enhanced detection)
            time.sleep(3)
            
            # Method 1: Search for button text (File 2)
            add_to_cart_found = False
            
            cart_texts = ['Add to Cart', 'Add to Trolley', 'Add to cart', 'Add to trolley', 'ADD TO CART']
            for text in cart_texts:
                try:
                    elements = self.driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                    for element in elements:
                        try:
                            if element.is_displayed():
                                add_to_cart_found = True
                                print(f"   ✓ Found: '{text}'")
                                break
                        except:
                            continue
                    if add_to_cart_found:
                        break
                except:
                    continue
            
            # Method 2: Search for common selectors (File 2)
            if not add_to_cart_found:
                selectors = [
                    "button[data-testid='add-to-cart']",
                    "button[data-test-id='add-to-cart']",
                    ".add-to-cart-button",
                    ".add-to-cart",
                    "#add-to-cart",
                    "[aria-label*='Add to cart']",
                    "[aria-label*='Add to trolley']",
                    "button.btn-primary",
                    "button.btn--primary",
                    "button[type='submit']",
                    "button:contains('Add')"
                ]
                
                for selector in selectors:
                    try:
                        if ":contains" in selector:
                            # Handle pseudo selector
                            continue
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            try:
                                if element.is_displayed():
                                    text = element.text.lower()
                                    if 'add to' in text or 'cart' in text or 'trolley' in text:
                                        add_to_cart_found = True
                                        print(f"   ✓ Found via: {selector}")
                                        break
                            except:
                                continue
                        if add_to_cart_found:
                            break
                    except:
                        continue
            
            result['add_to_cart_found'] = add_to_cart_found
            
            # 6. Determine result (File 2's better categorization)
            if add_to_cart_found:
                result['status'] = 'WORKING'
                result['is_working'] = True
                print("   ✅ WORKING - Add to Cart found")
            else:
                # Check why not working (File 2's detailed checks)
                page_text = self.driver.page_source.lower()
                
                if 'out of stock' in page_text:
                    result['status'] = 'OUT_OF_STOCK'
                    print("   ⚠️ OUT OF STOCK")
                elif 'product not found' in page_text or '404' in page_text or 'page not found' in page_text:
                    result['status'] = 'PRODUCT_NOT_FOUND'
                    print("   ❌ 404 - Product not found")
                elif 'no longer available' in page_text or 'discontinued' in page_text:
                    result['status'] = 'DISCONTINUED'
                    print("   ❌ Discontinued")
                elif 'sold out' in page_text:
                    result['status'] = 'SOLD_OUT'
                    print("   ⚠️ SOLD OUT")
                elif 'access denied' in page_text or '403' in page_text:
                    result['status'] = 'ACCESS_DENIED'
                    print("   ❌ Access Denied")
                else:
                    # Take screenshot for debugging
                    timestamp = datetime.now().strftime("%H%M%S")
                    screenshot_file = f"screenshot_{product_title[:20]}_{timestamp}.png"
                    try:
                        self.driver.save_screenshot(screenshot_file)
                        print(f"   📸 Screenshot saved: {screenshot_file}")
                    except:
                        pass
                    
                    result['status'] = 'NO_ADD_TO_CART'
                    print("   ❌ No Add to Cart button")
            
        except Exception as e:
            result['status'] = 'BROWSER_ERROR'
            result['error'] = str(e)[:100]
            print(f"   ❌ Browser Error: {str(e)[:50]}...")
        
        return result
    
    # Rest of the methods remain the same...
    # test_api_connection, run_complete_check, save_results, etc.
    
    def test_api_connection(self):
        """Test Shopify API connection (from File 1)"""
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
    
    def run_complete_check(self):
        """
        Main function: Find Bunnings URLs from metafields and check them
        """
        print("\n" + "="*60)
        print("🔗 COMBINED BUNNINGS LINK CHECKER - FIXED")
        print("="*60)
        print("This script will:")
        print("1. Discover Bunnings URLs from Shopify metafields")
        print("2. CLEAN URLs (remove ...)")
        print("3. Check each URL with enhanced detection")
        print("4. Save detailed results")
        print("="*60)
        
        # Test API connection first
        if not self.test_api_connection():
            print("❌ Cannot connect to Shopify. Please check credentials.")
            return []
        
        # Step 1: Discover metafield structure
        print("\n🔍 Step 1: Discovering and cleaning metafield URLs...")
        if not self.discover_metafields():
            print("❌ No Bunnings URLs found in products.")
            return []
        
        # Step 2: Check all discovered URLs with enhanced detection
        print(f"\n🔗 Step 2: Checking {len(self.bunnings_urls_found)} Bunnings URLs...")
        print("="*60)
        
        results = []
        
        for i, url_info in enumerate(self.bunnings_urls_found, 1):
            result = self.check_bunnings_url(url_info)
            results.append(result)
            
            # Small delay between requests
            if i < len(self.bunnings_urls_found):
                time.sleep(2)
        
        # Step 3: Save and display results
        self.save_results(results)
        self.print_summary(results)
        
        return results
    
    def save_results(self, results):
        """Save all results to CSV with enhanced fields"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bunnings_combined_results_{timestamp}.csv"
        
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
                "Test_Time",
                "Metafield_Namespace",
                "Metafield_Key"
            ])
            writer.writeheader()
            
            for r in results:
                # Find the original metafield info for this result
                metafield_info = None
                for url_info in self.bunnings_urls_found:
                    if url_info['product_id'] == r['product_id'] and url_info['url'] == r['url']:
                        metafield_info = url_info
                        break
                
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
                    "Test_Time": r["timestamp"],
                    "Metafield_Namespace": metafield_info["namespace"] if metafield_info else "",
                    "Metafield_Key": metafield_info["key"] if metafield_info else ""
                })
        
        print(f"\n💾 Complete results saved to: {filename}")
        
        # Also save broken links separately
        broken_links = [r for r in results if not r["is_working"]]
        if broken_links:
            self.save_broken_links_csv(broken_links)
    
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
                "Page_Title",
                "Error",
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
                    "Page_Title": r["page_title"][:100] if r["page_title"] else "",
                    "Error": r["error"] or "",
                    "Test_Time": r["timestamp"]
                })
        
        print(f"💾 Broken links saved to: {filename}")
    
    def print_summary(self, results):
        """Print summary statistics (enhanced from File 2)"""
        if not results:
            return
        
        working = sum(1 for r in results if r['is_working'])
        broken = len(results) - working
        
        print("\n" + "="*60)
        print("📋 SUMMARY")
        print("="*60)
        print(f"Total URLs Tested: {len(results)}")
        print(f"✅ Working: {working}")
        print(f"❌ Not Working: {broken}")
        
        # Detailed breakdown
        status_counts = {}
        for r in results:
            status = r['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\n📈 Detailed Breakdown:")
        print("-" * 40)
        
        # Group similar statuses
        status_groups = {
            "Working": ["WORKING"],
            "Out of Stock": ["OUT_OF_STOCK", "SOLD_OUT"],
            "Product Issues": ["PRODUCT_NOT_FOUND", "DISCONTINUED", "NO_ADD_TO_CART", "NOT_BUNNINGS_PAGE"],
            "HTTP Errors": ["BROKEN_404", "BROKEN_403", "BROKEN_SERVER_", "BROKEN_HTTP_ERROR", "ACCESS_DENIED"],
            "Technical Issues": ["cloudflare_blocked", "BROWSER_ERROR", "error", "not_tested"]
        }
        
        for group_name, status_list in status_groups.items():
            group_count = 0
            for status in status_list:
                for key, value in status_counts.items():
                    if key.startswith(status) if "_" in status else status in key:
                        group_count += value
            
            if group_count > 0:
                print(f"  {group_name}: {group_count}")
        
        # Show individual statuses for debugging
        print("\n🔍 All Status Codes:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
    
    def close(self):
        """Cleanup"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass


# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔗 COMBINED BUNNINGS LINK CHECKER - FIXED")
    print("="*60)
    print("Starting combined checker...")
    print("FIX: Removing ... from URLs before testing")
    print("="*60)
    
    checker = CombinedBunningsChecker(headless=False)  # Set to True for headless
    
    try:
        results = checker.run_complete_check()
        
        if results:
            broken_count = sum(1 for r in results if not r['is_working'])
            if broken_count > 0:
                print(f"\n⚠️  ACTION REQUIRED: Found {broken_count} non-working Bunnings links!")
                print("   Check the CSV files for details.")
            else:
                print(f"\n✅ SUCCESS: All links are working!")
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
