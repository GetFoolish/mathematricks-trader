# Coinbase Advanced Trade API Broker

## Overview

This broker implementation provides integration with Coinbase Advanced Trade API for cryptocurrency spot trading.

## Features

- ✅ Crypto spot trading (BTC, ETH, SOL, XRP, ADA, DOGE)
- ✅ Market and limit orders
- ✅ Real-time balance queries
- ✅ Official sandbox environment for testing
- ✅ Real-time price data
- ✅ Order book access

## Symbol Format

| Our Symbol | Coinbase Symbol | Description |
|------------|-----------------|-------------|
| BTC | BTC-USD | Bitcoin |
| ETH | ETH-USD | Ethereum |
| SOL | SOL-USD | Solana |
| XRP | XRP-USD | Ripple |
| ADA | ADA-USD | Cardano |
| DOGE | DOGE-USD | Dogecoin |

## Configuration

### Environment Variables

```bash
# Add to .env file
COINBASE_API_KEY_NAME=organizations/xxx/apiKeys/yyy
COINBASE_PRIVATE_KEY=-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----
```

### MongoDB Account Document

```json
{
  "account_id": "COINBASE_CANADA",
  "broker": "Coinbase",
  "account_type": "mock",
  "mode": ["mock_mock", "mock_live", "paper_live"],
  "status": "ACTIVE",
  "authentication_details": {
    "api_key": "organizations/xxx/apiKeys/yyy",
    "api_secret": "-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----",
    "sandbox": true,
    "initial_equity": 100000.0
  }
}
```

## Usage

### Initialize Broker

```python
from services.brokers.coinbase import CoinbaseBroker

config = {
    'api_key': 'organizations/xxx/apiKeys/yyy',
    'api_secret': '-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----',
    'sandbox': True  # Use sandbox environment for testing
}

broker = CoinbaseBroker(config)
broker.connect()
```

### Place Market Order

```python
order = {
    'instrument': 'BTC-USD',
    'action': 'BUY',
    'quantity': 0.01,
    'order_type': 'MARKET'
}

result = broker.place_order(order)
print(f"Order ID: {result['broker_order_id']}")
```

### Get Account Balance

```python
balance = broker.get_account_balance()
print(f"Total Equity: ${balance['equity']:,.2f}")
print(f"Cash: ${balance['cash_balance']:,.2f}")
print(f"Holdings: {balance['holdings']}")
```

### Get Current Price

```python
price = broker.get_current_price('BTC-USD')
print(f"BTC Price: ${price:,.2f}")
```

## Sandbox vs Production

### Sandbox (Testing)

- **Base URL:** `https://api.sandbox.coinbase.com`
- **Use:** Testing without real money
- **Credentials:** Separate sandbox API keys
- **Config:** `sandbox: true`

### Production (Live Trading)

- **Base URL:** `https://api.coinbase.com`
- **Use:** Real trading with real money
- **Credentials:** Production API keys
- **Config:** `sandbox: false`

## Authentication

Coinbase uses JWT-based authentication with:
- **API Key Name:** Organizations/API key identifier
- **Private Key:** EC private key in PEM format

The `coinbase-advanced-py` library handles JWT token generation automatically.

## Limitations

1. **Spot Trading Only:** No margin, futures, or options
2. **No True Positions:** Crypto holdings are treated as positions
3. **Rate Limits:** Coinbase enforces API rate limits
4. **Minimum Order Sizes:** Each product has minimum order requirements

## Testing

### Unit Test Example

```python
# Test connection
assert broker.connect() == True

# Test price fetching
price = broker.get_current_price('BTC-USD')
assert price > 0

# Test balance query
balance = broker.get_account_balance()
assert 'equity' in balance
```

### Integration Test

```bash
# Test with sample signals
.venv/bin/python tests/run_test_suite.py --signal-testing \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count 2
```

## Error Handling

All methods raise appropriate exceptions:
- `BrokerConnectionError`: Connection failures
- `OrderRejectedError`: Order rejection
- `BrokerAPIError`: API errors
- `InvalidSymbolError`: Unsupported symbols

## Logging

The broker logs all operations:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Dependencies

```bash
pip install coinbase-advanced-py>=1.2.0
```

## API Reference

- [Coinbase Advanced Trade API Docs](https://docs.cdp.coinbase.com/advanced-trade/docs/)
- [Sandbox Environment](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox)
- [Python SDK](https://github.com/coinbase/coinbase-advanced-py)
