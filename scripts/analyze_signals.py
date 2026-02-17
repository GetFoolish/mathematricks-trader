#!/usr/bin/env python3
"""Quick analysis of signal duplication"""

import os
from pymongo import MongoClient
from collections import Counter

# Connect
uri = "mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_trading"
client = MongoClient(uri)
db = client['mathematricks_trading']

# Get all signal_store documents
signal_store = list(db.signal_store.find({}, {"signal_id": 1, "legs.leg_id": 1}))

print("=== SIGNAL_STORE DUPLICATION ANALYSIS ===\n")

# Count documents per signal_id
signal_id_counts = Counter(s['signal_id'] for s in signal_store)

print(f"Total documents in signal_store: {len(signal_store)}")
print(f"Unique signal_ids: {len(signal_id_counts)}\n")

# Show duplicates
duplicates = {k: v for k, v in signal_id_counts.items() if v > 1}
if duplicates:
    print(f"DUPLICATES FOUND ({len(duplicates)} signal_ids):")
    for sig_id, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sig_id}: {count} documents")
else:
    print("No duplicates found")

print("\n=== ALL SIGNALS ===")
for sig_id, count in sorted(signal_id_counts.items()):
    print(f"{sig_id}: {count} document(s)")

client.close()
