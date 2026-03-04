# Cerebro Service

## Overview

The Cerebro Service is the intelligent core of the Mathematricks trading system. It processes incoming signals, makes portfolio management decisions, validates risk constraints, and generates execution orders.

**Main File:** `services/cerebro_service/cerebro_main.py`  
**Port:** 8001  
**Framework:** FastAPI

## Purpose

- **Portfolio Construction** - Intelligent position sizing using portfolio optimization algorithms
- **Risk Management** - Hard margin limits and position validation
- **Signal Classification** - Detect ENTRY vs EXIT signal types
- **Fund Allocation** - Distribute capital across multiple accounts
- **Margin Validation** - Ensure sufficient margin before order creation
- **Decision Recording** - Document all decisions with detailed math in `signal_store`

## Architecture

### How It Works

```
Signal Ingestion → Cerebro Service → trading_orders → Execution Service
                    ↓
              signal_store.decision
              (Decision + Math)
```

### Key Components

1. **Portfolio Constructor**
   - `MaxCAGRConstructor` - Maximize CAGR/Sharpe ratio
   - `MaxHybridConstructor` - Balance CAGR, Sharpe, and diversification
   - Context-aware position sizing

2. **Position Manager**
   - Tracks open positions per account
   - Validates position limits
   - Manages position lifecycle

3. **Margin Calculator**
   - IBKR margin rules for stocks, options, futures, forex
   - Mock broker for testing
   - Integration with broker adapters

4. **Fund Allocation Logic**
   - Distributes capital across accounts
   - Respects fund architecture
   - Handles multi-account routing

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | Required |
| `ACCOUNT_DATA_SERVICE_URL` | Account data service endpoint | `http://localhost:8082` |
| `EXECUTION_SERVICE_URL` | Execution service endpoint | `http://localhost:8083` |
| `USE_MOCK_BROKER` | Use mock broker for margin calc | `false` |
| `DEFAULT_ACCOUNT_ID` | Default account for orders | `Mock_Paper` |

### MVP Configuration

```python
MVP_CONFIG = {
    "max_margin_utilization_pct": 40,  # Hard limit - never exceed 40%
    "default_position_size_pct": 5,    # Fallback if no allocation found
    "slippage_alpha_threshold": 0.30   # Drop if >30% alpha lost
}
```

## MongoDB Collections

### Input: `signal_store`
Reads signal legs without decisions:
```javascript
{
  signal_id: "SIGNAL_123",
  legs: [
    {
      leg_id: "SIGNAL_123__entry_0",
      decision: null,  // Cerebro fills this
      raw: { ... }
    }
  ]
}
```

### Output: `signal_store` (Updated)
Writes decision to specific leg:
```javascript
{
  legs: [
    {
      leg_id: "SIGNAL_123__entry_0",
      decision: {
        status: "APPROVED" | "REJECTED" | "RESIZE",
        reason: "Position sizing approved",
        timestamp: ISODate,
        legs: [
          {
            instrument: "AAPL",
            quantity: 100,
            order_type: "MARKET",
            margin_required: 5000.0
          }
        ],
        math: `
--- 1. SIGNAL INPUT ---
Instrument: AAPL (STOCK)
Raw Quantity: 200

--- 2. SIGNAL TYPE ---
Type: ENTRY

--- 3. FUND ALLOCATION ---
Allocated Capital: $100,000
Available Capital: $95,000

--- 4. SCALING CALCULATION ---
Signal Account Equity: $500,000
Scaling Ratio: 0.19
Quantity: 200 x 0.19 = 38 -> 100

--- 5. MARGIN VALIDATION ---
Required: $15,000
Check: OK ($15,000 vs $95,000)

--- 6. BROKER ACCOUNT STATE ---
Equity: $100,000
Margin Available: $95,000

--- 7. FINAL DECISION ---
Decision: APPROVED
Final Qty: 100
        `
      },
      processing_timestamps: {
        cerebro_processed: ISODate
      }
    }
  ]
}
```

### Output: `trading_orders`
Creates orders for execution:
```javascript
{
  order_id: "ORDER_abc123",
  signal_id: "SIGNAL_123",
  mathematricks_signal_id: ObjectId("..."),
  strategy_id: "MaxCAGR_v2",
  account_id: "IBKR_Paper",
  
  instrument: "AAPL",
  side: "BUY",
  quantity: 100,
  order_type: "MARKET",
  price: 150.0,
  
  status: "PENDING_EXECUTION",
  cerebro_decision: { ... },
  
  created_at: ISODate
}
```

### References:
- `strategies` - Strategy configurations
- `funds` - Fund architecture and allocations
- `trading_accounts` - Account balances and positions
- `portfolio_tests` - Portfolio allocation results

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "cerebro_service",
  "mongodb": "connected"
}
```

### `GET /status`
Detailed service status.

**Response:**
```json
{
  "status": "running",
  "mongodb_connected": true,
  "position_manager_ready": true,
  "change_stream_active": true
}
```

### `POST /api/v1/process-signal`
Process a single signal (called by Signal Ingestion).

**Request:**
```json
{
  "signal_id": "SIGNAL_123",
  "mathematricks_signal_id": "507f1f77bcf86cd799439011",
  "raw_signal_mongodb_id": "507f1f77bcf86cd799439012",
  "strategy_name": "MaxCAGR_v2",
  "signal_type": "ENTRY",
  "signal": [
    {
      "instrument": "AAPL",
      "action": "BUY",
      "quantity": 200,
      "price": 150.0
    }
  ],
  "account_equity": 500000.0,
  "environment": "production"
}
```

**Response:**
```json
{
  "status": "success",
  "decision": "APPROVED",
  "signal_id": "SIGNAL_123",
  "orders_created": 1,
  "final_quantity": 100,
  "message": "Signal processed successfully"
}
```

## Key Functions

### `process_signal(signal_data, received_time, is_catchup, mongodb_object_id)`
Main signal processing function.

**Flow:**
1. Classify signal type (ENTRY/EXIT)
2. Get fund allocations for strategy
3. Get account state from account-data-service
4. Build portfolio context
5. Call portfolio constructor for position sizing
6. Validate margin requirements
7. Create decision document
8. Update signal_store with decision
9. Create trading orders
10. Return result

### `build_decision_v2(status, reason, signal, decision_obj, legs)`
Builds v2 decision document with detailed math breakdown.

**Sections:**
1. Signal Input
2. Signal Type Detection
3. Fund Allocation
4. Scaling Calculation
5. Margin Validation
6. Broker Account State
7. Final Decision

### `allocate_quantity_across_accounts(total_quantity, account_allocations, target_capital, instrument_type)`
Distributes quantity across accounts ensuring sum equals total.

**Example:**
- Input: 231 shares, 2 accounts, equal allocation
- Output: `[115, 116]` (not `[116, 116]`)

### `update_signal_store_with_decision(signal_store_id, decision_doc, raw_signal_id)`
Updates signal_store with Cerebro decision for specific leg.

## Signal Processing Flow

### ENTRY Signal Flow
1. **Receive Signal** from Signal Ingestion
2. **Get Fund Allocations** for strategy
3. **Fetch Account State** from Account Data Service
4. **Build Portfolio Context:**
   - Current positions
   - Available capital
   - Deployed capital
5. **Portfolio Constructor Decision:**
   - Scale quantity based on allocated vs signal account equity
   - Apply portfolio optimization algorithm
6. **Margin Validation:**
   - Calculate margin required
   - Check against available margin
   - Reject if exceeds limits
7. **Multi-Account Distribution:**
   - Split quantity across accounts
   - Ensure integer quantities sum correctly
8. **Create Orders:**
   - One order per account
   - Store in `trading_orders`
9. **Update signal_store:**
   - Write decision to leg
   - Add processing timestamp

### EXIT Signal Flow
1. **Receive EXIT Signal**
2. **Find Parent ENTRY Signal** in signal_store
3. **Get Actual Filled Quantity** from ENTRY execution
4. **Create EXIT Order** for filled quantity (not raw signal quantity)
5. **Update signal_store** with EXIT leg decision

## Portfolio Constructors

### MaxCAGRConstructor
Maximizes CAGR/Sharpe ratio weighted metric.

**Parameters:**
- `cagr_weight`: Weight for CAGR (0-1)
- `sharpe_weight`: Weight for Sharpe ratio (0-1)

**Algorithm:**
```
score = (cagr_weight * CAGR) + (sharpe_weight * Sharpe)
position_size = allocated_capital / max_positions
```

### MaxHybridConstructor
Balances multiple objectives.

**Parameters:**
- `cagr_weight`: CAGR importance
- `sharpe_weight`: Sharpe importance
- `diversification_weight`: Diversification importance

## Margin Calculation

### Stock Margin (Reg T)
- **Long positions:** 50% of notional value
- **Short positions:** 150% of notional value

### Options Margin
- **Long options:** Premium only (no margin)
- **Short options:** Complex calculation based on strike, underlying price
- **Spreads:** Net margin across legs

### Futures Margin
- **Initial margin:** Per contract (exchange-defined)
- **Maintenance margin:** Typically 75% of initial

### Forex Margin
- **Standard:** 1-5% of notional (depending on pair)

## Example Usage

### Processing a Signal Manually

```python
# Build signal data
signal_data = {
    'signal_id': 'TEST_001',
    'strategy_name': 'MaxCAGR_v2',
    'signal_type': 'ENTRY',
    'signal': [
        {
            'instrument': 'AAPL',
            'action': 'BUY',
            'quantity': 100,
            'price': 150.0,
            'order_type': 'MARKET'
        }
    ],
    'account_equity': 100000.0,
    'environment': 'production'
}

# Process signal
from datetime import datetime
result = process_signal(
    signal_data=signal_data,
    received_time=datetime.utcnow(),
    is_catchup=False,
    mongodb_object_id=None
)

print(f"Decision: {result['decision']}")
print(f"Orders Created: {result['orders_created']}")
```

### Querying Decisions

```python
# Find all approved decisions
decisions = signal_store_collection.find({
    'legs.decision.status': 'APPROVED'
})

for signal in decisions:
    for leg in signal['legs']:
        if leg.get('decision', {}).get('status') == 'APPROVED':
            print(leg['decision']['math'])
```

## Troubleshooting

### Problem: All signals rejected with "Insufficient margin"
**Cause:** Account data service returning stale balances
**Solution:**
- Call `/api/v1/sync-account-balance` endpoint before processing
- Check account-data-service is running and polling brokers
- Verify `ACCOUNT_DATA_SERVICE_URL` is correct

### Problem: EXIT signals using wrong quantity
**Cause:** Not reading actual filled quantity from ENTRY execution
**Solution:**
- Cerebro looks up ENTRY leg's `execution.filled_quantity`
- Falls back to `decision.quantity` if execution not complete
- Check that execution service is updating signal_store

### Problem: Quantity distribution doesn't sum correctly
**Symptoms:** `[116, 116]` instead of `[115, 116]`
**Solution:**
- `allocate_quantity_across_accounts()` uses floor division
- Distributes remainder one-by-one to accounts with higher capital

### Problem: Decision math shows NaN or Inf
**Cause:** Division by zero or invalid account data
**Debug:**
- Check `account_equity` is not zero
- Verify `allocated_capital` is positive
- Inspect margin calculation inputs

### Problem: Signals stuck in PENDING
**Cause:** Execution service not picking up orders
**Solution:**
- Check `trading_orders` collection has status="PENDING_EXECUTION"
- Verify execution service Change Stream is active
- Check execution service logs for errors

## Performance Notes

- **MongoDB Change Streams** provide real-time signal processing
- **Position Manager** caches positions in memory for fast lookups
- **Margin Calculation** may query broker for real-time margin (use mock for testing)
- **Multi-threading** disabled to avoid race conditions

## Dependencies

- `fastapi` - Web framework
- `pymongo` - MongoDB driver
- `requests` - HTTP client for service calls
- `numpy`, `pandas` - Portfolio calculations
- Custom modules:
  - `portfolio_constructor` - Position sizing algorithms
  - `position_manager` - Position tracking
  - `margin_calculation` - Margin validators
  - `fund_allocation_logic` - Capital distribution

## Related Services

- **Signal Ingestion** - Sends signals to Cerebro
- **Execution Service** - Executes orders created by Cerebro
- **Account Data Service** - Provides account balances and positions
- **Portfolio Builder** - Manages strategy configurations and allocations

## Change Stream Processing

Cerebro watches `signal_store` for new legs without decisions:

```python
pipeline = [
    {
        '$match': {
            'operationType': {'$in': ['insert', 'update']},
            # Match legs without decision
            '$or': [
                {'updateDescription.updatedFields.legs': {'$exists': True}},
                {'fullDocument.legs': {'$exists': True}}
            ]
        }
    }
]
```

On each event:
1. Extract signal data
2. Find leg without decision
3. Process signal
4. Update leg with decision
