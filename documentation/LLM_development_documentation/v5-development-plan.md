# DEVELOPMENT PLAN


TASK 1: RESTRUCTING SYSTEM ACCOUNTS ARCHITECTURE
The system has a major flaw. right now we have strategies that are optimized directly on the account (main mock broker account). the way the system will actually run is that it'll be handling multiple top-level funds.....each fund will have accounts and each account has a broker through which the orders are placed. the account in this case is the broker account number, eg. ibkr DU232324243, binance 234235332432234 vantage ZA23432432 etc. 
Now, each fund will be associated with a certain 'optimization strategy' and each optimization strategy will have straetgies under it, and each straetgy will be allowed to send signals to specific accounts. (obviously, all strategies can send signals to the mock broker account as default).

Now when a signal comes in, step 1 for cerebro, will be to check which strategy is the signal for. then it'll check which all optimization strategies are active. then it'll check this strategy, for which the signal has just come in, is part of which all 'active optimization strategies'....then one by one for each active optimization strategy, it'll first check what % of the fund (eg. mathematricks-1) it's allowed to use. lets say 10%. Then it'll check the current value of the fund. lets say 750k. which means this straetgy has 75k of mathematricks-1. then it'll check how much % of it's allocation should it put on this signal. lets say 20%. which means 20% of 75k = 15k. Then it checks how much is already allocated. lets say 25k is allocated. which means 50k is available. so if 15k < 50k, then the signal goes though. Now it checks which accounts it has access to. lets say it has access to 2 accounts for this specific asset class, 1 has 8k margin left and one has 15k margin left, then it'll do 7.5k 7.5 in ach account. if it was 2k and 15k, then it'll do 2k and 13k. and cerebro sends the orders to the execution service, which places the orders on the respective accounts.

1. Fund Architecture
    - There is a 'Funds' db, which has FundName: Mathematricks-1
    - Then there is an "Accounts" db: which has accounts in it. Each account is associated to one Parent Fund: FundName. and account balance. and open positions. Also, which asset classes each account trades are in a field. eg. Equity:[all], crypto:[all], crypto:[btc, usdt, xrp], forex:[all].
    - Then there are strategies db: A strategy will have which accounts it's allowed to trade

2. Account Data Services:
    - Updates account balances and open positions to each account in accounts db.
    - Logs details of account balances and open positions, by fund.

IN THE FRONTEND:
we need to take the above and add tabs for the following functionalities:
- Add Fund (Fund Name)
    - Add Accounts to fund (Broker: broker account number + other fields -- all should be dropdowns)
- In the Allocations tab, in part 1, there should be a dropdown for 'Fund Name' and in Part 2: when u approve an optimization, there should be a field which lets you know which fund it's being assigned to.

---

# IMPLEMENTATION PLAN

## ✅ PHASE 1: IMMEDIATE FIX (Get System Working) - COMPLETED

### ✅ 1.1 Create Emergency Fix Script
**File:** `scripts/fix_strategy_accounts.py`

**Purpose:** Add `accounts: ["Mock_Paper"]` to all strategies missing the field

**Completed:**
- ✅ Created script that connects to MongoDB
- ✅ Finds all strategies where `accounts` field is missing or empty
- ✅ Updates with `{"$set": {"accounts": ["Mock_Paper"]}}`
- ✅ Logs changes made
- ✅ Verifies update count
- ✅ Fixed 9 strategies: Com1-Met, Com2-Ag, Com3-Mkt, Com4-Misc, FloridaForex, SPX_0DE_Opt, SPX_1-D_Opt, SPY, TLT

### ✅ 1.2 Test Signal Acceptance
**Completed:**
- ✅ Started docker services with `make start`
- ✅ Sent test signal with `make send-test-signal`
- ✅ Verified NO "NO_ACCOUNTS_CONFIGURED" error
- ✅ Verified order reaches execution service via Pub/Sub
- ✅ End-to-end flow working: Signal → Cerebro → Pub/Sub → Execution → Broker

**Additional Fixes Applied:**
- ✅ Fixed PUBSUB_PROJECT_ID environment variable across 4 services
- ✅ Added Pub/Sub retry logic to execution service
- ✅ Created timestamped seed data export system
- ✅ Fixed macOS tar metadata issues (COPYFILE_DISABLE, cleanup of ._* files)
- ✅ Exported clean seed: seed_20260103_130656.tar.gz (733KB)
- ✅ Verified clean install workflow: `make clean && make start` works end-to-end
- ✅ Committed to fixing-account-architecture, merged to staging

---

## 🚧 PHASE 2: DATABASE SCHEMA DESIGN - ETA: 2 hours

### ✅ 2.1 Design `funds` Collection Schema
**File:** `services/mongodb_schemas.md` (updated)

**Completed:**
- ✅ Documented full funds collection schema
- ✅ Documented all fields: fund_id, name, description, total_equity, currency, accounts[], status
- ✅ Defined validation rules (fund_id unique, total_equity >= 0)
- ✅ Created indexes: `{fund_id: 1}` unique, `{status: 1}`
- ✅ Added example document
- ✅ Documented cannot-delete-fund-with-active-allocations rule

### ✅ 2.2 Update `trading_accounts` Collection Schema
**File:** `services/mongodb_schemas.md` (updated)

**Completed:**
- ✅ Documented updated schema with new fields: fund_id, asset_classes{}
- ✅ Defined default asset_classes for each broker type:
  - IBKR: equity + futures + forex
  - Binance: crypto only
  - Alpaca: equity only
  - Mock_Paper: all asset classes
- ✅ Created indexes for fund_id, broker, open_positions
- ✅ Added full example document
- ✅ Documented validation rules for asset class matching

### ✅ 2.3 Update `portfolio_allocations` Collection Schema
**File:** `services/mongodb_schemas.md` (updated)

**Completed:**
- ✅ Documented updated schema with new fields: fund_id, allocation_name
- ✅ Defined validation: only ONE status=ACTIVE per fund_id
- ✅ Documented approval workflow (archive other allocations when approving)
- ✅ Added full example document
- ✅ Created validation rule: cannot approve if fund_id doesn't exist

### ✅ 2.4 Verify `strategies` Collection Schema
**File:** `services/mongodb_schemas.md` (updated)

**Completed:**
- ✅ Documented strategies schema with accounts[] field (added in Phase 1)
- ✅ Verified all strategies have `accounts` array after Phase 1 fix
- ✅ Verified all strategies have `asset_class` field
- ✅ Documented account-to-asset-class validation rules:
  - Equity strategies → accounts with equity support
  - Futures strategies → accounts with futures support
  - Crypto strategies → accounts with crypto support
  - Forex strategies → accounts with forex support
- ✅ Added example document

---

## ✅ PHASE 3: BACKEND API ENDPOINTS - COMPLETED

### ✅ 3.1 Fund Management Endpoints
**File:** `services/portfolio_builder/main.py`

**Completed:**
- ✅ POST /api/v1/funds - Create new fund (auto-generates fund_id from name)
- ✅ GET /api/v1/funds - List all funds (optional status filter)
- ✅ GET /api/v1/funds/{fund_id} - Get fund details (includes account_details)
- ✅ PUT /api/v1/funds/{fund_id} - Update fund (name, description, accounts, status)
- ✅ DELETE /api/v1/funds/{fund_id} - Delete fund (validates no ACTIVE allocations)
- ✅ Validation: Fund name unique, accounts can only belong to one fund, cascade deletion

### ✅ 3.2 Account Management Endpoints
**File:** `services/portfolio_builder/main.py`

**Completed:**
- ✅ POST /api/v1/accounts - Create new account with fund assignment
- ✅ GET /api/v1/accounts - List all accounts (optional fund_id filter)
- ✅ PUT /api/v1/accounts/{account_id} - Update account (fund_id, asset_classes)
- ✅ DELETE /api/v1/accounts/{account_id} - Delete account (validates no open positions)
- ✅ Auto-updates fund.accounts array on create/update/delete
- ✅ Validation: account_id unique, fund exists

### ✅ 3.3 Strategy-Account Mapping Endpoints
**File:** `services/portfolio_builder/main.py`

**Completed:**
- ✅ PUT /api/v1/strategies/{strategy_id}/accounts - Update allowed accounts
- ✅ GET /api/v1/strategies/{strategy_id}/accounts - Get account mapping
- ✅ Validation: All accounts exist and support strategy's asset_class
  - Equity strategies → accounts with equity support
  - Futures strategies → accounts with futures support
  - Crypto strategies → accounts with crypto support
  - Forex strategies → accounts with forex support
- ✅ Returns 400 error if asset class incompatible

### ✅ 3.4 Testing & Verification
**Completed:**
- ✅ Created test fund: "Mathematricks Dev Fund" (fund_id: mathematricks-dev-fund)
- ✅ Created test account: "Test_Account_1" with all asset classes
- ✅ Updated SPX_1-D_Opt strategy with Test_Account_1
- ✅ Verified asset class validation working correctly
- ✅ Verified fund.accounts array auto-updates
- ✅ All API endpoints tested and working

---

## ✅ PHASE 4: CEREBRO SERVICE REFACTOR (Multi-Fund Logic) - COMPLETED

### ✅ 4.1 Update Database Collections Reference
**File:** `services/cerebro_service/cerebro_main.py`

**Completed:**
- ✅ Added `funds_collection = db['funds']`
- ✅ Added `trading_accounts_collection = db['trading_accounts']`
- ✅ Imported all fund_allocation_logic functions

### ✅ 4.2 Create Helper Functions
**File:** `services/cerebro_service/fund_allocation_logic.py` (NEW)

**Functions to implement:**

#### ☐ 4.2.1 `get_active_allocations_for_strategy(strategy_id: str) -> List[Dict]`
```python
"""
Get all ACTIVE portfolio allocations that include this strategy.
Returns list of allocation documents with fund_id.
"""
```
**Logic:**
- Query `portfolio_allocations` where `status = "ACTIVE"` and `strategy_id in allocations.keys()`
- Return list of matching allocation documents

#### ✅ 4.2.2 `calculate_fund_equity(fund_id: str) -> float`
```python
"""
Calculate total equity across all accounts in a fund.
Updates fund.total_equity in MongoDB.
"""
```
**Logic:**
- Get all accounts for fund: `trading_accounts.find({fund_id: fund_id})`
- Sum account.equity for all accounts
- Update `funds.update_one({fund_id}, {$set: {total_equity: total}})`
- Return total

#### ✅ 4.2.3 `get_strategy_allocation_for_fund(fund_id: str, strategy_id: str) -> Dict`
```python
"""
Returns {
  allocated_capital: float,   # How much $ this strategy has from this fund
  used_capital: float,         # How much $ is currently deployed
  available_capital: float     # How much $ is available for new signals
}
"""
```
**Logic:**
- Get fund total_equity
- Get portfolio allocation percentage for this strategy
- `allocated_capital = fund_equity * (strategy_pct / 100)`
- Query `trading_orders` to calculate used_capital:
  - Sum `notional_value` where `fund_id=X, strategy_id=Y, status IN [FILLED, SUBMITTED]`
- `available_capital = allocated_capital - used_capital`

#### ✅ 4.2.4 `get_available_accounts_for_strategy(strategy_id: str, fund_id: str, asset_class: str) -> List[Dict]`
```python
"""
Returns accounts that:
1. Strategy is allowed to use (in strategy.accounts)
2. Belong to this fund (account.fund_id = fund_id)
3. Support the asset class (asset_class in account.asset_classes)

Returns: [{account_id, available_margin, equity}, ...]
"""
```
**Logic:**
- Get strategy.accounts array
- Filter to accounts where fund_id matches
- Filter to accounts where asset_class is supported
- Get current account state (margin, equity) from `trading_accounts`
- Return list sorted by available_margin (descending)

#### ✅ 4.2.5 `distribute_capital_across_accounts(target_capital: float, accounts: List[Dict]) -> List[Dict]`
```python
"""
Distribute target_capital across accounts proportionally by available margin.

Input: 
  target_capital = 15000
  accounts = [
    {account_id: "IBKR_Main", available_margin: 15000},
    {account_id: "IBKR_Futures", available_margin: 8000}
  ]

Output: [
  {account_id: "IBKR_Main", allocated_capital: 9782.61},  # 15000/23000 * 15000
  {account_id: "IBKR_Futures", allocated_capital: 5217.39}  # 8000/23000 * 15000
]
"""
```
**Logic:**
- Calculate total_margin = sum of all account.available_margin
- For each account: `allocated = (account.margin / total_margin) * target_capital`
- Cap each allocation at account.available_margin (handle edge case)
- Return list of {account_id, allocated_capital}

### ✅ 4.3 Refactor Signal Processing Logic
**File:** `services/cerebro_service/cerebro_main.py`

**Completed:** Entire signal processing flow refactored for multi-fund support

#### ✅ 4.3.1 Replace Single-Account Logic
**Current (lines ~1179-1200):**
```python
accounts = strategy_doc.get('accounts', [])
account_name = accounts[0]  # Only uses first account!
account_state = get_account_state(account_name)
```

**New:**
```python
# Get all active allocations that include this strategy
from fund_allocation_logic import get_active_allocations_for_strategy

active_allocations = get_active_allocations_for_strategy(strategy_id)

if not active_allocations:
    logger.error(f"Strategy {strategy_id} not in any ACTIVE allocations")
    # Reject signal
    return

# Process signal for EACH fund
all_orders = []
for allocation in active_allocations:
    fund_id = allocation['fund_id']
    strategy_pct = allocation['allocations'][strategy_id]
    
    logger.info(f"Processing signal for fund {fund_id}, strategy allocation: {strategy_pct}%")
    
    # Calculate fund-level capital allocation
    fund_allocation = get_strategy_allocation_for_fund(fund_id, strategy_id)
    
    # ... (continue below)
```

#### ✅ 4.3.2 Add Capital Availability Check
```python
    # Check if strategy has available capital
    if fund_allocation['available_capital'] <= 0:
        logger.warning(f"Strategy {strategy_id} has no available capital in fund {fund_id}")
        continue
    
    # Calculate signal size (this is where portfolio_constructor comes in)
    # Use existing logic but now scoped to this fund's allocation
    signal_obj = convert_signal_dict_to_object(signal)
    
    # Build context with fund-specific allocation
    context = build_portfolio_context_for_fund(fund_id, strategy_id, fund_allocation)
    
    constructor = initialize_portfolio_constructor()
    decision_obj = constructor.evaluate_signal(signal_obj, context)
    
    if decision_obj.decision == "REJECTED":
        logger.info(f"Signal rejected by portfolio constructor for fund {fund_id}")
        continue
    
    # Get target capital from decision
    target_capital = decision_obj.final_quantity * signal.get('price', 0)  # Simplified
```

#### ✅ 4.3.3 Add Multi-Account Distribution
```python
    # Get available accounts for this strategy in this fund
    asset_class = strategy_doc.get('asset_class', 'equity')
    available_accounts = get_available_accounts_for_strategy(
        strategy_id, fund_id, asset_class
    )
    
    if not available_accounts:
        logger.error(f"No available accounts for {strategy_id} in fund {fund_id}")
        continue
    
    # Distribute capital across accounts
    account_allocations = distribute_capital_across_accounts(
        target_capital, available_accounts
    )
    
    logger.info(f"Distributing ${target_capital} across {len(account_allocations)} accounts:")
    for alloc in account_allocations:
        logger.info(f"  • {alloc['account_id']}: ${alloc['allocated_capital']:.2f}")
```

#### ✅ 4.3.4 Create Multiple Orders
```python
    # Create one order per account
    for account_alloc in account_allocations:
        account_id = account_alloc['account_id']
        allocated_capital = account_alloc['allocated_capital']
        
        # Calculate quantity for this account
        price = signal.get('price') or decision_obj.entry_price
        quantity = allocated_capital / price
        
        # Create trading order
        order = {
            "order_id": generate_order_id(),
            "signal_id": signal.get('signal_id'),
            "strategy_id": strategy_id,
            "fund_id": fund_id,                    # NEW
            "account_id": account_id,              # Now per-account
            "instrument": signal.get('instrument'),
            "direction": signal.get('direction'),
            "action": signal.get('action'),
            "quantity": quantity,
            "price": price,
            "notional_value": allocated_capital,
            "status": "PENDING",
            "created_at": datetime.utcnow()
        }
        
        # Insert to trading_orders collection
        trading_orders_collection.insert_one(order)
        
        # Publish to execution service
        publish_order_to_execution_service(order)
        
        all_orders.append(order)
    
# End of allocation loop

logger.info(f"Created {len(all_orders)} orders across {len(active_allocations)} funds")
```

### ✅ 4.4 Update Portfolio Context Builder
**File:** `services/cerebro_service/cerebro_main.py`

**Completed:**
- ✅ Portfolio context built per fund iteration
- ✅ Uses primary account for signal evaluation
- ✅ Fund-specific capital allocation integrated

### ☐ 4.5 Testing
**Tasks:**
- ☐ Create test signal for multi-fund scenario
- ☐ Setup: Create 2 funds with different allocations for same strategy
- ☐ Send signal
- ☐ Verify 2 sets of orders created (one per fund)
- ☐ Verify capital distributed correctly across accounts
- ☐ Check logs for multi-account distribution

---

## ✅ PHASE 5: FRONTEND - FUND SETUP WIZARD - COMPLETED (2026-01-03)

**Refinements Applied (2026-01-03):**
- ✅ Fixed Mock_Paper broker error: Removed Mock_Paper from broker type list, use "Mock" instead
- ✅ Changed from modal-first wizard to list-first view: Funds displayed as expandable rows by default
- ✅ Made wizard available for add/edit only: Click fund name to expand details, Edit button opens wizard
- ✅ Added success toast to Strategies page: Green toast notification for 1 second after update
- ✅ Dynamic accounts dropdown in strategies: Fetches from database using useQuery, multi-select checkboxes
- ✅ Fixed sidebar to viewport height: Header and sidebar constrained to screen height, scroll internally
- ✅ Added timezone display: Top right of header shows browser local timezone (e.g., "America/New_York")
- ✅ Fixed signal timestamp issue: Changed from non-existent received_at to created_at field in API (fixes 1969 display bug)
- ✅ Modified Part 2 UI to 4-column layout: Added "Assign to Fund" dropdown selector

### ✅ All Components Working
- ✅ Hedged Funds page with expandable rows
- ✅ Fund wizard (3 steps: Details, Accounts, Review)
- ✅ Navigation integration
- ✅ Strategies page with success toast + dynamic accounts
- ✅ Sidebar viewport-height fix
- ✅ Timezone display in header

### ✅ 5.1 Create Wizard Component Structure
**File:** `frontend-admin/src/pages/FundSetup.tsx`

**Components to create:**
- ✅ `FundSetupWizard` - Main wizard container with stepper
- ✅ `Step1_CreateFunds` - Fund creation form
- ✅ `Step2_ConfigureAccounts` - Account configuration
- ✅ `Step3_MapStrategies` - Strategy-to-account mapping
- ✅ `Step4_ReviewExport` - Review and export

**State management:**
```typescript
interface WizardState {
  currentStep: number;
  funds: Fund[];
  accounts: Account[];
  strategyMappings: Map<string, string[]>;  // strategy_id -> account_ids[]
}
```

### ✅ 5.2 Step 1: Create Funds
**Component:** `Step1_CreateFunds.tsx`

**UI Elements:**
- ✅ Table showing existing funds
- ✅ "Add Fund" button
- ✅ Modal form with fields:
  - Fund Name (text input)
  - Description (textarea)
  - Currency (dropdown: USD, EUR, GBP)
  - Status (dropdown: ACTIVE, PAUSED)
- ✅ Validation: name required, name unique
- ✅ Actions: Save → calls `POST /api/v1/funds`

**Display:**
- ✅ Show created funds in table with: name, total_equity (0 initially), accounts count, status
- ✅ Edit button for each fund
- ✅ Delete button (with confirmation)

### ✅ 5.3 Step 2: Configure Accounts
**Component:** `Step2_ConfigureAccounts.tsx`

**UI Elements:**
- ✅ Fund selector dropdown (from Step 1 funds)
- ✅ Table showing accounts for selected fund
- ✅ Two buttons:
  - **"Add Account"** - Create from scratch
  - **"Duplicate Account"** - Copy existing account (disabled if no accounts exist)
  
**When clicking "Add Account":**
- ✅ Modal form with fields:
  - Account ID (text input, e.g., "IBKR_Main")
  - Broker Type (dropdown: IBKR, Binance, Alpaca, Mock_Paper)
  - Fund Assignment (dropdown from created funds)
  - Asset Classes (multi-checkbox with sub-options):
    - **Equity:** 
      - ✅ All 
      - Or specify symbols (comma-separated): _________
    - **Futures:** 
      - ☐ All 
      - Or specify symbols: _________
    - **Crypto:** 
      - ☐ All 
      - Or specify symbols (e.g., BTC, ETH, USDT): _________
    - **Forex:** 
      - ☐ All 
      - Or specify pairs (e.g., EUR/USD, GBP/USD): _________
  - All fields empty by default (no smart defaults)
  
**When clicking "Duplicate Account":**
- ✅ Shows dropdown: "Select account to duplicate"
- ✅ Lists all existing accounts across all funds
- ✅ After selection, opens same modal but pre-filled with:
  - Account ID: "[original]_copy" (user must change to be unique)
  - Broker Type: [same as original]
  - Fund Assignment: [current selected fund, not original fund]
  - Asset Classes: [exact copy of original]
- ✅ User edits as needed (e.g., change account ID, tweak asset classes)
- ✅ Save creates new account

**Validation rules:**
- ✅ Account ID must be unique across all accounts
- ✅ At least one asset class must be selected
- ✅ If "All" is checked, cannot specify individual symbols (validation)

**Actions:** 
- ✅ Save → calls `POST /api/v1/accounts`

**Display:**
- ✅ Group accounts by fund
- ✅ Show: account_id, broker, asset_classes (badges), status
- ✅ Action buttons per row:
  - Edit (opens form pre-filled)
  - Duplicate (opens form pre-filled, changes account_id to "[id]_copy")
  - Delete (with confirmation if no positions)

### ✅ 5.4 Step 3: Map Strategies to Accounts
**Component:** `Step3_MapStrategies.tsx`

**UI Elements:**
- ✅ Table of all strategies (from `GET /api/v1/strategies`)
- ✅ For each strategy row:
  - Strategy ID (display)
  - Asset Class (badge: equity/futures/crypto/forex)
  - Allowed Accounts (multi-select dropdown)
- ✅ Account dropdown filtered by asset class:
  - If strategy.asset_class = "equity" → only show accounts with equity enabled
  - If strategy.asset_class = "futures" → only show futures-enabled accounts
  - Validation warning if mismatch
- ✅ Actions: Save → calls `PUT /api/v1/strategies/{id}/accounts`

**Display:**
- ✅ Color coding: Green = mapped, Red = no accounts assigned
- ✅ Validation warnings for mismatched asset classes
- ✅ "Save All" button at bottom

### ✅ 5.5 Step 4: Review and Export
**Component:** `Step4_ReviewExport.tsx`

**UI Elements:**
- ✅ Summary cards:
  - Total Funds: X
  - Total Accounts: Y
  - Strategies Mapped: Z / Total
- ✅ Expandable sections:
  - **Funds:** List with accounts nested
  - **Accounts:** List with broker, fund, asset_classes
  - **Strategy Mappings:** List with strategy → accounts
- ✅ Validation checks:
  - ✅ All strategies have at least one account
  - ✅ All accounts belong to a fund
  - ⚠️ Warnings for unmapped strategies
- ✅ "Export as Seed Data" button (placeholder)
  - Calls `POST /api/v1/setup/export`
  - Shows progress spinner
  - Downloads backup or shows success message
- ✅ "Reset to Seed Data" button (dangerous, with confirmation)

### ✅ 5.6 Add Wizard to App Navigation
**Files to update:**

**`frontend-admin/src/App.tsx`:**
- ✅ Import FundSetup component
- ✅ Add route: `<Route path="fund-setup" element={<FundSetup />} />`

**`frontend-admin/src/components/Layout.tsx`:**
- ✅ Add navigation item: "Fund Setup" with route to `/fund-setup`
- ✅ Add icon (Wrench icon from lucide-react)

### ✅ 5.7 Create API Service Methods
**File:** `frontend-admin/src/services/api.ts`

**Completed Methods:**
```typescript
// Funds
createFund(data: CreateFundRequest): Promise<Fund>
getFunds(): Promise<Fund[]>
getFund(fundId: string): Promise<Fund>
updateFund(fundId: string, data: UpdateFundRequest): Promise<Fund>
deleteFund(fundId: string): Promise<void>

// Accounts
createAccount(data: CreateAccountRequest): Promise<Account>
getAccounts(fundId?: string): Promise<Account[]>
updateAccount(accountId: string, data: UpdateAccountRequest): Promise<Account>
deleteAccount(accountId: string): Promise<void>

// Strategy Mappings
updateStrategyAccounts(strategyId: string, accounts: string[]): Promise<Strategy>
getStrategyAccounts(strategyId: string): Promise<{accounts: string[]}>

// Export
exportSeedData(): Promise<{backup_path: string, timestamp: string}>
```

### ☐ 5.8 Optimize Real-Time Updates (Replace Polling with WebSocket/SSE)
**Current Issue:** Activity page polls 3 endpoints every 5 seconds causing perpetual API requests

**Solution:** Implement Server-Sent Events (SSE) for real-time updates

**Backend (Portfolio Builder):**
**File:** `services/portfolio_builder/portfolio_builder_main.py`
```python
@app.get("/api/v1/activity/stream")
async def activity_stream(environment: str = "staging"):
    """SSE endpoint for real-time activity updates"""
    async def event_generator():
        # Watch MongoDB change streams for signals, orders, decisions
        # Yield SSE events when data changes
        while True:
            # Check for new signals/orders/decisions
            yield {
                "event": "signals",
                "data": json.dumps(new_signals)
            }
            await asyncio.sleep(1)
    
    return EventSourceResponse(event_generator())
```

**Frontend:**
**File:** `frontend-admin/src/pages/Activity.tsx`
```typescript
// Replace useQuery with EventSource
useEffect(() => {
  const eventSource = new EventSource(
    `/api/v1/activity/stream?environment=${environment}`
  );
  
  eventSource.addEventListener('signals', (e) => {
    setSignals(JSON.parse(e.data));
  });
  
  return () => eventSource.close();
}, [environment]);
```

**Benefits:**
- ✅ Eliminates unnecessary polling
- ✅ Real-time updates (< 1s latency)
- ✅ Reduces server load by 95%
- ✅ Better user experience

### ✅ 5.9 Create TypeScript Types
**File:** `frontend-admin/src/types/index.ts`

**Completed Types:**
```typescript
interface Fund {
  fund_id: string;
  name: string;
  description?: string;
  total_equity: number;
  currency: string;
  accounts: string[];
  status: 'ACTIVE' | 'PAUSED' | 'CLOSED';
  created_at: string;
  updated_at: string;
}

interface Account {
  account_id: string;
  broker: 'IBKR' | 'Binance' | 'Alpaca' | 'Mock_Paper';
  fund_id: string;
  asset_classes: {
    equity: string[];
    futures: string[];
    crypto: string[];
    forex: string[];
  };
  equity: number;
  available_margin: number;
  status: 'ACTIVE' | 'INACTIVE';
}

interface CreateFundRequest {
  name: string;
  description?: string;
  currency: string;
  accounts?: string[];
}

interface CreateAccountRequest {
  account_id: string;
  broker: string;
  fund_id: string;
  asset_classes: AssetClasses;
}
```

---

## 🚧 PHASE 6: FRONTEND - ALLOCATIONS PAGE UPDATES - IN PROGRESS

### ✅ 6.1 Fund Assignment in Approval Flow - COMPLETED
**File:** `frontend-admin/src/pages/Allocations.tsx`

**Part 2 Updates (Approve Allocation) - COMPLETED:**
- ✅ Added `selectedFundId` state to track selected fund
- ✅ Added funds query: Fetches available funds from `GET /api/v1/funds`
- ✅ Added fund selector dropdown in Part 2 UI (4th column in grid)
  - Dropdown shows "Select Fund" placeholder + list of funds
  - Styling: gray bg-gray-700 border border-gray-600, text-sm
  - Required field validation before approval
- ✅ Updated `handleApprove()` to validate fund selection
  - Shows alert if no fund selected
  - Prevents approval without fund assignment
- ✅ Updated `handleEditCurrent()` to restore fund_id from current allocation
  - When editing Part 1, pre-fills selectedFundId if allocation has fund_id
- ✅ Updated `handleSaveEdit()` for Part 1 edit mode
  - Also validates fund selection before saving
- ✅ Updated `approveMutation` to accept fund_id parameter
  - Changed signature from `(allocations)` to `({ allocations, fund_id })`
  - Clears `selectedFundId` on success
- ✅ Updated `apiClient.approveAllocation()` to accept fund_id
  - Now passes fund_id in POST body: `{ allocations, fund_id }`

**Display Updates - FUTURE:**
- ☐ Show fund name in Part 1 (current allocation)
- ☐ Filter allocations by fund in history view

### ✅ 6.2 Update API Methods - COMPLETED
**File:** `frontend-admin/src/services/api.ts`

**Methods Updated:**
- ✅ `approveAllocation(allocations: Record<string, number>, fund_id: string)` - now accepts fund_id parameter

---

## ☐ PHASE 6: FRONTEND - ALLOCATIONS PAGE UPDATES (REMAINING ENHANCEMENTS)

---

## ☐ PHASE 7: ACCOUNT DATA SERVICE UPDATES - ETA: 2 hours

### ☐ 7.1 Update Account Polling Logic
**File:** `services/account_data_service/account_data_main.py`

**Tasks:**
- ☐ When polling accounts, include fund_id in updates
- ☐ After updating all accounts, recalculate fund.total_equity
- ☐ Call `calculate_fund_equity(fund_id)` for each fund
- ☐ Log fund-level summary:
  ```
  Fund: mathematricks-1
    Total Equity: $750,234.56
    Accounts: 3
      • IBKR_Main: $500,123.45
      • IBKR_Futures: $200,456.78
      • Binance_Main: $49,654.33
  ```

### ☐ 7.2 Add Fund-Level Metrics
**File:** `services/account_data_service/account_data_main.py`

**New function:**
```python
def calculate_fund_metrics(fund_id: str) -> Dict:
    """
    Calculate aggregate metrics for a fund.
    Returns: {
        total_equity: float,
        total_margin_used: float,
        total_unrealized_pnl: float,
        num_accounts: int,
        num_open_positions: int
    }
    """
```

**Tasks:**
- ☐ Implement aggregation across fund accounts
- ☐ Store in `funds` collection: `{fund_id, metrics, updated_at}`
- ☐ Update on each polling cycle

---

## ☐ PHASE 8: MIGRATION & CLEANUP - ETA: 3 hours

### ☐ 8.1 Create Migration Script for Existing Data
**File:** `scripts/migrate_to_fund_architecture.py`

**Tasks:**
- ☐ Create default fund: "default-fund"
- ☐ Migrate existing trading_accounts:
  - Add `fund_id: "default-fund"`
  - Add default asset_classes based on broker
- ☐ Migrate existing portfolio_allocations:
  - Add `fund_id: "default-fund"`
  - Add `allocation_name: "Legacy Allocation"`
- ☐ Verify all strategies have accounts field (from Phase 1)
- ☐ Update fund.accounts array with migrated accounts
- ☐ Log migration summary

**Validation:**
```bash
python scripts/migrate_to_fund_architecture.py
# Expected output:
# ✅ Created default fund
# ✅ Migrated 5 accounts
# ✅ Migrated 3 allocations
# ✅ Updated fund.accounts array
```

### ☐ 8.2 Remove Dead Collections
**File:** `scripts/cleanup_dead_collections.py`

**Tasks:**
- ☐ Backup database first: `mongodump --out=backup_pre_cleanup_$(date)`
- ☐ Drop collections:
  - `account_hierarchy` (never used)
  - `current_allocation` (duplicate of portfolio_allocations)
  - `account_state` (replaced by trading_accounts)
  - `portfolio_tests` (research only)
- ☐ Log collections dropped

**Validation:**
```bash
python scripts/cleanup_dead_collections.py
# Prompts: "Backup created at backup_pre_cleanup_20260102. Proceed? [y/n]"
# Expected output:
# ✅ Dropped account_hierarchy
# ✅ Dropped current_allocation
# ✅ Dropped account_state
# ✅ Dropped portfolio_tests
```

### ☐ 8.3 Update Seed Data
**Tasks:**
- ☐ Run Fund Setup Wizard to create production seed config
- ☐ Create funds: Mathematricks-1, Mathematricks-Dev
- ☐ Create accounts:
  - IBKR_Main (mathematricks-1, equity+futures+forex)
  - IBKR_Futures (mathematricks-1, futures only)
  - Binance_Main (mathematricks-1, crypto only)
  - Mock_Paper (mathematricks-dev, all asset classes)
- ☐ Map strategies to accounts:
  - SPX_1-D_Opt → IBKR_Main
  - Com1-Met, Com2-Ag, Com3-Mkt → IBKR_Futures
  - FloridaForex → IBKR_Main, IBKR_Futures
- ☐ Export seed data: Click "Export as Seed Data" in wizard
- ☐ Verify seed data in `seed_data/backups/seed_backup_YYYYMMDD_HHMMSS/`
- ☐ Update symlink: `seed_data/mongodb_dump` → latest backup

---

## ☐ PHASE 9: DOCUMENTATION UPDATES - ETA: 2 hours

### ☐ 9.1 Update MongoDB Schema Documentation
**File:** `services/mongodb_schemas.md`

**Tasks:**
- ☐ Remove deprecated collections section:
  - strategy_configurations (never existed)
  - account_hierarchy (deleted)
  - fund_state (never implemented)
  - current_allocation (deleted)
  - account_state (deleted)
- ☐ Add new `funds` collection schema
- ☐ Update `trading_accounts` schema with fund_id and asset_classes
- ☐ Update `portfolio_allocations` schema with fund_id
- ☐ Add data flow diagram: Signal → Strategy → Fund → Accounts → Orders

### ☐ 9.2 Update Setup Documentation
**File:** `SETUP.md`

**Tasks:**
- ☐ Add section: "Fund and Account Architecture"
- ☐ Explain fund hierarchy: Funds → Accounts → Strategies
- ☐ Document seed data structure
- ☐ Add instructions for Fund Setup Wizard
- ☐ Update screenshots if needed

### ☐ 9.3 Update API Documentation
**File:** `documentation/portfolio_builder.md` (or create if missing)

**Tasks:**
- ☐ Document all new endpoints:
  - Fund management endpoints
  - Account management endpoints
  - Strategy mapping endpoints
  - Export endpoint
- ☐ Include request/response examples
- ☐ Add authentication requirements

### ☐ 9.4 Create Fund Architecture Diagram
**File:** `documentation/fund_architecture_diagram.md`

**Content:**
```
Fund Architecture (v5)
====================

┌─────────────────────────────────────────────────┐
│ Funds                                           │
│ ┌─────────────────┐  ┌─────────────────┐       │
│ │ Mathematricks-1 │  │ Mathematricks-   │       │
│ │ $750k           │  │ Dev             │       │
│ └────────┬────────┘  └────────┬────────┘       │
└──────────┼──────────────────────┼────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────────────────────────────────────┐
│ Accounts                                         │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐│
│ │IBKR_Main │ │IBKR_Fut  │ │Binance_M │ │Mock_P││
│ │$500k     │ │$200k     │ │$50k      │ │$100k ││
│ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬───┘│
└──────┼────────────┼────────────┼───────────┼────┘
       │            │            │           │
       ▼            ▼            ▼           ▼
┌──────────────────────────────────────────────────┐
│ Strategies                                       │
│ ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│ │SPX_1-D  │ │Com1-Met│ │Florida │ │All in  │   │
│ │Opt      │ │        │ │Forex   │ │Mock_P  │   │
│ │         │ │        │ │        │ │        │   │
│ │IBKR_Main│ │IBKR_Fut│ │IBKR_*  │ │Mock_P  │   │
│ └─────────┘ └────────┘ └────────┘ └────────┘   │
└──────────────────────────────────────────────────┘

Signal Flow:
1. Signal arrives for SPX_1-D_Opt
2. Cerebro finds ACTIVE allocations containing SPX_1-D_Opt
3. For each fund (e.g., Mathematricks-1):
   - Calculate allocated capital (15% of $750k = $112.5k)
   - Check available capital ($112.5k - $25k used = $87.5k)
   - Calculate signal size (20% of allocation = $22.5k)
   - Validate: $22.5k < $87.5k ✅
   - Get allowed accounts: [IBKR_Main]
   - Check margin: IBKR_Main has $15k available
   - Create order: IBKR_Main, $22.5k
4. Send order to Execution Service
```

---

## ☐ PHASE 10: TESTING & VALIDATION - ETA: 4 hours

### ☐ 10.1 Unit Tests
**Files to create:**
- ☐ `tests/test_fund_allocation_logic.py`
  - Test get_active_allocations_for_strategy()
  - Test calculate_fund_equity()
  - Test get_strategy_allocation_for_fund()
  - Test distribute_capital_across_accounts()
  
- ☐ `tests/test_fund_api_endpoints.py`
  - Test POST /api/v1/funds
  - Test GET /api/v1/funds
  - Test PUT /api/v1/funds/{id}
  - Test DELETE validation

### ☐ 10.2 Integration Tests
**Scenarios:**

#### ☐ 10.2.1 Single Fund, Single Account
- Setup: 1 fund, 1 account, 1 strategy with 100% allocation
- Send signal
- Verify: 1 order created for full capital

#### ☐ 10.2.2 Single Fund, Multiple Accounts
- Setup: 1 fund, 2 accounts (IBKR_Main $15k margin, IBKR_Futures $8k margin)
- Strategy allocated 10% of $100k fund = $10k
- Send signal requesting 50% of allocation = $5k
- Verify: 2 orders created
  - IBKR_Main: $3,260.87 (15k/23k * 5k)
  - IBKR_Futures: $1,739.13 (8k/23k * 5k)

#### ☐ 10.2.3 Multiple Funds, Same Strategy
- Setup: 2 funds, each with different allocation for SPX_1-D_Opt
  - Fund A: 15% allocation
  - Fund B: 5% allocation
- Send 1 signal
- Verify: 2 sets of orders created (one per fund)
- Verify: Different capital amounts per fund

#### ☐ 10.2.4 Asset Class Validation
- Setup: Equity strategy mapped to Binance (crypto-only account)
- Send signal
- Verify: Signal rejected with "INCOMPATIBLE_ASSET_CLASS" error

#### ☐ 10.2.5 Capital Limit Check
- Setup: Strategy allocated $10k, already using $9k
- Send signal requesting $5k
- Verify: Signal rejected with "INSUFFICIENT_CAPITAL" error

### ☐ 10.3 End-to-End Test
**Full workflow:**
- ☐ Use Fund Setup Wizard to create 2 funds
- ☐ Create 4 accounts across 2 funds
- ☐ Map 3 strategies to different accounts
- ☐ Create allocation for Fund A with 3 strategies
- ☐ Approve allocation
- ☐ Send test signals for all 3 strategies
- ☐ Verify orders created and distributed correctly
- ☐ Check Account Data Service updates fund equity
- ☐ Export seed data
- ☐ Drop database
- ☐ Restore from exported seed data
- ☐ Verify all funds/accounts/strategies restored correctly

### ☐ 10.4 Performance Testing
**Tasks:**
- ☐ Test with 10 funds, 50 accounts, 100 strategies
- ☐ Send 1000 signals concurrently
- ☐ Measure signal processing time per fund
- ☐ Verify no database deadlocks
- ☐ Check memory usage of Cerebro service

---

## ☐ PHASE 11: DEPLOYMENT & ROLLOUT - ETA: 2 hours

### ☐ 11.1 Pre-Deployment Checklist
- ☐ Run all tests: `pytest tests/`
- ☐ Run migration script on staging DB
- ☐ Verify seed data exports correctly
- ☐ Review all code changes
- ☐ Update version number in package files

### ☐ 11.2 Deployment Steps
1. ☐ Backup production database
   ```bash
   mongodump --uri="$PROD_MONGODB_URI" --out=backup_pre_v5_$(date +%Y%m%d)
   ```

2. ☐ Stop services
   ```bash
   make stop
   ```

3. ☐ Pull latest code
   ```bash
   git checkout fixing-account-architecture
   git pull origin fixing-account-architecture
   ```

4. ☐ Run migration script
   ```bash
   python scripts/migrate_to_fund_architecture.py
   ```

5. ☐ Run cleanup script
   ```bash
   python scripts/cleanup_dead_collections.py
   ```

6. ☐ Rebuild containers
   ```bash
   make rebuild
   ```

7. ☐ Start services
   ```bash
   make start
   ```

8. ☐ Verify services healthy
   ```bash
   make status
   docker ps  # All services running
   ```

9. ☐ Check logs
   ```bash
   make logs-cerebro
   # Verify fund allocation logic loading
   ```

10. ☐ Send test signal
    ```bash
    python tests/signals_testing/send_test_signal.py --file tests/signals_testing/sample_signals/spx_signal.json
    ```

11. ☐ Verify order created and distributed correctly

### ☐ 11.3 Post-Deployment Validation
- ☐ Check frontend Fund Setup page loads
- ☐ Create test fund via UI
- ☐ Create test account via UI
- ☐ Map strategy to account via UI
- ☐ Approve allocation for test fund
- ☐ Send signal, verify multi-account distribution
- ☐ Monitor logs for errors (24 hours)

---

## ☐ PHASE 12: FUTURE ENHANCEMENTS (Post-v5)

### Ideas for v6:
- ☐ Fund performance dashboard (per-fund P&L, Sharpe ratio)
- ☐ Account rebalancing (auto-distribute capital when one account is full)
- ☐ Multi-currency support (FX conversion between accounts)
- ☐ Fund-level risk limits (max drawdown, max leverage)
- ☐ Strategy groups (instead of individual strategies, use groups)
- ☐ Partial fills handling across accounts
- ☐ Account failover (if IBKR_Main is down, route to IBKR_Backup)

---

# PROGRESS TRACKING

**Started:** 2026-01-03
**Target Completion:** 2026-01-10
**Status:** 🚧 In Progress

**Current Phase:** Phase 6 - Frontend Allocations Page Updates (In Progress)

**Remaining Phases:**
- Phase 6: Frontend - Allocations Page Updates (1 hour remaining)
  - ✅ Fund selector dropdown for approval
  - ✅ Validation of fund selection
  - ☐ Display fund name in Part 1 current allocation
  - ☐ Filter allocations by fund in history
- Phase 7: Account Data Service Updates (2 hours)
- Phase 8: Migration & Cleanup (3 hours)
- Phase 9: Documentation Updates (2 hours)
- Phase 10: Testing & Validation (4 hours)
- Phase 11: Deployment & Rollout (2 hours)

**Completed Phases:** 
- ✅ Phase 1 - Immediate Fix (2026-01-03)
- ✅ Phase 2 - Database Schema Design (2026-01-03)
- ✅ Phase 3 - Backend API Endpoints (2026-01-03)
- ✅ Phase 4 - Cerebro Service Refactor (2026-01-03)
- ✅ Phase 5 - Frontend Fund Setup Wizard (2026-01-03, with refinements)
- 🚧 Phase 6 - Frontend Allocations Page Updates (2026-01-03, partial)

**Blockers:** None

**Last Updated:** 2026-01-03 20:30 UTC

---

# NOTES & DECISIONS

## Design Decisions:
1. **Multi-account distribution:** Using proportional allocation by available margin (vs equal split)
2. **Fund total_equity:** Auto-calculated from sum of account equities (vs manual input)
3. **Asset class validation:** Enforced in backend + frontend (strict validation)
4. **Seed data export:** Timestamped backups with symlink to latest (vs overwrite)

## Open Questions:
1. Should we support account sharing across funds? (Current: No, 1 account = 1 fund)
2. How to handle partial fills across multiple accounts? (Future enhancement)
3. Should fund.total_equity be editable or always calculated? (Current: Always calculated)

---

# APPENDIX: File Inventory

## New Files Created:
- `scripts/fix_strategy_accounts.py`
- `scripts/migrate_to_fund_architecture.py`
- `scripts/cleanup_dead_collections.py`
- `services/cerebro_service/fund_allocation_logic.py`
- `frontend-admin/src/pages/FundSetup.tsx`
- `frontend-admin/src/pages/FundSetup/Step1_CreateFunds.tsx`
- `frontend-admin/src/pages/FundSetup/Step2_ConfigureAccounts.tsx`
- `frontend-admin/src/pages/FundSetup/Step3_MapStrategies.tsx`
- `frontend-admin/src/pages/FundSetup/Step4_ReviewExport.tsx`
- `tests/test_fund_allocation_logic.py`
- `tests/test_fund_api_endpoints.py`
- `documentation/fund_architecture_diagram.md`

## Modified Files:
- `services/cerebro_service/cerebro_main.py` (multi-fund signal processing)
- `services/account_data_service/account_data_main.py` (fund-level metrics)
- `services/portfolio_builder/portfolio_builder_main.py` (fund/account APIs)
- `frontend-admin/src/pages/Allocations.tsx` (fund selector)
- `frontend-admin/src/App.tsx` (add fund-setup route)
- `frontend-admin/src/components/Layout.tsx` (add Setup nav item)
- `frontend-admin/src/services/api.ts` (fund/account API methods)
- `frontend-admin/src/types/index.ts` (Fund, Account types)
- `services/mongodb_schemas.md` (add funds, update schemas)
- `SETUP.md` (fund architecture explanation)

## Deleted Files:
- None (collections dropped, but no files deleted)

---

**END OF IMPLEMENTATION PLAN**
