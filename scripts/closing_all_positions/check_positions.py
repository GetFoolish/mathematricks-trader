#!/usr/bin/env python3
"""
Quick script to check current IBKR positions directly from broker
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from brokers.ibkr.ibkr_broker import IBKRBroker
import json

# IBKR Paper account config
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",  # Localhost since running from host (not inside Docker)
    "port": 55858,  # Host port mapped to container's 4004
    "client_id": 200,  # Different client ID to avoid conflict
    "account_id": "IBKR-PAPER"
}

print("🔌 Connecting to IBKR...")
broker = IBKRBroker(config)

try:
    broker.connect()
    print("✅ Connected!\n")
    
    print("📊 Fetching positions...")
    positions = broker.get_open_positions()
    
    if not positions:
        print("❌ No open positions found")
    else:
        print(f"\n✅ Found {len(positions)} open position(s):\n")
        print(json.dumps(positions, indent=2))
        
        # Summary
        print(f"\n📈 SUMMARY:")
        print(f"{'─'*60}")
        total_value = 0
        for pos in positions:
            symbol = pos['instrument']
            qty = pos['quantity']
            side = pos['side']
            avg = pos['avg_price']
            value = pos['market_value']
            total_value += value
            print(f"{symbol:8} {side:5} {qty:>8.2f} @ ${avg:>8.2f} = ${value:>12,.2f}")
        print(f"{'─'*60}")
        print(f"{'TOTAL':22} ${total_value:>12,.2f}\n")
    
finally:
    broker.disconnect()
    print("👋 Disconnected")
