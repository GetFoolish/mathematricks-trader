#!/usr/bin/env python3
"""
Cleanup Test Data Script

Removes stale signals, orders, and positions from the database to prepare for clean testing.
Run this before starting a new test session to ensure a clean slate.

Usage:
    python3 scripts/cleanup_test_data.py
    python3 scripts/cleanup_test_data.py --dry-run  # Preview what would be deleted
"""
import os
import sys
import argparse
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def cleanup_test_data(dry_run: bool = False, keep_hours: int = 24):
    """
    Clean up test data from MongoDB.

    Args:
        dry_run: If True, only show what would be deleted
        keep_hours: Keep data from last N hours (default: 24)
    """
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}🧹 CLEANUP TEST DATA{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}")
    
    if dry_run:
        print(f"{YELLOW}DRY RUN MODE - No data will be deleted{RESET}\n")
    else:
        print(f"{RED}⚠️  LIVE MODE - Data will be permanently deleted{RESET}\n")
    
    # Connect to MongoDB
    mongo_uri = os.getenv('MONGODB_URI')
    if not mongo_uri:
        print(f"{RED}❌ MONGODB_URI not set in .env{RESET}")
        return False
    
    use_tls = 'mongodb+srv' in mongo_uri or 'mongodb.net' in mongo_uri
    if use_tls:
        client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    else:
        client = MongoClient(mongo_uri)
    
    db = client['mathematricks_trading']
    
    # Calculate cutoff time
    cutoff_time = datetime.utcnow() - timedelta(hours=keep_hours)
    print(f"Cutoff time: {cutoff_time.isoformat()} (keeping last {keep_hours} hours)\n")
    
    # ========================================================================
    # 1. Clean up stale signals
    # ========================================================================
    print(f"{BOLD}1. Signal Store Cleanup{RESET}")
    
    # Remove completed/rejected signals older than cutoff
    stale_signals_query = {
        "$or": [
            {"status": {"$in": ["completed", "rejected", "cancelled"]}},
            {"created_at": {"$lt": cutoff_time}}
        ]
    }
    
    stale_signals_count = db.signal_store.count_documents(stale_signals_query)
    
    if stale_signals_count > 0:
        print(f"  Found {stale_signals_count} stale signals to remove")
        if not dry_run:
            result = db.signal_store.delete_many(stale_signals_query)
            print(f"  {GREEN}✅ Deleted {result.deleted_count} signals{RESET}")
    else:
        print(f"  {GREEN}✅ No stale signals found{RESET}")
    
    # Show pending signals (don't delete)
    pending_signals = db.signal_store.count_documents({
        "status": {"$nin": ["completed", "rejected", "cancelled"]}
    })
    if pending_signals > 0:
        print(f"  {YELLOW}⚠️  {pending_signals} pending signals (keeping){RESET}")
    
    # ========================================================================
    # 2. Clean up old orders
    # ========================================================================
    print(f"\n{BOLD}2. Trading Orders Cleanup{RESET}")
    
    old_orders_query = {
        "$or": [
            {"status": {"$in": ["FILLED", "REJECTED", "CANCELLED"]}},
            {"created_at": {"$lt": cutoff_time}}
        ]
    }
    
    old_orders_count = db.trading_orders.count_documents(old_orders_query)
    
    if old_orders_count > 0:
        print(f"  Found {old_orders_count} old orders to remove")
        if not dry_run:
            result = db.trading_orders.delete_many(old_orders_query)
            print(f"  {GREEN}✅ Deleted {result.deleted_count} orders{RESET}")
    else:
        print(f"  {GREEN}✅ No old orders found{RESET}")
    
    # Show pending orders
    pending_orders = db.trading_orders.count_documents({
        "status": {"$nin": ["FILLED", "REJECTED", "CANCELLED"]}
    })
    if pending_orders > 0:
        print(f"  {YELLOW}⚠️  {pending_orders} pending orders (keeping){RESET}")
    
    # ========================================================================
    # 3. Clean up closed positions
    # ========================================================================
    print(f"\n{BOLD}3. Closed Positions Cleanup{RESET}")
    
    # Get all accounts
    accounts = list(db.trading_accounts.find({}))
    total_closed = 0
    
    for account in accounts:
        account_id = account['account_id']
        all_positions = account.get('open_positions', [])
        
        # Separate open and closed positions
        open_positions = [p for p in all_positions if p.get('status') == 'OPEN']
        closed_positions = [p for p in all_positions if p.get('status') == 'CLOSED']
        
        if closed_positions:
            print(f"  Account {account_id}: {len(closed_positions)} closed positions")
            total_closed += len(closed_positions)
            
            if not dry_run:
                # Update account to only keep open positions
                db.trading_accounts.update_one(
                    {"account_id": account_id},
                    {"$set": {"open_positions": open_positions}}
                )
    
    if total_closed > 0:
        if not dry_run:
            print(f"  {GREEN}✅ Removed {total_closed} closed positions{RESET}")
        else:
            print(f"  Would remove {total_closed} closed positions")
    else:
        print(f"  {GREEN}✅ No closed positions found{RESET}")
    
    # ========================================================================
    # 4. Show open positions (don't delete)
    # ========================================================================
    print(f"\n{BOLD}4. Open Positions Summary{RESET}")
    
    for account in accounts:
        account_id = account['account_id']
        all_positions = account.get('open_positions', [])
        open_positions = [p for p in all_positions if p.get('status') == 'OPEN']
        
        if open_positions:
            print(f"  {YELLOW}⚠️  Account {account_id}: {len(open_positions)} open positions (keeping){RESET}")
            for pos in open_positions:
                symbol = pos.get('instrument', '?')
                qty = pos.get('quantity', 0)
                strategy = pos.get('strategy_id', '?')
                print(f"      - {symbol}: {qty} shares | Strategy: {strategy}")
        else:
            print(f"  {GREEN}✅ Account {account_id}: No open positions{RESET}")
    
    # ========================================================================
    # 5. Optional: Clear precision cache (for testing)
    # ========================================================================
    print(f"\n{BOLD}5. Precision Cache{RESET}")
    
    precision_count = db.precision_cache.count_documents({})
    print(f"  Current entries: {precision_count}")
    print(f"  {BLUE}ℹ️  Precision cache is preserved (not deleted){RESET}")
    
    # ========================================================================
    # Summary
    # ========================================================================
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}SUMMARY{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}")
    
    if dry_run:
        print(f"{YELLOW}DRY RUN - No changes made{RESET}")
        print(f"Run without --dry-run to actually delete data")
    else:
        print(f"{GREEN}✅ Cleanup complete!{RESET}")
        print(f"Database is ready for clean testing")
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean up test data from MongoDB')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview what would be deleted without actually deleting')
    parser.add_argument('--keep-hours', type=int, default=24,
                        help='Keep data from last N hours (default: 24)')
    args = parser.parse_args()
    
    try:
        success = cleanup_test_data(dry_run=args.dry_run, keep_hours=args.keep_hours)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Cancelled by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        sys.exit(1)
