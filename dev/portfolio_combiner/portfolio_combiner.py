import pandas as pd
import os
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import quantstats as qs

def compile_portfolio(data_folder, allocation_config):
    """
    Reads all strategy CSVs from a folder, aligns them to a master timeline,
    and calculates performance based on a hard-coded allocation dictionary.
    """
    print("Starting portfolio compilation...")

    # --- 1. Load and Process Each Strategy CSV ---
    all_strategy_dfs = []
    # Find all .csv files in the specified data folder
    csv_files = glob.glob(os.path.join(data_folder, '*.csv'))

    if not csv_files:
        print(f"ERROR: No CSV files found in the '{data_folder}' directory. Please check the folder path.")
        return

    print(f"Found {len(csv_files)} strategy files to process...")

    for filepath in csv_files:
        # Extract strategy name from filename (e.g., 'SPX_Condors.csv' -> 'SPX_Condors')
        strategy_name = os.path.basename(filepath).replace('.csv', '')
        
        # Read the CSV file
        try:
            df = pd.read_csv(filepath)
            # Standardize column names for easier processing
            df.columns = ['Date', 'Return_%', 'Notional_Value', 'Margin_Used']

            df['Date'] = pd.to_datetime(df['Date'])

            # Convert Return_% from string (e.g., '0.8463%') to float (e.g., 0.008463)
            df['Return_%'] = df['Return_%'].str.rstrip('%').astype('float') / 100

            df.set_index('Date', inplace=True)
            
            # Rename columns to be unique for this strategy
            df = df.add_prefix(f"{strategy_name}_")
            all_strategy_dfs.append(df)
            print(f"  - Processed '{strategy_name}'")
        except Exception as e:
            print(f"  - FAILED to process '{filepath}'. Error: {e}")

    # --- 2. Align All Strategies to a Master Timeline ---
    master_df = pd.concat(all_strategy_dfs, axis=1)
    master_df.fillna(0, inplace=True)
    master_df.sort_index(inplace=True)
    
    print("\nStep 1: All strategies aligned onto a master timeline.")
    
    # --- 3. Calculate Sized Returns Based on Allocation ---
    sized_returns_map = {}
    for strategy_name, config in allocation_config.items():
        account = config['account']
        multiplier = config['multiplier']
        
        raw_return_col = f"{strategy_name}_Return_%"
        sized_return_col = f"{strategy_name}_Sized_Return_%"
        
        if raw_return_col in master_df.columns:
            master_df[sized_return_col] = master_df[raw_return_col] * multiplier
            
            if account not in sized_returns_map:
                sized_returns_map[account] = []
            sized_returns_map[account].append(sized_return_col)
    
    print("Step 2: Sized returns calculated for each active strategy.")

    # --- 4. Calculate Account-Level Performance ---
    account_perf_df = pd.DataFrame(index=master_df.index)
    for account, sized_cols in sized_returns_map.items():
        account_perf_df[f"{account}_Return_%"] = master_df[sized_cols].sum(axis=1)

    print("Step 3: Daily performance calculated for each account.")

    # --- 5. Calculate Total Portfolio Performance ---
    total_portfolio_df = pd.DataFrame(index=account_perf_df.index)
    total_portfolio_df['Total_Return_%'] = account_perf_df.sum(axis=1)

    starting_capital = 1_000_000
    total_portfolio_df['Equity_Curve'] = starting_capital * (1 + total_portfolio_df['Total_Return_%']).cumprod()

    print("Step 4: Total portfolio performance and equity curve calculated.")

    # --- 6. Generate Equity Curve Graphs ---
    output_folder = 'output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 6a. Strategy-level equity curves
    for strategy_name in allocation_config.keys():
        sized_return_col = f"{strategy_name}_Sized_Return_%"
        if sized_return_col in master_df.columns:
            equity_curve = starting_capital * (1 + master_df[sized_return_col]).cumprod()

            plt.figure(figsize=(12, 6))
            plt.plot(equity_curve.index, equity_curve.values, linewidth=2)
            plt.title(f'{strategy_name} - Equity Curve', fontsize=14, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Equity ($)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gcf().autofmt_xdate()
            plt.tight_layout()
            plt.savefig(os.path.join(output_folder, f'[STRATEGY]{strategy_name}_equity_curve.png'), dpi=300)
            plt.close()

    # 6b. Account-level equity curves
    for account in sized_returns_map.keys():
        account_return_col = f"{account}_Return_%"
        if account_return_col in account_perf_df.columns:
            equity_curve = starting_capital * (1 + account_perf_df[account_return_col]).cumprod()

            plt.figure(figsize=(12, 6))
            plt.plot(equity_curve.index, equity_curve.values, linewidth=2)
            plt.title(f'{account} - Equity Curve', fontsize=14, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Equity ($)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gcf().autofmt_xdate()
            plt.tight_layout()
            plt.savefig(os.path.join(output_folder, f'[ACCOUNT]{account}_equity_curve.png'), dpi=300)
            plt.close()

    # 6c. Total portfolio equity curve
    plt.figure(figsize=(12, 6))
    plt.plot(total_portfolio_df.index, total_portfolio_df['Equity_Curve'].values, linewidth=2, color='green')
    plt.title('Total Portfolio - Equity Curve', fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Equity ($)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, '[PORTFOLIO]_equity_curve.png'), dpi=300)
    plt.close()

    # 6d. Combined graph with all curves
    plt.figure(figsize=(14, 8))

    # Plot strategy curves
    for strategy_name in allocation_config.keys():
        sized_return_col = f"{strategy_name}_Sized_Return_%"
        if sized_return_col in master_df.columns:
            equity_curve = starting_capital * (1 + master_df[sized_return_col]).cumprod()
            plt.plot(equity_curve.index, equity_curve.values, linewidth=1.5, label=f'{strategy_name}', alpha=0.7)

    # Plot account curves
    for account in sized_returns_map.keys():
        account_return_col = f"{account}_Return_%"
        if account_return_col in account_perf_df.columns:
            equity_curve = starting_capital * (1 + account_perf_df[account_return_col]).cumprod()
            plt.plot(equity_curve.index, equity_curve.values, linewidth=2, label=f'{account}', linestyle='--', alpha=0.8)

    # Plot portfolio curve
    plt.plot(total_portfolio_df.index, total_portfolio_df['Equity_Curve'].values, linewidth=3,
             label='Total Portfolio', color='green', alpha=0.9)

    plt.title('All Equity Curves Combined', fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Equity ($)', fontsize=12)
    plt.legend(loc='best', fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, '[ALL]_equity_curves.png'), dpi=300)
    plt.close()

    print("Step 5: Equity curve graphs generated.")

    # --- 7. Generate QuantStats Tearsheets ---
    tearsheet_folder = os.path.join(output_folder, 'tearsheets')
    os.makedirs(tearsheet_folder, exist_ok=True)

    # 7a. Strategy-level tearsheets
    for strategy_name in allocation_config.keys():
        sized_return_col = f"{strategy_name}_Sized_Return_%"
        if sized_return_col in master_df.columns:
            returns_series = master_df[sized_return_col].copy()
            returns_series.name = strategy_name

            tearsheet_path = os.path.join(tearsheet_folder, f'[STRATEGY]{strategy_name}_tearsheet.html')
            qs.reports.html(returns_series, output=tearsheet_path, title=f'{strategy_name} Strategy')
            print(f"  - Generated tearsheet: {tearsheet_path}")

    # 7b. Account-level tearsheets
    for account in sized_returns_map.keys():
        account_return_col = f"{account}_Return_%"
        if account_return_col in account_perf_df.columns:
            returns_series = account_perf_df[account_return_col].copy()
            returns_series.name = account

            tearsheet_path = os.path.join(tearsheet_folder, f'[ACCOUNT]{account}_tearsheet.html')
            qs.reports.html(returns_series, output=tearsheet_path, title=f'{account} Account')
            print(f"  - Generated tearsheet: {tearsheet_path}")

    # 7c. Total portfolio tearsheet
    returns_series = total_portfolio_df['Total_Return_%'].copy()
    returns_series.name = 'Total Portfolio'

    tearsheet_path = os.path.join(tearsheet_folder, '[PORTFOLIO]_tearsheet.html')
    qs.reports.html(returns_series, output=tearsheet_path, title='Total Portfolio')
    print(f"  - Generated tearsheet: {tearsheet_path}")

    print("Step 6: QuantStats tearsheets generated.")

    # --- 8. Save Output Files ---
    master_df.to_csv(os.path.join(output_folder, '1_master_aligned_data.csv'))
    account_perf_df.to_csv(os.path.join(output_folder, '2_account_performance.csv'))
    total_portfolio_df.to_csv(os.path.join(output_folder, '3_total_portfolio_performance.csv'))

    print(f"\nCompilation complete! Check the '{output_folder}' directory for results (CSVs, graphs, and tearsheets).")

# ==============================================================================
# --- MAIN EXECUTION BLOCK ---
# ==============================================================================
if __name__ == "__main__":
    
    # --- This is your Control Panel ---
    # 1. Define the folder where your strategy CSVs are located.
    STRATEGY_DATA_FOLDER = 'strategy_performance_data'
    
    # 2. Define your strategy allocations.
    #    The key (e.g., 'SPX_Condors') MUST EXACTLY MATCH the CSV filename.
    ALLOCATION_CONFIG = {
        'SPX_Condors':   {'account': 'IBKR Main',       'multiplier': 1.0},
        'Forex_Trend':   {'account': 'Futures Account', 'multiplier': 0.75},
        'Gold_Breakout': {'account': 'IBKR Main',       'multiplier': 0.5}
        # To add a new strategy, just add a new line here.
        # 'New_Strategy':  {'account': 'IBKR Main', 'multiplier': 0.25},
    }
    
    # --- Run the compilation process ---
    compile_portfolio(STRATEGY_DATA_FOLDER, ALLOCATION_CONFIG)