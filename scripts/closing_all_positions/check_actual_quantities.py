#!/usr/bin/env python3
"""
Get actual currency quantities (not CAD equivalent values)
"""
from ib_insync import IB
import time

config = {
    "host": "127.0.0.1",
    "port": 55858,
    "client_id": 208
}

print("🔌 Connecting to IBKR...")
ib = IB()
ib.connect(config["host"], config["port"], clientId=config["client_id"])
print("✅ Connected!\n")

try:
    print("💰 Fetching account values...")
    time.sleep(2)
    
    # Get account values
    account_values = ib.accountValues()
    
    print("=" * 80)
    print("ALL CASH BALANCE ENTRIES")
    print("=" * 80)
    
    for av in account_values:
        if av.tag == 'CashBalance':
            print(f"{av.currency:5s} | {av.tag:20s} | {av.value:>20s} | {av.account}")
    
    print("\n" + "=" * 80)
    print("EXCHANGE RATES")
    print("=" * 80)
    
    for av in account_values:
        if 'ExchangeRate' in av.tag:
            print(f"{av.currency:5s} | {av.tag:20s} | {av.value:>20s}")
    
finally:
    ib.disconnect()
    print("\n👋 Done!")
