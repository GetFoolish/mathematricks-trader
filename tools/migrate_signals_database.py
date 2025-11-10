#!/usr/bin/env python3
"""
Migrate trading_signals from mathematricks_signals → mathematricks_trading
Phase 7: MongoDB Consolidation
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')
mongo_uri = os.getenv('MONGODB_URI')
client = MongoClient(mongo_uri)

print('=' * 80)
print('PHASE 7: MONGODB CONSOLIDATION')
print('Migrate trading_signals: mathematricks_signals → mathematricks_trading')
print('=' * 80)

# Source and destination databases
source_db = client['mathematricks_signals']
dest_db = client['mathematricks_trading']

print('\n1. CHECKING SOURCE DATABASE:')
print('=' * 80)
signals_to_migrate = list(source_db.trading_signals.find())
print(f'   Found {len(signals_to_migrate)} signals in mathematricks_signals.trading_signals')

if len(signals_to_migrate) > 0:
    # Show sample signal
    sample = signals_to_migrate[0]
    print(f'\n   Sample signal:')
    print(f'      Signal ID: {sample.get("signalID")}')
    print(f'      Strategy: {sample.get("strategy_name")}')
    print(f'      Received: {sample.get("received_at")}')
    print(f'      Fields: {list(sample.keys())}')

print('\n2. CHECKING DESTINATION DATABASE:')
print('=' * 80)
existing_signals = dest_db.trading_signals.count_documents({})
print(f'   Existing signals in mathematricks_trading.trading_signals: {existing_signals}')

if existing_signals > 0:
    print(f'\n   ⚠️  WARNING: Destination collection already has {existing_signals} documents')
    print(f'   Migration will ADD {len(signals_to_migrate)} more documents')
    print(f'   Total after migration: {existing_signals + len(signals_to_migrate)} documents')
else:
    print(f'   ✅ Destination collection is empty - clean migration')

print('\n3. RUNNING MIGRATION:')
print('=' * 80)

if len(signals_to_migrate) > 0:
    # Insert signals into destination
    result = dest_db.trading_signals.insert_many(signals_to_migrate)
    print(f'   ✅ Migrated {len(result.inserted_ids)} signals to mathematricks_trading')

    # Verify migration
    final_count = dest_db.trading_signals.count_documents({})
    print(f'   ✅ Verified: mathematricks_trading.trading_signals now has {final_count} documents')
else:
    print('   ℹ️  No signals to migrate')

print('\n4. MIGRATION SUMMARY:')
print('=' * 80)
print(f'   Source: mathematricks_signals.trading_signals')
print(f'   Destination: mathematricks_trading.trading_signals')
print(f'   Migrated: {len(signals_to_migrate)} documents')
print(f'\n   ✅ MIGRATION COMPLETE')

print('\n5. NEXT STEPS:')
print('=' * 80)
print('   1. Update SignalIngestionService to use mathematricks_trading')
print('   2. Test signal ingestion with new database')
print('   3. Archive mathematricks_signals database (drop after 1 month of testing)')

print('\n' + '=' * 80)
