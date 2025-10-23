"""
MaxSharpe Portfolio Constructor

Optimizes portfolio allocations to maximize Sharpe ratio (risk-adjusted returns).
This approach balances returns with volatility, naturally favoring stable strategies
like SPX_0DTE_Opt that have excellent Sharpe ratios.

Key Differences from MaxCAGR:
- Objective: Maximize Sharpe ratio (return/volatility) instead of absolute CAGR
- Better diversification across uncorrelated strategies
- Lower drawdowns due to emphasis on risk-adjusted returns
- More consistent performance across market regimes

Expected Behavior:
- Will allocate to strategies with best risk-adjusted returns
- SPX_0DTE_Opt (3.50 Sharpe) should get significant allocation
- Lower absolute CAGR than MaxCAGR, but better Sharpe ratio
- More stable equity curve with lower volatility
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import logging

from ..base import PortfolioConstructor, PortfolioContext, SignalDecision, Signal

logger = logging.getLogger(__name__)


class MaxSharpeConstructor(PortfolioConstructor):
    """
    Portfolio constructor that maximizes Sharpe ratio.
    
    Optimization Objective: Maximize (Portfolio Return / Portfolio Volatility)
    
    Parameters:
    - max_leverage: Maximum total allocation (2.0 = 200%)
    - max_single_strategy: Maximum allocation per strategy (1.0 = 100%)
    - min_allocation: Minimum allocation to consider non-zero (default 0.01 = 1%)
    - risk_free_rate: Risk-free rate for Sharpe calculation (default 0.0)
    """
    
    def __init__(self, 
                 max_leverage: float = 2.0,
                 max_single_strategy: float = 1.0,
                 min_allocation: float = 0.01,
                 risk_free_rate: float = 0.0):
        """
        Initialize MaxSharpe constructor.
        
        Args:
            max_leverage: Maximum total portfolio allocation (2.0 = 200%)
            max_single_strategy: Maximum allocation per strategy (1.0 = 100%)
            min_allocation: Minimum allocation threshold (1%)
            risk_free_rate: Risk-free rate for Sharpe calculation
        """
        self.max_leverage = max_leverage
        self.max_single_strategy = max_single_strategy
        self.min_allocation = min_allocation
        self.risk_free_rate = risk_free_rate
        
        logger.info(f"MaxSharpe Constructor initialized:")
        logger.info(f"  Max Leverage: {max_leverage*100:.0f}%")
        logger.info(f"  Max Single Strategy: {max_single_strategy*100:.0f}%")
        logger.info(f"  Min Allocation: {min_allocation*100:.1f}%")
        logger.info(f"  Risk-Free Rate: {risk_free_rate*100:.2f}%")

    def _calculate_cagr(self, returns: np.ndarray) -> float:
        """Calculate CAGR from returns"""
        cumulative = (1 + returns).prod()
        n_years = len(returns) / 252
        cagr = (cumulative ** (1 / n_years)) - 1 if n_years > 0 else 0
        return cagr

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate max drawdown from returns"""
        cumulative = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

    def allocate_portfolio(self, context: PortfolioContext) -> Dict[str, float]:
        """
        Allocate portfolio to maximize Sharpe ratio.
        
        Process:
        1. Calculate mean returns on FULL available history (no truncation)
        2. Align strategies to common period for covariance calculation
        3. Optimize to maximize Sharpe ratio: (return - rf) / volatility
        4. Return allocations as percentages
        
        Args:
            context: PortfolioContext with strategy histories
            
        Returns:
            Dict of {strategy_id: allocation_pct}
        """
        logger.info("="*80)
        logger.info("MaxSharpe Portfolio Allocation")
        logger.info("="*80)
        
        if not context.strategy_histories:
            logger.warning("No strategy histories available")
            return {}
        
        # Step 1: Extract strategy data and calculate mean returns on FULL history
        strategy_ids = []
        mean_returns = []  # Calculated on full available history
        daily_returns_list = []  # Full history
        
        for sid, df in context.strategy_histories.items():
            if 'returns' not in df.columns or len(df) == 0:
                logger.warning(f"Skipping {sid}: no returns data")
                continue
            
            returns = df['returns'].values
            strategy_ids.append(sid)
            
            # Calculate mean on FULL available history (KEY: No truncation here!)
            mean_returns.append(np.mean(returns))
            daily_returns_list.append(returns)
        
        if len(strategy_ids) == 0:
            logger.warning("No valid strategies with returns data")
            return {}
        
        logger.info(f"Strategies: {strategy_ids}")
        logger.info(f"Strategy lengths: {[len(r) for r in daily_returns_list]}")
        
        # Convert to numpy
        mean_returns = np.array(mean_returns)
        
        # Step 2: Align strategies to common period for covariance calculation
        # (Covariance requires same time period, but mean uses full history)
        returns_lengths = [len(r) for r in daily_returns_list]
        min_length = min(returns_lengths)
        max_length = max(returns_lengths)
        
        if min_length != max_length:
            logger.info(f"Aligning strategies: {max_length} -> {min_length} days")
        
        # Truncate to common period (most recent data)
        aligned_returns_list = [returns[-min_length:] for returns in daily_returns_list]
        
        # Calculate covariance matrix on aligned period
        df = pd.DataFrame({sid: returns for sid, returns in zip(strategy_ids, aligned_returns_list)})
        cov_matrix = df.cov().values
        
        logger.info(f"Mean returns (daily, full history): {mean_returns}")
        logger.info(f"Volatilities (daily, aligned period): {np.sqrt(np.diag(cov_matrix))}")
        
        # Step 3: Optimize for maximum Sharpe ratio
        n_strategies = len(strategy_ids)
        
        # Initial guess (equal weight)
        initial_weights = np.array([1.0 / n_strategies] * n_strategies)
        
        # Bounds: 0 to max_single_strategy
        bounds = tuple((0, self.max_single_strategy) for _ in range(n_strategies))
        
        # Constraints
        constraints = [
            # Total weight between 0 and max_leverage
            {'type': 'ineq', 'fun': lambda w: self.max_leverage - np.sum(w)},
            {'type': 'ineq', 'fun': lambda w: np.sum(w)}
        ]
        
        # Objective: Negative Sharpe ratio (for minimization)
        def negative_sharpe(weights):
            portfolio_return = np.dot(weights, mean_returns)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            if portfolio_std == 0:
                return np.inf
            
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_std
            return -sharpe  # Negative for minimization
        
        logger.info("Running optimization (SLSQP)...")
        
        result = minimize(
            fun=negative_sharpe,
            x0=initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'disp': False, 'maxiter': 1000}
        )
        
        if not result.success:
            logger.error(f"Optimization failed: {result.message}")
            logger.warning("Falling back to equal weight allocation")
            optimal_weights = initial_weights
        else:
            optimal_weights = result.x
            logger.info("Optimization converged successfully")
        
        # Step 4: Convert to percentage allocations
        allocations = {}
        for sid, weight in zip(strategy_ids, optimal_weights):
            if weight >= self.min_allocation:  # Filter out tiny allocations
                allocation_pct = weight * 100
                allocations[sid] = round(allocation_pct, 2)
        
        # Calculate portfolio metrics for reporting
        total_allocation = sum(allocations.values())
        portfolio_return = np.dot(optimal_weights, mean_returns)
        portfolio_std = np.sqrt(np.dot(optimal_weights.T, np.dot(cov_matrix, optimal_weights)))
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_std if portfolio_std > 0 else 0
        
        logger.info(f"\n{'='*80}")
        logger.info("ALLOCATION RESULTS:")
        logger.info(f"{'='*80}")
        logger.info(f"Total Allocation: {total_allocation:.1f}%")
        logger.info(f"Expected Daily Return: {portfolio_return*100:.4f}%")
        logger.info(f"Expected Daily Volatility: {portfolio_std*100:.4f}%")
        logger.info(f"Sharpe Ratio (daily): {sharpe_ratio:.4f}")
        logger.info(f"Sharpe Ratio (annualized): {sharpe_ratio * np.sqrt(252):.2f}")
        logger.info(f"\nAllocations:")
        for sid, pct in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {sid}: {pct:.2f}%")
        logger.info(f"{'='*80}\n")
        
        return allocations
    
    def evaluate_signal(self, signal: Signal, context: PortfolioContext) -> SignalDecision:
        """
        Evaluate whether to take a signal based on current portfolio allocation.
        
        Logic:
        1. Get current portfolio allocations
        2. Check if signal's strategy has allocation > 0
        3. If yes, take the signal with size = allocation percentage
        4. If no, reject the signal
        
        Args:
            signal: Trading signal to evaluate
            context: Current portfolio context
            
        Returns:
            SignalDecision with action and size
        """
        # Get current allocations
        allocations = self.allocate_portfolio(context)
        
        strategy_id = signal.strategy_id
        
        if strategy_id in allocations and allocations[strategy_id] > 0:
            # Take signal with size = allocation percentage
            allocation_pct = allocations[strategy_id]
            
            logger.info(f"Signal ACCEPTED: {strategy_id} | Allocation: {allocation_pct:.1f}%")
            
            return SignalDecision(
                signal_id=signal.signal_id,
                strategy_id=strategy_id,
                action="take",
                size_pct=allocation_pct,
                reason=f"MaxSharpe allocation: {allocation_pct:.1f}%",
                timestamp=datetime.now()
            )
        else:
            # Reject signal
            logger.info(f"Signal REJECTED: {strategy_id} | No allocation")
            
            return SignalDecision(
                signal_id=signal.signal_id,
                strategy_id=strategy_id,
                action="reject",
                size_pct=0.0,
                reason="No allocation in MaxSharpe portfolio",
                timestamp=datetime.now()
            )
    
    def get_name(self) -> str:
        """Return constructor name"""
        return "MaxSharpe"
    
    def get_config(self) -> Dict:
        """Return configuration parameters"""
        return {
            "type": "MaxSharpe",
            "max_leverage": self.max_leverage,
            "max_single_strategy": self.max_single_strategy,
            "min_allocation": self.min_allocation,
            "risk_free_rate": self.risk_free_rate
        }
