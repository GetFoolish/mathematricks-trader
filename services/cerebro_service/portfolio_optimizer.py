"""
Portfolio Optimizer - MPT Implementation
Optimizes portfolio allocations using Modern Portfolio Theory (maximize Sharpe ratio)
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_correlation_matrix(strategies: Dict[str, Dict]) -> Tuple[np.ndarray, List[str]]:
    """
    Calculate correlation matrix from strategy daily returns.

    Args:
        strategies: Dict of {strategy_id: {"daily_returns": [float], ...}}

    Returns:
        Tuple of (correlation_matrix, strategy_names)
    """
    # Extract returns into DataFrame
    returns_data = {}
    for strategy_id, data in strategies.items():
        if 'daily_returns' not in data or not data['daily_returns']:
            logger.warning(f"Strategy {strategy_id} has no daily returns, skipping")
            continue
        returns_data[strategy_id] = data['daily_returns']

    if not returns_data:
        raise ValueError("No valid strategy data provided")

    # Check for different time periods and align
    returns_lengths = {sid: len(returns) for sid, returns in returns_data.items()}
    min_length = min(returns_lengths.values())
    max_length = max(returns_lengths.values())

    if min_length != max_length:
        logger.warning(f"Strategies have different time periods (min: {min_length}, max: {max_length})")
        logger.warning(f"Using most recent {min_length} days for correlation calculation")

        # Truncate all series to shortest length (use most recent data)
        returns_data = {sid: returns[-min_length:] for sid, returns in returns_data.items()}

    # Create DataFrame (all series now same length)
    df = pd.DataFrame(returns_data)

    # Calculate correlation matrix
    corr_matrix = df.corr().values
    strategy_names = list(df.columns)

    logger.info(f"Calculated correlation matrix for {len(strategy_names)} strategies")

    return corr_matrix, strategy_names


def portfolio_sharpe_ratio(weights: np.ndarray, mean_returns: np.ndarray,
                          cov_matrix: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """
    Calculate negative Sharpe ratio (for minimization).

    Args:
        weights: Portfolio weights (array)
        mean_returns: Mean returns for each strategy
        cov_matrix: Covariance matrix
        risk_free_rate: Risk-free rate (default 0)

    Returns:
        Negative Sharpe ratio
    """
    # Portfolio return
    portfolio_return = np.dot(weights, mean_returns)

    # Portfolio volatility
    portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

    # Sharpe ratio (return / volatility)
    if portfolio_std == 0:
        return -np.inf

    sharpe = (portfolio_return - risk_free_rate) / portfolio_std

    # Return negative (we minimize)
    return -sharpe


def portfolio_volatility(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    """
    Calculate portfolio volatility (for minimization).

    Args:
        weights: Portfolio weights (array)
        cov_matrix: Covariance matrix

    Returns:
        Portfolio volatility
    """
    portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    return portfolio_std


def calculate_portfolio_returns_series(weights: np.ndarray, daily_returns_list: List[List[float]]) -> np.ndarray:
    """
    Calculate portfolio daily returns series from strategy returns.

    Args:
        weights: Portfolio weights
        daily_returns_list: List of daily returns for each strategy

    Returns:
        Array of portfolio daily returns
    """
    # Convert to numpy arrays
    returns_matrix = np.array(daily_returns_list).T  # Shape: (n_days, n_strategies)
    portfolio_returns = np.dot(returns_matrix, weights)
    return portfolio_returns


def calculate_max_drawdown(portfolio_returns: np.ndarray) -> float:
    """
    Calculate maximum drawdown from daily returns.

    Args:
        portfolio_returns: Array of daily returns

    Returns:
        Maximum drawdown (negative value, e.g., -0.20 = -20%)
    """
    # Calculate cumulative returns
    cumulative = (1 + portfolio_returns).cumprod()
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()
    return max_drawdown


def calculate_cagr(portfolio_returns: np.ndarray, trading_days_per_year: int = 252) -> float:
    """
    Calculate CAGR from daily returns.

    Args:
        portfolio_returns: Array of daily returns
        trading_days_per_year: Number of trading days per year

    Returns:
        CAGR as decimal (e.g., 0.15 = 15% annual return)
    """
    # Total return
    total_return = (1 + portfolio_returns).prod()

    # Number of years
    n_days = len(portfolio_returns)
    n_years = n_days / trading_days_per_year

    # CAGR
    cagr = (total_return ** (1 / n_years)) - 1
    return cagr


def portfolio_negative_cagr(weights: np.ndarray, daily_returns_list: List[List[float]]) -> float:
    """
    Calculate negative CAGR (for minimization).

    Args:
        weights: Portfolio weights
        daily_returns_list: List of daily returns for each strategy

    Returns:
        Negative CAGR
    """
    portfolio_returns = calculate_portfolio_returns_series(weights, daily_returns_list)
    cagr = calculate_cagr(portfolio_returns)
    return -cagr  # Negative for minimization


def drawdown_constraint(weights: np.ndarray, daily_returns_list: List[List[float]],
                       max_drawdown_limit: float = -0.20) -> float:
    """
    Constraint function: max_drawdown must be >= max_drawdown_limit (less negative).

    Returns positive value if constraint satisfied, negative if violated.

    Args:
        weights: Portfolio weights
        daily_returns_list: List of daily returns for each strategy
        max_drawdown_limit: Maximum allowed drawdown (e.g., -0.20 = -20%)

    Returns:
        Constraint value (positive = satisfied)
    """
    portfolio_returns = calculate_portfolio_returns_series(weights, daily_returns_list)
    max_dd = calculate_max_drawdown(portfolio_returns)

    # Return positive if max_dd >= limit (e.g., -0.15 >= -0.20)
    # Constraint is satisfied when max_dd is less negative than limit
    return max_dd - max_drawdown_limit


def optimize_portfolio(strategies: Dict[str, Dict],
                      max_leverage: float = 2.0,
                      max_single_strategy: float = 0.5,
                      risk_free_rate: float = 0.0,
                      mode: str = "max_sharpe",
                      max_drawdown_limit: float = -0.20) -> Dict[str, float]:
    """
    Optimize portfolio allocations using MPT.

    Args:
        strategies: Dict of {strategy_id: {
            "daily_returns": [float],
            "mean_return_daily": float,
            "volatility_daily": float,
            ...
        }}
        max_leverage: Maximum total allocation (2.0 = 200%)
        max_single_strategy: Maximum allocation per strategy (0.5 = 50%)
        risk_free_rate: Risk-free rate for Sharpe calculation
        mode: Optimization mode - "max_sharpe", "max_cagr_drawdown", "min_volatility"
        max_drawdown_limit: Maximum allowed drawdown for max_cagr_drawdown mode (e.g., -0.20 = -20%)

    Returns:
        Dict of {strategy_id: allocation_pct} (percentages, e.g., 30.0 = 30%)
    """
    logger.info(f"Starting portfolio optimization for {len(strategies)} strategies")
    logger.info(f"Optimization Mode: {mode}")
    logger.info(f"Constraints: max_leverage={max_leverage*100}%, max_single_strategy={max_single_strategy*100}%")
    if mode == "max_cagr_drawdown":
        logger.info(f"Max Drawdown Constraint: {max_drawdown_limit*100:.1f}%")

    # Extract data
    strategy_ids = []
    mean_returns = []
    daily_returns_list = []

    for strategy_id, data in strategies.items():
        if 'daily_returns' not in data or not data['daily_returns']:
            logger.warning(f"Skipping {strategy_id}: no daily returns data")
            continue

        strategy_ids.append(strategy_id)
        mean_returns.append(data['mean_return_daily'])
        daily_returns_list.append(data['daily_returns'])

    if len(strategy_ids) == 0:
        raise ValueError("No valid strategies to optimize")

    n_strategies = len(strategy_ids)
    mean_returns = np.array(mean_returns)

    # Check daily returns lengths
    returns_lengths = [len(r) for r in daily_returns_list]
    logger.info(f"Daily returns lengths: {dict(zip(strategy_ids, returns_lengths))}")

    # Find minimum length (common period)
    min_length = min(returns_lengths)
    max_length = max(returns_lengths)

    if min_length != max_length:
        logger.warning(f"Strategies have different time periods (min: {min_length}, max: {max_length})")
        logger.warning(f"Using most recent {min_length} days for all strategies")

        # Truncate all series to the shortest length (use most recent data)
        daily_returns_list = [returns[-min_length:] for returns in daily_returns_list]

    # Calculate covariance matrix from daily returns
    df = pd.DataFrame({sid: returns for sid, returns in zip(strategy_ids, daily_returns_list)})
    cov_matrix = df.cov().values

    logger.info(f"Mean returns (daily): {mean_returns}")
    logger.info(f"Volatilities (daily): {np.sqrt(np.diag(cov_matrix))}")

    # Initial guess (equal weight)
    initial_weights = np.array([1.0 / n_strategies] * n_strategies)

    # Bounds for each strategy: [0, max_single_strategy]
    bounds = tuple((0, max_single_strategy) for _ in range(n_strategies))

    # Base constraints (common to all modes)
    constraints = [
        # Total weight between 0% and max_leverage (e.g., 200%)
        {'type': 'ineq', 'fun': lambda w: max_leverage - np.sum(w)},  # sum(w) <= max_leverage
        {'type': 'ineq', 'fun': lambda w: np.sum(w)}  # sum(w) >= 0
    ]

    # Choose objective function and additional constraints based on mode
    if mode == "max_sharpe":
        # Maximize Sharpe ratio
        objective_fun = portfolio_sharpe_ratio
        objective_args = (mean_returns, cov_matrix, risk_free_rate)
        logger.info("Objective: Maximize Sharpe Ratio")

    elif mode == "max_cagr_drawdown":
        # Maximize CAGR with drawdown constraint
        objective_fun = portfolio_negative_cagr
        objective_args = (daily_returns_list,)

        # Add drawdown constraint
        constraints.append({
            'type': 'ineq',
            'fun': lambda w: drawdown_constraint(w, daily_returns_list, max_drawdown_limit)
        })
        logger.info(f"Objective: Maximize CAGR with max drawdown <= {max_drawdown_limit*100:.1f}%")

    elif mode == "min_volatility":
        # Minimize volatility
        objective_fun = portfolio_volatility
        objective_args = (cov_matrix,)
        logger.info("Objective: Minimize Volatility")

    else:
        raise ValueError(f"Unknown optimization mode: {mode}")

    # Optimize
    logger.info("Running scipy.optimize.minimize (SLSQP)...")
    result = minimize(
        fun=objective_fun,
        x0=initial_weights,
        args=objective_args,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints,
        options={'disp': False, 'maxiter': 1000}
    )

    if not result.success:
        logger.error(f"Optimization failed: {result.message}")
        # Fallback to equal weight
        logger.warning("Falling back to equal weight allocation")
        optimal_weights = initial_weights
    else:
        optimal_weights = result.x
        logger.info(f"Optimization converged successfully")

    # Convert to percentage allocations
    allocations = {}
    for strategy_id, weight in zip(strategy_ids, optimal_weights):
        allocation_pct = weight * 100  # Convert to percentage
        allocations[strategy_id] = round(allocation_pct, 2)

    # Calculate portfolio metrics
    total_allocation = sum(allocations.values())
    portfolio_return = np.dot(optimal_weights, mean_returns)
    portfolio_std = np.sqrt(np.dot(optimal_weights.T, np.dot(cov_matrix, optimal_weights)))
    sharpe_ratio = (portfolio_return / portfolio_std) if portfolio_std > 0 else 0

    # Calculate CAGR and max drawdown for reporting
    portfolio_returns_series = calculate_portfolio_returns_series(optimal_weights, daily_returns_list)
    cagr = calculate_cagr(portfolio_returns_series)
    max_dd = calculate_max_drawdown(portfolio_returns_series)

    logger.info(f"\n{'='*70}")
    logger.info(f"OPTIMIZATION RESULTS ({mode.upper()}):")
    logger.info(f"{'='*70}")
    logger.info(f"Total Allocation: {total_allocation:.1f}%")
    logger.info(f"Leverage Ratio: {total_allocation/100:.2f}x")
    logger.info(f"Expected Daily Return: {portfolio_return*100:.4f}%")
    logger.info(f"Expected Daily Volatility: {portfolio_std*100:.4f}%")
    logger.info(f"Sharpe Ratio (daily): {sharpe_ratio:.4f}")
    logger.info(f"Sharpe Ratio (annualized, ~252 days): {sharpe_ratio * np.sqrt(252):.4f}")
    logger.info(f"CAGR: {cagr*100:.2f}%")
    logger.info(f"Max Drawdown: {max_dd*100:.2f}%")
    logger.info(f"\nAllocations:")
    for strategy_id, pct in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {strategy_id}: {pct:.2f}%")
    logger.info(f"{'='*70}\n")

    return allocations


def get_portfolio_metrics(allocations: Dict[str, float],
                         strategies: Dict[str, Dict]) -> Dict[str, float]:
    """
    Calculate expected portfolio metrics given allocations.

    Args:
        allocations: Dict of {strategy_id: allocation_pct}
        strategies: Dict of {strategy_id: strategy_data}

    Returns:
        Dict of portfolio metrics
    """
    # Extract data
    strategy_ids = list(allocations.keys())
    weights = np.array([allocations[sid] / 100 for sid in strategy_ids])  # Convert % to decimal
    mean_returns = np.array([strategies[sid]['mean_return_daily'] for sid in strategy_ids])

    # Build covariance matrix
    daily_returns_list = [strategies[sid]['daily_returns'] for sid in strategy_ids]

    # Align to shortest length (same logic as optimize_portfolio)
    returns_lengths = [len(r) for r in daily_returns_list]
    min_length = min(returns_lengths)
    if min(returns_lengths) != max(returns_lengths):
        daily_returns_list = [returns[-min_length:] for returns in daily_returns_list]

    df = pd.DataFrame({sid: returns for sid, returns in zip(strategy_ids, daily_returns_list)})
    cov_matrix = df.cov().values

    # Calculate metrics
    portfolio_return = np.dot(weights, mean_returns)
    portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    sharpe_ratio = (portfolio_return / portfolio_std) if portfolio_std > 0 else 0
    total_allocation = sum(allocations.values())

    return {
        "expected_daily_return": portfolio_return,
        "expected_daily_volatility": portfolio_std,
        "expected_sharpe_daily": sharpe_ratio,
        "expected_sharpe_annual": sharpe_ratio * np.sqrt(252),
        "total_allocation_pct": total_allocation,
        "leverage_ratio": total_allocation / 100
    }


if __name__ == "__main__":
    # Test with sample data
    logging.basicConfig(level=logging.INFO)

    # Sample strategies (mock data)
    test_strategies = {
        "SPX_1-D_Opt": {
            "daily_returns": list(np.random.normal(0.001, 0.02, 252)),
            "mean_return_daily": 0.001,
            "volatility_daily": 0.02
        },
        "Forex": {
            "daily_returns": list(np.random.normal(0.0008, 0.015, 252)),
            "mean_return_daily": 0.0008,
            "volatility_daily": 0.015
        },
        "Com1-Met": {
            "daily_returns": list(np.random.normal(0.0012, 0.025, 252)),
            "mean_return_daily": 0.0012,
            "volatility_daily": 0.025
        }
    }

    # Run optimization
    allocations = optimize_portfolio(test_strategies, max_leverage=2.0, max_single_strategy=0.5)
    print(f"\nOptimal Allocations: {allocations}")

    # Get metrics
    metrics = get_portfolio_metrics(allocations, test_strategies)
    print(f"\nPortfolio Metrics: {metrics}")
