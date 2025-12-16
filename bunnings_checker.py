#!/usr/bin/env python3
"""
Bunnings URL Checker - SHOPIFY METAFIELD INTEGRATION
Fetches Bunnings URLs from Shopify metafields and checks for Add to Cart button
"""

import time
import os
import csv
import requests
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# Shopify Configuration - UPDATE THESE VALUES
SHOPIFY_STORE_DOMAIN = "cassien24.myshopify.com"  # Your Shopify store domain
SHOPIFY_ACCESS_TOKEN = "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"  # Your Shopify access token
METAFIELD_NAMESPACE = "custom"  # Metafield namespace
METAFIELD_KEY = "au_link"  # Metafield key for Bunnings URLs

class BunningsShopifyChecker:
    def __init__(self, headless=False):
        """Initialize browser and Shopify connection"""
        self.headless = headless
        self.driver = None
        self.shopify_headers = {
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json"
        }
        self.setup_driver()
    
    def setup_driver(self):
        """Setup browser"""
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument('--headless=new')
            
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            
            # Block location
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.geolocation": 2,
                "profile.default_content_setting_values.notifications": 2,
            })
            
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options.add_argument(f'user-agent={user_agent}')
            
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            
            print("✅ Browser ready")
            
        except Exception as e:
            print(f"❌ Browser error: {e}")
            raise
    
    def fetch_products_with_bunnings_urls(self):
        """
        Fetch all products with Bunnings URLs from Shopify metafields
        Returns: List of products with their Bunnings URLs
        """
        print("📡 Fetching products from Shopify...")
        
        products_with_urls = []
        next_page_url = None
        
        try:
            # Initial API call
            if next_page_url:
                url = next_page_url
            else:
                url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2024-01/products.json?limit=250&fields=id,title,handle,metafields"
            
            while url:
                response = requests.get(url, headers=self.shopify_headers)
                
                if response.status_code != 200:
                    print(f"❌ Shopify API error: {response.status_code}")
                    print(f"Response: {response.text[:200]}")
                    break
                
                products_data = response.json()
                products = products_data.get('products', [])
                
                # Process each product
                for product in products:
                    product_id = product.get('id')
                    product_title = product.get('title', 'Unknown Product')
                    product_handle = product.get('handle', '')
                    metafields = product.get('metafields', [])
                    
                    # Look for Bunnings URL metafield
                    bunnings_url = None
                    for metafield in metafields:
                        if (metafield.get('namespace') == METAFIELD_NAMESPACE and 
                            metafield.get('key') == METAFIELD_KEY):
                            bunnings_url = metafield.get('value')
                            break
                    
                    if bunnings_url and 'bunnings.com.au' in bunnings_url.lower():
                        products_with_urls.append({
                            'product_id': product_id,
                            'product_title': product_title,
                            'product_handle': product_handle,
                            'bunnings_url': bunnings_url
                        })
                        print(f"   ✓ Found: {product_title} -> {bunnings_url[:60]}...")
                
                # Check for next page
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    # Extract next page URL
                    import re
                    match = re.search(r'<([^>]+)>; rel="next"', link_header)
                    if match:
                        url = match.group(1)
                    else:
                        url = None
                else:
                    url = None
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            print(f"✅ Found {len(products_with_urls)} product(s) with Bunnings URLs")
            
        except Exception as e:
            print(f"❌ Error fetching from Shopify: {e}")
        
        return products_with_urls
    
    def check_bunnings_url(self, url):
        """
        DIRECT CHECK: Load Bunnings URL, check for Add to Cart
        """
        print(f"\n🔗 Testing: {url[:80]}...")
        
        result = {
            'url': url,
            'page_title': 'Not loaded',
            'status': 'not_tested',
            'is_working': False,
            'add_to_cart_found': False,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # 1. Load the URL
            self.driver.get(url)
            time.sleep(8)  # Wait for initial load
            
            # 2. Get page title
            title = self.driver.title
            result['page_title'] = title
            print(f"   Title: {title[:60]}...")
            
            # 3. Check for Cloudflare
            if "Just a moment" in title:
                print("   ⚠️ Cloudflare, waiting...")
                time.sleep(10)
                title = self.driver.title
                
                if "Just a moment" in title:
                    result['status'] = 'cloudflare_blocked'
                    print("   ❌ Cloudflare blocked")
                    return result
            
            # 4. Check if it's a Bunnings page
            page_source = self.driver.page_source.lower()
            if not ('bunnings' in page_source or 'bunnings.com.au' in title.lower()):
                result['status'] = 'not_bunnings'
                print("   ❌ Not a Bunnings page")
                return result
            
            # 5. Look for Add to Cart button
            time.sleep(3)
            
            # Method 1: Search for button text
            add_to_cart_found = False
            
            cart_texts = ['Add to Cart', 'Add to Trolley', 'Add to cart', 'Add to trolley']
            for text in cart_texts:
                try:
                    elements = self.driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                    for element in elements:
                        try:
                            if element.is_displayed():
                                add_to_cart_found = True
                                print(f"   ✓ Found: '{text}'")
                                break
                        except:
                            continue
                    if add_to_cart_found:
                        break
                except:
                    continue
            
            # Method 2: Search for common selectors
            if not add_to_cart_found:
                selectors = [
                    "button[data-testid='add-to-cart']",
                    "button[data-test-id='add-to-cart']",
                    ".add-to-cart-button",
                    ".add-to-cart",
                    "#add-to-cart",
                    "[aria-label*='Add to cart']",
                    "[aria-label*='Add to trolley']",
                    "button.btn-primary",
                    "button.btn--primary"
                ]
                
                for selector in selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            try:
                                if element.is_displayed():
                                    text = element.text.lower()
                                    if 'add to' in text or 'cart' in text or 'trolley' in text:
                                        add_to_cart_found = True
                                        print(f"   ✓ Found via: {selector}")
                                        break
                            except:
                                continue
                        if add_to_cart_found:
                            break
                    except:
                        continue
            
            result['add_to_cart_found'] = add_to_cart_found
            
            # 6. Determine result
            if add_to_cart_found:
                result['status'] = 'working'
                result['is_working'] = True
                print("   ✅ WORKING - Add to Cart found")
            else:
                # Check why not working
                page_text = self.driver.page_source.lower()
                
                if 'out of stock' in page_text:
                    result['status'] = 'out_of_stock'
                    print("   ⚠️ OUT OF STOCK")
                elif 'product not found' in page_text or '404' in page_text:
                    result['status'] = 'not_found'
                    print("   ❌ 404 - Product not found")
                elif 'no longer available' in page_text:
                    result['status'] = 'discontinued'
                    print("   ❌ Discontinued")
                else:
                    result['status'] = 'no_add_to_cart'
                    print("   ❌ No Add to Cart button")
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"   ❌ Error: {str(e)[:50]}...")
        
        return result
    
    def bulk_test_from_shopify(self, output_file=None):
        """
        Test Bunnings URLs fetched from Shopify metafields
        """
        print("\n" + "="*60)
        print("🛍️  BUNNINGS URL CHECKER - SHOPIFY INTEGRATION")
        print("="*60)
        
        # Fetch products from Shopify
        products = self.fetch_products_with_bunnings_urls()
        
        if not products:
            print("❌ No products with Bunnings URLs found in Shopify")
            return []
        
        print(f"✅ Found {len(products)} product(s) with Bunnings URLs")
        print("="*60)
        
        # Test each URL
        results = []
        
        for i, product in enumerate(products, 1):
            product_title = product['product_title']
            bunnings_url = product['bunnings_url']
            
            print(f"\n[{i}/{len(products)}] {product_title}")
            print(f"   URL: {bunnings_url[:80]}...")
            
            result = self.check_bunnings_url(bunnings_url)
            
            # Add Shopify product info to result
            result['shopify_product_id'] = product['product_id']
            result['shopify_product_title'] = product_title
            result['shopify_product_handle'] = product['product_handle']
            
            results.append(result)
            
            # Small delay between tests
            if i < len(products):
                time.sleep(2)
        
        # Save results
        if output_file:
            report_file = output_file
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"shopify_test_results_{timestamp}.csv"
        
        self.save_results_csv(results, report_file)
        
        # Print summary
        self.print_summary(results)
        
        return results
    
    def save_results_csv(self, results, filename):
        """Save results to CSV"""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Shopify_Product_ID',
                'Shopify_Product_Title',
                'Shopify_Product_Handle',
                'Bunnings_URL',
                'Page_Title',
                'Status',
                'Working',
                'Add_to_Cart_Found',
                'Error',
                'Test_Time'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                writer.writerow({
                    'Shopify_Product_ID': result.get('shopify_product_id', ''),
                    'Shopify_Product_Title': result.get('shopify_product_title', '')[:100],
                    'Shopify_Product_Handle': result.get('shopify_product_handle', ''),
                    'Bunnings_URL': result['url'],
                    'Page_Title': result['page_title'][:200] if result['page_title'] else '',
                    'Status': result['status'],
                    'Working': 'Yes' if result['is_working'] else 'No',
                    'Add_to_Cart_Found': 'Yes' if result['add_to_cart_found'] else 'No',
                    'Error': result['error'] or '',
                    'Test_Time': result['timestamp']
                })
        
        print(f"\n📊 Results saved to: {filename}")
    
    def print_summary(self, results):
        """Print summary statistics"""
        if not results:
            return
        
        working = sum(1 for r in results if r['is_working'])
        broken = len(results) - working
        
        print("\n" + "="*60)
        print("📋 SUMMARY")
        print("="*60)
        print(f"Total Products Tested: {len(results)}")
        print(f"✅ Working: {working}")
        print(f"❌ Broken: {broken}")
        
        # Breakdown by status
        status_counts = {}
        for r in results:
            status = r['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\n📈 Breakdown:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
        
        # List broken products
        broken_products = [r for r in results if not r['is_working']]
        if broken_products:
            print("\n🔴 Broken Products:")
            for product in broken_products:
                title = product.get('shopify_product_title', 'Unknown')
                status = product['status']
                print(f"  • {title} ({status})")
    
    def update_product_status(self, product_id, new_status):
        """
        Update product status in Shopify (e.g., draft if Bunnings link is broken)
        You can extend this to mark products as draft when links are broken
        """
        if not SHOPIFY_ACCESS_TOKEN:
            print("⚠️  Shopify access token not configured - skipping status update")
            return False
        
        try:
            url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2024-01/products/{product_id}.json"
            
            # For example, set product to draft if link is broken
            data = {
                "product": {
                    "id": product_id,
                    "status": "draft" if new_status == "broken" else "active"
                }
            }
            
            response = requests.put(url, headers=self.shopify_headers, json=data)
            
            if response.status_code == 200:
                print(f"✅ Updated product {product_id} status to {data['product']['status']}")
                return True
            else:
                print(f"❌ Failed to update product status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating product: {e}")
            return False
    
    def close(self):
        """Close browser"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass


def main():
    """Main function"""
    print("\n" + "="*60)
    print("🛍️  BUNNINGS URL CHECKER - SHOPIFY EDITION")
    print("="*60)
    print("Fetches Bunnings URLs from Shopify metafields and checks them")
    print("="*60)
    
    # Check configuration
    if SHOPIFY_STORE_DOMAIN == "your-store.myshopify.com" or SHOPIFY_ACCESS_TOKEN == "shpat_your_access_token_here":
        print("\n⚠️  CONFIGURATION REQUIRED")
        print("Please update the following values at the top of the script:")
        print(f"  1. SHOPIFY_STORE_DOMAIN: Your Shopify store domain")
        print(f"  2. SHOPIFY_ACCESS_TOKEN: Your Shopify Admin API access token")
        print("\nTo get an access token:")
        print("  1. Go to Shopify Admin → Settings → Apps and sales channels")
        print("  2. Click 'Develop apps' → Create an app")
        print("  3. Configure Admin API scopes: read_products, read_metafields")
        print("  4. Install app and copy the access token")
        print("="*60)
        return
    
    print("\nOptions:")
    print("  1. Test URLs from Shopify metafields (bulk)")
    print("  2. Test single URL")
    print("  3. Fallback: Test URLs from file")
    print("="*60)
    
    try:
        choice = input("\nEnter choice (1-3): ").strip() or "1"
        
        # Initialize
        print("\n🚀 Starting browser...")
        checker = BunningsShopifyChecker(headless=False)  # Set True for no window
        
        if choice == "2":
            # Test single URL
            default_url = "https://www.bunnings.com.au/orion-grid-connect-smart-rechargeable-2k-security-camera-4-pack_p0503618?pid=0503618"
            url = input(f"Enter Bunnings URL [default: {default_url}]: ").strip()
            if not url:
                url = default_url
            
            result = checker.check_bunnings_url(url)
            
            print("\n" + "="*60)
            print("📋 RESULT")
            print("="*60)
            print(f"URL: {result['url']}")
            print(f"Title: {result['page_title']}")
            print(f"Status: {result['status']}")
            print(f"Working: {'✅ YES' if result['is_working'] else '❌ NO'}")
            print(f"Add to Cart: {'✅ FOUND' if result['add_to_cart_found'] else '❌ NOT FOUND'}")
            
        elif choice == "3":
            # Fallback to file method
            print(f"\n📁 Current directory: {os.getcwd()}")
            default_file = os.path.join(os.getcwd(), "bunnings_urls.txt")
            input_file = input(f"\nFile path [default: {default_file}]: ").strip()
            
            if not input_file:
                input_file = default_file
            
            input_file = os.path.expanduser(input_file)
            
            # Use original method for file-based testing
            urls = []
            if os.path.exists(input_file):
                with open(input_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and 'bunnings.com.au' in line.lower():
                            urls.append(line)
                
                if urls:
                    results = []
                    for i, url in enumerate(urls, 1):
                        print(f"\n[{i}/{len(urls)}] ", end="")
                        result = checker.check_bunnings_url(url)
                        results.append(result)
                        if i < len(urls):
                            time.sleep(2)
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    report_file = f"file_test_results_{timestamp}.csv"
                    checker.save_results_csv(results, report_file)
                    checker.print_summary(results)
                else:
                    print("❌ No valid Bunnings URLs found in file")
            else:
                print(f"❌ File not found: {input_file}")
            
        else:
            # Main option: Test from Shopify
            checker.bulk_test_from_shopify()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        if 'checker' in locals():
            checker.close()
        print("\n✨ Done!")


if __name__ == "__main__":
    main()
