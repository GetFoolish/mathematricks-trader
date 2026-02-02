#!/usr/bin/env python3
import pymongo
import json

# Connect without replica set configuration
client = pymongo.MongoClient("mongodb://localhost:27018/", directConnection=True)
db = client.mathematricks_trading

signals = db.signal_store.find({}).sort("created_at", -1).limit(1)

for signal in signals:
    print(f"\nSignal ID: {signal.get('signal_id')}")
    print(f"Legs: {len(signal.get('legs', []))}")
    
    for i, leg in enumerate(signal.get('legs', []), 1):
        print(f"\n--- Leg {i}: {leg.get('leg_id')} ---")
        
        timestamps = leg.get('processing_timestamps', {})
        print(f"Timestamps:")
        for key, val in timestamps.items():
            print(f"  {key}: {val}")
        
        lag = leg.get('processing_lag', {}) or {}
        print(f"\nLag:")
        if lag:
            print(f"  Summary: {lag.get('summary', 'N/A')}")
            print(f"  Total: {lag.get('total_lag_ms', 'N/A')}ms")
        else:
            print(f"  No lag calculated (execution not completed)")
        
        exec_data = leg.get('execution') or {}
        exec_status = exec_data.get('status', 'N/A') if exec_data else 'N/A'
        print(f"  Execution status: {exec_status}")
