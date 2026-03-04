#!/usr/bin/env python3
"""
Assign strategies to trading accounts based on asset class compatibility
"""
import os
from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27018/?directConnection=true')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['mathematricks_trading']

strategies_collection = db['strategies']
trading_accounts_collection = db['trading_accounts']

print("=" * 80)
print("Assigning Strategies to Trading Accounts")
print("=" * 80)

# Strategy-to-asset-class mapping
strategy_asset_classes = {
    'Com1-Met': 'commodities',
    'Com2-Ag': 'commodities',
    'Com3-Mkt': 'commodities',
    'Com4-Misc': 'commodities',
    'FloridaForex': 'forex',
    'SPX_0DE_Opt': 'options',
    'SPX_1-D_Opt': 'options',
    'SPY': 'equity',
    'TLT': 'equity'
}

# Update each strategy with correct asset_class and assign to compatible accounts
for strategy_id, asset_class in strategy_asset_classes.items():
    print(f"\n📊 Processing {strategy_id} (asset_class: {asset_class})")
    
    # Find accounts that support this asset class
    compatible_accounts = []
    for account in trading_accounts_collection.find({"fund_id": "mock-fund-1", "status": "ACTIVE"}):
        account_id = account['account_id']
        asset_classes = account.get('asset_classes', {})
        
        # Check if account supports this asset class
        supported_assets = asset_classes.get(asset_class, [])
        if supported_assets and (supported_assets == ['all'] or len(supported_assets) > 0):
            compatible_accounts.append(account_id)
            print(f"   ✓ {account_id} supports {asset_class}")
    
    if not compatible_accounts:
        print(f"   ⚠️  No compatible accounts found for {strategy_id}")
        continue
    
    # Update strategy with asset_class and accounts
    result = strategies_collection.update_one(
        {"strategy_id": strategy_id},
        {
            "$set": {
                "asset_class": asset_class,
                "accounts": compatible_accounts,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        print(f"   ✅ Assigned {strategy_id} to accounts: {compatible_accounts}")
    else:
        print(f"   ℹ️  {strategy_id} already up to date")

print("\n" + "=" * 80)
print("✅ Strategy-to-account assignment complete!")
print("=" * 80)

# Verify assignments
print("\n📋 Verification:")
for strategy in strategies_collection.find({}):
    strategy_id = strategy.get('strategy_id')
    asset_class = strategy.get('asset_class', 'unknown')
    accounts = strategy.get('accounts', [])
    print(f"   {strategy_id:20s} | {asset_class:15s} | {', '.join(accounts) if accounts else 'NO ACCOUNTS'}")
