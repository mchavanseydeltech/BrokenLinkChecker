name: Run Bunnings Checker

on:
  # Schedule: Every day at 3 AM UTC
  schedule:
    - cron: '0 3 * * *'
  
  # Manual trigger from GitHub UI
  workflow_dispatch:
    inputs:
      force_run:
        description: 'Force run even if secrets are not updated'
        required: false
        default: false
        type: boolean

jobs:
  check-bunnings:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v3
      with:
        fetch-depth: 1
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y wget unzip gnupg software-properties-common
        
    - name: Install Chrome
      run: |
        # Install Google Chrome Stable
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
        sudo apt-get update
        sudo apt-get install -y google-chrome-stable
        
        # Verify installation
        google-chrome --version
        
    - name: Install ChromeDriver
      run: |
        # Get Chrome version
        CHROME_MAJOR_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1)
        echo "Chrome major version: $CHROME_MAJOR_VERSION"
        
        # Download matching ChromeDriver
        CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR_VERSION")
        echo "Downloading ChromeDriver version: $CHROMEDRIVER_VERSION"
        
        wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
        unzip chromedriver_linux64.zip
        sudo mv chromedriver /usr/local/bin/
        sudo chmod +x /usr/local/bin/chromedriver
        
        # Verify ChromeDriver
        chromedriver --version
        
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install selenium==4.15.0 undetected-chromedriver==3.5.4 requests==2.31.0
        
        # Verify installations
        python -c "import selenium; print(f'Selenium: {selenium.__version__}')"
        python -c "import requests; print(f'Requests: {requests.__version__}')"
    
    - name: Create hardcoded script
      run: |
        # This creates the script from a heredoc
        # IMPORTANT: Edit the SHOPIFY_CONFIG values below with your actual secrets!
        
        cat > bunnings_checker_hardcoded.py << 'EOF'
#!/usr/bin/env python3
"""
Bunnings URL Checker - Hardcoded for GitHub Actions
SECRETS ARE HARDCODED - DO NOT SHARE THIS FILE PUBLICLY
"""

import time
import os
import csv
import requests
import json
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

# ============================================================
# HARDCODED SECRETS - UPDATE THESE WITH YOUR VALUES
# ============================================================
SHOPIFY_CONFIG = {
    # ⚠️ REPLACE WITH YOUR ACTUAL SHOPIFY STORE DOMAIN
    "shop_domain": "cassien24.myshopify.com",
    
    # ⚠️ REPLACE WITH YOUR ACTUAL SHOPIFY ACCESS TOKEN
    "access_token": "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",
    
    # Metafield configuration
    "metafield_namespace": "custom",
    "metafield_key": "au_link",
    
    # CI Settings
    "headless": True,
    "wait_time": 10,
    "check_delay": 2
}
# ============================================================

class HardcodedBunningsChecker:
    def __init__(self):
        self.config = SHOPIFY_CONFIG
        self.driver = None
        
        # Check if config is still using placeholder values
        if ("YOUR-STORE-NAME" in self.config["shop_domain"] or 
            "YOUR_ACTUAL_ACCESS_TOKEN" in self.config["access_token"]):
            print("\n" + "="*60)
            print("❌ CONFIGURATION REQUIRED")
            print("="*60)
            print("Please update the hardcoded values in SHOPIFY_CONFIG:")
            print(f"1. shop_domain: '{self.config['shop_domain']}'")
            print(f"2. access_token: '{self.config['access_token'][:20]}...'")
            print("\nSteps:")
            print("1. Edit this script file")
            print("2. Replace placeholder values with your actual Shopify credentials")
            print("3. Commit and push changes")
            print("="*60)
            sys.exit(1)
        
        self.setup_driver()
    
    def setup_driver(self):
        """Setup browser for GitHub Actions"""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-gpu')
            
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options.add_argument(f'user-agent={user_agent}')
            
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            print("✅ Browser ready")
            
        except Exception as e:
            print(f"❌ Browser error: {e}")
            raise
    
    def fetch_products(self):
        """Fetch products with Bunnings URLs"""
        print("📡 Fetching from Shopify...")
        
        shop = self.config["shop_domain"]
        token = self.config["access_token"]
        headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json"
        }
        
        products = []
        url = f"https://{shop}/admin/api/2024-01/products.json?limit=250&fields=id,title,handle,metafields"
        
        try:
            while url:
                response = requests.get(url, headers=headers)
                
                if response.status_code != 200:
                    print(f"❌ Shopify error: {response.status_code}")
                    break
                
                data = response.json()
                for product in data.get('products', []):
                    for metafield in product.get('metafields', []):
                        if (metafield.get('namespace') == self.config["metafield_namespace"] and 
                            metafield.get('key') == self.config["metafield_key"]):
                            bunnings_url = metafield.get('value')
                            if bunnings_url and 'bunnings.com.au' in bunnings_url.lower():
                                products.append({
                                    'id': product['id'],
                                    'title': product['title'],
                                    'handle': product.get('handle', ''),
                                    'url': bunnings_url
                                })
                                break
                
                # Check for next page
                link = response.headers.get('Link', '')
                if 'rel="next"' in link:
                    import re
                    match = re.search(r'<([^>]+)>; rel="next"', link)
                    url = match.group(1) if match else None
                else:
                    url = None
                
                time.sleep(0.3)
            
            print(f"✅ Found {len(products)} products")
            
        except Exception as e:
            print(f"❌ Fetch error: {e}")
        
        return products
    
    def check_url(self, url):
        """Check a single Bunnings URL"""
        print(f"🔗 Checking: {url[:60]}...")
        
        result = {
            'url': url,
            'working': False,
            'status': 'error',
            'error': None
        }
        
        try:
            self.driver.get(url)
            time.sleep(8)
            
            title = self.driver.title.lower()
            source = self.driver.page_source.lower()
            
            # Check for issues
            if 'just a moment' in title:
                result['status'] = 'cloudflare_blocked'
                return result
            elif 'out of stock' in source:
                result['status'] = 'out_of_stock'
                return result
            elif '404' in source or 'not found' in source:
                result['status'] = 'not_found'
                return result
            elif 'bunnings' not in source:
                result['status'] = 'not_bunnings'
                return result
            
            # Look for Add to Cart
            time.sleep(3)
            
            # Check by text
            cart_texts = ['Add to Cart', 'Add to Trolley', 'Add to cart', 'Add to trolley']
            found = False
            
            for text in cart_texts:
                try:
                    elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
                    for element in elements:
                        if element.is_displayed():
                            found = True
                            break
                    if found:
                        break
                except:
                    continue
            
            if found:
                result['working'] = True
                result['status'] = 'working'
                print("   ✅ Working")
            else:
                result['status'] = 'no_add_to_cart'
                print("   ❌ No Add to Cart")
            
        except Exception as e:
            result['error'] = str(e)
            print(f"   ❌ Error: {str(e)[:50]}")
        
        return result
    
    def run(self):
        """Main runner"""
        products = self.fetch_products()
        
        if not products:
            print("❌ No products found")
            return []
        
        results = []
        print(f"\n🔍 Checking {len(products)} URLs...")
        
        for i, product in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] {product['title'][:50]}...")
            
            check = self.check_url(product['url'])
            check['product_id'] = product['id']
            check['product_title'] = product['title']
            check['product_handle'] = product['handle']
            
            results.append(check)
            
            if i < len(products):
                time.sleep(2)
        
        return results
    
    def save_results(self, results):
        """Save CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'bunnings_results_{timestamp}.csv'
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Product ID', 'Title', 'URL', 'Status', 'Working'])
            
            for r in results:
                writer.writerow([
                    r.get('product_id', ''),
                    r.get('product_title', '')[:80],
                    r.get('url', ''),
                    r.get('status', ''),
                    'Yes' if r.get('working') else 'No'
                ])
        
        print(f"\n📊 Saved: {filename}")
        return filename
    
    def summary(self, results):
        """Print summary"""
        working = sum(1 for r in results if r.get('working'))
        total = len(results)
        
        print("\n" + "="*60)
        print("📋 SUMMARY")
        print("="*60)
        print(f"Total: {total}")
        print(f"✅ Working: {working}")
        print(f"❌ Broken: {total - working}")
        print("="*60)
    
    def close(self):
        """Cleanup"""
        if self.driver:
            self.driver.quit()

# Main execution
if __name__ == "__main__":
    print("🚀 Starting Hardcoded Bunnings Checker")
    print("="*60)
    
    checker = None
    try:
        checker = HardcodedBunningsChecker()
        results = checker.run()
        
        if results:
            csv_file = checker.save_results(results)
            checker.summary(results)
            print(f"\n✨ Done! Results in: {csv_file}")
        else:
            print("❌ No results")
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        if checker:
            checker.close()
EOF
        
        # Make it executable
        chmod +x bunnings_checker_hardcoded.py
        
        # Verify the script was created
        ls -la bunnings_checker_hardcoded.py
        head -30 bunnings_checker_hardcoded.py
    
    - name: ⚠️ IMPORTANT - Update hardcoded secrets
      run: |
        echo "=========================================="
        echo "⚠️  ACTION REQUIRED: Update Hardcoded Secrets"
        echo "=========================================="
        echo ""
        echo "Before running, you MUST edit the Python script"
        echo "and replace these placeholder values:"
        echo ""
        echo "1. shop_domain: 'YOUR-STORE-NAME.myshopify.com'"
        echo "   → Change to your actual Shopify store domain"
        echo ""
        echo "2. access_token: 'shpat_YOUR_ACTUAL_ACCESS_TOKEN_HERE'"
        echo "   → Change to your actual Shopify access token"
        echo ""
        echo "Steps:"
        echo "1. Open bunnings_checker_hardcoded.py in this workflow"
        echo "2. Edit lines with SHOPIFY_CONFIG dictionary"
        echo "3. Replace placeholder values with your actual credentials"
        echo "4. Commit and push changes"
        echo ""
        echo "Current values in script:"
        grep -A5 "SHOPIFY_CONFIG = " bunnings_checker_hardcoded.py
        echo ""
        echo "=========================================="
        
        # Check if still using placeholder values
        if grep -q "YOUR-STORE-NAME\|YOUR_ACTUAL_ACCESS_TOKEN" bunnings_checker_hardcoded.py; then
          echo "❌ Script still contains placeholder values!"
          echo "Please update the script with your actual Shopify credentials."
          exit 1
        else
          echo "✅ Script appears to have real credentials"
        fi
    
    - name: Run the checker
      run: |
        python bunnings_checker_hardcoded.py
        
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: bunnings-check-results
        path: bunnings_results_*.csv
        retention-days: 90
        
    - name: Show summary in workflow
      run: |
        echo "=========================================="
        echo "🏁 Workflow Completed"
        echo "=========================================="
        echo "Check the 'Artifacts' section above to"
        echo "download the CSV results file."
        echo ""
        echo "To view results:"
        echo "1. Click on this workflow run"
        echo "2. Scroll to 'Artifacts' section"
        echo "3. Download 'bunnings-check-results'"
        echo "=========================================="
