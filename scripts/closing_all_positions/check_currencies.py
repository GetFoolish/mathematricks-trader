#!/usr/bin/env python3
"""
Check IBKR account for all currencies with cash balances
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from ib_insync import IB
import time

# IBKR Paper account config
config = {
    "host": "127.0.0.1",
    "port": 55858,
    "client_id": 201  # Different client ID
}

print("🔌 Connecting to IBKR...")
ib = IB()

try:
    ib.connect(config["host"], config["port"], clientId=config["client_id"])
    print("✅ Connected!\n")
    
    # Give it a moment to sync
    time.sleep(2)
    
    print("💰 Fetching detailed account summary...")
    account_summary = ib.accountSummary()
    
    print(f"\n📊 Total account summary items: {len(account_summary)}\n")
    
    # Group by currency
    currencies = {}
    cash_by_currency = {}
    
    for item in account_summary:
        currency = item.currency if item.currency else 'N/A'
        tag = item.tag
        value = item.value
        
        if currency not in currencies:
            currencies[currency] = []
        currencies[currency].append(f"{tag}: {value}")
        
        # Track cash balances
        if tag == 'CashBalance' and currency != 'BASE':
            try:
                cash_val = float(value)
                if abs(cash_val) > 0.01:  # Only non-zero balances
                    cash_by_currency[currency] = cash_val
            except:
                pass
    
    print("💱 CURRENCIES FOUND:")
    print("=" * 60)
    for currency in sorted(currencies.keys()):
        print(f"\n{currency}:")
        for item in currencies[currency][:5]:  # Show first 5 items per currency
            print(f"  {item}")
        if len(currencies[currency]) > 5:
            print(f"  ... and {len(currencies[currency]) - 5} more items")
    
    print("\n\n💵 CASH BALANCES BY CURRENCY:")
    print("=" * 60)
    if cash_by_currency:
        for currency, amount in sorted(cash_by_currency.items()):
            print(f"{currency}: ${amount:,.2f}")
        
        # Check for non-USD/CAD
        non_standard = {c: v for c, v in cash_by_currency.items() if c not in ['USD', 'CAD']}
        if non_standard:
            print(f"\n⚠️  Non-USD/CAD currencies detected:")
            for currency, amount in sorted(non_standard.items()):
                print(f"   {currency}: ${amount:,.2f}")
        else:
            print("\n✅ Only USD and/or CAD currencies with cash")
    else:
        print("ℹ️  No non-zero cash balances found in foreign currencies")
    
finally:
    print("\n👋 Disconnecting...")
    ib.disconnect()
    print("Done!")
