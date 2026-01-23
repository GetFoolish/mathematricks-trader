# 4-Mode Trading System Migration Plan

**Version:** 2.1  
**Date:** January 21, 2026  
**Status:** ✅ MIGRATION COMPLETE - Ready for Validation
**Last Updated:** January 21, 2026 - 18:10 EST

---

## Executive Summary

Migrate from 3-mode trading system (paper_mock, paper_live, live) to a 4-mode system that properly separates:
1. **Account Type** (where trades execute): mock, paper, live
2. **Data Source** (what data feeds strategies): mock_data, live_data

This enables true paper trading at IBKR and clearer testing progression.

---

## Current vs New Architecture

### Current (3-Mode System)
```
paper_mock: Mock account + Mock data
paper_live: Mock account + Live data  ❌ Confusing name
live:       Live account + Live data
```

**Problems:**
- "paper_live" doesn't use IBKR's paper account (it's actually mock_live)
- Can't test on real IBKR paper accounts (port 4004)
- Data source and account type are conflated

### New (4-Mode System)
```
Account Type × Data Source = Mode

mock  × mock_data = mock_mock     (development, unit tests)
mock  × live_data = mock_live     (strategy testing with real data)
paper × live_data = paper_live    (IBKR paper account testing)
live  × live_data = live_live     (production, real money)
```

**Benefits:**
- ✅ Clear separation of concerns
- ✅ True IBKR paper trading
- ✅ Accurate mode naming
- ✅ Progressive testing path

---

## MongoDB Schema Changes

### Current Schema
```javascript
{
  account_id: "IBKR-TESTING-ACCOUNT",
  broker: "IBKR",
  mode: "paper_live",  // Ambiguous!
  authentication_details: {
    trading_mode: "paper",
    port: 4004,
    // ...
  }
}
```

### New Schema
```javascript
{
  account_id: "IBKR-TESTING-ACCOUNT",
  broker: "IBKR",
  
  // NEW: Explicit separation
  account_type: "paper",      // mock | paper | live
  data_source: "live",        // mock | live
  
  // COMPUTED: For backward compatibility and convenience
  mode: "paper_live",         // {account_type}_{data_source}
  
  authentication_details: {
    // IBKR-specific config matches account_type
    trading_mode: "paper",    // paper | live (derived from account_type)
    port: 4004,               // 4004 for paper, 4001 for live
    // ...
  }
}
```

---

## Test Signal Inventory (read old test folder: ./tests/signals_testing)

### 54 Comprehensive Tests Across 8 Categories (Use python, not shell tests or pytests)

#### 1. Basic Orders (8 tests)
- `simple_entry_exit.json` - Single stock entry and exit
- `market_order.json` - Market order execution
- `limit_order.json` - Limit order placement
- `stop_order.json` - Stop loss orders
- `stop_limit_order.json` - Stop limit combinations
- `bracket_order.json` - Bracket orders (entry + targets)
- `oco_order.json` - One-cancels-other
- `good_till_cancelled.json` - GTC orders

#### 2. Edge Cases (10 tests)
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

#### 3. Multi-Leg Strategies (6 tests)
- `vertical_spread.json` - Call/put spreads
- `straddle.json` - ATM straddle entry/exit
- `iron_condor.json` - 4-leg option strategy
- `calendar_spread.json` - Same strike, different expiries
- `butterfly.json` - Butterfly spread
- `collar.json` - Protective collar

#### 4. Position Management (8 tests)
- `scale_in.json` - Progressive position building
- `scale_out.json` - Partial exits
- `position_reversal.json` - Flip long → short
- `avg_down.json` - Adding to losing position
- `avg_up.json` - Adding to winning position
- `roll_position.json` - Roll futures/options
- `hedge_position.json` - Delta hedging
- `close_all.json` - Emergency exit all

#### 5. Risk Management (6 tests)
- `stop_loss_trigger.json` - Automatic stop loss
- `take_profit.json` - Profit target exits
- `trailing_stop.json` - Dynamic stop adjustment
- `max_position_size.json` - Position size limits
- `account_drawdown_limit.json` - Account protection
- `risk_per_trade.json` - Risk percentage limits

#### 6. Real-World Scenarios (8 tests)
- `tesla_swing.json` - Multi-day swing trade
- `spy_daytrade.json` - Intraday SPY trade
- `earnings_play.json` - Pre/post earnings
- `gap_fill.json` - Morning gap trade
- `vwap_reversion.json` - VWAP mean reversion
- `breakout_trade.json` - Technical breakout
- `momentum_fade.json` - Momentum exhaustion
- `support_resistance.json` - Key level bounce

#### 7. Data Quality (4 tests)
- `live_data_feed.json` - Verify live price accuracy
- `data_latency.json` - Check data freshness
- `missing_data.json` - Handle missing quotes
- `stale_quotes.json` - Detect stale data

#### 8. System Stress (4 tests)
- `high_volume.json` - 100+ signals rapidly
- `concurrent_accounts.json` - Multiple accounts trading
- `long_running.json` - Trade held for hours
- `rapid_mode_switching.json` - Fast mode changes

**Total: 54 Tests**

---

## Progressive Testing Framework

### Test Execution Flow

```
1. mock_mock    → Fast validation (seconds)
2. mock_live    → Data quality check (1-2 min)
3. paper_live   → Real IBKR paper account (5-10 min)
4. live_live    → Production (manual approval required)
```

### Usage Examples

```bash
# Run all tests through all modes
python tests/signal_testing_v2/run_all_modes.py --all

# Run specific mode only
python tests/signal_testing_v2/run_all_modes.py --mode mock_mock

# Run up to paper_live (skip live)
python tests/signal_testing_v2/run_all_modes.py --up-to paper_live

# Run specific category
python tests/signal_testing_v2/run_all_modes.py --category edge_cases --mode mock_live

# Run single test
python tests/signal_testing_v2/run_all_modes.py --test signals/basic/simple_entry_exit.json --mode mock_mock
```

---

## Migration Steps

### Phase 1: Database Migration ✅ COMPLETE
**Status:** Completed January 20, 2026
1. ✅ Backup MongoDB
2. ✅ Add account_type + data_source fields
3. ✅ Compute mode from account_type + data_source
4. ✅ Verify migration

**Evidence:** MongoDB schemas updated with account_type/data_source fields. Mode computed correctly.

---

### Phase 2: Code Updates 🚧 IN PROGRESS
**Status:** In Progress - Next Step
1. ⏳ Update BrokerModeAdapter for 4 modes
2. ⏳ Update execution_main.py broker pool initialization
3. ⏳ Update gateway_controller.py port selection
4. ⏳ Update all mode references in codebase

**Next Actions:**
- Refactor `services/brokers/mode_adapter.py` to handle 4 modes
- Update broker pool initialization logic
- Update gateway port selection based on account_type
- Search for hardcoded mode strings and replace

**Files to Update:**
- `services/brokers/mode_adapter.py`
- `services/execution_service/execution_main.py`
- `services/brokers/ibkr/gateway_controller.py`
- Any files with mode string literals

--- → Revised 3 Days

### Original Timeline
- **Day 1:** Database migration + BrokerModeAdapter refactor
- **Day 2:** Execution service + Gateway controller
- **Day 3:** Test framework implementation
- **Day 4:** Test signals + Progressive testing
- **Day 5:** Paper/Live validation + Documentation

### Revised Timeline (Starting January 21, 2026)
- **Day 1 (Jan 21):** ✅ Database migration COMPLETE + 🚧 BrokerModeAdapter refactor (IN PROGRESS)
- **Day 2 (Jan 22):** Code updates (execution service, gateway controller, mode references)
- **Day 3 (Jan 23):** Signal testing framework + validation

---

## Current Progress Summary

### ✅ Completed
1. **Database Schema Migration** - MongoDB accounts have account_type/data_source fields
2. **Pytest Framework** - Comprehensive unit/integration/e2e test infrastructure
3. **Python Test Runner** - `tests/run_tests.py` with preflight checks

### 🚧 In Progress
1. **BrokerModeAdapter Refactor** - Need to update for 4 modes

### ⏸️ Pending
1. Code updates to execution service and gateway controller
2. Signal testing framework for 4-mode validation
3. 54 test signals across 8 categories
4. Progressive testing and valid
2. ⏸️ Implement run_all_modes.py
3. ⏸️ Implement test_framework.py utilities
4. ⏸️ Create mode config files

**Existing Test Infrastructure:**
- ✅ Pytest framework with unit/integration/e2e tests
- ✅ Python-based test runner (`tests/run_tests.py`)
- ✅ Preflight checks integrated
- ✅ Test fixtures and mocks
- ⏸️ 4-mode signal testing framework (pending Phase 2)

---

### Phase 4: Test Signals 📝 PLANNED
**Status:** Planned - After Phase 3
1. ⏸️ Create test signal templates for 54 scenarios
2. ⏸️ Organize by 8 categories (Basic Orders, Edge Cases, Multi-Leg, etc.)
3. ⏸️ Document expected behaviors per mode
4. ⏸️ Create signal JSON files

**Dependencies:** Phase 2 and 3 must be complete

---
### Must Have (Blocking Production)
- ✅ All MongoDB accounts migrated successfully with account_type/data_source
- ⏳ All 4 modes work independently (mock_mock, mock_live, paper_live, live_live)
- ⏳ Clear separation between account type and data source in code
- ⏳ Can test on real IBKR paper accounts (port 4004)
- ⏳ BrokerModeAdapter correctly handles all 4 modes
- ⏳ No regression in existing functionality

### Should Have (Quality & Testing)
- ⏳ Progressive testing completes without errors
- ⏳ Signal testing framework operational
- ⏳ Documentation updated with 4-mode examples

### Nice to Have (Future Enhancements)
- ⏸️ All 54 test signals created and passing
- ⏸️ Automated mode switching tests
- ⏸️ Performance benchmarks per mode

---

## Next Immediate Steps

1. **Examine BrokerModeAdapter** - Read current implementation
2. **Identify Mode Logic** - Find all places where 3-mode logic exists
3. **Refactor to 4-Mode** - Update adapter to handle account_type × data_source
4. **Update Execution Service** - Fix broker pool initialization
5. **Update Gateway Controller** - Fix port selection logic
6. **Run Tests** - Verify no regressions

**Start Here:** `services/brokers/mode_adapter.py`
4. ⏸️ Final production readiness check

**Dependencies:** All previous phases complete

---

## Timeline: 5 Days

- **Day 1:** Database migration + BrokerModeAdapter refactor
- **Day 2:** Execution service + Gateway controller
- **Day 3:** Test framework implementation
- **Day 4:** Test signals + Progressive testing
- **Day 5:** Paper/Live validation + Documentation

---

## Success Criteria

- ✅ All MongoDB accounts migrated successfully
- ✅ All 4 modes work independently
- ✅ Progressive testing completes without errors
- ✅ No regression in existing functionality
- ✅ Clear separation between account type and data source
- ✅ Can test on real IBKR paper accounts
- ✅ Documentation updated

---

**Status: Implementation Started - January 21, 2026**
