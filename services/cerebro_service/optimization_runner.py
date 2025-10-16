"""
Portfolio Optimization Runner
Supports both scheduled optimization and CLI-based walk-forward backtesting
"""
import logging
import argparse
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import sys
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cerebro_service.portfolio_optimizer import optimize_portfolio, get_portfolio_metrics, calculate_correlation_matrix

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

logger = logging.getLogger(__name__)

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(
    mongo_uri,
    tls=True,
    tlsAllowInvalidCertificates=True  # For development only
)
db = mongo_client['mathematricks_trading']
strategy_backtest_data_collection = db['strategy_backtest_data']
portfolio_allocations_collection = db['portfolio_allocations']
portfolio_optimization_runs_collection = db['portfolio_optimization_runs']


def merge_strategy_data_sources(doc):
    """
    Merge raw data from backtest, developer_live, and mathematricks_live
    Priority: mathematricks_live > developer_live > backtest
    Returns: {date: return_value} dict and list of returns
    """
    merged_data = {}

    # Step 1: Add backtest data (lowest priority)
    for record in doc.get('raw_data_backtest', []):
        date = record['date']
        merged_data[date] = record['return']

    # Step 2: Overwrite with developer_live (medium priority)
    for record in doc.get('raw_data_developer_live', []):
        date = record['date']
        merged_data[date] = record['return']

    # Step 3: Overwrite with mathematricks_live (highest priority)
    for record in doc.get('raw_data_mathematricks_live', []):
        date = record['date']
        merged_data[date] = record['return']

    # Sort by date and extract returns
    sorted_dates = sorted(merged_data.keys())
    daily_returns = [merged_data[date] for date in sorted_dates]

    return daily_returns, sorted_dates


def run_daily_optimization():
    """
    Run portfolio optimization and save results to MongoDB
    Called daily at midnight by scheduler
    """
    try:
        logger.info("="*80)
        logger.info("STARTING DAILY PORTFOLIO OPTIMIZATION")
        logger.info("="*80)

        start_time = datetime.utcnow()

        # Step 1: Fetch all strategy backtest data from MongoDB
        logger.info("Fetching strategy backtest data from MongoDB...")
        strategies = {}
        for doc in strategy_backtest_data_collection.find():
            # Merge data sources with priority: mathematricks_live > developer_live > backtest
            daily_returns, sorted_dates = merge_strategy_data_sources(doc)

            if len(daily_returns) == 0:
                logger.warning(f"No data for strategy {doc['strategy_id']}, skipping...")
                continue

            # Calculate metrics from merged data
            import numpy as np
            returns_array = np.array(daily_returns)
            mean_return_daily = returns_array.mean()
            volatility_daily = returns_array.std()

            strategies[doc['strategy_id']] = {
                'daily_returns': daily_returns,
                'mean_return_daily': mean_return_daily,
                'volatility_daily': volatility_daily,
                'dates': sorted_dates  # Keep dates for alignment checking
            }

        if not strategies:
            logger.error("No strategy backtest data found in MongoDB - cannot optimize")
            return

        logger.info(f"Loaded {len(strategies)} strategies for optimization")

        # Step 2: Calculate correlation and covariance matrices (shared across all optimizations)
        logger.info("Calculating correlation matrix...")
        corr_matrix, strategy_names = calculate_correlation_matrix(strategies)

        import numpy as np
        vols = np.array([strategies[sid]['volatility_daily'] for sid in strategy_names])
        cov_matrix = corr_matrix * np.outer(vols, vols)

        # Step 3: Run all three optimization modes
        optimization_modes = [
            {"mode": "max_sharpe", "label": "Max Sharpe Ratio", "notes": "Maximize risk-adjusted returns"},
            {"mode": "max_cagr_drawdown", "label": "Max CAGR (20% DD)", "notes": "Maximize CAGR with 20% max drawdown constraint"},
            {"mode": "min_volatility", "label": "Min Volatility", "notes": "Minimize portfolio volatility (conservative)"}
        ]

        allocation_ids = []

        for opt_config in optimization_modes:
            mode = opt_config["mode"]
            label = opt_config["label"]
            notes = opt_config["notes"]

            logger.info(f"\n{'='*80}")
            logger.info(f"Running optimization: {label}")
            logger.info(f"{'='*80}")

            try:
                allocations = optimize_portfolio(
                    strategies,
                    max_leverage=2.0,
                    max_single_strategy=0.5,
                    risk_free_rate=0.0,
                    mode=mode,
                    max_drawdown_limit=-0.20  # 20% max drawdown for max_cagr_drawdown mode
                )
            except Exception as e:
                logger.error(f"Optimization failed for {label}: {str(e)}", exc_info=True)
                # Save failed run
                run_id = f"OPT_{mode.upper()}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                portfolio_optimization_runs_collection.insert_one({
                    "run_id": run_id,
                    "timestamp": datetime.utcnow(),
                    "optimization_mode": mode,
                    "strategies_used": list(strategies.keys()),
                    "optimization_result": {
                        "success": False,
                        "message": str(e),
                        "converged": False
                    },
                    "created_at": datetime.utcnow()
                })
                continue

            # Calculate portfolio metrics
            metrics = get_portfolio_metrics(allocations, strategies)

            # Save optimization run to MongoDB
            run_id = f"OPT_{mode.upper()}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            end_time = datetime.utcnow()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            optimization_run = {
                "run_id": run_id,
                "timestamp": datetime.utcnow(),
                "optimization_mode": mode,
                "optimization_label": label,
                "strategies_used": list(strategies.keys()),
                "correlation_matrix": corr_matrix.tolist(),
                "covariance_matrix": cov_matrix.tolist(),
                "constraints": {
                    "max_leverage": 2.0,
                    "max_single_strategy": 0.5,
                    "risk_free_rate": 0.0,
                    "max_drawdown_limit": -0.20 if mode == "max_cagr_drawdown" else None
                },
                "optimization_result": {
                    "success": True,
                    "message": "Optimization converged successfully",
                    "converged": True
                },
                "recommended_allocations": allocations,
                "portfolio_metrics": metrics,
                "execution_time_ms": execution_time_ms,
                "created_at": datetime.utcnow()
            }

            portfolio_optimization_runs_collection.insert_one(optimization_run)
            logger.info(f"✅ Saved optimization run: {run_id}")

            # Create new portfolio allocation with PENDING_APPROVAL status
            allocation_id = f"ALLOC_{mode.upper()}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

            new_allocation = {
                "allocation_id": allocation_id,
                "timestamp": datetime.utcnow(),
                "optimization_mode": mode,
                "optimization_label": label,
                "status": "PENDING_APPROVAL",
                "allocations": allocations,
                "expected_metrics": metrics,
                "optimization_run_id": run_id,
                "approved_by": None,
                "approved_at": None,
                "archived_at": None,
                "notes": notes,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            portfolio_allocations_collection.insert_one(new_allocation)
            allocation_ids.append(allocation_id)

            logger.info(f"✅ Created allocation recommendation: {allocation_id}")
            logger.info(f"   Mode: {label}")
            logger.info(f"   Total allocation: {metrics['total_allocation_pct']:.2f}%")
            logger.info(f"   Expected Sharpe (annual): {metrics['expected_sharpe_annual']:.2f}")

        # Step 4: Summary
        logger.info("\n" + "="*80)
        logger.info("ALL OPTIMIZATIONS COMPLETE")
        logger.info("="*80)
        logger.info(f"Strategies optimized: {len(strategies)}")
        logger.info(f"Optimization modes run: {len(allocation_ids)}")
        logger.info(f"Allocation IDs created:")
        for alloc_id in allocation_ids:
            logger.info(f"   • {alloc_id}")
        logger.info(f"Total execution time: {execution_time_ms:.0f}ms")
        logger.info(f"Status: All allocations awaiting portfolio manager approval")
        logger.info("="*80)

    except Exception as e:
        logger.error(f"Error in daily optimization: {str(e)}", exc_info=True)


def start_scheduler():
    """
    Start the background scheduler
    Runs optimization daily at midnight UTC
    """
    scheduler = BackgroundScheduler()

    # Run every day at midnight UTC
    trigger = CronTrigger(hour=0, minute=0)
    scheduler.add_job(run_daily_optimization, trigger, id='daily_optimization')

    scheduler.start()
    logger.info("✅ Portfolio optimization scheduler started")
    logger.info("   Schedule: Daily at 00:00 UTC")
    logger.info("   Next run: " + str(scheduler.get_job('daily_optimization').next_run_time))

    return scheduler


def load_strategies_from_mongodb(strategy_filter=None):
    """
    Load strategy data from MongoDB strategies collection.
    
    Args:
        strategy_filter: Optional list of strategy IDs to load
        
    Returns:
        Dict of {strategy_id: strategy_data}
    """
    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    strategies_collection = db['strategies']
    
    # Build query
    query = {}
    if strategy_filter:
        query = {'$or': [
            {'name': {'$in': strategy_filter}},
            {'strategy_id': {'$in': strategy_filter}}
        ]}
    
    strategies_cursor = strategies_collection.find(query)
    strategies_data = {}
    
    for doc in strategies_cursor:
        strategy_id = doc.get('strategy_id') or doc.get('name') or str(doc.get('_id'))
        
        if 'backtest_data' not in doc:
            continue
            
        backtest_data = doc['backtest_data']
        
        if 'daily_returns' in backtest_data and isinstance(backtest_data['daily_returns'], list):
            daily_returns = backtest_data['daily_returns']
            if len(daily_returns) > 0:
                if isinstance(daily_returns[0], dict):
                    dates = [datetime.fromisoformat(item['date']) if isinstance(item.get('date'), str)
                            else item['date'] for item in daily_returns]
                    returns = [float(item['return']) for item in daily_returns]
                else:
                    if 'dates' in backtest_data:
                        dates = [datetime.fromisoformat(d) if isinstance(d, str) else d 
                                for d in backtest_data['dates']]
                        returns = [float(r) for r in daily_returns]
                    else:
                        continue
                
                strategies_data[strategy_id] = {
                    'dates': dates,
                    'daily_returns': returns,
                    'mean_return_daily': np.mean(returns),
                    'volatility_daily': np.std(returns)
                }
    
    return strategies_data


def run_walk_forward_optimization(
    objective='max_cagr_drawdown',
    strategy_filter=None,
    max_leverage=2.0,
    max_single_strategy=1.0,
    max_drawdown=0.20,
    train_days=252,
    test_days=63,
    walk_type='anchored',
    margin_aware=False,
    account_equity=500000,
    max_margin=3.30,
    p95_buffer=1.70,
    test_mode=False
):
    """
    Run walk-forward optimization backtest.
    
    Args:
        objective: Optimization objective ('max_sharpe', 'max_cagr_drawdown', 'min_volatility')
        strategy_filter: List of strategy IDs to include (None = all)
        max_leverage: Maximum total allocation
        max_single_strategy: Maximum allocation per strategy
        max_drawdown: Maximum drawdown constraint (for max_cagr_drawdown mode)
        train_days: Training window size
        test_days: Test window size
        walk_type: 'anchored' or 'rolling'
        margin_aware: Enable margin-aware optimization
        account_equity: Account equity for margin calculations
        max_margin: Maximum margin multiplier
        p95_buffer: 95th percentile buffer
        test_mode: If True, don't save to MongoDB
    """
    logger.info("="*80)
    logger.info("WALK-FORWARD OPTIMIZATION BACKTEST")
    logger.info("="*80)
    logger.info(f"Objective: {objective}")
    logger.info(f"Walk-forward type: {walk_type}")
    logger.info(f"Training window: {train_days} days")
    logger.info(f"Test window: {test_days} days")
    logger.info(f"Max leverage: {max_leverage}x")
    logger.info(f"Max drawdown: {max_drawdown*100}%")
    if margin_aware:
        logger.info(f"Margin-aware: Yes (equity=${account_equity:,.0f}, max={max_margin}x)")
    logger.info("="*80)
    
    # Load strategies
    logger.info("\n[1/5] Loading strategies from MongoDB...")
    strategies_data = load_strategies_from_mongodb(strategy_filter)
    
    if not strategies_data:
        logger.error("No strategies loaded! Exiting.")
        return
    
    for sid in strategies_data:
        logger.info(f"  ✓ {sid}: {len(strategies_data[sid]['daily_returns'])} days")
    
    # Align strategies to master timeline (like portfolio_combiner.py)
    logger.info("\n[2/5] Aligning strategies to master timeline...")
    
    # Build DataFrames with dates as index
    strategy_dfs = []
    for sid, data in strategies_data.items():
        df = pd.DataFrame({
            'returns': data['daily_returns']
        }, index=data['dates'])
        df.columns = [sid]  # Use strategy ID as column name
        strategy_dfs.append(df)
    
    # Concat all strategies on timeline, fill NaN with 0 for missing days
    master_df = pd.concat(strategy_dfs, axis=1)
    master_df.fillna(0, inplace=True)
    master_df.sort_index(inplace=True)
    
    max_length = len(master_df)
    logger.info(f"  Master timeline: {max_length} days")
    logger.info(f"  Date range: {master_df.index[0]} to {master_df.index[-1]}")
    
    # Extract aligned returns for each strategy
    aligned_data = {}
    for sid in strategies_data.keys():
        returns = master_df[sid].values
        aligned_data[sid] = {
            'daily_returns': list(returns),
            'mean_return_daily': np.mean(returns),
            'volatility_daily': np.std(returns)
        }
    
    # Run walk-forward analysis
    logger.info(f"\n[3/5] Running {walk_type} walk-forward analysis...")
    
    results = []
    window_idx = 0
    test_start_idx = train_days
    
    while test_start_idx + test_days <= max_length:
        window_idx += 1
        test_end_idx = test_start_idx + test_days
        
        # Determine train start based on walk type
        if walk_type == 'anchored':
            train_start_idx = 0  # Always start from beginning (expanding window)
        else:  # rolling
            train_start_idx = max(0, test_start_idx - train_days)
        
        logger.info(f"\n  Window {window_idx}:")
        logger.info(f"    Train: days {train_start_idx} to {test_start_idx} ({test_start_idx - train_start_idx} days)")
        logger.info(f"    Test:  days {test_start_idx} to {test_end_idx} ({test_days} days)")
        
        # Prepare training data
        train_data = {}
        for sid, data in aligned_data.items():
            train_returns = data['daily_returns'][train_start_idx:test_start_idx]
            train_data[sid] = {
                'daily_returns': train_returns,
                'mean_return_daily': np.mean(train_returns),
                'volatility_daily': np.std(train_returns)
            }
        
        # Optimize on training window
        try:
            allocations = optimize_portfolio(
                strategies=train_data,
                max_leverage=max_leverage,
                max_single_strategy=max_single_strategy,
                mode=objective,
                max_drawdown_limit=-max_drawdown  # portfolio_optimizer uses negative values
            )
            
            logger.info(f"    Allocations: {len([v for v in allocations.values() if v > 0.01])} strategies")
            logger.info(f"    Total allocation: {sum(allocations.values()):.1f}%")
            
            # Apply allocations to test window
            test_data = {}
            for sid in allocations.keys():
                test_returns = aligned_data[sid]['daily_returns'][test_start_idx:test_end_idx]
                test_data[sid] = test_returns
            
            # Calculate portfolio returns in test window
            weights = np.array([allocations[sid] / 100 for sid in allocations.keys()])
            returns_matrix = np.array([test_data[sid] for sid in allocations.keys()]).T
            portfolio_returns = np.dot(returns_matrix, weights)
            
            # Calculate metrics
            cumulative = np.cumprod(1 + portfolio_returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            max_dd = drawdown.min()
            
            total_return = cumulative[-1] - 1
            cagr = ((1 + total_return) ** (252 / test_days)) - 1
            
            sharpe = (np.mean(portfolio_returns) / np.std(portfolio_returns) * np.sqrt(252)) if np.std(portfolio_returns) > 0 else 0
            
            logger.info(f"    Test CAGR: {cagr*100:.2f}%")
            logger.info(f"    Test Max DD: {max_dd*100:.2f}%")
            logger.info(f"    Test Sharpe: {sharpe:.2f}")
            
            results.append({
                'window': window_idx,
                'train_start': train_start_idx,
                'train_end': test_start_idx,
                'test_start': test_start_idx,
                'test_end': test_end_idx,
                'allocations': allocations,
                'portfolio_returns': portfolio_returns,
                'cagr': cagr,
                'max_dd': max_dd,
                'sharpe': sharpe
            })
            
        except Exception as e:
            logger.error(f"    Optimization failed: {str(e)}")
        
        # Move to next window
        test_start_idx += test_days
    
    # Combine all test window results
    logger.info(f"\n[4/5] Combining {len(results)} test windows...")
    all_returns = np.concatenate([r['portfolio_returns'] for r in results])
    
    cumulative_all = np.cumprod(1 + all_returns)
    running_max_all = np.maximum.accumulate(cumulative_all)
    drawdown_all = (cumulative_all - running_max_all) / running_max_all
    
    total_return_all = cumulative_all[-1] - 1
    cagr_all = ((1 + total_return_all) ** (252 / len(all_returns))) - 1
    max_dd_all = drawdown_all.min()
    sharpe_all = (np.mean(all_returns) / np.std(all_returns) * np.sqrt(252)) if np.std(all_returns) > 0 else 0
    
    logger.info("\n" + "="*80)
    logger.info("WALK-FORWARD BACKTEST RESULTS")
    logger.info("="*80)
    logger.info(f"Total windows: {len(results)}")
    logger.info(f"Total test days: {len(all_returns)}")
    logger.info(f"Combined CAGR: {cagr_all*100:.2f}%")
    logger.info(f"Combined Max DD: {max_dd_all*100:.2f}%")
    logger.info(f"Combined Sharpe: {sharpe_all:.2f}")
    logger.info(f"Total Return: {total_return_all*100:.2f}%")
    logger.info("="*80)
    
    # Save allocations to CSV
    logger.info("\n[4b/5] Saving allocations to CSV...")
    
    # Create outputs directory
    outputs_dir = os.path.join(os.path.dirname(__file__), 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)
    
    # Get all strategy IDs from the original aligned_data
    all_strategy_ids = sorted(list(aligned_data.keys()))
    
    # Build allocation rows
    allocation_rows = []
    for r in results:
        row = {
            'window': r['window'],
            'train_start': r['train_start'],
            'train_end': r['train_end'],
            'test_start': r['test_start'],
            'test_end': r['test_end'],
            'cagr': r['cagr'],
            'max_dd': r['max_dd'],
            'sharpe': r['sharpe']
        }
        # Add each strategy's allocation (0 if not allocated)
        for strategy_id in all_strategy_ids:
            row[strategy_id] = r['allocations'].get(strategy_id, 0.0)
        allocation_rows.append(row)
    
    # Create DataFrame
    allocations_df = pd.DataFrame(allocation_rows)
    
    # Sort columns: metadata first, then strategies alphabetically
    meta_cols = ['window', 'train_start', 'train_end', 'test_start', 'test_end', 'cagr', 'max_dd', 'sharpe']
    strategy_cols = sorted([col for col in allocations_df.columns if col not in meta_cols])
    allocations_df = allocations_df[meta_cols + strategy_cols]
    
    # No need to fillna since we explicitly set 0 for missing strategies above
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    allocations_csv_path = os.path.join(outputs_dir, f"WalkForward_{objective}_{walk_type}_{timestamp}_allocations.csv")
    allocations_df.to_csv(allocations_csv_path, index=False)
    logger.info(f"  ✓ Saved allocations per window: {allocations_csv_path}")

    
    if not test_mode:
        # Save to MongoDB
        logger.info("\n[5/5] Saving results to MongoDB...")
        mongo_uri = os.getenv('MONGODB_URI')
        client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
        db = client['mathematricks_trading']
        collection = db['walk_forward_results']
        
        result_doc = {
            'timestamp': datetime.utcnow(),
            'objective': objective,
            'walk_type': walk_type,
            'train_days': train_days,
            'test_days': test_days,
            'max_leverage': max_leverage,
            'max_drawdown': max_drawdown,
            'strategies': list(aligned_data.keys()),
            'num_windows': len(results),
            'combined_metrics': {
                'cagr': float(cagr_all),
                'max_dd': float(max_dd_all),
                'sharpe': float(sharpe_all),
                'total_return': float(total_return_all)
            },
            'windows': [
                {
                    'window': r['window'],
                    'cagr': float(r['cagr']),
                    'max_dd': float(r['max_dd']),
                    'sharpe': float(r['sharpe']),
                    'allocations': r['allocations']
                }
                for r in results
            ]
        }
        
        collection.insert_one(result_doc)
        logger.info("  ✓ Results saved to MongoDB")
    else:
        logger.info("\n[5/5] Test mode - skipping MongoDB save")
    
    logger.info("\n✅ Walk-forward backtest complete!")


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Portfolio Optimization Runner')
    parser.add_argument('--mode', choices=['scheduled', 'walk_forward', 'single'], default='single',
                        help='Run mode: scheduled (daily cron), walk_forward (backtest), or single (one-time)')
    parser.add_argument('--objective', choices=['max_sharpe', 'max_cagr_drawdown', 'min_volatility'], 
                        default='max_sharpe',
                        help='Optimization objective function')
    parser.add_argument('--strategies', type=str, default=None,
                        help='Comma-separated list of strategy IDs to include (default: all)')
    parser.add_argument('--max-leverage', type=float, default=2.0,
                        help='Maximum total allocation (2.0 = 200%%)')
    parser.add_argument('--max-single', type=float, default=1.0,
                        help='Maximum allocation per strategy (1.0 = 100%%)')
    parser.add_argument('--max-dd', type=float, default=0.20,
                        help='Maximum drawdown constraint for max_cagr_drawdown mode')
    parser.add_argument('--margin-aware', action='store_true',
                        help='Enable margin-aware optimization (considers margin requirements)')
    parser.add_argument('--account-equity', type=float, default=500000,
                        help='Account equity for margin calculations')
    parser.add_argument('--max-margin', type=float, default=3.30,
                        help='Maximum margin multiplier')
    parser.add_argument('--p95-buffer', type=float, default=1.70,
                        help='95th percentile buffer for margin')
    parser.add_argument('--test', action='store_true',
                        help='Test mode - just run optimization without saving to MongoDB')
    parser.add_argument('--train-days', type=int, default=252,
                        help='Training window size for walk-forward (default: 252 = 1 year)')
    parser.add_argument('--test-days', type=int, default=63,
                        help='Test window size for walk-forward (default: 63 = 3 months)')
    parser.add_argument('--walk-type', choices=['anchored', 'rolling'], default='anchored',
                        help='Walk-forward type: anchored (expanding) or rolling (fixed window)')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.mode == 'scheduled':
        logger.info("Starting scheduled optimization mode...")
        scheduler = start_scheduler()
        try:
            # Keep the script running
            import time
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            logger.info("Scheduler shut down")
    
    elif args.mode == 'walk_forward':
        logger.info("Running walk-forward backtest...")
        run_walk_forward_optimization(
            objective=args.objective,
            strategy_filter=args.strategies.split(',') if args.strategies else None,
            max_leverage=args.max_leverage,
            max_single_strategy=args.max_single,
            max_drawdown=args.max_dd,
            train_days=args.train_days,
            test_days=args.test_days,
            walk_type=args.walk_type,
            margin_aware=args.margin_aware,
            account_equity=args.account_equity,
            max_margin=args.max_margin,
            p95_buffer=args.p95_buffer,
            test_mode=args.test
        )
    
    else:  # single mode
        logger.info("Running single optimization (manual trigger)...")
        run_daily_optimization()
