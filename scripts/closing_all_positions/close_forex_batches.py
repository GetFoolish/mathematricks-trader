#!/usr/bin/env python3
"""
Close SEK and MXN forex positions in small batches.

Current positions:
- SEK: -$23,107,950.20 (SHORT SEK)
- MXN: -$4,523,210.98 (SHORT MXN)

Strategy:
1. Close 10% at a time
2. Verify after each batch
3. Use correct direction: SHORT (SELL USDXXX to buy back XXX)
"""

import sys
import time
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent / "services"))

from brokers.ibkr.ibkr_broker import IBKRBroker


def check_balances(broker: IBKRBroker):
    """Check current cash balances."""
    print("\n" + "=" * 80)
    print("CURRENT CASH BALANCES")
    print("=" * 80)
    
    account_values = broker.ib.accountValues()
    
    balances = {}
    for item in account_values:
        if item.tag == "CashBalance" and item.currency != "BASE":
            balance = float(item.value)
            if abs(balance) > 0.01:  # Only show non-zero balances
                balances[item.currency] = balance
    
    for currency in sorted(balances.keys()):
        balance = balances[currency]
        print(f"{currency:5s}: ${balance:,.2f}")
    
    print("=" * 80)
    return balances


def close_batch(broker: IBKRBroker, currency: str, pair: str, amount: float, batch_pct: float = 0.10):
    """
    Close a batch of a forex position.
    
    Args:
        broker: IBKRBroker instance
        currency: Currency code (SEK, MXN)
        pair: Forex pair (USDSEK, USDMXN)
        amount: Current balance (negative = short)
        batch_pct: Percentage to close (0.10 = 10%)
    """
    if abs(amount) < 1:
        print(f"\n{currency}: Position too small (${amount:.2f}), skipping")
        return True
    
    # Calculate batch size
    batch_amount = abs(amount) * batch_pct
    
    print(f"\n" + "=" * 80)
    print(f"CLOSING {currency} BATCH")
    print("=" * 80)
    print(f"Current position: ${amount:,.2f} (SHORT {currency})")
    print(f"Batch size: {batch_pct*100:.0f}% = ${batch_amount:,.2f}")
    print(f"Pair: {pair}")
    
    # For SHORT position (negative balance), we need to BUY back the currency
    # USDSEK/USDMXN: USD is base, XXX is quote
    # To BUY SEK/MXN = SELL USD for SEK/MXN = SELL (SHORT) the pair
    direction = "SHORT"
    print(f"Direction: {direction} (SELL {pair} to buy {currency})")
    
    # Create order
    order = {
        "instrument": pair,
        "instrument_type": "FOREX",
        "direction": direction,
        "quantity": batch_amount,
        "order_type": "MARKET",
        "account_id": "IBKR-PAPER",
        "mode": "paper_live",
        "fund_id": "test-fund",
        "strategy_id": "manual-close",
    }
    
    print(f"\nOrder: {direction} {batch_amount:,.2f} {pair}")
    print("Placing order...")
    
    try:
        result = broker.place_order(order)
        print(f"\n✅ Order placed successfully!")
        print(f"Result: {result}")
        return True
        
    except Exception as e:
        print(f"\n❌ Order failed: {e}")
        return False


def main():
    """Main function to close positions in batches."""
    print("=" * 80)
    print("CLOSE FOREX POSITIONS IN BATCHES")
    print("=" * 80)
    
    # Initialize broker
    config = {
        "host": "127.0.0.1",
        "port": 55858,
        "client_id": 206
    }
    broker = IBKRBroker(config)
    print("\nConnecting to IBKR...")
    broker.connect()
    
    if not broker.is_connected():
        print("❌ Failed to connect to IBKR")
        return
    
    print("✅ Connected to IBKR")
    
    try:
        # Check initial balances
        balances = check_balances(broker)
        
        sek_balance = balances.get("SEK", 0)
        mxn_balance = balances.get("MXN", 0)
        
        print(f"\nPositions to close:")
        print(f"  SEK: ${sek_balance:,.2f}")
        print(f"  MXN: ${mxn_balance:,.2f}")
        
        # Batch size (10% at a time)
        batch_pct = 0.10
        max_batches = 10  # Don't exceed 10 batches per currency
        
        # Close SEK in batches
        if abs(sek_balance) > 1:
            print(f"\n{'=' * 80}")
            print(f"PROCESSING SEK BATCHES")
            print(f"{'=' * 80}")
            
            for i in range(max_batches):
                # Get current balance
                balances = check_balances(broker)
                sek_balance = balances.get("SEK", 0)
                
                if abs(sek_balance) < 1:
                    print(f"\n✅ SEK position closed!")
                    break
                
                print(f"\n--- SEK Batch {i+1}/{max_batches} ---")
                success = close_batch(
                    broker, "SEK", "USDSEK", sek_balance, batch_pct
                )
                
                if not success:
                    print(f"\n⚠️ SEK batch {i+1} failed, stopping SEK closes")
                    break
                
                # Wait a bit for order to process
                time.sleep(2)
        
        # Close MXN in batches
        if abs(mxn_balance) > 1:
            print(f"\n{'=' * 80}")
            print(f"PROCESSING MXN BATCHES")
            print(f"{'=' * 80}")
            
            for i in range(max_batches):
                # Get current balance
                balances = check_balances(broker)
                mxn_balance = balances.get("MXN", 0)
                
                if abs(mxn_balance) < 1:
                    print(f"\n✅ MXN position closed!")
                    break
                
                print(f"\n--- MXN Batch {i+1}/{max_batches} ---")
                success = close_batch(
                    broker, "MXN", "USDMXN", mxn_balance, batch_pct
                )
                
                if not success:
                    print(f"\n⚠️ MXN batch {i+1} failed, stopping MXN closes")
                    
                    # Check if it's a margin error
                    balances = check_balances(broker)
                    mxn_balance = balances.get("MXN", 0)
                    print(f"\nRemaining MXN: ${mxn_balance:,.2f}")
                    
                    print("\n⚠️ MXN position may be too large for available margin.")
                    print("Consider resetting IBKR paper account.")
                    break
                
                # Wait a bit for order to process
                time.sleep(2)
        
        # Final balance check
        print("\n" + "=" * 80)
        print("FINAL BALANCES")
        print("=" * 80)
        check_balances(broker)
        
    finally:
        broker.disconnect()
        print("\n✅ Disconnected from IBKR")


if __name__ == "__main__":
    main()
