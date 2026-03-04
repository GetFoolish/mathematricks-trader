#!/usr/bin/env python3
"""
Initialize mock account balances for testing
"""
import os
from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27018/?directConnection=true')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['mathematricks_trading']

trading_accounts_collection = db['trading_accounts']

print("=" * 80)
print("Initializing Mock Account Balances")
print("=" * 80)

# Mock account balances (each $1M for testing)
mock_accounts = {
    'IBKR-MOCK': {
        'equity': 1000000.00,
        'margin_available': 1000000.00,
        'margin_used': 0.00,
        'unrealized_pnl': 0.00
    },
    'VANTAGE_MOCK': {
        'equity': 1000000.00,
        'margin_available': 1000000.00,
        'margin_used': 0.00,
        'unrealized_pnl': 0.00
    },
    'OANDA_MOCK': {
        'equity': 1000000.00,
        'margin_available': 1000000.00,
        'margin_used': 0.00,
        'unrealized_pnl': 0.00
    },
    'BINANCE_MOCK': {
        'equity': 1000000.00,
        'margin_available': 1000000.00,
        'margin_used': 0.00,
        'unrealized_pnl': 0.00
    },
    'BYBIT_MOCK': {
        'equity': 1000000.00,
        'margin_available': 1000000.00,
        'margin_used': 0.00,
        'unrealized_pnl': 0.00
    }
}

for account_id, balances in mock_accounts.items():
    result = trading_accounts_collection.update_one(
        {"account_id": account_id},
        {
            "$set": {
                **balances,
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    if result.modified_count > 0 or result.upserted_id:
        print(f"✅ {account_id:20s} | Equity: ${balances['equity']:,.2f} | Margin: ${balances['margin_available']:,.2f}")
    else:
        print(f"ℹ️  {account_id:20s} | Already up to date")

print("\n" + "=" * 80)
print("✅ Mock account balances initialized!")
print("=" * 80)

# Verify
print("\n📋 Verification:")
for account in trading_accounts_collection.find({"account_id": {"$in": list(mock_accounts.keys())}}):
    print(f"   {account['account_id']:20s} | Equity: ${account.get('equity', 0):,.2f} | Margin: ${account.get('margin_available', 0):,.2f}")
