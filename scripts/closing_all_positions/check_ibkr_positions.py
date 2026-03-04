#!/usr/bin/env python3
"""Check and close all IBKR positions"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from brokers.ibkr.ibkr_broker import IBKRBroker

def main():
    broker = IBKRBroker('IBKR-PAPER')
    broker.connect()
    
    positions = broker.ib.positions()
    
    print(f"\n{'='*60}")
    print(f"IBKR Open Positions: {len(positions)}")
    print(f"{'='*60}\n")
    
    if positions:
        for p in positions:
            print(f"Symbol: {p.contract.symbol}")
            print(f"  Position: {p.position}")
            print(f"  Avg Cost: ${p.avgCost:.2f}")
            print(f"  Market Value: ${p.marketValue:.2f}")
            print(f"  Unrealized PnL: ${p.unrealizedPNL:.2f}")
            print()
    else:
        print("No open positions")
    
    broker.disconnect()

if __name__ == "__main__":
    main()
