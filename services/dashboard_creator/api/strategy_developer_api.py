"""
Strategy Developer API
APIs for strategy developers to query their signal status and positions
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from pymongo import MongoClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/signal-senders")


# Store MongoDB client (set by main.py)
_mongo_client: Optional[MongoClient] = None


def set_mongo_client(client: MongoClient):
    """Set the MongoDB client for this module"""
    global _mongo_client
    _mongo_client = client


async def verify_api_key(x_api_key: str = Header(None)) -> str:
    """
    Verify API key and return strategy_id.

    Args:
        x_api_key: API key from request header

    Returns:
        strategy_id associated with the API key

    Raises:
        HTTPException: If API key is invalid or not provided
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required (X-API-Key header)")

    db = _mongo_client['mathematricks_trading']
    strategy = db['strategy_configurations'].find_one({"api_key": x_api_key})

    if not strategy:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return strategy["strategy_id"]


@router.get("/{strategy_id}/signals")
async def get_signals(
    strategy_id: str,
    limit: int = Query(50, ge=1, le=500, description="Number of signals to return"),
    status: Optional[str] = Query(None, description="Filter by status: EXECUTED or REJECTED"),
    x_api_key: str = Header(None, description="API key for authentication")
):
    """
    Get signals for a strategy with optional status filtering.

    Args:
        strategy_id: Strategy identifier
        limit: Maximum number of signals to return (1-500)
        status: Optional filter - "EXECUTED" or "REJECTED"
        x_api_key: API key from request header

    Returns:
        List of signals with status and details
    """
    # Verify API key matches strategy_id
    verified_strategy = await verify_api_key(x_api_key)
    if verified_strategy != strategy_id:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized for strategy {strategy_id}"
        )

    db = _mongo_client['mathematricks_trading']

    # Build query
    query = {"strategy_id": strategy_id}
    if status:
        if status == "EXECUTED":
            query["decision"] = "APPROVED"
        elif status == "REJECTED":
            query["decision"] = {"$ne": "APPROVED"}
        else:
            raise HTTPException(status_code=400, detail="status must be EXECUTED or REJECTED")

    # Query decisions from signal_store (embedded)
    # Need to match on signal_data.strategy_id since that's where the strategy is stored
    signal_store_query = {
        'cerebro_decision': {'$ne': None},
        'signal_data.strategy_name': strategy_id  # Match strategy in signal_data
    }
    if status:
        if status == "EXECUTED":
            signal_store_query['cerebro_decision.decision'] = "APPROVED"
        elif status == "REJECTED":
            signal_store_query['cerebro_decision.decision'] = {"$ne": "APPROVED"}

    # Get signal_store documents and extract decisions
    signal_store_docs = list(
        db['signal_store'].find(signal_store_query)
        .sort("received_at", -1)
        .limit(limit)
    )

    # Extract decisions from signal_store
    decisions = []
    for doc in signal_store_docs:
        decision = doc.get('cerebro_decision', {})
        if decision:
            decisions.append(decision)

    # Format response
    signals = []
    for decision in decisions:
        signals.append({
            "signal_id": decision.get("signal_id"),
            "timestamp": decision.get("timestamp", "").isoformat() + "Z" if hasattr(decision.get("timestamp", ""), 'isoformat') else str(decision.get("timestamp", "")),
            "ticker": decision.get("instrument", "UNKNOWN"),
            "action": decision.get("action", "UNKNOWN"),
            "status": "EXECUTED" if decision.get("decision") == "APPROVED" else "REJECTED",
            "requested_quantity": decision.get("original_quantity", 0),
            "actual_quantity": decision.get("final_quantity", 0),
            "position_size_usd": decision.get("allocated_capital", 0.0),
            "allocation_pct": decision.get("allocation_pct", 0.0),
            "execution_price": decision.get("price", 0.0),
            "reason": decision.get("reason", "UNKNOWN")
        })

    return {
        "strategy_id": strategy_id,
        "count": len(signals),
        "signals": signals
    }


@router.get("/{strategy_id}/signals/{signal_id}")
async def get_signal_details(
    strategy_id: str,
    signal_id: str,
    x_api_key: str = Header(None, description="API key for authentication")
):
    """
    Get detailed information about a specific signal.

    Args:
        strategy_id: Strategy identifier
        signal_id: Signal identifier
        x_api_key: API key from request header

    Returns:
        Detailed signal information including cerebro decision and execution
    """
    # Verify API key matches strategy_id
    verified_strategy = await verify_api_key(x_api_key)
    if verified_strategy != strategy_id:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized for strategy {strategy_id}"
        )

    db = _mongo_client['mathematricks_trading']

    # Get signal from signal_store (with embedded cerebro decision)
    signal_doc = db['signal_store'].find_one({"signal_id": signal_id})
    if not signal_doc or not signal_doc.get('cerebro_decision'):
        raise HTTPException(status_code=404, detail="Signal not found")

    decision = signal_doc.get('cerebro_decision')

    # Verify signal belongs to this strategy
    if decision.get("strategy_id") != strategy_id:
        raise HTTPException(
            status_code=403,
            detail="Signal does not belong to this strategy"
        )

    # Get execution details if executed
    execution = None
    if decision.get("decision") == "APPROVED":
        execution = db['execution_confirmations'].find_one({"signal_id": signal_id})

    # Convert ObjectId to string for JSON serialization
    decision_copy = {k: str(v) if k == "_id" else v for k, v in decision.items()}
    if execution:
        execution = {k: str(v) if k == "_id" else v for k, v in execution.items()}

    return {
        "signal_id": signal_id,
        "status": "EXECUTED" if decision.get("decision") == "APPROVED" else "REJECTED",
        "cerebro_decision": decision_copy,
        "execution": execution
    }


@router.get("/{strategy_id}/positions")
async def get_positions(
    strategy_id: str,
    x_api_key: str = Header(None, description="API key for authentication")
):
    """
    Get open positions for a strategy.

    Args:
        strategy_id: Strategy identifier
        x_api_key: API key from request header

    Returns:
        List of open positions for the strategy
    """
    # Verify API key matches strategy_id
    verified_strategy = await verify_api_key(x_api_key)
    if verified_strategy != strategy_id:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized for strategy {strategy_id}"
        )

    db = _mongo_client['mathematricks_trading']

    # Get latest account state
    account_state = db['account_state'].find_one(sort=[("timestamp", -1)])

    if not account_state:
        return {
            "strategy_id": strategy_id,
            "count": 0,
            "positions": []
        }

    # Extract positions for this strategy
    all_positions = account_state.get("open_positions", [])
    strategy_positions = [
        pos for pos in all_positions
        if pos.get("strategy_id") == strategy_id
    ]

    # Format positions
    formatted_positions = []
    for pos in strategy_positions:
        formatted_positions.append({
            "ticker": pos.get("instrument", "UNKNOWN"),
            "side": "LONG" if pos.get("direction") == "LONG" else "SHORT",
            "quantity": pos.get("quantity", 0),
            "entry_price": pos.get("avg_price", 0.0),
            "current_price": pos.get("current_price", 0.0),
            "unrealized_pnl": pos.get("unrealized_pnl", 0.0),
            "opened_at": pos.get("opened_at", "").isoformat() + "Z" if hasattr(pos.get("opened_at", ""), 'isoformat') else str(pos.get("opened_at", ""))
        })

    return {
        "strategy_id": strategy_id,
        "count": len(formatted_positions),
        "positions": formatted_positions
    }
