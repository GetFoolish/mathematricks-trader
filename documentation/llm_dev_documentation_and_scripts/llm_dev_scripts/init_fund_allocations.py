#!/usr/bin/env python3
"""
Initialize Fund Allocations in MongoDB

This script creates portfolio_allocations documents for all strategies in the system.
The allocations are used by Cerebro to determine position sizing for each signal.
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime

# Get MongoDB connection from environment or use default (use MONGODB_URI_LOCAL for scripts running outside Docker)
MONGODB_URI = os.getenv('MONGODB_URI_LOCAL', 'mongodb://localhost:27018/?directConnection=true')

def init_fund_allocations():
    """
    Initialize fund allocations for all strategies.
    """
    print("=" * 80)
    print("Initializing Fund Allocations")
    print("=" * 80)
    
    # Connect to MongoDB
    print(f"Connecting to MongoDB: {MONGODB_URI}")
    client = MongoClient(MONGODB_URI)
    db = client['mathematricks_trading']
    
    # Collections
    strategies_collection = db['strategies']
    portfolio_allocations_collection = db['portfolio_allocations']
    
    # Get all strategies
    strategies = list(strategies_collection.find({}, {"strategy_id": 1, "_id": 0}))
    strategy_ids = [s['strategy_id'] for s in strategies]
    
    print(f"\nFound {len(strategy_ids)} strategies:")
    for sid in strategy_ids:
        print(f"  - {sid}")
    
    # Check if allocations already exist
    existing_allocations = list(portfolio_allocations_collection.find({
        "fund_id": "mock-fund-1",
        "status": "ACTIVE"
    }))
    
    if existing_allocations:
        print(f"\n⚠️  Found {len(existing_allocations)} existing ACTIVE allocations for mock-fund-1")
        print("Do you want to DELETE existing allocations and create new ones? (yes/no)")
        response = input().strip().lower()
        
        if response != 'yes':
            print("Aborted. No changes made.")
            return
        
        # Delete existing allocations
        result = portfolio_allocations_collection.delete_many({
            "fund_id": "mock-fund-1",
            "status": "ACTIVE"
        })
        print(f"✅ Deleted {result.deleted_count} existing allocation(s)")
    
    # Calculate equal allocation percentage
    allocation_pct = round(100.0 / len(strategy_ids), 2) if strategy_ids else 0.0
    
    # Create allocations dictionary
    allocations = {strategy_id: allocation_pct for strategy_id in strategy_ids}
    
    # Create portfolio_allocation document
    allocation_doc = {
        "fund_id": "mock-fund-1",
        "allocation_name": "Equal Weight Test Allocation",
        "description": f"Equal weight allocation across {len(strategy_ids)} strategies ({allocation_pct}% each)",
        "allocations": allocations,
        "status": "ACTIVE",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert allocation
    result = portfolio_allocations_collection.insert_one(allocation_doc)
    
    print(f"\n✅ Created ACTIVE portfolio allocation:")
    print(f"   Fund: mock-fund-1")
    print(f"   Allocation Name: Equal Weight Test Allocation")
    print(f"   Strategies: {len(strategy_ids)}")
    print(f"   Allocation per strategy: {allocation_pct}%")
    print(f"   Document ID: {result.inserted_id}")
    print(f"\nAllocations:")
    for strategy_id, pct in allocations.items():
        print(f"   - {strategy_id}: {pct}%")
    
    # Verify
    verification = portfolio_allocations_collection.find_one({
        "fund_id": "mock-fund-1",
        "status": "ACTIVE"
    })
    
    if verification:
        print(f"\n✅ Verification successful - allocation is active in MongoDB")
    else:
        print(f"\n❌ Verification failed - allocation not found")
        return
    
    print("\n" + "=" * 80)
    print("Fund allocation initialization complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        init_fund_allocations()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
