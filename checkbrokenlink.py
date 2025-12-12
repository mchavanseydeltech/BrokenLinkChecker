#!/usr/bin/env python3
"""
Bunnings Product Checker - Enhanced Version
"""

import requests
import time
import random
import re
import json
from datetime import datetime
from urllib.parse import urlparse, parse_qs, quote_plus

# ------------------ HARDCODED CONFIG ------------------
  
SHOP = "cassien24.myshopify.com"
TOKEN = "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"
API_VERSION = "2025-10"
META_NAMESPACE = "custom"
META_KEY = "au_link"
# -----------------------------------------------------

class BunningsChecker:
    def __init__(self):
        self.session = requests.Session()
        self.setup_headers()
        
    def setup_headers(self):
        """Set up rotating headers to avoid blocking"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        ]
        
        self.session.headers.update({
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })
    
    def check_bunnings_url(self, url):
        """Comprehensive Bunnings URL checker"""
        try:
            # Clean URL and ensure proper format
            url = self.normalize_url(url)
            print(f"   Checking: {url[:80]}...")
            
            # Random delay to avoid rate limiting
            time.sleep(random.uniform(2, 4))
            
            # First, try HEAD request for efficiency
            try:
                head_resp = self.session.head(url, timeout=15, allow_redirects=True)
                if head_resp.status_code in [404, 410, 403]:
                    print(f"   ❌ BROKEN: HTTP {head_resp.status_code}")
                    return False, url, f"HTTP_{head_resp.status_code}"
            except:
                pass  # Continue to GET request
            
            # GET request for full analysis
            response = self.session.get(url, timeout=25, allow_redirects=True)
            final_url = response.url
            html = response.text
            
            print(f"   Status: {response.status_code}, Size: {len(html)} chars")
            
            # Check HTTP status codes
            if response.status_code != 200:
                print(f"   ❌ BROKEN: HTTP {response.status_code}")
                return False, final_url, f"HTTP_{response.status_code}"
            
            # Convert to lowercase for case-insensitive matching
            html_lower = html.lower()
            
            # --- COMPREHENSIVE CHECKS FOR BROKEN/INACTIVE PRODUCTS ---
            
            # 1. URL parameter checks
            if self.check_url_parameters(final_url):
                return False, final_url, "URL_PARAM_INACTIVE"
            
            # 2. Redirect checks
            if self.check_redirect_patterns(url, final_url):
                return False, final_url, "REDIRECT_TO_INACTIVE"
            
            # 3. HTML content checks
            if self.check_html_content(html_lower):
                return False, final_url, "HTML_CONTENT_INACTIVE"
            
            # 4. JavaScript/JSON-LD checks
            if self.check_javascript_patterns(html):
                return False, final_url, "JS_INACTIVE"
            
            # 5. Meta tag checks
            if self.check_meta_tags(html):
                return False, final_url, "META_INACTIVE"
            
            # 6. Specific Bunnings patterns
            if self.check_bunnings_specific(html):
                return False, final_url, "BUNNINGS_SPECIFIC"
            
            # 7. Product data checks
            if self.check_product_data(html):
                return False, final_url, "PRODUCT_DATA_MISSING"
            
            # 8. Search result page (product replaced by search)
            if self.check_search_result_page(html_lower, final_url):
                return False, final_url, "SEARCH_RESULT_PAGE"
            
            # If all checks pass
            print("   ✅ ACTIVE")
            return True, final_url, "ACTIVE"
            
        except requests.exceptions.Timeout:
            print("   ⚠ Timeout - Assuming active to be safe")
            return True, url, "TIMEOUT"
        except requests.exceptions.ConnectionError:
            print("   ⚠ Connection Error - Assuming active to be safe")
            return True, url, "CONNECTION_ERROR"
        except Exception as e:
            print(f"   ⚠ Error: {str(e)[:100]}")
            return True, url, f"ERROR_{type(e).__name__}"
    
    def normalize_url(self, url):
        """Normalize Bunnings URL format"""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        # Remove tracking parameters
        url = re.sub(r'[?&](utm_[^&]+|gclid|fbclid)=[^&]*', '', url)
        # Clean up double ? or trailing &
        url = re.sub(r'[?&]+$', '', url)
        url = re.sub(r'[?&]+', '?', url, count=1)
        return url
    
    def check_url_parameters(self, url):
        """Check URL for inactive parameters"""
        inactive_params = [
            'isinactiveproduct=true',
            'productunavailable=true',
            'discontinued=true',
            'status=inactive',
            'availability=false',
        ]
        
        url_lower = url.lower()
        for param in inactive_params:
            if param in url_lower:
                print(f"   ❌ Inactive URL parameter: {param}")
                return True
        return False
    
    def check_redirect_patterns(self, original_url, final_url):
        """Check if redirected to inactive or error pages"""
        # Check if redirected to search or category page
        search_patterns = [
            '/search',
            '/searchresult',
            '/category',
            '/s-',
            '/c-',
        ]
        
        for pattern in search_patterns:
            if pattern in final_url.lower() and pattern not in original_url.lower():
                print(f"   ❌ Redirected to search/category: {final_url}")
                return True
        
        # Check if redirected to homepage
        if 'bunnings.com.au' in final_url and '/product' not in final_url:
            print(f"   ❌ Redirected away from product page")
            return True
        
        return False
    
    def check_html_content(self, html_lower):
        """Check HTML content for inactive indicators"""
        # Comprehensive list of inactive indicators
        inactive_indicators = [
            # Product unavailable
            'product is no longer available',
            'this product has been discontinued',
            'product unavailable',
            'currently unavailable',
            'no longer stocked',
            'out of stock at',
            'not available online',
            'we couldn\'t find that product',
            
            # Error messages
            '404 error',
            'page not found',
            'this page doesn\'t exist',
            'we\'re sorry, but something went wrong',
            'product not found',
            
            # Bunnings specific
            'product may have been removed',
            'item may have been deleted',
            'check store availability',
            'available in selected stores only',
            'online only',
            
            # Generic
            'sorry',
            'error',
            'unavailable',
            'discontinued',
            'removed from sale',
            'no longer available for purchase',
        ]
        
        for indicator in inactive_indicators:
            if indicator in html_lower:
                print(f"   ❌ Found inactive indicator: '{indicator}'")
                return True
        
        # Check for "Add to Cart" button absence
        if 'add to cart' not in html_lower and 'add-to-cart' not in html_lower:
            print("   ⚠ No 'Add to Cart' button found")
            # Additional check for "Notify Me" which is sometimes used instead
            if 'notify me' not in html_lower and 'notify when back in stock' not in html_lower:
                print("   ❌ No purchase options available")
                return True
        
        return False
    
    def check_javascript_patterns(self, html):
        """Check JavaScript and JSON-LD for product status"""
        # Look for JSON-LD product data
        jsonld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
        matches = re.findall(jsonld_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    # Check availability
                    availability = data.get('availability', '')
                    if 'outofstock' in str(availability).lower() or 'discontinued' in str(availability).lower():
                        print("   ❌ JSON-LD indicates out of stock/discontinued")
                        return True
                    
                    # Check offers
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        if offers.get('availability', '').lower() == 'outofstock':
                            print("   ❌ JSON-LD offer indicates out of stock")
                            return True
            except:
                continue
        
        # Check for JavaScript variables indicating inactive status
        js_patterns = [
            r'productData\.isActive\s*=\s*false',
            r'product\.available\s*=\s*false',
            r'window\.productStatus\s*=\s*["\']inactive["\']',
            r'isinactiveproduct["\']?\s*[:=]\s*["\']?true',
            r'productunavailable["\']?\s*[:=]\s*["\']?true',
            r'data-product-available["\']?\s*[:=]\s*["\']?false',
        ]
        
        for pattern in js_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                print(f"   ❌ JavaScript indicates inactive: {pattern[:50]}")
                return True
        
        return False
    
    def check_meta_tags(self, html):
        """Check meta tags for noindex/nofollow"""
        meta_pattern = r'<meta[^>]+(?:name|property)=["\'](robots|googlebot)["\'][^>]+content=["\'][^>]*noindex[^>]*["\']'
        if re.search(meta_pattern, html, re.IGNORECASE):
            print("   ❌ Meta robots noindex found")
            return True
        
        # Check for canonical pointing elsewhere
        canonical_pattern = r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'][^>"\']+["\']'
        match = re.search(canonical_pattern, html, re.IGNORECASE)
        if match:
            canonical_href = re.search(r'href=["\']([^"\']+)["\']', match.group(0))
            if canonical_href and 'product' not in canonical_href.group(1).lower():
                print(f"   ❌ Canonical points away from product page")
                return True
        
        return False
    
    def check_bunnings_specific(self, html):
        """Check for Bunnings-specific patterns"""
        # Bunnings specific class names and IDs
        bunnings_patterns = [
            r'class=["\'][^"\']*product-unavailable[^"\']*["\']',
            r'class=["\'][^"\']*discontinued-product[^"\']*["\']',
            r'id=["\']unavailable-message["\']',
            r'data-testid=["\']product-unavailable["\']',
            r'class=["\'][^"\']*out-of-stock[^"\']*["\']',
        ]
        
        for pattern in bunnings_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                print(f"   ❌ Bunnings-specific inactive pattern: {pattern[:50]}")
                return True
        
        return False
    
    def check_product_data(self, html):
        """Check for missing critical product data"""
        # Product data that should be present
        required_selectors = [
            r'data-product-id=["\'][^"\']+["\']',
            r'data-sku=["\'][^"\']+["\']',
            r'productId["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'sku["\']?\s*[:=]\s*["\'][^"\']+["\']',
        ]
        
        found_count = 0
        for pattern in required_selectors:
            if re.search(pattern, html, re.IGNORECASE):
                found_count += 1
        
        # If no product identifiers found
        if found_count == 0:
            print("   ❌ No product identifiers found")
            return True
        
        return False
    
    def check_search_result_page(self, html_lower, final_url):
        """Check if we're on a search results page instead of product page"""
        search_indicators = [
            'search results',
            'searchresults',
            'multiple products found',
            'refine your search',
            'showing results for',
            'did you mean',
        ]
        
        # Check URL and content for search indicators
        if any(indicator in html_lower for indicator in search_indicators):
            # Verify it's not a product page with search-related text
            if 'product-details' not in html_lower and 'productDetails' not in html_lower:
                print("   ❌ Appears to be search results page, not product page")
                return True
        
        # Check for pagination or multiple products
        if ('class="product' in html_lower or 'class="search-result' in html_lower) and html_lower.count('class="product') > 2:
            print("   ❌ Multiple products found (likely search page)")
            return True
        
        return False

# ------------------ Shopify API Functions ------------------
def fetch_products():
    """Fetch products from Shopify"""
    query = f"""
    {{
      products(first: 250) {{
        nodes {{
          id
          title
          status
          handle
          onlineStoreUrl
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
    return data.get("data", {}).get("products", {}).get("nodes", [])

def update_product(product_id, status="DRAFT"):
    """Update product status"""
    mutation = f"""
    mutation {{
      productUpdate(input: {{ id: "{product_id}", status: {status} }}) {{
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
    print(f"🚀 Bunnings Link Checker - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Validate credentials
    if "yourstore" in SHOP or "shpat_xx" in TOKEN:
        print("❌ Please update SHOP and TOKEN in the script!")
        return
    
    # Initialize checker
    checker = BunningsChecker()
    
    # Fetch products
    products = fetch_products()
    print(f"📦 Found {len(products)} products")
    
    results = {
        'active': 0,
        'inactive': 0,
        'errors': 0,
        'inactive_reasons': {}
    }
    
    for p in products:
        print(f"\n{'='*60}")
        print(f"Product: {p.get('title', 'N/A')}")
        print(f"Shopify Status: {p.get('status', 'N/A')}")
        
        # Skip if already draft
        if p.get("status") == "DRAFT":
            print("  ⚠ Already DRAFT, skipping")
            continue
        
        # Get Bunnings URL
        mf = p.get("metafield")
        if not mf or not mf.get("value"):
            print("  ⚠ No Bunnings URL in metafield")
            continue
        
        url = mf["value"]
        
        # Check URL
        is_active, final_url, reason = checker.check_bunnings_url(url)
        
        if not is_active:
            print(f"  ❌ INACTIVE: {reason}")
            print(f"  📍 Final URL: {final_url[:100]}")
            
            # Update product to DRAFT
            result = update_product(p["id"])
            if "errors" in result or result.get("data", {}).get("productUpdate", {}).get("userErrors"):
                print("  ⚠ Failed to update product")
                results['errors'] += 1
            else:
                print("  ✅ Updated to DRAFT")
                results['inactive'] += 1
                results['inactive_reasons'][reason] = results['inactive_reasons'].get(reason, 0) + 1
        else:
            print(f"  ✅ ACTIVE ({reason})")
            results['active'] += 1
        
        # Be nice to the servers
        time.sleep(random.uniform(3, 6))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 FINAL SUMMARY")
    print("=" * 60)
    print(f"Active Products: {results['active']}")
    print(f"Inactive Products: {results['inactive']}")
    print(f"Errors: {results['errors']}")
    
    if results['inactive_reasons']:
        print("\n📈 Inactive Reasons:")
        for reason, count in results['inactive_reasons'].items():
            print(f"  {reason}: {count}")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
