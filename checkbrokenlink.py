#!/usr/bin/env python3
"""
Bunnings Product Checker using Selenium with retries - works on GitHub Actions
"""

import time
import csv
import random
from datetime import datetime
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ------------------ CONFIG ------------------
SHOP = "cassien24.myshopify.com"       # Shopify store
TOKEN = "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"   # Shopify Admin API access token
API_VERSION = "2025-10"
META_NAMESPACE = "custom"
META_KEY = "au_link"
CSV_FILE = "bunnings_check_results.csv"
MAX_RETRIES = 3                  # Number of retries if page blocked
RETRY_DELAY = 5                  # Seconds to wait before retry
# -------------------------------------------

# ------------------ Selenium Setup ------------------
def init_driver():
    options = Options()
    options.add_argument("--headless=new")       # GitHub Actions compatible
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)
    return driver

# ------------------ Bunnings Checker ------------------
def check_bunnings_url(driver, url):
    """
    Returns: (is_active, final_url, reason)
    Only inactive if:
      1️⃣ URL contains 'isinactiveproduct=true'
      2️⃣ HTML shows 'oops', 'not found', 'discontinued', 'unavailable', etc.
    Implements retries if page blocked.
    """
    url = url.strip()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver.get(url)
            time.sleep(random.uniform(2, 4))  # wait for page load
            final_url = driver.current_url.lower()
            html = driver.page_source.lower()

            # Retry if page looks like blocked
            blocked_indicators = [
                "captcha", "access denied", "temporarily unavailable", "unusual traffic"
            ]
            if any(b in html for b in blocked_indicators):
                print(f"⚠ Page blocked detected, retry {attempt}/{MAX_RETRIES}")
                time.sleep(RETRY_DELAY)
                continue

            # 1️⃣ URL parameter indicating inactive
            if "isinactiveproduct=true" in final_url:
                return False, final_url, "INACTIVEPARAM"

            # 2️⃣ Check page content for inactive messages
            inactive_keywords = [
                "oops",
                "product is no longer available",
                "this product has been discontinued",
                "product unavailable",
                "currently unavailable",
                "no longer stocked",
                "we couldn't find that product",
                "404 error",
                "page not found",
                "this page doesn't exist",
                "product not found",
            ]

            for kw in inactive_keywords:
                if kw in html:
                    return False, final_url, f"HTML_INACTIVE ({kw})"

            # Otherwise active
            return True, final_url, "ACTIVE"

        except Exception as e:
            print(f"⚠ Error on attempt {attempt}: {str(e)[:60]}")
            time.sleep(RETRY_DELAY)
            continue

    # If all retries fail, assume active but log warning
    return True, url, "ASSUMED_ACTIVE_AFTER_RETRIES"

# ------------------ Shopify API ------------------
def fetch_products():
    query = f"""
    {{
      products(first: 250) {{
        nodes {{
          id
          title
          status
          metafield(namespace: "{META_NAMESPACE}", key: "{META_KEY}") {{
            value
          }}
        }}
      }}
    }}
    """
    res = requests.post(
        f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json",
        headers={"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"},
        json={"query": query}
    )
    return res.json().get("data", {}).get("products", {}).get("nodes", [])

def update_product_to_draft(product_id):
    mutation = f"""
    mutation {{
      productUpdate(input: {{
        id: "{product_id}",
        status: DRAFT
      }}) {{
        product {{ id title status }}
        userErrors {{ field message }}
      }}
    }}
    """
    res = requests.post(
        f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json",
        headers={"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"},
        json={"query": mutation}
    )
    return res.json()

# ------------------ MAIN ------------------
def main():
    print("\n🚀 Bunnings Checker Started")
    print(f"Time: {datetime.now()}")
    print("="*60)

    driver = init_driver()
    products = fetch_products()
    print(f"Found {len(products)} products")

    summary = {"active": 0, "inactive": 0, "errors": 0, "reasons": {}}

    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Product Title", "Shopify Status", "Bunnings URL", "Final URL", "Result", "Reason"])

        for p in products:
            title = p.get("title", "N/A")
            status = p.get("status", "N/A")
            metafield = p.get("metafield", {})
            url = metafield.get("value") if metafield else None

            if not url:
                print(f"{title} → ⚠ No Bunnings URL")
                continue

            if status == "DRAFT":
                print(f"{title} → ⚠ Already DRAFT, skipping")
                continue

            # Check Bunnings URL
            is_active, final_url, reason = check_bunnings_url(driver, url)

            if not is_active:
                print(f"{title} → ❌ BROKEN ({reason})")
                result = update_product_to_draft(p["id"])
                user_errors = result.get("data", {}).get("productUpdate", {}).get("userErrors")
                if user_errors:
                    print(f"⚠ Shopify Update Error: {user_errors}")
                    summary["errors"] += 1
                else:
                    print("✅ Updated to DRAFT")
                    summary["inactive"] += 1
                    summary["reasons"][reason] = summary["reasons"].get(reason, 0) + 1
                writer.writerow([title, status, url, final_url, "INACTIVE", reason])
            else:
                print(f"{title} → ✅ ACTIVE")
                summary["active"] += 1
                writer.writerow([title, status, url, final_url, "ACTIVE", reason])

            time.sleep(random.uniform(1, 2))

    driver.quit()

    # Summary
    print("\n================= SUMMARY =================")
    print(f"Active Products: {summary['active']}")
    print(f"Inactive Products: {summary['inactive']}")
    print(f"Errors: {summary['errors']}")
    print("\nInactive Reasons:")
    for r, count in summary["reasons"].items():
        print(f" - {r}: {count}")
    print(f"\nCSV saved to {CSV_FILE}")
    print("===========================================\n")


if __name__ == "__main__":
    main()
