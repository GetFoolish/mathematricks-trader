#!/usr/bin/env python3
"""
Detailed MongoDB signal verification script
Checks signal_store collection for execution and cerebro decision data
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env from project root
project_root = Path(__file__).parent.parent
load_dotenv(project_root / '.env')

mongo_uri = os.getenv('MONGODB_URI_CLOUD')
if not mongo_uri:
    print("❌ MONGODB_URI_CLOUD not found in .env")
    sys.exit(1)

client = MongoClient(mongo_uri)
db = client['mathematricks_trading']

# Get signals from test
signals = list(db.signal_store.find(
    {},
    {'signal_id': 1, 'instrument': 1, 'signal_legs': 1, 'created_at': 1}
).sort('created_at', -1).limit(10))

print(f"📊 Found {len(signals)} signals in MongoDB Atlas\n")
print("="*80)

total_legs = 0
filled_legs = 0
approved_legs = 0

for sig in signals:
    signal_id = sig.get('signal_id', 'N/A')
    instrument = sig.get('instrument', 'N/A')
    legs = sig.get('signal_legs', [])
    created = sig.get('created_at', 'N/A')
    
    print(f"\n✅ Signal: {signal_id}")
    print(f"   Instrument: {instrument}")
    print(f"   Created: {created}")
    print(f"   Legs: {len(legs)}")
    
    if not legs:
        print(f"   ⚠️  No signal_legs found!")
        continue
    
    for i, leg in enumerate(legs):
        total_legs += 1
        
        if not leg:
            print(f"      Leg {i}: ❌ NULL/MISSING")
            continue
            
        leg_type = leg.get('leg_type', 'UNKNOWN')
        
        # Get cerebro decision (not 'decision')
        cerebro = leg.get('cerebro') or {}
        decision_status = cerebro.get('status', 'UNKNOWN')
        created_orders = cerebro.get('created_orders', [])
        decision_action = created_orders[0].get('action') if created_orders else 'N/A'
        quantity = created_orders[0].get('quantity') if created_orders else 'N/A'
        
        if decision_status in ['APPROVED', 'EXECUTED']:
            approved_legs += 1
        
        # Get execution data
        execution = leg.get('execution') or {}
        exec_status = execution.get('status', 'UNKNOWN')
        qty_filled = execution.get('total_quantity_filled', 0)
        orders = execution.get('orders', [])
        
        if exec_status and exec_status.upper() == 'FILLED':
            filled_legs += 1
        
        # Print leg summary
        print(f"      Leg {i} ({leg_type}):")
        print(f"         Cerebro: {decision_action} | {decision_status} | Qty={quantity}")
        print(f"         Execution: {exec_status} | Filled={qty_filled}")
        
        # Print order details
        if orders:
            for order in orders:
                order_id = order.get('order_id', 'N/A')
                account = order.get('account_id', 'N/A')
                price = order.get('avg_fill_price', 'N/A')
                filled_at = order.get('filled_at', 'N/A')
                print(f"           Order: {order_id}")
                print(f"              Account: {account}")
                print(f"              Price: {price}")
                print(f"              Filled at: {filled_at}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Total signals: {len(signals)}")
print(f"Total legs: {total_legs}")
print(f"Approved legs: {approved_legs}")
print(f"Filled legs: {filled_legs}")
print()

if total_legs > 0:
    if filled_legs == total_legs:
        print("✅ ALL LEGS FILLED!")
    elif filled_legs > 0:
        print(f"⚠️  {filled_legs}/{total_legs} legs filled ({filled_legs/total_legs*100:.1f}%)")
    else:
        print("❌ NO LEGS FILLED - Check execution-service")
else:
    print("⚠️  No signal legs found")
