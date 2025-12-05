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
    Uses stealth browser settings to detect Bunnings inactive redirects.
    Returns (is_valid, final_url)
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,                         # IMPORTANT: headful mode
                args=[
                    "--disable-blink-features=AutomationControlled",
                ]
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800}
            )

            page = context.new_page()

            # Visit original product URL
            page.goto(url, wait_until="networkidle")

            # Allow extra JS time (Bunnings sometimes redirects after JS loads)
            page.wait_for_timeout(3500)

            final_url = page.url.lower()

            # Detect redirected inactive page
            if "isinactiveproduct=true" in final_url:
                browser.close()
                return False, final_url

            # Detect landing on Bunnings search page with no results
            if "/search/products" in final_url:
                browser.close()
                return False, final_url

            # Detect fallback pages that display: "product not found"
            html = page.content().lower()
            if "inactive product" in html or "no products found" in html:
                browser.close()
                return False, final_url

            browser.close()
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
        print(f"❌ Inactive / Broken Link → {final_url}")
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
            f"https://" + SHOP + f"/admin/api/{API_VERSION}/graphql.json",
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
