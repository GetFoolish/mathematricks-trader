import pandas as pd
import os
import random
import math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def generate_strategy_file(strategy_name, save_path):
    """
    Generates a CSV file with realistic-looking, randomized historical data for a given strategy.

    Args:
        strategy_name (str): The name of the strategy to generate data for.
        save_path (str): The folder path where the CSV will be saved.
    """
    # --- Strategy Parameter Configuration ---
    # Define the unique characteristics of each strategy here.
    strategy_params = {
      # ===== IBKR Main Account Strategies (7) =====
      'SPX_Condors': {
          'days': 3650,
          'mean_return': 0.00035,
          'volatility': 0.011,
          'fat_tail_prob': 0.03,
          'fat_tail_mult': 2.2,
          'base_notional': 5500000,
          'base_margin': 50000,
          'margin_per_contract': 5000,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 10
      },
      'SPX_Butterflies': {
          'days': 3200,
          'mean_return': 0.00028,
          'volatility': 0.009,
          'fat_tail_prob': 0.025,
          'fat_tail_mult': 2.0,
          'base_notional': 3300000,
          'base_margin': 30000,
          'margin_per_contract': 3000,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 10
      },
      'NDX_IronCondors': {
          'days': 2800,
          'mean_return': 0.00042,
          'volatility': 0.013,
          'fat_tail_prob': 0.035,
          'fat_tail_mult': 2.3,
          'base_notional': 7200000,
          'base_margin': 65000,
          'margin_per_contract': 6500,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 10
      },
      'RUT_CreditSpreads': {
          'days': 3100,
          'mean_return': 0.00038,
          'volatility': 0.012,
          'fat_tail_prob': 0.03,
          'fat_tail_mult': 2.1,
          'base_notional': 4400000,
          'base_margin': 44000,
          'margin_per_contract': 4400,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 10
      },
      'Equity_LongShort': {
          'days': 2600,
          'mean_return': 0.00032,
          'volatility': 0.010,
          'fat_tail_prob': 0.028,
          'fat_tail_mult': 1.9,
          'base_notional': 2000000,
          'base_margin': 1000000,
          'margin_per_contract': 100000,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 10
      },
      'TLT_Covered_Calls': {
          'days': 3400,
          'mean_return': 0.00025,
          'volatility': 0.008,
          'fat_tail_prob': 0.02,
          'fat_tail_mult': 1.8,
          'base_notional': 1800000,
          'base_margin': 900000,
          'margin_per_contract': 90000,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 10
      },
      'VIX_Calendar': {
          'days': 2900,
          'mean_return': 0.00045,
          'volatility': 0.016,
          'fat_tail_prob': 0.04,
          'fat_tail_mult': 2.5,
          'base_notional': 3800000,
          'base_margin': 38000,
          'margin_per_contract': 3800,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 10
      },

      # ===== Futures Account Strategies (7) =====
      'Forex_Trend': {
          'days': 3650,
          'mean_return': 0.00045,
          'volatility': 0.016,
          'fat_tail_prob': 0.04,
          'fat_tail_mult': 2.1,
          'base_notional': 850000,
          'base_margin': 17000,
          'margin_per_contract': 2000,
          'min_position': 0.01,
          'position_increment': 0.1,
          'typical_contracts': 8.5
      },
      'Gold_Breakout': {
          'days': 3650,
          'mean_return': 0.00040,
          'volatility': 0.016,
          'fat_tail_prob': 0.03,
          'fat_tail_mult': 2.0,
          'base_notional': 425000,
          'base_margin': 41000,
          'margin_per_contract': 8200,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 5
      },
      'Crude_Momentum': {
          'days': 3300,
          'mean_return': 0.00048,
          'volatility': 0.018,
          'fat_tail_prob': 0.045,
          'fat_tail_mult': 2.2,
          'base_notional': 600000,
          'base_margin': 30000,
          'margin_per_contract': 6000,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 5
      },
      'ES_Scalping': {
          'days': 2400,
          'mean_return': 0.00035,
          'volatility': 0.014,
          'fat_tail_prob': 0.035,
          'fat_tail_mult': 2.0,
          'base_notional': 1250000,
          'base_margin': 62500,
          'margin_per_contract': 12500,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 5
      },
      'NQ_Trend': {
          'days': 2700,
          'mean_return': 0.00052,
          'volatility': 0.019,
          'fat_tail_prob': 0.04,
          'fat_tail_mult': 2.3,
          'base_notional': 1800000,
          'base_margin': 90000,
          'margin_per_contract': 18000,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 5
      },
      'ZN_MeanReversion': {
          'days': 3000,
          'mean_return': 0.00030,
          'volatility': 0.011,
          'fat_tail_prob': 0.025,
          'fat_tail_mult': 1.8,
          'base_notional': 550000,
          'base_margin': 11000,
          'margin_per_contract': 2200,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 5
      },
      'GC_Breakout': {
          'days': 3100,
          'mean_return': 0.00043,
          'volatility': 0.017,
          'fat_tail_prob': 0.038,
          'fat_tail_mult': 2.1,
          'base_notional': 720000,
          'base_margin': 36000,
          'margin_per_contract': 7200,
          'min_position': 1,
          'position_increment': 1,
          'typical_contracts': 5
      }
  }

    if strategy_name not in strategy_params:
        print(f"Error: Parameters for '{strategy_name}' not found. Cannot generate data.")
        return

    params = strategy_params[strategy_name]
    print(f"Generating data for '{strategy_name}'...")

    # --- Data Generation Loop ---
    records = []
    # Start date goes back based on strategy's history length
    current_date = datetime.now() - timedelta(days=params['days'])

    for i in range(params['days']):
        # Generate a random daily return based on a normal distribution (Box-Muller transform)
        u1, u2 = random.random(), random.random()
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        # Add fat tail effects - occasionally generate extreme moves
        if random.random() < params['fat_tail_prob']:
            # Fat tail event - amplify the move
            volatility = params['volatility'] * params['fat_tail_mult']
        else:
            volatility = params['volatility']

        daily_return = params['mean_return'] + volatility * z

        # Add some serial correlation for more realistic regime-like behavior
        if i > 0 and random.random() < 0.15:  # 15% chance of momentum continuation
            prev_return = records[-1]['Daily Returns (%)']
            daily_return += 0.3 * prev_return  # Slight momentum effect

        # Generate position size with some variation (±20% around typical contracts)
        # This simulates the strategy varying position size based on market conditions
        position_variation = 1 + (random.random() - 0.5) * 0.4  # 0.8 to 1.2
        raw_position = params['typical_contracts'] * position_variation

        # Round to valid position size based on increment
        actual_position = max(
            params['min_position'],
            round(raw_position / params['position_increment']) * params['position_increment']
        )

        # Calculate margin and notional based on actual position
        margin = actual_position * params['margin_per_contract']
        # Notional varies but should be correlated with position size
        notional_per_unit = params['base_notional'] / params['typical_contracts']
        notional = actual_position * notional_per_unit * (1 + (random.random() - 0.5) * 0.05)

        records.append({
            'Date': current_date.strftime('%Y-%m-%d'),
            'Daily Returns (%)': daily_return,
            'Maximum Daily Notional Value': notional,
            'Maximum Daily Margin Utilization ($)': margin
        })
        current_date += timedelta(days=1)

    # --- Create DataFrame and Save to CSV ---
    df = pd.DataFrame(records)
    
    # Format the numbers for better readability in the CSV
    df['Daily Returns (%)'] = df['Daily Returns (%)'].map('{:.4%}'.format)
    df['Maximum Daily Notional Value'] = df['Maximum Daily Notional Value'].map('{:.0f}'.format)
    df['Maximum Daily Margin Utilization ($)'] = df['Maximum Daily Margin Utilization ($)'].map('{:.0f}'.format)
    
    # Create the directory if it doesn't exist
    os.makedirs(save_path, exist_ok=True)
    
    filepath = os.path.join(save_path, f"{strategy_name}.csv")
    df.to_csv(filepath, index=False)

    print(f"Successfully created '{filepath}' with {len(records)} records.")

    # --- Generate Equity Curve Graph ---
    graph_folder = 'strategy_performance_data_graphs'
    os.makedirs(graph_folder, exist_ok=True)

    # Calculate equity curve (convert percentage strings back to floats)
    returns_numeric = [r['Daily Returns (%)'] for r in records]
    starting_capital = 1_000_000
    equity_curve = [starting_capital]

    for ret in returns_numeric:
        equity_curve.append(equity_curve[-1] * (1 + ret))

    # Create date array for plotting
    dates = [datetime.strptime(r['Date'], '%Y-%m-%d') for r in records]
    dates.insert(0, dates[0] - timedelta(days=1))  # Add starting point

    # Calculate total return and annualized return
    total_return = (equity_curve[-1] / equity_curve[0] - 1) * 100
    years = params['days'] / 365.25
    annualized_return = ((equity_curve[-1] / equity_curve[0]) ** (1/years) - 1) * 100

    # Plot
    plt.figure(figsize=(14, 7))
    plt.plot(dates, equity_curve, linewidth=2, color='darkblue')
    plt.title(f'{strategy_name} - Equity Curve\nTotal Return: {total_return:.2f}% | Annualized: {annualized_return:.2f}%',
              fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Equity ($)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.gcf().autofmt_xdate()
    plt.tight_layout()

    graph_path = os.path.join(graph_folder, f'{strategy_name}_equity_curve.png')
    plt.savefig(graph_path, dpi=300)
    plt.close()

    print(f"  - Graph saved: '{graph_path}' | Total Return: {total_return:.2f}% | Annualized: {annualized_return:.2f}%")

# ==============================================================================
# --- MAIN EXECUTION BLOCK ---
# ==============================================================================
if __name__ == "__main__":
    
    # Define the folder where you want to save the CSV files
    TARGET_FOLDER = 'strategy_performance_data'
    
    # List of strategies to generate
    STRATEGIES_TO_CREATE = [
      # IBKR Main
      'SPX_Condors', 'SPX_Butterflies', 'NDX_IronCondors', 'RUT_CreditSpreads',
      'Equity_LongShort', 'TLT_Covered_Calls', 'VIX_Calendar',
      # Futures Account
      'Forex_Trend', 'Gold_Breakout', 'Crude_Momentum', 'ES_Scalping',
      'NQ_Trend', 'ZN_MeanReversion', 'GC_Breakout'
  ]
    
    print("--- Starting Sample Data Generation ---")
    for strategy in STRATEGIES_TO_CREATE:
        generate_strategy_file(strategy, TARGET_FOLDER)
    print("\n--- Data Generation Complete ---")
    print(f"Your sample CSV files are now in the '{TARGET_FOLDER}' folder.")