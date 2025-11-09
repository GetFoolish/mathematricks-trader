"""
MaxCAGR Portfolio Constructor
Maximizes CAGR using Modern Portfolio Theory with drawdown constraints.
"""
import numpy as np
import pandas as pd
from typing import Dict
from scipy.optimize import minimize

from ..base import PortfolioConstructor
from ..context import PortfolioContext, Signal, SignalDecision


class MaxCAGRConstructor(PortfolioConstructor):
    """
    Portfolio constructor that maximizes CAGR using Modern Portfolio Theory.
    
    Features:
    - Optimizes for maximum Compound Annual Growth Rate
    - Enforces maximum drawdown constraint
    - Supports leveraged portfolios (allocations can exceed 100%)
    - Uses historical returns and covariance for optimization
    """
    
    def __init__(
        self,
        max_leverage: float = 2.0,
        max_drawdown_limit: float = 0.20,
        rebalance_frequency: str = 'monthly',
        risk_free_rate: float = 0.0,
        min_allocation: float = 0.0,
        max_single_strategy: float = 0.20
    ):
        """
        Initialize MaxCAGR constructor.
        
        Args:
            max_leverage: Maximum total allocation (2.0 = 200%)
            max_drawdown_limit: Maximum allowable drawdown (0.20 = 20%)
            rebalance_frequency: How often to rebalance ('daily', 'weekly', 'monthly')
            risk_free_rate: Risk-free rate for Sharpe calculation
            min_allocation: Minimum allocation per strategy (0.0 = can be zero)
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
        self.max_drawdown_limit = max_drawdown_limit
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
        Optimize portfolio allocation to maximize CAGR with drawdown constraint.
        
        Uses Modern Portfolio Theory to find optimal weights that maximize
        expected return while respecting drawdown limits.
        """
        # Extract strategy data
        if not context.strategy_histories:
            print("⚠️  No strategy histories available, using equal weights")
            return {}
        
        strategy_ids = list(context.strategy_histories.keys())
        n_strategies = len(strategy_ids)
        
        if n_strategies == 0:
            return {}
        
        # Build returns matrix
        returns_dict = {}
        for sid, df in context.strategy_histories.items():
            if 'returns' in df.columns:
                returns_dict[sid] = df['returns'].values
            elif 'return' in df.columns:
                returns_dict[sid] = df['return'].values
            else:
                print(f"⚠️  No returns column found for {sid}")
                continue
        
        if len(returns_dict) == 0:
            print("⚠️  No valid returns data, using equal weights")
            equal_weight = 100.0 / n_strategies
            return {sid: equal_weight for sid in strategy_ids}
        
        # Align all returns to same length (take intersection of dates)
        min_length = min(len(r) for r in returns_dict.values())
        aligned_returns = {sid: r[-min_length:] for sid, r in returns_dict.items()}
        
        # Convert to DataFrame
        returns_df = pd.DataFrame(aligned_returns)
        strategy_ids = list(returns_df.columns)
        n_strategies = len(strategy_ids)
        
        # Calculate mean returns and covariance
        mean_returns = returns_df.mean().values
        cov_matrix = returns_df.cov().values
        
        # Optimization objective: Maximize CAGR (geometric mean, not arithmetic)
        # This matches portfolio_optimizer.py implementation
        def objective(weights):
            # Calculate portfolio returns time series
            portfolio_returns = np.dot(returns_df.values, weights)
            
            # Calculate CAGR (geometric mean growth rate)
            cumulative = np.cumprod(1 + portfolio_returns)
            total_return = cumulative[-1]
            n_years = len(portfolio_returns) / 252  # Assuming 252 trading days per year
            
            if total_return <= 0 or n_years <= 0:
                return 1e10  # Return large penalty for invalid portfolios
            
            cagr = (total_return ** (1 / n_years)) - 1
            return -cagr  # Negative because we minimize
        
        # Drawdown constraint - calculate actual historical max drawdown
        # This matches the implementation in portfolio_optimizer.py
        def drawdown_constraint(weights):
            # Calculate portfolio returns time series
            portfolio_returns = np.dot(returns_df.values, weights)
            
            # Calculate cumulative returns
            cumulative = np.cumprod(1 + portfolio_returns)
            
            # Calculate running maximum
            running_max = np.maximum.accumulate(cumulative)
            
            # Calculate drawdown series
            drawdown = (cumulative - running_max) / running_max
            
            # Get maximum drawdown (most negative value)
            max_drawdown = drawdown.min()  # This is negative, e.g., -0.18
            
            # Return positive value when constraint is satisfied
            # max_drawdown must be >= -max_drawdown_limit (less negative)
            # Example: -0.15 >= -0.20 returns 0.05 (positive, satisfied)
            #          -0.25 >= -0.20 returns -0.05 (negative, violated)
            return max_drawdown + self.max_drawdown_limit
        
        # Constraints
        constraints = [
            # Total allocation must not exceed max_leverage * 100%
            {'type': 'ineq', 'fun': lambda w: self.max_leverage - np.sum(w)},
            # Drawdown constraint
            {'type': 'ineq', 'fun': drawdown_constraint}
        ]
        
        # Bounds for each weight
        bounds = tuple(
            (self.min_allocation, self.max_single_strategy)
            for _ in range(n_strategies)
        )
        
        # Initial guess: equal weights
        x0 = np.array([1.0 / n_strategies] * n_strategies)
        
        # Run optimization
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )
        
        if not result.success:
            print(f"⚠️  Optimization did not converge: {result.message}")
            print("   Using equal weights as fallback")
            equal_weight = 100.0 / n_strategies
            return {sid: equal_weight for sid in strategy_ids}
        
        # Convert weights to allocation percentages
        optimal_weights = result.x
        
        # Calculate and verify the actual drawdown with these weights
        portfolio_returns = np.dot(returns_df.values, optimal_weights)
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        actual_max_dd = drawdown.min()  # Negative value, e.g., -0.18
        
        # Debug output
        if context.is_backtest:
            print(f"      Historical max DD: {actual_max_dd*100:.2f}% (target: {-self.max_drawdown_limit*100:.0f}%)")
        
        allocations = {
            strategy_ids[i]: float(optimal_weights[i] * 100)
            for i in range(n_strategies)
        }
        
        # Filter out zero allocations
        allocations = {k: v for k, v in allocations.items() if v > 0.01}
        
        return allocations
    
    def evaluate_signal(self, signal: Signal, context: PortfolioContext) -> SignalDecision:
        """
        Evaluate a signal based on current allocations and risk limits.
        
        Decision logic:
        1. Check if strategy has allocation in current portfolio
        2. Calculate position size based on allocation percentage
        3. Check if position fits within margin limits
        4. Resize if needed, reject if constraints can't be met
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
        
        # Estimate margin required (simplified: assume 50% for stocks, 100% for futures)
        # In production, query broker API for exact requirements
        margin_requirement_pct = 0.5  # 50% margin requirement
        estimated_margin = allocated_capital * margin_requirement_pct
        
        # Check margin constraints
        max_margin_pct = self.max_leverage * 50  # If 2x leverage, allow up to 100% margin usage
        new_margin_used = context.margin_used + estimated_margin
        new_margin_pct = (new_margin_used / context.account_equity) * 100
        
        if new_margin_pct > max_margin_pct:
            # Try to resize to fit
            max_additional_margin = (max_margin_pct / 100 * context.account_equity) - context.margin_used
            
            if max_additional_margin <= 0:
                return SignalDecision(
                    action='REJECTED',
                    quantity=0.0,
                    reason=f'Insufficient margin (would exceed {max_margin_pct:.1f}% limit)',
                    allocated_capital=0.0,
                    margin_required=0.0
                )
            
            # Reduce quantity to fit
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
        
        # Approved!
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
        """Calculate portfolio metrics specific to MaxCAGR strategy"""
        if not context.strategy_histories:
            return {}
        
        # Calculate portfolio-level metrics
        metrics = {}
        
        # Get current allocations as weights
        total_alloc = sum(context.current_allocations.values())
        if total_alloc > 0:
            metrics['total_allocation_pct'] = total_alloc
            metrics['leverage_ratio'] = total_alloc / 100.0
        
        # Calculate number of strategies with non-zero allocation
        metrics['active_strategies'] = len([v for v in context.current_allocations.values() if v > 0])
        
        return metrics
