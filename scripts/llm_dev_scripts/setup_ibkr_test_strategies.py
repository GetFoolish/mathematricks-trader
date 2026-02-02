#!/usr/bin/env python3
"""
Setup test strategy documents in MongoDB for IBKR testing.
Run this to create the strategy documents needed for IBKR test signals.
"""
from pymongo import MongoClient
from datetime import datetime

def setup_test_strategies():
    """Create strategy documents for IBKR test signals"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client['mathematricks_trading']

    strategies = [
        {
            "strategy_id": "IBKR_Test_Stock",
            "strategy_name": "IBKR Test - Stock",
            "description": "Test strategy for IBKR stock trading (AAPL)",
            "account_id": "IBKR_Paper_Test",
            "passphrase": "test_password_123",
            "asset_class": "STOCK",
            "status": "ACTIVE",
            "risk_parameters": {
                "max_position_size": 0.1,  # 10% max per position
                "max_leverage": 1.0
            },
            "created_at": datetime.utcnow()
        },
        {
            "strategy_id": "IBKR_Test_Crypto",
            "strategy_name": "IBKR Test - Crypto",
            "description": "Test strategy for IBKR crypto trading (BTC)",
            "account_id": "IBKR_Paper_Test",
            "passphrase": "test_password_123",
            "asset_class": "CRYPTO",
            "status": "ACTIVE",
            "risk_parameters": {
                "max_position_size": 0.1,
                "max_leverage": 1.0
            },
            "created_at": datetime.utcnow()
        },
        {
            "strategy_id": "IBKR_Test_Forex",
            "strategy_name": "IBKR Test - Forex",
            "description": "Test strategy for IBKR forex trading (EUR/USD)",
            "account_id": "IBKR_Paper_Test",
            "passphrase": "test_password_123",
            "asset_class": "FOREX",
            "status": "ACTIVE",
            "risk_parameters": {
                "max_position_size": 0.1,
                "max_leverage": 1.0
            },
            "created_at": datetime.utcnow()
        },
        {
            "strategy_id": "IBKR_Test_Future",
            "strategy_name": "IBKR Test - Future",
            "description": "Test strategy for IBKR commodity futures (Gold)",
            "account_id": "IBKR_Paper_Test",
            "passphrase": "test_password_123",
            "asset_class": "FUTURE",
            "status": "ACTIVE",
            "risk_parameters": {
                "max_position_size": 0.1,
                "max_leverage": 1.0
            },
            "created_at": datetime.utcnow()
        },
        {
            "strategy_id": "IBKR_Test_Option",
            "strategy_name": "IBKR Test - Option",
            "description": "Test strategy for IBKR options (SPY)",
            "account_id": "IBKR_Paper_Test",
            "passphrase": "test_password_123",
            "asset_class": "OPTION",
            "status": "ACTIVE",
            "risk_parameters": {
                "max_position_size": 0.1,
                "max_leverage": 1.0
            },
            "created_at": datetime.utcnow()
        }
    ]

    print("=" * 60)
    print("=== Creating IBKR Test Strategy Documents ===")
    print("=" * 60)

    for strategy in strategies:
        strategy_id = strategy['strategy_id']

        # Check if already exists
        existing = db['strategies'].find_one({"strategy_id": strategy_id})
        if existing:
            print(f"✅ {strategy_id} already exists")

            # Update account_id if needed
            if existing.get('account_id') != 'IBKR_Paper_Test':
                db['strategies'].update_one(
                    {"strategy_id": strategy_id},
                    {"$set": {"account_id": "IBKR_Paper_Test"}}
                )
                print(f"   Updated account_id to IBKR_Paper_Test")
        else:
            result = db['strategies'].insert_one(strategy)
            print(f"✅ Created {strategy_id} (ID: {result.inserted_id})")

    print("\n" + "=" * 60)
    print("✅ Strategy setup complete!")
    print("=" * 60)
    print("\nCreated strategies:")
    for strategy in strategies:
        print(f"  - {strategy['strategy_id']:25} ({strategy['asset_class']})")
    print("\nAll strategies mapped to account: IBKR_Paper_Test")

def main():
    try:
        setup_test_strategies()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
