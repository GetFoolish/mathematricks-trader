# Broker Integration & Testing Plan

**Date Created:** 2026-01-31  
**Status:** Planning Phase  
**Goal:** Integrate Coinbase broker and reorganize testing infrastructure for comprehensive multi-broker, multi-mode validation

---

## Quick Start: Testing Commands

All testing is done via `tests/run_test_suite.py`. Adjust `--signal-count` for quick tests or omit for full signal files.

For development, if u need to make any temp scripts, please put them in the folder scripts/llm_dev_scripts

### Coinbase Testing Commands

```bash
# Quick test (2 signals)
.venv/bin/python tests/run_test_suite.py --signal-testing \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count 2

# Full test - mock_mock mode (all 10 signals: 5 entries + 5 exits)
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json

# Full test - mock_live mode
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source live \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json

# Full test - paper_live mode (requires Coinbase sandbox credentials)
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type paper --data-source live \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json
```

### IBKR Testing Commands (Reorganized)

```bash
# ===== IBKR - Market Hours (Stocks) =====
# Monday-Friday, 9:30 AM - 4:00 PM ET only

# Quick test - mock_mock
.venv/bin/python tests/run_test_suite.py --signal-testing \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/ibkr/ibkr-market-hours/tech_stocks.json --signal-count 2

# Full test - mock_mock (clean start)
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/ibkr/ibkr-market-hours/tech_stocks.json

# Full test - mock_live
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source live \
  --file tests/sample_signals/ibkr/ibkr-market-hours/tech_stocks.json

# Full test - paper_live (requires IB Gateway)
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type paper --data-source live \
  --file tests/sample_signals/ibkr/ibkr-market-hours/tech_stocks.json


# ===== IBKR - Weekday Off-Market (Crypto + Forex) =====
# Monday-Friday, outside 9:30 AM - 4:00 PM ET (e.g., 6:00 PM - 8:00 PM ET)

# Quick test - mock_mock
.venv/bin/python tests/run_test_suite.py --signal-testing \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/ibkr/ibkr-weekday-off-market/crypto_forex_evening.json --signal-count 2

# Full test - mock_mock
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/ibkr/ibkr-weekday-off-market/crypto_forex_evening.json

# Full test - mock_live
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source live \
  --file tests/sample_signals/ibkr/ibkr-weekday-off-market/crypto_forex_evening.json

# Full test - paper_live
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type paper --data-source live \
  --file tests/sample_signals/ibkr/ibkr-weekday-off-market/crypto_forex_evening.json


# ===== IBKR - All-the-Time (Crypto Only) =====
# 24/7 trading, works anytime (weekend, holidays)

# Quick test - mock_mock
.venv/bin/python tests/run_test_suite.py --signal-testing \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/ibkr/ibkr-all-the-time/crypto_24_7.json --signal-count 2

# Full test - mock_mock
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/ibkr/ibkr-all-the-time/crypto_24_7.json

# Full test - mock_live
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source live \
  --file tests/sample_signals/ibkr/ibkr-all-the-time/crypto_24_7.json

# Full test - paper_live
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type paper --data-source live \
  --file tests/sample_signals/ibkr/ibkr-all-the-time/crypto_24_7.json
```

### Comprehensive Multi-Mode Testing (After All Setup Complete)

```bash
# Test all brokers, all modes (sequential)
# Total: 12 test runs (2 brokers × 2 categories × 3 modes)

# Run this after everything is implemented
bash tests/test_all_brokers_all_modes.sh
```

---

## Phase 1: Coinbase Broker Integration

### 1.1 Coinbase Broker Research

**Coinbase Advanced Trade API Details:**
- REST API: https://api.coinbase.com
- Sandbox: https://api.sandbox.coinbase.com (official sandbox environment)
- Authentication: API Key + Private Key (PEM format)
- Supported Assets: BTC, ETH, SOL, XRP, ADA, DOGE, etc.
- Order Types: Market, Limit, Stop-Loss, Stop-Limit
- WebSocket: Real-time market data

**Coinbase vs IBKR Differences:**
- No IB Gateway needed (pure REST/WebSocket API)
- Crypto-only (no stocks, options, futures)
- Symbol format: `BTC-USD`, `ETH-USD`, etc.
- Official sandbox for testing (unlike Coinbase)
- Real-time fills (no delayed settlement)
- Requires JWT authentication

### 1.2 Implementation Tasks

#### Task 1.2.1: Create Coinbase Broker Class
**File:** `services/brokers/coinbase/coinbase_broker.py`

**Implementation Requirements:**
```python
class CoinbaseBroker(AbstractBroker):
    """
    Coinbase Advanced Trade API broker implementation
    
    Supports:
    - Crypto spot trading (BTC, ETH, SOL, etc.)
    - Market and limit orders
    - Real-time balance and position queries
    - Sandbox environment for paper trading
    """
    
    def __init__(self, config: Dict):
        """
        Config:
          - api_key: Coinbase API key name
          - api_secret: Coinbase private key (PEM format)
          - sandbox: bool (use sandbox.coinbase.com)
        """
        pass
    
    def connect(self) -> bool:
        """Test API credentials"""
        pass
    
    def place_order(self, order: Dict) -> Dict:
        """
        Place order via Coinbase Advanced Trade API
        Returns: order confirmation with broker_order_id
        """
        pass
    
    def get_account_balance(self) -> Dict:
        """Query Coinbase account balance"""
        pass
    
    def get_open_positions(self) -> List[Dict]:
        """
        Get open positions
        Note: Coinbase doesn't have "positions" for spot trading
        Return empty list or calculate from balance deltas
        """
        pass
    
    def get_current_price(self, instrument: str) -> float:
        """Get real-time price from Coinbase ticker API"""
        pass
```

**Files to Create:**
- `services/brokers/coinbase/__init__.py`
- `services/brokers/coinbase/coinbase_broker.py`
- `services/brokers/coinbase/README.md` (API documentation)

**Dependencies:**
```bash
# Add to requirements.txt
coinbase-advanced-py>=1.2.0  # Coinbase Advanced Trade API client
```

#### Task 1.2.2: Update BrokerFactory
**File:** `services/brokers/factory.py`

Add Coinbase to supported brokers:
```python
SUPPORTED_BROKERS = ['IBKR', 'Mock', 'Zerodha', 'Coinbase']

def create_broker(config: Dict) -> AbstractBroker:
    if broker_name == 'Coinbase':
        from brokers.coinbase import CoinbaseBroker
        return CoinbaseBroker(config)
```

#### Task 1.2.3: Add Coinbase Account to MongoDB
**Collection:** `trading_accounts`

```json
{
  "account_id": "COINBASE_CANADA",
  "broker": "Coinbase",
  "account_type": "mock",
  "mode": ["mock_mock", "mock_live", "paper_live"],
  "status": "ACTIVE",
  "authentication_details": {
    "api_key": "YOUR_COINBASE_API_KEY_NAME",
    "api_secret": "YOUR_COINBASE_PRIVATE_KEY",
    "sandbox": true,
    "initial_equity": 100000.0
  },
  "balances": {
    "base_currency": "USD",
    "equity": 100000.0,
    "cash_balance": 100000.0,
    "margin_available": 100000.0,
    "unrealized_pnl": 0.0,
    "realized_pnl": 0.0
  },
  "open_positions": []
}
```

**MongoDB Seed Script:**
```bash
# Run after Coinbase broker is implemented
.venv/bin/python scripts/llm_dev_scripts/seed_coinbase_account.py
```

---

## Phase 2: Coinbase Sample Signals

### 2.1 Signal Design

**Requirements:**
- 5 ENTRY signals
- 5 EXIT signals (matching each entry)
- Net position = 0 at end
- Crypto instruments (BTC, ETH, SOL)
- Market orders for simplicity

**Signal File Structure:**
```json
[
  {
    "strategy_name": "Coinbase_Crypto_Momentum",
    "signal_type": "ENTRY",
    "entry_signal_id": "$COINBASE_BTC_1",
    "signal_legs": [
      {
        "instrument": "BTC-USD",
        "instrument_type": "CRYPTO",
        "action": "BUY",
        "direction": "LONG",
        "quantity": 0.5,
        "order_type": "MARKET"
      }
    ],
    "environment": "staging",
    "wait": 5
  },
  {
    "strategy_name": "Coinbase_Crypto_Momentum",
    "signal_type": "EXIT",
    "entry_signal_id": "$COINBASE_BTC_1",
    "signal_legs": [
      {
        "instrument": "BTC-USD",
        "instrument_type": "CRYPTO",
        "action": "SELL",
        "direction": "CLOSE",
        "quantity": 0.5,
        "order_type": "MARKET"
      }
    ],
    "environment": "staging",
    "wait": 5
  }
  // ... 4 more entry/exit pairs
]
```

### 2.2 Sample Signals Breakdown

**File:** `tests/sample_signals/coinbase/crypto_spot_trading.json`

| Signal # | Type | Instrument | Action | Quantity | Entry ID |
|----------|------|------------|--------|----------|----------|
| 1 | ENTRY | BTC-USD (BTC) | BUY | 0.5 BTC | $COINBASE_BTC_1 |
| 2 | EXIT | BTC-USD (BTC) | SELL | 0.5 BTC | $COINBASE_BTC_1 |
| 3 | ENTRY | ETH-USD (ETH) | BUY | 5.0 ETH | $COINBASE_ETH_1 |
| 4 | EXIT | ETH-USD (ETH) | SELL | 5.0 ETH | $COINBASE_ETH_1 |
| 5 | ENTRY | SOL-USD (SOL) | BUY | 100 SOL | $COINBASE_SOL_1 |
| 6 | EXIT | SOL-USD (SOL) | SELL | 100 SOL | $COINBASE_SOL_1 |
| 7 | ENTRY | BTC-USD (BTC) | BUY | 1.0 BTC | $COINBASE_BTC_2 |
| 8 | EXIT | BTC-USD (BTC) | SELL | 1.0 BTC | $COINBASE_BTC_2 |
| 9 | ENTRY | ETH-USD (ETH) | BUY | 10.0 ETH | $COINBASE_ETH_2 |
| 10 | EXIT | ETH-USD (ETH) | SELL | 10.0 ETH | $COINBASE_ETH_2 |

**Net Position After All Signals:** 0 BTC, 0 ETH, 0 SOL ✅

### 2.3 Implementation Tasks

#### Task 2.3.1: Create Coinbase Signal Directory
```bash
mkdir -p tests/sample_signals/coinbase
```

#### Task 2.3.2: Generate Coinbase Signal File
**File:** `tests/sample_signals/coinbase/crypto_spot_trading.json`

Use realistic crypto prices:
- BTC: ~$45,000
- ETH: ~$2,400
- SOL: ~$100

Add appropriate `wait` times between signals (5-10 seconds).

---

## Phase 3: Coinbase Testing (3 Modes)

### 3.1 Testing Matrix

| Mode | Account Type | Data Source | Broker Setup | Expected Behavior |
|------|--------------|-------------|--------------|-------------------|
| **mock_mock** | mock | mock | Mock broker only | Instant fills, simulated prices |
| **mock_live** | mock | live | BrokerModeAdapter(Coinbase + Mock) | Real Coinbase prices, mock fills |
| **paper_live** | paper | live | Coinbase (sandbox or demo) | Real Coinbase API, test account |

### 3.2 Test Execution Plan

#### Test 3.2.1: mock_mock Mode
```bash
# Clean start, full test
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json
```

**Expected Results:**
- All 10 signals processed
- 5 positions opened and closed
- Final position: 0 BTC, 0 ETH, 0 SOL
- Mock broker balance updated
- All signals in signal_store with `processing_complete: true`

**Validation Queries:**
```bash
# Check final position
curl -s "http://localhost:8083/api/v1/positions?account_id=COINBASE-TESTNET" | jq '.open_positions'

# Should return: []

# Check signal_store completion
mongo mathematricks_trading --eval "db.signal_store.find({processing_complete: true}).count()"
# Should return: 10
```

#### Test 3.2.2: mock_live Mode
```bash
# Clean start, full test
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source live \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json
```

**Expected Results:**
- Real-time Coinbase prices used for fills
- Mock broker executes orders (no real Coinbase API calls for orders)
- BrokerModeAdapter routes:
  - `get_current_price()` → Coinbase
  - `get_account_balance()` → Coinbase (for realistic margin)
  - `place_order()` → Mock broker
- Final position: 0 (same as mock_mock)

**Validation:**
- Check logs for "Coinbase price fetched" messages
- Verify fill prices match real Coinbase ticker

#### Test 3.2.3: paper_live Mode
```bash
# Clean start, full test
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type paper --data-source live \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json
```

**Expected Results:**
- Real Coinbase sandbox/demo account used
- Orders placed via Coinbase REST API
- Real order confirmations with Coinbase order IDs
- Balances updated from Coinbase account

**Prerequisites:**
- Coinbase sandbox credentials configured
- `COINBASE-TESTNET` account in MongoDB with valid API keys

---

## Phase 4: IBKR Signal Reorganization

### 4.1 Current State Analysis

**Current Directory:** `tests/sample_signals/ibkr/`

**Current Files:**
- `tech_stocks_realistic.json` (11 stock pairs, 22 signals total)

**Problem:**
- Single file mixes time-sensitive instruments (stocks) with 24/7 instruments
- No separation for testing outside market hours
- Hard to test specific scenarios (market hours only, crypto only, etc.)

### 4.2 New Directory Structure

```
tests/sample_signals/ibkr/
├── ibkr-market-hours/
│   ├── tech_stocks.json           (AAPL, MSFT, GOOGL, NVDA, TSLA)
│   ├── financial_stocks.json      (JPM, BAC, GS, WFC)
│   └── README.md
├── ibkr-weekday-off-market/
│   ├── crypto_forex_evening.json  (BTC, ETH + EUR/USD, GBP/USD)
│   ├── futures_overnight.json     (ES, NQ futures)
│   └── README.md
└── ibkr-all-the-time/
    ├── crypto_24_7.json           (BTC, ETH only)
    ├── README.md
    └── .gitkeep
```

### 4.3 Signal File Specifications

#### File 4.3.1: ibkr-market-hours/tech_stocks.json

**Trading Window:** Monday-Friday, 9:30 AM - 4:00 PM ET

**Signals:** 10 total (5 entries + 5 exits)

| Signal # | Type | Instrument | Action | Quantity | Entry ID |
|----------|------|------------|--------|----------|----------|
| 1 | ENTRY | AAPL | BUY | 50 | $IBKR_AAPL_1 |
| 2 | EXIT | AAPL | SELL | 50 | $IBKR_AAPL_1 |
| 3 | ENTRY | MSFT | BUY | 30 | $IBKR_MSFT_1 |
| 4 | EXIT | MSFT | SELL | 30 | $IBKR_MSFT_1 |
| 5 | ENTRY | GOOGL | BUY | 20 | $IBKR_GOOGL_1 |
| 6 | EXIT | GOOGL | SELL | 20 | $IBKR_GOOGL_1 |
| 7 | ENTRY | NVDA | BUY | 40 | $IBKR_NVDA_1 |
| 8 | EXIT | NVDA | SELL | 40 | $IBKR_NVDA_1 |
| 9 | ENTRY | TSLA | BUY | 25 | $IBKR_TSLA_1 |
| 10 | EXIT | TSLA | SELL | 25 | $IBKR_TSLA_1 |

**Instrument Type:** `STOCK`  
**Market Hours Check:** ✅ Required  
**Weekend Trading:** ❌ Not allowed

#### File 4.3.2: ibkr-weekday-off-market/crypto_forex_evening.json

**Trading Window:** Monday-Friday, 6:00 PM - 8:00 PM ET (outside market hours)

**Signals:** 10 total (5 entries + 5 exits)

| Signal # | Type | Instrument | Action | Quantity | Entry ID |
|----------|------|------------|--------|----------|----------|
| 1 | ENTRY | BTC | BUY | 0.5 | $IBKR_BTC_1 |
| 2 | EXIT | BTC | SELL | 0.5 | $IBKR_BTC_1 |
| 3 | ENTRY | ETH | BUY | 5.0 | $IBKR_ETH_1 |
| 4 | EXIT | ETH | SELL | 5.0 | $IBKR_ETH_1 |
| 5 | ENTRY | EUR.USD | BUY | 10000 | $IBKR_EURUSD_1 |
| 6 | EXIT | EUR.USD | SELL | 10000 | $IBKR_EURUSD_1 |
| 7 | ENTRY | GBP.USD | BUY | 10000 | $IBKR_GBPUSD_1 |
| 8 | EXIT | GBP.USD | SELL | 10000 | $IBKR_GBPUSD_1 |
| 9 | ENTRY | BTC | BUY | 1.0 | $IBKR_BTC_2 |
| 10 | EXIT | BTC | SELL | 1.0 | $IBKR_BTC_2 |

**Instrument Types:** `CRYPTO`, `FOREX`  
**Market Hours Check:** ⚠️ Bypass (crypto/forex trade 24/7)  
**Weekend Trading:** ✅ Allowed

#### File 4.3.3: ibkr-all-the-time/crypto_24_7.json

**Trading Window:** Anytime (24/7, including weekends)

**Signals:** 6 total (3 entries + 3 exits)

| Signal # | Type | Instrument | Action | Quantity | Entry ID |
|----------|------|------------|--------|----------|----------|
| 1 | ENTRY | BTC | BUY | 0.5 | $IBKR_BTC_247_1 |
| 2 | EXIT | BTC | SELL | 0.5 | $IBKR_BTC_247_1 |
| 3 | ENTRY | ETH | BUY | 5.0 | $IBKR_ETH_247_1 |
| 4 | EXIT | ETH | SELL | 5.0 | $IBKR_ETH_247_1 |
| 5 | ENTRY | BTC | BUY | 1.0 | $IBKR_BTC_247_2 |
| 6 | EXIT | BTC | SELL | 1.0 | $IBKR_BTC_247_2 |

**Instrument Type:** `CRYPTO` only  
**Market Hours Check:** ⚠️ Bypass  
**Weekend Trading:** ✅ Allowed

### 4.4 Migration Plan

#### Task 4.4.1: Extract Current Signals
```bash
# Parse existing tech_stocks_realistic.json
# Split into 3 categories based on instrument_type
```

#### Task 4.4.2: Create New Directories
```bash
mkdir -p tests/sample_signals/ibkr/ibkr-market-hours
mkdir -p tests/sample_signals/ibkr/ibkr-weekday-off-market
mkdir -p tests/sample_signals/ibkr/ibkr-all-the-time
```

#### Task 4.4.3: Generate New Signal Files
Create 3 new JSON files with proper structure and metadata.

#### Task 4.4.4: Update README Files
Document each category's purpose, trading windows, and usage.

#### Task 4.4.5: Archive Old File
```bash
mv tests/sample_signals/ibkr/tech_stocks_realistic.json \
   tests/sample_signals/ibkr/tech_stocks_realistic.json.BACKUP
```

---

## Phase 5: IBKR Testing (3 Modes × 3 Categories)

### 5.1 Testing Matrix

| Category | mock_mock | mock_live | paper_live | Total Tests |
|----------|-----------|-----------|------------|-------------|
| **ibkr-market-hours** | ✅ | ✅ | ✅ | 3 |
| **ibkr-weekday-off-market** | ✅ | ✅ | ✅ | 3 |
| **ibkr-all-the-time** | ✅ | ✅ | ✅ | 3 |
| **Total** | 3 | 3 | 3 | **9** |

### 5.2 Test Execution Order

#### Phase 5.2.1: Market Hours Testing
```bash
# 1. mock_mock
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/ibkr/ibkr-market-hours/tech_stocks.json

# 2. mock_live
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source live \
  --file tests/sample_signals/ibkr/ibkr-market-hours/tech_stocks.json

# 3. paper_live
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type paper --data-source live \
  --file tests/sample_signals/ibkr/ibkr-market-hours/tech_stocks.json
```

#### Phase 5.2.2: Weekday Off-Market Testing
```bash
# Same 3-mode sequence for crypto_forex_evening.json
```

#### Phase 5.2.3: 24/7 Crypto Testing
```bash
# Same 3-mode sequence for crypto_24_7.json
```

### 5.3 Validation Criteria

For each test run:

**✅ Pass Criteria:**
1. All signals processed (`processing_complete: true`)
2. No errors in logs
3. Final net position = 0
4. Balances updated correctly
5. Execution times within expected range

**❌ Fail Criteria:**
1. Any signal stuck (`processing_complete: false`)
2. Broker connection errors
3. Position mismatch (non-zero final position)
4. MongoDB update failures

---

## Phase 6: Automation & CI/CD

### 6.1 Test Suite Script

**File:** `tests/test_all_brokers_all_modes.sh`

```bash
#!/bin/bash
# Comprehensive multi-broker, multi-mode testing

set -e  # Exit on error

echo "======================================"
echo "COMPREHENSIVE BROKER & MODE TESTING"
echo "======================================"

# Coinbase Tests (3 modes)
echo -e "\n### COINBASE TESTING ###"
for mode in "mock_mock" "mock_live" "paper_live"; do
    echo "Testing Coinbase - $mode"
    .venv/bin/python tests/run_test_suite.py --signal-testing --clean \
        --environment staging \
        --account-type ${mode%_*} --data-source ${mode#*_} \
        --file tests/sample_signals/coinbase/crypto_spot_trading.json
done

# IBKR Tests (9 total: 3 categories × 3 modes)
echo -e "\n### IBKR TESTING ###"
categories=("ibkr-market-hours/tech_stocks" "ibkr-weekday-off-market/crypto_forex_evening" "ibkr-all-the-time/crypto_24_7")

for category in "${categories[@]}"; do
    echo "Testing IBKR - $category"
    for mode in "mock_mock" "mock_live" "paper_live"; do
        echo "  Mode: $mode"
        .venv/bin/python tests/run_test_suite.py --signal-testing --clean \
            --environment staging \
            --account-type ${mode%_*} --data-source ${mode#*_} \
            --file "tests/sample_signals/ibkr/${category}.json"
    done
done

echo -e "\n✅ ALL TESTS COMPLETED"
```

### 6.2 GitHub Actions Workflow

**File:** `.github/workflows/broker-testing.yml`

```yaml
name: Multi-Broker Testing

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test-brokers:
    runs-on: ubuntu-latest
    
    services:
      mongodb:
        image: mongo:7
        ports:
          - 27018:27017
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run Coinbase tests
        run: |
          .venv/bin/python tests/run_test_suite.py --signal-testing \
            --account-type mock --data-source mock \
            --file tests/sample_signals/coinbase/crypto_spot_trading.json
      
      - name: Run IBKR tests
        run: |
          bash tests/test_all_brokers_all_modes.sh
```

---

## Implementation Checklist

### Phase 1: Coinbase Integration ✅
- [ ] Research Coinbase API documentation
- [ ] Create `services/brokers/coinbase/coinbase_broker.py`
- [ ] Implement `CoinbaseBroker` class (all methods)
- [ ] Update `BrokerFactory` to support Coinbase
- [ ] Add `coinbaseex` to `requirements.txt`
- [ ] Create MongoDB seed script for Coinbase account
- [ ] Test Coinbase broker standalone (unit tests)

### Phase 2: Coinbase Sample Signals ✅
- [ ] Create `tests/sample_signals/coinbase/` directory
- [ ] Design 10-signal sequence (5 entries + 5 exits, net=0)
- [ ] Generate `crypto_spot_trading.json`
- [ ] Validate signal format matches schema
- [ ] Add README.md with signal descriptions

### Phase 3: Coinbase Testing ✅
- [ ] Test Coinbase mock_mock mode (quick + full)
- [ ] Test Coinbase mock_live mode (quick + full)
- [ ] Test Coinbase paper_live mode (quick + full)
- [ ] Verify net position = 0 for all modes
- [ ] Document any Coinbase-specific quirks

### Phase 4: IBKR Reorganization ✅
- [ ] Create 3 new IBKR subdirectories
- [ ] Generate `ibkr-market-hours/tech_stocks.json`
- [ ] Generate `ibkr-weekday-off-market/crypto_forex_evening.json`
- [ ] Generate `ibkr-all-the-time/crypto_24_7.json`
- [ ] Add README.md to each subdirectory
- [ ] Archive old `tech_stocks_realistic.json`

### Phase 5: IBKR Testing ✅
- [ ] Test ibkr-market-hours (3 modes)
- [ ] Test ibkr-weekday-off-market (3 modes)
- [ ] Test ibkr-all-the-time (3 modes)
- [ ] Verify all 9 test combinations pass
- [ ] Compare results across modes for consistency

### Phase 6: Automation ✅
- [ ] Create `test_all_brokers_all_modes.sh`
- [ ] Make script executable (`chmod +x`)
- [ ] Run full test suite end-to-end
- [ ] Set up GitHub Actions workflow (optional)
- [ ] Document test results in this file

---

## Expected Outcomes

### Success Metrics
1. **Coinbase broker fully functional** in all 3 modes
2. **12 test combinations pass** (Coinbase: 3, IBKR: 9)
3. **Zero net positions** after each test sequence
4. **No manual intervention** needed during tests
5. **Test execution time** < 15 minutes total

### Deliverables
1. `services/brokers/coinbase/` module (complete)
2. `tests/sample_signals/coinbase/` directory (1 file)
3. `tests/sample_signals/ibkr/` reorganized (3 subdirectories, 3 files)
4. `tests/test_all_brokers_all_modes.sh` (automation script)
5. Updated `System-Overview.md` with Coinbase details

---

## Risk Assessment

### High Risk
- **Coinbase API rate limits:** May throttle requests during testing
  - *Mitigation:* Add delays between signals, use sandbox
- **IBKR Gateway availability:** Container might not start in time
  - *Mitigation:* Health checks with retry logic

### Medium Risk
- **Signal timing issues:** Weekend tests might fail for weekday-only instruments
  - *Mitigation:* Clear documentation on when to run each test
- **Mode adapter complexity:** mock_live mode routing might break
  - *Mitigation:* Extensive logging, unit tests

### Low Risk
- **JSON syntax errors:** Hand-written signal files might have typos
  - *Mitigation:* JSON schema validation, linting

---

## Timeline Estimate

| Phase | Tasks | Estimated Time | Dependencies |
|-------|-------|----------------|--------------|
| **Phase 1** | Coinbase Integration | 4-6 hours | Coinbase API docs |
| **Phase 2** | Coinbase Signals | 1-2 hours | Phase 1 complete |
| **Phase 3** | Coinbase Testing | 2-3 hours | Phase 2 complete |
| **Phase 4** | IBKR Reorganization | 2-3 hours | None |
| **Phase 5** | IBKR Testing | 3-4 hours | Phase 4 complete |
| **Phase 6** | Automation | 1-2 hours | Phases 3 & 5 complete |
| **Total** | | **13-20 hours** | |

---

## Notes

- All testing uses `staging` environment
- Production testing comes AFTER all staging tests pass
- Mock balances reset to $100,000 before each test (`--clean` flag)
- Logs are crucial - check `logs/execution_service.log`, `logs/signal_processing.log`

---

**Status:** ⏳ Planning Complete - Ready for Implementation  
**Next Step:** Begin Phase 1 - Coinbase Broker Integration
