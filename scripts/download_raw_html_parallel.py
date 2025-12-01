#!/usr/bin/env python3
"""
[STEP 2] RentFaster Raw HTML Downloader - Parallel Version

Downloads raw HTML for all listings and saves to local files.
This creates a cache that can be scraped offline later.

Configuration:
- Reads cities from cities_config.json
- Downloads only enabled cities
- Stores files in raw/{city_code}/ folders (e.g., raw/calgary/)

Reads: rentfaster_listings.json, cities_config.json
Outputs: raw/{city_code}/*.html files
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import random
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys

# Thread-safe lock for file operations
file_lock = threading.Lock()

# Raw HTML directory
RAW_DIR = Path("raw")
RAW_DIR.mkdir(exist_ok=True)

# Global statistics
stats = {
    'total': 0,
    'completed': 0,
    'success': 0,
    'failed': 0,
    'active_workers': 0,
    'batches_completed': 0,
    'total_batches': 0,
    'start_time': 0,
    'skipped': 0  # Already downloaded
}
stats_lock = threading.Lock()

def load_cities_config():
    """Load cities configuration from cities_config.json"""
    config_file = Path("cities_config.json")
    
    if not config_file.exists():
        print("⚠️  cities_config.json not found, using default Calgary")
        return [{
            "name": "Calgary",
            "province_code": "ab",
            "city_code": "calgary",
            "url": "https://www.rentfaster.ca/ab/calgary/",
            "enabled": True
        }]
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Filter enabled cities and sort by priority
    enabled_cities = [city for city in config.get('cities', []) if city.get('enabled', False)]
    enabled_cities.sort(key=lambda x: x.get('priority', 999))
    
    return enabled_cities

def print_live_status():
    """Print live updating status display"""
    with stats_lock:
        elapsed = time.time() - stats['start_time'] if stats['start_time'] > 0 else 0.001
        rate = stats['completed'] / elapsed if elapsed > 0 else 0
        remaining = (stats['total'] - stats['completed']) / rate if rate > 0 else 0
        
        progress_pct = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        batch_pct = (stats['batches_completed'] / stats['total_batches'] * 100) if stats['total_batches'] > 0 else 0
        success_pct = (stats['success'] / stats['completed'] * 100) if stats['completed'] > 0 else 0
        
        # Create progress bar
        bar_length = 40
        filled = int(bar_length * progress_pct / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Clear screen and move cursor to top
        print('\033[2J\033[H', end='')
        
        print(f"╔{'═'*78}╗")
        print(f"║ {'LIVE STATUS - Raw HTML Downloader'.center(76)} ║")
        print(f"╠{'═'*78}╣")
        print(f"║ Progress: [{bar}] {progress_pct:5.1f}% ║")
        print(f"║                                                                              ║")
        print(f"║ 📊 Downloads:  {stats['completed']:5d}/{stats['total']:5d}  "
              f"✅ Success: {stats['success']:5d} ({success_pct:5.1f}%)  "
              f"❌ Failed: {stats['failed']:4d} ║")
        print(f"║ ⏭️  Skipped: {stats['skipped']:5d} (already downloaded)                                  ║")
        print(f"║ 📦 Batches:   {stats['batches_completed']:4d}/{stats['total_batches']:4d} ({batch_pct:5.1f}%)  "
              f"👷 Active Workers: {stats['active_workers']:2d}                    ║")
        print(f"║ ⏱️  Time:     Elapsed: {elapsed/60:5.1f}m  |  Remaining: ~{remaining/60:5.1f}m  "
              f"Speed: {rate:5.2f}/s ║")
        print(f"╚{'═'*78}╝")
        print(f"\nPress Ctrl+C to stop gracefully...")

def setup_driver(headless=True):
    """Setup Chrome driver with anti-detection options"""
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless=new')
    
    # Enhanced anti-detection options for Cloudflare bypass
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Additional stealth options
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Set preferences
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Performance optimizations
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--log-level=3')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Execute CDP commands to avoid detection
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def download_html(driver, url, ref_id, city, thread_id):
    """Download raw HTML for a single listing"""
    try:
        # Navigate to page
        driver.get(url)
        
        # Random delay for Cloudflare
        cloudflare_wait = random.uniform(3, 7)
        time.sleep(cloudflare_wait)
        
        # Check if Cloudflare challenge is present
        page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        if 'cloudflare' in page_text or 'verify you are human' in page_text:
            time.sleep(random.uniform(5, 10))
        
        # Small random delay
        time.sleep(random.uniform(0.5, 1.5))
        
        # Get HTML source
        html_source = driver.page_source
        
        # Create city-specific directory structure: raw/{city_code}/
        city_code = city.lower().replace(' ', '_')
        city_dir = RAW_DIR / city_code
        city_dir.mkdir(parents=True, exist_ok=True)
        
        # Save to file in city directory
        html_file = city_dir / f"{ref_id}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_source)
        
        # Save metadata
        metadata = {
            'ref_id': ref_id,
            'url': url,
            'city': city,
            'downloaded_at': datetime.now().isoformat(),
            'file_size': len(html_source),
            'success': True
        }
        
        metadata_file = city_dir / f"{ref_id}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        return True
        
    except Exception as e:
        print(f"  [Thread {thread_id}] ❌ Error downloading {ref_id}: {e}")
        return False

def download_batch_worker(batch_data):
    """Worker function that downloads a batch of listings with a single Chrome instance"""
    batch, worker_id, headless = batch_data
    driver = None
    results = []
    
    with stats_lock:
        stats['active_workers'] += 1
    
    try:
        # Create ONE Chrome instance for this entire batch
        driver = setup_driver(headless=headless)
        
        for listing in batch:
            ref_id = listing.get('ref_id')
            link = listing.get('link', '')
            # Fix relative URLs - prepend base domain if needed
            if link.startswith('/'):
                url = f"https://www.rentfaster.ca{link}"
            else:
                url = link
            city = listing.get('city', 'unknown')
            
            # Check if already downloaded (check in city directory)
            city_code = city.lower().replace(' ', '_')
            city_dir = RAW_DIR / city_code
            html_file = city_dir / f"{ref_id}.html"
            if html_file.exists():
                with stats_lock:
                    stats['completed'] += 1
                    stats['skipped'] += 1
                continue
            
            # Download HTML
            success = download_html(driver, url, ref_id, city, worker_id)
            
            with stats_lock:
                stats['completed'] += 1
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
        
        return True
        
    except Exception as e:
        print(f"  [Worker {worker_id}] ❌ Fatal batch error: {e}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        with stats_lock:
            stats['active_workers'] -= 1
            stats['batches_completed'] += 1

def download_parallel(listings, num_workers=5, headless=True):
    """Download listings in parallel using multiple workers"""
    total = len(listings)
    
    print(f"\n{'='*80}")
    print(f"⚙️  CONFIGURATION")
    print(f"{'='*80}")
    print(f"   Workers: {num_workers}")
    print(f"   Mode: {'Headless (background)' if headless else 'Visible browsers'}")
    print(f"   Total listings: {total:,}")
    print(f"   Output directory: {RAW_DIR}/{{city_code}}/")
    
    # Split listings into batches
    print(f"\n📦 Creating batches...", end='', flush=True)
    batch_size = max(1, len(listings) // num_workers)
    batches = []
    for i in range(0, len(listings), batch_size):
        batch = listings[i:i + batch_size]
        worker_id = len(batches) + 1
        batches.append((batch, worker_id, headless))
    print(f" ✓")
    
    print(f"\n📥 BATCH DISTRIBUTION:")
    print(f"   Total listings: {total:,}")
    print(f"   Number of batches: {len(batches)}")
    print(f"   Listings per batch: ~{batch_size}")
    print(f"   Chrome instances: {len(batches)} (one per batch, reused within batch)")
    
    print(f"\n{'='*80}")
    print(f"🚀 STARTING PARALLEL DOWNLOAD")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    # Initialize stats
    stats['total'] = total
    stats['total_batches'] = len(batches)
    stats['start_time'] = start_time
    
    # Print initial status
    print_live_status()
    
    # Execute in parallel with live status updates
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all batch tasks
        future_to_batch = {
            executor.submit(download_batch_worker, batch_data): batch_data 
            for batch_data in batches
        }
        
        # Status update thread
        stop_updates = threading.Event()
        
        def update_display():
            while not stop_updates.is_set():
                time.sleep(1)
                print_live_status()
        
        update_thread = threading.Thread(target=update_display, daemon=True)
        update_thread.start()
        
        # Wait for completion
        for future in as_completed(future_to_batch):
            future.result()
        
        # Stop status updates
        stop_updates.set()
        update_thread.join(timeout=1)
    
    # Final status display
    print_live_status()
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"✅ DOWNLOAD COMPLETE")
    print(f"{'='*80}")
    print(f"   Total downloaded: {stats['success']:,}")
    print(f"   Skipped (already exists): {stats['skipped']:,}")
    print(f"   Failed: {stats['failed']:,}")
    print(f"   Total time: {elapsed/60:.1f} minutes")
    print(f"   Average speed: {stats['completed']/elapsed:.2f} files/second")
    print(f"   Output directory: {RAW_DIR}/{{city_code}}/")
    print(f"{'='*80}\n")

def main():
    print("=" * 80)
    print("📥 RentFaster Raw HTML Downloader (Parallel)")
    print("=" * 80)
    
    # Parse command line arguments
    limit = None
    if len(sys.argv) > 1:
        limit_str = sys.argv[1].lower()
        if limit_str in ['all', '0']:
            limit = None
        else:
            try:
                limit = int(sys.argv[1])
                if limit == 0:
                    limit = None
            except ValueError:
                print(f"❌ Error: First parameter must be a number or 'all'")
                sys.exit(1)
    
    num_workers = 5
    if len(sys.argv) > 2:
        try:
            num_workers = int(sys.argv[2])
        except ValueError:
            print(f"❌ Error: Second parameter must be a number")
            sys.exit(1)
    
    headless = True
    if len(sys.argv) > 3:
        headless_str = sys.argv[3].lower()
        if headless_str in ['false', 'no', '0', 'visible']:
            headless = False
    
    # Load cities configuration
    print("\n🌍 Loading cities configuration...")
    enabled_cities = load_cities_config()
    
    if not enabled_cities:
        print("❌ No cities enabled in cities_config.json")
        print("   Edit cities_config.json and set 'enabled: true' for at least one city")
        sys.exit(1)
    
    print(f"   Enabled cities: {', '.join(c['name'] for c in enabled_cities)}\n")
    
    # Load listings
    print("📂 Loading listings...")
    with open('rentfaster_listings.json', 'r', encoding='utf-8') as f:
        all_listings = json.load(f)
    
    print(f"   Loaded {len(all_listings):,} listings\n")
    
    # Check for already downloaded files (check all city folders)
    existing_files = []
    for city in enabled_cities:
        city_dir = RAW_DIR / city['city_code']
        if city_dir.exists():
            existing_files.extend(list(city_dir.glob("*.html")))
    existing_ids = {f.stem for f in existing_files}
    
    if existing_files:
        print(f"📝 Found {len(existing_files):,} already downloaded HTML files")
        remaining = [l for l in all_listings if l.get('ref_id') not in existing_ids]
        print(f"   {len(remaining):,} remaining to download\n")
        all_listings = remaining
    
    # Apply limit if specified
    if limit is not None:
        all_listings = all_listings[:limit]
        print(f"🧪 TEST MODE: Limiting to {limit} listings\n")
    
    if not all_listings:
        print("✅ All listings already downloaded!")
        sys.exit(0)
    
    print("=" * 80)
    print("⚙️  CONFIGURATION:")
    print("=" * 80)
    print(f"  Listings to download: {len(all_listings):,}")
    print(f"  Parallel workers:     {num_workers}")
    print(f"  Headless mode:        {headless}")
    print(f"  Estimated time:       ~{len(all_listings) / (num_workers * 0.1) / 60:.1f} minutes")
    print("=" * 80)
    
    input("\nPress Enter to start (or Ctrl+C to cancel)...")
    
    try:
        download_parallel(all_listings, num_workers=num_workers, headless=headless)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("💾 Downloaded files are saved in raw/ directory")

if __name__ == "__main__":
    main()
