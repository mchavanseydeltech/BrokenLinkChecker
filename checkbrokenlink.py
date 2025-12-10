
import requests

# ------------------ CONFIG ------------------
SHOP = "cassien24.myshopify.com"
TOKEN = "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"
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"
# -------------------------------------------

session = requests.Session()

# Fake browser headers so Cloudflare does NOT block us
session.headers.update({
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Upgrade-Insecure-Requests": "1"
})


def check_bunnings_redirect(url):
    """
    Detect inactive product by redirect chain ONLY.
    Bunnings inactive product ALWAYS ends at:
    /search/products?...isinactiveproduct=true
    """
    try:
        r = session.get(url, timeout=10, allow_redirects=True)

        final_url = r.url.lower()

        # Detect inactive redirect
        if "isinactiveproduct=true" in final_url:
            return False, final_url

        return True, final_url

    except Exception as e:
        print("Request error:", e)
        return False, url


# ------------------ FETCH PRODUCTS ------------------
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

# ------------------ PROCESS PRODUCTS ------------------
for p in products:

    mf = p.get("metafield")
    if not mf or not mf.get("value"):
        print(f"⚠ No AU Link for: {p['title']}")
        continue

    url = mf["value"]

    print(f"\nChecking: {p['title']} → {url}")

    ok, final_url = check_bunnings_redirect(url)

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
