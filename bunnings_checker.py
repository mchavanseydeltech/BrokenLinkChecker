#!/usr/bin/env python3
"""
Bunnings URL Checker – Shopify Metafield Mode with HTTP Pre-check
Fetches all Bunnings URLs from product metafields and checks them
Adds fast HTTP status check before Selenium verification
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
SHOPIFY_API_VERSION = "2025-10"

# Try different possible namespace/key combinations
METAFIELD_CONFIGS = [
    {"namespace": "custom", "key": "bunnings_au_link"},
    {"namespace": "global", "key": "bunnings_url"},
    {"namespace": "bunnings", "key": "url"},
    {"namespace": "references", "key": "bunnings"},
    # Add more possible configurations here
]

class BunningsChecker:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.session = requests.Session()  # HTTP session for status checks
        self.setup_driver()

    def setup_driver(self):
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.notifications": 2,
        })
        options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
        self.driver = uc.Chrome(options=options, use_subprocess=True)
        print("✅ Browser ready")

    def check_http_status(self, url):
        """
        Check URL accessibility via HTTP request
        Returns: (is_accessible: bool, status_code: int, error_message: str)
        """
        try:
            # Try HEAD first (faster), fall back to GET if needed
            try:
                response = self.session.head(url, timeout=15, allow_redirects=True, verify=True)
            except (ConnectionError, SSLError):
                response = self.session.get(url, timeout=15, allow_redirects=True, verify=True, stream=True)
            
            status_code = response.status_code
            
            # Consider 2xx and 3xx as accessible[citation:6]
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

    def extract_url_from_value(self, value):
        """Extract URL from various possible formats"""
        if not value:
            return None
        
        # Clean the value
        value = str(value).strip()
        
        # Try to parse as JSON
        try:
            data = json.loads(value)
            if isinstance(data, dict):
                # Look for URL in common keys
                for key in ['url', 'link', 'href', 'bunnings_url', 'source']:
                    if key in data and data[key]:
                        url = str(data[key]).strip()
                        if self.is_bunnings_url(url):
                            return url
                # Check all string values in the JSON
                for val in data.values():
                    if isinstance(val, str) and self.is_bunnings_url(val):
                        return val.strip()
        except:
            pass
        
        # Check if it's already a URL
        if self.is_bunnings_url(value):
            return value
        
        # Try to extract URL from text[citation:3]
        url_pattern = r'https?://[^\s<>"\']+'
        matches = re.findall(url_pattern, value)
        for match in matches:
            if self.is_bunnings_url(match):
                return match
        
        return None

    def is_bunnings_url(self, text):
        """Check if text contains Bunnings URL"""
        return "bunnings.com.au" in str(text).lower()

    def fetch_bunnings_urls(self):
        """Fetch all Bunnings URLs from Shopify product metafields"""
        print("\n🔗 Fetching URLs from Shopify product metafields...")
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        urls_with_product_info = []  # Store with product info
        endpoint = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
        params = {"limit": 250, "status": "any"}
        product_count = 0

        while endpoint:
            r = requests.get(endpoint, headers=headers, params=params)
            r.raise_for_status()
            products = r.json().get("products", [])
            if not products:
                break

            product_count += len(products)
            print(f"📦 Processing {len(products)} products (total: {product_count})...")

            for product in products:
                pid = product["id"]
                title = product.get("title", "N/A")
                handle = product.get("handle", "")
                
                mf_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{pid}/metafields.json"
                mf_resp = requests.get(mf_url, headers=headers)
                
                if mf_resp.status_code != 200:
                    continue
                    
                metafields = mf_resp.json().get("metafields", [])

                for mf in metafields:
                    value = mf.get("value", "")
                    if not value:
                        continue
                    
                    # Try to extract URL from value
                    extracted_url = self.extract_url_from_value(value)
                    if extracted_url:
                        urls_with_product_info.append({
                            "product_id": pid,
                            "product_title": title,
                            "product_handle": handle,
                            "url": extracted_url,
                            "metafield_namespace": mf.get("namespace", ""),
                            "metafield_key": mf.get("key", "")
                        })
                        print(f"  ✅ Found URL for '{title[:30]}...': {extracted_url[:60]}...")

            # Pagination
            link = r.headers.get("Link")
            if link and 'rel="next"' in link:
                endpoint = link.split(";")[0].strip("<> ")
                params = None
            else:
                endpoint = None
                
            time.sleep(0.5)  # Avoid rate limiting

        print(f"\n✅ Found {len(urls_with_product_info)} Bunnings URLs from {product_count} products\n")
        return urls_with_product_info

    def check_bunnings_url(self, url_info):
        """
        Check a Bunnings URL: HTTP check first, then Selenium if needed
        """
        url = url_info["url"]
        print(f"\n🔗 Testing: {url[:60]}...")
        
        result = {
            "product_id": url_info["product_id"],
            "product_title": url_info["product_title"],
            "product_handle": url_info["product_handle"],
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
        
        # ===== STEP 1: FAST HTTP STATUS CHECK =====
        http_accessible, http_status, http_error = self.check_http_status(url)
        result["http_status"] = http_status
        result["http_error"] = http_error
        
        if not http_accessible:
            # Mark as broken based on HTTP status[citation:6]
            if http_status == 404:
                result["status"] = "broken_404"
                print(f"   ❌ BROKEN - Page not found (HTTP 404)")
            elif http_status == 403:
                result["status"] = "broken_403"
                print(f"   ❌ BROKEN - Access forbidden (HTTP 403)")
            elif http_status and 500 <= http_status < 600:
                result["status"] = "broken_server_error"
                print(f"   ❌ BROKEN - Server error (HTTP {http_status})")
            else:
                result["status"] = "broken_http_error"
                print(f"   ❌ BROKEN - {http_error}")
            return result
        
        print(f"   ✓ Link accessible (HTTP {http_status})")
        
        # ===== STEP 2: SELENIUM BROWSER VERIFICATION =====
        try:
            self.driver.get(url)
            time.sleep(8)
            title = self.driver.title
            page = self.driver.page_source.lower()
            result["page_title"] = title

            if "bunnings" not in page:
                result["status"] = "not_bunnings"
                print("   ❌ Not a Bunnings page")
                return result

            add_found = False
            texts = ["add to cart", "add to trolley"]
            for t in texts:
                elems = self.driver.find_elements(
                    By.XPATH,
                    f"//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{t}')]"
                )
                for e in elems:
                    if e.is_displayed():
                        add_found = True
                        break
                if add_found:
                    break

            result["add_to_cart_found"] = add_found
            if add_found:
                result["status"] = "working"
                result["is_working"] = True
                print("   ✅ WORKING - Add to Cart found")
            elif "out of stock" in page:
                result["status"] = "out_of_stock"
                print("   ⚠️ OUT OF STOCK")
            elif "no longer available" in page:
                result["status"] = "discontinued"
                print("   ❌ Discontinued")
            elif "404" in page or "not found" in page:
                result["status"] = "broken_js_404"
                print("   ❌ BROKEN - JavaScript 404")
            else:
                result["status"] = "no_add_to_cart"
                print("   ❌ No Add to Cart button")

        except Exception as e:
            result["status"] = "selenium_error"
            result["error"] = str(e)
            print(f"   ❌ Selenium Error: {str(e)[:50]}...")
        
        return result

    def bulk_test(self):
        """Main function to test all Bunnings URLs"""
        print("\n🏪 BUNNINGS CHECKER – SHOPIFY METAFIELD MODE")
        print("="*60)
        
        # Fetch all URLs with product info
        url_list = self.fetch_bunnings_urls()
        
        if not url_list:
            print("\n❌ No URLs found. Please check:")
            print("   1. Metafield namespace/key in METAFIELD_CONFIGS")
            print("   2. Your Shopify credentials")
            print("   3. If products actually have Bunnings URLs")
            return

        print(f"\n🚀 Starting tests for {len(url_list)} URLs...")
        print("="*60)
        
        results = []
        broken_count = 0
        working_count = 0
        
        for i, url_info in enumerate(url_list, 1):
            print(f"[{i}/{len(url_list)}] Product: {url_info['product_title'][:40]}...")
            result = self.check_bunnings_url(url_info)
            results.append(result)
            
            # Track counts
            if result['is_working']:
                working_count += 1
            elif 'broken' in result['status']:
                broken_count += 1
            
            # Delay between tests
            if i < len(url_list):
                time.sleep(3)  # Increased delay for reliability

        # Save results
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bunnings_shopify_results_{ts}.csv"
        self.save_results_csv(results, filename)
        
        # Print summary
        self.print_summary(results)
        
        return results

    def save_results_csv(self, results, filename):
        """Save detailed results to CSV"""
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Product_ID",
                    "Product_Title",
                    "Product_Handle",
                    "Bunnings_URL",
                    "Page_Title",
                    "HTTP_Status",
                    "HTTP_Error",
                    "Status",
                    "Working",
                    "Add_to_Cart_Found",
                    "Error",
                    "Test_Time",
                ],
            )
            writer.writeheader()
            for r in results:
                writer.writerow({
                    "Product_ID": r["product_id"],
                    "Product_Title": r["product_title"][:100],
                    "Product_Handle": r["product_handle"],
                    "Bunnings_URL": r["url"],
                    "Page_Title": r["page_title"][:150] if r["page_title"] else "",
                    "HTTP_Status": r["http_status"] or "",
                    "HTTP_Error": r["http_error"] or "",
                    "Status": r["status"],
                    "Working": "Yes" if r["is_working"] else "No",
                    "Add_to_Cart_Found": "Yes" if r["add_to_cart_found"] else "No",
                    "Error": r["error"] or "",
                    "Test_Time": r["timestamp"],
                })
        print(f"\n📊 CSV saved: {filename}")

    def print_summary(self, results):
        """Print comprehensive summary"""
        if not results:
            return
        
        working = sum(1 for r in results if r["is_working"])
        broken = sum(1 for r in results if 'broken' in r["status"])
        other = len(results) - working - broken
        
        print("\n" + "="*60)
        print("📋 TEST SUMMARY")
        print("="*60)
        print(f"Total URLs Tested: {len(results)}")
        print(f"✅ Working (Add to Cart found): {working}")
        print(f"❌ Broken Links: {broken}")
        print(f"⚠️  Other Issues (out of stock, no cart, etc.): {other}")
        
        # Breakdown by status
        status_counts = {}
        for r in results:
            status = r["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\n📈 Detailed Breakdown:")
        for status, count in sorted(status_counts.items()):
            indicator = "❌" if 'broken' in status else ("✅" if status == 'working' else "⚠️")
            print(f"  {indicator} {status}: {count}")
        
        # List broken links
        broken_links = [r for r in results if 'broken' in r["status"]]
        if broken_links:
            print(f"\n🔍 Broken Links Found ({len(broken_links)}):")
            for r in broken_links[:10]:  # Show first 10
                print(f"  • {r['product_title'][:40]}...")
                print(f"    URL: {r['url'][:60]}...")
                print(f"    Reason: {r['status']} ({r['http_error'] or 'No HTTP error'})")
                print()
            
            if len(broken_links) > 10:
                print(f"  ... and {len(broken_links) - 10} more")

    def close(self):
        """Cleanup"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass


# ===== MAIN =====
if __name__ == "__main__":
    checker = BunningsChecker(headless=True)
    try:
        checker.bulk_test()
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        checker.close()
        print("\n✨ Done!")
