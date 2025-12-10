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
SHOP = "cassien24.myshopify.com"  # Replace with your store
TOKEN = "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"       # Replace with your token
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

data = response.json()
products = data["data"]["products"]["nodes"]

# ------------------ Function: Detect inactive Bunnings ------------------
def detect_inactive_bunnings(url, timeout=10):
    """
    Opens the page like a real browser and waits for JS redirects.
    Returns (True, final_url) if active, (False, final_url) if inactive.
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
            page.goto(url)

            # Wait until URL stabilizes (no changes for 1 sec or timeout)
            elapsed = 0
            last_url = page.url.lower()
            while elapsed < timeout:
                time.sleep(1)
                elapsed += 1
                current_url = page.url.lower()
                if current_url != last_url:
                    last_url = current_url
                    elapsed = 0  # reset timer if URL changed

            final_url = page.url.lower()
            browser.close()

            if "isinactiveproduct=true" in final_url:
                return False, final_url
            return True, final_url

    except Exception as e:
        print("Playwright warning (treating as active):", e)
        return True, url



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

        try:
            print(update.json())
        except Exception as e:
            print("❌ Failed to parse update response:", e)
            print(update.text)
    else:
        print(f"✔ Active Product → {final_url}")

print("\n✓ Completed all products.")
