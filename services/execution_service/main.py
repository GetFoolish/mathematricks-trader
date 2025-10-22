"""
Execution Service - MVP
Connects to IBKR broker, executes orders, and reports back execution confirmations and account state.
"""
import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv
import threading
import time
import queue
from ib_insync import IB, Stock, Order, MarketOrder, LimitOrder, util

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs/execution_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(
    mongo_uri,
    tls=True,
    tlsAllowInvalidCertificates=True  # For development only
)
db = mongo_client['mathematricks_trading']
execution_confirmations_collection = db['execution_confirmations']
trading_orders_collection = db['trading_orders']

# Initialize Google Cloud Pub/Sub
project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
subscriber = pubsub_v1.SubscriberClient()
publisher = pubsub_v1.PublisherClient()

trading_orders_subscription = subscriber.subscription_path(project_id, 'trading-orders-sub')
execution_confirmations_topic = publisher.topic_path(project_id, 'execution-confirmations')
account_updates_topic = publisher.topic_path(project_id, 'account-updates')

# Initialize IBKR connection
ib = IB()

# IBKR Configuration
IBKR_HOST = os.getenv('IBKR_HOST', '127.0.0.1')
IBKR_PORT = int(os.getenv('IBKR_PORT', '7497'))  # 7497 for TWS, 4002 for IB Gateway
IBKR_CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '1'))

# Order queue for threading safety
# Pub/Sub callbacks run in thread pool, but ib_insync needs main thread's event loop
order_queue = queue.Queue()


def connect_to_ibkr():
    """
    Connect to Interactive Brokers
    """
    try:
        if not ib.isConnected():
            logger.info(f"Connecting to IBKR at {IBKR_HOST}:{IBKR_PORT}")
            ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
            logger.info("Connected to IBKR successfully")
            return True
        return True
    except Exception as e:
        logger.error(f"Failed to connect to IBKR: {str(e)}")
        return False


def create_contract(instrument: str) -> Stock:
    """
    Create IBKR contract from instrument symbol
    MVP implementation - handles stocks only
    """
    logger.info(f"🔍 create_contract called with instrument='{instrument}' (type: {type(instrument)})")
    
    if not instrument or instrument.strip() == '':
        raise ValueError(f"Invalid instrument: '{instrument}' - cannot be empty")
    
    # Simplified: assumes US stocks
    # Full implementation would parse instrument type and create appropriate contract
    contract = Stock(symbol=instrument, exchange='SMART', currency='USD')
    
    logger.info(f"🔍 Created contract: {contract}")
    return contract


def create_order(order_data: Dict[str, Any]) -> Order:
    """
    Create IBKR order from order data
    """
    order_type = order_data.get('order_type', 'MARKET').upper()
    direction = order_data.get('direction', 'LONG').upper()
    action = order_data.get('action', 'ENTRY').upper()
    quantity = order_data.get('quantity', 0)
    price = order_data.get('price', 0)

    # Round quantity to whole number (IBKR API doesn't support fractional shares for most instruments)
    # Full implementation would check if instrument supports fractional trading
    quantity = int(round(quantity))

    if quantity == 0:
        logger.warning(f"Quantity rounded to 0 from {order_data.get('quantity')}, setting to 1")
        quantity = 1

    # Determine BUY/SELL action
    if action == 'ENTRY':
        ib_action = 'BUY' if direction == 'LONG' else 'SELL'
    else:  # EXIT
        ib_action = 'SELL' if direction == 'LONG' else 'BUY'

    # Create order based on type
    if order_type == 'MARKET':
        order = MarketOrder(ib_action, quantity)
    elif order_type == 'LIMIT':
        order = LimitOrder(ib_action, quantity, price)
    else:
        # Default to market order
        order = MarketOrder(ib_action, quantity)

    # Add stop loss and take profit if provided
    # This would be more sophisticated in full implementation
    return order


def submit_order_to_broker(order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Submit order to IBKR
    """
    try:
        if not ib.isConnected():
            if not connect_to_ibkr():
                return None

        # Create contract and order
        contract = create_contract(order_data['instrument'])
        
        # CRITICAL: Qualify the contract with IBKR to get all details
        logger.info(f"Qualifying contract with IBKR...")
        qualified_contracts = ib.qualifyContracts(contract)
        if not qualified_contracts:
            logger.error(f"Failed to qualify contract: {contract}")
            return None
        
        contract = qualified_contracts[0]
        logger.info(f"✅ Contract qualified: {contract}")
        
        order = create_order(order_data)

        # Place order
        trade = ib.placeOrder(contract, order)
        
        # Wait for order to be submitted or rejected
        # ib.sleep() processes events, so errors will come through
        ib.sleep(2)  # Give IBKR time to validate and accept/reject
        
        # Check if order was rejected/cancelled
        if trade.orderStatus.status in ['Cancelled', 'ApiCancelled', 'PendingCancel', 'Inactive']:
            logger.error(f"❌ Order {order_data['order_id']} was REJECTED by IBKR: {trade.orderStatus.status}")
            logger.error(f"   Trade log: {trade.log}")
            return None
        
        logger.info(f"Submitted order {order_data['order_id']} to IBKR - Status: {trade.orderStatus.status}")

        return {
            "order_id": order_data['order_id'],
            "ib_order_id": trade.order.orderId,
            "status": trade.orderStatus.status,
            "filled": trade.orderStatus.filled,
            "remaining": trade.orderStatus.remaining,
            "avg_fill_price": trade.orderStatus.avgFillPrice
        }

    except Exception as e:
        logger.error(f"Error submitting order {order_data['order_id']}: {str(e)}", exc_info=True)
        return None


def publish_execution_confirmation(execution_data: Dict[str, Any]):
    """
    Publish execution confirmation to Pub/Sub
    """
    try:
        message_data = json.dumps(execution_data, default=str).encode('utf-8')
        future = publisher.publish(execution_confirmations_topic, message_data)
        message_id = future.result()
        logger.info(f"Published execution confirmation: {message_id}")
    except Exception as e:
        logger.error(f"Error publishing execution confirmation: {str(e)}")


def publish_account_update(account_data: Dict[str, Any]):
    """
    Publish account update to Pub/Sub
    """
    try:
        message_data = json.dumps(account_data, default=str).encode('utf-8')
        future = publisher.publish(account_updates_topic, message_data)
        message_id = future.result()
        logger.info(f"Published account update: {message_id}")
    except Exception as e:
        logger.error(f"Error publishing account update: {str(e)}")


def get_account_state() -> Dict[str, Any]:
    """
    Get current account state from IBKR
    """
    try:
        if not ib.isConnected():
            if not connect_to_ibkr():
                return {}

        # Get account summary
        account_values = ib.accountSummary()

        # Extract key metrics
        equity = 0
        cash_balance = 0
        margin_used = 0
        margin_available = 0

        for value in account_values:
            if value.tag == 'NetLiquidation':
                equity = float(value.value)
            elif value.tag == 'TotalCashValue':
                cash_balance = float(value.value)
            elif value.tag == 'MaintMarginReq':
                margin_used = float(value.value)
            elif value.tag == 'AvailableFunds':
                margin_available = float(value.value)

        # Get positions
        positions = ib.positions()
        open_positions = []

        for pos in positions:
            open_positions.append({
                "instrument": pos.contract.symbol,
                "quantity": pos.position,
                "entry_price": pos.avgCost,
                "current_price": 0,  # Would need market data subscription
                "unrealized_pnl": 0,
                "margin_required": 0
            })

        # Get open orders (use openTrades() for Trade objects, not openOrders())
        open_trades = ib.openTrades()
        orders_list = []

        for trade in open_trades:
            orders_list.append({
                "order_id": str(trade.order.orderId),
                "instrument": trade.contract.symbol,
                "side": trade.order.action,
                "quantity": trade.order.totalQuantity,
                "order_type": trade.order.orderType,
                "price": getattr(trade.order, 'lmtPrice', 0)
            })

        return {
            "account": "IBKR_Main",
            "timestamp": datetime.utcnow(),
            "equity": equity,
            "cash_balance": cash_balance,
            "margin_used": margin_used,
            "margin_available": margin_available,
            "unrealized_pnl": 0,  # Calculate from positions
            "realized_pnl": 0,  # Track from executions
            "open_positions": open_positions,
            "open_orders": orders_list
        }

    except Exception as e:
        logger.error(f"Error getting account state: {str(e)}", exc_info=True)
        return {}


def trading_orders_callback(message):
    """
    Callback for trading orders from Pub/Sub
    Runs in thread pool - adds orders to queue for main thread processing
    """
    try:
        order_data = json.loads(message.data.decode('utf-8'))
        order_id = order_data.get('order_id')

        logger.info(f"Received trading order: {order_id} - adding to queue")

        # Add order to queue for main thread processing
        # Include the message so we can ack/nack it later
        order_queue.put({
            'order_data': order_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error processing trading order: {str(e)}", exc_info=True)
        message.nack()


def process_order_from_queue(order_item: Dict[str, Any]):
    """
    Process a single order from the queue in the main thread
    This runs in the main thread where IBKR's event loop is available
    """
    order_data = order_item['order_data']
    message = order_item['message']
    order_id = order_data.get('order_id')

    try:
        logger.info(f"Processing order from queue: {order_id}")

        # Submit order to broker (now safe - we're in main thread)
        result = submit_order_to_broker(order_data)

        if result:
            # CRITICAL: Only create execution confirmation if order was actually FILLED or PARTIALLY FILLED
            # Do NOT create fake fills for orders that are just submitted/pending
            
            status = result.get('status', '')
            filled_qty = result.get('filled', 0)
            
            logger.info(f"🔍 Order {order_id} result: status={status}, filled={filled_qty}")
            
            # Only proceed if there was an actual fill
            if status in ['Filled', 'PartiallyFilled'] or filled_qty > 0:
                # Create execution confirmation
                execution = {
                    "order_id": order_id,
                    "execution_id": result.get('ib_order_id'),
                    "timestamp": datetime.utcnow(),
                    "account": "IBKR_Main",
                    "instrument": order_data.get('instrument'),
                    "side": "BUY" if order_data.get('direction') == 'LONG' else "SELL",
                    "quantity": filled_qty,
                    "price": result.get('avg_fill_price', 0),
                    "commission": 0,  # Would get from IBKR execution details
                    "status": "FILLED" if result.get('remaining', 0) == 0 else "PARTIAL_FILL",
                    "broker_response": result
                }

                # Store execution
                execution_confirmations_collection.insert_one({
                    **execution,
                    "created_at": datetime.utcnow()
                })

                # Publish execution confirmation
                publish_execution_confirmation(execution)

                # Update order status in database
                trading_orders_collection.update_one(
                    {"order_id": order_id},
                    {"$set": {"status": execution['status'], "updated_at": datetime.utcnow()}}
                )

                logger.info(f"✅ Order {order_id} executed: {execution['status']}")
            else:
                # Order submitted but not filled yet - just update status
                logger.info(f"📋 Order {order_id} submitted to IBKR, status: {status}")
                trading_orders_collection.update_one(
                    {"order_id": order_id},
                    {"$set": {"status": status, "ib_order_id": result.get('ib_order_id'), "updated_at": datetime.utcnow()}}
                )
        else:
            # Order failed
            logger.error(f"❌ Order {order_id} failed to execute")

            # Update order status
            trading_orders_collection.update_one(
                {"order_id": order_id},
                {"$set": {"status": "REJECTED", "updated_at": datetime.utcnow()}}
            )

            # For exit orders, this is critical - implement retry logic
            if order_data.get('action') == 'EXIT':
                logger.critical(f"EXIT order {order_id} FAILED - manual intervention required!")
                # TODO: Trigger "raise hell" alerts

        # Get and publish updated account state
        account_state = get_account_state()
        if account_state:
            publish_account_update(account_state)

        # Acknowledge message
        message.ack()

    except Exception as e:
        logger.error(f"Error processing order {order_id}: {str(e)}", exc_info=True)
        message.nack()


def start_trading_orders_subscriber():
    """
    Start Pub/Sub subscriber for trading orders
    Runs in background thread
    """
    streaming_pull_future = subscriber.subscribe(trading_orders_subscription, callback=trading_orders_callback)
    logger.info("ExecutionService listening for trading orders...")

    try:
        streaming_pull_future.result()
    except Exception as e:
        logger.error(f"Subscriber error: {str(e)}")
        streaming_pull_future.cancel()


def periodic_account_updates():
    """
    Publish account updates periodically (every 30 seconds)
    """
    while True:
        try:
            time.sleep(30)
            account_state = get_account_state()
            if account_state:
                publish_account_update(account_state)
        except Exception as e:
            logger.error(f"Error in periodic account updates: {str(e)}")


if __name__ == "__main__":
    logger.info("Starting Execution Service MVP (IBKR)")

    # Connect to IBKR
    if not connect_to_ibkr():
        logger.error("Failed to connect to IBKR - exiting")
        exit(1)

    # MVP: Disabled periodic account updates to avoid asyncio event loop issues in threads
    # Account state is published after each execution
    logger.info("Periodic account updates disabled for MVP - account state published after executions")

    # Start Pub/Sub subscriber in background thread
    subscriber_thread = threading.Thread(target=start_trading_orders_subscriber, daemon=True)
    subscriber_thread.start()
    logger.info("Pub/Sub subscriber started in background thread")

    # Main loop: process orders from queue in main thread where IBKR event loop is available
    logger.info("Main thread ready to process orders from queue")
    try:
        while True:
            # Check if there are orders in the queue (non-blocking)
            try:
                order_item = order_queue.get(timeout=1)
                process_order_from_queue(order_item)
            except queue.Empty:
                # No orders in queue, just wait a bit
                pass

            # Let IBKR process events
            ib.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Shutting down Execution Service")
        ib.disconnect()
