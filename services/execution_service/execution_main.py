"""
Execution Service - MVP
Connects to IBKR broker, executes orders, and reports back execution confirmations and account state.
"""
import os
import sys
import logging
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, List
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv
import threading
import time
import queue
import requests

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

# Load environment variables from project root
env_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(env_path)

# Configure logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Create custom formatter matching Cerebro format
custom_formatter = logging.Formatter('|%(levelname)s|%(message)s|%(asctime)s|file:%(filename)s:line No.%(lineno)d')

# Create file handler with custom format
file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'execution_service.log'))
file_handler.setFormatter(custom_formatter)

# Create console handler with same format
console_handler = logging.StreamHandler()
console_handler.setFormatter(custom_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Signal processing log handler - unified log for complete signal journey
signal_processing_handler = logging.FileHandler(os.path.join(LOG_DIR, 'signal_processing.log'))
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

# ========================================================================
# COMMAND-LINE ARGUMENTS
# ========================================================================

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Execution Service - Order Execution Engine')
parser.add_argument('--use-mock-broker', action='store_true',
                    help='Use Mock broker for all orders (testing mode, overrides strategy account routing)')
args = parser.parse_args()

# Log mode
if args.use_mock_broker:
    logger.warning("=" * 80)
    logger.warning("🧪 MOCK MODE ENABLED: All orders will be routed to Mock_Paper broker")
    logger.warning("=" * 80)

# ========================================================================
# DATABASE AND PUB/SUB INITIALIZATION
# ========================================================================

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
if not mongo_uri:
    raise ValueError("MONGODB_URI environment variable is not set - check .env file")

# Only use TLS for remote MongoDB Atlas connections (not localhost)
use_tls = 'mongodb+srv' in mongo_uri or 'mongodb.net' in mongo_uri
if use_tls:
    mongo_client = MongoClient(
        mongo_uri,
        tls=True,
        tlsAllowInvalidCertificates=True  # For development only
    )
else:
    mongo_client = MongoClient(mongo_uri)  # No TLS for localhost
db = mongo_client['mathematricks_trading']
# execution_confirmations collection removed - execution data stored in signal_store.execution field
trading_orders_collection = db['trading_orders']
trading_accounts_collection = db['trading_accounts']  # For position tracking
signal_store_collection = db['signal_store']  # For updating execution data

# Initialize Google Cloud Pub/Sub
project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
subscriber = pubsub_v1.SubscriberClient()
publisher = pubsub_v1.PublisherClient()

trading_orders_subscription = subscriber.subscription_path(project_id, 'trading-orders-sub')
order_commands_subscription = subscriber.subscription_path(project_id, 'order-commands-sub')
execution_confirmations_topic = publisher.topic_path(project_id, 'execution-confirmations')
account_updates_topic = publisher.topic_path(project_id, 'account-updates')

# Account Data Service Configuration
ACCOUNT_DATA_SERVICE_URL = os.getenv('ACCOUNT_DATA_SERVICE_URL', 'http://localhost:5001')

# IBKR Configuration (fallback for backward compatibility)
IBKR_HOST = os.getenv('IBKR_HOST', '127.0.0.1')
IBKR_PORT = int(os.getenv('IBKR_PORT', '7497'))  # 7497 for TWS, 4002 for IB Gateway
IBKR_CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '1'))

# ========================================================================
# BROKER POOL - Multi-Broker Architecture
# ========================================================================

# Broker pool: {account_id: broker_instance}
broker_pool = {}


def get_active_accounts_from_service() -> List[Dict[str, Any]]:
    """
    Query AccountDataService for all active accounts.

    Returns:
        List of active account dictionaries
    """
    try:
        response = requests.get(f"{ACCOUNT_DATA_SERVICE_URL}/api/v1/accounts")
        response.raise_for_status()
        accounts_data = response.json()

        # Filter for ACTIVE accounts only
        active_accounts = [
            acc for acc in accounts_data.get('accounts', [])
            if acc.get('status') == 'ACTIVE'
        ]

        logger.info(f"Found {len(active_accounts)} active accounts from AccountDataService")
        return active_accounts

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get accounts from AccountDataService: {str(e)}")
        logger.warning("Falling back to single IBKR broker configuration")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting accounts: {str(e)}")
        return []


def initialize_broker_pool():
    """
    Initialize broker pool by creating broker instances for all active accounts.
    Falls back to single IBKR broker if AccountDataService unavailable.
    """
    global broker_pool

    logger.info("Initializing broker pool from AccountDataService...")

    # Get active accounts
    accounts = get_active_accounts_from_service()

    if not accounts:
        # Fallback: Always create Mock broker (safer for testing and development)
        logger.warning("No accounts from AccountDataService - creating Mock broker as fallback")
        account_id = "Mock_Paper"
        broker_config = {
            "broker": "Mock",
            "account_id": account_id,
            "initial_equity": 1000000.0
        }

        try:
            broker_instance = BrokerFactory.create_broker(broker_config)
            broker_pool[account_id] = broker_instance
            logger.info(f"✅ Created fallback Mock broker for account: {account_id}")
        except Exception as e:
            logger.error(f"❌ Failed to create fallback Mock broker: {str(e)}")

        return

    # Create broker instance for each active account
    for account in accounts:
        account_id = account.get('account_id')
        broker_name = account.get('broker')
        auth_details = account.get('authentication_details', {})

        try:
            # Build broker config
            broker_config = {
                "broker": broker_name,
                "account_id": account_id,
                **auth_details  # Spread auth details (host, port, client_id, etc.)
            }

            # Create broker instance
            broker_instance = BrokerFactory.create_broker(broker_config)
            broker_pool[account_id] = broker_instance

            logger.info(f"✅ Created {broker_name} broker for account: {account_id}")

        except Exception as e:
            logger.error(f"❌ Failed to create {broker_name} broker for account {account_id}: {str(e)}")
            continue

    logger.info(f"Broker pool initialized with {len(broker_pool)} broker(s)")


def get_broker_for_account(account_id: str) -> Optional['AbstractBroker']:
    """
    Get broker instance for specific account.

    Args:
        account_id: Account ID (e.g., "IBKR_Paper", "Mock_Paper")

    Returns:
        Broker instance, or None if not found
    """
    if account_id not in broker_pool:
        logger.error(f"❌ No broker found for account: {account_id}")
        logger.error(f"   Available accounts: {list(broker_pool.keys())}")
        return None

    return broker_pool[account_id]


# Initialize broker pool on startup
initialize_broker_pool()

# Order queue for threading safety
# Pub/Sub callbacks run in thread pool, orders are processed in main thread
order_queue = queue.Queue()
command_queue = queue.Queue()  # For cancel commands and other order management

# Track active IBKR orders by order_id for cancellation
active_ibkr_orders = {}  # {order_id: broker_order_id}

# 🚨 CRITICAL FAILSAFE: Track processed signal IDs to prevent duplicate execution
processed_signal_ids = set()  # In-memory deduplication
SIGNAL_ID_EXPIRY_HOURS = 24  # Keep signal IDs for 24 hours


def connect_all_brokers():
    """
    Connect to all brokers in the broker pool.
    """
    logger.info(f"Connecting to {len(broker_pool)} broker(s)...")

    success_count = 0
    for account_id, broker_instance in broker_pool.items():
        try:
            if not broker_instance.is_connected():
                logger.info(f"Connecting to {broker_instance.broker_name} for account {account_id}...")
                success = broker_instance.connect()
                if success:
                    logger.info(f"✅ Connected to {broker_instance.broker_name} for {account_id}")
                    success_count += 1
                else:
                    logger.error(f"❌ Failed to connect to {broker_instance.broker_name} for {account_id}")
            else:
                logger.info(f"Already connected to {broker_instance.broker_name} for {account_id}")
                success_count += 1

        except BrokerConnectionError as e:
            logger.error(f"❌ Broker connection error for {account_id}: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting {account_id}: {str(e)}")

    logger.info(f"Broker pool connection complete: {success_count}/{len(broker_pool)} connected")
    return success_count > 0


def submit_order_to_broker(order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Submit order to broker using broker pool (multi-broker routing).

    Routes order to correct broker based on order['account'] field.
    In mock mode (--use-mock-broker), overrides all routing to Mock_Paper.
    """
    try:
        # Get account from order
        account_id = order_data.get('account')
        if not account_id:
            logger.error(f"❌ Order {order_data.get('order_id')} missing 'account' field - cannot route to broker")
            return None

        # MOCK MODE OVERRIDE: Route all orders to Mock_Paper if flag set
        if args.use_mock_broker:
            original_account = account_id
            account_id = 'Mock_Paper'
            logger.debug(f"MOCK MODE: Overriding account {original_account} → Mock_Paper")

        # Get broker instance for this account
        broker = get_broker_for_account(account_id)
        if not broker:
            logger.error(f"❌ No broker found for account {account_id} - order {order_data.get('order_id')} cannot be executed")
            return None

        # Ensure broker is connected
        if not broker.is_connected():
            logger.debug(f"Connecting to {broker.broker_name} for account {account_id}...")
            if not broker.connect():
                logger.error(f"❌ Failed to connect to {broker.broker_name} for {account_id}")
                return None

        logger.debug(f"Submitting order {order_data.get('order_id')} to {broker.broker_name} (account: {account_id})")

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

        logger.debug(f"Order {order_data.get('order_id')} submitted - Broker Order ID: {broker_order_id}, Status: {result.get('status')}")

        # Return result with fill data from broker (Mock broker fills instantly, real broker updates later)
        return {
            "order_id": order_data['order_id'],
            "ib_order_id": broker_order_id,
            "status": result.get('status'),
            "filled": result.get('filled', 0),
            "remaining": result.get('remaining', order_data.get('quantity', 0)),
            "avg_fill_price": result.get('avg_fill_price', 0),
            "fills": result.get('fills', []),
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
        logger.debug(f"Published execution confirmation: {message_id}")
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


def update_signal_store_with_execution(order_data: Dict[str, Any], execution_data: Dict[str, Any]):
    """
    Update signal_store with execution results and calculate PnL for EXIT signals

    Args:
        order_data: Original order data from trading order
        execution_data: Execution results (quantity_filled, avg_fill_price, fills, etc.)
    """
    try:
        from bson import ObjectId

        mathematricks_signal_id = order_data.get('mathematricks_signal_id')
        if not mathematricks_signal_id:
            logger.error(f"❌ No mathematricks_signal_id in order_data - cannot update signal_store | OrderID: {order_data.get('order_id')}")
            logger.error(f"   Order data keys: {list(order_data.keys())}")
            return

        logger.debug(f"Updating signal_store for mathematricks_signal_id: {mathematricks_signal_id}")

        action = order_data.get('action', 'ENTRY').upper()
        is_exit = action in ['EXIT', 'SELL']

        # Prepare execution update
        execution_update = {
            "execution": {
                "order_id": order_data.get('order_id'),
                "broker_order_id": execution_data.get('broker_order_id'),
                "status": "FILLED",
                "avg_fill_price": execution_data['avg_fill_price'],
                "quantity_filled": execution_data['quantity_filled'],
                "fills": execution_data.get('fills', []),
                "filled_at": datetime.utcnow()
            },
            "updated_at": datetime.utcnow()
        }

        if not is_exit:
            # ENTRY signal: Set position_status to OPEN
            execution_update["position_status"] = "OPEN"
            execution_update["execution"]["total_cost_basis"] = (
                execution_data['avg_fill_price'] * execution_data['quantity_filled']
            )

            # Update signal_store
            result = signal_store_collection.update_one(
                {"_id": ObjectId(mathematricks_signal_id)},
                {"$set": execution_update}
            )
            if result.matched_count > 0:
                logger.info(f"✅ Updated signal_store {mathematricks_signal_id} with ENTRY execution (position OPEN)")
            else:
                logger.error(f"❌ Failed to update signal_store - signal {mathematricks_signal_id} not found in database")

        else:
            # EXIT signal: Calculate PnL and update entry signal
            entry_signal_id = order_data.get('entry_signal_id')
            if not entry_signal_id:
                logger.warning("⚠️ EXIT signal missing entry_signal_id - cannot calculate PnL")
                # Still update this exit signal
                signal_store_collection.update_one(
                    {"_id": ObjectId(mathematricks_signal_id)},
                    {"$set": execution_update}
                )
                return

            # Get entry signal
            entry_signal = signal_store_collection.find_one({"_id": ObjectId(entry_signal_id)})
            if not entry_signal or not entry_signal.get('execution'):
                logger.error(f"❌ Entry signal {entry_signal_id} not found or has no execution data")
                return

            # Calculate PnL
            entry_price = entry_signal['execution']['avg_fill_price']
            exit_price = execution_data['avg_fill_price']
            quantity = execution_data['quantity_filled']

            gross_pnl = (exit_price - entry_price) * quantity
            commission = execution_data.get('commission', 0)  # TODO: Get actual commissions
            net_pnl = gross_pnl - commission

            entry_cost_basis = entry_signal['execution'].get('total_cost_basis', entry_price * quantity)
            pnl_percent = (net_pnl / entry_cost_basis) * 100 if entry_cost_basis > 0 else 0

            holding_period_seconds = (
                datetime.utcnow() - entry_signal['execution']['filled_at']
            ).total_seconds()

            # Prepare PnL data
            pnl_data = {
                "gross_pnl": gross_pnl,
                "commission": commission,
                "net_pnl": net_pnl,
                "pnl_percent": pnl_percent,
                "holding_period_seconds": holding_period_seconds
            }

            execution_update["pnl"] = pnl_data

            # Update EXIT signal
            signal_store_collection.update_one(
                {"_id": ObjectId(mathematricks_signal_id)},
                {"$set": execution_update}
            )

            # Update ENTRY signal: add to exit_signals array and set CLOSED
            signal_store_collection.update_one(
                {"_id": ObjectId(entry_signal_id)},
                {
                    "$push": {"exit_signals": ObjectId(mathematricks_signal_id)},
                    "$set": {
                        "position_status": "CLOSED",
                        "pnl_realized": net_pnl,
                        "closed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.debug(f"Updated signal_store with EXIT execution and PnL")
            logger.debug(f"Entry signal: {entry_signal['signal_id']} → position CLOSED")
            logger.debug(f"Exit signal: {order_data.get('signal_id')}")
            logger.debug(f"Gross P&L: ${gross_pnl:.2f} | Net P&L: ${net_pnl:.2f} ({pnl_percent:.2f}%)")

    except Exception as e:
        logger.error(f"❌ Error updating signal_store with execution: {e}", exc_info=True)


def create_or_update_position(order_data: Dict[str, Any], filled_qty: float, avg_fill_price: float):
    """
    Create or update position in trading_accounts.{account_id}.open_positions after order fill
    Handles both ENTRY (create/increase) and EXIT (decrease/close) actions
    """
    try:
        strategy_id = order_data.get('strategy_id')
        instrument = order_data.get('instrument')
        direction = order_data.get('direction', 'LONG').upper()
        action = order_data.get('action', 'ENTRY').upper()
        signal_type = order_data.get('signal_type', '').upper()
        order_id = order_data.get('order_id')

        # For Mock broker, use "Mock_Paper" account
        # TODO: Get account_id from order_data when multi-account support is added
        account_id = "Mock_Paper" if args.use_mock_broker else "IBKR_Main"

        # Find account document
        account_doc = trading_accounts_collection.find_one({"account_id": account_id})
        if not account_doc:
            # Create account document if it doesn't exist
            account_doc = {
                "account_id": account_id,
                "open_positions": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            trading_accounts_collection.insert_one(account_doc)

        # Find existing position in open_positions array
        existing_position = None
        position_index = None
        open_positions = account_doc.get('open_positions', [])

        for idx, pos in enumerate(open_positions):
            if (pos.get('strategy_id') == strategy_id and
                pos.get('instrument') == instrument and
                pos.get('status') == 'OPEN'):
                existing_position = pos
                position_index = idx
                break

        # Determine if this is ENTRY or EXIT using signal_type OR direction+action
        # signal_type is preferred (set by Cerebro), fallback to direction+action logic
        is_entry = (
            signal_type == 'ENTRY' or
            (not signal_type and direction == 'LONG' and action == 'BUY') or
            (not signal_type and direction == 'SHORT' and action == 'SELL')
        )

        if is_entry:
            # ENTRY: Create new position or add to existing
            if existing_position:
                # Add to existing position (scale-in)
                current_qty = existing_position['quantity']
                current_avg_price = existing_position['avg_entry_price']

                new_qty = current_qty + filled_qty
                # Calculate new weighted average price
                new_avg_price = ((current_qty * current_avg_price) + (filled_qty * avg_fill_price)) / new_qty

                # Update the position in the array using array index
                trading_accounts_collection.update_one(
                    {'account_id': account_id},
                    {'$set': {
                        f'open_positions.{position_index}.quantity': new_qty,
                        f'open_positions.{position_index}.avg_entry_price': new_avg_price,
                        f'open_positions.{position_index}.updated_at': datetime.utcnow(),
                        f'open_positions.{position_index}.last_order_id': order_id
                    }}
                )
                logger.info(f"✅ Updated position {strategy_id}/{instrument}: {current_qty} → {new_qty} shares @ ${new_avg_price:.2f}")
            else:
                # Create new position and add to array
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
                trading_accounts_collection.update_one(
                    {'account_id': account_id},
                    {'$push': {'open_positions': position}}
                )
                logger.info(f"✅ Created position {strategy_id}/{instrument}: {filled_qty} shares @ ${avg_fill_price:.2f}")

        else:
            # EXIT: Reduce or close position
            if existing_position:
                current_qty = existing_position['quantity']

                if filled_qty >= current_qty:
                    # Full exit - close position by updating status in array
                    trading_accounts_collection.update_one(
                        {'account_id': account_id},
                        {'$set': {
                            f'open_positions.{position_index}.status': 'CLOSED',
                            f'open_positions.{position_index}.exit_order_id': order_id,
                            f'open_positions.{position_index}.avg_exit_price': avg_fill_price,
                            f'open_positions.{position_index}.closed_at': datetime.utcnow(),
                            f'open_positions.{position_index}.updated_at': datetime.utcnow()
                        }}
                    )
                    logger.info(f"✅ Closed position {strategy_id}/{instrument}: {current_qty} shares @ ${avg_fill_price:.2f}")
                else:
                    # Partial exit - reduce position quantity in array
                    new_qty = current_qty - filled_qty
                    trading_accounts_collection.update_one(
                        {'account_id': account_id},
                        {'$set': {
                            f'open_positions.{position_index}.quantity': new_qty,
                            f'open_positions.{position_index}.updated_at': datetime.utcnow(),
                            f'open_positions.{position_index}.last_order_id': order_id
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

    TODO: Update this function to work with broker pool architecture
    For now, this function is disabled (calls are commented out)
    """
    logger.warning("get_account_state() called but is disabled - needs broker pool update")
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

        logger.debug(f"Received trading order: {order_id} - adding to queue")

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
        logger.debug(f"Processing order from queue: {order_id}")

        # 🚨 CRITICAL FAILSAFE: Check if signal already processed
        if signal_id in processed_signal_ids:
            logger.critical(f"🚨 DUPLICATE SIGNAL BLOCKED! Signal {signal_id} already processed - REJECTING to prevent duplicate execution!")
            signal_logger.critical(f"ORDER: {signal_id} | DUPLICATE_BLOCKED | This signal was already processed - order rejected for safety")
            message.ack()  # ACK the message to prevent redelivery
            return

        # Add to processed set
        processed_signal_ids.add(signal_id)
        logger.debug(f"Signal {signal_id} marked as processed (total tracked: {len(processed_signal_ids)})")

        # Log to signal_processing.log - Order received (concise)
        logger.info("-" * 50)
        logger.info(f"📥 ORDER RECEIVED: {order_data.get('instrument')} | {order_data.get('direction')} | Qty: {order_data.get('quantity')} | OrderID: {order_id}")
        signal_logger.info(f"ORDER: {signal_id} | ORDER_RECEIVED | OrderID={order_id} | Instrument={order_data.get('instrument')} | Direction={order_data.get('direction')} | Quantity={order_data.get('quantity')}")

        # Submit order to broker (now safe - we're in main thread)
        logger.debug(f"Submitting order {order_id} to broker...")
        result = submit_order_to_broker(order_data)

        if result:
            # CRITICAL: Only create execution confirmation if order was actually FILLED or PARTIALLY FILLED
            # Do NOT create fake fills for orders that are just submitted/pending

            status = result.get('status', '')
            filled_qty = result.get('filled', 0)
            ib_order_id = result.get('ib_order_id')
            avg_fill_price = result.get('avg_fill_price', 0)

            logger.debug(f"Order {order_id} result: status={status}, filled={filled_qty}")

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

                # Note: Execution data is stored in signal_store.execution field
                # (redundant execution_confirmations collection removed)

                # Publish execution confirmation
                logger.debug(f"Publishing execution confirmation for {order_id}")
                publish_execution_confirmation(execution)

                # Create or update position in open_positions collection
                logger.debug(f"Creating/updating position for {order_id}")
                create_or_update_position(order_data, filled_qty, avg_fill_price)

                # Update signal_store with execution data and calculate PnL
                execution_data = {
                    "broker_order_id": result.get('ib_order_id'),
                    "quantity_filled": filled_qty,
                    "avg_fill_price": avg_fill_price,
                    "fills": result.get('fills', []),
                    "commission": 0  # TODO: Get actual commission from IBKR
                }
                logger.debug(f"Updating signal_store for {order_id}")
                update_signal_store_with_execution(order_data, execution_data)

                # Update order status in database
                trading_orders_collection.update_one(
                    {"order_id": order_id},
                    {"$set": {"status": execution['status'], "updated_at": datetime.utcnow()}}
                )

                signal_logger.info(f"ORDER: {signal_id} | EXECUTION_CONFIRMED | Fill confirmed and saved to database")
                logger.info(f"✅ ORDER COMPLETED: {order_data.get('instrument')} | Filled: {filled_qty} @ ${avg_fill_price:.2f} | Status: {execution['status']}")
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
        # TODO: Update get_account_state() to work with broker pool
        # account_state = get_account_state()
        # if account_state:
        #     publish_account_update(account_state)

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
    logger.debug("Trading orders subscriber started")

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
    logger.debug("Order commands subscriber started")

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
            # TODO: Update get_account_state() to work with broker pool
            # account_state = get_account_state()
            # if account_state:
            #     publish_account_update(account_state)
        except Exception as e:
            logger.error(f"Error in periodic account updates: {str(e)}")


if __name__ == "__main__":
    logger.info("🚀 Execution Service Starting")

    # Connect to all brokers in pool (continue even if some fail - orders will route to available brokers)
    if not connect_all_brokers():
        logger.warning("⚠️  No brokers connected - orders will queue until brokers available")
    else:
        logger.info(f"✅ Broker pool: {len(broker_pool)} broker(s) ready")

    # Initialize Mock broker with empty positions
    if args.use_mock_broker:
        account_id = "Mock_Paper"
        trading_accounts_collection.update_one(
            {'account_id': account_id},
            {
                '$set': {
                    'open_positions': [],
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        logger.info(f"✅ Mock broker account '{account_id}' initialized with empty positions")

    # Start Pub/Sub subscribers in background threads
    orders_subscriber_thread = threading.Thread(target=start_trading_orders_subscriber, daemon=True)
    orders_subscriber_thread.start()

    commands_subscriber_thread = threading.Thread(target=start_order_commands_subscriber, daemon=True)
    commands_subscriber_thread.start()

    logger.info("✅ Execution Service ready - listening for orders")
    logger.info("*" * 50)
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
