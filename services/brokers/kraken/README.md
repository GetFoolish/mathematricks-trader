# Kraken Broker Integration

## Overview
Kraken broker integration for crypto spot trading via REST API.

## Features
- ✅ Crypto spot trading (BTC, ETH, SOL, XRP, ADA, DOGE)
- ✅ Market and limit orders
- ✅ Real-time balance queries
- ✅ Real-time price data via ticker API
- ✅ Order book data
- ✅ Support for 3 trading modes (mock_mock, mock_live, paper_live)

## Symbol Format
Kraken uses specific symbol formats. This broker automatically maps common formats:

| Our Format | Kraken Format |
|------------|---------------|
| BTC, XBTUSD | XXBTZUSD |
| ETH, ETHUSD | XETHZUSD |
| SOL, SOLUSD | SOLUSD |
| XRP, XRPUSD | XXRPZUSD |
| ADA, ADAUSD | ADAUSD |
| DOGE, DOGEUSD | XDGUSD |

## Configuration

### Environment Variables
Add to `.env`:
```bash
KRAKEN_API_KEY=your_api_key_here
KRAKEN_API_SECRET=your_api_secret_here
```

### MongoDB Account Document
```json
{
  "account_id": "KRAKEN-TESTNET",
  "broker": "Kraken",
  "account_type": "mock",
  "mode": ["mock_mock", "mock_live", "paper_live"],
  "authentication_details": {
    "api_key": "YOUR_API_KEY",
    "api_secret": "YOUR_API_SECRET",
    "testnet": true
  }
}
```

## Usage

### Standalone Testing
```python
from services.brokers import BrokerFactory

config = {
    "broker": "Kraken",
    "account_id": "KRAKEN-TESTNET",
    "api_key": "your_key",
    "api_secret": "your_secret"
}

broker = BrokerFactory.create_broker(config)
broker.connect()

# Get price
price = broker.get_current_price("BTC")
print(f"BTC price: ${price:,.2f}")

# Get balance
balance = broker.get_account_balance()
print(f"Equity: ${balance['equity']:,.2f}")

# Place order
order = {
    "instrument": "BTC",
    "side": "BUY",
    "quantity": 0.001,
    "order_type": "MARKET"
}
result = broker.place_order(order)
print(f"Order ID: {result['broker_order_id']}")
```

## API Reference

### Methods

#### `connect() -> bool`
Test connection to Kraken API by querying server time and balance.

#### `get_current_price(instrument: str) -> float`
Get real-time market price for a crypto asset.

#### `get_account_balance() -> Dict`
Returns:
- `equity`: Total account value in USD (cash + crypto holdings)
- `cash_balance`: Available USD balance
- `margin_available`: Available for trading (same as cash for spot)
- `unrealized_pnl`: 0 (not tracked for spot trading)

#### `place_order(order: Dict) -> Dict`
Place market or limit order.

Order dict:
- `instrument`: Symbol (BTC, ETH, etc.)
- `side`: BUY or SELL
- `quantity`: Amount in crypto units (e.g., 0.5 BTC)
- `order_type`: MARKET or LIMIT
- `price`: Limit price (optional, for LIMIT orders)

Returns:
- `broker_order_id`: Kraken transaction ID
- `status`: FILLED, PARTIALLY_FILLED, SUBMITTED
- `filled_quantity`: Actual filled amount
- `avg_fill_price`: Average execution price

#### `get_order_book(instrument: str, depth: int = 10) -> Dict`
Get order book with bids and asks.

## Limitations

1. **No Official Testnet**: Kraken doesn't provide a dedicated testnet. Paper trading uses real API with small amounts.

2. **Spot Trading Only**: No margin trading, futures, or options support in this implementation.

3. **Position Tracking**: Kraken spot API doesn't have a "positions" concept. The `get_open_positions()` method returns an empty list. Position tracking is handled by our system in MongoDB.

4. **Rate Limits**: Kraken has API rate limits. Add delays between rapid calls if needed.

5. **Symbol Mapping**: Not all crypto pairs are mapped. Unmapped symbols will be sent as-is to Kraken API.

## Testing

### 1. Install Dependencies
```bash
pip install krakenex
```

### 2. Seed Account
```bash
.venv/bin/python scripts/seed_kraken_account.py
```

### 3. Run Tests
```bash
# Quick test (2 signals)
.venv/bin/python tests/run_test_suite.py --signal-testing \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/kraken/crypto_spot_trading.json --signal-count 2

# Full test
.venv/bin/python tests/run_test_suite.py --signal-testing --clean \
  --environment staging --account-type mock --data-source mock \
  --file tests/sample_signals/kraken/crypto_spot_trading.json
```

## Error Handling

- `BrokerConnectionError`: API credentials invalid or connection failed
- `OrderRejectedError`: Order rejected by Kraken (insufficient funds, invalid params)
- `InvalidSymbolError`: Symbol not found or invalid
- `BrokerAPIError`: General API error

## Notes

- For `mock_live` mode, price data comes from Kraken but orders execute via Mock broker
- For `paper_live` mode, both price and order execution use Kraken API (requires funded account)
- Balance calculation includes USD + crypto holdings valued at current prices
- All timestamps are in UTC

---

**Status**: ✅ Implemented  
**Last Updated**: 2026-01-31  
**Dependencies**: `krakenex>=2.2.0`
