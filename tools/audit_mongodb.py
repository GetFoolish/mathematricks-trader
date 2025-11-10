#!/usr/bin/env python3
"""
Audit all MongoDB collections and identify data to clean up
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['mathematricks_trading']

print('=' * 80)
print('MONGODB COLLECTIONS AUDIT')
print('=' * 80)

collections = db.list_collection_names()
print(f'\nTotal Collections: {len(collections)}\n')

# Expected collections from Phase 6
expected_collections = [
    'account_hierarchy',      # Fund → Brokers → Accounts structure
    'fund_state',            # Aggregated fund metrics
    'account_state',         # Individual account snapshots
    'signals',               # Trading signals from SignalIngestionService
    'orders',                # Orders from CerebroService
    'order_confirmations',   # Execution confirmations
    'cerebro_decisions',     # Position sizing decisions
    'strategies',            # Strategy metadata
    'portfolio_equity',      # Portfolio equity time series
]

print('EXPECTED COLLECTIONS (Phase 6):')
for coll in expected_collections:
    status = '✅' if coll in collections else '❌'
    print(f'  {status} {coll}')
print()

print('ALL COLLECTIONS DETAILS:')
print('=' * 80)

cleanup_candidates = []

for coll_name in sorted(collections):
    coll = db[coll_name]
    count = coll.count_documents({})

    print(f'\n{coll_name}:')
    print(f'  Documents: {count}')

    if count > 0:
        # Get sample and latest documents
        sample = coll.find_one({})
        latest = coll.find_one({}, sort=[('timestamp', -1)]) or coll.find_one({}, sort=[('created_at', -1)])

        if sample:
            # Show relevant fields
            if '_id' in sample:
                print(f'  Sample ID: {sample["_id"]}')
            if 'timestamp' in sample:
                print(f'  Latest timestamp: {latest.get("timestamp") if latest else sample.get("timestamp")}')
            if 'created_at' in sample:
                print(f'  Latest created_at: {latest.get("created_at") if latest else sample.get("created_at")}')

        # Check if collection is NOT in expected list
        if coll_name not in expected_collections:
            cleanup_candidates.append({
                'collection': coll_name,
                'count': count,
                'reason': 'Not in Phase 6 expected collections'
            })

        # Check for old test data (older than 7 days)
        if 'timestamp' in sample:
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            old_docs = coll.count_documents({'timestamp': {'$lt': seven_days_ago}})
            if old_docs > 0:
                print(f'  ⚠️  Old documents (>7 days): {old_docs}')
                cleanup_candidates.append({
                    'collection': coll_name,
                    'count': old_docs,
                    'reason': f'Old test data (>7 days) in {coll_name}'
                })

print('\n' + '=' * 80)
print('CLEANUP CANDIDATES:')
print('=' * 80)

if cleanup_candidates:
    for candidate in cleanup_candidates:
        print(f'\n❌ {candidate["collection"]}')
        print(f'   Documents: {candidate["count"]}')
        print(f'   Reason: {candidate["reason"]}')
else:
    print('\n✅ No cleanup needed - all collections are expected and current')

print('\n' + '=' * 80)
