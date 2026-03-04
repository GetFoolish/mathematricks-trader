#!/usr/bin/env python3
"""
Strategy Status Migration Script
Migrates strategy.status from string format to object format with defaults.

OLD FORMAT: status: "ACTIVE"
NEW FORMAT: status: { active: true, mode: "mock_mock", account_type: "mock", data_source: "mock" }

This script is backward compatible - it will skip strategies that already use the new format.
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
import argparse
from datetime import datetime

# Load environment
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
if not MONGODB_URI:
    print("❌ MONGODB_URI not set in environment")
    sys.exit(1)

def migrate_strategies(dry_run=True):
    """
    Migrate strategies from string status to object status with defaults.
    
    Args:
        dry_run: If True, only show what would be changed without modifying database
    """
    print("=" * 80)
    print("STRATEGY STATUS MIGRATION SCRIPT")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will update database)'}")
    print(f"MongoDB URI: {MONGODB_URI[:50]}...")
    print("")
    
    # Connect to MongoDB
    client = MongoClient(MONGODB_URI)
    db = client['mathematricks_trading']
    strategies_collection = db['strategies']
    
    # Get all strategies
    all_strategies = list(strategies_collection.find({}))
    print(f"📊 Found {len(all_strategies)} strategies in database")
    print("")
    
    # Track migration statistics
    already_migrated = 0
    to_migrate = 0
    migrated = 0
    errors = 0
    
    for strategy in all_strategies:
        strategy_id = strategy.get('strategy_id')
        current_status = strategy.get('status')
        
        # Skip if already using new format
        if isinstance(current_status, dict):
            already_migrated += 1
            print(f"✓ {strategy_id}: Already using new format (active={current_status.get('active')})")
            continue
        
        # Convert string status to object
        to_migrate += 1
        is_active = current_status in ['ACTIVE', 'TESTING']
        
        # Determine default mode, account_type, data_source based on strategy configuration
        # Default to mock for safety
        mode = "mock_mock"
        account_type = "mock"
        data_source = "mock"
        
        # Check if strategy has accounts configured
        accounts = strategy.get('accounts', {})
        if isinstance(accounts, dict):
            # New account format - determine defaults based on what's configured
            if accounts.get('live') and len(accounts['live']) > 0:
                mode = "live_live"
                account_type = "live"
                data_source = "live"
            elif accounts.get('paper') and len(accounts['paper']) > 0:
                mode = "paper_live"
                account_type = "paper"
                data_source = "live"
            # else: keep mock defaults
        
        new_status = {
            'active': is_active,
            'mode': mode,
            'account_type': account_type,
            'data_source': data_source
        }
        
        print(f"→ {strategy_id}:")
        print(f"  OLD: status = \"{current_status}\"")
        print(f"  NEW: status = {new_status}")
        
        if not dry_run:
            try:
                result = strategies_collection.update_one(
                    {'strategy_id': strategy_id},
                    {
                        '$set': {
                            'status': new_status,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                if result.modified_count > 0:
                    migrated += 1
                    print(f"  ✅ MIGRATED")
                else:
                    errors += 1
                    print(f"  ❌ FAILED (no documents modified)")
            except Exception as e:
                errors += 1
                print(f"  ❌ ERROR: {e}")
        else:
            print(f"  [DRY RUN - would migrate]")
        
        print("")
    
    # Print summary
    print("=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total strategies: {len(all_strategies)}")
    print(f"Already migrated: {already_migrated}")
    print(f"To migrate: {to_migrate}")
    
    if not dry_run:
        print(f"Successfully migrated: {migrated}")
        print(f"Errors: {errors}")
    else:
        print(f"\nRun with --execute to apply changes")
    
    print("=" * 80)


def rollback_migration(dry_run=True):
    """
    Rollback strategies from object status back to string format.
    
    Args:
        dry_run: If True, only show what would be changed without modifying database
    """
    print("=" * 80)
    print("STRATEGY STATUS ROLLBACK SCRIPT")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will update database)'}")
    print(f"MongoDB URI: {MONGODB_URI[:50]}...")
    print("")
    
    # Connect to MongoDB
    client = MongoClient(MONGODB_URI)
    db = client['mathematricks_trading']
    strategies_collection = db['strategies']
    
    # Get all strategies
    all_strategies = list(strategies_collection.find({}))
    print(f"📊 Found {len(all_strategies)} strategies in database")
    print("")
    
    # Track rollback statistics
    already_old_format = 0
    to_rollback = 0
    rolled_back = 0
    errors = 0
    
    for strategy in all_strategies:
        strategy_id = strategy.get('strategy_id')
        current_status = strategy.get('status')
        
        # Skip if already using old format
        if isinstance(current_status, str):
            already_old_format += 1
            print(f"✓ {strategy_id}: Already using old format (status={current_status})")
            continue
        
        # Convert object status to string
        to_rollback += 1
        is_active = current_status.get('active', True)
        new_status = 'ACTIVE' if is_active else 'INACTIVE'
        
        print(f"→ {strategy_id}:")
        print(f"  OLD: status = {current_status}")
        print(f"  NEW: status = \"{new_status}\"")
        
        if not dry_run:
            try:
                result = strategies_collection.update_one(
                    {'strategy_id': strategy_id},
                    {
                        '$set': {
                            'status': new_status,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                if result.modified_count > 0:
                    rolled_back += 1
                    print(f"  ✅ ROLLED BACK")
                else:
                    errors += 1
                    print(f"  ❌ FAILED (no documents modified)")
            except Exception as e:
                errors += 1
                print(f"  ❌ ERROR: {e}")
        else:
            print(f"  [DRY RUN - would rollback]")
        
        print("")
    
    # Print summary
    print("=" * 80)
    print("ROLLBACK SUMMARY")
    print("=" * 80)
    print(f"Total strategies: {len(all_strategies)}")
    print(f"Already old format: {already_old_format}")
    print(f"To rollback: {to_rollback}")
    
    if not dry_run:
        print(f"Successfully rolled back: {rolled_back}")
        print(f"Errors: {errors}")
    else:
        print(f"\nRun with --execute to apply changes")
    
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate strategy.status field between string and object formats"
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute the migration (default is dry-run)'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback to old string format instead of migrating to new format'
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if args.rollback:
        rollback_migration(dry_run=dry_run)
    else:
        migrate_strategies(dry_run=dry_run)
