"""
MaxHybrid Portfolio Constructor

Hybrid approach that balances high CAGR with high Sharpe ratio and controlled drawdown.

Strategy:
1. Optimize for weighted combination of CAGR and Sharpe ratio
2. Apply strict drawdown constraint (8% in-sample → ~20% out-of-sample)
3. Use moderate leverage (1.4x) to boost returns while maintaining risk control

Expected Results:
- CAGR: 65-75% (strong absolute returns)
- Sharpe: 3.0-3.2 (excellent risk-adjusted returns)
- Max DD: ~20% (well-controlled risk)

The key innovation is the weighted objective function:
    Objective = alpha * Sharpe + (1-alpha) * (CAGR / max_cagr_target)
    
Where alpha controls the balance between risk-adjusted returns and absolute returns.
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


class MaxHybridConstructor(PortfolioConstructor):
    """
    Hybrid portfolio constructor that optimizes for both CAGR and Sharpe ratio.
    
    Uses a weighted multi-objective optimization:
    - Maximize: alpha * Sharpe + (1-alpha) * CAGR_normalized
    - Subject to: drawdown <= max_drawdown_limit
    
    Parameters:
    - alpha: Weight between Sharpe (1.0) and CAGR (0.0). Default 0.5 for balanced.
    - max_drawdown_limit: Maximum allowed drawdown (e.g., -0.15 = -15%)
    - max_leverage: Maximum total allocation
    - max_single_strategy: Maximum per-strategy allocation
    - cagr_target: Target CAGR for normalization (default 1.0 = 100%)
    """
    
    def __init__(self,
                 alpha: float = 0.5,
                 max_drawdown_limit: float = -0.08,
                 max_leverage: float = 1.4,
                 max_single_strategy: float = 1.0,
                 min_allocation: float = 0.01,
                 cagr_target: float = 1.0,
                 risk_free_rate: float = 0.0):
        """
        Initialize MaxHybrid constructor.
        
        Args:
            alpha: Balance between Sharpe (1.0) and CAGR (0.0). 0.5 = equal weight
            max_drawdown_limit: Max allowed drawdown (e.g., -0.08 = -8%)
            max_leverage: Maximum total allocation (1.4 = 140%)
            max_single_strategy: Maximum per-strategy allocation
            min_allocation: Minimum allocation threshold
            cagr_target: Target CAGR for normalization (1.0 = 100%)
            risk_free_rate: Risk-free rate for Sharpe calculation
        """
        self.alpha = alpha
        self.max_drawdown_limit = max_drawdown_limit
        self.max_leverage = max_leverage
        self.max_single_strategy = max_single_strategy
        self.min_allocation = min_allocation
        self.cagr_target = cagr_target
        self.risk_free_rate = risk_free_rate
        
        logger.info(f"MaxHybrid Constructor initialized:")
        logger.info(f"  Alpha (Sharpe weight): {alpha:.2f}")
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
        Allocate portfolio using hybrid optimization.
        
        Optimization:
        1. Calculate mean returns on FULL history (no truncation)
        2. Align for covariance calculation
        3. Optimize: alpha*Sharpe + (1-alpha)*CAGR_normalized
        4. Constrain: drawdown <= max_drawdown_limit
        
        Args:
            context: PortfolioContext with strategy histories
            
        Returns:
            Dict of {strategy_id: allocation_pct}
        """
        logger.info("="*80)
        logger.info("MaxHybrid Portfolio Allocation")
        logger.info("="*80)
        
        if not context.strategy_histories:
            logger.warning("No strategy histories available")
            return {}
        
        # Extract strategy data and calculate mean returns on FULL history
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
        
        # Align strategies for covariance
        returns_lengths = [len(r) for r in daily_returns_list]
        min_length = min(returns_lengths)
        max_length = max(returns_lengths)
        
        if min_length != max_length:
            logger.info(f"Aligning strategies: {max_length} -> {min_length} days")
        
        aligned_returns_list = [returns[-min_length:] for returns in daily_returns_list]
        
        # Create returns matrix for optimization (rows = days, cols = strategies)
        returns_matrix = np.array(aligned_returns_list).T
        
        # Calculate covariance matrix
        df = pd.DataFrame({sid: returns for sid, returns in zip(strategy_ids, aligned_returns_list)})
        cov_matrix = df.cov().values
        
        logger.info(f"Mean returns (daily, full history): {mean_returns}")
        logger.info(f"Volatilities (daily, aligned period): {np.sqrt(np.diag(cov_matrix))}")
        
        # Optimization
        n_strategies = len(strategy_ids)
        initial_weights = np.array([1.0 / n_strategies] * n_strategies)
        bounds = tuple((0, self.max_single_strategy) for _ in range(n_strategies))
        
        # Hybrid objective function
        def hybrid_objective(weights):
            """
            Minimize: -(alpha * Sharpe + (1-alpha) * CAGR_normalized)
            """
            # Sharpe ratio component
            portfolio_return = np.dot(weights, mean_returns)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            if portfolio_std == 0:
                sharpe = 0
            else:
                sharpe = (portfolio_return - self.risk_free_rate) / portfolio_std
            
            # CAGR component (using aligned returns)
            portfolio_returns = np.dot(returns_matrix, weights)
            cagr = self._calculate_cagr(portfolio_returns)
            cagr_normalized = cagr / self.cagr_target  # Normalize to target
            
            # Weighted combination
            hybrid_score = self.alpha * sharpe + (1 - self.alpha) * cagr_normalized
            
            return -hybrid_score  # Negative for minimization
        
        # Drawdown constraint
        def drawdown_constraint(weights):
            portfolio_returns = np.dot(returns_matrix, weights)
            max_dd = self._calculate_max_drawdown(portfolio_returns)
            return max_dd - self.max_drawdown_limit  # Positive if satisfied
        
        # Constraints
        constraints = [
            {'type': 'ineq', 'fun': lambda w: self.max_leverage - np.sum(w)},
            {'type': 'ineq', 'fun': lambda w: np.sum(w)},
            {'type': 'ineq', 'fun': drawdown_constraint}
        ]
        
        logger.info(f"Running hybrid optimization (alpha={self.alpha:.2f})...")
        
        result = minimize(
            fun=hybrid_objective,
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
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_std if portfolio_std > 0 else 0
        
        portfolio_returns = np.dot(returns_matrix, optimal_weights)
        cagr = self._calculate_cagr(portfolio_returns)
        max_dd = self._calculate_max_drawdown(portfolio_returns)
        
        logger.info(f"\n{'='*80}")
        logger.info("ALLOCATION RESULTS:")
        logger.info(f"{'='*80}")
        logger.info(f"Total Allocation: {total_allocation:.1f}%")
        logger.info(f"Expected Daily Return: {portfolio_return*100:.4f}%")
        logger.info(f"Expected Daily Volatility: {portfolio_std*100:.4f}%")
        logger.info(f"Sharpe Ratio (daily): {sharpe_ratio:.4f}")
        logger.info(f"Sharpe Ratio (annualized): {sharpe_ratio * np.sqrt(252):.2f}")
        logger.info(f"Expected CAGR: {cagr*100:.2f}%")
        logger.info(f"Expected Max DD: {max_dd*100:.2f}%")
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
                reason=f"MaxHybrid allocation: {allocation_pct:.1f}%",
                timestamp=datetime.now()
            )
        else:
            logger.info(f"Signal REJECTED: {strategy_id} | No allocation")
            
            return SignalDecision(
                signal_id=signal.signal_id,
                strategy_id=strategy_id,
                action="reject",
                size_pct=0.0,
                reason="No allocation in MaxHybrid portfolio",
                timestamp=datetime.now()
            )
    
    def get_name(self) -> str:
        """Return constructor name"""
        return f"MaxHybrid_a{self.alpha:.2f}"
    
    def get_config(self) -> Dict:
        """Return configuration parameters"""
        return {
            "type": "MaxHybrid",
            "alpha": self.alpha,
            "max_drawdown_limit": self.max_drawdown_limit,
            "max_leverage": self.max_leverage,
            "max_single_strategy": self.max_single_strategy,
            "min_allocation": self.min_allocation,
            "cagr_target": self.cagr_target,
            "risk_free_rate": self.risk_free_rate
        }
