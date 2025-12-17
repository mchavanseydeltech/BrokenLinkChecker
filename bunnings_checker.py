#!/usr/bin/env python3
"""
BUNNINGS URL CHECKER WITH SHOPIFY INTEGRATION
Fetches URLs from Shopify au_link metafields and checks Add to Cart availability
"""

import time
import csv
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================================
# SHOPIFY API - CRITICAL IMPORT SECTION
# ============================================================================
try:
    # You install "shopifyapi" but import it as "shopify"
    import shopify
    print(f"✅ Shopify API imported successfully")
except ImportError as e:
    print(f"❌ FATAL: Could not import Shopify API. Error: {e}")
    print("\n💡 SOLUTION: Install the correct package:")
    print("   pip install shopifyapi")
    print("\nThe PyPI package is 'shopifyapi' but you import it as 'shopify'")
    sys.exit(1)

# ============================================================================
# SELENIUM IMPORTS
# ============================================================================
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc

# ============================================================================
# CONFIGURATION - EDIT THESE VALUES
# ============================================================================
SHOPIFY_CONFIG = {
    'shop_url': 'seydeltest.myshopify.com',
    'access_token': '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',
    'api_version': '2025-10',
}

BUNNINGS_CONFIG = {
    'headless_mode': True,
    'timeout_seconds': 30,
    'delay_between_tests': 3,
    'max_products': 50,
}

# ============================================================================
# SHOPIFY INTEGRATION CLASS
# ============================================================================
class ShopifyBunningsChecker:
    def __init__(self):
        """Initialize the checker with Shopify and Selenium"""
        self.driver = None
        self.setup_shopify()
        self.setup_browser()
    
    def setup_shopify(self):
        """Connect to Shopify API"""
        try:
            shop_url = SHOPIFY_CONFIG['shop_url']
            access_token = SHOPIFY_CONFIG['access_token']
            api_version = SHOPIFY_CONFIG['api_version']
            
            shopify.Session.setup(api_key="", password="")
            session = shopify.Session(shop_url, api_version, access_token)
            shopify.ShopifyResource.activate_session(session)
            
            print(f"✅ Connected to Shopify: {shop_url}")
        except Exception as e:
            print(f"❌ Shopify connection failed: {e}")
            sys.exit(1)
    
    def setup_browser(self):
        """Setup undetected Chrome browser for GitHub Actions"""
        try:
            options = uc.ChromeOptions()
            
            if BUNNINGS_CONFIG['headless_mode']:
                options.add_argument('--headless=new')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
            
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1920,1080')
            
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            options.add_argument(f'user-agent={user_agent}')
            
            self.driver = uc.Chrome(options=options)
            self.driver.set_page_load_timeout(BUNNINGS_CONFIG['timeout_seconds'])
            print("✅ Browser initialized")
            
        except Exception as e:
            print(f"❌ Browser setup failed: {e}")
            sys.exit(1)
    
    def fetch_products_with_bunnings_urls(self, limit: int = 50) -> List[Dict]:
        """Fetch Shopify products with Bunnings URLs in au_link metafield"""
        print(f"\n📦 Fetching products from Shopify (limit: {limit})...")
        products = []
        
        try:
            shopify_products = shopify.Product.find(limit=limit)
            print(f"Found {len(shopify_products)} total products")
            
            for product in shopify_products:
                metafields = product.metafields()
                for metafield in metafields:
                    if (metafield.key == 'au_link' and metafield.value and 
                        'bunnings.com.au' in metafield.value.lower()):
                        
                        product_info = {
                            'id': product.id,
                            'title': product.title,
                            'handle': product.handle,
                            'shopify_url': f"https://{SHOPIFY_CONFIG['shop_url']}/products/{product.handle}",
                            'bunnings_url': metafield.value.strip(),
                            'status': 'active' if product.published_at else 'draft',
                            'vendor': product.vendor or '',
                            'product_type': product.product_type or '',
                        }
                        products.append(product_info)
                        print(f"  ✓ {product.title[:40]}...")
                        break
            
            print(f"\n✅ Found {len(products)} products with Bunnings URLs")
            return products
            
        except Exception as e:
            print(f"❌ Error fetching products: {e}")
            return []
    
    def check_bunnings_availability(self, url: str) -> Dict:
        """Check if Add to Cart is available on Bunnings page"""
        result = {
            'url': url,
            'available': False,
            'status': 'unknown',
            'title': '',
            'price': '',
            'error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"\n🔍 Checking: {url[:80]}...")
        
        try:
            self.driver.get(url)
            time.sleep(5)
            
            page_title = self.driver.title
            result['title'] = page_title
            
            if "Just a moment" in page_title:
                print("  ⚠️  Cloudflare detected, waiting...")
                time.sleep(10)
            
            if not ('bunnings' in page_title.lower() or 'bunnings.com.au' in url):
                result['status'] = 'not_bunnings'
                return result
            
            time.sleep(3)
            
            # Look for Add to Cart button
            cart_found = False
            cart_texts = ['Add to Cart', 'Add to Trolley', 'Add to cart', 'Add to trolley']
            
            for text in cart_texts:
                try:
                    elements = self.driver.find_elements(By.XPATH, 
                        f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                    for element in elements:
                        if element.is_displayed():
                            cart_found = True
                            break
                    if cart_found:
                        break
                except:
                    continue
            
            if not cart_found:
                page_source = self.driver.page_source.lower()
                if 'out of stock' in page_source:
                    result['status'] = 'out_of_stock'
                elif 'sold out' in page_source:
                    result['status'] = 'sold_out'
                elif 'discontinued' in page_source:
                    result['status'] = 'discontinued'
                elif '404' in page_source:
                    result['status'] = 'not_found'
                else:
                    result['status'] = 'no_cart_button'
            else:
                result['available'] = True
                result['status'] = 'available'
                
                # Try to get price
                try:
                    price_selectors = ["[data-testid='price']", ".price", ".product-price"]
                    for selector in price_selectors:
                        try:
                            price_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if price_elem.is_displayed():
                                result['price'] = price_elem.text.strip()
                                break
                        except:
                            continue
                except:
                    pass
        
        except TimeoutException:
            result['status'] = 'timeout'
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        status_emoji = '✅' if result['available'] else '❌'
        print(f"  {status_emoji} {result['status'].upper()}")
        return result
    
    def update_shopify_stock_status(self, product_id: int, status: str) -> bool:
        """Update Shopify product with Bunnings stock status"""
        try:
            product = shopify.Product.find(product_id)
            
            # Check if metafield exists
            existing_metafield = None
            for mf in product.metafields():
                if mf.namespace == 'bunnings' and mf.key == 'stock_status':
                    existing_metafield = mf
                    break
            
            if existing_metafield:
                existing_metafield.value = status
                success = existing_metafield.save()
            else:
                metafield = shopify.Metafield({
                    'namespace': 'bunnings',
                    'key': 'stock_status',
                    'value': status,
                    'type': 'single_line_text_field'
                })
                success = product.add_metafield(metafield)
            
            if success:
                print(f"  ✅ Updated Shopify: bunnings.stock_status = '{status}'")
                return True
            else:
                print(f"  ❌ Failed to update Shopify")
                return False
                
        except Exception as e:
            print(f"  ❌ Error updating Shopify: {e}")
            return False
    
    def run_check(self, update_shopify: bool = True):
        """Main function: Fetch products, check Bunnings, update Shopify"""
        print("\n" + "="*60)
        print("🛒 BUNNINGS AVAILABILITY CHECKER")
        print("="*60)
        
        products = self.fetch_products_with_bunnings_urls(limit=BUNNINGS_CONFIG['max_products'])
        
        if not products:
            print("\n❌ No products to check. Exiting.")
            return
        
        print(f"\n🚀 Checking {len(products)} products...")
        results = []
        
        for i, product in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] {product['title'][:40]}...")
            check_result = self.check_bunnings_availability(product['bunnings_url'])
            
            full_result = {**product, **check_result, 'shopify_updated': False}
            
            if update_shopify and check_result['status'] != 'unknown':
                updated = self.update_shopify_stock_status(product['id'], check_result['status'])
                full_result['shopify_updated'] = updated
            
            results.append(full_result)
            
            if i < len(products):
                time.sleep(BUNNINGS_CONFIG['delay_between_tests'])
        
        self.save_results(results)
        self.show_summary(results)
    
    def save_results(self, results: List[Dict]):
        """Save results to CSV and JSON files"""
        if not results:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save CSV
        csv_filename = f"bunnings_check_results_{timestamp}.csv"
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'product_id', 'title', 'bunnings_url', 'status', 
                'available', 'price', 'shopify_updated', 'timestamp', 'error'
            ])
            writer.writeheader()
            for result in results:
                writer.writerow({
                    'product_id': result['id'],
                    'title': result['title'][:100],
                    'bunnings_url': result['bunnings_url'],
                    'status': result['status'],
                    'available': 'Yes' if result['available'] else 'No',
                    'price': result.get('price', ''),
                    'shopify_updated': 'Yes' if result.get('shopify_updated') else 'No',
                    'timestamp': result['timestamp'],
                    'error': result.get('error', '')[:200]
                })
        
        # Save JSON summary
        json_filename = f"bunnings_check_summary_{timestamp}.json"
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_checked': len(results),
            'available': sum(1 for r in results if r['available']),
            'not_available': len(results) - sum(1 for r in results if r['available']),
            'status_counts': {},
            'products': [{'id': r['id'], 'title': r['title'], 'status': r['status'], 
                         'available': r['available']} for r in results]
        }
        
        for result in results:
            status = result['status']
            summary['status_counts'][status] = summary['status_counts'].get(status, 0) + 1
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📊 Results saved to: {csv_filename}")
        print(f"📋 Summary saved to: {json_filename}")
    
    def show_summary(self, results: List[Dict]):
        """Display summary of results"""
        if not results:
            return
        
        available = sum(1 for r in results if r['available'])
        
        print("\n" + "="*60)
        print("📋 CHECK SUMMARY")
        print("="*60)
        print(f"Total products checked: {len(results)}")
        print(f"✅ Available on Bunnings: {available}")
        print(f"❌ Not available: {len(results) - available}")
        
        status_counts = {}
        for r in results:
            status_counts[r['status']] = status_counts.get(r['status'], 0) + 1
        
        print("\n📈 Status breakdown:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
    
    def close(self):
        """Cleanup resources"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n✅ Browser closed")
            except:
                pass
        try:
            shopify.ShopifyResource.clear_session()
            print("✅ Shopify session closed")
        except:
            pass

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def quick_run():
    """Simplified version for automation"""
    print(f"\n⚡ Quick Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        BUNNINGS_CONFIG['headless_mode'] = True
        checker = ShopifyBunningsChecker()
        checker.run_check(update_shopify=True)
        checker.close()
        return True
    except Exception as e:
        print(f"❌ Quick run failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--quick', '-q']:
        success = quick_run()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("\nUsage:")
        print("  python bunnings_checker.py          # Interactive mode")
        print("  python bunnings_checker.py --quick  # Automated mode")
    else:
        print("\n" + "="*60)
        print("🏪 BUNNINGS AVAILABILITY CHECKER")
        print("="*60)
        print("\nStarting in interactive mode...")
        checker = None
        try:
            BUNNINGS_CONFIG['headless_mode'] = False
            checker = ShopifyBunningsChecker()
            checker.run_check(update_shopify=True)
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            if checker:
                checker.close()
            print("\n✨ Done!")
