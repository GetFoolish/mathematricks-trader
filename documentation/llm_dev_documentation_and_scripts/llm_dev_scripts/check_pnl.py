#!/usr/bin/env python3
import json
import sys
import os

# Change to project root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(script_dir, '..', '..')
os.chdir(project_root)

# Read all signals from test results and analyze PnL calculations
with open('test_results/signal_test_mock_mock_20260202_172852_results.json') as f:
    data = json.load(f)

signals = data.get('all_signals_summary', [])

# Filter for TSLA signals with SHORT positions (signal 009)
for sig in signals:
    if 'sig_tech_stocks_009' in sig.get('signal_id', ''):
        print("=" * 80)
        print(f"Signal ID: {sig['signal_id']}")
        print(f"Instrument: {sig.get('instrument')}")
        print(f"Strategy: {sig.get('strategy_id')}")
        print("=" * 80)
        print()
        
        # Show both legs
        legs = sig.get('legs', [])
        entry_price = None
        entry_qty = None
        exit_price = None
        exit_qty = None
        
        for i, leg in enumerate(legs):
            leg_type = leg.get('leg_type', 'N/A')
            print(f"Leg {i} ({leg_type}):")
            raw = leg.get('raw', {})
            print(f"  Raw Action: {raw.get('action')}")
            print(f"  Raw Price: ${raw.get('price', 0)}")
            print(f"  Raw Quantity: {raw.get('quantity', 0)}")
            
            exec_data = leg.get('execution', {})
            if exec_data:
                filled_qty = exec_data.get('total_quantity_filled', 0)
                fill_price = exec_data.get('weighted_avg_price', 0)
                print(f"  Filled Qty: {filled_qty}")
                print(f"  Avg Fill Price: ${fill_price:.2f}")
                
                if leg_type == 'ENTRY':
                    entry_price = fill_price
                    entry_qty = filled_qty
                elif leg_type == 'EXIT':
                    exit_price = fill_price
                    exit_qty = filled_qty
            print()
        
        # Manual PnL calculation for verification
        if entry_price and exit_price and entry_qty == exit_qty:
            # For SHORT: Sell HIGH (entry), Buy LOW (exit) = profit
            # PnL = (entry_price - exit_price) * quantity
            print("Manual PnL Verification:")
            print(f"  Entry (SHORT): SELL {entry_qty} @ ${entry_price:.2f}")
            print(f"  Exit (CLOSE): BUY {exit_qty} @ ${exit_price:.2f}")
            
            # Check action to determine if LONG or SHORT
            entry_action = legs[0].get('raw', {}).get('action')
            if entry_action == 'SELL':
                # SHORT position: profit when exit price < entry price
                manual_pnl = (entry_price - exit_price) * entry_qty
                print(f"  Direction: SHORT (SELL then BUY)")
                print(f"  Formula: (Entry - Exit) * Qty = ({entry_price} - {exit_price}) * {entry_qty}")
            else:
                # LONG position: profit when exit price > entry price
                manual_pnl = (exit_price - entry_price) * entry_qty
                print(f"  Direction: LONG (BUY then SELL)")
                print(f"  Formula: (Exit - Entry) * Qty = ({exit_price} - {entry_price}) * {entry_qty}")
                
            print(f"  Expected Gross PnL: ${manual_pnl:.2f}")
            print()
        
        # Show position and PnL from system
        pos = sig.get('position', {})
        print(f"System Calculated:")
        print(f"  Position Status: {pos.get('status')}")
        pnl = pos.get('pnl', {})
        if pnl:
            print(f"  Gross PnL: ${pnl.get('gross', 0):.2f}")
            print(f"  Net PnL: ${pnl.get('net', 0):.2f}")
            print(f"  Percent: {pnl.get('percent', 0):.4f}%")
            print(f"  Commission: ${pnl.get('commission', 0):.2f}")
            
            # Verify calculation
            if entry_price and exit_price:
                entry_action = legs[0].get('raw', {}).get('action')
                if entry_action == 'SELL':
                    expected = (entry_price - exit_price) * entry_qty
                else:
                    expected = (exit_price - entry_price) * entry_qty
                    
                actual = pnl.get('gross', 0)
                print()
                if abs(expected - actual) < 0.01:
                    print(f"  ✅ PnL CORRECT: Expected ${expected:.2f} = Actual ${actual:.2f}")
                else:
                    print(f"  ❌ PnL MISMATCH: Expected ${expected:.2f} != Actual ${actual:.2f}")
                    print(f"  ❌ Difference: ${abs(expected - actual):.2f}")
        print()

print("\nChecking ALL signals for PnL correctness...")
print("=" * 80)

all_correct = True
for sig in signals:
    signal_id = sig.get('signal_id', '')
    legs = sig.get('legs', [])
    pos = sig.get('position', {})
    
    if pos.get('status') != 'CLOSED':
        continue
        
    # Extract prices
    entry_leg = next((l for l in legs if l.get('leg_type') == 'ENTRY'), None)
    exit_leg = next((l for l in legs if l.get('leg_type') == 'EXIT'), None)
    
    if not entry_leg or not exit_leg:
        continue
        
    entry_exec = entry_leg.get('execution', {})
    exit_exec = exit_leg.get('execution', {})
    
    if not entry_exec or not exit_exec:
        continue
        
    entry_price = entry_exec.get('weighted_avg_price', 0)
    exit_price = exit_exec.get('weighted_avg_price', 0)
    entry_qty = entry_exec.get('total_quantity_filled', 0)
    exit_qty = exit_exec.get('total_quantity_filled', 0)
    
    if entry_qty != exit_qty:
        print(f"⚠️  {signal_id}: Qty mismatch (entry={entry_qty}, exit={exit_qty})")
        continue
    
    # Determine direction
    entry_action = entry_leg.get('raw', {}).get('action')
    if entry_action == 'SELL':
        # SHORT
        expected_pnl = (entry_price - exit_price) * entry_qty
        direction = 'SHORT'
    else:
        # LONG
        expected_pnl = (exit_price - entry_price) * entry_qty
        direction = 'LONG'
    
    actual_pnl = pos.get('pnl', {}).get('gross', 0)
    
    diff = abs(expected_pnl - actual_pnl)
    if diff > 0.01:
        all_correct = False
        print(f"❌ {signal_id} ({direction}):")
        print(f"   Entry: ${entry_price:.2f} x {entry_qty}")
        print(f"   Exit: ${exit_price:.2f} x {exit_qty}")
        print(f"   Expected PnL: ${expected_pnl:.2f}")
        print(f"   Actual PnL: ${actual_pnl:.2f}")
        print(f"   DIFF: ${diff:.2f}")
    else:
        print(f"✅ {signal_id} ({direction}): ${actual_pnl:.2f} (correct)")

if all_correct:
    print("\n✅ All PnL calculations are CORRECT!")
else:
    print("\n❌ Some PnL calculations have errors!")
