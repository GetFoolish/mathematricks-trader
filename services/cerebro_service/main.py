"""
Cerebro Service - MVP
The intelligent core for portfolio management, risk assessment, and position sizing.
Implements hard margin limits and basic position sizing for MVP.
"""
import os
import logging
import json
import subprocess
import glob
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
import pandas as pd
import numpy as np

# Portfolio constructor imports
from portfolio_constructor.base import PortfolioConstructor
from portfolio_constructor.context import (
    PortfolioContext, Signal, SignalDecision, Position, Order
)
from portfolio_constructor.max_cagr.strategy import MaxCAGRConstructor
from portfolio_constructor.max_hybrid.strategy import MaxHybridConstructor

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

# Initialize FastAPI
app = FastAPI(title="Cerebro Service", version="1.0.0-MVP")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs/cerebro_service.log'),
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
trading_orders_collection = db['trading_orders']
cerebro_decisions_collection = db['cerebro_decisions']
standardized_signals_collection = db['standardized_signals']
portfolio_allocations_collection = db['portfolio_allocations']
strategies_collection = db['strategies']

# NEW: Collections for Allocations Page
current_allocation_collection = db['current_allocation']  # Part 1: Single document with current allocation
portfolio_tests_collection = db['portfolio_tests']  # Part 3: List of test runs

# Initialize Google Cloud Pub/Sub
project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
subscriber = pubsub_v1.SubscriberClient()
publisher = pubsub_v1.PublisherClient()

signals_subscription = subscriber.subscription_path(project_id, 'standardized-signals-sub')
trading_orders_topic = publisher.topic_path(project_id, 'trading-orders')

# AccountDataService URL
ACCOUNT_DATA_SERVICE_URL = os.getenv('ACCOUNT_DATA_SERVICE_URL', 'http://localhost:8002')

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


def load_strategy_histories_from_mongodb() -> Dict[str, pd.DataFrame]:
    """
    Load strategy backtest equity curves from MongoDB.
    
    Returns:
        Dict mapping strategy_id to DataFrame with returns
    """
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
# REST API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "cerebro_service",
        "version": "1.0.0-MVP",
        "allocations_loaded": len(ACTIVE_ALLOCATIONS) > 0,
        "strategies_count": len(ACTIVE_ALLOCATIONS)
    }


@app.post("/api/v1/reload-allocations")
async def api_reload_allocations():
    """
    Reload portfolio allocations from MongoDB
    Called by AccountDataService after approving new allocations
    """
    try:
        logger.info("API request: reloading portfolio allocations")
        reload_allocations()

        with ALLOCATIONS_LOCK:
            allocations_snapshot = dict(ACTIVE_ALLOCATIONS)

        return {
            "status": "success",
            "message": "Portfolio allocations reloaded",
            "strategies_count": len(allocations_snapshot),
            "allocations": allocations_snapshot
        }

    except Exception as e:
        logger.error(f"Error reloading allocations: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/v1/allocations")
async def get_allocations():
    """
    Get current active allocations
    """
    with ALLOCATIONS_LOCK:
        allocations_snapshot = dict(ACTIVE_ALLOCATIONS)

    return {
        "status": "success",
        "strategies_count": len(allocations_snapshot),
        "total_allocation_pct": sum(allocations_snapshot.values()),
        "allocations": allocations_snapshot
    }


# ============================================================================
# SIGNAL PROCESSING
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
    if isinstance(timestamp_str, str) and timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str[:-1] + '+00:00'
    
    return Signal(
        signal_id=signal_dict.get('signal_id'),
        strategy_id=signal_dict.get('strategy_id'),
        timestamp=signal_dict.get('timestamp') if isinstance(signal_dict.get('timestamp'), datetime) 
                  else datetime.fromisoformat(timestamp_str),
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


def process_signal_with_constructor(signal: Dict[str, Any]):
    """
    Process signal using Portfolio Constructor (NEW APPROACH)
    """
    signal_id = signal.get('signal_id')
    logger.info(f"Processing signal {signal_id} with Portfolio Constructor")

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
    
    # Log decision
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
        except Exception as e:
            logger.error(f"Failed to publish order to Pub/Sub: {str(e)}")

    # Update signal as processed
    standardized_signals_collection.update_one(
        {"signal_id": signal_id},
        {"$set": {"processed_by_cerebro": True}}
    )


def calculate_position_size(signal: Dict[str, Any], account_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate position size based on portfolio allocation and risk limits
    Uses strategy-specific allocation from ACTIVE portfolio allocation
    
    LEGACY FUNCTION - Kept for backwards compatibility
    New code should use process_signal_with_constructor() instead
    """
    strategy_id = signal.get('strategy_id')
    account_equity = account_state.get('equity', 0)
    margin_used = account_state.get('margin_used', 0)
    margin_available = account_state.get('margin_available', 0)

    logger.info(f"\n{'='*70}")
    logger.info(f"📊 POSITION SIZING CALCULATION for {signal.get('instrument')}")
    logger.info(f"{'='*70}")
    logger.info(f"Strategy: {strategy_id}")
    logger.info(f"Account State:")
    logger.info(f"  • Equity: ${account_equity:,.2f}")
    logger.info(f"  • Margin Used: ${margin_used:,.2f}")
    logger.info(f"  • Margin Available: ${margin_available:,.2f}")

    # Calculate current margin utilization
    current_margin_util_pct = (margin_used / account_equity * 100) if account_equity > 0 else 100
    logger.info(f"  • Current Margin Utilization: {current_margin_util_pct:.2f}%")

    # Check hard margin limit
    if current_margin_util_pct >= MVP_CONFIG['max_margin_utilization_pct']:
        logger.warning(f"❌ Margin utilization {current_margin_util_pct:.1f}% exceeds limit {MVP_CONFIG['max_margin_utilization_pct']}%")
        logger.info(f"{'='*70}\n")
        return {
            "approved": False,
            "reason": "MARGIN_LIMIT_EXCEEDED",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "margin_required": 0
        }

    # Get strategy allocation from active portfolio
    with ALLOCATIONS_LOCK:
        strategy_allocation_pct = ACTIVE_ALLOCATIONS.get(strategy_id, 0)

    # If no allocation, check if we should reject or use default
    if strategy_allocation_pct == 0:
        logger.warning(f"⚠️  No allocation found for strategy {strategy_id}")
        logger.warning(f"   Using fallback: {MVP_CONFIG['default_position_size_pct']}% default allocation")
        strategy_allocation_pct = MVP_CONFIG['default_position_size_pct']

    # Calculate position size based on strategy allocation
    allocated_capital = account_equity * (strategy_allocation_pct / 100)
    logger.info(f"\nPortfolio Allocation:")
    logger.info(f"  • Strategy Allocation: {strategy_allocation_pct:.2f}% of portfolio")
    logger.info(f"  • Allocated Capital: ${account_equity:,.2f} × {strategy_allocation_pct:.2f}% = ${allocated_capital:,.2f}")

    # Calculate quantity based on price and allocated capital
    signal_price = signal.get('price', 0)
    if signal_price <= 0:
        logger.error(f"❌ Invalid price {signal_price} for signal {signal['signal_id']}")
        logger.info(f"{'='*70}\n")
        return {
            "approved": False,
            "reason": "INVALID_PRICE",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "margin_required": 0
        }

    # Simplified quantity calculation (full implementation would consider instrument type, margin requirements)
    final_quantity = allocated_capital / signal_price
    logger.info(f"\nQuantity Calculation:")
    logger.info(f"  • Price per share: ${signal_price:.2f}")
    logger.info(f"  • Quantity: ${allocated_capital:,.2f} / ${signal_price:.2f} = {final_quantity:.2f} shares")

    # Estimate margin required (simplified: assume 50% margin requirement for stocks, 100% for futures)
    # In full implementation, would query broker API for exact margin requirements
    estimated_margin = allocated_capital * 0.5
    logger.info(f"\nMargin Requirements:")
    logger.info(f"  • Margin Requirement: 50% (stocks)")
    logger.info(f"  • Margin Required: ${allocated_capital:,.2f} × 0.5 = ${estimated_margin:,.2f}")

    # Check if we have enough available margin
    margin_after = margin_used + estimated_margin
    margin_util_after = (margin_after / account_equity * 100) if account_equity > 0 else 100
    logger.info(f"\nMargin Check:")
    logger.info(f"  • Current Margin Used: ${margin_used:,.2f}")
    logger.info(f"  • New Position Margin: ${estimated_margin:,.2f}")
    logger.info(f"  • Total Margin After: ${margin_after:,.2f}")
    logger.info(f"  • Margin Utilization After: {margin_util_after:.2f}%")
    logger.info(f"  • Max Allowed: {MVP_CONFIG['max_margin_utilization_pct']}%")

    if margin_util_after > MVP_CONFIG['max_margin_utilization_pct']:
        logger.info(f"\n⚠️  Position too large, reducing to fit margin limit...")
        # Reduce position size to fit within margin limit
        max_additional_margin = (MVP_CONFIG['max_margin_utilization_pct'] / 100 * account_equity) - margin_used
        if max_additional_margin <= 0:
            logger.warning(f"❌ Insufficient margin available")
            logger.info(f"{'='*70}\n")
            return {
                "approved": False,
                "reason": "INSUFFICIENT_MARGIN",
                "original_quantity": signal.get('quantity', 0),
                "final_quantity": 0,
                "margin_required": 0
            }

        # Reduce quantity proportionally
        reduction_factor = max_additional_margin / estimated_margin
        logger.info(f"  • Reduction Factor: {reduction_factor:.2%}")
        final_quantity = final_quantity * reduction_factor
        estimated_margin = max_additional_margin
        logger.info(f"  • Reduced Quantity: {final_quantity:.2f} shares")
        logger.info(f"  • Reduced Margin: ${estimated_margin:,.2f}")

    logger.info(f"\n✅ DECISION: APPROVED")
    logger.info(f"  • Final Quantity: {final_quantity:.2f} shares")
    logger.info(f"  • Capital Allocated: ${allocated_capital:,.2f}")
    logger.info(f"  • Margin Required: ${estimated_margin:,.2f}")
    logger.info(f"  • Final Margin Utilization: {margin_util_after:.2f}%")
    logger.info(f"{'='*70}\n")

    return {
        "approved": True,
        "reason": "APPROVED",
        "original_quantity": signal.get('quantity', 0),
        "final_quantity": final_quantity,
        "margin_required": estimated_margin,
        "allocated_capital": allocated_capital,
        "margin_utilization_before_pct": current_margin_util_pct,
        "margin_utilization_after_pct": margin_util_after
    }


def process_signal(signal: Dict[str, Any]):
    """
    Main signal processing logic
    """
    signal_id = signal.get('signal_id')
    logger.info(f"Processing signal {signal_id}")

    # Step 1: Check slippage rule
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

    # Step 3: Calculate position size
    sizing_result = calculate_position_size(signal, account_state)

    # Get strategy allocation for summary
    with ALLOCATIONS_LOCK:
        strat_alloc = ACTIVE_ALLOCATIONS.get(signal.get('strategy_id'), 0)

    # Log single-line position sizing summary
    logger.info(f"🎯 CEREBRO DECISION | Signal: {signal_id} | Strategy: {signal.get('strategy_id')} | Symbol: {signal.get('instrument')} | Action: {signal.get('action')} | "
                f"Allocation: {strat_alloc:.2f}% | Position Size: {sizing_result.get('final_quantity', 0):.2f} shares | Price: ${signal.get('price', 0):.2f} | "
                f"Capital: ${sizing_result.get('allocated_capital', 0):,.0f} | Margin: {sizing_result.get('margin_utilization_after_pct', 0):.1f}% | "
                f"Decision: {sizing_result['reason']}")

    # Step 4: Create decision record
    decision = {
        "signal_id": signal_id,
        "decision": "APPROVED" if sizing_result['approved'] else "REJECTED",
        "timestamp": datetime.utcnow(),
        "reason": sizing_result['reason'],
        "original_quantity": sizing_result['original_quantity'],
        "final_quantity": sizing_result['final_quantity'],
        "risk_assessment": {
            "margin_required": sizing_result.get('margin_required', 0),
            "allocated_capital": sizing_result.get('allocated_capital', 0),
            "margin_utilization_before_pct": sizing_result.get('margin_utilization_before_pct', 0),
            "margin_utilization_after_pct": sizing_result.get('margin_utilization_after_pct', 0)
        },
        "created_at": datetime.utcnow()
    }
    cerebro_decisions_collection.insert_one(decision)

    # Step 5: If approved, create trading order
    if sizing_result['approved']:
        # Generate order ID based on signal ID: {signal_id}_ORD
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
            "quantity": sizing_result['final_quantity'],
            "stop_loss": signal.get('stop_loss'),
            "take_profit": signal.get('take_profit'),
            "expiry": signal.get('expiry'),
            "cerebro_decision": decision,
            "status": "PENDING",
            "created_at": datetime.utcnow()
        }

        # Save to database
        trading_orders_collection.insert_one(trading_order)

        # Publish to Pub/Sub for ExecutionService
        message_data = json.dumps(trading_order, default=str).encode('utf-8')
        future = publisher.publish(trading_orders_topic, message_data)
        message_id = future.result()

        logger.info(f"Published trading order {order_id} for signal {signal_id}: {message_id}")
    else:
        logger.info(f"Signal {signal_id} rejected: {sizing_result['reason']}")


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
        logger.error(f"Error processing signal: {str(e)}", exc_info=True)
        message.nack()


def start_signal_subscriber():
    """
    Start Pub/Sub subscriber for signals
    """
    streaming_pull_future = subscriber.subscribe(signals_subscription, callback=signals_callback)
    logger.info("CerebroService listening for signals...")

    try:
        streaming_pull_future.result()
    except Exception as e:
        logger.error(f"Subscriber error: {str(e)}")
        streaming_pull_future.cancel()


# ============================================================================
# STRATEGY MANAGEMENT APIs
# ============================================================================

@app.get("/api/v1/strategies")
async def get_all_strategies():
    """
    Get all strategy configurations from unified strategies collection
    Returns list of all strategies with metadata and backtest data
    """
    try:
        strategies = list(strategies_collection.find({}))

        # Remove MongoDB _id
        for strategy in strategies:
            strategy.pop('_id', None)

        return {
            "status": "success",
            "count": len(strategies),
            "strategies": strategies
        }

    except Exception as e:
        logger.error(f"Error fetching strategies: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """
    Get single strategy configuration
    Includes backtest data (stored in same document in unified collection)
    """
    try:
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})

        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Remove MongoDB _id
        strategy.pop('_id', None)

        return {
            "status": "success",
            "strategy": strategy
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching strategy {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies")
async def create_strategy(strategy_data: Dict[str, Any]):
    """
    Create new strategy configuration in unified strategies collection
    Validates required fields and saves to MongoDB
    """
    try:
        # Validate required fields
        required_fields = ['strategy_id', 'name', 'asset_class', 'instruments']
        for field in required_fields:
            if field not in strategy_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        strategy_id = strategy_data['strategy_id']

        # Check if strategy already exists
        existing = strategies_collection.find_one({"strategy_id": strategy_id})
        if existing:
            raise HTTPException(status_code=409, detail=f"Strategy {strategy_id} already exists")

        # Add timestamps
        strategy_data['created_at'] = datetime.utcnow()
        strategy_data['updated_at'] = datetime.utcnow()
        strategy_data['status'] = strategy_data.get('status', 'ACTIVE')

        # Insert into MongoDB
        strategies_collection.insert_one(strategy_data)

        logger.info(f"✅ Created strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy {strategy_id} created",
            "strategy_id": strategy_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating strategy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, updates: Dict[str, Any]):
    """
    Update strategy configuration in unified strategies collection
    Allows partial updates of strategy fields
    """
    try:
        # Check if strategy exists
        existing = strategies_collection.find_one({"strategy_id": strategy_id})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Add updated timestamp
        updates['updated_at'] = datetime.utcnow()

        # Update in MongoDB
        result = strategies_collection.update_one(
            {"strategy_id": strategy_id},
            {"$set": updates}
        )

        if result.modified_count == 0:
            logger.warning(f"No changes made to strategy {strategy_id}")

        logger.info(f"✅ Updated strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy {strategy_id} updated",
            "strategy_id": strategy_id,
            "modified_count": result.modified_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """
    Delete strategy configuration (soft delete)
    Marks as INACTIVE instead of hard delete
    """
    try:
        # Check if strategy exists
        existing = strategies_collection.find_one({"strategy_id": strategy_id})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Soft delete - mark as INACTIVE
        result = strategies_collection.update_one(
            {"strategy_id": strategy_id},
            {
                "$set": {
                    "status": "INACTIVE",
                    "deleted_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✅ Deleted (soft) strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy {strategy_id} deleted (marked INACTIVE)",
            "strategy_id": strategy_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting strategy {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies/{strategy_id}/sync-backtest")
async def sync_strategy_backtest(strategy_id: str, backtest_data: Dict[str, Any]):
    """
    Sync/update strategy backtest data in unified strategies collection
    Updates the backtest_data field within the same document
    """
    try:
        # Check if strategy exists
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Add updated timestamp to backtest data
        backtest_data['last_updated'] = datetime.utcnow()

        # Update backtest_data field in the unified document
        result = strategies_collection.update_one(
            {"strategy_id": strategy_id},
            {
                "$set": {
                    "backtest_data": backtest_data,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✅ Synced backtest data for strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Backtest data synced for strategy {strategy_id}",
            "strategy_id": strategy_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing backtest for {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ALLOCATIONS PAGE APIs (NEW)
# ============================================================================

@app.get("/api/v1/allocations/current")
async def get_current_allocation():
    """
    Part 1: Get current active allocation
    Returns the single "approved" allocation that the system is currently using
    """
    try:
        allocation = current_allocation_collection.find_one({}, {'_id': 0})
        return {
            "status": "success",
            "allocation": allocation
        }
    except Exception as e:
        logger.error(f"Error fetching current allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/allocations/approve")
async def approve_allocation(request: Dict[str, Any]):
    """
    Part 2: Approve allocation (makes it current)
    Replaces the current allocation with the approved one
    """
    try:
        allocations = request.get('allocations')
        if not allocations:
            raise HTTPException(status_code=400, detail="allocations field is required")

        # Create new current allocation document
        new_allocation = {
            "allocations": allocations,
            "approved_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Replace the current allocation (upsert - insert if doesn't exist)
        current_allocation_collection.delete_many({})  # Remove all existing
        current_allocation_collection.insert_one(new_allocation)

        logger.info(f"✅ Approved new allocation with {len(allocations)} strategies")

        return {
            "status": "success",
            "message": "Allocation approved and set as current"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio-tests")
async def get_portfolio_tests():
    """
    Part 3: Get list of portfolio tests
    Returns all test runs sorted by creation date (newest first)
    """
    try:
        tests = list(portfolio_tests_collection.find({}, {'_id': 0}).sort('created_at', -1))

        # Sanitize data - replace NaN/Inf with 0.0 for JSON compatibility
        for test in tests:
            if 'allocations' in test:
                for strategy_id, value in test['allocations'].items():
                    if pd.isna(value) or not np.isfinite(value):
                        test['allocations'][strategy_id] = 0.0

            if 'performance' in test:
                for metric, value in test['performance'].items():
                    if pd.isna(value) or not np.isfinite(value):
                        test['performance'][metric] = 0.0

        return {
            "status": "success",
            "count": len(tests),
            "tests": tests
        }

    except Exception as e:
        logger.error(f"Error fetching portfolio tests: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/portfolio-tests/{test_id}")
async def delete_portfolio_test(test_id: str):
    """
    Part 3: Delete a portfolio test
    """
    try:
        # Get test to find file paths
        test = portfolio_tests_collection.find_one({"test_id": test_id}, {'_id': 0})

        if not test:
            raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

        # Delete archived files from research/outputs
        research_outputs = "/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/services/cerebro_service/research/outputs"
        test_archive_dir = f"{research_outputs}/{test_id}"

        if os.path.exists(test_archive_dir):
            shutil.rmtree(test_archive_dir)
            logger.info(f"Deleted test archive directory: {test_archive_dir}")

        # Delete from MongoDB
        result = portfolio_tests_collection.delete_one({"test_id": test_id})

        logger.info(f"✅ Deleted portfolio test: {test_id}")

        return {
            "status": "success",
            "message": f"Test {test_id} deleted"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting test {test_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio-tests/{test_id}/tearsheet")
async def get_tearsheet(test_id: str):
    """
    Get the HTML tearsheet for a specific test
    """
    try:
        # Get test from MongoDB
        test = portfolio_tests_collection.find_one({"test_id": test_id}, {'_id': 0})

        if not test:
            raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

        # Get tearsheet file path
        tearsheet_path = test.get('files', {}).get('tearsheet_html')

        if not tearsheet_path or not os.path.exists(tearsheet_path):
            raise HTTPException(status_code=404, detail="Tearsheet not found for this test")

        return FileResponse(tearsheet_path, media_type="text/html")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tearsheet for {test_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/portfolio-tests/run")
async def run_portfolio_test(request: Dict[str, Any]):
    """
    Part 4: Run a new portfolio optimization test (Research Lab)
    Runs construct_portfolio.py with selected strategies and saves results to MongoDB
    """
    try:
        strategies = request.get('strategies', [])
        constructor = request.get('constructor', 'max_hybrid')

        if not strategies or len(strategies) == 0:
            raise HTTPException(status_code=400, detail="At least one strategy must be selected")

        # Generate test ID
        test_id = f"test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"🔬 Running portfolio test: {test_id}")
        logger.info(f"   Constructor: {constructor}")
        logger.info(f"   Strategies: {strategies}")

        # Create output directory for this test in research/outputs
        research_outputs = "/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/services/cerebro_service/research/outputs"
        test_output_dir = f"{research_outputs}/{test_id}"
        os.makedirs(test_output_dir, exist_ok=True)

        # Run construct_portfolio.py with output directory set to test folder
        cmd = [
            "/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/venv/bin/python",
            "/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/services/cerebro_service/research/construct_portfolio.py",
            "--constructor", constructor,
            "--strategies", ",".join(strategies),
            "--output-dir", test_output_dir
        ]

        logger.info(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.error(f"Portfolio construction failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Portfolio construction failed: {result.stderr}")

        logger.info(f"Portfolio construction output:\n{result.stdout}")

        # Files are already in the correct location - just need to find them
        allocation_files = glob.glob(f"{test_output_dir}/*_allocations.csv")
        equity_files = glob.glob(f"{test_output_dir}/*_equity.csv")
        correlation_files = glob.glob(f"{test_output_dir}/*_correlation.csv")
        tearsheet_files = glob.glob(f"{test_output_dir}/*_tearsheet.html")

        if not allocation_files:
            raise HTTPException(status_code=500, detail="No allocation file generated")

        # Get file paths (should only be one of each since we specified output dir)
        archived_files = {
            'allocation_csv': allocation_files[0] if allocation_files else None,
            'equity_csv': equity_files[0] if equity_files else None,
            'correlation_csv': correlation_files[0] if correlation_files else None,
            'tearsheet_html': tearsheet_files[0] if tearsheet_files else None
        }

        logger.info(f"Test files saved to: {test_output_dir}")
        logger.info(f"Files: {list(archived_files.values())}")

        # Parse allocations from CSV (last row has final allocations) - use new location
        allocations_df = pd.read_csv(archived_files['allocation_csv'])

        # Get final window's allocation (last row)
        final_row = allocations_df.iloc[-1]
        allocations = {}
        for strategy_id in strategies:
            if strategy_id in allocations_df.columns:
                value = final_row[strategy_id]
                # Handle NaN/Inf values - replace with 0.0
                if pd.isna(value) or not np.isfinite(value):
                    allocations[strategy_id] = 0.0
                else:
                    allocations[strategy_id] = float(value)

        # Parse performance metrics from QuantStats tearsheet HTML
        performance_metrics = {}
        if 'tearsheet_html' in archived_files and archived_files['tearsheet_html'] and os.path.exists(archived_files['tearsheet_html']):
            import re
            with open(archived_files['tearsheet_html'], 'r') as f:
                html_content = f.read()

            # Extract metrics using regex patterns
            cagr_match = re.search(r'CAGR[^<]*</td>\s*<td[^>]*>([-\d.]+)%', html_content)
            sharpe_match = re.search(r'<td[^>]*>Sharpe</td>\s*<td[^>]*>([-\d.]+)</td>', html_content)
            max_dd_match = re.search(r'<td[^>]*>Max Drawdown</td>\s*<td[^>]*>([-\d.]+)%', html_content)
            volatility_match = re.search(r'<td[^>]*>Volatility \(ann\.\)</td>\s*<td[^>]*>([-\d.]+)%', html_content)

            performance_metrics = {
                "cagr": float(cagr_match.group(1)) if cagr_match else 0.0,
                "sharpe": float(sharpe_match.group(1)) if sharpe_match else 0.0,
                "max_drawdown": float(max_dd_match.group(1)) if max_dd_match else 0.0,
                "volatility": float(volatility_match.group(1)) if volatility_match else 0.0
            }

            logger.info(f"Performance metrics from tearsheet: {performance_metrics}")
        else:
            logger.warning("No tearsheet HTML file found - cannot extract performance metrics")

        # Store test results with archived file paths
        test_result = {
            "test_id": test_id,
            "constructor": constructor,
            "strategies": strategies,
            "allocations": allocations,
            "performance": performance_metrics,
            "files": archived_files,  # All archived file paths
            "created_at": datetime.utcnow()
        }

        # Save to MongoDB
        portfolio_tests_collection.insert_one(test_result)

        logger.info(f"✅ Portfolio test completed: {test_id}")

        return {
            "status": "success",
            "message": "Test completed successfully",
            "test_id": test_id,
            "allocations": allocations,
            "performance": performance_metrics
        }

    except subprocess.TimeoutExpired:
        logger.error("Portfolio construction timed out after 5 minutes")
        raise HTTPException(status_code=500, detail="Portfolio construction timed out")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error running portfolio test: {str(e)}")
        logger.error(f"Full traceback:\n{error_details}")
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\nCheck server logs for full traceback")


# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    On startup, load allocations and start Pub/Sub subscriber
    """
    logger.info("Cerebro Service starting up...")

    # Initialize portfolio constructor
    logger.info("Initializing Portfolio Constructor...")
    initialize_portfolio_constructor()

    # Load active portfolio allocations
    logger.info("Loading active portfolio allocations...")
    reload_allocations()

    # Start Pub/Sub subscriber in background thread
    subscriber_thread = threading.Thread(target=start_signal_subscriber, daemon=True)
    subscriber_thread.start()
    logger.info("Started Pub/Sub subscriber thread")

    logger.info("Cerebro Service ready")


if __name__ == "__main__":
    logger.info("Starting Cerebro Service MVP")
    uvicorn.run(app, host="0.0.0.0", port=8001)
