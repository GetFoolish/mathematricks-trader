"""
Backtest Data Ingestion Tool
Ingests strategy backtest data from CSVs into MongoDB for portfolio optimization.
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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


def parse_returns_from_csv(csv_path):
    """
    Parse daily returns from CSV file.

    Args:
        csv_path: Path to CSV file with Date and Daily Returns (%) columns

    Returns:
        DataFrame with Date and returns in decimal format
    """
    try:
        df = pd.read_csv(csv_path)

        # Validate columns
        if 'Date' not in df.columns or 'Daily Returns (%)' not in df.columns:
            raise ValueError(f"CSV must contain 'Date' and 'Daily Returns (%)' columns. Found: {df.columns}")

        # Parse dates
        df['Date'] = pd.to_datetime(df['Date'])

        # Handle different formats for Daily Returns (%)
        if df['Daily Returns (%)'].dtype == 'object':
            # String format like "0.5%" or "1.52%"
            df['Daily Returns (%)'] = df['Daily Returns (%)'].str.rstrip('%').astype('float') / 100
        elif df['Daily Returns (%)'].abs().max() > 1:
            # Percentage format like 0.5 (meaning 0.5%)
            df['Daily Returns (%)'] = df['Daily Returns (%)'] / 100
        # Otherwise assume it's already in decimal format (0.005)

        # Sort by date ascending
        df = df.sort_values('Date')

        return df

    except Exception as e:
        logger.error(f"Error parsing CSV {csv_path}: {e}")
        raise


def calculate_metrics(returns_series):
    """
    Calculate statistical metrics from daily returns.

    Args:
        returns_series: Pandas Series of daily returns (decimal format)

    Returns:
        Dict of metrics
    """
    returns_array = returns_series.values

    # Basic statistics
    mean_return_daily = float(np.mean(returns_array))
    volatility_daily = float(np.std(returns_array, ddof=1))  # Sample std dev

    # Sharpe ratio (annualized, assuming 252 trading days)
    if volatility_daily > 0:
        sharpe_ratio = (mean_return_daily / volatility_daily) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    # Maximum drawdown
    cumulative_returns = (1 + returns_series).cumprod()
    running_max = cumulative_returns.expanding().max()
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = float(drawdown.min())

    # Win rate (percentage of positive return days)
    win_rate = float((returns_array > 0).sum() / len(returns_array))

    return {
        'mean_return_daily': mean_return_daily,
        'volatility_daily': volatility_daily,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate
    }


def ingest_strategy(csv_path, strategy_id, margin_per_unit=5000, metadata=None):
    """
    Ingest a single strategy's backtest data into MongoDB.

    Args:
        csv_path: Path to CSV file
        strategy_id: Unique strategy identifier (e.g., "SPX_1-D_Opt")
        margin_per_unit: Margin required per contract/unit (default 5000)
        metadata: Optional dict with additional metadata

    Returns:
        Dict with ingestion results
    """
    logger.info(f"Ingesting strategy: {strategy_id}")

    try:
        # Parse CSV
        df = parse_returns_from_csv(csv_path)

        # Get backtest period
        start_date = df['Date'].min()
        end_date = df['Date'].max()
        total_days = len(df)

        logger.info(f"  Date range: {start_date.date()} to {end_date.date()} ({total_days} days)")

        # Calculate metrics
        metrics = calculate_metrics(df['Daily Returns (%)'])

        logger.info(f"  Mean daily return: {metrics['mean_return_daily']*100:.4f}%")
        logger.info(f"  Daily volatility: {metrics['volatility_daily']*100:.4f}%")
        logger.info(f"  Sharpe ratio: {metrics['sharpe_ratio']:.4f}")
        logger.info(f"  Max drawdown: {metrics['max_drawdown']*100:.2f}%")
        logger.info(f"  Win rate: {metrics['win_rate']*100:.1f}%")

        # Prepare document
        document = {
            'strategy_id': strategy_id,
            'backtest_period': {
                'start_date': start_date,
                'end_date': end_date,
                'total_days': total_days
            },
            'daily_returns': df['Daily Returns (%)'].tolist(),
            'mean_return_daily': metrics['mean_return_daily'],
            'volatility_daily': metrics['volatility_daily'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'win_rate': metrics['win_rate'],
            'margin_per_unit': margin_per_unit,
            'metadata': metadata or {
                'backtest_source': 'portfolio_combiner',
                'notes': 'Ingested from CSV'
            },
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        # Upsert to MongoDB (update if exists, insert if not)
        result = strategy_backtest_data_collection.update_one(
            {'strategy_id': strategy_id},
            {'$set': document},
            upsert=True
        )

        if result.upserted_id:
            logger.info(f"✅ Inserted new strategy: {strategy_id}")
        else:
            logger.info(f"✅ Updated existing strategy: {strategy_id}")

        return {
            'strategy_id': strategy_id,
            'success': True,
            'total_days': total_days,
            'metrics': metrics
        }

    except Exception as e:
        logger.error(f"❌ Error ingesting {strategy_id}: {e}")
        return {
            'strategy_id': strategy_id,
            'success': False,
            'error': str(e)
        }


def ingest_all_strategies(data_folder, margin_defaults=None):
    """
    Ingest all strategy CSV files from a folder.

    Args:
        data_folder: Path to folder containing strategy CSV files
        margin_defaults: Dict of {strategy_id: margin_per_unit} (optional)

    Returns:
        List of ingestion results
    """
    if margin_defaults is None:
        # Default margins for known strategies
        margin_defaults = {
            'SPX_1-D_Opt': 5000,
            'Forex': 2000,
            'Com1-Met': 8200,  # Gold
            'Com2-Ag': 3000,   # Agriculture
            'Com3-Mkt': 12500,  # ES/NQ
            'Com4-Misc': 6000,
            'SPY': 90000,      # Stock trading (rough estimate)
            'TLT': 90000,      # Bond ETF
            'chong_vansh_strategy': 5000  # Unknown strategy
        }

    logger.info(f"Scanning folder: {data_folder}")

    results = []
    csv_files = [f for f in os.listdir(data_folder) if f.endswith('.csv') and f != '.gitkeep']

    logger.info(f"Found {len(csv_files)} CSV files")

    for csv_file in csv_files:
        strategy_id = os.path.splitext(csv_file)[0]  # Remove .csv extension
        csv_path = os.path.join(data_folder, csv_file)

        # Get margin (use default or fallback to 5000)
        margin = margin_defaults.get(strategy_id, 5000)

        result = ingest_strategy(csv_path, strategy_id, margin_per_unit=margin)
        results.append(result)

        logger.info("")  # Blank line for readability

    # Summary
    logger.info("=" * 80)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 80)

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    logger.info(f"Total: {len(results)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")

    if failed:
        logger.error("\nFailed strategies:")
        for r in failed:
            logger.error(f"  - {r['strategy_id']}: {r['error']}")

    logger.info("\nAll strategies in database:")
    for r in successful:
        metrics = r['metrics']
        logger.info(f"  {r['strategy_id']:20s} | Sharpe: {metrics['sharpe_ratio']:6.2f} | Days: {r['total_days']:4d}")

    return results


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("BACKTEST DATA INGESTION TOOL")
    logger.info("=" * 80)

    # Default path to real strategy data
    default_data_folder = '/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/dev/portfolio_combiner/real_strategy_data'

    # Check if folder exists
    if not os.path.exists(default_data_folder):
        logger.error(f"Data folder not found: {default_data_folder}")
        sys.exit(1)

    # Ingest all strategies
    results = ingest_all_strategies(default_data_folder)

    logger.info("\n✅ Ingestion complete!")
