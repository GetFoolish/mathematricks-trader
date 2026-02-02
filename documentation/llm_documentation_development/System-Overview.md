# Mathematricks Trading System - Comprehensive System Overview

**Last Updated:** 2026-01-30  
**Purpose:** Complete architectural documentation for understanding the full trading system lifecycle  
**Audience:** AI agents, developers, system architects

---

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [The 4-Mode Trading System](#the-4-mode-trading-system)
3. [Broker Pool Management](#broker-pool-management)
4. [Service Interactions & Flow](#service-interactions--flow)
5. [Balance Update Mechanisms](#balance-update-mechanisms)
6. [Position Tracking Architecture](#position-tracking-architecture)
7. [Mode Validation & Routing](#mode-validation--routing)
8. [Data Flow: Signal → Execution → Reconciliation](#data-flow-signal--execution--reconciliation)
9. [Common Pitfalls & Edge Cases](#common-pitfalls--edge-cases)

---

## System Architecture Overview

### Core Services
The trading system consists of 4 primary microservices running in Docker containers:

| Service | Port | Responsibility | Key Collections |
|---------|------|----------------|-----------------|
| **Signal Ingestion Service** | N/A | Watches MongoDB for raw signals, standardizes them, writes to signal_store | `trading_signals_raw`, `signal_store` |
| **Cerebro Service** | 8081 | Processes signals, creates orders with position sizing & risk management | `signal_store`, `trading_accounts`, `strategies`, `funds` |
| **Execution Service** | 8083 | Manages broker pool, executes orders, updates positions | `signal_store`, `trading_accounts`, `trading_orders` |
| **Account Data Service** | 8082 | Polls broker accounts for balances & positions (background) | `trading_accounts` |

### Database Architecture
- **MongoDB** (port 27018): Single source of truth for all data
- **Collections:**
  - `trading_signals_raw`: Incoming signals from external sources
  - `signal_store`: Processed signals with execution history (replaces execution_confirmations)
  - `trading_accounts`: Account configs, balances, positions, authentication
  - `trading_orders`: Individual order records (legacy, being phased out)
  - `strategies`: Strategy configurations & account allowlists
  - `funds`: Fund allocations to strategies

### Communication Patterns
- **MongoDB Change Streams**: Event-driven updates (no pub/sub)
- **REST APIs**: Synchronous service-to-service calls
- **Polling + Events**: Hybrid approach for position tracking

---

## The 4-Mode Trading System

### Mode Composition
Every trading mode is computed from two dimensions:

```
Mode = {account_type}_{data_source}

Where:
  account_type ∈ {mock, paper, live}  ← WHERE ORDERS EXECUTE
  data_source  ∈ {mock, live}         ← WHERE MARKET DATA COMES FROM
```

### The 4 Modes

#### 1. **mock_mock** (Pure Simulation)
- **Account Type:** Mock
- **Data Source:** Mock
- **Broker Setup:** Mock broker only
- **Use Case:** Fast testing without market data
- **Characteristics:**
  - Instant execution simulation
  - No IBKR Gateway needed
  - No real market data
  - Perfect for unit tests

#### 2. **mock_live** (Hybrid Testing)
- **Account Type:** Mock
- **Data Source:** Live (IBKR)
- **Broker Setup:** `BrokerModeAdapter(real_broker=IBKR, mock_broker=Mock)`
- **Use Case:** Strategy testing with real market conditions
- **Characteristics:**
  - Real-time market data from IBKR
  - Simulated order execution (Mock broker)
  - Requires IB Gateway (for data)
  - Best for strategy validation

**Critical Implementation Detail:**
```python
# mock_live uses BrokerModeAdapter to route calls:
- get_current_price() → IBKR (real data)
- get_account_balance() → IBKR (for realistic margin)
- place_order() → Mock broker (simulated fill)
- get_positions() → Mock broker (from MongoDB)
```

#### 3. **paper_live** (IBKR Paper Account)
- **Account Type:** Paper
- **Data Source:** Live
- **Broker Setup:** IBKR broker (port 4004 - paper trading)
- **Use Case:** IBKR paper trading (true brokerage simulation)
- **Characteristics:**
  - Real IBKR paper account
  - Real order routing through IBKR TWS
  - Real market data
  - Requires IB Gateway on port 4004

#### 4. **live_live** (Production Trading)
- **Account Type:** Live
- **Data Source:** Live
- **Broker Setup:** IBKR broker (port 4001 - production)
- **Use Case:** Real money trading
- **Characteristics:**
  - Production trading with real capital
  - Real order execution
  - Real market data
  - **⚠️ CRITICAL LOGS:** All live_live operations logged with warnings
  - Requires IB Gateway on port 4001

### Mode Field in MongoDB

**Trading Accounts Collection:**
```json
{
  "account_id": "IBKR-MOCK",
  "broker": "IBKR",
  "account_type": "mock",           // ← WHERE ORDERS EXECUTE
  "mode": ["mock_mock", "mock_live"], // ← SUPPORTED MODES (can be array or string)
  "authentication_details": {
    // For mock_live: includes BOTH Mock config AND IBKR connection details
    "host": "ib-gateway-ibkr-mock",
    "port": 4004,
    "client_id": 2,
    "initial_balance": 1000000  // Mock broker config
  }
}
```

**Signal Data:**
```json
{
  "account_type": "mock",  // Extracted from mode
  "data_source": "live",   // Extracted from mode
  "mode": "mock_live"      // Computed field for convenience
}
```

---

## Broker Pool Management

### What is the Broker Pool?
Global dictionary in `execution_service` that holds all broker instances:

```python
# Global in execution_main.py
broker_pool: Dict[str, AbstractBroker] = {}
```

### Broker Pool Lifecycle

#### 1. **Initialization** (Startup)
```python
# execution_main.py - Module-level initialization
def initialize_broker_pool():
    """Called once at service startup - BLOCKING"""
    
    # Step 1: Query AccountDataService for active accounts
    accounts = get_active_accounts_from_service()
    
    # Step 2: Start IB Gateway containers for IBKR accounts
    start_required_gateways(accounts)
    
    # Step 3: Wait for gateways to be ready (health checks)
    wait_for_gateways_ready(accounts, max_wait=60)
    
    # Step 4: Create broker instances for each account × mode
    for account in accounts:
        for mode in account['mode']:  # mode can be array
            account_type, data_source = parse_mode(mode)
            
            if account_type == 'mock' and data_source == 'mock':
                # Create Mock broker only
                broker_pool[f"{account_id}_mock_mock"] = Mock()
                
            elif account_type == 'mock' and data_source == 'live':
                # Create BOTH brokers, wrap in adapter
                real_broker = IBKR(auth_details)
                mock_broker = Mock(auth_details)
                adapter = BrokerModeAdapter(
                    real_broker, mock_broker,
                    account_type='mock', data_source='live'
                )
                broker_pool[f"{account_id}_mock_live"] = adapter
                
            elif account_type == 'paper':
                # Create IBKR on port 4004
                broker_pool[f"{account_id}_paper_live"] = IBKR(port=4004)
                
            elif account_type == 'live':
                # Create IBKR on port 4001
                broker_pool[f"{account_id}_live_live"] = IBKR(port=4001)
```

#### 2. **Broker Pool Keys** (Multiple Keys for Same Broker)
```python
# For account IBKR-TESTING-ACCOUNT with mode=paper_live:
broker_pool = {
    # Mode-specific key (PRIMARY)
    "IBKR-TESTING-ACCOUNT_paper_live": <IBKRBroker>,
    
    # Account ID key (for backward compatibility)
    "IBKR-TESTING-ACCOUNT": <IBKRBroker>,
    
    # Legacy keys (deprecated but still used)
    "ibkr_paper": <IBKRBroker>
}
```

**Why Multiple Keys?**
- **Mode-specific keys** prevent overwrites when account supports multiple modes
- **Account ID keys** for simple lookups without mode
- **Legacy keys** for backward compatibility with old code

#### 3. **Broker Retrieval**
```python
def get_broker_for_account(account_id: str, mode: str = None) -> AbstractBroker:
    """
    Lookup broker from pool with mode-aware fallback
    
    Lookup order:
    1. Try mode_key: {account_id}_{mode} (if mode provided)
    2. Try account_id directly
    3. Try legacy keys (ibkr_paper, ibkr_live, mock)
    4. Return None if not found
    """
    if mode:
        # Try mode-specific key first
        broker = broker_pool.get(f"{account_id}_{mode}")
        if broker:
            return broker
    
    # Fallback to account_id
    broker = broker_pool.get(account_id)
    if broker:
        return broker
    
    # Legacy fallbacks
    # ...
    
    return None
```

#### 4. **Connection Management**
```python
# Brokers connect during initialization
def connect_all_brokers_sync():
    """Connect all brokers in pool (called at startup)"""
    for key, broker in broker_pool.items():
        try:
            if broker.connect():
                logger.info(f"✅ Connected: {key}")
            else:
                logger.warning(f"⚠️ Connection failed: {key}")
        except Exception as e:
            logger.error(f"❌ Error connecting {key}: {e}")
```

**Connection States:**
- Brokers stay connected throughout service lifetime
- IB Gateway containers run 24/7 (managed by `gateway_controller.py`)
- Reconnection handled automatically by `ib_insync` library

#### 5. **When Brokers are Recreated**
- **Service restart:** Full broker pool rebuild
- **Docker restart:** Containers restart, brokers reconnect
- **Manual reload:** ⚠️ REMOVED - caused race conditions
- **Gateway restart:** Broker reconnects automatically

---

## Service Interactions & Flow

### Complete Signal Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: SIGNAL INGESTION                                             │
└─────────────────────────────────────────────────────────────────────────┘

External Source (TradingView, API, etc.)
    ↓
    POST /webhooks/tradingview → writes to trading_signals_raw
    ↓
Signal Ingestion Service (MongoDBWatcher)
    ↓ watches trading_signals_raw collection
    ↓
SignalStandardizer
    - Validates required fields
    - Extracts account_type, data_source from signal
    - Computes mode = {account_type}_{data_source}
    - Generates mathematricks_signal_id
    ↓
Writes to signal_store collection
    {
      signal_id: "...",
      mathematricks_signal_id: "ENTRY-...",
      mode: "mock_live",
      account_type: "mock",
      data_source: "live",
      signal_data: {...},
      cerebro_decision: null,  // Updated in Phase 2
      execution: null,         // Updated in Phase 3
      processing_complete: false
    }

┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: CEREBRO PROCESSING (Order Creation)                          │
└─────────────────────────────────────────────────────────────────────────┘

Cerebro Service (MongoDBWatcher)
    ↓ watches signal_store collection (processing_complete=false)
    ↓
STEP 1: Validate Signal
    - Check strategy exists
    - Validate instrument
    - Check market hours
    ↓
STEP 2: Sync Account Balance (if needed)
    POST /api/v1/sync-account-balance → Execution Service
    - Cerebro calls execution service BEFORE position sizing
    - Ensures fresh balance for margin validation
    - Execution service queries broker if stale (>60s)
    ↓
STEP 3: Fund Allocation (Mode-Aware)
    get_accounts_for_strategy(strategy_id, mode="mock_live")
    - Extracts account_type from mode: "mock_live" → "mock"
    - Looks up strategy.accounts[account_type] for allowed accounts
    - Filters accounts matching mode
    ↓
STEP 4: Position Sizing
    - Calculate position size based on:
      * Account equity
      * Strategy allocation %
      * Risk per trade
      * Margin requirements
    ↓
STEP 5: Create Order Data
    order_data = {
      order_id: "ORD-...",
      signal_id: "...",
      account_id: "IBKR-MOCK",
      mode: "mock_live",  // ← CRITICAL for broker routing
      instrument: "AAPL",
      side: "BUY",
      quantity: 100,
      cerebro_decision: {...}  // Detailed calculation breakdown
    }
    ↓
STEP 6: Update signal_store
    Updates: cerebro_decision, order_id
    Does NOT set processing_complete=true (execution not done yet)
    ↓
STEP 7: Send to Execution
    POST /api/v1/execute-order → Execution Service

┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: EXECUTION (Order Routing & Fill)                             │
└─────────────────────────────────────────────────────────────────────────┘

Execution Service
    ↓
STEP 1: Queue Order
    order_queue.put(order_data)
    Returns: {"status": "queued"}
    ↓
STEP 2: Broker Lookup (Mode-Aware)
    broker = get_broker_for_account(account_id, mode="mock_live")
    
    Lookup order:
    1. broker_pool["IBKR-MOCK_mock_live"]  ← Mode-specific key
    2. broker_pool["IBKR-MOCK"]            ← Account key
    3. broker_pool["mock"]                 ← Legacy key
    ↓
STEP 3: Execute Order
    result = broker.place_order(order_data)
    
    For mock_live mode:
    - BrokerModeAdapter routes to mock_broker.place_order()
    - Mock broker simulates fill instantly
    - Returns fill confirmation
    ↓
STEP 4: Update Position (ENTRY Orders)
    trading_accounts.update_one(
      {"account_id": account_id},
      {
        "$push": {
          "open_positions": {
            "position_id": "POS-...",
            "instrument": "AAPL",
            "quantity": 100,
            "direction": "LONG",
            "avg_entry_price": 150.00,
            "status": "OPEN",
            "strategy_id": "...",
            "signal_id": "...",
            "entry_signal_id": "..."  // For EXIT matching
          }
        }
      }
    )
    ↓
STEP 5: Update signal_store.execution
    signal_store.update_one(
      {"signal_id": signal_id},
      {
        "$set": {
          "execution": {
            "status": "FILLED",
            "filled_quantity": 100,
            "avg_fill_price": 150.00,
            "orders": [{...}],
            "fills": [{...}],
            "timestamp": "..."
          },
          "processing_complete": true  // ← Signal journey complete
        }
      }
    )

┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: POSITION EXIT (Reconciliation Flow)                          │
└─────────────────────────────────────────────────────────────────────────┘

EXIT Signal Arrives
    ↓ Same flow through Signal Ingestion → Cerebro
    ↓
Execution Service (EXIT-specific logic)
    ↓
STEP 1: Find Entry Position
    position = find_position_by_entry_signal_id(entry_signal_id)
    
    CRITICAL: EXIT signals have entry_signal_ref field:
    {
      "entry_signal_ref": {
        "entry_signal_id": "ENTRY-AAPL-123",
        "mathematricks_signal_id": "ENTRY-AAPL-123"
      }
    }
    ↓
STEP 2: Execute EXIT Order
    broker.place_order(exit_order)
    ↓
STEP 3: Update Position Status
    trading_accounts.update_one(
      {"account_id": account_id, "open_positions.position_id": position_id},
      {
        "$set": {
          "open_positions.$.status": "CLOSED",
          "open_positions.$.exit_price": 155.00,
          "open_positions.$.exit_timestamp": "...",
          "open_positions.$.realized_pnl": 500.00
        }
      }
    )
    ↓
STEP 4: Update signal_store (EXIT Signal)
    IMPORTANT: update_signal_store_with_reconciliation()
    - Updates execution field with fills
    - Updates position.exit_quantity (recent fix)
    - Sets processing_complete=true
```

---

## Balance Update Mechanisms

### Two Approaches: Polling vs On-Demand Sync

#### 1. **Background Polling** (Account Data Service)
```python
# broker_poller.py
class BrokerPoller:
    def __init__(self, interval: int = 300):  # 5 minutes
        self.interval = interval
    
    def poll_account(self, account: Dict):
        """Periodic background polling"""
        broker = self._get_broker(account_id, config)
        
        # Get fresh balances from broker
        balance = broker.get_account_balance()
        
        # Update MongoDB
        repository.update_balances(account_id, {
            "equity": balance['equity'],
            "cash_balance": balance['cash_balance'],
            "margin_available": balance['margin_available'],
            "last_updated": datetime.utcnow()
        })
```

**When Used:**
- Regular background updates every 5 minutes
- Keeps balances reasonably fresh
- Low priority, eventual consistency

#### 2. **On-Demand Sync** (Execution Service API)
```python
# execution_main.py
@app.post('/api/v1/sync-account-balance')
async def sync_account_balance(account_id: str, max_age_seconds: int = 60):
    """Sync balance if stale, return cached if fresh"""
    
    # Check cache age
    account = trading_accounts_collection.find_one({"account_id": account_id})
    balances = account.get('balances', {})
    last_updated = balances.get('last_updated')
    
    if last_updated:
        age_seconds = (datetime.utcnow() - last_updated).total_seconds()
        if age_seconds < max_age_seconds:
            return {"balances": balances, "source": "cache"}
    
    # Fetch fresh from broker
    broker = broker_pool.get(f"{account_id}_{mode}")
    fresh_balance = await loop.run_in_executor(None, broker.get_account_balance)
    
    # Update MongoDB
    trading_accounts_collection.update_one(
        {"account_id": account_id},
        {"$set": {"balances": fresh_balance}}
    )
    
    return {"balances": fresh_balance, "source": "broker"}
```

**When Used:**
- Cerebro calls before position sizing (critical path)
- Ensures margin calculations use fresh data
- High priority, immediate consistency

### Balance Update Flow for mock_live Mode

```
Cerebro needs balance for position sizing
    ↓
POST /sync-account-balance?account_id=IBKR-MOCK&max_age=60
    ↓
Execution Service checks cache
    - If age < 60s: Return cached balance
    - If age ≥ 60s: Query broker
    ↓
For mock_live mode:
    broker = broker_pool["IBKR-MOCK_mock_live"]  # BrokerModeAdapter
    balance = broker.get_account_balance()
    ↓
BrokerModeAdapter.get_account_balance()
    ↓ Routes to real_broker (IBKR)
    ↓
IBKR.get_account_balance()
    - Queries IB Gateway for account summary
    - Returns real margin available, equity
    ↓
Execution Service updates MongoDB
    ↓
Cerebro receives fresh balance
    ↓
Position sizing uses real margin constraints
```

**Why This Matters for mock_live:**
- Mock broker simulates fills, but needs real margin constraints
- Using real IBKR balance ensures position sizing is realistic
- Prevents over-leveraging in simulation mode

---

## Position Tracking Architecture

### MongoDB Position Schema

```json
{
  "account_id": "IBKR-MOCK",
  "open_positions": [
    {
      "position_id": "POS-abc123",
      "instrument": "AAPL",
      "quantity": 100,
      "direction": "LONG",
      "avg_entry_price": 150.00,
      "current_price": 152.00,
      "unrealized_pnl": 200.00,
      "status": "OPEN",  // OPEN | CLOSED
      
      // Entry tracking
      "entry_timestamp": "2026-01-30T10:00:00Z",
      "entry_signal_id": "ENTRY-AAPL-123",
      "signal_id": "abc123",
      "strategy_id": "tech_momentum",
      "fund_id": "growth_fund",
      
      // Exit tracking (filled when position closes)
      "exit_price": null,
      "exit_timestamp": null,
      "exit_signal_id": null,
      "realized_pnl": null,
      
      // Multi-leg support
      "parent_signal_id": null,
      "leg_index": 0,
      "total_legs": 1,
      
      // Reconciliation
      "reconciliation_attempts": 0
    }
  ],
  "broker_positions_snapshot": [
    // Positions from broker.get_open_positions()
    // Used for reconciliation/comparison
  ]
}
```

### Position Lifecycle

#### 1. **ENTRY Signal → Create Position**
```python
# execution_main.py - handle_order_execution()
if signal_type == "ENTRY":
    new_position = {
        "position_id": generate_position_id(),
        "instrument": instrument,
        "quantity": filled_quantity,
        "direction": "LONG" if side == "BUY" else "SHORT",
        "avg_entry_price": avg_fill_price,
        "status": "OPEN",
        "entry_timestamp": datetime.utcnow(),
        "entry_signal_id": mathematricks_signal_id,
        "signal_id": signal_id,
        "strategy_id": strategy_id,
        "fund_id": fund_id
    }
    
    trading_accounts_collection.update_one(
        {"account_id": account_id},
        {"$push": {"open_positions": new_position}}
    )
```

#### 2. **EXIT Signal → Close Position**
```python
# execution_main.py - handle_order_execution()
if signal_type == "EXIT":
    # Find matching position by entry_signal_id
    entry_signal_id = signal_data.get('entry_signal_ref', {}).get('entry_signal_id')
    position = find_position(account_id, entry_signal_id)
    
    # Calculate PnL
    realized_pnl = calculate_pnl(position, exit_price)
    
    # Update position to CLOSED
    trading_accounts_collection.update_one(
        {"account_id": account_id, "open_positions.position_id": position_id},
        {"$set": {
            "open_positions.$.status": "CLOSED",
            "open_positions.$.exit_price": exit_price,
            "open_positions.$.exit_timestamp": datetime.utcnow(),
            "open_positions.$.exit_signal_id": signal_id,
            "open_positions.$.realized_pnl": realized_pnl
        }}
    )
```

#### 3. **Position Display Filtering**
```python
# Only show OPEN positions in UI/logs
open_positions = [
    pos for pos in account['open_positions']
    if pos.get('status') == 'OPEN'
]
```

### Position Reconciliation

**Problem:** Execution fills might not match position tracking updates

**Solution:** Reconciliation flow for EXIT signals

```python
# execution_main.py
def update_signal_store_with_reconciliation(signal_id, execution_data):
    """
    Update signal_store for signals that went through reconciliation
    (typically EXIT signals)
    
    CRITICAL: Must update BOTH execution field AND position tracking
    """
    
    # Update execution field
    signal_store_collection.update_one(
        {"signal_id": signal_id},
        {"$set": {
            "execution": execution_data,
            "processing_complete": True
        }}
    )
    
    # IMPORTANT: Also update position.exit_quantity
    # (Bug fix from 2026-01-30 - was missing this step)
    if execution_data.get('status') == 'FILLED':
        filled_qty = execution_data.get('total_quantity_filled', 0)
        
        # Update position tracking
        signal_doc = signal_store_collection.find_one({"signal_id": signal_id})
        entry_signal_id = signal_doc.get('entry_signal_ref', {}).get('entry_signal_id')
        
        trading_accounts_collection.update_one(
            {
                "account_id": account_id,
                "open_positions.entry_signal_id": entry_signal_id
            },
            {"$set": {
                "open_positions.$.exit_quantity": filled_qty,
                "open_positions.$.status": "CLOSED"
            }}
        )
```

---

## Mode Validation & Routing

### Mode Flow Through Services

```
1. SIGNAL INGESTION
   ↓
   Extracts account_type, data_source from raw signal
   Computes: mode = f"{account_type}_{data_source}"
   Saves to signal_store.mode

2. CEREBRO
   ↓
   Reads signal_store.mode
   Validates: account supports this mode
   Fund allocation: Filters accounts by mode
   Passes mode to Execution Service in order_data

3. EXECUTION
   ↓
   Reads order_data.mode
   Constructs broker lookup key: f"{account_id}_{mode}"
   Routes to correct broker in pool
```

### Mode Validation Rules

#### In Strategy Configuration
```json
// strategies collection
{
  "strategy_id": "tech_momentum",
  "accounts": {
    "mock": ["IBKR-MOCK"],      // Allowed for mock_mock, mock_live
    "paper": ["IBKR-PAPER"],    // Allowed for paper_live
    "live": ["IBKR-LIVE"]       // Allowed for live_live
  }
}
```

#### In Cerebro Fund Allocation
```python
# fund_allocation_logic.py
def get_accounts_for_strategy(strategy_id: str, mode: str):
    """
    Get allowed accounts for strategy, filtered by mode
    
    Mode-aware logic:
    1. Extract account_type from mode (mock_live → mock)
    2. Look up strategy.accounts[account_type]
    3. Filter those accounts to only ones supporting this mode
    """
    # Extract account_type
    account_type = mode.split('_')[0]  # mock_live → mock
    
    # Get allowed accounts for this account_type
    strategy = strategies_collection.find_one({"strategy_id": strategy_id})
    allowed_accounts = strategy.get('accounts', {}).get(account_type, [])
    
    # Filter accounts that support this specific mode
    accounts_with_mode = [
        acc for acc in trading_accounts_collection.find(
            {"account_id": {"$in": allowed_accounts}}
        )
        if mode in acc.get('mode', [])
    ]
    
    return accounts_with_mode
```

### Mode-Specific Broker Behavior

#### BrokerModeAdapter Routing
```python
# mode_adapter.py
class BrokerModeAdapter:
    def __init__(self, real_broker, mock_broker, account_type, data_source):
        self.real_broker = real_broker
        self.mock_broker = mock_broker
        self.account_type = account_type
        self.data_source = data_source
    
    def get_current_price(self, instrument):
        """Always from real broker (live data)"""
        return self.real_broker.get_current_price(instrument)
    
    def get_account_balance(self):
        """Always from real broker (realistic margin)"""
        return self.real_broker.get_account_balance()
    
    def place_order(self, order):
        """Routes based on account_type"""
        if self.account_type == 'mock':
            # Mock execution
            return self.mock_broker.place_order(order)
        else:
            # Real execution (paper or live)
            return self.real_broker.place_order(order)
    
    def get_open_positions(self):
        """Routes based on account_type"""
        if self.account_type == 'mock':
            # Mock positions (from MongoDB)
            return self.mock_broker.get_open_positions()
        else:
            # Real positions (from IBKR)
            return self.real_broker.get_open_positions()
```

---

## Data Flow: Signal → Execution → Reconciliation

### Complete Data Journey

```
PHASE 1: RAW SIGNAL
MongoDB: trading_signals_raw
{
  "_id": ObjectId("..."),
  "ticker": "AAPL",
  "action": "BUY",
  "quantity": 100,
  "account_type": "mock",
  "data_source": "live",
  "timestamp": "2026-01-30T10:00:00Z"
}

↓ Signal Ingestion Service watches this collection
↓ Standardizes and enriches

PHASE 2: SIGNAL STORE (Initial)
MongoDB: signal_store
{
  "_id": ObjectId("..."),
  "signal_id": "abc123",
  "mathematricks_signal_id": "ENTRY-AAPL-20260130-100000",
  "mode": "mock_live",
  "account_type": "mock",
  "data_source": "live",
  "signal_data": {...},
  "cerebro_decision": null,      // ← Updated in Phase 3
  "execution": null,             // ← Updated in Phase 4
  "processing_complete": false,
  "created_at": "2026-01-30T10:00:01Z"
}

↓ Cerebro Service watches processing_complete=false
↓ Processes signal, creates order

PHASE 3: SIGNAL STORE (After Cerebro)
{
  // ... same fields ...
  "cerebro_decision": {
    "action": "APPROVED",
    "account_id": "IBKR-MOCK",
    "allocated_capital": 50000,
    "position_size_shares": 100,
    "margin_required": 15000,
    "margin_available": 500000,
    "calculation_breakdown": {...}
  },
  "order_id": "ORD-abc123",
  "processing_complete": false  // ← Still false (not executed yet)
}

↓ Cerebro calls Execution Service
↓ POST /api/v1/execute-order

PHASE 4: SIGNAL STORE (After Execution)
{
  // ... same fields ...
  "execution": {
    "status": "FILLED",
    "filled_quantity": 100,
    "avg_fill_price": 150.25,
    "orders": [
      {
        "broker_order_id": "DU12345",
        "status": "FILLED",
        "filled_quantity": 100,
        "avg_fill_price": 150.25
      }
    ],
    "fills": [
      {
        "execution_id": "EXEC-1",
        "quantity": 100,
        "price": 150.25,
        "timestamp": "2026-01-30T10:00:05Z"
      }
    ],
    "timestamp": "2026-01-30T10:00:05Z"
  },
  "processing_complete": true  // ← DONE!
}

PHASE 5: POSITION TRACKING (trading_accounts)
{
  "account_id": "IBKR-MOCK",
  "open_positions": [
    {
      "position_id": "POS-xyz",
      "instrument": "AAPL",
      "quantity": 100,
      "direction": "LONG",
      "avg_entry_price": 150.25,
      "status": "OPEN",
      "entry_signal_id": "ENTRY-AAPL-20260130-100000",
      "signal_id": "abc123",
      "strategy_id": "tech_momentum"
    }
  ]
}
```

---

## Common Pitfalls & Edge Cases

### 1. **Broker Pool Key Mismatches**

**Problem:**
```python
# Account configured with mode=["mock_mock", "mock_live"]
# Broker stored under: "IBKR-MOCK_mock_live"
# But code looks up: broker_pool["IBKR-MOCK"]
# Result: KeyError or wrong broker
```

**Solution:**
- Always pass `mode` to `get_broker_for_account(account_id, mode)`
- Use mode-specific keys as primary lookup
- Fall back to account_id for backward compatibility

### 2. **Balance Staleness in Position Sizing**

**Problem:**
- Account Data Service polls every 5 minutes
- Mock broker executes order, updates balance in MongoDB
- But poll hasn't happened yet
- Next signal uses stale balance → incorrect position sizing

**Solution:**
- Cerebro calls `/sync-account-balance` BEFORE position sizing
- Ensures balance is fresh (<60s old)
- For mock_live: Gets real balance from IBKR

### 3. **Position Tracking Inconsistency**

**Problem:**
- EXIT signal goes through reconciliation path
- `update_signal_store_with_reconciliation()` updates execution field
- But forgets to update position.exit_quantity
- Frontend shows position still open

**Solution (Fixed 2026-01-30):**
```python
def update_signal_store_with_reconciliation(signal_id, execution_data):
    # Update execution field
    signal_store_collection.update_one(...)
    
    # CRITICAL: Also update position tracking
    if signal_type == "EXIT":
        trading_accounts_collection.update_one(
            {"account_id": account_id, "open_positions.entry_signal_id": entry_signal_id},
            {"$set": {
                "open_positions.$.exit_quantity": filled_qty,
                "open_positions.$.status": "CLOSED"
            }}
        )
```

### 4. **Mode Field Format Inconsistency**

**Problem:**
- Old accounts have `mode: "mock_mock"` (string)
- New accounts have `mode: ["mock_mock", "mock_live"]` (array)
- Code assumes one format

**Solution:**
```python
# Always normalize to list
mode = account.get('mode')
if isinstance(mode, str):
    modes = [mode]
elif isinstance(mode, list):
    modes = mode
else:
    logger.error(f"Invalid mode format: {mode}")
    modes = []
```

### 5. **IB Gateway Startup Race Condition**

**Problem:**
- Docker compose starts execution service
- Broker pool initialization tries to connect
- IB Gateway container still starting (60s delay)
- Connection fails, broker pool empty

**Solution:**
```python
def wait_for_gateways_ready(accounts, max_wait=60):
    """
    Wait for IB Gateway API to be actually ready
    Not just port open, but API responding
    """
    for account in ibkr_accounts:
        while time.time() - start < max_wait:
            if check_gateway_health(host, port):
                # API is ready
                break
            time.sleep(2)
```

### 6. **Mock Broker Balance Updates**

**Problem:**
- Mock broker has initial_balance=1000000
- Executes 10 trades
- Balance should decrease
- But MongoDB still shows 1000000

**Solution:**
- Mock broker updates `trading_accounts.balances` after each trade
- Account Data Service reads from MongoDB (not broker API)
- Balance automatically reflects mock executions

### 7. **Entry Signal ID Matching for Exits**

**Problem:**
- EXIT signal arrives
- Needs to find matching ENTRY position
- Signal has entry_signal_id, but position uses different ID format

**Solution:**
```python
# EXIT signal MUST have:
{
  "entry_signal_ref": {
    "entry_signal_id": "ENTRY-AAPL-123",  # Must match position.entry_signal_id
    "mathematricks_signal_id": "ENTRY-AAPL-123"
  }
}

# Position tracking MUST store:
{
  "entry_signal_id": "ENTRY-AAPL-123",  # From mathematricks_signal_id field
  "signal_id": "abc123"                  # MongoDB _id or raw signal_id
}
```

### 8. **Multi-Leg Signal Position Tracking**

**Problem:**
- Option spread has 4 legs
- Each leg executes separately
- Need to track overall spread position + individual legs

**Solution:**
```python
# Parent signal creates overall position
{
  "position_id": "POS-spread-123",
  "instrument": "AAPL_SPREAD",
  "status": "OPEN",
  "total_legs": 4,
  "legs_filled": 0  # Increment as each leg fills
}

# Each leg creates child position
{
  "position_id": "POS-leg-1",
  "parent_signal_id": "spread-123",
  "leg_index": 1,
  "total_legs": 4,
  "instrument": "AAPL 150C",
  "status": "OPEN"
}
```

---

## Appendix: Key Configuration Files

### gateway_config.yml
```yaml
# Execution Service - IB Gateway Management
always_start_accounts:
  - IBKR-TESTING-ACCOUNT  # Start gateway on service boot
  - IBKR-LIVE            # Production account

# Gateways start if:
# 1. Listed in always_start_accounts, OR
# 2. Account has open positions
```

### .env (Critical Variables)
```bash
MONGODB_URI=mongodb://localhost:27018
ACCOUNT_DATA_SERVICE_URL=http://localhost:8082

# IBKR Gateway Configuration
IBKR_GATEWAY_BASE_PORT=4000
# Paper accounts: 4002, 4004, 4006...
# Live accounts: 4001, 4003, 4005...
```

### docker-compose.yml (Service Dependencies)
```yaml
services:
  signal-ingestion:
    depends_on: [mongodb]
  
  cerebro:
    depends_on: [mongodb, signal-ingestion]
  
  execution-service:
    depends_on: [mongodb, cerebro]
  
  account-data-service:
    depends_on: [mongodb]
```

---

## Quick Reference: Service Responsibilities

| Component | Reads From | Writes To | Primary Responsibility |
|-----------|------------|-----------|------------------------|
| **Signal Ingestion** | `trading_signals_raw` | `signal_store` | Standardize incoming signals |
| **Cerebro** | `signal_store`, `strategies`, `funds`, `trading_accounts` | `signal_store` (cerebro_decision), `trading_orders` | Position sizing, risk management, order creation |
| **Execution** | `signal_store`, `trading_accounts` | `signal_store` (execution), `trading_accounts` (positions, balances) | Order execution, position tracking |
| **Account Data** | `trading_accounts` | `trading_accounts` (balances, broker_positions_snapshot) | Background polling, balance sync |

---

## Conclusion

This system uses a **4-mode architecture** to support multiple trading environments with a **unified codebase**. The broker pool acts as a **mode-aware routing layer**, and MongoDB serves as the **single source of truth** for all state.

**Critical Principles:**
1. **Mode must flow through the entire pipeline** (ingestion → cerebro → execution)
2. **Broker pool keys must include mode** to prevent overwrites
3. **Balance sync must happen before position sizing** (cerebro → execution API)
4. **Position tracking must update on BOTH ENTRY and EXIT** paths
5. **EXIT signals must match ENTRY via entry_signal_id**

**When in doubt:**
- Check broker pool keys (mode-specific vs account-specific)
- Verify mode field propagation through services
- Trace balance update timestamps
- Validate position status (OPEN vs CLOSED)

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-30  
**Maintained By:** AI Documentation Team
