#!/usr/bin/env python3
"""
[STEP 4] RentFaster Web Explorer

Flask web application to explore rental listings with interactive filters.
Provides a user-friendly interface to browse and filter rental data.

Reads: rentfaster_detailed_offline.json
Serves: Web UI at http://localhost:5001
"""

from flask import Flask, render_template, jsonify, send_from_directory
import json
import os

# Get the parent directory (project root)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configure Flask to use parent directory for templates and static files
app = Flask(__name__, 
            template_folder=os.path.join(project_root, 'templates'),
            static_folder=os.path.join(project_root, 'static'))

# Load data - use offline scraped data only
data_dir = os.path.join(project_root, 'data')
LISTINGS_JSON = os.path.join(data_dir, 'rentfaster_detailed_offline.json') if os.path.exists(os.path.join(data_dir, 'rentfaster_detailed_offline.json')) else os.path.join(data_dir, 'rentfaster_listings.json')

# Cache for listings data with file modification time
_listings_cache = None
_cache_mtime = None

@app.route('/')
def index():
    """Main page - unified interface for all listings"""
    return render_template('index.html')

@app.route('/api/listings')
def get_listings():
    """API endpoint to get all listings - auto-reloads when file changes"""
    global _listings_cache, _cache_mtime
    
    try:
        # Check if file has been modified
        current_mtime = os.path.getmtime(LISTINGS_JSON)
        
        # Reload if cache is empty or file has changed
        if _listings_cache is None or _cache_mtime != current_mtime:
            print(f"📥 Reloading data from {LISTINGS_JSON}")
            with open(LISTINGS_JSON, 'r', encoding='utf-8') as f:
                listings = json.load(f)
            
            # Enrich with calculated fields
            enriched = []
            for listing in listings:
                enriched_listing = enrich_listing(listing)
                enriched.append(enriched_listing)
            
            _listings_cache = enriched
            _cache_mtime = current_mtime
            print(f"✓ Loaded {len(enriched):,} listings")
        
        return jsonify(_listings_cache)
    except Exception as e:
        print(f"Error loading listings: {e}")
        return jsonify({'error': str(e)}), 500



def parse_price(price_str):
    """Parse price string"""
    if not price_str or price_str == "Please Call":
        return None, None, None
    
    if '-' in str(price_str):
        parts = str(price_str).split('-')
        try:
            min_price = float(parts[0].strip())
            max_price = float(parts[1].strip())
            avg_price = (min_price + max_price) / 2
            return min_price, max_price, avg_price
        except:
            pass
    
    try:
        price = float(str(price_str).replace(',', ''))
        return price, price, price
    except:
        return None, None, None

def parse_sq_feet(sq_feet_str):
    """Parse square feet"""
    if not sq_feet_str:
        return None, None, None
    
    if ',' in str(sq_feet_str):
        try:
            values = [float(x.strip()) for x in str(sq_feet_str).split(',') if x.strip()]
            if values:
                return min(values), max(values), sum(values) / len(values)
        except:
            pass
    
    try:
        sq_ft = float(str(sq_feet_str).replace(',', ''))
        return sq_ft, sq_ft, sq_ft
    except:
        return None, None, None

def parse_beds(beds_str):
    """Parse bedroom count"""
    if not beds_str or beds_str == "Bachelor":
        return 0
    try:
        return float(str(beds_str))
    except:
        return None

def enrich_listing(listing):
    """Add calculated fields"""
    enriched = listing.copy()
    
    # Parse price (handle both detailed and basic listings)
    price_value = listing.get('price')
    price_min, price_max, price_avg = parse_price(price_value)
    enriched['price_min'] = price_min
    enriched['price_max'] = price_max
    enriched['price_avg'] = price_avg
    
    # Parse square feet (handle both 'sq_feet' and 'sqft' fields)
    sqft_value = listing.get('sq_feet') or listing.get('sqft')
    sqft_min, sqft_max, sqft_avg = parse_sq_feet(sqft_value)
    enriched['sqft_min'] = sqft_min
    enriched['sqft_max'] = sqft_max
    enriched['sqft_avg'] = sqft_avg
    
    # Parse beds (handle both fields)
    beds_value = listing.get('beds')
    if beds_value is None:
        beds_value = listing.get('bedroom')
    enriched['beds_num'] = parse_beds(beds_value)
    
    # Calculate cost per sqft
    if price_avg and sqft_avg and sqft_avg > 0:
        enriched['cost_per_sqft'] = round(price_avg / sqft_avg, 2)
    else:
        enriched['cost_per_sqft'] = None
    
    # Pet friendly (handle both formats)
    enriched['pet_friendly'] = listing.get('cats_allowed') or listing.get('dogs_allowed') or listing.get('pets_allowed')
    
    # Availability
    enriched['immediately_available'] = 'Yes' if listing.get('availability') == 'Immediate' else 'No'
    
    # Utilities info (new detailed fields)
    utilities = listing.get('utilities_included', [])
    enriched['utilities_count'] = len(utilities) if isinstance(utilities, list) else 0
    enriched['has_utilities'] = enriched['utilities_count'] > 0
    
    # Amenities count (new detailed fields)
    amenities = listing.get('amenities', [])
    enriched['amenities_count'] = len(amenities) if isinstance(amenities, list) else 0
    
    # Furnished status (new detailed fields)
    furnished = listing.get('furnished', 'Unknown')
    enriched['is_furnished'] = 'Yes' if furnished in ['Furnished', 'Yes'] else 'No' if furnished in ['Unfurnished', 'No'] else 'Unknown'
    
    # Parking (new detailed fields)
    parking = listing.get('parking_spots')
    enriched['has_parking'] = parking is not None and parking > 0
    enriched['parking_spots'] = parking if parking else 0
    
    # Fix link to include full URL
    link = listing.get('link', '')
    if link and not link.startswith('http'):
        enriched['link'] = f'https://www.rentfaster.ca{link}'
    
    return enriched

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/api/stats')
def get_stats():
    """Get summary statistics"""
    try:
        with open(LISTINGS_JSON, 'r', encoding='utf-8') as f:
            listings = json.load(f)
        
        enriched = [enrich_listing(l) for l in listings]
        
        immediate = [l for l in enriched if l.get('immediately_available') == 'Yes']
        prices = [l['price_avg'] for l in enriched if l.get('price_avg')]
        sizes = [l['sqft_avg'] for l in enriched if l.get('sqft_avg')]
        costs = [l['cost_per_sqft'] for l in enriched if l.get('cost_per_sqft') and l['cost_per_sqft'] < 100]
        
        stats = {
            'total': len(listings),
            'immediate': len(immediate),
            'avg_price': round(sum(prices) / len(prices)) if prices else 0,
            'avg_size': round(sum(sizes) / len(sizes)) if sizes else 0,
            'avg_cost': round(sum(costs) / len(costs), 2) if costs else 0,
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug')
def get_debug_info():
    """Get debug/diagnostic information about the dataset"""
    try:
        with open(LISTINGS_JSON, 'r', encoding='utf-8') as f:
            listings = json.load(f)
        
        # Data quality metrics
        total = len(listings)
        
        # Field completeness
        has_price = sum(1 for l in listings if l.get('price'))
        has_sqft = sum(1 for l in listings if l.get('sq_feet'))
        has_beds = sum(1 for l in listings if l.get('beds'))
        has_baths = sum(1 for l in listings if l.get('baths'))
        has_address = sum(1 for l in listings if l.get('address'))
        has_community = sum(1 for l in listings if l.get('community'))
        has_link = sum(1 for l in listings if l.get('link'))
        has_availability = sum(1 for l in listings if l.get('availability'))
        
        # Price analysis
        prices = []
        for l in listings:
            _, _, avg = parse_price(l.get('price'))
            if avg:
                prices.append(avg)
        
        # Size analysis
        sizes = []
        for l in listings:
            _, _, avg = parse_sq_feet(l.get('sq_feet'))
            if avg:
                sizes.append(avg)
        
        # Unique values
        unique_communities = len(set(l.get('community') for l in listings if l.get('community')))
        unique_cities = len(set(l.get('city') for l in listings if l.get('city')))
        
        # Availability breakdown
        immediate = sum(1 for l in listings if l.get('availability') == 'Immediate')
        
        # Pet friendly
        cats_ok = sum(1 for l in listings if l.get('cats_allowed'))
        dogs_ok = sum(1 for l in listings if l.get('dogs_allowed'))
        
        # New detailed fields coverage
        has_furnished = sum(1 for l in listings if l.get('furnished') and l.get('furnished') != 'Unknown')
        has_utilities = sum(1 for l in listings if l.get('utilities_included'))
        has_amenities = sum(1 for l in listings if l.get('amenities') and len(l.get('amenities', [])) > 0)
        has_parking = sum(1 for l in listings if l.get('parking_spots') is not None)
        has_building_type = sum(1 for l in listings if l.get('building_type'))
        has_smoking = sum(1 for l in listings if l.get('smoking_allowed'))
        
        # Furnished breakdown
        furnished_yes = sum(1 for l in listings if l.get('furnished') in ['Furnished', 'Yes'])
        furnished_no = sum(1 for l in listings if l.get('furnished') in ['Unfurnished', 'No'])
        
        # Utilities stats
        utilities_counts = [len(l.get('utilities_included', [])) for l in listings if l.get('utilities_included')]
        avg_utilities = round(sum(utilities_counts) / len(utilities_counts), 1) if utilities_counts else 0
        
        # Amenities stats  
        amenities_counts = [len(l.get('amenities', [])) for l in listings if l.get('amenities')]
        avg_amenities = round(sum(amenities_counts) / len(amenities_counts), 1) if amenities_counts else 0
        
        debug_info = {
            'dataset': {
                'total_entries': total,
                'data_source': LISTINGS_JSON,
                'file_size_mb': round(os.path.getsize(LISTINGS_JSON) / 1024 / 1024, 2)
            },
            'completeness': {
                'price': {'count': has_price, 'percent': round(has_price/total*100, 1)},
                'sqft': {'count': has_sqft, 'percent': round(has_sqft/total*100, 1)},
                'beds': {'count': has_beds, 'percent': round(has_beds/total*100, 1)},
                'baths': {'count': has_baths, 'percent': round(has_baths/total*100, 1)},
                'address': {'count': has_address, 'percent': round(has_address/total*100, 1)},
                'community': {'count': has_community, 'percent': round(has_community/total*100, 1)},
                'link': {'count': has_link, 'percent': round(has_link/total*100, 1)},
                'availability': {'count': has_availability, 'percent': round(has_availability/total*100, 1)}
            },
            'price_stats': {
                'count': len(prices),
                'min': round(min(prices)) if prices else None,
                'max': round(max(prices)) if prices else None,
                'avg': round(sum(prices)/len(prices)) if prices else None,
                'median': round(sorted(prices)[len(prices)//2]) if prices else None
            },
            'size_stats': {
                'count': len(sizes),
                'min': round(min(sizes)) if sizes else None,
                'max': round(max(sizes)) if sizes else None,
                'avg': round(sum(sizes)/len(sizes)) if sizes else None,
                'median': round(sorted(sizes)[len(sizes)//2]) if sizes else None
            },
            'location': {
                'unique_communities': unique_communities,
                'unique_cities': unique_cities
            },
            'availability': {
                'immediate': immediate,
                'immediate_percent': round(immediate/total*100, 1) if total > 0 else 0
            },
            'pets': {
                'cats_allowed': cats_ok,
                'dogs_allowed': dogs_ok,
                'cats_percent': round(cats_ok/total*100, 1) if total > 0 else 0,
                'dogs_percent': round(dogs_ok/total*100, 1) if total > 0 else 0
            },
            'detailed_fields': {
                'furnished': {
                    'count': has_furnished,
                    'percent': round(has_furnished/total*100, 1) if total > 0 else 0,
                    'furnished': furnished_yes,
                    'unfurnished': furnished_no
                },
                'utilities': {
                    'count': has_utilities,
                    'percent': round(has_utilities/total*100, 1) if total > 0 else 0,
                    'avg_per_listing': avg_utilities
                },
                'amenities': {
                    'count': has_amenities,
                    'percent': round(has_amenities/total*100, 1) if total > 0 else 0,
                    'avg_per_listing': avg_amenities
                },
                'parking': {
                    'count': has_parking,
                    'percent': round(has_parking/total*100, 1) if total > 0 else 0
                },
                'building_type': {
                    'count': has_building_type,
                    'percent': round(has_building_type/total*100, 1) if total > 0 else 0
                },
                'smoking': {
                    'count': has_smoking,
                    'percent': round(has_smoking/total*100, 1) if total > 0 else 0
                }
            }
        }
        
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 80)
    print("🌐 RentFaster Web Explorer Starting...")
    print("=" * 80)
    print(f"\n✓ Loading data from {LISTINGS_JSON}")
    
    if not os.path.exists(LISTINGS_JSON):
        print(f"\n❌ Error: {LISTINGS_JSON} not found!")
        print("Please run the scraping workflow first:")
        print("  1. download_raw_html_parallel.py - Download HTML files")
        print("  2. scrape_offline_parallel.py - Parse offline data")
        exit(1)
    
    with open(LISTINGS_JSON, 'r', encoding='utf-8') as f:
        listings_count = len(json.load(f))
    
    print(f"✓ Loaded {listings_count:,} listings")
    print("\n" + "=" * 80)
    print("🚀 Starting web server...")
    print("=" * 80)
    print("\n📱 Open your browser and visit:")
    print("\n   👉  http://localhost:5001")
    print("\n" + "=" * 80)
    print("Press CTRL+C to stop the server")
    print("=" * 80 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
