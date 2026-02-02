#!/usr/bin/env python3
"""
Migrate precision_cache.json to MongoDB

This script reads the existing file-based precision cache and migrates
it to the new MongoDB collection.
"""

import json
import os
import sys
from pymongo import MongoClient
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(PROJECT_ROOT, 'services', 'data', 'precision_cache.json')


def migrate_precision_cache():
    """Migrate file-based cache to MongoDB"""
    
    print("="*70)
    print("🔄 MIGRATING PRECISION CACHE TO MONGODB")
    print("="*70)
    
    # Check if file exists
    if not os.path.exists(CACHE_FILE):
        print(f"\n⚠️  Cache file not found: {CACHE_FILE}")
        print("   Nothing to migrate. This is OK if starting fresh.")
        return
    
    print(f"\n📄 Reading cache from: {CACHE_FILE}")
    
    # Read JSON file
    try:
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        print(f"✅ Loaded cache data for {len(cache_data)} sources")
    except Exception as e:
        print(f"❌ Failed to read cache file: {e}")
        sys.exit(1)
    
    # Connect to MongoDB
    print("\n🔌 Connecting to MongoDB...")
    try:
        # MongoDB in Docker is exposed on host port 27018
        # Don't use MONGO_URI env var - it points to internal docker hostname
        mongo_uri = 'mongodb://localhost:27018/'
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db = client['mathematricks_trading']
        collection = db['precision_cache']
        
        # Test connection
        client.admin.command('ping')
        print(f"✅ Connected to MongoDB at {mongo_uri}")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print(f"   Make sure MongoDB container is running on port 27018")
        sys.exit(1)
    
    # Migrate data
    print("\n📦 Migrating data...")
    count = 0
    errors = 0
    
    for source, symbols in cache_data.items():
        for symbol, data in symbols.items():
            try:
                # Parse timestamp
                last_checked_str = data['last_checked']
                if last_checked_str.endswith('Z'):
                    last_checked_str = last_checked_str[:-1] + '+00:00'
                last_checked = datetime.fromisoformat(last_checked_str)
                
                # Create document
                doc = {
                    'source': source,
                    'symbol': symbol,
                    'precision': data['precision'],
                    'last_checked': last_checked
                }
                
                # Upsert to MongoDB
                collection.update_one(
                    {'source': source, 'symbol': symbol},
                    {'$set': doc},
                    upsert=True
                )
                count += 1
                print(f"  ✓ Migrated {source}/{symbol} (precision: {data['precision']})")
                
            except Exception as e:
                print(f"  ✗ Failed to migrate {source}/{symbol}: {e}")
                errors += 1
    
    print(f"\n📊 Migration Summary:")
    print(f"   ✅ Successfully migrated: {count} entries")
    if errors > 0:
        print(f"   ❌ Errors: {errors}")
    
    # Verify migration
    print("\n🔍 Verifying migration...")
    db_count = collection.count_documents({})
    print(f"   MongoDB documents: {db_count}")
    
    if db_count == count:
        print("   ✅ Verification successful!")
    else:
        print(f"   ⚠️  Count mismatch (expected {count}, got {db_count})")
    
    # Show sample
    print("\n📝 Sample entries:")
    for doc in collection.find().limit(5):
        print(f"   {doc['source']}/{doc['symbol']}: precision={doc['precision']}")
    
    print("\n" + "="*70)
    print("✅ MIGRATION COMPLETE")
    print("="*70)
    print("\n💡 Next steps:")
    print("   1. Restart services to use new MongoDB cache")
    print("   2. Verify services work correctly")
    print("   3. Add services/data/precision_cache.json to .gitignore")
    print("   4. Optionally backup and remove the old cache file")
    print()


if __name__ == '__main__':
    try:
        migrate_precision_cache()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
