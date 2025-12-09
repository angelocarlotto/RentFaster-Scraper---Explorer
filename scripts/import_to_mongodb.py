#!/usr/bin/env python3
"""
Import RentFaster data to MongoDB

Reads JSON data from the data/ directory and imports it into MongoDB.
Handles both rentfaster_detailed_offline.json and rentfaster_listings.json
"""

import json
import os
from pathlib import Path
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError
from datetime import datetime

# MongoDB connection string
MONGO_URI = "mongodb://root:fcHIctV8xDjncLMR0cwCzu6oDfHyhNqCPj2S@10.0.0.123:27023/?directConnection=true"

# Database and collection names
DB_NAME = "rentfaster"
COLLECTION_DETAILED = "listings_detailed"
COLLECTION_BASIC = "listings_basic"

# Data directory
DATA_DIR = Path("data")

def connect_to_mongodb():
    """Connect to MongoDB and return client and database"""
    print("=" * 80)
    print("🔌 Connecting to MongoDB...")
    print("=" * 80)
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        client.admin.command('ping')
        print("✅ Connected successfully!")
        db = client[DB_NAME]
        return client, db
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise

def load_json_file(file_path):
    """Load JSON data from file"""
    print(f"\n📂 Loading {file_path.name}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✓ Loaded {len(data):,} records")
        return data
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return None

def prepare_document(listing):
    """Prepare listing document for MongoDB"""
    doc = listing.copy()
    
    # Add metadata
    doc['_imported_at'] = datetime.utcnow()
    
    # Use ref_id as the unique identifier
    if 'ref_id' in doc:
        doc['_id'] = doc['ref_id']
    
    return doc

def import_to_collection(db, collection_name, data, description):
    """Import data to MongoDB collection using upsert"""
    print(f"\n{'=' * 80}")
    print(f"📥 Importing to collection: {collection_name}")
    print(f"   Description: {description}")
    print(f"{'=' * 80}")
    
    collection = db[collection_name]
    
    # Get initial count
    initial_count = collection.count_documents({})
    print(f"   Current documents in collection: {initial_count:,}")
    
    # Prepare bulk operations (upsert based on _id/ref_id)
    print(f"   Preparing {len(data):,} documents...")
    operations = []
    
    for listing in data:
        doc = prepare_document(listing)
        
        # Upsert operation: update if exists, insert if not
        operations.append(
            UpdateOne(
                {'_id': doc['_id']},
                {'$set': doc},
                upsert=True
            )
        )
    
    # Execute bulk write in batches
    batch_size = 1000
    total_inserted = 0
    total_updated = 0
    total_errors = 0
    
    print(f"   Executing bulk write in batches of {batch_size}...")
    
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(operations) + batch_size - 1) // batch_size
        
        try:
            result = collection.bulk_write(batch, ordered=False)
            total_inserted += result.upserted_count
            total_updated += result.modified_count
            
            print(f"   Batch {batch_num}/{total_batches}: "
                  f"✓ {result.upserted_count} inserted, "
                  f"{result.modified_count} updated")
        except BulkWriteError as e:
            total_errors += len(e.details.get('writeErrors', []))
            print(f"   Batch {batch_num}/{total_batches}: "
                  f"⚠️  {len(e.details.get('writeErrors', []))} errors")
            # Continue with next batch
    
    # Get final count
    final_count = collection.count_documents({})
    
    print(f"\n{'=' * 80}")
    print(f"✅ IMPORT COMPLETE - {collection_name}")
    print(f"{'=' * 80}")
    print(f"   📊 Statistics:")
    print(f"      • Documents before: {initial_count:,}")
    print(f"      • Documents after:  {final_count:,}")
    print(f"      • New inserts:      {total_inserted:,}")
    print(f"      • Updates:          {total_updated:,}")
    if total_errors > 0:
        print(f"      • Errors:           {total_errors:,}")
    print(f"{'=' * 80}\n")
    
    return {
        'initial': initial_count,
        'final': final_count,
        'inserted': total_inserted,
        'updated': total_updated,
        'errors': total_errors
    }

def create_indexes(db):
    """Create indexes for better query performance"""
    print(f"\n{'=' * 80}")
    print("🔍 Creating indexes...")
    print(f"{'=' * 80}")
    
    # Indexes for detailed collection
    detailed = db[COLLECTION_DETAILED]
    print(f"\n   Collection: {COLLECTION_DETAILED}")
    
    indexes = [
        ('city', 'City index'),
        ('price', 'Price index'),
        ('beds', 'Beds index'),
        ('type', 'Property type index'),
        ([('latitude', 1), ('longitude', 1)], 'Location index'),
    ]
    
    for idx_spec, description in indexes:
        try:
            if isinstance(idx_spec, list):
                detailed.create_index(idx_spec)
            else:
                detailed.create_index(idx_spec)
            print(f"      ✓ {description}")
        except Exception as e:
            print(f"      ⚠️  {description}: {e}")
    
    # Indexes for basic collection
    basic = db[COLLECTION_BASIC]
    print(f"\n   Collection: {COLLECTION_BASIC}")
    
    for idx_spec, description in indexes[:4]:  # Skip location for basic
        try:
            if isinstance(idx_spec, list):
                basic.create_index(idx_spec)
            else:
                basic.create_index(idx_spec)
            print(f"      ✓ {description}")
        except Exception as e:
            print(f"      ⚠️  {description}: {e}")
    
    print(f"\n{'=' * 80}\n")

def main():
    """Main import function"""
    print("\n" + "=" * 80)
    print("🚀 RentFaster MongoDB Importer")
    print("=" * 80)
    
    # Check if data directory exists
    if not DATA_DIR.exists():
        print(f"\n❌ Error: Data directory '{DATA_DIR}' not found!")
        return
    
    # Connect to MongoDB
    try:
        client, db = connect_to_mongodb()
    except Exception as e:
        print(f"\n❌ Failed to connect to MongoDB. Exiting.")
        return
    
    total_stats = {
        'collections': 0,
        'total_inserted': 0,
        'total_updated': 0,
        'total_errors': 0
    }
    
    # Import detailed listings (offline scraped data)
    detailed_file = DATA_DIR / "rentfaster_detailed_offline.json"
    if detailed_file.exists():
        data = load_json_file(detailed_file)
        if data:
            stats = import_to_collection(
                db, 
                COLLECTION_DETAILED, 
                data,
                "Detailed listings with full HTML scraping"
            )
            total_stats['collections'] += 1
            total_stats['total_inserted'] += stats['inserted']
            total_stats['total_updated'] += stats['updated']
            total_stats['total_errors'] += stats['errors']
    else:
        print(f"\n⚠️  File not found: {detailed_file}")
    
    # Import basic listings (initial fetch data)
    basic_file = DATA_DIR / "rentfaster_listings.json"
    if basic_file.exists():
        data = load_json_file(basic_file)
        if data:
            stats = import_to_collection(
                db, 
                COLLECTION_BASIC, 
                data,
                "Basic listings from initial fetch"
            )
            total_stats['collections'] += 1
            total_stats['total_inserted'] += stats['inserted']
            total_stats['total_updated'] += stats['updated']
            total_stats['total_errors'] += stats['errors']
    else:
        print(f"\n⚠️  File not found: {basic_file}")
    
    # Create indexes
    if total_stats['collections'] > 0:
        create_indexes(db)
    
    # Print final summary
    print("=" * 80)
    print("🎉 IMPORT SUMMARY")
    print("=" * 80)
    print(f"   Collections processed: {total_stats['collections']}")
    print(f"   Total new inserts:     {total_stats['total_inserted']:,}")
    print(f"   Total updates:         {total_stats['total_updated']:,}")
    if total_stats['total_errors'] > 0:
        print(f"   Total errors:          {total_stats['total_errors']:,}")
    print("=" * 80)
    print(f"\n✅ All data imported to database: {DB_NAME}")
    print(f"   • Collection: {COLLECTION_DETAILED}")
    print(f"   • Collection: {COLLECTION_BASIC}")
    print("=" * 80 + "\n")
    
    # Close connection
    client.close()
    print("🔌 MongoDB connection closed.\n")

if __name__ == "__main__":
    main()
