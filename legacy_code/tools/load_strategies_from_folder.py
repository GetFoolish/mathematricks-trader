#!/usr/bin/env python3
"""
Load Strategy Backtest Data from CSV Folder
Usage: python load_strategies_from_folder.py <path_to_csv_folder>

Synthetic Data Generation Logic (Excel-based):
- Date: From CSV (required)
- Daily_Return_Pct: From CSV (required)
- Account_Equity: Row 1 = starting_capital, Row N = previous_equity * (1 + previous_return/100)
- Daily_PnL: Row 1 = 0, Row N = current_equity - previous_equity
- Max_Margin_Used: ABS(return) / MAX(all_returns) * equity * 0.8
- Max_Notional_Value: margin * 3
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from scipy import stats

# Load environment
PROJECT_ROOT = "/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader"
load_dotenv(f'{PROJECT_ROOT}/.env')

# MongoDB connection
mongo_uri = os.getenv('MONGODB_URI')
client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
db = client['mathematricks_trading']


def detect_position_count_from_margin_steps(margin_data):
    """
    Detect estimated average position count by analyzing margin usage patterns.

    The logic:
    1. Get all non-zero margin values
    2. Calculate differences between consecutive sorted values (step sizes)
    3. Find the most common step size (this represents typical position margin)
    4. Estimate avg positions = median(margin) / typical_position_margin

    Args:
        margin_data: List of margin_used values from backtest

    Returns:
        dict with:
            - estimated_avg_positions: Estimated typical number of open positions
            - estimated_position_margin: Estimated margin per position
            - margin_pct_median: Median margin as % of equity
            - confidence: "high", "medium", or "low" based on data quality
    """
    # Filter out zero margin days (no positions)
    non_zero_margin = [m for m in margin_data if m > 0]

    if len(non_zero_margin) < 10:
        # Not enough data points
        return {
            "estimated_avg_positions": 3.0,  # Default assumption
            "estimated_position_margin": np.median(non_zero_margin) / 3.0 if non_zero_margin else 1000.0,
            "confidence": "low",
            "reason": "Insufficient data (less than 10 non-zero margin days)"
        }

    # Sort margin values
    sorted_margin = np.sort(non_zero_margin)

    # Calculate differences (step sizes)
    diffs = np.diff(sorted_margin)

    # Remove very small differences (noise) - keep diffs > 1% of median margin
    median_margin = np.median(sorted_margin)
    noise_threshold = median_margin * 0.01
    significant_diffs = diffs[diffs > noise_threshold]

    if len(significant_diffs) == 0:
        # All diffs are tiny - likely single position strategy
        return {
            "estimated_avg_positions": 1.0,
            "estimated_position_margin": median_margin,
            "confidence": "medium",
            "reason": "No significant margin steps detected - likely single position"
        }

    # Find the most common step size using histogram
    # Bin the diffs to find the mode
    hist, bin_edges = np.histogram(significant_diffs, bins=20)
    most_common_bin_idx = np.argmax(hist)
    typical_step = (bin_edges[most_common_bin_idx] + bin_edges[most_common_bin_idx + 1]) / 2

    # Alternative: use mode from scipy.stats
    try:
        mode_result = stats.mode(np.round(significant_diffs / 1000) * 1000, keepdims=False)  # Round to nearest 1000
        typical_step_alt = float(mode_result.mode) if hasattr(mode_result, 'mode') else typical_step
    except:
        typical_step_alt = typical_step

    # Use the histogram-based approach (more robust)
    estimated_position_margin = typical_step

    # Calculate estimated average positions
    estimated_avg_positions = median_margin / estimated_position_margin if estimated_position_margin > 0 else 1.0

    # Cap at reasonable bounds (1-20 positions)
    estimated_avg_positions = max(1.0, min(20.0, estimated_avg_positions))

    # Determine confidence based on data consistency
    cv = np.std(significant_diffs) / np.mean(significant_diffs) if np.mean(significant_diffs) > 0 else 1.0  # Coefficient of variation

    if cv < 0.3:
        confidence = "high"
    elif cv < 0.6:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "estimated_avg_positions": round(estimated_avg_positions, 1),
        "estimated_position_margin": round(estimated_position_margin, 2),
        "confidence": confidence,
        "reason": f"Detected from {len(non_zero_margin)} margin data points, CV={cv:.2f}"
    }


def load_strategies_from_folder(folder_path, starting_capital=1_000_000):
    """
    Load all CSV files in folder as strategy backtest data.
    Generates synthetic data for missing columns using Excel formula logic.

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

            # Check which columns exist vs need to be synthesized
            has_pnl = any('p&l' in col.lower() or 'pnl' in col.lower() for col in df.columns)
            has_notional = any('notional' in col.lower() for col in df.columns)
            has_margin = any('margin' in col.lower() for col in df.columns)
            has_account_equity = any('account' in col.lower() and 'equity' in col.lower() for col in df.columns)

            # Extract existing columns if they exist
            pnl_col = [col for col in df.columns if 'p&l' in col.lower() or 'pnl' in col.lower()][0] if has_pnl else None
            notional_col = [col for col in df.columns if 'notional' in col.lower()][0] if has_notional else None
            margin_col = [col for col in df.columns if 'margin' in col.lower()][0] if has_margin else None
            equity_col = [col for col in df.columns if 'account' in col.lower() and 'equity' in col.lower()][0] if has_account_equity else None

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
            else:
                print(f"   ✓ All columns provided by strategy developer")

            # =====================================================================
            # EXCEL-BASED SYNTHETIC DATA GENERATION
            # =====================================================================

            # Step 1: Get all returns for MAX calculation (needed for margin formula)
            returns_array = df[returns_col].values
            max_return = abs(returns_array).max() if len(returns_array) > 0 else 1.0

            # Avoid division by zero
            if max_return < 0.0001:
                max_return = 1.0

            # Step 2: Build the full data with Excel formulas
            raw_data_backtest_full = []
            equity = starting_capital  # Initial equity (Row 1: C2 = 1000000)

            for idx, row in df.iterrows():
                daily_return_pct = float(row[returns_col]) * 100  # Convert to percentage (e.g., 0.01 → 1%)

                # --- Account_Equity (C column) ---
                # Row 1: starting_capital
                # Row N: previous_equity * (1 + previous_return/100)
                if not has_account_equity:
                    if idx == df.index[0]:  # First row
                        account_equity = starting_capital
                    else:
                        # Already updated from previous iteration
                        account_equity = equity
                else:
                    account_equity = float(str(row[equity_col]).replace('$', '').replace(',', '').strip())
                    equity = account_equity  # Track for next iteration

                # --- Daily_PnL (D column) ---
                # Row 1: 0
                # Row N: current_equity - previous_equity
                if not has_pnl:
                    if idx == df.index[0]:  # First row
                        daily_pnl = 0.0
                    else:
                        daily_pnl = account_equity - equity_before_pnl
                else:
                    daily_pnl = float(str(row[pnl_col]).replace('$', '').replace(',', '').strip())

                # Store equity before P&L for next iteration's calculation
                equity_before_pnl = equity

                # Update equity for next iteration (C3 = C2 * (1 + B2/100))
                if not has_account_equity:
                    equity = account_equity * (1 + daily_return_pct / 100)

                # --- Max_Margin_Used (E column) ---
                # Formula: ABS(return) / MAX(returns) * equity * 0.8
                if not has_margin:
                    margin_used = (abs(daily_return_pct / 100) / max_return) * account_equity * 0.8
                else:
                    margin_used = float(str(row[margin_col]).replace('$', '').replace(',', '').strip())

                # --- Max_Notional_Value (F column) ---
                # Formula: margin * 3
                if not has_notional:
                    notional_value = margin_used * 3
                else:
                    notional_value = float(str(row[notional_col]).replace('$', '').replace(',', '').strip())

                raw_data_backtest_full.append({
                    'date': row[date_col].strftime('%Y-%m-%d'),
                    'return': float(row[returns_col]),  # Store as decimal (0.01 = 1%)
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
            print(f"   Final Equity: ${equity:,.0f} (from ${starting_capital:,.0f})")

            # Show margin statistics
            margin_pcts = [(d['margin_used'] / d['account_equity'] * 100) for d in raw_data_backtest_full if d['account_equity'] > 0]
            margin_dollars = [d['margin_used'] for d in raw_data_backtest_full]

            if margin_pcts:
                print(f"   Margin Used: min={min(margin_pcts):.1f}%, max={max(margin_pcts):.1f}%, avg={sum(margin_pcts)/len(margin_pcts):.1f}%")

            # Detect position count from margin steps
            position_analysis = detect_position_count_from_margin_steps(margin_dollars)
            print(f"   📊 Position Analysis:")
            print(f"      Estimated Avg Positions: {position_analysis['estimated_avg_positions']}")
            print(f"      Estimated Position Margin: ${position_analysis['estimated_position_margin']:,.2f}")
            print(f"      Confidence: {position_analysis['confidence']}")
            print(f"      Reason: {position_analysis['reason']}")

            # Calculate median margin percentage
            median_margin_pct = np.median(margin_pcts) if margin_pcts else 0.0

            if synthetic_columns:
                print(f"   📝 Synthetic columns: {', '.join(synthetic_columns)}")

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
                    "max_return_used": float(max_return),
                    "margin_formula": "ABS(return) / MAX(returns) * equity * 0.8",
                    "notional_formula": "margin * 3"
                },

                # Position sizing metadata
                "position_sizing": {
                    "estimated_avg_positions": position_analysis['estimated_avg_positions'],
                    "estimated_position_margin": position_analysis['estimated_position_margin'],
                    "median_margin_pct": float(median_margin_pct),
                    "confidence": position_analysis['confidence'],
                    "detection_method": "margin_step_analysis",
                    "reason": position_analysis['reason']
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
