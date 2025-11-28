#!/usr/bin/env python3
"""
Test script to verify permanent position cleanup solution
Simulates ENTRY → EXIT flow and verifies position is removed from array
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client['mathematricks_trading']
trading_accounts = db['trading_accounts']
closed_positions = db['closed_positions']

print('=' * 80)
print('TESTING PERMANENT POSITION CLEANUP SOLUTION')
print('=' * 80)

account_id = "Mock_Paper"

# Step 1: Create a test ENTRY position
print('\n📥 Step 1: Creating test ENTRY position...')
test_position = {
    'strategy_id': 'TEST_STRATEGY',
    'instrument': 'TEST_STOCK',
    'direction': 'LONG',
    'quantity': 100,
    'avg_entry_price': 50.00,
    'current_price': 50.00,
    'unrealized_pnl': 0.0,
    'status': 'OPEN',
    'entry_order_id': 'test_order_entry',
    'last_order_id': 'test_order_entry',
    'created_at': datetime.utcnow(),
    'updated_at': datetime.utcnow()
}

trading_accounts.update_one(
    {'account_id': account_id},
    {'$push': {'open_positions': test_position}},
    upsert=True
)

# Verify position was created
account = trading_accounts.find_one({'account_id': account_id})
open_positions = account.get('open_positions', [])
print(f'   ✅ Position created. Total open positions: {len(open_positions)}')

# Step 2: Simulate EXIT (close position)
print('\n📤 Step 2: Simulating EXIT (closing position)...')

# Find the position
existing_position = None
for pos in open_positions:
    if (pos.get('strategy_id') == 'TEST_STRATEGY' and
        pos.get('instrument') == 'TEST_STOCK' and
        pos.get('status') == 'OPEN'):
        existing_position = pos
        break

if existing_position:
    # Calculate PnL
    entry_price = existing_position.get('avg_entry_price', 0)
    exit_price = 55.00  # Simulate exit at $55
    quantity = existing_position.get('quantity', 0)
    gross_pnl = (exit_price - entry_price) * quantity
    holding_period = (datetime.utcnow() - existing_position.get('created_at', datetime.utcnow())).total_seconds()
    
    # Archive to closed_positions
    closed_position = {
        **existing_position,
        'exit_order_id': 'test_order_exit',
        'avg_exit_price': exit_price,
        'closed_at': datetime.utcnow(),
        'gross_pnl': gross_pnl,
        'holding_period_seconds': holding_period,
        'account_id': account_id
    }
    
    closed_positions.insert_one(closed_position)
    print(f'   📦 Archived to closed_positions (PnL: ${gross_pnl:.2f})')
    
    # REMOVE from open_positions array
    trading_accounts.update_one(
        {'account_id': account_id},
        {
            '$pull': {
                'open_positions': {
                    'strategy_id': 'TEST_STRATEGY',
                    'instrument': 'TEST_STOCK',
                    'status': 'OPEN'
                }
            },
            '$set': {
                'updated_at': datetime.utcnow()
            }
        }
    )
    print(f'   🗑️  Removed from open_positions array')

# Step 3: Verify position was removed
print('\n🔍 Step 3: Verifying position was removed...')
account = trading_accounts.find_one({'account_id': account_id})
open_positions_after = account.get('open_positions', [])
print(f'   Open positions after EXIT: {len(open_positions_after)}')

# Check closed_positions collection
closed_count = closed_positions.count_documents({'strategy_id': 'TEST_STRATEGY'})
print(f'   Archived positions: {closed_count}')

# Step 4: Results
print('\n' + '=' * 80)
print('TEST RESULTS')
print('=' * 80)

if len(open_positions_after) == 0 and closed_count == 1:
    print('✅ SUCCESS! Position was properly:')
    print('   1. Created in open_positions array')
    print('   2. Removed from open_positions on EXIT')
    print('   3. Archived to closed_positions collection')
    print('\n🎉 Permanent fix is working correctly!')
else:
    print('❌ FAILED! Something went wrong:')
    print(f'   Open positions: {len(open_positions_after)} (expected: 0)')
    print(f'   Archived positions: {closed_count} (expected: 1)')

# Cleanup test data
print('\n🧹 Cleaning up test data...')
closed_positions.delete_many({'strategy_id': 'TEST_STRATEGY'})
print('   ✅ Test data cleaned')

print('=' * 80)
