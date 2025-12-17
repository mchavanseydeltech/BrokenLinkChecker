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
# Shopify API
import shopify
# Selenium for browser automation
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
    'shop_url': 'seydeltest.myshopify.com',           # Your Shopify store URL
    'access_token': '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', # Shopify API token
    'api_version': '2025-10',                         # Shopify API version
}

BUNNINGS_CONFIG = {
    'headless_mode': True,        # Set True for GitHub Actions, False for local
    'timeout_seconds': 30,        # Max wait for page elements
    'delay_between_tests': 3,     # Seconds between URL tests
    'max_products': 50,           # Maximum products to check
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
            
            # Initialize Shopify session
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
                options.add_argument('--remote-debugging-port=9222')
            
            # Browser settings to appear more human
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--window-size=1920,1080')
            
            # User agent
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options.add_argument(f'user-agent={user_agent}')
            
            # Disable notifications and location
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.geolocation": 2,
            })
            
            # For GitHub Actions, try to find Chrome
            chrome_paths = [
                '/usr/bin/google-chrome-stable',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium',
                '/usr/bin/google-chrome'
            ]
            
            for path in chrome_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    print(f"✅ Found Chrome at: {path}")
                    break
            
            # Create driver
            self.driver = uc.Chrome(
                options=options,
                version_main=120,
                use_subprocess=True
            )
            
            # Set page load timeout
            self.driver.set_page_load_timeout(BUNNINGS_CONFIG['timeout_seconds'])
            
            print("✅ Browser initialized")
            
        except Exception as e:
            print(f"❌ Browser setup failed: {e}")
            
            # Try fallback with regular selenium
            try:
                print("Attempting fallback with regular selenium...")
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options
                
                chrome_options = Options()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--window-size=1920,1080')
                
                # Try to find chromedriver
                chromedriver_paths = [
                    '/usr/local/bin/chromedriver',
                    '/usr/bin/chromedriver',
                    '/usr/lib/chromium-browser/chromedriver'
                ]
                
                service = None
                for path in chromedriver_paths:
                    if os.path.exists(path):
                        service = Service(path)
                        print(f"✅ Found chromedriver at: {path}")
                        break
                
                if service:
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    print("✅ Browser initialized with fallback method")
                else:
                    # Last resort: let selenium manage driver
                    self.driver = webdriver.Chrome(options=chrome_options)
                    print("✅ Browser initialized with auto-managed driver")
                    
            except Exception as e2:
                print(f"❌ All browser setup methods failed: {e2}")
                print("\nTroubleshooting tips for GitHub Actions:")
                print("1. Check Chrome is installed: sudo apt-get install -y chromium-browser")
                print("2. Check chromedriver is installed: sudo apt-get install -y chromium-chromedriver")
                print("3. Try: pip install --upgrade undetected-chromedriver")
                sys.exit(1)
    
    def fetch_products_with_bunnings_urls(self, limit: int = 50) -> List[Dict]:
        """
        Fetch Shopify products that have au_link metafields with Bunnings URLs
        """
        print(f"\n📦 Fetching products from Shopify (limit: {limit})...")
        
        products = []
        
        try:
            # Get all products
            shopify_products = shopify.Product.find(limit=limit)
            
            print(f"Found {len(shopify_products)} total products")
            
            for product in shopify_products:
                # Get metafields for this product
                metafields = product.metafields()
                
                for metafield in metafields:
                    # Check for au_link metafield
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
                        break  # Found au_link, move to next product
            
            print(f"\n✅ Found {len(products)} products with Bunnings URLs")
            
            if not products:
                print("No products found with 'au_link' metafield containing Bunnings URLs.")
                print("Make sure your products have 'au_link' metafield with Bunnings URLs.")
            
            return products
            
        except Exception as e:
            print(f"❌ Error fetching products: {e}")
            return []
    
    def check_bunnings_availability(self, url: str) -> Dict:
        """
        Check if Add to Cart is available on Bunnings page
        """
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
            # Load the page
            self.driver.get(url)
            time.sleep(5)  # Initial load wait
            
            # Check for Cloudflare or blocking
            page_title = self.driver.title
            result['title'] = page_title
            
            if "Just a moment" in page_title or "Checking your browser" in self.driver.page_source:
                print("  ⚠️  Cloudflare detected, waiting longer...")
                time.sleep(10)
                page_title = self.driver.title
            
            # Check if we're on Bunnings
            if not ('bunnings' in page_title.lower() or 'bunnings.com.au' in url):
                result['status'] = 'not_bunnings'
                print("  ❌ Not a Bunnings page")
                return result
            
            # Wait for page to fully load
            time.sleep(3)
            
            # METHOD 1: Look for Add to Cart button by text
            cart_found = False
            
            # List of possible Add to Cart button texts
            cart_texts = [
                'Add to Cart', 
                'Add to Trolley',
                'Add to cart', 
                'Add to trolley',
                'ADD TO CART',
                'ADD TO TROLLEY'
            ]
            
            for text in cart_texts:
                try:
                    # Try finding by button text
                    elements = self.driver.find_elements(By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            cart_found = True
                            print(f"  ✅ Found: '{text}' button")
                            break
                    
                    if cart_found:
                        break
                        
                except Exception:
                    continue
            
            # METHOD 2: Look for common selectors
            if not cart_found:
                selectors = [
                    "button[data-testid='add-to-cart']",
                    "button[data-test-id='add-to-cart']",
                    "[data-locator='add-to-cart']",
                    ".add-to-cart-button",
                    ".add-to-cart",
                    "#add-to-cart",
                    "[aria-label*='add to cart']",
                    "[aria-label*='add to trolley']",
                    "button.btn-primary",
                    "button.btn--primary",
                ]
                
                for selector in selectors:
                    try:
                        # Try CSS selector
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        for element in elements:
                            try:
                                if element.is_displayed():
                                    element_text = element.text.lower()
                                    if any(term in element_text for term in ['add', 'cart', 'trolley']):
                                        cart_found = True
                                        print(f"  ✅ Found via selector: {selector}")
                                        break
                            except:
                                continue
                        
                        if cart_found:
                            break
                            
                    except Exception:
                        continue
            
            # METHOD 3: Look for price and stock status
            if not cart_found:
                try:
                    # Check for out of stock indicators
                    page_source = self.driver.page_source.lower()
                    
                    if 'out of stock' in page_source or 'out-of-stock' in page_source:
                        result['status'] = 'out_of_stock'
                        print("  ⚠️  OUT OF STOCK")
                    elif 'sold out' in page_source:
                        result['status'] = 'sold_out'
                        print("  ⚠️  SOLD OUT")
                    elif 'discontinued' in page_source or 'no longer available' in page_source:
                        result['status'] = 'discontinued'
                        print("  ❌ DISCONTINUED")
                    elif '404' in page_source or 'page not found' in page_source:
                        result['status'] = 'not_found'
                        print("  ❌ PAGE NOT FOUND")
                    else:
                        result['status'] = 'no_cart_button'
                        print("  ❌ Add to Cart button not found")
                        
                except Exception as e:
                    result['status'] = 'error_analyzing'
                    result['error'] = str(e)
                    print(f"  ❌ Error analyzing page: {e}")
            
            else:
                # Cart button found - product is available
                result['available'] = True
                result['status'] = 'available'
                print("  ✅ AVAILABLE - Add to Cart found")
                
                # Try to extract price
                try:
                    price_selectors = [
                        "[data-testid='price']",
                        ".price",
                        ".product-price",
                        "[itemprop='price']",
                        ".Price",
                    ]
                    
                    for selector in price_selectors:
                        try:
                            price_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if price_elem.is_displayed():
                                result['price'] = price_elem.text.strip()
                                print(f"  💰 Price: {result['price']}")
                                break
                        except:
                            continue
                            
                except Exception:
                    pass  # Price extraction is optional
        
        except TimeoutException:
            result['status'] = 'timeout'
            result['error'] = 'Page load timeout'
            print("  ⏱️  TIMEOUT loading page")
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"  ❌ ERROR: {str(e)[:50]}...")
        
        return result
    
    def update_shopify_stock_status(self, product_id: int, status: str) -> bool:
        """
        Update Shopify product with Bunnings stock status
        Creates/updates a metafield: bunnings_stock_status
        """
        try:
            # Get the product
            product = shopify.Product.find(product_id)
            
            # Prepare metafield data
            metafield_data = {
                'namespace': 'bunnings',
                'key': 'stock_status',
                'value': status,
                'type': 'single_line_text_field'
            }
            
            # Check if metafield already exists
            existing_metafield = None
            for mf in product.metafields():
                if mf.namespace == 'bunnings' and mf.key == 'stock_status':
                    existing_metafield = mf
                    break
            
            if existing_metafield:
                # Update existing metafield
                existing_metafield.value = status
                success = existing_metafield.save()
            else:
                # Create new metafield
                metafield = shopify.Metafield(metafield_data)
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
        """
        Main function: Fetch products, check Bunnings, update Shopify
        """
        print("\n" + "="*60)
        print("🛒 BUNNINGS AVAILABILITY CHECKER")
        print("="*60)
        
        # Step 1: Fetch products from Shopify
        products = self.fetch_products_with_bunnings_urls(limit=BUNNINGS_CONFIG['max_products'])
        
        if not products:
            print("\n❌ No products to check. Exiting.")
            return
        
        print(f"\n🚀 Starting availability check for {len(products)} products...")
        print("="*60)
        
        results = []
        
        # Step 2: Check each Bunnings URL
        for i, product in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] {product['title'][:40]}...")
            
            # Check availability
            check_result = self.check_bunnings_availability(product['bunnings_url'])
            
            # Combine product info with check result
            full_result = {
                **product,
                **check_result,
                'shopify_updated': False
            }
            
            # Step 3: Update Shopify if requested
            if update_shopify and check_result['status'] != 'unknown':
                updated = self.update_shopify_stock_status(
                    product_id=product['id'],
                    status=check_result['status']
                )
                full_result['shopify_updated'] = updated
            
            results.append(full_result)
            
            # Delay between checks
            if i < len(products):
                time.sleep(BUNNINGS_CONFIG['delay_between_tests'])
        
        # Step 4: Save results
        self.save_results(results)
        
        # Step 5: Show summary
        self.show_summary(results)
    
    def save_results(self, results: List[Dict]):
        """Save results to CSV and JSON files"""
        if not results:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to CSV
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
        
        print(f"\n📊 Results saved to: {csv_filename}")
        
        # Save summary to JSON
        json_filename = f"bunnings_check_summary_{timestamp}.json"
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_checked': len(results),
            'available': sum(1 for r in results if r['available']),
            'not_available': sum(1 for r in results if not r['available']),
            'status_counts': {},
            'products': []
        }
        
        # Count statuses
        for result in results:
            status = result['status']
            summary['status_counts'][status] = summary['status_counts'].get(status, 0) + 1
            
            # Add basic product info
            summary['products'].append({
                'id': result['id'],
                'title': result['title'],
                'status': result['status'],
                'available': result['available']
            })
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📋 Summary saved to: {json_filename}")
    
    def show_summary(self, results: List[Dict]):
        """Display summary of results"""
        if not results:
            return
        
        available = sum(1 for r in results if r['available'])
        not_available = len(results) - available
        
        print("\n" + "="*60)
        print("📋 CHECK SUMMARY")
        print("="*60)
        print(f"Total products checked: {len(results)}")
        print(f"✅ Available on Bunnings: {available}")
        print(f"❌ Not available: {not_available}")
        
        # Status breakdown
        status_counts = {}
        for r in results:
            status = r['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\n📈 Status breakdown:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
        
        # Show products that need attention
        problem_products = [r for r in results if not r['available']]
        if problem_products:
            print("\n⚠️  Products needing attention:")
            for product in problem_products[:5]:  # Show first 5
                print(f"  • {product['title'][:40]}... - Status: {product['status']}")
            if len(problem_products) > 5:
                print(f"  ... and {len(problem_products) - 5} more")
    
    def close(self):
        """Cleanup resources"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n✅ Browser closed")
            except:
                pass
        
        # Clear Shopify session
        try:
            shopify.ShopifyResource.clear_session()
            print("✅ Shopify session closed")
        except:
            pass

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("🏪 BUNNINGS AVAILABILITY CHECKER WITH SHOPIFY INTEGRATION")
    print("="*60)
    
    # Check credentials
    if ('your-store-name' in SHOPIFY_CONFIG['shop_url'] or 
        'your_actual' in SHOPIFY_CONFIG['access_token']):
        print("\n⚠️  WARNING: Default credentials detected!")
        print("Please edit the SHOPIFY_CONFIG at the top of this script.")
        print(f"  Store URL: {SHOPIFY_CONFIG['shop_url']}")
        print(f"  Access Token: {SHOPIFY_CONFIG['access_token'][:20]}...")
        
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("Please update credentials and run again.")
            return
    
    print("\nOptions:")
    print("  1. Full check (fetch from Shopify, check Bunnings, update Shopify)")
    print("  2. Check only (fetch and check, don't update Shopify)")
    print("  3. Test with single URL")
    print("="*60)
    
    choice = input("\nEnter choice (1-3): ").strip() or "1"
    
    checker = None
    
    try:
        checker = ShopifyBunningsChecker()
        
        if choice == "2":
            # Check only, don't update Shopify
            print("\n🔍 Running check only (Shopify will not be updated)...")
            checker.run_check(update_shopify=False)
            
        elif choice == "3":
            # Test single URL
            test_url = input("\nEnter Bunnings URL to test: ").strip()
            if not test_url:
                test_url = "https://www.bunnings.com.au/search/products?q=paint"
                print(f"Using default URL: {test_url}")
            
            print(f"\n🔍 Testing single URL: {test_url}")
            result = checker.check_bunnings_availability(test_url)
            
            print("\n" + "="*60)
            print("📋 TEST RESULT")
            print("="*60)
            print(f"URL: {result['url']}")
            print(f"Title: {result['title']}")
            print(f"Status: {result['status']}")
            print(f"Available: {'✅ YES' if result['available'] else '❌ NO'}")
            if result['price']:
                print(f"Price: {result['price']}")
            if result['error']:
                print(f"Error: {result['error']}")
                
        else:
            # Full check (default)
            print("\n🔄 Running full check...")
            checker.run_check(update_shopify=True)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if checker:
            checker.close()
        print("\n✨ Check complete!")

# ============================================================================
# QUICK RUN FOR AUTOMATION/SCHEDULING
# ============================================================================

def quick_run():
    """
    Simplified version for automation (cron jobs, task scheduler)
    Runs with default settings, no user interaction
    """
    print(f"\n⚡ Quick Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Force headless mode for automation
        BUNNINGS_CONFIG['headless_mode'] = True
        
        checker = ShopifyBunningsChecker()
        checker.run_check(update_shopify=True)
        checker.close()
        
        return True
    except Exception as e:
        print(f"❌ Quick run failed: {e}")
        return False

# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Check for command line arguments
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--quick', '-q']:
        # Run in quick/automated mode
        success = quick_run()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        # Show help
        print("\nUsage:")
        print("  python bunnings_checker.py          # Interactive mode")
        print("  python bunnings_checker.py --quick  # Automated mode (no interaction)")
        print("  python bunnings_checker.py --help   # Show this help")
    else:
        # Run interactive mode
        main()
