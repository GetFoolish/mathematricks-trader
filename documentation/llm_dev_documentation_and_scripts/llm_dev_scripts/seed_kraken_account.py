#!/usr/bin/env python3
"""
Seed Kraken Account to MongoDB
Creates KRAKEN_CANADA account with API credentials from .env
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Add project root to path (scripts/llm_dev_scripts -> scripts -> project_root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from project root
env_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=env_path)

def seed_kraken_account():
    """Create or update Kraken account in MongoDB"""
    
    # Get MongoDB URI
    mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27018'
    
    # Get Kraken API credentials from environment
    kraken_api_key = os.getenv('KRAKEN_CANADA_API_KEY')
    kraken_api_secret = os.getenv('KRAKEN_CANADA_PRIVATE_KEY')
    
    if not kraken_api_key or not kraken_api_secret:
        print("❌ Error: KRAKEN_CANADA_API_KEY and KRAKEN_CANADA_PRIVATE_KEY must be set in .env")
        print("   Add these lines to your .env file:")
        print("   KRAKEN_CANADA_API_KEY=your_api_key_here")
        print("   KRAKEN_CANADA_PRIVATE_KEY=your_private_key_here")
        return False
    
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB: {mongodb_uri}")
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()  # Test connection
        
        db = client['mathematricks_trading']
        trading_accounts = db['trading_accounts']
        
        # Check if account already exists
        existing = trading_accounts.find_one({"account_id": "KRAKEN_CANADA"})
        
        # Kraken account document
        kraken_account = {
            "account_id": "KRAKEN_CANADA",
            "broker": "Kraken",
            "account_type": "mock",  # Using mock for paper trading
            "mode": ["mock_mock", "mock_live", "paper_live"],
            "status": "ACTIVE",
            "authentication_details": {
                "api_key": kraken_api_key,
                "api_secret": kraken_api_secret,
                "testnet": True,  # For consistency (Kraken doesn't have official testnet)
                "initial_equity": 100000.0
            },
            "balances": {
                "base_currency": "USD",
                "equity": 100000.0,
                "cash_balance": 100000.0,
                "margin_available": 100000.0,
                "margin_used": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "last_updated": datetime.utcnow()
            },
            "open_positions": [],
            "broker_positions_snapshot": [],
            "created_at": existing.get('created_at', datetime.utcnow()) if existing else datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        if existing:
            # Update existing account
            result = trading_accounts.update_one(
                {"account_id": "KRAKEN_CANADA"},
                {"$set": kraken_account}
            )
            print(f"✅ Updated existing Kraken account (matched: {result.matched_count}, modified: {result.modified_count})")
        else:
            # Insert new account
            result = trading_accounts.insert_one(kraken_account)
            print(f"✅ Created new Kraken account with ID: {result.inserted_id}")
        
        # Verify account
        account = trading_accounts.find_one({"account_id": "KRAKEN_CANADA"})
        print(f"\n📋 Kraken Account Details:")
        print(f"   Account ID: {account['account_id']}")
        print(f"   Broker: {account['broker']}")
        print(f"   Account Type: {account['account_type']}")
        print(f"   Modes: {account['mode']}")
        print(f"   Status: {account['status']}")
        print(f"   Initial Equity: ${account['authentication_details']['initial_equity']:,.2f}")
        print(f"   Current Equity: ${account['balances']['equity']:,.2f}")
        print(f"   API Key: {kraken_api_key[:10]}...{kraken_api_key[-5:]}")
        
        print(f"\n✅ Kraken account seeded successfully!")
        print(f"\n🧪 Test with:")
        print(f"   .venv/bin/python tests/run_test_suite.py --signal-testing --clean \\")
        print(f"     --environment staging --account-type mock --data-source mock \\")
        print(f"     --file tests/sample_signals/kraken/crypto_spot_trading.json --signal-count 2")
        
        return True
        
    except Exception as e:
        print(f"❌ Error seeding Kraken account: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = seed_kraken_account()
    sys.exit(0 if success else 1)
