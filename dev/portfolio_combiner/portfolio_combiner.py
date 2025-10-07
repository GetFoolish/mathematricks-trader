import pandas as pd
import os
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import quantstats as qs

def validate_weights(allocation_config, accounts):
    """Validate that weights sum to 100% for each account."""
    for account_name in accounts.keys():
        strategies = {name: cfg for name, cfg in allocation_config.items()
                     if cfg['account'] == account_name}
        total_weight = sum(cfg['weight'] for cfg in strategies.values())
        if abs(total_weight - 100.0) > 0.01:
            raise ValueError(f"{account_name} weights sum to {total_weight:.2f}%, must be 100%")
        print(f"  ✓ {account_name}: {len(strategies)} strategies, weights sum to {total_weight:.1f}%")

def compile_portfolio(data_folder, allocation_config, starting_capital=1_000_000,
                     accounts=None, strategy_metadata=None):
    """
    Reads all strategy CSVs from a folder, aligns them to a master timeline,
    and calculates performance based on allocation config and capital.

    Args:
        data_folder: Path to folder containing strategy CSV files
        allocation_config: Dict mapping strategy names to account and weight
        starting_capital: Total starting capital across all accounts
        accounts: Dict mapping account names to starting_capital and target_margin_util_pct
        strategy_metadata: Dict mapping strategy names to margin_per_unit, min_position, increment
    """
    print("Starting portfolio compilation...")

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

    # --- 3. Calculate Positions from Margin Budgets ---
    strategy_equity_map = {}  # Map strategy name to its equity series
    account_strategy_map = {}  # Map account to list of strategies

    for strategy_name, config in allocation_config.items():
        account = config['account']
        weight = config['weight']

        raw_return_col = f"{strategy_name}_Return_%"
        margin_col = f"{strategy_name}_Margin_Used"

        if raw_return_col not in master_df.columns or margin_col not in master_df.columns:
            print(f"  - WARNING: Missing data for '{strategy_name}', skipping...")
            continue

        # Calculate margin allocation from account budget and weight
        if accounts and account in accounts:
            account_capital = accounts[account]['starting_capital']
            target_margin_pct = accounts[account]['target_margin_util_pct']
            account_margin_budget = account_capital * (target_margin_pct / 100)
            strategy_margin_allocation = account_margin_budget * (weight / 100)
        else:
            # Fallback if accounts not provided
            strategy_margin_allocation = starting_capital * 0.1  # Default 10%

        # Get position sizing metadata
        if strategy_metadata and strategy_name in strategy_metadata:
            metadata = strategy_metadata[strategy_name]
            margin_per_unit = metadata['margin_per_unit']
            min_position = metadata['min_position']
            increment = metadata['increment']

            # Calculate developer's implied position (for returns scaling)
            dev_implied_position = master_df[margin_col] / margin_per_unit
            master_df[f"{strategy_name}_Implied_Units"] = dev_implied_position

            # Calculate OUR target position from margin allocation (ignoring dev size!)
            target_position = strategy_margin_allocation / margin_per_unit

            # Round to valid increments and enforce minimum
            import numpy as np
            valid_position = np.round(target_position / increment) * increment
            valid_position = max(min_position, valid_position) if valid_position > 0 else 0

            # Store our position (constant over time!)
            master_df[f"{strategy_name}_Scaled_Units"] = valid_position

            # Calculate our actual margin used (should be constant!)
            master_df[f"{strategy_name}_Scaled_Margin"] = valid_position * margin_per_unit

            # Calculate position ratio for returns scaling
            position_ratio = valid_position / dev_implied_position.replace(0, 1)
            position_ratio = position_ratio.fillna(0)

            # Scale returns by position ratio
            master_df[f"{strategy_name}_Scaled_Return_%"] = master_df[raw_return_col] * position_ratio

            # Calculate scaled notional (if notional data exists)
            notional_col = f"{strategy_name}_Notional_Value"
            if notional_col in master_df.columns:
                master_df[f"{strategy_name}_Scaled_Notional"] = master_df[notional_col] * position_ratio
        else:
            # Fallback without metadata
            master_df[f"{strategy_name}_Scaled_Margin"] = strategy_margin_allocation
            master_df[f"{strategy_name}_Scaled_Return_%"] = master_df[raw_return_col]

        # Calculate equity curve starting from margin allocation
        scaled_return_col = f"{strategy_name}_Scaled_Return_%"
        starting_equity = strategy_margin_allocation  # Start equity = margin allocated
        equity_curve = [starting_equity]
        for ret in master_df[scaled_return_col]:
            equity_curve.append(equity_curve[-1] * (1 + ret))

        # Remove the starting value and align with dataframe index
        equity_series = pd.Series(equity_curve[1:], index=master_df.index)
        master_df[f"{strategy_name}_Equity_$"] = equity_series
        strategy_equity_map[strategy_name] = equity_series

        # Track which strategies belong to which account
        if account not in account_strategy_map:
            account_strategy_map[account] = []
        account_strategy_map[account].append(strategy_name)

    print("Step 2: Margin budgets allocated, positions calculated, and equity curves built.")

    # --- 4. Calculate Account-Level Performance ---
    account_perf_df = pd.DataFrame(index=master_df.index)

    for account, strategies in account_strategy_map.items():
        # Sum dollar equity values for all strategies in this account
        equity_cols = [f"{strat}_Equity_$" for strat in strategies]
        account_equity = master_df[equity_cols].sum(axis=1)
        account_perf_df[f"{account}_Equity_$"] = account_equity

        # Calculate daily returns from equity values
        account_perf_df[f"{account}_Return_%"] = account_equity.pct_change().fillna(0)

        # Calculate margin utilization for this account
        margin_cols = [f"{strat}_Scaled_Margin" for strat in strategies if f"{strat}_Scaled_Margin" in master_df.columns]
        if margin_cols:
            account_perf_df[f"{account}_Margin_Used"] = master_df[margin_cols].sum(axis=1)
            # Calculate margin utilization % based on account's starting capital
            if accounts and account in accounts:
                account_capital = accounts[account]['starting_capital']
                account_perf_df[f"{account}_Margin_Utilization_%"] = (account_perf_df[f"{account}_Margin_Used"] / account_capital) * 100

    print("Step 3: Account-level equity and performance calculated.")

    # --- 5. Calculate Total Portfolio Performance ---
    total_portfolio_df = pd.DataFrame(index=account_perf_df.index)

    # Sum all account equities to get total portfolio equity
    equity_cols = [col for col in account_perf_df.columns if col.endswith('_Equity_$')]
    total_portfolio_df['Equity_Curve'] = account_perf_df[equity_cols].sum(axis=1)

    # Calculate daily returns from portfolio equity
    total_portfolio_df['Total_Return_%'] = total_portfolio_df['Equity_Curve'].pct_change().fillna(0)

    print("Step 4: Total portfolio performance and equity curve calculated.")

    # --- 5a. Calculate Portfolio-Level Margin Metrics ---
    # Sum scaled margin across all strategies
    scaled_margin_cols = [col for col in master_df.columns if col.endswith('_Scaled_Margin')]
    total_portfolio_df['Total_Margin_Used'] = master_df[scaled_margin_cols].sum(axis=1) if scaled_margin_cols else 0

    # Calculate portfolio-level margin utilization
    total_portfolio_df['Margin_Utilization_%'] = (total_portfolio_df['Total_Margin_Used'] / starting_capital) * 100

    # Calculate notional exposure and leverage (if notional data exists)
    notional_cols = [col for col in master_df.columns if col.endswith('_Notional_Value')]
    if notional_cols:
        total_portfolio_df['Total_Notional_Exposure'] = master_df[notional_cols].sum(axis=1)
        total_portfolio_df['Leverage_Ratio'] = total_portfolio_df['Total_Notional_Exposure'] / starting_capital
    else:
        total_portfolio_df['Total_Notional_Exposure'] = 0
        total_portfolio_df['Leverage_Ratio'] = 0

    print("Step 4a: Portfolio-level margin metrics calculated.")

    # --- 5b. Validation Checks ---
    print("\n=== Running Validation Checks ===")

    # Check 1: Verify that sum of strategy equities equals account equity
    for account, strategies in account_strategy_map.items():
        equity_cols = [f"{strat}_Equity_$" for strat in strategies]
        sum_of_strategies = master_df[equity_cols].sum(axis=1)
        account_equity_col = f"{account}_Equity_$"

        if account_equity_col in account_perf_df.columns:
            account_equity = account_perf_df[account_equity_col]
            max_diff = (sum_of_strategies - account_equity).abs().max()

            if max_diff < 0.01:  # Allow for floating point errors
                print(f"  ✓ {account}: Strategy equities sum correctly (max diff: ${max_diff:.2f})")
            else:
                print(f"  ✗ WARNING {account}: Strategy equities don't sum correctly (max diff: ${max_diff:.2f})")

    # Check 2: Verify that sum of account equities equals portfolio equity
    account_equity_cols = [col for col in account_perf_df.columns if col.endswith('_Equity_$')]
    sum_of_accounts = account_perf_df[account_equity_cols].sum(axis=1)
    max_diff = (sum_of_accounts - total_portfolio_df['Equity_Curve']).abs().max()

    if max_diff < 0.01:
        print(f"  ✓ Portfolio: Account equities sum correctly (max diff: ${max_diff:.2f})")
    else:
        print(f"  ✗ WARNING Portfolio: Account equities don't sum correctly (max diff: ${max_diff:.2f})")

    # Check 3: Verify starting capital allocation
    total_allocated = sum(config.get('allocated_capital', starting_capital) for config in allocation_config.values())
    print(f"  ℹ Total allocated capital: ${total_allocated:,.0f} across {len(allocation_config)} strategies")

    if accounts:
        total_account_capital = sum(acc['starting_capital'] for acc in accounts.values())
        print(f"  ℹ Total account capital: ${total_account_capital:,.0f} across {len(accounts)} accounts")

        if total_allocated <= total_account_capital:
            print(f"  ✓ Allocated capital (${total_allocated:,.0f}) fits within account capital (${total_account_capital:,.0f})")
        else:
            print(f"  ✗ WARNING: Allocated capital (${total_allocated:,.0f}) exceeds account capital (${total_account_capital:,.0f})")

    print("=== Validation Complete ===\n")

    # --- 6. Generate Equity Curve Graphs ---
    output_folder = 'output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

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
            ax1.grid(True, alpha=0.3)

            # Bottom plot: Margin utilization
            ax2.plot(margin_util.index, margin_util.values, linewidth=2, color='tab:red')
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('Margin Utilization (%)', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

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
            ax1.grid(True, alpha=0.3)

            # Bottom plot: Margin utilization
            ax2.plot(margin_util.index, margin_util.values, linewidth=2, color='tab:red')
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('Margin Utilization (%)', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

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
    ax1.grid(True, alpha=0.3)

    # Bottom plot: Margin utilization
    ax2.plot(total_portfolio_df.index, total_portfolio_df['Margin_Utilization_%'].values, linewidth=2, color='tab:red')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Margin Utilization (%)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

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
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Bottom plot: Portfolio margin utilization
    ax2.plot(total_portfolio_df.index, total_portfolio_df['Margin_Utilization_%'].values,
             linewidth=2, color='tab:red')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Portfolio Margin Utilization (%)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

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
    returns_series = total_portfolio_df['Total_Return_%'].copy()
    returns_series.name = 'Total Portfolio'

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
                          ha="center", va="center", color="black", fontsize=7)

    ax.set_title('Strategy Returns Correlation Matrix', fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, '[CORRELATION]_strategy_returns.png'), dpi=300)
    plt.close()

    print("  - Generated correlation matrix: output/[CORRELATION]_strategy_returns.png")

    # --- 9. Generate Detailed Margin and PnL Analysis CSVs ---
    print("\nStep 9: Generating detailed margin and PnL analysis CSVs...")

    # CSV 1: Strategy Margin Analysis
    # Shows target vs actual margin, position sizes, and returns for each strategy
    strategy_margin_df = pd.DataFrame(index=master_df.index)

    for strategy_name, config in allocation_config.items():
        account = config['account']
        weight = config['weight']

        # Calculate target margin for this strategy
        if accounts and account in accounts:
            account_capital = accounts[account]['starting_capital']
            target_margin_pct = accounts[account]['target_margin_util_pct']
            account_margin_budget = account_capital * (target_margin_pct / 100)
            target_margin = account_margin_budget * (weight / 100)
        else:
            target_margin = 0

        # Add columns for this strategy
        strategy_margin_df[f"{strategy_name}_Target_Margin"] = target_margin

        if f"{strategy_name}_Scaled_Margin" in master_df.columns:
            strategy_margin_df[f"{strategy_name}_Actual_Margin"] = master_df[f"{strategy_name}_Scaled_Margin"]
            strategy_margin_df[f"{strategy_name}_Margin_Diff"] = master_df[f"{strategy_name}_Scaled_Margin"] - target_margin

        if f"{strategy_name}_Scaled_Units" in master_df.columns:
            strategy_margin_df[f"{strategy_name}_Position"] = master_df[f"{strategy_name}_Scaled_Units"]

        if f"{strategy_name}_Scaled_Return_%" in master_df.columns:
            strategy_margin_df[f"{strategy_name}_Return_%"] = master_df[f"{strategy_name}_Scaled_Return_%"]

        if f"{strategy_name}_Equity_$" in master_df.columns:
            strategy_margin_df[f"{strategy_name}_Equity"] = master_df[f"{strategy_name}_Equity_$"]

    strategy_margin_df.to_csv(os.path.join(output_folder, '4_strategy_margin_analysis.csv'))
    print("  - Generated: 4_strategy_margin_analysis.csv")

    # CSV 2: Account Margin Summary
    # Shows account-level margin tracking over time
    account_margin_summary = pd.DataFrame(index=master_df.index)

    for account, strategies in account_strategy_map.items():
        if accounts and account in accounts:
            account_capital = accounts[account]['starting_capital']
            target_margin_pct = accounts[account]['target_margin_util_pct']
            target_margin = account_capital * (target_margin_pct / 100)

            account_margin_summary[f"{account}_Capital"] = account_capital
            account_margin_summary[f"{account}_Target_Margin"] = target_margin

            # Sum actual margin used
            margin_cols = [f"{strat}_Scaled_Margin" for strat in strategies if f"{strat}_Scaled_Margin" in master_df.columns]
            if margin_cols:
                actual_margin = master_df[margin_cols].sum(axis=1)
                account_margin_summary[f"{account}_Actual_Margin"] = actual_margin
                account_margin_summary[f"{account}_Margin_Util_%"] = (actual_margin / account_capital) * 100
                account_margin_summary[f"{account}_Target_Util_%"] = target_margin_pct
                account_margin_summary[f"{account}_Margin_Diff"] = actual_margin - target_margin

            # Add equity
            if f"{account}_Equity_$" in account_perf_df.columns:
                account_margin_summary[f"{account}_Equity"] = account_perf_df[f"{account}_Equity_$"]

    account_margin_summary.to_csv(os.path.join(output_folder, '5_account_margin_summary.csv'))
    print("  - Generated: 5_account_margin_summary.csv")

    # CSV 3: Daily PnL Attribution
    # Shows daily PnL contribution by strategy and account
    pnl_attribution = pd.DataFrame(index=master_df.index)

    for strategy_name in allocation_config.keys():
        equity_col = f"{strategy_name}_Equity_$"
        if equity_col in master_df.columns:
            # Calculate daily PnL as change in equity
            daily_pnl = master_df[equity_col].diff().fillna(0)
            pnl_attribution[f"{strategy_name}_Daily_PnL"] = daily_pnl

    # Add account-level PnL
    for account in account_strategy_map.keys():
        equity_col = f"{account}_Equity_$"
        if equity_col in account_perf_df.columns:
            daily_pnl = account_perf_df[equity_col].diff().fillna(0)
            pnl_attribution[f"{account}_Daily_PnL"] = daily_pnl

    # Add portfolio-level PnL
    pnl_attribution['Portfolio_Daily_PnL'] = total_portfolio_df['Equity_Curve'].diff().fillna(0)
    pnl_attribution['Portfolio_Cumulative_PnL'] = pnl_attribution['Portfolio_Daily_PnL'].cumsum()

    pnl_attribution.to_csv(os.path.join(output_folder, '6_daily_pnl_attribution.csv'))
    print("  - Generated: 6_daily_pnl_attribution.csv")

    # --- 10. Save Original Output Files ---
    master_df.to_csv(os.path.join(output_folder, '1_master_aligned_data.csv'))
    account_perf_df.to_csv(os.path.join(output_folder, '2_account_performance.csv'))
    total_portfolio_df.to_csv(os.path.join(output_folder, '3_total_portfolio_performance.csv'))

    print(f"\nCompilation complete! Check the '{output_folder}' directory for results (CSVs, graphs, correlation matrix, and tearsheets).")

# ==============================================================================
# --- MAIN EXECUTION BLOCK ---
# ==============================================================================
if __name__ == "__main__":

    # --- This is your Control Panel ---
    # 1. Define the folder where your strategy CSVs are located.
    STRATEGY_DATA_FOLDER = 'strategy_performance_data'

    # 2. Define your accounts and their starting capital
    ACCOUNTS = {
        'IBKR Main': {
            'starting_capital': 500_000,
            'target_margin_util_pct': 80  # Target 80% margin utilization
        },
        'Futures Account': {
            'starting_capital': 300_000,
            'target_margin_util_pct': 80
        },
        'Crypto Account': {
            'starting_capital': 200_000,
            'target_margin_util_pct': 80
        }
    }

    # 3. Define position sizing metadata for each strategy
    #    This tells us how to scale positions and calculate implied position sizes
    STRATEGY_METADATA = {
      # IBKR Main
      'SPX_Condors': {'margin_per_unit': 5000, 'min_position': 1, 'increment': 1},
      'SPX_Butterflies': {'margin_per_unit': 3000, 'min_position': 1, 'increment': 1},
      'NDX_IronCondors': {'margin_per_unit': 6500, 'min_position': 1, 'increment': 1},
      'RUT_CreditSpreads': {'margin_per_unit': 4400, 'min_position': 1, 'increment': 1},
      'Equity_LongShort': {'margin_per_unit': 100000, 'min_position': 1, 'increment': 1},
      'TLT_Covered_Calls': {'margin_per_unit': 90000, 'min_position': 1, 'increment': 1},
      'VIX_Calendar': {'margin_per_unit': 3800, 'min_position': 1, 'increment': 1},
      # Futures Account
      'Forex_Trend': {'margin_per_unit': 2000, 'min_position': 0.01, 'increment': 0.1},
      'Gold_Breakout': {'margin_per_unit': 8200, 'min_position': 1, 'increment': 1},
      'Crude_Momentum': {'margin_per_unit': 6000, 'min_position': 1, 'increment': 1},
      'ES_Scalping': {'margin_per_unit': 12500, 'min_position': 1, 'increment': 1},
      'NQ_Trend': {'margin_per_unit': 18000, 'min_position': 1, 'increment': 1},
      'ZN_MeanReversion': {'margin_per_unit': 2200, 'min_position': 1, 'increment': 1},
      'GC_Breakout': {'margin_per_unit': 7200, 'min_position': 1, 'increment': 1},
      # Crypto Account
      'BTC_Trend': {'margin_per_unit': 15000, 'min_position': 0.01, 'increment': 0.01},
      'ETH_Momentum': {'margin_per_unit': 8000, 'min_position': 0.01, 'increment': 0.01},
      'BTC_ETH_Spread': {'margin_per_unit': 10000, 'min_position': 0.01, 'increment': 0.01},
      'SOL_Breakout': {'margin_per_unit': 3000, 'min_position': 0.1, 'increment': 0.1},
      'Altcoin_Basket': {'margin_per_unit': 5000, 'min_position': 0.1, 'increment': 0.1},
      'Funding_Rate_Arb': {'margin_per_unit': 12000, 'min_position': 0.01, 'increment': 0.01},
      'Crypto_MeanReversion': {'margin_per_unit': 6000, 'min_position': 0.1, 'increment': 0.1},
  }

    # 4. Define your strategy allocations using WEIGHTS
    #    Weights sum to 100% PER ACCOUNT
    #    Each strategy gets: (account_capital * target_margin% * weight%) of margin
    ALLOCATION_CONFIG = {
      # IBKR Main - 7 strategies, weights sum to 100%, margin budget = $400K (80% of $500K)
      'SPX_Condors':         {'account': 'IBKR Main', 'weight': 18.0},  # 18% of $400K = $72K margin
      'SPX_Butterflies':     {'account': 'IBKR Main', 'weight': 12.0},  # $48K margin
      'NDX_IronCondors':     {'account': 'IBKR Main', 'weight': 16.0},  # $64K margin
      'RUT_CreditSpreads':   {'account': 'IBKR Main', 'weight': 14.0},  # $56K margin
      'Equity_LongShort':    {'account': 'IBKR Main', 'weight': 15.0},  # $60K margin
      'TLT_Covered_Calls':   {'account': 'IBKR Main', 'weight': 13.0},  # $52K margin
      'VIX_Calendar':        {'account': 'IBKR Main', 'weight': 12.0},  # $48K margin
      # Sum = 100%

      # Futures Account - 7 strategies, weights sum to 100%, margin budget = $240K (80% of $300K)
      'Forex_Trend':         {'account': 'Futures Account', 'weight': 16.0},  # $38.4K margin
      'Gold_Breakout':       {'account': 'Futures Account', 'weight': 14.0},  # $33.6K margin
      'Crude_Momentum':      {'account': 'Futures Account', 'weight': 15.0},  # $36K margin
      'ES_Scalping':         {'account': 'Futures Account', 'weight': 18.0},  # $43.2K margin
      'NQ_Trend':            {'account': 'Futures Account', 'weight': 17.0},  # $40.8K margin
      'ZN_MeanReversion':    {'account': 'Futures Account', 'weight': 10.0},  # $24K margin
      'GC_Breakout':         {'account': 'Futures Account', 'weight': 10.0},  # $24K margin
      # Sum = 100%

      # Crypto Account - 7 strategies, weights sum to 100%, margin budget = $160K (80% of $200K)
      'BTC_Trend':           {'account': 'Crypto Account', 'weight': 20.0},  # $32K margin
      'ETH_Momentum':        {'account': 'Crypto Account', 'weight': 18.0},  # $28.8K margin
      'BTC_ETH_Spread':      {'account': 'Crypto Account', 'weight': 12.0},  # $19.2K margin
      'SOL_Breakout':        {'account': 'Crypto Account', 'weight': 15.0},  # $24K margin
      'Altcoin_Basket':      {'account': 'Crypto Account', 'weight': 15.0},  # $24K margin
      'Funding_Rate_Arb':    {'account': 'Crypto Account', 'weight': 10.0},  # $16K margin
      'Crypto_MeanReversion': {'account': 'Crypto Account', 'weight': 10.0},  # $16K margin
      # Sum = 100%
  }

    # --- Run the compilation process ---
    # NOTE: Starting capital is now calculated as sum of account capitals
    TOTAL_STARTING_CAPITAL = sum(acc['starting_capital'] for acc in ACCOUNTS.values())
    compile_portfolio(
        STRATEGY_DATA_FOLDER,
        ALLOCATION_CONFIG,
        TOTAL_STARTING_CAPITAL,
        accounts=ACCOUNTS,
        strategy_metadata=STRATEGY_METADATA
    )