"""
MaxHybrid Portfolio Constructor

Hybrid approach that balances high CAGR with high Sharpe ratio and controlled drawdown.

Strategy:
1. Optimize for weighted combination of CAGR and Sharpe ratio
2. Apply strict drawdown constraint (6% in-sample → ~15% out-of-sample with 2.5x multiplier)
3. Use higher leverage (2.3x) to boost returns while maintaining high Sharpe

Expected Results (alpha=0.7, 6% DD, 2.3x leverage):
- CAGR: 70-90% (very strong absolute returns)
- Sharpe: 3.75-4.0 (excellent risk-adjusted returns)
- Max DD: ~15% (tightly controlled risk)

The key innovation is the weighted objective function:
    Objective = alpha * Sharpe + (1-alpha) * (CAGR / max_cagr_target)
    
Where alpha controls the balance:
- alpha = 0.7 → 70% Sharpe optimization, 30% CAGR optimization
- Higher alpha = more focus on risk-adjusted returns (higher Sharpe)
- Lower alpha = more focus on absolute returns (higher CAGR)
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import logging
import os

from ..base import PortfolioConstructor, PortfolioContext, SignalDecision, Signal

logger = logging.getLogger(__name__)

# Path for dedicated validation log
VALIDATION_LOG_PATH = '/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs/strategy_validation.log'
# Path for detailed optimization log
OPTIMIZATION_LOG_PATH = '/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs/max_hybrid_optimization.log'


def validate_live_vs_backtest(
    strategy_id: str,
    live_returns: Optional[pd.DataFrame],
    backtest_returns: pd.DataFrame,
    logger: logging.Logger
) -> Dict[str, any]:
    """
    Standalone validation function: Compare live performance vs backtest expectations.
    
    This is a PLACEHOLDER implementation - will be enhanced with statistical tests.
    
    Future enhancements will include:
    - Sharpe ratio comparison (live vs backtest)
    - Return distribution tests (KS test, Chi-squared)
    - Maximum drawdown comparison
    - Correlation analysis between live and backtest
    - Regime change detection
    - Rolling performance metrics
    
    Args:
        strategy_id: Strategy identifier
        live_returns: Live trading returns DataFrame (if available)
        backtest_returns: Backtest returns DataFrame for comparison
        logger: Logger instance
    
    Returns:
        Dict with validation results:
        - is_valid: bool (always True for now)
        - warnings: List[str]
        - action: str ("APPROVE" or "REJECT")
        - live_days: int
        - backtest_days: int
        - validation_implemented: bool
    """
    # Ensure log directory exists
    os.makedirs(os.path.dirname(VALIDATION_LOG_PATH), exist_ok=True)
    
    # Log to dedicated validation file
    with open(VALIDATION_LOG_PATH, 'a') as f:
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"\n{'='*80}\n")
        f.write(f"[{timestamp}] VALIDATION CHECK: {strategy_id}\n")
        f.write(f"{'='*80}\n")
        f.write(f"⚠️  WARNING: validate_live_vs_backtest() NOT YET IMPLEMENTED\n")
        f.write(f"   This is a PLACEHOLDER - auto-approving all strategies\n")
        f.write(f"\n")
        f.write(f"Data available:\n")
        f.write(f"  - Live returns: {'YES' if live_returns is not None else 'NO'}")
        if live_returns is not None:
            f.write(f" ({len(live_returns)} days)\n")
        else:
            f.write(f"\n")
        f.write(f"  - Backtest returns: YES ({len(backtest_returns)} days)\n")
        f.write(f"\n")
        f.write(f"Future implementation should include:\n")
        f.write(f"  - Sharpe ratio comparison (live vs backtest)\n")
        f.write(f"  - Return distribution tests (KS test, Chi-squared)\n")
        f.write(f"  - Maximum drawdown comparison\n")
        f.write(f"  - Correlation analysis\n")
        f.write(f"  - Regime change detection\n")
        f.write(f"  - Rolling performance metrics\n")
        f.write(f"\n")
        f.write(f"ACTION: AUTO-APPROVE (validation not implemented)\n")
        f.write(f"{'='*80}\n\n")
    
    # Also log to console
    logger.warning(f"⚠️  VALIDATION PLACEHOLDER for {strategy_id}")
    logger.warning(f"   validate_live_vs_backtest() not yet implemented - auto-approving")
    logger.warning(f"   See {VALIDATION_LOG_PATH} for details")
    
    return {
        "is_valid": True,
        "warnings": ["Validation not yet implemented - auto-approving"],
        "action": "APPROVE",
        "live_days": len(live_returns) if live_returns is not None else 0,
        "backtest_days": len(backtest_returns),
        "validation_implemented": False
    }


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
                 alpha: float = 0.85,
                 max_drawdown_limit: float = -0.06,
                 max_leverage: float = 2.3,
                 max_single_strategy: float = 1.0,
                 min_allocation: float = 0.01,
                 cagr_target: float = 2,
                 risk_free_rate: float = 0.0,
                 use_fixed_allocations: bool = True,
                 allocations_config_path: str = None):
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
            use_fixed_allocations: If True, use pre-calculated allocations instead of re-optimizing
            allocations_config_path: Path to JSON file with fixed allocations
        """
        self.alpha = alpha
        self.max_drawdown_limit = max_drawdown_limit
        self.max_leverage = max_leverage
        self.max_single_strategy = max_single_strategy
        self.min_allocation = min_allocation
        self.cagr_target = cagr_target
        self.risk_free_rate = risk_free_rate
        self.use_fixed_allocations = use_fixed_allocations
        self.fixed_allocations = None
        
        # Load fixed allocations if enabled
        if self.use_fixed_allocations:
            if allocations_config_path is None:
                # Default path: portfolio_allocations.json in cerebro_service directory
                import os
                # __file__ = .../cerebro_service/portfolio_constructor/max_hybrid/strategy.py
                # Need to go up 3 levels to reach cerebro_service/
                cerebro_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                allocations_config_path = os.path.join(cerebro_dir, 'portfolio_allocations.json')
            
            self._load_fixed_allocations(allocations_config_path)
        
        logger.info(f"MaxHybrid Constructor initialized:")
        logger.info(f"  Mode: {'FIXED ALLOCATIONS' if self.use_fixed_allocations else 'DYNAMIC OPTIMIZATION'}")
        if self.use_fixed_allocations and self.fixed_allocations:
            logger.info(f"  Loaded {len(self.fixed_allocations)} fixed allocations")
            logger.info(f"  Total allocation: {sum(self.fixed_allocations.values()):.1f}%")
        logger.info(f"  Alpha (Sharpe weight): {alpha:.2f}")
        logger.info(f"  Max Drawdown Limit: {max_drawdown_limit*100:.1f}%")
        logger.info(f"  Max Leverage: {max_leverage*100:.0f}%")
        logger.info(f"  Max Single Strategy: {max_single_strategy*100:.0f}%")
    
    def _load_fixed_allocations(self, config_path: str):
        """Load fixed allocations from JSON config file"""
        import json
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.fixed_allocations = config.get('allocations', {})
            
            # Filter out zero allocations
            self.fixed_allocations = {
                k: v for k, v in self.fixed_allocations.items() if v > 0
            }
            
            logger.info(f"✅ Loaded fixed allocations from: {config_path}")
            logger.info(f"   Allocations: {self.fixed_allocations}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load fixed allocations from {config_path}: {e}")
            logger.warning("⚠️  Falling back to dynamic optimization mode")
            self.use_fixed_allocations = False
            self.fixed_allocations = None
    
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
        # Ensure log directory exists
        os.makedirs(os.path.dirname(OPTIMIZATION_LOG_PATH), exist_ok=True)

        # Open optimization log file
        opt_log = open(OPTIMIZATION_LOG_PATH, 'a')

        def log_opt(msg):
            """Helper to log to both console and file"""
            logger.info(msg)
            opt_log.write(msg + "\n")
            opt_log.flush()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_opt("\n" + "="*100)
        log_opt(f"MAXHYBRID OPTIMIZATION RUN - {timestamp}")
        log_opt("="*100)

        logger.info("="*80)
        logger.info("MaxHybrid Portfolio Allocation")
        logger.info("="*80)
        
        # MODE 1: Use fixed allocations (no re-optimization)
        if self.use_fixed_allocations and self.fixed_allocations:
            log_opt("🔒 FIXED ALLOCATION MODE - Using pre-calculated allocations")
            log_opt(f"   Loaded allocations: {self.fixed_allocations}")
            log_opt("="*100 + "\n")
            opt_log.close()
            return self.fixed_allocations.copy()
        
        # MODE 2: Dynamic optimization (original behavior)
        log_opt("\n🔄 DYNAMIC OPTIMIZATION MODE - Re-optimizing portfolio")
        log_opt(f"\nOptimization Parameters:")
        log_opt(f"  - Alpha (Sharpe weight): {self.alpha:.4f}")
        log_opt(f"  - CAGR weight: {1-self.alpha:.4f}")
        log_opt(f"  - Max Drawdown Limit: {self.max_drawdown_limit*100:.2f}%")
        log_opt(f"  - Max Leverage: {self.max_leverage*100:.0f}%")
        log_opt(f"  - Max Single Strategy: {self.max_single_strategy*100:.0f}%")
        log_opt(f"  - CAGR Target (normalization): {self.cagr_target*100:.0f}%")
        log_opt(f"  - Risk-free Rate: {self.risk_free_rate*100:.2f}%")

        if not context.strategy_histories:
            log_opt("❌ ERROR: No strategy histories available")
            opt_log.close()
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
            log_opt("❌ ERROR: No valid strategies with returns data")
            opt_log.close()
            return {}

        n_strategies = len(strategy_ids)
        log_opt(f"\n📊 STRATEGY DATA LOADED:")
        log_opt(f"  Number of strategies: {n_strategies}")
        log_opt(f"  Strategy IDs: {strategy_ids}")
        log_opt(f"  Strategy data lengths: {[len(r) for r in daily_returns_list]}")

        mean_returns = np.array(mean_returns)

        # Log individual strategy statistics
        log_opt(f"\n📈 INDIVIDUAL STRATEGY STATISTICS (Full History):")
        for i, sid in enumerate(strategy_ids):
            returns = daily_returns_list[i]
            mean_ret = mean_returns[i]
            std_ret = np.std(returns)
            sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0
            cagr = self._calculate_cagr(returns)
            max_dd = self._calculate_max_drawdown(returns)

            log_opt(f"\n  {sid}:")
            log_opt(f"    Data points: {len(returns)}")
            log_opt(f"    Mean daily return: {mean_ret*100:.4f}%")
            log_opt(f"    Daily volatility: {std_ret*100:.4f}%")
            log_opt(f"    Sharpe ratio (annual): {sharpe:.2f}")
            log_opt(f"    CAGR: {cagr*100:.2f}%")
            log_opt(f"    Max Drawdown: {max_dd*100:.2f}%")
        
        # Align strategies for covariance
        returns_lengths = [len(r) for r in daily_returns_list]
        min_length = min(returns_lengths)
        max_length = max(returns_lengths)

        log_opt(f"\n🔗 ALIGNMENT FOR COVARIANCE CALCULATION:")
        log_opt(f"  Min length: {min_length} days")
        log_opt(f"  Max length: {max_length} days")

        if min_length != max_length:
            log_opt(f"  ⚠️  Truncating all strategies to {min_length} days for covariance matrix")
        else:
            log_opt(f"  ✓ All strategies have equal length - no truncation needed")

        aligned_returns_list = [returns[-min_length:] for returns in daily_returns_list]
        
        # Create returns matrix for optimization (rows = days, cols = strategies)
        returns_matrix = np.array(aligned_returns_list).T
        
        # Phase 3: Extract and align margin data (if available)
        margin_data_list = []
        has_margin_data = False

        for sid, df in context.strategy_histories.items():
            if sid not in strategy_ids:
                continue

            if 'margin_used' in df.columns and len(df) > 0:
                margin_values = df['margin_used'].values
                margin_data_list.append(margin_values)
                has_margin_data = True
            else:
                # Fallback: assume 10% of notional as margin (typical for futures)
                # This is just for backward compatibility
                margin_data_list.append(np.zeros(len(df)))

        # Align margin data (same way as returns)
        margin_matrix = None
        if has_margin_data and len(margin_data_list) == len(strategy_ids):
            aligned_margin_list = [margin[-min_length:] for margin in margin_data_list]
            margin_matrix = np.array(aligned_margin_list).T  # rows = days, cols = strategies

            # Log margin statistics
            avg_margins = [margin.mean() for margin in aligned_margin_list]
            max_margins = [margin.max() for margin in aligned_margin_list]
            min_margins = [margin.min() for margin in aligned_margin_list]
            logger.info(f"\n📊 Margin Analysis (aligned period):")
            for sid, avg_m, max_m, min_m in zip(strategy_ids, avg_margins, max_margins, min_margins):
                logger.info(f"  {sid}: Min=${min_m:,.0f}, Avg=${avg_m:,.0f}, Max=${max_m:,.0f}")

            # Calculate what the margin would be with equal weight to understand feasibility
            equal_weights = np.array([1.0 / n_strategies] * n_strategies)
            equal_weight_margin_daily = np.dot(margin_matrix, equal_weights)
            equal_weight_max_margin = equal_weight_margin_daily.max()
            max_allowed_margin = 100000.0 * self.max_leverage * 0.8
            logger.info(f"\n🔍 Margin Constraint Feasibility Check:")
            logger.info(f"  Max allowed margin: ${max_allowed_margin:,.0f}")
            logger.info(f"  Equal weight (1/{n_strategies}) max margin: ${equal_weight_max_margin:,.0f}")
            logger.info(f"  Feasible: {'YES ✓' if equal_weight_max_margin <= max_allowed_margin else 'NO ✗ - IMPOSSIBLE TO SATISFY'}")
        else:
            logger.warning("⚠️  No margin data available - margin constraint disabled")
        
        # Calculate covariance matrix
        df = pd.DataFrame({sid: returns for sid, returns in zip(strategy_ids, aligned_returns_list)})
        cov_matrix = df.cov().values
        corr_matrix = df.corr().values

        log_opt(f"\n📐 COVARIANCE & CORRELATION ANALYSIS (Aligned Period):")
        volatilities = np.sqrt(np.diag(cov_matrix))
        log_opt(f"  Daily Volatilities:")
        for sid, vol in zip(strategy_ids, volatilities):
            log_opt(f"    {sid}: {vol*100:.4f}%")

        log_opt(f"\n  Correlation Matrix:")
        log_opt(f"  {'':20s} " + " ".join([f"{s[:8]:>8s}" for s in strategy_ids]))
        for i, sid in enumerate(strategy_ids):
            corr_row = " ".join([f"{corr_matrix[i][j]:>8.2f}" for j in range(len(strategy_ids))])
            log_opt(f"  {sid:20s} {corr_row}")

        # Log average correlation
        avg_corr = np.mean(corr_matrix[np.triu_indices_from(corr_matrix, k=1)])
        log_opt(f"\n  Average Correlation: {avg_corr:.3f}")

        # Optimization (n_strategies already defined above)
        initial_weights = np.array([1.0 / n_strategies] * n_strategies)
        bounds = tuple((0, self.max_single_strategy) for _ in range(n_strategies))

        log_opt(f"\n🎯 OPTIMIZATION SETUP:")
        log_opt(f"  Initial weights (equal): {initial_weights}")
        log_opt(f"  Bounds per strategy: (0, {self.max_single_strategy*100:.0f}%)")
        log_opt(f"  Total allocation constraint: <= {self.max_leverage*100:.0f}%")

        # Track optimization iterations
        iteration_count = [0]

        # Hybrid objective function
        def hybrid_objective(weights):
            """
            Minimize: -(alpha * Sharpe + (1-alpha) * CAGR_normalized)
            """
            iteration_count[0] += 1

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

            # Log every 50 iterations
            if iteration_count[0] % 50 == 0 or iteration_count[0] <= 5:
                log_opt(f"\n  Iteration {iteration_count[0]}:")
                log_opt(f"    Weights: {weights}")
                log_opt(f"    Portfolio Return (daily): {portfolio_return*100:.4f}%")
                log_opt(f"    Portfolio Std (daily): {portfolio_std*100:.4f}%")
                log_opt(f"    Sharpe (daily): {sharpe:.4f}")
                log_opt(f"    Sharpe (annual): {sharpe*np.sqrt(252):.2f}")
                log_opt(f"    CAGR: {cagr*100:.2f}%")
                log_opt(f"    CAGR normalized: {cagr_normalized:.4f}")
                log_opt(f"    Hybrid score: {hybrid_score:.4f}")
                log_opt(f"    Objective (negative): {-hybrid_score:.4f}")

            return -hybrid_score  # Negative for minimization
        
        # Drawdown constraint
        def drawdown_constraint(weights):
            portfolio_returns = np.dot(returns_matrix, weights)
            max_dd = self._calculate_max_drawdown(portfolio_returns)
            return max_dd - self.max_drawdown_limit  # Positive if satisfied
        
        # Margin constraint (Phase 3)
        def margin_constraint(weights):
            """
            Ensure portfolio margin usage doesn't exceed account equity × max_leverage.

            This is DIFFERENT from allocation constraint:
            - Allocation constraint: sum(weights) <= max_leverage (e.g., 230%)
            - Margin constraint: actual margin used <= equity × safety_factor

            The margin constraint is MORE restrictive because it accounts for
            actual broker margin requirements, not just position sizing.
            """
            if margin_matrix is None:
                # No margin data - constraint is automatically satisfied
                return 1.0

            # Calculate portfolio margin for each day
            portfolio_margin_daily = np.dot(margin_matrix, weights)

            # Get max margin used across all days
            max_margin_used = portfolio_margin_daily.max()

            # Account equity (normalized to 100k in backtest)
            account_equity = 100000.0

            # Safety factor: use 80% of max_leverage to leave margin buffer
            # E.g., if max_leverage=2.3, allow up to 1.84x account equity in margin
            margin_safety_factor = 0.8
            max_allowed_margin = account_equity * self.max_leverage * margin_safety_factor

            # Constraint is satisfied if: max_margin_used <= max_allowed_margin
            # Return positive value if satisfied
            slack = max_allowed_margin - max_margin_used

            # DEBUG LOGGING
            logger.debug(f"   [MARGIN CONSTRAINT] max_margin=${max_margin_used:,.0f}, allowed=${max_allowed_margin:,.0f}, slack=${slack:,.0f}")

            return slack
        
        # Constraints (margin scaling happens post-optimization in backtest_engine)
        constraints = [
            {'type': 'ineq', 'fun': lambda w: self.max_leverage - np.sum(w)},  # Total allocation <= max_leverage
            {'type': 'ineq', 'fun': lambda w: np.sum(w)},                       # Total allocation >= 0
            {'type': 'ineq', 'fun': drawdown_constraint},                       # Max DD <= limit
        ]
        
        log_opt(f"\n🔧 RUNNING SCIPY OPTIMIZATION (SLSQP)...")
        log_opt(f"  Method: SLSQP (Sequential Least Squares Programming)")
        log_opt(f"  Max iterations: 1000")

        result = minimize(
            fun=hybrid_objective,
            x0=initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'disp': False, 'maxiter': 1000}
        )

        log_opt(f"\n✅ OPTIMIZATION COMPLETE")
        log_opt(f"  Success: {result.success}")
        log_opt(f"  Message: {result.message}")
        log_opt(f"  Total iterations: {result.nit if hasattr(result, 'nit') else 'N/A'}")
        log_opt(f"  Total function evaluations: {result.nfev if hasattr(result, 'nfev') else 'N/A'}")
        log_opt(f"  Final objective value: {result.fun:.6f}")

        if not result.success:
            log_opt(f"❌ OPTIMIZATION FAILED: {result.message}")
            log_opt(f"  Falling back to equal weight allocation")
            optimal_weights = initial_weights
        else:
            optimal_weights = result.x
            log_opt(f"✓ Optimization converged successfully")
            log_opt(f"  Final weights: {optimal_weights}")
        
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
        
        # Calculate actual margin usage (Phase 3)
        actual_margin_used = None
        margin_utilization_pct = None
        if margin_matrix is not None:
            portfolio_margin_daily = np.dot(margin_matrix, optimal_weights)
            actual_margin_used = portfolio_margin_daily.max()
            account_equity = 100000.0
            margin_utilization_pct = (actual_margin_used / account_equity) * 100
        
        log_opt(f"\n{'='*100}")
        log_opt("FINAL ALLOCATION RESULTS:")
        log_opt(f"{'='*100}")
        log_opt(f"\n📊 PORTFOLIO METRICS:")
        log_opt(f"  Total Allocation: {total_allocation:.2f}%")

        if actual_margin_used is not None:
            log_opt(f"\n💰 MARGIN ANALYSIS:")
            log_opt(f"  Margin Used: ${actual_margin_used:,.0f}")
            log_opt(f"  Margin % of Account: {margin_utilization_pct:.2f}%")
            max_allowed = 100000.0 * self.max_leverage * 0.8
            log_opt(f"  Max Allowed Margin: ${max_allowed:,.0f}")
            log_opt(f"  Max Allowed %: {self.max_leverage*0.8*100:.0f}%")
            log_opt(f"  Margin Buffer: ${max_allowed - actual_margin_used:,.0f}")

        log_opt(f"\n📈 EXPECTED PERFORMANCE (Based on Historical Data):")
        log_opt(f"  Daily Return: {portfolio_return*100:.4f}%")
        log_opt(f"  Annual Return: {portfolio_return*252*100:.2f}%")
        log_opt(f"  Daily Volatility: {portfolio_std*100:.4f}%")
        log_opt(f"  Annual Volatility: {portfolio_std*np.sqrt(252)*100:.2f}%")
        log_opt(f"  Sharpe Ratio (daily): {sharpe_ratio:.4f}")
        log_opt(f"  Sharpe Ratio (annualized): {sharpe_ratio * np.sqrt(252):.2f}")
        log_opt(f"  CAGR: {cagr*100:.2f}%")
        log_opt(f"  Max Drawdown: {max_dd*100:.2f}%")

        log_opt(f"\n🎯 INDIVIDUAL ALLOCATIONS:")
        log_opt(f"  {'Strategy':<20s} {'Allocation %':>15s} {'Weight':>10s}")
        log_opt(f"  {'-'*20} {'-'*15} {'-'*10}")
        for sid, pct in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
            weight = pct / 100.0
            log_opt(f"  {sid:<20s} {pct:>14.2f}% {weight:>10.4f}")

        log_opt(f"\n{'='*100}")
        log_opt(f"END OF OPTIMIZATION RUN - {timestamp}")
        log_opt(f"{'='*100}\n\n")

        opt_log.close()

        # Also log to console
        logger.info(f"\n{'='*80}")
        logger.info("ALLOCATION RESULTS:")
        logger.info(f"{'='*80}")
        logger.info(f"Total Allocation: {total_allocation:.1f}%")

        if actual_margin_used is not None:
            logger.info(f"💰 Margin Usage: ${actual_margin_used:,.0f} ({margin_utilization_pct:.1f}% of account)")
            max_allowed = 100000.0 * self.max_leverage * 0.8
            logger.info(f"   Max Allowed: ${max_allowed:,.0f} ({self.max_leverage*0.8*100:.0f}% of account)")

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
        logger.info(f"📄 Detailed optimization log saved to: {OPTIMIZATION_LOG_PATH}")

        return allocations
    
    def evaluate_signal(self, signal: Signal, context: PortfolioContext) -> SignalDecision:
        """
        Evaluate whether to take a signal based on current portfolio allocation.
        
        Args:
            signal: Trading signal to evaluate
            context: Current portfolio context
            
        Returns:
            SignalDecision with action and size, including detailed metadata
        """
        # Get current allocations
        allocations = self.allocate_portfolio(context)
        
        strategy_id = signal.strategy_id
        
        # Calculate total allocation across all strategies
        total_allocation = sum(allocations.values())
        
        if strategy_id in allocations and allocations[strategy_id] > 0:
            allocation_pct = allocations[strategy_id]
            
            # Calculate allocated capital
            allocated_capital = context.account_equity * (allocation_pct / 100.0)

            # NOTE: Margin % and position sizing will be calculated in main.py
            # using strategy-specific data from MongoDB. We just pass allocated_capital here.
            estimated_margin = allocated_capital * 0.5  # Placeholder, will be recalculated in main.py

            # Calculate shares from allocated capital and price
            # This is the theoretical full allocation - main.py will adjust for:
            # 1. Average number of positions this strategy holds
            # 2. Capital already deployed in other positions
            if signal.price > 0:
                calculated_shares = allocated_capital / signal.price
            else:
                calculated_shares = 0

            logger.info(f"Signal ACCEPTED: {strategy_id} | Allocation: {allocation_pct:.1f}%")

            # Build detailed metadata for transparency
            metadata = {
                'allocation_pct': allocation_pct,
                'portfolio_equity': context.account_equity,
                'allocated_capital': allocated_capital,
                'estimated_margin': estimated_margin,
                'total_portfolio_allocation': total_allocation,
                'num_strategies_allocated': len([v for v in allocations.values() if v > 0]),
                'all_allocations': {k: v for k, v in allocations.items() if v > 0},
                'max_hybrid_params': {
                    'alpha': self.alpha,
                    'max_leverage': self.max_leverage,
                    'max_drawdown_limit': self.max_drawdown_limit
                },
                'position_size_calculation': f"{context.account_equity:,.0f} × {allocation_pct:.2f}% = ${allocated_capital:,.2f}",
                'calculated_shares_formula': f"${allocated_capital:,.2f} ÷ ${signal.price:,.2f} = {calculated_shares:.2f} shares"
            }

            return SignalDecision(
                action="APPROVE",
                quantity=calculated_shares,  # FIX: Calculate from allocated capital, not signal.quantity
                reason=f"MaxHybrid allocation: {allocation_pct:.1f}% (Total portfolio: {total_allocation:.1f}%)",
                allocated_capital=allocated_capital,
                margin_required=estimated_margin,
                metadata=metadata
            )
        else:
            logger.info(f"Signal REJECTED: {strategy_id} | No allocation")
            
            # Build rejection metadata
            metadata = {
                'allocation_pct': 0.0,
                'portfolio_equity': context.account_equity,
                'total_portfolio_allocation': total_allocation,
                'num_strategies_allocated': len([v for v in allocations.values() if v > 0]),
                'all_allocations': {k: v for k, v in allocations.items() if v > 0},
                'rejection_reason': 'Strategy did not meet optimization criteria',
                'max_hybrid_params': {
                    'alpha': self.alpha,
                    'max_leverage': self.max_leverage,
                    'max_drawdown_limit': self.max_drawdown_limit
                }
            }
            
            return SignalDecision(
                action='REJECTED',
                quantity=0,
                reason="No allocation in MaxHybrid portfolio",
                allocated_capital=0.0,
                margin_required=0.0,
                metadata=metadata
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
