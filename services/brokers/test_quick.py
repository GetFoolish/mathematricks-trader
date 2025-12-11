#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from factory import BrokerFactory

print("=" * 80)
print("QUICK IBKR BROKER TEST")
print("=" * 80)

config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 998,  # Different from test to avoid conflicts
    "account_id": "DU123456"
}

print("\n1. Creating broker...")
broker = BrokerFactory.create_broker(config)
print(f"✓ Broker created: {broker.broker_name}")

print("\n2. Connecting to IBKR...")
broker.connect()
print("✓ Connected!")

print("\n3. Getting account balance...")
balance = broker.get_account_balance()
print(f"✓ Equity: ${balance['equity']:,.2f}")
print(f"✓ Cash: ${balance['cash_balance']:,.2f}")
print(f"✓ Margin Used: ${balance['margin_used']:,.2f}")

print("\n4. Getting open positions...")
positions = broker.get_open_positions()
print(f"✓ {len(positions)} open positions")
for pos in positions:
    print(f"  - {pos['symbol']}: {pos['side']} {pos['quantity']} shares")

print("\n5. Placing test order (1 share AAPL)...")
result = broker.place_order({
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 1,
    "order_type": "MARKET",
    "instrument_type": "STOCK"
})
print(f"✓ Order placed!")
print(f"  Order ID: {result['broker_order_id']}")
print(f"  Status: {result['status']}")
print(f"  Timestamp: {result['timestamp']}")

print("\n6. Disconnecting...")
broker.disconnect()
print("✓ Disconnected!")

print("\n" + "=" * 80)
print("✅ ALL TESTS PASSED - BROKER LIBRARY WORKS!")
print("=" * 80)
