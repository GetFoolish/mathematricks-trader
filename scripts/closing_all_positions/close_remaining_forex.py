#!/usr/bin/env python3
"""
Clean up final small forex positions:
- CHF: -46.16 (short)
- MXN: -78,079.40 (short)
- SEK: -2.63 (short)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "services"))

from brokers.ibkr.ibkr_broker import IBKRBroker


def check_balances(broker: IBKRBroker):
    """Check current cash balances."""
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
    
    print("\n" + "=" * 80)
    for currency in sorted(balances.keys()):
        balance = balances[currency]
        rate = exchange_rates.get(currency, 1.0)
        cad_equiv = balance * rate
        print(f"{currency:5s}: {balance:>15,.2f} (CAD equiv: ${cad_equiv:,.2f})")
    print("=" * 80)
    
    return balances, exchange_rates


def place_trade(broker: IBKRBroker, pair: str, direction: str, quantity: float):
    """Place a forex trade."""
    print(f"\nTrade: {direction} {quantity:,.2f} {pair}")
    
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
        print(f"✅ Filled: {result.get('filled', 0):,.2f} @ {result.get('avg_fill_price', 0):.5f}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def main():
    """Close small remaining forex positions."""
    config = {
        "host": "127.0.0.1",
        "port": 55858,
        "client_id": 210
    }
    broker = IBKRBroker(config)
    broker.connect()
    
    if not broker.is_connected():
        print("❌ Failed to connect")
        return
    
    print("✅ Connected to IBKR")
    
    try:
        balances, rates = check_balances(broker)
        
        # Close CHF short: -46.16 CHF (short) → BUY CHF = SHORT USDCHF
        chf = balances.get("CHF", 0)
        if abs(chf) > 1:
            print(f"\n{'#' * 80}")
            print(f"Close CHF: {chf:,.2f} CHF (short)")
            print(f"Action: BUY CHF = SHORT USDCHF")
            print(f"{'#' * 80}")
            
            # Convert CHF to USD: CHF amount / USDCHF rate
            usd_qty = abs(chf) / 0.87  # USDCHF ≈ 0.87
            place_trade(broker, "USDCHF", "SHORT", usd_qty)
            time.sleep(2)
        
        # Close MXN short: -78,079.40 MXN (short) → BUY MXN = SHORT USDMXN
        balances, rates = check_balances(broker)
        mxn = balances.get("MXN", 0)
        if abs(mxn) > 1:
            print(f"\n{'#' * 80}")
            print(f"Close MXN: {mxn:,.2f} MXN (short)")
            print(f"Action: BUY MXN = SHORT USDMXN")
            print(f"{'#' * 80}")
            
            # Convert MXN to USD
            usd_qty = abs(mxn) / 17.15  # USDMXN ≈ 17.15
            place_trade(broker, "USDMXN", "SHORT", usd_qty)
            time.sleep(2)
        
        # Close SEK short: -2.63 SEK (short) → BUY SEK = SHORT USDSEK
        balances, rates = check_balances(broker)
        sek = balances.get("SEK", 0)
        if abs(sek) > 1:
            print(f"\n{'#' * 80}")
            print(f"Close SEK: {sek:,.2f} SEK (short)")
            print(f"Action: BUY SEK = SHORT USDSEK")
            print(f"{'#' * 80}")
            
            # Convert SEK to USD
            usd_qty = abs(sek) / 8.99  # USDSEK ≈ 8.99
            place_trade(broker, "USDSEK", "SHORT", usd_qty)
            time.sleep(2)
        
        # Convert any final USD to CAD
        balances, rates = check_balances(broker)
        usd = balances.get("USD", 0)
        if abs(usd) > 1:
            print(f"\n{'#' * 80}")
            print(f"Convert USD to CAD: {usd:,.2f} USD")
            print(f"{'#' * 80}")
            direction = "SHORT" if usd > 0 else "LONG"
            place_trade(broker, "USDCAD", direction, abs(usd))
            time.sleep(2)
        
        print(f"\n{'=' * 80}")
        print("FINAL BALANCES")
        print(f"{'=' * 80}")
        check_balances(broker)
        
    finally:
        broker.disconnect()
        print("\n✅ Disconnected")


if __name__ == "__main__":
    main()
