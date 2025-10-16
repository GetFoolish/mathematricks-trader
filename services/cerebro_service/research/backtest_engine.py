"""
Walk-Forward Backtest Engine
Runs walk-forward analysis for portfolio constructors.
"""
import pandas as pd
import numpy as np
import os
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
            # We want: 'services/cerebro_service/portfolio_constructor/max_hybrid/outputs'
            module_parts = constructor_module.split('.')
            if 'portfolio_constructor' in module_parts:
                idx = module_parts.index('portfolio_constructor')
                constructor_name = module_parts[idx + 1]  # e.g., 'max_hybrid'
                output_dir = f'services/cerebro_service/portfolio_constructor/{constructor_name}/outputs'
            else:
                # Fallback to root outputs folder
                output_dir = 'outputs/portfolio_tearsheets'
        
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
        strategy_ids = list(returns_matrix.columns)
        
        print(f"  ✓ Aligned {len(strategy_ids)} strategies")
        print(f"  ✓ Date range: {all_dates[0]} to {all_dates[-1]}")
        print(f"  ✓ Total days: {len(all_dates)}")
        
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
            
            print(f"\n  Window {window_count}:")
            print(f"    Train: {train_dates[0]} to {train_dates[-1]} ({len(train_dates)} days)")
            print(f"    Test:  {test_dates[0]} to {test_dates[-1]} ({len(test_dates)} days)")
            
            # Build context for training period
            train_context = self._build_context(
                returns_df=train_returns,
                is_backtest=True,
                current_date=train_dates[-1]
            )
            
            # Get allocations from constructor
            allocations = self.constructor.allocate_portfolio(train_context)
            
            # Apply drawdown protection at window level
            if self.apply_drawdown_protection and global_peak_equity > 0:
                current_dd = (global_peak_equity - current_equity) / global_peak_equity
                if current_dd > self.max_drawdown_threshold:
                    # Reduce allocations proportionally
                    excess_dd = current_dd - self.max_drawdown_threshold
                    reduction_factor = max(0.0, 1.0 - (excess_dd / self.max_drawdown_threshold))
                    print(f"    ⚠️  Portfolio in {current_dd*100:.1f}% drawdown - reducing allocations by {(1-reduction_factor)*100:.0f}%")
                    allocations = {k: v * reduction_factor for k, v in allocations.items()}
            
            print(f"    Allocations: {len(allocations)} strategies")
            total_alloc = sum(allocations.values())
            print(f"    Total allocation: {total_alloc:.1f}%")
            
            # Apply allocations to test period
            window_result = self._apply_allocations(
                allocations=allocations,
                test_returns=test_returns,
                test_dates=test_dates,
                starting_equity=current_equity,
                global_peak_equity=global_peak_equity if self.apply_drawdown_protection else None
            )
            
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
                'dates': test_dates
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
        """
        # Convert to DataFrame format
        dfs = []
        for sid, data in strategies_data.items():
            df = pd.DataFrame({
                'date': data['dates'],
                sid: data['returns']
            })
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            # Sort by date to ensure proper ordering
            df = df.sort_index()
            dfs.append(df)
        
        # Merge all strategies - OUTER JOIN for master timeline
        merged = pd.concat(dfs, axis=1, join='outer')  # Outer join to get ALL dates
        
        if len(merged) == 0:
            return {}
        
        # Fill NaN with 0 (strategies not trading on certain dates)
        merged = merged.fillna(0)
        
        # Ensure sorted by date
        merged = merged.sort_index()
        
        return {
            'dates': merged.index.tolist(),
            'returns_matrix': merged
        }
    
    def _build_context(
        self,
        returns_df: pd.DataFrame,
        is_backtest: bool = True,
        current_date: datetime = None
    ) -> PortfolioContext:
        """Build portfolio context from returns data"""
        # Convert returns DataFrame to strategy_histories format
        strategy_histories = {}
        for col in returns_df.columns:
            strategy_histories[col] = pd.DataFrame({
                'returns': returns_df[col].values
            })
        
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
        starting_equity: float = 100000.0,
        global_peak_equity: float = None
    ) -> Dict:
        """
        Apply allocations to test period and calculate portfolio returns.
        Optionally applies drawdown protection by reducing leverage when DD exceeds threshold.
        
        Args:
            global_peak_equity: If provided (for drawdown protection), use this as the peak
                              instead of the peak within this window only
        """
        # Convert allocation percentages to weights
        total_alloc = sum(allocations.values())
        
        if total_alloc == 0:
            # No allocations, return zeros
            return {
                'portfolio_returns': [0.0] * len(test_dates)
            }
        
        # Normalize allocations to weights (handle leverage)
        base_weights = {sid: (pct / 100.0) for sid, pct in allocations.items()}
        
        # Calculate portfolio returns for each day
        portfolio_returns = []
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
            
            portfolio_returns.append(daily_return)
            leverage_adjustments.append(current_leverage_multiplier)
            
            # Update equity curve and peak
            new_equity = equity_curve[-1] * (1 + daily_return)
            equity_curve.append(new_equity)
            
            # ALWAYS update peak to track highest point reached
            peak_equity = max(peak_equity, new_equity)
        
        if self.apply_drawdown_protection and protection_triggered_count > 0:
            print(f"      DD Protection triggered {protection_triggered_count}/{len(test_returns)} days")
        
        return {
            'portfolio_returns': portfolio_returns,
            'leverage_adjustments': leverage_adjustments if self.apply_drawdown_protection else None
        }
    
    def _combine_windows(self, window_results: List[Dict]) -> Dict:
        """Combine results from all windows into single equity curve"""
        all_returns = []
        all_dates = []
        allocations_history = []
        
        for window in window_results:
            all_returns.extend(window['portfolio_returns'])
            all_dates.extend(window['dates'])
            allocations_history.append({
                'date': window['test_start'],
                'allocations': window['allocations']
            })
        
        # Create DataFrame to sort by date
        df = pd.DataFrame({
            'date': all_dates,
            'returns': all_returns
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Extract sorted values
        all_dates = df['date'].tolist()
        all_returns = df['returns'].tolist()
        
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
            'dates': all_dates,
            'allocations_history': allocations_history
        }
    
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
        1. Portfolio equity curve CSV
        2. Allocations history CSV
        3. Correlation matrix CSV
        4. QuantStats HTML tearsheet
        """
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        constructor_name = self.constructor.__class__.__name__.replace('Constructor', '')
        base_filename = f"{constructor_name}_{timestamp}"
        
        # 1. Save portfolio equity curve
        equity_df = pd.DataFrame({
            'date': results['dates'],
            'equity': results['portfolio_equity_curve'],
            'returns': results['portfolio_returns']
        })
        equity_path = os.path.join(self.output_dir, f"{base_filename}_equity.csv")
        equity_df.to_csv(equity_path, index=False)
        print(f"  ✓ Saved equity curve: {equity_path}")
        
        # 2. Save allocations history
        allocations_records = []
        for window in results['window_allocations']:
            record = {
                'window': window['window_num'],
                'date': window['test_start'],
            }
            # Add each strategy allocation
            for strat_id, alloc in window['allocations'].items():
                record[strat_id] = alloc
            allocations_records.append(record)
        
        allocations_df = pd.DataFrame(allocations_records)
        allocations_path = os.path.join(self.output_dir, f"{base_filename}_allocations.csv")
        allocations_df.to_csv(allocations_path, index=False)
        print(f"  ✓ Saved allocations: {allocations_path}")
        
        # 3. Save correlation matrix
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
        
        # 4. Generate QuantStats tearsheet
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

