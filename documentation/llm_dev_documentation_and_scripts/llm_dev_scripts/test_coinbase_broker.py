#!/usr/bin/env python3
"""Test Coinbase broker initialization to debug RESTClient import issue."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

print("Step 1: Testing direct import...")
try:
    from coinbase.rest import RESTClient
    print(f"✅ RESTClient imported: {RESTClient}")
    print(f"   Is None: {RESTClient is None}")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print("\nStep 2: Testing broker module import...")
try:
    from services.brokers.coinbase.coinbase_broker import CoinbaseBroker
    print("✅ CoinbaseBroker imported")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print("\nStep 3: Creating broker config...")
config = {
    'account_id': 'COINBASE_CANADA',
    'api_key': 'test_key_name',
    'api_secret': 'test_secret_key',
    'sandbox': True
}
print(f"Config: {config}")

print("\nStep 4: Instantiating broker...")
try:
    broker = CoinbaseBroker(config)
    print(f"✅ Broker created: {broker}")
    print(f"   Data API URL: {broker.data_api_url}")
    print(f"   Order API URL: {broker.order_api_url}")
except Exception as e:
    print(f"❌ Broker instantiation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All tests passed!")
