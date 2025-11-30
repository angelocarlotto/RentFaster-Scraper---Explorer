#!/usr/bin/env python3
"""
Display summary of RentFaster data with multi-unit support
"""

import json

def main():
    # Load data
    with open('rentfaster_detailed_parallel.json', 'r') as f:
        listings = json.load(f)
    
    # Count multi-unit buildings
    multi_unit_listings = [l for l in listings if l.get('is_multi_unit')]
    parent_ids = set(l.get('parent_ref_id') for l in multi_unit_listings if l.get('parent_ref_id'))
    single_unit_listings = [l for l in listings if not l.get('is_multi_unit') and not l.get('parent_ref_id')]
    
    # Get largest multi-unit building
    buildings = {}
    for listing in multi_unit_listings:
        parent_id = listing.get('parent_ref_id')
        if parent_id:
            if parent_id not in buildings:
                buildings[parent_id] = []
            buildings[parent_id].append(listing)
    
    largest_building = max(buildings.items(), key=lambda x: len(x[1])) if buildings else (None, [])
    
    print("=" * 80)
    print("🏢 RENTFASTER DATA SUMMARY")
    print("=" * 80)
    print()
    print(f"📊 Total Listings in Database: {len(listings):,}")
    print(f"   ├─ Single-unit listings: {len(single_unit_listings):,}")
    print(f"   ├─ Multi-unit buildings: {len(parent_ids):,}")
    print(f"   └─ Multi-unit types: {len(multi_unit_listings):,}")
    print()
    print(f"🏠 Unique Properties: {len(single_unit_listings) + len(parent_ids):,}")
    print(f"   (Single units + Multi-unit buildings)")
    print()
    print(f"📈 Extra Units Captured: {len(multi_unit_listings):,}")
    print(f"   (Would have been missed without multi-unit detection)")
    print()
    
    if largest_building[0]:
        print(f"🏆 Largest Multi-Unit Building:")
        print(f"   ID: {largest_building[0]}")
        print(f"   Unit Types: {len(largest_building[1])}")
        if largest_building[1]:
            sample = largest_building[1][0]
            print(f"   Address: {sample.get('address', 'N/A')}")
            print(f"   Community: {sample.get('community', 'N/A')}")
    print()
    
    # Price statistics
    prices = []
    for l in listings:
        price = l.get('price')
        if price and price != 'None':
            try:
                if '-' in str(price):
                    # Handle price ranges
                    parts = str(price).split('-')
                    avg_price = (float(parts[0].strip()) + float(parts[1].strip())) / 2
                    prices.append(avg_price)
                else:
                    prices.append(float(price))
            except:
                pass
    
    if prices:
        print(f"💰 Price Statistics:")
        print(f"   Min: ${min(prices):,.0f}")
        print(f"   Max: ${max(prices):,.0f}")
        print(f"   Avg: ${sum(prices)/len(prices):,.0f}")
        print()
    
    # Bedroom distribution
    bed_dist = {}
    for l in listings:
        beds = l.get('beds')
        if beds is not None:
            try:
                beds = int(float(beds))
                bed_dist[beds] = bed_dist.get(beds, 0) + 1
            except:
                pass
    
    if bed_dist:
        print(f"🛏️  Bedroom Distribution:")
        for beds, count in sorted(bed_dist.items()):
            print(f"   {beds} bed: {count:,} listings")
        print()
    
    print("=" * 80)
    print("🌐 WEB INTERFACE:")
    print("=" * 80)
    print()
    print("To view the data in your browser, run:")
    print()
    print("   python3 web_app.py")
    print()
    print("Then visit:")
    print("   • http://localhost:5001 - All listings")
    print("   • http://localhost:5001/multi-unit - Multi-unit buildings")
    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
