"""
Cerebro Service - MVP
The intelligent core for portfolio management, risk assessment, and position sizing.
Implements hard margin limits and basic position sizing for MVP.
"""
import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
import threading
from fastapi import FastAPI
import uvicorn

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

# Initialize FastAPI
app = FastAPI(title="Cerebro Service", version="1.0.0-MVP")

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


def calculate_position_size(signal: Dict[str, Any], account_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate position size based on portfolio allocation and risk limits
    Uses strategy-specific allocation from ACTIVE portfolio allocation
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

        process_signal(data)

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


@app.on_event("startup")
async def startup_event():
    """
    On startup, load allocations and start Pub/Sub subscriber
    """
    logger.info("Cerebro Service starting up...")

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
