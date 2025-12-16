#!/usr/bin/env python3
"""
Bunnings URL Checker - SHOPIFY AUTOMATION
Uses ORIGINAL detection logic
Automatically drafts Shopify products if Add to Cart not found
"""

import time
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# =========================
# 🔐 SHOPIFY CONFIG (HARD-CODED)
# =========================
SHOPIFY_STORE = "cassien24.myshopify.com"
SHOPIFY_TOKEN = "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"
API_VERSION = "2025-10"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "au_link"

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json"
}

# =========================
# 🚀 BROWSER (UNCHANGED LOGIC)
# =========================
class BunningsDirectChecker:
    def __init__(self):
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.notifications": 2,
        })

        options.add_argument(
            "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        self.driver = uc.Chrome(options=options, use_subprocess=True)
        print("✅ Browser ready")

    # ===== YOUR ORIGINAL LOGIC (MINIMALLY TOUCHED) =====
    def check_bunnings_url(self, url):
        print(f"\n🔗 Testing: {url[:80]}...")

        try:
            self.driver.get(url)
            time.sleep(8)

            title = self.driver.title
            print(f"   Title: {title[:60]}")

            if "Just a moment" in title:
                print("   ⚠️ Cloudflare detected")
                time.sleep(10)
                if "Just a moment" in self.driver.title:
                    return False, "cloudflare_blocked"

            page_source = self.driver.page_source.lower()

            if not ('bunnings' in page_source or 'bunnings.com.au' in title.lower()):
                return False, "not_bunnings"

            # --- Add to Cart detection ---
            add_to_cart_found = False

            cart_texts = ['add to cart', 'add to trolley']
            for text in cart_texts:
                elements = self.driver.find_elements(
                    By.XPATH,
                    f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
                )
                for el in elements:
                    if el.is_displayed():
                        add_to_cart_found = True
                        break
                if add_to_cart_found:
                    break

            if not add_to_cart_found:
                selectors = [
                    "button[data-testid='add-to-cart']",
                    "button[data-test-id='add-to-cart']",
                    "[aria-label*='Add to cart']",
                    "[aria-label*='Add to trolley']",
                    "button.btn-primary"
                ]
                for selector in selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            add_to_cart_found = True
                            break
                    if add_to_cart_found:
                        break

            if add_to_cart_found:
                print("   ✅ WORKING")
                return True, "working"

            # --- Failure reasons ---
            if "out of stock" in page_source:
                return False, "out_of_stock"
            if "product not found" in page_source or "404" in page_source:
                return False, "not_found"
            if "no longer available" in page_source:
                return False, "discontinued"

            return False, "no_add_to_cart"

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False, "error"

    def close(self):
        self.driver.quit()
        print("🧹 Browser closed")

# =========================
# 🛍️ SHOPIFY FUNCTIONS
# =========================
def fetch_products():
    products = []
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products.json?limit=250"

    while url:
        r = requests.get(url, headers=HEADERS)
        data = r.json()

        for product in data.get("products", []):
            mf_url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product['id']}/metafields.json"
            mf = requests.get(mf_url, headers=HEADERS).json().get("metafields", [])

            for m in mf:
                if m["namespace"] == METAFIELD_NAMESPACE and m["key"] == METAFIELD_KEY:
                    products.append({
                        "id": product["id"],
                        "title": product["title"],
                        "url": m["value"]
                    })

        link = r.headers.get("Link")
        url = link.split(";")[0].strip("<>") if link and 'rel="next"' in link else None

    return products

def set_draft(product_id):
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}.json"
    payload = {"product": {"id": product_id, "status": "draft"}}
    r = requests.put(url, headers=HEADERS, json=payload)

    if r.status_code == 200:
        print(f"📝 Product {product_id} → DRAFT")
    else:
        print(f"❌ Draft failed: {r.text}")

# =========================
# 🧠 MAIN (AUTOMATED)
# =========================
if __name__ == "__main__":
    print("\n🚀 Shopify Bunnings Automation\n")

    products = fetch_products()
    print(f"📦 Products found: {len(products)}")

    checker = BunningsDirectChecker()

    for i, p in enumerate(products, 1):
        print(f"\n[{i}/{len(products)}] {p['title']}")
        working, status = checker.check_bunnings_url(p["url"])

        if not working:
            print(f"   ❌ {status} → Drafting")
            set_draft(p["id"])

        time.sleep(2)

    checker.close()
    print("\n✅ Automation complete")
