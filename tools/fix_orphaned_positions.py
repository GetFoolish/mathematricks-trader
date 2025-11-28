#!/usr/bin/env python3
"""
Fix orphaned positions in trading_accounts collection
Removes positions with missing or invalid status fields
"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client['mathematricks_trading']
trading_accounts = db['trading_accounts']

print('=' * 80)
print('FIXING ORPHANED POSITIONS')
print('=' * 80)

accounts = list(trading_accounts.find({}))

for account in accounts:
    account_id = account.get('account_id')
    open_positions = account.get('open_positions', [])
    
    if not open_positions:
        continue
    
    print(f'\nAccount: {account_id}')
    print(f'Total positions: {len(open_positions)}')
    
    # Separate positions by status
    valid_open = []
    closed = []
    orphaned = []
    
    for pos in open_positions:
        status = pos.get('status')
        
        if status == 'OPEN':
            valid_open.append(pos)
        elif status == 'CLOSED':
            closed.append(pos)
        else:
            # Missing or invalid status
            orphaned.append(pos)
    
    print(f'  Valid OPEN: {len(valid_open)}')
    print(f'  CLOSED: {len(closed)}')
    print(f'  Orphaned/Invalid: {len(orphaned)}')
    
    if orphaned:
        print('\n  Orphaned positions:')
        for pos in orphaned:
            print(f'    - {pos.get("strategy_id", "N/A")}/{pos.get("instrument", "N/A")}: '
                  f'{pos.get("quantity", 0)} @ ${pos.get("avg_entry_price", 0):.2f} '
                  f'(status: {pos.get("status", "MISSING")})')
    
    # Ask user what to do
    if orphaned or closed:
        print(f'\n  Cleanup options:')
        print(f'    1. Remove all CLOSED positions ({len(closed)} positions)')
        print(f'    2. Remove all orphaned positions ({len(orphaned)} positions)')
        print(f'    3. Remove both CLOSED and orphaned ({len(closed) + len(orphaned)} positions)')
        print(f'    4. Skip this account')
        
        choice = input(f'\n  Choose action for {account_id} (1-4): ').strip()
        
        positions_to_keep = open_positions.copy()
        
        if choice == '1':
            positions_to_keep = [p for p in positions_to_keep if p.get('status') != 'CLOSED']
        elif choice == '2':
            positions_to_keep = [p for p in positions_to_keep if p.get('status') in ['OPEN', 'CLOSED']]
        elif choice == '3':
            positions_to_keep = valid_open
        elif choice == '4':
            print('  Skipped.')
            continue
        else:
            print('  Invalid choice, skipping.')
            continue
        
        # Update the account
        result = trading_accounts.update_one(
            {'account_id': account_id},
            {
                '$set': {
                    'open_positions': positions_to_keep,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            print(f'  ✅ Updated {account_id}: {len(open_positions)} → {len(positions_to_keep)} positions')
        else:
            print(f'  ⚠️  No changes made to {account_id}')

print('\n' + '=' * 80)
print('CLEANUP COMPLETE')
print('=' * 80)
