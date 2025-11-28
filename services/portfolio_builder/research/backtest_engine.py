"""
Walk-Forward Backtest Engine
Runs walk-forward analysis for portfolio constructors.
"""
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ..portfolio_constructor.base import PortfolioConstructor
from ..portfolio_constructor.context import PortfolioContext
from .tearsheet_generator import generate_tearsheet


class WalkForwardBacktest:
    """
    Walk-forward backtesting engine for portfolio constructors.
    
    Process:
    1. Split data into train/test windows
    2. Train on in-sample data (optimize allocations)
    3. Test on out-of-sample data (apply allocations)
    4. Roll forward and repeat
    """
    
    def __init__(
        self,
        constructor: PortfolioConstructor,
        train_days: int = 252,
        test_days: int = 63,
        walk_forward_type: str = 'anchored',  # 'anchored' or 'rolling'
        apply_drawdown_protection: bool = False,
        max_drawdown_threshold: float = 0.20,
        output_dir: Optional[str] = None
    ):
        """
        Initialize walk-forward backtest engine.
        
        Args:
            constructor: Portfolio constructor to test
            train_days: Number of days for training window
            test_days: Number of days for test window (non-overlapping)
            walk_forward_type: 'anchored' (expanding train) or 'rolling' (fixed train window)
            apply_drawdown_protection: If True, reduce leverage when drawdown exceeds threshold
            max_drawdown_threshold: Drawdown threshold for protection (e.g., 0.20 = 20%)
            output_dir: Directory to save outputs (default: constructor's outputs/ folder)
            
        Walk-forward types:
        - anchored: Train on all data from start to test_start (expanding window)
                   Window 1: Train[0:252], Test[252:315]
                   Window 2: Train[0:315], Test[315:378]
        - rolling: Train on fixed-size window before test (rolling window)
                   Window 1: Train[0:252], Test[252:315]
                   Window 2: Train[63:315], Test[315:378]
        """
        self.constructor = constructor
        self.train_days = train_days
        self.test_days = test_days
        self.walk_forward_type = walk_forward_type
        self.apply_drawdown_protection = apply_drawdown_protection
        self.max_drawdown_threshold = max_drawdown_threshold
        self.test_periods = []
        
        # Set output directory - use constructor's outputs folder if not specified
        if output_dir is None:
            # Get the constructor's module file path
            constructor_module = constructor.__class__.__module__
            # e.g., 'services.cerebro_service.portfolio_constructor.max_hybrid.strategy'
            # We want absolute path: services/cerebro_service/portfolio_constructor/max_hybrid/outputs
            module_parts = constructor_module.split('.')
            if 'portfolio_constructor' in module_parts:
                idx = module_parts.index('portfolio_constructor')
                constructor_name = module_parts[idx + 1]  # e.g., 'max_hybrid'
                # Build absolute path to services/cerebro_service/portfolio_constructor/{constructor_name}/outputs
                current_file_dir = os.path.dirname(os.path.abspath(__file__))  # research/
                cerebro_service_dir = os.path.dirname(current_file_dir)  # services/cerebro_service/
                output_dir = os.path.join(cerebro_service_dir, 'portfolio_constructor', constructor_name, 'outputs')
            else:
                # Fallback to root outputs folder
                current_file_dir = os.path.dirname(os.path.abspath(__file__))
                cerebro_service_dir = os.path.dirname(current_file_dir)
                output_dir = os.path.join(cerebro_service_dir, 'outputs', 'portfolio_tearsheets')
        
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    
    def run(self, strategies_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Run walk-forward backtest.
        
        Args:
            strategies_data: Dict of {strategy_id: {dates: [...], returns: [...], ...}}
            
        Returns:
            Dict with:
            - portfolio_equity_curve: List of equity values
            - portfolio_returns: List of portfolio returns
            - dates: List of dates
            - allocations_history: List of allocation dicts over time
        """
        print("\n" + "="*80)
        print("WALK-FORWARD BACKTEST")
        print("="*80)
        
        # Step 1: Align all strategies to common dates
        print("\n[1/4] Aligning strategy data...")
        aligned_data = self._align_strategies(strategies_data)
        
        if not aligned_data:
            raise ValueError("No valid strategy data after alignment")
        
        all_dates = aligned_data['dates']
        returns_matrix = aligned_data['returns_matrix']  # DataFrame
        margin_matrix = aligned_data.get('margin_matrix')  # Optional
        notional_matrix = aligned_data.get('notional_matrix')  # Optional
        account_equity_matrix = aligned_data.get('account_equity_matrix')  # Optional - NEW
        strategy_ids = list(returns_matrix.columns)
        
        print(f"  ✓ Aligned {len(strategy_ids)} strategies")
        print(f"  ✓ Date range: {all_dates[0]} to {all_dates[-1]}")
        print(f"  ✓ Total days: {len(all_dates)}")
        
        # Phase 1: Log margin/notional data availability and patterns
        if margin_matrix is not None:
            print(f"\n  📊 Margin Data Analysis:")
            print(f"    ✓ Margin data available for all strategies")
            for sid in strategy_ids[:5]:  # Show first 5
                margin_values = margin_matrix[sid].values
                avg_margin = margin_values.mean()
                max_margin = margin_values.max()
                print(f"    - {sid}: Avg=${avg_margin:,.0f}, Max=${max_margin:,.0f}")
            if len(strategy_ids) > 5:
                print(f"    ... and {len(strategy_ids)-5} more strategies")
        else:
            print(f"\n  ⚠️  No margin data available (using legacy format)")
        
        if notional_matrix is not None:
            print(f"\n  📊 Notional Data Analysis:")
            print(f"    ✓ Notional data available for all strategies")
            for sid in strategy_ids[:5]:  # Show first 5
                notional_values = notional_matrix[sid].values
                avg_notional = notional_values.mean()
                max_notional = notional_values.max()
                print(f"    - {sid}: Avg=${avg_notional:,.0f}, Max=${max_notional:,.0f}")
            if len(strategy_ids) > 5:
                print(f"    ... and {len(strategy_ids)-5} more strategies")
        else:
            print(f"\n  ⚠️  No notional data available (using legacy format)")
        
        # Step 2: Run walk-forward windows (non-overlapping test periods)
        print(f"\n[2/4] Running walk-forward windows ({self.walk_forward_type})...")
        
        window_results = []
        window_count = 0
        global_peak_equity = 100000.0  # Track peak across ALL windows
        current_equity = 100000.0      # Track current equity
        
        # Walk forward: each test period is distinct (no overlap)
        test_start_idx = self.train_days  # First test starts after training period
        
        while test_start_idx + self.test_days <= len(all_dates):
            window_count += 1
            
            # Determine training window based on type
            if self.walk_forward_type == 'anchored':
                # Anchored: Train from start to test_start (expanding window)
                train_start_idx = 0
            else:  # rolling
                # Rolling: Train on fixed window before test
                train_start_idx = max(0, test_start_idx - self.train_days)
            
            train_dates = all_dates[train_start_idx:test_start_idx]
            test_dates = all_dates[test_start_idx:test_start_idx + self.test_days]
            
            train_returns = returns_matrix.iloc[train_start_idx:test_start_idx]
            test_returns = returns_matrix.iloc[test_start_idx:test_start_idx + self.test_days]
            
            # Extract margin/notional/account_equity data for training and test periods (if available)
            train_margin = margin_matrix.iloc[train_start_idx:test_start_idx] if margin_matrix is not None else None
            train_notional = notional_matrix.iloc[train_start_idx:test_start_idx] if notional_matrix is not None else None
            train_account_equity = account_equity_matrix.iloc[train_start_idx:test_start_idx] if account_equity_matrix is not None else None
            
            test_margin = margin_matrix.iloc[test_start_idx:test_start_idx + self.test_days] if margin_matrix is not None else None
            test_notional = notional_matrix.iloc[test_start_idx:test_start_idx + self.test_days] if notional_matrix is not None else None
            test_account_equity = account_equity_matrix.iloc[test_start_idx:test_start_idx + self.test_days] if account_equity_matrix is not None else None
            
            print(f"\n  Window {window_count}:")
            print(f"    Train: {train_dates[0]} to {train_dates[-1]} ({len(train_dates)} days)")
            print(f"    Test:  {test_dates[0]} to {test_dates[-1]} ({len(test_dates)} days)")
            
            # Build context for training period
            train_context = self._build_context(
                returns_df=train_returns,
                margin_df=train_margin,
                notional_df=train_notional,
                is_backtest=True,
                current_date=train_dates[-1]
            )
            
            # Get allocations from constructor
            allocations = self.constructor.allocate_portfolio(train_context)

            print(f"    📊 ALLOCATION DECISION TRACKING:")
            print(f"       [STEP 1] Optimizer output:")
            original_allocations = allocations.copy()
            original_total = sum(allocations.values())
            print(f"         Total allocation from optimizer: {original_total:.2f}%")
            print(f"         Strategies allocated: {len(allocations)}")
            for sid, pct in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
                print(f"           - {sid}: {pct:.2f}%")

            # POST-OPTIMIZATION MARGIN SCALING
            # Scale allocations if margin usage exceeds limits
            if allocations and test_margin is not None and len(allocations) > 0:
                # Convert allocations (%) to weights (decimal)
                total_alloc = sum(allocations.values())
                if total_alloc > 0:
                    weights = {sid: (pct / 100.0) for sid, pct in allocations.items()}

                    # Margin limit parameters (needed for calculation)
                    account_equity = current_equity
                    max_leverage = 2.3  # Should match constructor's max_leverage
                    margin_safety_factor = 0.8
                    max_allowed_margin = account_equity * max_leverage * margin_safety_factor

                    # Calculate portfolio margin for each day in test period
                    # FIXED: Normalize margin to percentages using account_equity
                    portfolio_margin_daily = []
                    for idx in range(len(test_dates)):
                        daily_margin_pct = 0.0  # Portfolio margin as % of portfolio equity

                        # Use account_equity to normalize margin into percentages
                        if test_account_equity is not None:
                            for sid, weight in weights.items():
                                if sid in test_margin.columns and sid in test_account_equity.columns:
                                    # Get strategy's margin and account equity for this day
                                    strategy_margin = test_margin[sid].iloc[idx]
                                    strategy_account_equity = test_account_equity[sid].iloc[idx]

                                    # Calculate strategy's margin as % of their account equity
                                    if strategy_account_equity > 0:
                                        strategy_margin_pct = strategy_margin / strategy_account_equity
                                    else:
                                        strategy_margin_pct = 0.0

                                    # Add weighted contribution to portfolio margin %
                                    daily_margin_pct += weight * strategy_margin_pct
                        else:
                            # FALLBACK: If no account_equity data, use old (broken) method
                            # This will trigger the scaling but at least won't crash
                            for sid, weight in weights.items():
                                if sid in test_margin.columns:
                                    daily_margin_pct += weight * test_margin[sid].iloc[idx] / account_equity

                        # Convert portfolio margin % to absolute dollars for current equity
                        daily_margin_dollars = daily_margin_pct * account_equity
                        portfolio_margin_daily.append(daily_margin_dollars)

                    max_margin_used = max(portfolio_margin_daily)
                    avg_margin_used = sum(portfolio_margin_daily) / len(portfolio_margin_daily)

                    print(f"\n       [STEP 2] Post-optimization margin check (OOS test period):")
                    print(f"         Current account equity: ${account_equity:,.2f}")
                    print(f"         Max leverage setting: {max_leverage}x")
                    print(f"         Margin safety factor: {margin_safety_factor}")
                    print(f"         Max allowed margin: ${max_allowed_margin:,.0f} ({max_allowed_margin/account_equity*100:.1f}% of equity)")
                    print(f"         Portfolio margin with optimizer weights:")
                    print(f"           - Max margin (worst day): ${max_margin_used:,.0f} ({max_margin_used/account_equity*100:.1f}% of equity)")
                    print(f"           - Avg margin (daily): ${avg_margin_used:,.0f} ({avg_margin_used/account_equity*100:.1f}% of equity)")

                    if max_margin_used > max_allowed_margin:
                        # Scale down ALL allocations proportionally
                        scale_factor = max_allowed_margin / max_margin_used
                        allocations = {sid: pct * scale_factor for sid, pct in allocations.items()}
                        new_total = sum(allocations.values())

                        print(f"\n         ⚠️  MARGIN LIMIT EXCEEDED - SCALING DOWN ALLOCATIONS")
                        print(f"           Reason: Max margin ${max_margin_used:,.0f} > Allowed ${max_allowed_margin:,.0f}")
                        print(f"           Scale factor applied: {scale_factor:.4f}x")
                        print(f"           Total allocation BEFORE scaling: {original_total:.2f}%")
                        print(f"           Total allocation AFTER scaling: {new_total:.2f}%")
                        print(f"           Reduction: {original_total - new_total:.2f}% ({(1-scale_factor)*100:.1f}% decrease)")
                    else:
                        print(f"\n         ✅ MARGIN CHECK PASSED - No scaling needed")
                        print(f"           Max margin ${max_margin_used:,.0f} <= Allowed ${max_allowed_margin:,.0f}")
                        print(f"           Buffer remaining: ${max_allowed_margin - max_margin_used:,.0f}")

            # Apply drawdown protection at window level
            print(f"\n       [STEP 3] Drawdown protection check:")
            if self.apply_drawdown_protection and global_peak_equity > 0:
                current_dd = (global_peak_equity - current_equity) / global_peak_equity
                print(f"         Drawdown protection: ENABLED")
                print(f"         Current equity: ${current_equity:,.2f}")
                print(f"         Peak equity: ${global_peak_equity:,.2f}")
                print(f"         Current drawdown: {current_dd*100:.2f}%")
                print(f"         Drawdown threshold: {self.max_drawdown_threshold*100:.2f}%")

                if current_dd > self.max_drawdown_threshold:
                    # Reduce allocations proportionally
                    excess_dd = current_dd - self.max_drawdown_threshold
                    reduction_factor = max(0.0, 1.0 - (excess_dd / self.max_drawdown_threshold))
                    before_dd_total = sum(allocations.values())
                    allocations = {k: v * reduction_factor for k, v in allocations.items()}
                    after_dd_total = sum(allocations.values())

                    print(f"\n         ⚠️  DRAWDOWN THRESHOLD EXCEEDED - REDUCING ALLOCATIONS")
                    print(f"           Excess drawdown: {excess_dd*100:.2f}%")
                    print(f"           Reduction factor: {reduction_factor:.4f}x")
                    print(f"           Total allocation BEFORE DD scaling: {before_dd_total:.2f}%")
                    print(f"           Total allocation AFTER DD scaling: {after_dd_total:.2f}%")
                    print(f"           Reduction: {before_dd_total - after_dd_total:.2f}% ({(1-reduction_factor)*100:.1f}% decrease)")
                else:
                    print(f"         ✅ DRAWDOWN CHECK PASSED - No reduction needed")
            else:
                print(f"         Drawdown protection: DISABLED")

            print(f"\n       [FINAL] Final allocations after all adjustments:")
            final_total = sum(allocations.values())
            print(f"         Total allocation: {final_total:.2f}%")
            print(f"         Number of strategies: {len(allocations)}")
            print(f"         Total reduction from optimizer: {original_total - final_total:.2f}% ({(1-final_total/original_total)*100:.1f}% decrease)")
            print(f"    " + "="*80)
            
            # Apply allocations to test period
            window_result = self._apply_allocations(
                allocations=allocations,
                test_returns=test_returns,
                test_dates=test_dates,
                test_margin=test_margin,
                test_notional=test_notional,
                test_account_equity=test_account_equity,
                starting_equity=current_equity,
                global_peak_equity=global_peak_equity if self.apply_drawdown_protection else None
            )
            
            # Calculate IN-SAMPLE (training period) metrics using the allocations
            weights = {sid: (pct / 100.0) for sid, pct in allocations.items()}
            train_portfolio_returns = []
            for idx in range(len(train_returns)):
                daily_ret = 0.0
                for sid, weight in weights.items():
                    if sid in train_returns.columns:
                        daily_ret += weight * train_returns[sid].iloc[idx]
                train_portfolio_returns.append(daily_ret)

            train_portfolio_returns_arr = np.array(train_portfolio_returns)
            in_sample_cagr = self._calculate_cagr(train_portfolio_returns_arr)
            in_sample_sharpe = (train_portfolio_returns_arr.mean() / train_portfolio_returns_arr.std() * np.sqrt(252)) if train_portfolio_returns_arr.std() > 0 else 0
            in_sample_max_dd = self._calculate_max_drawdown(train_portfolio_returns_arr)
            in_sample_volatility = train_portfolio_returns_arr.std() * np.sqrt(252)

            # Calculate OUT-OF-SAMPLE (test period) metrics
            test_portfolio_returns_arr = np.array(window_result['portfolio_returns'])
            oos_cagr = self._calculate_cagr(test_portfolio_returns_arr)
            oos_sharpe = (test_portfolio_returns_arr.mean() / test_portfolio_returns_arr.std() * np.sqrt(252)) if test_portfolio_returns_arr.std() > 0 else 0
            oos_max_dd = self._calculate_max_drawdown(test_portfolio_returns_arr)
            oos_volatility = test_portfolio_returns_arr.std() * np.sqrt(252)

            # Update equity tracking
            if len(window_result['portfolio_returns']) > 0:
                for ret in window_result['portfolio_returns']:
                    current_equity *= (1 + ret)
                    global_peak_equity = max(global_peak_equity, current_equity)

            window_results.append({
                'window_num': window_count,
                'train_start': train_dates[0],
                'train_end': train_dates[-1],
                'test_start': test_dates[0],
                'test_end': test_dates[-1],
                'allocations': allocations,
                'portfolio_returns': window_result['portfolio_returns'],
                'portfolio_margin': window_result.get('portfolio_margin', []),
                'portfolio_notional': window_result.get('portfolio_notional', []),
                'dates': test_dates,
                # IN-SAMPLE (optimization period) metrics
                'in_sample_cagr': in_sample_cagr,
                'in_sample_sharpe': in_sample_sharpe,
                'in_sample_max_dd': in_sample_max_dd,
                'in_sample_volatility': in_sample_volatility,
                # OUT-OF-SAMPLE (test period) metrics
                'oos_cagr': oos_cagr,
                'oos_sharpe': oos_sharpe,
                'oos_max_dd': oos_max_dd,
                'oos_volatility': oos_volatility
            })
            
            # Step forward to next NON-OVERLAPPING test period
            test_start_idx += self.test_days
        
        print(f"\n  ✓ Completed {window_count} walk-forward windows")
        
        # Step 3: Combine results
        print("\n[3/4] Combining results...")
        combined_results = self._combine_windows(window_results)
        
        print(f"  ✓ Portfolio equity curve: {len(combined_results['portfolio_equity_curve'])} points")
        
        # Step 4: Calculate final metrics
        print("\n[4/4] Calculating metrics...")
        metrics = self._calculate_metrics(combined_results)
        
        print(f"  ✓ Total Return: {metrics['total_return_pct']:.2f}%")
        print(f"  ✓ CAGR: {metrics['cagr_pct']:.2f}%")
        print(f"  ✓ Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  ✓ Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        
        combined_results['metrics'] = metrics
        combined_results['window_allocations'] = window_results  # Include for CSV export
        combined_results['strategies_data'] = strategies_data  # Include for correlation matrix
        
        # Step 5: Save all outputs
        print("\n[5/5] Saving outputs...")
        self._save_outputs(combined_results, strategies_data)
        
        return combined_results
    
    def _align_strategies(self, strategies_data: Dict) -> Dict:
        """
        Align all strategies to master timeline (outer join).
        
        Uses the UNION of all dates (master timeline approach).
        Strategies with missing dates get 0% returns (fillna(0)).
        This prevents truncating to the shortest strategy.
        
        Also aligns margin_used, notional_value, and account_equity data if available.
        """
        # Convert to DataFrame format
        dfs_returns = []
        dfs_margin = []
        dfs_notional = []
        dfs_account_equity = []
        
        for sid, data in strategies_data.items():
            # Returns data
            df_ret = pd.DataFrame({
                'date': data['dates'],
                sid: data['returns']
            })
            df_ret['date'] = pd.to_datetime(df_ret['date'])
            df_ret = df_ret.set_index('date')
            df_ret = df_ret.sort_index()
            dfs_returns.append(df_ret)
            
            # Margin data (if available)
            if 'margin_used' in data and data['margin_used']:
                df_mar = pd.DataFrame({
                    'date': data['dates'],
                    sid: data['margin_used']
                })
                df_mar['date'] = pd.to_datetime(df_mar['date'])
                df_mar = df_mar.set_index('date')
                df_mar = df_mar.sort_index()
                dfs_margin.append(df_mar)
            
            # Notional data (if available)
            if 'notional' in data and data['notional']:
                df_not = pd.DataFrame({
                    'date': data['dates'],
                    sid: data['notional']
                })
                df_not['date'] = pd.to_datetime(df_not['date'])
                df_not = df_not.set_index('date')
                df_not = df_not.sort_index()
                dfs_notional.append(df_not)
            
            # Account equity data (if available) - NEW
            if 'account_equity' in data and data['account_equity']:
                df_eq = pd.DataFrame({
                    'date': data['dates'],
                    sid: data['account_equity']
                })
                df_eq['date'] = pd.to_datetime(df_eq['date'])
                df_eq = df_eq.set_index('date')
                df_eq = df_eq.sort_index()
                dfs_account_equity.append(df_eq)
        
        # Merge returns - OUTER JOIN for master timeline
        merged_returns = pd.concat(dfs_returns, axis=1, join='outer')
        
        if len(merged_returns) == 0:
            return {}
        
        # Fill NaN with 0 (strategies not trading on certain dates)
        merged_returns = merged_returns.fillna(0)
        merged_returns = merged_returns.sort_index()
        
        # Merge margin data if available
        merged_margin = None
        if dfs_margin:
            merged_margin = pd.concat(dfs_margin, axis=1, join='outer')
            merged_margin = merged_margin.fillna(0)
            merged_margin = merged_margin.sort_index()
        
        # Merge notional data if available
        merged_notional = None
        if dfs_notional:
            merged_notional = pd.concat(dfs_notional, axis=1, join='outer')
            merged_notional = merged_notional.fillna(0)
            merged_notional = merged_notional.sort_index()
        
        # Merge account_equity data if available - NEW
        merged_account_equity = None
        if dfs_account_equity:
            merged_account_equity = pd.concat(dfs_account_equity, axis=1, join='outer')
            # For account equity, forward fill is more appropriate than 0
            merged_account_equity = merged_account_equity.ffill()
            merged_account_equity = merged_account_equity.fillna(100000)  # Default if no data
            merged_account_equity = merged_account_equity.sort_index()
        
        result = {
            'dates': merged_returns.index.tolist(),
            'returns_matrix': merged_returns
        }
        
        if merged_margin is not None:
            result['margin_matrix'] = merged_margin
        
        if merged_notional is not None:
            result['notional_matrix'] = merged_notional
        
        if merged_account_equity is not None:
            result['account_equity_matrix'] = merged_account_equity
        
        return result
    
    def _build_context(
        self,
        returns_df: pd.DataFrame,
        margin_df: pd.DataFrame = None,
        notional_df: pd.DataFrame = None,
        is_backtest: bool = True,
        current_date: datetime = None
    ) -> PortfolioContext:
        """Build portfolio context from returns data"""
        # Convert returns DataFrame to strategy_histories format
        strategy_histories = {}
        for col in returns_df.columns:
            hist_data = {'returns': returns_df[col].values}
            
            # Add margin data if available
            if margin_df is not None and col in margin_df.columns:
                hist_data['margin_used'] = margin_df[col].values
            
            # Add notional data if available
            if notional_df is not None and col in notional_df.columns:
                hist_data['notional_value'] = notional_df[col].values
            
            strategy_histories[col] = pd.DataFrame(hist_data)
        
        # Calculate correlation matrix
        correlation_matrix = returns_df.corr()
        
        # Build context
        context = PortfolioContext(
            account_equity=100000.0,  # Starting capital (arbitrary for backtest)
            margin_used=0.0,
            margin_available=50000.0,
            cash_balance=100000.0,
            open_positions=[],
            open_orders=[],
            current_allocations={},
            strategy_histories=strategy_histories,
            correlation_matrix=correlation_matrix,
            is_backtest=is_backtest,
            current_date=current_date
        )
        
        return context
    
    def _apply_allocations(
        self,
        allocations: Dict[str, float],
        test_returns: pd.DataFrame,
        test_dates: List[datetime],
        test_margin: pd.DataFrame = None,
        test_notional: pd.DataFrame = None,
        test_account_equity: pd.DataFrame = None,
        starting_equity: float = 100000.0,
        global_peak_equity: float = None
    ) -> Dict:
        """
        Apply allocations to test period and calculate portfolio returns.
        Optionally applies drawdown protection by reducing leverage when DD exceeds threshold.
        
        Args:
            test_margin: Optional margin data for test period
            test_notional: Optional notional data for test period
            test_account_equity: Optional account equity data for test period (for correct margin % calc)
            global_peak_equity: If provided (for drawdown protection), use this as the peak
                              instead of the peak within this window only
        """
        # Convert allocation percentages to weights
        total_alloc = sum(allocations.values())
        
        if total_alloc == 0:
            # No allocations, return zeros with all required fields
            n_days = len(test_dates)
            return {
                'portfolio_returns': [0.0] * n_days,
                'portfolio_margin': [0.0] * n_days,
                'portfolio_notional': [0.0] * n_days,
                'leverage_adjustments': [1.0] * n_days if self.apply_drawdown_protection else None
            }
        
        # Normalize allocations to weights (handle leverage)
        base_weights = {sid: (pct / 100.0) for sid, pct in allocations.items()}
        
        # Calculate portfolio returns for each day
        portfolio_returns = []
        portfolio_margin = []
        portfolio_notional = []
        equity_curve = [starting_equity]
        leverage_adjustments = []
        protection_triggered_count = 0
        
        # Track peak - use global if provided, and update it as we go
        if global_peak_equity is not None:
            peak_equity = global_peak_equity
        else:
            peak_equity = starting_equity
        
        for idx in range(len(test_returns)):
            # Apply drawdown protection if enabled
            current_leverage_multiplier = 1.0
            
            if self.apply_drawdown_protection and len(equity_curve) > 1:
                # Calculate current drawdown using peak (which updates within window)
                current_equity = equity_curve[-1]
                current_dd = (peak_equity - current_equity) / peak_equity
                
                # HARD STOP: If DD exceeds threshold, go to cash (zero leverage)
                if current_dd > self.max_drawdown_threshold:
                    current_leverage_multiplier = 0.0  # Flatten all positions
                    protection_triggered_count += 1
            
            # Apply (possibly reduced) weights
            active_weights = {sid: weight * current_leverage_multiplier 
                            for sid, weight in base_weights.items()}
            
            # Calculate daily return
            daily_return = 0.0
            for sid, weight in active_weights.items():
                if sid in test_returns.columns:
                    daily_return += weight * test_returns[sid].iloc[idx]
            
            # Calculate portfolio margin and notional using CORRECT methodology
            # STEP 1: Calculate per-strategy margin as % of their account equity
            # STEP 2: Weight by allocation to get portfolio margin %
            # STEP 3: Apply to current portfolio equity
            
            daily_margin_pct = 0.0  # Portfolio margin as % of portfolio equity
            daily_notional = 0.0
            
            # NEW CORRECT APPROACH: Use account_equity to normalize margin into percentages
            if test_margin is not None and test_account_equity is not None:
                for sid, weight in active_weights.items():
                    if sid in test_margin.columns and sid in test_account_equity.columns:
                        # Get strategy's margin and account equity for this day
                        strategy_margin = test_margin[sid].iloc[idx]
                        strategy_account_equity = test_account_equity[sid].iloc[idx]
                        
                        # Calculate strategy's margin as % of their account equity
                        if strategy_account_equity > 0:
                            strategy_margin_pct = strategy_margin / strategy_account_equity
                        else:
                            strategy_margin_pct = 0.0
                        
                        # Add weighted contribution to portfolio margin %
                        daily_margin_pct += weight * strategy_margin_pct
            
            # FALLBACK: If no account_equity data, use old scaling method (less accurate)
            elif test_margin is not None:
                for sid, weight in active_weights.items():
                    if sid in test_margin.columns:
                        daily_margin_pct += weight * test_margin[sid].iloc[idx] / starting_equity
            
            # Calculate notional value (still uses simple weighted sum)
            if test_notional is not None:
                for sid, weight in active_weights.items():
                    if sid in test_notional.columns:
                        daily_notional += weight * test_notional[sid].iloc[idx]
            
            # Apply portfolio margin % to current portfolio equity to get absolute margin $
            current_equity = equity_curve[-1]
            daily_margin_dollars = daily_margin_pct * current_equity
            
            portfolio_returns.append(daily_return)
            portfolio_margin.append(daily_margin_dollars)
            portfolio_notional.append(daily_notional)
            leverage_adjustments.append(current_leverage_multiplier)
            
            # Update equity curve and peak
            new_equity = current_equity * (1 + daily_return)
            equity_curve.append(new_equity)
            
            # ALWAYS update peak to track highest point reached
            peak_equity = max(peak_equity, new_equity)
        
        if self.apply_drawdown_protection and protection_triggered_count > 0:
            print(f"      DD Protection triggered {protection_triggered_count}/{len(test_returns)} days")
        
        return {
            'portfolio_returns': portfolio_returns,
            'portfolio_margin': portfolio_margin,
            'portfolio_notional': portfolio_notional,
            'leverage_adjustments': leverage_adjustments if self.apply_drawdown_protection else None
        }
    
    def _combine_windows(self, window_results: List[Dict]) -> Dict:
        """Combine results from all windows into single equity curve"""
        all_returns = []
        all_dates = []
        all_margin = []
        all_notional = []
        allocations_history = []
        
        for window in window_results:
            all_returns.extend(window['portfolio_returns'])
            all_dates.extend(window['dates'])
            all_margin.extend(window.get('portfolio_margin', [0] * len(window['dates'])))
            all_notional.extend(window.get('portfolio_notional', [0] * len(window['dates'])))
            allocations_history.append({
                'date': window['test_start'],
                'allocations': window['allocations']
            })
        
        # Create DataFrame to sort by date
        df = pd.DataFrame({
            'date': all_dates,
            'returns': all_returns,
            'margin': all_margin,
            'notional': all_notional
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Extract sorted values
        all_dates = df['date'].tolist()
        all_returns = df['returns'].tolist()
        all_margin = df['margin'].tolist()
        all_notional = df['notional'].tolist()
        
        # Calculate equity curve
        starting_equity = 100000.0
        equity_curve = [starting_equity]
        
        for ret in all_returns:
            new_equity = equity_curve[-1] * (1 + ret)
            equity_curve.append(new_equity)
        
        # Remove last element (one extra from initialization)
        equity_curve = equity_curve[:-1]
        
        return {
            'portfolio_returns': all_returns,
            'portfolio_equity_curve': equity_curve,
            'portfolio_margin': all_margin,
            'portfolio_notional': all_notional,
            'dates': all_dates,
            'allocations_history': allocations_history
        }
    
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

    def _calculate_metrics(self, results: Dict) -> Dict:
        """Calculate performance metrics"""
        returns = np.array(results['portfolio_returns'])
        equity_curve = np.array(results['portfolio_equity_curve'])
        
        # Total return
        total_return = (equity_curve[-1] / equity_curve[0] - 1) * 100
        
        # CAGR
        days = len(returns)
        years = days / 252.0
        cagr = ((equity_curve[-1] / equity_curve[0]) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # Sharpe ratio
        mean_return = returns.mean()
        std_return = returns.std()
        sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        
        # Max drawdown
        cumulative_returns = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        return {
            'total_return_pct': total_return,
            'cagr_pct': cagr,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'total_days': len(returns),
            'annual_volatility_pct': std_return * np.sqrt(252) * 100
        }
    
    def _save_outputs(self, results: Dict, strategies_data: Dict):
        """
        Save all backtest outputs to files.
        
        Saves:
        1. Configuration JSON
        2. Portfolio equity curve CSV
        3. Allocations history CSV
        4. Correlation matrix CSV
        5. QuantStats HTML tearsheet
        """
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        constructor_name = self.constructor.__class__.__name__.replace('Constructor', '')
        base_filename = f"{constructor_name}_{timestamp}"
        
        # 1. Save configuration
        config = {
            'constructor': {
                'name': self.constructor.__class__.__name__,
                'type': constructor_name,
                'config': self.constructor.get_config()
            },
            'backtest': {
                'train_days': self.train_days,
                'test_days': self.test_days,
                'walk_forward_type': self.walk_forward_type,
                'apply_drawdown_protection': self.apply_drawdown_protection,
                'max_drawdown_threshold': self.max_drawdown_threshold
            },
            'timestamp': timestamp,
            'output_dir': self.output_dir
        }
        
        config_path = os.path.join(self.output_dir, f"{base_filename}_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"  ✓ Saved config: {config_path}")
        
        # 2. Save portfolio equity curve with margin and notional
        equity_df = pd.DataFrame({
            'date': results['dates'],
            'equity': results['portfolio_equity_curve'],
            'returns': results['portfolio_returns'],
            'margin_used': results.get('portfolio_margin', [0] * len(results['dates'])),
            'notional_value': results.get('portfolio_notional', [0] * len(results['dates']))
        })
        
        # Calculate margin_used as % of equity
        equity_df['margin_used_pct'] = (equity_df['margin_used'] / equity_df['equity'] * 100)
        
        # Format columns as requested:
        # - equity: 0 decimals (integer)
        # - returns_pct: percentage with 3 decimals
        # - margin_used: 0 decimals (integer)
        # - margin_used_pct: percentage with 2 decimals
        # - notional_value: 0 decimals (integer)
        equity_df['equity'] = equity_df['equity'].round(0).astype(int)
        equity_df['returns'] = (equity_df['returns'] * 100).round(3)  # Convert to % with 3 decimals
        equity_df['margin_used'] = equity_df['margin_used'].round(0).astype(int)
        equity_df['margin_used_pct'] = equity_df['margin_used_pct'].round(2)
        equity_df['notional_value'] = equity_df['notional_value'].round(0).astype(int)
        
        # Rename returns column to make it clear it's a percentage
        equity_df = equity_df.rename(columns={'returns': 'returns_pct'})
        
        # Reorder columns for better readability
        equity_df = equity_df[['date', 'equity', 'returns_pct', 'margin_used', 'margin_used_pct', 'notional_value']]
        
        equity_path = os.path.join(self.output_dir, f"{base_filename}_equity.csv")
        equity_df.to_csv(equity_path, index=False)
        print(f"  ✓ Saved equity curve: {equity_path}")
        
        # 3. Save allocations history with performance metrics
        allocations_records = []
        for window in results['window_allocations']:
            record = {
                'window': window['window_num'],
                'test_start_date': window['test_start'],
                'train_start_date': window['train_start'],
                'train_end_date': window['train_end'],
                'test_end_date': window['test_end'],
                # In-sample (optimization period) metrics
                'in_sample_cagr_pct': round(window.get('in_sample_cagr', 0) * 100, 2),
                'in_sample_sharpe': round(window.get('in_sample_sharpe', 0), 2),
                'in_sample_max_dd_pct': round(window.get('in_sample_max_dd', 0) * 100, 2),
                'in_sample_volatility_pct': round(window.get('in_sample_volatility', 0) * 100, 2),
                # Out-of-sample (test period) metrics
                'oos_cagr_pct': round(window.get('oos_cagr', 0) * 100, 2),
                'oos_sharpe': round(window.get('oos_sharpe', 0), 2),
                'oos_max_dd_pct': round(window.get('oos_max_dd', 0) * 100, 2),
                'oos_volatility_pct': round(window.get('oos_volatility', 0) * 100, 2),
            }
            # Add each strategy allocation
            for strat_id, alloc in window['allocations'].items():
                record[strat_id] = round(alloc, 2)
            allocations_records.append(record)

        allocations_df = pd.DataFrame(allocations_records)

        # Reorder columns: metadata first, then performance metrics, then allocations
        metadata_cols = ['window', 'test_start_date', 'train_start_date', 'train_end_date', 'test_end_date']
        metric_cols = [
            'in_sample_cagr_pct', 'in_sample_sharpe', 'in_sample_max_dd_pct', 'in_sample_volatility_pct',
            'oos_cagr_pct', 'oos_sharpe', 'oos_max_dd_pct', 'oos_volatility_pct'
        ]
        allocation_cols = [col for col in allocations_df.columns if col not in metadata_cols + metric_cols]

        allocations_df = allocations_df[metadata_cols + metric_cols + allocation_cols]

        allocations_path = os.path.join(self.output_dir, f"{base_filename}_allocations.csv")
        allocations_df.to_csv(allocations_path, index=False)
        print(f"  ✓ Saved allocations with performance metrics: {allocations_path}")
        
        # 4. Save correlation matrix
        # Build full returns matrix from strategies_data
        returns_dfs = []
        for strat_id, data in strategies_data.items():
            df = pd.DataFrame({
                'date': data['dates'],
                strat_id: data['returns']
            })
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            returns_dfs.append(df)
        
        # Merge and calculate correlation
        full_returns = pd.concat(returns_dfs, axis=1, join='outer').fillna(0)
        correlation_matrix = full_returns.corr()
        
        # Round to 2 decimal places for readability
        correlation_matrix = correlation_matrix.round(2)
        
        corr_path = os.path.join(self.output_dir, f"{base_filename}_correlation.csv")
        correlation_matrix.to_csv(corr_path)
        print(f"  ✓ Saved correlation matrix: {corr_path}")
        
        # 5. Generate QuantStats tearsheet
        returns_series = pd.Series(
            results['portfolio_returns'],
            index=pd.to_datetime(results['dates'])
        )
        
        tearsheet_path = os.path.join(self.output_dir, f"{base_filename}_tearsheet.html")
        generate_tearsheet(
            returns_series=returns_series,
            output_path=tearsheet_path,
            title=f"{constructor_name} Portfolio - {timestamp}"
        )
        print(f"  ✓ Saved tearsheet: {tearsheet_path}")
        
        print(f"\n  📁 All outputs saved to: {self.output_dir}/")
        print(f"     Base filename: {base_filename}")


