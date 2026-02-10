"""
Cerebro Service - MongoDB Change Stream Signal Processing
The intelligent core for portfolio management, risk assessment, and position sizing.
Implements hard margin limits and smart position sizing.
"""
import os
import logging
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
import threading
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

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

# Fund allocation logic imports
from fund_allocation_logic import (
    get_active_allocations_for_strategy,
    get_strategy_allocation_for_fund,
    get_available_accounts_for_strategy,
    distribute_capital_across_accounts
)

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
portfolio_allocations_collection = db['portfolio_allocations']  # DEPRECATED: Use funds + portfolio_tests instead
current_allocation_collection = db['current_allocation']  # DEPRECATED: Use funds + portfolio_tests instead
strategies_collection = db['strategies']
funds_collection = db['funds']  # Fund architecture support
trading_accounts_collection = db['trading_accounts']  # Account data for fund allocation
portfolio_tests_collection = db['portfolio_tests']  # Portfolio test results with allocations

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
# Initialize precision service (MongoDB-based cache)
precision_service = get_precision_service()  # Uses default MongoDB URI from env


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


def allocate_quantity_across_accounts(
    total_quantity: Union[int, float],
    account_allocations: List[Dict[str, Any]],
    target_capital: float,
    instrument_type: str
) -> List[Union[int, float]]:
    """
    Allocate quantity across multiple accounts ensuring sum equals total_quantity.
    For OPTIONS/FUTURES: Uses floor division with remainder distribution (integer contracts).
    For CRYPTO/FOREX/STOCK: Distributes proportionally based on allocated capital (fractional OK).
    
    Args:
        total_quantity: Total quantity to distribute (int for options, float for crypto/forex)
        account_allocations: List of {account_id, allocated_capital} dicts
        target_capital: Total capital being distributed
        instrument_type: Instrument type for precision rules
        
    Returns:
        List of quantities, one per account, summing to total_quantity
        
    Example (OPTIONS):
        Input: total_quantity=231, 2 accounts with equal capital
        Output: [115, 116] (integer contracts)
    
    Example (CRYPTO):
        Input: total_quantity=0.5, 2 accounts with 60/40 capital split
        Output: [0.3, 0.2] (fractional BTC)
    """
    if not account_allocations:
        return []
    
    num_accounts = len(account_allocations)
    
    # For crypto/forex/stock, use proportional allocation (preserves fractions)
    if instrument_type in ['CRYPTO', 'FOREX', 'STOCK']:
        quantities = []
        if target_capital > 0:
            for account in account_allocations:
                allocated_capital = account.get('allocated_capital', 0)
                proportion = allocated_capital / target_capital
                quantities.append(total_quantity * proportion)
        else:
            # Equal distribution if no capital info
            qty_per_account = total_quantity / num_accounts
            quantities = [qty_per_account] * num_accounts
        
        logger.info(
            f"✅ Allocated {total_quantity} {instrument_type} units across {num_accounts} accounts: {quantities}"
        )
        return quantities
    
    # For options/futures, use integer contract allocation
    total_quantity = int(total_quantity)  # Ensure integer for contract-based instruments
    
    # Calculate base quantity and remainder using floor division
    base_qty = total_quantity // num_accounts
    remainder = total_quantity % num_accounts
    
    # Distribute base quantity to all accounts
    quantities = [base_qty] * num_accounts
    
    # Distribute remainder one-by-one to accounts with higher capital allocation
    # Sort by allocated_capital descending to give remainder to larger accounts
    sorted_indices = sorted(
        range(num_accounts),
        key=lambda i: account_allocations[i].get('allocated_capital', 0),
        reverse=True
    )
    
    for i in range(remainder):
        quantities[sorted_indices[i]] += 1
    
    # Verify sum equals total (assertion for safety)
    actual_sum = sum(quantities)
    if actual_sum != total_quantity:
        logger.error(
            f"⚠️ Quantity allocation error: {quantities} sum to {actual_sum}, expected {total_quantity}"
        )
        # Adjust last account to force correct sum
        quantities[-1] += (total_quantity - actual_sum)
    
    logger.info(
        f"✅ Allocated {total_quantity} contracts across {num_accounts} accounts: {quantities}"
    )
    
    return quantities


# Helper function to build v2 decision document
def build_decision_v2(
    status: str,
    reason: str,
    signal: dict,
    decision_obj: Optional['SignalDecision'] = None,
    legs: list = None
) -> dict:
    """
    Build a clean v2 cerebro document for signal_store.

    v2 Schema:
    - cerebro.status: APPROVED | REJECTED | RESIZE
    - cerebro.reason: Human-readable explanation
    - cerebro.created_orders[]: Final order specifications per instrument
    - cerebro.math: Detailed calculation breakdown
    """
    from bson import ObjectId

    # Build cerebro.created_orders from leg_results or signal
    created_orders = []
    leg_results = []

    if decision_obj and decision_obj.metadata.get('leg_results'):
        leg_results = decision_obj.metadata['leg_results']
    elif legs:
        # Build from raw signal legs
        # For EXIT signals, use decision_obj.quantity (actual filled from ENTRY) instead of raw leg quantity
        is_exit_signal = decision_obj and decision_obj.metadata.get('signal_type_info', {}).get('signal_type') in ['EXIT', 'SCALE_OUT']
        
        for i, leg in enumerate(legs):
            # For EXIT signals, override quantity with decision_obj.quantity (the actual filled amount from ENTRY)
            leg_quantity = decision_obj.quantity if (is_exit_signal and decision_obj) else leg.get('quantity', 0)
            
            leg_results.append({
                'leg_index': i,
                'instrument': leg.get('instrument') or leg.get('ticker'),
                'instrument_type': leg.get('instrument_type', 'STOCK'),
                'action': leg.get('action'),
                'direction': leg.get('direction'),
                'order_type': leg.get('order_type', 'MARKET'),
                'quantity': leg_quantity,  # Use actual filled quantity for EXIT, raw for ENTRY
                'price_used': leg.get('price', 0),
                # Preserve nested option legs (e.g., strike/expiry/right) if present
                'legs': leg.get('legs') if leg.get('legs') and isinstance(leg.get('legs'), list) else None
            })

    for leg in leg_results:
        created_orders.append({
            "instrument": leg.get('instrument'),
            "instrument_type": leg.get('instrument_type', 'STOCK'),
            "action": leg.get('action'),
            "direction": leg.get('direction'),
            "quantity": leg.get('quantity', 0),
            "order_type": leg.get('order_type', 'MARKET'),
            "price": leg.get('price_used', 0),
            "margin_required": leg.get('initial_margin', 0),
            # Note: broker, exchange, time_in_force are added later when distributing across accounts
            # If this leg contains nested option 'legs', attach them so execution receives full details
            "legs": leg.get('legs') if leg.get('legs') else None
        })

    # Build decision.math as formatted string (7 sections matching log_detailed_calculation_math)
    math_lines = []
    
    # Extract original quantity from signal (check legs structure first, fallback to top-level)
    raw_qty = 0
    if legs and len(legs) > 0:
        raw_qty = legs[0].get('quantity', 0)
    elif signal.get('legs') and len(signal.get('legs', [])) > 0:
        raw_qty = signal['legs'][0].get('quantity', 0)
    else:
        raw_qty = signal.get('quantity', 0)
    
    final_qty = decision_obj.quantity if decision_obj else 0

    # Extract first leg info for display (prefer passed legs param, fallback to signal.legs)
    first_leg = legs[0] if legs and len(legs) > 0 else (signal.get('legs', [{}])[0] if signal.get('legs') else signal)

    # --- 1. SIGNAL INPUT ---
    math_lines.append("--- 1. SIGNAL INPUT ---")
    math_lines.append(f"Instrument: {first_leg.get('instrument', 'N/A')} ({first_leg.get('instrument_type', 'UNKNOWN')})")
    math_lines.append(f"Action: {first_leg.get('action', 'N/A')} {first_leg.get('direction', '')}")
    math_lines.append(f"Raw Quantity: {raw_qty}")
    math_lines.append(f"Price: ${first_leg.get('price', 0):,.2f}")

    if decision_obj and decision_obj.metadata:
        metadata = decision_obj.metadata
        position_sizing = metadata.get('position_sizing', {})

        # --- 2. SIGNAL TYPE ---
        math_lines.append("\n--- 2. SIGNAL TYPE ---")
        signal_type = signal.get('signal_type', 'ENTRY')
        if metadata.get('signal_type_info'):
            st_info = metadata['signal_type_info']
            math_lines.append(f"Type: {st_info.get('signal_type', signal_type)}")
            math_lines.append(f"Detection: {st_info.get('method', 'N/A')}")
            if st_info.get('reasoning'):
                math_lines.append(f"Reasoning: {st_info.get('reasoning')}")
        else:
            math_lines.append(f"Type: {signal_type}")

        # --- 3. FUND ALLOCATION ---
        math_lines.append("\n--- 3. FUND ALLOCATION ---")
        allocated = position_sizing.get('allocated_capital', 0)
        deployed = position_sizing.get('deployed_capital', 0)
        available = position_sizing.get('allocated_capital_available', 0)
        position_count = position_sizing.get('position_count', 0)
        account_equity = metadata.get('account_state', {}).get('equity', 0)
        allocation_pct = position_sizing.get('allocation_percentage', 0)
        
        math_lines.append(f"Account Balance: ${account_equity:,.2f}")
        math_lines.append(f"Strategy Allocation: {allocation_pct:.2f}% of account")
        math_lines.append(f"Allocated Capital: ${allocated:,.2f}")
        math_lines.append(f"Deployed Capital: ${deployed:,.2f} ({position_count} positions)")
        math_lines.append(f"Available Capital: ${available:,.2f}")

        # --- 4. SCALING CALCULATION ---
        scaling = position_sizing.get('scaling_ratio', 1)
        signal_equity = position_sizing.get('signal_account_equity', 0)
        math_lines.append("\n--- 4. SCALING CALCULATION ---")
        if metadata.get('entry_signal_id'):
            # EXIT signal - show position matching info
            math_lines.append(f"Entry Signal: {metadata.get('entry_signal_ref', 'N/A')}")
            math_lines.append(f"Entry Quantity: {metadata.get('entry_quantity', 0)}")
            math_lines.append(f"Quantity to Close: {final_qty}")
            math_lines.append("Note: EXIT signals match entry position (no scaling)")
        elif signal_equity > 0:
            # ENTRY signal - always show scaling calculation
            math_lines.append(f"Signal Account Equity: ${signal_equity:,.2f} (from signal payload)")
            math_lines.append(f"Allocated Capital: ${allocated:,.2f} (strategy allocation before deployment)")
            math_lines.append(f"Scaling Ratio Calculation: ${allocated:,.2f} ÷ ${signal_equity:,.2f} = {scaling:.5f}")
            scaled_qty = raw_qty * scaling
            math_lines.append(f"Scaled Quantity: {raw_qty} × {scaling:.5f} = {scaled_qty:.4f}")
            math_lines.append(f"Final Quantity: {final_qty} (after precision rules)")
        else:
            # Fallback for edge cases
            math_lines.append("N/A - No scaling information available")

        # --- 5. MARGIN VALIDATION ---
        margin_required = position_sizing.get('margin_required', 0)
        margin_method = position_sizing.get('margin_method', 'Unknown')
        notional = position_sizing.get('notional_value', 0)
        math_lines.append("\n--- 5. MARGIN VALIDATION ---")
        math_lines.append(f"Method: {margin_method}")
        if notional > 0:
            math_lines.append(f"Notional: ${notional:,.2f}")
        math_lines.append(f"Margin Required: ${margin_required:,.2f}")
        math_lines.append(f"Allocated Capital: ${allocated:,.2f}")
        math_lines.append(f"Deployed Capital: ${deployed:,.2f} ({position_count} positions)")
        math_lines.append(f"Available Capital: ${available:,.2f}")
        if available > 0:
            check = "✅ OK" if margin_required <= available else "❌ EXCEEDS"
            math_lines.append(f"Affordability Check: {check} (${margin_required:,.2f} vs ${available:,.2f} available)")

        # --- 6. BROKER ACCOUNT STATE ---
        account_state = metadata.get('account_state', {})
        if account_state:
            math_lines.append("\n--- 6. BROKER ACCOUNT STATE ---")
            math_lines.append("Source: account-data-service (broker-reported)")
            math_lines.append(f"Equity: ${account_state.get('equity', 0):,.2f}")
            math_lines.append(f"Cash: ${account_state.get('cash_balance', 0):,.2f}")
            math_lines.append(f"Margin Used: ${account_state.get('margin_used', 0):,.2f}")
            math_lines.append(f"Margin Available: ${account_state.get('margin_available', 0):,.2f}")

        # --- 7. FINAL DECISION ---
        math_lines.append("\n--- 7. FINAL DECISION ---")
        math_lines.append(f"Decision: {status}")
        math_lines.append(f"Original Qty: {raw_qty}")
        math_lines.append(f"Final Qty: {final_qty}")
        math_lines.append(f"Reason: {reason}")

    math_breakdown = "\n".join(math_lines) if math_lines else "No calculation data"

    # Build the v2 cerebro document
    return {
        "status": status,
        "reason": reason,
        "timestamp": datetime.utcnow(),
        "created_orders": created_orders,
        "math": math_breakdown
    }


# Helper function to update signal_store with cerebro output
def update_signal_store_with_decision(signal_store_id: str, decision_doc: dict, raw_signal_id: str = None):
    """
    Update signal_store document with cerebro output in CONSOLIDATED SCHEMA (v3).

    CONSOLIDATED SCHEMA:
    - Finds the specific leg in legs[] array by matching raw._id
    - Updates legs[i].cerebro field for that leg
    - Sets processing_complete flag at document root

    Args:
        signal_store_id: MongoDB ObjectId of the signal_store document
        decision_doc: Decision document to store
        raw_signal_id: MongoDB ObjectId of the raw signal (to match leg)
    """
    if not signal_store_id:
        logger.warning("⚠️ No signal_store_id provided, skipping signal_store update")
        return

    try:
        from bson import ObjectId

        # Determine status for processing_complete flag
        status = decision_doc.get("status", decision_doc.get("decision", ""))

        # Get the signal document to find the matching leg
        signal_doc = signal_store_collection.find_one({"_id": ObjectId(signal_store_id)})
        if not signal_doc:
            logger.error(f"❌ Signal document {signal_store_id} not found")
            return

        legs = signal_doc.get('legs', [])
        if not legs:
            logger.error(f"❌ No legs found in signal document {signal_store_id}")
            return

        # Find the leg that matches this raw signal
        # For consolidated schema, there should be a leg with raw._id matching the raw signal
        leg_index = None

        # If raw_signal_id provided, match by raw._id
        if raw_signal_id:
            for idx, leg in enumerate(legs):
                if str(leg.get('raw', {}).get('_id')) == str(raw_signal_id):
                    leg_index = idx
                    break

        # Fallback: if only one leg, use it
        if leg_index is None and len(legs) == 1:
            leg_index = 0
            logger.debug(f"Using first leg (only one leg in document)")

        # Fallback: find first leg without decision
        if leg_index is None:
            for idx, leg in enumerate(legs):
                if not leg.get('cerebro'):
                    leg_index = idx
                    logger.debug(f"Using first leg without cerebro at index {idx}")
                    break

        if leg_index is None:
            logger.error(f"❌ Could not find matching leg in signal document {signal_store_id}")
            logger.error(f"   Document has {len(legs)} legs, raw_signal_id={raw_signal_id}")
            return

        # Update the specific leg's cerebro field and add cerebro timestamp
        now = datetime.utcnow()
        signal_store_collection.update_one(
            {"_id": ObjectId(signal_store_id)},
            {
                "$set": {
                    f"legs.{leg_index}.cerebro": decision_doc,
                    f"legs.{leg_index}.processing_timestamps.cerebro_processed": now,
                    "processing_complete": status in ["APPROVED", "RESIZE"],
                    "updated_at": now
                }
            }
        )
        logger.info(f"✅ Updated signal_store {signal_store_id} leg {leg_index} with cerebro (status={status})")

    except Exception as e:
        logger.error(f"⚠️ Failed to update signal_store: {e}", exc_info=True)


# ============================================================================
# SERVICE URLs
# ============================================================================

ACCOUNT_DATA_SERVICE_URL = os.getenv('ACCOUNT_DATA_SERVICE_URL', 'http://localhost:8082')
EXECUTION_SERVICE_URL = os.getenv('EXECUTION_SERVICE_URL', 'http://localhost:8083')


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

            # Portfolio constructor for optimal allocation algorithms
            # Note: All allocations now read from MongoDB (funds + portfolio_tests)
            PORTFOLIO_CONSTRUCTOR = MaxHybridConstructor(
                alpha=0.85,  # 85% Sharpe, 15% CAGR weighting
                max_drawdown_limit=-0.06,  # -6% max drawdown
                max_leverage=2.3,  # 230% max allocation
                max_single_strategy=1.0,  # 100% max per strategy
                min_allocation=0.01,  # 1% minimum
                cagr_target=2.0,  # 200% CAGR target for normalization
                use_cached_allocations=False,
                allocations_config_path=None,
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

def get_deployed_capital(strategy_id: str, account_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate deployed capital for a strategy from account state's open positions.
    Uses account-data-service data (which reads from MongoDB trading_accounts.open_positions[]).

    Args:
        strategy_id: Strategy ID to check
        account_state: Account state dict from account-data-service

    Returns:
        Dict with:
            - deployed_capital: Total cost basis of open positions
            - deployed_margin: Total margin used
            - open_positions: List of position documents
            - position_count: Number of open positions
    """
    try:
        # Get open positions from account state (from account-data-service)
        all_positions = account_state.get('open_positions', [])
        
        # Filter for this strategy
        strategy_positions = [p for p in all_positions if p.get('strategy_id') == strategy_id and p.get('status') == 'OPEN']
        
        # Calculate total capital deployed (quantity * avg_entry_price)
        total_capital = sum(
            p.get('quantity', 0) * p.get('avg_entry_price', 0)
            for p in strategy_positions
        )
        
        # Estimate margin (for stocks, typically 25% margin requirement)
        total_margin = total_capital * 0.25
        
        result = {
            'deployed_capital': total_capital,
            'deployed_margin': total_margin,
            'open_positions': strategy_positions,
            'position_count': len(strategy_positions)
        }
        
        logger.info(f"🔍 get_deployed_capital({strategy_id}): ${result['deployed_capital']:,.2f} from {result['position_count']} positions")
        if result['position_count'] > 0:
            for pos in strategy_positions:
                logger.info(f"   - {pos.get('instrument')}: {pos.get('quantity')} @ ${pos.get('avg_entry_price'):.2f} = ${pos.get('total_cost_basis', 0):,.2f}")
        
        return result
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
    Query AccountDataService for current account state.
    This now syncs fresh balances from broker first (if execution-service available).
    """
    from account_queries import get_account_state as _get_account_state
    return _get_account_state(
        account_name=account_name,
        account_data_service_url=ACCOUNT_DATA_SERVICE_URL,
        execution_service_url=EXECUTION_SERVICE_URL
    )


# ============================================================================
# ORDER COMMANDS
# ============================================================================

# NOTE: Order cancel commands removed - cerebro no longer publishes to pub/sub.
# Use execution-service API directly if order cancellation is needed.


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


def find_open_entry_signal(strategy_id: str, instrument: str, direction: str) -> Optional[Dict[str, Any]]:
    """
    Query signal_store for open entry signal (CONSOLIDATED SCHEMA v3)

    Args:
        strategy_id: Strategy identifier
        instrument: Instrument name
        direction: Direction of the EXIT signal (same as ENTRY direction)

    Returns:
        Entry signal document from signal_store, or None if not found
    """
    try:
        # EXIT signal has SAME direction as ENTRY (LONG->LONG, SHORT->SHORT)
        # It's the ACTION that differs: ENTRY=BUY/SELL_SHORT, EXIT=SELL/BUY_TO_COVER
        entry_direction = direction

        # CONSOLIDATED SCHEMA v3: Query for document with position.status = OPEN
        # The document root has: strategy_id, instrument, position.status
        # Each leg in legs[] has: cerebro.status, execution.status
        entry_signal = signal_store_collection.find_one({
            "strategy_id": strategy_id,
            "instrument": instrument,
            "position.status": "OPEN",
            # Check that at least one leg has APPROVED decision and FILLED execution
            "legs": {
                "$elemMatch": {
                    "leg_type": "ENTRY",
                    "cerebro.status": {"$in": ["APPROVED", "RESIZE"]},
                    "execution.status": "FILLED"
                }
            }
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


def find_and_cancel_pending_entry(strategy_id: str, instrument: str, direction: str) -> Optional[Dict[str, Any]]:
    """
    Find and cancel a pending (unfilled) ENTRY order when EXIT signal arrives too early.

    Real-world trading logic: If EXIT arrives before ENTRY fills, cancel the ENTRY
    rather than waiting. This prevents holding stale positions.

    Args:
        strategy_id: Strategy identifier
        instrument: Instrument name
        direction: Direction of the EXIT signal (same as ENTRY direction)

    Returns:
        Cancelled entry signal document if found and cancelled, None otherwise
    """
    # EXIT signal has SAME direction as ENTRY
    entry_direction = direction
    logger.info(f"🔍 Looking for pending entry to cancel: {strategy_id}/{instrument}/{entry_direction}")

    try:
        # Query for pending ENTRY order (v2 schema first, then v1 fallback)
        # v2: cerebro.status, position.status, execution.status
        # A pending entry is one that's been approved but NOT yet filled (execution.status != FILLED)
        pending_entry = signal_store_collection.find_one({
            "strategy_id": strategy_id,
            "raw.legs.instrument": instrument,
            "raw.legs.direction": entry_direction,
            "cerebro.status": {"$in": ["APPROVED", "RESIZE"]},
            "$and": [
                # Position not yet OPEN (null, doesn't exist, or not OPEN)
                {"$or": [
                    {"position.status": None},
                    {"position.status": {"$exists": False}},
                    {"position.status": {"$nin": ["OPEN", "CLOSED"]}}
                ]},
                # Execution not FILLED
                {"$or": [
                    {"execution": None},
                    {"execution": {"$exists": False}},
                    {"execution.status": {"$nin": ["FILLED"]}}
                ]}
            ]
        })

        # Fallback to v1 schema
        if not pending_entry:
            pending_entry = signal_store_collection.find_one({
                "strategy_id": strategy_id,
                "instrument": instrument,
                "direction": entry_direction,
                "cerebro_decision.decision": {"$in": ["APPROVE", "APPROVED"]},
                "position_status": {"$ne": "CLOSED"},
                "$or": [
                    {"execution": None},
                    {"execution": {"$exists": False}},
                    {"execution.status": {"$nin": ["FILLED"]}}
                ]
            })

        if not pending_entry:
            logger.info(f"📭 No pending entry order found for {strategy_id}/{instrument}/{entry_direction}")
            return None

        pending_signal_id = pending_entry.get('signal_id')
        logger.info(f"📋 Found pending entry order: {pending_signal_id}")

        # Check if there's a broker order to cancel
        execution = pending_entry.get('execution')
        broker_order_id = None
        if execution:
            # v2: execution.orders[]
            orders = execution.get('orders', [])
            if orders:
                broker_order_id = orders[-1].get('broker_order_id')
            # v1: execution.broker_order_id
            if not broker_order_id:
                broker_order_id = execution.get('broker_order_id')

        if broker_order_id:
            logger.info(f"🚫 Cancelling broker order: {broker_order_id}")
            try:
                # Cancel via broker adapter
                if broker_adapter:
                    cancel_success = broker_adapter.cancel_order(broker_order_id)
                    if cancel_success:
                        logger.info(f"✅ Broker order cancelled successfully")
                    else:
                        logger.warning(f"⚠️ Broker cancel returned False - order may already be filled/cancelled")
            except Exception as cancel_err:
                logger.warning(f"⚠️ Error cancelling broker order: {cancel_err}")

        # Update signal_store to mark entry as CANCELLED
        cancel_timestamp = datetime.datetime.utcnow()
        update_result = signal_store_collection.update_one(
            {"_id": pending_entry["_id"]},
            {
                "$set": {
                    # v2 schema
                    "cerebro.status": "CANCELLED",
                    "cerebro.reason": f"Cancelled: EXIT signal arrived before entry filled",
                    "cerebro.cancelled_at": cancel_timestamp,
                    "position.status": "CANCELLED",
                    # v1 schema (for backward compat)
                    "cerebro_decision.decision": "CANCELLED",
                    "cerebro_decision.reason": f"Cancelled: EXIT signal arrived before entry filled",
                    "position_status": "CANCELLED",
                    "updated_at": cancel_timestamp
                }
            }
        )

        if update_result.modified_count > 0:
            logger.info(f"✅ Entry signal {pending_signal_id} marked as CANCELLED in signal_store")
        else:
            logger.warning(f"⚠️ Failed to update entry signal {pending_signal_id} in signal_store")

        return pending_entry

    except Exception as e:
        logger.error(f"❌ Error in find_and_cancel_pending_entry: {e}")
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
    # Use signal_sent_EPOCH (internal EPOCH format) - convert to datetime for Signal object
    epoch_timestamp = signal_dict.get('signal_sent_EPOCH')

    # Validate timestamp exists
    if epoch_timestamp is None:
        raise ValueError(f"Signal {signal_dict.get('signal_id')} has no signal_sent_EPOCH. Developer must provide a valid EPOCH timestamp.")

    # Convert EPOCH to datetime
    if isinstance(epoch_timestamp, (int, float)):
        timestamp_value = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    elif isinstance(epoch_timestamp, datetime):
        # Already a datetime (edge case)
        timestamp_value = epoch_timestamp
    else:
        raise ValueError(f"Signal {signal_dict.get('signal_id')} has invalid signal_sent_EPOCH type: {type(epoch_timestamp)}. Must be int/float EPOCH or datetime.")

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

    Sections:
    1. SIGNAL INPUT - Raw signal data
    2. SIGNAL TYPE - Entry/Exit detection
    3. FUND ALLOCATION - Full calculation chain with formulas
    4. SCALING CALCULATION - Ratio-based quantity scaling
    5. MARGIN VALIDATION - Margin check results
    6. BROKER ACCOUNT STATE - Reference data from broker
    7. FINAL DECISION - Approved/Rejected with final quantity

    Args:
        signal: The incoming signal dictionary
        context: PortfolioContext object with fund_allocation data
        decision_obj: SignalDecision object with the final decision
        account_state: Account state dictionary from broker
    """
    signal_id = signal.get('signal_id')
    strategy_id = signal.get('strategy_id')

    # Extract position_sizing and fund_allocation data
    ps = decision_obj.metadata.get('position_sizing', {}) if decision_obj.metadata else {}
    fund_alloc = getattr(context, 'fund_allocation', {}) or {}

    log_lines = []
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | ===== START CALCULATION BREAKDOWN =====")

    # --- 1. SIGNAL INPUT ---
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- 1. SIGNAL INPUT ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal ID: {signal_id}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Strategy: {strategy_id}")
    instrument = signal.get('instrument')
    instrument_type = signal.get('instrument_type', 'UNKNOWN')
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Instrument: {instrument} ({instrument_type})")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Action: {signal.get('action')} {signal.get('direction')}")
    signal_qty = signal.get('quantity', 0)
    signal_price = signal.get('price', 0)
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Raw Quantity: {signal_qty}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal Price: ${signal_price:,.2f}")

    # Show signal's account_equity with SOURCE
    raw_account_equity = signal.get('account_equity')
    if raw_account_equity:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal Account Equity: ${raw_account_equity:,.2f} (from signal payload)")
    else:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal Account Equity: MISSING (will be rejected if ENTRY)")

    # --- 2. SIGNAL TYPE ---
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- 2. SIGNAL TYPE ---")
    if decision_obj.metadata and 'signal_type_info' in decision_obj.metadata:
        st_info = decision_obj.metadata['signal_type_info']
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Type: {st_info.get('signal_type', 'UNKNOWN')}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Detection: {st_info.get('method', 'N/A')}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Reasoning: {st_info.get('reasoning', 'N/A')}")

        # Show current position if exists (for EXIT signals)
        if st_info.get('current_position'):
            pos = st_info['current_position']
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Current Position: {pos.get('quantity')} units {pos.get('direction')} @ avg ${pos.get('avg_entry_price', 0):.2f}")
    else:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Type: N/A (no signal_type_info)")

    # --- 3. FUND ALLOCATION --- (CLEAR MATH CHAIN)
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- 3. FUND ALLOCATION ---")
    fund_id = fund_alloc.get('fund_id', 'N/A')
    fund_equity = fund_alloc.get('fund_equity', 0)
    strategy_pct = fund_alloc.get('strategy_pct', 0)
    allocated_capital = ps.get('allocated_capital', fund_alloc.get('allocated_capital', 0))
    deployed_capital = ps.get('deployed_capital', 0)
    available_capital = ps.get('allocated_capital_available', allocated_capital - deployed_capital)
    position_count = ps.get('position_count', 0)

    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Fund: {fund_id}")
    if fund_equity > 0:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Fund Total Equity: ${fund_equity:,.2f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Strategy Allocation: {strategy_pct:.2f}%")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital: ${fund_equity:,.2f} × {strategy_pct/100:.4f} = ${allocated_capital:,.2f}")
    else:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital: ${allocated_capital:,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Deployed Capital: ${deployed_capital:,.2f} ({position_count} open positions)")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Available Capital: ${allocated_capital:,.2f} - ${deployed_capital:,.2f} = ${available_capital:,.2f}")

    # Show open positions if any
    if position_count > 0:
        for idx, pos_summary in enumerate(ps.get('open_positions_summary', []), 1):
            cost_basis = pos_summary.get('cost_basis') or 0
            log_lines.append(
                f"SIGNAL: {signal_id} | DETAILED_MATH |   Position {idx}: {pos_summary.get('quantity', 0)} units "
                f"{pos_summary.get('instrument', 'N/A')} {pos_summary.get('direction', 'N/A')} (cost: ${cost_basis:,.2f})"
            )

    # --- 4. SCALING CALCULATION --- (CLEAR FORMULA)
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- 4. SCALING CALCULATION ---")
    signal_account_equity = ps.get('signal_account_equity', 0)
    scaling_ratio = ps.get('scaling_ratio', 0)
    allocated_capital_available = ps.get('allocated_capital_available', 0)

    if signal_account_equity > 0 and allocated_capital_available > 0:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Signal Account Equity: ${signal_account_equity:,.2f} (from signal payload)")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Allocated Capital Available: ${allocated_capital_available:,.2f} (strategy allocation minus deployed)")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Scaling Ratio Calculation: ${allocated_capital_available:,.2f} ÷ ${signal_account_equity:,.2f} = {scaling_ratio:.5f}")
        calculated_qty = signal_qty * scaling_ratio
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Scaled Quantity: {signal_qty} × {scaling_ratio:.5f} = {calculated_qty:.4f}")
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Final Quantity: {decision_obj.quantity} (after precision rules)")
    else:
        # Check if this is an EXIT signal
        signal_type_info = decision_obj.metadata.get('signal_type_info', {}) if decision_obj.metadata else {}
        sig_type = signal_type_info.get('signal_type', 'UNKNOWN')
        if sig_type in ['EXIT', 'SCALE_OUT']:
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | N/A - EXIT signals don't use scaling (quantity matches entry position)")
        else:
            log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | N/A - No signal_account_equity provided (required for ENTRY signals)")

    # --- 5. MARGIN VALIDATION ---
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- 5. MARGIN VALIDATION ---")
    margin_required = ps.get('margin_required', decision_obj.margin_required or 0)
    notional = ps.get('notional_value', 0)
    margin_method = ps.get('margin_method', 'Broker query')

    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Instrument: {instrument} ({instrument_type})")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Method: {margin_method}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Notional Value: ${notional:,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Required: ${margin_required:,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Available Capital: ${available_capital:,.2f}")
    if margin_required > available_capital:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Check: ${margin_required:,.2f} > ${available_capital:,.2f} ✗ EXCEEDS")
    else:
        log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Check: ${margin_required:,.2f} < ${available_capital:,.2f} ✓ OK")

    # --- 6. BROKER ACCOUNT STATE (reference) ---
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- 6. BROKER ACCOUNT STATE (reference) ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Source: account-data-service (broker-reported values)")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Equity: ${account_state.get('equity', 0):,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Cash Balance: ${account_state.get('cash_balance', 0):,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Used: ${account_state.get('margin_used', 0):,.2f}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Margin Available: ${account_state.get('margin_available', 0):,.2f}")

    # --- 7. FINAL DECISION ---
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | --- 7. FINAL DECISION ---")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Decision: {decision_obj.action}")
    log_lines.append(f"SIGNAL: {signal_id} | DETAILED_MATH | Original Quantity: {signal_qty}")
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

    Supports both v2 schema (raw.legs[], decision) and v1 schema (signal_data, cerebro_decision)
    """
    signal_id = signal.get('signal_id')
    signal_store_id = signal.get('mathematricks_signal_id')  # Extract from Pub/Sub message (mongodb_watcher created this)
    decision_written = False

    # Initialize signal processing logger on first signal
    signal_logger = get_signal_processing_logger()

    # Extract raw signal data and legs based on schema version
    # CONSOLIDATED SCHEMA (v3): legs at signal.legs[] with raw data at signal.legs[].raw
    # OLD SCHEMA (v2): legs at signal.raw.legs[]

    # Try consolidated schema first: signal.legs[]
    legs_array = signal.get('legs')  # Consolidated schema

    if legs_array and isinstance(legs_array, list) and len(legs_array) > 0:
        # CONSOLIDATED SCHEMA: Extract raw data and legs from first leg that needs processing
        # Find first leg without cerebro decision (needs cerebro processing)
        current_leg = None
        for leg in legs_array:
            if not leg.get('cerebro'):  # FIX: Check 'cerebro' field, not 'decision'
                current_leg = leg
                break

        if not current_leg:
            logger.debug(f"All legs already have cerebro decisions, skipping signal {signal_id}")
            return

        # Extract raw data from the current leg
        raw_obj = current_leg.get('raw', {})
        raw_signal_id = str(raw_obj.get('_id')) if raw_obj.get('_id') else None
        raw_signal = raw_obj  # For compatibility with code that uses raw_signal
        legs = raw_obj.get('legs', [])  # The actual signal legs (BUY/SELL actions)
    else:
        # OLD SCHEMA (v2): signal.raw.legs or signal.signal_data
        raw_obj = signal.get('raw', {})
        raw_signal_id = str(raw_obj.get('_id')) if raw_obj.get('_id') else None
        raw_signal = signal.get('signal_data', signal)  # v1 compatibility
        legs = raw_obj.get('legs') or raw_signal.get('legs') or raw_signal.get('signal_legs') or raw_signal.get('signal')
    if not legs or len(legs) == 0:
        logger.error(f"❌ No legs found in signal {signal_id} - cannot process")
        decision = build_decision_v2(
            status="REJECTED",
            reason="NO_LEGS_IN_SIGNAL",
            signal=signal
        )
        update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
        return

    # Build normalized signal from first leg in raw data (for compatibility with existing code)
    # NOTE: For multi-leg signals, 'legs' array has all legs from the raw signal
    # For ENTRY signals, use first leg. For EXIT/SCALE signals, should also use first leg
    # since EXIT signals typically have only one leg in their signal_legs array
    first_leg = legs[0]

    # Get the signal-level leg_index from current_leg (for CONSOLIDATED schema)
    # Use the leg that was just processed (if available)
    signal_leg_index = 0  # default
    if 'current_leg' in locals() and current_leg:
        signal_leg_index = current_leg.get('leg_index', 0)
    elif legs_array and isinstance(legs_array, list):
        # If current_leg not available, find the most recent leg without a decision
        for leg in legs_array:
            if not leg.get('decision'):
                signal_leg_index = leg.get('leg_index', 0)
                break

    normalized_signal = {
        'signal_id': signal_id,
        'strategy_id': signal.get('strategy_id'),
        'environment': signal.get('environment'),
        'data_source': signal.get('data_source', 'mock'),  # Preserve data_source for broker adapter
        'instrument': first_leg.get('instrument'),
        'instrument_type': first_leg.get('instrument_type', 'STOCK'),
        'action': first_leg.get('action'),
        'direction': first_leg.get('direction'),
        'quantity': first_leg.get('quantity'),
        'price': first_leg.get('price'),
        'order_type': first_leg.get('order_type', 'MARKET'),
        'signal_type': raw_obj.get('signal_type') or raw_signal.get('signal_type'),
        'signal_leg_index': signal_leg_index,  # Index of this leg in the signal_store legs[] array
        'entry_signal_id': raw_obj.get('entry_signal_id') or raw_signal.get('entry_signal_id'),
        'entry_name': raw_obj.get('entry_name'),
        'exit_name': raw_obj.get('exit_name'),
        'account_equity': raw_obj.get('account_equity') or raw_signal.get('account_equity'),
        'legs': legs
    }

    # Reject if account_equity missing (required for scaling)
    if normalized_signal.get('account_equity') is None:
        logger.error(f"❌ Missing account_equity in signal {signal_id} - rejecting")
        decision = build_decision_v2(
            status="REJECTED",
            reason="MISSING_ACCOUNT_EQUITY",
            signal=signal,
            legs=legs
        )
        update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
        return

    signal_logger.info(f"Processing signal {signal_id} with Portfolio Constructor")
    if signal_store_id:
        logger.info(f"📍 Mathematricks Signal ID: {signal_store_id}")

    # Unified signal processing log
    signal_logger.info(f"SIGNAL: {signal_id} | PROCESSING | Strategy={normalized_signal.get('strategy_id')} | Instrument={normalized_signal.get('instrument')} | Action={normalized_signal.get('action')}")

    # Step 1: Check slippage rule (keep existing logic)
    if normalized_signal.get('action') == 'ENTRY' and not check_slippage_rule(normalized_signal):
        decision = build_decision_v2(
            status="REJECTED",
            reason="SLIPPAGE_EXCEEDED",
            signal=signal
        )
        update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
        logger.info(f"Signal {signal_id} rejected due to slippage")
        return

    # Step 2: Get strategy document and determine account routing
    strategy_id = signal.get('strategy_id')
    strategy_doc = get_strategy_document(strategy_id)

    if not strategy_doc:
        logger.error(f"Strategy {strategy_id} not found - rejecting signal")
        decision = build_decision_v2(
            status="REJECTED",
            reason="STRATEGY_NOT_FOUND",
            signal=signal
        )
        update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
        return

    # ============================================================================
    # MULTI-FUND ARCHITECTURE: Get active allocations for this strategy
    # ============================================================================

    active_allocations = get_active_allocations_for_strategy(strategy_id, funds_collection, portfolio_tests_collection)

    if not active_allocations:
        logger.error(f"Strategy {strategy_id} has no ACTIVE allocations - rejecting signal")
        decision = build_decision_v2(
            status="REJECTED",
            reason="NO_ACTIVE_ALLOCATIONS",
            signal=signal
        )
        update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
        return
    
    logger.info(f"📊 Found {len(active_allocations)} ACTIVE allocation(s) for strategy {strategy_id}")
    for alloc in active_allocations:
        allocations_dict = alloc.get('allocations', {})
        strategy_pct = allocations_dict.get(strategy_id, 0)
        logger.info(f"   Fund: {alloc['fund_id']} | Allocation: {alloc['allocation_name']} | Strategy %: {strategy_pct:.1f}%")
    
    # ============================================================================
    # Process signal for EACH fund allocation
    # ============================================================================
    all_fund_orders = []  # Collect all orders across all funds
    missing_accounts = False
    
    for allocation in active_allocations:
        fund_id = allocation['fund_id']
        allocation_name = allocation['allocation_name']
        allocations_dict = allocation.get('allocations', {})
        strategy_pct = allocations_dict.get(strategy_id, 0)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🏦 Processing Fund: {fund_id} | Allocation: {allocation_name}")
        logger.info(f"💰 Strategy allocation: {strategy_pct:.1f}%")
        logger.info(f"{'='*70}")
        
        # Get fund equity from MongoDB (updated by account-data-service)
        fund_doc = funds_collection.find_one({"fund_id": fund_id})
        if not fund_doc:
            logger.warning(f"⚠️ Fund {fund_id} not found in database, skipping")
            continue
            
        fund_equity = fund_doc.get('total_equity', 0.0)
        
        if fund_equity <= 0:
            logger.warning(f"⚠️ Fund {fund_id} has zero or negative equity (${fund_equity:,.2f}), skipping")
            logger.warning(f"   Make sure account-data-service is running and has polled broker accounts")
            continue
        
        # Get strategy allocation details for this fund
        fund_allocation_data = get_strategy_allocation_for_fund(
            fund_id, strategy_id,
            portfolio_allocations_collection, trading_orders_collection,
            funds_collection, trading_accounts_collection,
            portfolio_tests_collection
        )
        
        allocated_capital = fund_allocation_data['allocated_capital']
        used_capital = fund_allocation_data['used_capital']
        available_capital = fund_allocation_data['available_capital']
        
        logger.info(f"💼 Fund equity: ${fund_equity:,.2f}")
        logger.info(f"📊 Allocated to strategy: ${allocated_capital:,.2f}")
        logger.info(f"💵 Used capital: ${used_capital:,.2f}")
        logger.info(f"✅ Available capital: ${available_capital:,.2f}")
        
        if available_capital <= 0:
            logger.warning(f"⚠️ No available capital for strategy {strategy_id} in fund {fund_id}, skipping")
            continue
        
        # Get available accounts for this strategy in this fund
        # For multi-asset strategies, determine actual asset class from signal's instrument_type
        strategy_asset_class = strategy_doc.get('asset_class', 'equity')
        # Map instrument_type from signal to account asset_class
        instrument_type = normalized_signal.get('instrument_type', 'STOCK').upper()
        instrument_to_asset_map = {
            'STOCK': 'equity',
            'EQUITY': 'equity',
            'OPTION': 'options',
            'OPTIONS': 'options',
            'FUTURE': 'futures',
            'FUTURES': 'futures',
            'FOREX': 'forex',
            'CRYPTO': 'crypto'
        }
        if strategy_asset_class == 'multi-asset':
            asset_class = instrument_to_asset_map.get(instrument_type, 'equity')
            logger.info(f"🔄 Multi-asset strategy: mapped instrument_type={instrument_type} → asset_class={asset_class}")
        else:
            asset_class = strategy_asset_class
            if instrument_type in instrument_to_asset_map:
                mapped_asset_class = instrument_to_asset_map[instrument_type]
                if mapped_asset_class != 'equity' and (strategy_asset_class is None or str(strategy_asset_class).lower() == 'equity'):
                    asset_class = mapped_asset_class
                    logger.warning(
                        f"⚠️ Strategy asset_class=equity but instrument_type={instrument_type}; "
                        f"using asset_class={asset_class} for account selection"
                    )
        
        mode = signal.get('mode')  # Extract mode for account routing (mock_live, paper_live, etc.)
        
        available_accounts = get_available_accounts_for_strategy(
            strategy_id, fund_id, asset_class,
            strategies_collection, trading_accounts_collection,
            mode=mode  # Pass mode for mode-aware account selection
        )
        
        if not available_accounts:
            logger.error(f"❌ No available accounts for strategy {strategy_id} in fund {fund_id}")
            missing_accounts = True
            continue
        
        logger.info(f"🎯 Found {len(available_accounts)} available account(s):")
        for acc in available_accounts:
            logger.info(f"   • {acc['account_id']}: ${acc['equity']:,.2f} equity, ${acc['available_margin']:,.2f} margin")
        
        # Use first account for initial signal evaluation
        # (Portfolio constructor needs ONE account context to make decision)
        primary_account = available_accounts[0]
        account_name = primary_account['account_id']
        
        logger.info(f"🎯 Using primary account for signal evaluation: {account_name}")

        # Configure broker adapter for live price fetching (per-signal)
        # Both 'paper' and 'live' accounts connect to real brokers and have live prices
        data_source = normalized_signal.get('data_source', 'mock')
        price_broker_id = None
        if data_source == 'live':
            strategy_accounts = strategy_doc.get('accounts', {})
            if isinstance(strategy_accounts, dict):
                # Try live accounts first, then paper accounts (both have real prices)
                for account_type in ['live', 'paper']:
                    candidates = strategy_accounts.get(account_type, [])
                    if candidates:
                        price_broker_id = candidates[0]
                        logger.info(f"📡 Price broker for live data: {price_broker_id} (from strategy.accounts.{account_type})")
                        break
                if not price_broker_id:
                    logger.error(f"No live or paper accounts configured for strategy {strategy_id} - cannot fetch live prices")
        broker_adapter.data_source = data_source
        broker_adapter.price_broker_id = price_broker_id
        logger.info(f"📡 Broker adapter configured: data_source={data_source}, price_broker={price_broker_id}")

        account_state = get_account_state(account_name)

        if not account_state:
            logger.error(f"Failed to get account state for {account_name}")
            decision = build_decision_v2(
                status="REJECTED",
                reason="ACCOUNT_STATE_UNAVAILABLE",
                signal=signal
            )
            update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
            return

        # Step 3: Build context (raw_obj, raw_signal, legs, normalized_signal already extracted at function start)
        context = build_portfolio_context(account_state)
        
        # Step 4: Override context with fund allocation capital
        # The ratio-based sizing will use this instead of account equity
        context.account_equity = allocated_capital  # Use fund's allocation as the "account"
        context.fund_allocation = {
            'fund_id': fund_id,
            'fund_equity': fund_equity,
            'strategy_pct': strategy_pct,
            'allocated_capital': allocated_capital,
            'available_capital': available_capital
        }
        
        # Use Portfolio Constructor for ratio-based sizing (but skip optimization)
        # Just approve the signal and let ratio logic calculate proper quantity
        decision_obj = SignalDecision(
            action='APPROVED',
            quantity=0,  # Will be calculated by ratio logic below
            reason=f'Fund allocation: {strategy_pct:.2f}% = ${allocated_capital:,.2f}',
            allocated_capital=allocated_capital,
            margin_required=0.0,
            metadata={'fund_allocation': True, 'fund_id': fund_id}
        )

        # Step 4.0: Determine multi-leg status (legs already extracted at function start)
        is_multi_leg = len(legs) > 1
        if is_multi_leg:
            logger.info(f"🔀 Multi-leg signal detected: {len(legs)} legs")
            for i, leg in enumerate(legs):
                logger.info(f"   Leg {i+1}: {leg.get('instrument')} {leg.get('action')} {leg.get('direction')}")

        # Step 4a: Determine Signal Type (ENTRY/EXIT/SCALE)
        signal_type_info = position_manager.determine_signal_type(normalized_signal)

        # Step 4a.1: CANCEL SIGNAL HANDLING - Cancel pending orders
        signal_type = signal_type_info.get('signal_type')
        if signal_type == 'CANCEL':
            logger.info(f"🚫 CANCEL signal received - cancelling pending orders")

            strategy_id = normalized_signal.get('strategy_id')
            instrument = normalized_signal.get('instrument')
            entry_signal_id = normalized_signal.get('entry_signal_id')

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
                # Update signal store with CANCEL decision (v2 schema)
                decision = build_decision_v2(
                    status="CANCEL_NO_TARGET",
                    reason=f"No pending orders found to cancel for {instrument}",
                    signal=signal
                )
                update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
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

            # Update signal store with CANCEL result (v2 schema)
            decision = build_decision_v2(
                status="CANCEL_SENT",
                reason=f"Sent cancel commands for {cancelled_count} pending order(s)",
                signal=signal
            )
            decision['cancelled_orders'] = cancelled_count
            update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)

            logger.info(f"✅ CANCEL signal processed - cancelled {cancelled_count} order(s)")
            return  # Don't process CANCEL signal as a new order

        # Step 4a.2: EXIT SIGNAL HANDLING - Approve for position reconciliation by Execution Service
        if signal_type in ['EXIT', 'SCALE_OUT'] and decision_obj.action in ['APPROVED', 'RESIZE']:
            logger.info(f"🔴 EXIT signal detected - preparing for position reconciliation")

            # Find entry signal for context (but don't crash if missing - Execution will handle it)
            entry_signal_id = normalized_signal.get('entry_signal_id')
            entry_signal = None
            entry_order_ids = []

            if entry_signal_id and entry_signal_id != "$PREVIOUS":
                # Direct lookup by ObjectId - single source of truth
                logger.info(f"✅ EXIT signal has entry_signal_id (ObjectId): {entry_signal_id[:12]}...")
                try:
                    from bson import ObjectId
                    entry_signal = signal_store_collection.find_one({"_id": ObjectId(entry_signal_id)})
                    if entry_signal:
                        logger.info(f"✅ Found entry signal by ObjectId: {entry_signal.get('signal_id')}")
                        # Extract order IDs from entry signal for cancellation reference
                        for leg in entry_signal.get('legs', []):
                            execution = leg.get('execution', {})
                            for order in execution.get('orders', []):
                                entry_order_ids.append(order.get('order_id'))
                    else:
                        logger.warning(f"⚠️ entry_signal_id provided but signal not found: {entry_signal_id}")
                except Exception as e:
                    logger.error(f"❌ Error looking up entry signal: {e}")

            # Fallback to fuzzy matching if no entry_signal_id provided or lookup failed
            if not entry_signal:
                logger.info("Using fuzzy matching to find ENTRY signal (strategy/instrument/direction)")
                entry_signal = find_open_entry_signal(
                    strategy_id=normalized_signal.get('strategy_id'),
                    instrument=normalized_signal.get('instrument'),
                    direction=normalized_signal.get('direction')
                )
                if entry_signal:
                    logger.info(f"✅ Found entry signal by fuzzy match: {entry_signal.get('signal_id')}")
                    # Extract order IDs
                    for leg in entry_signal.get('legs', []):
                        execution = leg.get('execution', {})
                        for order in execution.get('orders', []):
                            entry_order_ids.append(order.get('order_id'))

            # Calculate target position based on scale_out_percentage (if provided)
            scale_out_percentage = normalized_signal.get('scale_out_percentage', 100.0)
            if scale_out_percentage <= 0 or scale_out_percentage > 100:
                logger.warning(f"⚠️ Invalid scale_out_percentage {scale_out_percentage}%, using 100%")
                scale_out_percentage = 100.0

            # For partial exits, target_position is non-zero
            # For full exits, target_position is 0
            # Execution service will query broker for current position and work toward target
            if scale_out_percentage >= 100:
                target_position = 0  # Full exit
                exit_type = 'FULL_EXIT'
                logger.info(f"🎯 Target position: 0 (FULL EXIT)")
            else:
                # We don't know current position yet - Execution will calculate it
                # Just pass the percentage to close
                target_position = None  # Will be calculated by Execution based on broker position
                exit_type = 'PARTIAL_EXIT'
                logger.info(f"🎯 Target: Close {scale_out_percentage}% of position (PARTIAL EXIT)")

            # Build EXIT approval with entry context for Execution Service
            # Execution will handle: cancel pending entries, exit filled positions, retry logic
            exit_metadata = {
                **decision_obj.metadata,
                'signal_type_info': signal_type_info,
                'entry_signal_id': str(entry_signal['_id']) if entry_signal else None,
                'entry_signal_ref': entry_signal['signal_id'] if entry_signal else None,
                'entry_order_ids': entry_order_ids,  # For cancellation reference
                'exit_type': exit_type,
                'scale_out_percentage': scale_out_percentage,
                'target_position': target_position,  # 0 for full exit, None for partial
                'is_multi_leg': is_multi_leg,
                'leg_count': len(legs) if is_multi_leg else 1,
                'requires_reconciliation': True  # Flag for Execution Service to use reconciliation engine
            }

            # For multi-leg EXIT signals, include leg details
            if is_multi_leg and legs:
                logger.info(f"🔀 Multi-leg EXIT signal: Processing {len(legs)} legs")
                exit_leg_results = []
                for leg_index, leg in enumerate(legs):
                    instrument = leg.get('instrument')
                    exit_leg_results.append({
                        'leg_index': leg_index,
                        'instrument': instrument,
                        'instrument_type': leg.get('instrument_type', 'STOCK'),
                        'direction': leg.get('direction'),
                        'action': leg.get('action'),
                        'order_type': leg.get('order_type', 'MARKET'),
                        'price_used': leg.get('price', 0)
                    })
                exit_metadata['leg_results'] = exit_leg_results

            # CRITICAL: Get actual filled quantity from ENTRY execution in MongoDB
            # This is MANDATORY - we cannot use raw signal quantity for EXIT
            actual_filled_quantity = None
            
            if entry_signal:
                entry_legs = entry_signal.get('legs', [])
                if entry_legs:
                    # Find the ENTRY leg (should be first leg)
                    entry_leg = None
                    for leg in entry_legs:
                        if leg.get('leg_type') == 'ENTRY':
                            entry_leg = leg
                            break
                    
                    if not entry_leg:
                        entry_leg = entry_legs[0]  # Fallback to first leg
                    
                    entry_execution = entry_leg.get('execution', {})
                    if entry_execution:
                        # Get total_quantity_filled from entry execution (this is the actual filled amount)
                        filled_qty = entry_execution.get('total_quantity_filled', 0)
                        if filled_qty and filled_qty > 0:
                            actual_filled_quantity = filled_qty
                            logger.info(f"✅ Retrieved actual filled quantity from ENTRY execution: {filled_qty}")
                        else:
                            logger.error(f"❌ ENTRY execution exists but total_quantity_filled is {filled_qty}")
                    else:
                        logger.error(f"❌ ENTRY leg found but no execution data")
                else:
                    logger.error(f"❌ Entry signal found but no legs data")
            else:
                logger.error(f"❌ No entry signal found - cannot determine actual filled quantity")
            
            # Use actual filled quantity or fallback to raw (with warning)
            if actual_filled_quantity:
                exit_quantity = actual_filled_quantity
                logger.info(f"📊 EXIT quantity: {exit_quantity} (from ENTRY execution)")
            else:
                exit_quantity = normalized_signal.get('quantity', 0)
                logger.warning(f"⚠️ Using raw signal quantity {exit_quantity} - ENTRY execution data not available!")
            
            decision_obj = SignalDecision(
                action="APPROVED",
                quantity=exit_quantity,
                reason=f"EXIT: Target position {target_position if target_position is not None else f'{scale_out_percentage}% close'}" +
                       (f" (entry: {entry_signal['signal_id']})" if entry_signal else " (entry lookup will be done by Execution)"),
                allocated_capital=0,
                margin_required=0,
                metadata=exit_metadata
            )

            # Log approval details
            logger.info(f"✅ EXIT signal APPROVED for position reconciliation")
            logger.info(f"   Entry Reference: {entry_signal['signal_id'] if entry_signal else 'Will be looked up by Execution'}")
            logger.info(f"   Entry Order IDs for cancel: {entry_order_ids if entry_order_ids else 'None'}")
            logger.info(f"   Scale Out: {scale_out_percentage}%")
            logger.info(f"   Target Position: {target_position if target_position is not None else 'TBD by Execution'}")
            logger.info(f"⏭️ Execution Service will handle: cancel pending entries, exit filled positions, retry up to 6 times")

        # Step 4b: Smart Position Sizing - Adjust for capital distribution (ENTRY signals only)
        elif decision_obj.action in ['APPROVED', 'RESIZE']:
            strategy_id = normalized_signal.get('strategy_id')

            # Get strategy metadata for backtest margin comparison
            strategy_meta = get_strategy_metadata(strategy_id)
            median_margin_pct = strategy_meta['median_margin_pct']

            # RATIO-BASED POSITION SIZING
            # Calculate position capital based on signal's sizing intent
            # v2: account_equity is in raw.account_equity, v1: in signal_data.account_equity
            signal_account_equity = raw_obj.get('account_equity') or raw_signal.get('account_equity')

            # Calculate signal's position value from first leg (already normalized)
            signal_price = normalized_signal.get('price', 0)
            signal_quantity = normalized_signal.get('quantity', 1)
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
                log_detailed_calculation_math(normalized_signal, context, decision_obj, account_state)
                logger.info(f"\n{'='*70}")
                logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {normalized_signal.get('instrument')}")
                logger.info(f"{'='*70}")
                logger.info(f"Strategy: {normalized_signal.get('strategy_id')}")
                logger.info(f"Action: {decision_obj.action}")
                logger.info(f"Reason: {decision_obj.reason}")
                logger.info(f"{'='*70}\n")
                update_signal_store_with_decision(signal_store_id, build_decision_v2(
                    status=decision_obj.action,
                    reason=decision_obj.reason,
                    signal=signal,
                    decision_obj=decision_obj
                ))
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
                log_detailed_calculation_math(normalized_signal, context, decision_obj, account_state)
                logger.info(f"\n{'='*70}")
                logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {normalized_signal.get('instrument')}")
                logger.info(f"{'='*70}")
                logger.info(f"Strategy: {normalized_signal.get('strategy_id')}")
                logger.info(f"Action: {decision_obj.action}")
                logger.info(f"Reason: {decision_obj.reason}")
                logger.info(f"{'='*70}\n")
                update_signal_store_with_decision(signal_store_id, build_decision_v2(
                    status=decision_obj.action,
                    reason=decision_obj.reason,
                    signal=signal,
                    decision_obj=decision_obj
                ))
                return  # Exit early

            # Get allocated capital and deployed capital
            allocated_capital = decision_obj.allocated_capital
            deployment_info = get_deployed_capital(strategy_id, account_state)
            deployed_capital = deployment_info['deployed_capital']
            open_positions = deployment_info['open_positions']
            position_count = deployment_info['position_count']

            # Calculate available capital
            allocated_capital_available = allocated_capital - deployed_capital

            # Calculate scaling ratio for quantity using FULL ALLOCATED CAPITAL (before deployment)
            # Multi-fund architecture: Each strategy gets a slice of total equity
            # Example: Strategy has $100K allocation, signal designed for $100K → scaling = 1.0
            # Example: Strategy has $200K allocation, signal designed for $100K → scaling = 2.0
            # Note: Margin validation will check if we can afford this with available capital
            broker_account_equity = account_state.get('equity', 0)  # For logging reference only
            scaling_ratio = allocated_capital / signal_account_equity

            logger.info(f"📊 Allocation: ${allocated_capital:,.2f} - ${deployed_capital:,.2f} deployed = ${allocated_capital_available:,.2f} available")
            logger.info(f"📊 Scaling ratio: ${allocated_capital:,.2f} (allocated capital) / ${signal_account_equity:,.2f} (signal equity) = {scaling_ratio:.5f}")

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
                        log_detailed_calculation_math(normalized_signal, context, decision_obj, account_state)
                        logger.info(f"\n{'='*70}")
                        logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {normalized_signal.get('instrument')}")
                        logger.info(f"{'='*70}")
                        logger.info(f"Strategy: {normalized_signal.get('strategy_id')}")
                        logger.info(f"Action: {decision_obj.action}")
                        logger.info(f"Reason: {decision_obj.reason}")
                        logger.info(f"{'='*70}\n")
                        update_signal_store_with_decision(signal_store_id, build_decision_v2(
                            status=decision_obj.action,
                            reason=decision_obj.reason,
                            signal=signal,
                            decision_obj=decision_obj
                        ))
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
                    log_detailed_calculation_math(normalized_signal, context, decision_obj, account_state)
                    logger.info(f"\n{'='*70}")
                    logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {normalized_signal.get('instrument')}")
                    logger.info(f"{'='*70}")
                    logger.info(f"Strategy: {normalized_signal.get('strategy_id')}")
                    logger.info(f"Action: {decision_obj.action}")
                    logger.info(f"Reason: {decision_obj.reason}")
                    logger.info(f"{'='*70}\n")
                    update_signal_store_with_decision(signal_store_id, build_decision_v2(
                        status=decision_obj.action,
                        reason=decision_obj.reason,
                        signal=signal,
                        decision_obj=decision_obj
                    ))
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
                        'account_state': account_state,  # For decision.math display
                        'position_sizing': {
                            'allocation_percentage': strategy_pct,  # For display in Section 3
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
        log_detailed_calculation_math(normalized_signal, context, decision_obj, account_state)

        # Log decision summary to console and cerebro_service.log
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 PORTFOLIO CONSTRUCTOR DECISION for {normalized_signal.get('instrument')}")
        logger.info(f"{'='*70}")
        logger.info(f"Strategy: {normalized_signal.get('strategy_id')}")
        logger.info(f"Action: {decision_obj.action}")
        logger.info(f"Quantity: {decision_obj.quantity:.2f}")
        logger.info(f"Reason: {decision_obj.reason}")
        if decision_obj.allocated_capital:
            logger.info(f"Allocated Capital: ${decision_obj.allocated_capital:,.2f}")
        if decision_obj.margin_required:
            logger.info(f"Margin Required: ${decision_obj.margin_required:,.2f}")
        logger.info(f"{'='*70}")

        # Unified signal processing log for decision
        logger.info(f"SIGNAL: {signal_id} | DECISION | Action={decision_obj.action} | OrigQty={normalized_signal.get('quantity', 0)} | FinalQty={decision_obj.quantity} | Reason={decision_obj.reason}")

        # Step 6: If approved or resized, distribute capital across accounts and create orders
        if decision_obj.action in ['APPROVED', 'RESIZE']:
            # Get leg_results from metadata (for ENTRY signals with multi-leg calculation)
            # For EXIT signals or single-leg, fall back to creating from primary signal
            leg_results = decision_obj.metadata.get('leg_results', [])

            if not leg_results:
                # No leg_results (EXIT signal or legacy) - create single order from primary signal
                instrument_type = normalized_signal.get('instrument_type', 'STOCK')
                final_quantity_rounded = round_quantity_for_instrument(decision_obj.quantity, instrument_type)
                if final_quantity_rounded <= 0:
                    logger.warning(f"Rounded quantity is 0, rejecting signal")
                    continue  # Skip this fund, try next one

                # Determine price: fetch live if data_source='live', else use signal price
                if data_source == 'live':
                    order_price = broker_adapter.fetch_live_price(
                        normalized_signal.get('instrument'),
                        instrument_type
                    )
                    logger.info(f"📈 EXIT/single-leg: live price ${order_price} (signal price was ${normalized_signal.get('price')})")
                else:
                    order_price = normalized_signal.get('price')
                    if not order_price or order_price <= 0:
                        raise ValueError(f"No price available in signal for {normalized_signal.get('instrument')}")

                leg_results = [{
                    'leg_index': 0,
                    'instrument': normalized_signal.get('instrument'),
                    'instrument_type': instrument_type,
                    'direction': normalized_signal.get('direction'),
                    'action': normalized_signal.get('action'),
                    'order_type': normalized_signal.get('order_type', 'MARKET'),
                    'quantity': final_quantity_rounded,
                    'price_used': order_price
                }]

            # ============================================================================
            # MULTI-ACCOUNT DISTRIBUTION: Distribute capital across available accounts
            # ============================================================================

            # Calculate target capital from decision
            # Use price from leg_results (properly extracted), not signal top-level
            price_from_legs = leg_results[0].get('price_used', 1.0) if leg_results else 1.0
            target_capital = decision_obj.quantity * price_from_legs
        
            # Distribute capital across accounts proportionally by available margin
            account_allocations = distribute_capital_across_accounts(target_capital, available_accounts)
        
            logger.info(f"💰 Distributing ${target_capital:,.2f} across {len(account_allocations)} account(s):")
            for alloc in account_allocations:
                logger.info(f"   • {alloc['account_id']}: ${alloc['allocated_capital']:,.2f}")
        
            # Create orders for each account × each leg
            orders_created = []
            
            # Pre-allocate quantities for each leg across all accounts to ensure sum matches total
            leg_account_quantities = {}
            for leg_result in leg_results:
                leg_index = leg_result.get('leg_index', 0)
                leg_base_quantity = leg_result.get('quantity', 0)  # Keep as float for crypto/forex
                leg_instrument_type = leg_result.get('instrument_type', 'STOCK')
                
                # Use proper allocation function to distribute quantities
                allocated_quantities = allocate_quantity_across_accounts(
                    total_quantity=leg_base_quantity,
                    account_allocations=account_allocations,
                    target_capital=target_capital,
                    instrument_type=leg_instrument_type
                )
                leg_account_quantities[leg_index] = allocated_quantities
            
            # Update cerebro.created_orders with broker and account-specific details
            # This enriches the orders with execution-specific information
            enriched_orders = []
            for account_idx, account_alloc in enumerate(account_allocations):
                target_account_name = account_alloc['account_id']
                account_broker = account_alloc.get('broker', 'Unknown')
                account_capital = account_alloc['allocated_capital']
                
                for leg_result in leg_results:
                    leg_index = leg_result.get('leg_index', 0)
                    leg_quantity = leg_account_quantities[leg_index][account_idx]
                    leg_instrument_type = leg_result.get('instrument_type', 'STOCK')
                    
                    if leg_quantity > 0:
                        # Preserve fractional quantities for crypto/forex/stock
                        if leg_instrument_type in ['CRYPTO', 'FOREX', 'STOCK']:
                            final_quantity = leg_quantity  # Keep as float
                        else:
                            final_quantity = int(leg_quantity)  # Integer contracts for options/futures
                        
                        enriched_orders.append({
                            "instrument": leg_result.get('instrument'),
                            "instrument_type": leg_instrument_type,
                            "action": leg_result.get('action'),
                            "direction": leg_result.get('direction'),
                            "quantity": final_quantity,
                            "order_type": leg_result.get('order_type', 'MARKET'),
                            "price": leg_result.get('price_used', 0),
                            "margin_required": leg_result.get('initial_margin', 0) * (account_capital / target_capital) if target_capital > 0 else 0,
                            "broker": account_broker,  # ✅ Broker field included
                            "account_id": target_account_name,
                            "fund_id": fund_id,
                            "allocated_capital": account_capital,
                            "data_source": normalized_signal.get('data_source', 'mock'),  # ✅ For price enrichment
                            "legs": leg_result.get('legs') if leg_result.get('legs') else None
                        })
            
            # Build complete cerebro document with enriched orders
            decision_doc = build_decision_v2(
                status=decision_obj.action,
                reason=decision_obj.reason,
                signal=signal,
                decision_obj=decision_obj,
                legs=legs  # Pass legs explicitly so raw_qty can be extracted
            )
            
            # Replace created_orders with enriched version that includes broker/account info
            decision_doc["created_orders"] = enriched_orders
            
            # Update signal_store with COMPLETE cerebro document
            update_signal_store_with_decision(signal_store_id, decision_doc, raw_signal_id)
            decision_written = True
            logger.info(f"✅ Updated signal_store with cerebro including {len(enriched_orders)} enriched order(s) with broker info")
            
            # Now create and send trading orders to execution service
            
            for account_idx, account_alloc in enumerate(account_allocations):
                target_account_name = account_alloc['account_id']
                account_capital = account_alloc['allocated_capital']
                account_broker = account_alloc.get('broker', 'Unknown')

                for leg_result in leg_results:
                    leg_index = leg_result.get('leg_index', 0)
                    leg_instrument_type = leg_result.get('instrument_type', 'STOCK')

                    # Get pre-allocated quantity for this account and leg
                    leg_quantity = leg_account_quantities[leg_index][account_idx]

                    if leg_quantity <= 0:
                        logger.warning(f"Leg {leg_index+1} quantity is 0 for account {target_account_name}, skipping")
                        continue

                    # Generate unique order ID: signal_fund_account_signalleg_tradingleg
                    # IMPORTANT: Include signal_leg_index to differentiate ENTRY/EXIT orders for same signal
                    signal_leg_idx = normalized_signal.get('signal_leg_index', 0)
                    if len(leg_results) > 1:
                        order_id = f"{signal_id}_{fund_id}_{target_account_name}_SL{signal_leg_idx}_TL{leg_index}_ORD"
                    else:
                        order_id = f"{signal_id}_{fund_id}_{target_account_name}_SL{signal_leg_idx}_ORD"

                    # Get optional fields from raw_obj (v2) or first_leg (already in normalized)
                    first_leg = legs[0] if legs else {}

                    # For EXIT signals, determine the closing action
                    signal_type = normalized_signal.get('signal_type')
                    order_direction = leg_result.get('direction')
                    order_action = leg_result.get('action')

                    # For EXIT signals, set action to close the position
                    if signal_type in ['EXIT', 'SCALE_OUT']:
                        # If direction is LONG, we SELL to close
                        # If direction is SHORT, we BUY_TO_COVER to close
                        if order_direction == 'LONG':
                            order_action = 'SELL'
                        elif order_direction == 'SHORT':
                            order_action = 'BUY_TO_COVER'

                    # Conditional quantity conversion: preserve fractional for crypto/forex/stock, int for options/futures
                    if leg_instrument_type in ['CRYPTO', 'FOREX', 'STOCK']:
                        execution_quantity = leg_quantity  # Keep fractional (e.g., 0.5 BTC)
                    else:
                        execution_quantity = int(leg_quantity)  # Integer for contracts (options/futures)
                    
                    trading_order = {
                        "order_id": order_id,
                        "signal_id": signal_id,
                        "mathematricks_signal_id": signal_store_id,  # For execution_service to update signal_store
                        "raw_signal_mongodb_id": normalized_signal.get('raw_signal_mongodb_id'),  # To match leg in signal_store
                        "strategy_id": normalized_signal.get('strategy_id'),
                        "fund_id": fund_id,  # NEW: Fund architecture support
                        "account_id": target_account_name,  # NEW: Renamed from "account"
                        "account": target_account_name,  # DEPRECATED: Keep for backward compatibility
                        "broker": account_broker,  # Broker name (Mock, IBKR, Coinbase, etc.)
                        "timestamp": datetime.utcnow().isoformat(),  # Convert to ISO string for JSON
                        "instrument": leg_result.get('instrument'),
                        "direction": order_direction,
                        "action": order_action,
                        "signal_type": signal_type,  # ENTRY or EXIT (for execution service)
                        "side": "SELL" if signal_type in ['EXIT', 'SCALE_OUT'] else "BUY",  # Explicit side for execution service
                        "order_type": leg_result.get('order_type', 'MARKET'),
                        "price": leg_result.get('price_used', 0),
                        "quantity": execution_quantity,  # Fractional for crypto/forex/stock, integer for options/futures
                        "stop_loss": first_leg.get('stop_loss'),
                        "take_profit": first_leg.get('take_profit'),
                        "expiry": first_leg.get('expiry'),
                        # Multi-asset support: pass through instrument_type and related fields
                        "instrument_type": leg_result.get('instrument_type', 'STOCK'),
                        # For options, underlying is the instrument (SPY); for futures, use exchange
                        "underlying": leg_result.get('instrument') if leg_result.get('instrument_type') == 'OPTION' else first_leg.get('underlying'),
                        "exchange": first_leg.get('exchange'),  # For futures
                        # If this leg (or the raw first_leg) includes nested option legs,
                        # pass them through so execution service and brokers can construct
                        # complex OPTION contracts (IBKR requires a `legs` list).
                        "legs": leg_result.get('legs') or first_leg.get('legs'),
                        # Multi-leg metadata
                        "leg_index": leg_index,
                        "total_legs": len(leg_results),
                        "is_multi_leg": len(leg_results) > 1,
                        # Multi-fund metadata
                        "allocation_name": allocation_name,
                        "account_allocated_capital": account_capital,
                        "cerebro_decision": {
                            "allocated_capital": account_capital,
                            "margin_required": leg_result.get('initial_margin', decision_obj.margin_required * (account_capital / target_capital) if target_capital > 0 else 0),
                            "position_size_logic": "PortfolioConstructor:MaxCAGR:MultiFund",
                            "risk_metrics": {k: v for k, v in decision_obj.metadata.items() if k != 'leg_results'}  # Exclude leg_results to reduce size
                        },
                        "environment": normalized_signal.get('environment', 'staging'),
                        "data_source": normalized_signal.get('data_source', 'mock'),  # For broker adapter selection
                        "status": "PENDING",
                        "created_at": datetime.utcnow().isoformat()  # Convert to ISO string for JSON
                    }

                    # For EXIT signals, add entry_signal_id reference (MongoDB ObjectId)
                    if decision_obj.metadata.get('entry_signal_id'):
                        trading_order['entry_signal_id'] = decision_obj.metadata['entry_signal_id']
                        # Note: entry_signal_ref removed - execution service doesn't use it

                    # NOTE: trading_orders collection REMOVED
                    # Order data is now stored directly in signal_store legs by execution_service
                    # trading_orders_collection.insert_one(trading_order)  # REMOVED
                    
                    all_fund_orders.append(order_id)
                    orders_created.append(order_id)
                    logger.info(f"✅ Trading order prepared: {order_id} for {leg_quantity} {leg_result.get('instrument')} in account {target_account_name}")

                    # ============================================================
                    # CALL EXECUTION API (Direct API call with full order data)
                    # ============================================================
                    try:
                        execution_url = os.getenv('EXECUTION_SERVICE_URL', 'http://execution-service:8083')
                        api_endpoint = f"{execution_url}/api/v1/execute-order"
                        
                        # Pass full order data to execution service
                        payload = trading_order
                        
                        logger.info(f"📤 Calling Execution API: {api_endpoint}")
                        logger.info(f"   📋 CEREBRO → EXECUTION ORDER SUMMARY:")
                        logger.info(f"   order_id: {payload.get('order_id')}")
                        logger.info(f"   instrument: {payload.get('instrument')} ({payload.get('instrument_type')})")
                        logger.info(f"   action: {payload.get('action')} | direction: {payload.get('direction')}")
                        logger.info(f"   quantity: {payload.get('quantity')}")
                        logger.info(f"   price: ${payload.get('price')} (data_source={payload.get('data_source')})")
                        logger.info(f"   account_id: {payload.get('account_id')}")
                        logger.info(f"   fund_id: {payload.get('fund_id')}")
                        logger.info(f"   Full payload: {payload}")
                        
                        response = requests.post(
                            api_endpoint,
                            json=payload,
                            timeout=30  # 30 second timeout
                        )
                        
                        response.raise_for_status()
                        result = response.json()
                        
                        logger.info(f"✅ Execution API response: {result.get('status')} - {result.get('message')}")
                        
                    except requests.exceptions.RequestException as e:
                        logger.error(f"❌ Failed to call Execution API for order {order_id}: {str(e)}")
                        if hasattr(e, 'response') and e.response is not None:
                            logger.error(f"   Response body: {e.response.text}")
                        logger.error(f"   Order may not execute automatically!")
                        # Don't raise - can be manually re-triggered
                    except Exception as e:
                        logger.error(f"❌ Unexpected error calling Execution API: {str(e)}", exc_info=True)

                    # Pub/Sub removed - execution service watches MongoDB Change Streams
                    # Unified signal processing log for order creation
                    logger.info(f"SIGNAL: {signal_id} | ORDER_CREATED | FundID={fund_id} | AccountID={target_account_name} | OrderID={order_id} | Quantity={leg_quantity} | Instrument={leg_result.get('instrument')} | Direction={leg_result.get('direction')}")

            # Summary log for this fund
            if len(orders_created) > 0:
                logger.info(f"✅ Created {len(orders_created)} order(s) for fund {fund_id}")
            logger.info(f"{'='*70}\n")
        
        else:
            # REJECTED signal - save decision to signal_store
            decision_doc = build_decision_v2(
                status=decision_obj.action,
                reason=decision_obj.reason,
                signal=signal,
                decision_obj=decision_obj,
                legs=legs
            )
            update_signal_store_with_decision(signal_store_id, decision_doc, raw_signal_id)
            decision_written = True
            logger.info(f"✅ Saved REJECTED decision to signal_store")
    
        # ============================================================================
    # Summary: All funds processed
    # ============================================================================
    if len(all_fund_orders) > 0:
        logger.info(f"🎉 Signal {signal_id} processed successfully across {len(active_allocations)} fund(s)")
        logger.info(f"📦 Total orders created: {len(all_fund_orders)}")
    else:
        logger.warning(f"⚠️ Signal {signal_id} processed but no orders created")
        if not decision_written:
            reason = "NO_AVAILABLE_ACCOUNTS" if missing_accounts else "NO_ORDERS_CREATED"
            decision = build_decision_v2(
                status="REJECTED",
                reason=reason,
                signal=signal,
                legs=legs
            )
            update_signal_store_with_decision(signal_store_id, decision, raw_signal_id)
    logger.info("-" * 50)


# ============================================================================
# FASTAPI HTTP SERVER (Replaces Change Stream Watcher)
# ============================================================================

# Pydantic models for API requests
class ProcessSignalRequest(BaseModel):
    signal_store_id: str
    leg_index: int = 0

class ProcessSignalResponse(BaseModel):
    status: str
    signal_id: str
    message: str
    orders_created: Optional[list] = None

# Create FastAPI app
app = FastAPI(title="Cerebro Service", version="1.0")

# Service health status
service_status = {
    'ready': False,
    'signals_processed': 0,
    'last_signal_time': None
}

@app.get('/health')
def health_check():
    """Health check endpoint"""
    if service_status['ready']:
        return {
            'status': 'healthy',
            'ready': True,
            **service_status
        }
    else:
        return JSONResponse(
            status_code=503,
            content={
                'status': 'starting',
                'ready': False,
                **service_status
            }
        )

@app.get('/status')
def status_check():
    """Detailed status endpoint"""
    return {
        **service_status,
        'portfolio_constructor_initialized': portfolio_constructor is not None
    }

@app.post('/api/v1/process-signal', response_model=ProcessSignalResponse)
def process_signal_endpoint(request: ProcessSignalRequest):
    """
    Process a signal from signal_store collection.
    Called by signal_ingestion after adding a leg to signal_store.
    
    IMPORTANT: Responds immediately, processes in background thread.
    This prevents blocking signal_ingestion from sending more signals.
    
    Args:
        signal_store_id: MongoDB ObjectId of the signal_store document
        leg_index: Index of the leg that was just added (0 for ENTRY, 1+ for EXIT/SCALE)
    
    Returns:
        ProcessSignalResponse with status (processing started)
    """
    try:
        from bson import ObjectId
        
        logger.info(f"📥 API Request: Process signal {request.signal_store_id}, leg {request.leg_index}")
        
        # Quick validation - just check signal exists
        signal_data = signal_store_collection.find_one({'_id': ObjectId(request.signal_store_id)}, {'signal_id': 1})
        
        if not signal_data:
            logger.error(f"❌ Signal document {request.signal_store_id} not found")
            raise HTTPException(status_code=404, detail=f"Signal {request.signal_store_id} not found")
        
        signal_id = signal_data.get('signal_id', 'UNKNOWN')
        
        # Start processing in background thread - respond immediately
        def process_in_background():
            try:
                # Re-fetch full document in background thread
                signal_data_full = signal_store_collection.find_one({'_id': ObjectId(request.signal_store_id)})
                if signal_data_full:
                    signal_data_full['mathematricks_signal_id'] = str(signal_data_full['_id'])
                    logger.info(f"Processing signal: {signal_id}")
                    process_signal_with_constructor(signal_data_full)
                    service_status['signals_processed'] += 1
                    service_status['last_signal_time'] = datetime.utcnow().isoformat()
                    logger.info(f"✅ Background processing complete for {signal_id}")
            except Exception as e:
                logger.error(f"🚨 ERROR in background processing for {signal_id}: {str(e)}", exc_info=True)
        
        # Start background thread
        background_thread = threading.Thread(target=process_in_background, daemon=True)
        background_thread.start()
        
        # Respond immediately
        return ProcessSignalResponse(
            status="accepted",
            signal_id=signal_id,
            message=f"Signal {signal_id} accepted for processing"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🚨 ERROR accepting signal {request.signal_store_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error accepting signal: {str(e)}")

def run_fastapi_server():
    """Run FastAPI server (blocking)"""
    logger.info("Starting Cerebro FastAPI server on port 8082...")
    uvicorn.run(app, host='0.0.0.0', port=8082, log_level='info')


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting Cerebro Service (HTTP API)")
    logger.info("Architecture: Direct API calls (no Change Streams)")
    logger.info("Signal flow: signal_ingestion → HTTP POST → cerebro → HTTP POST → execution")

    # Initialize portfolio constructor
    initialize_portfolio_constructor()

    # Load allocations
    reload_allocations()
    
    # Mark service as ready
    service_status['ready'] = True
    logger.info("✅ Cerebro Service ready")

    # Start FastAPI HTTP server (BLOCKS)
    run_fastapi_server()
