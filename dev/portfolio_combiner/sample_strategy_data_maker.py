"""
Sample Strategy Data Maker V2
Generates or ingests strategy performance data with smart partial data handling.

Key Features:
1. Single CONFIG dict for all settings
2. Ingests real CSVs from input folder (supports partial data)
3. Generates synthetic data for remaining strategies needed
4. Developers provide: Date, Daily Returns (%), Notional, Margin
5. We calculate: Daily P&L ($) and Return on Notional (%)
"""

import pandas as pd
import os
import random
import math
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# ==============================================================================
# --- CONFIGURATION (Single Source of Truth) ---
# ==============================================================================

# Generate timestamped output folders
EPOCH = int(time.time())
OUTPUT_BASE = f'outputs/run_{EPOCH}'

CONFIG = {
    # How many synthetic strategies to add (in addition to real data)?
    'num_synthetic_strategies': 2,  # Will add 2 random strategies from the bank

    # Where to find real strategy data from developers
    'input_folder': 'real_strategy_data',

    # Where to save final processed data (inside timestamped outputs)
    'output_folder': f'{OUTPUT_BASE}/strategy_performance_data',

    # Where to save equity curve graphs (inside timestamped outputs)
    'graphs_folder': f'{OUTPUT_BASE}/strategy_performance_data_graphs',

    # Strategy bank: templates for generating synthetic data
    'strategy_bank': {
        # IBKR Main strategies
        'SPX_Condors': {
            'account': 'IBKR Main',
            'days': 3650,
            'mean_return': 0.00006,
            'volatility': 0.0011,
            'fat_tail_prob': 0.03,
            'fat_tail_mult': 2.2,
            'base_notional': 5500000,
            'base_margin': 50000
        },
        'SPX_Butterflies': {
            'account': 'IBKR Main',
            'days': 3200,
            'mean_return': 0.000062,
            'volatility': 0.0009,
            'fat_tail_prob': 0.025,
            'fat_tail_mult': 2.0,
            'base_notional': 3300000,
            'base_margin': 30000
        },
        'NDX_IronCondors': {
            'account': 'IBKR Main',
            'days': 2800,
            'mean_return': 0.000075,
            'volatility': 0.0013,
            'fat_tail_prob': 0.035,
            'fat_tail_mult': 2.3,
            'base_notional': 7200000,
            'base_margin': 65000
        },
        'RUT_CreditSpreads': {
            'account': 'IBKR Main',
            'days': 3100,
            'mean_return': 0.000070,
            'volatility': 0.0012,
            'fat_tail_prob': 0.03,
            'fat_tail_mult': 2.1,
            'base_notional': 4400000,
            'base_margin': 44000
        },
        'Equity_LongShort': {
            'account': 'IBKR Main',
            'days': 2600,
            'mean_return': 0.00040,
            'volatility': 0.0050,
            'fat_tail_prob': 0.028,
            'fat_tail_mult': 1.9,
            'base_notional': 2000000,
            'base_margin': 1000000
        },
        'TLT_Covered_Calls': {
            'account': 'IBKR Main',
            'days': 3400,
            'mean_return': 0.00032,
            'volatility': 0.0040,
            'fat_tail_prob': 0.02,
            'fat_tail_mult': 1.8,
            'base_notional': 1800000,
            'base_margin': 900000
        },
        'VIX_Calendar': {
            'account': 'IBKR Main',
            'days': 2900,
            'mean_return': 0.00011,
            'volatility': 0.0016,
            'fat_tail_prob': 0.04,
            'fat_tail_mult': 2.5,
            'base_notional': 3800000,
            'base_margin': 38000
        },

        # Futures strategies
        'Forex_Trend': {
            'account': 'Futures Account',
            'days': 3650,
            'mean_return': 0.00042,
            'volatility': 0.0020,
            'fat_tail_prob': 0.03,
            'fat_tail_mult': 2.0,
            'base_notional': 200000,
            'base_margin': 20000
        },
        'Gold_Breakout': {
            'account': 'Futures Account',
            'days': 3650,
            'mean_return': 0.00027,
            'volatility': 0.0018,
            'fat_tail_prob': 0.025,
            'fat_tail_mult': 1.9,
            'base_notional': 820000,
            'base_margin': 82000
        },
        'Crude_Momentum': {
            'account': 'Futures Account',
            'days': 3300,
            'mean_return': 0.00038,
            'volatility': 0.0022,
            'fat_tail_prob': 0.035,
            'fat_tail_mult': 2.1,
            'base_notional': 600000,
            'base_margin': 60000
        },
        'ES_Scalping': {
            'account': 'Futures Account',
            'days': 2400,
            'mean_return': 0.00055,
            'volatility': 0.0028,
            'fat_tail_prob': 0.04,
            'fat_tail_mult': 2.3,
            'base_notional': 1250000,
            'base_margin': 125000
        },
        'NQ_Trend': {
            'account': 'Futures Account',
            'days': 2700,
            'mean_return': 0.00038,
            'volatility': 0.0032,
            'fat_tail_prob': 0.045,
            'fat_tail_mult': 2.4,
            'base_notional': 1800000,
            'base_margin': 180000
        },
        'ZN_MeanReversion': {
            'account': 'Futures Account',
            'days': 3000,
            'mean_return': 0.00020,
            'volatility': 0.0012,
            'fat_tail_prob': 0.02,
            'fat_tail_mult': 1.7,
            'base_notional': 220000,
            'base_margin': 22000
        },
        'GC_Breakout': {
            'account': 'Futures Account',
            'days': 3100,
            'mean_return': 0.00028,
            'volatility': 0.0019,
            'fat_tail_prob': 0.03,
            'fat_tail_mult': 2.0,
            'base_notional': 720000,
            'base_margin': 72000
        },

        # Crypto strategies
        'BTC_Trend': {
            'account': 'Crypto Account',
            'days': 2800,
            'mean_return': 0.00065,
            'volatility': 0.035,
            'fat_tail_prob': 0.05,
            'fat_tail_mult': 2.5,
            'base_notional': 450000,
            'base_margin': 45000
        },
        'ETH_Momentum': {
            'account': 'Crypto Account',
            'days': 2600,
            'mean_return': 0.00072,
            'volatility': 0.038,
            'fat_tail_prob': 0.055,
            'fat_tail_mult': 2.6,
            'base_notional': 240000,
            'base_margin': 24000
        },
        'BTC_ETH_Spread': {
            'account': 'Crypto Account',
            'days': 2400,
            'mean_return': 0.00025,
            'volatility': 0.0150,
            'fat_tail_prob': 0.03,
            'fat_tail_mult': 1.8,
            'base_notional': 300000,
            'base_margin': 30000
        },
        'SOL_Breakout': {
            'account': 'Crypto Account',
            'days': 1800,
            'mean_return': 0.00085,
            'volatility': 0.055,
            'fat_tail_prob': 0.07,
            'fat_tail_mult': 3.0,
            'base_notional': 150000,
            'base_margin': 15000
        },
        'Altcoin_Basket': {
            'account': 'Crypto Account',
            'days': 2000,
            'mean_return': 0.00095,
            'volatility': 0.048,
            'fat_tail_prob': 0.06,
            'fat_tail_mult': 2.8,
            'base_notional': 250000,
            'base_margin': 25000
        },
        'Funding_Rate_Arb': {
            'account': 'Crypto Account',
            'days': 2200,
            'mean_return': 0.00042,
            'volatility': 0.0015,
            'fat_tail_prob': 0.02,
            'fat_tail_mult': 1.8,
            'base_notional': 360000,
            'base_margin': 36000
        },
        'Crypto_MeanReversion': {
            'account': 'Crypto Account',
            'days': 2400,
            'mean_return': 0.00090,
            'volatility': 0.0030,
            'fat_tail_prob': 0.04,
            'fat_tail_mult': 2.2,
            'base_notional': 300000,
            'base_margin': 30000
        }
    }
}


# ==============================================================================
# --- SMART CSV INGESTION (Handle Partial Data) ---
# ==============================================================================

def ingest_real_strategy_csv(filepath, starting_capital=1_000_000, typical_leverage=20):
    """
    Intelligently reads a CSV from developers and fills missing columns.
    The fix applied here makes margin/notional compound with equity AND dynamically
    adjusts based on daily return magnitude when they are missing.

    Args:
        filepath: Path to CSV file
        starting_capital: Starting account equity for calculations (e.g., if it's a new account)
        typical_leverage: Typical leverage ratio (notional / margin) for this instrument type
                         Default 20x (conservative for futures/commodities)

    Supports 3 formats:
    1. Just Daily Returns (%) - we estimate notional/margin dynamically based on compounding equity
                                and daily return magnitude.
    2. Returns + Notional + Margin - we calculate P&L.
    3. Full data - use as-is.
    """
    strategy_name = os.path.basename(filepath).replace('.csv', '')
    print(f"Ingesting '{strategy_name}' from {filepath}...")

    df = pd.read_csv(filepath)
    df['Date'] = pd.to_datetime(df['Date'])

    # IMPORTANT: Sort by date ascending to ensure equity curve is calculated correctly
    df = df.sort_values('Date').reset_index(drop=True)

    # Detect what columns we have
    has_returns = 'Daily Returns (%)' in df.columns
    has_notional = 'Maximum Daily Notional Value' in df.columns
    has_margin = 'Maximum Daily Margin Utilization ($)' in df.columns

    if not has_returns:
        print(f"  ERROR: '{strategy_name}' missing 'Daily Returns (%)' column. Skipping.")
        return None

    # Parse returns to decimal
    if df['Daily Returns (%)'].dtype == 'object':
        df['Daily Returns (%)'] = df['Daily Returns (%)'].str.rstrip('%').astype('float') / 100
    elif df['Daily Returns (%)'].abs().max() > 1:
        df['Daily Returns (%)'] = df['Daily Returns (%)'] / 100

    # Calculate equity curve first
    equity_curve = [starting_capital]
    for ret in df['Daily Returns (%)']:
        equity_curve.append(equity_curve[-1] * (1 + ret))
    
    df['Calculated Equity'] = equity_curve[1:]

    # Calculate Daily P&L ($) based on this equity curve
    df['Daily P&L ($)'] = df['Calculated Equity'] - pd.Series(equity_curve[:-1]).reset_index(drop=True)


    # Handle missing notional/margin with compounding and activity-based logic
    if not has_notional or not has_margin:
        print(f"  WARNING: Missing notional/margin data. Using intelligent estimates based on compounding equity AND daily activity.")

        # Define a base target margin utilization percentage (e.g., 5% of daily equity)
        base_target_margin_util_pct = 0.05
        
        # Calculate an activity factor based on absolute daily returns
        # Normalize returns to get a factor between (e.g.) 0.1 and 1.5
        abs_returns = df['Daily Returns (%)'].abs()
        
        # We want to scale margin based on the relative magnitude of returns.
        # Use a percentile to define "average" or "high" activity
        q95_abs_returns = abs_returns.quantile(0.95) if abs_returns.max() > 0 else 0.0001 # Avoid division by zero
        
        # Create a factor that increases with returns, capped at a reasonable level
        # A simple linear scaling: 0 return -> low factor, max return -> high factor
        # This makes margin factor relative to the strategy's typical return magnitude
        if q95_abs_returns > 0:
            margin_activity_factor = (abs_returns / q95_abs_returns).clip(upper=2.0) + 0.5
            # Shift and scale: e.g., if abs_returns is 0, factor is 0.5. If at q95, factor is 1.5. If higher, up to 2.5.
            # You can tune the +0.5 and upper=2.0 to control the min/max variance.
        else:
            margin_activity_factor = 0.5 # Default low activity if no returns

        # Apply the activity factor to the base margin percentage
        dynamic_target_margin_util_pct = base_target_margin_util_pct * margin_activity_factor

        if not has_margin:
            df['Maximum Daily Margin Utilization ($)'] = df['Calculated Equity'] * dynamic_target_margin_util_pct

        if not has_notional:
            df['Maximum Daily Notional Value'] = df['Maximum Daily Margin Utilization ($)'] * typical_leverage
            print(f"  Using {typical_leverage}x leverage ratio for notional estimates")
            
    else:
        # If notional and margin *are* provided in the CSV, ensure they are float types
        df['Maximum Daily Notional Value'] = df['Maximum Daily Notional Value'].str.replace(',', '').astype(float) if df['Maximum Daily Notional Value'].dtype == 'object' else df['Maximum Daily Notional Value'].astype(float)
        df['Maximum Daily Margin Utilization ($)'] = df['Maximum Daily Margin Utilization ($)'].str.replace(',', '').astype(float) if df['Maximum Daily Margin Utilization ($)'].dtype == 'object' else df['Maximum Daily Margin Utilization ($)'].astype(float)


    # Calculate Return on Notional
    df['Daily Return on Notional (%)'] = df.apply(
        lambda row: row['Daily P&L ($)'] / row['Maximum Daily Notional Value'] if row['Maximum Daily Notional Value'] > 0 else 0,
        axis=1
    )

    # Reorder columns and drop the intermediate 'Calculated Equity'
    df = df[['Date', 'Daily P&L ($)', 'Daily Returns (%)', 'Daily Return on Notional (%)',
             'Maximum Daily Notional Value', 'Maximum Daily Margin Utilization ($)']]

    print(f"  ✓ Ingested {len(df)} days of data")
    return strategy_name, df

# ==============================================================================
# --- SYNTHETIC DATA GENERATION ---
# ==============================================================================

def generate_synthetic_strategy(strategy_name, params, starting_capital=1_000_000):
    """
    Generates synthetic strategy data based on parameters.
    Outputs: Date, Daily Returns (%), Notional, Margin
    The fix applied here dynamically calculates Notional and Margin based on current equity.
    """
    print(f"Generating synthetic data for '{strategy_name}' with dynamic margin/notional...")

    records = []
    current_date = datetime.now() - timedelta(days=params['days'])
    
    # Initialize equity curve with starting capital
    current_equity = starting_capital 

    # Define target utilization and leverage for synthetic data
    # These can be made configurable in CONFIG if needed
    target_margin_util_pct = 0.05 # e.g., target 5% of current equity for margin
    target_leverage = 10 # e.g., target 10x leverage (notional / margin)

    for i in range(params['days']):
        # Generate return using Box-Muller transform with capped values
        u1, u2 = random.random(), random.random()
        u1 = max(0.0001, min(0.9999, u1))
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        z = max(-3.5, min(3.5, z))

        effective_vol = params['volatility'] * params['fat_tail_mult'] if random.random() < params['fat_tail_prob'] else params['volatility']
        daily_return = params['mean_return'] + effective_vol * z

        # Serial correlation (momentum) - reduced effect
        if i > 0 and random.random() < 0.15:
            # We need to get the previous day's return for serial correlation
            # Ensure 'Daily Returns (%)' is stored as a float before this step
            prev_daily_return = records[-1]['Daily Returns (%)']
            daily_return += 0.2 * prev_daily_return

        daily_return = max(-0.20, min(0.20, daily_return))

        # Calculate P&L and update current equity
        pnl = current_equity * daily_return
        current_equity += pnl # This is the current equity for the *next* day's calculation

        # Ensure equity doesn't drop below zero in synthetic generation
        if current_equity <= 0:
            current_equity = 0.01 # Prevent division by zero or negative equity
            daily_return = -1.0 # Reflect a total loss for the day

        # Dynamically calculate Notional and Margin based on current_equity
        # Here's where the fix is applied:
        margin_used = current_equity * target_margin_util_pct
        notional_value = margin_used * target_leverage
        
        # Add some random variation to notional/margin for realism,
        # but keep it tied to the dynamic base.
        notional_value *= (1 + (random.random() - 0.5) * 0.1) # +/- 5% variation
        margin_used *= (1 + (random.random() - 0.5) * 0.1) # +/- 5% variation

        # Ensure notional/margin are not negative
        notional_value = max(0, notional_value)
        margin_used = max(0, margin_used)


        records.append({
            'Date': current_date.strftime('%Y-%m-%d'),
            'Daily P&L ($)': pnl,
            'Daily Returns (%)': daily_return,
            'Daily Return on Notional (%)': pnl / notional_value if notional_value > 0 else 0,
            'Maximum Daily Notional Value': notional_value,
            'Maximum Daily Margin Utilization ($)': margin_used
        })
        current_date += timedelta(days=1)

    df = pd.DataFrame(records)
    print(f"  ✓ Generated {len(df)} days of data")
    return strategy_name, df

# ==============================================================================
# --- MAIN ORCHESTRATION ---
# ==============================================================================

def main():
    print("="*80)
    print("SAMPLE STRATEGY DATA MAKER V2")
    print("="*80)
    print(f"Adding {CONFIG['num_synthetic_strategies']} synthetic strategies to real data")
    print(f"Output: {CONFIG['output_folder']}/")

    os.makedirs(CONFIG['output_folder'], exist_ok=True)

    strategies_created = []

    # Step 1: Ingest ALL real data from input folder
    if CONFIG['input_folder'] and os.path.exists(CONFIG['input_folder']):
        print(f"\n--- Step 1: Ingesting Real Data from '{CONFIG['input_folder']}' ---")
        csv_files = [f for f in os.listdir(CONFIG['input_folder']) if f.endswith('.csv')]

        if not csv_files:
            print("  No CSV files found in input folder")

        for csv_file in csv_files:
            filepath = os.path.join(CONFIG['input_folder'], csv_file)
            result = ingest_real_strategy_csv(filepath)

            if result:
                strategy_name, df = result
                output_path = os.path.join(CONFIG['output_folder'], f'{strategy_name}.csv')

                # Format and save
                df['Daily P&L ($)'] = df['Daily P&L ($)'].map('{:.2f}'.format)
                df['Daily Returns (%)'] = df['Daily Returns (%)'].map('{:.4%}'.format)
                df['Daily Return on Notional (%)'] = df['Daily Return on Notional (%)'].map('{:.4%}'.format)
                df['Maximum Daily Notional Value'] = df['Maximum Daily Notional Value'].map('{:.0f}'.format)
                df['Maximum Daily Margin Utilization ($)'] = df['Maximum Daily Margin Utilization ($)'].map('{:.0f}'.format)

                df.to_csv(output_path, index=False)
                strategies_created.append(strategy_name)
                print(f"  → Saved to {output_path}")

    # Step 2: Generate N random synthetic strategies
    if CONFIG['num_synthetic_strategies'] > 0:
        print(f"\n--- Step 2: Generating {CONFIG['num_synthetic_strategies']} Random Synthetic Strategies ---")

        # Get available strategies (excluding already created ones)
        available_strategies = [name for name in CONFIG['strategy_bank'].keys()
                               if name not in strategies_created]

        # Randomly select N strategies
        import random
        selected_strategies = random.sample(available_strategies,
                                           min(CONFIG['num_synthetic_strategies'], len(available_strategies)))

        for strategy_name in selected_strategies:
            params = CONFIG['strategy_bank'][strategy_name]
            strategy_name, df = generate_synthetic_strategy(strategy_name, params)
            output_path = os.path.join(CONFIG['output_folder'], f'{strategy_name}.csv')

            # Format and save
            df['Daily P&L ($)'] = df['Daily P&L ($)'].map('{:.2f}'.format)
            df['Daily Returns (%)'] = df['Daily Returns (%)'].map('{:.4%}'.format)
            df['Daily Return on Notional (%)'] = df['Daily Return on Notional (%)'].map('{:.4%}'.format)
            df['Maximum Daily Notional Value'] = df['Maximum Daily Notional Value'].map('{:.0f}'.format)
            df['Maximum Daily Margin Utilization ($)'] = df['Maximum Daily Margin Utilization ($)'].map('{:.0f}'.format)

            df.to_csv(output_path, index=False)
            strategies_created.append(strategy_name)
            print(f"  → Saved to {output_path}")

    # Step 3: Generate preview graphs for all strategies
    print(f"\n--- Step 3: Generating Preview Graphs ---")
    os.makedirs(CONFIG['graphs_folder'], exist_ok=True)

    for strategy_name in strategies_created:
        csv_path = os.path.join(CONFIG['output_folder'], f'{strategy_name}.csv')
        df = pd.read_csv(csv_path)
        df['Date'] = pd.to_datetime(df['Date'])

        # IMPORTANT: Sort by date ascending to ensure calculations are correct
        df = df.sort_values('Date').reset_index(drop=True)

        # --- Robust Parsing of Numerical Columns ---
        # The issue is that these columns are saved as formatted strings,
        # but pd.read_csv might infer them as numeric (int/float) if they don't contain commas.
        # We need to ensure they are treated as strings before .str methods, then convert to float.

        # Parse 'Daily Returns (%)'
        # Handle cases where it might already be float or still a string like "0.0123%"
        if df['Daily Returns (%)'].dtype == 'object': # It's a string, likely with '%'
            df['Daily Returns (%)'] = df['Daily Returns (%)'].str.rstrip('%').astype(float) / 100
        elif df['Daily Returns (%)'].abs().max() > 1: # It's a number, but perhaps as a percentage (e.g., 5 for 5%)
            df['Daily Returns (%)'] = df['Daily Returns (%)'] / 100

        # Parse 'Maximum Daily Notional Value'
        # Ensure it's a string first to use .str.replace, then convert to float
        if df['Maximum Daily Notional Value'].dtype == 'object':
            df['Maximum Daily Notional Value'] = df['Maximum Daily Notional Value'].str.replace(',', '').astype(float)
        else: # Already numeric, no .str.replace needed
            df['Maximum Daily Notional Value'] = df['Maximum Daily Notional Value'].astype(float)

        # Parse 'Maximum Daily Margin Utilization ($)'
        # Ensure it's a string first to use .str.replace, then convert to float
        if df['Maximum Daily Margin Utilization ($)'].dtype == 'object':
            df['Maximum Daily Margin Utilization ($)'] = df['Maximum Daily Margin Utilization ($)'].str.replace(',', '').astype(float)
        else: # Already numeric, no .str.replace needed
            df['Maximum Daily Margin Utilization ($)'] = df['Maximum Daily Margin Utilization ($)'].astype(float)
        # --- End Robust Parsing ---


        # Calculate equity curve
        # Initial equity for graph display. Can be made configurable if needed.
        initial_graph_equity = 1_000_000
        equity = [initial_graph_equity]
        for ret in df['Daily Returns (%)']:
            equity.append(equity[-1] * (1 + ret))
        df['Equity'] = equity[1:] # Assign the calculated equity to the DataFrame

        # Calculate Margin Utilization Percentage
        # Handle division by zero if equity is zero
        df['Margin Utilization (%)'] = (df['Maximum Daily Margin Utilization ($)'] / df['Equity']) * 100
        df['Margin Utilization (%)'] = df['Margin Utilization (%)'].fillna(0).replace([float('inf'), -float('inf')], 0)
        # Cap at a reasonable max for display, e.g., 100%
        df['Margin Utilization (%)'] = df['Margin Utilization (%)'].clip(upper=100)


        # Create a figure with two subplots, sharing the x-axis
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=True, gridspec_kw={'height_ratios': [3, 1]})

        # --- Top Subplot: Equity Curve ---
        ax1.plot(df['Date'], df['Equity'], linewidth=2, color='tab:blue')
        ax1.set_ylabel('Equity ($)', fontsize=12)
        ax1.set_title(f'{strategy_name} - Equity & Margin Usage', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.ticklabel_format(style='plain', axis='y') # Prevent scientific notation on y-axis

        # --- Bottom Subplot: Margin Usage ---
        # Primary Y-axis: Margin Utilization (%)
        ax2.plot(df['Date'], df['Margin Utilization (%)'], linewidth=1.5, color='tab:red', label='Margin Utilization (%)')
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Margin Util. (%)', fontsize=12, color='tab:red')
        ax2.tick_params(axis='y', labelcolor='tab:red')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, df['Margin Utilization (%)'].max() * 1.1 if df['Margin Utilization (%)'].max() > 0 else 10) # Dynamic Y-limit
        
        # Secondary Y-axis: Margin Usage ($) in millions
        ax2_twin = ax2.twinx()
        ax2_twin.plot(df['Date'], df['Maximum Daily Margin Utilization ($)'] / 1_000_000, linewidth=1.5, color='tab:green', linestyle='--', label='Margin Usage ($M)')
        ax2_twin.set_ylabel('Margin Usage ($M)', fontsize=12, color='tab:green')
        ax2_twin.tick_params(axis='y', labelcolor='tab:green')
        ax2_twin.ticklabel_format(style='plain', axis='y') # Prevent scientific notation on y-axis


        # Combine legends for the bottom subplot
        lines, labels = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2_twin.legend(lines + lines2, labels + labels2, loc='upper left', fontsize=10)


        # Format x-axis dates
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        fig.tight_layout() # Adjust layout to prevent overlapping
        
        graph_path = os.path.join(CONFIG['graphs_folder'], f'{strategy_name}_equity_and_margin_curve.png')
        plt.savefig(graph_path, dpi=150)
        plt.close()
        print(f"  ✓ {strategy_name}")

    # Save EPOCH to file for portfolio_combiner.py to read
    epoch_file = os.path.join(OUTPUT_BASE, '.epoch')
    with open(epoch_file, 'w') as f:
        f.write(str(EPOCH))

    print(f"\n{'='*80}")
    print(f"COMPLETE: Created {len(strategies_created)} strategies")
    print(f"  - Real strategies: {len([s for s in strategies_created if s != 'synthetic'])}")
    print(f"  - Synthetic strategies: {CONFIG['num_synthetic_strategies']}")
    print(f"Output folder: {CONFIG['output_folder']}/")
    print(f"Run ID: {EPOCH}")
    print(f"{'='*80}")
    print(f"\nNext step: Run portfolio_combiner.py to analyze this data")


if __name__ == "__main__":
    main()
