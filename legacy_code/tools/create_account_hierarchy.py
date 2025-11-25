#!/usr/bin/env python3
"""
Initialize account hierarchy in MongoDB
Creates the account_hierarchy collection with fund → brokers → accounts structure
"""
import os
import sys
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
if not MONGODB_URI:
    print("❌ ERROR: MONGODB_URI not set in environment")
    sys.exit(1)

client = MongoClient(MONGODB_URI)
db = client['mathematricks_trading']

print("=" * 80)
print("CREATING ACCOUNT HIERARCHY")
print("=" * 80)

# Create account_hierarchy document
hierarchy = {
    "_id": "mathematricks_fund",
    "fund_name": "Mathematricks Capital",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
    "brokers": [
        {
            "broker_id": "IBKR",
            "broker_name": "Interactive Brokers",
            "connection": {
                "host": os.getenv('IBKR_HOST', '127.0.0.1'),
                "port": int(os.getenv('IBKR_PORT', '7497')),
                "client_id": int(os.getenv('IBKR_CLIENT_ID', '1'))
            },
            "accounts": [
                {
                    "account_id": "IBKR_Main",
                    "account_type": "MARGIN",
                    "status": "ACTIVE",
                    "description": "Primary trading account",
                    "created_at": datetime.utcnow()
                }
            ]
        }
        # Additional brokers can be added here:
        # {
        #     "broker_id": "ALPACA",
        #     "broker_name": "Alpaca Markets",
        #     "connection": {
        #         "api_key_env": "ALPACA_API_KEY",
        #         "api_secret_env": "ALPACA_API_SECRET",
        #         "base_url": "https://paper-api.alpaca.markets"
        #     },
        #     "accounts": [
        #         {
        #             "account_id": "ALPACA_Main",
        #             "account_type": "MARGIN",
        #             "status": "ACTIVE",
        #             "description": "Alpaca paper trading",
        #             "created_at": datetime.utcnow()
        #         }
        #     ]
        # }
    ]
}

# Upsert account hierarchy (update if exists, create if not)
print("\n1. Creating/updating account_hierarchy document...")
result = db.account_hierarchy.update_one(
    {"_id": "mathematricks_fund"},
    {"$set": hierarchy},
    upsert=True
)

if result.upserted_id:
    print(f"   ✅ Created new account_hierarchy: {result.upserted_id}")
else:
    print(f"   ✅ Updated existing account_hierarchy")

# Verify creation
print("\n2. Verifying account_hierarchy...")
hierarchy_doc = db.account_hierarchy.find_one({"_id": "mathematricks_fund"})
if hierarchy_doc:
    print(f"   ✅ Fund: {hierarchy_doc['fund_name']}")
    print(f"   ✅ Brokers: {len(hierarchy_doc['brokers'])}")
    for broker in hierarchy_doc['brokers']:
        print(f"      - {broker['broker_name']} ({broker['broker_id']})")
        print(f"        Accounts: {len(broker['accounts'])}")
        for account in broker['accounts']:
            print(f"          • {account['account_id']} ({account['status']})")
else:
    print("   ❌ ERROR: Could not find account_hierarchy document")
    sys.exit(1)

# Create indexes for efficient queries
print("\n3. Creating indexes...")

# Index on account_state collection for broker_id queries
db.account_state.create_index([("broker_id", 1), ("account_id", 1), ("timestamp", -1)])
print("   ✅ Created index: account_state (broker_id, account_id, timestamp)")

# Index on fund_state collection for timestamp queries
db.fund_state.create_index([("timestamp", -1)])
print("   ✅ Created index: fund_state (timestamp)")

print("\n" + "=" * 80)
print("✅ ACCOUNT HIERARCHY CREATED SUCCESSFULLY")
print("=" * 80)
print(f"\nFund: {hierarchy_doc['fund_name']}")
print(f"Total Brokers: {len(hierarchy_doc['brokers'])}")
total_accounts = sum(len(b['accounts']) for b in hierarchy_doc['brokers'])
print(f"Total Accounts: {total_accounts}")
print("\nYou can now run AccountDataService to poll all accounts.")
print("=" * 80)
