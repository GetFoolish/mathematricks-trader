import pandas as pd
import os
import glob
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import quantstats as qs

# Custom formatter for millions
def millions_formatter(x, pos):
    """Format y-axis labels in millions (e.g., 100M instead of 1e8)"""
    return f'{x/1e6:.0f}M' if x != 0 else '0'

def validate_weights(allocation_config, accounts):
    """Display allocation summary for each account (allocations can exceed 100% for leverage)."""
    for account_name in accounts.keys():
        strategies = {name: cfg for name, cfg in allocation_config.items()
                     if cfg['account'] == account_name}

        if len(strategies) == 0:
            print(f"  ⊘ {account_name}: 0 strategies (account unused)")
            continue

        total_weight = sum(cfg['weight'] for cfg in strategies.values())
        leverage = total_weight / 100.0
        print(f"  ✓ {account_name}: {len(strategies)} strategies, total allocation = {total_weight:.1f}% ({leverage:.2f}x leverage)")

def compile_portfolio(data_folder, allocation_config, starting_capital=1_000_000,
                     accounts=None, strategy_metadata=None, output_folder='output'):
    """
    Reads all strategy CSVs from a folder, aligns them to a master timeline,
    and calculates performance based on allocation config and capital.

    Args:
        data_folder: Path to folder containing strategy CSV files
        allocation_config: Dict mapping strategy names to account and weight
        starting_capital: Total starting capital across all accounts
        accounts: Dict mapping account names to starting_capital and target_margin_util_pct
        strategy_metadata: Dict mapping strategy names to margin_per_unit, min_position, increment
        output_folder: Path to folder for output files (graphs, CSVs, tearsheets)
    """
    print("Starting portfolio compilation...")

    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Validate weights
    if accounts:
        print("\nValidating strategy weights...")
        validate_weights(allocation_config, accounts)

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
            # Expected columns: Date, Daily P&L ($), Daily Returns (%), Daily Return on Notional (%), Maximum Daily Notional Value, Maximum Daily Margin Utilization ($)
            df.columns = ['Date', 'PnL_$', 'Return_%', 'Return_on_Notional_%', 'Notional_Value', 'Margin_Used']

            df['Date'] = pd.to_datetime(df['Date'])

            # Convert Return_% from string (e.g., '0.8463%') to float (e.g., 0.008463)
            df['Return_%'] = df['Return_%'].str.rstrip('%').astype('float') / 100

            df.set_index('Date', inplace=True)

            # Rename columns to be unique for this strategy (keep PnL_$ for direct P&L calculation)
            df = df[['PnL_$', 'Return_%', 'Notional_Value', 'Margin_Used']].add_prefix(f"{strategy_name}_")
            all_strategy_dfs.append(df)
            print(f"  - Processed '{strategy_name}'")
        except Exception as e:
            print(f"  - FAILED to process '{filepath}'. Error: {e}")

    # --- 2. Align All Strategies to a Master Timeline ---
    master_df = pd.concat(all_strategy_dfs, axis=1)
    master_df.fillna(0, inplace=True)
    master_df.sort_index(inplace=True)
    
    print("\nStep 1: All strategies aligned onto a master timeline.")

    # --- 3. PRE-CALCULATE DEVELOPER'S EQUITY CURVES ---
    print("\nStep 2a: Building developer's equity curves from returns...")

    import numpy as np

    dev_equity_curves = {}  # Store developer's equity curve for each strategy
    account_strategy_map = {}  # Map account to list of strategies

    for strategy_name, config in allocation_config.items():
        account = config['account']

        pnl_col = f"{strategy_name}_PnL_$"
        return_col = f"{strategy_name}_Return_%"
        margin_col = f"{strategy_name}_Margin_Used"

        if pnl_col not in master_df.columns or return_col not in master_df.columns:
            print(f"  - WARNING: Missing data for '{strategy_name}', skipping...")
            continue

        # Infer developer's starting equity from first day's P&L and return
        first_pnl = master_df[pnl_col].iloc[0]
        first_return = master_df[return_col].iloc[0]

        if abs(first_return) > 0.0001:  # Avoid division by zero
            dev_starting_equity = abs(first_pnl / first_return)
        else:
            # If first return is zero, try to find first non-zero return
            non_zero_mask = master_df[return_col].abs() > 0.0001
            if non_zero_mask.any():
                first_nonzero_idx = non_zero_mask.idxmax()
                dev_starting_equity = abs(master_df[pnl_col].loc[first_nonzero_idx] /
                                         master_df[return_col].loc[first_nonzero_idx])
            else:
                # Fallback: assume $1M
                dev_starting_equity = 1_000_000
                print(f"  - WARNING: Cannot infer equity for '{strategy_name}', assuming $1M")

        # Build developer's compounded equity curve (equity at END of each day)
        dev_equity = dev_starting_equity
        dev_equity_list = []
        for ret in master_df[return_col]:
            dev_equity = dev_equity * (1 + ret)
            dev_equity_list.append(dev_equity)  # Store equity AFTER applying return

        dev_equity_curves[strategy_name] = pd.Series(dev_equity_list, index=master_df.index)

        print(f"  - Built equity curve for '{strategy_name}' (starting: ${dev_starting_equity:,.0f})")

        # Calculate developer's implied position for margin tracking
        if strategy_metadata and strategy_name in strategy_metadata:
            margin_per_unit = strategy_metadata[strategy_name]['margin_per_unit']
            dev_implied_units = master_df[margin_col] / margin_per_unit
            master_df[f"{strategy_name}_Implied_Units"] = dev_implied_units

        # Track which strategies belong to which account
        if account not in account_strategy_map:
            account_strategy_map[account] = []
        account_strategy_map[account].append(strategy_name)

    print("Step 2a: Developer equity curves built.")

    # --- 3. ITERATIVE DAILY LOOP WITH WEIGHTED-AVERAGE RETURNS ---
    print("\nStep 2b: Running daily loop with weighted-average return calculation...")

    # Initialize portfolio equity at starting capital
    portfolio_equity = starting_capital

    # Storage for daily portfolio values
    daily_portfolio_equity = []
    daily_portfolio_returns = []
    daily_portfolio_margin = []

    # Iterate through each day
    for day_idx, day in enumerate(master_df.index):
        # STEP 1: Calculate weighted-average portfolio return for this day
        # Portfolio Return = Sum of (Strategy Return × Allocation%)
        portfolio_daily_return = 0.0
        total_margin = 0.0

        for strategy_name, config in allocation_config.items():
            if strategy_name not in dev_equity_curves:
                continue

            # Get strategy's daily return from developer data
            return_col = f"{strategy_name}_Return_%"
            strategy_return = master_df[return_col].iloc[day_idx]

            # Get allocation weight (expressed as percentage, e.g., 20.0 = 20%)
            allocation_pct = config['weight']

            # Add this strategy's weighted contribution to portfolio return
            # allocation_pct is already in percentage form, so divide by 100
            portfolio_daily_return += strategy_return * (allocation_pct / 100.0)

            # Calculate margin used by this strategy (for monitoring)
            # Scale developer's margin by our allocation
            margin_col = f"{strategy_name}_Margin_Used"
            dev_margin = master_df[margin_col].iloc[day_idx]
            dev_equity = dev_equity_curves[strategy_name].iloc[day_idx]

            # Our effective equity for this strategy
            strategy_equity = portfolio_equity * (allocation_pct / 100.0)

            # Scale margin proportionally
            scaling_ratio = strategy_equity / dev_equity if dev_equity > 0 else 0
            total_margin += dev_margin * scaling_ratio

        # STEP 2: Apply portfolio return to update equity
        portfolio_equity = portfolio_equity * (1 + portfolio_daily_return)

        # STEP 3: Store daily values
        daily_portfolio_equity.append(portfolio_equity)
        daily_portfolio_returns.append(portfolio_daily_return)
        daily_portfolio_margin.append(total_margin)

    # --- 4. Build Portfolio DataFrame from daily values ---
    print("\nStep 2c: Building portfolio performance DataFrame...")

    # Create total portfolio DataFrame
    total_portfolio_df = pd.DataFrame(index=master_df.index)
    total_portfolio_df['Equity_Curve'] = pd.Series(daily_portfolio_equity, index=master_df.index)
    total_portfolio_df['Total_Return_%'] = pd.Series(daily_portfolio_returns, index=master_df.index)
    total_portfolio_df['Total_Margin_Used'] = pd.Series(daily_portfolio_margin, index=master_df.index)
    total_portfolio_df['Margin_Utilization_%'] = (total_portfolio_df['Total_Margin_Used'] / starting_capital) * 100

    # Calculate notional exposure (sum across all strategies, scaled proportionally)
    notional_cols = [col for col in master_df.columns if col.endswith('_Notional_Value')]
    if notional_cols:
        total_notional = pd.Series(0, index=master_df.index)
        for day_idx, day in enumerate(master_df.index):
            for strategy_name, config in allocation_config.items():
                if strategy_name not in dev_equity_curves:
                    continue

                notional_col = f"{strategy_name}_Notional_Value"
                if notional_col not in master_df.columns:
                    continue

                dev_notional = master_df[notional_col].iloc[day_idx]
                dev_equity = dev_equity_curves[strategy_name].iloc[day_idx]
                portfolio_equity_today = daily_portfolio_equity[day_idx]

                allocation_pct = config['weight']
                strategy_equity = portfolio_equity_today * (allocation_pct / 100.0)
                scaling_ratio = strategy_equity / dev_equity if dev_equity > 0 else 0

                total_notional.iloc[day_idx] += dev_notional * scaling_ratio

        total_portfolio_df['Total_Notional_Exposure'] = total_notional
        total_portfolio_df['Leverage_Ratio'] = total_notional / starting_capital
    else:
        total_portfolio_df['Total_Notional_Exposure'] = 0
        total_portfolio_df['Leverage_Ratio'] = 0

    print("Step 2: Portfolio equity curve built with weighted-average returns.")

    # --- 4b. Build Individual Strategy Equity Curves for Visualization ---
    print("\nStep 2d: Building individual strategy equity curves...")

    # For each strategy, build its equity curve using its allocated capital and returns
    strategy_equity_map = {}

    for strategy_name, config in allocation_config.items():
        if strategy_name not in dev_equity_curves:
            continue

        allocation_pct = config['weight']
        strategy_starting_equity = starting_capital * (allocation_pct / 100.0)

        # Build equity curve by compounding strategy's returns
        strategy_equity = strategy_starting_equity
        strategy_equity_list = []
        strategy_margin_list = []

        for day_idx in range(len(master_df)):
            # Get strategy's return for this day
            return_col = f"{strategy_name}_Return_%"
            strategy_return = master_df[return_col].iloc[day_idx]

            # Apply return to equity
            strategy_equity = strategy_equity * (1 + strategy_return)
            strategy_equity_list.append(strategy_equity)

            # Calculate scaled margin for this strategy
            margin_col = f"{strategy_name}_Margin_Used"
            dev_margin = master_df[margin_col].iloc[day_idx]
            dev_equity = dev_equity_curves[strategy_name].iloc[day_idx]
            scaling_ratio = strategy_equity / dev_equity if dev_equity > 0 else 0
            strategy_margin = dev_margin * scaling_ratio
            strategy_margin_list.append(strategy_margin)

        # Store in master_df
        master_df[f"{strategy_name}_Equity_$"] = pd.Series(strategy_equity_list, index=master_df.index)
        master_df[f"{strategy_name}_Scaled_Return_%"] = master_df[f"{strategy_name}_Return_%"]
        master_df[f"{strategy_name}_Scaled_Margin"] = pd.Series(strategy_margin_list, index=master_df.index)
        strategy_equity_map[strategy_name] = pd.Series(strategy_equity_list, index=master_df.index)

    # --- 5. Calculate Account-Level Performance ---
    # With weighted-average returns, account performance = portfolio performance
    # (assuming all strategies are in the same account)
    account_perf_df = pd.DataFrame(index=master_df.index)

    for account, strategies in account_strategy_map.items():
        # Account equity = portfolio equity (since we use weighted average)
        account_perf_df[f"{account}_Equity_$"] = total_portfolio_df['Equity_Curve']
        account_perf_df[f"{account}_Return_%"] = total_portfolio_df['Total_Return_%']
        account_perf_df[f"{account}_Margin_Used"] = total_portfolio_df['Total_Margin_Used']
        account_perf_df[f"{account}_Margin_Utilization_%"] = total_portfolio_df['Margin_Utilization_%']

    print("Step 3: Account-level performance calculated (mapped from portfolio).")
    print("Step 4: Total portfolio performance and equity curve calculated.")

    # --- 5b. Validation Checks ---
    print("\n=== Running Validation Checks ===")

    # Check 1: Display total allocation and leverage
    total_allocation = sum(config['weight'] for config in allocation_config.values())
    leverage = total_allocation / 100.0
    print(f"  ℹ Total allocation: {total_allocation:.1f}% ({leverage:.2f}x leverage)")

    # Check 2: Verify starting and ending equity
    starting_equity = total_portfolio_df['Equity_Curve'].iloc[0]
    ending_equity = total_portfolio_df['Equity_Curve'].iloc[-1]
    total_return = ((ending_equity / starting_equity) - 1) * 100

    print(f"  ℹ Starting equity: ${starting_equity:,.0f}")
    print(f"  ℹ Ending equity: ${ending_equity:,.0f}")
    print(f"  ℹ Total return: {total_return:.2f}%")

    # Check 3: Account equity matches portfolio equity (with weighted-average approach)
    for account in account_strategy_map.keys():
        account_equity_col = f"{account}_Equity_$"
        if account_equity_col in account_perf_df.columns:
            max_diff = (account_perf_df[account_equity_col] - total_portfolio_df['Equity_Curve']).abs().max()
            if max_diff < 0.01:
                print(f"  ✓ {account}: Equity matches portfolio (max diff: ${max_diff:.2f})")
            else:
                print(f"  ✗ WARNING {account}: Equity doesn't match portfolio (max diff: ${max_diff:.2f})")

    print("=== Validation Complete ===\n")

    # --- 6. Generate Equity Curve Graphs ---
    # Note: output_folder is passed as parameter from main block

    # 6a. Strategy-level equity curves with margin utilization
    for strategy_name in allocation_config.keys():
        equity_col = f"{strategy_name}_Equity_$"
        margin_col = f"{strategy_name}_Scaled_Margin"

        if equity_col in master_df.columns:
            equity_curve = master_df[equity_col]

            # Get allocated capital for margin % calculation
            allocated_capital = allocation_config[strategy_name].get('allocated_capital', starting_capital)

            # Calculate margin utilization
            if margin_col in master_df.columns:
                margin_util = (master_df[margin_col] / allocated_capital) * 100
            else:
                margin_util = pd.Series(0, index=master_df.index)

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

            # Top plot: Equity curve
            ax1.plot(equity_curve.index, equity_curve.values, linewidth=2, color='tab:blue')
            ax1.set_ylabel('Equity ($)', fontsize=12)
            ax1.set_title(f'{strategy_name} - Equity Curve & Margin Utilization', fontsize=14, fontweight='bold')
            ax1.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
            ax1.grid(True, alpha=0.3)

            # Bottom plot: Margin utilization % (left axis) and $ (right axis)
            ax2.plot(margin_util.index, margin_util.values, linewidth=2, color='tab:red', label='Margin %')
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('Margin Utilization (%)', fontsize=12, color='tab:red')
            ax2.tick_params(axis='y', labelcolor='tab:red')
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

            # Add secondary y-axis for absolute margin dollars
            if margin_col in master_df.columns:
                ax2_right = ax2.twinx()
                margin_dollars = master_df[margin_col]
                ax2_right.plot(margin_dollars.index, margin_dollars.values, linewidth=2,
                              color='tab:orange', alpha=0.7, linestyle='--', label='Margin $')
                ax2_right.set_ylabel('Margin Used ($)', fontsize=12, color='tab:orange')
                ax2_right.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
                ax2_right.tick_params(axis='y', labelcolor='tab:orange')

            fig.autofmt_xdate()
            fig.tight_layout()
            plt.savefig(os.path.join(output_folder, f'[STRATEGY]{strategy_name}_equity_curve.png'), dpi=300)
            plt.close()

    # 6b. Account-level equity curves with margin utilization
    for account in account_strategy_map.keys():
        account_equity_col = f"{account}_Equity_$"
        account_margin_col = f"{account}_Margin_Utilization_%"

        if account_equity_col in account_perf_df.columns:
            equity_curve = account_perf_df[account_equity_col]

            # Get margin utilization (if available)
            if account_margin_col in account_perf_df.columns:
                margin_util = account_perf_df[account_margin_col]
            else:
                margin_util = pd.Series(0, index=account_perf_df.index)

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

            # Top plot: Equity curve
            ax1.plot(equity_curve.index, equity_curve.values, linewidth=2, color='tab:blue')
            ax1.set_ylabel('Equity ($)', fontsize=12)
            ax1.set_title(f'{account} - Equity Curve & Margin Utilization', fontsize=14, fontweight='bold')
            ax1.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
            ax1.grid(True, alpha=0.3)

            # Bottom plot: Margin utilization % (left axis) and $ (right axis)
            ax2.plot(margin_util.index, margin_util.values, linewidth=2, color='tab:red', label='Margin %')
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('Margin Utilization (%)', fontsize=12, color='tab:red')
            ax2.tick_params(axis='y', labelcolor='tab:red')
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

            # Add secondary y-axis for absolute margin dollars
            account_margin_used_col = f"{account}_Margin_Used"
            if account_margin_used_col in account_perf_df.columns:
                ax2_right = ax2.twinx()
                margin_dollars = account_perf_df[account_margin_used_col]
                ax2_right.plot(margin_dollars.index, margin_dollars.values, linewidth=2,
                              color='tab:orange', alpha=0.7, linestyle='--', label='Margin $')
                ax2_right.set_ylabel('Margin Used ($)', fontsize=12, color='tab:orange')
                ax2_right.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
                ax2_right.tick_params(axis='y', labelcolor='tab:orange')

            fig.autofmt_xdate()
            fig.tight_layout()
            plt.savefig(os.path.join(output_folder, f'[ACCOUNT]{account}_equity_curve.png'), dpi=300)
            plt.close()

    # 6c. Total portfolio equity curve with margin utilization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Top plot: Equity curve
    ax1.plot(total_portfolio_df.index, total_portfolio_df['Equity_Curve'].values, linewidth=2.5, color='tab:green')
    ax1.set_ylabel('Equity ($)', fontsize=12)
    ax1.set_title('Total Portfolio - Equity Curve & Margin Utilization', fontsize=14, fontweight='bold')
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
    ax1.grid(True, alpha=0.3)

    # Bottom plot: Margin utilization % (left axis) and $ (right axis)
    ax2.plot(total_portfolio_df.index, total_portfolio_df['Margin_Utilization_%'].values, linewidth=2, color='tab:red', label='Margin %')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Margin Utilization (%)', fontsize=12, color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

    # Add secondary y-axis for absolute margin dollars
    ax2_right = ax2.twinx()
    margin_dollars = total_portfolio_df['Total_Margin_Used']
    ax2_right.plot(margin_dollars.index, margin_dollars.values, linewidth=2,
                  color='tab:orange', alpha=0.7, linestyle='--', label='Margin $')
    ax2_right.set_ylabel('Margin Used ($)', fontsize=12, color='tab:orange')
    ax2_right.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
    ax2_right.tick_params(axis='y', labelcolor='tab:orange')

    fig.autofmt_xdate()
    fig.tight_layout()
    plt.savefig(os.path.join(output_folder, '[PORTFOLIO]_equity_curve.png'), dpi=300)
    plt.close()

    # 6d. Combined graph with all curves and margin utilization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=True)

    # Top plot: All equity curves
    # Plot strategy equity curves (in various colors)
    strategy_colors = ['tab:blue', 'tab:orange', 'tab:purple', 'tab:cyan', 'tab:pink', 'tab:olive']
    for idx, strategy_name in enumerate(allocation_config.keys()):
        equity_col = f"{strategy_name}_Equity_$"
        if equity_col in master_df.columns:
            equity_curve = master_df[equity_col]
            color = strategy_colors[idx % len(strategy_colors)]
            ax1.plot(equity_curve.index, equity_curve.values, linewidth=1.5, label=f'{strategy_name}',
                    alpha=0.7, color=color)

    # Plot account equity curves (in shades of grey)
    grey_colors = ['darkgrey', 'grey', 'dimgrey', 'lightslategrey']
    for idx, account in enumerate(account_strategy_map.keys()):
        account_equity_col = f"{account}_Equity_$"
        if account_equity_col in account_perf_df.columns:
            equity_curve = account_perf_df[account_equity_col]
            grey_color = grey_colors[idx % len(grey_colors)]
            ax1.plot(equity_curve.index, equity_curve.values, linewidth=2, label=f'{account}',
                    linestyle='--', alpha=0.8, color=grey_color)

    # Plot total portfolio equity curve (black)
    ax1.plot(total_portfolio_df.index, total_portfolio_df['Equity_Curve'].values, linewidth=3,
             label='Total Portfolio', color='black', alpha=0.9)

    ax1.set_ylabel('Equity ($)', fontsize=12)
    ax1.set_title('All Equity Curves & Portfolio Margin Utilization', fontsize=14, fontweight='bold')
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Bottom plot: Portfolio margin utilization % (left axis) and $ (right axis)
    ax2.plot(total_portfolio_df.index, total_portfolio_df['Margin_Utilization_%'].values,
             linewidth=2, color='tab:red', label='Margin %')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Portfolio Margin Utilization (%)', fontsize=12, color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

    # Add secondary y-axis for absolute margin dollars
    ax2_right = ax2.twinx()
    margin_dollars = total_portfolio_df['Total_Margin_Used']
    ax2_right.plot(margin_dollars.index, margin_dollars.values, linewidth=2,
                  color='tab:orange', alpha=0.7, linestyle='--', label='Margin $')
    ax2_right.set_ylabel('Margin Used ($)', fontsize=12, color='tab:orange')
    ax2_right.yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
    ax2_right.tick_params(axis='y', labelcolor='tab:orange')

    fig.autofmt_xdate()
    fig.tight_layout()
    plt.savefig(os.path.join(output_folder, '[ALL]_equity_curves.png'), dpi=300)
    plt.close()

    print("Step 5: Equity curve graphs generated.")

    # --- 7. Generate QuantStats Tearsheets ---
    tearsheet_folder = os.path.join(output_folder, 'tearsheets')
    os.makedirs(tearsheet_folder, exist_ok=True)

    # 7a. Strategy-level tearsheets
    for strategy_name in allocation_config.keys():
        # Calculate daily returns from equity curve
        equity_col = f"{strategy_name}_Equity_$"
        if equity_col in master_df.columns:
            returns_series = master_df[equity_col].pct_change().fillna(0)
            returns_series.name = strategy_name

            tearsheet_path = os.path.join(tearsheet_folder, f'[STRATEGY]{strategy_name}_tearsheet.html')
            qs.reports.html(returns_series, output=tearsheet_path, title=f'{strategy_name} Strategy')
            print(f"  - Generated tearsheet: {tearsheet_path}")

    # 7b. Account-level tearsheets
    for account in account_strategy_map.keys():
        account_return_col = f"{account}_Return_%"
        if account_return_col in account_perf_df.columns:
            returns_series = account_perf_df[account_return_col].copy()
            returns_series.name = account

            tearsheet_path = os.path.join(tearsheet_folder, f'[ACCOUNT]{account}_tearsheet.html')
            qs.reports.html(returns_series, output=tearsheet_path, title=f'{account} Account')
            print(f"  - Generated tearsheet: {tearsheet_path}")

    # 7c. Total portfolio tearsheet
    # Remove non-trading days (where all strategies had zero returns)
    # Keep only days where at least one strategy was trading
    returns_series_full = total_portfolio_df['Total_Return_%'].copy()

    # Filter to only trading days (non-zero return days, since zero means no trading occurred)
    # BUT: A portfolio can have a true 0% return if gains/losses cancel out
    # So we need a better filter: check if ANY strategy had activity
    strategy_returns_cols = [f"{name}_Return_%" for name in allocation_config.keys() if f"{name}_Return_%" in master_df.columns]
    any_trading = master_df[strategy_returns_cols].abs().sum(axis=1) > 0

    returns_series = returns_series_full[any_trading].copy()
    returns_series.name = 'Total Portfolio'

    print(f"  - Filtered to {len(returns_series)} trading days (removed {len(returns_series_full) - len(returns_series)} non-trading days)")

    tearsheet_path = os.path.join(tearsheet_folder, '[PORTFOLIO]_tearsheet.html')
    qs.reports.html(returns_series, output=tearsheet_path, title='Total Portfolio')
    print(f"  - Generated tearsheet: {tearsheet_path}")

    print("Step 6: QuantStats tearsheets generated.")

    # --- 8. Generate Correlation Matrix ---
    print("\nStep 7: Generating correlation matrix...")

    # Build returns dataframe for all strategies
    returns_df = pd.DataFrame(index=master_df.index)
    for strategy_name in allocation_config.keys():
        scaled_return_col = f"{strategy_name}_Scaled_Return_%"
        if scaled_return_col in master_df.columns:
            returns_df[strategy_name] = master_df[scaled_return_col]

    # Calculate correlation matrix
    corr_matrix = returns_df.corr()

    # Plot heatmap
    fig, ax = plt.subplots(figsize=(16, 14))
    im = ax.imshow(corr_matrix, cmap='RdYlGn', aspect='auto', vmin=-1, vmax=1)

    # Set ticks and labels
    ax.set_xticks(range(len(corr_matrix.columns)))
    ax.set_yticks(range(len(corr_matrix.columns)))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(corr_matrix.columns, fontsize=9)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Correlation', rotation=270, labelpad=20, fontsize=11)

    # Add correlation values as text
    for i in range(len(corr_matrix)):
        for j in range(len(corr_matrix)):
            text = ax.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}',
                          ha="center", va="center", color="black", fontsize=16)

    ax.set_title('Strategy Returns Correlation Matrix', fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, '[CORRELATION]_strategy_returns.png'), dpi=300)
    plt.close()

    print(f"  - Generated correlation matrix: {output_folder}/[CORRELATION]_strategy_returns.png")

    # --- 9. Generate Simplified CSV Outputs ---
    print("\nStep 9: Generating CSV outputs...")

    def format_and_save_csv(df, filepath):
        """Helper function to format numbers and save CSV with descending date order"""
        # Reset index to make Date a proper column
        df = df.reset_index(drop=True)

        # Sort by date descending (latest first)
        df = df.sort_values('Date', ascending=False).reset_index(drop=True)

        # Separate percentage columns from dollar columns
        percent_cols = [col for col in df.columns if 'Return' in col or 'return' in col]
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        dollar_cols = [col for col in numeric_cols if col not in percent_cols]

        # Round dollar columns to 0 decimals
        for col in dollar_cols:
            df[col] = df[col].round(0)

        # Convert percentage columns to percentage format (multiply by 100, keep 4 decimals)
        for col in percent_cols:
            if col in df.columns:
                df[col] = df[col] * 100

        # Save with formatting
        df.to_csv(filepath, index=False, float_format='%.4f')

        # Read back and format numbers manually
        df_formatted = pd.read_csv(filepath)

        # Add thousand separators to dollar columns
        for col in dollar_cols:
            if col in df_formatted.columns:
                df_formatted[col] = df_formatted[col].apply(lambda x: f'{int(x):,}' if pd.notna(x) else '')

        # Format percentage columns with 4 decimals and % sign
        for col in percent_cols:
            if col in df_formatted.columns:
                df_formatted[col] = df_formatted[col].apply(lambda x: f'{x:.4f}%' if pd.notna(x) else '')

        df_formatted.to_csv(filepath, index=False)

    # Save strategy-level CSVs: 1_[StrategyName].csv
    for strategy_name in allocation_config.keys():
        if strategy_name not in dev_equity_curves:
            continue

        strategy_csv = pd.DataFrame(index=master_df.index)
        strategy_csv['Date'] = master_df.index

        # Developer columns
        strategy_csv['Dev_Equity'] = dev_equity_curves[strategy_name]
        strategy_csv['Dev_Notional'] = master_df[f"{strategy_name}_Notional_Value"]
        strategy_csv['Dev_Margin'] = master_df[f"{strategy_name}_Margin_Used"]

        # Our columns
        if f"{strategy_name}_Equity_$" in master_df.columns:
            strategy_csv['Our_Equity'] = master_df[f"{strategy_name}_Equity_$"]
        if f"{strategy_name}_Scaled_Margin" in master_df.columns:
            strategy_csv['Our_Margin'] = master_df[f"{strategy_name}_Scaled_Margin"]

        # Calculate our notional (scaled proportionally like position)
        if f"{strategy_name}_Equity_$" in master_df.columns:
            # scaling_ratio = our_equity / dev_equity
            scaling_ratios = master_df[f"{strategy_name}_Equity_$"] / dev_equity_curves[strategy_name]
            strategy_csv['Our_Notional'] = master_df[f"{strategy_name}_Notional_Value"] * scaling_ratios

        # Save to CSV with formatting
        filepath = os.path.join(output_folder, f'1_{strategy_name}.csv')
        format_and_save_csv(strategy_csv, filepath)
        print(f"  - Generated: 1_{strategy_name}.csv")

    # Save account-level CSVs: 3_[AccountName].csv
    for account in account_strategy_map.keys():
        account_csv = pd.DataFrame(index=master_df.index)
        account_csv['Date'] = master_df.index

        if f"{account}_Equity_$" in account_perf_df.columns:
            account_csv['Equity'] = account_perf_df[f"{account}_Equity_$"]
        if f"{account}_Return_%"in account_perf_df.columns:
            account_csv['Daily_Return_%'] = account_perf_df[f"{account}_Return_%"]
        if f"{account}_Margin_Used" in account_perf_df.columns:
            account_csv['Margin'] = account_perf_df[f"{account}_Margin_Used"]

        # Calculate account-level notional
        strategies = account_strategy_map[account]
        notional_cols = [f"{strat}_Notional_Value" for strat in strategies if f"{strat}_Notional_Value" in master_df.columns]
        if notional_cols:
            # Scale each strategy's notional by its scaling ratio
            total_notional = pd.Series(0, index=master_df.index)
            for strategy_name in strategies:
                if f"{strategy_name}_Equity_$" in master_df.columns:
                    scaling_ratios = master_df[f"{strategy_name}_Equity_$"] / dev_equity_curves[strategy_name]
                    total_notional += master_df[f"{strategy_name}_Notional_Value"] * scaling_ratios
            account_csv['Notional'] = total_notional

        # Save to CSV with formatting
        filepath = os.path.join(output_folder, f'3_{account}.csv')
        format_and_save_csv(account_csv, filepath)
        print(f"  - Generated: 3_{account}.csv")

    # Save portfolio-level CSV: 4_Portfolio.csv
    portfolio_csv = pd.DataFrame(index=total_portfolio_df.index)
    portfolio_csv['Date'] = total_portfolio_df.index
    portfolio_csv['Equity'] = total_portfolio_df['Equity_Curve']
    portfolio_csv['Daily_Return_%'] = total_portfolio_df['Total_Return_%']
    portfolio_csv['Margin'] = total_portfolio_df['Total_Margin_Used']
    portfolio_csv['Notional'] = total_portfolio_df['Total_Notional_Exposure']

    # Save to CSV with formatting
    filepath = os.path.join(output_folder, '4_Portfolio.csv')
    format_and_save_csv(portfolio_csv, filepath)
    print("  - Generated: 4_Portfolio.csv")

    print(f"\nStep 9: CSV outputs generated.")

# ==============================================================================
# --- MAIN EXECUTION BLOCK ---
# ==============================================================================
if __name__ == "__main__":

    # ==============================================================================
    # --- SINGLE CONFIGURATION DICT (Your Only Control Panel) ---
    # ==============================================================================

    PORTFOLIO_COMBINATION_CONFIG = {
        # Account definitions
        'accounts': {
            'IBKR Main': {
                'starting_capital': 500_000,
                'target_margin_util_pct': 80,
                'margin_multiplier': 2.3
            },
            'Futures Account': {
                'starting_capital': 500_000,
                'target_margin_util_pct': 80,
                'margin_multiplier': 2.3
            },
            'Crypto Account': {
                'starting_capital': 500_000,
                'target_margin_util_pct': 80,
                'margin_multiplier': 2.3
            }
        },

        # Strategy configurations: margin_per_unit, min_position, increment, account, allocation (optional)
        'strategies': {
            # IBKR Main
            # 'SPX_Condors': {'margin_per_unit': 5000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main'},
            # 'SPX_Butterflies': {'margin_per_unit': 3000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main'},
            # 'NDX_IronCondors': {'margin_per_unit': 6500, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main'},
            # 'RUT_CreditSpreads': {'margin_per_unit': 4400, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main'},
            # 'Equity_LongShort': {'margin_per_unit': 100000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main'},
            # 'TLT_Covered_Calls': {'margin_per_unit': 90000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main'},
            # 'VIX_Calendar': {'margin_per_unit': 3800, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main'},

            # Futures Account
            # 'Forex_Trend': {'margin_per_unit': 2000, 'min_position': 0.01, 'increment': 0.1, 'account': 'Futures Account'},
            # 'Gold_Breakout': {'margin_per_unit': 8200, 'min_position': 1, 'increment': 1, 'account': 'Futures Account'},
            # 'Crude_Momentum': {'margin_per_unit': 6000, 'min_position': 1, 'increment': 1, 'account': 'Futures Account'},
            # 'ES_Scalping': {'margin_per_unit': 12500, 'min_position': 1, 'increment': 1, 'account': 'Futures Account', 'allocation': 40.0},
            # 'NQ_Trend': {'margin_per_unit': 18000, 'min_position': 1, 'increment': 1, 'account': 'Futures Account'},
            # 'ZN_MeanReversion': {'margin_per_unit': 2200, 'min_position': 1, 'increment': 1, 'account': 'Futures Account'},
            # 'GC_Breakout': {'margin_per_unit': 7200, 'min_position': 1, 'increment': 1, 'account': 'Futures Account'},

            # Crypto Account
            # 'BTC_Trend': {'margin_per_unit': 15000, 'min_position': 0.01, 'increment': 0.01, 'account': 'Crypto Account'},
            # 'ETH_Momentum': {'margin_per_unit': 8000, 'min_position': 0.01, 'increment': 0.01, 'account': 'Crypto Account'},
            # 'BTC_ETH_Spread': {'margin_per_unit': 10000, 'min_position': 0.01, 'increment': 0.01, 'account': 'Crypto Account'},
            # 'SOL_Breakout': {'margin_per_unit': 3000, 'min_position': 0.1, 'increment': 0.1, 'account': 'Crypto Account'},
            # 'Altcoin_Basket': {'margin_per_unit': 5000, 'min_position': 0.1, 'increment': 0.1, 'account': 'Crypto Account'},
            # 'Funding_Rate_Arb': {'margin_per_unit': 12000, 'min_position': 0.01, 'increment': 0.01, 'account': 'Crypto Account'},
            # 'Crypto_MeanReversion': {'margin_per_unit': 6000, 'min_position': 0.1, 'increment': 0.1, 'account': 'Crypto Account'},

            # Real strategies from folder
            'Com1-Met': {'margin_per_unit': 20000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 20.0},
            'Com2-Ag': {'margin_per_unit': 20000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 20.0},
            'Com3-Mkt': {'margin_per_unit': 20000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 20.0},
            'Com4-Misc': {'margin_per_unit': 20000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 20.0},
            'Forex': {'margin_per_unit': 50000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 50.0},
            'SPY': {'margin_per_unit': 6000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 0.0},
            'SPX_1-D_Opt': {'margin_per_unit': 6000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 100.0},
            'TLT': {'margin_per_unit': 6000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 0.0},
            'chong_vansh_strategy': {'margin_per_unit': 18000, 'min_position': 1, 'increment': 1, 'account': 'IBKR Main', 'allocation': 0.0},
            
        }
    }

    # ==============================================================================
    # --- AUTO-SETUP (Don't modify below) ---
    # ==============================================================================

    # 0. Setup timestamped output folders
    outputs_dir = 'outputs'
    if os.path.exists(outputs_dir):
        run_dirs = [d for d in os.listdir(outputs_dir) if d.startswith('run_')]
        if run_dirs:
            latest_run = sorted(run_dirs)[-1]
            OUTPUT_BASE = os.path.join(outputs_dir, latest_run)
            EPOCH = latest_run.replace('run_', '')
            print(f"Using latest run: {latest_run} (EPOCH: {EPOCH})")
        else:
            print("ERROR: No strategy data found. Run sample_strategy_data_maker.py first!")
            exit(1)
    else:
        print("ERROR: outputs/ directory not found. Run sample_strategy_data_maker.py first!")
        exit(1)

    PORTFOLIO_OUTPUT = f'{OUTPUT_BASE}/portfolio_analysis'
    STRATEGY_DATA_FOLDER = f'{OUTPUT_BASE}/strategy_performance_data'

    # 1. Extract accounts config
    ACCOUNTS = PORTFOLIO_COMBINATION_CONFIG['accounts']

    # 2. Scan folder for available strategies
    print(f"\nScanning {STRATEGY_DATA_FOLDER} for available strategies...")
    csv_files = glob.glob(os.path.join(STRATEGY_DATA_FOLDER, '*.csv'))
    available_strategies = [os.path.basename(f).replace('.csv', '') for f in csv_files]
    print(f"Found {len(available_strategies)} strategies: {', '.join(available_strategies)}")

    # 3. Build STRATEGY_METADATA and ALLOCATION_CONFIG from available strategies
    STRATEGY_METADATA = {}
    ALLOCATION_CONFIG = {}
    strategies_with_allocation = {}  # Track strategies with explicit allocation
    strategies_without_allocation = {}  # Track strategies needing auto-allocation

    for strategy_name in available_strategies:
        if strategy_name in PORTFOLIO_COMBINATION_CONFIG['strategies']:
            config = PORTFOLIO_COMBINATION_CONFIG['strategies'][strategy_name]

            # Extract metadata
            STRATEGY_METADATA[strategy_name] = {
                'margin_per_unit': config['margin_per_unit'],
                'min_position': config['min_position'],
                'increment': config['increment']
            }

            # Extract account assignment
            account = config['account']

            # Check if allocation is specified
            if 'allocation' in config:
                strategies_with_allocation[strategy_name] = {
                    'account': account,
                    'weight': config['allocation']
                }
            else:
                if account not in strategies_without_allocation:
                    strategies_without_allocation[account] = []
                strategies_without_allocation[account].append(strategy_name)
        else:
            print(f"  WARNING: '{strategy_name}' not found in PORTFOLIO_COMBINATION_CONFIG. Skipping...")

    # 4. Calculate allocations
    # First, add all strategies with explicit allocations
    ALLOCATION_CONFIG.update(strategies_with_allocation)

    # Calculate remaining allocation per account for auto-allocation
    for account in ACCOUNTS.keys():
        # Calculate used allocation
        used_allocation = sum(cfg['weight'] for name, cfg in strategies_with_allocation.items() if cfg['account'] == account)
        remaining_allocation = 100.0 - used_allocation

        # Distribute remaining allocation evenly among strategies without explicit allocation
        if account in strategies_without_allocation:
            num_auto_strategies = len(strategies_without_allocation[account])
            if num_auto_strategies > 0:
                weight_per_strategy = remaining_allocation / num_auto_strategies
                for strategy_name in strategies_without_allocation[account]:
                    ALLOCATION_CONFIG[strategy_name] = {
                        'account': account,
                        'weight': weight_per_strategy
                    }

    # 5. Display allocation summary
    print("\nAllocation Summary:")
    for account in ACCOUNTS.keys():
        strategies_in_account = [(name, cfg['weight']) for name, cfg in ALLOCATION_CONFIG.items() if cfg['account'] == account]
        total_weight = sum(weight for _, weight in strategies_in_account)
        print(f"\n  {account}: {len(strategies_in_account)} strategies, total weight = {total_weight:.2f}%")
        for name, weight in sorted(strategies_in_account, key=lambda x: x[1], reverse=True):
            allocation_type = "explicit" if name in strategies_with_allocation else "auto"
            print(f"    - {name}: {weight:.2f}% ({allocation_type})")

    # --- Run the compilation process ---
    # Calculate starting capital only from accounts that have strategies
    accounts_in_use = set(cfg['account'] for cfg in ALLOCATION_CONFIG.values())
    ACCOUNTS_IN_USE = {name: config for name, config in ACCOUNTS.items() if name in accounts_in_use}
    TOTAL_STARTING_CAPITAL = sum(acc['starting_capital'] for acc in ACCOUNTS_IN_USE.values())

    print(f"\nTotal Portfolio Starting Capital: ${TOTAL_STARTING_CAPITAL:,.0f}")
    print(f"Compiling portfolio with {len(ALLOCATION_CONFIG)} strategies across {len(ACCOUNTS_IN_USE)} accounts...")
    print(f"Allocation Config: {ALLOCATION_CONFIG}\n")
    print(f"Accounts In Use: {ACCOUNTS_IN_USE}\n")
    compile_portfolio(
        STRATEGY_DATA_FOLDER,
        ALLOCATION_CONFIG,
        TOTAL_STARTING_CAPITAL,
        accounts=ACCOUNTS_IN_USE,
        strategy_metadata=STRATEGY_METADATA,
        output_folder=PORTFOLIO_OUTPUT
    )

    print(f"\n{'='*80}")
    print(f"ALL OUTPUTS SAVED TO: {OUTPUT_BASE}/")
    print(f"  - Strategy data: {STRATEGY_DATA_FOLDER}")
    print(f"  - Portfolio analysis: {PORTFOLIO_OUTPUT}")
    print(f"{'='*80}")
