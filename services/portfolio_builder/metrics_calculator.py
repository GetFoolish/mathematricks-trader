"""
Metrics Calculator

This module calculates performance metrics from backtest data:
- CAGR (Compound Annual Growth Rate)
- Sharpe Ratio
- Calmar Ratio
- Maximum Drawdown
- Number of Trades (estimated)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional


def calculate_cagr(returns: pd.Series, days: int) -> float:
    """
    Calculate Compound Annual Growth Rate.

    Formula: CAGR = (Ending Value / Beginning Value) ^ (365 / days) - 1

    Args:
        returns: Series of daily returns (percentage)
        days: Number of trading days

    Returns:
        CAGR as percentage (e.g., 25.5 for 25.5%)
    """
    if days == 0:
        return 0.0

    # Calculate cumulative return
    cumulative_return = (1 + returns / 100).prod()

    # Calculate CAGR
    years = days / 365.0
    if years == 0:
        return 0.0

    cagr = (cumulative_return ** (1 / years) - 1) * 100

    return round(cagr, 2)


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe Ratio.

    Formula: Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns

    Args:
        returns: Series of daily returns (percentage)
        risk_free_rate: Annual risk-free rate (default: 0%)

    Returns:
        Annualized Sharpe Ratio
    """
    if len(returns) == 0:
        return 0.0

    # Calculate daily metrics
    daily_mean = returns.mean()
    daily_std = returns.std()

    if daily_std == 0:
        return 0.0

    # Convert annual risk-free rate to daily
    daily_rf = (1 + risk_free_rate / 100) ** (1/365) - 1

    # Calculate Sharpe ratio
    sharpe = (daily_mean / 100 - daily_rf) / (daily_std / 100)

    # Annualize (multiply by sqrt of trading days per year)
    annualized_sharpe = sharpe * np.sqrt(252)

    return round(annualized_sharpe, 2)


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Calculate Maximum Drawdown.

    Formula: Max DD = (Trough Value - Peak Value) / Peak Value

    Args:
        equity_curve: Series of account equity values

    Returns:
        Maximum drawdown as percentage (positive number, e.g., 15.5 for -15.5% drawdown)
    """
    if len(equity_curve) == 0:
        return 0.0

    # Calculate running maximum
    running_max = equity_curve.expanding().max()

    # Calculate drawdown at each point
    drawdown = (equity_curve - running_max) / running_max * 100

    # Maximum drawdown (most negative value)
    max_dd = abs(drawdown.min())

    return round(max_dd, 2)


def calculate_calmar_ratio(cagr: float, max_drawdown: float) -> float:
    """
    Calculate Calmar Ratio.

    Formula: Calmar = CAGR / Max Drawdown

    Args:
        cagr: Compound Annual Growth Rate (percentage)
        max_drawdown: Maximum drawdown (percentage, positive number)

    Returns:
        Calmar Ratio
    """
    if max_drawdown == 0:
        return 0.0

    calmar = cagr / max_drawdown

    return round(calmar, 2)


def estimate_num_trades(
    margin_data: Optional[pd.Series] = None,
    returns: Optional[pd.Series] = None
) -> int:
    """
    Estimate number of trades from margin usage or return data.

    Logic:
    - If margin_data available: Count days with non-zero margin
    - Otherwise: Count days with non-zero returns

    Args:
        margin_data: Series of Max_Margin_Used values (optional)
        returns: Series of Daily_Return_Pct values (optional)

    Returns:
        Estimated number of trades
    """
    if margin_data is not None:
        # Count days with margin > 0
        return int((margin_data > 0).sum())

    if returns is not None:
        # Count days with non-zero returns
        return int((returns.abs() > 0.001).sum())  # Threshold to avoid floating point issues

    return 0


def calculate_win_rate(returns: pd.Series) -> float:
    """
    Calculate win rate (percentage of profitable days).

    Args:
        returns: Series of daily returns (percentage)

    Returns:
        Win rate as percentage (e.g., 55.5 for 55.5%)
    """
    if len(returns) == 0:
        return 0.0

    winning_days = (returns > 0).sum()
    total_days = len(returns)

    win_rate = (winning_days / total_days) * 100

    return round(win_rate, 2)


def calculate_profit_factor(returns: pd.Series) -> float:
    """
    Calculate Profit Factor.

    Formula: Profit Factor = Sum of Gains / Sum of Losses

    Args:
        returns: Series of daily returns (percentage)

    Returns:
        Profit Factor
    """
    if len(returns) == 0:
        return 0.0

    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())

    if losses == 0:
        return 0.0 if gains == 0 else float('inf')

    profit_factor = gains / losses

    return round(profit_factor, 2)


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sortino Ratio (similar to Sharpe but only uses downside deviation).

    Formula: Sortino = (Mean Return - Risk Free Rate) / Downside Deviation

    Args:
        returns: Series of daily returns (percentage)
        risk_free_rate: Annual risk-free rate (default: 0%)

    Returns:
        Annualized Sortino Ratio
    """
    if len(returns) == 0:
        return 0.0

    # Calculate daily metrics
    daily_mean = returns.mean()

    # Calculate downside deviation (only negative returns)
    negative_returns = returns[returns < 0]
    if len(negative_returns) == 0:
        return 0.0

    downside_std = negative_returns.std()

    if downside_std == 0:
        return 0.0

    # Convert annual risk-free rate to daily
    daily_rf = (1 + risk_free_rate / 100) ** (1/365) - 1

    # Calculate Sortino ratio
    sortino = (daily_mean / 100 - daily_rf) / (downside_std / 100)

    # Annualize
    annualized_sortino = sortino * np.sqrt(252)

    return round(annualized_sortino, 2)


def calculate_all_metrics(raw_data: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate all performance metrics from raw backtest data.

    Args:
        raw_data: List of dictionaries containing backtest data with columns:
            - Date
            - Daily_Return_Pct
            - Account_Equity
            - Max_Margin_Used (optional)

    Returns:
        Dictionary containing all calculated metrics:
            - cagr: Compound Annual Growth Rate (%)
            - sharpe_ratio: Sharpe Ratio
            - calmar_ratio: Calmar Ratio
            - max_drawdown: Maximum Drawdown (%)
            - num_trades: Estimated number of trades
            - win_rate: Win rate (%)
            - profit_factor: Profit Factor
            - sortino_ratio: Sortino Ratio
            - total_return: Total return (%)
            - num_days: Number of trading days
            - start_date: First date in backtest
            - end_date: Last date in backtest
    """
    if not raw_data or len(raw_data) == 0:
        return {
            'cagr': 0.0,
            'sharpe_ratio': 0.0,
            'calmar_ratio': 0.0,
            'max_drawdown': 0.0,
            'num_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'sortino_ratio': 0.0,
            'total_return': 0.0,
            'num_days': 0,
            'start_date': None,
            'end_date': None
        }

    # Convert to DataFrame
    df = pd.DataFrame(raw_data)

    # Support both old capitalized format and new lowercase format
    date_col = 'date' if 'date' in df.columns else 'Date'
    return_col = 'return' if 'return' in df.columns else 'Daily_Return_Pct'
    equity_col = 'account_equity' if 'account_equity' in df.columns else 'Account_Equity'
    margin_col = 'margin_used' if 'margin_used' in df.columns else 'Max_Margin_Used'

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)

    # Extract series
    # If returns are in decimal format (0.025), convert to percentage (2.5)
    returns = df[return_col]
    if returns.abs().max() <= 1.0:
        returns = returns * 100.0

    equity = df[equity_col]
    margin = df.get(margin_col)

    # Calculate number of days
    num_days = len(df)

    # Calculate CAGR
    cagr = calculate_cagr(returns, num_days)

    # Calculate Sharpe Ratio
    sharpe = calculate_sharpe_ratio(returns)

    # Calculate Maximum Drawdown
    max_dd = calculate_max_drawdown(equity)

    # Calculate Calmar Ratio
    calmar = calculate_calmar_ratio(cagr, max_dd)

    # Estimate number of trades
    num_trades = estimate_num_trades(margin, returns)

    # Calculate Win Rate
    win_rate = calculate_win_rate(returns)

    # Calculate Profit Factor
    profit_factor = calculate_profit_factor(returns)

    # Calculate Sortino Ratio
    sortino = calculate_sortino_ratio(returns)

    # Calculate Total Return
    total_return = ((equity.iloc[-1] / equity.iloc[0]) - 1) * 100

    return {
        'cagr': cagr,
        'sharpe_ratio': sharpe,
        'calmar_ratio': calmar,
        'max_drawdown': max_dd,
        'num_trades': num_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'sortino_ratio': sortino,
        'total_return': round(total_return, 2),
        'num_days': num_days,
        'start_date': df[date_col].iloc[0].strftime('%Y-%m-%d'),
        'end_date': df[date_col].iloc[-1].strftime('%Y-%m-%d')
    }
