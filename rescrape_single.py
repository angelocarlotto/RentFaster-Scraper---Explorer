#!/usr/bin/env python3
"""
Re-scrape a single listing by ref_id and update it in the database
"""

import json
import sys
from scrape_details_parallel import setup_driver, extract_listing_details

def rescrape_listing(ref_id):
    """Re-scrape a listing and update it in the database"""
    
    # Load current database
    print(f"Loading database...")
    with open('rentfaster_detailed_parallel.json', 'r', encoding='utf-8') as f:
        listings = json.load(f)
    
    print(f"Total listings in database: {len(listings)}")
    
    # Find the listing
    target_listing = None
    target_index = None
    for i, listing in enumerate(listings):
        if str(listing.get('ref_id')) == str(ref_id):
            target_listing = listing
            target_index = i
            break
    
    if not target_listing:
        print(f"❌ Listing {ref_id} not found in database")
        return
    
    print(f"\n{'='*60}")
    print(f"Found listing: {ref_id}")
    print(f"  Title: {target_listing.get('title', 'N/A')}")
    print(f"  Link: {target_listing.get('link', 'N/A')}")
    print(f"{'='*60}\n")
    
    print("Current data:")
    print(f"  Beds: {target_listing.get('beds')}")
    print(f"  Parking: {target_listing.get('parking_spots')}")
    print(f"  Furnished: {target_listing.get('furnished')}")
    print(f"  Utilities: {target_listing.get('utilities_included')}")
    print(f"  Amenities: {len(target_listing.get('amenities', []))} items")
    
    # Re-scrape
    print(f"\n🔄 Re-scraping listing details...")
    driver = setup_driver(headless=False)  # Visible mode for debugging
    
    try:
        new_details = extract_listing_details(
            driver, 
            target_listing['link'], 
            target_listing['ref_id'], 
            thread_id=1
        )
        
        if new_details:
            # Handle multi-unit case
            if isinstance(new_details, list):
                print(f"\n⚠️  This is a multi-unit listing with {len(new_details)} units")
                print("Using first unit for comparison...")
                new_details = new_details[0]
            
            print(f"\n✅ Successfully scraped new details!")
            print(f"\nNew data:")
            print(f"  Beds: {new_details.get('beds')}")
            print(f"  Parking: {new_details.get('parking_spots')}")
            print(f"  Furnished: {new_details.get('furnished')}")
            print(f"  Utilities: {new_details.get('utilities_included')}")
            print(f"  Amenities: {len(new_details.get('amenities', []))} items")
            
            # Merge new details with original listing
            updated_listing = {**target_listing, **new_details}
            
            # Update in database
            listings[target_index] = updated_listing
            
            # Save back to file
            print(f"\n💾 Saving updated database...")
            with open('rentfaster_detailed_parallel.json', 'w', encoding='utf-8') as f:
                json.dump(listings, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Database updated successfully!")
            
            # Show comparison
            print(f"\n{'='*60}")
            print("COMPARISON:")
            print(f"{'='*60}")
            
            fields = ['beds', 'parking_spots', 'furnished']
            for field in fields:
                old = target_listing.get(field)
                new = updated_listing.get(field)
                status = "✅" if new != old else "  "
                print(f"{status} {field}: {old} → {new}")
            
            old_utils = target_listing.get('utilities_included', [])
            new_utils = updated_listing.get('utilities_included', [])
            if old_utils != new_utils:
                print(f"✅ utilities_included: {old_utils} → {new_utils}")
            
            old_amen = len(target_listing.get('amenities', []))
            new_amen = len(updated_listing.get('amenities', []))
            if old_amen != new_amen:
                print(f"✅ amenities count: {old_amen} → {new_amen}")
                print(f"   New amenities: {', '.join(updated_listing.get('amenities', [])[:10])}")
            
        else:
            print(f"❌ Failed to scrape new details")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ref_id = sys.argv[1]
    else:
        ref_id = "659073"  # Default to the listing we're investigating
    
    rescrape_listing(ref_id)
