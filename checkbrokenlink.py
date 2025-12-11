import subprocess
import sys
import requests
import time

# ------------------ Auto-install Playwright if missing ------------------
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Installing now...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "--with-deps"])
    from playwright.sync_api import sync_playwright

# ------------------ CONFIG ------------------
SHOP = "cassien24.myshopify.com"      # Replace with your store
TOKEN = "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"  # Replace with your Shopify access token
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"
# -------------------------------------------

# ------------------ Shopify GraphQL Fetch ------------------
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

try:
    data = response.json()
except Exception as e:
    print("❌ Failed to parse Shopify response:", e)
    print(response.text)
    exit()

if "errors" in data:
    print("❌ Shopify returned errors:", data["errors"])
    exit()

products = data["data"]["products"]["nodes"]

# ------------------ Function: Detect inactive Bunnings ------------------
def detect_inactive_bunnings(url, max_wait=15):
    """
    Detect inactive Bunnings products based on page content.
    Returns:
        True, final_url  → Product is ACTIVE
        False, final_url → Product is INACTIVE (draft)
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
            page.goto(url, wait_until="networkidle")  # wait for JS to finish

            final_url = page.url.lower()
            start_time = time.time()

            # Poll page content for up to max_wait seconds
            while time.time() - start_time < max_wait:
                content = page.content().lower()
                if "oops! this product is no longer available." in content:
                    browser.close()
                    return False, final_url  # INACTIVE → draft
                time.sleep(0.5)

            browser.close()
            return True, final_url  # ACTIVE if text not found

    except Exception as e:
        print("Playwright warning — treating as active:", e)
        return True, url  # Never mark DRAFT on exception

# ------------------ PROCESS PRODUCTS ------------------
for p in products:
    mf = p.get("metafield")
    if not mf or not mf.get("value"):
        print(f"⚠ No AU Link for: {p['title']}")
        continue

    url = mf["value"]
    print(f"\nChecking: {p['title']} → {url}")

    is_active, final_url = detect_inactive_bunnings(url)

    if not is_active:
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

        try:
            print(update.json())
        except Exception as e:
            print("❌ Failed to parse update response:", e)
            print(update.text)
    else:
        print(f"✔ ACTIVE → {final_url}")

print("\n✅ Completed all products.")
