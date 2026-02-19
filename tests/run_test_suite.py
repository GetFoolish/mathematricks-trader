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
    
    def clean_test_data(self, deployment_target: str = 'local') -> bool:
        """Clean test data from MongoDB and reset account balances
        
        Args:
            deployment_target: 'local' for Docker MongoDB, 'cloud' for MongoDB Atlas
        """
        print("\n" + "="*80)
        print(f"🧹 CLEANING TEST DATA ({deployment_target.upper()})")
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
            
            # Select MongoDB URI based on deployment target
            if deployment_target == 'cloud':
                mongodb_uri = os.getenv('MONGODB_URI_CLOUD')
                if not mongodb_uri:
                    print("   ❌ MONGODB_URI_CLOUD not set in .env file")
                    return False
            else:
                # Use MONGODB_URI_LOCAL for Mac scripts (port 27018), fallback to MONGODB_URI for Docker
                mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27018'
            
            print(f"   📡 Connecting to: {mongodb_uri.split('@')[1] if '@' in mongodb_uri else mongodb_uri}")
            
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
            
            # Reset trading account balances (ONLY MOCK accounts - paper/live use real balances)
            print("\n💰 Resetting account balances...")
            accounts = list(db['trading_accounts'].find({}))
            reset_count = 0
            for account in accounts:
                account_type = account.get('account_type', '').lower()
                account_id = account.get('account_id')
                
                # Only reset mock accounts - paper and live accounts keep their real balances
                if account_type != 'mock':
                    print(f"   ⏭️  {account_id}: skipped (account_type={account_type}, keeping real balance)")
                    continue
                
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
                print(f"   ✅ {account_id}: reset to ${initial_equity:,.2f}")
            
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
            
            # Reload broker pool in execution service (faster than full restart)
            print("\n🔄 Reloading broker pool in execution-service...")
            try:
                response = requests.post('http://localhost:8083/reload', timeout=30)
                response.raise_for_status()
                
                result = response.json()
                if result.get('status') == 'success':
                    print(f"   ✅ {result.get('message')}")
                else:
                    print(f"   ⚠️  Reload returned: {result}")
                    
            except Exception as e:
                print(f"   ⚠️  Could not reload broker pool: {e}")
                print(f"   ℹ️  Continuing anyway (may have stale cached data)")
            
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
    
    def run_signal_tests(self, environment: str = 'staging', account_type: str = None, data_source: str = 'mock', signal_count: int = None, signals_folder: str = None, signal_file: str = None, clean_before_test: bool = False, deployment_target: str = 'cloud') -> bool:
        """Run signal tests using run_signal_tests_full.py"""
        self.print_header(f"🧪 Signal Testing")
        
        try:
            import subprocess
            
            # Determine signals folder (from file or folder parameter)
            if signal_file:
                # Single file mode - use parent folder
                signal_file_path = Path(signal_file)
                if not signal_file_path.exists():
                    print(f"   ❌ Signal file not found: {signal_file_path}")
                    return False
                signals_folder_path = signal_file_path.parent
            elif signals_folder:
                signals_folder_path = Path(signals_folder)
            else:
                signals_folder_path = self.project_root / 'tests' / 'sample_signals' / 'mock'
            
            if not signals_folder_path.exists():
                print(f"   ❌ Signal folder not found: {signals_folder_path}")
                return False
            
            # Infer broker from folder name
            folder_name = signals_folder_path.name
            broker_map = {
                'mock': 'mock',
                'ibkr': 'mock',  # Generic ibkr folder uses mock broker
                'ibkr-paper': 'ibkr_paper',
                'ibkr-live': 'ibkr_live',
                'binance-paper': 'binance_paper',
                'binance-live': 'binance_live',
                'production': 'production'
            }
            
            broker = broker_map.get(folder_name, 'mock')
            
            # Build mode from account_type and data_source
            # Use account_type if explicitly provided, otherwise fall back to broker inferred from folder
            mode = f"{account_type if account_type else broker}_{data_source}"
            
            # Display test info
            if signal_file:
                print(f"   File: {Path(signal_file).name}")
                print(f"   Folder: {signals_folder_path}")
            else:
                signal_files = list(signals_folder_path.glob('*.json'))
                print(f"   Folder: {signals_folder_path}")
                print(f"   Found {len(signal_files)} signal file(s)")
            
            print(f"   Broker: {broker}")
            print(f"   Data Source: {data_source}")
            print(f"   Mode: {mode}\n")
            
            # For live data source, validate market data availability (regardless of broker)
            # Even mock_live mode needs IBKR connection for live market pricing
            if data_source == 'live':
                from market_validator import check_market_data_availability, print_market_status_report
                
                print(f"\n{'─'*80}")
                print(f"🔍 Validating Market Data Availability")
                print('─'*80 + "\n")
                
                # For mock broker with live data, check IBKR for data availability
                # For other brokers, use their own config
                broker_for_validation = 'ibkr_paper' if broker == 'mock' else broker
                
                # Pass file filter if specified (only validate that specific file)
                file_filter = Path(signal_file).name if signal_file else None
                validation_result = check_market_data_availability(signals_folder_path, broker_for_validation, file_filter=file_filter)
                should_proceed = print_market_status_report(validation_result)
                
                if not should_proceed:
                    print("\n⚠️  Test aborted due to market data unavailability")
                    return False
            
            # NOW clean test data if requested (after validation confirms we should proceed)
            if clean_before_test:
                print(f"\n{'─'*80}")
                success = self.clean_test_data(deployment_target=deployment_target)
                if not success:
                    print("\n⚠️  Test aborted due to cleanup failure")
                    return False
                print()  # Add spacing
            
            print(f"\n{'─'*80}")
            print(f"🚀 Testing: {mode.upper()}")
            print('─'*80 + "\n")
            
            # Build command
            test_script = self.project_root / 'tests' / 'run_signal_tests_full.py'
            cmd = [
                sys.executable,
                str(test_script),
                '--mode', mode,
                '--folder', str(signals_folder_path),
                '--environment', environment,
                '--deployment-target', deployment_target,
            ]
            
            # Add account_type if specified
            if account_type:
                cmd.extend(['--account-type', account_type])
            
            # Add file filter if specified
            if signal_file:
                cmd.extend(['--file', Path(signal_file).name])
            
            # Add signal_count if specified
            if signal_count is not None:
                cmd.extend(['--signal-count', str(signal_count)])
            
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
                    print(f"\n   ✅ {mode.upper()} tests PASSED")
                    self.passed.append(f"Signal Tests ({mode})")
                    return True
                else:
                    print(f"\n   ❌ {mode.upper()} tests FAILED")
                    self.failed.append(f"Signal Tests ({mode})")
                    return False
                    
            except subprocess.TimeoutExpired:
                print(f"\n   ❌ {mode.upper()} tests TIMEOUT")
                self.failed.append(f"Signal Tests ({mode})")
                return False
                
            except Exception as e:
                print(f"\n   ❌ Error running {mode}: {e}")
                self.failed.append(f"Signal Tests ({mode})")
                return False
            
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
  
  # Run only system validation tests
  python tests/run_test_suite.py --system
  
  # Mock execution with live data (your main use case)
  .venv/bin/python tests/run_test_suite.py \
    --environment staging \
    --data-source live \
    --file tests/sample_signals/ibkr/tech_stocks_realistic.json

  # Paper trading test
  .venv/bin/python tests/run_test_suite.py \
    --environment staging \
    --account-type paper \
    --file tests/sample_signals/ibkr/tech_stocks_realistic.json

  # Would fail (safety check)
  .venv/bin/python tests/run_test_suite.py \\
    --environment live \\
    --account-type paper  # ❌ ERROR: Paper not allowed in live
    --file tests/sample_signals/ibkr/tech_stocks_realistic.json
  
  # Clean and test mock mode
  python tests/run_test_suite.py --clean --signal-testing --signals-folder tests/sample_signals/mock
        """
    )
    
    parser.add_argument('--all', action='store_true',
                       help='Run all tests (system + signal tests)')
    parser.add_argument('--system', action='store_true',
                       help='Run system validation tests only')
    parser.add_argument('--signal-testing', action='store_true',
                       help='Run signal tests')
    parser.add_argument('--environment', type=str, choices=['staging', 'live'],
                       help='Environment for execution (staging=mock/paper, live=real money)', default='staging')
    parser.add_argument('--account-type', type=str, choices=['mock', 'paper', 'live'],
                       help='Account type for execution (overrides default based on environment)', default=None)
    parser.add_argument('--data-source', type=str, choices=['mock', 'live'],
                       help='Data source for testing (mock or live market data)', default='mock')
    parser.add_argument('--local', action='store_true',
                       help='Send signals to local Docker container (http://localhost:3000)')
    parser.add_argument('--cloud', action='store_true',
                       help='Send signals to cloud deployment (https://staging.mathematricks.fund or mathematricks.fund)')
    parser.add_argument('--clean', action='store_true',
                       help='Clean test data: reset balances, clear signals, restart services')
    parser.add_argument('--signal-count', type=int,
                       help='Limit total number of signals to send')
    parser.add_argument('--signals-folder', type=str,
                       help='Path to signals folder (e.g., tests/sample_signals/mock, tests/sample_signals/ibkr-paper)')
    parser.add_argument('--file', type=str,
                       help='Path to single signal file (e.g., tests/sample_signals/ibkr/tech_stocks_realistic.json)')
    
    args = parser.parse_args()
    
    suite = TestSuite()
    
    # If only --clean was specified (no tests), clean and exit
    if args.clean and not any([args.all, args.system, args.signal_testing]):
        # Determine deployment target
        if args.local and args.cloud:
            print("❌ ERROR: Cannot specify both --local and --cloud")
            return 1
        deployment_target = 'cloud' if args.cloud else 'local'
        success = suite.clean_test_data(deployment_target=deployment_target)
        return 0 if success else 1
    
    # Default to --all if no test args specified
    if not any([args.all, args.system, args.signal_testing]):
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
    
    # Run signal tests (will clean AFTER validation if --clean flag set)
    if args.signal_testing:
        # Determine deployment target
        if args.local and args.cloud:
            print("❌ ERROR: Cannot specify both --local and --cloud")
            return 1
        deployment_target = 'local' if args.local else 'cloud'
        
        suite.run_signal_tests(
            environment=args.environment,
            account_type=args.account_type,
            data_source=args.data_source,
            signal_count=getattr(args, 'signal_count'),
            signals_folder=args.signals_folder,
            signal_file=args.file,
            clean_before_test=args.clean,  # Pass clean flag to be executed after validation
            deployment_target=deployment_target
        )
    
    # Print summary
    return suite.print_summary()


if __name__ == '__main__':
    exit(main())
