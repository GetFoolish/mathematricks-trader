#!/usr/bin/env python3
"""
Test 2: Load equity curve data from CSV
Populates database with dummy strategy performance data for testing frontend
"""

import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.reporting import DataStore
from src.utils.logger import setup_logger

# Load environment variables
load_dotenv()

# Setup logger
logger = setup_logger('test_load_equity', 'test_load_equity.log')


def load_equity_curves_from_csv(csv_file_path: str):
    """
    Load equity curve data from CSV and insert into MongoDB

    Expected CSV format:
    date, strategy_name, equity, daily_pnl, daily_return_pct
    2024-01-01, Strategy_A, 100000, 0, 0
    2024-01-02, Strategy_A, 101500, 1500, 1.5
    ...
    """
    logger.info("=" * 80)
    logger.info("TEST 2: LOAD EQUITY CURVE DATA")
    logger.info("=" * 80)

    # Check if CSV file exists
    if not os.path.exists(csv_file_path):
        logger.error(f"❌ CSV file not found: {csv_file_path}")
        logger.info("\nExpected CSV format:")
        logger.info("date,strategy_name,equity,daily_pnl,daily_return_pct")
        logger.info("2024-01-01,Strategy_A,100000,0,0.0")
        logger.info("2024-01-02,Strategy_A,101500,1500,1.5")
        return False

    # Load CSV
    logger.info(f"Loading CSV file: {csv_file_path}")
    try:
        df = pd.read_csv(csv_file_path)
        logger.info(f"✅ Loaded {len(df)} rows from CSV")
    except Exception as e:
        logger.error(f"❌ Error reading CSV: {e}")
        return False

    # Validate CSV columns
    required_columns = ['date', 'strategy_name', 'equity', 'daily_pnl', 'daily_return_pct']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        logger.error(f"❌ Missing required columns: {missing_columns}")
        logger.info(f"Available columns: {list(df.columns)}")
        return False

    logger.info(f"Strategies found: {df['strategy_name'].unique().tolist()}")

    # Connect to MongoDB
    logger.info("\nConnecting to MongoDB...")
    mongodb_url = os.getenv('mongodbconnectionstring')

    if not mongodb_url:
        logger.error("❌ MongoDB connection string not found in .env")
        return False

    data_store = DataStore(mongodb_url)
    if not data_store.connect():
        logger.error("❌ Failed to connect to MongoDB")
        return False

    # Clear existing PnL history (optional - comment out to append)
    logger.info("\nClearing existing PnL history...")
    data_store.collections['pnl_history'].delete_many({})
    logger.info("✅ Cleared existing data")

    # Insert data row by row
    logger.info("\nInserting data into MongoDB...")
    successful_inserts = 0
    failed_inserts = 0

    for idx, row in df.iterrows():
        try:
            # Parse date
            date = pd.to_datetime(row['date'])

            # Store PnL record
            success = data_store.store_pnl_record(
                strategy_name=row['strategy_name'],
                pnl=float(row['daily_pnl']),
                returns_pct=float(row['daily_return_pct']),
                date=date
            )

            if success:
                successful_inserts += 1
            else:
                failed_inserts += 1

            # Progress indicator every 100 rows
            if (idx + 1) % 100 == 0:
                logger.info(f"  Progress: {idx + 1}/{len(df)} rows...")

        except Exception as e:
            logger.error(f"❌ Error inserting row {idx}: {e}")
            failed_inserts += 1

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info(f"✅ Successfully inserted: {successful_inserts} records")
    if failed_inserts > 0:
        logger.info(f"❌ Failed to insert: {failed_inserts} records")
    logger.info("=" * 80)

    # Calculate and store strategy performance metrics
    logger.info("\nCalculating strategy performance metrics...")

    strategies = df['strategy_name'].unique()

    for strategy in strategies:
        strategy_df = df[df['strategy_name'] == strategy]

        # Calculate metrics
        total_return = (strategy_df['equity'].iloc[-1] - strategy_df['equity'].iloc[0]) / strategy_df['equity'].iloc[0] * 100
        total_pnl = strategy_df['daily_pnl'].sum()
        avg_daily_return = strategy_df['daily_return_pct'].mean()
        win_rate = (strategy_df['daily_pnl'] > 0).sum() / len(strategy_df) * 100
        max_drawdown = calculate_max_drawdown(strategy_df['equity'].values)

        # Store in strategy_performance collection
        # Convert numpy types to Python native types for MongoDB
        perf_doc = {
            'strategy_name': strategy,
            'total_return_pct': float(total_return),
            'total_pnl': float(total_pnl),
            'avg_daily_return_pct': float(avg_daily_return),
            'win_rate_pct': float(win_rate),
            'max_drawdown_pct': float(max_drawdown),
            'num_days': int(len(strategy_df)),
            'start_date': pd.to_datetime(strategy_df['date'].iloc[0]).to_pydatetime(),
            'end_date': pd.to_datetime(strategy_df['date'].iloc[-1]).to_pydatetime(),
            'updated_at': datetime.now()
        }

        # Upsert (insert or update)
        data_store.collections['strategy_performance'].update_one(
            {'strategy_name': strategy},
            {'$set': perf_doc},
            upsert=True
        )

        logger.info(f"  ✅ {strategy}: {total_return:.2f}% return, {win_rate:.1f}% win rate")

    # Disconnect
    data_store.disconnect()

    logger.info("\n✅ Data load complete! You can now view:")
    logger.info("  - Combined Performance page (all strategies)")
    logger.info("  - Strategy Deepdive page (per-strategy analysis)")

    return True


def calculate_max_drawdown(equity_curve):
    """Calculate maximum drawdown percentage"""
    peak = equity_curve[0]
    max_dd = 0

    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak * 100
        if dd > max_dd:
            max_dd = dd

    return max_dd


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Load equity curve data from CSV into MongoDB')
    parser.add_argument('csv_file', help='Path to CSV file with equity curve data')

    args = parser.parse_args()

    success = load_equity_curves_from_csv(args.csv_file)

    if success:
        logger.info("\n✅ TEST PASSED")
    else:
        logger.info("\n❌ TEST FAILED")
