#!/usr/bin/env python3
"""
Bunnings URL Checker – Shopify Metafield Mode (FIXED)
✔ Fetches all products
✔ Reads metafields correctly
✔ Filters by namespace + key
✔ Extracts Bunnings URLs reliably
"""

import time
import csv
import json
import re
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# ======================================================
# 🔐 SHOPIFY CONFIG (HARDCODED)
# ======================================================
SHOPIFY_STORE = "seydeltest"
SHOPIFY_TOKEN = "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"
SHOPIFY_API_VERSION = "2024-10"   # ✅ VALID VERSION

# ✅ EXACT metafield locations
METAFIELD_CONFIGS = [
    {"namespace": "custom", "key": "bunnings_au_link"},
]

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json",
}

# ======================================================
class BunningsChecker:
    def __init__(self, headless=True):
        self.driver = None
        self.session = requests.Session()
        self.setup_driver(headless)

    # --------------------------------------------------
    def setup_driver(self, headless):
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        self.driver = uc.Chrome(options=options, use_subprocess=True)
        print("✅ Browser ready")

    # --------------------------------------------------
    def is_bunnings_url(self, text):
        return "bunnings.com.au" in str(text).lower()

    # --------------------------------------------------
    def extract_url(self, value):
        """Handles string, JSON, embedded URLs"""
        if not value:
            return None

        value = str(value).strip()

        # JSON value
        try:
            data = json.loads(value)
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, str) and self.is_bunnings_url(v):
                        return v
        except:
            pass

        # Plain string
        if self.is_bunnings_url(value):
            return value

        # Embedded URL
        urls = re.findall(r"https?://[^\s\"'>]+", value)
        for u in urls:
            if self.is_bunnings_url(u):
                return u

        return None

    # --------------------------------------------------
    def fetch_all_products(self):
        """Fetch ALL products (including draft)"""
        products = []
        url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
        params = {"limit": 250, "status": "any"}

        while url:
            r = requests.get(url, headers=HEADERS, params=params)
            r.raise_for_status()
            data = r.json()["products"]
            products.extend(data)

            link = r.headers.get("Link")
            if link and 'rel="next"' in link:
                url = link.split(";")[0].strip("<> ")
                params = None
            else:
                url = None

        print(f"📦 Total products fetched: {len(products)}")
        return products

    # --------------------------------------------------
    def fetch_bunnings_urls(self):
        print("\n🔗 Fetching Bunnings URLs from metafields...")
        products = self.fetch_all_products()
        results = []

        for p in products:
            pid = p["id"]
            title = p["title"]

            mf_url = (
                f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/"
                f"{SHOPIFY_API_VERSION}/products/{pid}/metafields.json"
            )

            r = requests.get(mf_url, headers=HEADERS)
            if r.status_code != 200:
                continue

            metafields = r.json()["metafields"]

            for mf in metafields:
                for cfg in METAFIELD_CONFIGS:
                    if (
                        mf["namespace"] == cfg["namespace"]
                        and mf["key"] == cfg["key"]
                    ):
                        url = self.extract_url(mf["value"])
                        if url:
                            results.append({
                                "product_id": pid,
                                "product_title": title,
                                "url": url,
                            })
                            print(f"  ✅ {title[:40]} → {url}")

        print(f"\n✅ Found {len(results)} Bunnings URLs\n")
        return results

    # --------------------------------------------------
    def check_url(self, url):
        """Simple HTTP check"""
        try:
            r = self.session.get(url, timeout=15, allow_redirects=True)
            return r.status_code
        except:
            return None

    # --------------------------------------------------
    def run(self):
        urls = self.fetch_bunnings_urls()
        if not urls:
            print("❌ No URLs found — check metafield data")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_name = f"bunnings_results_{ts}.csv"

        with open(csv_name, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Product ID", "Product Title", "URL", "HTTP Status"])

            for u in urls:
                status = self.check_url(u["url"])
                writer.writerow([
                    u["product_id"],
                    u["product_title"],
                    u["url"],
                    status,
                ])
                print(f"🔍 {status} → {u['url']}")

        print(f"\n📊 Results saved to {csv_name}")

    # --------------------------------------------------
    def close(self):
        if self.driver:
            self.driver.quit()
            print("✅ Browser closed")


# ======================================================
if __name__ == "__main__":
    checker = BunningsChecker(headless=True)
    try:
        checker.run()
    finally:
        checker.close()
        print("\n✨ Done")
