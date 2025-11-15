#!/usr/bin/env python3
"""
Add Mock_Paper account to MongoDB for testing
"""
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

# Load environment
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Connect to MongoDB
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI)
db = client['mathematricks_trading']
trading_accounts = db['trading_accounts']

# Mock Paper account document
mock_account = {
    "_id": "Mock_Paper",
    "account_id": "Mock_Paper",
    "account_name": "Mock Paper Trading",
    "broker": "Mock",
    "account_number": "MOCK001",
    "account_type": "Paper",
    "authentication_details": {
        "auth_type": "MOCK",
        "initial_equity": 100000
    },
    "balances": {
        "equity": 100000.0,
        "cash": 50000.0,
        "margin_used": 0.0,
        "margin_available": 50000.0,
        "buying_power": 200000.0
    },
    "open_positions": [],
    "status": "ACTIVE",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}

# Check if account already exists
existing = trading_accounts.find_one({"_id": "Mock_Paper"})

if existing:
    print("Mock_Paper account already exists in database")
    print(f"Status: {existing.get('status')}")

    # Update to ACTIVE if needed
    if existing.get('status') != 'ACTIVE':
        trading_accounts.update_one(
            {"_id": "Mock_Paper"},
            {"$set": {"status": "ACTIVE", "updated_at": datetime.utcnow()}}
        )
        print("✅ Updated Mock_Paper account status to ACTIVE")
    else:
        print("✅ Mock_Paper account is already ACTIVE")
else:
    # Insert new account
    result = trading_accounts.insert_one(mock_account)
    print(f"✅ Created Mock_Paper account with ID: {result.inserted_id}")
    print(f"   Broker: Mock")
    print(f"   Initial Equity: $100,000")
    print(f"   Status: ACTIVE")

print("\n📋 All trading accounts:")
for account in trading_accounts.find():
    print(f"   - {account['account_id']}: {account['broker']} ({account['status']})")

client.close()
