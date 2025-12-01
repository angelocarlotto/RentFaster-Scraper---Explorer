#!/bin/bash
# Quick script to check fetch progress

echo "🔍 Checking fetch progress..."
echo ""

# Check if fetch is running
if pgrep -f "fetch_listings_multi_city.py" > /dev/null; then
    echo "✅ Fetch is running"
    echo ""
    
    # Show recent log output
    if [ -f "fetch_all_cities_"*.log ]; then
        echo "📋 Recent progress:"
        tail -20 fetch_all_cities_*.log 2>/dev/null | grep -E "Page|Fetching|Total|Summary" | tail -10
    fi
else
    echo "⏸️  Fetch is not running"
fi

echo ""
echo "📊 Current listings file:"
if [ -f "rentfaster_listings.json" ]; then
    python3 -c "
import json
with open('rentfaster_listings.json') as f:
    listings = json.load(f)
    by_city = {}
    for listing in listings:
        city = listing.get('city_code', 'unknown')
        by_city[city] = by_city.get(city, 0) + 1
    
    print(f'   Total listings: {len(listings):,}')
    print(f'   Cities: {len(by_city)}')
    print()
    print('   By city:')
    for city in sorted(by_city.keys()):
        print(f'      {city:15s}: {by_city[city]:,}')
"
else
    echo "   File not found"
fi
