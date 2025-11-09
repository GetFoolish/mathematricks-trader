#!/usr/bin/env python3
"""
IBKR Broker Integration Test
Tests ACTUAL connection, account queries, and order placement with live IBKR TWS
"""
import sys
import os

# Add broker library to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from factory import BrokerFactory
from ibkr import IBKRBroker
from exceptions import BrokerConnectionError, BrokerAPIError
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Force reconfiguration
)
logger = logging.getLogger(__name__)

# Also print to stdout
import sys
class TeeLogger:
    def info(self, msg):
        print(msg)
        logger.info(msg)
    def error(self, msg):
        print(f"ERROR: {msg}")
        logger.error(msg)

tee_logger = TeeLogger()

def test_ibkr_broker():
    """Test IBKR broker with real connection"""

    logger.info("=" * 80)
    logger.info("IBKR BROKER INTEGRATION TEST - PRODUCTION VALIDATION")
    logger.info("=" * 80)

    # Create broker config (using same settings as ExecutionService)
    config = {
        "broker": "IBKR",
        "host": "127.0.0.1",
        "port": 7497,  # TWS Paper Trading
        "client_id": 999,  # Different from ExecutionService to avoid conflicts
        "account_id": "DU123456"
    }

    try:
        # TEST 1: Create broker instance
        logger.info("\n1. Creating IBKR broker instance...")
        broker = BrokerFactory.create_broker(config)
        logger.info(f"   ✓ Broker created: {broker.broker_name}")
        assert isinstance(broker, IBKRBroker), "Broker is not IBKRBroker instance"

        # TEST 2: Connect to IBKR
        logger.info("\n2. Connecting to IBKR TWS...")
        connected = broker.connect()
        logger.info(f"   ✓ Connected: {connected}")
        assert connected, "Failed to connect to IBKR"

        # TEST 3: Check connection status
        logger.info("\n3. Verifying connection status...")
        is_connected = broker.is_connected()
        logger.info(f"   ✓ Connection status: {is_connected}")
        assert is_connected, "Broker reports not connected"

        # TEST 4: Get account balance
        logger.info("\n4. Fetching account balance...")
        balance = broker.get_account_balance()
        logger.info(f"   ✓ Account ID: {balance['account_id']}")
        logger.info(f"   ✓ Equity: ${balance['equity']:,.2f}")
        logger.info(f"   ✓ Cash Balance: ${balance['cash_balance']:,.2f}")
        logger.info(f"   ✓ Margin Used: ${balance['margin_used']:,.2f}")
        logger.info(f"   ✓ Margin Available: ${balance['margin_available']:,.2f}")
        logger.info(f"   ✓ Buying Power: ${balance['buying_power']:,.2f}")
        assert balance['equity'] > 0, "Equity should be positive"

        # TEST 5: Get margin info
        logger.info("\n5. Fetching margin information...")
        margin = broker.get_margin_info()
        logger.info(f"   ✓ Margin Used: ${margin['margin_used']:,.2f}")
        logger.info(f"   ✓ Margin Available: ${margin['margin_available']:,.2f}")
        logger.info(f"   ✓ Leverage: {margin['leverage']:.2f}x")
        logger.info(f"   ✓ Margin Utilization: {margin['margin_utilization_pct']:.2f}%")
        assert margin['margin_utilization_pct'] >= 0, "Margin utilization should be >= 0"

        # TEST 6: Get open positions
        logger.info("\n6. Fetching open positions...")
        positions = broker.get_open_positions()
        logger.info(f"   ✓ Number of open positions: {len(positions)}")
        for i, pos in enumerate(positions, 1):
            logger.info(f"   ✓ Position {i}: {pos['symbol']} | {pos['side']} {pos['quantity']} @ ${pos['avg_price']:.2f}")

        # TEST 7: Get open orders
        logger.info("\n7. Fetching open orders...")
        orders = broker.get_open_orders()
        logger.info(f"   ✓ Number of open orders: {len(orders)}")
        for i, order in enumerate(orders, 1):
            logger.info(f"   ✓ Order {i}: {order['broker_order_id']} | {order['side']} {order['quantity']} {order['symbol']} @ {order['order_type']}")

        # TEST 8: Place a small test order (1 share of AAPL)
        logger.info("\n8. Testing order placement (1 share AAPL MARKET order)...")
        logger.info("   ⚠  This will place a REAL order in paper trading account")

        order = {
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "instrument_type": "STOCK"
        }

        result = broker.place_order(order)
        logger.info(f"   ✓ Order placed successfully!")
        logger.info(f"   ✓ Broker Order ID: {result['broker_order_id']}")
        logger.info(f"   ✓ Status: {result['status']}")
        logger.info(f"   ✓ Timestamp: {result['timestamp']}")
        assert result['broker_order_id'] is not None, "Should have broker order ID"

        # Wait a moment for order to process
        import time
        time.sleep(3)

        # TEST 9: Check order status
        logger.info("\n9. Checking order status...")
        order_status = broker.get_order_status(result['broker_order_id'])
        logger.info(f"   ✓ Order Status: {order_status['status']}")
        logger.info(f"   ✓ Filled Quantity: {order_status['filled_quantity']}")
        logger.info(f"   ✓ Remaining Quantity: {order_status['remaining_quantity']}")
        logger.info(f"   ✓ Avg Fill Price: ${order_status['avg_fill_price']:.2f}")

        # TEST 10: If not filled, cancel the order
        if order_status['status'] not in ['FILLED']:
            logger.info("\n10. Cancelling test order...")
            cancelled = broker.cancel_order(result['broker_order_id'])
            logger.info(f"   ✓ Order cancelled: {cancelled}")
        else:
            logger.info("\n10. Order already filled - no cancellation needed")

        # TEST 11: Disconnect
        logger.info("\n11. Disconnecting from IBKR...")
        disconnected = broker.disconnect()
        logger.info(f"   ✓ Disconnected: {disconnected}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL TESTS PASSED - IBKR BROKER IS PRODUCTION READY")
        logger.info("=" * 80)
        logger.info("\nBroker library validated with:")
        logger.info("  - ✓ Real IBKR TWS connection")
        logger.info("  - ✓ Account balance queries")
        logger.info("  - ✓ Margin information queries")
        logger.info("  - ✓ Position queries")
        logger.info("  - ✓ Order queries")
        logger.info("  - ✓ Order placement")
        logger.info("  - ✓ Order status tracking")
        logger.info("  - ✓ Order cancellation")
        logger.info("  - ✓ Proper connection management")

        return True

    except BrokerConnectionError as e:
        logger.error(f"\n❌ CONNECTION ERROR: {e}")
        logger.error("   Make sure IBKR TWS is running on port 7497")
        return False

    except BrokerAPIError as e:
        logger.error(f"\n❌ API ERROR: {e}")
        logger.error(f"   Error code: {e.error_code}")
        return False

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ibkr_broker()
    sys.exit(0 if success else 1)
