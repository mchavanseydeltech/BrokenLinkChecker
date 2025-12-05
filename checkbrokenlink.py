import requests

SHOP = "orionsecuritysystems.com.au"
TOKEN = "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"
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"   # Metafield: AU Link


def check_url(url):
    """Return (is_valid, final_url)."""
    try:
        r = requests.get(url, timeout=8, allow_redirects=True)
        final_url = r.url

        # Detect 404
        if r.status_code == 404:
            return False, final_url

        # Detect redirect to inactive product
        if "isinactiveproduct=true" in final_url.lower():
            return False, final_url

        # URL is OK
        return True, final_url

    except Exception as e:
        print("Error:", e)
        return False, url


# Step 1 — fetch products with AU Link metafield
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

products = response.json()["data"]["products"]["nodes"]

for p in products:
    mf = p.get("metafield")
    if not mf:
        continue

    url = mf["value"]
    print(f"\nChecking: {p['title']} → {url}")

    is_valid, final_url = check_url(url)

    # If broken OR redirected to &isinactiveproduct=true
    if not is_valid:
        print(f"❌ Invalid AU Link → {final_url}")
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

print("\nCompleted.")
