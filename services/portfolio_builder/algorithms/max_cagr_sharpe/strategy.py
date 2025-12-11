"""
MaxCAGR with Sharpe Constraint Portfolio Constructor

Maximizes CAGR subject to a minimum Sharpe ratio constraint.

This is the inverse of typical MPT approaches - instead of maximizing Sharpe,
we maximize absolute returns (CAGR) while ensuring we maintain excellent
risk-adjusted performance (Sharpe ≥ min_sharpe).

Optimization:
- Objective: Maximize CAGR (geometric mean of returns)
- Constraints:
  1. Sharpe ratio >= min_sharpe (e.g., 3.5)
  2. Max drawdown <= max_drawdown_limit (e.g., -20%)
  3. Total allocation <= max_leverage
  4. Per-strategy allocation <= max_single_strategy

Expected Results (min_sharpe=3.5):
- CAGR: 50-70% (higher than MaxSharpe's 30%, lower than MaxCAGR's 115%)
- Sharpe: 3.5-4.5 (enforced minimum)
- Max DD: Should naturally be low due to high Sharpe requirement
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


class MaxCAGRSharpeConstructor(PortfolioConstructor):
    """
    Portfolio constructor that maximizes CAGR with minimum Sharpe ratio constraint.
    
    Optimization Problem:
        Maximize: CAGR (compound annual growth rate)
        Subject to:
            - Sharpe ratio >= min_sharpe
            - Max drawdown >= max_drawdown_limit (less negative)
            - Sum(weights) <= max_leverage
            - weights[i] <= max_single_strategy
            - weights[i] >= 0
    
    This ensures we get high absolute returns while maintaining excellent
    risk-adjusted performance.
    """
    
    def __init__(self,
                 min_sharpe: float = 3.5,
                 max_drawdown_limit: float = -0.20,
                 max_leverage: float = 2.0,
                 max_single_strategy: float = 1.0,
                 min_allocation: float = 0.01,
                 risk_free_rate: float = 0.0):
        """
        Initialize MaxCAGRSharpe constructor.
        
        Args:
            min_sharpe: Minimum required Sharpe ratio (daily, will be annualized)
            max_drawdown_limit: Maximum allowed drawdown (e.g., -0.20 = -20%)
            max_leverage: Maximum total allocation
            max_single_strategy: Maximum per-strategy allocation
            min_allocation: Minimum allocation threshold
            risk_free_rate: Risk-free rate for Sharpe calculation
        """
        self.min_sharpe = min_sharpe
        self.max_drawdown_limit = max_drawdown_limit
        self.max_leverage = max_leverage
        self.max_single_strategy = max_single_strategy
        self.min_allocation = min_allocation
        self.risk_free_rate = risk_free_rate
        
        logger.info(f"MaxCAGRSharpe Constructor initialized:")
        logger.info(f"  Min Sharpe Ratio (annualized): {min_sharpe:.2f}")
        logger.info(f"  Max Drawdown Limit: {max_drawdown_limit*100:.1f}%")
        logger.info(f"  Max Leverage: {max_leverage*100:.0f}%")
        logger.info(f"  Max Single Strategy: {max_single_strategy*100:.0f}%")
    
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
        Allocate portfolio to maximize CAGR with Sharpe constraint.
        
        Process:
        1. Calculate mean returns on FULL available history
        2. Align strategies for covariance calculation
        3. Optimize to maximize CAGR
        4. Enforce Sharpe >= min_sharpe constraint
        5. Enforce drawdown <= max_drawdown_limit
        
        Args:
            context: PortfolioContext with strategy histories
            
        Returns:
            Dict of {strategy_id: allocation_pct}
        """
        logger.info("="*80)
        logger.info("MaxCAGRSharpe Portfolio Allocation")
        logger.info("="*80)
        
        if not context.strategy_histories:
            logger.warning("No strategy histories available")
            return {}
        
        # Step 1: Extract data and calculate mean returns on FULL history
        strategy_ids = []
        mean_returns = []
        daily_returns_list = []
        
        for sid, df in context.strategy_histories.items():
            if 'returns' not in df.columns or len(df) == 0:
                logger.warning(f"Skipping {sid}: no returns data")
                continue
            
            returns = df['returns'].values
            strategy_ids.append(sid)
            mean_returns.append(np.mean(returns))  # Full history
            daily_returns_list.append(returns)
        
        if len(strategy_ids) == 0:
            logger.warning("No valid strategies with returns data")
            return {}
        
        logger.info(f"Strategies: {strategy_ids}")
        logger.info(f"Strategy lengths: {[len(r) for r in daily_returns_list]}")
        
        mean_returns = np.array(mean_returns)
        
        # Step 2: Align strategies for covariance
        returns_lengths = [len(r) for r in daily_returns_list]
        min_length = min(returns_lengths)
        max_length = max(returns_lengths)
        
        if min_length != max_length:
            logger.info(f"Aligning strategies: {max_length} -> {min_length} days")
        
        aligned_returns_list = [returns[-min_length:] for returns in daily_returns_list]
        
        # Create returns matrix (rows = days, cols = strategies)
        returns_matrix = np.array(aligned_returns_list).T
        
        # Calculate covariance matrix
        df = pd.DataFrame({sid: returns for sid, returns in zip(strategy_ids, aligned_returns_list)})
        cov_matrix = df.cov().values
        
        logger.info(f"Mean returns (daily, full history): {mean_returns}")
        logger.info(f"Volatilities (daily, aligned period): {np.sqrt(np.diag(cov_matrix))}")
        
        # Step 3: Optimization
        n_strategies = len(strategy_ids)
        initial_weights = np.array([1.0 / n_strategies] * n_strategies)
        bounds = tuple((0, self.max_single_strategy) for _ in range(n_strategies))
        
        # Objective: Maximize CAGR (minimize negative CAGR)
        def negative_cagr(weights):
            portfolio_returns = np.dot(returns_matrix, weights)
            cagr = self._calculate_cagr(portfolio_returns)
            return -cagr
        
        # Sharpe constraint: Sharpe >= min_sharpe
        def sharpe_constraint(weights):
            """Returns positive if Sharpe >= min_sharpe"""
            portfolio_return = np.dot(weights, mean_returns)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            if portfolio_std == 0:
                return -np.inf  # Violated
            
            # Daily Sharpe
            sharpe_daily = (portfolio_return - self.risk_free_rate) / portfolio_std
            
            # Annualized Sharpe (this is what we compare to min_sharpe)
            sharpe_annual = sharpe_daily * np.sqrt(252)
            
            # Return positive if satisfied
            return sharpe_annual - self.min_sharpe
        
        # Drawdown constraint
        def drawdown_constraint(weights):
            """Returns positive if max_dd >= max_drawdown_limit"""
            portfolio_returns = np.dot(returns_matrix, weights)
            max_dd = self._calculate_max_drawdown(portfolio_returns)
            return max_dd - self.max_drawdown_limit
        
        # Constraints
        constraints = [
            # Total allocation
            {'type': 'ineq', 'fun': lambda w: self.max_leverage - np.sum(w)},
            {'type': 'ineq', 'fun': lambda w: np.sum(w)},
            # Sharpe constraint
            {'type': 'ineq', 'fun': sharpe_constraint},
            # Drawdown constraint
            {'type': 'ineq', 'fun': drawdown_constraint}
        ]
        
        logger.info(f"Running optimization (min_sharpe={self.min_sharpe:.2f})...")
        logger.info(f"  Objective: Maximize CAGR")
        logger.info(f"  Constraints: Sharpe >= {self.min_sharpe:.2f}, DD >= {self.max_drawdown_limit*100:.1f}%")
        
        result = minimize(
            fun=negative_cagr,
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
        
        # Convert to percentage allocations
        allocations = {}
        for sid, weight in zip(strategy_ids, optimal_weights):
            if weight >= self.min_allocation:
                allocation_pct = weight * 100
                allocations[sid] = round(allocation_pct, 2)
        
        # Calculate portfolio metrics
        total_allocation = sum(allocations.values())
        portfolio_return = np.dot(optimal_weights, mean_returns)
        portfolio_std = np.sqrt(np.dot(optimal_weights.T, np.dot(cov_matrix, optimal_weights)))
        sharpe_daily = (portfolio_return - self.risk_free_rate) / portfolio_std if portfolio_std > 0 else 0
        sharpe_annual = sharpe_daily * np.sqrt(252)
        
        portfolio_returns = np.dot(returns_matrix, optimal_weights)
        cagr = self._calculate_cagr(portfolio_returns)
        max_dd = self._calculate_max_drawdown(portfolio_returns)
        
        logger.info(f"\n{'='*80}")
        logger.info("ALLOCATION RESULTS:")
        logger.info(f"{'='*80}")
        logger.info(f"Total Allocation: {total_allocation:.1f}%")
        logger.info(f"Expected Daily Return: {portfolio_return*100:.4f}%")
        logger.info(f"Expected Daily Volatility: {portfolio_std*100:.4f}%")
        logger.info(f"Sharpe Ratio (daily): {sharpe_daily:.4f}")
        logger.info(f"Sharpe Ratio (annualized): {sharpe_annual:.2f} (min: {self.min_sharpe:.2f})")
        logger.info(f"Expected CAGR: {cagr*100:.2f}%")
        logger.info(f"Expected Max DD: {max_dd*100:.2f}%")
        
        # Check if constraints are satisfied
        if sharpe_annual >= self.min_sharpe:
            logger.info(f"✓ Sharpe constraint SATISFIED ({sharpe_annual:.2f} >= {self.min_sharpe:.2f})")
        else:
            logger.warning(f"⚠ Sharpe constraint VIOLATED ({sharpe_annual:.2f} < {self.min_sharpe:.2f})")
        
        if max_dd >= self.max_drawdown_limit:
            logger.info(f"✓ Drawdown constraint SATISFIED ({max_dd*100:.2f}% >= {self.max_drawdown_limit*100:.2f}%)")
        else:
            logger.warning(f"⚠ Drawdown constraint VIOLATED ({max_dd*100:.2f}% < {self.max_drawdown_limit*100:.2f}%)")
        
        logger.info(f"\nAllocations:")
        for sid, pct in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {sid}: {pct:.2f}%")
        logger.info(f"{'='*80}\n")
        
        return allocations
    
    def evaluate_signal(self, signal: Signal, context: PortfolioContext) -> SignalDecision:
        """
        Evaluate whether to take a signal based on current portfolio allocation.
        
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
            allocation_pct = allocations[strategy_id]
            
            logger.info(f"Signal ACCEPTED: {strategy_id} | Allocation: {allocation_pct:.1f}%")
            
            return SignalDecision(
                signal_id=signal.signal_id,
                strategy_id=strategy_id,
                action="take",
                size_pct=allocation_pct,
                reason=f"MaxCAGRSharpe allocation: {allocation_pct:.1f}%",
                timestamp=datetime.now()
            )
        else:
            logger.info(f"Signal REJECTED: {strategy_id} | No allocation")
            
            return SignalDecision(
                signal_id=signal.signal_id,
                strategy_id=strategy_id,
                action="reject",
                size_pct=0.0,
                reason="No allocation in MaxCAGRSharpe portfolio",
                timestamp=datetime.now()
            )
    
    def get_name(self) -> str:
        """Return constructor name"""
        return f"MaxCAGRSharpe_s{self.min_sharpe:.1f}"
    
    def get_config(self) -> Dict:
        """Return configuration parameters"""
        return {
            "type": "MaxCAGRSharpe",
            "min_sharpe": self.min_sharpe,
            "max_drawdown_limit": self.max_drawdown_limit,
            "max_leverage": self.max_leverage,
            "max_single_strategy": self.max_single_strategy,
            "min_allocation": self.min_allocation,
            "risk_free_rate": self.risk_free_rate
        }
