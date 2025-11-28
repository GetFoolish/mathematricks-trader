#!/usr/bin/env python3
"""
Quick test to send a signal and verify it executes
"""
import subprocess
import time
import sys
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

print('=' * 80)
print('TESTING SIGNAL EXECUTION END-TO-END')
print('=' * 80)

# Step 1: Send ENTRY signal
print('\n🔵 Step 1: Sending ENTRY signal...')
result = subprocess.run([
    'python3',
    'services/signal_ingestion/send_test_signal.py',
    '@services/signal_ingestion/sample_signals/equity_simple_signal_1.json'
], capture_output=True, text=True, cwd='/home/dazz/PROJECT/reddit/hfund/mathematricks-trader')

if result.returncode != 0:
    print(f'❌ Failed to send signal: {result.stderr}')
    sys.exit(1)

print('✅ Signal sent successfully')

# Step 2: Wait and check for position
print('\n⏳ Step 2: Waiting 10 seconds for signal to process...')
time.sleep(10)

# Step 3: Check database
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['mathematricks_trading']

# Check trading_orders
orders = list(db.trading_orders.find({}).sort('timestamp', -1).limit(1))
print(f'\n📋 Trading orders: {len(orders)}')
if orders:
    order = orders[0]
    print(f'   Latest order: {order.get("order_id")} | {order.get("instrument")} | {order.get("status")}')

# Check open_positions
account = db.trading_accounts.find_one({'account_id': 'Mock_Paper'})
if account:
    positions = account.get('open_positions', [])
    print(f'\n📊 Open positions: {len(positions)}')
    for pos in positions:
        print(f'   {pos.get("strategy_id")}/{pos.get("instrument")}: {pos.get("quantity")} @ ${pos.get("avg_entry_price"):.2f}')
else:
    print('\n⚠️  No account found')

# Check signal_store
signal_store = list(db.signal_store.find({}).sort('created_at', -1).limit(1))
if signal_store:
    sig = signal_store[0]
    print(f'\n📡 Latest signal_store:')
    print(f'   Signal ID: {sig.get("signal_id")}')
    print(f'   Cerebro decision: {sig.get("cerebro_decision", {}).get("decision", "N/A")}')
    print(f'   Position status: {sig.get("position_status", "N/A")}')

print('\n' + '=' * 80)
if len(orders) > 0 and len(positions) > 0:
    print('✅ SUCCESS! Signal was processed and position created!')
elif len(orders) > 0:
    print('⚠️  Order created but position not found (check execution_service logs)')
else:
    print('❌ FAILED! No orders created (check cerebro_service logs)')
print('=' * 80)
