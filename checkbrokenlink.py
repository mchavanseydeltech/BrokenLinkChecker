import requests
import time

SHOPIFY_STORE = "cassien24.myshopify.com"
ACCESS_TOKEN = "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"
API_VERSION = "2025-01"

HEADERS = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}

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
        if mf["namespace"] == "custom" and mf["key"] == "bunnings_url":
            return mf["value"]
    return None

def is_bunnings_inactive(url):
    try:
        r = requests.get(url, allow_redirects=True, timeout=10)
        final_url = r.url.lower()
        page = r.text.lower()

        if "search/products" in final_url:
            return True

        if "inactiveproducttype=bunnings" in final_url:
            return True

        if "add to cart" not in page and "product" not in page:
            return True

        return False
    except Exception as e:
        print(f"⚠️ Error checking {url}: {e}")
        return False

def make_product_draft(product_id):
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

def main():
    products = get_products()
    print(f"🔍 Checking {len(products)} products")

    for product in products:
        product_id = product["id"]
        bunnings_url = get_bunnings_url(product_id)

        if not bunnings_url:
            continue

        print(f"➡️ Checking product {product_id}")
        if is_bunnings_inactive(bunnings_url):
            make_product_draft(product_id)
            time.sleep(0.5)  # rate-limit safety

if __name__ == "__main__":
    main()
