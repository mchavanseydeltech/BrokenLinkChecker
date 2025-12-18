#!/usr/bin/env python3
"""
Bunnings URL Checker – STRICT MODE
Uses metafield custom.au_link
ACTIVE = Add to Cart button exists
BROKEN = No Add to Cart button
"""

import time
import csv
import re
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# =========================
# 🔐 SHOPIFY CONFIG
# =========================
SHOPIFY_STORE = "seydeltest"
SHOPIFY_TOKEN = "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"
SHOPIFY_API_VERSION = "2024-10"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "au_link"
# =========================


class BunningsChecker:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.urls = []

    # ---------- Browser ----------
    def setup_driver(self):
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        self.driver = uc.Chrome(options=options)

    # ---------- Extract URL ----------
    def extract_url(self, value):
        if not value:
            return None
        value = str(value).replace("...", "").strip()
        match = re.search(
            r'https?://(?:www\.)?bunnings\.com\.au/[^\s"<>\']+',
            value,
            re.IGNORECASE
        )
        return match.group(0) if match else None

    # ---------- Get Shopify URLs from custom.au_link ----------
    def fetch_urls(self):
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }

        products_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json?limit=50"
        products = requests.get(products_url, headers=headers).json().get("products", [])

        for p in products:
            mf_url = (
                f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/"
                f"{SHOPIFY_API_VERSION}/products/{p['id']}/metafields.json"
                f"?namespace={METAFIELD_NAMESPACE}&key={METAFIELD_KEY}"
            )

            resp = requests.get(mf_url, headers=headers).json()
            metafields = resp.get("metafields", [])

            for mf in metafields:
                url = self.extract_url(mf.get("value"))
                if url:
                    self.urls.append({
                        "product_id": p["id"],
                        "title": p["title"],
                        "url": url
                    })

        print(f"🔍 Found {len(self.urls)} Bunnings URLs in {METAFIELD_NAMESPACE}.{METAFIELD_KEY}")

    # ---------- Add to Cart detection ----------
    def has_add_to_cart(self):
        selectors = [
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'add to cart')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'add to trolley')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'buy online')]",
        ]

        for s in selectors:
            try:
                btns = self.driver.find_elements(By.XPATH, s)
                for b in btns:
                    if b.is_displayed():
                        return True
            except:
                pass
        return False

    # ---------- Check URL ----------
    def check_url(self, data):
        self.driver.get(data["url"])
        time.sleep(7)  # Wait for page to load

        # Redirected or inactive page
        if "search/products" in self.driver.current_url.lower() or "inactiveproducttype" in self.driver.current_url.lower():
            return "BROKEN"

        return "ACTIVE" if self.has_add_to_cart() else "BROKEN"

    # ---------- Run ----------
    def run(self):
        self.fetch_urls()
        if not self.urls:
            print("❌ No URLs found in metafield.")
            return

        self.setup_driver()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = f"bunnings_results_{timestamp}.csv"

        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Product ID", "Product Title", "Bunnings URL", "Status"
            ])

            for i, item in enumerate(self.urls, 1):
                print(f"[{i}/{len(self.urls)}] Checking {item['url']}")
                try:
                    status = self.check_url(item)
                except Exception as e:
                    status = f"ERROR: {str(e)[:100]}"
                writer.writerow([
                    item["product_id"], item["title"], item["url"], status
                ])
                print(f"   ➜ {status}")

        print(f"\n✅ Done. Results saved to {csv_file}")
        self.driver.quit()


# ---------- MAIN ----------
if __name__ == "__main__":
    checker = BunningsChecker(headless=True)
    checker.run()
