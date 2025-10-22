#!/usr/bin/env python3
"""Quick test to send SPY signal (should be approved with 6.54% allocation)"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from live_signal_tester import LiveSignalTester
import time

tester = LiveSignalTester(account='DU1234567')

print("=" * 100)
print("TESTING SPY ENTRY SIGNAL (should be APPROVED with 6.54% allocation)")
print("=" * 100)

# Get account state
account_state = tester.get_account_state()

# Generate SPY ENTRY signal
entry_signal = tester.generate_test_signal(
    strategy_id='SPY',
    instrument='SPY',
    direction='LONG',
    action='BUY',
    price=450.25,
    quantity=50
)

print(f"\nSending ENTRY signal: {entry_signal['signalID']}")
if tester.send_signal(entry_signal):
    print("✅ Signal sent! Waiting for processing...")
    time.sleep(2)
    
    # Fetch results
    decision = tester.fetch_cerebro_decision(entry_signal['signalID'])
    order = tester.fetch_execution_order(entry_signal['signalID'])
    
    # Wait for execution
    execution = None
    if order and order.get('status') != 'REJECTED':
        print("⏳ Waiting for execution confirmation from IBKR...")
        execution = tester.fetch_execution_confirmation(order.get('order_id'), max_wait=15)
    
    # Print analysis
    tester.print_signal_analysis(entry_signal, account_state, decision, order, execution)

print("\n" + "=" * 100)
print("Test complete!")
print("=" * 100)
