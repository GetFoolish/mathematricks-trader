#!/usr/bin/env python3
import json

with open('test_results/signal_test_mock_mock_20260202_174433_results.json') as f:
    data = json.load(f)

for sig in data.get('all_signals_summary', []):
    if 'sig_tech_stocks_009' in sig.get('signal_id', ''):
        print("=" * 80)
        print(f"Signal: {sig['signal_id']}")
        print(f"Instrument: {sig.get('instrument')}")
        print("=" * 80)
        
        legs = sig.get('legs', [])
        entry_action = legs[0].get('raw', {}).get('action') if legs else None
        entry_price = legs[0].get('execution', {}).get('weighted_avg_price', 0) if legs else 0
        entry_qty = legs[0].get('execution', {}).get('total_quantity_filled', 0) if legs else 0
        
        exit_price = legs[1].get('execution', {}).get('weighted_avg_price', 0) if len(legs) > 1 else 0
        exit_qty = legs[1].get('execution', {}).get('total_quantity_filled', 0) if len(legs) > 1 else 0
        
        print(f"\nEntry: {entry_action} {entry_qty} @ ${entry_price:.2f}")
        print(f"Exit: BUY {exit_qty} @ ${exit_price:.2f}")
        
        # Manual calculation
        if entry_action == 'SELL':
            expected_pnl = (entry_price - exit_price) * entry_qty
            print(f"\nDirection: SHORT")
            print(f"Expected PnL: (${entry_price} - ${exit_price}) × {entry_qty} = ${expected_pnl:.2f}")
        else:
            expected_pnl = (exit_price - entry_price) * entry_qty
            print(f"\nDirection: LONG")
            print(f"Expected PnL: (${exit_price} - ${entry_price}) × {entry_qty} = ${expected_pnl:.2f}")
        
        pos = sig.get('position', {})
        pnl = pos.get('pnl', {})
        actual_pnl = pnl.get('gross', 0)
        
        print(f"\nSystem Calculated:")
        print(f"  Position Status: {pos.get('status')}")
        print(f"  Gross PnL: ${actual_pnl:.2f}")
        print(f"  Net PnL: ${pnl.get('net', 0):.2f}")
        
        if abs(expected_pnl - actual_pnl) < 0.01:
            print(f"\n✅ PnL CORRECT!")
        else:
            print(f"\n❌ PnL WRONG! Expected ${expected_pnl:.2f}, got ${actual_pnl:.2f}")
            print(f"   Difference: ${abs(expected_pnl - actual_pnl):.2f}")
        break
