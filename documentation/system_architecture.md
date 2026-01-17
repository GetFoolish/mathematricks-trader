Architecture Understanding: Fund → Account → Strategy → Broker → Allocations
Based on the documentation, here's how the system works:

1. FUND (Top-Level Entity)
Purpose: Capital container that owns multiple trading accounts
Collection: funds
Key Fields:
fund_id: Unique identifier (e.g., "ibkr-testing", "mathematricks-1")
total_equity: Calculated sum of all account equities
accounts[]: List of account_ids owned by this fund
approved_allocation: CRITICAL - Snapshot of approved portfolio allocation
portfolio_test_id: Reference to the portfolio test
allocations{}: Dictionary of strategy_id → percentage (e.g., {"SPY": 20.0, "TLT": 15.0})
approved_at: When allocation was approved
2. TRADING ACCOUNTS (Fund's Resources)
Purpose: Actual broker accounts that execute trades
Collection: trading_accounts
Key Fields:
account_id: Unique identifier (e.g., "IBKR_Paper_Test", "IBKR_Main")
fund_id: Parent fund - which fund owns this account
broker: Which broker (IBKR, Binance, Mock, etc.)
asset_classes{}: CRITICAL - What this account can trade
Structure: {equities: [], futures: [], options: [], forex: [], crypto: []}
Values are arrays (empty array = can trade all in that class)
balances: Current equity, margin, cash, etc.
open_positions[]: Current holdings
3. STRATEGIES (Trading Logic)
Purpose: Individual trading strategies that generate signals
Collection: strategies
Key Fields:
strategy_id: Unique identifier (e.g., "SPY", "IBKR_Test_Stock")
asset_class: What this strategy trades (STOCK, CRYPTO, FOREX, FUTURE, OPTION)
accounts[]: CRITICAL - Which accounts this strategy is ALLOWED to use
status: ACTIVE/INACTIVE
4. ALLOCATIONS (Capital Distribution)
Source of Truth: portfolio_tests collection
Reference: funds.approved_allocation.portfolio_test_id
Structure: Dictionary mapping strategy_id to percentage
Example: {"SPY": 20.0, "TLT": 15.0, "Com1-Met": 10.0} = total 45% of fund allocated
5. SIGNAL FLOW (When Trade Signal Arrives)
SIGNAL ARRIVES
    ↓
[Signal Ingestion Service] → Writes to signal_store
    ↓
[Cerebro Service] (Change Stream watcher)
    ↓
1. GET FUND ALLOCATIONS
   - Find all ACTIVE allocations for this strategy_id
   - Query: funds (where status=ACTIVE) → get approved_allocation.allocations[strategy_id]
   
2. FOR EACH FUND WITH ALLOCATION:
   
   a) CALCULATE FUND EQUITY
      - Sum all trading_accounts.balances.equity where fund_id matches
      
   b) CALCULATE ALLOCATED CAPITAL
      - allocated_capital = fund_equity × allocation_percentage
      - Example: $1M fund × 15% SPY allocation = $150k
      
   c) GET COMPATIBLE ACCOUNTS
      - Filter accounts by:
        ✓ account.fund_id = current fund
        ✓ account.account_id IN strategy.accounts[] (permission)
        ✓ account.asset_classes[mapped_asset_class] exists
        ✓ account.status = ACTIVE
      
   d) ASSET CLASS MAPPING (THE BUG I FOUND!)
      - Strategies use: STOCK, CRYPTO, FOREX, FUTURE, OPTION
      - Accounts use: equities, crypto, forex, futures, options
      - Mapping needed: STOCK → equities, FUTURE → futures, etc.
      
   e) CALCULATE POSITION SIZE
      - Based on allocated_capital and signal parameters
      - Round to instrument lot sizes
      
   f) VALIDATE MARGIN
      - Call Account Data Service for margin check
      
   g) DISTRIBUTE ACROSS ACCOUNTS
      - Proportionally by account equity or other logic
      
   h) CREATE ORDERS
      - Insert into trading_orders collection
      - One order per account
      
   i) UPDATE SIGNAL_STORE
      - Write cerebro decision back to signal_store.legs[].decision
6. EXECUTION (Order → Broker)
Execution Service watches trading_orders collection
Routes orders to appropriate broker API
Updates order status and fills