"""
Cerebro Service - Pub/Sub Signal Processing Only
The intelligent core for portfolio management, risk assessment, and position sizing.
Implements hard margin limits and smart position sizing.
"""
import os
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
import threading

# Portfolio constructor imports
from portfolio_constructor.base import PortfolioConstructor
from portfolio_constructor.context import (
    PortfolioContext, Signal, SignalDecision, Position, Order
)
from portfolio_constructor.max_cagr.strategy import MaxCAGRConstructor
from portfolio_constructor.max_hybrid.strategy import MaxHybridConstructor

# Position manager import
from position_manager import PositionManager

# Margin calculation imports
from margin_calculation import MarginCalculatorFactory
from broker_adapter import CerebroBrokerAdapter

# Precision service import
from precision_service import get_precision_service

# Load environment variables
# Determine project root dynamically
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SERVICE_DIR))
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(ENV_PATH)

# Configure logging
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Create custom formatter for both file and console
custom_formatter = logging.Formatter('|%(levelname)s|%(message)s|%(asctime)s|file:%(filename)s:line No.%(lineno)d')

# Create file handler with custom format
file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'cerebro_service.log'))
file_handler.setFormatter(custom_formatter)

# Create console handler with same format
console_handler = logging.StreamHandler()
console_handler.setFormatter(custom_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Signal processing handler - unified log for signal journey (lazy initialization)
signal_processing_handler = None

def get_signal_processing_logger():
    """Lazy initialization of signal_processing.log handler"""
    global signal_processing_handler
    if signal_processing_handler is None:
        signal_processing_handler = logging.FileHandler(os.path.join(LOG_DIR, 'signal_processing.log'))
        signal_processing_handler.setLevel(logging.INFO)
        signal_processing_formatter = logging.Formatter(
            '%(asctime)s | [CEREBRO] | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        signal_processing_handler.setFormatter(signal_processing_formatter)
        signal_processing_handler.addFilter(lambda record: 'SIGNAL:' in record.getMessage())
        logger.addHandler(signal_processing_handler)
        logger.info("Signal processing log initialized")
    return logger


# ============================================================================
# MONGODB CONNECTION
# ============================================================================

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
# Only use TLS for remote MongoDB Atlas connections
use_tls = 'mongodb+srv' in mongo_uri or 'mongodb.net' in mongo_uri
if use_tls:
    mongo_client = MongoClient(
        mongo_uri,
        tls=True,
        tlsAllowInvalidCertificates=True  # For development only
    )
else:
    mongo_client = MongoClient(mongo_uri)
db = mongo_client['mathematricks_trading']
trading_orders_collection = db['trading_orders']
signal_store_collection = db['signal_store']  # Unified signal storage with embedded cerebro decisions
portfolio_allocations_collection = db['portfolio_allocations']
current_allocation_collection = db['current_allocation']  # Current approved allocation
strategies_collection = db['strategies']

# Collections from signal_collector database (for Activity tab)
signals_db = mongo_client['mathematricks_signals']
incoming_signals_collection = signals_db['trading_signals']  # Raw signals from webhook

# Initialize Position Manager
# Use Mock_Paper account by default (consistent with execution_service)
# TODO: Support multi-account routing based on strategy configuration
DEFAULT_ACCOUNT_ID = os.getenv('DEFAULT_ACCOUNT_ID', 'Mock_Paper')
position_manager = PositionManager(mongo_client, default_account_id=DEFAULT_ACCOUNT_ID)

# Initialize Broker Adapter for margin calculations
# Check if we're in mock broker mode
USE_MOCK_BROKER = os.getenv('USE_MOCK_BROKER', 'false').lower() == 'true'
broker_adapter = CerebroBrokerAdapter(broker_name="IBKR", use_mock=USE_MOCK_BROKER)

# Initialize Precision Service for quantity normalization
precision_service = get_precision_service(PROJECT_ROOT)


def round_quantity_for_instrument(quantity: float, instrument_type: str) -> float:
    """
    Round quantity based on instrument type precision.

    Args:
        quantity: Raw quantity to round
        instrument_type: Type of instrument (STOCK, CRYPTO, FOREX, etc.)

    Returns:
        Rounded quantity appropriate for the instrument type
    """
    precision = precision_service._get_default_precision(instrument_type)
    return precision_service.normalize_quantity(quantity, precision)


# Helper function to update signal_store with cerebro decision
def update_signal_store_with_decision(signal_store_id: str, decision_doc: dict):
    """
    Update signal_store document with embedded cerebro_decision
    This is the single source of truth for cerebro decisions
    """
    if not signal_store_id:
        logger.warning("⚠️ No signal_store_id provided, skipping signal_store update")
        return

    try:
        from bson import ObjectId

        # Update signal_store with embedded decision
        signal_store_collection.update_one(
            {"_id": ObjectId(signal_store_id)},
            {
                "$set": {
                    "cerebro_decision": decision_doc,
                    "processing_complete": decision_doc.get("decision") in ["APPROVED", "RESIZE"],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"✅ Updated signal_store {signal_store_id} with cerebro decision")

    except Exception as e:
        logger.error(f"⚠️ Failed to update signal_store: {e}")


# ============================================================================
# GOOGLE CLOUD PUB/SUB
# ============================================================================

# Pub/Sub clients (initialized in main block to avoid triggering during imports)
project_id = None
subscriber = None
publisher = None
signals_subscription = None
trading_orders_topic = None
order_commands_topic = None

# AccountDataService URL
ACCOUNT_DATA_SERVICE_URL = os.getenv('ACCOUNT_DATA_SERVICE_URL', 'http://localhost:8082')


# ============================================================================
# CONFIGURATION
# ============================================================================

# MVP Configuration
MVP_CONFIG = {
    "max_margin_utilization_pct": 40,  # Hard limit - never exceed 40% margin utilization
    "default_position_size_pct": 5,  # Fallback if no allocation found
    "slippage_alpha_threshold": 0.30,  # Drop signal if >30% alpha lost to slippage
}

# Global: Active portfolio allocations {strategy_id: allocation_pct}
ACTIVE_ALLOCATIONS = {}
ALLOCATIONS_LOCK = threading.Lock()

# Global: Portfolio Constructor instance
PORTFOLIO_CONSTRUCTOR = None
CONSTRUCTOR_LOCK = threading.Lock()


# ============================================================================
# PORTFOLIO CONSTRUCTOR
# ============================================================================

def initialize_portfolio_constructor():
    """Initialize the portfolio constructor (MaxHybrid strategy)"""
    global PORTFOLIO_CONSTRUCTOR

    with CONSTRUCTOR_LOCK:
        if PORTFOLIO_CONSTRUCTOR is None:
            logger.info("Initializing Portfolio Constructor (MaxHybrid)")

            # Use cached approved allocations for speed (signals are time-critical)
            # This file is updated by PortfolioBuilder when allocations are approved via frontend
            allocations_cache_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'current_portfolio_allocation_approved.json'
            )

            PORTFOLIO_CONSTRUCTOR = MaxHybridConstructor(
                alpha=0.85,  # 85% Sharpe, 15% CAGR weighting
                max_drawdown_limit=-0.06,  # -6% max drawdown
                max_leverage=2.3,  # 230% max allocation
                max_single_strategy=1.0,  # 100% max per strategy
                min_allocation=0.01,  # 1% minimum
                cagr_target=2.0,  # 200% CAGR target for normalization
                use_cached_allocations=True,  # ⚡ Use cached allocations (not recalculated - signals are time-critical)
                allocations_config_path=allocations_cache_path,  # current_portfolio_allocation_approved.json
                risk_free_rate=0.0
            )
            logger.info("✅ Portfolio Constructor initialized (MaxHybrid)")

    return PORTFOLIO_CONSTRUCTOR


def load_active_allocations() -> Dict[str, float]:
    """
    Load active portfolio allocations from MongoDB
    Returns dict of {strategy_id: allocation_pct}
    """
    try:
        # Find the currently ACTIVE allocation
        active_allocation = portfolio_allocations_collection.find_one(
            {"status": "ACTIVE"},
            sort=[("approved_at", -1)]  # Get most recently approved
        )

        if not active_allocation:
            logger.warning("No ACTIVE portfolio allocation found in MongoDB")
            logger.warning("Using fallback: equal allocation for all strategies")
            return {}

        allocations = active_allocation.get('allocations', {})
        logger.info(f"✅ Loaded ACTIVE portfolio allocation (ID: {active_allocation.get('allocation_id')})")
        logger.info(f"   Total strategies: {len(allocations)}")
        logger.info(f"   Total allocation: {sum(allocations.values()):.2f}%")

        for strategy_id, pct in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"     • {strategy_id}: {pct:.2f}%")

        return allocations

    except Exception as e:
        logger.error(f"Failed to load active allocations: {str(e)}")
        return {}


def download_allocations_from_mongo_to_cache(update_action: str = "cerebro_restart"):
    """
    Download current allocation from MongoDB and save to local JSON cache.
    This is called on Cerebro startup and when allocations change.

    Args:
        update_action: Either 'cerebro_restart' or 'allocation_changed_by_user'
    """
    try:
        # Get current allocation from MongoDB
        allocation_doc = current_allocation_collection.find_one({}, {'_id': 0})

        if not allocation_doc:
            logger.warning("⚠️  No current allocation found in MongoDB")
            return

        allocations = allocation_doc.get('allocations', {})

        # Save to local JSON cache
        cache_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'current_portfolio_allocation_approved.json'
        )

        cache_data = {
            "_comment": "Current approved portfolio allocation (downloaded from MongoDB)",
            "_source": "MongoDB current_allocation collection",
            "_metadata": {
                "approved_at": allocation_doc.get('approved_at', datetime.utcnow()).isoformat() if isinstance(allocation_doc.get('approved_at'), datetime) else str(allocation_doc.get('approved_at')),
                "num_strategies": len([v for v in allocations.values() if v > 0])
            },
            "allocations": allocations,
            "total_allocation_pct": sum(allocations.values()),
            "mode": "approved_downloaded_from_mongo",
            "last_updated": datetime.utcnow().isoformat(),
            "update_action": update_action
        }

        with open(cache_path, 'w') as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"✅ Downloaded allocations from MongoDB to cache: {cache_path}")
        logger.info(f"   Update action: {update_action}")
        logger.info(f"   Strategies: {len(allocations)}, Total: {sum(allocations.values()):.1f}%")

    except Exception as e:
        logger.error(f"❌ Failed to download allocations from MongoDB: {e}", exc_info=True)


def reload_allocations():
    """
    Reload active allocations from MongoDB (thread-safe)
    """
    global ACTIVE_ALLOCATIONS
    with ALLOCATIONS_LOCK:
        ACTIVE_ALLOCATIONS = load_active_allocations()
    logger.info(f"Portfolio allocations reloaded: {len(ACTIVE_ALLOCATIONS)} strategies")


def load_strategy_histories_from_mongodb() -> Dict[str, Any]:
    """
    Load strategy backtest equity curves from MongoDB.

    Returns:
        Dict mapping strategy_id to DataFrame with returns
    """
    import pandas as pd

    histories = {}

    try:
        # Query all ACTIVE strategies from MongoDB
        strategies = list(strategies_collection.find({"status": "ACTIVE"}))

        logger.info(f"Loading histories for {len(strategies)} ACTIVE strategies...")

        for strat_doc in strategies:
            strategy_id = strat_doc.get('strategy_id')

            if not strategy_id:
                continue

            # Try to extract backtest equity curve from raw_data_backtest_full
            if 'raw_data_backtest_full' in strat_doc:
                raw_data = strat_doc['raw_data_backtest_full']

                # Should be a list of dicts with 'date', 'return', 'account_equity', etc
                if isinstance(raw_data, list) and len(raw_data) > 0:
                    try:
                        # Extract returns from backtest data
                        dates = [pd.to_datetime(item['date']) for item in raw_data]
                        returns = [item.get('return', 0) for item in raw_data]

                        # Create DataFrame
                        df = pd.DataFrame({
                            'returns': returns  # Note: plural 'returns' to match MaxHybrid expectation
                        }, index=dates)

                        # Remove any NaN values
                        df = df.dropna()

                        if len(df) > 0:
                            histories[strategy_id] = df
                            logger.info(f"  ✅ {strategy_id}: Loaded {len(df)} backtest returns")
                        else:
                            logger.warning(f"  ⚠️  {strategy_id}: Backtest data produced zero valid returns")

                    except (KeyError, ValueError, TypeError) as e:
                        logger.error(f"  ❌ {strategy_id}: Failed to parse backtest data - {e}")
                else:
                    logger.warning(f"  ⚠️  {strategy_id}: raw_data_backtest_full is empty or invalid format")
            else:
                logger.warning(f"  ⚠️  {strategy_id}: No raw_data_backtest_full field")

        if histories:
            logger.info(f"✅ Successfully loaded {len(histories)} strategy histories")
        else:
            logger.warning("⚠️  NO strategy histories loaded - optimizer will have no data to work with")

    except Exception as e:
        logger.error(f"Error loading strategy histories: {e}", exc_info=True)

    return histories


# ============================================================================
# STRATEGY METADATA & CACHING
# ============================================================================



def get_strategy_metadata(strategy_id: str) -> Dict[str, Any]:
    """
    Get strategy metadata for backtest margin comparison.

    Returns:
        dict with:
            - median_margin_pct (decimal, e.g., 0.5 for 50%)
    """
    try:
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            logger.warning(f"Strategy {strategy_id} not found in MongoDB")
            return {
                "median_margin_pct": 0.5  # 50% default
            }

        position_sizing = strategy.get('position_sizing', {})
        return {
            "median_margin_pct": position_sizing.get('median_margin_pct', 50.0) / 100.0  # Convert % to decimal
        }
    except Exception as e:
        logger.error(f"Error getting strategy metadata for {strategy_id}: {e}")
        return {
            "median_margin_pct": 0.5
        }


def get_strategy_document(strategy_id: str) -> Optional[Dict[str, Any]]:
    """
    Get full strategy document from MongoDB including accounts field.

    Args:
        strategy_id: Strategy identifier

    Returns:
        Strategy document dict or None if not found
    """
    try:
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            logger.warning(f"Strategy {strategy_id} not found in MongoDB")
            return None
        return strategy
    except Exception as e:
        logger.error(f"Error getting strategy document for {strategy_id}: {e}")
        return None


# ============================================================================
# MARGIN ESTIMATION
# ============================================================================

def estimate_ibkr_margin(signal: Dict[str, Any], quantity: float, price: float) -> Dict[str, Any]:
    """
    Estimate realistic IBKR margin requirements based on asset class.

    This provides realistic margin estimates for different asset types,
    which may differ significantly from historical backtest margins.

    Args:
        signal: Signal dictionary containing instrument_type and other fields
        quantity: Number of units/shares/contracts
        price: Price per unit

    Returns:
        Dict with:
            - estimated_margin: Dollar amount required for margin
            - margin_pct: Percentage of notional value
            - calculation_method: Description of how margin was calculated
            - notional_value: Total position notional value
    """
    instrument_type = (signal.get('instrument_type') or 'STOCK').upper()
    notional_value = quantity * price

    # Asset-specific margin rates (based on typical IBKR requirements)
    if instrument_type == 'STOCK':
        margin_pct = 0.25  # Reg T: 25% of stock value
        method = "Reg T Margin (25% of stock value)"
        estimated_margin = notional_value * margin_pct

    elif instrument_type == 'FOREX':
        margin_pct = 0.02  # 50:1 leverage = 2% margin
        method = "Forex Margin (50:1 leverage)"
        estimated_margin = notional_value * margin_pct

    elif instrument_type == 'FUTURE':
        # Futures margin varies by contract
        # Use conservative 5% estimate (real margin depends on contract specs)
        margin_pct = 0.05
        method = "Futures Initial Margin (5% conservative estimate)"

        # Apply contract multiplier for futures
        # Most commodity futures have multipliers: GC=100oz, CL=1000barrels, etc.
        multiplier = 100
        notional_value = quantity * price * multiplier
        estimated_margin = notional_value * margin_pct

    elif instrument_type == 'OPTION':
        # Options: Use SPAN-like estimate based on underlying notional
        # For multi-leg: sum individual leg margins
        legs = signal.get('legs', [])

        if legs:
            # Multi-leg option strategy (e.g., iron condor, spreads)
            total_margin = 0
            for leg in legs:
                leg_notional = leg['quantity'] * leg['strike'] * 100  # Options multiplier
                # Rough SPAN estimate: ~20% of notional per leg
                total_margin += leg_notional * 0.20

            estimated_margin = total_margin
            margin_pct = (estimated_margin / notional_value * 100) if notional_value > 0 else 20.0
            method = f"Multi-leg Option SPAN estimate ({len(legs)} legs)"
        else:
            # Single option position
            margin_pct = 0.20
            method = "Single Option SPAN estimate (20% of notional)"
            estimated_margin = notional_value * 100 * margin_pct  # Options multiplier
    else:
        # Unknown type - use conservative 25%
        margin_pct = 0.25
        method = "Default conservative estimate"
        estimated_margin = notional_value * margin_pct

    return {
        'estimated_margin': estimated_margin,
        'margin_pct': margin_pct * 100 if margin_pct < 1 else margin_pct,  # Convert to percentage if decimal
        'calculation_method': method,
        'notional_value': notional_value
    }


# ============================================================================
# POSITION MANAGEMENT
# ============================================================================

def get_deployed_capital(strategy_id: str) -> Dict[str, Any]:
    """
    Get currently deployed capital for a strategy from OPEN positions (not pending orders).
    Uses PositionManager for accurate position tracking.

    Args:
        strategy_id: Strategy ID to check

    Returns:
        Dict with:
            - deployed_capital: Total cost basis of open positions
            - deployed_margin: Total margin used
            - open_positions: List of position documents
            - position_count: Number of open positions
    """
    try:
        return position_manager.get_deployed_capital(strategy_id)
    except Exception as e:
        logger.error(f"Error getting deployed capital for {strategy_id}: {e}")
        return {
            'deployed_capital': 0.0,
            'deployed_margin': 0.0,
            'open_positions': [],
            'position_count': 0
        }


# ============================================================================
# ACCOUNT DATA
# ============================================================================

def get_account_state(account_name: str) -> Optional[Dict[str, Any]]:
    """
    Query AccountDataService for current account state
    """
    try:
        response = requests.get(f"{ACCOUNT_DATA_SERVICE_URL}/api/v1/account/{account_name}/state")
        response.raise_for_status()
        return response.json().get('state')
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.error(f"No account state found for {account_name} - signals will be rejected")
            return None
        logger.error(f"Failed to get account state for {account_name}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Failed to get account state for {account_name}: {str(e)}")
        return None


# ============================================================================
# ORDER COMMANDS
# ============================================================================

def publish_cancel_command(order_id: str, reason: str = ""):
    """
    Publish a cancel command to order-commands topic
    """
    try:
        command_data = {
            'command': 'CANCEL',
            'order_id': order_id,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
        message_data = json.dumps(command_data, default=str).encode('utf-8')
        future = publisher.publish(order_commands_topic, message_data)
        message_id = future.result()
        logger.info(f"✅ Published cancel command for order {order_id}: {message_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error publishing cancel command for {order_id}: {e}")
        return False


def check_and_cancel_pending_entry(signal: Dict[str, Any], signal_type_info: Dict[str, Any]) -> bool:
    """
    Check if there's a pending ENTRY order for this instrument/strategy that should be cancelled
    Returns True if a pending order was found and cancel command was sent
    """
    try:
        # Only check for EXIT signals
        if signal_type_info.get('signal_type') != 'EXIT':
            return False

        strategy_id = signal.get('strategy_id')
        instrument = signal.get('instrument')

        # Query trading_orders collection for pending ENTRY orders
        pending_orders = list(trading_orders_collection.find({
            'strategy_id': strategy_id,
            'instrument': instrument,
            'status': {'$in': ['PENDING', 'SUBMITTED', 'PRESUBMITTED']},  # Order statuses before fill
            'action': {'$in': ['ENTRY', 'BUY', 'SELL']}  # ENTRY orders
        }).sort('created_at', -1).limit(5))  # Check last 5 orders

        if not pending_orders:
            logger.info(f"✅ No pending ENTRY orders found for {strategy_id}/{instrument}")
            return False

        # Cancel all pending ENTRY orders
        cancelled_count = 0
        for order in pending_orders:
            order_id = order.get('order_id')
            logger.warning(f"🚫 EXIT signal received but ENTRY order {order_id} is still pending - sending cancel command")

            success = publish_cancel_command(
                order_id,
                reason=f"EXIT signal received for {instrument} before ENTRY filled"
            )

            if success:
                cancelled_count += 1
                # Update order status in MongoDB to 'CANCEL_REQUESTED'
                trading_orders_collection.update_one(
                    {'order_id': order_id},
                    {'$set': {
                        'status': 'CANCEL_REQUESTED',
                        'cancel_requested_at': datetime.utcnow(),
                        'cancel_reason': 'EXIT signal received before fill'
                    }}
                )

        if cancelled_count > 0:
            logger.info(f"✅ Sent cancel commands for {cancelled_count} pending ENTRY order(s)")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Error checking/cancelling pending orders: {e}", exc_info=True)
        return False


def opposite_direction(direction: str) -> str:
    """Get opposite direction for entry/exit matching"""
    return "LONG" if direction == "SHORT" else "SHORT"


def find_open_entry_signal(strategy_id: str, instrument: str, direction: str) -> Optional[Dict[str, Any]]:
    """
    Query signal_store for open entry signal

    Args:
        strategy_id: Strategy identifier
        instrument: Instrument name
        direction: Direction of the EXIT signal (we need opposite for ENTRY)

    Returns:
        Entry signal document from signal_store, or None if not found
    """
    try:
        # For an EXIT signal with direction SHORT, we need to find ENTRY with direction LONG (and vice versa)
        entry_direction = opposite_direction(direction)

        entry_signal = signal_store_collection.find_one({
            "strategy_id": strategy_id,
            "instrument": instrument,
            "direction": entry_direction,
            "position_status": "OPEN",
            "cerebro_decision.decision": "APPROVE",
            "execution.status": "FILLED"
        })

        if entry_signal:
            logger.info(f"✅ Found open entry signal: {entry_signal.get('signal_id')} for {instrument} {entry_direction}")
            return entry_signal
        else:
            logger.warning(f"⚠️ No open entry signal found for {strategy_id}/{instrument}/{entry_direction}")
            return None

    except Exception as e:
        logger.error(f"❌ Error querying signal_store for entry signal: {e}")
        return None


def wait_for_entry_fill(strategy_id: str, instrument: str, direction: str, max_wait: int = 30) -> Optional[Dict[str, Any]]:
    """
    Wait for entry order to fill with exponential backoff retry logic.

    This handles the case where EXIT signals arrive before ENTRY orders fill in the broker.
    Instead of rejecting the EXIT signal, we wait for the entry to fill.

    Args:
        strategy_id: Strategy identifier
        instrument: Instrument name
        direction: Direction of the EXIT signal (we need opposite for ENTRY)
        max_wait: Maximum total wait time in seconds (default: 30)

    Returns:
        Entry signal document from signal_store if filled, or None if timeout
    """
    logger.info(f"⏳ Waiting for entry order to fill (max {max_wait}s)...")

    # First check if entry signal already filled
    entry_signal = find_open_entry_signal(strategy_id, instrument, direction)
    if entry_signal:
        logger.info(f"✅ Entry already filled, proceeding with exit")
        return entry_signal

    # Check if there's a pending ENTRY order
    entry_direction = opposite_direction(direction)

    try:
        # DEBUG: First let's see what entry signals exist for this instrument (newest first)
        debug_query = {
            "strategy_id": strategy_id,
            "instrument": instrument,
            "direction": entry_direction
        }
        all_entries = list(signal_store_collection.find(debug_query).sort("created_at", -1).limit(5))
        logger.info(f"🔍 DEBUG: Found {len(all_entries)} entry signals for {strategy_id}/{instrument}/{entry_direction} (showing 5 most recent)")
        for idx, entry in enumerate(all_entries, 1):
            logger.info(f"   Entry {idx}: signal_id={entry.get('signal_id')}")
            logger.info(f"            cerebro_decision.action={entry.get('cerebro_decision', {}).get('action')}")
            logger.info(f"            position_status={entry.get('position_status')}")
            logger.info(f"            execution.status={entry.get('execution', {}).get('status') if entry.get('execution') else None}")
            logger.info(f"            execution (full)={entry.get('execution')}")

        # Query for pending ENTRY order in signal_store (cerebro approved but not filled yet)
        # Note: execution field is null until order fills, position_status is null until filled
        pending_entry = signal_store_collection.find_one({
            "strategy_id": strategy_id,
            "instrument": instrument,
            "direction": entry_direction,
            "cerebro_decision.decision": "APPROVE",
            "position_status": {"$ne": "CLOSED"},  # Include null, "OPEN", and any other non-CLOSED status
            "$or": [
                {"execution": None},  # Order not yet sent to execution_service
                {"execution": {"$exists": False}},  # No execution field at all
                {"execution.status": {"$nin": ["FILLED"]}}  # Order in-flight but not filled
            ]
        })

        if not pending_entry:
            logger.warning(f"⚠️ No pending entry order found for {strategy_id}/{instrument}/{entry_direction}")
            logger.warning(f"   Cannot wait for fill - rejecting EXIT signal")
            return None

        logger.info(f"📋 Found pending entry order: {pending_entry.get('signal_id')}")
        logger.info(f"   Status: {pending_entry.get('execution', {}).get('status', 'UNKNOWN')}")

        # Retry with exponential backoff: 2s, 4s, 8s, 16s (max 30s total)
        retry_delays = [2, 4, 8, 16]
        total_waited = 0

        for i, delay in enumerate(retry_delays, 1):
            # Cap delay to not exceed max_wait
            actual_delay = min(delay, max_wait - total_waited)
            if actual_delay <= 0:
                break

            logger.info(f"⏳ Retry {i}/{len(retry_delays)}: Waiting {actual_delay}s for entry to fill...")
            time.sleep(actual_delay)
            total_waited += actual_delay

            # Check if entry filled during wait
            entry_signal = find_open_entry_signal(strategy_id, instrument, direction)
            if entry_signal:
                logger.info(f"✅ Entry filled after {total_waited}s wait! Proceeding with exit")
                return entry_signal

            # Check if we've exceeded max wait time
            if total_waited >= max_wait:
                logger.error(f"⏰ Timeout after {total_waited}s - entry order still not filled")
                break

        # Timeout - send critical alert
        logger.critical(f"🚨 CRITICAL: EXIT signal timeout waiting for entry fill")
        logger.critical(f"   Strategy: {strategy_id}")
        logger.critical(f"   Instrument: {instrument}")
        logger.critical(f"   Direction: {entry_direction}")
        logger.critical(f"   Pending Entry Signal: {pending_entry.get('signal_id')}")
        logger.critical(f"   Waited: {total_waited}s")
        logger.critical(f"   Action Required: Manual intervention needed to close position")

        # TODO: Send Telegram notification
        # send_telegram_alert(
        #     f"🚨 EXIT signal timeout for {strategy_id}/{instrument}\n"
        #     f"Entry order {pending_entry.get('signal_id')} still pending after {total_waited}s\n"
        #     f"Manual intervention required"
        # )

        return None

    except Exception as e:
        logger.error(f"❌ Error in wait_for_entry_fill: {e}")
        return None


# ============================================================================
# SLIPPAGE CALCULATION
# ============================================================================

def calculate_slippage(signal: Dict[str, Any]) -> float:
    """
    Calculate slippage based on time delay
    MVP implementation - simplified logic
    """
    signal_time = signal.get('timestamp')
    if isinstance(signal_time, datetime):
        delay_seconds = (datetime.utcnow() - signal_time).total_seconds()
    else:
        delay_seconds = 0

    # Simplified: assume 0.1% slippage per minute of delay
    slippage_pct = (delay_seconds / 60) * 0.001
    return slippage_pct


def check_slippage_rule(signal: Dict[str, Any]) -> bool:
    """
    Check if signal violates the 30% alpha slippage rule
    Returns True if signal should be accepted, False if should be dropped
    """
    slippage_pct = calculate_slippage(signal)
    expected_alpha = signal.get('metadata', {}).get('expected_alpha', 0)

    if expected_alpha <= 0:
        # No alpha data, accept signal
        return True

    alpha_lost_pct = slippage_pct / expected_alpha if expected_alpha > 0 else 0

    if alpha_lost_pct > MVP_CONFIG['slippage_alpha_threshold']:
        logger.warning(f"Signal {signal['signal_id']} dropped: {alpha_lost_pct:.1%} alpha lost to slippage")
        return False

    return True


# ============================================================================
# PORTFOLIO CONTEXT
# ============================================================================

def build_portfolio_context(account_state: Dict[str, Any]) -> PortfolioContext:
    """
    Build PortfolioContext from account state for live trading.
    Loads strategy histories from MongoDB (backtest data).
    """
    # Convert open positions to Position objects
    positions = []
    for pos_dict in account_state.get('open_positions', []):
        positions.append(Position(
            instrument=pos_dict.get('instrument'),
            quantity=pos_dict.get('quantity', 0),
            entry_price=pos_dict.get('entry_price', 0),
            current_price=pos_dict.get('current_price', 0),
            unrealized_pnl=pos_dict.get('unrealized_pnl', 0),
            margin_required=pos_dict.get('margin_required', 0),
            strategy_id=pos_dict.get('strategy_id')
        ))

    # Convert open orders to Order objects
    orders = []
    for order_dict in account_state.get('open_orders', []):
        orders.append(Order(
            order_id=order_dict.get('order_id'),
            instrument=order_dict.get('instrument'),
            side=order_dict.get('side'),
            quantity=order_dict.get('quantity', 0),
            order_type=order_dict.get('order_type'),
            price=order_dict.get('price', 0),
            strategy_id=order_dict.get('strategy_id')
        ))

    # Get current allocations
    with ALLOCATIONS_LOCK:
        current_allocations = dict(ACTIVE_ALLOCATIONS)

    # Load strategy histories from MongoDB (backtest data)
    strategy_histories = load_strategy_histories_from_mongodb()

    # Build context
    context = PortfolioContext(
        account_equity=account_state.get('equity', 0),
        margin_used=account_state.get('margin_used', 0),
        margin_available=account_state.get('margin_available', 0),
        cash_balance=account_state.get('cash_balance', 0),
        open_positions=positions,
        open_orders=orders,
        current_allocations=current_allocations,
        strategy_histories=strategy_histories,
        is_backtest=False,
        current_date=datetime.utcnow()
    )

    return context


def convert_signal_dict_to_object(signal_dict: Dict[str, Any]) -> Signal:
    """Convert signal dictionary to Signal object"""
    # Handle timestamp with 'Z' suffix
    timestamp_str = signal_dict.get('timestamp')

    # Validate timestamp exists
    if timestamp_str is None:
        raise ValueError(f"Signal {signal_dict.get('signal_id')} has no timestamp. Developer must provide a valid timestamp.")

    # Determine timestamp value
    if isinstance(timestamp_str, datetime):
        timestamp_value = timestamp_str
    elif isinstance(timestamp_str, str):
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'
        timestamp_value = datetime.fromisoformat(timestamp_str)
    else:
        raise ValueError(f"Signal {signal_dict.get('signal_id')} has invalid timestamp type: {type(timestamp_str)}. Must be datetime or ISO format string.")

    return Signal(
        signal_id=signal_dict.get('signal_id'),
        strategy_id=signal_dict.get('strategy_id'),
        timestamp=timestamp_value,
        instrument=signal_dict.get('instrument'),
        direction=signal_dict.get('direction'),
        action=signal_dict.get('action'),
        order_type=signal_dict.get('order_type'),
        price=signal_dict.get('price', 0),
        quantity=signal_dict.get('quantity', 0),
        stop_loss=signal_dict.get('stop_loss'),
        take_profit=signal_dict.get('take_profit'),
        expiry=signal_dict.get('expiry'),
        metadata=signal_dict.get('metadata', {})
    )


# ============================================================================
# DETAILED LOGGING
# ============================================================================

def log_detailed_calculation_math(signal: Dict[str, Any], context, decision_obj, account_state: Dict[str, Any]):
    """
    Log detailed calculation math to signal_processing.log only (not console).
    This provides full transparency into position sizing calculations.

    Args:
        signal: The incoming signal dictionary
        context: PortfolioContext object
        decision_obj: SignalDecision object with the final decision
        account_state: Account state dictionary
    """
    signal_id = signal.get('signal_id')
    strategy_id = signal.get('strategy_id')

    # Build detailed log message
    log_lines = []
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | ===== START CALCULATION BREAKDOWN =====")

    # Full signal payload
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- FULL SIGNAL PAYLOAD ---")
    signal_payload = {k: v for k, v in signal.items() if k not in ['_id']}  # Exclude MongoDB _id
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Raw Signal: {json.dumps(signal_payload, default=str)}")

    # Input data summary
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- INPUT DATA SUMMARY ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Strategy: {strategy_id}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Instrument: {signal.get('instrument')}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Direction: {signal.get('direction')}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Action: {signal.get('action')}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal Quantity: {signal.get('quantity', 0)}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal Price: ${signal.get('price', 0):,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal Account Equity: ${signal.get('account_equity', 0):,.2f}")

    # Signal type detection
    if decision_obj.metadata and 'signal_type_info' in decision_obj.metadata:
        st_info = decision_obj.metadata['signal_type_info']
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- SIGNAL TYPE DETECTION ---")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Detected Type: {st_info['signal_type']}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Detection Method: {st_info['method']}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Reasoning: {st_info['reasoning']}")

        # Show current position if exists
        if st_info.get('current_position'):
            pos = st_info['current_position']
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Current Position: {pos.get('quantity')} shares {pos.get('direction')} @ avg ${pos.get('avg_entry_price', 0):.2f}")
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Cost Basis: ${pos.get('total_cost_basis', 0):,.2f}")

    # Account state
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- ACCOUNT STATE ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Account Equity: ${account_state.get('equity', 0):,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Cash Balance: ${account_state.get('cash_balance', 0):,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Used: ${account_state.get('margin_used', 0):,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Available: ${account_state.get('margin_available', 0):,.2f}")
    if account_state.get('equity', 0) > 0:
        margin_pct = (account_state.get('margin_used', 0) / account_state.get('equity', 1)) * 100
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Used %: {margin_pct:.2f}%")

    # Portfolio context
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- PORTFOLIO CONTEXT ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Portfolio Equity: ${context.account_equity:,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Number of Active Allocations: {len(context.current_allocations) if context.current_allocations else 0}")

    # Strategy allocation
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- ALLOCATION CALCULATION ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Account Equity: ${context.account_equity:,.2f}")
    if decision_obj.metadata and 'allocation_pct' in decision_obj.metadata:
        allocation_pct = decision_obj.metadata.get('allocation_pct', 0)
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Strategy Allocation: {allocation_pct:.2f}%")

        # Show calculation
        if decision_obj.metadata and 'position_sizing' in decision_obj.metadata:
            allocated = decision_obj.metadata['position_sizing'].get('allocated_capital', decision_obj.allocated_capital)
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital: ${context.account_equity:,.2f} × {allocation_pct/100:.4f} = ${allocated:,.2f}")
        else:
            allocated_cap = decision_obj.allocated_capital if decision_obj.allocated_capital is not None else 0
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital: ${context.account_equity:,.2f} × {allocation_pct/100:.4f} = ${allocated_cap:,.2f}")

    # Position sizing details (if available)
    if decision_obj.metadata and 'position_sizing' in decision_obj.metadata:
        ps = decision_obj.metadata['position_sizing']

        # Deployed capital section
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- DEPLOYED CAPITAL ---")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Open Positions: {ps.get('position_count', 0)}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Deployed Capital: ${ps.get('deployed_capital', 0):,.2f}")
        allocated = ps.get('allocated_capital', 0)
        deployed = ps.get('deployed_capital', 0)
        available = ps.get('allocated_capital_available', allocated - deployed)
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital Available: ${allocated:,.2f} - ${deployed:,.2f} = ${available:,.2f}")

        # Ratio-based quantity section
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- RATIO-BASED QUANTITY ---")
        signal_qty = signal.get('quantity', 0)
        signal_equity = ps.get('signal_account_equity', 0)
        scaling_ratio = ps.get('scaling_ratio', 0)
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal: {signal_qty} units with ${signal_equity:,.2f} equity")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Scaling Ratio: ${available:,.2f} / ${signal_equity:,.2f} = {scaling_ratio:.5f}")
        calculated_qty = signal_qty * scaling_ratio
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Calculated Quantity: {signal_qty} × {scaling_ratio:.5f} = {calculated_qty:.4f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Normalized Quantity: {decision_obj.quantity}")

        # Show current open positions for this strategy
        if ps.get('position_count', 0) > 0:
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- CURRENT OPEN POSITIONS ({ps['position_count']}) ---")
            for idx, pos_summary in enumerate(ps.get('open_positions_summary', []), 1):
                cost_basis = pos_summary.get('cost_basis') or 0
                log_lines.append(
                    f"SIGNAL: {signal_id} | DETAILED_MATH | Position {idx}: {pos_summary.get('quantity', 0)} units "
                    f"{pos_summary.get('instrument', 'N/A')} {pos_summary.get('direction', 'N/A')} (cost: ${cost_basis:,.2f})"
                )

    # Margin validation section
    if decision_obj.metadata and 'position_sizing' in decision_obj.metadata:
        ps = decision_obj.metadata['position_sizing']
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- MARGIN VALIDATION ---")

        margin_required = ps.get('margin_required', decision_obj.margin_required)
        available = ps.get('allocated_capital_available', 0)
        notional = ps.get('notional_value', 0)
        margin_method = ps.get('margin_method', 'Broker query')

        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Required: ${margin_required:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital Available: ${available:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Notional Value: ${notional:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Method: {margin_method}")

        # Show margin check result
        if margin_required > available:
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Check: ${margin_required:,.2f} > ${available:,.2f} = EXCEEDS")
        else:
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Check: ${margin_required:,.2f} < ${available:,.2f} = OK")
    elif decision_obj.margin_required:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- MARGIN VALIDATION ---")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital: ${decision_obj.allocated_capital:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Required: ${decision_obj.margin_required:,.2f}")

    # Final decision
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- FINAL DECISION ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Decision: {decision_obj.action}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Original Quantity: {signal.get('quantity', 0)}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Final Quantity: {decision_obj.quantity}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Reason: {decision_obj.reason}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | ===== END CALCULATION BREAKDOWN =====")

    # Log all lines to signal_processing.log (will be filtered by handler)
    for line in log_lines:
        logger.info(line)


# ============================================================================
# SIGNAL PROCESSING
# ============================================================================

def process_signal_with_constructor(signal: Dict[str, Any]):
    """
    Process signal using Portfolio Constructor (NEW APPROACH)
    """
    signal_id = signal.get('signal_id')
    signal_store_id = signal.get('mathematricks_signal_id')  # Extract from Pub/Sub message (mongodb_watcher created this)

    # Initialize signal processing logger on first signal
    signal_logger = get_signal_processing_logger()

    signal_logger.info(f"Processing signal {signal_id} with Portfolio Constructor")
    if signal_store_id:
        logger.info(f"📍 Mathematricks Signal ID: {signal_store_id}")

    # Unified signal processing log
    signal_logger.info(f"SIGNAL: {signal_id} | PROCESSING | Strategy={signal.get('strategy_id')} | Instrument={signal.get('instrument')} | Action={signal.get('action')}")

    # Step 1: Check slippage rule (keep existing logic)
    if signal.get('action') == 'ENTRY' and not check_slippage_rule(signal):
        decision = {
            "signal_id": signal_id,
            "decision": "REJECTED",
            "timestamp": datetime.utcnow(),
            "reason": "SLIPPAGE_EXCEEDED",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "risk_assessment": {},
            "created_at": datetime.utcnow()
        }
        # Write decision to signal_store (embedded)
        update_signal_store_with_decision(signal_store_id, decision)
        logger.info(f"Signal {signal_id} rejected due to slippage")
        return

    # Step 2: Get strategy document and determine account routing
    strategy_id = signal.get('strategy_id')
    strategy_doc = get_strategy_document(strategy_id)

    if not strategy_doc:
        logger.error(f"Strategy {strategy_id} not found - rejecting signal")
        decision = {
            "signal_id": signal_id,
            "decision": "REJECTED",
            "timestamp": datetime.utcnow(),
            "reason": "STRATEGY_NOT_FOUND",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "risk_assessment": {},
            "created_at": datetime.utcnow()
        }
        update_signal_store_with_decision(signal_store_id, decision)
        return

    # Get account(s) from strategy document
    accounts = strategy_doc.get('accounts', [])

    if not accounts or len(accounts) == 0:
        logger.error(f"Strategy {strategy_id} has no accounts configured - rejecting signal")
        decision = {
            "signal_id": signal_id,
            "decision": "REJECTED",
            "timestamp": datetime.utcnow(),
            "reason": "NO_ACCOUNTS_CONFIGURED",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "risk_assessment": {},
            "created_at": datetime.utcnow()
        }
        update_signal_store_with_decision(signal_store_id, decision)
        return

    # For single-account strategies: use accounts[0]
    # For multi-account strategies (future): implement distribution logic
    account_name = accounts[0]
    logger.info(f"Routing signal for strategy {strategy_id} to account: {account_name}")

    account_state = get_account_state(account_name)

    if not account_state:
        logger.error(f"Failed to get account state for {account_name}")
        decision = {
            "signal_id": signal_id,
            "decision": "REJECTED",
            "timestamp": datetime.utcnow(),
            "reason": "ACCOUNT_STATE_UNAVAILABLE",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "risk_assessment": {},
            "created_at": datetime.utcnow()
        }
        # Write decision to signal_store (embedded)
        update_signal_store_with_decision(signal_store_id, decision)
        return

    # Step 3: Build context and convert signal
    context = build_portfolio_context(account_state)
    signal_obj = convert_signal_dict_to_object(signal)

    # Step 4: Get portfolio constructor and evaluate signal
    constructor = initialize_portfolio_constructor()
    decision_obj: SignalDecision = constructor.evaluate_signal(signal_obj, context)

    # Step 4.0: Extract legs for multi-leg processing
    # If 'legs' is provided, use all legs; otherwise create single-leg array from primary signal
    legs = signal.get('legs')
    if legs and len(legs) > 1:
        is_multi_leg = True
        logger.info(f"🔀 Multi-leg signal detected: {len(legs)} legs")
        for i, leg in enumerate(legs):
            logger.info(f"   Leg {i+1}: {leg.get('instrument')} {leg.get('action')} {leg.get('direction')}")
    else:
        is_multi_leg = False
        # Create single-leg array from primary signal fields
        legs = [{
            'instrument': signal.get('instrument'),
            'instrument_type': signal.get('instrument_type', 'STOCK'),
            'direction': signal.get('direction'),
            'action': signal.get('action'),
            'order_type': signal.get('order_type'),
            'price': signal.get('price'),
            'quantity': signal.get('quantity'),
            'environment': signal.get('environment', 'staging')
        }]

    # Step 4a: Determine Signal Type (ENTRY/EXIT/SCALE)
    signal_type_info = position_manager.determine_signal_type(signal)

    # Step 4a.1: CANCEL SIGNAL HANDLING - Cancel pending orders
    signal_type = signal_type_info.get('signal_type')
    if signal_type == 'CANCEL':
        logger.info(f"🚫 CANCEL signal received - cancelling pending orders")

        strategy_id = signal.get('strategy_id')
        instrument = signal.get('instrument')
        entry_signal_id = signal.get('entry_signal_id')

        # Query trading_orders collection for pending orders to cancel
        # Look for orders that are PENDING, SUBMITTED, or PRESUBMITTED (not yet filled)
        query = {
            'strategy_id': strategy_id,
            'instrument': instrument,
            'status': {'$in': ['PENDING', 'SUBMITTED', 'PRESUBMITTED', 'PreSubmitted']}
        }

        pending_orders = list(trading_orders_collection.find(query).sort('created_at', -1).limit(10))

        if not pending_orders:
            logger.warning(f"⚠️ No pending orders found to cancel for {strategy_id}/{instrument}")
            # Update signal store with CANCEL status
            if signal_store_id:
                from bson import ObjectId
                signal_store_collection.update_one(
                    {'_id': ObjectId(signal_store_id)},
                    {'$set': {
                        'cerebro_decision': {
                            'action': 'CANCEL_NO_TARGET',
                            'timestamp': datetime.utcnow(),
                            'message': f'No pending orders found to cancel for {instrument}'
                        },
                        'status': 'processed'
                    }}
                )
            return

        # Cancel all matching pending orders
        cancelled_count = 0
        for order in pending_orders:
            order_id = order.get('order_id')
            logger.info(f"🚫 Cancelling order: {order_id}")

            success = publish_cancel_command(
                order_id,
                reason=f"CANCEL signal received for {instrument}"
            )

            if success:
                cancelled_count += 1
                # Update order status in MongoDB to 'CANCEL_REQUESTED'
                trading_orders_collection.update_one(
                    {'order_id': order_id},
                    {'$set': {
                        'status': 'CANCEL_REQUESTED',
                        'cancel_requested_at': datetime.utcnow(),
                        'cancel_reason': 'CANCEL signal received'
                    }}
                )

        # Update signal store with CANCEL result
        if signal_store_id:
            from bson import ObjectId
            signal_store_collection.update_one(
                {'_id': ObjectId(signal_store_id)},
                {'$set': {
                    'cerebro_decision': {
                        'action': 'CANCEL_SENT',
                        'timestamp': datetime.utcnow(),
                        'cancelled_orders': cancelled_count,
                        'message': f'Sent cancel commands for {cancelled_count} pending order(s)'
                    },
                    'status': 'processed'
                }}
            )

        logger.info(f"✅ CANCEL signal processed - cancelled {cancelled_count} order(s)")
        return  # Don't process CANCEL signal as a new order

    # Step 4a.2: Check for pending ENTRY orders if this is an EXIT signal
    # DISABLED: We now use retry logic to wait for entry fills instead of canceling
    # check_and_cancel_pending_entry(signal, signal_type_info)

    # Step 4a.3: EXIT SIGNAL HANDLING - Query signal_store for exact entry quantity
    if signal_type in ['EXIT', 'SCALE_OUT'] and decision_obj.action in ['APPROVE', 'RESIZE']:
        logger.info(f"🔴 EXIT signal detected - querying signal_store for entry quantity")

        # PRIORITY 1: Check if EXIT signal explicitly provides entry_signal_id
        entry_signal_id = signal.get('entry_signal_id')
        entry_signal = None

        if entry_signal_id and entry_signal_id != "$PREVIOUS":
            # Direct lookup by ObjectId - most reliable method
            logger.info(f"✅ EXIT signal has entry_signal_id - using direct lookup: {entry_signal_id[:12]}...")
            try:
                from bson import ObjectId
                entry_signal = signal_store_collection.find_one({"_id": ObjectId(entry_signal_id)})
                if entry_signal:
                    logger.info(f"✅ Found exact entry signal by ID: {entry_signal.get('signal_id')}")
                else:
                    logger.warning(f"⚠️ entry_signal_id provided but signal not found: {entry_signal_id}")
            except Exception as e:
                logger.error(f"❌ Error looking up entry_signal_id {entry_signal_id}: {e}")

        # PRIORITY 2: Fallback to fuzzy matching if no entry_signal_id provided or lookup failed
        if not entry_signal:
            logger.info("Using fuzzy matching to find ENTRY signal (strategy/instrument/direction)")
            entry_signal = find_open_entry_signal(
                strategy_id=signal.get('strategy_id'),
                instrument=signal.get('instrument'),
                direction=signal.get('direction')  # EXIT direction (we'll find opposite)
            )

            # If entry not found immediately, wait for it to fill (with retry logic)
            if not entry_signal:
                logger.warning(f"⚠️ Entry not filled yet - initiating retry logic")
                entry_signal = wait_for_entry_fill(
                    strategy_id=signal.get('strategy_id'),
                    instrument=signal.get('instrument'),
                    direction=signal.get('direction'),
                    max_wait=30
                )

        if entry_signal and entry_signal.get('execution') and entry_signal['execution'].get('quantity_filled'):
            # Found entry signal with execution data - use exact quantity
            entry_quantity_filled = entry_signal['execution']['quantity_filled']

            logger.info(f"✅ Found entry signal: {entry_signal['signal_id']}")
            logger.info(f"✅ Entry quantity filled: {entry_quantity_filled}")

            # For multi-leg EXIT signals, query entry's leg_results for exact quantities
            exit_leg_results = []
            if is_multi_leg and legs:
                logger.info(f"🔀 Multi-leg EXIT signal: Processing {len(legs)} legs")

                # Get leg_results from entry signal's cerebro_decision
                entry_leg_results = entry_signal.get('cerebro_decision', {}).get('risk_assessment', {}).get('metadata', {}).get('leg_results', [])

                if entry_leg_results:
                    logger.info(f"✅ Found entry leg_results with {len(entry_leg_results)} legs")
                else:
                    logger.warning(f"⚠️ Entry signal missing leg_results - will use EXIT signal quantities")

                for leg_index, leg in enumerate(legs):
                    instrument = leg.get('instrument')
                    leg_instrument_type = leg.get('instrument_type', 'STOCK')

                    # Find matching entry leg by instrument to get the actual filled quantity
                    if entry_leg_results:
                        entry_leg = next((el for el in entry_leg_results if el.get('instrument') == instrument), None)
                        if entry_leg:
                            leg_quantity = entry_leg.get('quantity', 0)
                            logger.info(f"   Leg {leg_index+1}: {instrument} - using entry qty={leg_quantity}")
                        else:
                            # Instrument not found in entry - use EXIT signal quantity as fallback
                            leg_quantity = leg.get('quantity', 0)
                            logger.warning(f"   Leg {leg_index+1}: {instrument} - no entry match, using EXIT qty={leg_quantity}")
                    else:
                        # No entry leg_results - use EXIT signal quantity
                        leg_quantity = leg.get('quantity', 0)
                        logger.info(f"   Leg {leg_index+1}: {instrument} - using EXIT qty={leg_quantity}")

                    # Normalize to broker precision
                    precision = precision_service.get_precision(
                        broker=broker_adapter,
                        broker_id=account_name,
                        symbol=instrument,
                        instrument_type=leg_instrument_type
                    )
                    normalized_quantity = precision_service.normalize_quantity(leg_quantity, precision)

                    exit_leg_results.append({
                        'leg_index': leg_index,
                        'instrument': instrument,
                        'instrument_type': leg_instrument_type,
                        'direction': leg.get('direction'),
                        'action': leg.get('action'),
                        'order_type': leg.get('order_type', 'MARKET'),
                        'quantity': normalized_quantity,
                        'price_used': leg.get('price', 0)
                    })
                    logger.info(f"   EXIT Leg {leg_index+1}: {instrument} {leg.get('action')} qty={normalized_quantity}")

                # Use primary leg quantity for decision (backward compatibility)
                exact_quantity = exit_leg_results[0]['quantity'] if exit_leg_results else entry_quantity_filled
            else:
                # Single-leg EXIT - use the entry's filled quantity
                exact_quantity = entry_quantity_filled

            # Create new decision with exact quantity (no margin calculator)
            exit_metadata = {
                **decision_obj.metadata,
                'signal_type_info': signal_type_info,
                'entry_signal_id': str(entry_signal['_id']),
                'entry_signal_ref': entry_signal['signal_id'],
                'entry_quantity': entry_quantity_filled,
                'exit_type': 'FULL_EXIT' if signal_type == 'EXIT' else 'PARTIAL_EXIT',
                'is_multi_leg': is_multi_leg,
                'leg_count': len(legs) if is_multi_leg else 1
            }

            # Add leg_results for multi-leg EXIT
            if exit_leg_results:
                exit_metadata['leg_results'] = exit_leg_results

            decision_obj = SignalDecision(
                action="APPROVE",
                quantity=exact_quantity,
                reason=f"EXIT: Closing position from entry signal {entry_signal['signal_id']}" + (f" ({len(legs)} legs)" if is_multi_leg else ""),
                allocated_capital=0,
                margin_required=0,
                metadata=exit_metadata
            )

            # Skip margin calculator - jump to decision logging
            logger.info(f"⏭️ Skipping margin calculator for EXIT signal")

        else:
            # Timeout or no entry found after retry - reject with critical error
            logger.critical(f"🚨 CRITICAL: EXIT signal REJECTED - No filled entry found after retry")
            logger.critical(f"   Strategy: {signal.get('strategy_id')}")
            logger.critical(f"   Instrument: {signal.get('instrument')}")
            logger.critical(f"   This indicates a serious issue - manual intervention required")

            decision_obj = SignalDecision(
                action="REJECTED",
                quantity=0,
                reason=f"No open position found in signal_store for {signal.get('strategy_id')}/{signal.get('instrument')} after 30s retry",
                allocated_capital=0,
                margin_required=0,
                metadata={
                    **decision_obj.metadata,
                    'signal_type_info': signal_type_info,
                    'rejection_reason': 'no_open_position_found_after_retry',
                    'retry_attempted': True
                }
            )

    # Step 4b: Smart Position Sizing - Adjust for capital distribution (ENTRY signals only)
    elif decision_obj.action in ['APPROVE', 'RESIZE']:
        strategy_id = signal.get('strategy_id')

        # Get strategy metadata for backtest margin comparison
        strategy_meta = get_strategy_metadata(strategy_id)
        median_margin_pct = strategy_meta['median_margin_pct']

        # RATIO-BASED POSITION SIZING
        # Calculate position capital based on signal's sizing intent
        signal_account_equity = signal.get('account_equity')

        # Calculate signal's position value from first leg
        if legs and len(legs) > 0:
            signal_price = legs[0].get('price', 0)
            signal_quantity = legs[0].get('quantity', 1)
        else:
            signal_price = signal.get('price', 0)
            signal_quantity = signal.get('quantity', 1)
        signal_position_value = signal_price * signal_quantity

        # Validate required fields for ratio-based sizing
        if not signal_account_equity or signal_account_equity <= 0:
            logger.error(f"❌ Missing or invalid account_equity in signal: {signal_account_equity}")
            decision_obj = SignalDecision(
                action="REJECTED",
                quantity=0,
                reason=f"Missing required field 'account_equity' for position sizing",
                allocated_capital=decision_obj.allocated_capital,
                margin_required=0.0,
                metadata={
                    **decision_obj.metadata,
                    'signal_type_info': signal_type_info,
                    'rejection_reason': 'missing_account_equity'
                }
            )
            # Log and update signal store for rejected signal
            log_detailed_calculation_math(signal, context, decision_obj, account_state)
            logger.info(f"\n{'='*70}")
            logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {signal.get('instrument')}")
            logger.info(f"{'='*70}")
            logger.info(f"Strategy: {signal.get('strategy_id')}")
            logger.info(f"Action: {decision_obj.action}")
            logger.info(f"Reason: {decision_obj.reason}")
            logger.info(f"{'='*70}\n")
            update_signal_store_with_decision(signal_store_id, {
                "signal_id": signal_id,
                "strategy_id": signal.get('strategy_id'),
                "decision": decision_obj.action,
                "timestamp": datetime.utcnow(),
                "reason": decision_obj.reason,
                "original_quantity": signal.get('quantity', 0),
                "final_quantity": 0,
                "environment": signal.get('environment', 'staging'),
                "risk_assessment": {
                    "allocated_capital": decision_obj.allocated_capital,
                    "margin_required": 0,
                    "metadata": decision_obj.metadata
                },
                "created_at": datetime.utcnow()
            })
            return  # Exit early

        if signal_position_value <= 0:
            logger.error(f"❌ Invalid signal position value: price={signal_price}, qty={signal_quantity}")
            decision_obj = SignalDecision(
                action="REJECTED",
                quantity=0,
                reason=f"Invalid signal position value (price={signal_price}, quantity={signal_quantity})",
                allocated_capital=decision_obj.allocated_capital,
                margin_required=0.0,
                metadata={
                    **decision_obj.metadata,
                    'signal_type_info': signal_type_info,
                    'rejection_reason': 'invalid_position_value'
                }
            )
            # Log and update signal store for rejected signal
            log_detailed_calculation_math(signal, context, decision_obj, account_state)
            logger.info(f"\n{'='*70}")
            logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {signal.get('instrument')}")
            logger.info(f"{'='*70}")
            logger.info(f"Strategy: {signal.get('strategy_id')}")
            logger.info(f"Action: {decision_obj.action}")
            logger.info(f"Reason: {decision_obj.reason}")
            logger.info(f"{'='*70}\n")
            update_signal_store_with_decision(signal_store_id, {
                "signal_id": signal_id,
                "strategy_id": signal.get('strategy_id'),
                "decision": decision_obj.action,
                "timestamp": datetime.utcnow(),
                "reason": decision_obj.reason,
                "original_quantity": signal.get('quantity', 0),
                "final_quantity": 0,
                "environment": signal.get('environment', 'staging'),
                "risk_assessment": {
                    "allocated_capital": decision_obj.allocated_capital,
                    "margin_required": 0,
                    "metadata": decision_obj.metadata
                },
                "created_at": datetime.utcnow()
            })
            return  # Exit early

        # Get allocated capital and deployed capital
        allocated_capital = decision_obj.allocated_capital
        deployment_info = get_deployed_capital(strategy_id)
        deployed_capital = deployment_info['deployed_capital']
        open_positions = deployment_info['open_positions']
        position_count = deployment_info['position_count']

        # Calculate available capital
        allocated_capital_available = allocated_capital - deployed_capital

        # Calculate scaling ratio for quantity
        scaling_ratio = allocated_capital_available / signal_account_equity

        logger.info(f"📊 Allocation: ${allocated_capital:,.2f} - ${deployed_capital:,.2f} deployed = ${allocated_capital_available:,.2f} available")
        logger.info(f"📊 Scaling ratio: ${allocated_capital_available:,.2f} / ${signal_account_equity:,.2f} = {scaling_ratio:.5f}")

        # Check if we have capital available
        if allocated_capital_available <= 0:
            # No capital left - reject signal
            decision_obj = SignalDecision(
                action="REJECTED",
                quantity=0,
                reason=f"No capital available (deployed ${deployed_capital:,.2f} of ${allocated_capital:,.2f})",
                allocated_capital=allocated_capital,
                margin_required=0.0,
                metadata={
                    **decision_obj.metadata,
                    'signal_type_info': signal_type_info,
                    'allocated_capital': allocated_capital,
                    'deployed_capital': deployed_capital,
                    'allocated_capital_available': allocated_capital_available,
                    'position_count': position_count,
                    'rejection_reason': 'fully_deployed'
                }
            )
        else:
            # RATIO-BASED POSITION SIZING WITH MARGIN VALIDATION
            # Calculate quantity from signal's ratio, then validate margin fits

            try:
                # Step 1: Calculate ratio-based quantity for each leg and fetch margin
                leg_results = []
                total_margin_required = 0.0
                total_notional = 0.0

                for leg_index, leg in enumerate(legs):
                    # Validate instrument_type exists for this leg
                    leg_instrument_type = leg.get('instrument_type', 'STOCK')
                    if not leg_instrument_type:
                        raise ValueError(
                            f"Leg {leg_index+1} missing required field 'instrument_type'. "
                            "Valid values: STOCK, ETF, FOREX, OPTION, FUTURE, CRYPTO"
                        )

                    # SIMPLE RATIO SCALING
                    # quantity = signal_qty × scaling_ratio
                    signal_leg_quantity = leg.get('quantity', 0)
                    if signal_leg_quantity <= 0:
                        raise ValueError(f"Leg {leg_index+1} has invalid quantity: {signal_leg_quantity}")

                    # Calculate quantity using simple scaling ratio
                    ratio_based_quantity = signal_leg_quantity * scaling_ratio

                    logger.info(f"📊 Leg {leg_index+1} quantity: {signal_leg_quantity} × {scaling_ratio:.5f} = {ratio_based_quantity:.4f}")

                    # Create signal dict for this leg (merge with parent signal metadata)
                    leg_signal = {
                        **signal,  # Inherit strategy_id, signal_id, etc.
                        'instrument': leg.get('instrument'),
                        'instrument_type': leg_instrument_type,
                        'direction': leg.get('direction'),
                        'action': leg.get('action'),
                        'order_type': leg.get('order_type', 'MARKET'),
                        'price': leg.get('price', 0),
                        'quantity': leg.get('quantity', 0),
                        'signal_price': leg.get('price', 0)
                    }

                    # Create appropriate margin calculator for this leg
                    calculator = MarginCalculatorFactory.create_calculator(leg_signal, broker_adapter)

                    # Fetch current price from broker
                    price_data = calculator.fetch_current_price(leg.get('instrument'), signal=leg_signal)
                    price_used = price_data['price']

                    # Normalize quantity to broker precision
                    precision = precision_service.get_precision(
                        broker=broker_adapter,
                        broker_id=account_name,
                        symbol=leg.get('instrument'),
                        instrument_type=leg_instrument_type
                    )
                    normalized_quantity = precision_service.normalize_quantity(ratio_based_quantity, precision)

                    # Fetch margin requirement for this exact quantity
                    margin_data = calculator.fetch_margin_requirement(
                        ticker=leg.get('instrument'),
                        quantity=normalized_quantity,
                        price=price_used,
                        signal_data=leg_signal
                    )

                    # Calculate notional value
                    notional_value = normalized_quantity * price_used

                    leg_results.append({
                        'leg_index': leg_index,
                        'instrument': leg.get('instrument'),
                        'instrument_type': leg_instrument_type,
                        'direction': leg.get('direction'),
                        'action': leg.get('action'),
                        'order_type': leg.get('order_type', 'MARKET'),
                        'quantity_raw': ratio_based_quantity,
                        'quantity': normalized_quantity,
                        'precision': precision,
                        'price_used': price_used,
                        'initial_margin': margin_data['initial_margin'],
                        'margin_pct': margin_data.get('margin_pct', 0),
                        'notional_value': notional_value,
                        'calculation_method': margin_data.get('calculation_method', 'Ratio-based with broker margin')
                    })

                    total_margin_required += margin_data['initial_margin']
                    total_notional += notional_value

                    logger.info(f"✅ Leg {leg_index+1}/{len(legs)}: {leg.get('instrument')} | Qty={normalized_quantity} | Price=${price_used:.2f} | Margin=${margin_data['initial_margin']:,.2f}")

                # Step 2: Check if total margin exceeds available capital - REJECT if so
                if total_margin_required > allocated_capital_available:
                    logger.error(f"❌ Total margin ${total_margin_required:,.2f} > allocated capital available ${allocated_capital_available:,.2f}")
                    logger.error(f"❌ Rejecting signal - margin exceeds available capital")

                    decision_obj = SignalDecision(
                        action="REJECTED",
                        quantity=0,
                        reason=f"Margin ${total_margin_required:,.2f} exceeds allocated capital available ${allocated_capital_available:,.2f}",
                        allocated_capital=allocated_capital,
                        margin_required=total_margin_required,
                        metadata={
                            **decision_obj.metadata,
                            'signal_type_info': signal_type_info,
                            'rejection_reason': 'margin_exceeds_capital',
                            'allocated_capital': allocated_capital,
                            'deployed_capital': deployed_capital,
                            'allocated_capital_available': allocated_capital_available,
                            'margin_required': total_margin_required,
                            'calculated_quantities': [lr['quantity'] for lr in leg_results]
                        }
                    )
                    # Log and update signal store for rejected signal
                    log_detailed_calculation_math(signal, context, decision_obj, account_state)
                    logger.info(f"\n{'='*70}")
                    logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {signal.get('instrument')}")
                    logger.info(f"{'='*70}")
                    logger.info(f"Strategy: {signal.get('strategy_id')}")
                    logger.info(f"Action: {decision_obj.action}")
                    logger.info(f"Reason: {decision_obj.reason}")
                    logger.info(f"{'='*70}\n")
                    update_signal_store_with_decision(signal_store_id, {
                        "signal_id": signal_id,
                        "strategy_id": signal.get('strategy_id'),
                        "decision": decision_obj.action,
                        "timestamp": datetime.utcnow(),
                        "reason": decision_obj.reason,
                        "original_quantity": signal.get('quantity', 0),
                        "final_quantity": 0,
                        "environment": signal.get('environment', 'staging'),
                        "risk_assessment": {
                            "allocated_capital": allocated_capital,
                            "allocated_capital_available": allocated_capital_available,
                            "margin_required": total_margin_required,
                            "metadata": decision_obj.metadata
                        },
                        "created_at": datetime.utcnow()
                    })
                    return  # Exit early

                # Log multi-leg summary
                if is_multi_leg:
                    logger.info(f"🔀 Multi-leg summary: {len(legs)} legs | Total Margin: ${total_margin_required:,.2f} | Total Notional: ${total_notional:,.2f}")

                # Calculate backtest margin for comparison
                backtest_margin = allocated_capital_available * median_margin_pct

                # For decision object, use primary leg quantity (for backward compatibility)
                # Actual orders will use leg_results
                primary_leg_result = leg_results[0]
                adjusted_shares = primary_leg_result['quantity']
                price_used = primary_leg_result['price_used']
                ibkr_margin_info = {
                    'estimated_margin': total_margin_required,
                    'margin_pct': (total_margin_required / total_notional * 100) if total_notional > 0 else 0,
                    'calculation_method': 'multi_leg' if is_multi_leg else primary_leg_result['calculation_method'],
                    'notional_value': total_notional
                }

                logger.info(f"✅ Margin ${total_margin_required:,.2f} < allocated capital available ${allocated_capital_available:,.2f} - APPROVED")

            except Exception as e:
                # Margin calculation failed - REJECT signal
                logger.error(f"❌ Margin calculation failed: {e}")
                decision_obj = SignalDecision(
                    action="REJECTED",
                    quantity=0,
                    reason=f"Margin calculation failed: {str(e)}",
                    allocated_capital=decision_obj.allocated_capital,
                    margin_required=0.0,
                    metadata={
                        **decision_obj.metadata,
                        'signal_type_info': signal_type_info,
                        'rejection_reason': 'margin_calculation_failed',
                        'error': str(e)
                    }
                )
                # Skip to decision logging
                log_detailed_calculation_math(signal, context, decision_obj, account_state)
                logger.info(f"\n{'='*70}")
                logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {signal.get('instrument')}")
                logger.info(f"{'='*70}")
                logger.info(f"Strategy: {signal.get('strategy_id')}")
                logger.info(f"Action: {decision_obj.action}")
                logger.info(f"Reason: {decision_obj.reason}")
                logger.info(f"{'='*70}\n")
                update_signal_store_with_decision(signal_store_id, {
                    "signal_id": signal_id,
                    "strategy_id": signal.get('strategy_id'),
                    "decision": decision_obj.action,
                    "timestamp": datetime.utcnow(),
                    "reason": decision_obj.reason,
                    "original_quantity": signal.get('quantity', 0),
                    "final_quantity": 0,
                    "environment": signal.get('environment', 'staging'),
                    "risk_assessment": {
                        "allocated_capital": decision_obj.allocated_capital,
                        "margin_required": 0,
                        "metadata": decision_obj.metadata
                    },
                    "created_at": datetime.utcnow()
                })
                return  # Exit early

            # Update decision with adjusted values
            decision_obj = SignalDecision(
                action=decision_obj.action,
                quantity=adjusted_shares,
                reason=f"{decision_obj.reason} | {signal_type_info['signal_type']} | Scaling: {scaling_ratio:.5f}" + (f" | Multi-leg: {len(legs)}" if is_multi_leg else ""),
                allocated_capital=allocated_capital_available,
                margin_required=ibkr_margin_info['estimated_margin'],
                metadata={
                    **decision_obj.metadata,
                    'signal_type_info': signal_type_info,
                    'is_multi_leg': is_multi_leg,
                    'leg_count': len(legs),
                    'leg_results': leg_results,
                    'position_sizing': {
                        'allocated_capital': allocated_capital,
                        'deployed_capital': deployed_capital,
                        'allocated_capital_available': allocated_capital_available,
                        'signal_account_equity': signal_account_equity,
                        'scaling_ratio': scaling_ratio,
                        'position_count': position_count,
                        'open_positions_summary': [
                            {
                                'instrument': p.get('instrument'),
                                'direction': p.get('direction'),
                                'quantity': p.get('quantity'),
                                'cost_basis': p.get('total_cost_basis')
                            } for p in open_positions
                        ],
                        # Backtest margin (historical)
                        'backtest_margin': backtest_margin,
                        'backtest_margin_pct': median_margin_pct * 100,
                        # Broker margin
                        'margin_required': ibkr_margin_info['estimated_margin'],
                        'margin_pct': ibkr_margin_info['margin_pct'],
                        'margin_method': ibkr_margin_info['calculation_method'],
                        'notional_value': ibkr_margin_info['notional_value'],
                        'price_used': price_used
                    }
                }
            )

    # Log detailed calculation math to signal_processing.log (not console)
    log_detailed_calculation_math(signal, context, decision_obj, account_state)

    # Log decision summary to console and cerebro_service.log
    logger.info(f"\n{'='*70}")
    logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {signal.get('instrument')}")
    logger.info(f"{'='*70}")
    logger.info(f"Strategy: {signal.get('strategy_id')}")
    logger.info(f"Action: {decision_obj.action}")
    logger.info(f"Quantity: {decision_obj.quantity:.2f}")
    logger.info(f"Reason: {decision_obj.reason}")
    if decision_obj.allocated_capital:
        logger.info(f"Allocated Capital: ${decision_obj.allocated_capital:,.2f}")
    if decision_obj.margin_required:
        logger.info(f"Margin Required: ${decision_obj.margin_required:,.2f}")
    logger.info(f"{'='*70}")

    # Step 5: Save decision to MongoDB
    decision_doc = {
        "signal_id": signal_id,
        "strategy_id": signal.get('strategy_id'),
        "decision": decision_obj.action,  # "APPROVE", "REJECT", "RESIZE"
        "timestamp": datetime.utcnow(),
        "reason": decision_obj.reason,
        "original_quantity": signal.get('quantity', 0),
        "final_quantity": decision_obj.quantity,
        "environment": signal.get('environment', 'staging'),
        "risk_assessment": {
            "allocated_capital": decision_obj.allocated_capital,
            "margin_required": decision_obj.margin_required,
            "metadata": decision_obj.metadata
        },
        "created_at": datetime.utcnow()
    }

    # For EXIT signals, add entry reference at top level for easier querying
    if decision_obj.metadata.get('entry_signal_id'):
        decision_doc['entry_signal_id'] = decision_obj.metadata['entry_signal_id']
        decision_doc['entry_signal_ref'] = decision_obj.metadata.get('entry_signal_ref')

    # Write decision to signal_store (embedded)
    update_signal_store_with_decision(signal_store_id, decision_doc)

    # Unified signal processing log for decision
    logger.info(f"SIGNAL: {signal_id} | DECISION | Action={decision_obj.action} | OrigQty={signal.get('quantity', 0)} | FinalQty={decision_obj.quantity} | Reason={decision_obj.reason}")

    # Step 6: If approved or resized, create trading orders for each leg
    if decision_obj.action in ['APPROVE', 'RESIZE']:
        # Get leg_results from metadata (for ENTRY signals with multi-leg calculation)
        # For EXIT signals or single-leg, fall back to creating from primary signal
        leg_results = decision_obj.metadata.get('leg_results', [])

        if not leg_results:
            # No leg_results (EXIT signal or legacy) - create single order from primary signal
            instrument_type = signal.get('instrument_type', 'STOCK')
            final_quantity_rounded = round_quantity_for_instrument(decision_obj.quantity, instrument_type)
            if final_quantity_rounded <= 0:
                logger.warning(f"Rounded quantity is 0, rejecting signal")
                return

            leg_results = [{
                'leg_index': 0,
                'instrument': signal.get('instrument'),
                'instrument_type': instrument_type,
                'direction': signal.get('direction'),
                'action': signal.get('action'),
                'order_type': signal.get('order_type', 'MARKET'),
                'quantity': final_quantity_rounded,
                'price_used': signal.get('price', 0)
            }]

        # Create orders for each leg
        orders_created = []
        for leg_result in leg_results:
            leg_index = leg_result.get('leg_index', 0)
            leg_instrument_type = leg_result.get('instrument_type', 'STOCK')
            leg_quantity = round_quantity_for_instrument(leg_result.get('quantity', 0), leg_instrument_type)

            if leg_quantity <= 0:
                logger.warning(f"Leg {leg_index+1} quantity is 0, skipping")
                continue

            # Generate unique order ID for each leg
            if len(leg_results) > 1:
                order_id = f"{signal_id}_LEG{leg_index}_ORD"
            else:
                order_id = f"{signal_id}_ORD"

            trading_order = {
                "order_id": order_id,
                "signal_id": signal_id,
                "mathematricks_signal_id": signal_store_id,  # For execution_service to update signal_store
                "strategy_id": signal.get('strategy_id'),
                "account": account_name,
                "timestamp": datetime.utcnow(),
                "instrument": leg_result.get('instrument'),
                "direction": leg_result.get('direction'),
                "action": leg_result.get('action'),
                "signal_type": signal.get('signal_type'),  # ENTRY or EXIT (for execution service)
                "order_type": leg_result.get('order_type', 'MARKET'),
                "price": leg_result.get('price_used', 0),
                "quantity": leg_quantity,
                "stop_loss": signal.get('stop_loss'),
                "take_profit": signal.get('take_profit'),
                "expiry": signal.get('expiry'),
                # Multi-asset support: pass through instrument_type and related fields
                "instrument_type": leg_result.get('instrument_type', 'STOCK'),
                "underlying": signal.get('underlying'),  # For options
                "exchange": signal.get('exchange'),  # For futures
                # Multi-leg metadata
                "leg_index": leg_index,
                "total_legs": len(leg_results),
                "is_multi_leg": len(leg_results) > 1,
                "cerebro_decision": {
                    "allocated_capital": decision_obj.allocated_capital / len(leg_results),  # Per-leg allocation
                    "margin_required": leg_result.get('initial_margin', decision_obj.margin_required / len(leg_results)),
                    "position_size_logic": "PortfolioConstructor:MaxCAGR",
                    "risk_metrics": {k: v for k, v in decision_obj.metadata.items() if k != 'leg_results'}  # Exclude leg_results to reduce size
                },
                "environment": signal.get('environment', 'staging'),
                "status": "PENDING",
                "created_at": datetime.utcnow()
            }

            # For EXIT signals, add entry_signal_id reference
            if decision_obj.metadata.get('entry_signal_id'):
                trading_order['entry_signal_id'] = decision_obj.metadata['entry_signal_id']
                trading_order['entry_signal_ref'] = decision_obj.metadata.get('entry_signal_ref')

            # Save to MongoDB
            trading_orders_collection.insert_one(trading_order)
            orders_created.append(order_id)
            logger.info(f"✅ Trading order created: {order_id} for {leg_quantity} {leg_result.get('instrument')}")

            # Publish to Pub/Sub
            try:
                message_data = json.dumps(trading_order, default=str).encode('utf-8')
                future = publisher.publish(trading_orders_topic, message_data)
                future.result(timeout=5)
                logger.info(f"✅ Order published to Pub/Sub topic")

                # Unified signal processing log for order creation
                logger.info(f"SIGNAL: {signal_id} | ORDER_CREATED | OrderID={order_id} | Quantity={leg_quantity} | Instrument={leg_result.get('instrument')} | Direction={leg_result.get('direction')}")
            except Exception as e:
                logger.error(f"Failed to publish order to Pub/Sub: {str(e)}")

        # Summary log for multi-leg
        if len(orders_created) > 1:
            logger.info(f"🔀 Multi-leg signal: Created {len(orders_created)} orders")
        logger.info("-" * 50)


# ============================================================================
# PUB/SUB SUBSCRIBER
# ============================================================================

def signals_callback(message):
    """
    Callback for standardized signals from Pub/Sub
    """
    try:
        data = json.loads(message.data.decode('utf-8'))
        logger.info(f"Received signal: {data.get('signal_id')}")

        # Use new portfolio constructor approach
        process_signal_with_constructor(data)

        message.ack()

    except Exception as e:
        signal_id = data.get('signal_id', 'UNKNOWN') if 'data' in locals() else 'UNKNOWN'
        logger.error(f"🚨 CRITICAL ERROR processing signal {signal_id}: {str(e)}", exc_info=True)
        logger.error(f"Signal data: {data if 'data' in locals() else 'Not available'}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {e.args}")

        # IMPORTANT: ACK the message to prevent infinite redelivery loop
        # The failsafe in execution service will catch any duplicate attempts
        logger.warning(f"⚠️ ACKing failed signal {signal_id} to prevent redelivery loop")
        message.ack()


def start_signal_subscriber():
    """
    Start Pub/Sub subscriber for signals with automatic reconnection on failure
    """
    while True:
        try:
            streaming_pull_future = subscriber.subscribe(signals_subscription, callback=signals_callback)
            logger.info("CerebroService listening for signals...")
            streaming_pull_future.result()  # Blocks until error
        except Exception as e:
            logger.error(f"Subscriber error: {str(e)}")
            logger.warning("Reconnecting to Pub/Sub in 5 seconds...")
            try:
                streaming_pull_future.cancel()
            except:
                pass
            time.sleep(5)  # Wait before reconnecting
            logger.info("Attempting to reconnect...")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting Cerebro Service (Pub/Sub Only)")

    # Initialize Pub/Sub clients
    project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
    subscriber = pubsub_v1.SubscriberClient()
    publisher = pubsub_v1.PublisherClient()
    signals_subscription = subscriber.subscription_path(project_id, 'standardized-signals-sub')
    trading_orders_topic = publisher.topic_path(project_id, 'trading-orders')
    order_commands_topic = publisher.topic_path(project_id, 'order-commands')

    # Download current allocation from MongoDB to local cache (for fast signal processing)
    download_allocations_from_mongo_to_cache(update_action="cerebro_restart")

    # Initialize portfolio constructor (uses the cached allocations)
    initialize_portfolio_constructor()

    # Load allocations
    reload_allocations()

    # Start signal subscriber (BLOCKS)
    start_signal_subscriber()
