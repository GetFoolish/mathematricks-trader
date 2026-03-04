# Broker Documentation

Comprehensive documentation for all broker integrations in the Mathematricks Trading System.

## Supported Brokers

| Broker | Status | Markets | Testing Support | Documentation |
|--------|--------|---------|-----------------|---------------|
| **Mock** | ✅ Production | All (simulated) | Full | [mock.md](mock.md) |
| **IBKR** | ✅ Production | Stocks, Options, Futures, Forex, Crypto | Paper Trading | [ibkr_gateway.md](ibkr_gateway.md) |
| **Coinbase** | ✅ Production | Crypto Spot | Sandbox | [coinbase.md](coinbase.md) |
| **Zerodha** | ✅ Production | Indian Stocks, Derivatives | Limited | See services/brokers/zerodha/ |
| **Kraken** | 🚧 Beta | Crypto Spot | Limited | See services/brokers/kraken/ |

## Quick Comparison

### Mock Broker
- **Use Case:** Unit testing, integration testing, fast development
- **Speed:** Instant fills (no market delays)
- **Cost:** Free
- **Data:** Mock or real (via hybrid mode)
- **Risk:** Zero (simulated only)

### IBKR (Interactive Brokers)
- **Use Case:** Production trading, paper trading, multi-asset strategies
- **Speed:** Real market execution
- **Cost:** Low commissions, market data fees may apply
- **Data:** Real-time (with subscription) or delayed
- **Risk:** Paper account (zero risk) or Live account (real money)

### Coinbase
- **Use Case:** Cryptocurrency spot trading
- **Speed:** Real market execution
- **Cost:** Coinbase fees apply
- **Data:** Real-time crypto prices
- **Risk:** Sandbox (zero risk) or Production (real money)

## Architecture Overview

All brokers implement the `AbstractBroker` interface defined in [services/brokers/base.py](../../services/brokers/base.py):

```python
class AbstractBroker(ABC):
    # Connection Management
    def connect() -> bool
    def disconnect() -> bool
    def is_connected() -> bool

    # Order Management
    def place_order(order: Dict) -> Dict
    def cancel_order(broker_order_id: str) -> bool
    def get_order_status(broker_order_id: str) -> Dict

    # Account Data
    def get_account_balance(account_id: Optional[str]) -> Dict
    def get_open_positions(account_id: Optional[str]) -> List[Dict]
    def get_margin_info(account_id: Optional[str]) -> Dict
    def get_open_orders(account_id: Optional[str]) -> List[Dict]
    
    # Utility
    def get_quantity_precision(symbol: str, instrument_type: str) -> int
```

## 4-Mode Trading System

The system supports four trading modes via `BrokerModeAdapter`:

| Mode | Account Type | Data Source | Description | IBKR Port |
|------|-------------|-------------|-------------|-----------|
| **mock_mock** | Mock | Mock | Fully simulated, fastest testing | N/A |
| **mock_live** | Mock | Live (IBKR) | Strategy testing with real prices | 4004 (paper) |
| **paper_live** | Paper (IBKR) | Live (IBKR) | True IBKR paper trading | 4004 |
| **live_live** | Live (IBKR) | Live (IBKR) | Production - **REAL MONEY** | 4001 |

See [BrokerModeAdapter documentation](../../services/brokers/adapters/mode_adapter.py) for implementation details.

## Standard Order Schema

All brokers accept orders in a **universal internal format**:

```python
{
    # Required fields
    'order_id': str,              # Internal tracking ID
    'strategy_id': str,           # Strategy identifier
    'instrument': str,            # Symbol (e.g., "AAPL", "EURUSD", "BTC")
    'instrument_type': str,       # "STOCK" | "OPTION" | "FOREX" | "FUTURE" | "CRYPTO"
    'direction': str,             # "LONG" | "SHORT"
    'quantity': float,            # Quantity (can be fractional for forex/crypto)
    'order_type': str,            # "MARKET" | "LIMIT"
    
    # Optional fields
    'limit_price': float,         # For LIMIT orders
    'stop_price': float,          # For STOP orders
    'price': float,               # Market price hint (for mock broker)
    'action': str,                # "ENTRY" | "EXIT" (not sent to broker)
    
    # For options
    'legs': [                     # Multi-leg option orders
        {
            'strike': float,
            'expiry': str,        # Format: "YYYYMMDD"
            'right': str,         # "C" | "P" | "CALL" | "PUT"
            'action': str,        # "BUY" | "SELL"
            'quantity': int
        }
    ],
    
    # For futures
    'expiry': str,                # "YYYYMMDD"
    'exchange': str,              # "NYMEX", "COMEX", etc.
    'underlying': str             # For derivatives
}
```

Each broker implementation translates this internal format to its broker-specific schema.

## Exception Hierarchy

All brokers raise exceptions from the common hierarchy:

```
BrokerError (base)
├── BrokerConnectionError      # Connection failures
├── BrokerAPIError            # General API errors
├── AuthenticationError       # Auth failures
├── BrokerTimeoutError        # Timeout errors
├── OrderRejectedError        # Order rejection
├── OrderNotFoundError        # Order not found
├── InsufficientFundsError    # Insufficient funds
├── InvalidSymbolError        # Invalid symbol
└── MarketClosedError         # Market closed
```

See [services/brokers/exceptions.py](../../services/brokers/exceptions.py) for complete definitions.

## Configuration Examples

### Mock Broker
```python
config = {
    "broker": "Mock",
    "account_id": "Mock_Paper",
    "initial_equity": 100000.0
}
```

### IBKR Broker
```python
# Paper Trading
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4004,           # Paper account
    "client_id": 1,
    "account_id": "DU123456"
}

# Live Trading (⚠️ REAL MONEY)
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4001,           # Live account
    "client_id": 1,
    "account_id": "U123456"
}
```

### Coinbase Broker
```python
# Sandbox
config = {
    "broker": "Coinbase",
    "api_key": "organizations/xxx/apiKeys/yyy",
    "api_secret": "-----BEGIN EC PRIVATE KEY-----\n...",
    "sandbox": True
}

# Production (⚠️ REAL MONEY)
config = {
    "broker": "Coinbase",
    "api_key": "organizations/xxx/apiKeys/yyy",
    "api_secret": "-----BEGIN EC PRIVATE KEY-----\n...",
    "sandbox": False
}
```

## Getting Started

### 1. Choose Your Broker

- **Mock:** For fast development and unit testing
- **IBKR Paper:** For realistic paper trading with real market data
- **IBKR Live:** For production trading (requires funded account)
- **Coinbase Sandbox:** For crypto testing
- **Coinbase Production:** For live crypto trading

### 2. Set Up Credentials

Create a `.env` file with broker credentials (see [SETUP.md](../../SETUP.md)).

### 3. Create Trading Account Document

Add account to MongoDB `trading_accounts` collection (see individual broker docs).

### 4. Test Connection

```python
from services.brokers.factory import BrokerFactory

config = {...}  # See broker-specific docs
broker = BrokerFactory.create_broker(config)

if broker.connect():
    print("✅ Connected successfully")
    balance = broker.get_account_balance()
    print(f"Account balance: ${balance['equity']:,.2f}")
else:
    print("❌ Connection failed")
```

## Testing Strategy

### Progressive Testing Path

1. **mock_mock:** Develop and unit test with instant fills
2. **mock_live:** Test strategy logic with real market data
3. **paper_live:** Test full integration on IBKR paper account
4. **live_live:** Deploy to production (after thorough testing)

### Test Files

- Unit tests: `tests/brokers/`
- Integration tests: `tests/integration/`
- Sample signals: `tests/sample_signals/`

## Security Best Practices

### Credentials

- ✅ Store credentials in `.env` file
- ✅ Use environment variables
- ✅ Never commit credentials to git
- ✅ Use MongoDB encrypted fields for sensitive data

### Live Trading Protection

- ✅ Always test in paper mode first
- ✅ Use position limits and risk controls
- ✅ Enable kill switches in production
- ✅ Monitor all live trades
- ✅ Set up alerts for errors/rejections

### API Keys

- ✅ Use separate keys for sandbox/production
- ✅ Restrict API key permissions
- ✅ Rotate keys regularly
- ✅ Monitor API usage

## Troubleshooting

### Connection Issues

**IBKR:**
- Ensure IB Gateway or TWS is running
- Check port number (4004 for paper, 4001 for live)
- Verify API connections enabled in TWS settings
- Check client_id is not already in use

**Coinbase:**
- Verify API key format
- Check private key PEM format
- Ensure sandbox flag matches environment
- Check API rate limits

**Mock:**
- Verify MongoDB connection (for position tracking)
- Check `MONGODB_URI` environment variable

### Order Rejections

Common causes:
- Insufficient buying power
- Invalid symbol
- Market closed
- Invalid order parameters
- Risk limits exceeded

Check logs for detailed rejection reasons.

### Data Issues

**IBKR:**
- Subscribe to market data in TWS
- Check market data type (1=live, 3=delayed, 4=delayed frozen)
- Verify instrument is traded on requested exchange

**Mock:**
- Ensure `price` field provided for MARKET orders in mock_mock mode
- For mock_live mode, verify real broker connection for pricing

## Performance Considerations

### Connection Pooling

- Mock: Instant, no network overhead
- IBKR: Reuse connections, avoid frequent connect/disconnect
- Coinbase: REST API, no persistent connection

### Rate Limits

- IBKR: ~50 requests/second
- Coinbase: Varies by endpoint (check API docs)
- Mock: No limits

### Latency

- Mock: <1ms (instant fills)
- IBKR: 10-100ms (depends on network)
- Coinbase: 100-500ms (REST API)

## Contributing

When adding a new broker:

1. Implement `AbstractBroker` interface
2. Add exception handling
3. Implement quantity precision logic
4. Create comprehensive documentation
5. Add unit tests
6. Add integration tests
7. Update this README

See existing brokers for reference implementations.

## Further Reading

- [Mock Broker Documentation](mock.md)
- [IBKR Gateway Documentation](ibkr_gateway.md)
- [Coinbase Broker Documentation](coinbase.md)
- [Broker Factory Code](../../services/brokers/factory.py)
- [Abstract Broker Interface](../../services/brokers/base.py)
- [Exception Definitions](../../services/brokers/exceptions.py)
- [Mode Adapter](../../services/brokers/adapters/mode_adapter.py)
