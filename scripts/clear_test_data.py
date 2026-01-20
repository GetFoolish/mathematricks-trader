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
        
        # Get the restart timestamp to filter logs
        restart_timestamp = datetime.now()
        
        # Wait for service to be fully operational
        print("  Waiting for execution-service to be ready...")
        print("  (Note: IB Gateway initialization takes ~60s, please be patient)")
        max_wait = 150  # 2.5 minutes max
        wait_interval = 5  # Check every 5 seconds
        elapsed = 0
        
        change_stream_ready = False
        execution_ready = False
        
        while elapsed < max_wait:
            time.sleep(wait_interval)
            elapsed += wait_interval
            
            current_time = datetime.now().strftime("%H:%M:%S")
            
            # Check if container is running
            try:
                result = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Status}}", 
                     "mathematricks-trader-execution-service-1"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                status = result.stdout.strip()
                
                if status != "running":
                    print(f"  [{current_time}] Waiting for container to start (status: {status})...")
                    continue
                
                # Container is running, check RECENT logs (since restart) for readiness signals
                # Use --since parameter to only get logs from after the restart
                since_seconds = int((datetime.now() - restart_timestamp).total_seconds()) + 5
                result = subprocess.run(
                    ["docker", "logs", "--since", f"{since_seconds}s", 
                     "mathematricks-trader-execution-service-1"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                logs = result.stdout + result.stderr
                
                # Check for BOTH critical readiness signals in RECENT logs only
                change_stream_ready = "MongoDB Change Stream connected for trading_orders" in logs
                execution_ready = "Execution Service ready - listening for orders" in logs
                
                if change_stream_ready and execution_ready:
                    print(f"  [{current_time}] ✅ execution-service fully restarted and ready ({elapsed}s)")
                    break
                else:
                    waiting_for = []
                    if not execution_ready:
                        waiting_for.append("IB Gateway initialization")
                    if not change_stream_ready:
                        waiting_for.append("MongoDB change stream")
                    print(f"  [{current_time}] Waiting for {' and '.join(waiting_for)} to start...")
                    
            except subprocess.CalledProcessError as e:
                print(f"  [{current_time}] Check failed: {e}, retrying...")
                continue
        else:
            print(f"  [{current_time}] ⚠️  Warning: execution-service not fully ready after {max_wait}s")
            print(f"     Change stream ready: {change_stream_ready}, Execution ready: {execution_ready}")
            
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
