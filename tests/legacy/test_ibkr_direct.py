#!/usr/bin/env python3
"""
Test IBKR connection and order placement directly
"""

from ib_insync import IB, Stock, MarketOrder
import time

def test_ibkr_connection():
    print("=" * 80)
    print("TESTING IBKR CONNECTION AND ORDER PLACEMENT")
    print("=" * 80)
    
    ib = IB()
    
    try:
        # Connect to TWS
        print("\n1. Connecting to TWS on 127.0.0.1:7497...")
        ib.connect('127.0.0.1', 7497, clientId=999)  # Use different client ID than execution service
        print("✅ Connected successfully!")
        
        # Wait for connection to settle
        ib.sleep(2)
        
        # Create a simple stock contract
        print("\n2. Creating SPY stock contract...")
        contract = Stock(symbol='SPY', exchange='SMART', currency='USD')
        print(f"   Contract: {contract}")
        
        # Qualify the contract (this validates it with IBKR)
        print("\n3. Qualifying contract with IBKR...")
        qualified_contracts = ib.qualifyContracts(contract)
        if qualified_contracts:
            contract = qualified_contracts[0]
            print(f"✅ Contract qualified: {contract}")
            print(f"   ConId: {contract.conId}")
            print(f"   Symbol: {contract.symbol}")
            print(f"   Exchange: {contract.exchange}")
        else:
            print("❌ Failed to qualify contract!")
            return
        
        # Create a small test order
        print("\n4. Creating test market order (1 share)...")
        order = MarketOrder('BUY', 1)
        print(f"   Order: {order}")
        
        # Place the order
        print("\n5. Placing order with IBKR...")
        trade = ib.placeOrder(contract, order)
        print(f"✅ Order placed!")
        print(f"   Order ID: {trade.order.orderId}")
        print(f"   Initial status: {trade.orderStatus.status}")
        
        # Wait for order to be processed
        print("\n6. Waiting for order status updates...")
        for i in range(5):
            ib.sleep(1)
            print(f"   [{i+1}s] Status: {trade.orderStatus.status}, Filled: {trade.orderStatus.filled}, Remaining: {trade.orderStatus.remaining}")
            
            if trade.orderStatus.status in ['Filled', 'Cancelled']:
                break
        
        # Show final status
        print(f"\n7. Final order status:")
        print(f"   Status: {trade.orderStatus.status}")
        print(f"   Filled: {trade.orderStatus.filled}")
        print(f"   Avg Fill Price: {trade.orderStatus.avgFillPrice}")
        print(f"   Remaining: {trade.orderStatus.remaining}")
        
        if trade.orderStatus.status == 'Cancelled':
            print(f"\n⚠️  Order was cancelled!")
            print(f"   Trade log: {trade.log}")
        
        # Cancel if still pending
        if trade.orderStatus.status not in ['Filled', 'Cancelled']:
            print("\n8. Cancelling test order...")
            ib.cancelOrder(order)
            ib.sleep(1)
            print(f"✅ Order cancelled")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n9. Disconnecting...")
        ib.disconnect()
        print("✅ Disconnected")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_ibkr_connection()
