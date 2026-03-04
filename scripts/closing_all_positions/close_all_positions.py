#!/usr/bin/env python3
"""
Close all open IBKR positions
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from brokers.ibkr.ibkr_broker import IBKRBroker
import json
import time

# IBKR Paper account config
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",  
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
        print("❌ No open positions to close")
        sys.exit(0)
    
    print(f"\n✅ Found {len(positions)} open position(s) to close:\n")
    
    # Display positions
    total_value = 0
    for pos in positions:
        symbol = pos['instrument']
        qty = pos['quantity']
        side = pos['side']
        avg = pos['avg_price']
        value = pos['market_value']
        total_value += value
        print(f"  {symbol:8} {side:5} {qty:>8.2f} @ ${avg:>8.2f} = ${value:>12,.2f}")
    print(f"  {'─'*60}")
    print(f"  {'TOTAL':22} ${total_value:>12,.2f}\n")
    
    # Confirm
    response = input("⚠️  Close ALL positions? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Cancelled")
        sys.exit(0)
    
    print("\n🚀 Closing positions...\n")
    
    # Close each position
    for i, pos in enumerate(positions, 1):
        symbol = pos['instrument']
        qty = pos['quantity']
        position_side = pos['side']  # LONG or SHORT
        
        # To close: LONG position needs SELL (SHORT), SHORT position needs BUY (LONG)
        close_direction = "SHORT" if position_side == "LONG" else "LONG"
        action_text = "SELL" if position_side == "LONG" else "BUY"
        
        print(f"[{i}/{len(positions)}] Closing {symbol}: {action_text} {qty:.2f} shares...")
        
        order = {
            "instrument": symbol,
            "instrument_type": "STOCK",
            "direction": close_direction,  # SHORT→SELL, LONG→BUY
            "quantity": qty,
            "order_type": "MARKET",
            "account_id": config["account_id"]
        }
        
        try:
            result = broker.place_order(order)
            status = result.get('status', 'UNKNOWN')
            broker_order_id = result.get('broker_order_id', 'N/A')
            print(f"  ✅ Order placed: {broker_order_id} ({status})")
            
            # Wait a bit between orders
            if i < len(positions):
                time.sleep(1)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n⏳ Waiting 3 seconds for fills...")
    time.sleep(3)
    
    # Check remaining positions
    print("\n📊 Checking remaining positions...")
    new_positions = broker.get_open_positions()
    
    if not new_positions:
        print("✅ All positions closed successfully!")
    else:
        print(f"⚠️  {len(new_positions)} position(s) still open:")
        for pos in new_positions:
            print(f"  {pos['instrument']}: {pos['quantity']} {pos['side']}")
    
finally:
    broker.disconnect()
    print("\n👋 Disconnected")
