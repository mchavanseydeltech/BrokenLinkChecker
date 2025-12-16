#!/usr/bin/env python3
"""
Bunnings URL Checker (GitHub Actions SAFE)
- Fetches Bunnings URLs from Shopify product metafields
- Checks for Add to Cart button
- Sets product to DRAFT if Add to Cart not found
"""

import time
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# ==============================
# 🔐 HARD-CODED SHOPIFY DETAILS
# ==============================
SHOPIFY_STORE = "cassien24.myshopify.com"
SHOPIFY_ACCESS_TOKEN = "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"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "au_link"

API_VERSION = "2025-10"

# ==============================
# 🚀 SELENIUM CHECKER
# ==============================
class BunningsDirectChecker:
    def __init__(self):
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        options = uc.ChromeOptions()

        # ✅ REQUIRED FOR GITHUB ACTIONS
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=1920,1080")

        options.add_argument(
            "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        self.driver = uc.Chrome(
            options=options,
            use_subprocess=True,
            headless=True
        )

        print("✅ Headless Chrome started")

    def check_add_to_cart(self, url):
        print(f"🔗 Checking: {url}")

        try:
            self.driver.get(url)
            time.sleep(10)

            title = self.driver.title.lower()
            if "just a moment" in title:
                print("⏳ Cloudflare detected, waiting...")
                time.sleep(12)

            page = self.driver.page_source.lower()

            keywords = [
                "add to cart",
                "add to trolley",
                "data-testid=\"add-to-cart\"",
                "aria-label=\"add to cart\""
            ]

            for k in keywords:
                if k in page:
                    print("✅ Add to Cart FOUND")
                    return True

            print("❌ Add to Cart NOT FOUND")
            return False

        except Exception as e:
            print(f"❌ Selenium error: {e}")
            return False

    def close(self):
        if self.driver:
            self.driver.quit()
            print("🧹 Browser closed")

# ==============================
# 🛍️ SHOPIFY HELPERS
# ==============================
HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json"
}

def fetch_products_with_bunnings_url():
    products = []
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products.json?limit=250"

    while url:
        r = requests.get(url, headers=HEADERS)
        data = r.json()

        for product in data.get("products", []):
            mf_url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product['id']}/metafields.json"
            mf_resp = requests.get(mf_url, headers=HEADERS)
            metafields = mf_resp.json().get("metafields", [])

            for mf in metafields:
                if mf["namespace"] == METAFIELD_NAMESPACE and mf["key"] == METAFIELD_KEY:
                    if mf["value"]:
                        products.append({
                            "id": product["id"],
                            "title": product["title"],
                            "url": mf["value"]
                        })

        link = r.headers.get("Link")
        if link and 'rel="next"' in link:
            url = link.split(";")[0].strip("<>")
        else:
            url = None

    return products

def mark_product_draft(product_id):
    endpoint = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}.json"
    payload = {"product": {"id": product_id, "status": "draft"}}

    r = requests.put(endpoint, headers=HEADERS, json=payload)

    if r.status_code == 200:
        print(f"📝 Product {product_id} set to DRAFT")
    else:
        print(f"❌ Failed to update product {product_id}: {r.text}")

# ==============================
# 🧠 MAIN
# ==============================
if __name__ == "__main__":
    print("\n🚀 Starting Bunnings Checker\n")

    products = fetch_products_with_bunnings_url()
    print(f"📦 Found {len(products)} products")

    if not products:
        print("❌ No products found. Exiting.")
        exit(0)

    checker = BunningsDirectChecker()

    drafted = 0
    for i, p in enumerate(products, 1):
        print(f"\n[{i}/{len(products)}] {p['title']}")

        ok = checker.check_add_to_cart(p["url"])
        if not ok:
            mark_product_draft(p["id"])
            drafted += 1

        time.sleep(2)

    checker.close()

    print("\n==============================")
    print(f"✅ Total products checked: {len(products)}")
    print(f"📝 Products drafted: {drafted}")
    print("==============================\n")
