#!/usr/bin/env python3
"""
Fix IBKR_Test_Stock strategy to have mode-specific accounts.

This ensures:
- mock_mock mode uses IBKR-MOCK account
- mock_live mode uses IBKR-MOCK account  
- paper_live mode uses IBKR-TESTING-ACCOUNT
- live_live mode uses appropriate live account

Without this, mock_mock mode incorrectly routes to IBKR-TESTING-ACCOUNT,
causing orders to fill at live prices instead of mock prices.
"""
from pymongo import MongoClient
from datetime import datetime
import os

def fix_strategy_accounts():
    """Update IBKR test strategies with mode-specific accounts"""
    # Use MONGODB_URI from environment or default to localhost
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27018/')
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000, directConnection=True)
    db = client['mathematricks_trading']
    
    # Update IBKR_Test_Stock strategy
    result = db.strategies.update_one(
        {"strategy_id": "IBKR_Test_Stock"},
        {
            "$set": {
                # MODE-SPECIFIC ACCOUNTS (v5 schema)
                "accounts": {
                    "mock": ["IBKR-MOCK"],              # For mock_mock, mock_live
                    "paper": ["IBKR-TESTING-ACCOUNT"],  # For paper_live
                    "live": []                           # No live account yet
                },
                "updated_at": datetime.utcnow()
            },
            # Remove old account_id field if it exists
            "$unset": {
                "account_id": ""
            }
        }
    )
    
    if result.modified_count > 0:
        print("✅ Updated IBKR_Test_Stock strategy with mode-specific accounts:")
        print("   • mock_mock/mock_live → IBKR-MOCK")
        print("   • paper_live → IBKR-TESTING-ACCOUNT")
    else:
        print("⚠️  IBKR_Test_Stock strategy not found or already up-to-date")
    
    # Verify the update
    strategy = db.strategies.find_one(
        {"strategy_id": "IBKR_Test_Stock"},
        {"strategy_id": 1, "accounts": 1, "_id": 0}
    )
    
    if strategy:
        print("\n📋 Current configuration:")
        print(f"   Strategy: {strategy.get('strategy_id')}")
        print(f"   Accounts: {strategy.get('accounts')}")
    
    client.close()

if __name__ == "__main__":
    fix_strategy_accounts()
