# Mock Broker Documentation

The Mock Broker provides instant order fills for testing without connecting to real markets. It's ideal for unit tests, integration tests, and rapid development.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Mock Pricing](#mock-pricing)
- [MongoDB Integration](#mongodb-integration)
- [Use Cases](#use-cases)
- [Testing Modes](#testing-modes)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)

## Overview

The Mock Broker simulates a real broker without making actual trades or connecting to markets. It provides:

- ✅ Instant order fills (no market delays)
- ✅ Support for all instrument types (stocks, forex, options, futures, crypto)
- ✅ MongoDB integration for position tracking
- ✅ Realistic account balance management
- ✅ Compatible with 4-mode system (mock_mock, mock_live)

**Implementation:** [services/brokers/mock/mock_broker.py](../../services/brokers/mock/mock_broker.py)

## Features

### Instant Fills

All orders are filled **instantly** with zero latency:

```python
# Order placed at 12:00:00.000
result = broker.place_order(order)
# Order filled at 12:00:00.001 (instant)

assert result['status'] == 'Filled'
assert result['filled'] == order['quantity']
assert result['remaining'] == 0
```

### All Instrument Types

Supports the same instruments as real brokers:

| Type | Examples | Precision |
|------|----------|-----------|
| **STOCK** | AAPL, TSLA, GOOGL | 0 decimals (integers) |
| **ETF** | SPY, QQQ, IWM | 0 decimals (integers) |
| **FOREX** | EURUSD, GBPJPY | 0 decimals (whole units) |
| **OPTION** | AAPL calls/puts | 0 decimals (contracts) |
| **FUTURE** | CL, GC, ES | 0 decimals (contracts) |
| **CRYPTO** | BTC, ETH, SOL | 8 decimals |
| **COMMODITY** | GOLD, SILVER | 0 decimals |

### MongoDB Single Source of Truth

Mock broker uses MongoDB as the **single source of truth** for all account data:

- ✅ Account balances read from database
- ✅ Positions tracked in database
- ✅ No in-memory caching
- ✅ Consistent with `clear_test_data.py` resets

This ensures that test data resets work correctly and account state is always accurate.

## How It Works

### Order Execution Flow

```
1. ExecutionService sends order → Mock Broker
2. Mock Broker validates order
3. Mock Broker determines fill price:
   - LIMIT orders: Use limit_price
   - MARKET orders: Use price field (from signal or BrokerModeAdapter)
4. Order filled instantly
5. Fill confirmation returned
6. Positions/balances updated in MongoDB
```

### Pricing Logic

Mock broker has **no fallback pricing** - it requires a price:

#### mock_mock Mode
Signal must include `price` field:
```python
order = {
    'instrument': 'AAPL',
    'direction': 'LONG',
    'quantity': 100,
    'order_type': 'MARKET',
    'price': 150.00  # Required!
}
```

#### mock_live Mode
BrokerModeAdapter enriches with live price from real broker:
```python
# Signal doesn't need price
signal = {
    'instrument': 'AAPL',
    'direction': 'LONG',
    'quantity': 100,
    'order_type': 'MARKET'
}

# BrokerModeAdapter fetches live price from IBKR
enriched_order = {
    **signal,
    'price': 152.35,  # Live price from IBKR
    '_price_source': 'real_broker'
}

# Mock broker uses live price
```

### Connection Management

Mock broker simulates connection without network calls:

```python
broker.connect()     # Always succeeds instantly
broker.is_connected()  # Returns True
broker.disconnect()  # Instant cleanup
```

On connection, it ensures the account exists in MongoDB with proper schema.

## Configuration

### Basic Configuration

```python
config = {
    "broker": "Mock",
    "account_id": "Mock_Paper",
    "initial_equity": 100000.0  # Used for initial account creation only
}

from services.brokers.factory import BrokerFactory
broker = BrokerFactory.create_broker(config)
```

### MongoDB Account Document

The Mock broker expects this schema in `trading_accounts` collection:

```json
{
  "account_id": "Mock_Paper",
  "account_name": "Mock Paper Trading",
  "broker": "Mock",
  "account_number": "MOCK_Mock_Paper",
  "account_type": "mock",
  "data_source": "mock",
  "mode": "mock_mock",
  "authentication_details": {
    "auth_type": "MOCK",
    "initial_equity": 100000.0
  },
  "balances": {
    "equity": 100000.0,
    "cash": 50000.0,
    "cash_balance": 50000.0,
    "margin_used": 0.0,
    "margin_available": 50000.0,
    "buying_power": 200000.0,
    "unrealized_pnl": 0.0,
    "realized_pnl": 0.0,
    "last_updated": "2025-01-07T12:00:00Z"
  },
  "open_positions": [],
  "status": "ACTIVE",
  "created_at": "2025-01-07T12:00:00Z",
  "updated_at": "2025-01-07T12:00:00Z"
}
```

### Read-Only Mode

When used as a secondary broker in hybrid setups (e.g., BrokerModeAdapter), set `read_only: true`:

```python
config = {
    "broker": "Mock",
    "account_id": "IBKR_Paper",
    "read_only": True  # Prevents MongoDB config overwrites
}
```

This prevents the Mock broker from overwriting the `broker` and `mode` fields if the account is actually an IBKR account temporarily using Mock for orders.

## Usage Examples

### Basic Order Placement

```python
from services.brokers.mock import MockBroker

# Initialize
broker = MockBroker({
    "broker": "Mock",
    "account_id": "Mock_Paper",
    "initial_equity": 100000.0
})

# Connect
broker.connect()

# Place market order
order = {
    'instrument': 'AAPL',
    'direction': 'LONG',
    'quantity': 100,
    'order_type': 'MARKET',
    'price': 150.00  # Required for mock_mock mode
}

result = broker.place_order(order)
print(f"Order {result['broker_order_id']} filled at ${result['avg_fill_price']}")
```

### Limit Order

```python
order = {
    'instrument': 'TSLA',
    'direction': 'LONG',
    'quantity': 50,
    'order_type': 'LIMIT',
    'limit_price': 200.00  # Uses limit_price instead of price
}

result = broker.place_order(order)
assert result['avg_fill_price'] == 200.00  # Filled at limit price
```

### Account Data Queries

```python
# Get balance
balance = broker.get_account_balance()
print(f"Equity: ${balance['equity']:,.2f}")
print(f"Buying Power: ${balance['buying_power']:,.2f}")

# Get positions
positions = broker.get_open_positions()
for pos in positions:
    print(f"{pos['instrument']}: {pos['quantity']} @ ${pos['avg_price']}")

# Get margin info
margin = broker.get_margin_info()
print(f"Margin Used: ${margin['margin_used']:,.2f}")
print(f"Margin Available: ${margin['margin_available']:,.2f}")
```

### Order Status

```python
# Place order
result = broker.place_order(order)
broker_order_id = result['broker_order_id']

# Query status
status = broker.get_order_status(broker_order_id)
print(f"Status: {status['status']}")
print(f"Filled: {status['filled_quantity']}/{status['filled_quantity'] + status['remaining_quantity']}")
```

### Multi-Asset Order

```python
# Forex
forex_order = {
    'instrument': 'EURUSD',
    'instrument_type': 'FOREX',
    'direction': 'LONG',
    'quantity': 10000,
    'order_type': 'MARKET',
    'price': 1.0850
}

# Crypto
crypto_order = {
    'instrument': 'BTC',
    'instrument_type': 'CRYPTO',
    'direction': 'LONG',
    'quantity': 0.5,  # Fractional quantity
    'order_type': 'MARKET',
    'price': 42000.00
}

# Options
option_order = {
    'instrument': 'AAPL',
    'instrument_type': 'OPTION',
    'direction': 'LONG',
    'quantity': 1,
    'order_type': 'MARKET',
    'price': 5.50,  # Option premium
    'legs': [
        {
            'strike': 150,
            'expiry': '20250117',
            'right': 'CALL',
            'action': 'BUY',
            'quantity': 1
        }
    ]
}
```

## Mock Pricing

### MARKET Orders

**Requires `price` field** - Mock broker has no market data feed:

```python
# ✅ Correct
order = {
    'order_type': 'MARKET',
    'price': 150.00  # Must be provided
}

# ❌ Incorrect (will raise ValueError)
order = {
    'order_type': 'MARKET'
    # Missing price!
}
```

**Sources of price:**

1. **mock_mock mode:** Signal includes price
2. **mock_live mode:** BrokerModeAdapter fetches from real broker

### LIMIT Orders

Use `limit_price` field:

```python
order = {
    'order_type': 'LIMIT',
    'limit_price': 149.50  # Fill price
}
```

### Price Validation

Mock broker logs critical errors if price is missing:

```python
# If price is missing for MARKET order:
logger.critical(
    f"⚠️ CRITICAL: {instrument} MARKET order missing 'price' field! "
    f"Cannot execute without a price (no fallback pricing)."
)
raise ValueError(f"MARKET order for {instrument} missing 'price' field.")
```

## MongoDB Integration

### Account Balance Storage

All balances are stored in MongoDB `trading_accounts` collection:

```python
def get_account_balance(self, account_id=None):
    """Read balance from MongoDB (single source of truth)"""
    account_doc = trading_accounts_collection.find_one({"account_id": account_id})
    
    if not account_doc:
        return fallback_balance  # Only if account doesn't exist
    
    # Return from MongoDB (no caching)
    return {
        "equity": account_doc['balances']['equity'],
        "cash_balance": account_doc['balances']['cash_balance'],
        "margin_used": account_doc['balances']['margin_used'],
        # ...
    }
```

### Position Tracking

Positions are stored in `open_positions` array:

```python
def get_open_positions(self, account_id=None):
    """Read positions from MongoDB"""
    account_doc = trading_accounts_collection.find_one({"account_id": account_id})
    
    if not account_doc:
        return []
    
    # Filter for OPEN status only
    all_positions = account_doc.get('open_positions', [])
    return [pos for pos in all_positions if pos['status'] == 'OPEN']
```

### Account Creation/Update

On connection, Mock broker ensures account exists:

```python
def _ensure_account_exists(self):
    """Create or update account in MongoDB"""
    if self.read_only:
        return  # Skip if read-only mode
    
    existing = trading_accounts_collection.find_one({"account_id": self.account_id})
    
    if existing:
        # Update balances only (preserve broker/mode config)
        trading_accounts_collection.update_one(
            {"account_id": self.account_id},
            {"$set": {"balances": {...}, "updated_at": datetime.utcnow()}}
        )
    else:
        # Create new account
        trading_accounts_collection.insert_one(mock_account_doc)
```

## Use Cases

### 1. Unit Testing

Fast, isolated tests without external dependencies:

```python
def test_order_placement():
    broker = MockBroker({"broker": "Mock", "account_id": "Test"})
    broker.connect()
    
    result = broker.place_order({
        'instrument': 'AAPL',
        'quantity': 100,
        'order_type': 'MARKET',
        'price': 150.00
    })
    
    assert result['status'] == 'Filled'
    assert result['filled'] == 100
```

### 2. Integration Testing

Test full signal flow without real money:

```bash
python tests/run_test_suite.py \
  --signal-testing \
  --environment staging \
  --account-type mock \
  --data-source mock \
  --file tests/sample_signals/stock_trading.json \
  --signal-count 5
```

### 3. Development Testing

Rapid iteration during development:

```python
# Test strategy logic without waiting for market data
for signal in test_signals:
    broker.place_order(signal)
    # Instant feedback
```

### 4. System Testing

Test system components (ExecutionService, AccountDataService):

```python
# ExecutionService can use Mock broker for testing
execution_service = ExecutionService(broker=mock_broker)
execution_service.process_signal(signal)
```

### 5. CI/CD Pipeline

Fast automated tests in CI environment:

```yaml
# .github/workflows/test.yml
- name: Run unit tests
  run: |
    pytest tests/brokers/test_mock_broker.py
    # All tests use mock broker - no real broker needed
```

## Testing Modes

Mock broker is used in two of the four trading modes:

### mock_mock Mode

**Fully simulated** - No real broker connection:

```json
{
  "account_id": "Mock_Paper",
  "broker": "Mock",
  "account_type": "mock",
  "data_source": "mock",
  "mode": "mock_mock"
}
```

**Characteristics:**
- Orders: Mock broker (instant fills)
- Pricing: From signals (must include `price` field)
- Speed: Fastest (no network calls)
- Use: Unit tests, fast development

### mock_live Mode

**Hybrid** - Real pricing, simulated execution:

```json
{
  "account_id": "Mock_Live",
  "broker": "Mock",
  "account_type": "mock",
  "data_source": "live",
  "mode": "mock_live"
}
```

**Characteristics:**
- Orders: Mock broker (instant fills)
- Pricing: From IBKR (real market data)
- Speed: Medium (network calls for pricing only)
- Use: Strategy testing with real market conditions

**BrokerModeAdapter handles price enrichment:**

```python
# Signal doesn't need price
signal = {'instrument': 'AAPL', 'quantity': 100}

# Adapter fetches live price from IBKR
enriched = adapter._enrich_with_real_pricing(signal)
# enriched['price'] = 152.35 (live IBKR price)

# Mock broker executes at live price
mock_broker.place_order(enriched)
```

## Limitations

### 1. No Market Data Feed

Mock broker has no price data - must be provided:

```python
# ❌ This fails in mock_mock mode
order = {'instrument': 'AAPL', 'order_type': 'MARKET'}

# ✅ This works
order = {'instrument': 'AAPL', 'order_type': 'MARKET', 'price': 150.00}
```

### 2. Instant Fills Only

No realistic fill simulation:
- No partial fills
- No order rejection
- No slippage
- No market impact

For realistic execution testing, use IBKR paper account.

### 3. No Order Book

No bid/ask spreads or order book simulation.

### 4. No Market Hours

Orders fill 24/7, ignoring market hours.

### 5. Simplified Margin

Uses 2x leverage for all instruments (not realistic).

### 6. No Commission/Fees

Fills at exact price with no costs.

## Troubleshooting

### Missing Price Error

**Error:**
```
ValueError: MARKET order for AAPL missing 'price' field.
Cannot execute without a price (no fallback pricing).
```

**Solution:**

For **mock_mock mode**, add price to signal:
```python
signal['price'] = 150.00
```

For **mock_live mode**, ensure:
1. Real broker (IBKR) is connected
2. BrokerModeAdapter is being used
3. Symbol is valid for real broker

### MongoDB Connection Error

**Error:**
```
WARNING: MongoDB not available, position tracking disabled
```

**Solution:**

1. Check `MONGODB_URI` environment variable:
```bash
echo $MONGODB_URI
# Should be: mongodb://localhost:27018/mathematricks_trading
```

2. Ensure MongoDB is running:
```bash
docker-compose ps mongodb
# Should show "Up"
```

3. Test connection:
```bash
mongosh $MONGODB_URI --eval "db.adminCommand('ping')"
```

### Account Not Found

**Error:**
```
WARNING: Account Mock_Paper not found in MongoDB
```

**Solution:**

Mock broker creates account on first connection:
```python
broker.connect()  # Creates account if missing
```

Or manually create account:
```bash
mongosh $MONGODB_URI
db.trading_accounts.insertOne({
  "account_id": "Mock_Paper",
  "broker": "Mock",
  "balances": {...},
  "open_positions": []
})
```

### Read-Only Mode Warning

**Log:**
```
Mock Broker initialized for account IBKR_Paper (read-only mode - no MongoDB writes)
```

**Explanation:**

This is normal when Mock broker is used as a secondary broker in BrokerModeAdapter. It prevents overwriting the real account's broker configuration.

### Order ID Not Found

**Error:**
```
ValueError: Order MOCK_1234567890_5678 not found in mock broker
```

**Solution:**

Mock broker only tracks orders in memory (not persisted). Order IDs are session-specific. Use MongoDB `orders` collection for persistent order history.

## Performance

Mock broker is **extremely fast**:

| Operation | Latency | Throughput |
|-----------|---------|------------|
| connect() | <1ms | N/A |
| place_order() | <1ms | >10,000/sec |
| get_account_balance() | 1-5ms | ~1,000/sec (MongoDB read) |
| get_open_positions() | 1-5ms | ~1,000/sec (MongoDB read) |
| cancel_order() | <1ms | >10,000/sec |

### Optimization Tips

1. **Minimize MongoDB queries** - Cache balance if reading frequently
2. **Batch orders** - Process multiple signals in one pass
3. **Use mock_mock** - Fastest mode (no network calls)
4. **Clear test data between runs** - Prevents large position arrays

## Best Practices

### 1. Always Provide Price in Signals

For mock_mock mode:
```python
signal = {
    'instrument': 'AAPL',
    'quantity': 100,
    'order_type': 'MARKET',
    'price': 150.00  # Always include
}
```

### 2. Use Realistic Initial Equity

Match production account size:
```python
config = {
    "initial_equity": 100000.0  # Same as production
}
```

### 3. Clean Up Between Tests

```python
# Clear test data
scripts/clear_test_data.py --environment staging

# Reconnect to recreate fresh account
broker.connect()
```

### 4. Validate Order Results

```python
result = broker.place_order(order)
assert result['status'] == 'Filled'
assert result['filled'] == order['quantity']
assert 'broker_order_id' in result
```

### 5. Test with Multiple Instruments

```python
# Test across asset classes
for instrument_type in ['STOCK', 'FOREX', 'CRYPTO']:
    order = create_test_order(instrument_type)
    result = broker.place_order(order)
    assert result['status'] == 'Filled'
```

## See Also

- [Abstract Broker Interface](../../services/brokers/base.py)
- [BrokerModeAdapter](../../services/brokers/adapters/mode_adapter.py)
- [Mock Broker Implementation](../../services/brokers/mock/mock_broker.py)
- [Testing Guide](../../tests/README.md)
- [4-Mode System Documentation](../README.md)
