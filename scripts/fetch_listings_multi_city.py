#!/usr/bin/env python3
"""
[STEP 1] Fetch listings from multiple cities based on cities_config.json - PARALLEL VERSION

This script queries the RentFaster API for each enabled city and combines results.
Uses Selenium to bypass Cloudflare protection with parallel browser workers.

Reads: cities_config.json
Outputs: rentfaster_listings.json
"""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-safe statistics
stats_lock = threading.Lock()
city_stats = {}

def load_cities_config():
    """Load cities configuration"""
    config_file = Path("cities_config.json")
    
    if not config_file.exists():
        print("❌ cities_config.json not found!")
        return []
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    enabled_cities = [city for city in config.get('cities', []) if city.get('enabled', False)]
    enabled_cities.sort(key=lambda x: x.get('priority', 999))
    
    return enabled_cities

def fetch_city_listings(city_config, driver, is_first_city, max_pages, worker_id):
    """Fetch listings for a specific city using Selenium to bypass Cloudflare"""
    print(f"[Worker {worker_id}] 📍 Fetching listings for {city_config['name']}...")
    
    all_listings = []
    page = 1
    
    while page <= max_pages:
        try:
            # Build API URL with query parameters
            if 'city_id' in city_config:
                url = (f"https://www.rentfaster.ca/api/search.json?"
                       f"city_id={city_config['city_id']}&"
                       f"cur_page={page}&"
                       f"type=&"
                       f"beds=")
            else:
                url = (f"https://www.rentfaster.ca/api/search.json?"
                       f"proximity_type=location-city&"
                       f"cur_page={page}&"
                       f"type=&"
                       f"beds=&"
                       f"keywords={city_config['city_code']}")
            
            print(f"[Worker {worker_id}]    Page {page}...", end='', flush=True)
            
            # Load the page
            driver.get(url)
            
            # Wait for Cloudflare challenge on first page of first city
            if page == 1 and is_first_city:
                print(f" (waiting 15s for Cloudflare)...", end='', flush=True)
                time.sleep(15)
            else:
                time.sleep(3)
            
            # Get the JSON response from the page
            page_text = driver.find_element(By.TAG_NAME, 'body').text
            data = json.loads(page_text)
            
            listings = data.get('listings', [])
            
            if not listings:
                print(f" ✓ (empty, done)")
                break
            
            # Add city info to each listing
            for listing in listings:
                listing['city_code'] = city_config['city_code']
                listing['province_code'] = city_config['province_code']
            
            all_listings.extend(listings)
            print(f" ✓ ({len(listings)} listings)")
            
            page += 1
            
        except json.JSONDecodeError as e:
            print(f" ❌ JSON Error: {e}")
            break
        except Exception as e:
            print(f" ❌ Unexpected error: {e}")
            break
    
    print(f"[Worker {worker_id}]    Total: {len(all_listings):,} listings from {city_config['name']}")
    
    with stats_lock:
        city_stats[city_config['name']] = len(all_listings)
    
    return all_listings

def fetch_city_worker(city_config, max_pages, worker_id, is_first):
    """Worker function to fetch listings for a single city in a separate browser"""
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        listings = fetch_city_listings(city_config, driver, is_first, max_pages, worker_id)
        return listings
    finally:
        print(f"[Worker {worker_id}] 🌐 Closing browser...")
        driver.quit()

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Fetch listings from RentFaster for multiple cities (parallel)')
    parser.add_argument('--max-pages', type=int, default=200, 
                        help='Maximum number of pages to fetch per city (default: 200)')
    parser.add_argument('--workers', type=int, default=3,
                        help='Number of parallel browser workers (default: 3, max: 10)')
    args = parser.parse_args()
    
    # Validate workers
    if args.workers < 1:
        args.workers = 1
    if args.workers > 10:
        print("⚠️  Warning: Maximum 10 workers allowed, using 10")
        args.workers = 10
    
    print("=" * 80)
    print("🌍 RENTFASTER MULTI-CITY LISTINGS FETCHER (PARALLEL)")
    print("=" * 80)
    print(f"⚙️  Max pages per city: {args.max_pages}")
    print(f"⚙️  Parallel workers: {args.workers}")
    
    # Load configuration
    enabled_cities = load_cities_config()
    
    if not enabled_cities:
        print("\n❌ No cities enabled in cities_config.json")
        print("   Edit the file and set 'enabled: true' for at least one city")
        return
    
    print(f"\n📋 Enabled cities: {', '.join(c['name'] for c in enabled_cities)}")
    print(f"   Total: {len(enabled_cities)} cities")
    
    # Fetch listings in parallel
    print(f"\n🚀 Starting parallel fetch with {args.workers} workers...")
    start_time = time.time()
    
    all_listings = []
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all cities to the worker pool
        futures = []
        for idx, city in enumerate(enabled_cities):
            is_first = (idx == 0)
            future = executor.submit(fetch_city_worker, city, args.max_pages, idx % args.workers, is_first)
            futures.append(future)
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                city_listings = future.result()
                all_listings.extend(city_listings)
            except Exception as e:
                print(f"❌ Error fetching city: {e}")
    
    elapsed_time = time.time() - start_time
    
    # Remove duplicates by ref_id
    print(f"\n🔍 Removing duplicates...")
    seen = set()
    unique_listings = []
    for listing in all_listings:
        ref_id = listing.get('ref_id')
        if ref_id and ref_id not in seen:
            seen.add(ref_id)
            unique_listings.append(listing)
    
    duplicates_removed = len(all_listings) - len(unique_listings)
    if duplicates_removed > 0:
        print(f"   Removed {duplicates_removed:,} duplicate listings")
    
    # Save to file
    output_file = 'rentfaster_listings.json'
    print(f"\n💾 Saving to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unique_listings, f, ensure_ascii=False, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("✅ FETCH COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Summary by City:")
    for city_name in sorted(city_stats.keys()):
        print(f"   {city_name:15s}: {city_stats[city_name]:5,} listings")
    print(f"   {'─' * 23}")
    print(f"   {'Total (unique)':15s}: {len(unique_listings):5,} listings")
    print(f"\n⏱️  Time taken: {elapsed_time/60:.1f} minutes ({elapsed_time:.1f} seconds)")
    print(f"📁 Saved to: {output_file}")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n💡 Next step: Run download_raw_html_parallel.py to download HTML files")
    print("=" * 80)

if __name__ == "__main__":
    main()
