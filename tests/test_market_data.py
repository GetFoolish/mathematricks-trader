#!/usr/bin/env python3
"""Quick test to fetch AAPL market data from IB Gateway"""

from ib_insync import IB, Stock
import time

def test_market_data():
    ib = IB()
    
    try:
        # Connect to IB Gateway (using auto-assigned port from Docker)
        print("🔌 Connecting to IB Gateway on port 57873...")
        ib.connect('localhost', 57873, clientId=999)
        print(f"✅ Connected! Server version: {ib.client.serverVersion()}")
        
        # Create AAPL stock contract
        aapl = Stock('AAPL', 'SMART', 'USD')
        
        # Request contract details to qualify the contract
        print("\n📋 Requesting contract details for AAPL...")
        contracts = ib.qualifyContracts(aapl)
        if not contracts:
            print("❌ Could not qualify AAPL contract")
            return
        
        aapl = contracts[0]
        print(f"✅ Contract qualified: {aapl}")
        
        # Request market data
        print("\n📊 Requesting market data...")
        ticker = ib.reqMktData(aapl, snapshot=False)
        
        # Wait for data to arrive
        print("⏳ Waiting for market data (10 seconds)...")
        for i in range(10):
            ib.sleep(1)
            if ticker.last or ticker.close:
                break
        
        # Print results
        print("\n" + "="*60)
        print("AAPL Market Data:")
        print("="*60)
        print(f"Last Price:   {ticker.last if ticker.last else 'N/A'}")
        print(f"Bid:          {ticker.bid if ticker.bid else 'N/A'}")
        print(f"Ask:          {ticker.ask if ticker.ask else 'N/A'}")
        print(f"Close:        {ticker.close if ticker.close else 'N/A'}")
        print(f"Volume:       {ticker.volume if ticker.volume else 'N/A'}")
        print(f"Market:       {ticker.marketName() if hasattr(ticker, 'marketName') else 'N/A'}")
        print("="*60)
        
        if not ticker.last and not ticker.close:
            print("\n⚠️  No market data received!")
            print("Possible reasons:")
            print("1. Market is closed (check if US market hours)")
            print("2. No market data subscription on IBKR account")
            print("3. Market data permissions not granted")
            print("\nTicker object:", ticker)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if ib.isConnected():
            print("\n🔌 Disconnecting...")
            ib.disconnect()

if __name__ == "__main__":
    test_market_data()
