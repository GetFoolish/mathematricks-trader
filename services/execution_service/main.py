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
from ib_insync import IB, Stock, Option, Forex, Future, Order, MarketOrder, LimitOrder, ComboLeg, util

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

# Initialize IBKR connection
ib = IB()

# IBKR Configuration
IBKR_HOST = os.getenv('IBKR_HOST', '127.0.0.1')
IBKR_PORT = int(os.getenv('IBKR_PORT', '7497'))  # 7497 for TWS, 4002 for IB Gateway
IBKR_CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '1'))

# Order queue for threading safety
# Pub/Sub callbacks run in thread pool, but ib_insync needs main thread's event loop
order_queue = queue.Queue()
command_queue = queue.Queue()  # For cancel commands and other order management

# Track active IBKR orders by order_id for cancellation
active_ibkr_orders = {}  # {order_id: ib_insync.Trade}

# 🚨 CRITICAL FAILSAFE: Track processed signal IDs to prevent duplicate execution
processed_signal_ids = set()  # In-memory deduplication
SIGNAL_ID_EXPIRY_HOURS = 24  # Keep signal IDs for 24 hours


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


def create_contracts_from_order(order_data: Dict[str, Any]) -> list:
    """
    Create IBKR contracts from order data - supports multi-asset and multi-leg

    Returns:
        List of dicts: [{'contract': Contract, 'action': 'BUY'/'SELL', 'quantity': int, 'ratio': int}, ...]

    Raises:
        ValueError: If required fields missing or invalid
    """
    instrument = order_data.get('instrument', '').strip() if order_data.get('instrument') else ''
    instrument_type = (order_data.get('instrument_type') or '').upper()

    # Validation: instrument_type is REQUIRED
    if not instrument_type:
        raise ValueError("REJECTED: Missing required field 'instrument_type'. Must be STOCK, OPTION, FOREX, or FUTURE")

    if instrument_type not in ['STOCK', 'OPTION', 'FOREX', 'FUTURE']:
        raise ValueError(f"REJECTED: Invalid instrument_type '{instrument_type}'. Must be STOCK, OPTION, FOREX, or FUTURE")

    logger.info(f"🔍 create_contracts_from_order called | Type: {instrument_type} | Instrument: {instrument}")

    contracts_list = []

    if instrument_type == 'STOCK':
        # Stock contract
        if not instrument:
            raise ValueError("REJECTED: Missing 'instrument' field for STOCK type")

        contract = Stock(symbol=instrument, exchange='SMART', currency='USD')
        contracts_list.append({
            'contract': contract,
            'action': order_data.get('action', 'ENTRY').upper(),
            'quantity': order_data.get('quantity', 0),
            'ratio': 1
        })
        logger.info(f"✅ Created STOCK contract: {contract}")

    elif instrument_type == 'OPTION':
        # Option contract(s) - supports multi-leg
        legs = order_data.get('legs')
        if not legs or not isinstance(legs, list):
            raise ValueError("REJECTED: OPTION type requires 'legs' field as list")

        underlying = order_data.get('underlying', '').strip()
        if not underlying:
            raise ValueError("REJECTED: OPTION type requires 'underlying' field")

        for i, leg in enumerate(legs, 1):
            # Validate required fields per leg
            required_fields = ['strike', 'expiry', 'right', 'action', 'quantity']
            missing = [f for f in required_fields if f not in leg]
            if missing:
                raise ValueError(f"REJECTED: Option leg {i} missing required fields: {missing}")

            # Validate right field
            if leg['right'].upper() not in ['C', 'P', 'CALL', 'PUT']:
                raise ValueError(f"REJECTED: Option leg {i} invalid 'right' field: {leg['right']}. Must be C/P or CALL/PUT")

            right = leg['right'].upper()
            if right == 'CALL':
                right = 'C'
            elif right == 'PUT':
                right = 'P'

            contract = Option(
                symbol=underlying,
                lastTradeDateOrContractMonth=str(leg['expiry']),
                strike=float(leg['strike']),
                right=right,
                exchange='SMART'
            )

            contracts_list.append({
                'contract': contract,
                'action': leg['action'].upper(),
                'quantity': int(leg['quantity']),
                'ratio': leg.get('ratio', 1)
            })
            logger.info(f"✅ Created OPTION contract leg {i}: {underlying} {leg['strike']}{right} exp {leg['expiry']}")

    elif instrument_type == 'FOREX':
        # Forex contract
        if not instrument:
            raise ValueError("REJECTED: Missing 'instrument' field for FOREX type")

        # Instrument should be currency pair like EURUSD
        if len(instrument) != 6:
            raise ValueError(f"REJECTED: FOREX instrument must be 6-character currency pair (e.g. EURUSD), got: {instrument}")

        contract = Forex(pair=instrument, exchange='IDEALPRO')
        contracts_list.append({
            'contract': contract,
            'action': order_data.get('action', 'ENTRY').upper(),
            'quantity': order_data.get('quantity', 0),
            'ratio': 1
        })
        logger.info(f"✅ Created FOREX contract: {contract}")

    elif instrument_type == 'FUTURE':
        # Future contract
        if not instrument:
            raise ValueError("REJECTED: Missing 'instrument' field for FUTURE type")

        expiry = order_data.get('expiry', '').strip()
        if not expiry:
            raise ValueError("REJECTED: FUTURE type requires 'expiry' field (YYYYMMDD format)")

        exchange = order_data.get('exchange', 'NYMEX').upper()

        contract = Future(
            symbol=instrument,
            lastTradeDateOrContractMonth=expiry,
            exchange=exchange
        )
        contracts_list.append({
            'contract': contract,
            'action': order_data.get('action', 'ENTRY').upper(),
            'quantity': order_data.get('quantity', 0),
            'ratio': 1
        })
        logger.info(f"✅ Created FUTURE contract: {instrument} exp {expiry} on {exchange}")

    logger.info(f"🔍 Created {len(contracts_list)} contract(s)")
    return contracts_list


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
    Submit order(s) to IBKR - handles single and multi-leg orders

    For multi-leg orders (e.g., iron condor), submits each leg separately and aggregates results.
    """
    try:
        if not ib.isConnected():
            if not connect_to_ibkr():
                return None

        # Create contracts from order data (may return multiple for options)
        try:
            contracts_list = create_contracts_from_order(order_data)
        except ValueError as ve:
            # Validation error - reject immediately with clear message
            logger.error(f"❌ Order {order_data.get('order_id')} validation failed: {str(ve)}")
            return None

        if not contracts_list:
            logger.error(f"❌ No contracts created for order {order_data.get('order_id')}")
            return None

        logger.info(f"📋 Processing {len(contracts_list)} leg(s) for order {order_data.get('order_id')}")

        # For multi-leg, we'll submit each leg separately
        # In production, complex spreads should use ComboOrder, but for MVP we keep it simple
        trades = []
        all_qualified = True

        for i, contract_item in enumerate(contracts_list, 1):
            contract = contract_item['contract']
            leg_action = contract_item['action']
            leg_quantity = contract_item['quantity']

            logger.info(f"🔍 Qualifying leg {i}/{len(contracts_list)} with IBKR...")
            qualified_contracts = ib.qualifyContracts(contract)

            if not qualified_contracts:
                logger.error(f"❌ Failed to qualify contract leg {i}: {contract}")
                all_qualified = False
                continue

            qualified_contract = qualified_contracts[0]
            logger.info(f"✅ Contract leg {i} qualified: {qualified_contract}")

            # Determine BUY/SELL based on leg action and original direction
            # For options, leg action is explicit (from legs array)
            # For stock/forex/futures, use original order direction
            instrument_type = order_data.get('instrument_type', 'STOCK').upper()

            if instrument_type == 'OPTION':
                # Use explicit leg action
                ib_action = leg_action
            else:
                # Single-leg: derive from action field
                # Action can be: BUY, SELL, ENTRY, or EXIT
                action = order_data.get('action', '').upper()
                direction = order_data.get('direction', 'LONG').upper()

                # If action is explicitly BUY or SELL, use it directly
                if action in ['BUY', 'SELL']:
                    ib_action = action
                # Otherwise, derive from ENTRY/EXIT and direction
                elif action == 'ENTRY':
                    ib_action = 'BUY' if direction == 'LONG' else 'SELL'
                elif action == 'EXIT':
                    ib_action = 'SELL' if direction == 'LONG' else 'BUY'
                else:
                    # Fallback: assume ENTRY behavior
                    logger.warning(f"Unknown action '{action}', defaulting to ENTRY behavior")
                    ib_action = 'BUY' if direction == 'LONG' else 'SELL'

            # Create order for this leg
            order_type = order_data.get('order_type', 'MARKET').upper()
            price = order_data.get('price', 0)

            # Round quantity to whole number
            leg_quantity = int(round(leg_quantity))
            if leg_quantity == 0:
                leg_quantity = 1

            if order_type == 'MARKET':
                order = MarketOrder(ib_action, leg_quantity)
            elif order_type == 'LIMIT':
                order = LimitOrder(ib_action, leg_quantity, price)
            else:
                order = MarketOrder(ib_action, leg_quantity)

            # Place order for this leg
            logger.info(f"📤 Placing leg {i}: {ib_action} {leg_quantity} {qualified_contract.symbol}")
            trade = ib.placeOrder(qualified_contract, order)
            trades.append(trade)

        if not all_qualified:
            logger.error(f"❌ Some contracts failed qualification for order {order_data.get('order_id')}")
            return None

        # Wait for all legs to be processed
        ib.sleep(2)

        # Aggregate results from all legs
        all_statuses = []
        total_filled = 0
        rejected_count = 0

        for i, trade in enumerate(trades, 1):
            status = trade.orderStatus.status
            filled = trade.orderStatus.filled
            all_statuses.append(status)
            total_filled += filled

            if status in ['Cancelled', 'ApiCancelled', 'PendingCancel', 'Inactive']:
                logger.error(f"❌ Leg {i} was REJECTED by IBKR: {status}")
                logger.error(f"   Trade log: {trade.log}")
                rejected_count += 1
            else:
                logger.info(f"✅ Leg {i} submitted - Status: {status}, Filled: {filled}")

        if rejected_count > 0:
            logger.error(f"❌ Order {order_data.get('order_id')} - {rejected_count}/{len(trades)} legs rejected")
            return None

        # Determine overall status
        # If all legs same status, use that; otherwise use "Mixed"
        unique_statuses = set(all_statuses)
        if len(unique_statuses) == 1:
            overall_status = all_statuses[0]
        else:
            overall_status = "Mixed"

        logger.info(f"✅ Order {order_data.get('order_id')} submitted - {len(trades)} leg(s), Overall Status: {overall_status}")

        # Track active orders for cancellation
        order_id = order_data['order_id']
        active_ibkr_orders[order_id] = trades  # Store all trade objects for this order

        return {
            "order_id": order_data['order_id'],
            "ib_order_id": trades[0].order.orderId if trades else None,  # Return first leg's order ID
            "status": overall_status,
            "filled": total_filled,
            "remaining": sum(t.orderStatus.remaining for t in trades),
            "avg_fill_price": trades[0].orderStatus.avgFillPrice if trades else 0,
            "num_legs": len(trades)
        }

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


def cancel_order(order_id: str) -> bool:
    """
    Cancel an active order by order_id
    Returns True if successfully cancelled, False otherwise
    """
    try:
        if order_id not in active_ibkr_orders:
            logger.warning(f"⚠️ Cannot cancel order {order_id} - not found in active orders")
            return False

        trades = active_ibkr_orders[order_id]
        logger.info(f"🚫 Cancelling order {order_id} ({len(trades)} leg(s))...")

        # Cancel all legs of the order
        cancelled_count = 0
        for i, trade in enumerate(trades, 1):
            try:
                # Check if order is still cancellable
                status = trade.orderStatus.status
                if status in ['Filled', 'Cancelled', 'ApiCancelled', 'Inactive']:
                    logger.info(f"   Leg {i} already {status} - skipping")
                    continue

                # Cancel the order
                ib.cancelOrder(trade.order)
                cancelled_count += 1
                logger.info(f"   ✓ Cancelled leg {i}")

            except Exception as e:
                logger.error(f"   ✗ Error cancelling leg {i}: {e}")

        # Wait briefly for cancellation to process
        ib.sleep(0.5)

        # Remove from tracking
        del active_ibkr_orders[order_id]
        logger.info(f"✅ Order {order_id} cancelled ({cancelled_count}/{len(trades)} legs)")

        return cancelled_count > 0

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

    # Main loop: process orders AND commands from queues in main thread where IBKR event loop is available
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

            # Let IBKR process events
            ib.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Shutting down Execution Service")
        ib.disconnect()
