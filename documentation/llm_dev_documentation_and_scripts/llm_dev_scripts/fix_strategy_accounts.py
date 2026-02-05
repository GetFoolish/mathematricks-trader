#!/usr/bin/env python3
"""
Emergency Fix Script: Add accounts field to strategies
-------------------------------------------------------
This script adds the 'accounts' field to all strategies in MongoDB
that are missing this field or have it empty.

Default account: Mock_Paper

Usage:
    python scripts/fix_strategy_accounts.py
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime

def main():
    # Get MongoDB URI from environment
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27018/?directConnection=true')
    
    print("=" * 60)
    print("EMERGENCY FIX: Adding accounts field to strategies")
    print("=" * 60)
    print(f"MongoDB URI: {mongodb_uri}")
    print(f"Database: mathematricks_trading")
    print(f"Collection: strategies")
    print(f"Default account: Mock_Paper")
    print()
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        db = client['mathematricks_trading']
        strategies_collection = db['strategies']
        
        # Find strategies without accounts field or with empty accounts
        query = {
            "$or": [
                {"accounts": {"$exists": False}},
                {"accounts": []},
                {"accounts": None}
            ]
        }
        
        # Count strategies needing fix
        strategies_to_fix = list(strategies_collection.find(query))
        count = len(strategies_to_fix)
        
        if count == 0:
            print("✅ All strategies already have accounts field configured!")
            print("   No updates needed.")
            return
        
        print(f"Found {count} strategies missing accounts field:")
        for strategy in strategies_to_fix:
            strategy_id = strategy.get('strategy_id', 'UNKNOWN')
            print(f"  • {strategy_id}")
        
        print()
        print("Updating strategies...")
        
        # Update all strategies
        result = strategies_collection.update_many(
            query,
            {
                "$set": {
                    "accounts": ["Mock_Paper"],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print()
        print("=" * 60)
        print("✅ UPDATE COMPLETE")
        print("=" * 60)
        print(f"Matched documents: {result.matched_count}")
        print(f"Modified documents: {result.modified_count}")
        print()
        
        # Verify fix
        remaining = strategies_collection.count_documents(query)
        if remaining == 0:
            print("✅ VERIFICATION PASSED: All strategies now have accounts field")
        else:
            print(f"⚠️  WARNING: {remaining} strategies still missing accounts field")
        
        # List updated strategies
        print()
        print("Updated strategies:")
        updated_strategies = strategies_collection.find(
            {"accounts": ["Mock_Paper"]},
            {"strategy_id": 1, "accounts": 1, "_id": 0}
        )
        
        for strategy in updated_strategies:
            strategy_id = strategy.get('strategy_id', 'UNKNOWN')
            accounts = strategy.get('accounts', [])
            print(f"  • {strategy_id}: {accounts}")
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
