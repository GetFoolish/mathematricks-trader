# signal_store Schema v2 (Proposed)

## Design Principles
1. **No duplication** - each piece of data lives in ONE place
2. **Clear ownership** - top-level fields are cerebro's final decision, raw data is nested
3. **Readable math** - `decision.math` shows exactly how cerebro calculated quantities
4. **Clean lifecycle** - clear progression from signal → decision → execution → closed

---

## Proposed Schema

```javascript
{
  // === IDENTITY (immutable after creation) ===
  _id: ObjectId,                    // MongoDB ID = mathematricks_signal_id
  signal_id: "sig_com1_met_009",    // From raw signal
  strategy_id: "Com1-Met",          // From raw signal
  environment: "staging",           // staging | production

  // === RAW SIGNAL (immutable - audit trail) ===
  raw: {
    _id: ObjectId,                  // Reference to trading_signals_raw
    received_at: ISODate,           // When signal was received
    sent_epoch: 1767888629,         // signal_sent_EPOCH from source
    entry_name: "$ENTRY_5",         // For linking entry/exit
    account_equity: 10000,          // Backtest account equity
    legs: [                         // Original signal legs (unchanged)
      {
        instrument: "HG",
        instrument_type: "FUTURE",
        action: "BUY",
        direction: "LONG",
        quantity: 3,                // <-- RAW quantity (what backtest sent)
        order_type: "MARKET",
        price: 4.2,
        stop_loss: 4.15,
        take_profit: 4.3
      }
    ]
  },

  // === CEREBRO DECISION (the authoritative trading decision) ===
  decision: {
    status: "APPROVED",             // APPROVED | REJECTED | RESIZE
    reason: "Fund allocation scaled position",
    timestamp: ISODate,

    // Final quantities to trade (THIS IS WHAT MATTERS)
    legs: [
      {
        instrument: "HG",
        instrument_type: "FUTURE",
        action: "BUY",
        direction: "LONG",
        quantity: 167,              // <-- FINAL quantity after scaling
        order_type: "MARKET",
        price: 4.2,                 // Price used for margin calc
        margin_required: 70.14
      }
    ],

    // The math cerebro used to reach this decision
    math: {
      signal_type: "ENTRY",
      scaling_ratio: 55.55,         // Live capital / backtest capital

      capital: {
        backtest_equity: 10000,     // From signal
        fund_allocated: 555500,     // Total allocated to this strategy
        fund_deployed: 0,           // Already in positions
        fund_available: 555500      // Available for this trade
      },

      margin: {
        method: "Futures Mock Margin (10%)",
        per_contract: 70.14,
        total_required: 11713.38,   // 167 * 70.14
        as_percent_of_available: 2.1
      },

      quantity_calc: {
        raw_quantity: 3,
        scaled_raw: 166.65,         // 3 * 55.55
        rounded: 167,               // Final after precision rules
        precision: 0                // Decimal places for this instrument
      }
    },

    // For EXIT signals only
    entry_ref: {
      signal_id: "sig_com1_met_008",
      signal_store_id: ObjectId
    }
  },

  // === EXECUTION (filled by execution service) ===
  execution: {
    status: "FILLED",               // PENDING | PARTIAL | FILLED | FAILED

    orders: [                       // One or more orders per signal (can be split across brokers/funds)
      {
        order_id: "sig_com1_met_009_mock-fund-1_VANTAGE_MOCK_ORD",
        broker_name: "MockBroker",  // NEW: Name of broker used (MockBroker, IBKRBroker, etc.)
        broker_order_id: "MOCK_1767888631_6835",
        fund_id: "mock-fund-1",
        account_id: "VANTAGE_MOCK",
        quantity_requested: 84,
        quantity_filled: 84,
        avg_fill_price: 4.2,
        filled_at: ISODate,
        fills: [
          {
            timestamp: ISODate,
            quantity: 84,
            price: 4.2,
            exchange: "MOCK",
            execution_id: "929f90a8..."
          }
        ]
      }
    ],

    // Aggregate across all orders
    total_quantity_filled: 84,
    total_cost_basis: 352.8,
    weighted_avg_price: 4.2
  },

  // === POSITION LIFECYCLE ===
  position: {
    status: "CLOSED",               // null | OPEN | CLOSED
    opened_at: ISODate,
    closed_at: ISODate,
    exit_signals: [ObjectId],       // References to EXIT signal_store docs

    // PnL (only populated when CLOSED)
    pnl: {
      gross: 2.94,
      net: 2.94,
      percent: 0.83,
      commission: 0,
      holding_seconds: 12
    }
  },

  // === TIMESTAMPS ===
  created_at: ISODate,              // When signal_store doc created
  updated_at: ISODate               // Last modification
}
```

---

## Key Changes from v1

| Aspect | v1 (Current) | v2 (Proposed) |
|--------|--------------|---------------|
| Raw quantity | Top-level `quantity: 3` | `raw.legs[].quantity: 3` |
| Final quantity | `cerebro_decision.final_quantity: 167` | `decision.legs[].quantity: 167` |
| Scaling math | Buried in `risk_assessment.metadata` | Clean `decision.math` object |
| Full raw signal | `signal_data` (entire doc with duplication) | `raw` (only unique fields) |
| PnL location | `pnl_realized` + `execution.pnl` | Single `position.pnl` |
| Position status | Top-level `position_status` | `position.status` |

---

## Migration Notes

### Fields Removed (duplicates)
- `instrument`, `direction`, `action`, `price`, `quantity` at top level
- `cerebro_decision.signal_id` (already at top level)
- `cerebro_decision.strategy_id` (already at top level)
- `cerebro_decision.original_quantity` (now in `decision.math.quantity_calc.raw_quantity`)
- `signal_data._id`, `signal_data.created_at` (redundant)

### Fields Reorganized
- `signal_data` → `raw` (slimmed down)
- `cerebro_decision` → `decision` (cleaner structure)
- `execution` → `execution` (with `orders` array for multi-fund)
- `position_status`, `exit_signals`, `pnl_realized`, `closed_at` → `position` object

---

## Example: ENTRY Signal Document

```javascript
{
  _id: ObjectId("695fd6f5a9f63115a685900b"),
  signal_id: "sig_com1_met_009",
  strategy_id: "Com1-Met",
  environment: "staging",

  raw: {
    _id: ObjectId("695fd6f5e39723ccc17b53d4"),
    received_at: ISODate("2026-01-08T16:10:29.659Z"),
    sent_epoch: 1767888629,
    entry_name: "$ENTRY_5",
    account_equity: 10000,
    legs: [{
      instrument: "HG",
      instrument_type: "FUTURE",
      action: "BUY",
      direction: "LONG",
      quantity: 3,
      order_type: "MARKET",
      price: 4.2,
      stop_loss: 4.15,
      take_profit: 4.3
    }]
  },

  decision: {
    status: "APPROVED",
    reason: "Fund allocation scaled position",
    timestamp: ISODate("2026-01-08T16:10:30.897Z"),
    legs: [{
      instrument: "HG",
      instrument_type: "FUTURE",
      action: "BUY",
      direction: "LONG",
      quantity: 167,
      order_type: "MARKET",
      price: 4.2,
      margin_required: 70.14
    }],
    math: {
      signal_type: "ENTRY",
      scaling_ratio: 55.55,
      capital: {
        backtest_equity: 10000,
        fund_allocated: 555500,
        fund_deployed: 0,
        fund_available: 555500
      },
      margin: {
        method: "Futures Mock Margin (10%)",
        per_contract: 70.14,
        total_required: 11713.38,
        as_percent_of_available: 2.1
      },
      quantity_calc: {
        raw_quantity: 3,
        scaled_raw: 166.65,
        rounded: 167,
        precision: 0
      }
    }
  },

  execution: {
    status: "FILLED",
    orders: [{
      order_id: "sig_com1_met_009_mock-fund-1_VANTAGE_MOCK_ORD",
      broker_name: "MockBroker",
      broker_order_id: "MOCK_1767888631_6835",
      fund_id: "mock-fund-1",
      account_id: "VANTAGE_MOCK",
      quantity_requested: 84,
      quantity_filled: 84,
      avg_fill_price: 4.2,
      filled_at: ISODate("2026-01-08T16:10:31.044Z"),
      fills: [{
        timestamp: "2026-01-08T16:10:31.041939Z",
        quantity: 84,
        price: 4.2,
        exchange: "MOCK",
        execution_id: "929f90a8-a69c-497e-a7c1-c515a05c6ca9"
      }]
    }],
    total_quantity_filled: 84,
    total_cost_basis: 352.8,
    weighted_avg_price: 4.2
  },

  position: {
    status: "CLOSED",
    opened_at: ISODate("2026-01-08T16:10:31.044Z"),
    closed_at: ISODate("2026-01-08T16:10:41.599Z"),
    exit_signals: [ObjectId("695fd700a9f63115a685900c")],
    pnl: {
      gross: 2.94,
      net: 2.94,
      percent: 0.83,
      commission: 0,
      holding_seconds: 10
    }
  },

  created_at: ISODate("2026-01-08T16:10:29.661Z"),
  updated_at: ISODate("2026-01-08T16:10:41.599Z")
}
```

---

## Example: EXIT Signal Document

```javascript
{
  _id: ObjectId("695fd700a9f63115a685900c"),
  signal_id: "sig_com1_met_010",
  strategy_id: "Com1-Met",
  environment: "staging",

  raw: {
    _id: ObjectId("695fd700e39723ccc17b53d5"),
    received_at: ISODate("2026-01-08T16:10:40.123Z"),
    sent_epoch: 1767888640,
    exit_name: "$EXIT_5",
    entry_name: "$ENTRY_5",
    legs: [{
      instrument: "HG",
      instrument_type: "FUTURE",
      action: "SELL",
      direction: "LONG",
      quantity: 3,
      order_type: "MARKET",
      price: 4.21
    }]
  },

  decision: {
    status: "APPROVED",
    reason: "Closing position from entry $ENTRY_5",
    timestamp: ISODate("2026-01-08T16:10:40.500Z"),
    legs: [{
      instrument: "HG",
      instrument_type: "FUTURE",
      action: "SELL",
      direction: "LONG",
      quantity: 84,  // Matches open position, not raw signal
      order_type: "MARKET",
      price: 4.21
    }],
    math: {
      signal_type: "EXIT",
      entry_ref: {
        signal_id: "sig_com1_met_009",
        signal_store_id: ObjectId("695fd6f5a9f63115a685900b")
      },
      quantity_calc: {
        raw_quantity: 3,
        open_position_quantity: 84,
        quantity_to_close: 84
      }
    }
  },

  execution: {
    status: "FILLED",
    orders: [{
      order_id: "sig_com1_met_010_mock-fund-1_VANTAGE_MOCK_ORD",
      broker_order_id: "MOCK_1767888641_1234",
      fund_id: "mock-fund-1",
      account_id: "VANTAGE_MOCK",
      quantity_requested: 84,
      quantity_filled: 84,
      avg_fill_price: 4.21,
      filled_at: ISODate("2026-01-08T16:10:41.044Z"),
      fills: [...]
    }],
    total_quantity_filled: 84,
    total_proceeds: 353.64,
    weighted_avg_price: 4.21
  },

  position: null,  // EXIT signals don't track position lifecycle

  created_at: ISODate("2026-01-08T16:10:40.125Z"),
  updated_at: ISODate("2026-01-08T16:10:41.599Z")
}
```

---

## Implementation Order

1. **Update mongodb_watcher.py** - Create documents with new `raw` structure
2. **Update cerebro_main.py** - Write `decision` with `math` breakdown
3. **Update execution_main.py** - Write to `execution.orders[]` and `position`
4. **Update frontend API** - Read from new field locations
5. **Migration script** - Convert existing documents (optional)
