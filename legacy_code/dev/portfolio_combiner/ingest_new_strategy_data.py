import pandas as pd
import os
from datetime import datetime

def ingest_strategy_data(input_csv_path, strategy_name, output_folder='strategy_performance_data', starting_capital=1_000_000, custom_params=None):
    """
    Converts a CSV with Date and Daily Returns (%) columns into the full format required by portfolio_combiner.
    Reconstructs all other columns using the same logic as sample_strategy_data_maker.py.

    Args:
        input_csv_path (str): Path to CSV with columns: Date, Daily Returns (%)
        strategy_name (str): Name of the strategy (will be used as filename)
        output_folder (str): Folder where the reconstructed CSV will be saved
        starting_capital (float): Starting capital for equity curve calculation
        custom_params (dict): Optional custom parameters to override defaults. Format:
            {
                'base_notional': 5500000,        # Total notional value at typical position
                'base_margin': 50000,            # Total margin at typical position
                'margin_per_contract': 5000,     # Margin required per contract/unit
                'typical_contracts': 10,         # Typical position size in contracts
                'min_position': 1,               # Minimum position size
                'position_increment': 1          # Position sizing increment
            }
    """

    # --- Strategy Parameter Configuration ---
    # These parameters are used to estimate notional and margin values
    # You can override these by passing custom_params argument
    strategy_params = {
      # ===== IBKR Main Account Strategies (7) =====
      'SPX_Condors': {
          'base_notional': 5500000,
          'base_margin': 50000,
          'margin_per_contract': 5000,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'SPX_Butterflies': {
          'base_notional': 3300000,
          'base_margin': 30000,
          'margin_per_contract': 3000,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'NDX_IronCondors': {
          'base_notional': 7200000,
          'base_margin': 65000,
          'margin_per_contract': 6500,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'RUT_CreditSpreads': {
          'base_notional': 4400000,
          'base_margin': 44000,
          'margin_per_contract': 4400,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'Equity_LongShort': {
          'base_notional': 2000000,
          'base_margin': 1000000,
          'margin_per_contract': 100000,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'TLT_Covered_Calls': {
          'base_notional': 1800000,
          'base_margin': 900000,
          'margin_per_contract': 90000,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'VIX_Calendar': {
          'base_notional': 3800000,
          'base_margin': 38000,
          'margin_per_contract': 3800,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      # ===== Futures Account Strategies (7) =====
      'Forex_Trend': {
          'base_notional': 200000,
          'base_margin': 20000,
          'margin_per_contract': 2000,
          'typical_contracts': 10,
          'min_position': 0.01,
          'position_increment': 0.1
      },
      'Gold_Breakout': {
          'base_notional': 820000,
          'base_margin': 82000,
          'margin_per_contract': 8200,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'Crude_Momentum': {
          'base_notional': 600000,
          'base_margin': 60000,
          'margin_per_contract': 6000,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'ES_Scalping': {
          'base_notional': 1250000,
          'base_margin': 125000,
          'margin_per_contract': 12500,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'NQ_Trend': {
          'base_notional': 1800000,
          'base_margin': 180000,
          'margin_per_contract': 18000,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'ZN_MeanReversion': {
          'base_notional': 220000,
          'base_margin': 22000,
          'margin_per_contract': 2200,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      'GC_Breakout': {
          'base_notional': 720000,
          'base_margin': 72000,
          'margin_per_contract': 7200,
          'typical_contracts': 10,
          'min_position': 1,
          'position_increment': 1
      },
      # ===== Crypto Account Strategies (7) =====
      'BTC_Trend': {
          'base_notional': 450000,
          'base_margin': 45000,
          'margin_per_contract': 15000,
          'typical_contracts': 3,
          'min_position': 0.01,
          'position_increment': 0.01
      },
      'ETH_Momentum': {
          'base_notional': 240000,
          'base_margin': 24000,
          'margin_per_contract': 8000,
          'typical_contracts': 3,
          'min_position': 0.01,
          'position_increment': 0.01
      },
      'BTC_ETH_Spread': {
          'base_notional': 300000,
          'base_margin': 30000,
          'margin_per_contract': 10000,
          'typical_contracts': 3,
          'min_position': 0.01,
          'position_increment': 0.01
      },
      'SOL_Breakout': {
          'base_notional': 150000,
          'base_margin': 15000,
          'margin_per_contract': 3000,
          'typical_contracts': 5,
          'min_position': 0.1,
          'position_increment': 0.1
      },
      'Altcoin_Basket': {
          'base_notional': 250000,
          'base_margin': 25000,
          'margin_per_contract': 5000,
          'typical_contracts': 5,
          'min_position': 0.1,
          'position_increment': 0.1
      },
      'Funding_Rate_Arb': {
          'base_notional': 360000,
          'base_margin': 36000,
          'margin_per_contract': 12000,
          'typical_contracts': 3,
          'min_position': 0.01,
          'position_increment': 0.01
      },
      'Crypto_MeanReversion': {
          'base_notional': 300000,
          'base_margin': 30000,
          'margin_per_contract': 6000,
          'typical_contracts': 5,
          'min_position': 0.1,
          'position_increment': 0.1
      }
    }

    # Use custom params if provided, otherwise look up in strategy_params
    if custom_params:
        params = custom_params
        print(f"Ingesting data for '{strategy_name}' with custom parameters...")
        print(f"  - Typical Position: {params['typical_contracts']} contracts")
        print(f"  - Base Notional: ${params['base_notional']:,.0f}")
        print(f"  - Base Margin: ${params['base_margin']:,.0f}")
    elif strategy_name in strategy_params:
        params = strategy_params[strategy_name]
        print(f"Ingesting data for '{strategy_name}' using default parameters...")
    else:
        print(f"Error: Strategy '{strategy_name}' not found in strategy_params and no custom_params provided.")
        print(f"Available strategies: {', '.join(strategy_params.keys())}")
        print(f"\nAlternatively, provide custom_params dict with keys: base_notional, base_margin, margin_per_contract, typical_contracts")
        return

    # --- Read Input CSV ---
    try:
        df = pd.read_csv(input_csv_path)

        # Validate columns
        if 'Date' not in df.columns or 'Daily Returns (%)' not in df.columns:
            print(f"Error: CSV must contain 'Date' and 'Daily Returns (%)' columns.")
            print(f"Found columns: {', '.join(df.columns)}")
            return

        df['Date'] = pd.to_datetime(df['Date'])

        # Handle different formats for Daily Returns (%)
        # Could be: "0.5%", 0.005, or 0.5
        if df['Daily Returns (%)'].dtype == 'object':
            # String format like "0.5%"
            df['Daily Returns (%)'] = df['Daily Returns (%)'].str.rstrip('%').astype('float') / 100
        elif df['Daily Returns (%)'].abs().max() > 1:
            # Percentage format like 0.5 (meaning 0.5%)
            df['Daily Returns (%)'] = df['Daily Returns (%)'] / 100
        # Otherwise assume it's already in decimal format (0.005)

    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # --- Reconstruct Missing Columns ---
    records = []
    equity_curve = [starting_capital]

    # Use typical position for estimation
    typical_position = params['typical_contracts']
    notional_per_unit = params['base_notional'] / params['typical_contracts']
    margin_per_unit = params['margin_per_contract']

    for idx, row in df.iterrows():
        # Get previous day's equity
        previous_day_equity = equity_curve[-1]

        # Calculate daily P&L from returns
        daily_return_pct = row['Daily Returns (%)']
        daily_pnl = previous_day_equity * daily_return_pct

        # Update equity curve
        new_equity = previous_day_equity + daily_pnl
        equity_curve.append(new_equity)

        # Estimate notional value using typical position
        # (Note: This is an estimate - real data had random variations)
        notional = typical_position * notional_per_unit

        # Calculate return on notional
        return_on_notional = (daily_pnl / notional) if notional != 0 else 0

        # Estimate margin using typical position
        margin = typical_position * margin_per_unit

        # Build record
        records.append({
            'Date': row['Date'].strftime('%Y-%m-%d'),
            'Daily P&L ($)': daily_pnl,
            'Daily Returns (%)': daily_return_pct,
            'Daily Return on Notional (%)': return_on_notional,
            'Maximum Daily Notional Value': notional,
            'Maximum Daily Margin Utilization ($)': margin
        })

    # --- Create Output DataFrame ---
    output_df = pd.DataFrame(records)

    # Format the numbers for readability (matching sample_strategy_data_maker.py format)
    output_df['Daily P&L ($)'] = output_df['Daily P&L ($)'].map('{:.2f}'.format)
    output_df['Daily Returns (%)'] = output_df['Daily Returns (%)'].map('{:.4%}'.format)
    output_df['Daily Return on Notional (%)'] = output_df['Daily Return on Notional (%)'].map('{:.4%}'.format)
    output_df['Maximum Daily Notional Value'] = output_df['Maximum Daily Notional Value'].map('{:.0f}'.format)
    output_df['Maximum Daily Margin Utilization ($)'] = output_df['Maximum Daily Margin Utilization ($)'].map('{:.0f}'.format)

    # --- Save to CSV ---
    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, f"{strategy_name}.csv")
    output_df.to_csv(output_path, index=False)

    print(f"Successfully created '{output_path}' with {len(records)} records.")
    print(f"Equity grew from ${starting_capital:,.0f} to ${equity_curve[-1]:,.0f}")

    total_return = ((equity_curve[-1] / starting_capital) - 1) * 100
    print(f"Total Return: {total_return:.2f}%")

    return output_path


# ==============================================================================
# --- EXAMPLE USAGE ---
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("INGEST NEW STRATEGY DATA")
    print("=" * 80)
    print("\nThis script converts a CSV with Date + Daily Returns (%) into the full format")
    print("required by portfolio_combiner.py")

    print("\n" + "=" * 80)
    print("OPTION 1: Use predefined strategy parameters")
    print("=" * 80)
    print("""
ingest_strategy_data(
    input_csv_path='my_strategy_returns.csv',
    strategy_name='SPX_Condors',
    output_folder='strategy_performance_data',
    starting_capital=1_000_000
)
""")

    print("Available predefined strategies:")
    strategies = ['SPX_Condors', 'SPX_Butterflies', 'NDX_IronCondors', 'RUT_CreditSpreads',
                  'Equity_LongShort', 'TLT_Covered_Calls', 'VIX_Calendar', 'Forex_Trend',
                  'Gold_Breakout', 'Crude_Momentum', 'ES_Scalping', 'NQ_Trend',
                  'ZN_MeanReversion', 'GC_Breakout', 'BTC_Trend', 'ETH_Momentum',
                  'BTC_ETH_Spread', 'SOL_Breakout', 'Altcoin_Basket', 'Funding_Rate_Arb',
                  'Crypto_MeanReversion']
    for i, strat in enumerate(strategies, 1):
        print(f"  {i:2d}. {strat}")

    print("\n" + "=" * 80)
    print("OPTION 2: Use custom parameters for new strategy")
    print("=" * 80)
    print("""
custom_params = {
    'base_notional': 5500000,        # Total notional value at typical position
    'base_margin': 50000,            # Total margin required at typical position
    'margin_per_contract': 5000,     # Margin per contract/unit
    'typical_contracts': 10,         # Typical position size
    'min_position': 1,               # Minimum position (optional)
    'position_increment': 1          # Position increment (optional)
}

ingest_strategy_data(
    input_csv_path='my_new_strategy.csv',
    strategy_name='MyNewStrategy',
    output_folder='strategy_performance_data',
    starting_capital=1_000_000,
    custom_params=custom_params
)
""")

    print("\n" + "=" * 80)
    print("INPUT CSV FORMAT")
    print("=" * 80)
    print("\nYour CSV must have these columns: Date, Daily Returns (%)")
    print("\nAccepted formats for Daily Returns (%):")
    print("  1. Percentage string:  '0.5%', '-0.3%', '1.2%'")
    print("  2. Percentage decimal: 0.5, -0.3, 1.2  (will be divided by 100)")
    print("  3. Decimal format:     0.005, -0.003, 0.012")

    print("\nExample CSV:")
    print("-" * 40)
    print("Date,Daily Returns (%)")
    print("2020-01-01,0.5%")
    print("2020-01-02,-0.3%")
    print("2020-01-03,0.8%")
    print("-" * 40)

    print("\n" + "=" * 80)
