# Mock Broker Documentation

## Overview

The Mock Broker provides instant order fills for testing when markets are closed or during development. It eliminates the need to wait for market hours and allows rapid iteration on trading logic.

---

## Where Mock Equity is Set

The mock equity is configured in **two places**:

### 1. MockBroker Class Default (services/brokers/mock/mock_broker.py)

**Line 47:**
```python
self.initial_equity = config.get("initial_equity", 1000000.0)
```

This reads from the broker config. If not provided, defaults to $1M.

**Line 224-227 (get_account_balance method):**
```python
return {
    "account_id": account,
    "equity": self.initial_equity,
    "cash_balance": self.initial_equity * 0.5,  # 50% cash
    ...
}
```

### 2. MongoDB Account Document

**In trading_accounts collection:**
```javascript
{
  "_id": "Mock_Paper",
  "authentication_details": {
    "auth_type": "MOCK",
    "initial_equity": 1000000  // ← Set here
  }
}
```

---

## How to Change Mock Equity

### Option 1: Change in MongoDB (Recommended)
```bash
mongosh mathematricks_trading --eval "
db.trading_accounts.updateOne(
  {_id: 'Mock_Paper'},
  {\$set: {'authentication_details.initial_equity': 250000}}
)
"
```

Then restart execution service - it will read the new value when creating the broker.

### Option 2: Edit MockBroker Code
Change line 47 in `services/brokers/mock/mock_broker.py`:
```python
self.initial_equity = config.get("initial_equity", 250000.0)  # Change to desired amount
```

---

## How to Test Mock Broker

### Step 1: Start Execution Service with Mock Mode Flag
```bash
cd services/execution_service
python3 main.py --use-mock-broker
```

**Expected logs:**
```
|WARNING|================================================================================|...
|WARNING|🧪 MOCK MODE ENABLED: All orders will be routed to Mock_Paper broker|...
|WARNING|================================================================================|...
|INFO|Initializing broker pool from AccountDataService...|...
|INFO|Found 2 active accounts from AccountDataService|...
|INFO|✅ Created Mock broker for account: Mock_Paper|...
|INFO|✅ Created IBKR broker for account: IBKR_PAPER|...
|INFO|Broker pool initialized with 2 broker(s)|...
|INFO|Starting Execution Service with Broker Pool (Multi-Broker Support)|...
|INFO|Connecting to 2 broker(s)...|...
|INFO|✅ Connected to Mock for Mock_Paper|...
```

**Note:** The `--use-mock-broker` flag overrides ALL order routing to Mock_Paper, regardless of which account is configured in strategies.

### Step 2: Start Cerebro Service (in another terminal, normal mode)
```bash
cd services/cerebro_service
python3 main.py
```

### Step 3: Send Test Signal
```bash
cd services/signal_ingestion
python3 send_test_signal.py @sample_signals/simple_signal_equity_1.json
```

### Step 4: Watch the Logs

**Expected flow:**

**Cerebro logs:**
```
|INFO|Routing signal for strategy SPX_1-D_Opt to account: IBKR_PAPER|...
|INFO|ENTRY signal detected|...
|INFO|✅ Order published to Pub/Sub topic|...
```

**Execution logs (with Mock Mode Override):**
```
|INFO|🧪 MOCK MODE: Overriding account IBKR_PAPER → Mock_Paper|...
|INFO|📋 Submitting order test_SPX_1-D_Opt_AAPL_xxx to Mock (account: Mock_Paper)|...
|INFO|Mock Broker: Order MOCK_1731520000_5678 FILLED instantly | Instrument=AAPL | Qty=75 | Price=$150.00|...
|INFO|✅ Order test_SPX_1-D_Opt_AAPL_xxx submitted - Broker Order ID: MOCK_xxx, Status: Filled|...
```

10 seconds later, EXIT signal:
```
|INFO|🔴 EXIT signal detected - querying signal_store for entry quantity|...
|INFO|✅ Found entry signal: test_SPX_1-D_Opt_AAPL_xxx|...
|INFO|✅ Using exact entry quantity: 75|...
|INFO|Mock Broker: Order MOCK_xxx FILLED instantly | Instrument=AAPL | Qty=75 | Price=$152.00|...
```

**Success indicators:**
- ✅ Entry fills instantly (Mock broker)
- ✅ EXIT finds filled entry (retry logic not needed since instant fill)
- ✅ EXIT uses exact quantity (75 shares in, 75 shares out)
- ✅ No residual positions

---

## Testing the Retry Logic

To actually test the retry logic with Mock broker, you'd need to **slow down the mock fills** or **delay execution updates**. But since Mock fills instantly, the retry logic won't trigger.

**The retry logic will be tested when you switch back to IBKR:**
```bash
mongosh mathematricks_trading --eval "
db.strategies.updateOne(
  {strategy_id: 'SPX_1-D_Opt'},
  {\$set: {accounts: ['IBKR_PAPER']}}
)
"
```

Then during market hours, the EXIT signal will arrive while ENTRY is pending, triggering the retry logic!

---

## Switching Between Mock and IBKR

### Use Mock Broker (for testing when markets closed)

**Simply add the `--use-mock-broker` flag when starting execution service:**

```bash
cd services/execution_service
python3 main.py --use-mock-broker
```

This overrides ALL order routing to Mock_Paper, regardless of strategy configuration.

### Use IBKR (for production or market hours testing)

**Start execution service WITHOUT the flag:**

```bash
cd services/execution_service
python3 main.py
```

This uses normal routing based on strategy account configuration.

**Advantages of Flag Approach:**
- ✅ No database changes required
- ✅ No risk of forgetting to change strategies back
- ✅ Works for ALL strategies simultaneously
- ✅ Clear visibility (flag + warning logs)
- ✅ Safe (requires explicit flag to enable mock mode)

---

## Features

- ✅ **Instant Fills**: All orders fill immediately at submitted price
- ✅ **All Instruments**: Supports stocks, forex, options, futures, commodities
- ✅ **All Order Types**: MARKET, LIMIT orders supported
- ✅ **No Dependencies**: No external connections needed
- ✅ **Configurable Equity**: Set initial equity via MongoDB or config
- ✅ **24/7 Testing**: Test anytime without waiting for market hours

---

## Mock Account Structure

```json
{
  "_id": "Mock_Paper",
  "account_id": "Mock_Paper",
  "account_name": "Mock Paper Trading",
  "broker": "Mock",
  "account_number": "MOCK001",
  "account_type": "Paper",
  "authentication_details": {
    "auth_type": "MOCK",
    "initial_equity": 1000000
  },
  "balances": {
    "equity": 1000000.0,
    "cash": 500000.0,
    "margin_used": 0.0,
    "margin_available": 500000.0,
    "buying_power": 2000000.0
  },
  "open_positions": [],
  "status": "ACTIVE"
}
```

---

## Implementation Details

### MockBroker Class (services/brokers/mock/mock_broker.py)

**Key Methods:**
- `connect()`: Always returns True instantly
- `disconnect()`: Always returns True
- `is_connected()`: Returns connection state
- `place_order()`: Returns instant fill with mock order ID
- `cancel_order()`: Always succeeds
- `get_account_balance()`: Returns mock account data
- `get_open_positions()`: Returns empty list (no position tracking in MVP)

### Order ID Format
Mock orders generate IDs in the format:
```
MOCK_{timestamp}_{random_4_digits}
```

Example: `MOCK_1731520000_5678`

### Fill Price Logic
- **MARKET orders**: Uses `order.get('price', 100.0)` or defaults to $100
- **LIMIT orders**: Uses `order.get('limit_price', 100.0)`

---

## Troubleshooting

### Mock broker not initializing
**Check:** Is Mock_Paper account ACTIVE in MongoDB?
```bash
mongosh mathematricks_trading --eval "db.trading_accounts.find({_id: 'Mock_Paper'})"
```

### Orders going to IBKR instead of Mock
**Check:** Strategy routing
```bash
mongosh mathematricks_trading --eval "db.strategies.find({strategy_id: 'SPX_1-D_Opt'}, {accounts: 1})"
```

Should show: `"accounts": ["Mock_Paper"]`

### Execution service not finding Mock account
**Check:** AccountDataService is running
```bash
curl http://localhost:5001/api/v1/accounts
```

Should include Mock_Paper in response.

---

## Future Enhancements (Phase 2)

Potential improvements for more realistic testing:

1. **Position Tracking**: Track open positions in-memory
2. **Price Variation**: Use random prices within realistic ranges
3. **Partial Fills**: Simulate partial fills for large orders
4. **Configurable Delays**: Add artificial delay to simulate network latency
5. **Failure Simulation**: Random order rejections for error handling tests
6. **Slippage Simulation**: Apply slippage to fills based on order size
7. **Market Hours**: Optionally enforce market hours even for mock
