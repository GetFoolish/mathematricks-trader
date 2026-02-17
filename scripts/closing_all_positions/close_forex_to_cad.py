#!/usr/bin/env python3
"""
Close remaining forex positions: CHF, MXN, SEK → USD, then USD → CAD
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
    "client_id": 208,
    "account_id": "IBKR-PAPER"
}

# Step 1: Convert CHF, MXN, SEK to USD
# Current positions from check_cash_balances.py:
# CHF: $-201.16 (short CHF) → BUY CHF via CHFUSD
# MXN: $-4,523,210.98 (short MXN) → BUY MXN via USDMXN  
# SEK: $-2,311,821.85 (short SEK) → BUY SEK via USDSEK
step1_trades = [
    ("CHF", -201.16, "USDCHF", "SHORT"),      # Short CHF → BUY CHF = SELL USDCHF (SHORT)
    ("MXN", -4523210.98, "USDMXN", "LONG"),   # Short MXN → BUY MXN = BUY USDMXN (LONG)
    ("SEK", -2311821.85, "USDSEK", "LONG"),   # Short SEK → BUY SEK = BUY USDSEK (LONG)
]

print("🔌 Connecting to IBKR...")
broker = IBKRBroker(config)

try:
    broker.connect()
    print("✅ Connected!\n")
    
    print("=" * 80)
    print("STEP 1: Close CHF, MXN, SEK positions (convert to USD)")
    print("=" * 80)
    
    print(f"\n💱 Converting {len(step1_trades)} currencies to USD:\n")
    
    for currency, balance, pair, direction in step1_trades:
        position_type = "LONG" if balance > 0 else "SHORT"
        action = "BUY" if direction == "LONG" else "SELL"
        print(f"  {currency:5} {position_type:5} ${balance:>15,.2f} → {action} {pair}")
    
    response = input(f"\n⚠️  Execute Step 1? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("❌ Cancelled by user")
        sys.exit(0)
    
    print("\n🚀 Executing Step 1 trades...\n")
    
    for i, (currency, balance, pair, direction) in enumerate(step1_trades, 1):
        abs_qty = abs(balance)
        action_text = "BUY" if direction == "LONG" else "SELL"
        
        print(f"[{i}/{len(step1_trades)}] {currency}: {action_text} {abs_qty:,.2f} via {pair}...")
        
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
            
            if i < len(step1_trades):
                time.sleep(2)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n⏳ Waiting 5 seconds for fills...")
    time.sleep(5)
    
    # Check current USD balance
    print("\n📊 Checking USD balance after Step 1...")
    from ib_insync import IB
    ib = broker.ib
    time.sleep(2)
    
    account_values = ib.accountValues()
    usd_balance = 0
    
    for av in account_values:
        if av.tag == 'CashBalance' and av.currency == 'USD':
            try:
                usd_balance = float(av.value)
                break
            except:
                pass
    
    print(f"💵 USD Balance: ${usd_balance:,.2f}")
    
    if abs(usd_balance) < 1:
        print("✅ USD balance negligible, no need for Step 2")
    else:
        print("\n" + "=" * 80)
        print("STEP 2: Convert USD to CAD")
        print("=" * 80)
        
        usd_position_type = "LONG" if usd_balance > 0 else "SHORT"
        
        # Determine direction for USDCAD
        # If USD balance is positive (long USD) → SELL USD → SELL USDCAD (SHORT)
        # If USD balance is negative (short USD) → BUY USD → BUY USDCAD (LONG)
        direction = "SHORT" if usd_balance > 0 else "LONG"
        action_text = "SELL" if usd_balance > 0 else "BUY"
        
        print(f"\n💱 Converting USD to CAD:")
        print(f"  USD   {usd_position_type:5} ${usd_balance:>15,.2f} → {action_text} USDCAD\n")
        
        response = input(f"⚠️  Execute Step 2? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Step 2 cancelled")
        else:
            print("\n🚀 Executing Step 2 trade...\n")
            
            abs_qty = abs(usd_balance)
            
            order = {
                "instrument": "USDCAD",
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
                
                print("\n⏳ Waiting 5 seconds for fill...")
                time.sleep(5)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("✅ All forex closing trades completed!")
    print("=" * 80)
    print("\nℹ️  Run check_cash_balances.py to verify all positions are closed")
    
finally:
    print("\n👋 Disconnecting...")
    broker.disconnect()
    print("Done!")
