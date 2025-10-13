"""
Portfolio Optimization Scheduler
Runs daily portfolio optimization at midnight and saves recommendations to MongoDB
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import sys

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


if __name__ == "__main__":
    # For testing: run optimization immediately
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Running portfolio optimization (manual trigger)...")
    run_daily_optimization()
