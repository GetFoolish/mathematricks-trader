"""
Execution Service - MVP
Connects to IBKR broker, executes orders, and reports back execution confirmations and account state.
"""
import os
import sys
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

# Add services directory to path so we can import brokers package
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
SERVICES_PATH = os.path.join(PROJECT_ROOT, 'services')
sys.path.insert(0, SERVICES_PATH)

# Import broker library
from brokers import BrokerFactory, OrderSide, OrderType, OrderStatus
from brokers.exceptions import (
    BrokerConnectionError,
    OrderRejectedError,
    BrokerAPIError,
    InvalidSymbolError
)

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

# Signal processing log handler - unified log for complete signal journey
signal_processing_handler = logging.FileHandler('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs/signal_processing.log')
signal_processing_handler.setLevel(logging.INFO)
signal_processing_formatter = logging.Formatter(
    '%(asctime)s | [EXECUTION] | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
signal_processing_handler.setFormatter(signal_processing_formatter)
# Only log signal-related events to this file (filtered later)
signal_processing_handler.addFilter(lambda record: 'SIGNAL:' in record.getMessage() or 'ORDER:' in record.getMessage())

# Add signal processing handler
signal_logger = logging.getLogger('signal_processing')
signal_logger.addHandler(signal_processing_handler)
signal_logger.setLevel(logging.INFO)

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
open_positions_collection = db['open_positions']

# Initialize Google Cloud Pub/Sub
project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
subscriber = pubsub_v1.SubscriberClient()
publisher = pubsub_v1.PublisherClient()

trading_orders_subscription = subscriber.subscription_path(project_id, 'trading-orders-sub')
order_commands_subscription = subscriber.subscription_path(project_id, 'order-commands-sub')
execution_confirmations_topic = publisher.topic_path(project_id, 'execution-confirmations')
account_updates_topic = publisher.topic_path(project_id, 'account-updates')

# IBKR Configuration
IBKR_HOST = os.getenv('IBKR_HOST', '127.0.0.1')
IBKR_PORT = int(os.getenv('IBKR_PORT', '7497'))  # 7497 for TWS, 4002 for IB Gateway
IBKR_CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '1'))

# Initialize broker using BrokerFactory
broker_config = {
    "broker": "IBKR",
    "host": IBKR_HOST,
    "port": IBKR_PORT,
    "client_id": IBKR_CLIENT_ID,
    "account_id": os.getenv('IBKR_ACCOUNT_ID', 'IBKR_Main')
}

broker = BrokerFactory.create_broker(broker_config)
logger.info(f"Broker created: {broker.broker_name}")

# Order queue for threading safety
# Pub/Sub callbacks run in thread pool, orders are processed in main thread
order_queue = queue.Queue()
command_queue = queue.Queue()  # For cancel commands and other order management

# Track active IBKR orders by order_id for cancellation
active_ibkr_orders = {}  # {order_id: broker_order_id}

# 🚨 CRITICAL FAILSAFE: Track processed signal IDs to prevent duplicate execution
processed_signal_ids = set()  # In-memory deduplication
SIGNAL_ID_EXPIRY_HOURS = 24  # Keep signal IDs for 24 hours


def connect_to_ibkr():
    """
    Connect to Interactive Brokers using broker library
    """
    try:
        if not broker.is_connected():
            logger.info(f"Connecting to IBKR at {IBKR_HOST}:{IBKR_PORT}")
            success = broker.connect()
            if success:
                logger.info("Connected to IBKR successfully")
                return True
            else:
                logger.error("Failed to connect to IBKR")
                return False
        return True
    except BrokerConnectionError as e:
        logger.error(f"Broker connection error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error connecting to IBKR: {str(e)}")
        return False


def submit_order_to_broker(order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Submit order to broker using broker library

    Uses the AbstractBroker interface for placing orders.
    """
    try:
        if not broker.is_connected():
            if not connect_to_ibkr():
                return None

        logger.info(f"📋 Submitting order {order_data.get('order_id')} via broker library")

        # Use broker library's place_order method
        # The broker library handles all contract creation, qualification, and submission
        result = broker.place_order(order_data)

        if not result:
            logger.error(f"❌ Broker rejected order {order_data.get('order_id')}")
            return None

        # Track active orders for cancellation
        order_id = order_data['order_id']
        broker_order_id = result.get('broker_order_id')
        active_ibkr_orders[order_id] = broker_order_id

        logger.info(f"✅ Order {order_data.get('order_id')} submitted - Broker Order ID: {broker_order_id}, Status: {result.get('status')}")

        return {
            "order_id": order_data['order_id'],
            "ib_order_id": broker_order_id,
            "status": result.get('status'),
            "filled": 0,  # Will be updated when order fills
            "remaining": order_data.get('quantity', 0),
            "avg_fill_price": 0,
            "num_legs": 1
        }

    except OrderRejectedError as e:
        logger.error(f"❌ Order {order_data.get('order_id')} rejected: {e.rejection_reason}")
        return None
    except InvalidSymbolError as e:
        logger.error(f"❌ Invalid symbol in order {order_data.get('order_id')}: {str(e)}")
        return None
    except BrokerAPIError as e:
        logger.error(f"❌ Broker API error for order {order_data.get('order_id')}: {e.error_code} - {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error submitting order {order_data.get('order_id')}: {str(e)}", exc_info=True)
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


def create_or_update_position(order_data: Dict[str, Any], filled_qty: float, avg_fill_price: float):
    """
    Create or update position in open_positions collection after order fill
    Handles both ENTRY (create/increase) and EXIT (decrease/close) actions
    """
    try:
        strategy_id = order_data.get('strategy_id')
        instrument = order_data.get('instrument')
        direction = order_data.get('direction', 'LONG').upper()
        action = order_data.get('action', 'ENTRY').upper()
        order_id = order_data.get('order_id')

        # Find existing position
        existing_position = open_positions_collection.find_one({
            'strategy_id': strategy_id,
            'instrument': instrument,
            'status': 'OPEN'
        })

        if action in ['ENTRY', 'BUY']:
            # ENTRY: Create new position or add to existing
            if existing_position:
                # Add to existing position (scale-in)
                current_qty = existing_position['quantity']
                current_avg_price = existing_position['avg_entry_price']

                new_qty = current_qty + filled_qty
                # Calculate new weighted average price
                new_avg_price = ((current_qty * current_avg_price) + (filled_qty * avg_fill_price)) / new_qty

                open_positions_collection.update_one(
                    {'_id': existing_position['_id']},
                    {'$set': {
                        'quantity': new_qty,
                        'avg_entry_price': new_avg_price,
                        'updated_at': datetime.utcnow(),
                        'last_order_id': order_id
                    }}
                )
                logger.info(f"✅ Updated position {strategy_id}/{instrument}: {current_qty} → {new_qty} shares @ ${new_avg_price:.2f}")
            else:
                # Create new position
                position = {
                    'strategy_id': strategy_id,
                    'instrument': instrument,
                    'direction': direction,
                    'quantity': filled_qty,
                    'avg_entry_price': avg_fill_price,
                    'current_price': avg_fill_price,
                    'unrealized_pnl': 0.0,
                    'status': 'OPEN',
                    'entry_order_id': order_id,
                    'last_order_id': order_id,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                open_positions_collection.insert_one(position)
                logger.info(f"✅ Created position {strategy_id}/{instrument}: {filled_qty} shares @ ${avg_fill_price:.2f}")

        elif action in ['EXIT', 'SELL']:
            # EXIT: Reduce or close position
            if existing_position:
                current_qty = existing_position['quantity']

                if filled_qty >= current_qty:
                    # Full exit - close position
                    open_positions_collection.update_one(
                        {'_id': existing_position['_id']},
                        {'$set': {
                            'status': 'CLOSED',
                            'exit_order_id': order_id,
                            'avg_exit_price': avg_fill_price,
                            'closed_at': datetime.utcnow(),
                            'updated_at': datetime.utcnow()
                        }}
                    )
                    logger.info(f"✅ Closed position {strategy_id}/{instrument}: {current_qty} shares @ ${avg_fill_price:.2f}")
                else:
                    # Partial exit - reduce position
                    new_qty = current_qty - filled_qty
                    open_positions_collection.update_one(
                        {'_id': existing_position['_id']},
                        {'$set': {
                            'quantity': new_qty,
                            'updated_at': datetime.utcnow(),
                            'last_order_id': order_id
                        }}
                    )
                    logger.info(f"✅ Reduced position {strategy_id}/{instrument}: {current_qty} → {new_qty} shares")
            else:
                logger.warning(f"⚠️ EXIT order {order_id} filled but no open position found for {strategy_id}/{instrument}")

    except Exception as e:
        logger.error(f"❌ Error creating/updating position: {e}", exc_info=True)


def get_account_state() -> Dict[str, Any]:
    """
    Get current account state using broker library
    """
    try:
        if not broker.is_connected():
            if not connect_to_ibkr():
                return {}

        # Get account balance using broker library
        balance = broker.get_account_balance()

        # Get open positions
        positions = broker.get_open_positions()

        # Get margin info
        margin_info = broker.get_margin_info()

        # Get open orders
        open_orders = broker.get_open_orders()

        return {
            "account": "IBKR_Main",
            "timestamp": datetime.utcnow(),
            "equity": balance.get('equity', 0),
            "cash_balance": balance.get('cash', 0),
            "margin_used": margin_info.get('margin_used', 0),
            "margin_available": margin_info.get('margin_available', 0),
            "unrealized_pnl": balance.get('unrealized_pnl', 0),
            "realized_pnl": 0,  # Track from executions
            "open_positions": positions,
            "open_orders": open_orders
        }

    except Exception as e:
        logger.error(f"Error getting account state: {str(e)}", exc_info=True)
        return {}


def cancel_order(order_id: str) -> bool:
    """
    Cancel an active order by order_id using broker library
    Returns True if successfully cancelled, False otherwise
    """
    try:
        if order_id not in active_ibkr_orders:
            logger.warning(f"⚠️ Cannot cancel order {order_id} - not found in active orders")
            return False

        broker_order_id = active_ibkr_orders[order_id]
        logger.info(f"🚫 Cancelling order {order_id} (broker order ID: {broker_order_id})...")

        # Use broker library to cancel order
        success = broker.cancel_order(broker_order_id)

        if success:
            # Remove from tracking
            del active_ibkr_orders[order_id]
            logger.info(f"✅ Order {order_id} cancelled successfully")
            return True
        else:
            logger.warning(f"⚠️ Failed to cancel order {order_id}")
            return False

    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}", exc_info=True)
        return False


def order_commands_callback(message):
    """
    Callback for order commands (cancel, modify, etc.) from Pub/Sub
    Runs in thread pool - adds commands to queue for main thread processing
    """
    try:
        command_data = json.loads(message.data.decode('utf-8'))
        command_type = command_data.get('command')
        order_id = command_data.get('order_id')

        logger.info(f"Received order command: {command_type} for {order_id}")

        # Add command to queue for main thread processing
        command_queue.put({
            'command_data': command_data,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error processing order command: {str(e)}", exc_info=True)
        message.nack()


def process_command_from_queue(command_item: Dict[str, Any]):
    """
    Process a single command from the queue in the main thread
    """
    command_data = command_item['command_data']
    message = command_item['message']
    command_type = command_data.get('command')
    order_id = command_data.get('order_id')

    try:
        logger.info(f"Processing command: {command_type} for {order_id}")

        if command_type == 'CANCEL':
            success = cancel_order(order_id)
            if success:
                logger.info(f"✅ Successfully cancelled order {order_id}")
            else:
                logger.warning(f"⚠️ Failed to cancel order {order_id}")

        else:
            logger.warning(f"⚠️ Unknown command type: {command_type}")

        # Ack the message
        message.ack()

    except Exception as e:
        logger.error(f"Error processing command {command_type} for {order_id}: {e}", exc_info=True)
        message.nack()


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

    # Extract signal ID from order ID (format: {signal_id}_ORD)
    signal_id = order_id.replace('_ORD', '') if order_id.endswith('_ORD') else order_id

    try:
        logger.info(f"Processing order from queue: {order_id}")

        # 🚨 CRITICAL FAILSAFE: Check if signal already processed
        if signal_id in processed_signal_ids:
            logger.critical(f"🚨 DUPLICATE SIGNAL BLOCKED! Signal {signal_id} already processed - REJECTING to prevent duplicate execution!")
            signal_logger.critical(f"ORDER: {signal_id} | DUPLICATE_BLOCKED | This signal was already processed - order rejected for safety")
            message.ack()  # ACK the message to prevent redelivery
            return

        # Add to processed set
        processed_signal_ids.add(signal_id)
        logger.info(f"✅ Signal {signal_id} marked as processed (total tracked: {len(processed_signal_ids)})")

        # Log to signal_processing.log - Order received
        signal_logger.info(f"ORDER: {signal_id} | ORDER_RECEIVED | OrderID={order_id} | Instrument={order_data.get('instrument')} | Direction={order_data.get('direction')} | Quantity={order_data.get('quantity')}")

        # Submit order to broker (now safe - we're in main thread)
        signal_logger.info(f"ORDER: {signal_id} | SUBMITTING_TO_IBKR | Sending order to Interactive Brokers...")
        result = submit_order_to_broker(order_data)

        if result:
            # CRITICAL: Only create execution confirmation if order was actually FILLED or PARTIALLY FILLED
            # Do NOT create fake fills for orders that are just submitted/pending

            status = result.get('status', '')
            filled_qty = result.get('filled', 0)
            ib_order_id = result.get('ib_order_id')
            avg_fill_price = result.get('avg_fill_price', 0)

            logger.info(f"🔍 Order {order_id} result: status={status}, filled={filled_qty}")

            # Log IBKR response
            signal_logger.info(f"ORDER: {signal_id} | IBKR_RESPONSE | Status={status} | IBKR_OrderID={ib_order_id} | Filled={filled_qty} | AvgPrice=${avg_fill_price}")

            # Only proceed if there was an actual fill
            if status in ['Filled', 'PartiallyFilled'] or filled_qty > 0:
                signal_logger.info(f"ORDER: {signal_id} | ORDER_FILLED | Quantity={filled_qty} | Price=${avg_fill_price} | Status={status}")

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

                # Create or update position in open_positions collection
                create_or_update_position(order_data, filled_qty, avg_fill_price)

                # Update order status in database
                trading_orders_collection.update_one(
                    {"order_id": order_id},
                    {"$set": {"status": execution['status'], "updated_at": datetime.utcnow()}}
                )

                signal_logger.info(f"ORDER: {signal_id} | EXECUTION_CONFIRMED | Fill confirmed and saved to database")
                logger.info(f"✅ Order {order_id} executed: {execution['status']}")
            else:
                # Order submitted but not filled yet - just update status
                signal_logger.info(f"ORDER: {signal_id} | WAITING_FOR_FILL | Order accepted by IBKR, waiting for execution...")
                logger.info(f"📋 Order {order_id} submitted to IBKR, status: {status}")
                trading_orders_collection.update_one(
                    {"order_id": order_id},
                    {"$set": {"status": status, "ib_order_id": result.get('ib_order_id'), "updated_at": datetime.utcnow()}}
                )
        else:
            # Order failed
            signal_logger.error(f"ORDER: {signal_id} | ORDER_REJECTED | IBKR rejected the order - check execution_service.log for details")
            logger.error(f"❌ Order {order_id} failed to execute")

            # Update order status
            trading_orders_collection.update_one(
                {"order_id": order_id},
                {"$set": {"status": "REJECTED", "updated_at": datetime.utcnow()}}
            )

            # For exit orders, this is critical - implement retry logic
            if order_data.get('action') == 'EXIT':
                signal_logger.critical(f"ORDER: {signal_id} | EXIT_ORDER_FAILED | CRITICAL: Exit order failed - manual intervention required!")
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


def start_order_commands_subscriber():
    """
    Start Pub/Sub subscriber for order commands (cancel, modify, etc.)
    Runs in background thread
    """
    streaming_pull_future = subscriber.subscribe(order_commands_subscription, callback=order_commands_callback)
    logger.info("ExecutionService listening for order commands...")

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

    # Start Pub/Sub subscribers in background threads
    orders_subscriber_thread = threading.Thread(target=start_trading_orders_subscriber, daemon=True)
    orders_subscriber_thread.start()
    logger.info("Trading orders subscriber started in background thread")

    commands_subscriber_thread = threading.Thread(target=start_order_commands_subscriber, daemon=True)
    commands_subscriber_thread.start()
    logger.info("Order commands subscriber started in background thread")

    # Main loop: process orders AND commands from queues in main thread
    logger.info("Main thread ready to process orders and commands from queues")
    try:
        while True:
            # Check if there are orders in the queue (non-blocking)
            try:
                order_item = order_queue.get(timeout=0.1)
                process_order_from_queue(order_item)
            except queue.Empty:
                pass

            # Check if there are commands in the queue (non-blocking)
            try:
                command_item = command_queue.get(timeout=0.1)
                process_command_from_queue(command_item)
            except queue.Empty:
                pass

            # Small sleep to prevent CPU spinning
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Shutting down Execution Service")
        broker.disconnect()
