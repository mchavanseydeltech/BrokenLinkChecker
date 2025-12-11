import requests

# ------------------ CONFIG ------------------
SHOP = "cassien24.myshopify.com"      # Replace with your store
TOKEN = "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"  # Replace with your Shopify access token
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"
# -------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# ------------------ Fetch products ------------------
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

# ------------------ Function: detect inactive Bunnings ------------------
def detect_inactive_bunnings(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        final_url = r.url.lower()
        page_text = r.text.lower()

        if "isinactiveproduct=true" in final_url or "oops! this product is no longer available." in page_text:
            return False, final_url  # INACTIVE
        return True, final_url  # ACTIVE

    except Exception as e:
        print("⚠ Request failed, treating as active:", e)
        return True, url  # fallback

# ------------------ Process products ------------------
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

        print(update.json())
    else:
        print(f"✔ ACTIVE → {final_url}")

print("\n✅ Completed all products.")
