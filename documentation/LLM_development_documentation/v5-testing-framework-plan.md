# V5 TESTING FRAMEWORK PLAN

**Status:** ✅ ARCHITECTURE FIXED - Signal Processing Working
**Created:** 2026-01-04
**Last Updated:** 2026-01-06 22:37 EST
**Major Refactor:** 2026-01-06 (Pub/Sub Removal, EPOCH Timestamps)

---

## CURRENT STATUS - JANUARY 6, 2026

✅ **Framework Complete** - All 98 signal files created with EPOCH timestamps
✅ **Architecture Fixed** - Removed Pub/Sub, MongoDB Change Streams only
✅ **Fund System Working** - $5M fund equity, 9 strategies allocated
✅ **Signal Processing Working** - Validates, calculates position sizes, finds accounts
⚠️ **Pending:** Complete end-to-end test and verify order execution

### Quick Test (Current State)
```bash
# Run single signal test (delay=999 to test one signal)
.venv/bin/python -u tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals --delay 999

# Check cerebro logs for order creation
docker logs mathematricks-trader-cerebro-service-1 2>&1 | grep -A 10 "ORDER CREATED"

# Run full test suite (delay=6 seconds between signals)
.venv/bin/python -u tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals --delay 6
```

---

## MAJOR ARCHITECTURAL CHANGES (2026-01-06)

### ✅ COMPLETED: Pub/Sub Removal
**Decision:** Remove Google Cloud Pub/Sub entirely, use MongoDB Change Streams only

**Why:** Simplified architecture, single source of truth (MongoDB), easier debugging

**Changes Made:**
1. **cerebro_service/cerebro_main.py**
   - Removed Pub/Sub imports and initialization
   - Removed Pub/Sub publishing from order creation
   - Now writes orders directly to `trading_orders` collection
   - Reads fund equity from MongoDB (doesn't recalculate)

2. **execution_service/execution_main.py**
   - Removed Pub/Sub imports and publishing functions
   - Added `watch_trading_orders()` for MongoDB Change Stream
   - Listens to `trading_orders` collection for new orders

3. **account_data_service/broker_poller.py**
   - Added MongoDB persistence for fund.total_equity
   - Calculates fund equity after each poll cycle
   - Persists to `funds` collection (total_equity field)
   - Special handling for Mock brokers (skips polling)

### ✅ COMPLETED: EPOCH Timestamp Architecture
**Decision:** Use EPOCH timestamps internally everywhere, human-readable only for display

**Why:** Avoid timezone issues, simplify validation, consistent data format

**Changes Made:**
1. **Test Signals** - All 90 signals use `signal_sent_EPOCH` field (integer)
2. **cerebro_main.py** - Updated `convert_signal_dict_to_object()` to read `signal_sent_EPOCH`
3. **Conversion** - EPOCH converted to datetime only for Signal object (internal processing)
4. **Display** - Human-readable timestamps used only in logs and frontend

### ✅ COMPLETED: Fund Architecture Fixes
**Issues Fixed:**
1. Fund equity showing $0 in cerebro (now reads from MongoDB: $5,000,000)
2. No ACTIVE allocations (created via init_fund_allocations_v2.py)
3. Strategy-to-account mapping missing (created via assign_strategies_to_accounts.py)
4. Repository query bug (was querying by `_id` instead of `account_id`)

**Fund Hierarchy:**
```
funds (mock-fund-1)
  └─ total_equity: $5,000,000 (updated by account-data-service)
     └─ portfolio_allocations (ACTIVE)
        ├─ Com1-Met: 11.11% → $555,500
        ├─ Com2-Ag: 11.11% → $555,500
        ├─ Com3-Mkt: 11.11% → $555,500
        ├─ Com4-Misc: 11.11% → $555,500
        ├─ FloridaForex: 11.11% → $555,500
        ├─ SPX_0DE_Opt: 11.11% → $555,500
        ├─ SPX_1-D_Opt: 11.11% → $555,500
        ├─ SPY: 11.11% → $555,500
        └─ TLT: 11.11% → $555,500

trading_accounts (5 mock accounts, each $1M)
  ├─ IBKR-MOCK → SPY, TLT, SPX_0DE_Opt, SPX_1-D_Opt
  ├─ VANTAGE_MOCK → Com1-Met, Com2-Ag, Com3-Mkt, Com4-Misc, FloridaForex
  ├─ OANDA_MOCK → Com1-Met, Com2-Ag, Com3-Mkt, Com4-Misc, FloridaForex
  ├─ BYBIT_MOCK → (available for future strategies)
  └─ BINANCE_MOCK → (available for future strategies)
```

### ✅ COMPLETED: Critical Bug Fixes
1. **repository.py (Line 20)** - Changed query from `{"_id": account_id}` to `{"account_id": account_id}`
   - Fixed 404 errors when cerebro queried `/api/v1/account/IBKR-MOCK/state`
   
2. **broker_poller.py** - Fixed database truth testing bug
   - Changed from `if funds_collection:` to `if self.db is not None:`
   
3. **cerebro_main.py** - Fixed allocation field name
   - Changed from `fund.get('strategies', {})` to `fund.get('allocations', {})`
   
4. **fund_allocation_logic.py** - Fixed function call signature
   - Updated `get_strategy_allocation_for_fund()` call to match new signature

---

## OVERVIEW

Build comprehensive test signal suite for all 9 strategies with realistic market prices, create two signal folders (realistic + edge-case), and enhance send_test_signal.py with folder-based bulk testing and deterministic seed-based shuffling.

This testing framework enables reproducible, controlled testing of the multi-fund signal processing pipeline with realistic scenarios.

---

## CLARIFYING QUESTIONS - ANSWERED ✅

### Question 1: Instrument Variety per Strategy
**Status:** ✅ Decided (2026-01-05)
**Decision:** Option C - Use all possible instruments per strategy
**Rationale:** Comprehensive testing, realistic strategy behavior

### Question 2: Fund Assignment
**Status:** ✅ Decided (2026-01-05)
**Decision:** Use "Mock-Fund-1" for all test signals
**Rationale:** User preference, clear test fund separation

### Question 3: Price Variation
**Status:** ✅ Decided (2026-01-05)
**Decision:** Option A - Fixed prices each test run (no variation)
**Rationale:** Reproducibility across environments, easier to debug price-related issues

### Question 4: Account Distribution Simulation
**Status:** ✅ Decided (2026-01-05)
**Decision:** Option B - Add multi-account distribution to realistic signals now
**Rationale:** Test fund allocation logic immediately, not just edge cases

---

## PHASE 1: SIGNAL TEMPLATE DESIGN

**Status:** 🚧 In Progress
**Target:** Design signal templates per asset class

### Template 1: Commodities Futures (Metals, Ag, Oil)
```json
{
  "strategy_name": "{strategy_name}",
  "signal_type": "ENTRY",
  "signal_sent_EPOCH": 1730116800,
  "signalID": "sig_auto_{timestamp}_{random}",
  "account_equity": 500000,
  "signal_legs": [
    {
      "instrument": "{contract_symbol}",
      "instrument_type": "FUTURE",
      "action": "BUY",
      "direction": "LONG",
      "quantity": {quantity},
      "order_type": "MARKET",
      "price": {entry_price},
      "stop_loss": {stop_price},
      "take_profit": {tp_price}
    }
  ],
  "environment": "staging",
  "staging": true,
  "fund_id": "Mock-Fund-1"
}
```

### Template 2: Forex Pairs
```json
{
  "strategy_name": "FloridaForex",
  "signal_type": "ENTRY",
  "signal_sent_EPOCH": 1730116800,
  "signalID": "sig_auto_{timestamp}_{random}",
  "account_equity": 500000,
  "signal_legs": [
    {
      "instrument": "{pair}",
      "instrument_type": "FOREX",
      "action": "BUY",
      "direction": "LONG",
      "quantity": 100000,
      "order_type": "MARKET",
      "price": {entry_price},
      "secType": "CASH",
      "currency": "USD"
    }
  ],
  "environment": "staging",
  "staging": true,
  "fund_id": "Mock-Fund-1"
}
```

### Template 3: Options (0DTE and 1D)
```json
{
  "strategy_name": "{strategy_name}",
  "signal_type": "ENTRY",
  "signal_sent_EPOCH": 1730116800,
  "signalID": "sig_auto_{timestamp}_{random}",
  "account_equity": 500000,
  "signal_legs": [
    {
      "instrument": "SPY",
      "instrument_type": "OPTION",
      "action": "BUY",
      "direction": "LONG",
      "quantity": 2,
      "order_type": "MARKET",
      "price": {entry_price},
      "underlying": "SPY",
      "strike": {strike},
      "expiry": "{expiry_date}",
      "right": "C"
    }
  ],
  "environment": "staging",
  "staging": true,
  "fund_id": "Mock-Fund-1"
}
```

### Template 4: Equity (SPY, TLT)
```json
{
  "strategy_name": "{strategy_name}",
  "signal_type": "ENTRY",
  "signal_sent_EPOCH": 1730116800,
  "signalID": "sig_auto_{timestamp}_{random}",
  "account_equity": 500000,
  "signal_legs": [
    {
      "instrument": "{symbol}",
      "instrument_type": "STOCK",
      "action": "BUY",
      "direction": "LONG",
      "quantity": {quantity},
      "order_type": "MARKET",
      "price": {entry_price},
      "secType": "STK",
      "exchange": "NYSE",
      "currency": "USD"
    }
  ],
  "environment": "staging",
  "staging": true,
  "fund_id": "Mock-Fund-1"
}
```

### EXIT Signal Template (All Asset Classes)
```json
{
  "strategy_name": "{strategy_name}",
  "signal_type": "EXIT",
  "signal_sent_EPOCH": 1730116800,
  "signalID": "sig_auto_{timestamp}_{random}",
  "entry_signal_id": "$ENTRY_1",
  "account_equity": 500000,
  "signal_legs": [
    {
      "instrument": "{same_as_entry}",
      "instrument_type": "{same_type}",
      "action": "SELL",
      "direction": "LONG",
      "quantity": {exit_quantity},
      "order_type": "MARKET",
      "price": {exit_price}
    }
  ],
  "environment": "staging",
  "staging": true,
  "fund_id": "Mock-Fund-1"
}
```

---

## PHASE 2: SIGNAL FILE GENERATION

**Status:** ⏳ Not Started
**Target:** Create 7-10 realistic signals per strategy

### 2.1 Com1 - Met (Metals Futures)
**Instruments:** GC (Gold), SI (Silver), HG (Copper)
**File:** `com1_met_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.2 Com2 - Ag (Agriculture Futures)
**Instruments:** ZC (Corn), ZW (Wheat), ZS (Soybeans)
**File:** `com2_ag_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.3 Com3 - Mkt (Mixed Commodities)
**Instruments:** CL (Crude Oil), GC (Gold), NG (Natural Gas)
**File:** `com3_mkt_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.4 Com4 - Misc (Miscellaneous Commodities)
**Instruments:** CC (Cocoa), SB (Sugar), KC (Coffee)
**File:** `com4_misc_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.5 FloridaForex (Forex Trading)
**Instruments:** EURUSD, GBPUSD, AUDCAD
**File:** `florida_forex_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.6 SPX 0DE Opt (Same-Day Options)
**Instruments:** SPY 0DTE calls, SPY 0DTE puts
**File:** `spx_0de_opt_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.7 SPX 1-D Opt (1-Day Options)
**Instruments:** SPY 1D calls, SPY 1D puts
**File:** `spx_1d_opt_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.8 SPY (Equity)
**Instruments:** SPY shares
**File:** `spy_realistic.json`
**Status:** ⏳ Awaiting generation and review

### 2.9 TLT (Fixed Income)
**Instruments:** TLT shares
**File:** `tlt_realistic.json`
**Status:** ⏳ Awaiting generation and review

---

## PHASE 3: EDGE-CASE SIGNALS

**Status:** ⏳ Not Started
**Target:** Create edge case variants in `sample_signals_edgecases/`

**Edge Cases to Test:**

- ☐ Insufficient margin rejection
- ☐ Asset class mismatch
- ☐ Capital limit exceeded
- ☐ Stop-loss triggered
- ☐ Partial fill across accounts
- ☐ Order rejection and recovery
- ☐ Multi-fund distribution
- ☐ Account failover

---

## PHASE 4: ENVIRONMENT CONFIGURATION

**Status:** ⏳ Not Started
**Target:** Add seed requirement to .env

**File:** `.env`
**Addition:** `SIGNAL_TEST_SEED=1`

**Tasks:**
- ☐ Add `SIGNAL_TEST_SEED=1` to `.env`
- ☐ Add to `.env.example`
- ☐ Document in SETUP.md

---

## PHASE 5: ENHANCE send_test_signal.py

**Status:** ⏳ Not Started
**Target:** Add folder-based bulk testing and seed control

**New Features:**
- ☐ `--folder` parameter for loading all JSON files
- ☐ `--seed` CLI override (optional)
- ☐ Seed-based shuffle using random.seed()
- ☐ Folder loading with glob pattern
- ☐ Backward compatibility with `--file`
- ☐ Validation that SIGNAL_TEST_SEED exists in .env

---

## PHASE 6: CREATE TEST RUNNER

**Status:** ⏳ Not Started
**Target:** New script to execute full test suite

**File:** `tests/signals_testing/run_full_test.py`

**Features:**
- ☐ Load all signals from folder
- ☐ Send with fixed seed for reproducibility
- ☐ Log results per signal
- ☐ Report summary (total, success, failure)
- ☐ Export results to JSON

---

## PROGRESS TRACKING

### ✅ ALL PHASES COMPLETE

**Phase 1-3: Signal Generation (COMPLETE)**
- ✅ 9 realistic signal files (90 signals total)
- ✅ 8 edge-case signal files
- ✅ All positions perfectly balanced (zero final position)
- ✅ All signals tagged with fund_id="Mock-Fund-1"

**Phase 4-5: Environment & Scripts (COMPLETE)**
- ✅ SIGNAL_TEST_SEED=1 added to .env
- ✅ send_test_signal.py enhanced (--folder, --seed)
- ✅ run_full_test.py created (automated test runner)
- ✅ Makefile updated (make reseed-db, make test-signals)

**Phase 6: Seed Data Management (COMPLETE)**
- ✅ export_seed_data.sh fixed (container→host copy)
- ✅ restore_seed_data.sh fixed (drops DB before restore)
- ✅ init_mongodb.sh fixed (auto-restore on make start)
- ✅ Seed file created: seed_20260105_130235.tar.gz (108 docs)

**Phase 7: Documentation (COMPLETE)**
- ✅ TESTING_QUICKSTART.md created
- ✅ STRATEGY_INVENTORY.md created
- ✅ v5-testing-framework-plan.md (this document)

### ⚠️ PRE-TEST CHECKLIST

Before first test run:
- [ ] Install venv dependencies: `.venv/bin/pip install -r requirements.txt`
- [ ] Add --delay parameter to send_test_signal.py (optional enhancement)
- [ ] Remove duplicate venv folder (keep .venv only)
- [ ] Run first test: `make test-signals`

### 📊 DELIVERABLES SUMMARY

**Signal Files:** 98 total
- 9 realistic strategy files (90 signals)
- 8 edge-case scenario files (8 signals)

**Scripts Enhanced:**
- send_test_signal.py (--folder, --seed support)
- run_full_test.py (test automation)
- export_seed_data.sh (fixed container copy)
- restore_seed_data.sh (drops DB first)
- init_mongodb.sh (auto-restore on empty DB)

**Makefile Commands:**
- `make reseed-db` - Restore clean database
- `make export-seed-data` - Export current DB state
- `make test-signals` - Full automated test run

**Seed Data:**
- seed_20260105_130235.tar.gz (736KB)
- 12 collections, 108 documents
- 9 strategies, 44 signals, 40 signal_store entries

---

## KNOWN ISSUES TO RESOLVE

1. **Missing venv dependencies** - ModuleNotFoundError: dotenv
   - Fix: `.venv/bin/pip install -r requirements.txt`

2. **Duplicate venv folders** - Both venv/ and .venv/ exist
   - Fix: Remove venv/, keep .venv/

3. **No signal delay visibility** - Hard to observe signals in logs
   - Enhancement: Add --delay parameter to scripts (optional)

---

## DECISIONS LOG

| Decision | Value | Date | Rationale |
|---|---|---|---|
| **Instrument Variety** | All instruments per strategy | 2026-01-05 | Comprehensive testing |
| **Fund Assignment** | Mock-Fund-1 | 2026-01-05 | User preference |
| **Price Variation** | Fixed prices (no variation) | 2026-01-05 | Reproducibility |
| **Multi-Account Testing** | Include in realistic signals | 2026-01-05 | Test fund logic early |

---

**Last Updated:** 2026-01-05 09:00 UTC
**Next Step:** Generate Com1 - Met realistic signals for review
