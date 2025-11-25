#!/usr/bin/env python3
"""
Check mathematricks_signals database
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')
client = MongoClient(os.getenv('MONGODB_URI'))

print('=' * 80)
print('MONGODB DATABASES CHECK')
print('=' * 80)

# List all databases
databases = client.list_database_names()
print(f'\nAll Databases: {databases}\n')

# Check mathematricks_signals
if 'mathematricks_signals' in databases:
    print('✅ mathematricks_signals database EXISTS')
    signals_db = client['mathematricks_signals']
    collections = signals_db.list_collection_names()

    print(f'\nCollections in mathematricks_signals: {len(collections)}')
    for coll_name in collections:
        count = signals_db[coll_name].count_documents({})
        print(f'   {coll_name}: {count} documents')

        if count > 0:
            sample = signals_db[coll_name].find_one({})
            print(f'      Sample fields: {list(sample.keys())}')
else:
    print('❌ mathematricks_signals database DOES NOT EXIST')

# Check mathematricks_trading
print('\n' + '=' * 80)
if 'mathematricks_trading' in databases:
    print('✅ mathematricks_trading database EXISTS')
    trading_db = client['mathematricks_trading']
    collections = trading_db.list_collection_names()

    print(f'\nCollections in mathematricks_trading: {len(collections)}')
    for coll_name in collections:
        count = trading_db[coll_name].count_documents({})
        print(f'   {coll_name}: {count} documents')
else:
    print('❌ mathematricks_trading database DOES NOT EXIST')

print('\n' + '=' * 80)
