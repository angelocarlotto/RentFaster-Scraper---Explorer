#!/usr/bin/env python3
"""
RentFaster Parallel Detailed Scraper
Uses multiple Chrome instances in parallel to scrape faster
Can run 5-10 browsers simultaneously depending on your machine
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import traceback
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os
import random

# Thread-safe lock for file operations
file_lock = threading.Lock()

# Debug settings
DEBUG_MODE = False
DEBUG_DIR = "debug_logs"
SAVE_SCREENSHOTS = True  # Save screenshots on errors
SAVE_HTML_DUMPS = True   # Save HTML source on errors

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
    'errors': []  # Track error details
}
stats_lock = threading.Lock()

# Setup logging
def setup_debug_logging():
    """Setup debug logging infrastructure"""
    if not DEBUG_MODE:
        return None
    
    debug_path = Path(DEBUG_DIR)
    debug_path.mkdir(exist_ok=True)
    
    log_file = debug_path / f"scraper_parallel_debug_{int(time.time())}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(threadName)-10s] [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Debug mode enabled. Logs: {log_file}")
    return logger

logger = setup_debug_logging()

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
        
        multi_unit = stats.get('multi_unit_found', 0)
        total_units = stats.get('total_units_found', 0)
        
        print(f"╔{'═'*78}╗")
        print(f"║ {'LIVE STATUS - RentFaster Details Scraper'.center(76)} ║")
        print(f"╠{'═'*78}╣")
        print(f"║ Progress: [{bar}] {progress_pct:5.1f}% ║")
        print(f"║                                                                              ║")
        print(f"║ 📊 Listings:  {stats['completed']:5d}/{stats['total']:5d}  "
              f"✅ Success: {stats['success']:5d} ({success_pct:5.1f}%)  "
              f"❌ Failed: {stats['failed']:4d} ║")
        print(f"║ 🏢 Multi-Unit: {multi_unit:4d} buildings  |  {total_units:4d} total unit types found        ║")
        print(f"║ 📦 Batches:   {stats['batches_completed']:4d}/{stats['total_batches']:4d} ({batch_pct:5.1f}%)  "
              f"👷 Active Workers: {stats['active_workers']:2d}                    ║")
        print(f"║ ⏱️  Time:     Elapsed: {elapsed/60:5.1f}m  |  Remaining: ~{remaining/60:5.1f}m  "
              f"Speed: {rate:5.2f}/s ║")
        print(f"╚{'═'*78}╝")
        print(f"\nPress Ctrl+C to stop gracefully...")

def save_debug_screenshot(driver, ref_id: str, thread_id: int, reason: str):
    """Save screenshot for debugging"""
    if not (DEBUG_MODE and SAVE_SCREENSHOTS):
        return
    
    try:
        debug_path = Path(DEBUG_DIR) / "screenshots"
        debug_path.mkdir(parents=True, exist_ok=True)
        
        filename = debug_path / f"{ref_id}_{reason}_{int(time.time())}.png"
        driver.save_screenshot(str(filename))
        if logger:
            logger.debug(f"[Thread {thread_id}] Screenshot saved: {filename}")
    except Exception as e:
        if logger:
            logger.error(f"[Thread {thread_id}] Failed to save screenshot: {e}")

def save_debug_html(driver, ref_id: str, thread_id: int, reason: str):
    """Save HTML source for debugging"""
    if not (DEBUG_MODE and SAVE_HTML_DUMPS):
        return
    
    try:
        debug_path = Path(DEBUG_DIR) / "html_dumps"
        debug_path.mkdir(parents=True, exist_ok=True)
        
        filename = debug_path / f"{ref_id}_{reason}_{int(time.time())}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        if logger:
            logger.debug(f"[Thread {thread_id}] HTML saved: {filename}")
    except Exception as e:
        if logger:
            logger.error(f"[Thread {thread_id}] Failed to save HTML: {e}")

def log_error_details(ref_id: str, thread_id: int, error_type: str, exception: Exception, url: str = None):
    """Log detailed error information"""
    error_info = {
        'ref_id': ref_id,
        'thread_id': thread_id,
        'error_type': error_type,
        'exception': str(exception),
        'traceback': traceback.format_exc(),
        'url': url,
        'timestamp': datetime.now().isoformat()
    }
    
    with stats_lock:
        stats['errors'].append(error_info)
    
    if logger:
        logger.error(f"[Thread {thread_id}] Error details for {ref_id}:")
        logger.error(json.dumps(error_info, indent=2))
    
    # Save to file
    if DEBUG_MODE:
        try:
            debug_path = Path(DEBUG_DIR) / "errors"
            debug_path.mkdir(parents=True, exist_ok=True)
            
            filename = debug_path / f"{ref_id}_error_{int(time.time())}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to save error details: {e}")

def setup_driver(headless=False):
    """Setup Chrome driver with options to avoid detection"""
    try:
        if logger:
            logger.debug(f"Setting up Chrome driver (headless={headless})")
        
        chrome_options = Options()
        
        # Run headless for parallel execution (recommended)
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
        
        # Set preferences to appear more like a real browser
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Performance optimizations for parallel execution
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        
        # Suppress logs in non-debug mode
        if not DEBUG_MODE:
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        if logger:
            logger.debug("Chrome driver setup successful")
    
        # Execute CDP commands to avoid detection
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    except Exception as e:
        if logger:
            logger.error(f"Failed to setup Chrome driver: {e}")
            logger.error(traceback.format_exc())
        raise

def extract_multi_unit_details(driver, url, ref_id, thread_id):
    """Extract details from a multi-unit listing (apartment building with multiple unit types)"""
    try:
        units = []
        
        # Find all unit cards
        unit_cards = driver.find_elements(By.CSS_SELECTOR, '.units-wrap > .card.block')
        
        if not unit_cards:
            print(f"  [Thread {thread_id}] ⚠️  No unit cards found in multi-unit listing {ref_id}")
            return None
        
        print(f"  [Thread {thread_id}] 🏢 Found {len(unit_cards)} unit types in {ref_id}")
        
        # Extract shared property information
        page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        
        # Get address/building name
        building_address = 'Unknown'
        try:
            h1_elem = driver.find_element(By.TAG_NAME, 'h1')
            building_address = h1_elem.text.strip()
        except:
            pass
        
        # Extract each unit type
        for idx, card in enumerate(unit_cards, 1):
            try:
                unit_details = {
                    'ref_id': f"{ref_id}_unit_{idx}",
                    'parent_ref_id': ref_id,
                    'url': url,
                    'building_address': building_address,
                    'is_multi_unit': True,
                    'unit_type': None,
                    'units_available': None,
                    'beds': None,
                    'baths': None,
                    'sqft': None,
                    'price': None,
                    'utilities_included': [],
                    'furnished': 'Unknown',
                    'parking_spots': None,
                    'amenities': [],
                    'smoking_allowed': 'Unknown',
                    'building_type': 'Apartment',
                    'scraped_at': datetime.now().isoformat()
                }
                
                card_text = card.text
                
                # Extract unit type (e.g., "1 Bedroom Apartment", "Studio")
                try:
                    unit_type_elem = card.find_element(By.CSS_SELECTOR, 'h3, .unit-type, strong')
                    unit_details['unit_type'] = unit_type_elem.text.strip()
                except:
                    # Try to extract from first line of card text
                    first_line = card_text.split('\n')[0] if '\n' in card_text else card_text[:50]
                    unit_details['unit_type'] = first_line.strip()
                
                # Extract number of units available
                import re
                units_match = re.search(r'(\d+)\s*unit[s]?', card_text, re.IGNORECASE)
                if units_match:
                    unit_details['units_available'] = int(units_match.group(1))
                
                # Extract bedrooms
                bed_patterns = [
                    r'(\d+)\s*Bed',
                    r'(\d+)\s*BR',
                    r'(\d+)\s*Bedroom'
                ]
                for pattern in bed_patterns:
                    bed_match = re.search(pattern, card_text, re.IGNORECASE)
                    if bed_match:
                        unit_details['beds'] = int(bed_match.group(1))
                        break
                
                # Check for Studio
                if unit_details['beds'] is None and ('studio' in card_text.lower() or 'bachelor' in card_text.lower()):
                    unit_details['beds'] = 0
                
                # Extract bathrooms
                bath_patterns = [
                    r'(\d+(?:\.\d+)?)\s*Bath',
                    r'(\d+(?:\.\d+)?)\s*BA'
                ]
                for pattern in bath_patterns:
                    bath_match = re.search(pattern, card_text, re.IGNORECASE)
                    if bath_match:
                        unit_details['baths'] = float(bath_match.group(1))
                        break
                
                # Extract square footage
                sqft_match = re.search(r'(\d+(?:,\d+)?)\s*(?:sq\.?\s*)?ft', card_text, re.IGNORECASE)
                if sqft_match:
                    sqft_str = sqft_match.group(1).replace(',', '')
                    unit_details['sqft'] = int(sqft_str)
                
                # Extract price
                price_match = re.search(r'\$\s*(\d+(?:,\d+)?)', card_text)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    unit_details['price'] = int(price_str)
                
                # Extract utilities
                utilities_keywords = ['heat', 'water', 'electricity', 'hydro', 'gas', 'internet', 'cable']
                for keyword in utilities_keywords:
                    if keyword in card_text.lower():
                        unit_details['utilities_included'].append(keyword)
                
                # Check if furnished
                if 'furnished' in card_text.lower():
                    if 'unfurnished' in card_text.lower():
                        unit_details['furnished'] = 'No'
                    else:
                        unit_details['furnished'] = 'Yes'
                
                units.append(unit_details)
                print(f"  [Thread {thread_id}]   ✓ Unit {idx}: {unit_details['unit_type']} - {unit_details['beds']} bed, ${unit_details['price']}")
                
            except Exception as e:
                print(f"  [Thread {thread_id}]   ⚠️  Error extracting unit {idx}: {e}")
                continue
        
        return units if units else None
        
    except Exception as e:
        print(f"  [Thread {thread_id}] ❌ Error extracting multi-unit details: {e}")
        return None

def extract_listing_details(driver, url, ref_id, thread_id):
    """Extract detailed information from a listing page"""
    start_time = time.time()
    
    try:
        if logger:
            logger.debug(f"[Thread {thread_id}] Starting extraction for {ref_id}: {url}")
        
        driver.get(url)
        
        if logger:
            logger.debug(f"[Thread {thread_id}] Page loaded in {time.time() - start_time:.2f}s")
        
        # Wait for Cloudflare challenge to pass (if present)
        # Use random delay between 3-7 seconds to appear more human-like
        cloudflare_wait = random.uniform(3, 7)
        time.sleep(cloudflare_wait)
        
        # Check if Cloudflare challenge is still present
        page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        if 'cloudflare' in page_text or 'verify you are human' in page_text:
            # Wait additional time for Cloudflare to resolve
            if logger:
                logger.debug(f"[Thread {thread_id}] Cloudflare detected, waiting extra 5-10 seconds...")
            time.sleep(random.uniform(5, 10))
        
        # Add small random delay between requests (human-like behavior)
        time.sleep(random.uniform(0.5, 1.5))
        
        # CHECK FOR MULTI-UNIT LISTING FIRST
        try:
            units_wrap = driver.find_element(By.CSS_SELECTOR, '.units-wrap')
            # Count how many unit cards exist
            unit_cards = driver.find_elements(By.CSS_SELECTOR, '.units-wrap > .card.block')
            if units_wrap and len(unit_cards) > 1:
                # True multi-unit building with multiple unit types
                print(f"  [Thread {thread_id}] 🏢 Multi-unit listing detected for {ref_id} ({len(unit_cards)} unit types)")
                return extract_multi_unit_details(driver, url, ref_id, thread_id)
        except:
            # Not a multi-unit listing, continue with single-unit extraction
            pass
        
        # Wait for content to load
        wait = WebDriverWait(driver, 10)
        
        details = {
            'ref_id': ref_id,
            'url': url,
            'scraped_at': datetime.now().isoformat(),
            'is_multi_unit': False,
            'beds': None,  # Add bedroom extraction
            'parking_spots': None,
            'furnished': None,
            'utilities_included': [],
            'amenities': [],
            'pet_deposit': None,
            'smoking_allowed': None,
            'appliances': [],
            'full_description': None,
            'building_type': None,
            'available_date': None,
            'lease_term': None,
        }
        
        # Get page text for analysis
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        page_source = driver.page_source
        
        # IMPROVED: Extract from Floor Plans section (most reliable)
        try:
            import re
            floor_plans = driver.find_elements(By.CSS_SELECTOR, '.units-wrap .card.block')
            if floor_plans:
                plan_text = floor_plans[0].text
                
                # Extract bedrooms
                bed_match = re.search(r'(\d+)\s*Bedroom', plan_text, re.IGNORECASE)
                if bed_match:
                    details['beds'] = int(bed_match.group(1))
                
                # Extract furnished status
                if 'Unfurnished' in plan_text:
                    details['furnished'] = 'Unfurnished'
                elif 'Furnished' in plan_text:
                    details['furnished'] = 'Furnished'
        except:
            pass
        
        # Fallback: Try to extract bedroom from page source if floor plans failed
        if details['beds'] is None:
            try:
                import re
                bed_match = re.search(r'(\d+)\s*(bedroom|bed|bd)', page_source, re.IGNORECASE)
                if bed_match:
                    details['beds'] = int(bed_match.group(1))
                elif 'bachelor' in page_source.lower() or 'studio' in page_source.lower():
                    details['beds'] = 0
            except:
                pass
        
        # IMPROVED: Extract utilities from specific section
        try:
            util_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'Utilities Included')]")
            util_parent = util_elem.find_element(By.XPATH, './parent::*')
            util_text = util_parent.text
            
            utilities = ['Heat', 'Water', 'Electricity', 'Hydro', 'Gas', 'Internet', 'Cable', 'Sewer']
            for util in utilities:
                if util in util_text:
                    details['utilities_included'].append(util)
        except:
            # Fallback to old method
            utilities_keywords = ['heat', 'water', 'electricity', 'hydro', 'gas', 'internet', 'cable']
            try:
                for keyword in utilities_keywords:
                    if keyword in page_text.lower() and ('included' in page_text.lower() or 'paid' in page_text.lower()):
                        details['utilities_included'].append(keyword.title())
            except:
                pass
        
        # IMPROVED: Extract parking from Parking Information section
        try:
            # Try to find parking spots
            park_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'Parking Spots') or contains(text(), 'parking spots')]")
            park_parent = park_elem.find_element(By.XPATH, './parent::*')
            park_text = park_parent.text
            
            import re
            spots_match = re.search(r'(\d+)\s*spot', park_text, re.IGNORECASE)
            if spots_match:
                details['parking_spots'] = int(spots_match.group(1))
        except:
            # Fallback to old method
            try:
                parking_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Parking') or contains(text(), 'parking')]")
                for elem in parking_elements:
                    text = elem.text
                    if 'parking' in text.lower():
                        import re
                        numbers = re.findall(r'\d+', text)
                        if numbers:
                            details['parking_spots'] = int(numbers[0])
                            break
            except:
                pass
        
        # Check if furnished (if not already set from floor plans)
        if details['furnished'] is None:
            try:
                if 'furnished' in page_text.lower():
                    if 'unfurnished' in page_text.lower():
                        details['furnished'] = 'Unfurnished'
                    else:
                        details['furnished'] = 'Furnished'
                else:
                    details['furnished'] = 'Unknown'
            except:
                details['furnished'] = 'Unknown'
        
        # NEW: Extract full description
        try:
            # Try to find the main description section
            desc_selectors = [
                '.listing-description',
                '.description',
                '[class*="description"]',
                '.property-description',
                '#description'
            ]
            
            for selector in desc_selectors:
                try:
                    desc_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    desc_text = desc_elem.text.strip()
                    if desc_text and len(desc_text) > 20:  # Must have substantial content
                        details['full_description'] = desc_text
                        break
                except:
                    continue
            
            # Fallback: Extract from page text between specific markers
            if not details['full_description']:
                # Look for common description patterns
                desc_patterns = [
                    r'Description[:\s]+(.+?)(?=Features|Amenities|Contact|$)',
                    r'About this property[:\s]+(.+?)(?=Features|Amenities|Contact|$)',
                ]
                for pattern in desc_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        desc = match.group(1).strip()
                        if len(desc) > 20:
                            details['full_description'] = desc[:1000]  # Limit to 1000 chars
                            break
        except:
            pass
        
        # IMPROVED: Better parking extraction from description and page text
        if not details['parking_spots']:
            try:
                # Get full page text for comprehensive search
                search_text = page_text.lower()
                
                # More comprehensive parking patterns (ordered by specificity)
                parking_patterns = [
                    r'(\d+)\s+spots?\s+per\s+unit',  # "2 spots per unit" (most specific)
                    r'parking\s+spots[:\s]+(\d+)\s+spot',  # "Parking Spots: 2 spots"
                    r'total\s+property\s+parking\s+spots[:\s]+(\d+)',  # "Total Property Parking Spots: 2"
                    r'(\d+)\s+parking\s+(?:spot|stall|space)s?',  # "2 parking spots"
                    r'(\d+)\s+(?:titled|underground|surface|assigned|reserved)\s+parking',  # "2 underground parking"
                    r'(?:two|three|four|five)\s+parking\s+stalls?',  # "Two parking stalls"
                    r'parking[:\s]+(\d+)',  # "Parking: 2"
                    r'(\d+)\s+stalls?\s+included',  # "2 stalls included"
                ]
                
                for pattern in parking_patterns:
                    match = re.search(pattern, search_text)
                    if match:
                        parking_num = int(match.group(1))
                        if 0 < parking_num < 100:  # Sanity check (exclude building totals like 800)
                            details['parking_spots'] = parking_num
                            if logger:
                                logger.debug(f"[Thread {thread_id}] Extracted {parking_num} parking spots using pattern: {pattern}")
                            break
                
                # Also try word-to-number conversion for spelled-out numbers
                if not details['parking_spots']:
                    word_numbers = {
                        'one': 1, 'two': 2, 'three': 3, 'four': 4, 
                        'five': 5, 'six': 6, 'seven': 7, 'eight': 8
                    }
                    for word, num in word_numbers.items():
                        if f'{word} parking' in search_text or f'{word} stall' in search_text:
                            details['parking_spots'] = num
                            break
            except:
                pass
        
        # IMPROVED: Extract amenities from Features & Amenities section
        try:
            feat_section = driver.find_element(By.XPATH, "//*[contains(text(), 'Features & Amenities')]")
            parent = feat_section.find_element(By.XPATH, './following-sibling::*')
            amenities_text = parent.text
            
            # Split by lines and filter
            lines = amenities_text.split('\n')
            for line in lines:
                line = line.strip()
                # Skip headers and add valid amenities
                if line and len(line) > 2 and len(line) < 50 and line not in ['Property', 'Building', 'Neighbourhood']:
                    # Skip numbers in parentheses like "Property (17)"
                    if not re.search(r'\(\d+\)$', line):
                        details['amenities'].append(line)
        except:
            # Fallback to keyword search
            try:
                amenity_keywords = [
                    'gym', 'fitness', 'pool', 'laundry', 'balcony', 'patio', 
                    'dishwasher', 'air conditioning', 'elevator', 'storage',
                    'bike room', 'concierge', 'security', 'guest suite'
                ]
                for keyword in amenity_keywords:
                    if keyword in page_text.lower():
                        details['amenities'].append(keyword.title())
            except:
                pass
        
        # Smoking allowed
        try:
            if 'no smoking' in page_text or 'non-smoking' in page_text:
                details['smoking_allowed'] = 'No'
            elif 'smoking allowed' in page_text:
                details['smoking_allowed'] = 'Yes'
        except:
            pass
        
        # Try to find building type
        try:
            building_keywords = ['apartment', 'condo', 'townhouse', 'house', 'duplex', 'basement']
            for keyword in building_keywords:
                if keyword in page_text:
                    details['building_type'] = keyword.title()
                    break
        except:
            pass
        
        if logger:
            logger.debug(f"[Thread {thread_id}] Successfully extracted details for {ref_id} in {time.time() - start_time:.2f}s")
        
        return details
        
    except Exception as e:
        print(f"  [Thread {thread_id}] ❌ Error scraping {ref_id}: {e}")
        
        # Log error details
        log_error_details(ref_id, thread_id, "extraction_error", e, url)
        
        # Save debug artifacts
        try:
            save_debug_screenshot(driver, ref_id, thread_id, "error")
            save_debug_html(driver, ref_id, thread_id, "error")
        except:
            pass
        
        return None

def scrape_listing_worker(listing, thread_id, headless):
    """Worker function for parallel scraping - DEPRECATED, use scrape_batch_worker instead"""
    driver = None
    try:
        driver = setup_driver(headless=headless)
        details = extract_listing_details(driver, listing['link'], listing['ref_id'], thread_id)
        
        if details:
            # Merge with original data
            merged = {**listing, **details}
            print(f"  [Thread {thread_id}] ✓ {listing['ref_id']} - Parking: {details['parking_spots']}, Furnished: {details['furnished']}, Amenities: {len(details['amenities'])}")
            return merged
        return None
        
    except Exception as e:
        print(f"  [Thread {thread_id}] ❌ Error: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def scrape_batch_worker(batch_data):
    """Worker function that processes a batch of listings with a single Chrome instance"""
    batch, worker_id, headless = batch_data
    driver = None
    results = []
    batch_start_time = time.time()
    
    with stats_lock:
        stats['active_workers'] += 1
    
    if logger:
        logger.info(f"[Worker {worker_id}] Starting batch of {len(batch)} listings")
    
    try:
        # Create ONE Chrome instance for this entire batch
        driver = setup_driver(headless=headless)
        
        if logger:
            logger.debug(f"[Worker {worker_id}] Chrome driver ready")
        
        for i, listing in enumerate(batch, 1):
            try:
                details = extract_listing_details(driver, listing['link'], listing['ref_id'], worker_id)
                
                if details:
                    # Check if multi-unit (returns list) or single-unit (returns dict)
                    if isinstance(details, list):
                        # Multi-unit listing: add each unit as a separate result
                        for unit in details:
                            merged = {**listing, **unit}
                            results.append(merged)
                        with stats_lock:
                            stats['completed'] += 1
                            stats['success'] += 1
                            stats['multi_unit_found'] = stats.get('multi_unit_found', 0) + 1
                            stats['total_units_found'] = stats.get('total_units_found', 0) + len(details)
                    else:
                        # Single-unit listing: merge with original data
                        merged = {**listing, **details}
                        results.append(merged)
                        with stats_lock:
                            stats['completed'] += 1
                            stats['success'] += 1
                else:
                    results.append(listing)  # Keep original data
                    with stats_lock:
                        stats['completed'] += 1
                        stats['failed'] += 1
                    
            except Exception as e:
                if logger:
                    logger.error(f"[Worker {worker_id}] Error processing listing {listing.get('ref_id', 'unknown')}: {e}")
                log_error_details(listing.get('ref_id', 'unknown'), worker_id, "listing_error", e, listing.get('link'))
                
                results.append(listing)  # Keep original data on error
                with stats_lock:
                    stats['completed'] += 1
                    stats['failed'] += 1
        
        batch_elapsed = time.time() - batch_start_time
        if logger:
            logger.info(f"[Worker {worker_id}] Batch complete in {batch_elapsed:.1f}s - {len(results)} results")
        
        return results
        
    except Exception as e:
        if logger:
            logger.error(f"[Worker {worker_id}] Fatal batch error: {e}")
            logger.error(traceback.format_exc())
        return [listing for listing in batch]  # Return original data on batch error
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                if logger:
                    logger.error(f"[Worker {worker_id}] Error closing driver: {e}")
        with stats_lock:
            stats['active_workers'] -= 1
            stats['batches_completed'] += 1

def print_debug_summary():
    """Print comprehensive debug summary"""
    print(f"\n{'='*80}")
    print(f"🐛 DEBUG SUMMARY")
    print(f"{'='*80}")
    
    with stats_lock:
        errors = stats.get('errors', [])
    
    if errors:
        print(f"\n⚠️  ERRORS ENCOUNTERED: {len(errors)}")
        print(f"{'='*80}")
        
        # Group errors by type
        error_types = {}
        for error in errors:
            error_type = error.get('error_type', 'unknown')
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(error)
        
        for error_type, type_errors in error_types.items():
            print(f"\n{error_type}: {len(type_errors)} occurrences")
            for i, error in enumerate(type_errors[:5], 1):  # Show first 5
                print(f"   {i}. {error['ref_id']} - {error['exception'][:100]}")
            if len(type_errors) > 5:
                print(f"   ... and {len(type_errors) - 5} more")
        
        # Save detailed error report
        try:
            debug_path = Path(DEBUG_DIR)
            debug_path.mkdir(exist_ok=True)
            
            error_report_file = debug_path / f"error_summary_{int(time.time())}.json"
            with open(error_report_file, 'w', encoding='utf-8') as f:
                json.dump(errors, f, indent=2)
            
            print(f"\n📝 Detailed error report saved: {error_report_file}")
        except Exception as e:
            print(f"\n⚠️  Failed to save error report: {e}")
    else:
        print("\n✅ No errors encountered!")
    
    print(f"\n📂 Debug files location: {DEBUG_DIR}/")
    try:
        debug_path = Path(DEBUG_DIR)
        if debug_path.exists():
            screenshots = list((debug_path / "screenshots").glob("*.png")) if (debug_path / "screenshots").exists() else []
            html_dumps = list((debug_path / "html_dumps").glob("*.html")) if (debug_path / "html_dumps").exists() else []
            error_files = list((debug_path / "errors").glob("*.json")) if (debug_path / "errors").exists() else []
            
            print(f"   Screenshots: {len(screenshots)}")
            print(f"   HTML dumps: {len(html_dumps)}")
            print(f"   Error logs: {len(error_files)}")
    except:
        pass
    
    print(f"{'='*80}\n")

def save_progress(data, filename='rentfaster_detailed_parallel.json'):
    """Thread-safe save progress to JSON file"""
    with file_lock:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def scrape_parallel(listings, num_workers=5, headless=True, batch_save=10):
    """Scrape listings in parallel using multiple workers with Chrome instance reuse"""
    detailed_listings = []
    total = len(listings)
    
    print(f"\n{'='*80}")
    print(f"⚙️  CONFIGURATION")
    print(f"{'='*80}")
    print(f"   Workers: {num_workers}")
    print(f"   Mode: {'Headless (background)' if headless else 'Visible browsers'}")
    print(f"   Batch save: every {batch_save} listings")
    print(f"   Total listings: {total}")
    
    # Split listings into batches (one batch per worker)
    print(f"\n📦 Creating batches...", end='', flush=True)
    batch_size = max(1, len(listings) // num_workers)
    batches = []
    for i in range(0, len(listings), batch_size):
        batch = listings[i:i + batch_size]
        worker_id = len(batches) + 1
        batches.append((batch, worker_id, headless))
    print(f" ✓")
    
    print(f"\n� BATCH DISTRIBUTION:")
    print(f"   Total listings: {total}")
    print(f"   Number of batches: {len(batches)}")
    print(f"   Listings per batch: ~{batch_size}")
    print(f"   Chrome instances: {len(batches)} (one per batch, reused within batch)")
    
    print(f"\n{'='*80}")
    print(f"🚀 STARTING PARALLEL SCRAPING")
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
            executor.submit(scrape_batch_worker, batch_data): batch_data 
            for batch_data in batches
        }
        
        # Status update thread
        stop_updates = threading.Event()
        
        def update_display():
            while not stop_updates.is_set():
                time.sleep(1)  # Update every second for steadier display
                print_live_status()
        
        update_thread = threading.Thread(target=update_display, daemon=True)
        update_thread.start()
        
        # Process completed batches
        for future in as_completed(future_to_batch):
            batch_results = future.result()
            detailed_listings.extend(batch_results)
            
            # Save progress periodically
            if len(detailed_listings) % batch_save == 0:
                save_progress(detailed_listings)
        
        # Stop status updates
        stop_updates.set()
        update_thread.join(timeout=1)
    
    # Final status display
    print_live_status()
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"✅ ALL BATCHES COMPLETE")
    print(f"{'='*80}")
    print(f"   Total listings processed: {len(detailed_listings)}")
    print(f"   Total time: {elapsed/60:.1f} minutes")
    print(f"   Average speed: {len(detailed_listings)/elapsed:.2f} listings/second")
    print(f"{'='*80}\n")
    
    return detailed_listings

def main():
    import sys
    
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("=" * 80)
        print("🚀 RentFaster PARALLEL Detailed Scraper")
        print("=" * 80)
        print("\nUSAGE:")
        print("  python3 scrape_details_parallel.py [num_listings] [num_workers] [headless] [force_rescrape]")
        print("\nPARAMETERS:")
        print("  num_listings    : Number of listings to scrape (default: all available)")
        print("  num_workers     : Number of parallel Chrome instances (default: 5)")
        print("                    Recommended: 5-10 depending on your machine")
        print("  headless        : Run browsers in background (default: true)")
        print("                    Options: true/false, yes/no, 1/0, headless/visible")
        print("  force_rescrape  : Re-scrape already scraped listings (default: false)")
        print("                    Options: true/false, yes/no, 1/0, force/skip")
        print("\nEXAMPLES:")
        print("  python3 scrape_details_parallel.py")
        print("    → Scrape REMAINING listings with 5 workers (headless)")
        print()
        print("  python3 scrape_details_parallel.py 50")
        print("    → Scrape 50 REMAINING listings with 5 workers (headless)")
        print()
        print("  python3 scrape_details_parallel.py 0 8")
        print("    → Scrape ALL REMAINING listings with 8 workers (headless)")
        print()
        print("  python3 scrape_details_parallel.py 0 8 true true")
        print("    → RE-SCRAPE ALL 7,000+ listings with 8 workers (force update)")
        print()
        print("  python3 scrape_details_parallel.py 50 10 false")
        print("    → Scrape 50 REMAINING listings with 10 workers (visible browsers)")
        print()
        print("  python3 scrape_details_parallel.py 100 5 true force")
        print("    → Re-scrape first 100 listings (force update existing data)")
        print("\nNOTES:")
        print("  • By default, already scraped listings are SKIPPED")
        print("  • Use force_rescrape=true to update existing data")
        print("  • Progress is saved periodically to prevent data loss")
        print("  • Use Ctrl+C to stop gracefully (progress will be saved)")
        print("  • Headless mode is recommended for faster performance")
        print("=" * 80)
        sys.exit(0)
    
    print("=" * 80)
    print("🚀 RentFaster PARALLEL Detailed Scraper")
    print("=" * 80)
    
    # Parse command line arguments
    # Usage: python3 scrape_details_parallel.py [num_listings] [num_workers] [headless]
    # Examples:
    #   python3 scrape_details_parallel.py           # Scrape all with 5 workers (headless)
    #   python3 scrape_details_parallel.py 50        # Scrape 50 listings with 5 workers
    #   python3 scrape_details_parallel.py 50 10     # Scrape 50 listings with 10 workers
    #   python3 scrape_details_parallel.py 50 10 false  # Scrape 50 with 10 workers (visible browsers)
    
    # Parameter 1: Number of listings to scrape (default: all, use 0 for all)
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            if limit == 0:
                limit = None  # 0 means "all"
            elif limit < 0:
                print(f"❌ Error: Number of listings must be positive (or 0 for all)")
                sys.exit(1)
        except ValueError:
            print(f"❌ Error: First parameter must be a number (listings to scrape)")
            print(f"   Usage: python3 scrape_details_parallel.py [num_listings] [num_workers] [headless]")
            print(f"   Try: python3 scrape_details_parallel.py --help")
            sys.exit(1)
    
    # Parameter 2: Number of parallel workers (default: 5)
    num_workers = 5
    if len(sys.argv) > 2:
        try:
            num_workers = int(sys.argv[2])
            if num_workers < 1:
                print(f"❌ Error: Number of workers must be at least 1")
                sys.exit(1)
            elif num_workers > 20:
                print(f"⚠️  Warning: {num_workers} workers may overload your system. Recommended: 5-10")
                print(f"   Continue anyway? (y/n): ", end='')
                response = input().lower()
                if response not in ['y', 'yes']:
                    print("   Cancelled.")
                    sys.exit(0)
        except ValueError:
            print(f"❌ Error: Second parameter must be a number (parallel workers)")
            print(f"   Usage: python3 scrape_details_parallel.py [num_listings] [num_workers] [headless]")
            print(f"   Try: python3 scrape_details_parallel.py --help")
            sys.exit(1)
    
    # Parameter 3: Headless mode (default: true)
    headless = True
    if len(sys.argv) > 3:
        headless_str = sys.argv[3].lower()
        if headless_str in ['false', 'no', '0', 'visible']:
            headless = False
        elif headless_str in ['true', 'yes', '1', 'headless']:
            headless = True
        else:
            print(f"⚠️  Warning: Third parameter should be 'true' or 'false'. Using headless=true")
    
    # Parameter 4: Force re-scrape (default: false - skip already scraped)
    force_rescrape = False
    if len(sys.argv) > 4:
        force_str = sys.argv[4].lower()
        if force_str in ['true', 'yes', '1', 'force']:
            force_rescrape = True
        elif force_str in ['false', 'no', '0', 'skip']:
            force_rescrape = False
        else:
            print(f"⚠️  Warning: Fourth parameter should be 'true' or 'false'. Using force_rescrape=false")
    
    # Load existing listings
    print("\n📂 Loading existing listings...")
    with open('rentfaster_listings.json', 'r', encoding='utf-8') as f:
        all_listings = json.load(f)
    
    print(f"   Loaded {len(all_listings):,} listings\n")
    
    # Check for existing detailed data
    try:
        with open('rentfaster_detailed_parallel.json', 'r', encoding='utf-8') as f:
            existing = json.load(f)
            
            if force_rescrape:
                # FIXED: Create backup and reset database when force re-scraping
                import shutil
                backup_file = f"rentfaster_detailed_parallel_backup_{int(time.time())}.json"
                shutil.copy('rentfaster_detailed_parallel.json', backup_file)
                print(f"📝 Found {len(existing)} previously scraped")
                print(f"   💾 Backup created: {backup_file}")
                print(f"   🔄 FORCE RE-SCRAPE MODE: Database will be REPLACED (not added to)\n")
                existing = []  # Clear existing data - start fresh!
            else:
                scraped_ids = {d['ref_id'] for d in existing}
                all_listings = [l for l in all_listings if l['ref_id'] not in scraped_ids]
                print(f"📝 Found {len(existing)} previously scraped")
                print(f"   {len(all_listings):,} remaining to scrape\n")
    except FileNotFoundError:
        existing = []
        print("📝 Starting fresh scrape\n")
    
    # Apply limit if specified
    if limit is not None:
        all_listings = all_listings[:limit]
        if force_rescrape:
            print(f"🧪 TEST MODE: Re-scraping first {limit} listings (force update)\n")
        else:
            print(f"🧪 TEST MODE: Limiting to {limit} remaining listings\n")
    
    print("=" * 80)
    print("⚙️  CONFIGURATION:")
    print("=" * 80)
    print(f"  Listings to scrape: {len(all_listings):,}")
    print(f"  Parallel workers:   {num_workers}")
    print(f"  Headless mode:      {headless}")
    print(f"  Force re-scrape:    {force_rescrape} {'(Update existing data)' if force_rescrape else '(Skip already scraped)'}")
    print(f"  Estimated time:     ~{len(all_listings) / (num_workers * 0.5) / 60:.1f} minutes")
    print("=" * 80)
    
    input("\nPress Enter to start (or Ctrl+C to cancel)...")
    
    try:
        # Run parallel scraping
        new_listings = scrape_parallel(all_listings, num_workers=num_workers, headless=headless)
        
        # Combine with existing
        print(f"\n{'='*80}")
        print(f"💾 SAVING FINAL RESULTS")
        print(f"{'='*80}")
        print(f"Combining with existing data...", end='', flush=True)
        all_detailed = existing + new_listings
        print(f" ✓ Total: {len(all_detailed)} listings")
        
        # Save final results
        print(f"Saving JSON...", end='', flush=True)
        save_progress(all_detailed)
        print(f" ✓")
        
        print(f"\n{'='*80}")
        print(f"✅ SCRAPING COMPLETE!")
        print(f"{'='*80}")
        print(f"   Total in database: {len(all_detailed):,}")
        print(f"   New this run: {len(new_listings):,}")
        print(f"   Previously scraped: {len(existing):,}")
        print(f"\n   📁 File saved:")
        print(f"      • rentfaster_detailed_parallel.json ({len(all_detailed)} listings)")
        print(f"{'='*80}\n")
        
        # Print debug summary if enabled
        if DEBUG_MODE:
            print_debug_summary()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        if new_listings:
            all_detailed = existing + new_listings
            save_progress(all_detailed)
            print(f"💾 Saved {len(all_detailed)} listings before exit")
        if DEBUG_MODE:
            print_debug_summary()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        if new_listings:
            all_detailed = existing + new_listings
            save_progress(all_detailed)
            print(f"💾 Saved {len(all_detailed)} listings before exit")

if __name__ == "__main__":
    main()
