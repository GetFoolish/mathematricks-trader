"""
Strategy Data Ingestion Script
Reads portfolio_combiner CSV outputs and stores full data in MongoDB
Including: dates, returns, margin, notional, P&L
"""
import os
import glob
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

def ingest_strategy_data(csv_folder_path):
    """
    Ingest strategy data from portfolio_combiner CSV files into MongoDB

    Args:
        csv_folder_path: Path to folder containing strategy CSV files
            (e.g., outputs/run_*/strategy_performance_data/)
    """
    print(f"Starting data ingestion from: {csv_folder_path}\n")

    # Connect to MongoDB
    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    collection = db['strategy_backtest_data']

    # Find all CSV files
    csv_files = glob.glob(os.path.join(csv_folder_path, '*.csv'))

    if not csv_files:
        print(f"ERROR: No CSV files found in {csv_folder_path}")
        return

    print(f"Found {len(csv_files)} strategy files to ingest\n")

    ingested_count = 0
    updated_count = 0
    error_count = 0

    for filepath in csv_files:
        strategy_name = os.path.basename(filepath).replace('.csv', '')

        try:
            print(f"Processing: {strategy_name}")

            # Read CSV
            df = pd.read_csv(filepath)

            # Expected columns: Date, Daily P&L ($), Daily Returns (%),
            #                   Daily Return on Notional (%), Maximum Daily Notional Value,
            #                   Maximum Daily Margin Utilization ($)

            # Parse dates
            df['Date'] = pd.to_datetime(df['Date'])

            # Parse returns (remove % sign and convert to float)
            df['Daily Returns (%)'] = df['Daily Returns (%)'].str.rstrip('%').astype('float') / 100

            # Build raw_data_backtest (simple format for compatibility)
            raw_data_backtest = []
            for idx, row in df.iterrows():
                raw_data_backtest.append({
                    'date': row['Date'].strftime('%Y-%m-%d'),
                    'return': row['Daily Returns (%)']
                })

            # Build raw_data_backtest_full (complete format with margin/notional/account_equity)
            raw_data_backtest_full = []
            for idx, row in df.iterrows():
                raw_data_backtest_full.append({
                    'date': row['Date'].strftime('%Y-%m-%d'),
                    'return': row['Daily Returns (%)'],
                    'pnl': float(row['Daily P&L ($)']),
                    'notional_value': float(row['Maximum Daily Notional Value']),
                    'margin_used': float(row['Maximum Daily Margin Utilization ($)']),
                    'account_equity': float(row['Account Equity ($)'])  # NEW - needed for margin %
                })

            # Calculate basic metrics for backward compatibility
            returns = df['Daily Returns (%)'].values
            mean_return_daily = float(returns.mean())
            volatility_daily = float(returns.std())

            # Prepare document
            doc = {
                'strategy_id': strategy_name,
                'raw_data_backtest': raw_data_backtest,
                'raw_data_backtest_full': raw_data_backtest_full,  # NEW - full data
                'metrics': {
                    'mean_return_daily': mean_return_daily,
                    'volatility_daily': volatility_daily,
                    'total_days': len(df),
                    'start_date': df['Date'].min().strftime('%Y-%m-%d'),
                    'end_date': df['Date'].max().strftime('%Y-%m-%d')
                },
                'last_updated': datetime.utcnow(),
                'data_source': 'portfolio_combiner_csv',
                'data_source_path': filepath
            }

            # Upsert into MongoDB
            result = collection.replace_one(
                {'strategy_id': strategy_name},
                doc,
                upsert=True
            )

            if result.matched_count > 0:
                print(f"  ✓ Updated: {strategy_name} ({len(df)} days)")
                updated_count += 1
            else:
                print(f"  ✓ Inserted: {strategy_name} ({len(df)} days)")
                ingested_count += 1

        except Exception as e:
            print(f"  ✗ ERROR processing {strategy_name}: {str(e)}")
            error_count += 1
            continue

    print(f"\n{'='*60}")
    print(f"Ingestion Complete!")
    print(f"  - New inserts: {ingested_count}")
    print(f"  - Updates: {updated_count}")
    print(f"  - Errors: {error_count}")
    print(f"{'='*60}\n")

    client.close()


if __name__ == "__main__":
    # Default to latest run
    outputs_dir = '/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/dev/portfolio_combiner/outputs'

    if len(sys.argv) > 1:
        # Use provided path
        csv_folder = sys.argv[1]
    else:
        # Auto-detect latest run
        run_dirs = [d for d in os.listdir(outputs_dir) if d.startswith('run_')]
        if not run_dirs:
            print("ERROR: No run directories found in outputs/")
            sys.exit(1)

        latest_run = sorted(run_dirs)[-1]
        csv_folder = os.path.join(outputs_dir, latest_run, 'strategy_performance_data')
        print(f"Auto-detected latest run: {latest_run}\n")

    ingest_strategy_data(csv_folder)
