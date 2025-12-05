import requests
from playwright.sync_api import sync_playwright

# ---------------- CONFIG ----------------
SHOP = "546bf9.myshopify.com"
TOKEN = "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"
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"
# ----------------------------------------
def check_bunnings_url(url):
    """
    Opens URL in a real browser (executes JS)
    Returns (is_valid, final_url)
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Open the page and wait for all JS
            page.goto(url, wait_until="networkidle")

            final_url = page.url.lower()

            browser.close()

            # Detect inactive product
            if "isinactiveproduct=true" in final_url:
                return False, final_url

            return True, final_url

    except Exception as e:
        print("Browser error:", e)
        return False, url


# ---------------- FETCH PRODUCTS ----------------
query = f"""
{{
  products(first: 200) {{
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

data = response.json()

products = data["data"]["products"]["nodes"]

# ---------------- PROCESS PRODUCTS ----------------
for p in products:
    mf = p.get("metafield")

    if not mf or not mf.get("value"):
        print(f"⚠ Skipping {p['title']}: No AU Link")
        continue

    url = mf["value"]
    print(f"\nChecking: {p['title']} → {url}")

    is_valid, final_url = check_bunnings_url(url)

    if not is_valid:
        print(f"❌ Inactive or Broken Link → {final_url}")
        print("→ Setting product to DRAFT...")

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

        print("Update result:", update.json())
    else:
        print(f"✔ URL OK → {final_url}")

print("\n✅ Completed.")
