#!/usr/bin/env python3
"""
Setup IBKR test account in MongoDB for testing IBKR integration.
Run this before testing IBKR integration.
"""
from pymongo import MongoClient
from datetime import datetime

def setup_ibkr_test_account():
    """Create IBKR_Paper_Test account in trading_accounts collection"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client['mathematricks_trading']

    # Check if account already exists
    existing = db['trading_accounts'].find_one({"account_id": "IBKR_Paper_Test"})
    if existing:
        print("✅ IBKR_Paper_Test account already exists")
        print(f"   Current mode: {existing.get('mode', 'unknown')}")

        update_mode = input("\\nUpdate mode to paper_live? (y/n): ").lower()
        if update_mode == 'y':
            db['trading_accounts'].update_one(
                {"account_id": "IBKR_Paper_Test"},
                {"$set": {"mode": "paper_live"}}
            )
            print("✅ Updated mode to paper_live")
        return

    # Create new account
    account = {
        "account_id": "IBKR_Paper_Test",
        "broker": "IBKR",
        "mode": "paper_live",  # Start with paper_live mode
        "authentication_details": {
            "host": "127.0.0.1",
            "port": 4002,  # Paper port
            "client_id": 1
        },
        "balances": {
            "equity": 100000.0,
            "cash_balance": 100000.0,
            "margin_used": 0.0,
            "margin_available": 100000.0,
            "last_updated": datetime.utcnow()
        },
        "open_positions": [],
        "asset_classes": ["equity", "futures", "options", "forex", "crypto"],
        "status": "ACTIVE",
        "created_at": datetime.utcnow()
    }

    result = db['trading_accounts'].insert_one(account)
    print(f"✅ Created IBKR_Paper_Test account (ID: {result.inserted_id})")
    print("   Mode: paper_live")
    print("   Initial balance: $100,000")

def add_mode_to_mock_account():
    """Add mode field to existing Mock_Paper account if missing"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client['mathematricks_trading']

    mock_account = db['trading_accounts'].find_one({"account_id": "Mock_Paper"})
    if mock_account:
        if 'mode' not in mock_account:
            db['trading_accounts'].update_one(
                {"account_id": "Mock_Paper"},
                {"$set": {"mode": "paper_mock"}}
            )
            print("✅ Added mode: paper_mock to Mock_Paper account")
        else:
            print(f"✅ Mock_Paper account already has mode: {mock_account['mode']}")
    else:
        print("⚠️  Mock_Paper account not found (will be created on first use)")

def main():
    print("="*60)
    print("=== IBKR Test Account Setup ===")
    print("="*60)

    try:
        setup_ibkr_test_account()
        add_mode_to_mock_account()

        print("\n" + "="*60)
        print("✅ Setup complete!")
        print("="*60)
        print("\nNext steps:")
        print("1. Start IB Gateway: docker-compose up -d ib-gateway")
        print("2. Wait 30 seconds for gateway to start")
        print("3. Run tests: .venv/bin/python tests/signals_testing/run_ibkr_test.py")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
