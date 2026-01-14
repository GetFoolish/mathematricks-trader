"""
Generate realistic test strategy data with 5000+ rows for comprehensive testing.

This script creates all 12 test CSV files with realistic data:
- Proper equity curves
- Realistic returns distribution
- Drawdown periods
- Recovery periods
- Multi-year backtests
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Set random seed for reproducibility
np.random.seed(42)

# Configuration
NUM_DAYS = 5000
STARTING_EQUITY = 100000
OUTPUT_DIR = os.path.dirname(__file__)


def generate_realistic_returns(num_days, win_rate=0.55, avg_win=1.2, avg_loss=-0.8, volatility=0.5):
    """
    Generate realistic return series.

    Args:
        num_days: Number of trading days
        win_rate: Probability of winning day (0-1)
        avg_win: Average win percentage
        avg_loss: Average loss percentage
        volatility: Volatility factor for randomness

    Returns:
        Array of daily returns
    """
    returns = []

    for i in range(num_days):
        if np.random.random() < win_rate:
            # Winning day
            ret = np.random.normal(avg_win, volatility)
            ret = max(0.1, ret)  # Minimum 0.1% win
        else:
            # Losing day
            ret = np.random.normal(avg_loss, volatility * 0.8)
            ret = min(-0.1, ret)  # Minimum 0.1% loss

        returns.append(ret)

    return np.array(returns)


def calculate_equity_curve(starting_equity, returns):
    """Calculate equity curve from returns."""
    equity = [starting_equity]

    for ret in returns:
        new_equity = equity[-1] * (1 + ret / 100)
        equity.append(new_equity)

    return equity[1:]  # Remove initial value


def calculate_daily_pnl(equity):
    """Calculate daily PnL from equity curve."""
    pnl = [0]  # First day

    for i in range(1, len(equity)):
        pnl.append(equity[i] - equity[i-1])

    return pnl


def calculate_margin_used(returns, equity):
    """Calculate realistic margin usage."""
    max_return = np.abs(returns).max()

    if max_return == 0:
        return np.zeros(len(returns))

    # Margin proportional to position size (based on return magnitude)
    margin = (np.abs(returns) / max_return) * equity * 0.8

    return margin


def calculate_notional_value(margin):
    """Calculate notional value (3x margin for futures)."""
    return margin * 3


def generate_dates(num_days, start_date='2020-01-01'):
    """Generate date range (business days only)."""
    start = pd.to_datetime(start_date)
    dates = pd.bdate_range(start=start, periods=num_days)
    return dates


def create_full_data_csv(num_days=NUM_DAYS):
    """Test File 1: Full data with all columns."""
    print("Generating test_strategy_full_data.csv (5000 rows)...")

    dates = generate_dates(num_days)
    returns = generate_realistic_returns(num_days, win_rate=0.58, avg_win=1.5, avg_loss=-1.0)
    equity = calculate_equity_curve(STARTING_EQUITY, returns)
    pnl = calculate_daily_pnl(equity)
    margin = calculate_margin_used(returns, equity)
    notional = calculate_notional_value(margin)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': np.round(returns, 4),
        'Account_Equity': np.round(equity, 2),
        'Daily_PnL': np.round(pnl, 2),
        'Max_Margin_Used': np.round(margin, 2),
        'Max_Notional_Value': np.round(notional, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_full_data.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(df)} rows, Final Equity: ${equity[-1]:,.2f}")
    return df


def create_missing_1col_csv(num_days=NUM_DAYS):
    """Test File 2: Missing Max_Notional_Value."""
    print("Generating test_strategy_missing_1col.csv...")

    dates = generate_dates(num_days)
    returns = generate_realistic_returns(num_days, win_rate=0.56, avg_win=1.3, avg_loss=-0.9)
    equity = calculate_equity_curve(STARTING_EQUITY, returns)
    pnl = calculate_daily_pnl(equity)
    margin = calculate_margin_used(returns, equity)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': np.round(returns, 4),
        'Account_Equity': np.round(equity, 2),
        'Daily_PnL': np.round(pnl, 2),
        'Max_Margin_Used': np.round(margin, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_missing_1col.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(df)} rows, Missing: Max_Notional_Value")
    return df


def create_missing_2cols_csv(num_days=NUM_DAYS):
    """Test File 3: Missing Max_Margin_Used and Max_Notional_Value."""
    print("Generating test_strategy_missing_2cols.csv...")

    dates = generate_dates(num_days)
    returns = generate_realistic_returns(num_days, win_rate=0.54, avg_win=1.1, avg_loss=-0.85)
    equity = calculate_equity_curve(STARTING_EQUITY, returns)
    pnl = calculate_daily_pnl(equity)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': np.round(returns, 4),
        'Account_Equity': np.round(equity, 2),
        'Daily_PnL': np.round(pnl, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_missing_2cols.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(df)} rows, Missing: Max_Margin_Used, Max_Notional_Value")
    return df


def create_missing_3cols_csv(num_days=NUM_DAYS):
    """Test File 4: Missing 3 columns (only Date, Return, Equity)."""
    print("Generating test_strategy_missing_3cols.csv...")

    dates = generate_dates(num_days)
    returns = generate_realistic_returns(num_days, win_rate=0.52, avg_win=1.0, avg_loss=-0.8)
    equity = calculate_equity_curve(STARTING_EQUITY, returns)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': np.round(returns, 4),
        'Account_Equity': np.round(equity, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_missing_3cols.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(df)} rows, Missing: Daily_PnL, Max_Margin_Used, Max_Notional_Value")
    return df


def create_minimal_csv(num_days=NUM_DAYS):
    """Test File 5: Minimal data (only Date and Daily_Return_Pct)."""
    print("Generating test_strategy_minimal.csv...")

    dates = generate_dates(num_days)
    returns = generate_realistic_returns(num_days, win_rate=0.60, avg_win=1.4, avg_loss=-0.9)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': np.round(returns, 4)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_minimal.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(df)} rows, Only: Date, Daily_Return_Pct")
    return df


def create_incremental_time_csv():
    """Test File 7: Additional 500 days for incremental update."""
    print("Generating test_strategy_incremental_time.csv...")

    # Start 500 days after the main test data
    start_date = pd.bdate_range(start='2020-01-01', periods=5001)[-1]
    dates = pd.bdate_range(start=start_date, periods=500)

    returns = generate_realistic_returns(500, win_rate=0.55, avg_win=1.3, avg_loss=-0.85)

    # Calculate equity continuing from where full_data left off
    # We'll need to get the last equity from full_data
    full_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'test_strategy_full_data.csv'))
    last_equity = full_df['Account_Equity'].iloc[-1]

    equity = calculate_equity_curve(last_equity, returns)
    pnl = calculate_daily_pnl(equity)
    margin = calculate_margin_used(returns, equity)
    notional = calculate_notional_value(margin)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': np.round(returns, 4),
        'Account_Equity': np.round(equity, 2),
        'Daily_PnL': np.round(pnl, 2),
        'Max_Margin_Used': np.round(margin, 2),
        'Max_Notional_Value': np.round(notional, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_incremental_time.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(df)} rows for incremental time update")
    return df


def create_incremental_columns_csv(num_days=5000):
    """Test File 8: Add new column to existing data."""
    print("Generating test_strategy_incremental_columns.csv...")

    # Use same dates as minimal data
    minimal_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'test_strategy_minimal.csv'))
    dates = pd.to_datetime(minimal_df['Date'])
    returns = minimal_df['Daily_Return_Pct'].values

    # Add Max_Margin_Used column
    equity = calculate_equity_curve(STARTING_EQUITY, returns)
    margin = calculate_margin_used(returns, equity)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': returns,
        'Max_Margin_Used': np.round(margin, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_incremental_columns.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(df)} rows with new Max_Margin_Used column")
    return df


def create_overlap_conflict_csv():
    """Test File 9: Overlapping dates (last 100 days from full_data + 50 new)."""
    print("Generating test_strategy_overlap_conflict.csv...")

    full_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'test_strategy_full_data.csv'))

    # Get last 100 days from full_data
    overlap_df = full_df.tail(100).copy()

    # Add 50 new days
    last_date = pd.to_datetime(overlap_df['Date'].iloc[-1])
    new_dates = pd.bdate_range(start=last_date + timedelta(days=1), periods=50)

    last_equity = overlap_df['Account_Equity'].iloc[-1]
    new_returns = generate_realistic_returns(50, win_rate=0.57, avg_win=1.2, avg_loss=-0.8)
    new_equity = calculate_equity_curve(last_equity, new_returns)
    new_pnl = calculate_daily_pnl(new_equity)
    new_margin = calculate_margin_used(new_returns, new_equity)
    new_notional = calculate_notional_value(new_margin)

    new_df = pd.DataFrame({
        'Date': new_dates,
        'Daily_Return_Pct': np.round(new_returns, 4),
        'Account_Equity': np.round(new_equity, 2),
        'Daily_PnL': np.round(new_pnl, 2),
        'Max_Margin_Used': np.round(new_margin, 2),
        'Max_Notional_Value': np.round(new_notional, 2)
    })

    combined_df = pd.concat([overlap_df, new_df], ignore_index=True)

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_overlap_conflict.csv')
    combined_df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(combined_df)} rows (100 overlapping + 50 new)")
    return combined_df


def create_overlap_force_csv():
    """Test File 10: Same as overlap_conflict but with modified values."""
    print("Generating test_strategy_overlap_force.csv...")

    overlap_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'test_strategy_overlap_conflict.csv'))

    # Modify returns slightly for overlapping period
    overlap_df['Daily_Return_Pct'] = overlap_df['Daily_Return_Pct'] * 1.1  # 10% higher returns

    # Recalculate dependent columns
    returns = overlap_df['Daily_Return_Pct'].values
    equity = calculate_equity_curve(STARTING_EQUITY, returns)
    pnl = calculate_daily_pnl(equity)
    margin = calculate_margin_used(returns, equity)
    notional = calculate_notional_value(margin)

    overlap_df['Account_Equity'] = np.round(equity, 2)
    overlap_df['Daily_PnL'] = np.round(pnl, 2)
    overlap_df['Max_Margin_Used'] = np.round(margin, 2)
    overlap_df['Max_Notional_Value'] = np.round(notional, 2)

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_overlap_force.csv')
    overlap_df.to_csv(filepath, index=False)
    print(f"  ✓ Created {len(overlap_df)} rows with modified values")
    return overlap_df


def create_invalid_format_csv():
    """Test File 11: Invalid data for error testing."""
    print("Generating test_strategy_invalid_format.csv...")

    df = pd.DataFrame({
        'Date': ['2025-01-01', '2025-01-02', '2025-01-03'],
        'Daily_Return_Pct': ['INVALID', 1.5, -0.8]
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_invalid_format.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created 3 rows with invalid return value")
    return df


def create_missing_required_csv():
    """Test File 12: Missing required column."""
    print("Generating test_strategy_missing_required.csv...")

    dates = generate_dates(100)
    equity = calculate_equity_curve(STARTING_EQUITY, generate_realistic_returns(100))

    df = pd.DataFrame({
        'Date': dates,
        'Account_Equity': np.round(equity, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_missing_required.csv')
    df.to_csv(filepath, index=False)
    print(f"  ✓ Created 100 rows missing Daily_Return_Pct")
    return df


def create_high_performance_strategy():
    """Bonus: High-performing strategy for showcasing."""
    print("Generating test_strategy_high_performance.csv...")

    dates = generate_dates(NUM_DAYS)
    returns = generate_realistic_returns(NUM_DAYS, win_rate=0.65, avg_win=1.8, avg_loss=-0.6)
    equity = calculate_equity_curve(STARTING_EQUITY, returns)
    pnl = calculate_daily_pnl(equity)
    margin = calculate_margin_used(returns, equity)
    notional = calculate_notional_value(margin)

    df = pd.DataFrame({
        'Date': dates,
        'Daily_Return_Pct': np.round(returns, 4),
        'Account_Equity': np.round(equity, 2),
        'Daily_PnL': np.round(pnl, 2),
        'Max_Margin_Used': np.round(margin, 2),
        'Max_Notional_Value': np.round(notional, 2)
    })

    filepath = os.path.join(OUTPUT_DIR, 'test_strategy_high_performance.csv')
    df.to_csv(filepath, index=False)

    # Calculate metrics
    total_return = ((equity[-1] / STARTING_EQUITY) - 1) * 100
    cagr = ((equity[-1] / STARTING_EQUITY) ** (365 / len(equity))) ** (365 / len(equity)) - 1

    print(f"  ✓ Created {len(df)} rows")
    print(f"    Final Equity: ${equity[-1]:,.2f}")
    print(f"    Total Return: {total_return:.2f}%")
    return df


def main():
    """Generate all test data files."""
    print("=" * 60)
    print("Generating Realistic Test Strategy Data (5000+ rows)")
    print("=" * 60)
    print()

    # Create all test files
    create_full_data_csv()
    create_missing_1col_csv()
    create_missing_2cols_csv()
    create_missing_3cols_csv()
    create_minimal_csv()

    # These depend on files above being created first
    create_incremental_time_csv()
    create_incremental_columns_csv()
    create_overlap_conflict_csv()
    create_overlap_force_csv()

    # Error test files
    create_invalid_format_csv()
    create_missing_required_csv()

    # Bonus high-performance strategy
    create_high_performance_strategy()

    print()
    print("=" * 60)
    print("✓ All test data files generated successfully!")
    print("=" * 60)
    print()
    print("Test files created:")
    print("  1. test_strategy_full_data.csv (5000 rows)")
    print("  2. test_strategy_missing_1col.csv (5000 rows)")
    print("  3. test_strategy_missing_2cols.csv (5000 rows)")
    print("  4. test_strategy_missing_3cols.csv (5000 rows)")
    print("  5. test_strategy_minimal.csv (5000 rows)")
    print("  7. test_strategy_incremental_time.csv (500 rows)")
    print("  8. test_strategy_incremental_columns.csv (5000 rows)")
    print("  9. test_strategy_overlap_conflict.csv (150 rows)")
    print(" 10. test_strategy_overlap_force.csv (150 rows)")
    print(" 11. test_strategy_invalid_format.csv (3 rows)")
    print(" 12. test_strategy_missing_required.csv (100 rows)")
    print(" 13. test_strategy_high_performance.csv (5000 rows - BONUS)")


if __name__ == '__main__':
    main()
