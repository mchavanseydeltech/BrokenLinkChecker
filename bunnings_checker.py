#!/usr/bin/env python3
"""
Automated Bunnings URL Checker - Shopify Metafields
If Add to Cart button not found, product is set to DRAFT
"""

import time
from datetime import datetime
import requests
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# --------------------------
# HARD-CODED SHOPIFY CREDENTIALS
# --------------------------
SHOPIFY_STORE = "cassien24.myshopify.com"  # Replace with your Shopify store
SHOPIFY_ACCESS_TOKEN = "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"  # Replace with your token

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

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass

# --------------------------
# SHOPIFY FUNCTIONS
# --------------------------
def fetch_products_with_bunnings_url():
    """Fetch products and their Bunnings URLs"""
    products_data = []
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
                        products_data.append({"id": product['id'], "url": mf["value"], "title": product["title"]})
        link_header = resp.headers.get("Link")
        if link_header and 'rel="next"' in link_header:
            next_url = link_header.split(';')[0].strip('<> ')
            endpoint = next_url
        else:
            endpoint = None
    return products_data

def mark_product_as_draft(product_id):
    """Set Shopify product to draft"""
    endpoint = f"https://{SHOPIFY_STORE}/admin/api/2025-10/products/{product_id}.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {"product": {"id": product_id, "status": "draft"}}
    resp = requests.put(endpoint, json=payload, headers=headers)
    if resp.status_code == 200:
        print(f"   📝 Product {product_id} set to DRAFT")
    else:
        print(f"   ❌ Failed to update product {product_id}: {resp.text}")

# --------------------------
# MAIN SCRIPT
# --------------------------
if __name__ == "__main__":
    print("🚀 Fetching products with Bunnings URLs from Shopify...")
    products_data = fetch_products_with_bunnings_url()
    print(f"✅ Found {len(products_data)} products with Bunnings URLs")

    if not products_data:
        print("❌ No products found. Check metafields.")
        exit(0)

    checker = BunningsDirectChecker(headless=False)
    total_working = 0
    total_drafted = 0

    for i, product in enumerate(products_data, 1):
        print(f"\n[{i}/{len(products_data)}] {product['title']}")
        result = checker.check_bunnings_url(product['url'])
        if result['add_to_cart_found']:
            total_working += 1
        else:
            mark_product_as_draft(product['id'])
            total_drafted += 1
        time.sleep(2)

    checker.close()

    print("\n📋 SUMMARY")
    print("="*40)
    print(f"Total Products Tested: {len(products_data)}")
    print(f"✅ Working (Add to Cart found): {total_working}")
    print(f"📝 Drafted Products (Add to Cart NOT found): {total_drafted}")
