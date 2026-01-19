# IBKR Integration Plan: 3-Mode Trading System (paper_mock | paper_live | live)

## Progress Tracker

**Last Updated**: 2026-01-14

### Phase 0: Test Infrastructure (COMPLETED ✅)
- [x] Created 5 test signal files in tests/signals_testing/sample_signals_ibkr/
  - ibkr_stock_aapl.json (AAPL stock)
  - ibkr_crypto_btc.json (BTC crypto)
  - ibkr_forex_eurusd.json (EUR/USD forex)
  - ibkr_future_gc.json (Gold commodity future)
  - ibkr_option_spy.json (SPY option)
- [x] Created test runner script (tests/signals_testing/run_ibkr_test.py)
- [x] Created account setup script (scripts/setup_ibkr_test_account.py)
- [x] Created IBKR_Paper_Test account in MongoDB (ID: 696815ae81685caa0273b0f1)
  - Mode: paper_live
  - Initial balance: $100,000
- [x] Run initial test (expected to fail) - COMPLETED
  - **Test Results** (2026-01-14 23:17):
    - ✅ Pre-flight checks all passed
    - ✅ IB Gateway running
    - ✅ IBKR_Paper_Test account found in MongoDB
    - ✅ Test signals sent successfully (5 ENTRY + 5 EXIT)
    - ❌ All signals REJECTED by cerebro_service
    - **Root Cause**: Strategy documents don't exist in MongoDB
      - Error: "Strategy IBKR_Test_Stock not found - rejecting signal"
      - Error: "Strategy IBKR_Test_Crypto not found - rejecting signal"
      - Error: "Strategy IBKR_Test_Forex not found - rejecting signal"
      - Error: "Strategy IBKR_Test_Future not found - rejecting signal"
    - ❌ Option signal has validation error: "Missing required field: quantity"
    - ⚠️  IBKR_Paper_Test account NOT loaded by execution service
      - Service only loaded 5 accounts (IBKR-MOCK, BINANCE_MOCK, VANTAGE_MOCK, BYBIT_MOCK, OANDA_MOCK)
      - Account exists in DB but wasn't returned by AccountDataService
  - **Next Steps**:
    1. Create strategy documents in MongoDB
    2. Fix option signal format
    3. Debug AccountDataService to ensure IBKR_Paper_Test is returned

- [x] Create strategy documents ✅ (2026-01-14 23:28)
  - Created 5 strategy documents mapped to IBKR_Paper_Test account
- [x] Fix option signal format ✅ (2026-01-14 23:28)
  - Added `quantity` field to signal_leg level
- [x] Debug account loading ✅ (2026-01-14 23:30)
  - **Finding**: IBKR_Paper_Test account exists in MongoDB but isn't being polled
  - **Root Cause**: broker_poller can't connect to IBKR accounts without real broker setup
  - **Resolution Path**: Must implement BrokerModeAdapter (Phase 1) to enable mode-based broker creation

### Phase 1: Core Implementation (IN PROGRESS - READY TO START)
- [ ] Implement BrokerModeAdapter
- [ ] Add get_market_price() to IBKR broker
- [ ] Update broker pool initialization
- [ ] Add safety checks for live mode

### Phase 2: Debug & Iterate (PENDING)
- [ ] Fix broker pool initialization issues
- [ ] Fix order routing issues
- [ ] Fix pricing enrichment issues
- [ ] Verify realistic pricing in logs

### Phase 3: Live Mode Testing (PENDING)
- [ ] Switch to live mode
- [ ] Run single signal test
- [ ] Verify real execution

---

## Overview
Integrate IBKR (InteractiveBrokers) with a flexible 3-mode system that supports:
- **paper_mock**: Fake pricing + mock broker orders (current test mode)
- **paper_live**: LIVE pricing from IBKR + mock broker orders (NEW - for realistic testing)
- **live**: Live pricing + real IBKR orders (production trading)

**Goal**: Enable testing with IBKR paper account first, then transition to live account, while maintaining a paper_live mode for ongoing safe testing with real market data.

---

## Architecture: Hybrid Adapter Pattern

```
Execution Service
    ↓
Broker Pool: {account_id → broker_instance}
    ↓
Mode Router (reads 'mode' from trading_accounts collection)
    ↓
┌──────────────┬──────────────┬──────────────┐
│ paper_mock   │ paper_live   │    live      │
├──────────────┼──────────────┼──────────────┤
│ Mock Pricing │ IBKR Pricing │ IBKR Pricing │
│ Mock Orders  │ Mock Orders  │ IBKR Orders  │
└──────────────┴──────────────┴──────────────┘
```

**Key Design Decision**: Use a `BrokerModeAdapter` wrapper class that:
- Wraps real broker + mock broker instances
- Routes `place_order()` calls based on mode
- For `paper_live`: fetches live prices from IBKR, sends orders to Mock

---

## Implementation Steps (Test-Driven Development Approach)

### Phase 0: Test Infrastructure First
**Strategy**: Build tests FIRST, then implement features until tests pass

#### 0.1 Create IBKR Test Account in MongoDB
**Method**: MongoDB shell or Python script

**Account Document**:
```javascript
db.trading_accounts.insertOne({
  "account_id": "IBKR_Paper_Test",
  "broker": "IBKR",
  "mode": "paper_live",  // Start with paper_live mode
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4002,  // Paper port
    "client_id": 1
  },
  "balances": {
    "equity": 100000,
    "cash_balance": 100000,
    "margin_used": 0,
    "margin_available": 100000,
    "last_updated": new Date()
  },
  "open_positions": [],
  "asset_classes": ["equity", "futures", "options", "forex", "crypto"],
  "status": "ACTIVE",
  "created_at": new Date()
})
```

**Add mode field to existing Mock account** (if not already present):
```javascript
db.trading_accounts.updateOne(
  {"account_id": "Mock_Paper"},
  {"$set": {"mode": "paper_mock"}},
  {upsert: true}
)
```

#### 0.2 Create Test Signal Files
**Directory**: `tests/signals_testing/sample_signals_ibkr/` (NEW)

Create 5 test signal files with simple 1-entry + 1-exit patterns.

**File 1: Stock - AAPL** (`ibkr_stock_aapl.json`)
```json
[
  {
    "strategy_name": "IBKR_Test_Stock",
    "passphrase": "test_password_123",
    "signal_type": "ENTRY",
    "entry_name": "$AAPL_1",
    "account_equity": 100000,
    "signal_legs": [{
      "instrument": "AAPL",
      "instrument_type": "STOCK",
      "action": "BUY",
      "direction": "LONG",
      "quantity": 10,
      "order_type": "MARKET",
      "environment": "staging"
    }],
    "wait": 5
  },
  {
    "strategy_name": "IBKR_Test_Stock",
    "passphrase": "test_password_123",
    "signal_type": "EXIT",
    "entry_signal_id": "$AAPL_1",
    "signal_legs": [{
      "instrument": "AAPL",
      "instrument_type": "STOCK",
      "action": "SELL",
      "direction": "SHORT",
      "quantity": 10,
      "order_type": "MARKET",
      "environment": "staging"
    }]
  }
]
```

**File 2: Crypto - BTC** (`ibkr_crypto_btc.json`)
```json
[
  {
    "strategy_name": "IBKR_Test_Crypto",
    "signal_type": "ENTRY",
    "entry_name": "$BTC_1",
    "signal_legs": [{
      "instrument": "BTC",
      "instrument_type": "CRYPTO",
      "action": "BUY",
      "direction": "LONG",
      "quantity": 0.01,
      "order_type": "MARKET",
      "environment": "staging"
    }],
    "wait": 5
  },
  {
    "strategy_name": "IBKR_Test_Crypto",
    "signal_type": "EXIT",
    "entry_signal_id": "$BTC_1",
    "signal_legs": [{
      "instrument": "BTC",
      "instrument_type": "CRYPTO",
      "action": "SELL",
      "direction": "SHORT",
      "quantity": 0.01,
      "order_type": "MARKET",
      "environment": "staging"
    }]
  }
]
```

**File 3: Forex - EUR.USD** (`ibkr_forex_eurusd.json`)
```json
[
  {
    "strategy_name": "IBKR_Test_Forex",
    "signal_type": "ENTRY",
    "entry_name": "$EUR_1",
    "signal_legs": [{
      "instrument": "EURUSD",
      "instrument_type": "FOREX",
      "action": "BUY",
      "direction": "LONG",
      "quantity": 20000,
      "order_type": "MARKET",
      "environment": "staging"
    }],
    "wait": 5
  },
  {
    "strategy_name": "IBKR_Test_Forex",
    "signal_type": "EXIT",
    "entry_signal_id": "$EUR_1",
    "signal_legs": [{
      "instrument": "EURUSD",
      "instrument_type": "FOREX",
      "action": "SELL",
      "direction": "SHORT",
      "quantity": 20000,
      "order_type": "MARKET",
      "environment": "staging"
    }]
  }
]
```

**File 4: Commodity Future - Gold** (`ibkr_future_gc.json`)
```json
[
  {
    "strategy_name": "IBKR_Test_Future",
    "signal_type": "ENTRY",
    "entry_name": "$GC_1",
    "signal_legs": [{
      "instrument": "GC",
      "instrument_type": "FUTURE",
      "action": "BUY",
      "direction": "LONG",
      "quantity": 1,
      "order_type": "MARKET",
      "expiry": "20250228",
      "exchange": "COMEX",
      "environment": "staging"
    }],
    "wait": 5
  },
  {
    "strategy_name": "IBKR_Test_Future",
    "signal_type": "EXIT",
    "entry_signal_id": "$GC_1",
    "signal_legs": [{
      "instrument": "GC",
      "instrument_type": "FUTURE",
      "action": "SELL",
      "direction": "SHORT",
      "quantity": 1,
      "order_type": "MARKET",
      "expiry": "20250228",
      "exchange": "COMEX",
      "environment": "staging"
    }]
  }
]
```

**File 5: Option - SPY** (`ibkr_option_spy.json`)
```json
[
  {
    "strategy_name": "IBKR_Test_Option",
    "signal_type": "ENTRY",
    "entry_name": "$SPY_OPT_1",
    "signal_legs": [{
      "instrument": "SPY",
      "instrument_type": "OPTION",
      "underlying": "SPY",
      "action": "BUY",
      "direction": "LONG",
      "order_type": "MARKET",
      "legs": [{
        "strike": 500,
        "expiry": "20250221",
        "right": "C",
        "action": "BUY",
        "quantity": 1
      }],
      "environment": "staging"
    }],
    "wait": 5
  },
  {
    "strategy_name": "IBKR_Test_Option",
    "signal_type": "EXIT",
    "entry_signal_id": "$SPY_OPT_1",
    "signal_legs": [{
      "instrument": "SPY",
      "instrument_type": "OPTION",
      "underlying": "SPY",
      "action": "SELL",
      "direction": "SHORT",
      "order_type": "MARKET",
      "legs": [{
        "strike": 500,
        "expiry": "20250221",
        "right": "C",
        "action": "SELL",
        "quantity": 1
      }],
      "environment": "staging"
    }]
  }
]
```

#### 0.3 Create Test Runner Script
**File**: `tests/signals_testing/run_ibkr_test.py` (NEW)

```python
"""
IBKR-specific test runner with pre-flight checks and validation.
Run this to test IBKR integration end-to-end.
"""
import os
import sys
import subprocess
import time
from pymongo import MongoClient

def check_ib_gateway():
    """Verify IB Gateway container is running"""
    print("\n[Check 1/4] Checking IB Gateway container...")
    result = subprocess.run(
        ['docker', 'ps', '--filter', 'name=ib-gateway', '--format', '{{.Status}}'],
        capture_output=True, text=True
    )
    if 'Up' not in result.stdout:
        print("❌ IB Gateway not running. Start with: docker-compose up -d ib-gateway")
        sys.exit(1)
    print("✅ IB Gateway is running")

def check_account_exists():
    """Verify IBKR test account exists in MongoDB"""
    print("\n[Check 2/4] Checking IBKR_Paper_Test account in MongoDB...")
    client = MongoClient('mongodb://localhost:27017/')
    db = client['mathematricks_trading']
    account = db['trading_accounts'].find_one({"account_id": "IBKR_Paper_Test"})

    if not account:
        print("❌ IBKR_Paper_Test account not found in MongoDB")
        print("   Create it with: db.trading_accounts.insertOne({...})")
        sys.exit(1)

    mode = account.get('mode', 'unknown')
    print(f"✅ IBKR_Paper_Test account found (mode: {mode})")
    return mode

def check_execution_service():
    """Verify execution service is running"""
    print("\n[Check 3/4] Checking execution service...")
    result = subprocess.run(
        ['docker', 'ps', '--filter', 'name=execution-service', '--format', '{{.Status}}'],
        capture_output=True, text=True
    )
    if 'Up' not in result.stdout:
        print("⚠️  Execution service not running via docker")
        print("   Make sure it's running manually or via docker-compose")
    else:
        print("✅ Execution service is running")

def check_test_signals_exist():
    """Verify test signal files exist"""
    print("\n[Check 4/4] Checking test signal files...")
    folder = "tests/signals_testing/sample_signals_ibkr"
    expected_files = [
        "ibkr_stock_aapl.json",
        "ibkr_crypto_btc.json",
        "ibkr_forex_eurusd.json",
        "ibkr_future_gc.json",
        "ibkr_option_spy.json"
    ]

    missing = []
    for file in expected_files:
        path = os.path.join(folder, file)
        if not os.path.exists(path):
            missing.append(file)

    if missing:
        print(f"❌ Missing test signal files: {', '.join(missing)}")
        print(f"   Create them in {folder}/")
        sys.exit(1)

    print(f"✅ All {len(expected_files)} test signal files found")

def run_test():
    """Run the actual IBKR test"""
    print("\n" + "="*60)
    print("=== RUNNING IBKR TEST SIGNALS ===")
    print("="*60)
    print("\nℹ️  Connect VNC Viewer to localhost:5900 to monitor IB Gateway")
    print("   Password: ibgateway\n")

    time.sleep(3)  # Give user time to connect VNC

    # Run test with small delay between signals
    cmd = (
        ".venv/bin/python tests/signals_testing/run_full_test.py "
        "--folder tests/signals_testing/sample_signals_ibkr "
        "--delay 10 "
        "--signal_count 10"
    )

    print(f"Running: {cmd}\n")
    os.system(cmd)

def validate_results():
    """Post-test validation"""
    print("\n" + "="*60)
    print("=== TEST VALIDATION CHECKLIST ===")
    print("="*60)
    print("\nPlease manually verify:")
    print("  [ ] Pricing is realistic (e.g., AAPL ~$170, not 100.0) - check logs")
    print("  [ ] Orders went to Mock broker - check trading_accounts.open_positions")
    print("  [ ] No real orders submitted - check IB Gateway VNC (activity log empty)")
    print("  [ ] Signals processed - check signal_store collection")
    print("\nTo query results:")
    print("  MongoDB: db.signal_store.find({strategy_id: 'IBKR_Test_Stock'}).pretty()")
    print("  MongoDB: db.trading_accounts.findOne({account_id: 'IBKR_Paper_Test'})")

def main():
    print("="*60)
    print("=== IBKR TEST SUITE PRE-FLIGHT CHECKS ===")
    print("="*60)

    try:
        check_ib_gateway()
        mode = check_account_exists()
        check_execution_service()
        check_test_signals_exist()

        print("\n✅ All pre-flight checks passed!")
        print(f"\nℹ️  Running in mode: {mode}")

        if mode == 'live':
            print("\n⚠️  WARNING: Account is in LIVE mode - real money at risk!")
            response = input("Type 'YES' to continue with live trading: ")
            if response != 'YES':
                print("Aborted.")
                sys.exit(0)

        run_test()
        validate_results()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

**Make executable**:
```bash
chmod +x tests/signals_testing/run_ibkr_test.py
```

#### 0.4 Initial Test Run (EXPECTED TO FAIL)
**Purpose**: Run tests to see what breaks, then fix

```bash
# Step 1: Start IB Gateway
docker-compose up -d ib-gateway
sleep 30  # Wait for startup

# Step 2: Connect VNC (optional but recommended)
# RealVNC Viewer → localhost:5900 (password: ibgateway)

# Step 3: Run test (will fail - mode not implemented yet)
.venv/bin/python tests/signals_testing/run_ibkr_test.py
```

**Expected Failure**: Account has `mode: "paper_live"` but execution service doesn't know how to handle it yet.

---

### Phase 1: Implement Features to Make Tests Pass

#### 1.1 Create Adapter Layer (Foundation)

#### 1.1 Create Adapter Directory
**Location**: `services/brokers/adapters/`

#### 1.2 Implement Mode Adapter
**File**: `services/brokers/adapters/mode_adapter.py` (NEW)

```python
class BrokerModeAdapter(AbstractBroker):
    def __init__(self, real_broker, mock_broker, mode: str):
        self.real_broker = real_broker  # IBKR instance
        self.mock_broker = mock_broker  # Mock instance
        self.mode = mode  # "paper_mock" | "paper_live" | "live"

    def place_order(self, order):
        if self.mode == "live":
            return self.real_broker.place_order(order)
        else:  # paper_mock or paper_live
            # For paper_live, enrich with live pricing
            if self.mode == "paper_live":
                order = self._enrich_with_real_pricing(order)
            return self.mock_broker.place_order(order)

    def _enrich_with_real_pricing(self, order):
        # Get live market price from IBKR
        symbol = order['instrument']
        instrument_type = order['instrument_type']
        real_price = self.real_broker.get_market_price(symbol, instrument_type)
        order['price'] = real_price
        return order

    # Delegate all other methods based on mode
    def get_account_balance(self, account_id=None):
        if self.mode == "live":
            return self.real_broker.get_account_balance(account_id)
        return self.mock_broker.get_account_balance(account_id)
```

**Critical Methods to Implement**:
- `place_order()` - Route to mock/real based on mode
- `get_account_balance()` - Route to mock/real
- `get_open_positions()` - Route to mock/real
- `_enrich_with_real_pricing()` - Fetch live price from IBKR for paper_live mode

#### 1.3 Add Market Price Method to IBKR Broker
**File**: `services/brokers/ibkr/ibkr_broker.py`
**Location**: Add after line ~840

```python
def get_market_price(self, symbol: str, instrument_type: str) -> float:
    """
    Get current market price for instrument (for paper_live mode).

    Returns:
        Mid-price (bid+ask)/2 or last traded price
    """
    contract = self._create_contract(symbol, instrument_type)
    ticker = self.ib.reqMktData(contract)
    self.ib.sleep(1)  # Wait for price to populate

    # Return mid-price or last price
    if ticker.bid and ticker.ask:
        return (ticker.bid + ticker.ask) / 2
    elif ticker.last:
        return ticker.last
    else:
        raise BrokerAPIError(f"No market data available for {symbol}")
```

---

### Phase 2: Broker Pool Integration

#### 2.1 Update Broker Pool Initialization
**File**: `services/execution_service/execution_main.py`
**Lines**: 195-238 (modify `initialize_broker_pool()`)

**Changes**:
```python
def initialize_broker_pool():
    accounts = get_active_accounts_from_service()

    for account in accounts:
        account_id = account.get('account_id')
        broker_name = account.get('broker')
        auth_details = account.get('authentication_details', {})
        mode = account.get('mode', 'paper_mock')  # NEW: Read mode field

        # Build broker based on mode
        if mode == 'paper_mock':
            # Create only Mock broker
            broker_config = {
                "broker": "Mock",
                "account_id": account_id,
                **auth_details
            }
            broker_instance = BrokerFactory.create_broker(broker_config)

        elif mode == 'paper_live':
            # Create BOTH IBKR + Mock, wrap in adapter
            real_config = {
                "broker": "IBKR",
                "account_id": account_id,
                **auth_details
            }
            mock_config = {
                "broker": "Mock",
                "account_id": account_id,
                **auth_details
            }
            real_broker = BrokerFactory.create_broker(real_config)
            mock_broker = BrokerFactory.create_broker(mock_config)
            broker_instance = BrokerModeAdapter(real_broker, mock_broker, mode='paper_live')

        elif mode == 'live':
            # Create only IBKR broker
            broker_config = {
                "broker": broker_name,
                "account_id": account_id,
                **auth_details
            }
            broker_instance = BrokerFactory.create_broker(broker_config)

        broker_pool[account_id] = broker_instance
```

#### 2.2 Add Safety Checks for Live Mode
**File**: `services/execution_service/execution_main.py`
**Lines**: 309-389 (modify `submit_order_to_broker()`)

**Add at start of function**:
```python
def submit_order_to_broker(order_data):
    account_id = order_data.get('account_id')

    # Get account to check mode
    account = trading_accounts_collection.find_one({"account_id": account_id})
    mode = account.get('mode', 'paper_mock') if account else 'paper_mock'

    # SAFETY: Critical warning on live mode
    if mode == 'live':
        logger.critical(f"⚠️ LIVE MODE ORDER: {order_data['instrument']} - Real money at risk!")

        # Optional: Check environment flag
        allow_live = os.getenv('ALLOW_LIVE_TRADING', 'false').lower() == 'true'
        if not allow_live:
            logger.error("❌ Live trading blocked by ALLOW_LIVE_TRADING flag")
            return {"status": "REJECTED", "reason": "Live trading not enabled"}

    broker = get_broker_for_account(account_id)
    # ... rest of function
```

#### 2.3 Remove Legacy Mock Mode Flag
**File**: `services/execution_service/execution_main.py`
**Lines to delete**:
- Lines 81-89: `--use-mock-broker` argument parsing
- Lines 283-286: Mock broker skip logic in `connect_all_brokers()`

**Reason**: Mode is now per-account in database, not a global flag

---

### Phase 3: Docker & VNC Configuration

#### 3.1 Update Docker Compose for Mode Switching
**File**: `docker-compose.yml`
**Lines**: 145-161

**Changes**:
```yaml
ib-gateway:
  image: ghcr.io/gnzsnz/ib-gateway:latest
  ports:
    - "4001:4003"  # Live API port
    - "4002:4004"  # Paper API port
    - "5900:5900"  # VNC (already exposed - no change needed)
  environment:
    - TWS_USERID=${IBKR_USERNAME}          # NEW: Generic username variable
    - TWS_PASSWORD=${IBKR_PASSWORD}        # NEW: Generic password variable
    - TRADING_MODE=${IBKR_TRADING_MODE}    # NEW: "paper" or "live"
    - TWOFA_TIMEOUT_ACTION=restart
    - READ_ONLY_API=no
    - IBC_AcceptIncomingConnectionAction=accept
    - VNC_SERVER_PASSWORD=ibgateway        # Already correct
  restart: unless-stopped
```

#### 3.2 Update Environment Variables
**File**: `.env`

**Add these variables**:
```bash
# IBKR Mode Control
IBKR_TRADING_MODE=paper  # "paper" or "live"
IBKR_USERNAME=${IBKR_PAPER_USERNAME}  # Switch to IBKR_LIVE_USERNAME for live
IBKR_PASSWORD=${IBKR_PAPER_PASSWORD}  # Switch to IBKR_LIVE_PASSWORD for live

# Safety Flag
ALLOW_LIVE_TRADING=false  # Set to "true" only when ready for live trading

# Existing credentials (keep as-is)
IBKR_PAPER_USERNAME=akasfz348
IBKR_PAPER_PASSWORD=gagan114
IBKR_LIVE_USERNAME=vandan0605
IBKR_LIVE_PASSWORD=Gagan114#
```

#### 3.3 VNC Connection Documentation
**File**: `docs/IBKR_VNC_SETUP.md` (NEW)

**Contents**:
```markdown
# IB Gateway VNC Monitoring

## Connecting with RealVNC Viewer

1. Ensure IB Gateway is running: `docker-compose up -d ib-gateway`
2. Open RealVNC Viewer
3. Connect to: `localhost:5900`
4. Password: `ibgateway`

## What You'll See
- IB Gateway login status
- API connection indicator (green = connected)
- Real-time order activity log
- 2FA prompts (if needed)

## Troubleshooting
- **Connection refused**: Container not running → `docker ps | grep ib-gateway`
- **Black screen**: Gateway still starting → wait 30s and reconnect
- **2FA prompt**: Enter TOTP code manually (only first login)
```

---

### Phase 2: Debug and Iterate
**Strategy**: Run tests → observe failures → fix code → repeat

#### 2.1 Debug Cycle
1. Run `run_ibkr_test.py`
2. Observe what breaks (broker pool initialization? order routing? pricing?)
3. Fix the specific issue
4. Re-run test
5. Repeat until all tests pass

#### 2.2 Success Criteria
**Tests pass when**:
- Pre-flight checks all pass (green checkmarks)
- Signals are processed without errors
- Realistic pricing appears in logs (AAPL ~$170, not 100.0)
- Orders routed to Mock broker (check `trading_accounts.open_positions`)
- No real orders in IB Gateway (VNC shows empty activity log)

---

### Phase 3: Live Mode Testing (After Paper Tests Pass)

#### 3.1 Switch to Live Mode
**ONLY after paper_live tests work perfectly**

**Step 1**: Update account mode
```javascript
db.trading_accounts.updateOne(
  {"account_id": "IBKR_Paper_Test"},
  {"$set": {"mode": "live"}}
)
```

**Step 2**: Update IB Gateway to live
```bash
# .env changes
IBKR_TRADING_MODE=live
IBKR_USERNAME=${IBKR_LIVE_USERNAME}
IBKR_PASSWORD=${IBKR_LIVE_PASSWORD}
ALLOW_LIVE_TRADING=true

# Restart container
docker-compose restart ib-gateway
```

**Step 3**: Run SINGLE signal
```bash
.venv/bin/python tests/signals_testing/run_full_test.py \
  --folder tests/signals_testing/sample_signals_ibkr \
  --signal_count 1
```

**Step 4**: Verify real execution
- Check VNC for real order submission
- Check IBKR web portal for actual fills
- Verify in `signal_store` collection

---

## Removed Sections

The following were moved to Phase 0 (test-first approach):
- Test signal file creation (now in 0.2)
- Test runner script (now in 0.3)
- IBKR test account creation (now in 0.1)

The following testing sections were consolidated into Phase 2-3:
- Paper mode testing workflow
- Live mode testing workflow

---

## Test-First Development Summary

**Phase 0**: Write ALL tests and test infrastructure
**Phase 1**: Implement code to make tests pass (adapter, broker pool, safety features)
**Phase 2**: Debug iteratively until paper_live tests pass
**Phase 3**: Switch to live mode and test with real broker (1 signal first)

This ensures we have clear success criteria and avoid over-engineering.

---

---

---

## Verification Checklist

### Pre-Flight (Before Any Test)
- [ ] IB Gateway container running: `docker ps | grep ib-gateway`
- [ ] VNC connection works: Connect to localhost:5900
- [ ] Gateway logged in: Check VNC for green connection
- [ ] Test account exists: Query `trading_accounts.IBKR_Paper_Test`
- [ ] Mode is correct: Verify `mode` field in account document

### Paper Mode Success Criteria
- [ ] Pricing is realistic (e.g., AAPL ~$170, not 100.0)
- [ ] Orders go to Mock broker: `trading_accounts.open_positions` populated
- [ ] No real orders: IB Gateway VNC shows empty activity log
- [ ] Signals processed: `signal_store` has execution data

### Live Mode Success Criteria (CRITICAL)
- [ ] Small quantities only (1-10 shares/contracts)
- [ ] Market is open (stocks need market hours)
- [ ] Real order appears in IB Gateway VNC
- [ ] Real fill confirmed in IBKR web portal
- [ ] Execution logged in `signal_store`

---

## Critical Files Modified

| File | Type | Purpose |
|------|------|---------|
| `services/brokers/adapters/mode_adapter.py` | NEW | Core adapter implementing 3-mode routing |
| `services/brokers/ibkr/ibkr_broker.py` | MODIFY | Add `get_market_price()` method (~line 840) |
| `services/execution_service/execution_main.py` | MODIFY | Update `initialize_broker_pool()` (lines 195-238) and add safety checks (lines 309-389) |
| `docker-compose.yml` | MODIFY | Add `IBKR_TRADING_MODE` env variable (lines 145-161) |
| `.env` | MODIFY | Add mode control variables |
| `scripts/migrations/add_mode_field_to_accounts.py` | NEW | MongoDB migration for mode field |
| `tests/signals_testing/sample_signals_ibkr/` | NEW | 5 test signal files for each asset type |
| `tests/signals_testing/run_ibkr_test.py` | NEW | IBKR-specific test runner with pre-flight checks |
| `docs/IBKR_VNC_SETUP.md` | NEW | VNC connection documentation |

---

## Safety Features

### Environment-Based Live Lock
- `ALLOW_LIVE_TRADING=false` in `.env` by default
- Execution service rejects live orders if flag is false
- Prevents accidental live trading in staging

### Mode Validation
- Account mode validated before order submission
- Critical warning logged for live mode orders
- VNC monitoring for visual confirmation

### Rollback Plan
If issues arise:
1. Set all accounts to `mode: "paper_mock"`
2. Restart execution service
3. Remove `mode_adapter.py` if needed
4. Fall back to legacy `--use-mock-broker` flag temporarily

---

## Risk Mitigation

### Edge Cases Handled
1. **IB Gateway disconnect during paper_live**: Fallback to mock pricing with warning
2. **Mode mismatch**: Validate `IBKR_TRADING_MODE` matches account mode
3. **Partial fills**: Already handled by existing `update_signal_store_with_execution()`
4. **Connection retries**: Existing IBKR broker handles Error 326 (client_id in use)

### Testing Strategy
- Start with paper_live mode (safest - real pricing, mock orders)
- Test all 5 asset types before moving to live
- Run single signal in live mode first before full test suite
- Monitor VNC throughout for visual confirmation

---

## Next Steps After Implementation

1. **Phase 1 Testing**: Implement through Phase 2, test paper_live mode with all 5 signals
2. **Phase 2 Validation**: Verify realistic pricing, no real orders submitted
3. **Phase 3 Live Prep**: Only proceed to live after 100% confidence in paper_live results
4. **Phase 4 Live Test**: Single AAPL stock signal in live mode
5. **Phase 5 Full Live**: All 5 asset types in live mode (if Phase 4 succeeds)

**Estimated complexity**: Medium
**Estimated risk**: Low (with proper testing sequence)
**Rollback difficulty**: Easy (database flag flip)
