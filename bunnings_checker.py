#!/usr/bin/env python3
"""
Bunnings URL Checker – Shopify Metafield Debugger
Finds your actual metafield structure before testing
"""

import time
import csv
import requests
import json
import re
from datetime import datetime
from requests.exceptions import RequestException, Timeout, SSLError, ConnectionError
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# =========================
# 🔐 SHOPIFY CONFIG (HARDCODED)
# =========================
SHOPIFY_STORE = "seydeltest"
SHOPIFY_TOKEN = "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"
SHOPIFY_API_VERSION = "2024-10"  # Changed to stable version
# =========================

class BunningsDebugger:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.session = requests.Session()
        
    def debug_metafield_structure(self, sample_size=5):
        """
        Debug function to find ALL metafields and see their structure
        """
        print("🔍 DEBUGGING METAFIELD STRUCTURE")
        print("="*60)
        
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        
        # Fetch products
        endpoint = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
        params = {"limit": sample_size, "fields": "id,title,vendor,product_type"}
        
        all_bunnings_urls = []
        metafield_patterns = {}
        
        try:
            r = requests.get(endpoint, headers=headers, params=params)
            if r.status_code != 200:
                print(f"❌ API Error: {r.status_code} - {r.text[:100]}")
                return None
                
            products = r.json().get("products", [])
            
            print(f"📦 Found {len(products)} products to examine")
            print("="*60)
            
            for i, product in enumerate(products, 1):
                pid = product["id"]
                title = product.get("title", "N/A")
                vendor = product.get("vendor", "")
                product_type = product.get("product_type", "")
                
                print(f"\n[{i}] 📦 Product: {title}")
                print(f"    ID: {pid} | Vendor: {vendor} | Type: {product_type}")
                print("    " + "-"*40)
                
                # Get ALL metafields for this product
                mf_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{pid}/metafields.json"
                mf_resp = requests.get(mf_url, headers=headers)
                
                if mf_resp.status_code == 200:
                    metafields = mf_resp.json().get("metafields", [])
                    
                    if metafields:
                        print(f"    Found {len(metafields)} metafields:")
                        
                        for mf in metafields:
                            namespace = mf.get("namespace", "")
                            key = mf.get("key", "")
                            value = str(mf.get("value", ""))
                            mf_type = mf.get("type", "")
                            mf_id = mf.get("id", "")
                            
                            # Store pattern for statistics
                            pattern = f"{namespace}.{key}"
                            metafield_patterns[pattern] = metafield_patterns.get(pattern, 0) + 1
                            
                            # Check for Bunnings URLs in any value
                            if "bunnings.com.au" in value.lower():
                                print(f"    ✅ FOUND BUNNINGS URL!")
                                print(f"        {namespace}.{key} ({mf_type})")
                                
                                # Try to extract clean URL
                                url = self.extract_clean_url(value)
                                print(f"        URL: {url[:80]}...")
                                
                                all_bunnings_urls.append({
                                    "product_id": pid,
                                    "product_title": title,
                                    "namespace": namespace,
                                    "key": key,
                                    "original_value": value[:100],
                                    "clean_url": url
                                })
                            else:
                                # Show first 50 chars of non-Bunnings values
                                display_value = value.replace('\n', ' ').replace('\r', ' ')
                                if len(display_value) > 50:
                                    display_value = display_value[:50] + "..."
                                print(f"    {namespace}.{key} = {display_value}")
                    else:
                        print("    No metafields found for this product")
                else:
                    print(f"    ❌ Error fetching metafields: {mf_resp.status_code}")
                
                # Small delay to avoid rate limiting
                if i < len(products):
                    time.sleep(0.3)
                    
        except Exception as e:
            print(f"❌ Debug error: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Print summary
        print("\n" + "="*60)
        print("📊 DEBUG SUMMARY")
        print("="*60)
        
        print(f"\n📦 Products examined: {len(products)}")
        print(f"🔗 Bunnings URLs found: {len(all_bunnings_urls)}")
        
        if metafield_patterns:
            print(f"\n🔍 Metafield patterns found:")
            for pattern, count in sorted(metafield_patterns.items(), key=lambda x: x[1], reverse=True):
                print(f"  {pattern}: {count} products")
        
        if all_bunnings_urls:
            print(f"\n✅ BUNNINGS URLS FOUND:")
            for url_info in all_bunnings_urls:
                print(f"\n  Product: {url_info['product_title'][:40]}...")
                print(f"    Metafield: {url_info['namespace']}.{url_info['key']}")
                print(f"    Clean URL: {url_info['clean_url'][:80]}...")
                print(f"    Original: {url_info['original_value']}...")
            
            # Save findings to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = f"bunnings_debug_findings_{timestamp}.json"
            with open(debug_file, 'w') as f:
                json.dump({
                    "store": SHOPIFY_STORE,
                    "products_examined": len(products),
                    "bunnings_urls_found": len(all_bunnings_urls),
                    "metafield_patterns": metafield_patterns,
                    "bunnings_urls": all_bunnings_urls
                }, f, indent=2)
            print(f"\n💾 Debug data saved to: {debug_file}")
            
            # Generate recommended METAFIELD_CONFIGS
            print(f"\n💡 RECOMMENDED METAFIELD_CONFIGS:")
            print("Copy this into your main script:")
            print("\nMETAFIELD_CONFIGS = [")
            unique_patterns = set()
            for url_info in all_bunnings_urls:
                pattern = {"namespace": url_info["namespace"], "key": url_info["key"]}
                if str(pattern) not in unique_patterns:
                    print(f'    {pattern},')
                    unique_patterns.add(str(pattern))
            print("]")
            
        else:
            print(f"\n❌ NO BUNNINGS URLS FOUND IN {len(products)} PRODUCTS")
            print("\nPossible issues:")
            print("1. Wrong Shopify store name or token")
            print("2. No products have Bunnings URLs yet")
            print("3. URLs stored differently (not in metafields)")
            print("4. Need to check more products")
            
            # Offer to check more products
            check_more = input(f"\nCheck more products? (Enter number or 'n'): ").strip()
            if check_more.lower() != 'n' and check_more.isdigit():
                return self.debug_metafield_structure(sample_size=int(check_more))
        
        return all_bunnings_urls
    
    def extract_clean_url(self, value):
        """Extract clean URL from various formats"""
        if not value:
            return ""
        
        value = str(value).strip()
        
        # Try JSON format
        try:
            data = json.loads(value)
            if isinstance(data, dict):
                # Look for URL in common keys
                for key in ['url', 'link', 'href', 'bunnings_url', 'source', 'reference']:
                    if key in data and data[key]:
                        url = str(data[key]).strip()
                        if "bunnings.com.au" in url.lower():
                            return url
        except:
            pass
        
        # Look for URL pattern
        url_pattern = r'https?://[^\s<>"\']+'
        matches = re.findall(url_pattern, value)
        for match in matches:
            if "bunnings.com.au" in match.lower():
                return match
        
        # Return original if no clean URL found
        return value[:100] + ("..." if len(value) > 100 else "")
    
    def test_api_connection(self):
        """Test if Shopify API connection works"""
        print("\n🔧 TESTING SHOPIFY API CONNECTION")
        print("="*60)
        
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }
        
        # Test 1: Get product count
        count_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/count.json"
        try:
            r = requests.get(count_url, headers=headers, timeout=10)
            if r.status_code == 200:
                count = r.json().get("count", 0)
                print(f"✅ API Connection Successful!")
                print(f"   Store: {SHOPIFY_STORE}")
                print(f"   Total Products: {count}")
                return True
            else:
                print(f"❌ API Error: {r.status_code}")
                print(f"   Response: {r.text[:100]}")
                return False
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            return False
    
    def quick_bunnings_test(self, test_url):
        """Quick test of a Bunnings URL"""
        if not self.driver:
            self.setup_driver()
        
        print(f"\n🚀 QUICK TEST: {test_url[:60]}...")
        
        try:
            self.driver.get(test_url)
            time.sleep(5)
            
            title = self.driver.title
            print(f"   Title: {title}")
            
            page_source = self.driver.page_source.lower()
            
            if "bunnings" in page_source:
                print("   ✅ Bunnings page detected")
                
                # Look for Add to Cart
                cart_found = False
                texts = ["add to cart", "add to trolley"]
                for t in texts:
                    try:
                        elements = self.driver.find_elements(
                            By.XPATH,
                            f"//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{t}')]"
                        )
                        for element in elements:
                            if element.is_displayed():
                                cart_found = True
                                print(f"   ✅ Found: '{t}'")
                                break
                        if cart_found:
                            break
                    except:
                        continue
                
                if cart_found:
                    print("   ✅ PRODUCT IS WORKING")
                else:
                    print("   ❌ No Add to Cart found (might be out of stock)")
            else:
                print("   ❌ Not a Bunnings page")
                
        except Exception as e:
            print(f"   ❌ Test error: {e}")
    
    def setup_driver(self):
        """Setup browser for quick tests"""
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f'user-agent={user_agent}')
        
        self.driver = uc.Chrome(options=options, use_subprocess=True)
        print("✅ Browser ready for testing")
    
    def close(self):
        """Cleanup"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass


def main_menu():
    """Main menu for debugging"""
    print("\n" + "="*60)
    print("🏪 BUNNINGS METAFIELD DEBUGGER")
    print("="*60)
    print("This tool helps you find how Bunnings URLs are stored")
    print("="*60)
    
    debugger = BunningsDebugger(headless=True)
    
    try:
        # First test API connection
        if not debugger.test_api_connection():
            print("\n❌ Cannot connect to Shopify. Check:")
            print(f"   1. Store name: {SHOPIFY_STORE}")
            print(f"   2. API token: {SHOPIFY_TOKEN[:20]}...")
            print(f"   3. API version: {SHOPIFY_API_VERSION}")
            return
        
        print("\nOptions:")
        print("  1. Debug metafield structure (find Bunnings URLs)")
        print("  2. Test a specific Bunnings URL")
        print("  3. Check more products")
        print("="*60)
        
        choice = input("\nEnter choice (1-3): ").strip() or "1"
        
        if choice == "1":
            sample = input("How many products to check? (default: 5): ").strip()
            sample_size = int(sample) if sample.isdigit() else 5
            debugger.debug_metafield_structure(sample_size=sample_size)
            
        elif choice == "2":
            test_url = input("Enter Bunnings URL to test: ").strip()
            if test_url:
                debugger.quick_bunnings_test(test_url)
            else:
                print("❌ No URL provided")
                
        elif choice == "3":
            sample = input("How many products to check? (default: 20): ").strip()
            sample_size = int(sample) if sample.isdigit() else 20
            debugger.debug_metafield_structure(sample_size=sample_size)
            
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        debugger.close()
        print("\n✨ Debug complete!")


# ===== MAIN =====
if __name__ == "__main__":
    main_menu()
