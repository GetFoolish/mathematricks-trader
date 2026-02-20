#!/usr/bin/env python3
import pymongo
from pprint import pprint
import json

# Connect to MongoDB Atlas
client = pymongo.MongoClient('mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_trading')
db = client['mathematricks_trading']
collection = db['signal_store']

# Query for the specific signal
signal_id = 'AUDCAD_1771524420422_6po2m41jj'
signal = collection.find_one({'signal_id': signal_id})

if signal:
    print('=== FULL DOCUMENT STRUCTURE ===')
    print(json.dumps(signal, indent=2, default=str))
    print('\n\n=== KEY OBSERVATIONS ===')
    
    # Check for signal_status at top level
    if 'signal_status' in signal:
        print(f'✓ Top-level signal_status found: {signal["signal_status"]}')
    else:
        print('✗ No top-level signal_status field')
    
    # Check legs array
    if 'legs' in signal:
        print(f'\n✓ Legs array exists with {len(signal["legs"])} leg(s)')
        for i, leg in enumerate(signal['legs']):
            print(f'\n  Leg {i+1} keys: {list(leg.keys())}')
            if 'cerebro' in leg:
                print(f'  - Has cerebro field')
                if isinstance(leg['cerebro'], dict):
                    print(f'    cerebro keys: {list(leg["cerebro"].keys())}')
            if 'decision' in leg:
                print(f'  - Has decision field: {leg["decision"]}')
            if 'execution_status' in leg:
                print(f'  - Has execution_status: {leg["execution_status"]}')
            if 'status' in leg:
                print(f'  - Has status: {leg["status"]}')
    else:
        print('✗ No legs array found')
    
    # List all top-level status-related fields
    status_fields = [k for k in signal.keys() if 'status' in k.lower()]
    if status_fields:
        print(f'\n✓ Status-related fields at top level: {status_fields}')
else:
    print(f'Signal not found: {signal_id}')

client.close()
