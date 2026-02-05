# Coinbase Advanced Trade API Broker

Complete documentation for Coinbase cryptocurrency spot trading integration.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Symbol Format](#symbol-format)
- [Sandbox vs Production](#sandbox-vs-production)
- [Authentication](#authentication)
- [Setup Guide](#setup-guide)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Supported Cryptocurrencies](#supported-cryptocurrencies)
- [Limitations](#limitations)
- [API Workarounds](#api-workarounds)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The Coinbase broker integration provides cryptocurrency spot trading via Coinbase Advanced Trade API.

**Implementation:** [services/brokers/coinbase/coinbase_broker.py](../../services/brokers/coinbase/coinbase_broker.py)

### Features

- ✅ Crypto spot trading (BTC, ETH, SOL, XRP, ADA, DOGE, etc.)
- ✅ Market and limit orders
- ✅ Real-time balance queries
- ✅ Official sandbox environment for testing
- ✅ Real-time price data
- ✅ Order book access
- ✅ Multi-currency holdings tracking

### What's NOT Supported

- ❌ Margin trading
- ❌ Futures/derivatives
- ❌ Options
- ❌ Staking/lending
- ❌ Crypto-to-crypto pairs (only crypto-to-USD)

## Symbol Format

The broker accepts both short and full symbol formats:

| Our Symbol | Coinbase Symbol | Description |
|------------|-----------------|-------------|
| BTC | BTC-USD | Bitcoin |
| BTC-USD | BTC-USD | Bitcoin (explicit) |
| ETH | ETH-USD | Ethereum |
| SOL | SOL-USD | Solana |
| XRP | XRP-USD | Ripple |
| ADA | ADA-USD | Cardano |
| DOGE | DOGE-USD | Dogecoin |

**Auto-normalization:** The broker automatically converts `BTC` → `BTC-USD`

```python
# All three are equivalent:
broker.get_current_price('BTC')
broker.get_current_price('BTC-USD')
broker.get_current_price('btc-usd')  # Case-insensitive
```

## Sandbox vs Production

### Sandbox (Testing)

**Zero risk** - Test without real money:

```python
config = {
    'api_key': 'organizations/xxx/apiKeys/yyy',
    'api_secret': '-----BEGIN EC PRIVATE KEY-----\n...',
    'sandbox': True  # Sandbox environment
}
```

- **Base URL:** `https://api-sandbox.coinbase.com`
- **Credentials:** Separate sandbox API keys
- **Use:** Testing, development, CI/CD
- **Cost:** Free

### Production (Live Trading)

**Real money** - Live cryptocurrency trading:

```python
config = {
    'api_key': 'organizations/xxx/apiKeys/yyy',
    'api_secret': '-----BEGIN EC PRIVATE KEY-----\n...',
    'sandbox': False  # Production environment
}
```

- **Base URL:** `https://api.coinbase.com`
- **Credentials:** Production API keys
- **Use:** Real trading
- **Cost:** Coinbase fees apply

> ⚠️ **Always test in sandbox first** before enabling production trading.

## Authentication

Coinbase uses JWT-based authentication with:

1. **API Key Name:** Organizations/API key identifier (e.g., `organizations/xxx/apiKeys/yyy`)
2. **Private Key:** EC private key in PEM format

### Generating API Keys

#### Step 1: Create API Key in Coinbase

1. Log into [Coinbase](https://www.coinbase.com)
2. Navigate to **Settings → API**
3. Click **New API Key**
4. Set permissions:
   - ✅ View account information
   - ✅ Trade
   - ⚠️ **DO NOT enable withdraw** (for safety)
5. Save the API key name and download the private key JSON

#### Step 2: Extract Credentials

Coinbase provides a JSON file like:

```json
{
  "name": "organizations/abc-123/apiKeys/def-456",
  "privateKey": "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIBVT...j1kz\n-----END EC PRIVATE KEY-----"
}
```

Extract:
- **API Key Name:** `organizations/abc-123/apiKeys/def-456`
- **Private Key:** The PEM-formatted string (including `-----BEGIN/END-----`)

#### Step 3: Store in Environment

Add to `.env` file:

```bash
# Sandbox credentials
COINBASE_SANDBOX_API_KEY=organizations/xxx-sandbox/apiKeys/yyy
COINBASE_SANDBOX_PRIVATE_KEY=-----BEGIN EC PRIVATE KEY-----\nMHcCAQ...\n-----END EC PRIVATE KEY-----

# Production credentials (⚠️ NEVER commit to git)
COINBASE_API_KEY=organizations/xxx/apiKeys/yyy
COINBASE_PRIVATE_KEY=-----BEGIN EC PRIVATE KEY-----\nMHcCAQ...\n-----END EC PRIVATE KEY-----
```

**Important:** Preserve `\n` newline characters in the private key!

## Setup Guide

### Prerequisites

```bash
# Install Coinbase SDK
pip install coinbase-advanced-py>=1.2.0
```

### MongoDB Account Document

Add Coinbase account to `trading_accounts` collection:

```json
{
  "account_id": "COINBASE_MAIN",
  "account_name": "Coinbase Main Trading Account",
  "broker": "Coinbase",
  "account_type": "mock",
  "data_source": "live",
  "mode": "mock_live",
  "authentication_details": {
    "api_key": "organizations/xxx/apiKeys/yyy",
    "api_secret": "-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----",
    "sandbox": true
  },
  "balances": {
    "equity": 10000.0,
    "cash_balance": 5000.0,
    "margin_used": 0.0,
    "margin_available": 10000.0,
    "buying_power": 10000.0,
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

### Test Connection

```python
from services.brokers.coinbase import CoinbaseBroker

config = {
    'api_key': os.getenv('COINBASE_SANDBOX_API_KEY'),
    'api_secret': os.getenv('COINBASE_SANDBOX_PRIVATE_KEY'),
    'sandbox': True
}

broker = CoinbaseBroker(config)

if broker.connect():
    print("✅ Connected to Coinbase Sandbox")
    balance = broker.get_account_balance()
    print(f"Balance: ${balance['equity']:,.2f}")
    broker.disconnect()
else:
    print("❌ Connection failed")
```

## Configuration

### Basic Configuration

```python
from services.brokers.coinbase import CoinbaseBroker
from services.brokers.factory import BrokerFactory

# Using factory
config = {
    "broker": "Coinbase",
    "api_key": "organizations/xxx/apiKeys/yyy",
    "api_secret": "-----BEGIN EC PRIVATE KEY-----\n...",
    "sandbox": True
}

broker = BrokerFactory.create_broker(config)
```

### Direct Initialization

```python
broker = CoinbaseBroker({
    'api_key': os.getenv('COINBASE_API_KEY'),
    'api_secret': os.getenv('COINBASE_PRIVATE_KEY'),
    'sandbox': False  # Production
})
```

### Account ID

Coinbase broker uses the account name from config or defaults to "Coinbase":

```python
config = {
    "broker": "Coinbase",
    "account_id": "COINBASE_MAIN",  # Optional, for tracking
    "api_key": "...",
    "api_secret": "..."
}
```

## Usage Examples

### Connect and Check Balance

```python
broker = CoinbaseBroker(config)
broker.connect()

balance = broker.get_account_balance()
print(f"Total Equity: ${balance['equity']:,.2f}")
print(f"Cash (USD): ${balance['cash_balance']:,.2f}")
print(f"Holdings: {balance['holdings']}")
# Holdings: {'BTC': 0.5, 'ETH': 2.3}
```

### Place Market Order

```python
# Buy Bitcoin
order = {
    'instrument': 'BTC-USD',
    'action': 'BUY',
    'quantity': 0.01,  # 0.01 BTC
    'order_type': 'MARKET'
}

result = broker.place_order(order)
print(f"Order ID: {result['broker_order_id']}")
print(f"Status: {result['status']}")
print(f"Avg Price: ${result['average_price']:,.2f}")
```

### Place Limit Order

```python
# Sell Ethereum at $2500
order = {
    'instrument': 'ETH-USD',
    'action': 'SELL',
    'quantity': 0.5,
    'order_type': 'LIMIT',
    'limit_price': 2500.00
}

result = broker.place_order(order)
print(f"Limit order placed: {result['broker_order_id']}")
```

### Get Current Price

```python
# Get real-time price
btc_price = broker.get_current_price('BTC-USD')
print(f"BTC: ${btc_price:,.2f}")

eth_price = broker.get_current_price('ETH')  # Auto-normalized
print(f"ETH: ${eth_price:,.2f}")
```

### Get Open Positions

```python
positions = broker.get_open_positions()

for pos in positions:
    print(f"{pos['symbol']}: {pos['quantity']} @ ${pos['avg_price']:,.2f}")
    print(f"  Current: ${pos['current_price']:,.2f}")
    print(f"  P&L: ${pos['unrealized_pnl']:,.2f}")
```

### Cancel Order

```python
# Place limit order
result = broker.place_order(limit_order)
order_id = result['broker_order_id']

# Cancel it
if broker.cancel_order(order_id):
    print("Order cancelled")
else:
    print("Cancel failed (may already be filled)")
```

### Get Order Status

```python
status = broker.get_order_status(order_id)
print(f"Status: {status['status']}")
print(f"Filled: {status['filled_quantity']}")
print(f"Remaining: {status['remaining_quantity']}")
```

### Multi-Currency Portfolio

```python
broker.connect()

# Buy multiple cryptos
cryptos = [
    {'instrument': 'BTC', 'quantity': 0.1},
    {'instrument': 'ETH', 'quantity': 1.0},
    {'instrument': 'SOL', 'quantity': 10.0}
]

for crypto in cryptos:
    order = {
        'instrument': crypto['instrument'],
        'action': 'BUY',
        'quantity': crypto['quantity'],
        'order_type': 'MARKET'
    }
    result = broker.place_order(order)
    print(f"Bought {crypto['quantity']} {crypto['instrument']}")

# Check portfolio
balance = broker.get_account_balance()
print(f"\nPortfolio value: ${balance['equity']:,.2f}")
print("Holdings:")
for symbol, qty in balance['holdings'].items():
    print(f"  {symbol}: {qty}")
```

## Supported Cryptocurrencies

The broker has built-in support for common cryptocurrencies:

| Symbol | Name | Min Order Size |
|--------|------|----------------|
| BTC-USD | Bitcoin | 0.00001 BTC |
| ETH-USD | Ethereum | 0.0001 ETH |
| SOL-USD | Solana | 0.01 SOL |
| XRP-USD | Ripple | 1 XRP |
| ADA-USD | Cardano | 1 ADA |
| DOGE-USD | Dogecoin | 1 DOGE |

**Note:** Minimum order sizes vary by product. Check Coinbase documentation for specifics.

### Adding New Symbols

To add support for additional cryptocurrencies, update `SYMBOL_MAP` in `coinbase_broker.py`:

```python
SYMBOL_MAP = {
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    # Add new symbols here:
    'AVAX': 'AVAX-USD',
    'MATIC': 'MATIC-USD'
}
```

## Limitations

### 1. Spot Trading Only

- ✅ Buy/sell crypto for USD
- ❌ No margin/leverage
- ❌ No futures/derivatives
- ❌ No options

### 2. USD Pairs Only

- ✅ BTC-USD, ETH-USD, etc.
- ❌ No BTC-ETH or other crypto-to-crypto pairs
- ❌ No fiat pairs other than USD

### 3. Position Tracking

Coinbase spot trading doesn't have traditional "positions" like stocks:

```python
# Holdings are tracked as "positions"
positions = broker.get_open_positions()
# Returns: [{symbol: 'BTC', quantity: 0.5, ...}]
```

### 4. No True Paper Trading

- Sandbox has limited functionality
- Some endpoints may not work in sandbox
- Production testing requires small real amounts

### 5. Rate Limits

Coinbase enforces API rate limits:
- **Public endpoints:** 10 requests/second
- **Private endpoints:** 15 requests/second

The broker doesn't implement rate limiting - you must handle this at a higher level.

### 6. Minimum Order Sizes

Each product has minimum order requirements:

```python
# Too small - will be rejected
order = {'instrument': 'BTC', 'quantity': 0.000001}  # Below minimum

# Minimum varies by product - check Coinbase docs
```

## API Workarounds

### Sandbox Price Data Issue

**Problem:** Coinbase sandbox lacks market data endpoints.

**Solution:** The broker uses **production API for pricing**, sandbox only for orders:

```python
# Data client: Always production (for prices)
self.data_client = RESTClient(base_url="https://api.coinbase.com")

# Order client: Respects sandbox flag
self.order_client = RESTClient(
    base_url="https://api-sandbox.coinbase.com" if sandbox else "https://api.coinbase.com"
)
```

This allows testing order execution in sandbox while getting real price data.

### JWT Token Generation

The `coinbase-advanced-py` SDK automatically generates JWT tokens for authentication:

```python
# SDK handles JWT generation internally
response = self.client.get_accounts()
# No manual token management needed
```

## Error Handling

All Coinbase operations raise appropriate exceptions:

```python
from services.brokers.exceptions import *

try:
    result = broker.place_order(order)
except BrokerConnectionError as e:
    print(f"Connection failed: {e}")
except OrderRejectedError as e:
    print(f"Order rejected: {e}")
except InvalidSymbolError as e:
    print(f"Invalid symbol: {e.symbol}")
except BrokerAPIError as e:
    print(f"API error: {e}")
```

### Common Exceptions

```python
# Connection error
BrokerConnectionError("Not connected to Coinbase")

# Invalid symbol
InvalidSymbolError("Symbol 'INVALID' not recognized")

# Order rejected
OrderRejectedError("Order rejected: Insufficient funds")

# API error
BrokerAPIError("Failed to get account balance: Timeout")
```

## Troubleshooting

### Connection Fails

**Error:**
```
BrokerConnectionError: Not connected to Coinbase
```

**Solution:**

1. Verify API credentials:
```python
print(config['api_key'])  # Should start with "organizations/"
print(config['api_secret'][:50])  # Should start with "-----BEGIN EC"
```

2. Check private key format:
```python
# Must include newlines (\n)
api_secret = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQ...\n-----END EC PRIVATE KEY-----"
```

3. Test with Coinbase API directly:
```bash
curl -H "Authorization: Bearer $TOKEN" https://api.coinbase.com/api/v3/brokerage/accounts
```

### Library Not Installed

**Error:**
```
BrokerConnectionError: coinbase-advanced-py library not installed
```

**Solution:**
```bash
pip install coinbase-advanced-py>=1.2.0
```

### Invalid Symbol

**Error:**
```
InvalidSymbolError: Symbol 'INVALID' not recognized. Supported: ['BTC', 'ETH', ...]
```

**Solution:**

1. Check symbol spelling:
```python
# ✅ Correct
broker.get_current_price('BTC-USD')

# ❌ Wrong
broker.get_current_price('BITCOIN')
```

2. Add to SYMBOL_MAP if needed (for new cryptos)

### Order Rejected

**Error:**
```
OrderRejectedError: Order rejected: Insufficient funds
```

**Solution:**

1. Check balance:
```python
balance = broker.get_account_balance()
print(f"Available: ${balance['cash_balance']:,.2f}")
```

2. Reduce order size:
```python
order['quantity'] = order['quantity'] / 2
```

3. Verify minimum order size for the product

### Sandbox Issues

**Error:**
```
BrokerAPIError: Endpoint not available in sandbox
```

**Solution:**

Some endpoints don't work in sandbox. For comprehensive testing, use production with small amounts:

```python
# Test with minimal amount in production
config['sandbox'] = False
order = {'instrument': 'BTC', 'quantity': 0.00001}  # ~$0.50
```

### Rate Limit Exceeded

**Error:**
```
BrokerAPIError: Rate limit exceeded
```

**Solution:**

1. Add delay between requests:
```python
import time
for order in orders:
    broker.place_order(order)
    time.sleep(0.2)  # 200ms delay (5 req/sec)
```

2. Implement exponential backoff:
```python
for attempt in range(3):
    try:
        result = broker.place_order(order)
        break
    except BrokerAPIError as e:
        if "rate limit" in str(e).lower():
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
        else:
            raise
```

## Best Practices

### 1. Use Environment Variables

```python
import os

config = {
    'api_key': os.getenv('COINBASE_API_KEY'),
    'api_secret': os.getenv('COINBASE_PRIVATE_KEY'),
    'sandbox': os.getenv('ENVIRONMENT') != 'production'
}
```

### 2. Test in Sandbox First

```python
# Development/testing
config['sandbox'] = True

# Production
if environment == 'production':
    config['sandbox'] = False
```

### 3. Handle Rate Limits

```python
import time

def place_order_with_retry(broker, order, max_retries=3):
    for attempt in range(max_retries):
        try:
            return broker.place_order(order)
        except BrokerAPIError as e:
            if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
```

### 4. Validate Symbols

```python
# Normalize symbol before using
try:
    normalized = broker._normalize_symbol(symbol)
    price = broker.get_current_price(normalized)
except InvalidSymbolError:
    logger.warning(f"Symbol {symbol} not supported")
```

### 5. Check Balance Before Orders

```python
balance = broker.get_account_balance()
cost = order['quantity'] * broker.get_current_price(order['instrument'])

if cost > balance['cash_balance']:
    logger.error(f"Insufficient funds: ${cost:.2f} > ${balance['cash_balance']:.2f}")
    raise InsufficientFundsError("Not enough USD balance")
```

### 6. Use Limit Orders for Large Amounts

```python
# For large orders, use limit to control price
if order_value > 10000:  # $10k+
    current_price = broker.get_current_price(order['instrument'])
    order['order_type'] = 'LIMIT'
    order['limit_price'] = current_price * 1.01  # 1% slippage tolerance
```

### 7. Monitor Holdings

```python
# Periodically check portfolio
balance = broker.get_account_balance()
if balance['equity'] < min_equity:
    logger.critical(f"⚠️ Portfolio below minimum: ${balance['equity']:,.2f}")
    # Alert or stop trading
```

### 8. Log All Operations

```python
import logging
logging.basicConfig(level=logging.INFO)

# Broker logs all operations:
logger.info(f"Placing order: {order}")
result = broker.place_order(order)
logger.info(f"Order result: {result}")
```

### 9. Handle Partial Fills

```python
# For limit orders, check fill status
result = broker.place_order(limit_order)
time.sleep(5)  # Wait for fill

status = broker.get_order_status(result['broker_order_id'])
if status['remaining_quantity'] > 0:
    logger.warning(f"Partial fill: {status['filled_quantity']}/{order['quantity']}")
    # Cancel remaining or wait longer
```

### 10. Separate Sandbox and Production Keys

```bash
# .env file
# Sandbox (for testing)
COINBASE_SANDBOX_API_KEY=organizations/xxx-sandbox/apiKeys/yyy
COINBASE_SANDBOX_PRIVATE_KEY=...

# Production (real money)
COINBASE_API_KEY=organizations/xxx/apiKeys/zzz
COINBASE_PRIVATE_KEY=...
```

## Performance

Coinbase REST API performance characteristics:

| Operation | Latency | Notes |
|-----------|---------|-------|
| connect() | 200-500ms | Verifies credentials |
| place_order() | 100-500ms | Market order execution |
| get_account_balance() | 100-300ms | REST API call |
| get_current_price() | 100-300ms | Production API |
| cancel_order() | 100-500ms | REST API call |

**Optimization tips:**
- Cache prices for short periods (5-10 seconds)
- Batch operations when possible
- Use websockets for real-time data (future enhancement)

## See Also

- [Abstract Broker Interface](../../services/brokers/base.py)
- [Coinbase Broker Implementation](../../services/brokers/coinbase/coinbase_broker.py)
- [Coinbase Advanced Trade API Docs](https://docs.cdp.coinbase.com/advanced-trade/docs/)
- [Coinbase Sandbox](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox)
- [coinbase-advanced-py SDK](https://github.com/coinbase/coinbase-advanced-py)
- [Exception Definitions](../../services/brokers/exceptions.py)
