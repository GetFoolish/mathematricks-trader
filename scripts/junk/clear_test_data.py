#!/usr/bin/env python3
"""
Clear test data from MongoDB collections.

Clears:
- trading_signals_raw
- signal_store
- trading_orders

Resets:
- trading_accounts: balances reset to initial_equity, open_positions cleared

Usage:
    python scripts/junk/clear_test_data.py
"""
import os
import subprocess
import sys
import time
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def clear_test_data():
    """Clear test collections from MongoDB"""
    # Use MONGODB_URI_LOCAL for Mac scripts, fallback to MONGODB_URI for Docker
    mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI')

    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)

    db = client['mathematricks_trading']

    collections = ['trading_signals_raw', 'signal_store', 'trading_orders']

    print("=" * 60)
    print("Clearing test data...")
    print("=" * 60)

    for coll_name in collections:
        before_count = db[coll_name].count_documents({})
        result = db[coll_name].delete_many({})
        print(f"  {coll_name}: deleted {result.deleted_count} documents (was {before_count})")

    # Reset trading account balances to initial equity
    print("\nResetting trading account balances...")
    accounts = db['trading_accounts'].find({})
    reset_count = 0
    for account in accounts:
        initial_equity = account.get('authentication_details', {}).get('initial_equity', 1000000.0)

        # Reset balances to initial state
        reset_balances = {
            'equity': initial_equity,
            'cash': initial_equity / 2,  # Half in cash
            'cash_balance': initial_equity / 2,
            'margin_used': 0.0,
            'margin_available': initial_equity / 2,
            'buying_power': initial_equity * 2,  # 2x leverage
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
        }

        db['trading_accounts'].update_one(
            {'_id': account['_id']},
            {
                '$set': {
                    'balances.equity': reset_balances['equity'],
                    'balances.cash': reset_balances['cash'],
                    'balances.cash_balance': reset_balances['cash_balance'],
                    'balances.margin_used': reset_balances['margin_used'],
                    'balances.margin_available': reset_balances['margin_available'],
                    'balances.buying_power': reset_balances['buying_power'],
                    'balances.unrealized_pnl': reset_balances['unrealized_pnl'],
                    'balances.realized_pnl': reset_balances['realized_pnl'],
                    'open_positions': []
                }
            }
        )
        reset_count += 1
        print(f"  {account.get('account_id', account.get('_id'))}: reset to ${initial_equity:,.2f} equity")

    if reset_count > 0:
        print(f"  Total accounts reset: {reset_count}")

    # Restart execution-service to clear in-memory duplicate tracking
    print("\nRestarting execution-service to clear in-memory state...")
    try:
        subprocess.run(
            ["docker", "restart", "mathematricks-trader-execution-service-1"],
            check=True,
            capture_output=True
        )
        time.sleep(3)  # Wait for service to restart
        print("  execution-service restarted")
    except subprocess.CalledProcessError as e:
        print(f"  Warning: Could not restart execution-service: {e}")
    except FileNotFoundError:
        print("  Warning: docker command not found, skipping container restart")

    print("=" * 60)
    print("Done!")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    clear_test_data()
