#!/usr/bin/env python3
"""
Close all forex positions (convert foreign currency balances to base currency)
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
    "client_id": 202,  # Different client ID
    "account_id": "IBKR-PAPER"
}

# Forex pairs mapping - use CAD pairs where available since base is CAD
# Format: (currency, pair, is_base_first)
# is_base_first = True means currency is base (e.g., AUDCAD = AUD is base)
# is_base_first = False means currency is quote (e.g., CADJPY = JPY is quote)
FOREX_PAIRS = {
    'AUD': ('AUDCAD', True),   # AUD is base
    'CHF': ('CADCHF', False),  # CHF is quote
    'EUR': ('EURCAD', True),   # EUR is base
    'GBP': ('GBPCAD', True),   # GBP is base
    'MXN': ('CADMXN', False),  # MXN is quote
    'NZD': ('NZDCAD', True),   # NZD is base
    'SEK': ('CADSEK', False),  # SEK is quote
}

print("🔌 Connecting to IBKR...")
broker = IBKRBroker(config)

try:
    broker.connect()
    print("✅ Connected!\n")
    
    print("💱 Fetching forex positions...")
    from ib_insync import IB
    
    # Get raw account summary to find forex balances
    ib = broker.ib
    time.sleep(1)
    account_summary = ib.accountSummary()
    
    # Find non-zero cash balances in foreign currencies
    forex_positions = {}
    for item in account_summary:
        if item.tag == 'CashBalance' and item.currency not in ['BASE', 'USD', 'CAD']:
            try:
                amount = float(item.value)
                if abs(amount) > 0.01:  # Only non-zero
                    forex_positions[item.currency] = amount
            except:
                pass
    
    if not forex_positions:
        print("✅ No forex positions to close!")
    else:
        print(f"\n✅ Found {len(forex_positions)} forex position(s) to close:\n")
        
        # Display positions
        for currency, amount in sorted(forex_positions.items()):
            position_type = "LONG" if amount > 0 else "SHORT"
            close_action = "SELL" if amount > 0 else "BUY"
            print(f"  {currency:5} {position_type:5} ${amount:>12,.2f} → {close_action}")
        
        # Ask for confirmation
        response = input(f"\n⚠️  Close ALL forex positions? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Cancelled by user")
        else:
            print("\n🚀 Closing forex positions...\n")
            
            for i, (currency, balance) in enumerate(sorted(forex_positions.items()), 1):
                if currency not in FOREX_PAIRS:
                    print(f"[{i}/{len(forex_positions)}] Skipping {currency}: No pair mapping defined")
                    continue
                
                pair, is_base_first = FOREX_PAIRS[currency]
                
                # Determine order direction
                # For base currency (e.g., EURCAD where EUR is base):
                #   - Positive balance = long EUR → SELL EURCAD (SHORT) to convert to CAD
                #   - Negative balance = short EUR → BUY EURCAD (LONG) to cover
                # For quote currency (e.g., CADCHF where CHF is quote):
                #   - Positive balance = long CHF → BUY CADCHF (LONG) to convert CHF to CAD
                #   - Negative balance = short CHF → SELL CADCHF (SHORT) to cover
                if is_base_first:
                    # Currency is the base in the pair
                    direction = "SHORT" if balance > 0 else "LONG"
                else:
                    # Currency is the quote in the pair
                    direction = "LONG" if balance > 0 else "SHORT"
                
                action_text = "BUY" if balance < 0 else "SELL"
                abs_qty = abs(balance)
                
                print(f"[{i}/{len(forex_positions)}] Closing {currency}: {action_text} {abs_qty:,.2f} via {pair} ({direction})...")
                
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
                    if i < len(forex_positions):
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"  ❌ Error: {e}")
            
            print("\n⏳ Waiting 3 seconds for fills...")
            time.sleep(3)
            
            # Check remaining forex positions
            print("\n📊 Checking remaining forex positions...")
            account_summary = ib.accountSummary()
            
            remaining = {}
            for item in account_summary:
                if item.tag == 'CashBalance' and item.currency not in ['BASE', 'USD', 'CAD']:
                    try:
                        amount = float(item.value)
                        if abs(amount) > 0.01:
                            remaining[item.currency] = amount
                    except:
                        pass
            
            if not remaining:
                print("✅ All forex positions closed successfully!")
            else:
                print(f"⚠️  {len(remaining)} forex position(s) still open:")
                for currency, amount in sorted(remaining.items()):
                    print(f"  {currency}: ${amount:,.2f}")
    
finally:
    print("\n👋 Disconnecting...")
    broker.disconnect()
    print("Done!")
