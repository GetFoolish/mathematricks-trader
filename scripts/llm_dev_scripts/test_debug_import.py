import sys
import os
sys.path.insert(0, '.')

# Check module-level import
import services.brokers.coinbase.coinbase_broker as broker_module
print(f"1. Module-level RESTClient: {broker_module.RESTClient}")
print(f"   Is None: {broker_module.RESTClient is None}")

# Now try to instantiate
from dotenv import load_dotenv
load_dotenv()

config = {
    'account_id': 'COINBASE_CANADA',
    'api_key': os.getenv('COINBASE_API_KEY_UAE_NAME'),
    'api_secret': os.getenv('COINBASE_API_KEY_UAE_KEY'),
    'sandbox': True
}

# Monkey-patch to debug
CoinbaseBroker = broker_module.CoinbaseBroker
original_init = CoinbaseBroker.__init__

def debug_init(self, config):
    print(f"\n2. Inside __init__, checking RESTClient...")
    print(f"   RESTClient from module: {broker_module.RESTClient}")
    print(f"   RESTClient is None: {broker_module.RESTClient is None}")
    
    # Call original
    original_init(self, config)

CoinbaseBroker.__init__ = debug_init

try:
    broker = CoinbaseBroker(config)
    print(f"\n✅ Success! Broker created")
    print(f"   Data API: {broker.data_api_url}")
    print(f"   Order API: {broker.order_api_url}")
except Exception as e:
    print(f"\n❌ Failed: {e}")
    import traceback
    traceback.print_exc()
