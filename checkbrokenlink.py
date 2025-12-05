import requests

SHOP = "orionsecuritysystems.myshopify.com"
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
        print("Error checking URL:", e)
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

# --- Safely parse response ---
try:
    data = response.json()
except Exception as e:
    print("❌ Failed to parse JSON:", e)
    print(response.text)
    exit()

# Check for errors in Shopify response
if "errors" in data:
    print("❌ Shopify returned errors:", data["errors"])
    exit()

if "data" not in data or "products" not in data["data"]:
    print("❌ Unexpected Shopify response structure:")
    print(response.text)
    exit()

products = data["data"]["products"]["nodes"]

# --- Loop through products ---
for p in products:
    mf = p.get("metafield")
    if not mf or not mf.get("value"):
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

        # Print update result safely
        try:
            print("Update result:", update.json())
        except Exception as e:
            print("❌ Failed to parse update response:", e)
            print(update.text)
    else:
        print(f"✔ URL OK → {final_url}")

print("\nCompleted.")
