#!/usr/bin/env python3
"""
Clean up MongoDB collections
- Remove collections not needed for Phase 6+
- Clean old test data (>7 days) from current collections
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['mathematricks_trading']

print('=' * 80)
print('MONGODB CLEANUP')
print('=' * 80)

# Collections to DROP entirely (not needed for Phase 6+)
DROP_COLLECTIONS = [
    'current_allocation',          # Old - replaced by portfolio_builder API
    'dashboard_snapshots',         # Old - frontend will query APIs directly
    'execution_confirmations',     # Old name - now using order_confirmations
    'open_positions',             # Old - AccountDataService tracks this now
    'portfolio_tests',            # Test data
    'strategy_metadata_cache',    # Old cache - strategies collection is source of truth
]

# Collections to CLEAN (remove old data >7 days)
CLEAN_OLD_DATA = [
    'account_state',
    'cerebro_decisions',
    'trading_orders',
]

print('\n1. DROPPING UNNECESSARY COLLECTIONS:')
print('=' * 80)
for coll_name in DROP_COLLECTIONS:
    if coll_name in db.list_collection_names():
        count = db[coll_name].count_documents({})
        db[coll_name].drop()
        print(f'   ✅ Dropped {coll_name} ({count} documents)')
    else:
        print(f'   ⏭️  {coll_name} (already removed)')

print('\n2. CLEANING OLD DATA (>7 days):')
print('=' * 80)
seven_days_ago = datetime.utcnow() - timedelta(days=7)

for coll_name in CLEAN_OLD_DATA:
    if coll_name not in db.list_collection_names():
        print(f'   ⏭️  {coll_name} (collection not found)')
        continue

    coll = db[coll_name]

    # Count old documents
    old_count = coll.count_documents({'timestamp': {'$lt': seven_days_ago}})

    if old_count > 0:
        # Delete old documents
        result = coll.delete_many({'timestamp': {'$lt': seven_days_ago}})
        print(f'   ✅ Cleaned {coll_name}: removed {result.deleted_count} old documents')
    else:
        print(f'   ✅ {coll_name}: no old data to clean')

print('\n3. FINAL COLLECTION STATUS:')
print('=' * 80)

collections = db.list_collection_names()
print(f'\nRemaining Collections: {len(collections)}\n')

for coll_name in sorted(collections):
    count = db[coll_name].count_documents({})
    print(f'   {coll_name}: {count} documents')

print('\n' + '=' * 80)
print('✅ CLEANUP COMPLETE')
print('=' * 80)
