#!/usr/bin/env python3
"""
Bunnings URL Checker – Shopify Metafield Mode
Fetches all Bunnings URLs from product metafields (all products)
Detects URLs in plain text or JSON, with debug printing
Checks each URL for Add to Cart button using Selenium (headless)
"""

import time
import csv
import requests
import json
import re
from datetime import datetime
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
# =========================

class BunningsChecker:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
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
        
        # Try to extract URL from text
        url_pattern = r'https?://[^\s<>"\']+'
        matches = re.findall(url_pattern, value)
        for match in matches:
            if self.is_bunnings_url(match):
                return match
        
        return None

    def is_bunnings_url(self, text):
        """Check if text contains Bunnings URL"""
        return "bunnings.com.au" in str(text).lower()

    def fetch_all_metafields_debug(self):
        """Debug function to see ALL metafields"""
        print("\n🔍 DEBUG: Fetching ALL metafields from ALL products...")
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        
        endpoint = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
        params = {"limit": 10, "fields": "id,title"}  # Start with 10 products for debugging
        
        try:
            r = requests.get(endpoint, headers=headers, params=params)
            r.raise_for_status()
            products = r.json().get("products", [])
            
            print(f"\n📦 Found {len(products)} products")
            
            all_metafields = []
            for product in products:
                pid = product["id"]
                title = product.get("title", "N/A")
                print(f"\n{'='*60}")
                print(f"Product ID: {pid}")
                print(f"Title: {title}")
                print(f"{'='*60}")
                
                # Get metafields for this product
                mf_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{pid}/metafields.json"
                mf_resp = requests.get(mf_url, headers=headers)
                
                if mf_resp.status_code == 200:
                    metafields = mf_resp.json().get("metafields", [])
                    print(f"Found {len(metafields)} metafields:")
                    
                    for mf in metafields:
                        namespace = mf.get("namespace", "")
                        key = mf.get("key", "")
                        value = mf.get("value", "")[:100]  # First 100 chars
                        mf_type = mf.get("type", "")
                        
                        print(f"  - {namespace}.{key} ({mf_type}): {value}")
                        
                        # Check if this looks like a Bunnings URL
                        if self.is_bunnings_url(value):
                            print(f"    ⭐ CONTAINS BUNNINGS URL!")
                            extracted = self.extract_url_from_value(value)
                            if extracted:
                                print(f"    ✨ Extracted URL: {extracted}")
                                all_metafields.append({
                                    "product_id": pid,
                                    "product_title": title,
                                    "namespace": namespace,
                                    "key": key,
                                    "value": value,
                                    "extracted_url": extracted
                                })
                else:
                    print(f"  ❌ Failed to fetch metafields: {mf_resp.status_code}")
                
                time.sleep(0.5)  # Avoid rate limiting
            
            return all_metafields
            
        except Exception as e:
            print(f"❌ Error in debug mode: {e}")
            return []

    def fetch_bunnings_urls(self):
        print("\n🔗 Fetching URLs from Shopify product metafields...")
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        urls = []
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
                        urls.append(extracted_url)
                        print(f"  ✅ Found URL in {mf.get('namespace')}.{mf.get('key')}: {extracted_url[:80]}...")

            # Pagination
            link = r.headers.get("Link")
            if link and 'rel="next"' in link:
                endpoint = link.split(";")[0].strip("<> ")
                params = None
            else:
                endpoint = None
                
            time.sleep(0.5)  # Avoid rate limiting

        urls = list(set(urls))  # Remove duplicates
        print(f"\n✅ Found {len(urls)} unique Bunnings URLs\n")
        return urls

    def check_bunnings_url(self, url):
        print(f"\n🔗 Testing: {url[:80]}")
        result = {
            "url": url,
            "page_title": "",
            "status": "",
            "is_working": False,
            "add_to_cart_found": False,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.driver.get(url)
            time.sleep(8)
            title = self.driver.title
            page = self.driver.page_source.lower()
            result["page_title"] = title

            if "bunnings" not in page:
                result["status"] = "not_bunnings"
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
            elif "out of stock" in page:
                result["status"] = "out_of_stock"
            elif "no longer available" in page:
                result["status"] = "discontinued"
            elif "404" in page:
                result["status"] = "not_found"
            else:
                result["status"] = "no_add_to_cart"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def bulk_test(self):
        # First, run debug to see what metafields exist
        debug_data = self.fetch_all_metafields_debug()
        
        if debug_data:
            print(f"\n📊 DEBUG SUMMARY: Found {len(debug_data)} metafields containing Bunnings URLs")
            for item in debug_data:
                print(f"  - Product: {item['product_title']} ({item['product_id']})")
                print(f"    Metafield: {item['namespace']}.{item['key']}")
                print(f"    URL: {item['extracted_url'][:100]}...")
        
        # Now fetch all URLs properly
        urls = self.fetch_bunnings_urls()
        
        if not urls:
            print("\n❌ No URLs found. Possible issues:")
            print("   1. Metafields might have different namespace/key")
            print("   2. URLs might be stored in a different format")
            print("   3. No products have Bunnings URLs yet")
            print("\n💡 Check the debug output above to see your actual metafield structure.")
            print("   Then update the METAFIELD_CONFIGS list in the script.")
            return

        results = []
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}]", end=" ")
            results.append(self.check_bunnings_url(url))
            time.sleep(2)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"shopify_bunnings_results_{ts}.csv"
        self.save_results_csv(results, filename)
        self.print_summary(results)

    def save_results_csv(self, results, filename):
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Bunnings_URL",
                    "Page_Title",
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
                    "Bunnings_URL": r["url"],
                    "Page_Title": r["page_title"][:200],
                    "Status": r["status"],
                    "Working": "Yes" if r["is_working"] else "No",
                    "Add_to_Cart_Found": "Yes" if r["add_to_cart_found"] else "No",
                    "Error": r["error"] or "",
                    "Test_Time": r["timestamp"],
                })
        print(f"\n📊 CSV saved: {filename}")

    def print_summary(self, results):
        working = sum(1 for r in results if r["is_working"])
        broken = len(results) - working
        print("\n📋 SUMMARY")
        print(f"Total URLs Tested: {len(results)}")
        print(f"✅ Working: {working}")
        print(f"❌ Broken: {broken}")

        status_counts = {}
        for r in results:
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

        print("\n📈 Breakdown by status:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass


# ===== MAIN =====
if __name__ == "__main__":
    print("\n🏪 BUNNINGS CHECKER – SHOPIFY METAFIELD MODE")
    print("🔍 Running in DEBUG mode first to detect metafield structure...")
    
    checker = BunningsChecker(headless=True)  # headless for GitHub Actions
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
