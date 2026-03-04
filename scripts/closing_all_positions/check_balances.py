#!/usr/bin/env python3
"""
Quick script to check IBKR account balances and currencies
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from brokers.ibkr.ibkr_broker import IBKRBroker
import json

# IBKR Paper account config
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 55858,
    "client_id": 200,
    "account_id": "IBKR-PAPER"
}

print("🔌 Connecting to IBKR...")
broker = IBKRBroker(config)

try:
    broker.connect()
    print("✅ Connected!\n")
    
    print("💰 Fetching account balance...")
    balance_data = broker.get_account_balance(config["account_id"])
    
    print("\n📊 FULL BALANCE DATA:")
    print("=" * 60)
    print(json.dumps(balance_data, indent=2))
    
    # Check for currencies other than USD/CAD
    print("\n💱 CURRENCY CHECK:")
    print("=" * 60)
    
    # Common fields that might contain currency info
    currencies_found = set()
    
    # Check if balance_data is a dict with currency breakdowns
    if isinstance(balance_data, dict):
        for key, value in balance_data.items():
            if isinstance(value, dict) and 'currency' in value:
                currencies_found.add(value['currency'])
            elif 'currency' in str(key).lower():
                currencies_found.add(str(value))
    
    if currencies_found:
        print(f"Found currencies: {', '.join(sorted(currencies_found))}")
        non_usd_cad = currencies_found - {'USD', 'CAD'}
        if non_usd_cad:
            print(f"⚠️  Non-USD/CAD currencies detected: {', '.join(sorted(non_usd_cad))}")
        else:
            print("✅ Only USD and/or CAD currencies found")
    else:
        print("ℹ️  Could not detect currency breakdown - check raw data above")
    
finally:
    print("\n👋 Disconnecting...")
    broker.disconnect()
    print("Done!")
