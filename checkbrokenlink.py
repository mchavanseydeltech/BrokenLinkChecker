from playwright.sync_api import sync_playwright
import requests
import time

# ------------------ CONFIG ------------------
SHOP = "cassien24.myshopify.com"
TOKEN = "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"
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"
# -------------------------------------------


def detect_inactive_bunnings(url):
    """
    Opens the page like a REAL browser. Detects JS redirects.
    Works for:
      - HTTP redirects
      - JavaScript redirects
      - Meta refresh redirects
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ))
            page = context.new_page()

            page.goto(url, wait_until="networkidle")

            time.sleep(2)  # allow JS redirects

            final_url = page.url.lower()

            browser.close()

            # detect inactive
            if "isinactiveproduct=true" in final_url:
                return False, final_url

            return True, final_url

    except Exception as e:
        print("Playwright error:", e)
        return False, url


# ------------------ FETCH PRODUCTS ------------------
query = f"""
{{
  products(first: 250) {{
    nodes {{
      id
      title
      metafield(namespace: "{META_NAMESPACE}", key: "{META_KEY}") {{
        value
      }}
    }}
  }}
}}
"""

response = requests.post(
    f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json",
    headers={
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    },
    json={"query": query}
)

products = response.json()["data"]["products"]["nodes"]

# ------------------ PROCESS PRODUCTS ------------------
for p in products:

    mf = p.get("metafield")
    if not mf or not mf.get("value"):
        print(f"⚠ No AU Link for: {p['title']}")
        continue

    url = mf["value"]

    print(f"\nChecking: {p['title']} → {url}")

    ok, final_url = detect_inactive_bunnings(url)

    if not ok:
        print(f"❌ INACTIVE → {final_url}")
        print("→ Moving to DRAFT")

        mutation = f"""
        mutation {{
          productUpdate(input: {{
            id: "{p['id']}",
            status: DRAFT
          }}) {{
            product {{
              id
              status
            }}
            userErrors {{
              field
              message
            }}
          }}
        }}
        """

        update = requests.post(
            f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json",
            headers={
                "X-Shopify-Access-Token": TOKEN,
                "Content-Type": "application/json",
            },
            json={"query": mutation}
        )

        print(update.json())
    else:
        print(f"✔ Active Product → {final_url}")

print("\n✓ Completed")
