#!/usr/bin/env python3
"""
Unified Test Suite Runner for Mathematricks Trader
Run with: python tests/run_test_suite.py --all
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSuite:
    """Unified test suite runner"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def clean_test_data(self) -> bool:
        """Clean test data from MongoDB and reset account balances"""
        print("\n" + "="*80)
        print("🧹 CLEANING TEST DATA")
        print("="*80)
        
        try:
            import pymongo
            import subprocess
            import requests
            from datetime import datetime
            import time
            import os
            from dotenv import load_dotenv
            
            # Load environment variables
            load_dotenv()
            
            # Use MONGODB_URI_LOCAL for Mac scripts (port 27018), fallback to MONGODB_URI for Docker
            mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27018'
            
            # Connect to MongoDB
            client = pymongo.MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
            client.server_info()
            db = client['mathematricks_trading']
            
            # Clear test collections
            collections = ['trading_signals_raw', 'signal_store', 'trading_orders']
            
            print("\n📦 Clearing collections...")
            for coll_name in collections:
                before_count = db[coll_name].count_documents({})
                result = db[coll_name].delete_many({})
                print(f"   ✅ {coll_name}: deleted {result.deleted_count} document(s)")
            
            # Reset trading account balances
            print("\n💰 Resetting account balances...")
            accounts = list(db['trading_accounts'].find({}))
            reset_count = 0
            for account in accounts:
                initial_equity = account.get('authentication_details', {}).get('initial_equity', 1000000.0)
                
                reset_balances = {
                    'equity': initial_equity,
                    'cash': initial_equity / 2,
                    'cash_balance': initial_equity / 2,
                    'margin_used': 0.0,
                    'margin_available': initial_equity / 2,
                    'buying_power': initial_equity * 2,
                    'unrealized_pnl': 0.0,
                    'realized_pnl': 0.0,
                }
                
                db['trading_accounts'].update_one(
                    {'_id': account['_id']},
                    {
                        '$set': {
                            'balances.equity': reset_balances['equity'],
                            'balances.cash': reset_balances['cash'],
                            'balances.cash_balance': reset_balances['cash_balance'],
                            'balances.margin_used': reset_balances['margin_used'],
                            'balances.margin_available': reset_balances['margin_available'],
                            'balances.buying_power': reset_balances['buying_power'],
                            'balances.unrealized_pnl': reset_balances['unrealized_pnl'],
                            'balances.realized_pnl': reset_balances['realized_pnl'],
                            'open_positions': []
                        }
                    }
                )
                reset_count += 1
                print(f"   ✅ {account.get('account_id')}: reset to ${initial_equity:,.2f}")
            
            # Reset fund total_equity
            print("\n💼 Resetting fund total_equity...")
            funds = list(db['funds'].find({}))
            for fund in funds:
                fund_id = fund.get('fund_id')
                
                # Get all accounts for this fund
                fund_accounts = list(db['trading_accounts'].find({'fund_id': fund_id}))
                
                # Sum equity across all accounts
                total_equity = sum(
                    acc.get('balances', {}).get('equity', 0.0)
                    for acc in fund_accounts
                )
                
                # Update fund total_equity
                db['funds'].update_one(
                    {'fund_id': fund_id},
                    {'$set': {'total_equity': total_equity}}
                )
                print(f"   ✅ {fund_id}: reset to ${total_equity:,.2f}")
            
            # Restart execution service
            print("\n🔄 Restarting execution-service...")
            try:
                subprocess.run(
                    ["docker", "restart", "mathematricks-trader-execution-service-1"],
                    check=True,
                    capture_output=True,
                    timeout=10
                )
                
                # Wait for service to be healthy
                print("   ⏳ Waiting for service to be healthy...")
                max_wait = 60
                wait_interval = 2
                elapsed = 0
                service_ready = False
                
                while elapsed < max_wait:
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                    
                    try:
                        response = requests.get('http://localhost:8083/health', timeout=2)
                        if response.status_code == 200:
                            health_data = response.json()
                            if health_data.get('ready'):
                                service_ready = True
                                print(f"   ✅ execution-service ready ({elapsed}s)")
                                break
                    except:
                        pass
                
                if not service_ready:
                    print(f"   ⚠️  Service not ready after {max_wait}s (continuing anyway)")
                    
            except Exception as e:
                print(f"   ⚠️  Could not restart execution-service: {e}")
            
            print("\n" + "="*80)
            print("✅ TEST DATA CLEANED")
            print("="*80)
            
            client.close()
            return True
            
        except Exception as e:
            print(f"\n❌ CLEAN FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def print_header(self, title: str):
        """Print formatted test header"""
        print(f"\n{'='*80}")
        print(f"📋 {title}")
        print('='*80)
    
    def test_mongodb(self) -> bool:
        """Test MongoDB connection and configuration"""
        print("\n🔍 MongoDB Connection & Configuration")
        try:
            import pymongo
            client = pymongo.MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
            client.server_info()
            print("   ✅ PASS: MongoDB connected")
            
            db = client['mathematricks_trading']
            accounts = list(db.trading_accounts.find())
            print(f"   ✅ PASS: Found {len(accounts)} trading account(s)")
            
            # Check for 4-mode fields
            for acc in accounts:
                acc_id = acc.get('account_id')
                acc_type = acc.get('account_type')
                data_src = acc.get('data_source')
                
                if not acc_type or not data_src:
                    self.warnings.append(f"{acc_id} missing 4-mode fields")
                    print(f"      ⚠️  {acc_id}: Missing account_type or data_source")
                else:
                    print(f"      ✅ {acc_id}: {acc_type}_{data_src}")
            
            return True
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_mongodb_collections(self) -> bool:
        """Test MongoDB collections exist"""
        print("\n🔍 MongoDB Collections")
        try:
            import pymongo
            client = pymongo.MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
            db = client['mathematricks_trading']
            
            # Core collections required for system to function
            core_collections = ['strategies', 'trading_accounts']
            
            # Optional collections (created on first use)
            optional_collections = ['signals', 'positions', 'orders']
            
            existing = db.list_collection_names()
            
            # Check core collections
            missing_core = [c for c in core_collections if c not in existing]
            if missing_core:
                print(f"   ❌ FAIL: Missing core collections: {missing_core}")
                return False
            
            print(f"   ✅ PASS: All core collections exist")
            
            # Show all collections
            for col in core_collections:
                count = db[col].count_documents({})
                print(f"      ✅ {col}: {count} document(s)")
            
            for col in optional_collections:
                if col in existing:
                    count = db[col].count_documents({})
                    print(f"      ✅ {col}: {count} document(s)")
                else:
                    print(f"      ⚠️  {col}: Not created yet (will be created on first use)")
            
            return True
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            return False
    
    
    def test_docker_services(self) -> bool:
        """Test all required Docker services are running"""
        print("\n🔍 Docker Services")
        try:
            import subprocess
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}\\t{{.Status}}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                print("   ❌ FAIL: Docker not running")
                return False
            
            containers = [line.split('\t') for line in result.stdout.strip().split('\n') if line]
            
            if not containers:
                print("   ❌ FAIL: No containers running")
                return False
            
            # List of required containers for the trading system
            required_containers = [
                'mathematricks-trader-mongodb-1',
                'mathematricks-trader-execution-service-1',
                'mathematricks-trader-account-data-service-1',
                'mathematricks-trader-signal-ingestion-1',
                'mathematricks-trader-dashboard-creator-1',
                'mathematricks-trader-portfolio-builder-1',
                'mathematricks-trader-cerebro-service-1',
                'mathematricks-trader-frontend-1',
                'ib-gateway-ibkr-testing-account',
            ]
            
            running_containers = {name: status for name, status in containers}
            
            print(f"   ✅ PASS: {len(containers)} container(s) running")
            
            # Check all required containers
            all_running = True
            for req_container in required_containers:
                if req_container in running_containers:
                    status = running_containers[req_container]
                    status_icon = "✅" if "Up" in status else "⚠️"
                    # Truncate status for readability
                    status_display = status[:50] if len(status) <= 50 else status[:47] + "..."
                    print(f"      {status_icon} {req_container}: {status_display}")
                else:
                    print(f"      ❌ {req_container}: NOT RUNNING")
                    all_running = False
            
            return all_running
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_python_environment(self) -> bool:
        """Test Python environment is compatible"""
        print("\n🔍 Python Environment")
        try:
            import sys
            version = sys.version_info
            
            # Check Python version
            if version < (3, 9):
                print(f"   ❌ FAIL: Python 3.9+ required, found {version.major}.{version.minor}")
                return False
            
            print(f"   ✅ PASS: Python {version.major}.{version.minor}.{version.micro}")
            
            # Check required packages
            required_packages = ['pymongo', 'ib_insync']
            missing = []
            
            for package in required_packages:
                try:
                    __import__(package.replace("-", "_"))
                    print(f"      ✅ {package} installed")
                except ImportError:
                    missing.append(package)
                    print(f"      ❌ {package} NOT installed")
            
            if missing:
                print(f"   ❌ FAIL: Missing packages: {missing}")
                return False
            
            return True
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            return False
    
    def test_ibkr_gateway(self) -> bool:
        """Test IB Gateway container is running"""
        print("\n🔍 IB Gateway")
        try:
            import subprocess
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'name=ib-gateway', '--format', '{{.Names}}\\t{{.Status}}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                print("   ❌ FAIL: Cannot check Docker")
                return False
            
            gateways = [line.split('\t') for line in result.stdout.strip().split('\n') if line]
            
            if not gateways:
                print("   ❌ FAIL: No IB Gateway containers running")
                return False
            
            print(f"   ✅ PASS: {len(gateways)} IB Gateway container(s) running")
            for name, status in gateways:
                status_icon = "✅" if "Up" in status else "⚠️"
                status_display = status[:50] if len(status) <= 50 else status[:47] + "..."
                print(f"      {status_icon} {name}: {status_display}")
            
            return True
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            return False
    
    
    def run_system_tests(self):
        """Run system validation tests"""
        self.print_header("🧪 System Validation Tests")
        
        tests = [
            ("MongoDB Connection", self.test_mongodb),
            ("Docker Services", self.test_docker_services),
            ("Python Environment", self.test_python_environment),
            ("IB Gateway", self.test_ibkr_gateway),
        ]
        
        for name, test_func in tests:
            try:
                if test_func():
                    self.passed.append(name)
                else:
                    self.failed.append(name)
            except Exception as e:
                print(f"\n   ❌ UNEXPECTED ERROR in {name}: {e}")
                self.failed.append(name)
    
    def run_signal_tests(self, mode: str = None, up_to: str = None, signal_count: int = None, signals_folder: str = None) -> bool:
        """Run signal tests using run_signal_tests_full.py"""
        self.print_header(f"🧪 Signal Testing")
        
        try:
            import subprocess
            
            # Determine which modes to test
            modes_to_test = []
            
            if up_to:
                mode_order = ['mock_mock', 'mock_live', 'paper_live', 'live_live']
                try:
                    up_to_idx = mode_order.index(up_to)
                    modes_to_test = mode_order[:up_to_idx + 1]
                except ValueError:
                    print(f"   ❌ Invalid mode: {up_to}")
                    return False
            elif mode:
                modes_to_test = [mode]
            else:
                # Default: test first 3 modes (skip live_live)
                modes_to_test = ['mock_mock', 'mock_live', 'paper_live']
            
            print(f"   Testing modes: {', '.join(modes_to_test)}")
            
            # Use provided signals folder or default to tests/sample_signals
            if signals_folder:
                signals_folder_path = Path(signals_folder)
            else:
                signals_folder_path = self.project_root / 'tests' / 'sample_signals'
            
            if not signals_folder_path.exists():
                print(f"   ❌ Signal folder not found: {signals_folder_path}")
                return False
            
            # Count signal files
            signal_files = list(signals_folder_path.glob('*.json'))
            print(f"   Found {len(signal_files)} signal file(s) in {signals_folder_path.name}\n")
            
            # Run test for each mode
            all_passed = True
            for test_mode in modes_to_test:
                print(f"\n{'─'*80}")
                print(f"🚀 Testing mode: {test_mode.upper()}")
                print('─'*80 + "\n")
                
                # Build command
                test_script = self.project_root / 'tests' / 'run_signal_tests_full.py'
                cmd = [
                    sys.executable,
                    str(test_script),
                    '--mode', test_mode,
                    '--folder', str(signals_folder_path),
                    '--output-dir', str(self.project_root / 'test_results')
                ]
                
                # Add signal_count if specified
                if signal_count is not None:
                    cmd.extend(['--signal_count', str(signal_count)])
                
                # Run the test
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=str(self.project_root),
                        capture_output=False,
                        text=True,
                        timeout=600 * 2  # 20 minute timeout
                    )
                    
                    if result.returncode == 0:
                        print(f"\n   ✅ {test_mode.upper()} tests PASSED")
                        self.passed.append(f"Signal Tests ({test_mode})")
                    else:
                        print(f"\n   ❌ {test_mode.upper()} tests FAILED")
                        self.failed.append(f"Signal Tests ({test_mode})")
                        all_passed = False
                        
                        # Stop testing if a mode fails
                        print(f"\n   ⚠️  {test_mode} had failures, stopping signal testing")
                        break
                        
                except subprocess.TimeoutExpired:
                    print(f"\n   ❌ {test_mode.upper()} tests TIMEOUT")
                    self.failed.append(f"Signal Tests ({test_mode})")
                    all_passed = False
                    break
                    
                except Exception as e:
                    print(f"\n   ❌ Error running {test_mode}: {e}")
                    self.failed.append(f"Signal Tests ({test_mode})")
                    all_passed = False
                    break
            
            return all_passed
            
        except Exception as e:
            print(f"\n   ❌ FAIL: {e}")
            import traceback
            traceback.print_exc()
            self.failed.append("Signal Tests")
            return False
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("📊 TEST SUMMARY")
        
        total = len(self.passed) + len(self.failed)
        
        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)}):")
            for test in self.passed:
                print(f"   ✅ {test}")
        
        if self.failed:
            print(f"\n❌ FAILED ({len(self.failed)}):")
            for test in self.failed:
                print(f"   ❌ {test}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   ⚠️  {warning}")
        
        print(f"\n{'='*80}")
        if not self.failed:
            print(f"✅ ALL TESTS PASSED ({len(self.passed)}/{total})")
        else:
            print(f"⚠️  SOME TESTS FAILED ({len(self.passed)}/{total} passed)")
        print('='*80)
        
        return 0 if not self.failed else 1


def main():
    parser = argparse.ArgumentParser(
        description='Unified Test Suite for Mathematricks Trader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clean test data (reset balances, clear signals)
  python tests/run_test_suite.py --clean
  
  # Run all tests (system + signal tests up to paper_live)
  python tests/run_test_suite.py --all
  
  # Clean and run all tests
  python tests/run_test_suite.py --clean && python tests/run_test_suite.py --all
  
  # Run only system validation tests
  python tests/run_test_suite.py --system
  
  # Run signal tests in specific mode
  python tests/run_test_suite.py --signal-testing --mode mock_mock
  
  # Run signal tests up to paper_live
  python tests/run_test_suite.py --signal-testing --up-to paper_live
  
  # Run everything including live_live
  python tests/run_test_suite.py --all --include-live
        """
    )
    
    parser.add_argument('--all', action='store_true',
                       help='Run all tests (system + signal tests up to paper_live)')
    parser.add_argument('--system', action='store_true',
                       help='Run system validation tests only')
    parser.add_argument('--signal-testing', action='store_true',
                       help='Run signal tests')
    parser.add_argument('--mode', type=str, choices=['mock_mock', 'mock_live', 'paper_live', 'live_live'],
                       help='Run signal tests in specific mode')
    parser.add_argument('--up-to', type=str, choices=['mock_mock', 'mock_live', 'paper_live', 'live_live'],
                       help='Run signal tests up to this mode')
    parser.add_argument('--include-live', action='store_true',
                       help='Include live_live mode in --all tests (USE WITH CAUTION)')
    parser.add_argument('--clean', action='store_true',
                       help='Clean test data: reset balances, clear signals, restart services')
    parser.add_argument('--signal_count', type=int,
                       help='Limit total number of signals to send (applies per-mode)')
    parser.add_argument('--signals-folder', type=str,
                       help='Path to signals folder (default: tests/sample_signals)')
    
    args = parser.parse_args()
    
    suite = TestSuite()
    
    # Handle --clean flag (clean first if requested)
    if args.clean:
        success = suite.clean_test_data()
        if not success:
            return 1
        
        # If only --clean was specified, exit after cleaning
        if not any([args.all, args.system, args.signal_testing, args.mode, args.up_to]):
            return 0
        
        # Otherwise continue to run tests after cleaning
        print("\n")  # Add spacing before test output
    
    # Default to --all if no test args specified (and not just --clean)
    if not args.clean and not any([args.all, args.system, args.signal_testing, args.mode, args.up_to]):
        args.all = True
    
    print("="*80)
    print("🧪 Mathematricks Trader - Unified Test Suite")
    print("="*80)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run system tests
    if args.all or args.system:
        suite.run_system_tests()
        
        # If system tests failed, stop here
        if suite.failed:
            print("\n" + "="*80)
            print("⚠️  SYSTEM TESTS FAILED - Cannot proceed to signal testing")
            print("   Please fix the above issues and try again.")
            print("="*80)
            return suite.print_summary()
    
    # Run signal tests
    if args.all:
        # Run up to paper_live by default (or live_live if --include-live)
        up_to_mode = 'live_live' if args.include_live else 'paper_live'
        suite.run_signal_tests(up_to=up_to_mode, signal_count=args.signal_count)
    elif args.signal_testing:
        if args.mode:
            suite.run_signal_tests(mode=args.mode, signal_count=args.signal_count, signals_folder=args.signals_folder)
        elif args.up_to:
            suite.run_signal_tests(up_to=args.up_to, signal_count=args.signal_count, signals_folder=args.signals_folder)
        else:
            # Default to mock_mock if no mode specified
            suite.run_signal_tests(mode='mock_mock', signal_count=args.signal_count, signals_folder=args.signals_folder)
    
    # Print summary
    return suite.print_summary()


if __name__ == '__main__':
    exit(main())
