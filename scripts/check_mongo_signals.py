#!/usr/bin/env python3
"""Quick script to check MongoDB Atlas for recent signals"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from pymongo import MongoClient

# Connect to MongoDB Atlas
mongo_uri = os.getenv('MONGODB_URI_CLOUD')
if not mongo_uri:
    print("❌ MONGODB_URI_CLOUD not found in environment!")
    print("   Make sure .env file exists with MONGODB_URI_CLOUD set")
    sys.exit(1)

print(f"🔗 Connecting to: {mongo_uri[:50]}...")
client = MongoClient(mongo_uri)
db = client['mathematricks_trading']

# Get the most recent signals (last 10 minutes)
recent_time = datetime.utcnow() - timedelta(minutes=10)
signals = list(db.signal_store.find(
    {'created_at': {'$gte': recent_time}},
    {'signal_id': 1, 'instrument': 1, 'signal_legs': 1, 'created_at': 1}
).sort('created_at', -1).limit(10))

print(f"📊 Found {len(signals)} recent signals in MongoDB Atlas (last 10 min):\n")

if len(signals) == 0:
    print("⚠️  No signals found in last 10 minutes!")
    print("\nChecking total signal_store count...")
    total = db.signal_store.count_documents({})
    print(f"Total signals in collection: {total}")
    
    if total > 0:
        print("\nMost recent signal:")
        latest = db.signal_store.find_one({}, sort=[('created_at', -1)])
        print(f"  Signal ID: {latest.get('signal_id')}")
        print(f"  Created: {latest.get('created_at')}")
else:
    for sig in signals:
        signal_id = sig.get('signal_id', 'N/A')
        instrument = sig.get('instrument', 'N/A')
        legs = sig.get('signal_legs', [])
        created = sig.get('created_at', 'N/A')
        
        print(f"Signal: {signal_id}")
        print(f"  Instrument: {instrument}")
        print(f"  Created: {created}")
        print(f"  Legs: {len(legs)}")
        
        for i, leg in enumerate(legs):
            exec_status = leg.get('execution', {}).get('status', 'UNKNOWN')
            decision_status = leg.get('decision', {}).get('status', 'UNKNOWN')  
            qty = leg.get('execution', {}).get('total_quantity_filled', 0)
            print(f"    Leg {i}: Decision={decision_status}, Exec={exec_status}, Qty={qty}")
        print()
