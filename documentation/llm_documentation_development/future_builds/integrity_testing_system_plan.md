# Integrity Testing System Implementation Plan

## Overview
Implement a comprehensive integrity testing system with two modes:
- **Quick Test**: 1-2 signals per strategy (18 signals total, ~3-5 min) - validates core system integrity
- **Detailed Test**: All 90 signals (~10-15 min) - existing functionality with added integrity checks

All tests will validate: mathematical accuracy, state consistency, data flow integrity, and edge case handling.

## User Requirements Summary
- Quick test: All 9 strategies with 1-2 ENTRY/EXIT pairs each
- Detailed test: Full existing test suite with integrity validation
- Checks: Cerebro math, state consistency, data flow, edge cases
- Report format: Pass/fail with error messages

---

## Implementation Steps

### Phase 1: Create Test Configuration
**File**: `tests/signals_testing/test_config.py` [NEW]

Create configuration defining which signals to use in quick mode:
```python
QUICK_TEST_SIGNALS = {
    "SPY": {"file": "spy_realistic.json", "signals": [0, 1]},  # First ENTRY-EXIT pair
    "TLT": {"file": "tlt_realistic.json", "signals": [0, 1]},
    # ... all 9 strategies
}
QUICK_TEST_DELAY = 3  # seconds between signals
```

**Purpose**: Define signal selection for quick mode without hardcoding in main test runner.

---

### Phase 2: Create Integrity Validator
**File**: `tests/signals_testing/integrity_validator.py` [NEW]

Implement `IntegrityValidator` class with these validation methods:

#### 1. `validate_cerebro_math()`
Verifies position sizing calculations from MongoDB data:
- **Scaling ratio**: `allocated_capital / signal_account_equity`
- **Scaled quantity**: `raw_quantity × scaling_ratio`
- **Margin calculation**: `final_quantity × per_contract_margin`

Reads from: `signal_store` collection, checks `decision.math` fields

#### 2. `validate_state_consistency()`
Verifies database state consistency:
- **Fund equity**: `funds.total_equity == sum(accounts.balances.equity)`
- **Capital allocation**: `used_capital ≤ allocated_capital`
- **Position quantities**: `remaining = entry_quantity - exit_quantity` (should be 0 for CLOSED)

Reads from: `funds`, `trading_accounts`, `trading_orders`, `signal_store`

#### 3. `validate_data_flow()`
Verifies signal processing pipeline:
- Every signal has a `decision` object
- APPROVED signals have `execution` data
- Orders in `execution.orders[]` exist in `trading_orders` collection

Reads from: `signal_store`, `trading_orders`

#### 4. `validate_invariants()`
Verifies critical system invariants:
- Allocation percentages ≤ max_leverage
- Position quantities ≥ 0
- No NaN/Inf in critical fields (equity, margin, etc.)

Reads from: `funds`, `portfolio_tests`, `trading_accounts`

#### 5. `validate_edge_cases()`
Verifies edge case handling:
- Insufficient margin rejections are valid (margin_required > capital_available)
- Multi-fund routing creates correct number of orders
- Warnings if edge cases not tested

Reads from: `signal_store` (rejected signals, multi-fund signals)

**Key Method**: `validate_all()` - orchestrates all checks and returns results dict

---

### Phase 3: Create Report Generator
**File**: `tests/signals_testing/integrity_report.py` [NEW]

Implement `IntegrityReportGenerator` class:

#### Methods
- `generate_console_report(results)` - formatted terminal output with colors
- `generate_json_report(results, output_file)` - detailed JSON report

#### Console Report Format
```
================================================================================
INTEGRITY TEST REPORT
================================================================================
Overall Status: ✅ PASS
Checks Run: 156 | Passed: 156 | Failed: 0

CATEGORY BREAKDOWN
------------------
CEREBRO_MATH: ✅ PASS (54 checks)
STATE_CONSISTENCY: ✅ PASS (36 checks)
...

ERRORS (if any)
---------------
1. SCALING_RATIO
   Signal: sig_spy_001
   Message: Scaling ratio mismatch...
```

---

### Phase 4: Modify Main Test Runner
**File**: `tests/signals_testing/run_full_test.py` [MODIFY]

#### Changes Required

**1. Add command-line arguments** (around line 197):
```python
parser.add_argument("--quick", action="store_true",
    help="Run quick test (1-2 signals per strategy, ~3-5 min)")
parser.add_argument("--integrity-checks", action="store_true",
    help="Run integrity validation after test")
```

**2. Modify `run_test()` function** (around line 51):
Add parameters: `quick_mode=False, run_integrity=False`

**3. Add quick mode logic** (after line 86):
```python
if quick_mode:
    from test_config import QUICK_TEST_SIGNALS, QUICK_TEST_DELAY
    # Load only selected signals from config
    delay = QUICK_TEST_DELAY if delay is None else delay
```

**4. Add integrity validation** (after line 145):
```python
if run_integrity or quick_mode:
    from integrity_validator import IntegrityValidator
    from integrity_report import IntegrityReportGenerator

    # Connect to MongoDB
    validator = IntegrityValidator(mongo_client, run_id)
    integrity_results = validator.validate_all()

    # Print console report
    report = IntegrityReportGenerator.generate_console_report(integrity_results)
    print(report)

    # Save JSON report
    integrity_file = os.path.join(output_dir, f"{run_id}_integrity.json")
    IntegrityReportGenerator.generate_json_report(integrity_results, integrity_file)

    # Add to test results
    test_results['integrity_checks'] = integrity_results
```

**5. Update main()** (around line 252):
```python
exit_code = run_test(
    ...,
    quick_mode=args.quick,
    run_integrity=args.integrity_checks or args.quick  # Quick mode always runs checks
)
```

---

### Phase 5: Create Standalone Integrity Runner (Optional)
**File**: `tests/signals_testing/run_integrity_test.py` [NEW]

Create standalone script that can:
- Analyze existing test data without re-running tests
- Trigger new quick test and validate
- Useful for debugging specific test runs

**Usage**:
```bash
# Analyze specific test run
python run_integrity_test.py --test-run-id test_run_20260114_123456

# Run quick test and validate
python run_integrity_test.py --trigger-test
```

---

## Critical Implementation Details

### MongoDB Connection
All validators need MongoDB client. In `run_full_test.py`:
```python
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(mongo_uri)
```

### Signal Selection for Quick Mode
Modify `send_test_signal.py` or `run_full_test.py` to filter signals based on `test_config.QUICK_TEST_SIGNALS`:
- Load all JSON files as normal
- Filter to only selected signal indices per file
- Maintain ENTRY→EXIT pairing (signals come in pairs)

### Floating Point Comparison
Use tolerance for float comparisons:
```python
tolerance = 0.0001
if abs(expected - actual) > tolerance:
    # Fail
```

### Error Context
Each error should include:
- `signal_id` or relevant identifier
- `check` name
- `expected` vs `actual` values
- Descriptive `message`

---

## Files to Create/Modify

### New Files (Create)
1. `tests/signals_testing/test_config.py` (~50 lines)
2. `tests/signals_testing/integrity_validator.py` (~600-700 lines)
3. `tests/signals_testing/integrity_report.py` (~150-200 lines)
4. `tests/signals_testing/run_integrity_test.py` (~100 lines, optional)

### Existing Files (Modify)
1. `tests/signals_testing/run_full_test.py` (~50 lines added)
   - Add imports (line ~48)
   - Add CLI args (line ~197)
   - Modify `run_test()` function (line ~51)
   - Add integrity validation (line ~145)
   - Update `main()` (line ~252)

### Reference Files (No Changes, but consult during implementation)
- `services/cerebro_service/cerebro_main.py` - for understanding scaling calculations
- `services/cerebro_service/fund_allocation_logic.py` - for allocation formulas
- `services/execution_service/execution_main.py` - for position tracking
- `documentation/mongodb_schemas.md` - for database structure

---

## Usage After Implementation

### Quick Test (Recommended for Active Development)
```bash
# Clear data and run quick test with integrity checks
.venv/bin/python scripts/junk/clear_test_data.py && \
.venv/bin/python tests/signals_testing/run_full_test.py --quick

# Output files:
# - test_results/test_run_TIMESTAMP_results.json
# - test_results/test_run_TIMESTAMP_integrity.json
```

### Detailed Test (Comprehensive Validation)
```bash
# Clear data and run full test with integrity checks
.venv/bin/python scripts/junk/clear_test_data.py && \
.venv/bin/python tests/signals_testing/run_full_test.py --integrity-checks --delay 10

# Uses all 90 signals from sample_signals/
```

### Standalone Analysis
```bash
# Analyze existing test data
.venv/bin/python tests/signals_testing/run_integrity_test.py --test-run-id test_run_20260114_123456
```

---

## Validation Logic Details

### Cerebro Math Validation
For each ENTRY signal in `signal_store`:
```python
# 1. Verify scaling_ratio
expected = capital['fund_available'] / capital['backtest_equity']
actual = math['scaling_ratio']
assert abs(expected - actual) < 0.0001

# 2. Verify scaled quantity
expected = quantity_calc['raw_quantity'] * math['scaling_ratio']
actual = quantity_calc['scaled_raw']
assert abs(expected - actual) < 0.01

# 3. Verify margin calculation
expected = legs[0]['quantity'] * margin['per_contract']
actual = margin['total_required']
assert abs(expected - actual) < 0.01
```

### State Consistency Validation
```python
# 1. Fund equity = sum of accounts
fund_equity = funds.find_one({"fund_id": fund_id})['total_equity']
accounts = trading_accounts.find({"fund_id": fund_id})
accounts_sum = sum(acc['balances']['equity'] for acc in accounts)
assert abs(fund_equity - accounts_sum) < 0.01

# 2. Used capital ≤ allocated capital
allocated = fund_equity * (allocation_pct / 100)
used = sum(order['notional_value'] for order in trading_orders.find({
    "fund_id": fund_id,
    "strategy_id": strategy_id,
    "status": {"$in": ["FILLED", "SUBMITTED"]}
}))
assert used <= allocated + 0.01  # Small tolerance

# 3. Position quantity balance
entry_qty = entry_signal['execution']['total_quantity_filled']
exit_qty = sum(exit['execution']['total_quantity_filled'] for exit in exit_signals)
remaining = entry_qty - exit_qty
if position['status'] == 'CLOSED':
    assert abs(remaining) < 0.01
```

### Data Flow Validation
```python
# For each signal:
# 1. Has decision
assert 'decision' in signal

# 2. APPROVED signals have execution
if signal['decision']['status'] == 'APPROVED':
    assert 'execution' in signal

# 3. Orders exist in trading_orders
for order in signal['execution']['orders']:
    assert trading_orders.find_one({"order_id": order['order_id']}) is not None
```

### Invariant Validation
```python
# 1. Allocation ≤ max_leverage
total_allocation = sum(allocations.values())
assert total_allocation <= fund['max_leverage']

# 2. Positive position quantities
for position in account['open_positions']:
    if position['status'] == 'OPEN':
        assert position['quantity'] >= 0

# 3. No NaN/Inf
for field in ['equity', 'cash_balance', 'margin_used']:
    value = account['balances'][field]
    assert not (math.isnan(value) or math.isinf(value))
```

---

## Expected Outcomes

### Quick Test Results
- **Execution time**: 3-5 minutes (18 signals with 3 sec delays)
- **Signals tested**: 18 (2 per strategy × 9 strategies)
- **Integrity checks**: ~150-180 individual checks
- **Output**: Pass/fail report with error details

### Detailed Test Results
- **Execution time**: 10-15 minutes (90 signals with 6 sec delays)
- **Signals tested**: 90 (10 per strategy × 9 strategies)
- **Integrity checks**: ~700-900 individual checks
- **Output**: Comprehensive validation report

### Report Files Generated
1. `test_run_TIMESTAMP_results.json` - test execution summary
2. `test_run_TIMESTAMP_integrity.json` - detailed integrity check results

---

## Error Detection Examples

The system will detect errors like:
- ❌ Scaling ratio calculation incorrect: expected 5.28000, got 5.27998
- ❌ Fund equity mismatch: fund shows $528,000 but accounts sum to $527,999.50
- ❌ Position quantity imbalance: entry_qty=100, exit_qty=99, remaining=1 (should be 0)
- ❌ Used capital exceeds allocation: used $55,000 > allocated $50,000
- ❌ NaN detected in account equity field

---

## Testing the Implementation

### Step-by-step verification:
1. **Test quick mode signal selection**
   ```bash
   # Verify only 18 signals are sent (not 90)
   python run_full_test.py --quick | grep "signals_sent"
   ```

2. **Test integrity checks produce results**
   ```bash
   # Check for integrity report in output
   cat test_results/test_run_*_integrity.json | jq '.summary'
   ```

3. **Verify all check categories run**
   ```bash
   # Should show: cerebro_math, state_consistency, data_flow, invariants, edge_cases
   cat test_results/test_run_*_integrity.json | jq '.details | keys'
   ```

4. **Test error detection** (inject known error)
   ```bash
   # Manually modify a signal in MongoDB to have incorrect scaling_ratio
   # Run integrity checks - should detect the error
   ```

---

## Dependencies

### Python Packages (Already Available)
- `pymongo` - MongoDB operations
- `python-dotenv` - Environment variables
- Standard library: `json`, `argparse`, `time`, `math`

### Environment Variables (Already Configured)
- `MONGODB_URI` - MongoDB connection string
- `SIGNAL_TEST_SEED` - Random seed for tests

### System Requirements
- MongoDB running with `mathematricks_trading` database
- All services running (signal-ingestion, cerebro, execution, account-data)
- Test environment cleared before running tests

---

## Future Enhancements (Not in Scope)

1. **Real-time monitoring**: Stream validation results during test execution
2. **Comparison reports**: Compare results across multiple test runs
3. **Performance metrics**: Track validation execution time per check
4. **Custom check plugins**: Allow adding new validation rules without modifying core
5. **Web dashboard**: Visual representation of test results and trends
6. **Continuous integration**: Automated test runs on code changes

---

## Success Criteria

Implementation is complete when:
1. ✅ Quick test runs in 3-5 minutes with 18 signals
2. ✅ Detailed test runs with full 90 signals
3. ✅ All 5 integrity check categories implemented and working
4. ✅ Pass/fail reports generated with error details
5. ✅ Both JSON and console reports are readable and actionable
6. ✅ Integration with existing test infrastructure is seamless
7. ✅ No disruption to current testing workflow
8. ✅ Documentation is clear for adding new integrity checks

The system should catch errors during development and provide confidence that critical calculations remain accurate as the codebase evolves.
