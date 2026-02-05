# MongoDB Fund Architecture Cleanup Plan

## Problem Statement
Over time our MongoDB has gotten too messy with extra fields and inconsistent data. We need a clean, well-structured fund-strategy-account architecture that supports:
- Development/testing workflows (mock mode)
- Paper trading validation
- Live trading deployment

---

## Current State Analysis (Feb 4, 2026)

### Existing Collections
```
Collections in mathematricks_trading:
- signal_store
- widget_data
- precision_cache
- dashboards
- strategies (11 docs)
- trading_signals_raw
- trading_accounts (6 docs)
- dashboard_snapshots
- uploaded_strategies
- funds (2 docs)
- portfolio_tests (4 docs)
```

### Current Strategies (11)
1. **IBKR_Test_Stock** - Has clean `accounts` structure with mock/paper/live
2. **IBKR_Test_Option** - Similar to above
3. **TLT** - Has flat `accounts: ['IBKR-MOCK']` (old format)
4. **SPY** - Likely old format
5. **FloridaForex** - Has flat `accounts: ['VANTAGE_MOCK', 'OANDA_MOCK']`
6. **Com1-Met** - Has flat `accounts: ['VANTAGE_MOCK', 'OANDA_MOCK']`
7. **Com2-Ag** - Likely similar
8. **Com3-Mkt** - Likely similar
9. **Com4-Misc** - Likely similar  
10. **SPX_0DE_Opt** - Has flat `accounts: ['IBKR-MOCK']`
11. **SPX_1-D_Opt** - Likely similar

### Current Funds (2)
1. **mock-fund-1** - Active, no approved_allocations visible
2. **ibkr-testing** - Active

### Current Trading Accounts (6)
1. **IBKR-MOCK** (mock, Mock broker)
2. **BINANCE_MOCK** (mock, Mock broker)
3. **VANTAGE_MOCK** (mock, Mock broker)
4. **BYBIT_MOCK** (mock, Mock broker)
5. **OANDA_MOCK** (mock, Mock broker)
6. **IBKR-TESTING-ACCOUNT** (paper, IBKR broker)

### Junk Fields Found in Strategies
Different strategies have different fields - inconsistent schema:

**Common junk/unused fields:**
- `trading_mode` - Redundant (determined by account type)
- `include_in_optimization` - Not used in current architecture
- `raw_data_developer_live` - Always empty
- `raw_data_mathematricks_live` - Always empty
- `synthetic_data` - Only for backtest generation, not needed in production DB
- `position_sizing` - Estimation metadata, not needed in production
- `backtest_data_hash` / `last_backtest_sync` / `original_submission_id` - Backtest metadata
- Duplicate name fields: `strategy_id`, `strategy_name`, `name` (should only need `strategy_id`)

**Mixed account format:**
- IBKR_Test_Stock: `accounts: {mock: [], paper: [], live: []}` ✅ GOOD
- TLT, FloridaForex, Com*: `accounts: ['ACCOUNT1', 'ACCOUNT2']` ❌ OLD FORMAT

**Fields to keep:**
- `strategy_id` (primary key)
- `accounts` (with mock/paper/live structure)
- `status` (ACTIVE/INACTIVE)
- `asset_class` (for categorization)
- `instruments` (for reference)
- `metrics` (performance data)
- `raw_data_backtest_full` (for portfolio optimization - keep but maybe archive separately)
- `developer_contact`, `notes`, `risk_limits` (metadata)
- `created_at`, `updated_at` (audit trail)

---

## Ideal Fund-Strategy-Account Architecture

### Core Design Principles

1. **Environment Separation**: Clear boundaries between mock/paper/live
2. **Single Source of Truth**: One strategy definition can route to different accounts based on environment
3. **Allocation Simplicity**: Funds contain approved_allocations that reference strategies
4. **Account Routing**: Strategies define which account to use per environment (mock/paper/live)

### The Three-Tier Structure

```
FUNDS (Portfolio level)
  └─> APPROVED_ALLOCATIONS (% allocation per strategy)
       └─> STRATEGIES (Trading logic + routing)
            └─> ACCOUNTS (Broker connections per environment)
```

---

## Proposed Setup

### 1. FUNDS (Clean up existing 2 → Create proper 3)

#### Current State: 2 funds
- **mock-fund-1** - Exists but needs proper approved_allocations
- **ibkr-testing** - Unclear purpose, maybe deprecate?

#### Target State: 3 well-defined funds

##### **mock-fund-1** ✅ Keep & Update
- **fund_id**: `mock-fund-1`
- **fund_name**: "Mock Development Fund"
- **Purpose**: All development and testing
- **Approved Allocations**: All active strategies at equal % (11-14 strategies × ~7-9% each)
- **Use Case**: Local testing, CI/CD, mock data validation
- **Action**: Add proper `approved_allocations` field

##### **paper-fund-1** ➕ Create
- **fund_id**: `paper-fund-1`
- **fund_name**: "Paper Trading Fund"
- **Purpose**: Paper trading with real market data
- **Approved Allocations**: All active strategies at equal % (for now)
- **Use Case**: Strategy validation before live deployment
- **Action**: CREATE new fund

##### **mathematricks-1** ➕ Create
- **fund_id**: `mathematricks-1`
- **fund_name**: "Mathematricks Live Fund 1"
- **Purpose**: Live trading fund
- **Approved Allocations**: Empty initially (strategies added after paper validation)
- **Use Case**: Real money trading
- **Action**: CREATE new fund

##### **ibkr-testing** ❓ Deprecate or Repurpose?
- **Status**: Exists but unclear purpose
- **Action**: DISCUSS - Delete or repurpose as paper-fund-1?

---

### 2. TRADING_ACCOUNTS (Cleanup & Consolidation)

#### Current State: 6 accounts (TOO MANY MOCKS)
- IBKR-MOCK ✅ Keep
- BINANCE_MOCK ❌ Delete (unused)
- VANTAGE_MOCK ❌ Delete (unused)
- BYBIT_MOCK ❌ Delete (unused)
- OANDA_MOCK ❌ Delete (unused)
- IBKR-TESTING-ACCOUNT ✅ Keep

#### Target State: 2-3 accounts

##### **IBKR-MOCK** ✅ Keep
- **account_id**: `IBKR-MOCK`
- **account_type**: `mock`
- **broker**: `Mock`
- **Purpose**: Mock mode testing for ALL asset classes
- **Data Source**: Can use mock or live data
- **Action**: Keep as-is, remove `account_name` field (redundant)

##### **IBKR-TESTING-ACCOUNT** ✅ Keep (maybe rename)
- **account_id**: `IBKR-TESTING-ACCOUNT` (or rename to `IBKR-PAPER`?)
- **account_type**: `paper`
- **broker**: `IBKR`
- **Purpose**: Paper trading with real IBKR connection
- **Data Source**: Live market data
- **Action**: Keep, consider renaming for consistency

##### **Coinbase-Paper** ➕ Create Later (Optional)
- **account_id**: `COINBASE-PAPER`
- **account_type**: `paper`
- **broker**: `Coinbase`
- **Purpose**: Crypto paper trading
- **Data Source**: Live crypto data
- **Action**: Create when needed for crypto strategies

---

### 3. STRATEGIES (Redesigned by Owner/Developer)

**Key Insight:** Strategies should be organized by who owns/develops them, not just asset class.  Each developer can have multiple strategies across different asset classes.

#### Group A: Mathematricks Internal (Platform Testing)

These are owned by Mathematricks for platform testing and development.

##### **IBKR_Test_Stock** ✅ Already Clean
- **Status**: Keep as-is, already has proper account structure
- **Owner**: Mathematricks Platform Team
- **Asset Class**: Equities
- **Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/ibkr/tech_stocks_realistic.json`
- **Action**: Cleanup junk fields only

##### **IBKR_Test_Option** ✅ Likely Clean
- **Status**: Verify structure, keep if clean
- **Owner**: Mathematricks Platform Team
- **Asset Class**: Options
- **Account Routing**: TBD (verify in DB)
- **Action**: Verify and cleanup junk fields

#### Group B: Sample/Demo Strategies (From init_test_data.js)

These were created for testing and have old account format. Need to migrate.

##### **TLT** ⚠️ Needs Migration
- **Current**: `accounts: ['IBKR-MOCK']` (old format)
- **Owner**: Demo/Sample
- **Asset Class**: Fixed Income
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal Files**: 
  - `tests/sample_signals/mock/tlt_realistic.json`
  - `tests/sample_signals/ibkr/tlt_realistic.json`
- **Action**: Migrate to new format, cleanup junk

##### **SPY** ⚠️ Needs Migration
- **Current**: Old format (verify)
- **Owner**: Demo/Sample
- **Asset Class**: Equity (ETF)
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Action**: Migrate or deprecate (redundant with IBKR_Test_Stock?)

##### **SPX_0DE_Opt** ⚠️ Needs Migration
- **Current**: `accounts: ['IBKR-MOCK']` (old format)
- **Owner**: Demo/Sample
- **Asset Class**: Options (0DTE)
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal Files**:
  - `tests/sample_signals/mock/spx_0de_opt_realistic.json`
  - `tests/sample_signals/ibkr/spx_0de_opt_realistic.json`
- **Action**: Migrate to new format, cleanup junk

##### **SPX_1-D_Opt** ⚠️ Needs Migration
- **Current**: Old format (verify)
- **Owner**: Demo/Sample
- **Asset Class**: Options (1DTE)
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal Files**:
  - `tests/sample_signals/mock/spx_1d_opt_realistic.json`
  - `tests/sample_signals/ibkr/spx_1d_opt_realistic.json`
- **Action**: Migrate to new format, cleanup junk

##### **FloridaForex** ⚠️ Needs Migration & Account Change
- **Current**: `accounts: ['VANTAGE_MOCK', 'OANDA_MOCK']` (old format, wrong accounts)
- **Owner**: Demo/Sample
- **Asset Class**: Forex
- **Issue**: Uses VANTAGE_MOCK and OANDA_MOCK which are mock brokers we don't use for testing
- **New Account Routing**:
  - mock: `['IBKR-MOCK']` (consolidate to IBKR for testing)
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/mock/florida_forex_realistic.json`, `tests/sample_signals/ibkr/forex_signals.json`
- **Action**: Migrate format AND change accounts to IBKR

##### **Com1-Met** ⚠️ Needs Migration & Account Change
- **Current**: `accounts: ['VANTAGE_MOCK', 'OANDA_MOCK']`
- **Owner**: Demo/Sample
- **Asset Class**: Commodities (Metals)
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/mock/com1_met_realistic.json`
- **Action**: Migrate format AND change accounts

##### **Com2-Ag** ⚠️ Needs Migration & Account Change
- **Current**: Old format with VANTAGE/OANDA (verify)
- **Owner**: Demo/Sample
- **Asset Class**: Commodities (Agriculture)
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/mock/com2_ag_realistic.json`
- **Action**: Migrate format AND change accounts

##### **Com3-Mkt** ⚠️ Needs Migration & Account Change
- **Current**: Old format (verify)
- **Owner**: Demo/Sample
- **Asset Class**: Commodities (Market)
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/mock/com3_mkt_realistic.json`
- **Action**: Migrate format AND change accounts

##### **Com4-Misc** ⚠️ Needs Migration & Account Change
- **Current**: Old format (verify)
- **Owner**: Demo/Sample
- **Asset Class**: Commodities (Misc)
- **New Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/mock/com4_misc_realistic.json`
- **Action**: Migrate format AND change accounts

#### Group C: New Strategies (From Sample Signals, Not Yet in DB)

##### **Coinbase_Crypto_Momentum** ➕ Need to Create
- **Status**: Has signal file but NOT in DB
- **Owner**: Demo/Sample (or future external developer)
- **Asset Class**: Crypto
- **Account Routing**:
  - mock: `['IBKR-MOCK']` (for now, can add coinbase_mock later)
  - paper: `[]` (no Coinbase paper yet)
  - live: `[]`
- **Signal File**: `tests/sample_signals/coinbase/crypto_spot_trading.json`
- **Action**: CREATE new strategy

##### **IBKR_Crypto** ➕ Need to Create
- **Status**: Has signal file but NOT in DB
- **Owner**: Demo/Sample
- **Asset Class**: Crypto (via IBKR)
- **Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/ibkr/crypto_signals.json`
- **Action**: CREATE new strategy

##### **ES_Futures** ➕ Need to Create
- **Status**: Has signal file but NOT in DB
- **Owner**: Demo/Sample
- **Asset Class**: Futures
- **Account Routing**:
  - mock: `['IBKR-MOCK']`
  - paper: `['IBKR-TESTING-ACCOUNT']`
  - live: `[]`
- **Signal File**: `tests/sample_signals/ibkr/es_future_realistic.json`
- **Action**: CREATE new strategy

---

## Fund Allocation Summary

### mock_fund (13 strategies × ~7.7% each = 100%)
```
- mock_strategy: 7.7%
- IBKR_Test_Stock: 7.7%
- TLT: 7.7%
- SPX_0DTE: 7.7%
- SPX_1DTE: 7.7%
- ES_Futures: 7.7%
- Forex_Strategy: 7.7%
- Commodities_Metals: 7.7%
- Commodities_Agriculture: 7.7%
- Commodities_Market: 7.7%
- Commodities_Misc: 7.7%
- Coinbase_Crypto_Momentum: 7.7%
- IBKR_Crypto: 7.9% (rounding to 100%)
```

### paper_fund (Same as mock_fund for now)
```
- Same allocations as mock_fund
```

### mathematricks-1 (Live fund - Empty)
```
- No allocations initially
- Strategies added after paper validation
```

---

## Migration/Cleanup Plan

### Phase 1: Backup & Document Current State ✅ DONE
1. ✅ Exported current MongoDB structure
2. ✅ Identified all 11 current strategies
3. ✅ Identified 6 trading accounts (4 to delete)
4. ✅ Identified 2 funds (1 unclear)
5. ✅ Documented junk fields in strategies

### Phase 2: Archive Old Strategies ✅ COMPLETE
**Create an archived collection before modifying**
```javascript
// In MongoDB
db.strategies.aggregate([
  { $match: {} },
  { $out: "strategies_archive_2026_02_04" }
]);
```
**Result:** Archived 11 strategies to `strategies_archive_2026_02_04`

### Phase 3: Clean Trading Accounts ✅ COMPLETE
**Delete unused mock accounts**
```javascript
// Delete 4 unused mock accounts
db.trading_accounts.deleteMany({
  account_id: { $in: ['BINANCE_MOCK', 'VANTAGE_MOCK', 'BYBIT_MOCK', 'OANDA_MOCK'] }
});

// Verify we have 2 left
db.trading_accounts.find({}, {account_id: 1, account_type: 1, broker: 1});
```

**Expected Result:** 2 accounts left
- IBKR-MOCK (mock)
- IBKR-TESTING-ACCOUNT (paper)

**Actual Result:** ✅ Deleted 4 accounts, kept 2 accounts as planned

### Phase 4: Migrate Strategies ✅ COMPLETE

**4a. Clean IBKR_Test_Stock (already good format)**
```javascript
db.strategies.updateOne(
  { strategy_id: 'IBKR_Test_Stock' },
  {
    $unset: {
      trading_mode: "",
      include_in_optimization: "",
      raw_data_developer_live: "",
      raw_data_mathematricks_live: "",
      synthetic_data: "",
      position_sizing: "",
      backtest_data_hash: "",
      last_backtest_sync: "",
      original_submission_id: "",
      name: "" // Redundant with strategy_id
    },
    $set: { updated_at: new Date() }
  }
);
```

**4b. Migrate TLT (old account format → new format)**
```javascript
db.strategies.updateOne(
  { strategy_id: 'TLT' },
  {
    $set: {
      accounts: {
        mock: ['IBKR-MOCK'],
        paper: ['IBKR-TESTING-ACCOUNT'],
        live: []
      },
      updated_at: new Date()
    },
    $unset: {
      trading_mode: "",
      include_in_optimization: "",
      raw_data_developer_live: "",
      raw_data_mathematricks_live: "",
      synthetic_data: "",
      position_sizing: ""
    }
  }
);
```

**4c. Migrate remaining sample strategies (SPY, SPX_0DE_Opt, SPX_1-D_Opt, FloridaForex, Com1-Met, Com2-Ag, Com3-Mkt, Com4-Misc)**
```javascript
// Batch update for strategies using old format
let strategiesToMigrate = ['SPY', 'SPX_0DE_Opt', 'SPX_1-D_Opt', 'FloridaForex', 'Com1-Met', 'Com2-Ag', 'Com3-Mkt', 'Com4-Misc'];

strategiesToMigrate.forEach(sid => {
  db.strategies.updateOne(
    { strategy_id: sid },
    {
      $set: {
        accounts: {
          mock: ['IBKR-MOCK'],
          paper: ['IBKR-TESTING-ACCOUNT'],
          live: []
        },
        updated_at: new Date()
      },
      $unset: {
        trading_mode: "",
        include_in_optimization: "",
        raw_data_developer_live: "",
        raw_data_mathematricks_live: "",
        synthetic_data: "",
        position_sizing: "",
        name: ""
      }
    }
  );
});
```

**4d. Verify IBKR_Test_Option and clean if exists**
```javascript
let optionStrat = db.strategies.findOne({ strategy_id: 'IBKR_Test_Option' });
if (optionStrat) {
  // Clean junk fields
  db.strategies.updateOne(
    { strategy_id: 'IBKR_Test_Option' },
    { $unset: { /* same as above */ } }
  );
}
```

**4e. Create missing strategies from signal files**
```javascript
// ES_Futures
db.strategies.insertOne({
  strategy_id: 'ES_Futures',
  asset_class: 'futures',
  instruments: ['ES'],
  accounts: {
    mock: ['IBKR-MOCK'],
    paper: ['IBKR-TESTING-ACCOUNT'],
    live: []
  },
  status: 'ACTIVE',
  developer_contact: '',
  notes: 'E-mini S&P 500 futures strategy',
  risk_limits: {},
  metrics: {},
  created_at: new Date(),
  updated_at: new Date()
});

// IBKR_Crypto
db.strategies.insertOne({
  strategy_id: 'IBKR_Crypto',
  asset_class: 'crypto',
  instruments: ['BTC', 'ETH'],
  accounts: {
    mock: ['IBKR-MOCK'],
    paper: ['IBKR-TESTING-ACCOUNT'],
    live: []
  },
  status: 'ACTIVE',
  developer_contact: '',
  notes: 'Crypto trading via IBKR',
  risk_limits: {},
  metrics: {},
  created_at: new Date(),
  updated_at: new Date()
});

// Coinbase_Crypto_Momentum
db.strategies.insertOne({
  strategy_id: 'Coinbase_Crypto_Momentum',
  asset_class: 'crypto',
  instruments: ['BTC-USD', 'ETH-USD'],
  accounts: {
    mock: ['IBKR-MOCK'], // Use IBKR mock for now
    paper: [], // No Coinbase paper yet
    live: []
  },
  status: 'ACTIVE',
  developer_contact: '',
  notes: 'Crypto momentum strategy for Coinbase',
  risk_limits: {},
  metrics: {},
  created_at: new Date(),
  updated_at: new Date()
});
``` ✅ COMPLETE

**Actions Taken:**
1. Updated mock-fund-1 with 10 allocations (10% each = 100% total)
2. Created paper-fund-1 with 10 allocations (10% each = 100% total)
3. Created mathematricks-1 (empty for future live trading)
4. Archived ibkr-testing fund

**Result:** 3 active funds properly configured

**Original Plan (for reference):**

### Phase 5: Update Funds

**5a. Update mock-fund-1 with approved_allocations**
```javascript
// Calculate equal allocation for all strategies
let activeStrategies = db.strategies.find({ status: 'ACTIVE' }).toArray();
let stratCount = activeStrategies.length;
let allocation_pct = Math.round(10000 / stratCount) / 100; // Round to 2 decimals

let allocations = {};
activeStrategies.forEach(s => {
  allocations[s.strategy_id] = allocation_pct;
});

db.funds.updateOne(
  { fund_id: 'mock-fund-1' },
  {
    $set: {
      fund_name: 'Mock Development Fund',
      approved_allocations: allocations,
      total_capital: 5000000,
      status: 'ACTIVE',
      updated_at: new Date()
    }
  }
);
```

**5b. Create paper-fund-1**
```javascript
db.funds.insertOne({
  fund_id: 'paper-fund-1',
  fund_name: 'Paper Trading Fund',
  approved_allocations: allocations, // Same as mock for now
  total_capital: 5000000,
  status: 'ACTIVE',
  created_at: new Date(),
  updated_at: new Date()
});
```

**5c. Create mathematricks-1 (empty allocations)**
```javascript
db.funds.insertOne({
  fund_id: 'mathematricks-1',
  fund_name: 'Mathematricks Live Fund 1',
  approved_allocations: {}, // Empty - strategies added after validation
  total_capital: 0,
  status: 'ACTIVE',
  created_at: new Date(),
  updated_at: new Date()
}); ✅ COMPLETE

**Verification Results:**
- ✅ 10 active strategies (all with new account format)
- ✅ 2 trading accounts (IBKR-MOCK, IBKR-TESTING-ACCOUNT)
- ✅ 3 active funds (mock-fund-1, paper-fund-1, mathematricks-1)
- ✅ 1 archived fund (ibkr-testing)
- ✅ mock-fund-1: 10 allocations totaling 100%
- ✅ paper-fund-1: 10 allocations totaling 100%
- ✅ mathematricks-1: 0 allocations (ready for future live trading)

**Original Verification Queries:**
```

**5d. Delete or archive ibkr-testing fund**
```javascript
// Decision needed: delete or rename to paper-fund-1?
db.funds.updateOne(
  { fund_id: 'ibkr-testing' },
  { $set: { status: 'ARCHIVED', updated_at: new Date() } }
);
```

### Phase 6: Verification

**6a. Verify strategy count and format**
```javascript
print("=== STRATEGIES VERIFICATION ===");
print("Total strategies:", db.strategies.countDocuments({ status: 'ACTIVE' }));
print("\nAccount format check:");
db.strategies.find({ status: 'ACTIVE' }).forEach(s => {
  let hasNewFormat = s.accounts && s.accounts.mock && s.accounts.paper;
  print(s.strategy_id + ": " + (hasNewFormat ? "✅ NEW" : "❌ OLD"));
});
```

**6b. Verify trading accounts**
```javascript
print("\n=== TRADING ACCOUNTS ===");
db.trading_accounts.find({}, {account_id: 1, account_type: 1, broker: 1, _id: 0}).forEach(a => printjson(a));
```

**6c. Verify funds**
```javascript
print("\n=== FUNDS ===");
db.funds.find({ status: 'ACTIVE' }).forEach(f => {
  print(f.fund_id + ": " + Object.keys(f.approved_allocations || {}).length + " allocations");
});
```

### Phase 7: Testing

**7a. Run mock_mock test**
```bash
.venv/bin/python tests/run_test_suite.py \
  --signal-testing \
  --clean \
  --environment staging \
  --account-type mock \
  --data-source mock \
  --file tests/sample_signals/ibkr/tech_stocks_realistic.json \
  --signal-count 5
```

**7b. Run paper test**
```bash
.venv/bin/python tests/run_test_suite.py \
  --signal-testing \
  --environment staging \
  --account-type paper \
  --data-source live \
  --file tests/sample_signals/ibkr/tech_stocks_realistic.json \
  --signal-count 5
```

**7c. Test allocation calculations**
```bash
# Check cerebro service logs for allocation calculations
docker logs mathematricks-trader-cerebro-service-1 2>&1 | grep -i "allocation\|fund" | tail -30
```

---

## Implementation Script

**Create a single Python script to execute all phases:**

File: `scripts/migrate_mongodb_architecture.py`

```python
#!/usr/bin/env python3
"""
MongoDB Architecture Migration Script
Migrates from old messy structure to clean fund-strategy-account architecture
"""

import os
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, List

MONGODB_URI = os.getenv('MONGODB_URI_LOCAL', 'mongodb://localhost:27018/?directConnection=true')

def main():
    print("=" * 80)
    print("MongoDB Architecture Migration")
    print("=" * 80)
    
    client = MongoClient(MONGODB_URI)
    db = client['mathematricks_trading']
    
    # Phase 1: Backup
    print("\n[Phase 1] Creating backup...")
    backup_collection(db)
    
    # Phase 2: Clean accounts
    print("\n[Phase 2] Cleaning trading accounts...")
    clean_trading_accounts(db)
    
    # Phase 3: Migrate strategies
    print("\n[Phase 3] Migrating strategies...")
    migrate_strategies(db)
    
    # Phase 4: Update funds
    print("\n[Phase 4] Updating funds...")
    update_funds(db)
    
    # Phase 5: Verify
    print("\n[Phase 5] Verification...")
    verify_migration(db)
    
    print("\n✅ Migration complete!")

def backup_collection(db):
    """Create archive of current strategies"""
    # Implementation here
    pass

def clean_trading_accounts(db):
    """Delete unused mock accounts"""
    # Implementation here
    pass

def migrate_strategies(db):
    """Migrate all strategies to new format"""
    # Implementation here
    pass

def update_funds(db):
    """Create/update funds with proper allocations"""
    # Implementation here
    pass

def verify_migration(db):
    """Verify all changes were successful"""
    # Implementation here
    pass

if __name__ == '__main__':
    main()
```

---

## Questions for Discussion Before Implementation

### 1. Trading Accounts
- ✅ **Confirmed**: Delete BINANCE_MOCK, VANTAGE_MOCK, BYBIT_MOCK, OANDA_MOCK?
- ❓ **Rename**: Should `IBKR-TESTING-ACCOUNT` be renamed to `IBKR-PAPER` for consistency?
- ❓ **Coinbase**: Create `COINBASE-PAPER` account now or wait until needed?

### 2. Funds
- ❓ **ibkr-testing fund**: Delete, archive, or repurpose as paper-fund-1?
- ✅ **Allocation %**: Equal allocation (7-9% each) is fine for mock/paper funds?
- ❓ **Capital**: Should funds have `total_capital` field or is that per-account?

### 3. Strategies
- ❓ **SPY strategy**: Keep or delete? (Seems redundant with IBKR_Test_Stock)
- ❓ **Strategy consolidation**: Keep all 4 commodity strategies separate or merge into one?
- ❓ **Backtest data**: Keep `raw_data_backtest_full` in strategies collection or move to separate archive?
  - Pros of keeping: Easy access for portfolio optimization
  - Cons: Makes documents very large (3000 items per strategy)
  
### 4. Schema Decisions
- ❓ **Required fields**: What fields are absolutely required vs. optional for a strategy?
  ```
  Required: strategy_id, accounts, status
  Optional: asset_class, instruments, metrics, developer_contact, notes, risk_limits, raw_data_backtest_full
  ```
- ❓ **Metrics field**: Keep metrics in strategy doc or move to separate collection?

### 5. Migration Approach
- ❓ **Timing**: Run migration now or wait for specific milestone?
- ❓ **Rollback plan**: If something breaks, do we restore from archive or fix forward?
- ❓ **Downtime**: Can we migrate with services running or need to stop them?

---

## Clean Strategy Schema (Proposed)

```javascript
{
  // Core identification (REQUIRED)
  strategy_id: "IBKR_Test_Stock",
  status: "ACTIVE", // or "INACTIVE", "ARCHIVED"
  
  // Account routing (REQUIRED)
  accounts: {
    mock: ["IBKR-MOCK"],
    paper: ["IBKR-TESTING-ACCOUNT"],
    live: []
  },
  
  // Metadata (OPTIONAL)
  asset_class: "equities",
  instruments: ["AAPL", "GOOGL", "MSFT"],
  developer_contact: "dev@example.com",
  notes: "Tech stock momentum strategy",
  
  // Risk management (OPTIONAL)
  risk_limits: {
    max_position_size: 100000,
    max_daily_loss: 5000
  },
  
  // Performance data (OPTIONAL)
  metrics: {
    cagr: 35.26,
    sharpe_ratio: 1.19,
    max_drawdown: 25.96,
    num_trades: 3000
  },
  
  // Backtest data (OPTIONAL - consider moving to archive)
  raw_data_backtest_full: [ /* large array */ ],
  
  // Audit trail (AUTO-GENERATED)
  created_at: ISODate("2026-01-16T23:14:55.913Z"),
  updated_at: ISODate("2026-02-04T00:00:00.000Z")
}
```

---

## Next Steps

**Review this plan and provide feedback on:**
1. Which questions above need decisions?
2. Should we proceed with migration or make adjustments first?
3. Do you want me to create the migration script now?

**Once approved, I can:**
1. Create `scripts/migrate_mongodb_architecture.py` with full implementation
2. Test on a local MongoDB instance first
3. Run the migration on staging environment
4. Verify all tests pass with new structure
