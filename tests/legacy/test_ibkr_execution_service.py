#!/usr/bin/env python3
"""Test getting AAPL price through execution service IBKRBroker"""

from services.brokers.ibkr.ibkr_broker import IBKRBroker

def test_execution_service():
    """Test getting AAPL price via execution service IBKRBroker"""
    print('\n========== EXECUTION SERVICE (IBKRBroker) ==========')
    
    # Create a config object for IBKRBroker
    config = {
        'host': '127.0.0.1',
        'port': 58624,  # External port mapped from container
        'client_id': 10005,
        'account_id': 'ibkr-testing-account'
    }
    
    print('🔌 Initializing IBKR Broker...')
    broker = IBKRBroker(config)
    
    print('📡 Connecting to IB Gateway...')
    broker.connect(skip_sync=True)  # skip_sync=True for read-only market data
    print('✅ Connected!')
    
    print('📊 Getting AAPL latest price...')
    price = broker.get_market_price('AAPL', 'stock')
    print(f'📈 AAPL Price: ${price}')
    
    broker.disconnect()
    print('✅ Disconnected\n')

if __name__ == '__main__':
    test_execution_service()
