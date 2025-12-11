import requests

# ------------------ CONFIG ------------------
SHOP = "cassien24.myshopify.com"      # Replace with your store
TOKEN = "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"  # Replace with your Shopify access token
API_VERSION = "2025-10"

META_NAMESPACE = "custom"
META_KEY = "au_link"  # Metafield containing Bunnings product URL
# -------------------------------------------

# Headers to mimic real browser (avoid Cloudflare blocks)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# ------------------ FETCH PRODUCTS ------------------
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

# ------------------ FUNCTION: Detect Inactive Bunnings ------------------
def detect_inactive_bunnings(url):
    try:
        # Follow redirects
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        final_url = r.url.lower()
        html_content = r.text.lower()

        # 1. Check for specific patterns in the FINAL URL
        url_inactive_indicators = [
            'isinactiveproduct=true',
            'outofstock',
            'discontinued',
            'product-not-found',
            'error',
            '404'
        ]
        if any(indicator in final_url for indicator in url_inactive_indicators):
            return False, final_url  # INACTIVE

        # 2. Check HTTP status code for client or server errors
        if r.status_code >= 400:
            print(f"   HTTP {r.status_code} status code detected.")
            return False, final_url  # INACTIVE

        # 3. Check for specific text in the PAGE CONTENT
        content_inactive_indicators = [
            'this product is no longer available',
            'out of stock',
            'product discontinued',
            'page not found',
            'sorry, we couldn’t find that page'
        ]
        if any(indicator in html_content for indicator in content_inactive_indicators):
            return False, final_url  # INACTIVE

        # If none of the above conditions are met, assume the product is active
        return True, final_url  # ACTIVE

    except requests.exceptions.RequestException as e:
        print(f"⚠ Request failed for {url}: {e}")
        # Depending on your preference, you can treat failures as active or inactive.
        # Treating as active prevents accidentally hiding products due to network errors.
        return True, url
    except Exception as e:
        print(f"⚠ Unexpected error for {url}: {e}")
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
