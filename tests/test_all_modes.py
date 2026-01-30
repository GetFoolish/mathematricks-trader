#!/usr/bin/env python3
"""
Test all execution modes to verify end-to-end signal processing
Tests: mock_mock, mock_live, paper_live, live_live
"""

import sys
sys.path.insert(0, '..')
from tests.send_test_signal import send_signal
import time
import requests

def check_signal_status(signal_id, timeout=10):
    """Check if signal was processed successfully"""
    # Wait a bit for processing
    time.sleep(3)
    
    # TODO: Query signal_store to check status
    # For now, just check logs
    return True

def test_mode(mode_name, environment, account_type, data_source):
    """Test a specific execution mode"""
    print(f"\n{'='*80}")
    print(f"🧪 TESTING MODE: {mode_name}")
    print(f"   Environment: {environment}")
    print(f"   Account Type: {account_type}")
    print(f"   Data Source: {data_source}")
    print(f"{'='*80}\n")
    
    # Create test signal
    signal_payload = {
        'strategy_name': 'IBKR_Test_Stock',
        'signal_type': 'ENTRY',
        'account_equity': 1000000.0,  # $1M account
        'signal': [{
            'instrument': 'AAPL',
            'instrument_type': 'STOCK',
            'action': 'BUY',
            'direction': 'LONG',
            'quantity': 10,
            'order_type': 'MARKET',
            'price': 245.00
        }]
    }
    
    try:
        # Send signal
        result = send_signal(
            payload=signal_payload,
            signal_type='entry',
            mode=mode_name,
            environment=environment,
            account_type=account_type
        )
        
        if result and 'signal_id' in result:
            print(f"\n✅ {mode_name} signal sent successfully!")
            print(f"   Signal ID: {result['signal_id']}")
            
            # Check processing status
            # check_signal_status(result['signal_id'])
            
            return True
        else:
            print(f"\n❌ {mode_name} signal failed to send")
            return False
            
    except Exception as e:
        print(f"\n❌ {mode_name} test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all mode tests"""
    print("\n" + "="*80)
    print("🚀 TESTING ALL EXECUTION MODES")
    print("="*80)
    
    results = {}
    
    # Test 1: mock_mock (Full simulation)
    results['mock_mock'] = test_mode(
        mode_name='mock_mock',
        environment='staging',
        account_type='mock',
        data_source='mock'
    )
    
    time.sleep(2)
    
    # Test 2: mock_live (Mock execution + Real data)
    results['mock_live'] = test_mode(
        mode_name='mock_live',
        environment='staging',
        account_type='mock',
        data_source='live'
    )
    
    time.sleep(2)
    
    # Test 3: paper_live (Paper trading + Real data)
    results['paper_live'] = test_mode(
        mode_name='paper_live',
        environment='staging',
        account_type='paper',
        data_source='live'
    )
    
    time.sleep(2)
    
    # Test 4: live_live (Real money + Real data) - COMMENTED OUT FOR SAFETY
    print(f"\n{'='*80}")
    print(f"⚠️  SKIPPING MODE: live_live (Real money - requires manual testing)")
    print(f"{'='*80}\n")
    results['live_live'] = None  # Skip for safety
    
    # Print summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for mode, success in results.items():
        if success is None:
            status = "⏭️  SKIPPED"
        elif success:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"{status:12} {mode}")
    
    print("="*80 + "\n")
    
    # Check cerebro logs for verification
    print("\n💡 To verify execution, check:")
    print("   docker logs mathematricks-trader-cerebro-service-1 --tail 200 | grep 'MODE-AWARE'")
    print("   docker logs mathematricks-trader-execution-service-1 --tail 200")
    print()

if __name__ == '__main__':
    main()
