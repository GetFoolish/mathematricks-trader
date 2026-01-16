#!/usr/bin/env python3
"""
Generate synthetic backtest CSV files for IBKR test strategies.
Creates 3000 days of realistic backtest data for 5 different asset classes.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_strategy_backtest(
    strategy_name: str,
    num_days: int = 3000,
    mean_daily_return: float = 0.0005,
    volatility: float = 0.015,
    sharpe_ratio: float = 1.2,
    avg_margin_pct: float = 0.25,
    starting_capital: float = 1000000
):
    """
    Generate synthetic backtest data with realistic characteristics.

    Args:
        strategy_name: Name of the strategy
        num_days: Number of trading days (default 3000)
        mean_daily_return: Average daily return (default 0.05%)
        volatility: Daily volatility (default 1.5%)
        sharpe_ratio: Target Sharpe ratio (default 1.2)
        avg_margin_pct: Average margin as % of account equity (default 25%)
        starting_capital: Starting account equity (default $1M)
    """

    # Generate dates (going back from today)
    end_date = datetime.now()
    dates = [end_date - timedelta(days=i) for i in range(num_days)]
    dates.reverse()

    # Generate returns with some autocorrelation for realism
    returns = np.random.normal(mean_daily_return, volatility, num_days)

    # Add some autocorrelation (momentum effect)
    for i in range(1, len(returns)):
        returns[i] += 0.15 * returns[i-1]

    # Add occasional drawdown periods
    drawdown_starts = np.random.choice(num_days, size=5, replace=False)
    for start in drawdown_starts:
        duration = np.random.randint(20, 60)
        for i in range(start, min(start + duration, num_days)):
            returns[i] -= 0.003  # Drawdown drift

    # Calculate cumulative metrics
    account_equity = starting_capital
    equity_curve = []
    pnl_values = []
    notional_values = []
    margin_values = []

    for i, ret in enumerate(returns):
        # Calculate PnL
        pnl = account_equity * ret
        account_equity += pnl

        # Generate notional value (with some randomness)
        # Higher for leveraged strategies, varies day to day
        base_notional = account_equity * (avg_margin_pct / 0.1)  # Assume 10% margin requirement
        notional = base_notional * np.random.uniform(0.7, 1.3)

        # Margin used (typically 10-30% of notional)
        margin = notional * np.random.uniform(0.10, 0.30)

        equity_curve.append(account_equity)
        pnl_values.append(pnl)
        notional_values.append(notional)
        margin_values.append(margin)

    # Create DataFrame
    df = pd.DataFrame({
        'date': [d.strftime('%Y-%m-%d') for d in dates],
        'return': returns,
        'pnl': pnl_values,
        'notional_value': notional_values,
        'margin_used': margin_values,
        'account_equity': equity_curve
    })

    return df


def main():
    """Generate all 5 IBKR demo strategy CSV files"""

    strategies = [
        {
            'filename': 'IBKR_Test_Stock.csv',
            'strategy_name': 'IBKR_Test_Stock',
            'mean_daily_return': 0.0008,  # 0.08% daily (strong performer)
            'volatility': 0.012,           # 1.2% daily vol
            'sharpe_ratio': 1.5,
            'avg_margin_pct': 0.15,        # Stocks use less margin
            'starting_capital': 1000000
        },
        {
            'filename': 'IBKR_Test_Crypto.csv',
            'strategy_name': 'IBKR_Test_Crypto',
            'mean_daily_return': 0.0012,  # 0.12% daily (high return)
            'volatility': 0.035,           # 3.5% daily vol (very volatile)
            'sharpe_ratio': 0.9,
            'avg_margin_pct': 0.30,        # Crypto can use more leverage
            'starting_capital': 1000000
        },
        {
            'filename': 'IBKR_Test_Forex.csv',
            'strategy_name': 'IBKR_Test_Forex',
            'mean_daily_return': 0.0006,  # 0.06% daily
            'volatility': 0.008,           # 0.8% daily vol (low vol)
            'sharpe_ratio': 1.8,           # High Sharpe (consistent)
            'avg_margin_pct': 0.40,        # Forex highly leveraged
            'starting_capital': 1000000
        },
        {
            'filename': 'IBKR_Test_Future.csv',
            'strategy_name': 'IBKR_Test_Future',
            'mean_daily_return': 0.0007,  # 0.07% daily
            'volatility': 0.018,           # 1.8% daily vol
            'sharpe_ratio': 1.1,
            'avg_margin_pct': 0.35,        # Futures leveraged
            'starting_capital': 1000000
        },
        {
            'filename': 'IBKR_Test_Option.csv',
            'strategy_name': 'IBKR_Test_Option',
            'mean_daily_return': 0.0015,  # 0.15% daily (highest return)
            'volatility': 0.025,           # 2.5% daily vol
            'sharpe_ratio': 1.3,
            'avg_margin_pct': 0.28,        # Options margin varies
            'starting_capital': 1000000
        }
    ]

    output_dir = '/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks/mathematricks-trader/tests/strategy_addition/ibkr_demo_strategies'

    print("=" * 60)
    print("=== Generating IBKR Demo Strategy CSV Files ===")
    print("=" * 60)

    for strategy in strategies:
        print(f"\nGenerating {strategy['filename']}...")

        df = generate_strategy_backtest(
            strategy_name=strategy['strategy_name'],
            num_days=3000,
            mean_daily_return=strategy['mean_daily_return'],
            volatility=strategy['volatility'],
            sharpe_ratio=strategy['sharpe_ratio'],
            avg_margin_pct=strategy['avg_margin_pct'],
            starting_capital=strategy['starting_capital']
        )

        output_path = f"{output_dir}/{strategy['filename']}"
        df.to_csv(output_path, index=False)

        # Calculate and print statistics
        total_return = (df['account_equity'].iloc[-1] / df['account_equity'].iloc[0] - 1) * 100
        max_drawdown = ((df['account_equity'].cummax() - df['account_equity']) / df['account_equity'].cummax()).max() * 100
        actual_sharpe = df['return'].mean() / df['return'].std() * np.sqrt(252)

        print(f"  ✅ Created: {output_path}")
        print(f"     Rows: {len(df)}")
        print(f"     Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
        print(f"     Total return: {total_return:.2f}%")
        print(f"     Max drawdown: {max_drawdown:.2f}%")
        print(f"     Sharpe ratio: {actual_sharpe:.2f}")
        print(f"     Final equity: ${df['account_equity'].iloc[-1]:,.2f}")

    print("\n" + "=" * 60)
    print("✅ All 5 CSV files generated successfully!")
    print("=" * 60)
    print(f"\nFiles saved to: {output_dir}/")
    print("\nNext steps:")
    print("1. Upload these CSV files through the frontend strategy upload interface")
    print("2. Map them to the 'IBKR_PAPER_TESTING' account")
    print("3. Set status to ACTIVE and include_in_optimization to true")
    print("4. Run test signals to verify integration")


if __name__ == '__main__':
    main()
