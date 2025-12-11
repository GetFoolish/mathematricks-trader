#!/usr/bin/env python3
"""
Test TWS Order Submission
Sends a simple test market buy order to TWS to verify API connection
"""
import sys
import os
import time
from datetime import datetime

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from brokers import BrokerFactory, OrderSide, OrderType

def test_tws_order(symbol="AAPL", quantity=1, dry_run=False):
    """
    Test TWS order submission

    Args:
        symbol: Stock symbol to trade (default: AAPL)
        quantity: Number of shares (default: 1)
        dry_run: If True, connect but don't actually place order (default: True)
    """
    print("=" * 70)
    print("TWS ORDER TEST")
    print("=" * 70)
    print()

    # Configuration
    host = os.getenv('IBKR_HOST', '127.0.0.1')
    port = int(os.getenv('IBKR_PORT', '7497'))
    client_id = int(os.getenv('IBKR_CLIENT_ID', '999'))  # Use 999 to avoid conflict with ExecutionService (client_id=1)

    print(f"Configuration:")
    print(f"  TWS Host: {host}:{port}")
    print(f"  Client ID: {client_id}")
    print(f"  Symbol: {symbol}")
    print(f"  Quantity: {quantity}")
    print(f"  Order Type: MARKET BUY")
    print(f"  Dry Run: {dry_run}")
    print()

    # Create broker instance
    print("Step 1: Creating broker instance...")
    broker_config = {
        "broker": "IBKR",
        "host": host,
        "port": port,
        "client_id": client_id,
        "account_id": "IBKR_Main"
    }

    try:
        broker = BrokerFactory.create_broker(broker_config)
        print(f"  ✅ Broker created: {broker.broker_name}")
    except Exception as e:
        print(f"  ❌ Failed to create broker: {e}")
        return False

    print()

    # Connect to TWS
    print("Step 2: Connecting to TWS...")
    try:
        success = broker.connect()
        if not success:
            print("  ❌ Connection failed")
            print()
            print("Troubleshooting:")
            print("  1. Ensure TWS is running and logged in")
            print("  2. In TWS → File → Global Configuration → API → Settings:")
            print("     → Enable 'Enable ActiveX and Socket Clients'")
            print("     → Add 127.0.0.1 to 'Trusted IP Addresses'")
            print(f"     → Socket Port: {port}")
            print("  3. Try a different client_id (currently using: {})".format(client_id))
            return False

        print("  ✅ Connected to TWS successfully!")
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False

    print()

    # Get account info
    print("Step 3: Fetching account information...")
    try:
        account_balance = broker.get_account_balance()
        account_id = account_balance.get('account_id', 'Unknown')
        net_liq = account_balance.get('net_liquidation', 0)
        available = account_balance.get('available_funds', 0)
        buying_power = account_balance.get('buying_power', 0)

        print(f"  Account ID: {account_id}")
        print(f"  Net Liquidation: ${net_liq:,.2f}")
        print(f"  Available Funds: ${available:,.2f}")
        print(f"  Buying Power: ${buying_power:,.2f}")
        print(f"  ✅ Account data retrieved")
    except Exception as e:
        print(f"  ⚠️  Could not fetch account info: {e}")
        account_balance = {"account_id": "IBKR_Main"}

    print()

    # Place order (or dry run)
    if dry_run:
        print("Step 4: DRY RUN - Not placing actual order")
        print(f"  Would place: BUY {quantity} {symbol} @ MARKET")
        print()
        print("To place a REAL order, run:")
        print(f"  python tools/test_tws_order.py {symbol} {quantity} --live")
    else:
        print("Step 4: Placing REAL BUY order...")
        print(f"  ⚠️  WARNING: This will place a REAL order in TWS!")
        print(f"  Order: BUY {quantity} {symbol} @ MARKET")

        # Create BUY order data (using broker API format)
        buy_order_data = {
            "order_id": f"TEST_BUY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "signal_id": f"TEST_SIGNAL_BUY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "strategy_id": "TEST_STRATEGY",
            "symbol": symbol,  # Broker expects 'symbol' not 'instrument'
            "side": OrderSide.BUY.value,  # Broker expects 'side' not 'action'
            "order_type": OrderType.MARKET.value,
            "quantity": quantity,
            "instrument_type": "STOCK",
            "account_id": account_balance.get('account_id', 'IBKR_Main')
        }

        try:
            result = broker.place_order(buy_order_data)

            print(f"  📥 RAW BUY ORDER RESPONSE FROM TWS:")
            print(f"  {'-'*66}")
            import json
            print(f"  {json.dumps(result, indent=4)}")
            print(f"  {'-'*66}")

            if result and result.get('status') in ['SUBMITTED', 'FILLED', 'PENDING', 'Filled', 'Submitted', 'Pending']:
                print(f"  ✅ BUY order submitted successfully!")
                print(f"  Broker Order ID: {result.get('broker_order_id')}")
                print(f"  Status: {result.get('status')}")
                print(f"  Message: {result.get('message', 'Order placed')}")

                # Store broker_order_id for status check
                buy_broker_order_id = result.get('broker_order_id')
            else:
                print(f"  ❌ BUY order submission failed")
                return False

        except Exception as e:
            print(f"  ❌ BUY order error: {e}")
            return False

        # Wait 5 seconds and check order status
        print()
        print("  Waiting 5 seconds to check BUY order fill status...")
        time.sleep(5)

        try:
            order_status = broker.get_order_status(buy_broker_order_id)
            print(f"  📊 BUY ORDER FILL STATUS:")
            print(f"  {'-'*66}")
            print(f"  {json.dumps(order_status, indent=4)}")
            print(f"  {'-'*66}")

            if order_status.get('filled_quantity', 0) > 0:
                print(f"  ✅ BUY order filled!")
                print(f"     Filled Quantity: {order_status.get('filled_quantity')}")
                print(f"     Avg Fill Price: ${order_status.get('avg_fill_price', 0):.2f}")
                print(f"     Status: {order_status.get('status')}")
        except Exception as e:
            print(f"  ⚠️  Could not retrieve BUY order status: {e}")

        print()
        print("Step 5: Waiting 20 seconds before closing position...")
        for i in range(20, 0, -1):
            print(f"  {i} seconds remaining...", end='\r')
            time.sleep(1)
        print()
        print()

        print("Step 6: Placing REAL SELL order to close position...")
        print(f"  Order: SELL {quantity} {symbol} @ MARKET")

        # Create SELL order data
        sell_order_data = {
            "order_id": f"TEST_SELL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "signal_id": f"TEST_SIGNAL_SELL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "strategy_id": "TEST_STRATEGY",
            "symbol": symbol,
            "side": OrderSide.SELL.value,  # SELL to close
            "order_type": OrderType.MARKET.value,
            "quantity": quantity,
            "instrument_type": "STOCK",
            "account_id": account_balance.get('account_id', 'IBKR_Main')
        }

        try:
            result = broker.place_order(sell_order_data)

            print(f"  📥 RAW SELL ORDER RESPONSE FROM TWS:")
            print(f"  {'-'*66}")
            import json
            print(f"  {json.dumps(result, indent=4)}")
            print(f"  {'-'*66}")

            if result and result.get('status') in ['SUBMITTED', 'FILLED', 'PENDING', 'Filled', 'Submitted', 'Pending']:
                print(f"  ✅ SELL order submitted successfully!")
                print(f"  Broker Order ID: {result.get('broker_order_id')}")
                print(f"  Status: {result.get('status')}")
                print(f"  Message: {result.get('message', 'Position closed')}")

                # Store broker_order_id for status check
                sell_broker_order_id = result.get('broker_order_id')
            else:
                print(f"  ❌ SELL order submission failed")
                return False

        except Exception as e:
            print(f"  ❌ SELL order error: {e}")
            return False

        # Wait 5 seconds and check order status
        print()
        print("  Waiting 5 seconds to check SELL order fill status...")
        time.sleep(5)

        try:
            order_status = broker.get_order_status(sell_broker_order_id)
            print(f"  📊 SELL ORDER FILL STATUS:")
            print(f"  {'-'*66}")
            print(f"  {json.dumps(order_status, indent=4)}")
            print(f"  {'-'*66}")

            if order_status.get('filled_quantity', 0) > 0:
                print(f"  ✅ SELL order filled!")
                print(f"     Filled Quantity: {order_status.get('filled_quantity')}")
                print(f"     Avg Fill Price: ${order_status.get('avg_fill_price', 0):.2f}")
                print(f"     Status: {order_status.get('status')}")
        except Exception as e:
            print(f"  ⚠️  Could not retrieve SELL order status: {e}")

    print()

    # Disconnect
    print("Step 5: Disconnecting from TWS...")
    broker.disconnect()
    print("  ✅ Disconnected")

    print()
    print("=" * 70)
    if dry_run:
        print("✅ DRY RUN COMPLETED - TWS Connection Working!")
    else:
        print("✅ ORDER TEST COMPLETED")
    print("=" * 70)

    return True


if __name__ == "__main__":
    # Load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Parse command line arguments
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    quantity = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    dry_run = False  # Always run in live mode (paper account)

    success = test_tws_order(symbol=symbol, quantity=quantity, dry_run=dry_run)
    sys.exit(0 if success else 1)
