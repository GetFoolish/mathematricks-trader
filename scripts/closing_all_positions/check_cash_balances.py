#!/usr/bin/env python3
"""
Check cash balances by currency
"""
from ib_insync import IB
import time

config = {
    "host": "127.0.0.1",
    "port": 55858,
    "client_id": 205
}

print("🔌 Connecting to IBKR...")
ib = IB()
ib.connect(config["host"], config["port"], clientId=config["client_id"])
print("✅ Connected!\n")

try:
    print("💰 Fetching account values...")
    time.sleep(2)
    
    # Get account values which include cash balances
    account_values = ib.accountValues()
    
    # Filter for cash balance by currency
    cash_balances = {}
    for av in account_values:
        if av.tag == 'CashBalance' and av.currency not in ['BASE']:
            try:
                amount = float(av.value)
                if abs(amount) > 0.01:  # Only non-zero
                    cash_balances[av.currency] = amount
            except:
                pass
    
    print("💵 CASH BALANCES BY CURRENCY:")
    print("=" * 60)
    
    if cash_balances:
        for currency in sorted(cash_balances.keys()):
            amount = cash_balances[currency]
            print(f"{currency:5}: ${amount:>12,.2f}")
        
        # Check for non-USD/CAD
        non_standard = {c: v for c, v in cash_balances.items() if c not in ['USD', 'CAD']}
        if non_standard:
            print(f"\n⚠️  {len(non_standard)} Non-USD/CAD currencies:")
            for currency, amount in sorted(non_standard.items()):
                print(f"   {currency}: ${amount:,.2f}")
        else:
            print("\n✅ Only USD and/or CAD currencies with cash")
    else:
        print("✅ No foreign currency cash balances found!")
    pass
    
finally:
    print("\n👋 Disconnecting...")
    ib.disconnect()
    print("Done!")
