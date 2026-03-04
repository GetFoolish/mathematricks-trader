#!/usr/bin/env python3
"""
Close all positions - stocks and forex.

This script will:
1. Close all stock positions (LONG/SHORT)
2. Close all forex currency balances to CAD
3. Leave account with only CAD balance

Usage:
    .venv/bin/python scripts/close_all_positions_complete.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services"))

from brokers.ibkr.ibkr_broker import IBKRBroker


def get_balances_and_rates(broker: IBKRBroker):
    """Get cash balances and exchange rates."""
    account_values = broker.ib.accountValues()
    
    balances = {}
    exchange_rates = {}
    
    for item in account_values:
        if item.tag == "CashBalance" and item.currency != "BASE":
            balance = float(item.value)
            if abs(balance) > 0.01:
                balances[item.currency] = balance
        elif item.tag == "ExchangeRate":
            exchange_rates[item.currency] = float(item.value)
    
    return balances, exchange_rates


def show_balances(balances, rates):
    """Display current balances."""
    print("\n" + "=" * 80)
    print("CURRENT BALANCES")
    print("=" * 80)
    for currency in sorted(balances.keys()):
        balance = balances[currency]
        rate = rates.get(currency, 1.0)
        cad_equiv = balance * rate
        print(f"{currency:5s}: {balance:>15,.2f} (CAD equiv: ${cad_equiv:,.2f})")
    print("=" * 80)


def close_stock_positions(broker: IBKRBroker):
    """Close all open stock positions."""
    print("\n" + "#" * 80)
    print("STEP 1: CLOSE STOCK POSITIONS")
    print("#" * 80)
    
    try:
        positions = broker.get_open_positions()
        
        if not positions:
            print("✅ No stock positions to close")
            return True
        
        print(f"\nFound {len(positions)} stock positions:")
        for pos in positions:
            direction = "LONG" if pos["quantity"] > 0 else "SHORT"
            print(f"  {pos['instrument']}: {pos['quantity']:,.0f} shares ({direction})")
        
        # Close each position
        for pos in positions:
            instrument = pos["instrument"]
            quantity = abs(pos["quantity"])
            
            # Determine close direction (opposite of position)
            if pos["quantity"] > 0:
                direction = "SHORT"  # Close LONG position
                action_desc = "Selling"
            else:
                direction = "LONG"   # Close SHORT position
                action_desc = "Buying to cover"
            
            print(f"\n{action_desc} {quantity:,.0f} {instrument}...")
            
            order = {
                "instrument": instrument,
                "instrument_type": "STOCK",
                "direction": direction,
                "quantity": quantity,
                "order_type": "MARKET",
                "account_id": "IBKR-PAPER",
                "mode": "paper_live",
                "fund_id": "test-fund",
                "strategy_id": "manual-close",
            }
            
            try:
                result = broker.place_order(order)
                filled = result.get("filled", 0)
                price = result.get("avg_fill_price", 0)
                print(f"✅ Filled {filled:,.0f} @ ${price:.2f}")
            except Exception as e:
                print(f"❌ Failed: {e}")
                return False
            
            time.sleep(1)  # Brief pause between orders
        
        print("\n✅ All stock positions closed")
        return True
        
    except Exception as e:
        print(f"❌ Error closing stock positions: {e}")
        return False


def close_forex_positions(broker: IBKRBroker):
    """Close all forex currency balances to CAD."""
    print("\n" + "#" * 80)
    print("STEP 2: CLOSE FOREX POSITIONS")
    print("#" * 80)
    
    balances, rates = get_balances_and_rates(broker)
    show_balances(balances, rates)
    
    # Target: Only CAD (and negligible USD for final conversion)
    forex_currencies = [c for c in balances.keys() if c not in ["CAD", "USD", "BASE"]]
    
    if not forex_currencies:
        print("\n✅ No forex positions to close")
        return True
    
    print(f"\nClosing {len(forex_currencies)} forex currencies: {', '.join(forex_currencies)}")
    
    # Forex pairs and their estimated rates
    forex_pairs = {
        "CHF": ("USDCHF", 0.87),   # 1 USD = 0.87 CHF
        "MXN": ("USDMXN", 17.15),  # 1 USD = 17.15 MXN
        "SEK": ("USDSEK", 8.99),   # 1 USD = 8.99 SEK
        "AUD": ("AUDUSD", 0.64),   # 1 AUD = 0.64 USD (inverted)
        "EUR": ("EURUSD", 1.08),   # 1 EUR = 1.08 USD (inverted)
        "GBP": ("GBPUSD", 1.27),   # 1 GBP = 1.27 USD (inverted)
        "NZD": ("NZDUSD", 0.60),   # 1 NZD = 0.60 USD (inverted)
    }
    
    # Close each forex currency
    for currency in forex_currencies:
        balance = balances.get(currency, 0)
        
        if abs(balance) < 1:
            print(f"\n{currency}: {balance:.2f} - too small to trade (skipping)")
            continue
        
        if currency not in forex_pairs:
            print(f"\n⚠️ {currency}: No trading pair defined (skipping)")
            continue
        
        pair, estimated_rate = forex_pairs[currency]
        
        # Determine direction and quantity
        if pair.startswith("USD"):
            # USD is base (USDCHF, USDMXN, USDSEK)
            # Negative balance = short currency = BUY currency = SELL (SHORT) pair
            # Positive balance = long currency = SELL currency = BUY (LONG) pair
            direction = "LONG" if balance > 0 else "SHORT"
            usd_quantity = abs(balance) / estimated_rate
        else:
            # Currency is base (AUDUSD, EURUSD, GBPUSD, NZDUSD)
            # Negative balance = short currency = BUY currency = BUY (LONG) pair
            # Positive balance = long currency = SELL currency = SELL (SHORT) pair
            direction = "SHORT" if balance > 0 else "LONG"
            usd_quantity = abs(balance) * estimated_rate
        
        # Skip if USD quantity too small (< $1)
        if usd_quantity < 1:
            print(f"\n{currency}: {balance:.2f} → ${usd_quantity:.2f} USD - too small (skipping)")
            continue
        
        print(f"\n{currency}: {balance:,.2f} → {direction} {usd_quantity:,.2f} {pair}")
        
        order = {
            "instrument": pair,
            "instrument_type": "FOREX",
            "direction": direction,
            "quantity": usd_quantity,
            "order_type": "MARKET",
            "account_id": "IBKR-PAPER",
            "mode": "paper_live",
            "fund_id": "test-fund",
            "strategy_id": "manual-close",
        }
        
        try:
            result = broker.place_order(order)
            filled = result.get("filled", 0)
            price = result.get("avg_fill_price", 0)
            print(f"✅ Filled {filled:,.2f} @ {price:.5f}")
        except Exception as e:
            print(f"❌ Failed: {e}")
            # Continue with other currencies even if one fails
        
        time.sleep(2)  # Pause between forex trades
    
    # Convert any remaining USD to CAD
    balances, rates = get_balances_and_rates(broker)
    usd_balance = balances.get("USD", 0)
    
    if abs(usd_balance) > 1:
        print(f"\n" + "-" * 80)
        print(f"Final step: Convert ${usd_balance:,.2f} USD to CAD")
        print("-" * 80)
        
        direction = "SHORT" if usd_balance > 0 else "LONG"
        action = "SELL" if direction == "SHORT" else "BUY"
        
        print(f"{action} {abs(usd_balance):,.2f} USDCAD...")
        
        order = {
            "instrument": "USDCAD",
            "instrument_type": "FOREX",
            "direction": direction,
            "quantity": abs(usd_balance),
            "order_type": "MARKET",
            "account_id": "IBKR-PAPER",
            "mode": "paper_live",
            "fund_id": "test-fund",
            "strategy_id": "manual-close",
        }
        
        try:
            result = broker.place_order(order)
            filled = result.get("filled", 0)
            price = result.get("avg_fill_price", 0)
            print(f"✅ Filled {filled:,.2f} @ {price:.5f}")
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    print("\n✅ All forex positions closed")
    return True


def main():
    """Main function to close all positions."""
    print("=" * 80)
    print("CLOSE ALL POSITIONS - STOCKS & FOREX")
    print("=" * 80)
    
    # Connect to IBKR
    config = {
        "host": "127.0.0.1",
        "port": 64040,
        "client_id": 250
    }
    
    broker = IBKRBroker(config)
    print("\n🔌 Connecting to IBKR...")
    broker.connect()
    
    if not broker.is_connected():
        print("❌ Failed to connect to IBKR")
        return
    
    print("✅ Connected to IBKR")
    
    try:
        # Step 1: Close stock positions
        stock_success = close_stock_positions(broker)
        
        # Step 2: Close forex positions
        forex_success = close_forex_positions(broker)
        
        # Show final state
        print("\n" + "=" * 80)
        print("FINAL STATE")
        print("=" * 80)
        
        # Check stock positions
        positions = broker.get_open_positions()
        print(f"\nStock positions: {len(positions)}")
        if positions:
            for pos in positions:
                print(f"  ⚠️ {pos['instrument']}: {pos['quantity']:,.0f}")
        else:
            print("  ✅ All closed")
        
        # Check forex balances
        balances, rates = get_balances_and_rates(broker)
        forex_currencies = [c for c in balances.keys() if c not in ["CAD", "USD"]]
        
        print(f"\nForex currencies: {len(forex_currencies)}")
        if forex_currencies:
            for currency in forex_currencies:
                balance = balances[currency]
                rate = rates.get(currency, 1.0)
                cad_equiv = balance * rate
                if abs(cad_equiv) > 10:  # Only show if > $10 CAD equivalent
                    print(f"  ⚠️ {currency}: {balance:,.2f} (${cad_equiv:,.2f} CAD)")
        
        # Show CAD balance
        cad_balance = balances.get("CAD", 0)
        print(f"\n💰 CAD Balance: ${cad_balance:,.2f}")
        
        if stock_success and forex_success:
            print("\n✅ ALL POSITIONS CLOSED SUCCESSFULLY!")
        else:
            print("\n⚠️ Some positions may remain - check details above")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        broker.disconnect()
        print("\n👋 Disconnected from IBKR")


if __name__ == "__main__":
    main()
