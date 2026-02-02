#!/usr/bin/env python3
import pymongo
import json

# Connect without replica set configuration
client = pymongo.MongoClient("mongodb://localhost:27018/", directConnection=True)
db = client.mathematricks_trading

signals = db.trading_signals_raw.find({}).sort("timestamp", -1).limit(5)

print("Recent raw signals:")
for signal in signals:
    print(f"\n{signal.get('signal_id')} - {signal.get('signal_type')} - {signal.get('timestamp')}")
    print(f"  Strategy: {signal.get('strategy_name')}")
    print(f"  Instrument: {signal.get('instrument')}")
    print(f"  Action: {signal.get('action')}")
