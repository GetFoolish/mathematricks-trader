# Strategy Upload Test Data

This directory contains 12 test CSV files designed to systematically test the strategy backtest upload functionality, including synthetic data generation, incremental updates, and error handling.

## Test Files Overview

| File | Purpose | Expected Behavior |
|------|---------|-------------------|
| `test_strategy_full_data.csv` | Baseline with all columns | No synthetic warnings |
| `test_strategy_missing_1col.csv` | Missing Max_Notional_Value | Generate notional = margin × 3 |
| `test_strategy_missing_2cols.csv` | Missing margin & notional | Generate both synthetic columns |
| `test_strategy_missing_3cols.csv` | Missing 3 optional columns | Generate PnL, margin, notional |
| `test_strategy_minimal.csv` | Only Date + Return | Generate all 4 optional columns |
| `test_strategy_empty_simulation.csv` | Empty file | Error: "At least 1 row required" |
| `test_strategy_incremental_time.csv` | Extend dates | Append new dates, update hash |
| `test_strategy_incremental_columns.csv` | Add missing column | Backfill old rows, merge new data |
| `test_strategy_overlap_conflict.csv` | Overlapping dates | Error without force_replace |
| `test_strategy_overlap_force.csv` | Force replace overlaps | Replace existing dates |
| `test_strategy_invalid_format.csv` | Invalid return value | Error: "Must be numeric" |
| `test_strategy_missing_required.csv` | Missing required column | Error: "Missing Daily_Return_Pct" |

## Column Definitions

### Required Columns
- **Date**: YYYY-MM-DD format
- **Daily_Return_Pct**: Daily return percentage (e.g., 2.5 for 2.5%)

### Optional Columns (will be generated synthetically if missing)
- **Account_Equity**: Account value after applying daily return
- **Daily_PnL**: Profit/Loss for the day
- **Max_Margin_Used**: Maximum margin used during the day
- **Max_Notional_Value**: Maximum notional value of positions

## Synthetic Data Formulas

When columns are missing, they are generated using these formulas:

```python
# Starting values
starting_equity = 100000  # $100k default

# Account_Equity (cumulative)
equity[0] = starting_equity
equity[i] = equity[i-1] * (1 + return_pct[i] / 100)

# Daily_PnL
pnl[i] = equity[i] - equity[i-1]

# Max_Margin_Used
max_return = max(abs(return_pct))
margin[i] = (abs(return_pct[i]) / max_return) * equity[i] * 0.8

# Max_Notional_Value
notional[i] = margin[i] * 3
```

## Testing Workflow

### 1. Full Data Test
```bash
# Upload test_strategy_full_data.csv
# Expected: Success, no warnings
```

### 2. Progressive Column Removal
```bash
# Upload test_strategy_missing_1col.csv → test_strategy_minimal.csv
# Expected: Increasing number of synthetic data warnings
```

### 3. Incremental Time Update
```bash
# First upload test_strategy_full_data.csv (dates: 01-01 to 01-03)
# Then upload test_strategy_incremental_time.csv (dates: 01-04 to 01-05)
# Expected: Dates appended, hash recalculated, allocations invalidated
```

### 4. Incremental Column Addition
```bash
# First upload test_strategy_minimal.csv (only Date + Return)
# Then upload test_strategy_incremental_columns.csv (adds Max_Margin_Used)
# Expected: Old rows backfilled, new rows use real data, hash updated
```

### 5. Overlap Handling
```bash
# First upload test_strategy_full_data.csv
# Then upload test_strategy_overlap_conflict.csv (without force_replace)
# Expected: Error - date 2025-01-03 already exists
# Then upload test_strategy_overlap_force.csv (with force_replace=true)
# Expected: Success - date replaced, warning shown
```

### 6. Error Cases
```bash
# test_strategy_invalid_format.csv → Error: "Invalid return value"
# test_strategy_missing_required.csv → Error: "Missing Daily_Return_Pct"
# test_strategy_empty_simulation.csv → Error: "At least 1 row required"
```

## Integration with Backend Tests

These files are used by:
- `tests/test_backtest_upload_handler.py` - Unit tests for CSV parsing and synthetic generation
- `tests/test_metrics_calculator.py` - Unit tests for CAGR, Sharpe, Calmar calculations
- `tests/integration/test_strategy_submission_flow.py` - End-to-end tests

## Manual Testing Checklist

- [ ] Upload all 12 files via public portal
- [ ] Verify synthetic data warnings appear correctly
- [ ] Test incremental time updates
- [ ] Test incremental column additions
- [ ] Test overlap detection and force_replace
- [ ] Verify error messages for invalid files
- [ ] Confirm allocation invalidation after data changes
- [ ] Check hash consistency across uploads
