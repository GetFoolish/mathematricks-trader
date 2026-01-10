# Signals Testing

The Signals Testing infrastructure provides tools for testing the trading system end-to-end by sending realistic test signals and validating the entire signal processing pipeline.

## Table of Contents
- [Overview](#overview)
- [Test Scripts](#test-scripts)
- [Test Signals](#test-signals)
- [Workflow](#workflow)
- [Usage](#usage)
- [Best Practices](#best-practices)

---

## Overview

### Purpose
- **End-to-End Testing**: Validate entire signal processing pipeline
- **Realistic Scenarios**: Test with real-world signal patterns
- **Performance Testing**: Measure system throughput
- **Regression Testing**: Ensure changes don't break existing functionality

### Technology Stack
- **Python 3.11+**
- **PyMongo** (direct MongoDB insertion)
- **JSON** (signal format)

### Location
```
tests/signals_testing/
├── send_test_signal.py            # CLI tool to send signals
├── run_full_test.py               # Automated test suite runner
├── sample_signals/                # Test signal JSON files
│   ├── spy_realistic.json
│   ├── com1_met_realistic.json
│   ├── florida_forex_realistic.json
│   └── ...
├── STRATEGY_INVENTORY.md          # Catalog of test strategies
└── TESTING_QUICKSTART.md          # Quick start guide
```

---

## Test Scripts

### 1. `send_test_signal.py`
**Purpose**: Send individual test signals to MongoDB

**Features**:
- Direct MongoDB insertion (bypasses webhook)
- Supports ENTRY/EXIT signal pairs
- Placeholder resolution (`$ENTRY_1` → actual signal ID)
- Sequential signal sending with wait times
- Environment support (staging/production)

**Usage**:
```bash
# Send single signal
python send_test_signal.py --file sample_signals/spy_realistic.json

# Send all signals from folder
python send_test_signal.py --folder sample_signals/

# Send with custom seed (reproducible shuffling)
python send_test_signal.py --folder sample_signals/ --seed 42

# Send with custom delay between signals
python send_test_signal.py --folder sample_signals/ --delay 10
```

**CLI Options**:
```
--file FILE           Path to JSON signal file
--folder FOLDER       Path to folder containing *.json files
--seed SEED           Random seed (positive=reproducible, 0=random, negative=no shuffle)
--delay SECONDS       Delay between signals (default: use signal's wait value)
--list-strategies     List available strategies from MongoDB
```

### 2. `run_full_test.py`
**Purpose**: Automated test suite with result tracking

**Features**:
- Runs all signals from folder
- Saves test results to JSON
- Measures duration and success rate
- Generates timestamped result files

**Usage**:
```bash
# Run full test suite (default: sample_signals/)
python run_full_test.py

# Run with specific folder
python run_full_test.py --folder sample_signals/

# Run with custom seed and delay
python run_full_test.py --seed 42 --delay 10

# Run limited number of signals
python run_full_test.py --signal_count 5

# Interactive mode (pause after each signal)
python run_full_test.py --pause-and-play
```

**Output**:
```
test_results/
└── test_run_20260109_212657_results.json
```

**Result Format**:
```json
{
    "run_id": "test_run_20260109_212657",
    "timestamp": "2026-01-09T21:26:57Z",
    "folder": "sample_signals",
    "seed": 1,
    "delay": 10,
    "status": "success",
    "signals_sent": 45,
    "duration_seconds": 31.09,
    "start_time": "2026-01-09T21:26:57Z",
    "end_time": "2026-01-09T21:27:28Z"
}
```

---

## Test Signals

### Signal Format

**ENTRY Signal Example** ([spy_realistic.json](../tests/signals_testing/sample_signals/spy_realistic.json)):
```json
[
    {
        "strategy_name": "SPY",
        "signal_type": "ENTRY",
        "signal_sent_EPOCH": 1735980000,
        "signalID": "sig_spy_001",
        "entry_name": "$SPY_1",          // Placeholder for test runner
        "account_equity": 100000,
        "signal_legs": [
            {
                "instrument": "SPY",
                "instrument_type": "STOCK",
                "action": "BUY",
                "direction": "LONG",
                "quantity": 100,
                "order_type": "MARKET",
                "price": 450.25,
                "stop_loss": 445.00,
                "take_profit": 460.00
            }
        ],
        "environment": "staging",
        "staging": true,
        "wait": 6                         // Wait 6 seconds before next signal
    },
    {
        "strategy_name": "SPY",
        "signal_type": "EXIT",
        "signal_sent_EPOCH": 1735980060,
        "signalID": "sig_spy_002",
        "entry_signal_id": "$SPY_1",     // Links to ENTRY via placeholder
        "signal_legs": [
            {
                "instrument": "SPY",
                "instrument_type": "STOCK",
                "action": "SELL",
                "direction": "LONG",
                "quantity": 100,
                "order_type": "MARKET",
                "price": 455.50
            }
        ],
        "environment": "staging",
        "staging": true,
        "wait": 6
    }
]
```

### Placeholder System

**Problem**: EXIT signals need to reference their ENTRY signal ID, but we don't know the ID until the ENTRY is sent.

**Solution**: Use placeholders that get resolved at runtime

**How it works**:
1. ENTRY signal has `entry_name: "$SPY_1"`
2. Test runner sends ENTRY, gets back `signalID: "sig_spy_001"`
3. Test runner registers: `$SPY_1` → `sig_spy_001`
4. EXIT signal has `entry_signal_id: "$SPY_1"`
5. Test runner resolves `$SPY_1` → `sig_spy_001` before sending EXIT

**Unique Placeholders** (v5):
To prevent collisions across files, each file uses unique prefixes:
- `spy_realistic.json`: `$SPY_1`, `$SPY_2`, etc.
- `com1_met_realistic.json`: `$COM1_MET_1`, `$COM1_MET_2`, etc.
- `florida_forex_realistic.json`: `$FLORIDA_FOREX_1`, etc.

### Available Test Signals

**Equity Strategies**:
- [spy_realistic.json](../tests/signals_testing/sample_signals/spy_realistic.json) - S&P 500 ETF signals
- [tlt_realistic.json](../tests/signals_testing/sample_signals/tlt_realistic.json) - Treasury Bond ETF signals

**Futures Strategies**:
- [com1_met_realistic.json](../tests/signals_testing/sample_signals/com1_met_realistic.json) - Metals futures (GC, SI)
- [com2_ag_realistic.json](../tests/signals_testing/sample_signals/com2_ag_realistic.json) - Agricultural futures (ZW, ZC, ZS)
- [com3_mkt_realistic.json](../tests/signals_testing/sample_signals/com3_mkt_realistic.json) - Market futures (ES, NQ)
- [com4_misc_realistic.json](../tests/signals_testing/sample_signals/com4_misc_realistic.json) - Misc futures (CL, NG)

**Options Strategies**:
- [spx_0de_opt_realistic.json](../tests/signals_testing/sample_signals/spx_0de_opt_realistic.json) - 0DTE SPX options
- [spx_1d_opt_realistic.json](../tests/signals_testing/sample_signals/spx_1d_opt_realistic.json) - 1-day SPX options

**Forex Strategies**:
- [florida_forex_realistic.json](../tests/signals_testing/sample_signals/florida_forex_realistic.json) - Forex pairs (EUR/USD, GBP/USD)

---

## Workflow

### Complete Testing Workflow

```
1. CLEAR TEST DATA
   ↓
   python scripts/junk/clear_test_data.py
   - Deletes trading_signals_raw, signal_store, trading_orders
   - Resets account balances to initial_equity
   - Restarts execution-service (clears in-memory state)

2. RUN TEST SUITE
   ↓
   python tests/signals_testing/run_full_test.py --folder sample_signals --delay 10
   - Loads all *.json files from sample_signals/
   - Shuffles signals (respecting ENTRY before EXIT constraint)
   - Sends signals with 10-second delays
   - Tracks results

3. SIGNAL PROCESSING
   ↓
   Each signal goes through:
   a) Signal Ingestion → Creates signal_store document
   b) Cerebro → Adds decision{}, creates trading_orders
   c) Execution → Executes orders, updates positions
   d) Updates signal_store with execution data

4. VERIFY RESULTS
   ↓
   - Check test_results/test_run_*.json for summary
   - Check MongoDB for:
     * signal_store: All signals processed?
     * trading_orders: All orders filled?
     * trading_accounts: Positions updated?
   - Check logs for errors

5. ANALYZE RESULTS
   ↓
   - Review rejected signals (if any)
   - Check P&L calculations
   - Verify position tracking
   - Validate margin usage
```

---

## Usage

### Quick Start

```bash
# 1. Clear previous test data
python scripts/junk/clear_test_data.py

# 2. Run full test suite
python tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals --delay 10

# 3. Check results
cat test_results/test_run_*.json
```

### Via Makefile

```bash
# Run full test (clears data + runs test)
make test-signals

# Just clear test data
make clear-test-data

# Send single test signal
make send-test-signal
```

### Custom Test Scenarios

#### Test Specific Strategy
```bash
# Send only SPY signals
python send_test_signal.py --file sample_signals/spy_realistic.json
```

#### Test with Reproducible Seed
```bash
# Same signal order every run
python run_full_test.py --seed 42
```

#### Test with Random Order
```bash
# Different order each run
python run_full_test.py --seed 0
```

#### Test Limited Signals
```bash
# Only send first 5 signals
python run_full_test.py --signal_count 5
```

#### Interactive Testing
```bash
# Pause after each signal (press Enter to continue)
python run_full_test.py --pause-and-play
```

---

## Best Practices

### 1. Always Clear Before Testing
```bash
# ALWAYS start with clean slate
python scripts/junk/clear_test_data.py
```

### 2. Use Consistent Seed for Regression Testing
```bash
# Use same seed to compare results across code changes
python run_full_test.py --seed 42
```

### 3. Allow Time for Processing
```bash
# Use sufficient delay (10+ seconds) for all services to process
python run_full_test.py --delay 10
```

### 4. Monitor Logs During Testing
```bash
# Terminal 1: Run test
python run_full_test.py

# Terminal 2: Watch logs
make logs
```

### 5. Verify Results After Each Test
```bash
# Check MongoDB
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading

> db.signal_store.countDocuments({})          # Should match signals sent
> db.signal_store.countDocuments({"position.status": "CLOSED"})  # Check closed positions
> db.trading_orders.countDocuments({"status": "FILLED"})        # Check filled orders
> db.trading_orders.countDocuments({"status": "REJECTED"})      # Check for rejections
```

### 6. Create New Test Signals

**Template** (new_strategy.json):
```json
[
    {
        "strategy_name": "New_Strategy",
        "signal_type": "ENTRY",
        "signalID": "sig_new_001",
        "entry_name": "$NEW_1",
        "account_equity": 50000,
        "signal_legs": [
            {
                "instrument": "AAPL",
                "instrument_type": "STOCK",
                "action": "BUY",
                "direction": "LONG",
                "quantity": 10,
                "order_type": "MARKET",
                "price": 175.50
            }
        ],
        "environment": "staging",
        "staging": true,
        "wait": 6
    },
    {
        "strategy_name": "New_Strategy",
        "signal_type": "EXIT",
        "signalID": "sig_new_002",
        "entry_signal_id": "$NEW_1",
        "signal_legs": [
            {
                "instrument": "AAPL",
                "instrument_type": "STOCK",
                "action": "SELL",
                "direction": "LONG",
                "quantity": 10,
                "order_type": "MARKET",
                "price": 180.00
            }
        ],
        "environment": "staging",
        "staging": true,
        "wait": 6
    }
]
```

**Test**:
```bash
python send_test_signal.py --file new_strategy.json
```

---

## Troubleshooting

### No Signals Processed
**Check**: Is signal ingestion service running?
```bash
docker ps | grep signal-ingestion
make logs-signal-ingestion
```

### Orders Not Executing
**Check**: Is execution service running?
```bash
docker ps | grep execution
make logs-execution
```

### Position Sizing Wrong
**Check**: Cerebro logs for allocation calculations
```bash
make logs-cerebro
```

### Rejected Signals
**Check**: MongoDB for rejection reasons
```bash
> db.signal_store.find({"legs.decision.rejected": true}).pretty()
```

---

## Related Documentation
- [Signal Ingestion](signal_ingestion_service.md) - Signal processing
- [Cerebro Service](cerebro_service.md) - Position sizing
- [Execution Service](execution_service.md) - Order execution
- [Setup Guide](../Setup.md) - Initial setup
