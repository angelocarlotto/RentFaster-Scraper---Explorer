#!/usr/bin/env python3
"""
Test script to fetch listings using Selenium (bypasses Cloudflare)
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

def fetch_with_selenium(city_name, city_code):
    """Fetch listings for a city using Selenium"""
    print("=" * 80)
    print(f"🌍 Testing {city_name} with Selenium")
    print("=" * 80)
    
    # Setup Chrome options
    chrome_options = Options()
    # Use visible browser - Cloudflare detects headless
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    print("\n🔧 Setting up Chrome driver...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Hide automation
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    all_listings = []
    
    try:
        page = 1
        max_pages = 200  # Safety limit
        
        while page <= max_pages:
            # API endpoint
            url = f"https://www.rentfaster.ca/api/search.json?proximity_type=location-city&cur_page={page}&type=&beds=&keywords={city_code}"
            
            print(f"\n📍 Page {page}: {url}")
            driver.get(url)
            
            if page == 1:
                # First page needs more time for Cloudflare
                print("⏳ Waiting for Cloudflare challenge (15 seconds)...")
                time.sleep(15)
            else:
                # Subsequent pages are faster
                print("⏳ Waiting (3 seconds)...")
                time.sleep(3)
            
            # Get page content
            page_text = driver.find_element(By.TAG_NAME, 'body').text
            
            # Try to parse as JSON
            try:
                data = json.loads(page_text)
                listings = data.get('listings', [])
                total_count = data.get('total_count', 0)
                
                if not listings:
                    print(f"   ✓ No more listings (page empty)")
                    break
                
                print(f"   ✓ Got {len(listings)} listings")
                
                # Add city metadata
                for listing in listings:
                    listing['city_code'] = city_code
                    listing['province_code'] = listing.get('prov', 'ab')
                
                all_listings.extend(listings)
                page += 1
                
            except json.JSONDecodeError:
                print(f"   ❌ Not valid JSON")
                print(f"   Page content: {page_text[:200]}")
                
                if "Just a moment" in page_text:
                    print("   ⚠️ Still on Cloudflare challenge page")
                break
        
        print(f"\n{'='*80}")
        print(f"✅ TOTAL: {len(all_listings)} listings from {city_name}")
        print(f"{'='*80}")
        
        if all_listings:
            print(f"\nSample listing:")
            sample = all_listings[0]
            print(f"  ref_id: {sample.get('ref_id')}")
            print(f"  title: {sample.get('title', 'N/A')[:50]}...")
            print(f"  price: ${sample.get('price', 'N/A')}")
            print(f"  beds: {sample.get('beds', 'N/A')}")
        
        return all_listings
        
    finally:
        print("\n⏸️  Browser will close in 3 seconds...")
        time.sleep(3)
        driver.quit()
        print("✅ Browser closed\n")

if __name__ == "__main__":
    # Test Calgary
    calgary_listings = fetch_with_selenium("Calgary", "calgary")
    
    print(f"\n📊 RESULTS:")
    print(f"   Calgary: {len(calgary_listings)} listings")
    
    if calgary_listings:
        # Save to test file
        with open('test_calgary_listings.json', 'w', encoding='utf-8') as f:
            json.dump(calgary_listings, f, indent=2)
        print(f"\n💾 Saved to test_calgary_listings.json")
