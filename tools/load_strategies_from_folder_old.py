#!/usr/bin/env python3
"""
Load Strategy Backtest Data from CSV Folder
Usage: python load_strategies_from_folder.py <path_to_csv_folder>
"""
import os
import sys
import random
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

def load_strategies_from_folder(folder_path, starting_capital=1_000_000):
    """
    Load all CSV files in folder as strategy backtest data.
    Generates synthetic data for missing columns using intelligent defaults.
    
    Args:
        folder_path: Path to folder containing CSV files
        starting_capital: Starting capital for equity curve calculation (default: $1M)
    """

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

    # Default parameters for synthetic data generation
    DEFAULT_PARAMS = {
        'base_notional': 1_000_000,
        'base_margin': 100_000,
        'typical_contracts': 10
    }

    # Strategy-specific parameters (can be customized)
    STRATEGY_PARAMS = {
        'SPY': {'base_notional': 500_000, 'base_margin': 250_000, 'typical_contracts': 5},
        'TLT': {'base_notional': 300_000, 'base_margin': 150_000, 'typical_contracts': 3},
        'SPX_0DTE_Opt': {'base_notional': 5_000_000, 'base_margin': 50_000, 'typical_contracts': 10},
        'SPX_1-D_Opt': {'base_notional': 4_000_000, 'base_margin': 40_000, 'typical_contracts': 10},
        'Forex': {'base_notional': 200_000, 'base_margin': 20_000, 'typical_contracts': 10},
        'Com1-Met': {'base_notional': 800_000, 'base_margin': 80_000, 'typical_contracts': 10},
        'Com2-Ag': {'base_notional': 600_000, 'base_margin': 60_000, 'typical_contracts': 10},
        'Com3-Mkt': {'base_notional': 900_000, 'base_margin': 90_000, 'typical_contracts': 10},
        'Com4-Misc': {'base_notional': 400_000, 'base_margin': 40_000, 'typical_contracts': 5}
    }

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
            if df[returns_col].dtype == 'object':
                df[returns_col] = df[returns_col].astype(str).str.rstrip('%,').str.strip()
            df[returns_col] = pd.to_numeric(df[returns_col], errors='coerce')
            
            # Check if returns are in percentage format (like 0.5 meaning 0.5%)
            if df[returns_col].abs().max() > 1:
                df[returns_col] = df[returns_col] / 100

            # Remove rows with NaN returns
            df = df[df[returns_col].notna()]

            if len(df) == 0:
                print(f"⚠️  Skipping - no valid data after cleaning")
                continue

            # Get strategy parameters for synthetic data generation
            params = STRATEGY_PARAMS.get(strategy_id, DEFAULT_PARAMS)
            notional_per_contract = params['base_notional'] / params['typical_contracts']
            margin_per_contract = params['base_margin'] / params['typical_contracts']
            
            # Check which columns exist vs need to be synthesized
            has_pnl = any('p&l' in col.lower() or 'pnl' in col.lower() for col in df.columns)
            has_notional = any('notional' in col.lower() for col in df.columns)
            has_margin = any('margin' in col.lower() for col in df.columns)
            has_account_equity = any('account' in col.lower() and 'equity' in col.lower() for col in df.columns)
            
            synthetic_columns = []
            if not has_pnl:
                synthetic_columns.append('pnl')
            if not has_notional:
                synthetic_columns.append('notional_value')
            if not has_margin:
                synthetic_columns.append('margin_used')
            if not has_account_equity:
                synthetic_columns.append('account_equity')
            
            if synthetic_columns:
                print(f"   🔧 Generating synthetic data for: {', '.join(synthetic_columns)}")

            # Build raw_data_backtest_full with all required fields
            raw_data_backtest_full = []
            equity_curve = starting_capital
            
            for idx, row in df.iterrows():
                daily_return = float(row[returns_col])
                
                # Calculate or extract Daily P&L
                if has_pnl:
                    pnl_col = [col for col in df.columns if 'p&l' in col.lower() or 'pnl' in col.lower()][0]
                    daily_pnl = float(str(row[pnl_col]).replace('$', '').replace(',', '').strip())
                else:
                    # Synthetic: calculate from returns and equity
                    daily_pnl = equity_curve * daily_return
                
                # Update equity curve
                equity_curve += daily_pnl
                
                # Calculate or extract Notional Value
                if has_notional:
                    notional_col = [col for col in df.columns if 'notional' in col.lower()][0]
                    notional_value = float(str(row[notional_col]).replace('$', '').replace(',', '').strip())
                else:
                    # Synthetic: only generate notional when strategy is trading (non-zero returns)
                    if abs(daily_return) < 0.0001:  # No position
                        notional_value = 0.0
                    else:
                        notional_value = params['typical_contracts'] * notional_per_contract
                
                # Calculate or extract Margin Used
                if has_margin:
                    margin_col = [col for col in df.columns if 'margin' in col.lower()][0]
                    margin_used = float(str(row[margin_col]).replace('$', '').replace(',', '').strip())
                else:
                    # Synthetic: only generate margin when strategy is trading (non-zero returns)
                    if abs(daily_return) < 0.0001:  # No position
                        margin_used = 0.0
                    else:
                        # Use typical contracts * margin per contract (fixed position size)
                        margin_used = params['typical_contracts'] * margin_per_contract
                
                # Calculate or extract Account Equity
                if has_account_equity:
                    equity_col = [col for col in df.columns if 'account' in col.lower() and 'equity' in col.lower()][0]
                    account_equity = float(str(row[equity_col]).replace('$', '').replace(',', '').strip())
                else:
                    # Synthetic: use current equity curve value
                    account_equity = equity_curve
                
                raw_data_backtest_full.append({
                    'date': row[date_col].strftime('%Y-%m-%d'),
                    'return': daily_return,
                    'pnl': daily_pnl,
                    'notional_value': notional_value,
                    'margin_used': margin_used,
                    'account_equity': account_equity
                })

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
            print(f"   Data points: {len(raw_data_backtest_full)}")
            print(f"   Date range: {start_date} to {end_date}")
            print(f"   Mean return: {mean_return_daily*100:.4f}% daily")
            print(f"   Volatility: {volatility_daily*100:.4f}% daily")
            print(f"   Sharpe (annual): {sharpe_ratio:.2f}")
            print(f"   Max Drawdown: {max_drawdown*100:.2f}%")
            print(f"   Final Equity: ${equity_curve:,.0f} (from ${starting_capital:,.0f})")
            if synthetic_columns:
                print(f"   📝 Synthetic columns marked in metadata")

            # Create unified strategy document
            strategy_doc = {
                # Core identification
                "strategy_id": strategy_id,
                "strategy_name": strategy_id.replace('_', ' ').replace('-', ' - '),
                
                # Configuration
                "asset_class": "unknown",  # Can be updated via frontend
                "instruments": [],  # Can be updated via frontend
                "status": "ACTIVE",
                "trading_mode": "PAPER",
                "account": "IBKR_Main",
                "include_in_optimization": True,
                
                # Backtest data
                "raw_data_backtest_full": raw_data_backtest_full,
                "raw_data_developer_live": [],  # Empty initially
                "raw_data_mathematricks_live": [],  # Empty initially
                
                # Metrics
                "metrics": {
                    "mean_return_daily": float(mean_return_daily),
                    "volatility_daily": float(volatility_daily),
                    "sharpe_ratio": float(sharpe_ratio),
                    "max_drawdown": float(max_drawdown),
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_days": len(raw_data_backtest_full)
                },
                
                # Metadata
                "synthetic_data": {
                    "columns_generated": synthetic_columns,
                    "starting_capital": starting_capital,
                    "params_used": params
                },
                
                # Timestamps
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Insert/update single unified document
            db.strategies.replace_one(
                {"strategy_id": strategy_id},
                strategy_doc,
                upsert=True
            )

            print(f"   ✅ Loaded into MongoDB (unified document)")
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
    strategies = list(db.strategies.find({}, {"strategy_id": 1, "status": 1, "include_in_optimization": 1}))
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
