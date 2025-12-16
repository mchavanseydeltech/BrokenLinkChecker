import time
import requests

# -------------------------
# Shopify Config (hardcoded)
# -------------------------
SHOPIFY_STORE = "cassien24.myshopify.com"  # Replace with your store
ACCESS_TOKEN = "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"   # Replace with your token
API_VERSION = "2025-10"

HEADERS = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}

# -------------------------
# Shopify Functions
# -------------------------
def get_products():
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products.json"
    params = {"limit": 250, "status": "active"}
    res = requests.get(url, headers=HEADERS, params=params)
    res.raise_for_status()
    return res.json()["products"]

def get_bunnings_url(product_id):
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}/metafields.json"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    for mf in res.json()["metafields"]:
        if mf["namespace"] == "custom" and mf["key"] == "au_link":
            return mf["value"]
    return None

def make_product_draft(product_id):
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}.json"
    payload = {"product": {"id": product_id, "status": "draft"}}
    r = requests.put(url, json=payload, headers=HEADERS)
    r.raise_for_status()
    print(f"✅ Product {product_id} moved to DRAFT")

# -------------------------
# Bunnings Detection
# -------------------------
def is_bunnings_inactive(url):
    """
    Returns True if Bunnings product is inactive
    Checks final URL for inactive flags
    """
    try:
        r = requests.get(url, allow_redirects=True, timeout=10)
        final_url = r.url.lower()
        print(f"Checking URL: {url}")
        print(f"Final URL: {final_url}")

        # Detect inactive products by URL parameters
        if "inactiveproducttype=bunnings" in final_url and "isinactiveproduct=true" in final_url:
            print("Inactive detected: Bunnings redirect with inactive flags")
            return True

        print("Product is active")
        return False

    except Exception as e:
        print(f"⚠️ Error checking URL {url}: {e}")
        return False

# -------------------------
# Main Runner
# -------------------------
def main():
    products = get_products()
    print(f"Found {len(products)} active products in Shopify")

    for product in products:
        product_id = product["id"]
        bunnings_url = get_bunnings_url(product_id)

        if not bunnings_url:
            print(f"Skipping product {product_id}: no Bunnings URL")
            continue

        if is_bunnings_inactive(bunnings_url):
            make_product_draft(product_id)
        else:
            print(f"Product {product_id} remains active")

        time.sleep(0.5)  # rate-limit safety

if __name__ == "__main__":
    main()
