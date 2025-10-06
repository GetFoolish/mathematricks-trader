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
        'SPX_Condors': {
            'days': 3650,  # 10 years of data
            'mean_return': 0.00035,  # Slight alpha (~15% annual)
            'volatility': 0.011,   # Moderate volatility for stochastic appearance
            'fat_tail_prob': 0.03,  # 3% chance of fat tail event
            'fat_tail_mult': 2.2,   # Fat tails are 2.2x normal volatility
            'base_notional': 5500000,
            'base_margin': 50000
        },
        'Forex_Trend': {
            'days': 1460,  # 4 years of data
            'mean_return': 0.00045,  # Slight alpha (~18% annual)
            'volatility': 0.016,   # Higher volatility
            'fat_tail_prob': 0.04,  # 4% chance of fat tail event
            'fat_tail_mult': 2.1,
            'base_notional': 850000,
            'base_margin': 17000
        },
        'Gold_Breakout': {
            'days': 2555,  # 7 years of data
            'mean_return': 0.00040,  # Slight alpha (~23% annual)
            'volatility': 0.016,   # High volatility but reduced
            'fat_tail_prob': 0.03,  # 3% chance of fat tail event
            'fat_tail_mult': 2.0,
            'base_notional': 425000,
            'base_margin': 41000
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

        # Add some random noise to notional and margin to make it look realistic
        notional = params['base_notional'] * (1 + (random.random() - 0.5) * 0.1)
        margin = params['base_margin'] * (1 + (random.random() - 0.5) * 0.1)

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
    STRATEGIES_TO_CREATE = ['SPX_Condors', 'Forex_Trend', 'Gold_Breakout']
    
    print("--- Starting Sample Data Generation ---")
    for strategy in STRATEGIES_TO_CREATE:
        generate_strategy_file(strategy, TARGET_FOLDER)
    print("\n--- Data Generation Complete ---")
    print(f"Your sample CSV files are now in the '{TARGET_FOLDER}' folder.")