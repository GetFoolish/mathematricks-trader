# Signals Testing

## Overview

The signals testing framework provides tools to inject test signals into the Mathematricks Trader system for end-to-end testing. It includes sample signal templates for various asset classes and a CLI tool for sending signals to MongoDB.

## Location

`/tests/signals_testing/`

## Key Components

1. Sample signal templates for different strategies and asset classes
2. CLI tool for sending test signals (`send_test_signal.py`)
3. Signal validation and formatting utilities
4. Test signal generation helpers

## Files Structure

```
tests/signals_testing/
├── send_test_signal.py           # CLI tool for sending signals
├── sample_signals/               # Pre-built signal templates
│   ├── equity_simple_signal_1.json
│   ├── equity_ladder_signal_1.json
│   ├── equity_pairs_signal_1.json
│   ├── futures_gold_simple_signal_1.json
│   ├── futures_copper_simple_signal_1.json
│   ├── crypto_btc_simple_signal_1.json
│   ├── crypto_btc_ladder_signal_1.json
│   ├── forex_simple_signal_1.json
│   └── forex_ladder_signal_1.json
└── README.md
```

## Sample Signal Templates

### Equity Simple Signal
File: `equity_simple_signal_1.json`

Basic single-leg equity trade:
```json
{
  "strategy_name": "SPX 1-Day Options",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "SPY",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 10,
      "order_type": "MARKET",
      "stop_loss": 420.00,
      "take_profit": 435.00
    }
  ],
  "environment": "staging"
}
```

### Equity Ladder Signal
File: `equity_ladder_signal_1.json`

Multi-leg ladder strategy with scaling:
```json
{
  "strategy_name": "SPX Ladder Strategy",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "SPY",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 5,
      "order_type": "LIMIT",
      "limit_price": 430.00,
      "leg": 1
    },
    {
      "instrument": "SPY",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 5,
      "order_type": "LIMIT",
      "limit_price": 425.00,
      "leg": 2
    },
    {
      "instrument": "SPY",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 5,
      "order_type": "LIMIT",
      "limit_price": 420.00,
      "leg": 3
    }
  ],
  "environment": "staging"
}
```

### Equity Pairs Signal
File: `equity_pairs_signal_1.json`

Pairs trading (long/short):
```json
{
  "strategy_name": "Equity Pairs",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "SPY",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 100,
      "order_type": "MARKET"
    },
    {
      "instrument": "IWM",
      "action": "ENTRY",
      "direction": "SHORT",
      "quantity": 100,
      "order_type": "MARKET"
    }
  ],
  "environment": "staging"
}
```

### Futures Signal
File: `futures_gold_simple_signal_1.json`

Gold futures trade:
```json
{
  "strategy_name": "Gold Futures Strategy",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "GC",
      "secType": "FUT",
      "exchange": "NYMEX",
      "lastTradeDateOrContractMonth": "202412",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 1,
      "order_type": "MARKET",
      "stop_loss": 2000.00,
      "take_profit": 2100.00
    }
  ],
  "environment": "staging"
}
```

### Crypto Signal
File: `crypto_btc_simple_signal_1.json`

Bitcoin crypto trade:
```json
{
  "strategy_name": "BTC Swing Strategy",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "BTC",
      "secType": "CRYPTO",
      "exchange": "PAXOS",
      "currency": "USD",
      "action": "ENTRY",
      "direction": "LONG",
      "cashQty": 10000.00,
      "order_type": "MARKET"
    }
  ],
  "environment": "staging"
}
```

### Forex Signal
File: `forex_simple_signal_1.json`

EUR/USD forex trade:
```json
{
  "strategy_name": "Forex Pairs Strategy",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "EUR",
      "secType": "CASH",
      "exchange": "IDEALPRO",
      "currency": "USD",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 20000,
      "order_type": "MARKET"
    }
  ],
  "environment": "staging"
}
```

## send_test_signal.py CLI Tool

### Basic Usage

```bash
# Send signal from file
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json

# Send signal with custom strategy name
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json --strategy "My Test Strategy"

# List available sample signals
python send_test_signal.py --list

# Send signal to production environment
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json --environment production
```

### Command-Line Arguments

```
--file FILE               Path to signal JSON file
--strategy STRATEGY       Override strategy name
--environment ENV         Set environment (staging or production)
--list                    List available sample signals
--verbose                 Enable verbose logging
--dry-run                 Validate signal without sending
```

### Examples

**1. Send Simple Equity Signal**
```bash
cd tests/signals_testing
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json
```

Output:
```
Sending signal to MongoDB...
Signal sent successfully!
Signal ID: sig_1732450800_5678
Strategy: SPX 1-Day Options
Environment: staging
```

**2. Send Multiple Signals Sequentially**
```bash
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json
sleep 5
python send_test_signal.py --file sample_signals/crypto_btc_simple_signal_1.json
sleep 5
python send_test_signal.py --file sample_signals/futures_gold_simple_signal_1.json
```

**3. Dry Run (Validate Only)**
```bash
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json --dry-run
```

Output:
```
Validating signal...
Signal is valid!
Structure: ✓
Required fields: ✓
Instrument format: ✓

[Dry run - signal not sent]
```

**4. List Available Templates**
```bash
python send_test_signal.py --list
```

Output:
```
Available sample signals:
1. equity_simple_signal_1.json - Basic equity trade
2. equity_ladder_signal_1.json - Multi-leg ladder strategy
3. equity_pairs_signal_1.json - Pairs trading
4. futures_gold_simple_signal_1.json - Gold futures
5. futures_copper_simple_signal_1.json - Copper futures
6. crypto_btc_simple_signal_1.json - Bitcoin spot
7. forex_simple_signal_1.json - EUR/USD forex
```

## Signal Structure

### Required Fields

All signals must include:
- `strategy_name` - Name of the strategy sending the signal
- `timestamp` - ISO 8601 formatted timestamp
- `signal` - Array of signal legs
- `environment` - "staging" or "production"

### Signal Leg Fields

Each signal leg must include:
- `instrument` - Symbol/ticker
- `action` - "ENTRY" or "EXIT"
- `direction` - "LONG" or "SHORT" (for ENTRY)
- `order_type` - "MARKET", "LIMIT", "STOP", "STOP_LIMIT"

Optional fields:
- `quantity` - Number of shares/contracts (for non-crypto)
- `cashQty` - USD amount (for crypto)
- `limit_price` - Price for limit orders
- `stop_loss` - Stop loss price
- `take_profit` - Take profit price
- `secType` - Security type (STK, FUT, OPT, CRYPTO, CASH)
- `exchange` - Exchange name
- `currency` - Currency code
- `lastTradeDateOrContractMonth` - For futures/options

## Testing Workflow

### 1. Start Services
```bash
python mvp_demo_start.py
```

### 2. Send Test Signal
```bash
cd tests/signals_testing
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json
```

### 3. Monitor Signal Flow
```bash
# Watch unified signal journey
tail -f logs/signal_processing.log

# Watch specific services
tail -f logs/signal_ingestion.log
tail -f logs/cerebro_service.log
tail -f logs/execution_service.log
```

### 4. Check Signal in MongoDB
```bash
mongosh
use mathematricks_trading

# Find signal by ID
db.signal_store.findOne({"signal_id": "sig_1732450800_5678"})

# Check Cerebro decision
db.signal_store.findOne(
  {"signal_id": "sig_1732450800_5678"},
  {"cerebro_decision": 1}
)

# Check execution
db.execution_confirmations.findOne({"signal_id": "sig_1732450800_5678"})
```

### 5. Verify Position
```bash
# Check open positions
db.positions.find({"status": "OPEN"})

# Check account balances
db.trading_accounts.findOne({}, {"balances": 1, "open_positions": 1})
```

## Creating Custom Test Signals

### Template
```json
{
  "strategy_name": "Your Strategy Name",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "SYMBOL",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 100,
      "order_type": "MARKET"
    }
  ],
  "environment": "staging"
}
```

### Tips

1. **Use staging environment for testing**
   - Set `"environment": "staging"`
   - Prevents production trades

2. **Start with simple signals**
   - Single-leg market orders
   - Known liquid symbols (SPY, AAPL)

3. **Test edge cases**
   - Invalid symbols
   - Large quantities (test rejection)
   - After-hours signals

4. **Use realistic timestamps**
   - Current time for immediate processing
   - Future time for scheduled signals

## Signal Validation

### Automated Checks

The `send_test_signal.py` tool validates:
- JSON structure
- Required fields present
- Valid action values (ENTRY/EXIT)
- Valid direction values (LONG/SHORT)
- Valid order types
- Timestamp format

### Manual Validation

Check signal before sending:
```bash
python send_test_signal.py --file my_signal.json --dry-run
```

## Troubleshooting

### Signal Not Detected

**Issue:** Signal sent but not processed

**Check:**
1. Signal Ingestion Service is running
2. MongoDB replica set is active
3. Signal has correct `environment` field
4. Check `trading_signals_raw` collection:
   ```bash
   db.trading_signals_raw.find().sort({_id: -1}).limit(1)
   ```

### Signal Rejected by Cerebro

**Issue:** Signal processed but rejected

**Check:**
1. Account has sufficient margin
2. Symbol is valid for broker
3. Quantity meets minimum requirements
4. Check Cerebro decision in `signal_store`:
   ```bash
   db.signal_store.findOne(
     {"signal_id": "sig_xxx"},
     {"cerebro_decision": 1}
   )
   ```

### Order Not Placed

**Issue:** Signal approved but order not placed

**Check:**
1. Execution Service is running
2. Broker connection is active
3. Check `execution_confirmations` collection
4. Look for errors in `execution_service.log`

### Order Rejected by Broker

**Issue:** Order sent but broker rejects

**Common Reasons:**
- Insufficient margin
- Invalid symbol
- Market closed
- Lot size error (futures/options)
- Exchange not supported

**Check:**
```bash
db.execution_confirmations.findOne(
  {"signal_id": "sig_xxx"},
  {"status": 1, "rejection_reason": 1}
)
```

## Performance Testing

### Stress Testing

Send multiple signals in quick succession:
```bash
for i in {1..10}; do
  python send_test_signal.py --file sample_signals/equity_simple_signal_1.json
  sleep 1
done
```

Monitor:
- Signal processing latency
- System resource usage
- Database performance
- Order placement rate

### Latency Testing

Measure end-to-end signal latency:
```python
import time

# Send signal
start = time.time()
send_signal()

# Wait for fill
while not is_filled():
    time.sleep(0.1)

latency = time.time() - start
print(f"End-to-end latency: {latency:.2f}s")
```

## Related Documentation

- [Signal Ingestion Service](signal_ingestion.md) - Processes test signals
- [Cerebro Service](cerebro_service.md) - Analyzes test signals
- [Execution Service](execution_service.md) - Executes test orders
- [Brokers](brokers.md) - Use Mock broker for safe testing

## Best Practices

1. **Always use staging environment for testing**
   - Prevents accidental production trades
   - Safe to test with real brokers

2. **Start services before sending signals**
   - Run `mvp_demo_start.py` first
   - Verify all services are healthy

3. **Monitor logs during testing**
   - Watch `signal_processing.log`
   - Check for errors immediately

4. **Use Mock broker for initial testing**
   - No real money risk
   - Fast feedback
   - Switch to real broker after validation

5. **Clean up test data**
   - Remove test signals from MongoDB
   - Close test positions
   - Reset account state

6. **Document test cases**
   - Create named signal templates
   - Include expected outcomes
   - Track edge cases

## Safety Considerations

- **Never send test signals to production without explicit approval**
- **Use appropriate position sizes for testing**
- **Monitor account balances during testing**
- **Have emergency stop procedures ready**
- **Keep test and production environments separate**
- **Use different accounts for testing when possible**

## Future Enhancements

1. **Automated Test Suites**
   - Pytest integration
   - Automated signal generation
   - Expected outcome validation

2. **Signal Replay**
   - Replay historical signals
   - Backtesting integration
   - Performance comparison

3. **Load Testing**
   - High-volume signal generation
   - Concurrent signal processing
   - System limits discovery

4. **Signal Templates Library**
   - More asset classes
   - Complex multi-leg strategies
   - Edge case scenarios
