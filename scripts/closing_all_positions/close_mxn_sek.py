#!/usr/bin/env python3
"""
Close remaining MXN and SEK positions using valid IBKR pairs
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from brokers.ibkr.ibkr_broker import IBKRBroker
import time

# IBKR Paper account config
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 55858,
    "client_id": 207,
    "account_id": "IBKR-PAPER"
}

# Remaining forex positions - using USD pairs since CAD pairs don't exist
# MXN: -17,351.40 (short MXN) - use USDMXN
# SEK: -36,177.19 (short SEK) - use USDSEK
forex_closes = [
    ("MXN", -17351.40, "USDMXN", "SHORT"),    # Short MXN -> need to BUY MXN, so SELL USDMXN
    ("SEK", -36177.19, "USDSEK", "SHORT"),    # Short SEK -> need to BUY SEK, so SELL USDSEK
]

print("🔌 Connecting to IBKR...")
broker = IBKRBroker(config)

try:
    broker.connect()
    print("✅ Connected!\n")
    
    print(f"💱 Closing remaining {len(forex_closes)} forex position(s):\n")
    
    # Display positions
    for currency, balance, pair, direction in forex_closes:
        position_type = "LONG" if balance > 0 else "SHORT"
        action = "BUY" if direction == "LONG" else "SELL"
        print(f"  {currency:5} {position_type:5} ${balance:>12,.2f} → {action} {pair}")
    
    # Ask for confirmation
    response = input(f"\n⚠️  Close remaining forex positions? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("❌ Cancelled by user")
    else:
        print("\n🚀 Closing forex positions...\n")
        
        for i, (currency, balance, pair, direction) in enumerate(forex_closes, 1):
            abs_qty = abs(balance)
            action_text = "BUY" if direction == "LONG" else "SELL"
            
            print(f"[{i}/{len(forex_closes)}] Closing {currency}: {action_text} {abs_qty:,.2f} via {pair}...")
            
            order = {
                "instrument": pair,
                "instrument_type": "FOREX",
                "direction": direction,
                "quantity": abs_qty,
                "order_type": "MARKET",
                "account_id": config["account_id"]
            }
            
            try:
                result = broker.place_order(order)
                status = result.get('status', 'UNKNOWN')
                broker_order_id = result.get('broker_order_id', 'N/A')
                print(f"  ✅ Order placed: {broker_order_id} ({status})")
                
                # Wait between orders
                if i < len(forex_closes):
                    time.sleep(2)
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        print("\n⏳ Waiting 5 seconds for fills...")
        time.sleep(5)
        
        print("\n✅ All remaining forex close orders submitted!")
        print("ℹ️  Run check_cash_balances.py to verify all positions are closed")
    
finally:
    print("\n👋 Disconnecting...")
    broker.disconnect()
    print("Done!")
