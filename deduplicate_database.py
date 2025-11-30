#!/usr/bin/env python3
"""
Deduplicate rentfaster_detailed_offline.json
Keeps only the MOST RECENT version of each ref_id
"""

import json
from datetime import datetime

def deduplicate_database():
    print("=" * 80)
    print("🧹 DATABASE DEDUPLICATION")
    print("=" * 80)
    
    # Load database
    print("\n📂 Loading database...")
    with open('rentfaster_detailed_offline.json', 'r') as f:
        all_data = json.load(f)
    
    print(f"   Total entries: {len(all_data):,}")
    
    # Group by ref_id
    print("\n📊 Analyzing duplicates...")
    grouped = {}
    for entry in all_data:
        ref_id = entry.get('ref_id')
        if ref_id not in grouped:
            grouped[ref_id] = []
        grouped[ref_id].append(entry)
    
    # Count duplicates
    duplicates = {ref_id: entries for ref_id, entries in grouped.items() if len(entries) > 1}
    print(f"   Unique ref_ids: {len(grouped):,}")
    print(f"   Duplicated ref_ids: {len(duplicates):,}")
    
    if duplicates:
        print(f"\n   Top 10 most duplicated:")
        sorted_dups = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        for ref_id, entries in sorted_dups:
            print(f"      {ref_id}: {len(entries)} copies")
    
    # Keep only most recent for each ref_id
    print(f"\n🔄 Deduplicating...")
    deduplicated = []
    removed = 0
    
    for ref_id, entries in grouped.items():
        if len(entries) == 1:
            # No duplicates, keep as is
            deduplicated.append(entries[0])
        else:
            # Multiple entries, keep most recent
            # Sort by scraped_at (most recent first)
            sorted_entries = sorted(entries, key=lambda x: x.get('scraped_at', ''), reverse=True)
            most_recent = sorted_entries[0]
            deduplicated.append(most_recent)
            removed += len(entries) - 1
            
            # Debug: show what we're keeping
            if len(entries) > 2:  # Only show significant duplicates
                print(f"      {ref_id}: Keeping {most_recent.get('scraped_at', 'Unknown')[:19]} (removed {len(entries)-1} older)")
    
    print(f"\n   Entries removed: {removed:,}")
    print(f"   Final count: {len(deduplicated):,}")
    
    # Save deduplicated (backup disabled)
    print(f"\n💾 Saving deduplicated database...")
    with open('rentfaster_detailed_offline.json', 'w', encoding='utf-8') as f:
        json.dump(deduplicated, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✅ DEDUPLICATION COMPLETE!")
    print(f"{'='*80}")
    print(f"   Original: {len(all_data):,} entries")
    print(f"   Removed:  {removed:,} duplicates")
    print(f"   Final:    {len(deduplicated):,} unique entries")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    deduplicate_database()
