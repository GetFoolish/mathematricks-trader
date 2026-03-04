#!/usr/bin/env python3
"""
Quick Market Data Test
Tests if IBKR Gateway can stream live market data for AAPL
"""
import os
import sys
import time
from pymongo import MongoClient
from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from services.brokers.ibkr.ibkr_broker import IBKRBroker

def test_market_data():
    """Test market data connection for IBKR-TESTING-ACCOUNT"""
    
    print("\n" + "="*70)
    print("🧪 TESTING IBKR MARKET DATA CONNECTION")
    print("="*70 + "\n")
    
    # Get account config from MongoDB
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27018/')
    # Replace internal Docker hostname with localhost
    if 'mongodb://' in mongo_uri:
        mongo_uri = mongo_uri.replace('mongodb://mongodb:', 'mongodb://localhost:')
        mongo_uri = mongo_uri.replace(':27017/', ':27018/')
        mongo_uri = mongo_uri.replace(':27017', ':27018')
        if '?' not in mongo_uri:
            mongo_uri += '/?directConnection=true'
    
    client = MongoClient(mongo_uri)
    db = client['mathematricks_trading']
    
    account = db['trading_accounts'].find_one({"account_id": "IBKR-TESTING-ACCOUNT"})
    if not account:
        print("❌ IBKR-TESTING-ACCOUNT not found in database")
        return False
    
    # Build broker config
    auth = account.get('authentication_details', {})
    config = {
        'broker': 'IBKR',
        'account_id': 'IBKR-TESTING-ACCOUNT',
        'host': auth.get('host', '127.0.0.1'),
        'port': auth.get('port', 4002),
        'client_id': auth.get('client_id', 1),
    }
    
    print(f"📡 Connecting to IBKR Gateway at {config['host']}:{config['port']}")
    print(f"   Client ID: {config['client_id']}\n")
    
    try:
        # Create broker instance
        broker = IBKRBroker(config)
        
        print("🔌 Connecting to IB Gateway...")
        broker.connect()
        print("✅ Connected!\n")
        
        # Wait a moment for connection to stabilize
        time.sleep(2)
        
        # Test symbols
        test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'SPY']
        
        print("📊 Testing market data for US stocks:")
        print("-" * 70)
        
        success_count = 0
        for symbol in test_symbols:
            try:
                print(f"\n🔍 Fetching price for {symbol}...", end=" ", flush=True)
                price = broker.get_market_price(symbol, 'STOCK')
                
                if price and price > 0:
                    print(f"✅ ${price:.2f}")
                    success_count += 1
                else:
                    print(f"❌ No data (price={price})")
            except Exception as e:
                print(f"❌ Error: {str(e)[:60]}")
        
        print("\n" + "-" * 70)
        print(f"\n📈 Results: {success_count}/{len(test_symbols)} symbols returned data")
        
        # Disconnect
        print("\n🔌 Disconnecting...")
        broker.disconnect()
        print("✅ Disconnected")
        
        if success_count == 0:
            print("\n" + "="*70)
            print("⚠️  MARKET DATA NOT AVAILABLE")
            print("="*70)
            print("\n🔧 Troubleshooting steps:")
            print("   1. Check IB Gateway UI via VNC: vnc://localhost:55460")
            print("      Password: ibgateway")
            print("   2. Verify market data subscriptions in TWS/Gateway")
            print("   3. Check if paper trading account has market data permissions")
            print("   4. Ensure US Securities data is enabled")
            print("\n💡 For paper accounts, you may need:")
            print("   • US Securities Snapshot and Futures Value Bundle")
            print("   • Real-time market data subscription (free for paper)")
            return False
        else:
            print("\n✅ Market data is working!")
            return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_market_data()
    sys.exit(0 if success else 1)
