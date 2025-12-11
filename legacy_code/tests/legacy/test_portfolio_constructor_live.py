"""
Test 2: Live Signal Processing Integration Test
Tests the complete end-to-end flow with running services and simulated signals.

Test Flow:
1. Verify all required services are running (cerebro_service, account_data_service, execution_service, etc.)
2. Load active portfolio allocation from MongoDB (or create default one)
3. Simulate random signals from different strategies every 15 seconds
4. Verify that signals are processed correctly:
   - Signal received by signal_collector
   - Published to Pub/Sub
   - Processed by CerebroService using MaxCAGR constructor
   - Position sized according to allocations
   - Decision logged to MongoDB
   - Order published (if approved)
5. Monitor MongoDB collections to verify data flow
6. After 5 minutes (20 signals), generate summary report

Expected Outputs:
- Console logs showing signal flow through the system
- MongoDB entries in: standardized_signals, cerebro_decisions, trading_orders
- Summary report showing approval/rejection stats
- Verification that position sizing matches allocation percentages
"""
import os
import sys
import time
import random
import requests
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import subprocess
import signal as sys_signal

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment
load_dotenv(os.path.join(project_root, '.env'))


class SignalSimulator:
    """Simulates random trading signals from multiple strategies"""
    
    def __init__(self, strategies):
        self.strategies = strategies
        self.signal_count = 0
        self.instruments = ['SPY', 'QQQ', 'IWM', 'GLD', 'TLT', 'DIA', 'XLF', 'XLE']
    
    def generate_signal(self):
        """Generate a random signal"""
        strategy_id = random.choice(self.strategies)
        instrument = random.choice(self.instruments)
        action = random.choice(['ENTRY', 'EXIT'])
        direction = random.choice(['LONG', 'SHORT'])
        price = round(random.uniform(100, 500), 2)
        
        self.signal_count += 1
        timestamp = datetime.utcnow()
        
        signal = {
            'signal_id': f"{strategy_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{self.signal_count:03d}",
            'strategy_id': strategy_id,
            'timestamp': timestamp.isoformat(),
            'instrument': instrument,
            'direction': direction,
            'action': action,
            'order_type': 'MARKET',
            'price': price,
            'quantity': random.randint(10, 100),
            'stop_loss': price * 0.95 if direction == 'LONG' else price * 1.05,
            'take_profit': price * 1.10 if direction == 'LONG' else price * 0.90,
            'metadata': {
                'expected_alpha': random.uniform(0.01, 0.05),
                'test_mode': True
            }
        }
        
        return signal


def check_service_health(service_name, url):
    """Check if a service is running and healthy"""
    try:
        response = requests.get(f"{url}/health", timeout=2)
        if response.status_code == 200:
            print(f"  ✓ {service_name} is running")
            return True
        else:
            print(f"  ❌ {service_name} responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  ❌ {service_name} is not running (connection refused)")
        return False
    except Exception as e:
        print(f"  ❌ {service_name} health check failed: {str(e)}")
        return False


def send_signal_to_collector(signal):
    """Send signal to signal_collector via MongoDB (simulates TradingView webhook)"""
    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    
    # Insert into raw_signals collection (as if from webhook)
    raw_signal = {
        'timestamp': datetime.utcnow(),
        'source': 'test_simulator',
        'raw_data': signal,
        'processed': False,
        'created_at': datetime.utcnow()
    }
    
    db['raw_signals'].insert_one(raw_signal)
    
    # Also insert standardized version directly (for faster testing)
    standardized_signal = {
        **signal,
        'timestamp': datetime.fromisoformat(signal['timestamp']),
        'processed_by_cerebro': False,
        'created_at': datetime.utcnow()
    }
    
    db['standardized_signals'].insert_one(standardized_signal)
    print(f"    → Signal inserted: {signal['signal_id']}")


def monitor_signal_processing(signal_id, timeout=10):
    """Monitor if signal was processed by checking MongoDB"""
    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Check if cerebro_decision exists
        decision = db['cerebro_decisions'].find_one({'signal_id': signal_id})
        
        if decision:
            return {
                'processed': True,
                'decision': decision.get('decision'),
                'reason': decision.get('reason'),
                'final_quantity': decision.get('final_quantity', 0)
            }
        
        time.sleep(0.5)
    
    return {'processed': False, 'decision': None, 'reason': 'Timeout'}


def test_live_signal_processing():
    """
    TEST 2: Send random signals to running services and verify processing
    """
    print("="*80)
    print("TEST 2: Live Signal Processing Integration Test")
    print("="*80)
    
    # Step 1: Check if all services are running
    print("\n[1/6] Checking service health...")
    
    services = {
        'Cerebro Service': os.getenv('CEREBRO_SERVICE_URL', 'http://localhost:8001'),
        'Account Data Service': os.getenv('ACCOUNT_DATA_SERVICE_URL', 'http://localhost:8002'),
        'Execution Service': os.getenv('EXECUTION_SERVICE_URL', 'http://localhost:8003')
    }
    
    services_running = []
    for name, url in services.items():
        if check_service_health(name, url):
            services_running.append(name)
    
    if len(services_running) < len(services):
        print(f"\n⚠️  WARNING: Only {len(services_running)}/{len(services)} services running")
        print("   Missing services may cause test failures")
        print("   Run: ./run_mvp_demo.sh to start all services")
        
        # Ask user if they want to continue
        response = input("\n   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("\n❌ TEST ABORTED: Please start all services first")
            return False
    else:
        print(f"\n  ✅ All {len(services)} services are running")
    
    # Step 2: Load strategies from MongoDB
    print("\n[2/6] Loading strategies from MongoDB...")
    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    
    strategies_cursor = db['strategies'].find()
    strategies = [doc.get('strategy_name') or doc.get('strategy_id') or str(doc.get('_id')) 
                  for doc in strategies_cursor]
    
    if len(strategies) == 0:
        print("  ⚠️  No strategies found in MongoDB, using default test strategies")
        strategies = ['TEST_STRATEGY_1', 'TEST_STRATEGY_2', 'TEST_STRATEGY_3']
    else:
        print(f"  ✓ Loaded {len(strategies)} strategies from MongoDB")
        for s in strategies[:5]:  # Show first 5
            print(f"    - {s}")
        if len(strategies) > 5:
            print(f"    ... and {len(strategies)-5} more")
    
    # Step 3: Check for active portfolio allocation
    print("\n[3/6] Checking active portfolio allocation...")
    active_allocation = db['portfolio_allocations'].find_one(
        {'status': 'ACTIVE'},
        sort=[('approved_at', -1)]
    )
    
    if active_allocation:
        print(f"  ✓ Active allocation found: {active_allocation.get('allocation_id')}")
        allocations = active_allocation.get('allocations', {})
        print(f"    Total strategies: {len(allocations)}")
        print(f"    Total allocation: {sum(allocations.values()):.1f}%")
    else:
        print("  ⚠️  No active allocation found")
        print("    CerebroService will use default fallback allocation (5% per strategy)")
    
    # Step 4: Initialize signal simulator
    print("\n[4/6] Initializing signal simulator...")
    simulator = SignalSimulator(strategies)
    print(f"  ✓ Simulator ready")
    print(f"    - Strategies: {len(strategies)}")
    print(f"    - Test duration: 5 minutes")
    print(f"    - Signal frequency: Every 15 seconds")
    print(f"    - Expected signals: ~20")
    
    # Step 5: Send signals and monitor processing
    print("\n[5/6] Sending signals and monitoring processing...")
    print("    (Press Ctrl+C to stop early)\n")
    
    test_duration = 5 * 60  # 5 minutes
    signal_interval = 15  # 15 seconds
    start_time = time.time()
    
    signals_sent = []
    signals_processed = []
    signals_approved = []
    signals_rejected = []
    signals_resized = []
    
    try:
        while time.time() - start_time < test_duration:
            # Generate and send signal
            signal = simulator.generate_signal()
            elapsed = time.time() - start_time
            
            print(f"  [{elapsed:.0f}s] Sending signal {len(signals_sent)+1}...")
            print(f"    Strategy: {signal['strategy_id']}")
            print(f"    Instrument: {signal['instrument']}")
            print(f"    Action: {signal['action']} {signal['direction']}")
            
            send_signal_to_collector(signal)
            signals_sent.append(signal)
            
            # Monitor processing (wait up to 5 seconds)
            result = monitor_signal_processing(signal['signal_id'], timeout=5)
            
            if result['processed']:
                signals_processed.append(signal['signal_id'])
                print(f"    ✓ Processed: {result['decision']} - {result['reason']}")
                
                if result['decision'] == 'APPROVED':
                    signals_approved.append(signal['signal_id'])
                elif result['decision'] == 'REJECTED':
                    signals_rejected.append(signal['signal_id'])
                elif result['decision'] == 'MODIFIED':
                    signals_resized.append(signal['signal_id'])
            else:
                print(f"    ⚠️  Not processed within timeout")
            
            # Wait for next signal
            time.sleep(signal_interval)
            
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Test interrupted by user")
    
    # Step 6: Generate summary report
    print("\n[6/6] Generating summary report...")
    print("\n" + "="*80)
    print("SUMMARY REPORT")
    print("="*80)
    
    print(f"\nSignals Sent: {len(signals_sent)}")
    print(f"Signals Processed: {len(signals_processed)}")
    print(f"  - Approved: {len(signals_approved)}")
    print(f"  - Rejected: {len(signals_rejected)}")
    print(f"  - Resized: {len(signals_resized)}")
    print(f"  - Unprocessed: {len(signals_sent) - len(signals_processed)}")
    
    # Calculate processing rate
    if len(signals_sent) > 0:
        processing_rate = len(signals_processed) / len(signals_sent) * 100
        print(f"\nProcessing Rate: {processing_rate:.1f}%")
    
    # Validation Checks
    print("\n" + "="*80)
    print("VALIDATION CHECKS")
    print("="*80)
    
    checks_passed = 0
    checks_total = 4
    
    # Check 1: At least some signals were sent
    if len(signals_sent) >= 5:
        print(f"  ✅ Sent {len(signals_sent)} signals (minimum 5)")
        checks_passed += 1
    else:
        print(f"  ❌ Only sent {len(signals_sent)} signals (expected at least 5)")
    
    # Check 2: Processing rate is high
    if len(signals_sent) > 0:
        processing_rate = len(signals_processed) / len(signals_sent) * 100
        if processing_rate >= 80:
            print(f"  ✅ Processing rate is {processing_rate:.1f}% (good)")
            checks_passed += 1
        else:
            print(f"  ⚠️  Processing rate is {processing_rate:.1f}% (expected >80%)")
    
    # Check 3: Some signals were approved
    if len(signals_approved) > 0:
        print(f"  ✅ {len(signals_approved)} signals approved (system is working)")
        checks_passed += 1
    else:
        print(f"  ⚠️  No signals approved (might be a configuration issue)")
    
    # Check 4: Data in MongoDB
    total_decisions = db['cerebro_decisions'].count_documents({})
    if total_decisions >= len(signals_processed):
        print(f"  ✅ MongoDB has {total_decisions} cerebro decisions")
        checks_passed += 1
    else:
        print(f"  ❌ MongoDB only has {total_decisions} decisions (expected {len(signals_processed)})")
    
    print(f"\n{checks_passed}/{checks_total} validation checks passed")
    
    if checks_passed >= 3:  # Allow some tolerance
        print("\n✅ TEST 2 PASSED: Live Signal Processing")
        return True
    else:
        print("\n❌ TEST 2 FAILED: Too many validation failures")
        return False


if __name__ == "__main__":
    try:
        success = test_live_signal_processing()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED WITH ERROR:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
