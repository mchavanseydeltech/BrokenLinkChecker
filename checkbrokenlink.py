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
def detect_inactive_bunnings(url):
    """
    Detect inactive Bunnings products:
    1. Using Playwright (headful) to handle Cloudflare
    2. Fallback to requests if timeout occurs
    Returns (True, final_url) if active, (False, final_url) if inactive
    """
    # --- Try Playwright first ---
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=50)  # headful + slow for anti-bot
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                viewport={"width":1920,"height":1080},
                locale="en-US",
                timezone_id="Australia/Sydney",
                java_script_enabled=True
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=90000)  # 90s
            page.wait_for_timeout(3000)  # extra 3s to ensure JS

            final_url = page.url.lower()

            # Check for "Oops!" text indicating inactive product
            if page.locator("text=Oops! This product is no longer available.").count() > 0:
                browser.close()
                return False, final_url  # INACTIVE → draft

            browser.close()
            return True, final_url  # ACTIVE

    except Exception as e:
        print("⚠ Playwright failed (fallback to requests):", e)

    # --- Fallback using requests ---
    try:
        r = requests.get(url, timeout=15, allow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        })
        final_url = r.url.lower()
        page_text = r.text.lower()

        if "isinactiveproduct=true" in final_url or "oops! this product is no longer available." in page_text:
            return False, final_url  # INACTIVE
        return True, final_url  # ACTIVE

    except Exception as e:
        print("⚠ Requests fallback failed, treating as active:", e)
        return True, url

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
