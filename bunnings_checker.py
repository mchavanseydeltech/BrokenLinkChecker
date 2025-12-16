#!/usr/bin/env python3
"""
Shopify Bunnings URL Checker - Local Terminal Version
Fetches URLs from Shopify metafield 'custom.au_link' and checks for Add to Cart button.
"""

import time
from datetime import datetime
import csv
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# ------------------- CONFIG (HARDCODED) -------------------
SHOP = "cassien24.myshopify.com"  # <-- Your Shopify store
ACCESS_TOKEN = "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"  # <-- Your Shopify Admin API token
HEADLESS = True  # Set False if you want to see Chrome
# ----------------------------------------------------------

# ------------------- CHECKER CLASS -------------------
class BunningsDirectChecker:
    def __init__(self, headless=HEADLESS):
        self.headless = headless
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--window-size=1920,1080")
        self.driver = uc.Chrome(options=options)

    # Fetch Shopify URLs from metafields
    def fetch_bunnings_urls_from_shopify(self):
        urls = []
        base_url = f"https://{SHOP}/admin/api/2025-10/products.json?limit=250"
        headers = {
            "X-Shopify-Access-Token": ACCESS_TOKEN,
            "Content-Type": "application/json"
        }

        print("📡 Fetching products from Shopify...")
        while base_url:
            response = requests.get(base_url, headers=headers)
            if response.status_code != 200:
                print(f"❌ Shopify API Error: {response.status_code} {response.text}")
                break

            data = response.json()
            products = data.get("products", [])
            for product in products:
                product_id = product["id"]
                mf_url = f"https://{SHOP}/admin/api/2025-10/products/{product_id}/metafields.json"
                mf_resp = requests.get(mf_url, headers=headers)
                if mf_resp.status_code != 200:
                    continue
                metafields = mf_resp.json().get("metafields", [])
                for mf in metafields:
                    if mf["key"] == "au_link" and mf["namespace"] == "custom":
                        link = mf.get("value")
                        if link and "bunnings.com.au" in link:
                            urls.append(link)

            # Pagination
            link_header = response.headers.get("Link")
            if link_header and 'rel="next"' in link_header:
                next_link = link_header.split(";")[0].strip("<>")
                base_url = next_link
            else:
                base_url = None

        print(f"✅ Found {len(urls)} Bunnings URL(s) from Shopify metafields")
        return urls

    # Check a single Bunnings URL
    def check_bunnings_url(self, url):
        print(f"\n🔗 Testing: {url[:80]}...")
        result = {
            "url": url,
            "page_title": "Not loaded",
            "status": "not_tested",
            "is_working": False,
            "add_to_cart_found": False,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.driver.get(url)
            time.sleep(5)
            title = self.driver.title
            result["page_title"] = title
            print(f"   Title: {title[:60]}...")

            # Check Add to Cart
            add_to_cart_found = False
            cart_texts = ["add to cart", "add to trolley"]
            for text in cart_texts:
                elements = self.driver.find_elements(
                    By.XPATH,
                    f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{text}')]"
                )
                for el in elements:
                    try:
                        if el.is_displayed():
                            add_to_cart_found = True
                            print(f"   ✓ Found: '{text}'")
                            break
                    except:
                        continue
                if add_to_cart_found:
                    break

            # CSS fallback
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
                    for el in elements:
                        try:
                            if el.is_displayed() and ("add to" in el.text.lower() or "cart" in el.text.lower()):
                                add_to_cart_found = True
                                print(f"   ✓ Found via selector: {selector}")
                                break
                        except:
                            continue
                    if add_to_cart_found:
                        break

            result["add_to_cart_found"] = add_to_cart_found
            if add_to_cart_found:
                result["status"] = "working"
                result["is_working"] = True
                print("   ✅ WORKING - Add to Cart found")
            else:
                result["status"] = "inactive_or_no_cart"
                print("   ❌ No Add to Cart button / inactive")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"   ❌ Error: {str(e)[:50]}...")

        return result

    # Bulk test all URLs
    def bulk_test_urls(self):
        urls = self.fetch_bunnings_urls_from_shopify()
        if not urls:
            print("❌ No URLs to test")
            return []

        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] ", end="")
            res = self.check_bunnings_url(url)
            results.append(res)
            if i < len(urls):
                time.sleep(2)

        # Save results CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"shopify_bunnings_results_{timestamp}.csv"
        self.save_results_csv(results, filename)
        self.print_summary(results)
        return results

    # Save results CSV
    def save_results_csv(self, results, filename):
        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "Bunnings_URL",
                "Page_Title",
                "Status",
                "Working",
                "Add_to_Cart_Found",
                "Error",
                "Test_Time"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({
                    "Bunnings_URL": r["url"],
                    "Page_Title": r["page_title"][:200] if r["page_title"] else "",
                    "Status": r["status"],
                    "Working": "Yes" if r["is_working"] else "No",
                    "Add_to_Cart_Found": "Yes" if r["add_to_cart_found"] else "No",
                    "Error": r["error"] or "",
                    "Test_Time": r["timestamp"]
                })
        print(f"\n📊 Results saved to: {filename}")

    def print_summary(self, results):
        working = sum(1 for r in results if r["is_working"])
        broken = len(results) - working
        print("\n📋 SUMMARY")
        print(f"Total URLs Tested: {len(results)}")
        print(f"✅ Working: {working}")
        print(f"❌ Broken / Inactive: {broken}")

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

# ------------------- MAIN -------------------
def main():
    checker = BunningsDirectChecker(headless=HEADLESS)
    try:
        checker.bulk_test_urls()
    except KeyboardInterrupt:
        print("\n⚠️  Stopped by user")
    finally:
        checker.close()
        print("\n✨ Done!")

if __name__ == "__main__":
    main()
