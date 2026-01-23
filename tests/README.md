# Test Framework Documentation

## Overview

This test framework provides comprehensive testing capabilities for the Mathematricks Trader system, covering unit tests, integration tests, and end-to-end scenarios.

## Directory Structure

```
tests/
├── conftest.py                 # Root pytest configuration and fixtures
├── pytest.ini                  # Pytest settings (in project root)
│
├── unit/                       # Unit tests (isolated component tests)
│   ├── test_signal_ingestion.py
│   ├── test_execution_service.py
│   └── ...
│
├── integration/                # Integration tests (multi-component)
│   ├── test_signal_flow_integration.py
│   └── ...
│
├── e2e/                        # End-to-end tests (complete workflows)
│   ├── test_trade_scenarios.py
│   └── ...
│
├── fixtures/                   # Test fixtures
│   ├── broker_fixtures.py     # Broker-related fixtures
│   ├── database_fixtures.py   # Database fixtures
│   └── ...
│
├── mocks/                      # Mock implementations
│   ├── mock_services.py       # Mock services for testing
│   └── ...
│
├── helpers/                    # Test helpers and utilities
│   ├── test_utils.py          # General utilities
│   ├── db_helpers.py          # Database helpers
│   └── data_generators.py     # Test data generators
│
├── test_data/                  # Test data files
│   └── generated/             # Generated test data
│
├── test_output/               # Test output files
│
└── signals_testing/           # Legacy signal testing (kept for compatibility)
    ├── run_full_test.py
    └── sample_signals_*/
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# End-to-end tests only
pytest -m e2e

# Slow tests
pytest -m slow

# Critical tests
pytest -m critical
```

### Run Specific Test Files
```bash
# Single file
pytest tests/unit/test_signal_ingestion.py

# Multiple files
pytest tests/unit/ tests/integration/
```

### Run Tests with Coverage
```bash
pytest --cov=services --cov-report=html
```

### Run Tests in Parallel
```bash
pip install pytest-xdist
pytest -n auto
```

### Run with Verbose Output
```bash
pytest -v
pytest -vv  # Extra verbose
```

## Test Markers

The framework provides several markers to categorize tests:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Tests that take > 10 seconds
- `@pytest.mark.broker` - Tests requiring broker connection
- `@pytest.mark.database` - Tests requiring database
- `@pytest.mark.docker` - Tests requiring Docker services
- `@pytest.mark.smoke` - Quick smoke tests
- `@pytest.mark.critical` - Critical path tests

### Example Usage
```python
@pytest.mark.unit
@pytest.mark.critical
def test_signal_validation():
    # Test code here
    pass
```

## Fixtures

### Database Fixtures

```python
def test_with_clean_db(clean_signals_collection):
    """Use clean signals collection"""
    clean_signals_collection.insert_one({"test": "data"})
```

Available database fixtures:
- `mongo_client` - MongoDB client
- `test_db` - Test database (auto-cleanup)
- `signals_collection` - Signals collection
- `strategies_collection` - Strategies collection
- `positions_collection` - Positions collection
- `orders_collection` - Orders collection
- `accounts_collection` - Accounts collection
- `clean_*_collection` - Pre-cleaned collections

### Broker Fixtures

```python
def test_with_mock_broker(mock_ibkr_gateway):
    """Use mock broker gateway"""
    order = mock_ibkr_gateway.place_order("AAPL", "BUY", 100)
```

Available broker fixtures:
- `mock_ibkr_gateway` - Mock IBKR gateway
- `mock_ib_client` - Mock IB client
- `sample_ibkr_order_filled` - Sample filled order
- `sample_ibkr_position` - Sample position
- `broker_error_responses` - Common error responses

### Sample Data Fixtures

```python
def test_with_sample_data(sample_signal, sample_strategy):
    """Use pre-defined sample data"""
    assert sample_signal["strategy_id"] == sample_strategy["strategy_id"]
```

Available sample data:
- `sample_signal` - Sample signal
- `sample_strategy` - Sample strategy
- `sample_account` - Sample account
- `sample_position` - Sample position
- `sample_order` - Sample order
- `sample_signals_batch` - Batch of signals
- `sample_strategies_batch` - Batch of strategies

## Test Helpers

### Signal Generator

```python
from tests.helpers.test_utils import SignalGenerator

def test_generate_signals():
    generator = SignalGenerator(strategy_id="test_123")
    
    # Generate entry signal
    entry = generator.generate_entry_signal("AAPL", price=150.00)
    
    # Generate exit signal
    exit_signal = generator.generate_exit_signal("AAPL", price=155.00)
    
    # Generate paired signals
    entry, exit_signal = generator.generate_signal_pair("AAPL")
```

### Data Generators

```python
from tests.helpers.data_generators import (
    SignalDataGenerator,
    MarketDataGenerator,
    StrategyDataGenerator
)

def test_with_generated_data():
    # Generate signal file
    gen = SignalDataGenerator()
    signal_file = gen.generate_signal_file("AAPL", num_pairs=10)
    
    # Generate market data
    ohlcv_data = MarketDataGenerator.generate_ohlcv_data("AAPL", days=30)
    
    # Generate strategies
    strategies = StrategyDataGenerator.generate_strategies(5)
```

### Database Helpers

```python
from tests.helpers.db_helpers import DatabaseTestHelper

def test_with_db_helper(test_db):
    helper = DatabaseTestHelper(test_db)
    
    # Seed data
    helper.seed_signals([signal1, signal2])
    
    # Assertions
    helper.assert_signal_exists("sig_123")
    
    # Wait for status
    helper.wait_for_signal_status("sig_123", "PROCESSED", timeout=10)
```

### Assertion Helpers

```python
from tests.helpers.test_utils import AssertionHelper

def test_with_assertions(sample_signal):
    # Validate signal structure
    AssertionHelper.assert_signal_valid(sample_signal)
    
    # Check datetime is recent
    AssertionHelper.assert_datetime_recent(sample_signal["timestamp"])
    
    # Check dict contains expected fields
    AssertionHelper.assert_dict_contains(
        sample_signal,
        {"symbol": "AAPL", "action": "ENTRY"}
    )
```

## Writing Tests

### Unit Test Example

```python
import pytest
from tests.helpers.test_utils import SignalGenerator

@pytest.mark.unit
class TestSignalValidation:
    
    def test_valid_signal(self, sample_signal):
        """Test valid signal passes validation"""
        assert "signal_id" in sample_signal
        assert "strategy_id" in sample_signal
        assert sample_signal["action"] in ["ENTRY", "EXIT"]
    
    def test_invalid_signal(self):
        """Test invalid signal fails validation"""
        invalid = {"symbol": "AAPL"}  # Missing required fields
        
        required = ["signal_id", "strategy_id", "action", "timestamp"]
        is_valid = all(field in invalid for field in required)
        
        assert not is_valid
```

### Integration Test Example

```python
import pytest
from tests.helpers.db_helpers import DatabaseTestHelper

@pytest.mark.integration
@pytest.mark.database
class TestSignalStorage:
    
    def test_store_and_retrieve(self, test_db, sample_signal):
        """Test storing and retrieving signals"""
        # Store
        test_db.signals.insert_one(sample_signal)
        
        # Retrieve
        stored = test_db.signals.find_one(
            {"signal_id": sample_signal["signal_id"]}
        )
        
        assert stored is not None
        assert stored["symbol"] == sample_signal["symbol"]
```

### End-to-End Test Example

```python
import pytest
from tests.helpers.test_utils import SignalGenerator

@pytest.mark.e2e
class TestCompleteTradeFlow:
    
    def test_full_trade_lifecycle(
        self,
        test_db,
        sample_strategy,
        sample_account,
        mock_ibkr_gateway
    ):
        """Test complete trade from signal to position close"""
        # Setup
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        # Generate signal
        generator = SignalGenerator(sample_strategy["strategy_id"])
        entry = generator.generate_entry_signal("AAPL", price=150.00)
        
        # Process signal -> order -> position
        test_db.signals.insert_one(entry)
        order = mock_ibkr_gateway.place_order("AAPL", "BUY", 100)
        mock_ibkr_gateway.fill_order(order["order_id"], 150.05)
        
        # Verify
        assert order["status"] == "FILLED"
```

## Test Data Generation

### Generate Complete Dataset

```python
from tests.helpers.data_generators import generate_complete_test_dataset

# Generate all test data
dataset = generate_complete_test_dataset()

# Returns paths to generated files:
# - Signal files for multiple symbols
# - Edge case signals
# - Strategies configuration
# - Accounts configuration
# - Market data files
```

### Generate Custom Signals

```python
from tests.helpers.data_generators import SignalDataGenerator

generator = SignalDataGenerator()

# Single symbol
signal_file = generator.generate_signal_file("AAPL", num_pairs=10)

# Multiple symbols
files = generator.generate_batch_signal_files(
    ["AAPL", "GOOGL", "MSFT"],
    signals_per_symbol=20
)

# Edge cases
edge_cases = generator.generate_edge_case_signals()
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest -m "unit or integration" --cov=services
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Use fixtures with cleanup to ensure clean state
3. **Markers**: Tag tests appropriately for easy filtering
4. **Naming**: Use descriptive test names that explain what is being tested
5. **AAA Pattern**: Arrange, Act, Assert structure in tests
6. **Mocking**: Mock external dependencies (brokers, APIs) for unit tests
7. **Real Integration**: Use real database for integration tests (with cleanup)
8. **Fast Tests**: Keep unit tests fast (<1s), mark slow tests appropriately

## Troubleshooting

### Tests Can't Find Modules
```bash
# Make sure you're running from project root
cd /path/to/project
pytest

# Or explicitly set PYTHONPATH
PYTHONPATH=. pytest
```

### Database Connection Issues
```bash
# Ensure MongoDB is running
docker ps | grep mongo

# Check connection string
echo $MONGO_URI
```

### Slow Test Runs
```bash
# Run only fast tests
pytest -m "not slow"

# Run tests in parallel
pytest -n auto

# Run specific subsection
pytest tests/unit/
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [pytest-xdist](https://pytest-xdist.readthedocs.io/)
