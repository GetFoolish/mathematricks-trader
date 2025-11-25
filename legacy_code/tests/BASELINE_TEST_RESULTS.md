# Baseline Test Results - Phase -1

**Date:** November 7, 2025
**Branch:** mathematricks-trader-v4
**Python Version:** 3.11.14
**Pytest Version:** 8.0.0

## Test Execution Summary

**Total Tests:** 58 collected
**Passed:** 7 (12%)
**Failed:** 5 (9%) - stopped after 5 failures (--maxfail=5)
**Not Run:** 46 (79%) - due to maxfail limit

**Execution Time:** 33.87 seconds

## Services Status

All required services were running during tests:

- ✅ **CerebroService** - http://localhost:8001/health
- ✅ **AccountDataService** - http://localhost:8002/health
- ✅ **Pub/Sub Emulator** - http://localhost:8085

## Test Results by Module

### Test 01: Signal Ingestion (2 passed, 2 failed)

✅ **PASSED:** `test_signal_collector_mongodb_catchup`
✅ **PASSED:** `test_signal_environment_filtering`
❌ **FAILED:** `test_signal_ingestion_from_script_to_pubsub`
   - **Issue:** No messages received from Pub/Sub after 15 seconds
   - **Root Cause:** Pub/Sub subscription timing issue or signal_collector not publishing

❌ **FAILED:** `test_signal_standardization_format`
   - **Issue:** Signal ID sequence number is 6 digits (190158) instead of expected 3 digits
   - **Root Cause:** Signal ID generation using timestamp microseconds instead of counter
   - **Expected:** `{strategy}_{YYYYMMDD}_{HHMMSS}_{###}`
   - **Actual:** `FormatTest_20251107_190158_190158`

### Test 02: Cerebro Processing (5 passed, 1 failed)

✅ **PASSED:** `test_cerebro_position_sizing_calculation`
✅ **PASSED:** `test_cerebro_margin_limit_enforcement`
✅ **PASSED:** `test_cerebro_allocation_based_sizing`
✅ **PASSED:** `test_cerebro_exit_signal_handling`
✅ **PASSED:** `test_cerebro_smart_position_sizing`

❌ **FAILED:** `test_cerebro_signal_to_order_flow`
   - **Issue:** Decision value is 'REJECT' but test expects 'APPROVED' or 'REJECTED'
   - **Root Cause:** Inconsistent decision value naming in Cerebro
   - **Actual:** Decision: REJECT, Reason: "No allocation in MaxHybrid portfolio"

### Test 03: Execution Service (0 passed, 2 failed)

❌ **FAILED:** `test_execution_service_contract_creation`
   - **Issue:** ImportError - cannot import 'create_contracts_from_order' from main
   - **Root Cause:** Import path issue in test (function exists in execution_service/main.py)

❌ **FAILED:** `test_execution_service_action_mapping`
   - **Issue:** Same ImportError as above
   - **Root Cause:** Same import path issue

### Tests 04-10: Not Run

Due to --maxfail=5 setting, tests stopped after 5 failures. Remaining test files:

- ⏸️ `test_04_order_fill_tracking.py` (9 tests)
- ⏸️ `test_05_strategy_management.py` (9 tests)
- ⏸️ `test_06_portfolio_optimization.py` (9 tests)
- ⏸️ `test_07_frontend_admin.py` (2 tests)
- ⏸️ `test_08_dashboard_creator.py` (3 tests)
- ⏸️ `test_09_frontend_client.py` (6 tests)
- ⏸️ `test_10_end_to_end_signal_flow.py` (6 tests)

## Failures Analysis

### Critical Issues (Block Testing):

1. **Signal ID Format Inconsistency**
   - Location: `signal_collector.py` signal ID generation
   - Impact: HIGH - Signal tracking and debugging depends on consistent IDs
   - Fix Priority: P0

2. **Cerebro Decision Value Inconsistency**
   - Location: `services/cerebro_service/main.py`
   - Impact: MEDIUM - Tests expect 'REJECTED' but code uses 'REJECT'
   - Fix Priority: P1

### Minor Issues (Non-Blocking):

3. **Pub/Sub Message Delivery**
   - Location: Test or signal_collector Pub/Sub publishing
   - Impact: LOW - Other tests show Pub/Sub works, likely test timing issue
   - Fix Priority: P2

4. **Import Path in Tests**
   - Location: `test_03_execution_service.py`
   - Impact: LOW - Function exists, just import issue
   - Fix Priority: P2

## Warnings

- ⚠️ **DeprecationWarning:** FastAPI `@app.on_event("startup")` is deprecated
  - Location: `services/cerebro_service/main.py:2137`
  - Recommendation: Migrate to lifespan event handlers

## Next Steps

1. **Fix Critical Issues:**
   - [ ] Standardize signal ID format to use 3-digit counter
   - [ ] Unify decision values (use 'REJECTED' consistently)

2. **Fix Minor Issues:**
   - [ ] Fix test import paths for execution_service tests
   - [ ] Investigate Pub/Sub message delivery timing

3. **Re-run Full Suite:**
   - [ ] Run without --maxfail to see all test results
   - [ ] Generate full HTML report

4. **Documentation:**
   - [ ] Update test documentation based on findings
   - [ ] Document any business logic changes needed

## HTML Report

Full HTML test report available at:
`tests/reports/test_report.html`

## Conclusion

**Phase -1 Status:** ✅ **INFRASTRUCTURE COMPLETE** / ⚠️ **BASELINE ISSUES IDENTIFIED**

The test infrastructure is working correctly:
- 58 tests collected and executable
- pytest fixtures functional
- Service health checks working
- MongoDB and Pub/Sub connections established

However, the baseline reveals issues in the existing codebase that need fixing before proceeding with refactoring:
- Signal ID format inconsistency
- Decision value inconsistency
- Some test implementation issues

**Recommendation:** Fix the 4 identified issues, then re-run full suite to establish clean baseline before starting Phase 0 refactoring.
