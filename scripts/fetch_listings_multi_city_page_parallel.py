#!/usr/bin/env python3
"""
RentFaster Multi-City Listings Fetcher with Page-Level Parallelization
Fetches rental listings from multiple cities simultaneously at the PAGE level,
not the city level, to avoid bottlenecks on large cities like Calgary.
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import threading

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Thread-safe statistics
stats_lock = threading.Lock()
city_stats = {}
page_results = {}  # Store results by (city_name, page_num)
city_completed = {}  # Track which cities are done (got empty page)

def setup_driver():
    """Setup and return a Chrome WebDriver instance with anti-detection"""
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Hide webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def fetch_page(city_config, page_num, driver, worker_id, is_first_page_ever):
    """Fetch a single page for a city"""
    city_name = city_config['name']
    city_id = city_config['city_id']
    
    url = f"https://www.rentfaster.ca/api/search.json?proximity_type=location-city&cur_page={page_num}&city_id={city_id}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.get(url)
            
            # On first page ever, wait for Cloudflare
            if is_first_page_ever:
                print(f"[Worker {worker_id}]    Page {page_num}... (waiting 15s for Cloudflare)...", end='', flush=True)
                time.sleep(15)
            else:
                print(f"[Worker {worker_id}] {city_name} Page {page_num}...", end='', flush=True)
                # Add delay between requests to be respectful
                time.sleep(0.5)
            
            # Wait for JSON to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "pre"))
            )
            
            # Extract JSON
            pre_element = driver.find_element(By.TAG_NAME, "pre")
            json_text = pre_element.text
            data = json.loads(json_text)
            
            listings = data.get('listings', [])
            print(f" ✓ ({len(listings)} listings)", flush=True)
            
            return listings
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f" ⚠️ Retry {attempt+1}/{max_retries}...", end='', flush=True)
                time.sleep(2)
            else:
                print(f" ✗ Failed after {max_retries} attempts", flush=True)
                return []
    
    return []

def worker_thread(task_queue, results_queue, worker_id, is_first_worker):
    """Worker thread that processes tasks from the queue"""
    driver = None
    is_first_page = is_first_worker  # Only first worker does Cloudflare wait
    
    try:
        driver = setup_driver()
        time.sleep(worker_id * 0.5)  # Stagger driver startup to avoid Chrome issues
        
        while True:
            try:
                # Get next task (non-blocking with timeout)
                task = task_queue.get(timeout=2)
                if task is None:  # Poison pill to stop worker
                    break
                
                city_config, page_num = task
                city_name = city_config['name']
                
                # Check if city is already completed (got empty page)
                with stats_lock:
                    if city_completed.get(city_name, False):
                        # Skip this page, city is done
                        task_queue.task_done()
                        continue
                
                # Fetch the page
                listings = fetch_page(city_config, page_num, driver, worker_id, is_first_page)
                is_first_page = False  # Only first page needs Cloudflare wait
                
                # If empty page, mark city as completed
                if len(listings) == 0:
                    with stats_lock:
                        city_completed[city_name] = True
                        print(f"[Worker {worker_id}] 🏁 {city_name} completed (empty page)", flush=True)
                
                # Store results
                results_queue.put((city_name, page_num, listings))
                
                # Mark task as done
                task_queue.task_done()
                
            except Exception as e:
                if "Empty" not in str(e):  # Ignore empty queue timeout
                    print(f"[Worker {worker_id}] Error in task: {e}", flush=True)
                break
                
    except Exception as e:
        print(f"[Worker {worker_id}] Fatal error: {e}", flush=True)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        print(f"[Worker {worker_id}] 🌐 Browser closed", flush=True)

def main():
    parser = argparse.ArgumentParser(description='Fetch RentFaster listings with page-level parallelization')
    parser.add_argument('--workers', type=int, default=10, help='Number of parallel workers (default: 10)')
    parser.add_argument('--max-pages', type=int, default=200, help='Maximum pages per city (default: 200)')
    args = parser.parse_args()
    
    # Limit workers to reasonable range
    args.workers = max(1, min(args.workers, 20))
    
    print("=" * 80)
    print("🌍 RENTFASTER MULTI-CITY LISTINGS FETCHER (PAGE-LEVEL PARALLEL)")
    print("=" * 80)
    print(f"⚙️  Max pages per city: {args.max_pages}")
    print(f"⚙️  Parallel workers: {args.workers}")
    print()
    
    # City configurations
    cities = [
        {'name': 'Calgary', 'city_id': '1', 'enabled': True},
        {'name': 'Edmonton', 'city_id': '2', 'enabled': True},
        {'name': 'Regina', 'city_id': '3', 'enabled': True},
        {'name': 'Saskatoon', 'city_id': '4', 'enabled': True},
        {'name': 'Winnipeg', 'city_id': '7', 'enabled': True},
        {'name': 'Vancouver', 'city_id': '11', 'enabled': True},
        {'name': 'Toronto', 'city_id': '5', 'enabled': True},
        {'name': 'Airdrie', 'city_id': '8', 'enabled': True},
        {'name': 'Chestermere', 'city_id': '9', 'enabled': True},
        {'name': 'Cochrane', 'city_id': '10', 'enabled': True},
        {'name': 'Fort Saskatchewan', 'city_id': '12', 'enabled': True},
        {'name': 'Beaumont', 'city_id': '13', 'enabled': True},
        {'name': 'Leduc', 'city_id': '14', 'enabled': True},
        {'name': 'St. Albert', 'city_id': '15', 'enabled': True},
        {'name': 'Surrey', 'city_id': '16', 'enabled': True},
        {'name': 'Victoria', 'city_id': '17', 'enabled': True},
        {'name': 'Brampton', 'city_id': '18', 'enabled': True},
        {'name': 'Kitchener', 'city_id': '19', 'enabled': True},
        {'name': 'London', 'city_id': '20', 'enabled': True},
        {'name': 'Mississauga', 'city_id': '21', 'enabled': True},
        {'name': 'Ottawa', 'city_id': '22', 'enabled': True},
        {'name': 'Waterloo', 'city_id': '23', 'enabled': True},
    ]
    
    enabled_cities = [c for c in cities if c.get('enabled', True)]
    
    print(f"📋 Enabled cities: {', '.join([c['name'] for c in enabled_cities])}")
    print(f"   Total: {len(enabled_cities)} cities")
    print()
    
    # Create task queue - ALL pages for ALL cities
    task_queue = Queue()
    results_queue = Queue()
    
    # Initialize city completion tracking
    global city_completed
    for city in enabled_cities:
        city_completed[city['name']] = False
    
    print("🔨 Building task queue...")
    total_tasks = 0
    for city in enabled_cities:
        for page_num in range(1, args.max_pages + 1):
            task_queue.put((city, page_num))
            total_tasks += 1
    
    print(f"   Total tasks: {total_tasks} (max {args.max_pages} pages per city)")
    print(f"   ⚡ Smart early stopping: will skip remaining pages after empty result")
    print()
    
    # Start workers
    print(f"🚀 Starting {args.workers} workers...")
    start_time = time.time()
    
    workers = []
    for i in range(args.workers):
        is_first = (i == 0)
        thread = threading.Thread(
            target=worker_thread,
            args=(task_queue, results_queue, i, is_first),
            daemon=True
        )
        thread.start()
        workers.append(thread)
    
    # Wait for all tasks to complete
    task_queue.join()
    
    # Stop workers by sending poison pills
    for _ in range(args.workers):
        task_queue.put(None)
    
    # Wait for workers to finish
    for worker in workers:
        worker.join()
    
    print()
    print("📊 Collecting results...")
    
    # Collect all results
    city_listings = {}
    while not results_queue.empty():
        city_name, page_num, listings = results_queue.get()
        if city_name not in city_listings:
            city_listings[city_name] = []
        city_listings[city_name].extend(listings)
    
    # Flatten and deduplicate
    all_listings = []
    seen_refs = set()
    
    print()
    print("📋 Results by city:")
    for city_name in [c['name'] for c in enabled_cities]:
        listings = city_listings.get(city_name, [])
        print(f"   {city_name:25s}: {len(listings):5,} listings")
        
        for listing in listings:
            ref_id = listing.get('ref_id')
            if ref_id and ref_id not in seen_refs:
                seen_refs.add(ref_id)
                all_listings.append(listing)
    
    # Add metadata
    for listing in all_listings:
        listing['scraped_at'] = datetime.now().isoformat()
    
    # Save to file
    output_file = 'rentfaster_listings.json'
    print()
    print(f"💾 Saving {len(all_listings):,} unique listings to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_listings, f, indent=2, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    
    print()
    print("=" * 80)
    print("✅ FETCH COMPLETE!")
    print("=" * 80)
    print(f"📊 Total listings: {len(all_listings):,}")
    print(f"⏱️  Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"📁 Output file: {output_file}")
    print("=" * 80)

if __name__ == '__main__':
    main()
