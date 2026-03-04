#!/usr/bin/env python3
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27018/')
db = client['mathematricks_trading']

# Get recent mock_mock signals
signals = db.signal_store.find({'mode': 'mock_mock'}).sort('created_at', -1).limit(5)

print("Comparing Raw Signal Prices vs Fill Prices in mock_mock mode:\n")
print(f"{'Instrument':<10} {'Raw Price':<12} {'Fill Price':<12} {'Match':<8}")
print("=" * 50)

for signal in signals:
    if 'legs' in signal:
        for leg in signal['legs']:
            # Get raw price from signal
            raw_price = None
            if 'raw' in leg and 'signal_legs' in leg['raw'] and leg['raw']['signal_legs']:
                raw_price = leg['raw']['signal_legs'][0].get('price')
            
            # Get fill price from execution
            fill_price = None
            instrument = 'N/A'
            if 'execution' in leg and 'orders' in leg['execution'] and leg['execution']['orders']:
                fill_price = leg['execution']['orders'][0].get('avg_fill_price')
            
            if 'decision' in leg and 'legs' in leg['decision'] and leg['decision']['legs']:
                instrument = leg['decision']['legs'][0].get('instrument', 'N/A')
            
            if raw_price is not None and fill_price is not None:
                match = "✓" if abs(raw_price - fill_price) < 0.01 else "✗ DIFF"
                print(f"{instrument:<10} ${raw_price:<11.2f} ${fill_price:<11.2f} {match}")

client.close()
