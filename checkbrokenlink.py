#!/usr/bin/env python3
"""
Bunnings Product Checker - Corrected version
Detects truly inactive links using isinactiveproduct=true and product content
"""

import requests
import time
import random
import csv
from datetime import datetime

# ------------------ CONFIG ------------------
SHOP = "cassien24.myshopify.com"       # Your Shopify store
TOKEN = "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"   # Shopify Admin API access token
API_VERSION = "2025-10"
META_NAMESPACE = "custom"
META_KEY = "au_link"
CSV_FILE = "bunnings_check_results.csv"
# -------------------------------------------

class BunningsChecker:
    def __init__(self):
        self.session = requests.Session()
        self.setup_headers()

    def setup_headers(self):
        """Random User-Agent headers"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        ]
        self.session.headers.update({"User-Agent": random.choice(user_agents)})

    def normalize_url(self, url):
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def check_bunnings_url(self, url):
        """Check Bunnings URL for true inactivity"""
        try:
            url = self.normalize_url(url)
            print(f"Checking: {url}")
            time.sleep(random.uniform(1, 3))  # avoid rate limiting

            resp = self.session.get(url, timeout=15, allow_redirects=True)
            final_url = resp.url.lower()
            html = resp.text.lower()

            # 1️⃣ Truly inactive if Bunnings adds this parameter
            if "isinactiveproduct=true" in final_url:
                return False, final_url, "INACTIVEPARAM"

            # 2️⃣ Redirect to search page without product → inactive
            if "/search" in final_url and "/product" not in final_url:
                return False, final_url, "SEARCH_REDIRECT"

            # 3️⃣ Ensure product exists on the page
            if "add to cart" not in html and "data-product-id" not in html:
                return False, final_url, "NO_PRODUCT_CONTENT"

            # Otherwise, considered active
            return True, final_url, "ACTIVE"

        except Exception as e:
            return True, url, f"ERROR_{str(e)[:40]}"


# ------------------ Shopify API ------------------

def fetch_products():
    """Fetch products from Shopify"""
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
    """Update Shopify product to DRAFT"""
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
    print("\n🚀 Bunnings Link Checker Started")
    print(f"Time: {datetime.now()}")
    print("=" * 60)

    checker = BunningsChecker()
    products = fetch_products()
    print(f"Found {len(products)} products")

    summary = {"active": 0, "inactive": 0, "errors": 0, "reasons": {}}

    # CSV setup
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

            # Check URL
            is_active, final_url, reason = checker.check_bunnings_url(url)

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
