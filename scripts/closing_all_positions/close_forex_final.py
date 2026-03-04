#!/usr/bin/env python3
"""
Final forex cleanup - two simple steps:
1. Close USD short by buying USD (BUY USDCAD)
2. Close MXN long by selling MXN for USD (BUY USDMXN)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "services"))

from brokers.ibkr.ibkr_broker import IBKRBroker


def check_balances(broker: IBKRBroker):
    """Check current cash balances (actual currency amounts)."""
    print("\n" + "=" * 80)
    print("CURRENT CASH BALANCES (Actual Currency Amounts)")
    print("=" * 80)
    
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
    
    for currency in sorted(balances.keys()):
        balance = balances[currency]
        rate = exchange_rates.get(currency, 1.0)
        cad_equiv = balance * rate
        print(f"{currency:5s}: {balance:>15,.2f} (CAD equiv: ${cad_equiv:,.2f})")
    
    print("=" * 80)
    return balances, exchange_rates


def place_trade(broker: IBKRBroker, description: str, pair: str, direction: str, quantity: float):
    """Place a forex trade."""
    print(f"\n{'=' * 80}")
    print(f"TRADE: {description}")
    print(f"{'=' * 80}")
    print(f"Pair: {pair}")
    print(f"Direction: {direction}")
    print(f"Quantity: {quantity:,.2f}")
    
    order = {
        "instrument": pair,
        "instrument_type": "FOREX",
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
        print(f"\n✅ Trade executed successfully!")
        print(f"Filled: {result.get('filled', 0):,.2f}")
        print(f"Price: {result.get('avg_fill_price', 0):.5f}")
        return True
    except Exception as e:
        print(f"\n❌ Trade failed: {e}")
        return False


def main():
    """Execute two-step forex cleanup."""
    print("=" * 80)
    print("FINAL FOREX CLEANUP")
    print("=" * 80)
    
    # Connect
    config = {
        "host": "127.0.0.1",
        "port": 55858,
        "client_id": 209
    }
    broker = IBKRBroker(config)
    print("\nConnecting to IBKR...")
    broker.connect()
    
    if not broker.is_connected():
        print("❌ Failed to connect")
        return
    
    print("✅ Connected")
    
    try:
        # Initial state
        balances, rates = check_balances(broker)
        usd_balance = balances.get("USD", 0)
        mxn_balance = balances.get("MXN", 0)  # Actual MXN amount
        
        print(f"\nStep 1: Close USD short ({usd_balance:,.2f} USD)")
        print(f"Step 2: Close MXN long ({mxn_balance:,.2f} MXN)")
        
        # STEP 1: Close USD short - BUY USD (BUY USDCAD = buy USD, sell CAD)
        if abs(usd_balance) > 1:
            print(f"\n{'#' * 80}")
            print("STEP 1: CLOSE USD SHORT")
            print(f"{'#' * 80}")
            print(f"Current: USD = {usd_balance:,.2f} (SHORT)")
            print(f"Action: BUY USD, SELL CAD")
            print(f"Trade: BUY (LONG) USDCAD")
            
            success = place_trade(
                broker,
                "Close USD short - Buy USD",
                "USDCAD",
                "LONG",
                abs(usd_balance)
            )
            
            if success:
                time.sleep(2)
                balances, rates = check_balances(broker)
                print(f"\n✅ Step 1 complete. USD balance: {balances.get('USD', 0):,.2f}")
            else:
                print("\n⚠️ Step 1 failed, stopping")
                return
        
        # STEP 2: Close MXN long - SELL MXN (BUY USDMXN = buy USD, sell MXN)
        balances, rates = check_balances(broker)
        mxn_balance = balances.get("MXN", 0)  # Actual MXN amount
        
        if abs(mxn_balance) > 1:
            # Convert MXN to USD for USDMXN trade
            # USDMXN ≈ 17.15, so 1 USD = 17.15 MXN
            estimated_usdmxn_rate = 17.0
            usd_quantity = abs(mxn_balance) / estimated_usdmxn_rate
            
            print(f"\n{'#' * 80}")
            print("STEP 2: CLOSE MXN LONG")
            print(f"{'#' * 80}")
            print(f"Current: MXN = {mxn_balance:,.2f} (LONG)")
            print(f"Estimated USDMXN rate: {estimated_usdmxn_rate}")
            print(f"USD quantity to trade: {usd_quantity:,.2f}")
            print(f"Action: SELL MXN, BUY USD")
            print(f"Trade: BUY (LONG) {usd_quantity:,.2f} USDMXN")
            
            success = place_trade(
                broker,
                "Close MXN long - Sell MXN for USD",
                "USDMXN",
                "LONG",
                usd_quantity
            )
            
            if success:
                time.sleep(2)
                balances, rates = check_balances(broker)
                print(f"\n✅ Step 2 complete. MXN balance: {balances.get('MXN', 0):,.2f}")
            else:
                print("\n⚠️ Step 2 failed")
                return
        
        # STEP 3: Convert final USD to CAD
        balances, rates = check_balances(broker)
        usd_balance = balances.get("USD", 0)
        
        if abs(usd_balance) > 1:
            print(f"\n{'#' * 80}")
            print("STEP 3: CONVERT USD TO CAD")
            print(f"{'#' * 80}")
            print(f"Current: USD = {usd_balance:,.2f}")
            print(f"Action: SELL USD, BUY CAD")
            
            # Determine direction
            direction = "SHORT" if usd_balance > 0 else "LONG"
            
            success = place_trade(
                broker,
                "Convert USD to CAD",
                "USDCAD",
                direction,
                abs(usd_balance)
            )
            
            if success:
                time.sleep(2)
                print(f"\n✅ Step 3 complete")
        
        # Final state
        print(f"\n{'=' * 80}")
        print("FINAL STATE")
        print(f"{'=' * 80}")
        check_balances(broker)
        
    finally:
        broker.disconnect()
        print("\n✅ Disconnected from IBKR")


if __name__ == "__main__":
    main()
