#!/usr/bin/env python3
"""
Bunnings URL Checker - Shopify Metafield Version
Fetches URLs from Shopify product metafield `custom.au_link` and checks if Add to Cart is available.
"""

import time
from datetime import datetime
import csv
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# ---------- CONFIG ----------
SHOP = "cassien24.myshopify.com"  # Replace with your store
ACCESS_TOKEN = "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"  # Replace with your token
HEADLESS = False  # Set True for no browser window
# -----------------------------

class BunningsDirectChecker:
    def __init__(self, headless=HEADLESS):
        """Initialize browser"""
        self.headless = headless
        self.driver = None
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

    # ------------------- Shopify Metafield Fetch -------------------
    def fetch_bunnings_urls_from_shopify(self):
        """
        Fetch all product metafields for 'custom.au_link' from Shopify
        Returns a list of URLs
        """
        urls = []
        base_url = f"https://{SHOP}/admin/api/2025-10/products.json?limit=250"
        headers = {
            "X-Shopify-Access-Token": ACCESS_TOKEN,
            "Content-Type": "application/json"
        }

        print("📡 Fetching products from Shopify...")
        while base_url:
            response = requests.get(base_url, headers=headers)
            if response.status_code != 200:
                print(f"❌ Shopify API Error: {response.status_code} {response.text}")
                break

            data = response.json()
            products = data.get("products", [])
            
            for product in products:
                product_id = product["id"]
                mf_url = f"https://{SHOP}/admin/api/2025-10/products/{product_id}/metafields.json"
                mf_resp = requests.get(mf_url, headers=headers)
                if mf_resp.status_code != 200:
                    continue
                metafields = mf_resp.json().get("metafields", [])
                for mf in metafields:
                    if mf["key"] == "au_link" and mf["namespace"] == "custom":
                        link = mf.get("value")
                        if link and "bunnings.com.au" in link:
                            urls.append(link)
            
            # Pagination
            link_header = response.headers.get('Link')
            if link_header and 'rel="next"' in link_header:
                next_link = link_header.split(';')[0].strip('<>')
                base_url = next_link
            else:
                base_url = None

        print(f"✅ Found {len(urls)} Bunnings URL(s) from Shopify metafields")
        return urls

    # ------------------- URL CHECK -------------------
    def check_bunnings_url(self, url):
        """Load Bunnings URL and check for Add to Cart"""
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
            self.driver.get(url)
            time.sleep(8)
            title = self.driver.title
            result['page_title'] = title
            print(f"   Title: {title[:60]}...")
            
            # Cloudflare check
            if "Just a moment" in title:
                print("   ⚠️ Cloudflare detected, waiting...")
                time.sleep(10)
                title = self.driver.title
                if "Just a moment" in title:
                    result['status'] = 'cloudflare_blocked'
                    print("   ❌ Cloudflare blocked")
                    return result
            
            # Bunnings page check
            page_source = self.driver.page_source.lower()
            if 'bunnings' not in page_source and 'bunnings.com.au' not in title.lower():
                result['status'] = 'not_bunnings'
                print("   ❌ Not a Bunnings page")
                return result
            
            # Look for Add to Cart
            add_to_cart_found = False
            cart_texts = ['add to cart', 'add to trolley']
            for text in cart_texts:
                elements = self.driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]")
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
            
            # CSS selectors fallback
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
            
            result['add_to_cart_found'] = add_to_cart_found
            
            if add_to_cart_found:
                result['status'] = 'working'
                result['is_working'] = True
                print("   ✅ WORKING - Add to Cart found")
            else:
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

    # ------------------- BULK TEST -------------------
    def bulk_test_urls(self):
        """Fetch Shopify URLs and test them"""
        urls = self.fetch_bunnings_urls_from_shopify()
        if not urls:
            print("❌ No URLs found to test")
            return []
        
        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] ", end="")
            result = self.check_bunnings_url(url)
            results.append(result)
            if i < len(urls):
                time.sleep(2)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"shopify_bunnings_results_{timestamp}.csv"
        self.save_results_csv(results, report_file)
        self.print_summary(results)
        return results

    # ------------------- SAVE CSV -------------------
    def save_results_csv(self, results, filename):
        """Save results to CSV"""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
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
                    'Bunnings_URL': result['url'],
                    'Page_Title': result['page_title'][:200] if result['page_title'] else '',
                    'Status': result['status'],
                    'Working': 'Yes' if result['is_working'] else 'No',
                    'Add_to_Cart_Found': 'Yes' if result['add_to_cart_found'] else 'No',
                    'Error': result['error'] or '',
                    'Test_Time': result['timestamp']
                })
        print(f"\n📊 Results saved to: {filename}")

    # ------------------- SUMMARY -------------------
    def print_summary(self, results):
        if not results:
            return
        working = sum(1 for r in results if r['is_working'])
        broken = len(results) - working
        print("\n" + "="*60)
        print("📋 SUMMARY")
        print("="*60)
        print(f"Total URLs Tested: {len(results)}")
        print(f"✅ Working: {working}")
        print(f"❌ Broken: {broken}")
        status_counts = {}
        for r in results:
            status = r['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        print("\n📈 Breakdown:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass

# ------------------- MAIN -------------------
def main():
    print("\n🏪 BUNNINGS SHOPIFY URL CHECKER")
    checker = BunningsDirectChecker(headless=HEADLESS)
    try:
        checker.bulk_test_urls()
    except KeyboardInterrupt:
        print("\n⚠️  Stopped by user")
    finally:
        checker.close()
        print("\n✨ Done!")

if __name__ == "__main__":
    main()
