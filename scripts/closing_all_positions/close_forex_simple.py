#!/usr/bin/env python3
"""
Close all forex cash positions (convert to CAD) - simple version
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
    "client_id": 206,
    "account_id": "IBKR-PAPER"
}

# Current forex positions after failed close attempts (positions flipped)
# Format: (currency, balance, pair, direction)
forex_closes = [
    ("AUD", 14140.00, "AUDCAD", "SHORT"),     # Now LONG AUD -> SELL AUDCAD
    ("EUR", -4040.00, "EURCAD", "LONG"),      # Now SHORT EUR -> BUY EURCAD
    ("GBP", 1010.00, "GBPCAD", "SHORT"),      # Now LONG GBP -> SELL GBPCAD
    ("NZD", -2020.00, "NZDCAD", "LONG"),      # Now SHORT NZD -> BUY NZDCAD    ("CHF", -201.16, "CADCHF", "SHORT"),      # Now SHORT CHF (quote) -> SELL CADCHF
    ("MXN", 280143.64, "USDMXN", "LONG"),     # Now massively LONG MXN -> BUY USDMXN to close
    ("SEK", 289169.44, "USDSEK", "LONG"),     # Now massively LONG SEK -> BUY USDSEK to close
]

print("🔌 Connecting to IBKR...")
broker = IBKRBroker(config)

try:
    broker.connect()
    print("✅ Connected!\n")
    
    print(f"💱 Found {len(forex_closes)} forex position(s) to close:\n")
    
    # Display positions
    for currency, balance, pair, direction in forex_closes:
        position_type = "LONG" if balance > 0 else "SHORT"
        action = "BUY" if direction == "LONG" else "SELL"
        print(f"  {currency:5} {position_type:5} ${balance:>12,.2f} → {action} {pair}")
    
    # Ask for confirmation
    response = input(f"\n⚠️  Close ALL forex positions? (yes/no): ").strip().lower()
    
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
        
        print("\n✅ All forex close orders submitted!")
        print("ℹ️  Run check_cash_balances.py to verify positions are closed")
    
finally:
    print("\n👋 Disconnecting...")
    broker.disconnect()
    print("Done!")
