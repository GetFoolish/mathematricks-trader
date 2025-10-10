#!/usr/bin/env python3
"""
Metrics Calculator for Mathematricks Trader
Calculate performance metrics using quantstats
"""

from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from datetime import datetime
import quantstats as qs

# Suppress quantstats warnings
import warnings
warnings.filterwarnings('ignore')


class MetricsCalculator:
    """Calculate trading performance metrics"""

    def __init__(self, data_store=None):
        """
        Initialize metrics calculator

        Args:
            data_store: DataStore instance for fetching data
        """
        self.data_store = data_store

    def calculate_returns(
        self,
        pnl_history: List[Dict]
    ) -> pd.Series:
        """
        Calculate returns from PnL history

        Args:
            pnl_history: List of PnL records

        Returns:
            Pandas Series of returns indexed by date
        """
        if not pnl_history:
            return pd.Series()

        df = pd.DataFrame(pnl_history)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df = df.sort_index()

        return df['returns_pct'] / 100  # Convert to decimal

    def calculate_equity_curve(
        self,
        pnl_history: List[Dict],
        initial_capital: float = 100000
    ) -> pd.Series:
        """
        Calculate equity curve from PnL history

        Args:
            pnl_history: List of PnL records
            initial_capital: Starting capital

        Returns:
            Pandas Series of equity values indexed by date
        """
        returns = self.calculate_returns(pnl_history)

        if returns.empty:
            return pd.Series([initial_capital], index=[datetime.now()])

        # Calculate cumulative returns
        equity = (1 + returns).cumprod() * initial_capital

        # Add initial value
        equity = pd.concat([
            pd.Series([initial_capital], index=[returns.index[0]]),
            equity
        ])

        return equity

    def calculate_basic_metrics(
        self,
        pnl_history: List[Dict]
    ) -> Dict:
        """
        Calculate performance metrics using quantstats

        Args:
            pnl_history: List of PnL records

        Returns:
            Dictionary of metrics
        """
        returns = self.calculate_returns(pnl_history)

        if returns.empty:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'calmar_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'volatility': 0.0,
                'var': 0.0,
                'cvar': 0.0
            }

        # Use quantstats for metrics
        total_return = qs.stats.comp(returns) * 100
        sharpe = qs.stats.sharpe(returns)
        sortino = qs.stats.sortino(returns)
        calmar = qs.stats.calmar(returns)
        max_drawdown = abs(qs.stats.max_drawdown(returns) * 100)
        volatility = qs.stats.volatility(returns) * 100
        var = abs(qs.stats.var(returns) * 100)
        cvar = abs(qs.stats.cvar(returns) * 100)

        # Win rate (manual calculation)
        positive_days = (returns > 0).sum()
        total_days = len(returns)
        win_rate = (positive_days / total_days * 100) if total_days > 0 else 0

        return {
            'total_return': round(total_return, 2),
            'sharpe_ratio': round(sharpe, 2),
            'sortino_ratio': round(sortino, 2),
            'calmar_ratio': round(calmar, 2),
            'max_drawdown': round(max_drawdown, 2),
            'win_rate': round(win_rate, 2),
            'volatility': round(volatility, 2),
            'var': round(var, 2),
            'cvar': round(cvar, 2)
        }

    def calculate_strategy_correlation(
        self,
        strategy_returns: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix between strategies

        Args:
            strategy_returns: Dict of {strategy_name: returns_series}

        Returns:
            Correlation matrix as DataFrame
        """
        if not strategy_returns:
            return pd.DataFrame()

        # Combine returns into DataFrame
        df = pd.DataFrame(strategy_returns)

        # Calculate correlation
        correlation = df.corr()

        return correlation

    def get_strategy_performance(
        self,
        strategy_name: Optional[str] = None
    ) -> Dict:
        """
        Get performance metrics for a strategy

        Args:
            strategy_name: Name of strategy (None for all)

        Returns:
            Performance metrics dictionary
        """
        if not self.data_store:
            return {}

        # Fetch PnL history
        pnl_history = self.data_store.get_pnl_history(
            strategy_name=strategy_name
        )

        # Calculate metrics
        metrics = self.calculate_basic_metrics(pnl_history)

        # Add equity curve
        equity_curve = self.calculate_equity_curve(pnl_history)
        metrics['equity_curve'] = equity_curve.to_dict()

        return metrics

    def get_all_strategy_returns(self) -> Dict[str, pd.Series]:
        """
        Get returns for all strategies

        Returns:
            Dictionary of {strategy_name: returns_series}
        """
        if not self.data_store:
            return {}

        strategy_returns = {}

        strategies = self.data_store.get_strategy_list()

        for strategy in strategies:
            pnl_history = self.data_store.get_pnl_history(
                strategy_name=strategy
            )
            returns = self.calculate_returns(pnl_history)
            if not returns.empty:
                strategy_returns[strategy] = returns

        return strategy_returns
