# Tests for Mathematricks Trader V1

This folder contains test scripts to validate system functionality.

## Test 1: Telegram Notifications

**File:** `test_telegram.py`

Tests the Telegram notification system by sending test messages.

**Usage:**
```bash
python tests/test_telegram.py
```

**Requirements:**
- `.env` file configured with:
  - `TELEGRAM_ENABLED=true`
  - `TELEGRAM_BOT_TOKEN=<your_token>`
  - `TELEGRAM_CHAT_ID=<your_chat_id>`

**What it does:**
- Sends a test message to your Telegram
- Tests all notification types (signal received, trades executed, etc.)
- Verifies Telegram integration is working

---

## Test 2: Load Equity Curves

**File:** `test_load_equity_curves.py`

Loads historical equity curve data from a CSV file into MongoDB for testing the frontend dashboard.

**Usage:**
```bash
python tests/test_load_equity_curves.py tests/sample_equity_curves.csv
```

**CSV Format:**
```csv
date,strategy_name,equity,daily_pnl,daily_return_pct
2024-01-01,Strategy_A,100000,0,0.0
2024-01-02,Strategy_A,101500,1500,1.5
```

**What it does:**
- Reads equity curve data from CSV
- Clears existing PnL history in MongoDB
- Inserts all records into `pnl_history` collection
- Calculates and stores strategy performance metrics
- Populates data for Combined Performance and Strategy Deepdive pages

**Sample data:**
A sample CSV file with 5 strategies and 10 days of data is included: `sample_equity_curves.csv`

---

## Test 3: Random Signal Generator

**File:** `test_random_signals.py`

Continuously sends random trading signals to the system at random intervals (2-10 seconds).

**Usage:**
```bash
# Terminal 1: Start the trading system
python main.py

# Terminal 2: Start the random signal generator
python tests/test_random_signals.py
```

**What it does:**
- Generates random signals with realistic tickers and prices
- Sends signals to the running trading system
- Waits 2-10 seconds between each signal
- Runs continuously until you press Ctrl+C
- Logs all signal processing results

**Ticker Pool:**
- US Stocks: AAPL, MSFT, GOOGL, AMZN, TSLA, etc.
- ETFs: SPY, QQQ, IWM, TLT, GLD
- Indian Stocks: RELIANCE, TCS, INFY
- Crypto: BTC, ETH, SOL
- Forex: EURUSD, GBPUSD, USDJPY

**Use Case:**
- Test real-time signal processing
- Verify frontend updates in real-time
- Stress test the system with continuous signals
- Validate Telegram notifications
- Test MongoDB data storage

**Stop the test:** Press `Ctrl+C`

---

## Running All Tests

To run tests in sequence:

```bash
# Test 1: Telegram
python tests/test_telegram.py

# Test 2: Load sample equity data
python tests/test_load_equity_curves.py tests/sample_equity_curves.csv

# Test 3: Random signals (in separate terminal after starting main.py)
python main.py  # Terminal 1
python tests/test_random_signals.py  # Terminal 2
```

---

## Notes

- All tests use configuration from `.env` file
- Tests do not hardcode any values - everything comes from the codebase
- Logs are stored in `logs/` folder
- MongoDB database used: `mathematricks_trader`
- Collections: `trading_signals`, `orders`, `positions`, `pnl_history`, `strategy_performance`
