#!/usr/bin/env python3
"""
Automated Bunnings URL Checker - Shopify Metafields
Fetches Bunnings URLs from Shopify products and checks Add to Cart button
"""

import time
import csv
from datetime import datetime
import requests
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# --------------------------
# HARD-CODED SHOPIFY CREDENTIALS
# --------------------------
SHOPIFY_STORE = "cassien24.myshopify.com"  # e.g., 'myshopify-store.myshopify.com'
SHOPIFY_ACCESS_TOKEN = "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"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "au_link"

# --------------------------
# BUNNINGS CHECKER CLASS
# --------------------------
class BunningsDirectChecker:
    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.notifications": 2,
        })
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f'user-agent={user_agent}')
        self.driver = uc.Chrome(options=options, use_subprocess=True)
        print("✅ Browser ready")

    def check_bunnings_url(self, url):
        print(f"\n🔗 Testing: {url[:80]}...")
        result = {
            'url': url,
            'page_title': 'Not loaded',
            'status': 'not_tested',
            'is_working': False,
            'add_to_cart_found': False,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }

        try:
            self.driver.get(url)
            time.sleep(8)  # initial load
            title = self.driver.title
            result['page_title'] = title
            print(f"   Title: {title[:60]}...")

            # Cloudflare check
            if "Just a moment" in title:
                print("   ⚠️ Cloudflare, waiting 10s...")
                time.sleep(10)
                title = self.driver.title
                if "Just a moment" in title:
                    result['status'] = 'cloudflare_blocked'
                    print("   ❌ Cloudflare blocked")
                    return result

            page_source = self.driver.page_source.lower()
            if not ('bunnings' in page_source or 'bunnings.com.au' in title.lower()):
                result['status'] = 'not_bunnings'
                print("   ❌ Not a Bunnings page")
                return result

            # Look for Add to Cart button
            time.sleep(3)
            add_to_cart_found = False
            cart_texts = ['Add to Cart', 'Add to Trolley', 'Add to cart', 'Add to trolley']
            for text in cart_texts:
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
                    "button.btn--primary"
                ]
                for selector in selectors:
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

            result['add_to_cart_found'] = add_to_cart_found

            # Determine status
            page_text = self.driver.page_source.lower()
            if add_to_cart_found:
                result['status'] = 'working'
                result['is_working'] = True
                print("   ✅ WORKING - Add to Cart found")
            else:
                if 'out of stock' in page_text:
                    result['status'] = 'out_of_stock'
                    print("   ⚠️ OUT OF STOCK")
                elif 'product not found' in page_text or '404' in page_text:
                    result['status'] = 'not_found'
                    print("   ❌ 404 - Product not found")
                elif 'no longer available' in page_text:
                    result['status'] = 'discontinued'
                    print("   ❌ Discontinued")
                else:
                    result['status'] = 'no_add_to_cart'
                    print("   ❌ No Add to Cart button")

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"   ❌ Error: {str(e)[:50]}...")

        return result

    def save_results_csv(self, results, filename):
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Bunnings_URL','Page_Title','Status','Working','Add_to_Cart_Found','Error','Test_Time']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({
                    'Bunnings_URL': r['url'],
                    'Page_Title': r['page_title'][:200] if r['page_title'] else '',
                    'Status': r['status'],
                    'Working': 'Yes' if r['is_working'] else 'No',
                    'Add_to_Cart_Found': 'Yes' if r['add_to_cart_found'] else 'No',
                    'Error': r['error'] or '',
                    'Test_Time': r['timestamp']
                })
        print(f"\n📊 Results saved to: {filename}")

    def print_summary(self, results):
        working = sum(1 for r in results if r['is_working'])
        broken = len(results) - working
        print("\n📋 SUMMARY")
        print("="*40)
        print(f"Total URLs Tested: {len(results)}")
        print(f"✅ Working: {working}")
        print(f"❌ Broken: {broken}")
        status_counts = {}
        for r in results:
            status_counts[r['status']] = status_counts.get(r['status'],0)+1
        print("\n📈 Breakdown by status:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass

# --------------------------
# FETCH SHOPIFY METAFIELDS
# --------------------------
def fetch_bunnings_urls():
    urls = []
    endpoint = f"https://{SHOPIFY_STORE}/admin/api/2025-10/products.json?limit=250"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,"Content-Type":"application/json"}

    while endpoint:
        resp = requests.get(endpoint, headers=headers)
        data = resp.json()
        for product in data.get("products", []):
            mf_resp = requests.get(f"https://{SHOPIFY_STORE}/admin/api/2025-10/products/{product['id']}/metafields.json", headers=headers)
            metafields = mf_resp.json().get("metafields", [])
            for mf in metafields:
                if mf["namespace"] == METAFIELD_NAMESPACE and mf["key"] == METAFIELD_KEY:
                    if mf["value"]:
                        urls.append(mf["value"])
        # Pagination
        link_header = resp.headers.get("Link")
        if link_header and 'rel="next"' in link_header:
            next_url = link_header.split(';')[0].strip('<> ')
            endpoint = next_url
        else:
            endpoint = None
    return urls

# --------------------------
# MAIN SCRIPT
# --------------------------
if __name__ == "__main__":
    print("🚀 Fetching Bunnings URLs from Shopify...")
    bunnings_urls = fetch_bunnings_urls()
    print(f"✅ Found {len(bunnings_urls)} URLs")

    if not bunnings_urls:
        print("❌ No URLs found. Check metafields.")
        exit(0)

    checker = BunningsDirectChecker(headless=False)
    results = []

    for i, url in enumerate(bunnings_urls,1):
        print(f"\n[{i}/{len(bunnings_urls)}]")
        result = checker.check_bunnings_url(url)
        results.append(result)
        time.sleep(2)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    checker.save_results_csv(results, f"bunnings_results_{timestamp}.csv")
    checker.print_summary(results)
    checker.close()
