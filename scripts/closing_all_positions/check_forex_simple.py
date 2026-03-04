#!/usr/bin/env python3
"""
Simple check for forex positions using direct IB connection
"""
from ib_insync import IB, Forex, MarketOrder
import time

config = {
    "host": "127.0.0.1",
    "port": 55858,
    "client_id": 204
}

print("🔌 Connecting to IBKR...")
ib = IB()
ib.connect(config["host"], config["port"], clientId=config["client_id"])
print("✅ Connected!\n")

try:
    print("💱 Checking forex positions (using positions())...")
    time.sleep(2)
    
    # Request positions
    ib.reqPositions()
    time.sleep(2)
    
    positions = ib.positions()
    forex_positions = [p for p in positions if hasattr(p.contract, 'secType') and p.contract.secType == 'CASH']
    
    print(f"Found {len(forex_positions)} forex position(s)")
    
    for pos in forex_positions:
        print(f"  {pos.contract.symbol}/{pos.contract.currency}: {pos.position}")
    
    if not forex_positions:
        print("\n✅ No forex positions found!")
    
finally:
    print("\n👋 Disconnecting...")
    ib.disconnect()
    print("Done!")
