#!/usr/bin/env python3
"""
Bunnings URL Checker - GitHub Actions Version
"""

import time
import os
import sys
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

print("🚀 Bunnings URL Checker - Starting...")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

# List files for debugging
print("\n📁 Files in current directory:")
for f in os.listdir('.'):
    print(f"  {f}")

def setup_browser():
    """Setup browser for headless mode"""
    print("\n🛠️ Setting up browser...")
    
    options = uc.ChromeOptions()
    
    # Headless mode for GitHub Actions
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Additional settings
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        print("Initializing Chrome driver...")
        driver = uc.Chrome(options=options, version_main=120)
        print(f"✅ Browser ready - Chrome {driver.capabilities['browserVersion']}")
        return driver
    except Exception as e:
        print(f"❌ Failed to setup browser: {e}")
        raise

def check_url(driver, url):
    """Check a single URL"""
    print(f"\n🔗 Checking: {url[:60]}...")
    
    try:
        driver.get(url)
        time.sleep(8)  # Wait for page load
        
        title = driver.title
        print(f"   Title: {title[:50]}...")
        
        # Check for Cloudflare
        if "Just a moment" in title or "Checking" in title:
            print("   ⚠️ Cloudflare detected, waiting...")
            time.sleep(15)
            title = driver.title
            if "Just a moment" in title:
                return "CLOUDFLARE_BLOCKED", False
        
        # Check page content
        page_text = driver.page_source.lower()
        
        # Look for Add to Cart button
        if 'add to cart' in page_text or 'add to trolley' in page_text:
            print("   ✅ ADD TO CART FOUND")
            return "WORKING", True
        elif 'out of stock' in page_text:
            print("   ⚠️ OUT OF STOCK")
            return "OUT_OF_STOCK", False
        elif 'product not found' in page_text or '404' in page_text:
            print("   ❌ PRODUCT NOT FOUND")
            return "NOT_FOUND", False
        else:
            print("   ❌ NO ADD TO CART")
            return "NO_ADD_TO_CART", False
            
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)[:50]}")
        return f"ERROR: {str(e)[:30]}", False

def main():
    """Main function"""
    driver = None
    
    try:
        # Setup browser
        driver = setup_browser()
        
        # Read URLs
        urls_file = "bunnings_urls.txt"
        if not os.path.exists(urls_file):
            print(f"\n❌ ERROR: {urls_file} not found!")
            print("Creating sample file...")
            with open(urls_file, 'w') as f:
                f.write("# Sample Bunnings URLs\n")
                f.write("https://www.bunnings.com.au/orion-grid-connect-smart-rechargeable-2k-security-camera-4-pack_p0503618\n")
                f.write("https://www.bunnings.com.au/search/products?q=security+camera\n")
        
        print(f"\n📖 Reading URLs from: {urls_file}")
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not urls:
            print("❌ No URLs found in file")
            return
        
        print(f"✅ Found {len(urls)} URL(s) to check")
        
        # Check each URL
        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] ", end="")
            status, working = check_url(driver, url)
            results.append({
                'url': url,
                'status': status,
                'working': working,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Delay between requests
            if i < len(urls):
                time.sleep(3)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = f"results_{timestamp}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['URL', 'Status', 'Working', 'Timestamp'])
            for r in results:
                writer.writerow([r['url'], r['status'], r['working'], r['timestamp']])
        
        # Print summary
        working_count = sum(1 for r in results if r['working'])
        print("\n" + "="*50)
        print("📊 SUMMARY")
        print("="*50)
        print(f"Total URLs checked: {len(results)}")
        print(f"✅ Working: {working_count}")
        print(f"❌ Not working: {len(results) - working_count}")
        print(f"📁 Results saved to: {csv_file}")
        print("="*50)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if driver:
            driver.quit()
            print("\n✅ Browser closed")

if __name__ == "__main__":
    main()
