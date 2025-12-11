"""
Account Queries Module - Pure Functions
Contains functions for querying account data and portfolio state.
Can be imported and tested without triggering service initialization.
"""
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_account_state(account_name: str, account_data_service_url: str) -> Optional[Dict[str, Any]]:
    """
    Query AccountDataService for current account state.

    Args:
        account_name: Name of the trading account (e.g., "IBKR_Main")
        account_data_service_url: URL of the AccountDataService (e.g., "http://localhost:8002")

    Returns:
        Dict with account state:
            - account: str
            - equity: float
            - cash_balance: float
            - margin_used: float
            - margin_available: float
            - unrealized_pnl: float
            - realized_pnl: float
            - open_positions: list
            - open_orders: list

        Returns None if service is unavailable or error occurs.
        Returns MVP defaults if account not found (404).
    """
    try:
        response = requests.get(f"{account_data_service_url}/api/v1/account/{account_name}/state")
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


def get_strategy_allocation(
    strategy_id: str,
    portfolio_builder_url: str
) -> Optional[float]:
    """
    Query PortfolioBuilder for current allocation of a strategy.

    Args:
        strategy_id: Strategy identifier
        portfolio_builder_url: URL of the PortfolioBuilder service (e.g., "http://localhost:8003")

    Returns:
        float: Allocation percentage (e.g., 15.5 for 15.5%)
        Returns None if service unavailable or strategy not found.
    """
    try:
        response = requests.get(f"{portfolio_builder_url}/api/v1/allocations/current")
        response.raise_for_status()
        data = response.json()

        # Extract allocation for this strategy
        allocations = data.get('allocations', {})
        return allocations.get(strategy_id, 0.0)

    except Exception as e:
        logger.error(f"Failed to get allocation for {strategy_id}: {str(e)}")
        return None


def get_deployed_capital(strategy_id: str, account_data_service_url: str, account_name: str = "IBKR_Main") -> Dict[str, Any]:
    """
    Get capital currently deployed for a specific strategy.

    Args:
        strategy_id: Strategy identifier
        account_data_service_url: URL of the AccountDataService
        account_name: Trading account name

    Returns:
        Dict with:
            - deployed_capital: float (total capital in open positions)
            - margin_used: float (margin used by open positions)
            - open_positions: list (list of open position dicts)
            - num_positions: int
    """
    account_state = get_account_state(account_name, account_data_service_url)

    if not account_state:
        return {
            'deployed_capital': 0.0,
            'margin_used': 0.0,
            'open_positions': [],
            'num_positions': 0
        }

    # Filter positions by strategy
    open_positions = account_state.get('open_positions', [])
    strategy_positions = [p for p in open_positions if p.get('strategy_id') == strategy_id]

    # Calculate deployed capital (sum of position values)
    deployed_capital = sum(
        abs(p.get('quantity', 0)) * p.get('avg_price', 0)
        for p in strategy_positions
    )

    # Calculate margin used (simplified - would query broker for accurate margin)
    margin_used = sum(p.get('margin_used', 0) for p in strategy_positions)

    return {
        'deployed_capital': deployed_capital,
        'margin_used': margin_used,
        'open_positions': strategy_positions,
        'num_positions': len(strategy_positions)
    }


def calculate_available_margin(account_state: Dict[str, Any], max_margin_pct: float) -> float:
    """
    Calculate available margin for new positions given current utilization and limits.

    Args:
        account_state: Account state dict with equity, margin_used
        max_margin_pct: Maximum allowed margin utilization percentage

    Returns:
        float: Available margin in dollars
    """
    equity = account_state.get('equity', 0)
    margin_used = account_state.get('margin_used', 0)

    max_allowed_margin = equity * (max_margin_pct / 100)
    available_margin = max_allowed_margin - margin_used

    return max(0, available_margin)  # Never return negative


def get_portfolio_state(account_name: str, account_data_service_url: str) -> Dict[str, Any]:
    """
    Get comprehensive portfolio state for position sizing decisions.

    Args:
        account_name: Trading account name
        account_data_service_url: URL of the AccountDataService

    Returns:
        Dict with:
            - equity: float
            - margin_used: float
            - margin_available: float
            - margin_utilization_pct: float
            - cash_balance: float
            - num_open_positions: int
            - unrealized_pnl: float
            - realized_pnl: float
    """
    account_state = get_account_state(account_name, account_data_service_url)

    if not account_state:
        return {
            'equity': 0.0,
            'margin_used': 0.0,
            'margin_available': 0.0,
            'margin_utilization_pct': 0.0,
            'cash_balance': 0.0,
            'num_open_positions': 0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }

    equity = account_state.get('equity', 0)
    margin_used = account_state.get('margin_used', 0)
    margin_utilization_pct = (margin_used / equity * 100) if equity > 0 else 0

    return {
        'equity': equity,
        'margin_used': margin_used,
        'margin_available': account_state.get('margin_available', 0),
        'margin_utilization_pct': margin_utilization_pct,
        'cash_balance': account_state.get('cash_balance', 0),
        'num_open_positions': len(account_state.get('open_positions', [])),
        'unrealized_pnl': account_state.get('unrealized_pnl', 0),
        'realized_pnl': account_state.get('realized_pnl', 0)
    }
