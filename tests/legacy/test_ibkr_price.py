#!/usr/bin/env python3
"""Test getting AAPL price through IBKR - both direct and via execution service"""

from ib_insync import IB, Stock

def test_direct():
    """Test getting AAPL price directly from IB Gateway"""
    print('\n========== DIRECT IB GATEWAY CONNECTION ==========')
    print('🔌 Connecting to IB Gateway...')
    ib = IB()
    ib.connect('127.0.0.1', 58624, clientId=10004, readonly=True, timeout=15)
    print('✅ Connected!')

    print('📊 Requesting AAPL market data...')
    contract = Stock('AAPL', 'SMART', 'USD')
    ib.qualifyContracts(contract)
    print(f'✅ Contract qualified: {contract}')

    # Request market data
    ticker = ib.reqMktData(contract)
    ib.sleep(2)  # Wait for data

    print(f'📈 AAPL Price Data:')
    print(f'   Last: {ticker.last}')
    print(f'   Bid: {ticker.bid}')
    print(f'   Ask: {ticker.ask}')
    print(f'   Close: {ticker.close}')

    ib.cancelMktData(contract)
    ib.disconnect()
    print('✅ Disconnected\n')

if __name__ == '__main__':
    test_direct()

