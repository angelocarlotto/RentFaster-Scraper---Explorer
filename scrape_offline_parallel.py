#!/usr/bin/env python3
"""
RentFaster Offline Scraper - Works with locally downloaded HTML files
Much faster than online scraping and avoids Cloudflare issues
"""

from pathlib import Path
import json
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys
from bs4 import BeautifulSoup

# Thread-safe lock for file operations
file_lock = threading.Lock()

# Raw HTML directory
RAW_DIR = Path("raw")

# Global statistics
stats = {
    'total': 0,
    'completed': 0,
    'success': 0,
    'failed': 0,
    'active_workers': 0,
    'start_time': 0,
    'multi_unit_found': 0,
    'total_units_found': 0
}
stats_lock = threading.Lock()

def print_live_status():
    """Print live updating status display"""
    with stats_lock:
        elapsed = time.time() - stats['start_time'] if stats['start_time'] > 0 else 0.001
        rate = stats['completed'] / elapsed if elapsed > 0 else 0
        remaining = (stats['total'] - stats['completed']) / rate if rate > 0 else 0
        
        progress_pct = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        success_pct = (stats['success'] / stats['completed'] * 100) if stats['completed'] > 0 else 0
        
        # Create progress bar
        bar_length = 40
        filled = int(bar_length * progress_pct / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Clear screen and move cursor to top
        print('\033[2J\033[H', end='')
        
        multi_unit = stats.get('multi_unit_found', 0)
        total_units = stats.get('total_units_found', 0)
        
        print(f"╔{'═'*78}╗")
        print(f"║ {'LIVE STATUS - Offline Scraper'.center(76)} ║")
        print(f"╠{'═'*78}╣")
        print(f"║ Progress: [{bar}] {progress_pct:5.1f}% ║")
        print(f"║                                                                              ║")
        print(f"║ 📊 Listings:  {stats['completed']:5d}/{stats['total']:5d}  "
              f"✅ Success: {stats['success']:5d} ({success_pct:5.1f}%)  "
              f"❌ Failed: {stats['failed']:4d} ║")
        print(f"║ 🏢 Multi-Unit: {multi_unit:4d} buildings  |  {total_units:4d} total unit types found        ║")
        print(f"║ 👷 Active Workers: {stats['active_workers']:2d}                                                        ║")
        print(f"║ ⏱️  Time:     Elapsed: {elapsed/60:5.1f}m  |  Remaining: ~{remaining/60:5.1f}m  "
              f"Speed: {rate:5.2f}/s ║")
        print(f"╚{'═'*78}╝")
        print(f"\nPress Ctrl+C to stop gracefully...")

def extract_from_local_html(html_file, ref_id, city, thread_id):
    """Extract details from local HTML file"""
    try:
        # Find HTML file (check root and city subdirectory)
        if not html_file:
            # Try root directory first
            html_file = RAW_DIR / f"{ref_id}.html"
            if not html_file.exists():
                # Try city subdirectory
                city_dir = RAW_DIR / city.lower().replace(' ', '_')
                html_file = city_dir / f"{ref_id}.html"
        
        if not html_file.exists():
            return None
        
        # Read HTML file
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        page_text = soup.get_text()
        
        details = {
            'ref_id': ref_id,
            'scraped_at': datetime.now().isoformat(),
            'is_multi_unit': False,
            'beds': None,
            'parking_spots': None,
            'furnished': None,
            'utilities_included': [],
            'amenities': [],
            'full_description': None,
        }
        
        # Extract parking with improved patterns
        search_text = page_text.lower()
        
        parking_patterns = [
            r'(\d+)\s+spots?\s+per\s+unit',  # "2 spots per unit"
            r'parking\s+spots[:\s]+(\d+)\s+spot',  # "Parking Spots: 2 spots"
            r'total\s+property\s+parking\s+spots[:\s]+(\d+)',  # "Total Property Parking Spots: 2"
            r'(\d+)\s+parking\s+(?:spot|stall|space)s?',  # "2 parking spots"
            r'(\d+)\s+(?:titled|underground|surface|assigned|reserved)\s+parking',
            r'parking[:\s]+(\d+)',
            r'(\d+)\s+stalls?\s+included',
        ]
        
        for pattern in parking_patterns:
            match = re.search(pattern, search_text)
            if match:
                parking_num = int(match.group(1))
                if 0 < parking_num < 100:  # Sanity check
                    details['parking_spots'] = parking_num
                    break
        
        # Also try word-to-number conversion
        if not details['parking_spots']:
            word_numbers = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4,
                'five': 5, 'six': 6, 'seven': 7, 'eight': 8
            }
            for word, num in word_numbers.items():
                if f'{word} parking' in search_text or f'{word} stall' in search_text:
                    details['parking_spots'] = num
                    break
        
        # Extract full description
        # Look for description sections
        desc_selectors = [
            '.listing-description',
            '.description',
            '[class*="description"]',
            '.property-description',
            '#description'
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                desc_text = desc_elem.get_text(strip=True)
                if desc_text and len(desc_text) > 20:
                    details['full_description'] = desc_text
                    break
        
        # Fallback: Extract from page text
        if not details['full_description']:
            desc_patterns = [
                r'Welcome to.*?(?=Contact|Apply|Features|Amenities|$)',
                r'This.*?(?=Contact|Apply|Features|Amenities|$)',
            ]
            for pattern in desc_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                if match:
                    desc = match.group(0).strip()
                    if len(desc) > 50:
                        details['full_description'] = desc[:1000]
                        break
        
        # Extract bedrooms
        bed_match = re.search(r'(\d+)\s*(bedroom|bed|bd)', page_text, re.IGNORECASE)
        if bed_match:
            details['beds'] = int(bed_match.group(1))
        elif 'bachelor' in page_text.lower() or 'studio' in page_text.lower():
            details['beds'] = 0
        
        # Extract furnished status
        if 'unfurnished' in page_text.lower():
            details['furnished'] = 'Unfurnished'
        elif 'furnished' in page_text.lower():
            details['furnished'] = 'Furnished'
        else:
            details['furnished'] = 'Unknown'
        
        # Extract utilities
        utilities_keywords = ['heat', 'water', 'electricity', 'hydro', 'gas', 'internet', 'cable']
        for keyword in utilities_keywords:
            if keyword in page_text.lower() and 'included' in page_text.lower():
                details['utilities_included'].append(keyword.title())
        
        # Extract amenities
        amenity_keywords = [
            'gym', 'fitness', 'pool', 'laundry', 'balcony', 'patio',
            'dishwasher', 'air conditioning', 'elevator', 'storage',
            'bike room', 'concierge', 'security'
        ]
        for keyword in amenity_keywords:
            if keyword in page_text.lower():
                details['amenities'].append(keyword.title())
        
        return details
        
    except Exception as e:
        print(f"  [Thread {thread_id}] ❌ Error parsing {ref_id}: {e}")
        return None

def scrape_batch_worker(batch_data):
    """Worker function that processes a batch of listings from local files"""
    batch, worker_id = batch_data
    results = []
    
    with stats_lock:
        stats['active_workers'] += 1
    
    try:
        for listing in batch:
            ref_id = listing.get('ref_id')
            city = listing.get('city', 'unknown')
            
            # Extract details from local HTML (function will find the file)
            details = extract_from_local_html(None, ref_id, city, worker_id)
            
            if details:
                # Merge with original data
                merged = {**listing, **details}
                results.append(merged)
                with stats_lock:
                    stats['completed'] += 1
                    stats['success'] += 1
            else:
                results.append(listing)
                with stats_lock:
                    stats['completed'] += 1
                    stats['failed'] += 1
        
        return results
        
    except Exception as e:
        print(f"  [Worker {worker_id}] ❌ Fatal batch error: {e}")
        return [listing for listing in batch]
    finally:
        with stats_lock:
            stats['active_workers'] -= 1

def save_progress(data, filename='rentfaster_detailed_offline.json'):
    """Thread-safe save progress to JSON file"""
    with file_lock:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def scrape_parallel(listings, num_workers=10):
    """Scrape listings in parallel from local HTML files"""
    detailed_listings = []
    total = len(listings)
    
    print(f"\n{'='*80}")
    print(f"⚙️  CONFIGURATION")
    print(f"{'='*80}")
    print(f"   Workers: {num_workers}")
    print(f"   Mode: Offline (from local HTML files)")
    print(f"   Input directory: {RAW_DIR}")
    print(f"   Total listings: {total:,}")
    
    # Split listings into batches
    print(f"\n📦 Creating batches...", end='', flush=True)
    batch_size = max(1, len(listings) // num_workers)
    batches = []
    for i in range(0, len(listings), batch_size):
        batch = listings[i:i + batch_size]
        worker_id = len(batches) + 1
        batches.append((batch, worker_id))
    print(f" ✓")
    
    print(f"\n📊 BATCH DISTRIBUTION:")
    print(f"   Total listings: {total:,}")
    print(f"   Number of batches: {len(batches)}")
    print(f"   Listings per batch: ~{batch_size}")
    
    print(f"\n{'='*80}")
    print(f"🚀 STARTING PARALLEL SCRAPING")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    # Initialize stats
    stats['total'] = total
    stats['start_time'] = start_time
    
    # Print initial status
    print_live_status()
    
    # Execute in parallel with live status updates
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all batch tasks
        future_to_batch = {
            executor.submit(scrape_batch_worker, batch_data): batch_data 
            for batch_data in batches
        }
        
        # Status update thread
        stop_updates = threading.Event()
        
        def update_display():
            while not stop_updates.is_set():
                time.sleep(0.5)
                print_live_status()
        
        update_thread = threading.Thread(target=update_display, daemon=True)
        update_thread.start()
        
        # Process completed batches
        for future in as_completed(future_to_batch):
            batch_results = future.result()
            detailed_listings.extend(batch_results)
            
            # Save progress periodically
            if len(detailed_listings) % 100 == 0:
                save_progress(detailed_listings)
        
        # Stop status updates
        stop_updates.set()
        update_thread.join(timeout=1)
    
    # Final status display
    print_live_status()
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"✅ SCRAPING COMPLETE")
    print(f"{'='*80}")
    print(f"   Total listings processed: {len(detailed_listings):,}")
    print(f"   Successful: {stats['success']:,}")
    print(f"   Failed: {stats['failed']:,}")
    print(f"   Total time: {elapsed/60:.1f} minutes")
    print(f"   Average speed: {len(detailed_listings)/elapsed:.2f} listings/second")
    print(f"{'='*80}\n")
    
    return detailed_listings

def main():
    print("=" * 80)
    print("🚀 RentFaster Offline Scraper (Parallel)")
    print("=" * 80)
    
    # Check if raw directory exists
    if not RAW_DIR.exists():
        print("\n❌ ERROR: Raw directory not found!")
        print("   Please run 'download_raw_html_parallel.py' first to download HTML files.")
        print(f"   Expected directory: {RAW_DIR}/")
        sys.exit(1)
    
    # Parse command line arguments
    num_workers = 10
    if len(sys.argv) > 1:
        try:
            num_workers = int(sys.argv[1])
        except ValueError:
            print(f"❌ Error: First parameter must be a number (workers)")
            sys.exit(1)
    
    # Load listings
    print("\n📂 Loading listings...")
    with open('rentfaster_listings.json', 'r', encoding='utf-8') as f:
        all_listings = json.load(f)
    
    print(f"   Loaded {len(all_listings):,} listings\n")
    
    # Check how many have HTML files (including subdirectories)
    html_files = []
    html_ids = set()
    
    # Check root directory
    html_files.extend(RAW_DIR.glob("*.html"))
    
    # Check city subdirectories
    for city_dir in RAW_DIR.iterdir():
        if city_dir.is_dir():
            html_files.extend(city_dir.glob("*.html"))
    
    html_ids = {f.stem for f in html_files}
    
    if not html_files:
        print("\n❌ ERROR: No raw HTML files found!")
        print("   Please run 'download_raw_html_parallel.py' first to download HTML files.")
        print(f"   Expected directory: {RAW_DIR}/ or {RAW_DIR}/city_name/")
        sys.exit(1)
    
    print(f"📁 Found {len(html_files):,} HTML files in {RAW_DIR}/")
    
    # Filter to only listings with HTML files
    listings_with_html = [l for l in all_listings if l.get('ref_id') in html_ids]
    
    if not listings_with_html:
        print("\n❌ ERROR: No matching listings found!")
        sys.exit(1)
    
    print(f"   {len(listings_with_html):,} listings have HTML files\n")
    
    print("=" * 80)
    print("⚙️  CONFIGURATION:")
    print("=" * 80)
    print(f"  Listings to scrape: {len(listings_with_html):,}")
    print(f"  Parallel workers:   {num_workers}")
    print(f"  Estimated time:     ~{len(listings_with_html) / (num_workers * 50) / 60:.1f} minutes")
    print("=" * 80)
    
    input("\nPress Enter to start (or Ctrl+C to cancel)...")
    
    try:
        # Run parallel scraping
        new_listings = scrape_parallel(listings_with_html, num_workers=num_workers)
        
        # Save final results
        print(f"\n{'='*80}")
        print(f"💾 SAVING FINAL RESULTS")
        print(f"{'='*80}")
        print(f"Saving JSON...", end='', flush=True)
        save_progress(new_listings)
        print(f" ✓")
        
        print(f"\n{'='*80}")
        print(f"✅ COMPLETE!")
        print(f"{'='*80}")
        print(f"   Total in database: {len(new_listings):,}")
        print(f"\n   📁 File saved:")
        print(f"      • rentfaster_detailed_offline.json ({len(new_listings):,} listings)")
        print(f"{'='*80}\n")
        
        # Show parking stats
        with_parking = sum(1 for item in new_listings if item.get('parking_spots'))
        with_desc = sum(1 for item in new_listings if item.get('full_description'))
        
        print(f"📊 EXTRACTION STATISTICS:")
        print(f"   Parking spots: {with_parking:,} ({with_parking/len(new_listings)*100:.1f}%)")
        print(f"   Full descriptions: {with_desc:,} ({with_desc/len(new_listings)*100:.1f}%)")
        print(f"{'='*80}\n")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        if 'new_listings' in locals() and new_listings:
            save_progress(new_listings)
            print(f"💾 Saved {len(new_listings):,} listings before exit")

if __name__ == "__main__":
    main()
