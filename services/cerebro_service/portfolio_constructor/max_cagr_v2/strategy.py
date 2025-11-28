"""
MaxCAGR V2 Portfolio Constructor
================================
Exact implementation matching portfolio_optimizer.py with NO look-ahead bias.

Key Improvements:
1. Calculates mean returns on each strategy's FULL AVAILABLE history (in context)
2. Calculates covariance on the COMMON aligned period
3. Uses actual CAGR (geometric mean), not arithmetic mean
4. Proper drawdown constraint implementation
5. No look-ahead: Only uses data passed in context (training period in walk-forward)

This matches the working portfolio_optimizer.py exactly.
"""
import numpy as np
import pandas as pd
from typing import Dict
from scipy.optimize import minimize
import logging

from ..base import PortfolioConstructor
from ..context import PortfolioContext, Signal, SignalDecision

logger = logging.getLogger(__name__)


class MaxCAGRV2Constructor(PortfolioConstructor):
    """
    Portfolio constructor that maximizes CAGR using exact portfolio_optimizer.py logic.
    
    Features:
    - Optimizes for maximum Compound Annual Growth Rate (geometric mean)
    - Enforces maximum drawdown constraint
    - Supports leveraged portfolios
    - NO LOOK-AHEAD BIAS: Uses only data in context (training period)
    - Mean returns calculated on each strategy's full available history
    - Covariance calculated on aligned common period
    """
    
    def __init__(
        self,
        max_leverage: float = 2.0,
        max_drawdown_limit: float = 0.20,
        rebalance_frequency: str = 'monthly',
        risk_free_rate: float = 0.0,
        min_allocation: float = 0.0,
        max_single_strategy: float = 1.0
    ):
        """
        Initialize MaxCAGR V2 constructor.
        
        Args:
            max_leverage: Maximum total allocation (2.0 = 200%)
            max_drawdown_limit: Maximum allowable drawdown (0.20 = 20%)
                               Note: Stored as positive, but used as negative in constraint
            rebalance_frequency: How often to rebalance
            risk_free_rate: Risk-free rate for calculations
            min_allocation: Minimum allocation per strategy
            max_single_strategy: Maximum allocation to single strategy (1.0 = 100%)
        """
        super().__init__(
            max_leverage=max_leverage,
            max_drawdown_limit=max_drawdown_limit,
            rebalance_frequency=rebalance_frequency,
            risk_free_rate=risk_free_rate,
            min_allocation=min_allocation,
            max_single_strategy=max_single_strategy
        )
        
        self.max_leverage = max_leverage
        self.max_drawdown_limit = max_drawdown_limit  # Stored as positive (e.g., 0.20)
        self.rebalance_frequency = rebalance_frequency
        self.risk_free_rate = risk_free_rate
        self.min_allocation = min_allocation
        self.max_single_strategy = max_single_strategy

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
        Optimize portfolio allocation using MPT to maximize CAGR with drawdown constraint.
        
        Follows portfolio_optimizer.py logic exactly:
        1. Extract data from context (NO look-ahead - only what's passed in)
        2. Calculate mean returns on each strategy's FULL available data
        3. Align strategies and calculate covariance on common period
        4. Optimize CAGR with drawdown constraint using scipy
        5. Return allocations as percentages
        """
        if not context.strategy_histories:
            if context.is_backtest:
                print("⚠️  No strategy histories available")
            return {}
        
        # Step 1: Extract data from context (this IS the training data - no look-ahead!)
        strategy_ids = []
        mean_returns = []
        daily_returns_list = []
        
        for sid, df in context.strategy_histories.items():
            if 'returns' not in df.columns or len(df) == 0:
                if context.is_backtest:
                    print(f"⚠️  No returns column found for {sid}")
                continue
            
            returns = df['returns'].values
            
            strategy_ids.append(sid)
            # Calculate mean on FULL available history (whatever is in context)
            mean_returns.append(np.mean(returns))
            daily_returns_list.append(returns)
        
        if len(strategy_ids) == 0:
            if context.is_backtest:
                print("⚠️  No valid returns data")
            return {}
        
        n_strategies = len(strategy_ids)
        mean_returns = np.array(mean_returns)
        
        # Step 2: Check daily returns lengths and align
        returns_lengths = [len(r) for r in daily_returns_list]
        min_length = min(returns_lengths)
        max_length = max(returns_lengths)
        
        if context.is_backtest and min_length != max_length:
            print(f"      Strategies have different lengths (min: {min_length}, max: {max_length})")
            print(f"      Using most recent {min_length} days for covariance calculation")
        
        # Truncate all series to shortest length (use most recent data) for covariance
        # This matches portfolio_optimizer.py line 264
        aligned_returns_list = [returns[-min_length:] for returns in daily_returns_list]
        
        # Step 3: Calculate covariance matrix from ALIGNED daily returns
        df = pd.DataFrame({sid: returns for sid, returns in zip(strategy_ids, aligned_returns_list)})
        cov_matrix = df.cov().values
        
        # Step 4: Define objective function - NEGATIVE CAGR (for minimization)
        def portfolio_negative_cagr(weights: np.ndarray) -> float:
            """Calculate negative CAGR for minimization"""
            # Calculate portfolio returns using aligned data
            returns_matrix = np.array(aligned_returns_list).T  # Shape: (n_days, n_strategies)
            portfolio_returns = np.dot(returns_matrix, weights)
            
            # Calculate CAGR (geometric mean)
            cumulative = (1 + portfolio_returns).prod()
            n_days = len(portfolio_returns)
            n_years = n_days / 252
            
            if cumulative <= 0 or n_years <= 0:
                return 1e10  # Large penalty
            
            cagr = (cumulative ** (1 / n_years)) - 1
            return -cagr  # Negative for minimization
        
        # Step 5: Define drawdown constraint
        def drawdown_constraint(weights: np.ndarray) -> float:
            """
            Constraint: max_drawdown >= -max_drawdown_limit
            Returns positive value if satisfied
            
            Matches portfolio_optimizer.py line 185
            """
            returns_matrix = np.array(aligned_returns_list).T
            portfolio_returns = np.dot(returns_matrix, weights)
            
            # Calculate cumulative returns
            cumulative = np.cumprod(1 + portfolio_returns)
            
            # Calculate running maximum
            running_max = np.maximum.accumulate(cumulative)
            
            # Calculate drawdown series
            drawdown = (cumulative - running_max) / running_max
            
            # Get maximum drawdown (most negative value)
            max_dd = drawdown.min()  # This is negative, e.g., -0.18
            
            # Return positive value when constraint is satisfied
            # max_dd >= -max_drawdown_limit
            # Example: -0.15 >= -0.20 returns 0.05 (positive, satisfied)
            #          -0.25 >= -0.20 returns -0.05 (negative, violated)
            return max_dd - (-self.max_drawdown_limit)  # Convert limit to negative
        
        # Step 6: Set up constraints (matches portfolio_optimizer.py)
        constraints = [
            # Total allocation <= max_leverage
            {'type': 'ineq', 'fun': lambda w: self.max_leverage - np.sum(w)},
            # Total allocation >= 0
            {'type': 'ineq', 'fun': lambda w: np.sum(w)},
            # Drawdown constraint
            {'type': 'ineq', 'fun': drawdown_constraint}
        ]
        
        # Step 7: Bounds for each weight
        bounds = tuple((self.min_allocation, self.max_single_strategy) for _ in range(n_strategies))
        
        # Step 8: Initial guess (equal weight)
        initial_weights = np.array([1.0 / n_strategies] * n_strategies)
        
        # Step 9: Run optimization (matches portfolio_optimizer.py)
        result = minimize(
            fun=portfolio_negative_cagr,
            x0=initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'disp': False, 'maxiter': 1000}
        )
        
        if not result.success:
            if context.is_backtest:
                print(f"⚠️  Optimization did not converge: {result.message}")
                print("   Using equal weights as fallback")
            equal_weight = 100.0 / n_strategies
            return {sid: equal_weight for sid in strategy_ids}
        
        optimal_weights = result.x
        
        # Step 10: Verify drawdown constraint (for debugging in backtest)
        if context.is_backtest:
            returns_matrix = np.array(aligned_returns_list).T
            portfolio_returns = np.dot(returns_matrix, optimal_weights)
            cumulative = np.cumprod(1 + portfolio_returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            actual_max_dd = drawdown.min()
            
            print(f"      Historical max DD: {actual_max_dd*100:.2f}% (target: {-self.max_drawdown_limit*100:.0f}%)")
        
        # Step 11: Convert weights to allocation percentages
        allocations = {
            strategy_ids[i]: float(optimal_weights[i] * 100)
            for i in range(n_strategies)
        }
        
        # Filter out near-zero allocations
        allocations = {k: v for k, v in allocations.items() if v > 0.01}
        
        return allocations
    
    def evaluate_signal(self, signal: Signal, context: PortfolioContext) -> SignalDecision:
        """
        Evaluate a signal based on current allocations and risk limits.
        
        Same as MaxCAGR V1 - this part doesn't need changes.
        """
        strategy_id = signal.strategy_id
        
        # Get this strategy's allocation
        allocated_pct = context.current_allocations.get(strategy_id, 0.0)
        
        if allocated_pct <= 0:
            return SignalDecision(
                action='REJECTED',
                quantity=0.0,
                reason=f'Strategy {strategy_id} not in current allocation',
                allocated_capital=0.0,
                margin_required=0.0
            )
        
        # Calculate allocated capital
        allocated_capital = context.account_equity * (allocated_pct / 100.0)
        
        # Calculate position size
        if signal.price <= 0:
            return SignalDecision(
                action='REJECTED',
                quantity=0.0,
                reason='Invalid price (<=0)',
                allocated_capital=0.0,
                margin_required=0.0
            )
        
        quantity = allocated_capital / signal.price
        
        # Estimate margin required
        margin_requirement_pct = 0.5
        estimated_margin = allocated_capital * margin_requirement_pct
        
        # Check margin constraints
        max_margin_pct = self.max_leverage * 50
        new_margin_used = context.margin_used + estimated_margin
        new_margin_pct = (new_margin_used / context.account_equity) * 100
        
        if new_margin_pct > max_margin_pct:
            # Try to resize
            max_additional_margin = (max_margin_pct / 100 * context.account_equity) - context.margin_used
            
            if max_additional_margin <= 0:
                return SignalDecision(
                    action='REJECTED',
                    quantity=0.0,
                    reason=f'Insufficient margin (would exceed {max_margin_pct:.1f}% limit)',
                    allocated_capital=0.0,
                    margin_required=0.0
                )
            
            # Reduce quantity
            reduction_factor = max_additional_margin / estimated_margin
            quantity = quantity * reduction_factor
            estimated_margin = max_additional_margin
            allocated_capital = quantity * signal.price
            
            return SignalDecision(
                action='RESIZE',
                quantity=quantity,
                reason=f'Resized to fit margin limit ({max_margin_pct:.1f}%)',
                allocated_capital=allocated_capital,
                margin_required=estimated_margin,
                metadata={
                    'original_allocation_pct': allocated_pct,
                    'reduction_factor': reduction_factor,
                    'margin_utilization_after_pct': new_margin_pct
                }
            )
        
        # Approved
        return SignalDecision(
            action='APPROVE',
            quantity=quantity,
            reason='Within allocation and margin limits',
            allocated_capital=allocated_capital,
            margin_required=estimated_margin,
            metadata={
                'allocation_pct': allocated_pct,
                'margin_utilization_before_pct': context.get_margin_utilization_pct(),
                'margin_utilization_after_pct': new_margin_pct
            }
        )
    
    def calculate_metrics(self, context: PortfolioContext) -> Dict[str, any]:
        """Calculate portfolio metrics"""
        if not context.strategy_histories:
            return {}
        
        metrics = {}
        
        total_alloc = sum(context.current_allocations.values())
        if total_alloc > 0:
            metrics['total_allocation_pct'] = total_alloc
            metrics['leverage_ratio'] = total_alloc / 100.0
        
        metrics['active_strategies'] = len([v for v in context.current_allocations.values() if v > 0])
        
        return metrics
