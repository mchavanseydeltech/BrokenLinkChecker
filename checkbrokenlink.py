#!/usr/bin/env python3
"""
Bunnings Product Checker - No Selenium Version
"""

import requests
import time
import random
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# ------------------ HARDCODED CONFIG ------------------
SHOP = "cassien24.myshopify.com"       # Replace with your Shopify store
TOKEN = "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"  # Replace with your Shopify access token
API_VERSION = "2025-10"
META_NAMESPACE = "custom"
META_KEY = "au_link"
# -----------------------------------------------------

def detect_inactive_bunnings(url):
    """Smart detection without Selenium"""
    session = requests.Session()
    
    # Realistic headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    
    try:
        # Small random delay
        time.sleep(random.uniform(1, 2))
        
        print(f"   Fetching: {url}")
        response = session.get(url, headers=headers, timeout=20, allow_redirects=True)
        
        # Check for blocking
        if response.status_code == 403:
            print("   ⚠ 403 Forbidden - Trying alternative approach...")
            # Try with different headers
            headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15"
            response = session.get(url, headers=headers, timeout=20, allow_redirects=True)
        
        final_url = response.url.lower()
        html = response.text.lower()
        
        print(f"   Status: {response.status_code}, Size: {len(html)} chars")
        
        # CHECK 1: Direct URL parameter
        if "isinactiveproduct=true" in final_url:
            print("   ❌ INACTIVE (URL parameter)")
            return False, final_url
        
        # CHECK 2: Query parameter
        parsed = urlparse(final_url)
        params = parse_qs(parsed.query)
        if 'isinactiveproduct' in params and 'true' in str(params['isinactiveproduct']).lower():
            print("   ❌ INACTIVE (Query param)")
            return False, final_url
        
        # CHECK 3: JavaScript patterns in HTML
        js_patterns = [
            r'isinactiveproduct["\']?\s*[:=]\s*["\']?true',
            r'window\.location.*isinactiveproduct',
            r'meta.*refresh.*isinactiveproduct',
            r'productunavailable',
            r'product-unavailable',
        ]
        
        for pattern in js_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                print(f"   ❌ INACTIVE (Pattern: {pattern[:30]}...)")
                return False, final_url
        
        # CHECK 4: Page content indicators
        indicators = [
            'product is no longer available',
            'this product has been discontinued',
            'page not found',
            '404 error',
            'out of stock',
            'not available',
            'unavailable',
        ]
        
        for indicator in indicators:
            if indicator in html:
                print(f"   ❌ INACTIVE (Text: {indicator})")
                return False, final_url
        
        # If all checks pass, product is active
        print("   ✅ ACTIVE")
        return True, final_url
        
    except Exception as e:
        print(f"   ⚠ Error: {e}")
        return True, url  # Default to active on error

def fetch_products():
    """Fetch products from Shopify"""
    query = f"""
    {{
      products(first: 250) {{
        nodes {{
          id
          title
          status
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
    return data["data"]["products"]["nodes"]

def update_product(product_id):
    """Update product to DRAFT"""
    mutation = f"""
    mutation {{
      productUpdate(input: {{ id: "{product_id}", status: DRAFT }}) {{
        product {{ id title status }}
        userErrors {{ field message }}
      }}
    }}
    """
    
    response = requests.post(
        f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json",
        headers={
            "X-Shopify-Access-Token": TOKEN,
            "Content-Type": "application/json",
        },
        json={"query": mutation}
    )
    
    return response.json()

# ------------------ MAIN ------------------
def main():
    print(f"🚀 Bunnings Checker - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Validate credentials
    if "yourstore" in SHOP or "shpat_xx" in TOKEN:
        print("❌ Please update SHOP and TOKEN in the script!")
        return
    
    products = fetch_products()
    print(f"📦 Found {len(products)} products")
    
    inactive_count = 0
    active_count = 0
    
    for p in products:
        print(f"\nChecking: {p['title']}")
        
        mf = p.get("metafield")
        if not mf or not mf.get("value"):
            print("  ⚠ No Bunnings URL")
            continue
        
        url = mf["value"]
        
        # Skip if already draft
        if p.get("status") == "DRAFT":
            print("  ⚠ Already DRAFT, skipping")
            continue
        
        # Check status
        is_active, final_url = detect_inactive_bunnings(url)
        
        if not is_active:
            print(f"  ❌ Moving to DRAFT: {final_url[:100]}...")
            
            result = update_product(p["id"])
            if "errors" in result or result.get("data", {}).get("productUpdate", {}).get("userErrors"):
                print("  ⚠ Failed to update")
            else:
                print("  ✅ Updated successfully")
                inactive_count += 1
        else:
            print(f"  ✅ Active: {final_url[:100]}...")
            active_count += 1
        
        # Be nice to the server
        time.sleep(random.uniform(2, 4))
    
    print("\n" + "=" * 60)
    print(f"📊 Summary: {active_count} active, {inactive_count} inactive")
    print("=" * 60)

if __name__ == "__main__":
    main()
