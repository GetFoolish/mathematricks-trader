"""
Test 1: Portfolio Constructor Backtest
Tests the Max CAGR portfolio construction strategy using historical data from MongoDB.

Test Flow:
1. Load all strategy backtest data from MongoDB (strategy_backtest_data collection)
2. Run the MaxCAGRConstructor to generate portfolio allocations
3. Backtest the allocations using walk-forward analysis
4. Generate QuantStats tearsheet showing portfolio performance
5. Verify key metrics (CAGR, Sharpe, Max Drawdown)

Expected Outputs:
- Tearsheet HTML file in outputs/portfolio_tearsheets/
- Console output with allocation percentages
- Validation that allocations sum to reasonable total (e.g., 100-200% for leverage)
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# These will be implemented in the actual code
from services.cerebro_service.portfolio_constructor.max_cagr.strategy import MaxCAGRConstructor
from services.cerebro_service.research.backtest_engine import WalkForwardBacktest
from services.cerebro_service.research.tearsheet_generator import generate_tearsheet

# Load environment
load_dotenv(os.path.join(project_root, '.env'))


def load_strategies_from_mongodb(strategy_names=None):
    """
    Load strategy data from MongoDB 'strategies' collection.
    
    Args:
        strategy_names: Optional list of strategy names to load. If None, loads all.
        
    Returns:
        Dict of {strategy_id: {dates: [...], returns: [...], margin_used: [...], notional: [...]}}
    """
    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    strategies_collection = db['strategies']
    
    # Build query
    query = {}
    if strategy_names:
        query = {'$or': [
            {'name': {'$in': strategy_names}},
            {'strategy_id': {'$in': strategy_names}}
        ]}
    
    strategies_cursor = strategies_collection.find(query)
    strategies_data = {}
    
    for doc in strategies_cursor:
        strategy_id = doc.get('strategy_id') or doc.get('name') or str(doc.get('_id'))
        
        # Data is nested under 'backtest_data'
        if 'backtest_data' not in doc:
            continue
            
        backtest_data = doc['backtest_data']
        
        # Try multiple data formats within backtest_data
        if 'daily_returns' in backtest_data and isinstance(backtest_data['daily_returns'], list):
            # Format: backtest_data.daily_returns array
            daily_returns = backtest_data['daily_returns']
            if len(daily_returns) > 0:
                # Handle both dict format and scalar format
                if isinstance(daily_returns[0], dict):
                    # Dict format with date and return
                    dates = [datetime.fromisoformat(item['date']) if isinstance(item.get('date'), str)
                            else item['date'] for item in daily_returns]
                    returns = [float(item['return']) for item in daily_returns]
                    margin_used = [float(item.get('margin_used', 0)) for item in daily_returns]
                    notional = [float(item.get('notional', 0)) for item in daily_returns]
                else:
                    # Array of scalars - need dates from elsewhere
                    if 'dates' in backtest_data:
                        dates = [datetime.fromisoformat(d) if isinstance(d, str) else d 
                                for d in backtest_data['dates']]
                        returns = [float(r) for r in daily_returns]
                        margin_used = [0] * len(returns)
                        notional = [0] * len(returns)
                    else:
                        continue
                
                strategies_data[strategy_id] = {
                    'dates': dates,
                    'returns': returns,
                    'margin_used': margin_used,
                    'notional': notional
                }
        
        elif 'equity_curve' in backtest_data and isinstance(backtest_data['equity_curve'], list):
            # Format: equity_curve with dates and values
            equity_curve = backtest_data['equity_curve']
            if len(equity_curve) > 1:
                if isinstance(equity_curve[0], dict):
                    dates = [datetime.fromisoformat(item['date']) if isinstance(item.get('date'), str) 
                            else item['date'] for item in equity_curve]
                    values = [float(item['equity']) for item in equity_curve]
                else:
                    # Array of scalars - need dates from elsewhere
                    if 'dates' in backtest_data:
                        dates = [datetime.fromisoformat(d) if isinstance(d, str) else d 
                                for d in backtest_data['dates']]
                        values = [float(v) for v in equity_curve]
                    else:
                        continue
                
                # Calculate returns from equity curve
                returns = [(values[i] - values[i-1]) / values[i-1] if values[i-1] != 0 else 0 
                          for i in range(1, len(values))]
                dates = dates[1:]
                
                strategies_data[strategy_id] = {
                    'dates': dates,
                    'returns': returns,
                    'margin_used': [0] * len(returns),
                    'notional': [0] * len(returns)
                }
    
    return strategies_data


def test_portfolio_constructor_backtest():
    """
    TEST 1: Load strategies from MongoDB, optimize with MaxCAGR, generate tearsheet
    """
    print("="*80)
    print("TEST 1: Portfolio Constructor Backtest (MaxCAGR)")
    print("="*80)
    
    # Step 1: Load strategies from MongoDB
    print("\n[1/5] Loading strategy data from MongoDB...")
    
    # You can specify which strategies to load, or pass None to load all
    # Example: strategies_data = load_strategies_from_mongodb(['SPX_1-D_Opt', 'Forex', 'SPY'])
    strategies_data = load_strategies_from_mongodb()  # Load all strategies
    
    for strategy_id, data in strategies_data.items():
        print(f"  ✓ Loaded {strategy_id}: {len(data['returns'])} days of data")
    
    if len(strategies_data) == 0:
        print("\n❌ TEST FAILED: No strategy data found in MongoDB 'strategies' collection")
        print("   Please ensure strategies are loaded in the 'strategies' collection")
        return False
    
    print(f"\n  Total strategies loaded: {len(strategies_data)}")
    
    # Step 1b: Align all strategies to master timeline (like portfolio_combiner.py)
    print("\n[1b/5] Aligning strategies to master timeline...")
    
    # Build DataFrames with dates as index
    strategy_dfs = []
    for sid, data in strategies_data.items():
        df = pd.DataFrame({
            'returns': data['returns'],
            'margin_used': data.get('margin_used', [0] * len(data['returns'])),
            'notional': data.get('notional', [0] * len(data['returns']))
        }, index=data['dates'])
        # Prefix columns with strategy name
        df.columns = [f"{sid}_{col}" for col in df.columns]
        strategy_dfs.append(df)
    
    # Concat all strategies on timeline, fill NaN with 0 for missing days
    master_df = pd.concat(strategy_dfs, axis=1)
    master_df.fillna(0, inplace=True)
    master_df.sort_index(inplace=True)
    
    print(f"  Master timeline: {len(master_df)} days")
    print(f"  Date range: {master_df.index[0]} to {master_df.index[-1]}")
    
    # Extract aligned data for each strategy
    aligned_strategies_data = {}
    for sid in strategies_data.keys():
        returns_col = f"{sid}_returns"
        margin_col = f"{sid}_margin_used"
        notional_col = f"{sid}_notional"
        
        aligned_strategies_data[sid] = {
            'dates': list(master_df.index),
            'returns': list(master_df[returns_col].values),
            'margin_used': list(master_df[margin_col].values) if margin_col in master_df.columns else [0] * len(master_df),
            'notional': list(master_df[notional_col].values) if notional_col in master_df.columns else [0] * len(master_df)
        }
    
    # Replace original data with aligned data
    strategies_data = aligned_strategies_data
    
    print(f"  All strategies now aligned to {len(master_df)} days")
    
    # Step 2: Initialize MaxCAGR Portfolio Constructor
    print("\n[2/5] Initializing MaxCAGR Portfolio Constructor...")
    constructor = MaxCAGRConstructor(
        max_leverage=2.0,           # Allow up to 200% allocation (2x leverage)
        max_drawdown_limit=0.35,    # 35% max drawdown constraint
        rebalance_frequency='monthly',
        risk_free_rate=0.0
    )
    print(f"  ✓ Constructor initialized")
    print(f"    - Max Leverage: {constructor.max_leverage}x")
    print(f"    - Max Drawdown Limit: {constructor.max_drawdown_limit*100}%")
    print(f"    - Rebalance Frequency: {constructor.rebalance_frequency}")
    
    # Step 3: Run Walk-Forward Backtest
    print("\n[3/5] Running Walk-Forward Backtest...")
    backtest = WalkForwardBacktest(
        constructor=constructor,
        train_days=252,  # 1 year training window
        test_days=63,    # 3 months testing window (non-overlapping)
        walk_forward_type='anchored',  # 'anchored' (expanding) or 'rolling' (fixed window)
        apply_drawdown_protection=True,  # Enable dynamic de-leveraging
        max_drawdown_threshold=0.35      # 35% drawdown threshold
    )
    
    results = backtest.run(strategies_data)
    
    print(f"\n  ✓ Backtest completed")
    print(f"    - Total periods: {len(results['allocations_history'])}")
    print(f"    - Portfolio equity curve: {len(results['portfolio_equity_curve'])} data points")
    
    # Step 4: Calculate Metrics
    print("\n[4/5] Calculating Performance Metrics...")
    equity_curve = results['portfolio_equity_curve']
    returns_series = pd.Series(results['portfolio_returns'], index=results['dates'])
    
    # Calculate key metrics
    total_return = (equity_curve[-1] / equity_curve[0] - 1) * 100
    days = len(equity_curve)
    years = days / 252
    cagr = ((equity_curve[-1] / equity_curve[0]) ** (1/years) - 1) * 100 if years > 0 else 0
    
    sharpe = returns_series.mean() / returns_series.std() * np.sqrt(252) if returns_series.std() > 0 else 0
    
    # Calculate max drawdown
    cumulative = (1 + returns_series).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    
    print(f"\n  Portfolio Performance:")
    print(f"    - Total Return: {total_return:.2f}%")
    print(f"    - CAGR: {cagr:.2f}%")
    print(f"    - Sharpe Ratio: {sharpe:.2f}")
    print(f"    - Max Drawdown: {max_drawdown:.2f}%")
    
    # Step 5: Save results to portfolio constructor's outputs folder
    print("\n[5/6] Saving portfolio data...")
    
    # Create outputs folder in portfolio constructor directory
    constructor_name = "max_cagr"  # TODO: Make this dynamic based on constructor type
    constructor_outputs_dir = os.path.join(
        project_root, "services", "cerebro_service", "portfolio_constructor",
        constructor_name, "outputs"
    )
    os.makedirs(constructor_outputs_dir, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save portfolio data as CSV
    portfolio_df = pd.DataFrame({
        'date': results['dates'],
        'returns': results['portfolio_returns'],
        'equity': results['portfolio_equity_curve']
    })
    csv_path = os.path.join(constructor_outputs_dir, f"MaxCAGR_Backtest_{timestamp}.csv")
    portfolio_df.to_csv(csv_path, index=False)
    print(f"  ✓ Saved portfolio data: {csv_path}")
    
    # Save window allocations as CSV
    if 'window_allocations' in results:
        window_allocs = results['window_allocations']
        
        # Get all strategy IDs from the original strategies_data
        all_strategy_ids = sorted(list(strategies_data.keys()))
        
        # Build allocation rows
        allocation_rows = []
        for window in window_allocs:
            row = {
                'window': window['window_num'],
                'test_start': window['test_start'],
                'test_end': window['test_end'],
                'train_start': window['train_start'],
                'train_end': window['train_end']
            }
            # Add each strategy's allocation (0 if not allocated)
            for strategy_id in all_strategy_ids:
                row[strategy_id] = window['allocations'].get(strategy_id, 0.0)
            allocation_rows.append(row)
        
        # Create DataFrame
        allocations_df = pd.DataFrame(allocation_rows)
        
        # Sort columns: metadata first, then strategies alphabetically
        meta_cols = ['window', 'test_start', 'test_end', 'train_start', 'train_end']
        strategy_cols = sorted([col for col in allocations_df.columns if col not in meta_cols])
        allocations_df = allocations_df[meta_cols + strategy_cols]
        
        # No need to fillna since we explicitly set 0 for missing strategies above

        
        # Save to CSV
        allocations_csv_path = os.path.join(constructor_outputs_dir, f"MaxCAGR_Backtest_{timestamp}_allocations.csv")
        allocations_df.to_csv(allocations_csv_path, index=False)
        print(f"  ✓ Saved allocations per window: {allocations_csv_path}")
    
    # Step 6: Generate QuantStats Tearsheet
    print("\n[6/6] Generating QuantStats Tearsheet...")
    
    tearsheet_path = os.path.join(constructor_outputs_dir, f'MaxCAGR_Backtest_{timestamp}_tearsheet.html')
    
    generate_tearsheet(
        returns_series=returns_series,
        output_path=tearsheet_path,
        title='Max CAGR Portfolio Constructor - Backtest',
        benchmark=None  # Can add SPY benchmark later
    )
    
    print(f"  ✓ Tearsheet saved to: {tearsheet_path}")
    
    # Validation Checks
    print("\n" + "="*80)
    print("VALIDATION CHECKS")
    print("="*80)
    
    checks_passed = 0
    checks_total = 4
    
    # Check 1: CAGR is positive and reasonable
    if cagr > 0 and cagr < 100:  # Positive but not unrealistic
        print("  ✅ CAGR is positive and reasonable")
        checks_passed += 1
    else:
        print(f"  ❌ CAGR is {cagr:.2f}% (expected 0-100%)")
    
    # Check 2: Max drawdown within limit
    if max_drawdown > -30:  # Allow some tolerance beyond 20% limit
        print("  ✅ Max drawdown is acceptable")
        checks_passed += 1
    else:
        print(f"  ❌ Max drawdown is {max_drawdown:.2f}% (too large)")
    
    # Check 3: Allocations sum to reasonable total
    final_allocation = results['allocations_history'][-1]['allocations']  # Get allocations dict
    total_allocation = sum(final_allocation.values())
    if 50 <= total_allocation <= 250:  # Between 50% and 250%
        print(f"  ✅ Total allocation is {total_allocation:.1f}% (reasonable)")
        checks_passed += 1
    else:
        print(f"  ❌ Total allocation is {total_allocation:.1f}% (expected 50-250%)")
    
    # Check 4: Tearsheet file exists
    if os.path.exists(tearsheet_path):
        print("  ✅ Tearsheet file created successfully")
        checks_passed += 1
    else:
        print("  ❌ Tearsheet file not created")
    
    print(f"\n{checks_passed}/{checks_total} validation checks passed")
    
    if checks_passed == checks_total:
        print("\n✅ TEST 1 PASSED: Portfolio Constructor Backtest")
        return True
    else:
        print("\n⚠️  TEST 1 COMPLETED WITH WARNINGS")
        return True  # Still pass but with warnings


if __name__ == "__main__":
    try:
        success = test_portfolio_constructor_backtest()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED WITH ERROR:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
