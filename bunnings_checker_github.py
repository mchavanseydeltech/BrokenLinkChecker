#!/usr/bin/env python3
"""
Bunnings URL Checker - OPTIMIZED FOR GITHUB ACTIONS
This version is modified to run reliably in GitHub Actions environment
"""

import time
import os
import sys
import csv
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

class BunningsGitHubChecker:
    def __init__(self, headless=True, github_actions=True):
        """Initialize browser optimized for GitHub Actions"""
        self.headless = headless
        self.github_actions = github_actions
        self.driver = None
        self.results_dir = "checker_results"
        self.setup_driver()
    
    def setup_driver(self):
        """Setup browser optimized for headless/CI environment"""
        try:
            print("🚀 Setting up browser for GitHub Actions...")
            
            options = uc.ChromeOptions()
            
            # Essential arguments for headless/CI environment
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            if self.headless:
                print("   Running in headless mode")
                options.add_argument('--headless')
                options.add_argument('--window-size=1920,1080')
            
            # Additional arguments for stability
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            
            # User agent
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options.add_argument(f'user-agent={user_agent}')
            
            # Block unnecessary content
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.geolocation": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.images": 1,  # Allow images
                "profile.managed_default_content_settings.images": 1,
            })
            
            # For GitHub Actions, use a specific version
            if self.github_actions:
                # Try to use a stable Chrome version
                options.add_argument('--disable-software-rasterizer')
                options.add_argument('--remote-debugging-port=9222')
                options.add_argument('--remote-debugging-address=0.0.0.0')
                options.add_argument('--no-first-run')
                options.add_argument('--no-default-browser-check')
                options.add_argument('--disable-background-timer-throttling')
                options.add_argument('--disable-backgrounding-occluded-windows')
                options.add_argument('--disable-renderer-backgrounding')
            
            # Initialize driver with more robust settings
            driver_executable_path = None
            if os.path.exists('/usr/local/bin/chromedriver'):
                driver_executable_path = '/usr/local/bin/chromedriver'
            
            print("   Initializing undetected-chromedriver...")
            self.driver = uc.Chrome(
                options=options,
                driver_executable_path=driver_executable_path,
                use_subprocess=True,
                version_main=120  # Specify a stable version
            )
            
            # Set implicit wait
            self.driver.implicitly_wait(10)
            
            # Test browser
            self.driver.get("about:blank")
            print(f"✅ Browser ready - Chrome version: {self.driver.capabilities['browserVersion']}")
            print(f"   Platform: {self.driver.capabilities['platformName']}")
            
        except Exception as e:
            print(f"❌ Browser setup error: {str(e)}")
            print("Attempting fallback configuration...")
            self.setup_fallback_driver()
    
    def setup_fallback_driver(self):
        """Fallback setup if primary setup fails"""
        try:
            print("🔄 Trying fallback browser setup...")
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            
            # Try with regular ChromeDriver
            if os.path.exists('/usr/local/bin/chromedriver'):
                self.driver = webdriver.Chrome(
                    executable_path='/usr/local/bin/chromedriver',
                    options=options
                )
            else:
                self.driver = webdriver.Chrome(options=options)
            
            print("✅ Fallback browser ready")
            
        except Exception as e:
            print(f"❌ Fallback also failed: {e}")
            raise
    
    def check_bunnings_url(self, url):
        """
        Check Bunnings URL with GitHub Actions optimizations
        """
        print(f"\n🔗 Testing: {url}")
        
        result = {
            'url': url,
            'page_title': 'Not loaded',
            'status': 'not_tested',
            'is_working': False,
            'add_to_cart_found': False,
            'error': None,
            'timestamp': datetime.now().isoformat(),
            'response_time': None,
            'screenshot': None
        }
        
        start_time = time.time()
        
        try:
            # 1. Load the URL with longer wait for CI
            print("   Loading page...")
            self.driver.get(url)
            
            # Wait longer in CI environment
            wait_time = 15 if self.github_actions else 10
            time.sleep(wait_time)
            
            # 2. Get page title
            title = self.driver.title
            result['page_title'] = title
            print(f"   Title: {title}")
            
            # 3. Check for Cloudflare or security challenges
            page_source = self.driver.page_source
            
            if "Just a moment" in title or "Checking your browser" in page_source:
                print("   ⚠️ Cloudflare detected, waiting longer...")
                time.sleep(20)  # Extra wait for Cloudflare
                
                if "Just a moment" in self.driver.title:
                    result['status'] = 'cloudflare_blocked'
                    result['error'] = 'Cloudflare security challenge'
                    print("   ❌ Cloudflare blocked access")
                    
                    # Try to take screenshot
                    try:
                        screenshot_name = f"cloudflare_{int(time.time())}.png"
                        self.driver.save_screenshot(os.path.join(self.results_dir, screenshot_name))
                        result['screenshot'] = screenshot_name
                    except:
                        pass
                    
                    return result
            
            # 4. Check if it's a Bunnings page
            if not ('bunnings' in page_source.lower() or 'bunnings.com.au' in title.lower()):
                result['status'] = 'not_bunnings'
                print("   ❌ Not a Bunnings page")
                return result
            
            # 5. Look for Add to Cart button with multiple strategies
            print("   Searching for Add to Cart button...")
            time.sleep(5)
            
            # Strategy 1: Direct text search (case-insensitive)
            cart_found = False
            cart_texts = [
                'Add to Cart', 'Add to Trolley', 
                'ADD TO CART', 'ADD TO TROLLEY',
                'add to cart', 'add to trolley'
            ]
            
            for text in cart_texts:
                try:
                    # Using JavaScript to find elements with text
                    js_script = f"""
                    var elements = Array.from(document.querySelectorAll('*'));
                    return elements.filter(el => {{
                        var text = el.textContent || el.innerText;
                        return text.trim().toLowerCase().includes('{text.lower()}');
                    }});
                    """
                    
                    elements = self.driver.execute_script(js_script)
                    if elements and len(elements) > 0:
                        # Check if any element is visible
                        for element in elements:
                            try:
                                if element.is_displayed():
                                    cart_found = True
                                    print(f"   ✓ Found text: '{text}'")
                                    break
                            except:
                                continue
                        if cart_found:
                            break
                except:
                    continue
            
            # Strategy 2: Common button selectors
            if not cart_found:
                selectors = [
                    "button[data-testid*='add-to-cart']",
                    "button[data-test-id*='add-to-cart']",
                    "[data-testid*='addToCart']",
                    "button:contains('Add to Cart')",
                    "button:contains('Add to Trolley')",
                    ".add-to-cart-button",
                    ".add-to-cart",
                    "#add-to-cart",
                    "[aria-label*='Add to cart']",
                    "[aria-label*='Add to trolley']",
                    "button.btn-primary",
                    "button.btn--primary",
                    "button[type='submit']",
                    "a.button[href*='cart']",
                    "a.btn[href*='cart']"
                ]
                
                for selector in selectors:
                    try:
                        # Try CSS selector first
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            try:
                                if element.is_displayed():
                                    element_text = element.text.lower()
                                    if any(term in element_text for term in ['add to', 'cart', 'trolley']):
                                        cart_found = True
                                        print(f"   ✓ Found via selector: {selector}")
                                        break
                            except:
                                continue
                        if cart_found:
                            break
                    except:
                        continue
            
            # Strategy 3: Look for price and buy section
            if not cart_found:
                try:
                    # Check for price elements (often near add to cart)
                    price_selectors = [
                        "[data-testid*='price']",
                        ".price",
                        ".product-price",
                        ".buy-box",
                        ".purchase-box",
                        ".product-action"
                    ]
                    
                    for selector in price_selectors:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            # Look for buttons near price
                            parent = elements[0].find_element(By.XPATH, "./..")
                            buttons = parent.find_elements(By.TAG_NAME, "button")
                            if buttons:
                                cart_found = True
                                print(f"   ✓ Found button near price section")
                                break
                except:
                    pass
            
            result['add_to_cart_found'] = cart_found
            result['response_time'] = round(time.time() - start_time, 2)
            
            # 6. Determine result
            page_text = page_source.lower()
            
            if cart_found:
                result['status'] = 'working'
                result['is_working'] = True
                print(f"   ✅ WORKING - Add to Cart found ({result['response_time']}s)")
            else:
                # Check specific error cases
                if 'out of stock' in page_text:
                    result['status'] = 'out_of_stock'
                    print("   ⚠️ OUT OF STOCK")
                elif 'product not found' in page_text or '404' in page_text or 'not found' in page_text:
                    result['status'] = 'not_found'
                    print("   ❌ 404 - Product not found")
                elif 'no longer available' in page_text or 'discontinued' in page_text:
                    result['status'] = 'discontinued'
                    print("   ❌ Discontinued")
                elif 'sold out' in page_text:
                    result['status'] = 'sold_out'
                    print("   ❌ Sold out")
                elif 'unavailable' in page_text:
                    result['status'] = 'unavailable'
                    print("   ❌ Unavailable")
                else:
                    result['status'] = 'no_add_to_cart'
                    print("   ❌ No Add to Cart button found")
            
            # Take screenshot for debugging
            if not cart_found and self.github_actions:
                try:
                    os.makedirs(self.results_dir, exist_ok=True)
                    url_hash = hash(url) % 10000
                    screenshot_name = f"{result['status']}_{url_hash}_{int(time.time())}.png"
                    screenshot_path = os.path.join(self.results_dir, screenshot_name)
                    self.driver.save_screenshot(screenshot_path)
                    result['screenshot'] = screenshot_name
                    print(f"   📸 Screenshot saved: {screenshot_name}")
                except Exception as e:
                    print(f"   Note: Could not save screenshot: {e}")
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['response_time'] = round(time.time() - start_time, 2)
            print(f"   ❌ Error: {str(e)[:100]}")
            
            # Try to capture error screenshot
            try:
                os.makedirs(self.results_dir, exist_ok=True)
                screenshot_name = f"error_{int(time.time())}.png"
                self.driver.save_screenshot(os.path.join(self.results_dir, screenshot_name))
                result['screenshot'] = screenshot_name
            except:
                pass
        
        return result
    
    def bulk_test_urls(self, input_file, output_prefix="github_actions"):
        """
        Test multiple URLs optimized for GitHub Actions
        """
        print("\n" + "="*70)
        print("🏪 BUNNINGS URL CHECKER - GITHUB ACTIONS OPTIMIZED")
        print("="*70)
        
        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Check input file
        if not os.path.exists(input_file):
            print(f"❌ File not found: {input_file}")
            print(f"Creating sample file...")
            sample_file = self.create_sample_file(input_file)
            print(f"✅ Created: {sample_file}")
            print("Please add your Bunnings URLs and re-run")
            return []
        
        # Read URLs
        urls = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    if 'bunnings.com.au' in line.lower():
                        urls.append(line)
                    else:
                        print(f"⚠️ Line {i}: Skipping non-Bunnings URL")
        
        if not urls:
            print("❌ No valid Bunnings URLs found")
            return []
        
        print(f"✅ Found {len(urls)} Bunnings URL(s) to test")
        print(f"📍 Results will be saved to: {self.results_dir}/")
        print("="*70)
        
        # Test each URL
        results = []
        successful = 0
        failed = 0
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] ", end="")
            
            try:
                result = self.check_bunnings_url(url)
                results.append(result)
                
                if result['is_working']:
                    successful += 1
                else:
                    failed += 1
                
                # Save progress every 5 URLs
                if i % 5 == 0 or i == len(urls):
                    self.save_progress(results, output_prefix)
                
                # Delay between requests
                if i < len(urls):
                    delay = 3 if self.github_actions else 2
                    time.sleep(delay)
                    
            except KeyboardInterrupt:
                print("\n⚠️ Stopped by user")
                break
            except Exception as e:
                print(f"\n❌ Critical error on URL {i}: {e}")
                error_result = {
                    'url': url,
                    'page_title': 'Error',
                    'status': 'critical_error',
                    'is_working': False,
                    'add_to_cart_found': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat(),
                    'response_time': None
                }
                results.append(error_result)
                failed += 1
        
        # Save final results
        self.save_results(results, output_prefix)
        
        # Print summary
        self.print_summary(results, successful, failed)
        
        return results
    
    def create_sample_file(self, filename="bunnings_urls.txt"):
        """Create sample URLs file"""
        sample_content = """# Bunnings URLs for GitHub Actions Testing
# Add one Bunnings product URL per line

# Example URLs:
https://www.bunnings.com.au/orion-grid-connect-smart-rechargeable-2k-security-camera-4-pack_p0503618
https://www.bunnings.com.au/orion-4k-wired-outdoor-security-camera_p0252107
https://www.bunnings.com.au/orion-grid-connect-smart-doorbell-camera_p0252108

# Add your URLs below:
# https://www.bunnings.com.au/product-name_product-code
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(sample_content)
        
        return filename
    
    def save_progress(self, results, prefix):
        """Save intermediate progress"""
        try:
            progress_file = os.path.join(self.results_dir, f"{prefix}_progress.json")
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
        except:
            pass
    
    def save_results(self, results, prefix):
        """Save results in multiple formats"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save as CSV
        csv_file = os.path.join(self.results_dir, f"{prefix}_results_{timestamp}.csv")
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'URL', 'Page_Title', 'Status', 'Working', 
                    'Add_to_Cart_Found', 'Response_Time_sec', 
                    'Error', 'Screenshot', 'Timestamp'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    writer.writerow({
                        'URL': result['url'],
                        'Page_Title': result['page_title'][:150],
                        'Status': result['status'],
                        'Working': 'Yes' if result['is_working'] else 'No',
                        'Add_to_Cart_Found': 'Yes' if result['add_to_cart_found'] else 'No',
                        'Response_Time_sec': result.get('response_time', ''),
                        'Error': (result['error'] or '')[:100],
                        'Screenshot': result.get('screenshot', ''),
                        'Timestamp': result['timestamp']
                    })
            
            print(f"\n📊 CSV results saved to: {csv_file}")
        except Exception as e:
            print(f"\n⚠️ Could not save CSV: {e}")
        
        # Save as JSON
        json_file = os.path.join(self.results_dir, f"{prefix}_results_{timestamp}.json")
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"📄 JSON results saved to: {json_file}")
        except Exception as e:
            print(f"⚠️ Could not save JSON: {e}")
        
        # Save summary
        summary_file = os.path.join(self.results_dir, f"{prefix}_summary_{timestamp}.txt")
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_summary_text(results))
            print(f"📋 Summary saved to: {summary_file}")
        except Exception as e:
            print(f"⚠️ Could not save summary: {e}")
    
    def generate_summary_text(self, results):
        """Generate summary text"""
        working = sum(1 for r in results if r['is_working'])
        broken = len(results) - working
        
        summary = []
        summary.append("=" * 60)
        summary.append("BUNNINGS URL CHECKER - SUMMARY REPORT")
        summary.append("=" * 60)
        summary.append(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append(f"Total URLs Tested: {len(results)}")
        summary.append(f"✅ Working: {working}")
        summary.append(f"❌ Broken: {broken}")
        summary.append(f"📈 Success Rate: {(working/len(results)*100 if results else 0):.1f}%")
        summary.append("")
        
        # Status breakdown
        status_counts = {}
        for r in results:
            status = r['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        summary.append("Status Breakdown:")
        for status, count in sorted(status_counts.items()):
            summary.append(f"  {status}: {count}")
        
        summary.append("")
        
        # Response times
        times = [r.get('response_time', 0) for r in results if r.get('response_time')]
        if times:
            summary.append(f"Avg Response Time: {sum(times)/len(times):.2f}s")
            summary.append(f"Min Response Time: {min(times):.2f}s")
            summary.append(f"Max Response Time: {max(times):.2f}s")
        
        summary.append("")
        summary.append("=" * 60)
        
        return "\n".join(summary)
    
    def print_summary(self, results, successful, failed):
        """Print summary to console"""
        print("\n" + "="*60)
        print("📋 TEST COMPLETE - SUMMARY")
        print("="*60)
        print(f"Total URLs Tested: {len(results)}")
        print(f"✅ Working: {successful}")
        print(f"❌ Broken: {failed}")
        
        if results:
            success_rate = (successful / len(results)) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
            
            # List broken URLs
            if failed > 0:
                print("\n🔍 Broken URLs:")
                for result in results:
                    if not result['is_working']:
                        status = result['status']
                        url_short = result['url'][:60] + "..." if len(result['url']) > 60 else result['url']
                        print(f"  • {status}: {url_short}")
        
        print(f"\n📁 Results saved in: {self.results_dir}/")
        print("="*60)
    
    def close(self):
        """Close browser safely"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Browser closed")
            except:
                pass


def main():
    """Main function optimized for GitHub Actions"""
    print("\n" + "="*60)
    print("🏪 BUNNINGS URL CHECKER - GITHUB ACTIONS VERSION")
    print("="*60)
    print("Optimized for running in CI/CD environments")
    print("="*60)
    
    # Check if running in GitHub Actions
    github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    headless = github_actions  # Always headless in GitHub Actions
    
    if github_actions:
        print("✅ Running in GitHub Actions environment")
        print("✅ Browser will run in headless mode")
    
    try:
        # Default to bulk test in GitHub Actions
        if github_actions:
            input_file = "bunnings_urls.txt"
            print(f"\n📁 Using input file: {input_file}")
            print(f"📁 Working directory: {os.getcwd()}")
            
            # List files in directory (for debugging)
            print("\n📂 Directory contents:")
            for file in os.listdir('.'):
                print(f"  • {file}")
            
            checker = BunningsGitHubChecker(headless=headless, github_actions=True)
            results = checker.bulk_test_urls(input_file, output_prefix="github")
            
        else:
            # Interactive mode for local testing
            print("\nOptions:")
            print("  1. Test URLs from file")
            print("  2. Test single URL")
            print("  3. Create sample file")
            
            choice = input("\nEnter choice (1-3): ").strip() or "1"
            
            checker = BunningsGitHubChecker(headless=False, github_actions=False)
            
            if choice == "2":
                url = input("Enter Bunnings URL: ").strip()
                if not url:
                    url = "https://www.bunnings.com.au/orion-grid-connect-smart-rechargeable-2k-security-camera-4-pack_p0503618"
                
                result = checker.check_bunnings_url(url)
                print(f"\nResult: {result['status']}")
                print(f"Working: {'Yes' if result['is_working'] else 'No'}")
                
            elif choice == "3":
                filename = input("Filename [bunnings_urls.txt]: ").strip() or "bunnings_urls.txt"
                checker.create_sample_file(filename)
                
            else:
                input_file = input("Input file [bunnings_urls.txt]: ").strip() or "bunnings_urls.txt"
                input_file = os.path.expanduser(input_file)
                checker.bulk_test_urls(input_file, output_prefix="local")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Exit with error code for GitHub Actions
        if github_actions:
            sys.exit(1)
    finally:
        if 'checker' in locals():
            checker.close()
        
        print("\n✨ Done!")
        
        # Exit cleanly for GitHub Actions
        if github_actions:
            sys.exit(0)


if __name__ == "__main__":
    main()
