# Execution Modes Architecture

**Last Updated**: 2026-01-29  
**Status**: FROZEN - Under Review
MONGODB is running on 27018
---

## 🎯 FINAL ARCHITECTURE PROPOSAL

### Core Concepts

The system uses **THREE independent user inputs** that work together to determine execution behavior:

#### 1. **environment** (High-Level Safety Override)
- **Purpose**: Prevent accidental real-money execution
- **Values**:
  - `staging`: Safe testing environment - ONLY allows mock/paper accounts
  - `live`: Production environment - allows ALL account types (including real money)
- **Validation**: Enforced at execution service - rejects invalid combinations
- **Example**: `environment=staging` + `account_type=live` → ❌ REJECTED

#### 2. **account_type** (Where Orders Execute)
- **Purpose**: Determines which account executes orders
- **Values**:
  - `mock`: Unlimited virtual funds, simulated execution
  - `paper`: Limited IBKR paper account (~$154K CAD), real broker API
  - `live`: Real money account, real broker API
- **Account Routing**: Strategy documents define allowed accounts per type:
  ```json
  {
    "strategy_id": "IBKR_Test_Stock",
    "accounts": {
      "mock": ["IBKR-MOCK"],
      "paper": ["IBKR-TESTING-ACCOUNT"],
      "live": ["IBKR-LIVE-ACCOUNT"]
    }
  }
  ```

#### 3. **data_source** (Where Market Data Comes From)
- **Purpose**: Determines where to fetch prices, quotes, contract details
- **Values**:
  - `mock`: Simulated/hardcoded prices (no external API calls)
  - `live`: Real IBKR market data (live quotes, real prices)
- **BrokerModeAdapter**: Routes data operations to appropriate broker instance

---

### Derived Concept: mode

**NOT a user input** - automatically calculated by the system.

- **Formula**: `mode = "{account_type}_{data_source}"`
- **Purpose**: Shorthand identifier for logging and internal routing
- **Valid Combinations**:
  | mode | account_type | data_source | Use Case |
  |------|--------------|-------------|----------|
  | `mock_mock` | mock | mock | Full simulation, no external dependencies |
  | `mock_live` | mock | live | Test with real market data, no money at risk |
  | `paper_mock` | paper | mock | Test paper execution with fake data |
  | `paper_live` | paper | live | Paper trading with real market data |
  | `live_mock` | live | mock | ⚠️ Real money with fake data (discouraged) |
  | `live_live` | live | live | Full production - real money + real data |

---

## 🔄 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER INPUT (Test Suite / Signal Sender)                     │
│    → environment: staging/live                                  │
│    → account_type: mock/paper/live                              │
│    → data_source: mock/live                                     │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. SIGNAL CREATION (send_test_signal.py)                       │
│    → Adds to signal payload: environment, account_type,        │
│      data_source                                                │
│    → Derives mode = f"{account_type}_{data_source}"            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. SIGNAL RECEIVER (webhook API)                               │
│    → Stores in trading_signals_raw:                             │
│      {environment, account_type, data_source, mode, ...}        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. MONGODB WATCHER (change stream)                             │
│    → Extracts from raw signal                                   │
│    → Passes to signal-ingestion                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. SIGNAL INGESTION                                             │
│    → Stores in signal_store:                                    │
│      {environment, account_type, data_source, mode, ...}        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. CEREBRO SERVICE (position sizing & routing)                  │
│    → Reads mode from signal                                     │
│    → Extracts account_type = mode.split('_')[0]                 │
│    → Looks up strategy.accounts[account_type]                   │
│    → Routes to correct account (e.g., IBKR-MOCK for mock)       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. EXECUTION SERVICE (order submission)                         │
│    → Validates environment + account_type combination           │
│    → Creates BrokerModeAdapter(account_type, data_source)       │
│    → Routes data operations to data_broker (for prices)         │
│    → Routes execution operations to execution_broker (orders)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ Validation Rules

### Environment + Account Type Matrix

| environment | account_type | Valid? | Reason |
|-------------|--------------|--------|--------|
| staging | mock | ✅ | Safe testing |
| staging | paper | ✅ | Safe testing with limited funds |
| staging | live | ❌ | REJECTED - staging prevents real money |
| live | mock | ✅ | Allowed (though unusual in production) |
| live | paper | ✅ | Allowed (though unusual in production) |
| live | live | ✅ | Full production |

### Implementation Location
- **Execution Service** (`execution_main.py`): Validates before creating BrokerModeAdapter
- **Cerebro Service**: No validation (trusts signal_store data)
- **Signal Sender**: Validates before sending (optional, for UX)

---

## 🏗️ Current Implementation Status

### ✅ FULLY IMPLEMENTED (2026-01-29)
- [x] BrokerModeAdapter class with data/execution routing
- [x] Execution service validation (environment + account_type)
- [x] Test suite CLI flags (--environment, --account-type, --data-source)
- [x] send_test_signal.py adds all FOUR fields (environment, account_type, data_source, mode)
- [x] mongodb_watcher extracts all FOUR fields from raw signals (catchup + real-time)
- [x] signal_store schema includes all FOUR fields
- [x] Mode-specific account structure in strategies collection
- [x] **account_type field flowing through entire pipeline** ✅
- [x] **cerebro mode-aware account routing** ✅
- [x] **mode field derived and stored correctly** ✅
- [x] **IBKR_Test_Stock strategy updated to mode-specific format** ✅

### 🎯 VALIDATED
**Test Results (mock_live mode)**:
```
Signal: sig_1769713245_4898
Environment: staging
Account Type: mock  
Data Source: live
Mode: mock_live

Cerebro Logs:
  [MODE-AWARE] Mode: mock_live → Account Type: mock
  [MODE-AWARE] Using mode-specific accounts for mock: ['IBKR-MOCK']
  [DEBUG] Found 1 matching accounts
  🎯 Found 1 available account(s):
     • IBKR-MOCK: $1,000,000.00 equity, $500,000.00 margin
```

### ⚠️ Remaining Tasks
- [ ] **signal-receiver validation** - add input validation for all 4 fields
- [ ] **IBKR_Test_Option strategy** - migrate to mode-specific format
- [ ] **Test all mode combinations** - mock_mock, paper_live, etc.
- [ ] **Documentation updates** - README, architecture docs

---

## 📋 IMPLEMENTATION PLAN

### Service-by-Service Responsibilities

#### 1. send_test_signal.py (Test Signal Generator)
**Responsibilities**:
- Accept CLI params or function args: environment, account_type, data_source
- Derive mode = f"{account_type}_{data_source}"
- Add all four fields to signal payload
- Validate inputs before sending

**Required Fields in Payload**:
```python
{
  "environment": "staging",      # User input
  "account_type": "mock",         # User input
  "data_source": "live",          # User input
  "mode": "mock_live",            # Derived
  # ... rest of signal
}
```

**Current Status**: Adds environment, data_source, mode - **MISSING account_type**

---

#### 2. Signal Receiver API (signals.cjs)
**Responsibilities**:
- Receive webhook signal
- Validate all four fields exist
- Validate environment ∈ {staging, live}
- Validate account_type ∈ {mock, paper, live}
- Validate data_source ∈ {mock, live}
- Validate mode = f"{account_type}_{data_source}"
- Validate environment+account_type combo (reject staging+live)
- Store in trading_signals_raw with ALL fields

**Current Status**: Only logs fields - **NO VALIDATION**

---

#### 3. MongoDB Watcher (mongodb_watcher.py)
**Responsibilities**:
- Watch trading_signals_raw for new documents
- Extract all four fields from raw signal
- Pass to signal-ingestion callback
- Build signal_store document with all fields

**Required Extraction**:
```python
signal_data = {
    'environment': raw_signal_doc.get('environment', 'staging'),
    'account_type': raw_signal_doc.get('account_type'),
    'data_source': raw_signal_doc.get('data_source', 'mock'),
    'mode': raw_signal_doc.get('mode'),
    # ... other fields
}
```

**Current Status**: Extracts environment, data_source, mode - **MISSING account_type**

---

#### 4. Signal Ingestion (signal_ingestion_main.py)
**Responsibilities**:
- Receive signal data from watcher
- Validate all four fields present (warn if missing)
- Process signal and create signal_store document
- Ensure all fields stored in signal_store

**Current Status**: Passes through data from watcher - **needs validation**

---

#### 5. Cerebro Service (cerebro_main.py)
**Responsibilities**:
- Read signal from Pub/Sub (includes all fields)
- Extract mode or account_type for routing
- Look up strategy.accounts[account_type]
- Filter accounts by fund_id
- Route signal to correct account
- Send order to execution service with all fields

**Account Routing Logic**:
```python
mode = signal.get('mode')  # e.g., "mock_live"
account_type = mode.split('_')[0]  # "mock"
allowed_accounts = strategy['accounts'][account_type]  # ["IBKR-MOCK"]
```

**Current Status**: Code written but mode is None - **Pub/Sub message missing mode**

---

#### 6. Execution Service (execution_main.py)
**Responsibilities**:
- Receive order from cerebro (includes all fields)
- Validate environment+account_type combo
- Extract account_type and data_source
- Create BrokerModeAdapter(account_type, data_source)
- Execute order using adapter
- Log all four fields

**Validation**:
```python
if environment == 'staging' and account_type == 'live':
    raise ValueError("Cannot use live account in staging environment")
```

**Current Status**: Validation exists - **WORKS CORRECTLY**

---

### Priority 0: Fix Core Data Flow

#### Task 1: Add `account_type` field everywhere
**Problem**: account_type is a user input but not stored in pipeline - only mode exists.

**Files to Change**:
1. **tests/send_test_signal.py** (line ~287-290)
   - Add: `signal_payload["account_type"] = account_type`
   - Ensure account_type parameter flows from process_folder() to send_signal()

2. **services/signal_ingestion/mongodb_watcher.py** (3 locations)
   - Line ~322 (catchup): `'account_type': raw_signal_doc.get('account_type')`
   - Line ~595 (real-time): `'account_type': raw_signal_doc.get('account_type')`  
   - Line ~155 (_build_signal_store_doc): Add account_type to signal_store schema

3. **Validation Check**:
   ```python
   db.signal_store.findOne({}, {account_type: 1, mode: 1, environment: 1, data_source: 1})
   # Expected: {account_type: "mock", mode: "mock_live", environment: "staging", data_source: "live"}
   ```

**Status**: Ready to implement

---

#### Task 2: Fix Cerebro to receive mode from signal_store
**Problem**: Cerebro logs show "[LEGACY] No mode provided" - mode field not in signal object.

**Root Cause Investigation**:
1. ✅ cerebro_main.py passes `mode = signal.get('mode')` to account lookup
2. ✅ fund_allocation_logic.py accepts mode parameter
3. ❌ **signal object doesn't have mode field** when cerebro processes it

**Why mode is missing**:
- Cerebro receives signal via Pub/Sub from mongodb_watcher
- mongodb_watcher publishes specific fields, NOT entire signal_store document
- Need to check what fields are published in Pub/Sub message

**Files to Investigate & Fix**:
1. **services/signal_ingestion/mongodb_watcher.py**
   - Find where Pub/Sub message is built for cerebro
   - Ensure mode, account_type, environment, data_source are included
   - Search for: `publish_signal_to_pubsub` or similar function

2. **Alternative Fix** (if Pub/Sub already has all fields):
   - Check signal_store schema - verify mode is stored
   - Check cerebro's signal extraction logic
   - May need to extract from nested field (signal.raw.mode vs signal.mode)

**Validation**:
- Cerebro logs should show: `[MODE-AWARE] Mode: mock_live → Account Type: mock`
- Cerebro logs should show: `Using mode-specific accounts for mock: ['IBKR-MOCK']`

**Status**: Need to find Pub/Sub message builder and add mode field

---

#### Task 3: Migrate Strategy Documents
**Problem**: Existing strategies may use legacy flat account lists.

**Fix**:
- [x] `IBKR_Test_Stock`: Updated to mode-specific structure
- [ ] `IBKR_Test_Option`: Update to mode-specific structure
- [ ] All other strategies: Audit and update

**Schema**:
```json
// OLD (LEGACY):
{
  "strategy_id": "IBKR_Test_Stock",
  "accounts": ["IBKR-TESTING-ACCOUNT"]
}

// NEW (MODE-AWARE):
{
  "strategy_id": "IBKR_Test_Stock",
  "accounts": {
    "mock": ["IBKR-MOCK"],
    "paper": ["IBKR-TESTING-ACCOUNT"],
    "live": ["IBKR-LIVE-ACCOUNT"]
  }
}
```

**Backward Compatibility**: fund_allocation_logic.py already handles both formats.

---

### Priority 1: Clean Up Field Names

**Problem**: Inconsistent terminology across services.

**Standardize**:
- Use `account_type` everywhere (NOT `account_mode`, `broker_type`, etc.)
- Use `data_source` everywhere (NOT `data_mode`, `market_data_source`, etc.)
- Use `environment` everywhere (NOT `env`, `execution_env`, etc.)
- Use `mode` everywhere (NOT `execution_mode`, `broker_mode`, etc.)

**Audit Locations**:
- [ ] send_test_signal.py
- [ ] signal-receiver API (signals.cjs)
- [ ] mongodb_watcher.py
- [ ] signal_ingestion (if it processes these fields)
- [ ] cerebro_main.py
- [ ] execution_main.py
- [ ] BrokerModeAdapter class

---

### Priority 2: Add Validation at Each Layer

#### Signal Receiver (webhook API)
**Location**: `mathematricks-website/netlify/functions/signals.cjs`

**Add**:
- [ ] Validate environment is 'staging' or 'live'
- [ ] Validate account_type is 'mock', 'paper', or 'live'
- [ ] Validate data_source is 'mock' or 'live'
- [ ] Validate environment + account_type combination
- [ ] Reject invalid signals with 400 error

---

#### Signal Ingestion
**Location**: `services/signal_ingestion/signal_ingestion_main.py`

**Add**:
- [ ] Validate all four fields exist (environment, account_type, data_source, mode)
- [ ] Validate mode matches account_type + data_source
- [ ] Log warning if fields missing (for backward compatibility)

---

#### Cerebro Service
**Location**: `services/cerebro_service/cerebro_main.py`

**Add**:
- [ ] Validate mode field exists in signal
- [ ] Validate strategy.accounts[account_type] exists
- [ ] Reject signal if account_type not supported by strategy
- [ ] Log clear error messages

---

#### Execution Service
**Location**: `services/execution_service/execution_main.py`

**Current**: Already validates environment + account_type ✅

**Enhance**:
- [ ] Validate all fields exist before creating BrokerModeAdapter
- [ ] Return clear error to cerebro if validation fails
- [ ] Log all four fields at order creation time

---

### Priority 3: Testing & Validation

#### Test All Mode Combinations
- [ ] `mock_mock`: Full simulation (baseline test)
- [ ] `mock_live`: Mock execution + real IBKR data (main use case)
- [ ] `paper_mock`: Paper execution + fake data
- [ ] `paper_live`: Paper trading with real data
- [ ] `live_live`: Production (manual test only, not automated)

#### Test Validation Rejections
- [ ] staging + live account → should REJECT at execution service
- [ ] Strategy without mock accounts + mock_live signal → should REJECT at cerebro
- [ ] Missing mode field → should handle gracefully or reject

#### Test Account Routing
- [ ] mock_live signal → routes to IBKR-MOCK account
- [ ] paper_live signal → routes to IBKR-TESTING-ACCOUNT
- [ ] Verify BrokerModeAdapter uses correct broker instances

---

### Priority 4: Documentation & Cleanup

#### Update Documentation
- [ ] Update README.md with mode architecture
- [ ] Update IBKR_TESTING_COMPLETION_GUIDE.md with mode examples
- [ ] Update system_architecture.md with field flow diagram
- [ ] Add this MODES.md to main documentation index

#### Remove Redundant Code
- [ ] Remove any old `staging` boolean logic (replaced by environment)
- [ ] Remove any hardcoded broker selection (replaced by BrokerModeAdapter)
- [ ] Consolidate validation logic (don't duplicate across services)

#### Add Type Safety
- [ ] Add enums for environment, account_type, data_source
- [ ] Add Pydantic models for signal schema
- [ ] Add type hints for mode-related parameters

---

## 🔍 Debug Checklist

When mode-based routing isn't working:

1. **Check signal_store document**:
   ```python
   db.signal_store.findOne(
     {signal_id: "sig_xxx"},
     {environment: 1, account_type: 1, data_source: 1, mode: 1, _id: 0}
   )
   ```
   Expected: All four fields present and correct

2. **Check cerebro logs**:
   - Should see: `mode = signal.get('mode')` extracting mode
   - Should see: `[MODE-AWARE] Mode: {mode} → Account Type: {account_type}`
   - Should NOT see: `[LEGACY] No mode provided`

3. **Check execution logs**:
   - Should see: `Creating broker adapter: environment={env}, account_type={type}, data_source={source}`
   - Should see: `Determined mode: {mode}`

4. **Check strategy document**:
   ```python
   db.strategies.findOne(
     {strategy_id: "IBKR_Test_Stock"},
     {accounts: 1, _id: 0}
   )
   ```
   Expected: `accounts: {mock: [...], paper: [...], live: [...]}`

5. **Check account exists in fund**:
   ```python
   db.funds.findOne(
     {fund_id: "mock-fund-1"},
     {accounts: 1, _id: 0}
   )
   ```
   Expected: `accounts: ["IBKR-MOCK", ...]` contains the target account

---

## 📝 Notes

### Why Three Separate Fields?

**Alternative Considered**: Use only `mode` (e.g., "mock_live") and parse it everywhere.

**Why Rejected**:
- Parsing `mode.split('_')` in multiple places is error-prone
- Validation logic needs separate access to environment, account_type, data_source
- BrokerModeAdapter needs account_type and data_source explicitly
- Cerebro needs account_type for routing
- More explicit = clearer intent and easier debugging

**Chosen Approach**: Store all three inputs + derived mode
- Clear separation of concerns
- Each service uses what it needs
- mode is convenience for logging/debugging

### Why Not Just Use environment?

**Alternative Considered**: Only use environment (staging/live) and infer everything else.

**Why Rejected**:
- Conflates "safety level" with "execution method" and "data source"
- Can't express "test with real data but no money" (mock_live)
- Can't test paper trading with simulated data (paper_mock)
- Loses flexibility for different testing scenarios

### Why Derive mode?

**Alternative Considered**: Make users specify mode directly instead of account_type + data_source.

**Why Rejected**:
- mode is just a shorthand: `f"{account_type}_{data_source}"`
- Users think in terms of "which account" and "which data"
- Deriving mode eliminates possibility of mismatch
- Less cognitive load on users

---

## 🎯 Success Criteria

**System is considered fixed when**:

1. ✅ All four fields (environment, account_type, data_source, mode) flow through entire pipeline
2. ✅ Cerebro logs show mode-aware account routing
3. ✅ mock_live test routes to IBKR-MOCK account
4. ✅ paper_live test routes to IBKR-TESTING-ACCOUNT  
5. ✅ BrokerModeAdapter correctly routes data vs execution operations
6. ✅ Validation rejects invalid combinations (staging + live account)
7. ✅ All tests pass (mock_mock, mock_live, paper_live)
8. ✅ Clean logs with no "[LEGACY]" warnings
9. ✅ Documentation updated and complete

---

**END OF DOCUMENT**
