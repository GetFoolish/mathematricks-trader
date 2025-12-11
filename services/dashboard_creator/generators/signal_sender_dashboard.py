"""
Signal Sender Dashboard Generator
Generates per-strategy dashboard JSON for strategy developers
"""
import os
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from pymongo import MongoClient

logger = logging.getLogger(__name__)


def generate_signal_sender_dashboard(
    strategy_id: str,
    mongo_client: MongoClient
) -> Dict[str, Any]:
    """
    Generate dashboard for a specific strategy.

    Args:
        strategy_id: Strategy identifier
        mongo_client: MongoDB client instance

    Returns:
        Dict containing strategy dashboard with signals, positions, performance
    """
    db = mongo_client['mathematricks_trading']

    logger.info(f"Generating signal sender dashboard for {strategy_id}...")

    # Query signal_store for this strategy's decisions (embedded)
    signal_store_docs = list(
        db['signal_store'].find({
            "cerebro_decision": {"$ne": None},
            "cerebro_decision.strategy_id": strategy_id
        }).sort("received_at", -1).limit(100)
    )

    # Extract embedded decisions
    decisions = [doc.get('cerebro_decision') for doc in signal_store_docs if doc.get('cerebro_decision')]

    # Query account_state for open positions (filter by strategy)
    account_state = db['account_state'].find_one(sort=[("timestamp", -1)])
    positions = _extract_strategy_positions(account_state, strategy_id)

    # Get current allocation for this strategy
    allocation = db['portfolio_allocations'].find_one(
        {"status": "ACTIVE"},
        sort=[("updated_at", -1)]
    )
    current_allocation_pct = 0.0
    if allocation:
        current_allocation_pct = allocation.get("allocations", {}).get(strategy_id, 0.0)

    # Calculate summary metrics
    summary = _calculate_summary_metrics(decisions, current_allocation_pct)

    # Calculate performance metrics
    performance = _calculate_strategy_performance(decisions)

    # Format recent signals
    recent_signals = _format_signals(decisions[:20])

    # Calculate rejection breakdown
    rejection_breakdown = _calculate_rejection_reasons(decisions)

    dashboard = {
        "strategy_id": strategy_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "performance": performance,
        "recent_signals": recent_signals,
        "open_positions": positions,
        "rejection_breakdown": rejection_breakdown
    }

    # Store to MongoDB
    db['dashboard_snapshots'].update_one(
        {"dashboard_type": "signal_sender", "strategy_id": strategy_id},
        {"$set": {**dashboard, "updated_at": datetime.utcnow()}},
        upsert=True
    )

    logger.info(
        f"Signal sender dashboard generated for {strategy_id}: "
        f"{summary['total_signals_sent']} signals, "
        f"{summary['rejection_rate_pct']:.1f}% rejection rate"
    )

    return dashboard


def _calculate_summary_metrics(
    decisions: List[Dict[str, Any]],
    current_allocation_pct: float
) -> Dict[str, Any]:
    """Calculate summary metrics from cerebro decisions"""
    total_signals = len(decisions)
    if total_signals == 0:
        return {
            "total_signals_sent": 0,
            "signals_executed": 0,
            "signals_rejected": 0,
            "rejection_rate_pct": 0.0,
            "win_rate_pct": 0.0,
            "avg_position_size_usd": 0.0,
            "total_pnl": 0.0,
            "sharpe_ratio": 0.0,
            "current_allocation_pct": current_allocation_pct
        }

    executed = len([d for d in decisions if d.get("decision") == "APPROVED"])
    rejected = total_signals - executed

    # Calculate avg position size (from executed signals)
    executed_decisions = [d for d in decisions if d.get("decision") == "APPROVED"]
    avg_position_size = 0.0
    if executed_decisions:
        position_sizes = [
            d.get("allocated_capital", 0.0) for d in executed_decisions
        ]
        avg_position_size = sum(position_sizes) / len(position_sizes)

    return {
        "total_signals_sent": total_signals,
        "signals_executed": executed,
        "signals_rejected": rejected,
        "rejection_rate_pct": (rejected / total_signals * 100) if total_signals > 0 else 0.0,
        "win_rate_pct": 0.0,  # TODO: Requires P&L tracking per signal
        "avg_position_size_usd": avg_position_size,
        "total_pnl": 0.0,     # TODO: Requires P&L tracking
        "sharpe_ratio": 0.0,  # TODO: Requires return series
        "current_allocation_pct": current_allocation_pct
    }


def _calculate_strategy_performance(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate performance metrics for the strategy.

    TODO: For now, returns placeholder data.
    In production, this should track P&L per signal and calculate returns.
    """
    return {
        "daily_return_pct": 0.0,    # TODO: Requires daily P&L tracking
        "mtd_return_pct": 0.0,      # TODO: Requires monthly P&L
        "ytd_return_pct": 0.0,      # TODO: Requires yearly P&L
        "max_drawdown_pct": 0.0     # TODO: Requires equity curve
    }


def _format_signals(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format cerebro decisions as signal status list"""
    formatted_signals = []

    for decision in decisions:
        formatted_signals.append({
            "signal_id": decision.get("signal_id"),
            "timestamp": decision.get("timestamp", datetime.utcnow()).isoformat() + "Z",
            "ticker": decision.get("instrument", "UNKNOWN"),
            "action": decision.get("action", "UNKNOWN"),
            "requested_quantity": decision.get("original_quantity", 0),
            "status": "EXECUTED" if decision.get("decision") == "APPROVED" else "REJECTED",
            "actual_quantity": decision.get("final_quantity", 0),
            "position_size_usd": decision.get("allocated_capital", 0.0),
            "allocation_pct": decision.get("allocation_pct", 0.0),
            "execution_price": decision.get("price", 0.0),
            "approval_reason": decision.get("reason", "UNKNOWN")
        })

    return formatted_signals


def _extract_strategy_positions(
    account_state: Dict[str, Any],
    strategy_id: str
) -> List[Dict[str, Any]]:
    """Extract open positions for this strategy from account state"""
    if not account_state:
        return []

    open_positions = account_state.get("open_positions", [])

    # Filter positions by strategy_id
    strategy_positions = [
        pos for pos in open_positions
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
            "opened_at": pos.get("opened_at", datetime.utcnow()).isoformat() + "Z",
            "days_held": (datetime.utcnow() - pos.get("opened_at", datetime.utcnow())).days
        })

    return formatted_positions


def _calculate_rejection_reasons(decisions: List[Dict[str, Any]]) -> Dict[str, int]:
    """Calculate breakdown of rejection reasons"""
    rejection_counts = {}

    for decision in decisions:
        if decision.get("decision") != "APPROVED":
            reason = decision.get("reason", "UNKNOWN")

            # Categorize rejection reasons
            if "ALLOCATION" in reason or "allocation" in reason:
                key = "NO_ALLOCATION"
            elif "MARGIN" in reason or "margin" in reason:
                key = "MARGIN_EXCEEDED"
            elif "RISK" in reason or "risk" in reason:
                key = "RISK_LIMIT"
            else:
                key = "OTHER"

            rejection_counts[key] = rejection_counts.get(key, 0) + 1

    return rejection_counts


def generate_all_signal_sender_dashboards(mongo_client: MongoClient) -> int:
    """
    Generate dashboards for all active strategies.

    Args:
        mongo_client: MongoDB client instance

    Returns:
        Number of dashboards generated
    """
    db = mongo_client['mathematricks_trading']

    # Get all active strategies
    strategies = list(
        db['strategy_configurations'].find({"status": "ACTIVE"})
    )

    count = 0
    for strategy in strategies:
        strategy_id = strategy["strategy_id"]
        try:
            generate_signal_sender_dashboard(strategy_id, mongo_client)
            count += 1
        except Exception as e:
            logger.error(f"Failed to generate dashboard for {strategy_id}: {e}")

    logger.info(f"Generated {count} signal sender dashboards")
    return count


if __name__ == "__main__":
    # Test the generator
    logging.basicConfig(level=logging.INFO)

    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri)

    # Test with a specific strategy
    strategy_id = "TestStrategy"
    dashboard = generate_signal_sender_dashboard(strategy_id, client)

    import json
    print(json.dumps(dashboard, indent=2))
