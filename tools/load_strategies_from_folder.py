#!/usr/bin/env python3
"""
Load Strategy Backtest Data from CSV Folder
Usage: python load_strategies_from_folder.py <path_to_csv_folder>
"""
import os
import sys
import pandas as pd
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
PROJECT_ROOT = "/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader"
load_dotenv(f'{PROJECT_ROOT}/.env')

# MongoDB connection
mongo_uri = os.getenv('MONGODB_URI')
client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
db = client['mathematricks_trading']

def load_strategies_from_folder(folder_path):
    """Load all CSV files in folder as strategy backtest data"""

    if not os.path.exists(folder_path):
        print(f"❌ Folder not found: {folder_path}")
        sys.exit(1)

    # Find all CSV files
    csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

    if not csv_files:
        print(f"❌ No CSV files found in: {folder_path}")
        sys.exit(1)

    print("="*80)
    print(f"LOADING STRATEGIES FROM: {folder_path}")
    print("="*80)
    print(f"Found {len(csv_files)} CSV files\n")

    loaded_count = 0

    for csv_file in sorted(csv_files):
        strategy_id = csv_file.replace('.csv', '')
        csv_path = os.path.join(folder_path, csv_file)

        print(f"\n📊 Processing: {strategy_id}")
        print("-" * 60)

        try:
            # Read CSV
            df = pd.read_csv(csv_path)

            # Find date column (try different names)
            date_col = None
            for col in df.columns:
                if 'date' in col.lower():
                    date_col = col
                    break

            if date_col is None:
                print(f"⚠️  Skipping - no date column found")
                print(f"   Available columns: {', '.join(df.columns)}")
                continue

            # Find returns column (try different names)
            returns_col = None
            for col in df.columns:
                if 'return' in col.lower():
                    returns_col = col
                    break

            if returns_col is None:
                print(f"⚠️  Skipping - no returns column found")
                print(f"   Available columns: {', '.join(df.columns)}")
                continue

            # Parse dates
            df[date_col] = pd.to_datetime(df[date_col])

            # Clean returns data: strip % signs and convert to decimal
            df[returns_col] = df[returns_col].astype(str).str.rstrip('%,').str.strip()
            df[returns_col] = pd.to_numeric(df[returns_col], errors='coerce') / 100

            # Remove rows with NaN returns
            df = df[df[returns_col].notna()]

            if len(df) == 0:
                print(f"⚠️  Skipping - no valid data after cleaning")
                continue

            # Build raw_data_backtest: preserve ALL columns from CSV
            raw_data_backtest = []
            for _, row in df.iterrows():
                record = {
                    "date": row[date_col].strftime('%Y-%m-%d'),
                    "return": float(row[returns_col])
                }

                # Add any other columns that exist (max_notional, max_margin, pnl, etc.)
                for col in df.columns:
                    if col not in [date_col, returns_col]:
                        # Try to convert to float, skip if can't
                        try:
                            # Clean percentage or currency symbols
                            val = str(row[col]).replace('%', '').replace('$', '').replace(',', '').strip()
                            if val and val.lower() not in ['nan', 'none', '']:
                                record[col.lower().replace(' ', '_')] = float(val)
                        except:
                            pass

                raw_data_backtest.append(record)

            # Calculate metrics from returns
            returns_series = df[returns_col]
            mean_return_daily = returns_series.mean()
            volatility_daily = returns_series.std()

            # Calculate Sharpe ratio (annualized)
            sharpe_ratio = (mean_return_daily / volatility_daily * (252 ** 0.5)) if volatility_daily > 0 else 0

            # Calculate max drawdown
            cumulative = (1 + returns_series).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()

            # Get date range
            start_date = df[date_col].min().strftime('%Y-%m-%d')
            end_date = df[date_col].max().strftime('%Y-%m-%d')

            # Display metrics
            print(f"   Data points: {len(raw_data_backtest)}")
            print(f"   Date range: {start_date} to {end_date}")
            print(f"   Mean return: {mean_return_daily*100:.4f}% daily")
            print(f"   Volatility: {volatility_daily*100:.4f}% daily")
            print(f"   Sharpe (annual): {sharpe_ratio:.2f}")
            print(f"   Max Drawdown: {max_drawdown*100:.2f}%")

            # Insert strategy configuration
            strategy_doc = {
                "strategy_id": strategy_id,
                "name": strategy_id.replace('_', ' ').replace('-', ' - '),
                "asset_class": "unknown",  # Can be updated later
                "instruments": [],  # Can be updated later
                "status": "ACTIVE",
                "trading_mode": "PAPER",
                "account": "IBKR_Main",
                "include_in_optimization": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            db.strategy_configurations.replace_one(
                {"strategy_id": strategy_id},
                strategy_doc,
                upsert=True
            )

            # Insert backtest data with new structure
            backtest_doc = {
                "strategy_id": strategy_id,
                "raw_data_backtest": raw_data_backtest,
                "raw_data_developer_live": [],  # Empty initially
                "raw_data_mathematricks_live": [],  # Empty initially
                "metrics": {
                    "mean_return_daily": float(mean_return_daily),
                    "volatility_daily": float(volatility_daily),
                    "sharpe_ratio": float(sharpe_ratio),
                    "max_drawdown": float(max_drawdown),
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_days": len(raw_data_backtest)
                },
                "last_updated": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }

            db.strategy_backtest_data.replace_one(
                {"strategy_id": strategy_id},
                backtest_doc,
                upsert=True
            )

            print(f"   ✅ Loaded into MongoDB")
            loaded_count += 1

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            continue

    print("\n" + "="*80)
    print(f"✅ COMPLETE: Loaded {loaded_count}/{len(csv_files)} strategies")
    print("="*80)

    # Show what's in MongoDB now
    print("\n📋 Strategies in MongoDB:")
    strategies = list(db.strategy_configurations.find({}, {"strategy_id": 1, "status": 1, "include_in_optimization": 1}))
    for s in strategies:
        opt = "✓" if s.get('include_in_optimization') else "✗"
        print(f"   [{opt}] {s['strategy_id']} - {s.get('status', 'N/A')}")

    print("\n💡 Next steps:")
    print("   1. Run portfolio optimization: cd services/cerebro_service && python optimization_runner.py")
    print("   2. Check frontend: http://localhost:5173/strategies")
    print()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python load_strategies_from_folder.py <path_to_csv_folder>")
        print("\nExample:")
        print("  python load_strategies_from_folder.py /path/to/strategy/csvs")
        sys.exit(1)

    folder_path = sys.argv[1]
    load_strategies_from_folder(folder_path)
