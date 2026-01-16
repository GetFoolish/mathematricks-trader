#!/usr/bin/env python3
"""
IBKR-specific test runner with pre-flight checks and validation.
Run this to test IBKR integration end-to-end.
"""
import os
import sys
import subprocess
import time
from pymongo import MongoClient

def check_ib_gateway():
    """Verify IB Gateway container is running"""
    print("\n[Check 1/4] Checking IB Gateway container...")
    result = subprocess.run(
        ['docker', 'ps', '--filter', 'name=ib-gateway', '--format', '{{.Status}}'],
        capture_output=True, text=True
    )
    if 'Up' not in result.stdout:
        print("❌ IB Gateway not running. Start with: docker-compose up -d ib-gateway")
        sys.exit(1)
    print("✅ IB Gateway is running")

def check_account_exists():
    """Verify IBKR test account exists in MongoDB"""
    print("\n[Check 2/4] Checking IBKR_Paper_Test account in MongoDB...")
    client = MongoClient('mongodb://localhost:27017/')
    db = client['mathematricks_trading']
    account = db['trading_accounts'].find_one({"account_id": "IBKR_Paper_Test"})

    if not account:
        print("❌ IBKR_Paper_Test account not found in MongoDB")
        print("   Create it with: db.trading_accounts.insertOne({...})")
        sys.exit(1)

    mode = account.get('mode', 'unknown')
    print(f"✅ IBKR_Paper_Test account found (mode: {mode})")
    return mode

def check_execution_service():
    """Verify execution service is running"""
    print("\n[Check 3/4] Checking execution service...")
    result = subprocess.run(
        ['docker', 'ps', '--filter', 'name=execution-service', '--format', '{{.Status}}'],
        capture_output=True, text=True
    )
    if 'Up' not in result.stdout:
        print("⚠️  Execution service not running via docker")
        print("   Make sure it's running manually or via docker-compose")
    else:
        print("✅ Execution service is running")

def check_test_signals_exist():
    """Verify test signal files exist"""
    print("\n[Check 4/4] Checking test signal files...")
    folder = "tests/signals_testing/sample_signals_ibkr"
    expected_files = [
        "ibkr_stock_aapl.json",
        "ibkr_crypto_btc.json",
        "ibkr_forex_eurusd.json",
        "ibkr_future_gc.json",
        "ibkr_option_spy.json"
    ]

    missing = []
    for file in expected_files:
        path = os.path.join(folder, file)
        if not os.path.exists(path):
            missing.append(file)

    if missing:
        print(f"❌ Missing test signal files: {', '.join(missing)}")
        print(f"   Create them in {folder}/")
        sys.exit(1)

    print(f"✅ All {len(expected_files)} test signal files found")

def run_test():
    """Run the actual IBKR test"""
    print("\n" + "="*60)
    print("=== RUNNING IBKR TEST SIGNALS ===")
    print("="*60)
    print("\nℹ️  Connect VNC Viewer to localhost:5900 to monitor IB Gateway")
    print("   Password: ibgateway\n")

    time.sleep(3)  # Give user time to connect VNC

    # Run test with small delay between signals
    cmd = (
        ".venv/bin/python tests/signals_testing/run_full_test.py "
        "--folder tests/signals_testing/sample_signals_ibkr "
        "--delay 10 "
        "--signal_count 10"
    )

    print(f"Running: {cmd}\n")
    os.system(cmd)

def validate_results():
    """Post-test validation"""
    print("\n" + "="*60)
    print("=== TEST VALIDATION CHECKLIST ===")
    print("="*60)
    print("\nPlease manually verify:")
    print("  [ ] Pricing is realistic (e.g., AAPL ~$170, not 100.0) - check logs")
    print("  [ ] Orders went to Mock broker - check trading_accounts.open_positions")
    print("  [ ] No real orders submitted - check IB Gateway VNC (activity log empty)")
    print("  [ ] Signals processed - check signal_store collection")
    print("\nTo query results:")
    print("  MongoDB: db.signal_store.find({strategy_id: 'IBKR_Test_Stock'}).pretty()")
    print("  MongoDB: db.trading_accounts.findOne({account_id: 'IBKR_Paper_Test'})")

def main():
    print("="*60)
    print("=== IBKR TEST SUITE PRE-FLIGHT CHECKS ===")
    print("="*60)

    try:
        check_ib_gateway()
        mode = check_account_exists()
        check_execution_service()
        check_test_signals_exist()

        print("\n✅ All pre-flight checks passed!")
        print(f"\nℹ️  Running in mode: {mode}")

        if mode == 'live':
            print("\n⚠️  WARNING: Account is in LIVE mode - real money at risk!")
            response = input("Type 'YES' to continue with live trading: ")
            if response != 'YES':
                print("Aborted.")
                sys.exit(0)

        run_test()
        validate_results()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
