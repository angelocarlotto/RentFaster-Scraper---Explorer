#!/usr/bin/env python3
"""
RentFaster Web Scraper
======================
Scrapes rental listings from RentFaster using their internal API endpoint.
Uses only requests library (no Selenium, no Playwright).

How to use:
1. Go to https://www.rentfaster.ca and apply your desired filters
2. Copy the complete URL from your browser's address bar
3. Replace SEARCH_URL below with your URL (or use API_PARAMS for advanced filtering)
4. Run: python main.py

The script automatically:
- Detects the API endpoint and extracts parameters from your URL
- Paginates through all results (48 listings per page)
- Deduplicates by ref_id
- Exports to JSON only
"""

import json
import re
import time
import os
import threading
import traceback
import logging
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Dict, List, Optional

import requests

# Global statistics for live display
stats = {
    'total_pages': 0,
    'current_page': 0,
    'total_listings': 0,
    'unique_listings': 0,
    'duplicates': 0,
    'start_time': 0
}
stats_lock = threading.Lock()

def print_live_status():
    """Print live updating status display for API scraping"""
    with stats_lock:
        elapsed = time.time() - stats['start_time'] if stats['start_time'] > 0 else 0.001
        pages_done = stats['current_page']
        pages_total = stats['total_pages'] if stats['total_pages'] > 0 else 1
        
        progress_pct = (pages_done / pages_total * 100) if pages_total > 0 else 0
        rate = pages_done / elapsed if elapsed > 0 else 0
        remaining = (pages_total - pages_done) / rate if rate > 0 else 0
        
        # Create progress bar
        bar_length = 40
        filled = int(bar_length * progress_pct / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Clear screen and move cursor to top
        print('\033[2J\033[H', end='')
        
        print(f"╔{'═'*78}╗")
        print(f"║ {'LIVE STATUS - RentFaster API Scraper'.center(76)} ║")
        print(f"╠{'═'*78}╣")
        print(f"║ Progress: [{bar}] {progress_pct:5.1f}% ║")
        print(f"║                                                                              ║")
        print(f"║ 📄 Pages:     {pages_done:4d}/{pages_total:4d}  "
              f"📊 Total Fetched: {stats['total_listings']:5d}                  ║")
        print(f"║ ✅ Unique:    {stats['unique_listings']:5d}  "
              f"♻️  Duplicates: {stats['duplicates']:4d}  "
              f"Speed: {rate:4.2f} pages/s     ║")
        print(f"║ ⏱️  Time:     Elapsed: {elapsed/60:5.1f}m  |  Remaining: ~{remaining/60:5.1f}m              ║")
        print(f"╚{'═'*78}╝")
        print(f"\nPress Ctrl+C to stop gracefully...")


# ============================================================================
# CONFIGURATION - Change these settings as needed
# ============================================================================

# IMPORTANT: Replace this with your filtered search URL from the browser's address bar
# Example: "https://www.rentfaster.ca/ab/calgary/rentals/?l=11,51.0458,-114.0575#listview"
SEARCH_URL = "https://www.rentfaster.ca/ab/calgary/rentals/?l=11,51.0458,-114.0575"

# Alternative: You can directly specify API parameters here (overrides SEARCH_URL)
# Leave as None to auto-extract from SEARCH_URL
API_PARAMS = None
# Example API_PARAMS:
# API_PARAMS = {
#     'city': 'calgary',
#     'type': 'apartment',  # apartment, house, condo, etc.
#     'beds': '2',
#     'price_range_adv[from]': '1000',
#     'price_range_adv[to]': '2000',
# }

# Output file names
OUTPUT_JSON = "rentfaster_listings.json"

# Debug settings
DEBUG_MODE = False        # Enable verbose debug output
DEBUG_DIR = "debug_logs"  # Directory for debug files
SAVE_FAILED_RESPONSES = True  # Save failed API responses

# HTTP settings
REQUEST_DELAY = 0.5      # Seconds between page requests (be polite)
REQUEST_TIMEOUT = 30     # Seconds before request timeout

# RentFaster API endpoint (internal API discovered through browser inspection)
API_ENDPOINT = "https://www.rentfaster.ca/api/search.json"

# HTTP headers to mimic a real browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.rentfaster.ca/",
}


# ============================================================================
# DEBUG & LOGGING FUNCTIONS
# ============================================================================

def setup_debug_logging():
    """Setup debug logging infrastructure"""
    if not DEBUG_MODE:
        return None
    
    # Create debug directory
    debug_path = Path(DEBUG_DIR)
    debug_path.mkdir(exist_ok=True)
    
    # Setup file logger
    log_file = debug_path / f"scraper_debug_{int(time.time())}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Debug mode enabled. Logs will be saved to: {log_file}")
    return logger

def log_debug(logger, message: str, data: dict = None):
    """Log debug message with optional data"""
    if logger:
        logger.debug(message)
        if data:
            logger.debug(f"Data: {json.dumps(data, indent=2)}")
    elif DEBUG_MODE:
        print(f"[DEBUG] {message}")
        if data:
            print(f"[DEBUG] Data: {json.dumps(data, indent=2)}")

def log_error(logger, message: str, exception: Exception = None):
    """Log error with stack trace"""
    if logger:
        logger.error(message)
        if exception:
            logger.error(f"Exception: {str(exception)}")
            logger.error(traceback.format_exc())
    elif DEBUG_MODE:
        print(f"[ERROR] {message}")
        if exception:
            print(f"[ERROR] {str(exception)}")
            traceback.print_exc()

def save_debug_response(page_num: int, response_data: dict, status: str):
    """Save API response for debugging"""
    if not (DEBUG_MODE and SAVE_FAILED_RESPONSES):
        return
    
    debug_path = Path(DEBUG_DIR)
    debug_path.mkdir(exist_ok=True)
    
    filename = debug_path / f"page_{page_num}_{status}_{int(time.time())}.json"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)
        if DEBUG_MODE:
            print(f"[DEBUG] Saved {status} response to: {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to save debug response: {e}")

def log_request_metrics(logger, page_num: int, start_time: float, status_code: int, response_size: int):
    """Log HTTP request performance metrics"""
    elapsed = time.time() - start_time
    log_debug(logger, f"Request metrics for page {page_num}:", {
        'status_code': status_code,
        'elapsed_time_ms': round(elapsed * 1000, 2),
        'response_size_bytes': response_size,
        'throughput_kbps': round((response_size / 1024) / elapsed, 2) if elapsed > 0 else 0
    })


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_api_params_from_url(url: str) -> Dict:
    """
    Extract API parameters from a RentFaster search URL.
    
    Args:
        url: RentFaster search URL from browser
    
    Returns:
        Dictionary of API parameters
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Flatten lists to single values
    api_params = {k: v[0] if isinstance(v, list) and len(v) == 1 else v 
                  for k, v in params.items()}
    
    # Extract city from URL path if not in params
    if 'city' not in api_params:
        # URL format: /ab/calgary/rentals/
        path_parts = [p for p in parsed.path.split('/') if p]
        if len(path_parts) >= 2:
            city = path_parts[1]  # Second part is usually the city
            api_params['city'] = city
    
    return api_params


def build_page_url(base_url: str, page: int) -> str:
    """
    Build URL for a specific page by manipulating query parameters.
    
    Args:
        base_url: Base search URL (may contain filters and fragments)
        page: Page number (1-indexed)
    
    Returns:
        URL string for the specified page
    
    Note:
        - Removes any fragment (e.g., #listview) from the URL
        - Adds or updates the 'page' query parameter
        - Preserves all other query parameters
    """
    parsed = urlparse(base_url)
    
    # Remove fragment (#listview, etc.) to avoid pagination issues
    parsed = parsed._replace(fragment="")
    
    # Parse existing query parameters
    query = parse_qs(parsed.query, keep_blank_values=True)
    
    # Update or add page parameter (page 1 typically has no page param)
    if page > 1:
        query["page"] = [str(page)]
    elif "page" in query:
        del query["page"]
    
    # Rebuild query string
    new_query = urlencode(query, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    
    return urlunparse(new_parsed)


def extract_preloaded_listings(html: str) -> Optional[List[Dict]]:
    """
    Extract preloadedListings JavaScript array from HTML.
    
    Args:
        html: Raw HTML content
    
    Returns:
        List of listing dictionaries, or None if not found/invalid
    
    Example in HTML:
        var preloadedListings = [{...}, {...}, ...];
    """
    # Pattern to match: preloadedListings = [...];
    pattern = r"preloadedListings\s*=\s*(\[[\s\S]*?]);"
    match = re.search(pattern, html)
    
    if not match:
        return None
    
    json_str = match.group(1)
    
    try:
        data = json.loads(json_str)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse preloadedListings JSON: {e}")
        return None


def extract_total_listings(html: str) -> Optional[int]:
    """
    Extract preloadedListingsTotal from HTML.
    
    Args:
        html: Raw HTML content
    
    Returns:
        Total number of listings reported by the site, or None if not found
    
    Example in HTML:
        var preloadedListingsTotal = 8839;
    """
    pattern = r"preloadedListingsTotal\s*=\s*(\d+)\s*;"
    match = re.search(pattern, html)
    
    if match:
        return int(match.group(1))
    
    return None


def normalize_listing(raw: Dict) -> Dict:
    """
    Normalize a raw listing object into a standardized format.
    
    Args:
        raw: Raw listing dictionary from preloadedListings array
    
    Returns:
        Normalized listing dictionary with consistent field names
    
    Field mappings:
        - cats/dogs -> cats_allowed/dogs_allowed
        - email -> email_enabled
        - thumb2 (preferred) or thumb -> thumb
        - link (relative) -> full URL with domain prepended
    """
    # Build base normalized dict
    normalized = {
        "ref_id": raw.get("ref_id"),
        "id": raw.get("id"),
        "title": raw.get("title"),
        "intro": raw.get("intro"),
        "address": raw.get("address"),
        "community": raw.get("community"),
        "city": raw.get("city"),
        "province": raw.get("province"),
        "availability": raw.get("availability"),
        "date": raw.get("date"),
        "price": raw.get("price"),
        "price2": raw.get("price2"),
        "beds": raw.get("beds"),
        "beds2": raw.get("beds2"),
        "baths": raw.get("baths"),
        "sq_feet": raw.get("sq_feet"),
        "sq_feet2": raw.get("sq_feet2"),
        "cats_allowed": raw.get("cats"),
        "dogs_allowed": raw.get("dogs"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "userId": raw.get("userId"),
        "phone": raw.get("phone"),
        "phone_2": raw.get("phone_2"),
        "email_enabled": raw.get("email"),
    }
    
    # Handle link - prepend domain if relative path
    link = raw.get("link", "")
    if link and not link.startswith("http"):
        normalized["link"] = f"https://www.rentfaster.ca{link}"
    else:
        normalized["link"] = link if link else None
    
    # Handle thumbnail - prefer thumb2, fallback to thumb
    normalized["thumb"] = raw.get("thumb2") or raw.get("thumb")
    
    return normalized


def save_to_json(listings: List[Dict], filename: str) -> None:
    """
    Save listings to a JSON file.
    
    Args:
        listings: List of normalized listing dictionaries
        filename: Output filename
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved {len(listings)} listings to {filename}")


# ============================================================================
# MAIN SCRAPING LOGIC
# ============================================================================

def main():
    """
    Main function to orchestrate the scraping process.
    
    Process:
        1. Extract API parameters from SEARCH_URL or use API_PARAMS
        2. Call API endpoint to get first page and total count
        3. Loop through all pages (48 listings per API page)
        4. Deduplicate and save results
    """
    # Setup debug logging
    logger = setup_debug_logging()
    
    print("=" * 80)
    print("RentFaster Scraper Starting (API Mode)")
    if DEBUG_MODE:
        print(f"🐛 DEBUG MODE ENABLED - Logs: {DEBUG_DIR}/")
    print("=" * 80)
    
    # Determine API parameters
    if API_PARAMS:
        api_params = API_PARAMS.copy()
        print(f"Using provided API_PARAMS")
    else:
        print(f"Extracting parameters from: {SEARCH_URL}")
        api_params = extract_api_params_from_url(SEARCH_URL)
    
    print(f"API Parameters: {api_params}")
    print()
    
    # Create session for efficient connection reuse
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Dictionary to store unique listings by ref_id
    all_listings_dict = {}
    
    # Statistics
    total_pages_scraped = 0
    total_raw_listings = 0
    total_listings_count = 0
    
    try:
        # ===== FETCH FIRST PAGE FROM API =====
        print("� Fetching page 0 from API...")
        
        # Add page parameter (API uses 0-indexed pages)
        request_params = api_params.copy()
        request_params['cur_page'] = 0
        
        log_debug(logger, "Fetching page 0", {'params': request_params})
        
        try:
            start_time = time.time()
            response = session.get(API_ENDPOINT, params=request_params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Log request metrics
            log_request_metrics(logger, 0, start_time, response.status_code, len(response.content))
            
            data = response.json()
            log_debug(logger, f"Successfully parsed JSON from page 0", {
                'listings_count': len(data.get('listings', [])),
                'total': data.get('total', 0)
            })
            
        except requests.exceptions.RequestException as e:
            log_error(logger, f"Request error fetching from API", e)
            save_debug_response(0, {'error': str(e)}, 'request_error')
            print(f"❌ Error fetching from API: {e}")
            print("⚠ Please check your internet connection.")
            return
        except json.JSONDecodeError as e:
            log_error(logger, f"JSON decode error", e)
            save_debug_response(0, {'raw_response': response.text[:1000]}, 'json_error')
            print(f"❌ Error parsing API response: {e}")
            return
        
        # Extract data from API response
        first_page_listings = data.get('listings', [])
        total_listings_count = data.get('total', 0)
        
        if not first_page_listings:
            print("❌ No listings found in API response.")
            print("⚠ This might mean:")
            print("   - No listings match your filters")
            print("   - The API parameters are incorrect")
            print(f"   - API response: {data}")
            return
        
        page_size = len(first_page_listings)
        print(f"   ✓ Found {page_size} listings on page 0")
        print(f"   ✓ Total listings available: {total_listings_count}")
        
        # Calculate total pages (ceiling division)
        if total_listings_count > 0 and page_size > 0:
            estimated_pages = (total_listings_count + page_size - 1) // page_size
            print(f"   ✓ Estimated pages: {estimated_pages} (at {page_size} per page)")
        else:
            estimated_pages = 1
            print(f"   ⚠ Could not calculate pages, using fallback")

        # Initialize stats
        stats['total_pages'] = estimated_pages
        stats['start_time'] = time.time()
        
        # ===== PROCESS FIRST PAGE =====
        print()
        print("📊 Processing page 0 listings...")
        new_count = 0
        
        for raw_listing in first_page_listings:
            normalized = normalize_listing(raw_listing)
            ref_id = normalized.get("ref_id")
            
            if ref_id and ref_id not in all_listings_dict:
                all_listings_dict[ref_id] = normalized
                new_count += 1
        
        total_raw_listings += len(first_page_listings)
        total_pages_scraped = 1
        
        # Update stats
        with stats_lock:
            stats['current_page'] = 1
            stats['total_listings'] = len(first_page_listings)
            stats['unique_listings'] = new_count
            stats['duplicates'] = len(first_page_listings) - new_count
        
        print(f"   ✓ Added {new_count} unique listings from page 0")
        print(f"   ✓ Total unique so far: {len(all_listings_dict)}")
        print()
        
        # ===== LOOP THROUGH REMAINING PAGES =====
        if estimated_pages > 1:
            print(f"🔄 Starting live scraping monitor...")
            print()
            
            # Print initial status
            print_live_status()
            
            # Start status update thread
            stop_updates = threading.Event()
            
            def update_display():
                while not stop_updates.is_set():
                    time.sleep(1)  # Update every 1 second for steady display
                    print_live_status()
            
            update_thread = threading.Thread(target=update_display, daemon=True)
            update_thread.start()
            
            for page_num in range(1, estimated_pages):
                
                # Update page parameter
                request_params = api_params.copy()
                request_params['cur_page'] = page_num
                
                log_debug(logger, f"Fetching page {page_num}")
                
                try:
                    start_time = time.time()
                    response = session.get(API_ENDPOINT, params=request_params, timeout=REQUEST_TIMEOUT)
                    response.raise_for_status()
                    
                    # Log request metrics
                    log_request_metrics(logger, page_num, start_time, response.status_code, len(response.content))
                    
                    data = response.json()
                    log_debug(logger, f"Page {page_num} fetched", {
                        'listings_count': len(data.get('listings', []))
                    })
                    
                except requests.exceptions.RequestException as e:
                    log_error(logger, f"Request error on page {page_num}", e)
                    save_debug_response(page_num, {'error': str(e)}, 'request_error')
                    print(f"   ❌ Error fetching page {page_num}: {e}")
                    print("   Stopping pagination.")
                    break
                except json.JSONDecodeError as e:
                    log_error(logger, f"JSON error on page {page_num}", e)
                    save_debug_response(page_num, {'raw_response': response.text[:1000]}, 'json_error')
                    print(f"   ❌ Error parsing API response: {e}")
                    break
                
                page_listings = data.get('listings', [])
                
                if not page_listings:
                    print(f"   ⚠ No listings found on page {page_num}")
                    print("   Reached end of results.")
                    break
                
                # Process listings from this page
                new_count = 0
                duplicate_count = 0
                
                for raw_listing in page_listings:
                    normalized = normalize_listing(raw_listing)
                    ref_id = normalized.get("ref_id")
                    
                    if not ref_id:
                        continue
                    
                    if ref_id in all_listings_dict:
                        duplicate_count += 1
                    else:
                        all_listings_dict[ref_id] = normalized
                        new_count += 1
                
                total_raw_listings += len(page_listings)
                total_pages_scraped += 1
                
                # Update stats
                with stats_lock:
                    stats['current_page'] = page_num + 1
                    stats['total_listings'] = total_raw_listings
                    stats['unique_listings'] = len(all_listings_dict)
                    stats['duplicates'] = total_raw_listings - len(all_listings_dict)
                
                # Stop if no new listings found
                if new_count == 0:
                    break
                
                # Be polite - delay between requests
                time.sleep(REQUEST_DELAY)
            
            # Stop status updates
            stop_updates.set()
            update_thread.join(timeout=1)
            
            # Final status display
            print_live_status()
        
        # ===== SAVE RESULTS =====
        print()
        print("=" * 80)
        print("Scraping Complete!")
        print("=" * 80)
        print(f"Pages scraped: {total_pages_scraped}")
        print(f"Raw listings found: {total_raw_listings}")
        print(f"Unique listings: {len(all_listings_dict)}")
        print()
        
        if not all_listings_dict:
            print("⚠ No listings found. Nothing to save.")
            return
        
        # Convert dict to list
        all_listings = list(all_listings_dict.values())
        
        print("💾 Saving results...")
        save_to_json(all_listings, OUTPUT_JSON)
        
        print()
        print("✅ Done!")
        
    except KeyboardInterrupt:
        print("\n")
        print("=" * 80)
        print("⚠ Interrupted by user (Ctrl+C)")
        print("=" * 80)
        
        if all_listings_dict:
            print(f"💾 Saving {len(all_listings_dict)} listings collected so far...")
            all_listings = list(all_listings_dict.values())
            save_to_json(all_listings, OUTPUT_JSON)
            print("✓ Partial results saved.")
        else:
            print("⚠ No listings collected yet.")
    
    finally:
        session.close()


if __name__ == "__main__":
    main()
