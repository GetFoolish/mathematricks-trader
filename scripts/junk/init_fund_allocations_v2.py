#!/usr/bin/env python3
"""
Initialize Fund Allocations in MongoDB (v2 - Proper Workflow)

This script creates portfolio test allocations first, then approves them to assign to mock-fund-1.
Follows the proper workflow: portfolio_tests (draft) → portfolio_allocations (approved, assigned to fund).
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

# Get MongoDB connection from environment or use default (use MONGODB_URI_LOCAL for scripts running outside Docker)
MONGODB_URI = os.getenv('MONGODB_URI_LOCAL', 'mongodb://localhost:27018/?directConnection=true')

def init_fund_allocations():
    """
    Initialize fund allocations for all strategies.
    Step 1: Create allocation in portfolio_tests
    Step 2: Approve it and assign to mock-fund-1 in portfolio_allocations
    """
    print("=" * 80)
    print("Initializing Fund Allocations (Test → Approve → Assign)")
    print("=" * 80)
    
    # Connect to MongoDB
    print(f"Connecting to MongoDB: {MONGODB_URI}")
    client = MongoClient(MONGODB_URI)
    db = client['mathematricks_trading']
    
    # Collections
    strategies_collection = db['strategies']
    portfolio_tests_collection = db['portfolio_tests']
    portfolio_allocations_collection = db['portfolio_allocations']
    
    # Get all strategies
    strategies = list(strategies_collection.find({}, {"strategy_id": 1, "_id": 0}))
    strategy_ids = [s['strategy_id'] for s in strategies]
    
    print(f"\nFound {len(strategy_ids)} strategies:")
    for sid in strategy_ids:
        print(f"  - {sid}")
    
    if not strategy_ids:
        print("❌ No strategies found! Please add strategies first.")
        return
    
    # Calculate equal allocation percentage
    allocation_pct = round(100.0 / len(strategy_ids), 2)
    
    # Create allocations dictionary
    allocations = {strategy_id: allocation_pct for strategy_id in strategy_ids}
    
    # STEP 1: Create test allocation in portfolio_tests
    print("\n" + "=" * 80)
    print("STEP 1: Creating test allocation in portfolio_tests")
    print("=" * 80)
    
    test_allocation_doc = {
        "allocation_name": "Equal Weight Test Allocation",
        "description": f"Equal weight allocation across {len(strategy_ids)} strategies ({allocation_pct}% each)",
        "allocations": allocations,
        "status": "PENDING",  # Not yet approved
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    test_result = portfolio_tests_collection.insert_one(test_allocation_doc)
    test_allocation_id = test_result.inserted_id
    
    print(f"✅ Created test allocation:")
    print(f"   Allocation ID: {test_allocation_id}")
    print(f"   Allocation Name: Equal Weight Test Allocation")
    print(f"   Strategies: {len(strategy_ids)}")
    print(f"   Allocation per strategy: {allocation_pct}%")
    print(f"   Status: PENDING")
    
    # STEP 2: Approve and assign to mock-fund-1 in portfolio_allocations
    print("\n" + "=" * 80)
    print("STEP 2: Approving allocation and assigning to mock-fund-1")
    print("=" * 80)
    
    # Check if active allocation already exists for this fund
    existing_active = portfolio_allocations_collection.find_one({
        "fund_id": "mock-fund-1",
        "status": "ACTIVE"
    })
    
    if existing_active:
        print(f"⚠️  Found existing ACTIVE allocation for mock-fund-1")
        print(f"   Archiving existing allocation: {existing_active.get('allocation_name')}")
        
        # Archive the old allocation
        portfolio_allocations_collection.update_one(
            {"_id": existing_active['_id']},
            {"$set": {"status": "ARCHIVED", "updated_at": datetime.utcnow()}}
        )
        print(f"✅ Archived old allocation")
    
    # Create new ACTIVE allocation with fund assignment
    approved_allocation_doc = {
        "fund_id": "mock-fund-1",
        "allocation_name": "Equal Weight Test Allocation",
        "description": f"Equal weight allocation across {len(strategy_ids)} strategies ({allocation_pct}% each)",
        "allocations": allocations,
        "status": "ACTIVE",
        "test_allocation_id": str(test_allocation_id),  # Reference to original test
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    approved_result = portfolio_allocations_collection.insert_one(approved_allocation_doc)
    
    print(f"✅ Created ACTIVE portfolio allocation:")
    print(f"   Fund: mock-fund-1")
    print(f"   Allocation ID: {approved_result.inserted_id}")
    print(f"   Allocation Name: Equal Weight Test Allocation")
    print(f"   Strategies: {len(strategy_ids)}")
    print(f"   Allocation per strategy: {allocation_pct}%")
    print(f"   Status: ACTIVE")
    print(f"\nAllocations:")
    for strategy_id, pct in sorted(allocations.items()):
        print(f"   - {strategy_id}: {pct}%")
    
    # Update test allocation status to APPROVED
    portfolio_tests_collection.update_one(
        {"_id": test_allocation_id},
        {"$set": {"status": "APPROVED", "updated_at": datetime.utcnow()}}
    )
    
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
    print("\n💡 Next steps:")
    print("   1. Restart cerebro-service: make restart-cerebro")
    print("   2. Run test signals: .venv/bin/python -u tests/signals_testing/run_full_test.py")


if __name__ == "__main__":
    try:
        init_fund_allocations()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
