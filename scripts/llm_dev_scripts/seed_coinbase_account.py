#!/usr/bin/env python3
"""
Seed Coinbase Account to MongoDB
Creates COINBASE_CANADA account, strategy, and fund integration
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

def seed_coinbase_integration():
    """Create Coinbase account, strategy, and fund integration"""
    
    # Get MongoDB URI
    mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27018'
    
    # Get Coinbase API credentials from environment
    coinbase_api_key = os.getenv('COINBASE_API_KEY_UAE_NAME')
    coinbase_api_secret = os.getenv('COINBASE_API_KEY_UAE_KEY')
    
    if not coinbase_api_key or not coinbase_api_secret:
        print("❌ Error: COINBASE_API_KEY_UAE_NAME and COINBASE_API_KEY_UAE_KEY must be set in .env")
        print("   Add these lines to your .env file:")
        print("   COINBASE_API_KEY_UAE_NAME=organizations/xxx/apiKeys/yyy")
        print("   COINBASE_API_KEY_UAE_KEY=-----BEGIN EC PRIVATE KEY-----...")
        return False
    
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB: {mongodb_uri}")
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()  # Test connection
        
        db = client['mathematricks_trading']
        
        # ============================================
        # 1. CREATE/UPDATE COINBASE ACCOUNT
        # ============================================
        print("\n📊 Step 1: Creating Coinbase account...")
        trading_accounts = db['trading_accounts']
        
        existing_account = trading_accounts.find_one({"account_id": "COINBASE_CANADA"})
        
        coinbase_account = {
            "account_id": "COINBASE_CANADA",
            "broker": "Coinbase",
            "account_type": "mock",  # Using mock for paper trading
            "mode": ["mock_mock", "mock_live", "paper_live"],
            "status": "ACTIVE",
            "authentication_details": {
                "api_key": coinbase_api_key,
                "api_secret": coinbase_api_secret,
                "sandbox": True,  # Use Coinbase sandbox for testing
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
                "last_updated": datetime.now()
            },
            "open_positions": [],
            "broker_positions_snapshot": [],
            "created_at": existing_account.get('created_at', datetime.now()) if existing_account else datetime.now(),
            "updated_at": datetime.now()
        }
        
        if existing_account:
            trading_accounts.update_one(
                {"account_id": "COINBASE_CANADA"},
                {"$set": coinbase_account}
            )
            print(f"   ✅ Updated existing Coinbase account")
        else:
            trading_accounts.insert_one(coinbase_account)
            print(f"   ✅ Created new Coinbase account")
        
        # ============================================
        # 2. CREATE/UPDATE CRYPTO STRATEGY
        # ============================================
        print("\n🎯 Step 2: Creating Coinbase crypto strategy...")
        strategies = db['strategies']
        
        existing_strategy = strategies.find_one({"strategy_name": "Coinbase_Crypto_Momentum"})
        
        crypto_strategy = {
            "strategy_name": "Coinbase_Crypto_Momentum",
            "description": "Cryptocurrency momentum trading on Coinbase (BTC, ETH, SOL)",
            "status": "ACTIVE",
            "environment": "staging",
            "accounts": ["COINBASE_CANADA"],  # Link to Coinbase account
            "instruments": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "trading_hours": "24/7",
            "max_positions": 10,
            "risk_parameters": {
                "max_position_size": 10000.0,
                "max_loss_per_trade": 500.0,
                "daily_loss_limit": 2000.0
            },
            "created_at": existing_strategy.get('created_at', datetime.now()) if existing_strategy else datetime.now(),
            "updated_at": datetime.now()
        }
        
        if existing_strategy:
            strategies.update_one(
                {"strategy_name": "Coinbase_Crypto_Momentum"},
                {"$set": crypto_strategy}
            )
            print(f"   ✅ Updated existing strategy")
        else:
            strategies.insert_one(crypto_strategy)
            print(f"   ✅ Created new strategy")
        
        # ============================================
        # 3. CREATE/UPDATE FUND WITH COINBASE ACCOUNT
        # ============================================
        print("\n💼 Step 3: Adding Coinbase account to fund...")
        funds = db['funds']
        
        # Check if staging fund exists
        existing_fund = funds.find_one({"fund_name": "Staging_Test_Fund"})
        
        if existing_fund:
            # Add COINBASE_CANADA to accounts if not already there
            current_accounts = existing_fund.get('accounts', [])
            if "COINBASE_CANADA" not in current_accounts:
                current_accounts.append("COINBASE_CANADA")
                funds.update_one(
                    {"fund_name": "Staging_Test_Fund"},
                    {
                        "$set": {
                            "accounts": current_accounts,
                            "updated_at": datetime.now()
                        }
                    }
                )
                print(f"   ✅ Added COINBASE_CANADA to existing fund")
            else:
                print(f"   ℹ️  COINBASE_CANADA already in fund")
        else:
            # Create new fund with COINBASE_CANADA
            new_fund = {
                "fund_name": "Staging_Test_Fund",
                "description": "Test fund for staging environment with multiple brokers",
                "status": "ACTIVE",
                "environment": "staging",
                "accounts": ["COINBASE_CANADA"],
                "strategies": ["Coinbase_Crypto_Momentum"],
                "total_equity": 100000.0,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            funds.insert_one(new_fund)
            print(f"   ✅ Created new fund with COINBASE_CANADA")
        
        # ============================================
        # SUMMARY
        # ============================================
        print("\n" + "="*60)
        print("✅ COINBASE INTEGRATION COMPLETE")
        print("="*60)
        
        # Verify account
        account = trading_accounts.find_one({"account_id": "COINBASE_CANADA"})
        print(f"\n📋 Account: {account['account_id']}")
        print(f"   Broker: {account['broker']}")
        print(f"   Modes: {account['mode']}")
        print(f"   Equity: ${account['balances']['equity']:,.2f}")
        print(f"   Sandbox: {account['authentication_details']['sandbox']}")
        
        # Verify strategy
        strategy = strategies.find_one({"strategy_name": "Coinbase_Crypto_Momentum"})
        print(f"\n🎯 Strategy: {strategy['strategy_name']}")
        print(f"   Accounts: {strategy['accounts']}")
        print(f"   Instruments: {strategy['instruments']}")
        
        # Verify fund
        fund = funds.find_one({"fund_name": "Staging_Test_Fund"})
        print(f"\n💼 Fund: {fund['fund_name']}")
        print(f"   Accounts: {fund['accounts']}")
        
        print(f"\n🧪 Test signal flow:")
        print(f"   Signal → Strategy (Coinbase_Crypto_Momentum)")
        print(f"   Strategy → Account (COINBASE_CANADA)")
        print(f"   Account → Broker (Coinbase sandbox)")
        
        print(f"\n🧪 Next steps:")
        print(f"   1. Create sample signals: tests/sample_signals/coinbase/crypto_spot_trading.json")
        print(f"   2. Test mock_mock mode (simulated)")
        print(f"   3. Test mock_live mode (real prices)")
        print(f"   4. Test paper_live mode (sandbox)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = seed_coinbase_integration()
    sys.exit(0 if success else 1)
