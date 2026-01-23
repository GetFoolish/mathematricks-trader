# 4-Mode Signal Testing Framework

Progressive testing framework for the 4-mode trading system.

## Directory Structure

```
tests/signal_testing_v2/
├── run_all_modes.py          # Main test runner
├── test_framework.py          # Test utilities and framework
├── README.md                  # This file
├── config/                    # Mode configurations
│   ├── mock_mock.json
│   ├── mock_live.json
│   ├── paper_live.json
│   └── live_live.json
└── signals/                   # Test signals organized by category
    ├── basic/                 # Basic order tests (8)
    ├── edge_cases/            # Edge case tests (10)
    ├── multi_leg/             # Multi-leg strategy tests (6)
    ├── position_management/   # Position management tests (8)
    ├── risk/                  # Risk management tests (6)
    ├── real_world/            # Real-world scenario tests (8)
    ├── data_quality/          # Data quality tests (4)
    └── stress/                # System stress tests (4)
```

## Trading Modes

### 1. mock_mock (Development)
- **Account Type**: Mock
- **Data Source**: Mock data
- **Use Case**: Fast development and unit testing
- **Duration**: Seconds
- **Gateway Required**: No

### 2. mock_live (Strategy Testing)
- **Account Type**: Mock
- **Data Source**: Live market data
- **Use Case**: Test strategies with real market data without risk
- **Duration**: 1-2 minutes
- **Gateway Required**: Yes (for live data)

### 3. paper_live (IBKR Paper Trading)
- **Account Type**: IBKR Paper (port 4004)
- **Data Source**: Live market data
- **Use Case**: True paper trading on IBKR infrastructure
- **Duration**: 5-10 minutes
- **Gateway Required**: Yes

### 4. live_live (Production)
- **Account Type**: Live
- **Data Source**: Live market data
- **Use Case**: Production trading - REAL MONEY
- **Duration**: Varies
- **Gateway Required**: Yes
- **⚠️ Requires Manual Approval**

## Usage

### Run All Tests Through All Modes

```bash
python tests/signal_testing_v2/run_all_modes.py --all
```

### Run Specific Mode Only

```bash
# Fast testing with mock data
python tests/signal_testing_v2/run_all_modes.py --mode mock_mock

# Test with live data, mock account
python tests/signal_testing_v2/run_all_modes.py --mode mock_live

# Test on IBKR paper account
python tests/signal_testing_v2/run_all_modes.py --mode paper_live
```

### Progressive Testing (Recommended)

```bash
# Run tests up to paper_live (skips live_live)
python tests/signal_testing_v2/run_all_modes.py --up-to paper_live
```

### Test Specific Signal

```bash
# Test single signal in all modes
python tests/signal_testing_v2/run_all_modes.py --test signals/basic/simple_entry_exit.json --all

# Test single signal in specific mode
python tests/signal_testing_v2/run_all_modes.py --test signals/basic/market_order.json --mode mock_mock
```

### Test by Category

```bash
# Test all basic orders in mock_live mode
python tests/signal_testing_v2/run_all_modes.py --category basic --mode mock_live

# Test all edge cases progressively
python tests/signal_testing_v2/run_all_modes.py --category edge_cases --up-to paper_live
```

## Test Categories

### 1. Basic Orders (8 tests)
- `simple_entry_exit.json` - Single stock entry and exit
- `market_order.json` - Market order execution
- `limit_order.json` - Limit order placement
- `stop_order.json` - Stop loss orders
- `stop_limit_order.json` - Stop limit combinations
- `bracket_order.json` - Bracket orders (entry + targets)
- `oco_order.json` - One-cancels-other
- `good_till_cancelled.json` - GTC orders

### 2. Edge Cases (10 tests)
- `rapid_signals.json` - Multiple signals within seconds
- `duplicate_signals.json` - Same signal_id sent twice
- `partial_fills.json` - Large orders that fill partially
- `rejected_orders.json` - Invalid symbols, insufficient funds
- `market_closed.json` - Orders outside market hours
- `invalid_symbol.json` - Non-existent tickers
- `insufficient_funds.json` - Over-leveraged positions
- `extreme_price_movement.json` - Flash crash scenarios
- `connection_loss.json` - Network interruptions
- `order_cancellation.json` - Cancel before fill

### 3-8. Additional Categories
(Position Management, Risk Management, Real-World Scenarios, etc.)

## Creating New Test Signals

Signal files are JSON with template variables:

```json
{
  "signal_id": "test_my_signal_{{timestamp}}",
  "strategy_id": "test_strategy_1",
  "account_id": "IBKR-TESTING-ACCOUNT",
  "instrument": "AAPL",
  "instrument_type": "STOCK",
  "signal_type": "ENTRY",
  "direction": "LONG",
  "signal_time": "{{current_time}}",
  "quantity": 1,
  "metadata": {
    "test_name": "my_custom_test",
    "test_category": "basic",
    "description": "Description of what this test validates"
  }
}
```

### Template Variables
- `{{timestamp}}` - Current Unix timestamp
- `{{current_time}}` - ISO format datetime
- `{{account_id}}` - Dynamically set based on mode

## Pre-Flight Checklist

Before running tests:

1. ✅ MongoDB is running
2. ✅ Services are up (signal ingestion, execution)
3. ✅ IBKR Gateway running (for mock_live, paper_live, live_live)
4. ✅ Account credentials configured
5. ✅ Test account has sufficient balance

## Expected Test Flow

```
1. Send signal to signal ingestion API
2. Wait for signal processing
3. Verify order creation in MongoDB
4. Check order status (FILLED, SUBMITTED, PENDING)
5. Record result (success/failure, duration, errors)
```

## Troubleshooting

### Tests Fail in mock_mock
- Check MongoDB connection
- Verify signal ingestion service is running
- Check signal format/validation

### Tests Fail in mock_live
- Ensure IBKR Gateway is connected
- Verify live market data access
- Check symbol validity

### Tests Fail in paper_live
- Verify IBKR paper account credentials
- Check port 4004 connection
- Ensure paper account has margin/buying power

## Safety Features

1. **Mode Validation**: Tests verify account is in correct mode before running
2. **Progressive Stoppage**: If a mode fails, testing stops (doesn't proceed to next mode)
3. **Production Guard**: live_live mode requires explicit confirmation
4. **Rollback**: Tests don't modify permanent data (use test account only)

## Best Practices

1. **Always start with mock_mock** - Fast feedback on signal format issues
2. **Use progressive testing** - Catch issues early before production
3. **Test during market hours** - For mock_live and paper_live modes
4. **Monitor logs** - Check service logs during test execution
5. **Clean up test data** - Clear test signals/orders between runs

## Integration with CI/CD

```yaml
# Example GitHub Actions workflow
- name: Run Signal Tests
  run: |
    # Fast tests in CI
    python tests/signal_testing_v2/run_all_modes.py --mode mock_mock
    
    # Extended tests (optional)
    # python tests/signal_testing_v2/run_all_modes.py --up-to mock_live
```

## Future Enhancements

- [ ] Parallel test execution
- [ ] Test result persistence to MongoDB
- [ ] Performance benchmarking per mode
- [ ] Automated test signal generation
- [ ] Test coverage reporting
- [ ] Integration with monitoring/alerting

---

**Version:** 1.0  
**Last Updated:** January 21, 2026  
**Status:** Active
