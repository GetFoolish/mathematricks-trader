# Portfolio Combiner Redesign - Final Implementation Plan

## Phase 1: Commit Current Work
**Action:** Save current state before major refactor

```bash
cd /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader
git add dev/portfolio_combiner/
git commit -m "Add margin utilization visualization with stacked subplots

- Strategy, account, and portfolio graphs show equity + margin on separate subplots
- Calculate margin metrics and add to CSV outputs
- Starting capital parameter added to configuration"
git push origin mathematricks-trader-v1
```

---

## Phase 2: Update Email Template
**File:** `dev/portfolio_combiner/email_for_strategy_devs.md`

**Add after existing 4 sections:**

```markdown
**5. Unit-Level Margin Information**

To accurately scale your strategy within our portfolio, we need to understand the margin requirement per tradeable unit:

**Margin Per Unit (Contract/Lot/Share)**
How much margin does one tradeable unit require?
* **For Options:** "$5,000 per contract for a 50-point wide credit spread"
* **For Forex:** "$2,000 per standard lot (100,000 units) at 50:1 leverage"
* **For Futures:** "$8,200 per Gold (GC) contract per CME requirements"
* **For Stocks:** "50% margin requirement in Reg-T account"

**Minimum Position Size & Increments**
What are the position sizing constraints?
* **Minimum Position:** "1 contract minimum" or "0.01 lots (micro lot)"
* **Position Increments:** "Whole contracts only" or "0.1 lot increments"

*Note: We'll combine this with your daily margin utilization data to calculate position sizes and ensure accurate scaling.*
```

---

## Phase 3: Update sample_strategy_data_maker.py
**File:** `dev/portfolio_combiner/sample_strategy_data_maker.py`

**Add position metadata to strategy configs:**

```python
strategy_params = {
    'SPX_Condors': {
        'days': 3650,
        'mean_return': 0.00035,
        'volatility': 0.011,
        'fat_tail_prob': 0.03,
        'fat_tail_mult': 2.2,
        'base_notional': 5500000,
        'base_margin': 50000,

        # NEW: Position sizing metadata
        'margin_per_contract': 5000,
        'min_position': 1,
        'position_increment': 1,
        'typical_contracts': 10,  # For generating realistic variance
    },
    'Forex_Trend': {
        'days': 1460,
        'mean_return': 0.00045,
        'volatility': 0.018,
        'fat_tail_prob': 0.04,
        'fat_tail_mult': 2.1,
        'base_notional': 850000,
        'base_margin': 17000,

        'margin_per_lot': 2000,
        'min_position': 0.1,
        'position_increment': 0.1,
        'typical_lots': 8.5,
    },
    'Gold_Breakout': {
        'days': 2555,
        'mean_return': 0.00040,
        'volatility': 0.016,
        'fat_tail_prob': 0.03,
        'fat_tail_mult': 2.0,
        'base_notional': 425000,
        'base_margin': 41000,

        'margin_per_contract': 8200,
        'min_position': 1,
        'position_increment': 1,
        'typical_contracts': 5,
    }
}
```

**Generate internally consistent data:**

```python
# Inside the loop, calculate position size for each day
typical_units = params.get('typical_contracts') or params.get('typical_lots')
margin_per_unit = params.get('margin_per_contract') or params.get('margin_per_lot')
increment = params['position_increment']

# Vary position size randomly (50% to 150% of typical)
position_variance = random.uniform(0.5, 1.5)
units = typical_units * position_variance

# Round to valid increment
units = round(units / increment) * increment
units = max(params['min_position'], units)

# Calculate margin based on actual position
margin = units * margin_per_unit

# Calculate notional (derive from margin with leverage factor)
# For options: notional is much higher than margin
leverage_factor = params['base_notional'] / params['base_margin']
notional = margin * leverage_factor

# Returns remain as generated (% of allocated capital)
# daily_return is already calculated from the random walk
```

---

## Phase 4: Redesign portfolio_combiner.py Configuration
**File:** `dev/portfolio_combiner/portfolio_combiner.py`

**Replace main configuration block:**

```python
if __name__ == "__main__":

    # --- Define Account Capital Allocations ---
    ACCOUNTS = {
        'IBKR Main': {
            'starting_capital': 600_000,
        },
        'Futures Account': {
            'starting_capital': 400_000,
        }
    }

    # --- Define Strategy Metadata (from developer data) ---
    STRATEGY_METADATA = {
        'SPX_Condors': {
            'margin_per_unit': 5000,
            'min_position': 1,
            'increment': 1,
        },
        'Forex_Trend': {
            'margin_per_unit': 2000,
            'min_position': 0.1,
            'increment': 0.1,
        },
        'Gold_Breakout': {
            'margin_per_unit': 8200,
            'min_position': 1,
            'increment': 1,
        }
    }

    # --- Define Strategy Allocations ---
    ALLOCATION_CONFIG = {
        'SPX_Condors': {
            'account': 'IBKR Main',
            'allocated_capital': 200_000,
            'max_position_scale': 1.0,  # 100% of their position
        },
        'Forex_Trend': {
            'account': 'Futures Account',
            'allocated_capital': 300_000,
            'max_position_scale': 0.75,  # 75% of their position
        },
        'Gold_Breakout': {
            'account': 'IBKR Main',
            'allocated_capital': 150_000,
            'max_position_scale': 0.8,  # 80% of their position
        }
    }

    # --- Run the compilation process ---
    compile_portfolio('strategy_performance_data', ALLOCATION_CONFIG,
                     ACCOUNTS, STRATEGY_METADATA)
```

---

## Phase 5: Rewrite Core Portfolio Logic

### 5.1: Update Function Signature

```python
def compile_portfolio(data_folder, allocation_config, accounts, strategy_metadata):
    """
    Combine multiple trading strategies into a unified portfolio.

    Args:
        data_folder: Path to strategy CSV files
        allocation_config: Dict with strategy allocations
        accounts: Dict with account capital
        strategy_metadata: Dict with position sizing constraints
    """
```

### 5.2: Calculate Implied Positions (After Loading CSVs)

```python
# After loading and aligning strategies
for strategy_name in allocation_config.keys():
    margin_col = f"{strategy_name}_Margin_Used"
    meta = strategy_metadata[strategy_name]

    # Calculate implied contracts from margin data
    master_df[f"{strategy_name}_Implied_Units"] = (
        master_df[margin_col] / meta['margin_per_unit']
    )
```

### 5.3: Calculate Scaled Positions

```python
def scale_position(implied_units, max_scale, allocated_capital,
                   margin_per_unit, min_pos, increment):
    """
    Scale position respecting constraints.

    Returns: (scaled_units, actual_margin)
    """
    # Target position after scaling
    target_units = implied_units * max_scale

    # Round to valid increment
    if target_units == 0:
        return 0, 0

    rounded_units = round(target_units / increment) * increment
    rounded_units = max(min_pos, rounded_units)

    # Check capital constraint
    required_margin = rounded_units * margin_per_unit
    if required_margin > allocated_capital:
        # Reduce to fit
        max_affordable = allocated_capital / margin_per_unit
        rounded_units = (max_affordable // increment) * increment
        rounded_units = max(min_pos, rounded_units) if max_affordable >= min_pos else 0

    actual_margin = rounded_units * margin_per_unit
    return rounded_units, actual_margin

# Apply to each strategy
for strategy_name, config in allocation_config.items():
    meta = strategy_metadata[strategy_name]
    implied_col = f"{strategy_name}_Implied_Units"

    results = master_df[implied_col].apply(
        lambda x: scale_position(
            x,
            config['max_position_scale'],
            config['allocated_capital'],
            meta['margin_per_unit'],
            meta['min_position'],
            meta['increment']
        )
    )

    master_df[f"{strategy_name}_Scaled_Units"] = [r[0] for r in results]
    master_df[f"{strategy_name}_Scaled_Margin"] = [r[1] for r in results]
```

### 5.4: Calculate Scaled Returns and Notional

```python
for strategy_name in allocation_config.keys():
    # Position ratio (actual vs implied)
    implied_units = master_df[f"{strategy_name}_Implied_Units"].replace(0, 1)
    scaled_units = master_df[f"{strategy_name}_Scaled_Units"]
    position_ratio = scaled_units / implied_units

    # Scale returns by position ratio
    raw_return = master_df[f"{strategy_name}_Return_%"]
    master_df[f"{strategy_name}_Scaled_Return_%"] = raw_return * position_ratio

    # Scale notional by position ratio
    raw_notional = master_df[f"{strategy_name}_Notional_Value"]
    master_df[f"{strategy_name}_Scaled_Notional"] = raw_notional * position_ratio
```

### 5.5: Calculate Strategy Equity Curves (Dollar Values)

```python
for strategy_name, config in allocation_config.items():
    allocated_cap = config['allocated_capital']
    return_col = f"{strategy_name}_Scaled_Return_%"

    # Build equity series
    equity = allocated_cap
    equity_values = []

    for ret in master_df[return_col]:
        equity = equity * (1 + ret)
        equity_values.append(equity)

    master_df[f"{strategy_name}_Equity_Value"] = equity_values
```

### 5.6: Calculate Account Equity (Sum Dollar Values)

```python
account_perf_df = pd.DataFrame(index=master_df.index)

for account_name, account_config in accounts.items():
    # Find strategies in this account
    strategies_in_account = [
        s for s, cfg in allocation_config.items()
        if cfg['account'] == account_name
    ]

    # Sum equity values (dollars!)
    equity_cols = [f"{s}_Equity_Value" for s in strategies_in_account]
    account_perf_df[f"{account_name}_Equity_Value"] = (
        master_df[equity_cols].sum(axis=1)
    )

    # Calculate returns from equity changes
    account_perf_df[f"{account_name}_Return_%"] = (
        account_perf_df[f"{account_name}_Equity_Value"].pct_change().fillna(0)
    )

    # Sum margin
    margin_cols = [f"{s}_Scaled_Margin" for s in strategies_in_account]
    account_perf_df[f"{account_name}_Margin_Used"] = (
        master_df[margin_cols].sum(axis=1)
    )

    # Sum notional
    notional_cols = [f"{s}_Scaled_Notional" for s in strategies_in_account]
    account_perf_df[f"{account_name}_Notional_Exposure"] = (
        master_df[notional_cols].sum(axis=1)
    )

    # Margin utilization vs ACCOUNT capital (not total)
    account_capital = account_config['starting_capital']
    account_perf_df[f"{account_name}_Margin_Utilization_%"] = (
        account_perf_df[f"{account_name}_Margin_Used"] / account_capital * 100
    )
```

### 5.7: Calculate Portfolio Equity (Sum Account Dollar Values)

```python
total_portfolio_df = pd.DataFrame(index=master_df.index)

# Sum account equity values
equity_cols = [f"{acc}_Equity_Value" for acc in accounts.keys()]
total_portfolio_df['Portfolio_Equity_Value'] = (
    account_perf_df[equity_cols].sum(axis=1)
)

# Calculate returns from equity changes
total_portfolio_df['Total_Return_%'] = (
    total_portfolio_df['Portfolio_Equity_Value'].pct_change().fillna(0)
)

# Alias for compatibility
total_portfolio_df['Equity_Curve'] = total_portfolio_df['Portfolio_Equity_Value']

# Sum margin and notional
margin_cols = [f"{acc}_Margin_Used" for acc in accounts.keys()]
total_portfolio_df['Total_Margin_Used'] = account_perf_df[margin_cols].sum(axis=1)

notional_cols = [f"{acc}_Notional_Exposure" for acc in accounts.keys()]
total_portfolio_df['Total_Notional_Exposure'] = account_perf_df[notional_cols].sum(axis=1)

# Total allocated capital
total_allocated = sum(cfg['allocated_capital'] for cfg in allocation_config.values())

# Margin utilization vs total ALLOCATED capital
total_portfolio_df['Margin_Utilization_%'] = (
    total_portfolio_df['Total_Margin_Used'] / total_allocated * 100
)

# Leverage = notional / allocated capital
total_portfolio_df['Leverage_Ratio'] = (
    total_portfolio_df['Total_Notional_Exposure'] / total_allocated
)
```

---

## Phase 6: Update Visualizations

**Strategy graphs:**
```python
equity_curve = master_df[f"{strategy_name}_Equity_Value"]
margin_col = f"{strategy_name}_Scaled_Margin"
allocated_cap = allocation_config[strategy_name]['allocated_capital']

margin_util = (master_df[margin_col] / allocated_cap) * 100
```

**Account graphs:**
```python
equity_curve = account_perf_df[f"{account_name}_Equity_Value"]
margin_util = account_perf_df[f"{account_name}_Margin_Utilization_%"]
```

**Portfolio graph:**
```python
equity_curve = total_portfolio_df['Portfolio_Equity_Value']
margin_util = total_portfolio_df['Margin_Utilization_%']
```

---

## Phase 7: Update CSV Outputs

**1_master_aligned_data.csv** - Add:
- `{Strategy}_Implied_Units`
- `{Strategy}_Scaled_Units`
- `{Strategy}_Scaled_Margin`
- `{Strategy}_Scaled_Notional`
- `{Strategy}_Scaled_Return_%`
- `{Strategy}_Equity_Value`

**2_account_performance.csv** - Add:
- `{Account}_Equity_Value`

**3_total_portfolio_performance.csv** - Add:
- `Portfolio_Equity_Value`

---

## Phase 8: Fix QuantStats Tearsheets

```python
# Calculate returns from equity changes (not from summed returns!)
for strategy_name in allocation_config.keys():
    equity_col = f"{strategy_name}_Equity_Value"
    returns_series = master_df[equity_col].pct_change().fillna(0)
    returns_series.name = strategy_name

    qs.reports.html(returns_series, output=tearsheet_path, title=f'{strategy_name} Strategy')
```

Same for account and portfolio tearsheets - use equity-derived returns.

---

## Phase 9: Add Validation Checks

```python
print("\n" + "="*60)
print("VALIDATION CHECKS")
print("="*60)

# Check 1: Sum of strategies = account equity
for account_name in accounts.keys():
    strategies = [s for s, c in allocation_config.items() if c['account'] == account_name]
    sum_strategies = sum(master_df[f"{s}_Equity_Value"].iloc[-1] for s in strategies)
    account_equity = account_perf_df[f"{account_name}_Equity_Value"].iloc[-1]

    if abs(sum_strategies - account_equity) > 1:
        print(f"   {account_name}: Strategy sum ${sum_strategies:,.0f} != Account equity ${account_equity:,.0f}")
    else:
        print(f" {account_name}: Equity reconciliation OK")

# Check 2: Sum of accounts = portfolio equity
sum_accounts = sum(account_perf_df[f"{a}_Equity_Value"].iloc[-1] for a in accounts.keys())
portfolio_equity = total_portfolio_df['Portfolio_Equity_Value'].iloc[-1]

if abs(sum_accounts - portfolio_equity) > 1:
    print(f"   Portfolio: Account sum ${sum_accounts:,.0f} != Portfolio equity ${portfolio_equity:,.0f}")
else:
    print(f" Portfolio: Equity reconciliation OK")

# Check 3: Position rounding drift
for strategy_name, config in allocation_config.items():
    implied = master_df[f"{strategy_name}_Implied_Units"]
    scaled = master_df[f"{strategy_name}_Scaled_Units"]

    # Only check when positions exist
    valid_positions = implied > 0
    if valid_positions.sum() > 0:
        actual_ratio = (scaled[valid_positions] / implied[valid_positions]).mean()
        target_ratio = config['max_position_scale']
        drift = actual_ratio - target_ratio

        if abs(drift) > 0.05:
            print(f"   {strategy_name}: Position rounding causes {drift:+.1%} drift")
        else:
            print(f" {strategy_name}: Position scaling within tolerance")

print("="*60 + "\n")
```

---

## Phase 10: Test Plan

### Test 1: Run with Current Sample Data
```bash
cd dev/portfolio_combiner
python sample_strategy_data_maker.py
python portfolio_combiner.py
```

**Expected:**
- No errors
- Validation checks all pass
- Equity curves look reasonable

### Test 2: Verify Equity Summation
```python
# In output CSVs, check last row:
# Sum of strategy equities = account equity
# Sum of account equities = portfolio equity
```

### Test 3: Verify Position Scaling
```python
# For SPX_Condors with 75% scale:
# Implied units × 0.75 H Scaled units (within rounding)
# Scaled margin = Scaled units × $5,000
```

### Test 4: Verify Margin Utilization
```python
# IBKR Main has $600K capital
# If using $100K margin
# Should show 16.67% utilization (not wrong %)
```

### Test 5: Verify QuantStats
- Open tearsheet HTML
- Check equity curve matches CSV
- Check metrics are reasonable (Sharpe > 0, drawdown < 50%, etc.)

---

## Execution Order

1.  Commit current work (Phase 1)
2.  Update email template (Phase 2)
3.  Update sample_strategy_data_maker.py (Phase 3)
4.  Update portfolio_combiner.py configuration (Phase 4)
5.  Rewrite core logic (Phase 5)
6.  Update graphs (Phase 6)
7.  Update CSVs (Phase 7)
8.  Fix tearsheets (Phase 8)
9.  Add validation (Phase 9)
10.  Test everything (Phase 10)
11.  Final commit

---

## Files Changed

1. `dev/portfolio_combiner/email_for_strategy_devs.md` - Minor addition
2. `dev/portfolio_combiner/sample_strategy_data_maker.py` - Add metadata, fix data generation
3. `dev/portfolio_combiner/portfolio_combiner.py` - Major rewrite (~200 lines changed)

## Estimated Time
- Phase 1-3: 10 minutes
- Phase 4-5: 60 minutes (core logic rewrite)
- Phase 6-9: 30 minutes
- Phase 10: 20 minutes (testing)

**Total: ~2 hours**
