#!/usr/bin/env python3
"""Test IBKR market data connection"""
import sys
sys.path.insert(0, '/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks/mathematricks-trader')

from services.brokers.ibkr.ibkr_broker import IBKRBroker
from ib_insync import Stock

config = {
    'broker': 'IBKR',
    'account_id': 'IBKR-TESTING-ACCOUNT',
    'host': '127.0.0.1',
    'port': 62772,  # Docker container port mapping (4004 -> 62772)
    'client_id': 5
}

broker = IBKRBroker(config)
print('🔌 Connecting to IB Gateway DOCKER at 127.0.0.1:62772...')
broker.connect()
print('✅ Connected!')

# Request LIVE market data
# 1 = Live (requires subscription)
# 3 = Delayed (free, 15-min delay)
# 4 = Delayed Frozen (free, last price after market close)
print('📊 Requesting LIVE market data (type 1)...')
broker.ib.reqMarketDataType(1)
broker.ib.sleep(1)

# Create contract and request data
print('📈 Creating AAPL contract...')
contract = Stock('AAPL', 'SMART', 'USD')
broker.ib.qualifyContracts(contract)
print(f'✅ Contract qualified: {contract}')

print('📡 Requesting market data for AAPL...')
ticker = broker.ib.reqMktData(contract, '', False, False)
print(f'Ticker object: {ticker}')

print('⏳ Waiting for market data (10 seconds)...')
for i in range(10):
    broker.ib.sleep(1)  # Use ib.sleep() instead of time.sleep() for event loop
    print(f'  [{i+1}s] bid={ticker.bid}, ask={ticker.ask}, last={ticker.last}')
    if ticker.bid or ticker.ask or ticker.last:
        mid = (ticker.bid + ticker.ask)/2 if (ticker.bid and ticker.ask) else ticker.last
        print(f'\n✅ SUCCESS! AAPL Price: ${mid:.2f}')
        break
else:
    print('\n❌ No market data received after 10 seconds')
    print('Check IB Gateway UI for market data subscription popup!')

broker.ib.cancelMktData(contract)
broker.disconnect()
print('\n✅ Disconnected')
