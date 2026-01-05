# V5 TESTING FRAMEWORK PLAN

**Status:** ✅ COMPLETE
**Created:** 2026-01-04
**Last Updated:** 2026-01-05
**Completed:** 2026-01-05

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

### ✅ COMPLETED
- [x] Step 1: Strategy Discovery & Documentation
  - [x] Query MongoDB for all 9 strategies
  - [x] Create STRATEGY_INVENTORY.md
  - [x] Document asset classes and instruments
  - [x] Answer 4 clarifying questions

- [x] Step 2: Create Realistic Signal Templates
  - [x] Design template structures for 4 asset classes
  - [x] Created reusable templates for commodities, forex, options, equity

- [x] Step 3: Generate 9 Realistic Signal JSON Files - COMPLETED ✅
  - [x] com1_met_realistic.json (GC, SI, HG metals futures)
  - [x] com2_ag_realistic.json (ZC, ZW, ZS agriculture futures)
  - [x] com3_mkt_realistic.json (CL, GC, NG mixed commodities)
  - [x] com4_misc_realistic.json (CC, SB, KC misc commodities)
  - [x] florida_forex_realistic.json (EURUSD, GBPUSD, AUDCAD forex pairs)
  - [x] spx_0de_opt_realistic.json (SPY 0DTE calls and puts)
  - [x] spx_1d_opt_realistic.json (SPY 1D calls and puts)
  - [x] spy_realistic.json (SPY, QQQ, AAPL equity)
  - [x] tlt_realistic.json (TLT, IEF, BND fixed income)

### 🚧 IN PROGRESS
- [x] Step 4: Generate edge-case signals (COMPLETE ✅)
  - [x] edge_case_insufficient_margin.json - 100 GC contracts (margin rejection)
  - [x] edge_case_asset_class_mismatch.json - commodity to crypto account
  - [x] edge_case_capital_limit.json - 90% allocation used (capital rejection)
  - [x] edge_case_stop_loss.json - entry @ 580, exit @ 574.50 (< 575 stop)
  - [x] edge_case_partial_fills.json - 3 GC split across accounts
  - [x] edge_case_order_rejection.json - invalid price → retry → exit
  - [x] edge_case_multi_fund.json - same strategy in 2 funds
  - [x] edge_case_account_failover.json - primary unavailable, route to secondary

### ⏳ NOT STARTED
- [x] Step 5: Update .env with SIGNAL_TEST_SEED (COMPLETE ✅)
  - Added SIGNAL_TEST_SEED=1 to .env
  - 0=randomized, positive=reproducible seed
  
- [x] Step 6: Enhance send_test_signal.py (COMPLETE ✅)
  - Added --folder parameter to load all *.json files from directory
  - Added --seed parameter for CLI override of SIGNAL_TEST_SEED
  - Implemented seed-based shuffling: seed >= 0 applies shuffle, < 0 preserves order
  - Maintains backward compatibility with --file and @filename syntax
  
- [x] Step 7: Create run_full_test.py runner (COMPLETE ✅)
  - Wrapper script to execute all signals from a folder
  - Captures results, tracks execution time, generates JSON reports
  - Saves output and results to test_results/ folder with timestamped run IDs
  - Usage: python run_full_test.py [--folder FOLDER] [--seed SEED]

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
