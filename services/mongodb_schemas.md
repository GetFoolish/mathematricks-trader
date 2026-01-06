# MongoDB Schemas - v5 (Fund Architecture)

## Database: `mathematricks_trading`

---

## NEW COLLECTIONS (v5)

### Collection: `funds`
**Purpose:** Top-level fund entities that own accounts and capital

```json
{
  "_id": ObjectId,
  "fund_id": String,                          // Primary key (e.g., "mathematricks-1")
  "name": String,                             // Display name (e.g., "Mathematricks Capital Fund 1")
  "description": String,                      // Optional description
  "total_equity": Number,                     // Current total equity (auto-calculated from accounts)
  "currency": String,                         // "USD", "EUR", "GBP"
  "accounts": [String],                       // Array of account_ids owned by this fund
  "status": String,                           // "ACTIVE" | "PAUSED" | "CLOSED"
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
- `{fund_id: 1}` - Unique index
- `{status: 1}` - For filtering active funds

**Validation Rules:**
- `fund_id` must be unique and lowercase
- `total_equity` must be >= 0
- `status` must be one of: ACTIVE, PAUSED, CLOSED
- Cannot delete fund if it has ACTIVE allocations

**Example:**
```json
{
  "fund_id": "mathematricks-1",
  "name": "Mathematricks Capital Fund 1",
  "description": "Main production fund",
  "total_equity": 750234.56,
  "currency": "USD",
  "accounts": ["IBKR_Main", "IBKR_Futures", "Binance_Main"],
  "status": "ACTIVE",
  "created_at": ISODate("2026-01-03T00:00:00Z"),
  "updated_at": ISODate("2026-01-03T18:00:00Z")
}
```

---

### Collection: `trading_accounts` (UPDATED)
**Purpose:** Broker accounts with fund ownership and asset class constraints

**ADDED FIELDS in v5:**
```json
{
  // ... existing fields ...
  "fund_id": String,                          // NEW: Parent fund (e.g., "mathematricks-1")
  "asset_classes": {                          // NEW: What this account can trade
    "equity": [String],                       // ["all"] or ["SPY", "AAPL", ...]
    "futures": [String],                      // ["all"] or ["ES", "NQ", ...]
    "crypto": [String],                       // ["all"] or ["BTC", "ETH", "USDT"]
    "forex": [String]                         // ["all"] or ["EUR/USD", "GBP/USD"]
  }
}
```

**Full Schema:**
```json
{
  "_id": ObjectId,
  "account_id": String,                       // Unique identifier (e.g., "IBKR_Main")
  "broker": String,                           // "IBKR", "Binance", "Alpaca", "Mock_Paper"
  "broker_account_number": String,            // Actual broker account (e.g., "DU123456")
  "fund_id": String,                          // Parent fund
  "asset_classes": {
    "equity": [String],
    "futures": [String],
    "crypto": [String],
    "forex": [String]
  },
  "equity": Number,                           // Current account equity
  "cash_balance": Number,
  "margin_used": Number,
  "margin_available": Number,
  "unrealized_pnl": Number,
  "realized_pnl": Number,
  "open_positions": [
    {
      "instrument": String,
      "strategy_id": String,                  // Which strategy owns this position
      "quantity": Number,
      "entry_price": Number,
      "current_price": Number,
      "unrealized_pnl": Number,
      "margin_required": Number
    }
  ],
  "status": String,                           // "ACTIVE" | "INACTIVE" | "PENDING"
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
- `{account_id: 1}` - Unique index
- `{fund_id: 1}` - For querying by fund
- `{broker: 1}` - For broker-specific queries
- `{open_positions.instrument: 1}` - For position lookups
- `{open_positions.strategy_id: 1}` - For strategy position queries

**Default Asset Classes by Broker:**
- **IBKR:** `{equity: ["all"], futures: ["all"], crypto: [], forex: ["all"]}`
- **Binance:** `{equity: [], futures: [], crypto: ["all"], forex: []}`
- **Alpaca:** `{equity: ["all"], futures: [], crypto: [], forex: []}`
- **Mock_Paper:** `{equity: ["all"], futures: ["all"], crypto: ["all"], forex: ["all"]}`

**Example:**
```json
{
  "account_id": "IBKR_Main",
  "broker": "IBKR",
  "broker_account_number": "DU123456",
  "fund_id": "mathematricks-1",
  "asset_classes": {
    "equity": ["all"],
    "futures": ["all"],
    "crypto": [],
    "forex": ["all"]
  },
  "equity": 500123.45,
  "cash_balance": 450000.00,
  "margin_used": 50123.45,
  "margin_available": 449876.55,
  "unrealized_pnl": 123.45,
  "realized_pnl": 5678.90,
  "open_positions": [
    {
      "instrument": "SPY",
      "strategy_id": "SPX_1-D_Opt",
      "quantity": 100,
      "entry_price": 450.00,
      "current_price": 451.23,
      "unrealized_pnl": 123.00,
      "margin_required": 10000.00
    }
  ],
  "status": "ACTIVE",
  "created_at": ISODate("2026-01-01T00:00:00Z"),
  "updated_at": ISODate("2026-01-03T18:00:00Z")
}
```

---

### Collection: `portfolio_allocations` (UPDATED)
**Purpose:** Portfolio allocation recommendations with fund assignment

**ADDED FIELDS in v5:**
```json
{
  // ... existing fields ...
  "fund_id": String,                          // NEW: Which fund this allocation is for
  "allocation_name": String                   // NEW: User-friendly name
}
```

**Full Schema:**
```json
{
  "_id": ObjectId,
  "allocation_id": String,
  "fund_id": String,                          // Which fund (e.g., "mathematricks-1")
  "allocation_name": String,                  // e.g., "Conservative Mix Q1 2026"
  "timestamp": ISODate,
  "status": String,                           // "PENDING_APPROVAL" | "ACTIVE" | "ARCHIVED"
  "allocations": {
    // Key: strategy_id, Value: allocation percentage
    "SPX_1-D_Opt": 45.5,
    "FloridaForex": 30.2,
    "Com1-Met": 24.3
  },
  "expected_metrics": {
    "expected_daily_return": Number,
    "expected_daily_volatility": Number,
    "expected_sharpe_daily": Number,
    "expected_sharpe_annual": Number,
    "total_allocation_pct": Number,
    "leverage_ratio": Number
  },
  "optimization_run_id": String,
  "approved_by": String,
  "approved_at": ISODate,
  "archived_at": ISODate,
  "notes": String,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Validation Rules:**
- Only ONE allocation with `status="ACTIVE"` per fund_id
- When approving allocation, must set all other allocations for same fund to ARCHIVED
- Cannot approve allocation if fund_id does not exist

**Example:**
```json
{
  "allocation_id": "alloc_20260103_001",
  "fund_id": "mathematricks-1",
  "allocation_name": "Aggressive Growth Jan 2026",
  "status": "ACTIVE",
  "allocations": {
    "SPX_1-D_Opt": 15.0,
    "FloridaForex": 10.0,
    "Com1-Met": 5.0
  },
  "expected_metrics": {
    "expected_sharpe_annual": 1.85,
    "total_allocation_pct": 30.0,
    "leverage_ratio": 0.3
  },
  "approved_by": "portfolio_manager",
  "approved_at": ISODate("2026-01-03T12:00:00Z"),
  "created_at": ISODate("2026-01-03T10:00:00Z"),
  "updated_at": ISODate("2026-01-03T12:00:00Z")
}
```

---

## UPDATED COLLECTIONS (v5)

### Collection: `strategies` (UPDATED)
**Purpose:** Strategy definitions with account permissions

**ADDED FIELD in v5:**
```json
{
  // ... existing fields ...
  "accounts": [String]                        // ADDED: Which accounts strategy can trade (e.g., ["IBKR_Main", "IBKR_Futures"])
}
```

**Full Schema:**
```json
{
  "_id": ObjectId,
  "strategy_id": String,                      // Unique identifier (e.g., "SPX_1-D_Opt")
  "strategy_name": String,                    // Human-readable name
  "asset_class": String,                      // "equity" | "futures" | "crypto" | "forex"
  "accounts": [String],                       // Allowed accounts for this strategy
  "status": String,                           // "ACTIVE" | "INACTIVE" | "TESTING"
  "trading_mode": String,                     // "LIVE" | "PAPER"
  "include_in_optimization": Boolean,
  "risk_limits": {
    "max_position_size": Number,
    "max_daily_loss": Number
  },
  "developer_contact": String,
  "notes": String,
  "last_backtest_sync": ISODate,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Validation Rules:**
- All accounts in `accounts[]` must exist in `trading_accounts` collection
- Asset class of strategy must match asset classes supported by accounts
  - Example: `asset_class="equity"` can only use accounts where `asset_classes.equity != []`

**Example:**
```json
{
  "strategy_id": "SPX_1-D_Opt",
  "strategy_name": "SPX 1-Day Options",
  "asset_class": "equity",
  "accounts": ["IBKR_Main"],
  "status": "ACTIVE",
  "trading_mode": "LIVE",
  "include_in_optimization": true,
  "risk_limits": {
    "max_position_size": 50000,
    "max_daily_loss": 5000
  },
  "developer_contact": "trader@example.com",
  "created_at": ISODate("2026-01-01T00:00:00Z"),
  "updated_at": ISODate("2026-01-03T00:00:00Z")
}
```

---

### Collection: `trading_orders` (UPDATED)
**Purpose:** Orders with fund and account tracking

**ADDED FIELD in v5:**
```json
{
  // ... existing fields ...
  "fund_id": String,                          // NEW: Which fund this order belongs to
  "account_id": String                        // RENAMED from "account" for consistency
}
```

**Full Schema:**
```json
{
  "_id": ObjectId,
  "order_id": String,
  "signal_id": String,
  "strategy_id": String,
  "fund_id": String,                          // Fund this order is for
  "account_id": String,                       // Specific account to execute on
  "timestamp": ISODate,
  "instrument": String,
  "direction": String,                        // "LONG" | "SHORT"
  "action": String,                           // "ENTRY" | "EXIT"
  "order_type": String,                       // "MARKET" | "LIMIT" | "STOP"
  "price": Number,
  "quantity": Number,
  "notional_value": Number,                   // quantity * price
  "stop_loss": Number,
  "take_profit": Number,
  "expiry": ISODate,
  "cerebro_decision": {
    "allocated_capital": Number,
    "margin_required": Number,
    "position_size_logic": String,
    "risk_metrics": Object
  },
  "status": String,                           // "PENDING" | "SUBMITTED" | "FILLED" | "REJECTED" | "CANCELLED"
  "broker_order_id": String,                  // Broker's order ID (after submission)
  "filled_at": ISODate,
  "filled_price": Number,
  "filled_quantity": Number,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
- `{order_id: 1}` - Unique index
- `{fund_id: 1, strategy_id: 1, status: 1}` - For fund-level capital calculations
- `{account_id: 1, status: 1}` - For account-level queries
- `{signal_id: 1}` - Link to original signal

---

## EXISTING COLLECTIONS (Unchanged)

### Collection: `raw_signals`
Stores raw incoming signals from external providers (before standardization)
```json
{
  "_id": ObjectId,
  "timestamp": ISODate,
  "source": String,  // "tradingview", "custom_provider", etc.
  "raw_data": Object,  // Original payload as received
  "processed": Boolean,
  "created_at": ISODate
}
```

### Collection: `standardized_signals`
Stores signals in the internal "Mathematricks" format
```json
{
  "_id": ObjectId,
  "signal_id": String,  // Unique identifier
  "strategy_id": String,
  "timestamp": ISODate,
  "instrument": String,  // "SPX", "EURUSD", "GC", etc.
  "direction": String,  // "LONG", "SHORT"
  "action": String,  // "ENTRY", "EXIT"
  "order_type": String,  // "MARKET", "LIMIT", "STOP"
  "price": Number,
  "quantity": Number,
  "stop_loss": Number,
  "take_profit": Number,
  "expiry": ISODate,
  "metadata": {
    "expected_alpha": Number,  // For 30% slippage rule
    "backtest_data": Object
  },
  "processed_by_cerebro": Boolean,
  "created_at": ISODate
}
```

### Collection: `trading_orders`
Orders generated by CerebroService after position sizing
```json
{
  "_id": ObjectId,
  "order_id": String,
  "signal_id": String,
  "strategy_id": String,
  "account": String,  // "IBKR_Main", "Binance_Futures"
  "timestamp": ISODate,
  "instrument": String,
  "direction": String,
  "action": String,
  "order_type": String,
  "price": Number,
  "quantity": Number,  // Position-sized quantity
  "stop_loss": Number,
  "take_profit": Number,
  "expiry": ISODate,
  "cerebro_decision": {
    "allocated_capital": Number,
    "margin_required": Number,
    "position_size_logic": String,
    "risk_metrics": Object
  },
  "status": String,  // "PENDING", "SUBMITTED", "FILLED", "REJECTED", "CANCELLED"
  "created_at": ISODate
}
```

### Collection: `execution_confirmations`
Fills, partial fills, and rejections from brokers
```json
{
  "_id": ObjectId,
  "order_id": String,
  "execution_id": String,  // Broker's execution ID
  "timestamp": ISODate,
  "account": String,
  "instrument": String,
  "side": String,  // "BUY", "SELL"
  "quantity": Number,
  "price": Number,
  "commission": Number,
  "status": String,  // "FILLED", "PARTIAL_FILL", "REJECTED"
  "broker_response": Object,
  "created_at": ISODate
}
```

### Collection: `account_state`
Real-time account data from brokers
```json
{
  "_id": ObjectId,
  "account": String,
  "timestamp": ISODate,
  "equity": Number,
  "cash_balance": Number,
  "margin_used": Number,
  "margin_available": Number,
  "unrealized_pnl": Number,
  "realized_pnl": Number,
  "open_positions": [
    {
      "instrument": String,
      "quantity": Number,
      "entry_price": Number,
      "current_price": Number,
      "unrealized_pnl": Number,
      "margin_required": Number
    }
  ],
  "open_orders": [
    {
      "order_id": String,
      "instrument": String,
      "side": String,
      "quantity": Number,
      "order_type": String,
      "price": Number
    }
  ],
  "created_at": ISODate
}
```

### Collection: `cerebro_decisions`
Log of Cerebro's position sizing decisions
```json
{
  "_id": ObjectId,
  "signal_id": String,
  "decision": String,  // "APPROVED", "REJECTED", "MODIFIED"
  "timestamp": ISODate,
  "reason": String,
  "original_quantity": Number,
  "final_quantity": Number,
  "risk_assessment": {
    "portfolio_margin_before": Number,
    "portfolio_margin_after": Number,
    "margin_utilization_pct": Number,
    "cvar_contribution": Number,
    "correlation_impact": Object
  },
  "created_at": ISODate
}
```

### Collection: `strategy_backtest_data`
Backtest data for each strategy (used for portfolio optimization)
```json
{
  "_id": ObjectId,
  "strategy_id": String,  // "SPX_1-D_Opt", "Forex", etc.
  "backtest_period": {
    "start_date": ISODate,
    "end_date": ISODate,
    "total_days": Number
  },
  "daily_returns": [Number],  // Array of daily returns (e.g., [0.001, -0.002, 0.003, ...])
  "mean_return_daily": Number,  // Average daily return
  "volatility_daily": Number,  // Daily standard deviation
  "sharpe_ratio": Number,  // Sharpe ratio (daily)
  "max_drawdown": Number,  // Maximum drawdown percentage
  "win_rate": Number,  // Percentage of winning days
  "margin_per_unit": Number,  // Margin required per contract/unit
  "metadata": {
    "instrument": String,
    "backtest_source": String,  // "portfolio_combiner", "manual", etc.
    "notes": String
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### Collection: `portfolio_allocations`
Portfolio allocation recommendations and active allocations
```json
{
  "_id": ObjectId,
  "allocation_id": String,  // Unique identifier
  "timestamp": ISODate,
  "status": String,  // "PENDING_APPROVAL", "ACTIVE", "ARCHIVED"
  "allocations": {
    // Key: strategy_id, Value: allocation percentage
    "SPX_1-D_Opt": 45.5,
    "Forex": 30.2,
    "Com1-Met": 24.3
  },
  "expected_metrics": {
    "expected_daily_return": Number,
    "expected_daily_volatility": Number,
    "expected_sharpe_daily": Number,
    "expected_sharpe_annual": Number,
    "total_allocation_pct": Number,  // Sum of all allocations (can be > 100%)
    "leverage_ratio": Number  // total_allocation_pct / 100
  },
  "optimization_run_id": String,  // Reference to portfolio_optimization_runs._id
  "approved_by": String,  // "auto" or portfolio manager username
  "approved_at": ISODate,
  "archived_at": ISODate,
  "notes": String,  // Manual edits, reasoning, etc.
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### Collection: `portfolio_optimization_runs`
Historical record of portfolio optimization runs
```json
{
  "_id": ObjectId,
  "run_id": String,  // Unique identifier
  "timestamp": ISODate,
  "strategies_used": [String],  // Array of strategy_ids included in optimization
  "correlation_matrix": [[Number]],  // 2D array of correlation coefficients
  "covariance_matrix": [[Number]],  // 2D array of covariance values
  "constraints": {
    "max_leverage": Number,  // e.g., 2.0 for 200%
    "max_single_strategy": Number,  // e.g., 0.5 for 50%
    "risk_free_rate": Number
  },
  "optimization_result": {
    "success": Boolean,
    "message": String,
    "converged": Boolean,
    "iterations": Number
  },
  "recommended_allocations": {
    // Same structure as portfolio_allocations.allocations
    "SPX_1-D_Opt": 45.5,
    "Forex": 30.2,
    "Com1-Met": 24.3
  },
  "portfolio_metrics": {
    "expected_daily_return": Number,
    "expected_daily_volatility": Number,
    "expected_sharpe_daily": Number,
    "expected_sharpe_annual": Number,
    "total_allocation_pct": Number,
    "leverage_ratio": Number
  },
  "execution_time_ms": Number,
  "created_at": ISODate
}
```

### Collection: `strategy_configurations`
Strategy operational settings and control panel
```json
{
  "_id": ObjectId,
  "strategy_id": String,  // Unique identifier (e.g., "SPX_1-D_Opt", "Forex")
  "strategy_name": String,  // Human-readable name (e.g., "SPX 1-Day Options")
  "status": String,  // ACTIVE | INACTIVE | TESTING
  "trading_mode": String,  // LIVE | PAPER
  "account": String,  // IBKR_Main | IBKR_Futures | Binance_Main
  "include_in_optimization": Boolean,  // Whether to include in portfolio optimization
  "risk_limits": {
    "max_position_size": Number,  // Maximum position size in dollars
    "max_daily_loss": Number  // Maximum daily loss in dollars
  },
  "developer_contact": String,  // Email or Slack handle of strategy developer
  "notes": String,  // Free-text notes about the strategy
  "last_backtest_sync": ISODate,  // When backtest data was last synced
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Purpose:** Central registry of all strategies with their operational settings. Controls which strategies are active, where they trade, and how they behave.

**Workflow:**
1. Developer uploads backtest CSV → runs ingestion tool → data in `strategy_backtest_data`
2. Portfolio manager creates entry in `strategy_configurations` via frontend
3. Sets: Status=ACTIVE, Account=IBKR_Main, Mode=PAPER, Include in optimization=Yes
4. Portfolio optimizer runs → only considers ACTIVE strategies with optimization flag
5. Signal arrives → system checks config → routes to correct account + mode

## Database: `mathematricks_signals` (Existing)
Used by signal_collector.py - DO NOT MODIFY

### Collection: `trading_signals`
See signal_collector.py:350-359 for integration point
