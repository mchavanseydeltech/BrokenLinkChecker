import requests
import json

# ------------------ CONFIG ------------------
SHOP = "546bf9.myshopify.com"  # must include .myshopify.com
TOKEN = "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"  # Admin API token
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"   # Metafield: AU Link
SET_DRAFT = True  # Set to False if you only want to list inactive products
# -------------------------------------------


def check_url(url):
    """
    Returns (is_valid, final_url)
    False if URL is 404 or contains '&isinactiveproduct=true'
    """
    try:
        r = requests.get(url, timeout=8, allow_redirects=True)
        final_url = r.url.lower()  # follow redirects

        # Broken link
        if r.status_code == 404:
            return False, final_url

        # Redirect to inactive product
        if "isinactiveproduct=true" in final_url:
            return False, final_url

        return True, final_url

    except Exception as e:
        print(f"Error checking URL {url}: {e}")
        return False, url


# ------------------ STEP 1: Fetch products ------------------
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
        "User-Agent": "Python Shopify Script"
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

products = data.get("data", {}).get("products", {}).get("nodes", [])

if not products:
    print("⚠ No products found.")
    exit()

# ------------------ STEP 2: Check URLs ------------------
inactive_products = []

for p in products:
    mf = p.get("metafield")
    if not mf or not mf.get("value"):
        print(f"⚠ Skipping {p['title']}: AU Link metafield missing or empty")
        continue

    url = mf["value"]
    print(f"\nChecking: {p['title']} → {url}")

    is_valid, final_url = check_url(url)

    if not is_valid:
        print(f"❌ Inactive or broken → {final_url}")
        inactive_products.append({
            "title": p["title"],
            "id": p["id"],
            "original_url": url,
            "final_url": final_url
        })

        # Optionally set product to draft
        if SET_DRAFT:
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
                    "User-Agent": "Python Shopify Script"
                },
                json={"query": mutation}
            )
            try:
                print("→ Set to DRAFT result:", update.json())
            except Exception as e:
                print("❌ Failed to parse update response:", e)
                print(update.text)
    else:
        print(f"✔ URL OK → {final_url}")

# ------------------ STEP 3: Report ------------------
print("\n✅ Inactive/Broken products found:", len(inactive_products))
for ip in inactive_products:
    print(f"- {ip['title']} → {ip['final_url']}")
