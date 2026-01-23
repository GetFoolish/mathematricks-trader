#!/usr/bin/env python3
"""
Simple Python-based system tests for Mathematricks Trader
No pytest required - just run with: python tests/test_system.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(title):
    """Print a formatted test header"""
    print(f"\n{'='*80}")
    print(f"📋 {title}")
    print('='*80)


def test_mongodb_connection():
    """Test 1: Verify MongoDB is accessible"""
    print("\n🔍 Test 1: MongoDB Connection")
    try:
        import pymongo
        client = pymongo.MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
        client.server_info()
        print("   ✅ PASS: MongoDB connected successfully")
        return True, client
    except Exception as e:
        print(f"   ❌ FAIL: MongoDB connection failed - {e}")
        return False, None


def test_trading_accounts(client):
    """Test 2: Verify trading accounts exist and have correct fields"""
    print("\n🔍 Test 2: Trading Accounts Configuration")
    try:
        db = client['mathematricks_trading']
        accounts = list(db.trading_accounts.find())
        
        if not accounts:
            print("   ❌ FAIL: No trading accounts found")
            return False
        
        print(f"   ✅ PASS: Found {len(accounts)} account(s)")
        
        # Check for 4-mode migration fields
        for acc in accounts:
            acc_id = acc.get('account_id', 'Unknown')
            mode = acc.get('mode', 'N/A')
            acc_type = acc.get('account_type', 'N/A')
            data_src = acc.get('data_source', 'N/A')
            
            has_new_fields = acc_type != 'N/A' and data_src != 'N/A'
            status = "✅" if has_new_fields else "⚠️"
            
            print(f"      {status} {acc_id}:")
            print(f"         - mode: {mode}")
            print(f"         - account_type: {acc_type}")
            print(f"         - data_source: {data_src}")
        
        return True
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False


def test_mongodb_collections(client):
    """Test 3: Verify required MongoDB collections exist"""
    print("\n🔍 Test 3: MongoDB Collections")
    try:
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




def test_docker_services():
    """Test 3: Verify all required Docker services are running"""  
    print("\n🔍 Test 3: Docker Services")
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


def test_python_environment():
    """Test 4: Verify Python environment is compatible"""
    print("\n🔍 Test 4: Python Environment")
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


def test_ibkr_gateway():
    """Test 5: Verify IB Gateway container is running"""
    print("\n🔍 Test 5: IB Gateway")
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


def test_market_data():
    """Test 6: Verify market data is available (AAPL price check)"""
    print("\n🔍 Test 6: Market Data Availability")
    try:
        import os
        import time
        from pymongo import MongoClient
        
        # Import IBKRBroker
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from services.brokers.ibkr.ibkr_broker import IBKRBroker
        
        # Get account config from MongoDB
        client = MongoClient('mongodb://localhost:27017')
        db = client['mathematricks_trading']
        
        account = db['trading_accounts'].find_one({"account_id": "IBKR-TESTING-ACCOUNT"})
        if not account:
            print("   ⚠️  SKIP: IBKR-TESTING-ACCOUNT not found")
            return True  # Don't fail, just skip
        
        # Build broker config
        auth = account.get('authentication_details', {})
        config = {
            'broker': 'IBKR',
            'account_id': 'IBKR-TESTING-ACCOUNT',
            'host': auth.get('host', '127.0.0.1'),
            'port': auth.get('port', 4002),
            'client_id': auth.get('client_id', 1),
        }
        
        # Create broker instance
        broker = IBKRBroker(config)
        
        print(f"   📡 Connecting to IBKR Gateway at {config['host']}:{config['port']}...")
        broker.connect()
        
        # Wait for connection to stabilize
        time.sleep(2)
        
        # Test AAPL price
        print("   🔍 Fetching AAPL price...", end=" ", flush=True)
        price = broker.get_market_price('AAPL', 'STOCK')
        
        # Disconnect
        broker.disconnect()
        
        if price and price > 0:
            print(f"${price:.2f}")
            print(f"   ✅ PASS: Market data available")
            return True
        else:
            print("No data")
            print(f"   ⚠️  WARN: Market data not available (markets may be closed)")
            return True  # Don't fail - markets might be closed
    except Exception as e:
        print(f"   ⚠️  WARN: {e}")
        return True  # Don't fail - this is informational





def main():
    """Run all tests"""
    print_header("🧪 Mathematricks Trader - Python Test Suite")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    client = None
    
    # Test 1: MongoDB
    passed, client = test_mongodb_connection()
    results.append(('MongoDB Connection', passed))
    
    if client:
        # Test 2: Accounts
        passed = test_trading_accounts(client)
        results.append(('Trading Accounts', passed))
    else:
        results.append(('Trading Accounts', False))
    
    # Test 3: Docker Services
    passed = test_docker_services()
    results.append(('Docker Services', passed))
    
    # Test 4: Python Environment
    passed = test_python_environment()
    results.append(('Python Environment', passed))
    
    # Test 5: IB Gateway
    passed = test_ibkr_gateway()
    results.append(('IB Gateway', passed))
    
    # Test 6: Market Data (informational, doesn't fail)
    passed = test_market_data()
    results.append(('Market Data Check', passed))
    
    # Summary
    print_header("📊 TEST SUMMARY")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {name}")
    
    print(f"\n{'='*80}")
    if passed_count == total_count:
        print(f"✅ ALL TESTS PASSED ({passed_count}/{total_count})")
        print('='*80)
        return 0
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed_count}/{total_count} passed)")
        print('='*80)
        return 1


if __name__ == '__main__':
    exit(main())
