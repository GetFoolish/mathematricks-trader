# Mathematricks Trader - Integration Tests

## Overview

This directory contains the integration test suite for the Mathematricks Trader system. These tests verify the complete signal-to-execution pipeline and all major system components.

## ⚠️ CRITICAL TEST WRITING PRINCIPLE

**TESTS MUST IMPORT FROM MAIN CODE - NEVER HARDCODE LOGIC**

- ✅ **DO:** Import functions, classes, and utilities from the main codebase
- ✅ **DO:** Test the actual code that runs in production
- ✅ **DO:** Use pytest fixtures for shared test setup
- ❌ **DON'T:** Rewrite business logic in test files
- ❌ **DON'T:** Hardcode calculations, algorithms, or data transformations
- ❌ **DON'T:** Duplicate code from services into tests

### Example

```python
# ❌ BAD - Hardcoded logic in test
def test_position_sizing():
    equity = 250000
    allocation = 0.13
    position_size = equity * allocation * 0.05  # Hardcoded calculation
    assert position_size == 1625

# ✅ GOOD - Import from main code
from services.cerebro_service.main import calculate_position_size

def test_position_sizing():
    signal = create_test_signal()
    account_state = create_test_account_state()
    result = calculate_position_size(signal, account_state)
    assert result['final_quantity'] > 0
```

## Prerequisites

### Services Must Be Running

Before running tests, ensure all services are started:

```bash
./run_mvp_demo.sh
```

This starts:
- **CerebroService** (port 8001)
- **AccountDataService** (port 8002)
- **ExecutionService** (port 8003)
- **Google Pub/Sub Emulator** (port 8085)
- **signal_collector.py** (MongoDB change streams)

### Dependencies

Install test dependencies:

```bash
pip install -r tests/requirements.txt
```

## Running Tests

### Run All Tests

```bash
./tests/run_tests.sh
```

This will:
1. Check if services are running
2. Install test dependencies
3. Run all integration tests (stops after 5 failures by default)
4. Generate HTML report in `tests/reports/test_report.html`
5. Open report in browser (macOS only)

**Note:** By default, tests stop after 5 failures to provide fast feedback. To run ALL tests regardless of failures:

```bash
./tests/run_tests.sh --maxfail=0
```

### Run Specific Test File

```bash
pytest tests/integration/test_01_signal_ingestion.py -v
```

### Run Specific Test Function

```bash
pytest tests/integration/test_01_signal_ingestion.py::test_signal_ingestion_from_script_to_pubsub -v
```

### Run Tests with Coverage

```bash
pytest tests/integration/ --cov=services --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py                             # Shared pytest fixtures
├── requirements.txt                        # Test dependencies
├── run_tests.sh                            # Test runner script
├── README.md                               # This file
├── integration/                            # Integration tests
│   ├── test_01_signal_ingestion.py        # Signal webhook → MongoDB → Pub/Sub
│   ├── test_02_cerebro_processing.py      # Position sizing logic
│   ├── test_03_execution_service.py       # TWS order placement
│   ├── test_04_order_fill_tracking.py     # Order fill detection
│   ├── test_05_strategy_management.py     # Strategy CRUD operations
│   ├── test_06_portfolio_optimization.py  # Portfolio constructors
│   ├── test_07_frontend_admin.py          # Frontend workflows
│   ├── test_08_dashboard_creator.py       # Dashboard JSON generation
│   ├── test_09_frontend_client.py         # Client dashboard
│   └── test_10_end_to_end_signal_flow.py  # Full pipeline test
├── unit/                                   # Unit tests (future)
├── reports/                                # Test reports (auto-generated)
└── legacy/                                 # Old tests (archived)
```

## Test Descriptions

### Test 1: Signal Ingestion
Tests the signal ingestion pipeline from TradingView webhook to Pub/Sub.

**Verifies:**
- Signal sent via `send_test_FOREX_signal.sh` reaches MongoDB
- signal_collector.py picks up signal from MongoDB Change Streams
- Signal is standardized and published to 'standardized-signals' topic
- Environment filtering (staging vs production)

### Test 2: Cerebro Processing
Tests position sizing and risk management logic in CerebroService.

**Verifies:**
- Position sizing calculation based on allocation %
- Margin limit enforcement (40% max in MVP)
- Smart position sizing (dividing allocation across estimated positions)
- EXIT signal handling
- Decision record creation

### Test 3: Execution Service (To Be Written)
Tests order placement and TWS integration.

### Test 4: Order Fill Tracking (To Be Written)
Tests order fill detection and position updates.

### Test 5: Strategy Management (To Be Written)
Tests strategy CRUD operations via CerebroService API.

### Test 6: Portfolio Optimization (To Be Written)
Tests portfolio construction algorithms (MaxHybrid, MaxSharpe, MaxCAGR).

### Test 7: Frontend Admin (To Be Written)
Tests frontend-admin UI workflows.

### Test 8: Dashboard Creator (To Be Written)
Tests dashboard JSON generation service.

### Test 9: Frontend Client (To Be Written)
Tests frontend-client dashboard display.

### Test 10: End-to-End Signal Flow (To Be Written)
Tests complete pipeline from signal to execution.

## Shared Fixtures (conftest.py)

### MongoDB Fixtures
- `mongodb_client` - MongoDB Atlas connection
- `signals_collection` - trading_signals collection
- `strategies_collection` - strategies collection
- `orders_collection` - orders collection
- `account_state_collection` - account_state collection

### Pub/Sub Fixtures
- `pubsub_publisher` - Pub/Sub publisher client (emulator)
- `pubsub_subscriber` - Pub/Sub subscriber client (emulator)

### Test Data Factories
- `test_signal_factory()` - Creates TradingView format signals
- `test_standardized_signal_factory()` - Creates Cerebro format signals

### Cleanup Fixtures
- `cleanup_test_signals(signal_id)` - Removes test signals after test
- `cleanup_test_orders(order_id)` - Removes test orders after test
- `cleanup_test_strategies(strategy_id)` - Removes test strategies after test

### Helper Functions
- `wait_for_pubsub_message(subscriber, subscription, timeout)` - Waits for Pub/Sub messages
- `wait_for_mongodb_document(collection, query, timeout)` - Waits for MongoDB documents

## Debugging Tests

### View Logs While Testing

```bash
# In separate terminals:
tail -f logs/signal_processing.log
tail -f logs/cerebro_service.log
tail -f logs/execution_service.log
tail -f logs/account_data_service.log
```

### Run Tests with Verbose Output

```bash
pytest tests/integration/ -vv --tb=long
```

### Run Single Test with Print Statements

```bash
pytest tests/integration/test_01_signal_ingestion.py::test_signal_ingestion_from_script_to_pubsub -s
```

The `-s` flag shows print() output during test execution.

## Continuous Integration (Future)

Once deployed to GCP, these tests will run:
- On every commit to `main` branch
- Before every deployment
- On a nightly schedule

## Troubleshooting

### Services Not Running

```
❌ Some services are not running!
   Run './run_mvp_demo.sh' to start all services
```

**Solution:** Start services with `./run_mvp_demo.sh`

### MongoDB Connection Failed

```
pymongo.errors.ServerSelectionTimeoutError: ...
```

**Solution:** Check MongoDB Atlas connection string in `.env` file

### Pub/Sub Emulator Not Found

```
❌ Pub/Sub Emulator is not responding at http://localhost:8085
```

**Solution:** Pub/Sub emulator is started by `run_mvp_demo.sh`. Make sure it's running.

### Test Hangs on Pub/Sub Message Wait

**Issue:** Test waits for message that never arrives

**Solution:**
1. Check if CerebroService is running and processing signals
2. Check logs: `tail -f logs/cerebro_service.log`
3. Verify Pub/Sub topics exist: `gcloud pubsub topics list --project=mathematricks-trader`

## Contributing

When adding new tests:

1. **Follow the import principle** - Never hardcode business logic
2. **Use fixtures** - Leverage shared fixtures from conftest.py
3. **Clean up after yourself** - Use cleanup fixtures to remove test data
4. **Document the test** - Add clear docstring explaining what is tested
5. **Keep tests fast** - Use appropriate timeouts, don't sleep unnecessarily
6. **Make tests deterministic** - Tests should pass/fail consistently

## Test Coverage Goals

- **Signal Ingestion:** 100% coverage
- **Cerebro Processing:** 90%+ coverage
- **Execution Service:** 85%+ coverage
- **Portfolio Optimization:** 80%+ coverage
- **End-to-End Flows:** All critical paths tested

## Other Test Scripts

In addition to the integration test suite, this directory contains utility scripts for testing:

### Signal Testers
- `signal_sender.py` - Send individual test signals to staging/production
- `live_signal_tester.py` - Live signal testing with real-time monitoring
- `comprehensive_signal_tester.py` - Comprehensive test suite v1
- `comprehensive_signal_tester_v2.py` - Comprehensive test suite v2

### Execution Testers
- `test_multiasset_execution.py` - Multi-asset execution tests

### Stress Testing
- `run_stress_test.sh` - Stress test runner

### Usage Example

```bash
# Send test signal to staging
python tests/signal_sender.py --ticker SPY --action BUY --price 450.25 --environment staging

# Run stress test
./tests/run_stress_test.sh
```

## Contact

For questions about tests, see:
- `/documentation/MathematricksTraderSystemCleanup.md` - System architecture
- `/documentation/CLAUDE.md` - Project instructions
