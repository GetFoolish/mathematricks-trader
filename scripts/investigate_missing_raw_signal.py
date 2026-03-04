#!/usr/bin/env python3
"""
Investigate why the second raw signal is missing
"""
import os
import sys
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI_LOCAL', 'mongodb://localhost:27018/?directConnection=true')
client = MongoClient(MONGODB_URI)
db = client['mathematricks_trading']

signal_id = "sig_1771432766_3413_432766_1771432766"

print("=" * 80)
print("INVESTIGATING MISSING RAW SIGNAL")
print("=" * 80)
print()

# 1. Get the signal_store document
print("1. SIGNAL_STORE DOCUMENT:")
print("-" * 80)
signal_store = db.signal_store.find_one({"signal_id": signal_id})
if signal_store:
    print(f"Signal ID: {signal_store['signal_id']}")
    print(f"Signal Legs: {len(signal_store.get('signal_legs', []))}")
    print()
    
    raw_signal_ids = []
    for i, leg in enumerate(signal_store.get('signal_legs', [])):
        raw_signal_id = leg.get('raw_signal_id')
        print(f"  Leg {i}:")
        print(f"    leg_id: {leg.get('leg_id')}")
        print(f"    leg_type: {leg.get('leg_type')}")
        print(f"    raw_signal_id: {raw_signal_id}")
        if raw_signal_id:
            raw_signal_ids.append(raw_signal_id)
        print()
else:
    print("Signal not found in signal_store!")
    sys.exit(1)

print()
print("=" * 80)
print("2. SEARCHING FOR RAW SIGNALS BY OBJECTID:")
print("-" * 80)
print()

for i, raw_id in enumerate(raw_signal_ids):
    print(f"Looking for raw signal {i+1}: {raw_id}")
    
    # Try to find by ObjectId
    try:
        raw_signal = db.trading_signals_raw.find_one({"_id": ObjectId(raw_id)})
        if raw_signal:
            print(f"  ✓ FOUND!")
            print(f"  signalID: {raw_signal.get('signalID')}")
            print(f"  signal_type: {raw_signal.get('signal_type')}")
            print(f"  received_at: {raw_signal.get('received_at')}")
            if 'signals' in raw_signal:
                print(f"  Number of signal legs: {len(raw_signal['signals'])}")
                for j, sig_leg in enumerate(raw_signal['signals']):
                    print(f"    Leg {j}: {sig_leg.get('instrument')} | {sig_leg.get('action')} | {sig_leg.get('direction')} | Qty: {sig_leg.get('quantity')} | Price: {sig_leg.get('price')}")
        else:
            print(f"  ✗ NOT FOUND in trading_signals_raw collection")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
    print()

print()
print("=" * 80)
print("3. ALL RAW SIGNALS FOR THIS SIGNAL_ID:")
print("-" * 80)
print()

# Search by signalID prefix
all_raw_signals = list(db.trading_signals_raw.find({
    "signalID": {"$regex": f"^{signal_id}"}
}).sort("received_at", 1))

print(f"Found {len(all_raw_signals)} raw signals with signalID starting with '{signal_id}'")
print()

for i, raw in enumerate(all_raw_signals):
    print(f"Raw Signal {i+1}:")
    print(f"  _id: {raw.get('_id')}")
    print(f"  signalID: {raw.get('signalID')}")
    print(f"  signal_type: {raw.get('signal_type')}")
    print(f"  received_at: {raw.get('received_at')}")
    print()

print()
print("=" * 80)
print("4. CHECKING FOR EXIT SIGNALS:")
print("-" * 80)
print()

# Look for any EXIT signals
exit_signals = list(db.trading_signals_raw.find({
    "signal_type": "EXIT"
}).sort("received_at", -1).limit(10))

print(f"Found {len(exit_signals)} recent EXIT signals in trading_signals_raw")
print()

for i, exit_sig in enumerate(exit_signals):
    print(f"EXIT Signal {i+1}:")
    print(f"  _id: {exit_sig.get('_id')}")
    print(f"  signalID: {exit_sig.get('signalID')}")
    print(f"  received_at: {exit_sig.get('received_at')}")
    print()

print()
print("=" * 80)
print("CONCLUSION:")
print("-" * 80)
print()
print(f"Expected raw signals: {len(raw_signal_ids)}")
print(f"Found raw signals with matching signalID: {len(all_raw_signals)}")
print()
if len(raw_signal_ids) != len(all_raw_signals):
    print("⚠️  MISMATCH: The signal_store references raw signals that don't exist!")
    print("This suggests the raw signals were deleted or never created.")
