#!/usr/bin/env python3
"""
Clear test data from MongoDB collections.

Clears:
- trading_signals_raw
- signal_store
- trading_orders

Resets:
- trading_accounts: balances reset to initial_equity, open_positions cleared
- funds: total_equity recalculated from sum of account equities

Usage:
    python scripts/junk/clear_test_data.py
"""
import os
import subprocess
import sys
import time
import json
import requests
from datetime import datetime
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

    # Reset fund total_equity by summing account equities
    print("\nResetting fund total_equity...")
    funds = db['funds'].find({})
    for fund in funds:
        fund_id = fund.get('fund_id')

        # Get all accounts for this fund
        fund_accounts = db['trading_accounts'].find({'fund_id': fund_id})

        # Sum equity across all accounts
        total_equity = sum(
            acc.get('balances', {}).get('equity', 0.0)
            for acc in fund_accounts
        )

        # Update fund total_equity
        db['funds'].update_one(
            {'fund_id': fund_id},
            {'$set': {'total_equity': total_equity}}
        )
        print(f"  {fund_id}: reset to ${total_equity:,.2f} total_equity")

    # Restart execution-service to clear in-memory duplicate tracking
    print("\nRestarting execution-service to clear in-memory state...")
    try:
        subprocess.run(
            ["docker", "restart", "mathematricks-trader-execution-service-1"],
            check=True,
            capture_output=True
        )
        print("  execution-service restart initiated...")
        
        # Wait for service to be healthy by polling health endpoint
        print("  Waiting for execution-service to be healthy...")
        max_wait = 90  # 1.5 minutes max
        wait_interval = 2  # Check every 2 seconds
        elapsed = 0
        
        service_ready = False
        
        while elapsed < max_wait:
            time.sleep(wait_interval)
            elapsed += wait_interval
            
            current_time = datetime.now().strftime("%H:%M:%S")
            
            try:
                # Check health endpoint via host network (execution service exposes 8083)
                response = requests.get('http://localhost:8083/health', timeout=2)
                
                if response.status_code == 200:
                    health_data = response.json()
                    if health_data.get('ready'):
                        service_ready = True
                        brokers = health_data.get('brokers_connected', 0)
                        pending = health_data.get('pending_orders_processed', 0)
                        print(f"  [{current_time}] ✅ execution-service ready ({elapsed}s)")
                        print(f"     Brokers connected: {brokers}, Pending orders processed: {pending}")
                        break
                    else:
                        status = health_data.get('status', 'unknown')
                        print(f"  [{current_time}] Waiting for service (status: {status})...")
                elif response.status_code == 503:
                    print(f"  [{current_time}] Service starting...")
                else:
                    print(f"  [{current_time}] Unexpected status code: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                print(f"  [{current_time}] Waiting for health endpoint to be available...")
            except requests.exceptions.Timeout:
                print(f"  [{current_time}] Health check timeout, retrying...")
            except Exception as e:
                print(f"  [{current_time}] Check failed: {e}, retrying...")
        
        if not service_ready:
            print(f"  [{current_time}] ⚠️  Warning: execution-service not ready after {max_wait}s")
            print(f"     Container may still be initializing - check logs if issues occur")
        
        # Verify MongoDB connection with a simple query
        print("  Verifying MongoDB connection...")
        try:
            # Simple ping to verify connection
            client.admin.command('ping')
            # Quick test query
            db['trading_accounts'].find_one()
            print(f"  ✅ MongoDB connection verified")
        except Exception as e:
            print(f"  ⚠️  Warning: MongoDB connection test failed: {e}")
            
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
