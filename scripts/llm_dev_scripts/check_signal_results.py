#!/usr/bin/env python3
"""Check the most recent signal processing results."""

from pymongo import MongoClient

client = MongoClient('localhost', 27017)
db = client['mathematricks_trading']

# Get the most recent signal
signal = db['signal_store'].find_one({}, sort=[('_id', -1)])

if signal:
    print('='*80)
    print('MOST RECENT SIGNAL')
    print('='*80)
    print(f"Signal ID: {signal.get('signal_id')}")
    print(f"Ticker: {signal.get('signal_legs', [{}])[0].get('instrument')}")
    print(f"Action: {signal.get('signal_legs', [{}])[0].get('action')}")
    print(f"Original Quantity: {signal.get('signal_legs', [{}])[0].get('quantity')}")
    print()
    
    # Check ENTRY leg
    if 'ENTRY' in signal:
        entry = signal['ENTRY']
        print('ENTRY Leg:')
        print(f"  Status: {entry.get('status')}")
        print(f"  Cerebro Quantity: {entry.get('cerebro_quantity')}")
        print(f"  Broker Qty: {entry.get('broker_quantity')}")
        print(f"  Allocated Capital: {entry.get('allocated_capital_available')}")
        print(f"  Broker Name: {entry.get('broker_name')}")
        print(f"  Broker Order ID: {entry.get('broker_order_id')}")
        
        if 'filled_orders' in entry:
            for order in entry['filled_orders']:
                print(f"  Filled: {order.get('filled_quantity')} @ {order.get('avg_fill_price')}")
        print()
    
    # Check EXIT leg
    if 'EXIT' in signal:
        exit_leg = signal['EXIT']
        print('EXIT Leg:')
        print(f"  Status: {exit_leg.get('status')}")
        print(f"  Cerebro Quantity: {exit_leg.get('cerebro_quantity')}")
        print(f"  Broker Qty: {exit_leg.get('broker_quantity')}")
        print(f"  Allocated Capital: {exit_leg.get('allocated_capital_available')}")
        print(f"  Broker Name: {exit_leg.get('broker_name')}")
        print(f"  Broker Order ID: {exit_leg.get('broker_order_id')}")
        
        if 'filled_orders' in exit_leg:
            for order in exit_leg['filled_orders']:
                print(f"  Filled: {order.get('filled_quantity')} @ {order.get('avg_fill_price')}")
else:
    print("No signals found in database")
