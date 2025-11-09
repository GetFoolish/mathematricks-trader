"""
Client Dashboard Generator
Generates fund-level dashboard JSON for mathematricks.fund (Netlify site)
"""
import os
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from pymongo import MongoClient

logger = logging.getLogger(__name__)


def generate_client_dashboard(mongo_client: MongoClient) -> Dict[str, Any]:
    """
    Generate client-facing fund dashboard JSON.

    Queries MongoDB collections and aggregates fund-level metrics.

    Args:
        mongo_client: MongoDB client instance

    Returns:
        Dict containing dashboard JSON with fund metrics, performance, allocations, trades
    """
    db = mongo_client['mathematricks_trading']

    logger.info("Generating client dashboard...")

    # Get account state (latest snapshot)
    account_state = db['account_state'].find_one(sort=[("timestamp", -1)])

    # Get current allocation
    allocation = db['portfolio_allocations'].find_one(
        {"status": "ACTIVE"},
        sort=[("updated_at", -1)]
    )

    # Get recent trades (last 7 days, limit 20)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_trades = list(
        db['execution_confirmations'].find(
            {"timestamp": {"$gte": seven_days_ago}}
        ).sort("timestamp", -1).limit(20)
    )

    # Build dashboard JSON
    dashboard = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "fund": _extract_fund_metrics(account_state),
        "performance": _calculate_performance_metrics(account_state),
        "allocations": _format_allocations(allocation),
        "recent_trades": _format_trades(recent_trades),
        "chart_data": {
            "equity_curve": [],  # TODO: Implement once we have historical data
            "daily_returns": []   # TODO: Implement once we have historical data
        }
    }

    # Store to MongoDB for fast retrieval
    db['dashboard_snapshots'].update_one(
        {"dashboard_type": "client"},
        {"$set": {**dashboard, "updated_at": datetime.utcnow()}},
        upsert=True
    )

    logger.info(f"Client dashboard generated: ${dashboard['fund']['total_equity']:,.2f} total equity")

    return dashboard


def _extract_fund_metrics(account_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract fund-level metrics from account state"""
    if not account_state:
        logger.warning("No account state found, using defaults")
        return {
            "total_equity": 0.0,
            "total_cash": 0.0,
            "total_margin_used": 0.0,
            "total_unrealized_pnl": 0.0,
            "total_realized_pnl": 0.0,
            "num_brokers": 0,
            "num_accounts": 0
        }

    return {
        "total_equity": account_state.get("equity", 0.0),
        "total_cash": account_state.get("cash_balance", 0.0),
        "total_margin_used": account_state.get("margin_used", 0.0),
        "total_unrealized_pnl": account_state.get("unrealized_pnl", 0.0),
        "total_realized_pnl": account_state.get("realized_pnl", 0.0),
        "num_brokers": 1,  # Currently only IBKR_Main
        "num_accounts": 1
    }


def _calculate_performance_metrics(account_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate performance metrics.

    TODO: For now, returns dummy data.
    In production, this should query historical equity curve and calculate:
    - Daily return from previous day's equity
    - MTD return from start of month
    - YTD return from start of year
    - CAGR, Sharpe, Max DD from full backtest
    """
    if not account_state:
        return {
            "daily_return_pct": 0.0,
            "mtd_return_pct": 0.0,
            "ytd_return_pct": 0.0,
            "cagr_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "volatility_pct": 0.0
        }

    # For MVP, return placeholder values
    # TODO: Implement historical equity curve tracking and calculate actual metrics
    return {
        "daily_return_pct": 0.0,  # Requires yesterday's equity
        "mtd_return_pct": 0.0,    # Requires month-start equity
        "ytd_return_pct": 0.0,    # Requires year-start equity
        "cagr_pct": 0.0,          # Requires full backtest
        "sharpe_ratio": 0.0,      # Requires return series
        "max_drawdown_pct": 0.0,  # Requires equity curve
        "volatility_pct": 0.0     # Requires return series
    }


def _format_allocations(allocation: Dict[str, Any]) -> Dict[str, float]:
    """Format allocations as strategy_id → allocation_pct mapping"""
    if not allocation:
        logger.warning("No active allocation found")
        return {}

    allocations_dict = allocation.get("allocations", {})

    # Convert to simple dict format: {"StrategyName": 13.5, ...}
    return {
        strategy_id: allocation_pct
        for strategy_id, allocation_pct in allocations_dict.items()
    }


def _format_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format recent trades for dashboard display"""
    formatted_trades = []

    for trade in trades:
        timestamp = trade.get("timestamp", datetime.utcnow())
        # Handle both datetime and string timestamps
        if isinstance(timestamp, datetime):
            date_str = timestamp.strftime("%Y-%m-%d")
            time_str = timestamp.strftime("%H:%M:%S")
        else:
            date_str = str(timestamp)[:10]
            time_str = str(timestamp)[11:19] if len(str(timestamp)) > 19 else "00:00:00"

        formatted_trades.append({
            "date": date_str,
            "time": time_str,
            "symbol": trade.get("instrument", "UNKNOWN"),
            "side": "BUY" if trade.get("direction") == "LONG" else "SELL",
            "quantity": trade.get("quantity", 0),
            "price": trade.get("avg_fill_price", 0.0),
            "pnl": trade.get("unrealized_pnl", 0.0),  # TODO: Calculate actual P&L
            "strategy": trade.get("strategy_id", "UNKNOWN")
        })

    return formatted_trades


if __name__ == "__main__":
    # Test the generator
    logging.basicConfig(level=logging.INFO)

    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri)

    dashboard = generate_client_dashboard(client)

    import json
    print(json.dumps(dashboard, indent=2))
