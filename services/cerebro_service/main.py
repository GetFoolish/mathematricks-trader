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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'cerebro_service.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Signal processing handler - unified log for signal journey
signal_processing_handler = logging.FileHandler(os.path.join(LOG_DIR, 'signal_processing.log'))
signal_processing_handler.setLevel(logging.INFO)
signal_processing_formatter = logging.Formatter(
    '%(asctime)s | [CEREBRO] | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
signal_processing_handler.setFormatter(signal_processing_formatter)
signal_processing_handler.addFilter(lambda record: 'SIGNAL:' in record.getMessage())
logger.addHandler(signal_processing_handler)


# ============================================================================
# MONGODB CONNECTION
# ============================================================================

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(
    mongo_uri,
    tls=True,
    tlsAllowInvalidCertificates=True  # For development only
)
db = mongo_client['mathematricks_trading']
trading_orders_collection = db['trading_orders']
cerebro_decisions_collection = db['cerebro_decisions']
standardized_signals_collection = db['standardized_signals']
portfolio_allocations_collection = db['portfolio_allocations']
strategies_collection = db['strategies']
strategy_metadata_cache = db['strategy_metadata_cache']  # Cache for strategy metadata

# Create indexes for cache collection
strategy_metadata_cache.create_index("strategy_id", unique=True)
strategy_metadata_cache.create_index("last_updated")

# Collections from signal_collector database (for Activity tab)
signals_db = mongo_client['mathematricks_signals']
incoming_signals_collection = signals_db['trading_signals']  # Raw signals from webhook

# Initialize Position Manager
position_manager = PositionManager(mongo_client)


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
ACCOUNT_DATA_SERVICE_URL = os.getenv('ACCOUNT_DATA_SERVICE_URL', 'http://localhost:8002')


# ============================================================================
# CONFIGURATION
# ============================================================================

# MVP Configuration
MVP_CONFIG = {
    "max_margin_utilization_pct": 40,  # Hard limit - never exceed 40% margin utilization
    "default_position_size_pct": 5,  # Fallback if no allocation found
    "slippage_alpha_threshold": 0.30,  # Drop signal if >30% alpha lost to slippage
    "default_account": "IBKR_Main"  # MVP uses single account
}

# Global: Active portfolio allocations {strategy_id: allocation_pct}
ACTIVE_ALLOCATIONS = {}
ALLOCATIONS_LOCK = threading.Lock()

# Global: Portfolio Constructor instance
PORTFOLIO_CONSTRUCTOR = None
CONSTRUCTOR_LOCK = threading.Lock()


# ============================================================================
# LEGACY FUNCTIONS (for backward compatibility with tests)
# ============================================================================

def calculate_position_size(signal: Dict[str, Any], account_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate position size based on portfolio allocation and risk limits.

    LEGACY FUNCTION - Kept for backwards compatibility with tests.
    New code should use process_signal_with_constructor() instead.

    This wrapper function uses global ACTIVE_ALLOCATIONS and calls the pure function
    from position_sizing.py module.
    """
    from position_sizing import calculate_position_size_legacy

    strategy_id = signal.get('strategy_id')

    # Get strategy allocation from global ACTIVE_ALLOCATIONS
    with ALLOCATIONS_LOCK:
        strategy_allocation_pct = ACTIVE_ALLOCATIONS.get(strategy_id, 0)

    # Call pure function with explicit parameters
    return calculate_position_size_legacy(
        signal=signal,
        account_state=account_state,
        strategy_allocation_pct=strategy_allocation_pct,
        mvp_config=MVP_CONFIG
    )


# ============================================================================
# PORTFOLIO CONSTRUCTOR
# ============================================================================

def initialize_portfolio_constructor():
    """Initialize the portfolio constructor (MaxHybrid strategy)"""
    global PORTFOLIO_CONSTRUCTOR

    with CONSTRUCTOR_LOCK:
        if PORTFOLIO_CONSTRUCTOR is None:
            logger.info("Initializing Portfolio Constructor (MaxHybrid)")
            PORTFOLIO_CONSTRUCTOR = MaxHybridConstructor(
                alpha=0.85,  # 85% Sharpe, 15% CAGR weighting
                max_drawdown_limit=-0.06,  # -6% max drawdown
                max_leverage=2.3,  # 230% max allocation
                max_single_strategy=1.0,  # 100% max per strategy
                min_allocation=0.01,  # 1% minimum
                cagr_target=2.0,  # 200% CAGR target for normalization
                use_fixed_allocations=True,  # 🔒 Use pre-calculated allocations from backtest
                allocations_config_path=None,  # Uses default: portfolio_allocations.json
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

def compute_strategy_metadata_from_doc(strategy_doc: Dict) -> Dict:
    """
    Extract metadata from strategy document.

    Args:
        strategy_doc: Strategy document from MongoDB

    Returns:
        Dict with estimated_avg_positions, median_margin_pct, estimated_position_margin
    """
    position_sizing = strategy_doc.get('position_sizing', {})
    return {
        'estimated_avg_positions': position_sizing.get('estimated_avg_positions', 3.0),
        'median_margin_pct': position_sizing.get('median_margin_pct', 50.0) / 100.0,  # Convert % to decimal
        'estimated_position_margin': position_sizing.get('estimated_position_margin', 10000.0)
    }


def get_strategy_metadata_cached(strategy_id: str) -> Dict[str, Any]:
    """
    Get strategy metadata with intelligent caching.
    Only recomputes if raw data row count has changed.

    This dramatically speeds up signal processing by avoiding
    repeated loading of backtest data from MongoDB.

    Args:
        strategy_id: Strategy identifier

    Returns:
        Dict with:
            - estimated_avg_positions
            - median_margin_pct
            - estimated_position_margin
    """
    # Default metadata in case of errors
    DEFAULT_METADATA = {
        'estimated_avg_positions': 3.0,
        'median_margin_pct': 0.5,
        'estimated_position_margin': 10000.0
    }

    try:
        # Check cache first
        cache_doc = strategy_metadata_cache.find_one({"strategy_id": strategy_id})

        # Get current strategy document
        strategy_doc = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy_doc:
            logger.warning(f"Strategy {strategy_id} not found in MongoDB")
            return DEFAULT_METADATA

        current_row_count = len(strategy_doc.get('raw_data_backtest_full', []))

        # Cache validation
        if cache_doc:
            cached_row_count = cache_doc.get('data_row_count', 0)
            cache_age_seconds = (datetime.utcnow() - cache_doc.get('last_updated')).total_seconds()

            # Use cache if: (1) row count matches AND (2) less than 24 hours old
            if cached_row_count == current_row_count and cache_age_seconds < 86400:
                logger.debug(f"✅ Cache HIT for {strategy_id} ({current_row_count} rows)")
                return {
                    'estimated_avg_positions': cache_doc['estimated_avg_positions'],
                    'median_margin_pct': cache_doc['median_margin_pct'],
                    'estimated_position_margin': cache_doc['estimated_position_margin']
                }
            else:
                logger.info(f"🔄 Cache STALE for {strategy_id}: rows {cached_row_count}→{current_row_count}, age {cache_age_seconds/3600:.1f}h")

        # Cache miss or stale - compute metadata
        logger.info(f"🔄 Computing metadata for {strategy_id} ({current_row_count} rows)")
        metadata = compute_strategy_metadata_from_doc(strategy_doc)

        # Save to cache
        cache_entry = {
            'strategy_id': strategy_id,
            'data_row_count': current_row_count,
            'last_updated': datetime.utcnow(),
            **metadata
        }
        strategy_metadata_cache.update_one(
            {'strategy_id': strategy_id},
            {'$set': cache_entry},
            upsert=True
        )

        return metadata

    except Exception as e:
        logger.error(f"Error getting cached metadata for {strategy_id}: {e}")
        return DEFAULT_METADATA


def warmup_strategy_caches():
    """
    Pre-compute and cache all strategy metadata at startup.
    This ensures fast signal processing from the first signal.
    """
    try:
        logger.info("🔥 Warming up strategy metadata caches...")
        active_strategies = list(strategies_collection.find({"status": "ACTIVE"}))

        for strat in active_strategies:
            strategy_id = strat.get('strategy_id')
            if strategy_id:
                get_strategy_metadata_cached(strategy_id)  # Forces cache creation

        logger.info(f"✅ Cached metadata for {len(active_strategies)} strategies")
    except Exception as e:
        logger.error(f"Error warming up caches: {e}")


def get_strategy_metadata(strategy_id: str) -> Dict[str, Any]:
    """
    Get strategy metadata including position sizing and margin data.

    Returns:
        dict with:
            - estimated_avg_positions
            - median_margin_pct
            - estimated_position_margin
    """
    try:
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            logger.warning(f"Strategy {strategy_id} not found in MongoDB")
            return {
                "estimated_avg_positions": 3.0,  # Default
                "median_margin_pct": 0.5,  # 50% default
                "estimated_position_margin": 10000.0
            }

        position_sizing = strategy.get('position_sizing', {})
        return {
            "estimated_avg_positions": position_sizing.get('estimated_avg_positions', 3.0),
            "median_margin_pct": position_sizing.get('median_margin_pct', 50.0) / 100.0,  # Convert % to decimal
            "estimated_position_margin": position_sizing.get('estimated_position_margin', 10000.0)
        }
    except Exception as e:
        logger.error(f"Error getting strategy metadata for {strategy_id}: {e}")
        return {
            "estimated_avg_positions": 3.0,
            "median_margin_pct": 0.5,
            "estimated_position_margin": 10000.0
        }


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
            # Account state not found - use MVP defaults for testing
            logger.warning(f"No account state found for {account_name}, using MVP defaults")
            return {
                "account": account_name,
                "equity": 100000.0,  # $100k default
                "cash_balance": 100000.0,
                "margin_used": 0.0,
                "margin_available": 50000.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "open_positions": [],
                "open_orders": []
            }
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
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Requested Quantity: {signal.get('quantity', 0)}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Price: ${signal.get('price', 0):,.2f}")

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
    if decision_obj.metadata and 'allocation_pct' in decision_obj.metadata:
        allocation_pct = decision_obj.metadata.get('allocation_pct', 0)
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Strategy Allocation: {allocation_pct:.2f}%")

        # Show correct calculation: account_equity × allocation_pct = total_strategy_allocation
        if decision_obj.metadata and 'position_sizing' in decision_obj.metadata:
            total_allocation = decision_obj.metadata['position_sizing'].get('total_strategy_allocation', 0)
            if total_allocation is not None:
                log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Calculation: {context.account_equity:,.2f} × {allocation_pct:.2f}% = ${total_allocation:,.2f}")
        else:
            # Fallback to allocated_capital if position_sizing not available
            allocated_cap = decision_obj.allocated_capital if decision_obj.allocated_capital is not None else 0
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Calculation: {context.account_equity:,.2f} × {allocation_pct:.2f}% = ${allocated_cap:,.2f}")

    # Position sizing details (if available)
    if decision_obj.metadata and 'position_sizing' in decision_obj.metadata:
        ps = decision_obj.metadata['position_sizing']
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- SMART POSITION SIZING ---")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Total Strategy Allocation: ${ps['total_strategy_allocation']:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Estimated Avg Positions: {ps['estimated_avg_positions']:.1f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Per-Position Capital: ${ps['per_position_capital']:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Calculation: ${ps['total_strategy_allocation']:,.2f} ÷ {ps['estimated_avg_positions']:.1f} = ${ps['per_position_capital']:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Deployed Capital: ${ps['deployed_capital']:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Remaining Capital: ${ps['remaining_capital']:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | This Position Capital: ${ps['this_position_capital']:,.2f}")

        # Show current open positions for this strategy
        if ps.get('position_count', 0) > 0:
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- CURRENT OPEN POSITIONS ({ps['position_count']}) ---")
            for idx, pos_summary in enumerate(ps.get('open_positions_summary', []), 1):
                cost_basis = pos_summary.get('cost_basis') or 0
                log_lines.append(
                    f"SIGNAL: {signal_id} | DETAILED_MATH | Position {idx}: {pos_summary.get('quantity', 0)} shares "
                    f"{pos_summary.get('instrument', 'N/A')} {pos_summary.get('direction', 'N/A')} (cost: ${cost_basis:,.2f})"
                )
        else:
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- CURRENT OPEN POSITIONS (0) ---")
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | No open positions for this strategy")

    # Margin calculation - Show BOTH backtest and IBKR estimates
    if decision_obj.margin_required or (decision_obj.metadata and 'position_sizing' in decision_obj.metadata):
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- MARGIN CALCULATION ---")

        if decision_obj.metadata and 'position_sizing' in decision_obj.metadata:
            ps = decision_obj.metadata['position_sizing']

            # Backtest margin (historical reference)
            backtest_margin_pct = ps.get('backtest_margin_pct', ps.get('margin_pct_used', 0))
            backtest_margin = ps.get('backtest_margin', 0)
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | 📊 Backtest Margin %: {backtest_margin_pct:.2f}% (historical median)")
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | 📊 Backtest Margin: ${backtest_margin:,.2f}")
            if decision_obj.allocated_capital > 0:
                log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | 📊 Calculation: ${decision_obj.allocated_capital:,.2f} × {backtest_margin_pct:.2f}% = ${backtest_margin:,.2f}")

            # IBKR estimated margin (realistic requirement)
            ibkr_margin = ps.get('ibkr_estimated_margin', decision_obj.margin_required)
            ibkr_margin_pct = ps.get('ibkr_margin_pct', 0)
            ibkr_method = ps.get('ibkr_margin_method', 'Standard calculation')
            notional = ps.get('notional_value', 0)

            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | 💰 IBKR Estimated Margin: ${ibkr_margin:,.2f}")
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | 💰 IBKR Margin %: {ibkr_margin_pct:.2f}%")
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | 💰 Method: {ibkr_method}")
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | 💰 Notional Value: ${notional:,.2f}")

            # Show warning if estimates differ significantly
            if backtest_margin > 0:
                ratio = ibkr_margin / backtest_margin
                if ratio > 2 or ratio < 0.5:
                    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | ⚠️ WARNING: IBKR estimate is {ratio:.1f}x backtest margin")
        else:
            # Fallback if metadata not available
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital: ${decision_obj.allocated_capital:,.2f}")
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Required: ${decision_obj.margin_required:,.2f}")

    # Position sizing
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- POSITION SIZING ---")
    if decision_obj.allocated_capital and signal.get('price', 0) > 0:
        calculated_shares = decision_obj.allocated_capital / signal.get('price', 1)
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Shares (before rounding): {calculated_shares:.4f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Calculation: ${decision_obj.allocated_capital:,.2f} ÷ ${signal.get('price', 0):,.2f} = {calculated_shares:.4f} shares")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Final Shares (rounded): {decision_obj.quantity:.0f}")

    # Notional value
    if decision_obj.quantity > 0 and signal.get('price', 0) > 0:
        notional_value = decision_obj.quantity * signal.get('price', 0)
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Final Notional Value: ${notional_value:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Calculation: {decision_obj.quantity:.0f} shares × ${signal.get('price', 0):,.2f} = ${notional_value:,.2f}")

    # Final decision
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- FINAL DECISION ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Decision: {decision_obj.action}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Original Quantity: {signal.get('quantity', 0)}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Final Quantity: {decision_obj.quantity:.0f}")
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
    logger.info(f"Processing signal {signal_id} with Portfolio Constructor")

    # Unified signal processing log
    logger.info(f"SIGNAL: {signal_id} | PROCESSING | Strategy={signal.get('strategy_id')} | Instrument={signal.get('instrument')} | Action={signal.get('action')}")

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
        cerebro_decisions_collection.insert_one(decision)
        logger.info(f"Signal {signal_id} rejected due to slippage")
        return

    # Step 2: Get account state
    account_name = MVP_CONFIG['default_account']
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
        cerebro_decisions_collection.insert_one(decision)
        return

    # Step 3: Build context and convert signal
    context = build_portfolio_context(account_state)
    signal_obj = convert_signal_dict_to_object(signal)

    # Step 4: Get portfolio constructor and evaluate signal
    constructor = initialize_portfolio_constructor()
    decision_obj: SignalDecision = constructor.evaluate_signal(signal_obj, context)

    # Step 4a: Determine Signal Type (ENTRY/EXIT/SCALE)
    signal_type_info = position_manager.determine_signal_type(signal)

    # Step 4a.1: Check for pending ENTRY orders if this is an EXIT signal
    check_and_cancel_pending_entry(signal, signal_type_info)

    # Step 4b: Smart Position Sizing - Adjust for capital distribution
    if decision_obj.action in ['APPROVE', 'RESIZE']:
        strategy_id = signal.get('strategy_id')

        # Get strategy metadata (avg positions, margin %) - CACHED
        strategy_meta = get_strategy_metadata_cached(strategy_id)
        estimated_avg_positions = strategy_meta['estimated_avg_positions']
        median_margin_pct = strategy_meta['median_margin_pct']

        # Calculate per-position allocation
        per_position_capital = decision_obj.allocated_capital / estimated_avg_positions

        # Get currently deployed capital and position state
        deployment_info = get_deployed_capital(strategy_id)
        deployed_capital = deployment_info['deployed_capital']
        open_positions = deployment_info['open_positions']
        position_count = deployment_info['position_count']
        remaining_capital = decision_obj.allocated_capital - deployed_capital

        # Determine this position's capital (min of per-position and remaining)
        position_capital = min(per_position_capital, remaining_capital)

        # Check if we have capital available
        if position_capital <= 0:
            # No capital left - reject signal
            decision_obj = SignalDecision(
                action="REJECTED",
                quantity=0,
                reason=f"No capital remaining (deployed ${deployed_capital:,.2f} of ${decision_obj.allocated_capital:,.2f})",
                allocated_capital=decision_obj.allocated_capital,
                margin_required=0.0,
                metadata={
                    **decision_obj.metadata,
                    'signal_type_info': signal_type_info,
                    'deployed_capital': deployed_capital,
                    'remaining_capital': remaining_capital,
                    'position_count': position_count,
                    'rejection_reason': 'fully_deployed'
                }
            )
        else:
            # Calculate shares from adjusted position capital
            if signal.get('price', 0) > 0:
                adjusted_shares = position_capital / signal.get('price', 0)
            else:
                adjusted_shares = 0

            # Calculate BOTH backtest margin AND estimated IBKR margin
            backtest_margin = position_capital * median_margin_pct
            ibkr_margin_info = estimate_ibkr_margin(signal, adjusted_shares, signal.get('price', 0))

            # Update decision with adjusted values
            decision_obj = SignalDecision(
                action=decision_obj.action,
                quantity=adjusted_shares,
                reason=f"{decision_obj.reason} | {signal_type_info['signal_type']} | Pos-sizing: {estimated_avg_positions:.1f} avg pos",
                allocated_capital=position_capital,  # Adjusted to this position's allocation
                margin_required=ibkr_margin_info['estimated_margin'],  # Use IBKR estimate as primary
                metadata={
                    **decision_obj.metadata,
                    'signal_type_info': signal_type_info,
                    'position_sizing': {
                        'total_strategy_allocation': decision_obj.allocated_capital,
                        'estimated_avg_positions': estimated_avg_positions,
                        'per_position_capital': per_position_capital,
                        'deployed_capital': deployed_capital,
                        'remaining_capital': remaining_capital,
                        'this_position_capital': position_capital,
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
                        'margin_pct_used': median_margin_pct * 100,  # Keep for backward compatibility
                        # IBKR estimated margin (realistic)
                        'ibkr_estimated_margin': ibkr_margin_info['estimated_margin'],
                        'ibkr_margin_pct': ibkr_margin_info['margin_pct'],
                        'ibkr_margin_method': ibkr_margin_info['calculation_method'],
                        'notional_value': ibkr_margin_info['notional_value'],
                        'shares_calculation': f"${position_capital:,.2f} ÷ ${signal.get('price', 0):,.2f} = {adjusted_shares:.2f} shares"
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
    logger.info(f"{'='*70}\n")

    # Step 5: Save decision to MongoDB
    decision_doc = {
        "signal_id": signal_id,
        "decision": decision_obj.action,  # "APPROVE", "REJECT", "RESIZE"
        "timestamp": datetime.utcnow(),
        "reason": decision_obj.reason,
        "original_quantity": signal.get('quantity', 0),
        "final_quantity": decision_obj.quantity,
        "risk_assessment": {
            "allocated_capital": decision_obj.allocated_capital,
            "margin_required": decision_obj.margin_required,
            "metadata": decision_obj.metadata
        },
        "created_at": datetime.utcnow()
    }
    cerebro_decisions_collection.insert_one(decision_doc)

    # Unified signal processing log for decision
    logger.info(f"SIGNAL: {signal_id} | DECISION | Action={decision_obj.action} | OrigQty={signal.get('quantity', 0)} | FinalQty={decision_obj.quantity:.0f} | Reason={decision_obj.reason}")

    # Step 6: If approved or resized, create trading order
    if decision_obj.action in ['APPROVE', 'RESIZE']:
        # Round to whole shares for IBKR compatibility
        final_quantity_rounded = round(decision_obj.quantity)

        if final_quantity_rounded <= 0:
            logger.warning(f"Rounded quantity is 0, rejecting signal")
            return

        order_id = f"{signal_id}_ORD"
        trading_order = {
            "order_id": order_id,
            "signal_id": signal_id,
            "strategy_id": signal.get('strategy_id'),
            "account": account_name,
            "timestamp": datetime.utcnow(),
            "instrument": signal.get('instrument'),
            "direction": signal.get('direction'),
            "action": signal.get('action'),
            "order_type": signal.get('order_type'),
            "price": signal.get('price'),
            "quantity": final_quantity_rounded,
            "stop_loss": signal.get('stop_loss'),
            "take_profit": signal.get('take_profit'),
            "expiry": signal.get('expiry'),
            # Multi-asset support: pass through instrument_type and related fields
            "instrument_type": signal.get('instrument_type'),  # STOCK, OPTION, FOREX, FUTURE
            "underlying": signal.get('underlying'),  # For options
            "legs": signal.get('legs'),  # For multi-leg options
            "exchange": signal.get('exchange'),  # For futures
            "cerebro_decision": {
                "allocated_capital": decision_obj.allocated_capital,
                "margin_required": decision_obj.margin_required,
                "position_size_logic": "PortfolioConstructor:MaxCAGR",
                "risk_metrics": decision_obj.metadata
            },
            "status": "PENDING",
            "created_at": datetime.utcnow()
        }

        # Save to MongoDB
        trading_orders_collection.insert_one(trading_order)
        logger.info(f"✅ Trading order created: {order_id} for {final_quantity_rounded} shares")

        # Publish to Pub/Sub
        try:
            message_data = json.dumps(trading_order, default=str).encode('utf-8')
            future = publisher.publish(trading_orders_topic, message_data)
            future.result(timeout=5)
            logger.info(f"✅ Order published to Pub/Sub topic")

            # Unified signal processing log for order creation
            logger.info(f"SIGNAL: {signal_id} | ORDER_CREATED | OrderID={order_id} | Quantity={final_quantity_rounded} | Instrument={signal.get('instrument')} | Direction={signal.get('direction')}")
        except Exception as e:
            logger.error(f"Failed to publish order to Pub/Sub: {str(e)}")

    # Update signal as processed
    standardized_signals_collection.update_one(
        {"signal_id": signal_id},
        {"$set": {"processed_by_cerebro": True}}
    )


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

    # Warmup caches
    warmup_strategy_caches()

    # Initialize portfolio constructor
    initialize_portfolio_constructor()

    # Load allocations
    reload_allocations()

    # Start signal subscriber (BLOCKS)
    start_signal_subscriber()
