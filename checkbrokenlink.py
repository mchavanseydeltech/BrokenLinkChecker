import requests
import time

# -------------------------
# Config (hardcoded)
# -------------------------
SHOPIFY_STORE = "cassien24.myshopify.com"  # replace with your store
ACCESS_TOKEN = "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"    # replace with your access token
API_VERSION = "2025-10"

HEADERS = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}

# -------------------------
# Helper Functions
# -------------------------

def get_products():
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products.json"
    params = {"limit": 250, "status": "active"}  # only active products
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

def is_bunnings_inactive(url):
    """
    Returns True if the Bunnings product is inactive
    """
    try:
        r = requests.get(url, allow_redirects=True, timeout=10)
        final_url = r.url.lower()
        page = r.text.lower()

        print(f"Checking Bunnings URL: {url}")
        print(f"Final URL: {final_url}")

        # Case 1: Redirected to search page
        if "search/products" in final_url:
            print("Inactive detected: Redirected to search page")
            return True

        # Case 2: Inactive flag in URL
        if "inactiveproducttype=bunnings" in final_url:
            print("Inactive detected: inactiveproducttype flag found")
            return True

        # Case 3: Missing main product container
        # Adjust the selector based on live Bunnings product page HTML
        if "product__details" not in page and "product__title" not in page:
            print("Inactive detected: main product container missing")
            return True

        # Product looks active
        print("Product is active")
        return False

    except Exception as e:
        print(f"⚠️ Error checking URL {url}: {e}")
        return False

def make_product_draft(product_id):
    """
    Set Shopify product status to draft
    """
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/products/{product_id}.json"
    payload = {
        "product": {
            "id": product_id,
            "status": "draft"
        }
    }
    r = requests.put(url, json=payload, headers=HEADERS)
    r.raise_for_status()
    print(f"✅ Product {product_id} moved to DRAFT")

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

        # Rate-limit safety
        time.sleep(0.5)

if __name__ == "__main__":
    main()
