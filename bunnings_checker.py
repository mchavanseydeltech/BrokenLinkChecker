#!/usr/bin/env python3
"""
Bunnings URL Checker – Shopify Product Metafield Mode
Fetches all Bunnings URLs from product metafields (all products)
Checks each URL for Add to Cart button using Selenium (headless)
"""

import time
import csv
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# =========================
# 🔐 SHOPIFY CONFIG (HARDCODED)
# =========================
SHOPIFY_STORE = "cassien24"  # e.g., "seydeltech"
SHOPIFY_TOKEN = "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"
SHOPIFY_API_VERSION = "2025-10"

METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "au_link"
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

    def fetch_bunnings_urls(self):
        print("\n🔗 Fetching URLs from Shopify product metafields...")
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        urls = []
        endpoint = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
        params = {"limit": 250, "status": "any"}

        while endpoint:
            r = requests.get(endpoint, headers=headers, params=params)
            r.raise_for_status()
            products = r.json().get("products", [])

            if not products:
                break

            for product in products:
                pid = product["id"]
                mf_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{pid}/metafields.json"
                mf_resp = requests.get(mf_url, headers=headers)
                mf_resp.raise_for_status()

                metafields = mf_resp.json().get("metafields", [])
                for mf in metafields:
                    if (mf["namespace"] == METAFIELD_NAMESPACE
                        and mf["key"] == METAFIELD_KEY
                        and mf.get("value")
                        and "bunnings.com.au" in mf["value"]):
                        urls.append(mf["value"].strip())

            link = r.headers.get("Link")
            if link and 'rel="next"' in link:
                endpoint = link.split(";")[0].strip("<> ")
                params = None
            else:
                endpoint = None

        urls = list(set(urls))
        print(f"✅ Found {len(urls)} Bunnings URLs\n")
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
            result["page_title"] = title
            page = self.driver.page_source.lower()

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
        urls = self.fetch_bunnings_urls()
        if not urls:
            print("❌ No URLs found")
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
    checker = BunningsChecker(headless=True)  # headless for GitHub Actions
    try:
        checker.bulk_test()
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        checker.close()
        print("\n✨ Done!")
