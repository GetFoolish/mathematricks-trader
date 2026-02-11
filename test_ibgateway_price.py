#!/usr/bin/env python3
"""
Quick test script to fetch a price directly from IB Gateway.
Usage: .venv/bin/python test_ibgateway_price.py [SYMBOL]
"""
import sys
import time
from ib_insync import IB, Stock, util

# Configuration
HOST = "127.0.0.1"
PORT = 49347  # IB Gateway port (check with: docker port ib-gateway-ibkr-paper)
CLIENT_ID = 999  # Use unique client ID to avoid conflicts

def get_price(symbol='AAPL'):
    """Fetch current market price for a symbol."""
    ib = IB()
    
    try:
        print(f"🔌 Connecting to IB Gateway at {HOST}:{PORT}...")
        ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=10)
        print(f"✅ Connected! Client ID: {CLIENT_ID}")
        
        # Request market data type (4 = delayed frozen for paper)
        ib.reqMarketDataType(4)
        print(f"📊 Set market data type to: 4 (delayed frozen)")
        
        # Create contract
        contract = Stock(symbol, 'SMART', 'USD')
        print(f"\n📈 Requesting price for {symbol}...")
        
        # Request market data
        ticker = ib.reqMktData(contract, '', False, False)
        
        # Wait for data
        print("⏳ Waiting for market data...")
        timeout = 10
        start = time.time()
        
        while time.time() - start < timeout:
            ib.sleep(0.5)
            
            # Check if we have price data
            if ticker.marketPrice() and ticker.marketPrice() > 0:
                print(f"\n✅ SUCCESS! Got price data:")
                print(f"   Symbol: {symbol}")
                print(f"   Last Price: ${ticker.last:.2f}" if ticker.last else "   Last Price: N/A")
                print(f"   Bid: ${ticker.bid:.2f}" if ticker.bid else "   Bid: N/A")
                print(f"   Ask: ${ticker.ask:.2f}" if ticker.ask else "   Ask: N/A")
                print(f"   Market Price: ${ticker.marketPrice():.2f}")
                print(f"   Close: ${ticker.close:.2f}" if ticker.close else "   Close: N/A")
                return ticker.marketPrice()
            
            # Show progress
            if hasattr(ticker, 'bid') and ticker.bid:
                print(f"   Bid: ${ticker.bid:.2f}", end='\r')
        
        print(f"\n⚠️  Timeout: No market data received after {timeout} seconds")
        print(f"   Ticker state: {ticker}")
        return None
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if ib.isConnected():
            print("\n🔌 Disconnecting...")
            ib.disconnect()
            print("✅ Disconnected")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'AAPL'
    
    print("=" * 60)
    print("IB Gateway Direct Price Test")
    print("=" * 60)
    
    price = get_price(symbol)
    
    if price:
        print(f"\n🎉 Final Result: {symbol} = ${price:.2f}")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to get price for {symbol}")
        sys.exit(1)
