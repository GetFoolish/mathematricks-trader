# Brokers Abstraction Layer

## Overview

The Brokers abstraction layer provides a unified interface for interacting with multiple broker integrations. All brokers implement the same contract (AbstractBroker interface), allowing the system to work with IBKR, Zerodha, or Mock brokers interchangeably.

## Location

`/services/brokers/`

## Key Responsibilities

1. Provide unified broker interface (AbstractBroker)
2. Implement broker-specific connections and API calls
3. Handle broker authentication and sessions
4. Place orders with appropriate broker
5. Query account balances and positions
6. Calculate margin requirements
7. Handle broker-specific error conditions
8. Support multiple asset classes per broker

## Main Files

### factory.py
- BrokerFactory for creating broker instances
- Broker configuration parsing
- Connection management

### base.py
- AbstractBroker interface definition
- Common broker methods
- Enums for order types, sides, statuses

### exceptions.py
- Broker-specific exceptions
- Error handling utilities

### ibkr/ibkr_broker.py
- Interactive Brokers implementation
- Uses `ib_insync` library
- Supports stocks, futures, options, forex, crypto

### zerodha/zerodha_broker.py
- Zerodha/Kite implementation
- Uses `kiteconnect` library
- NSE/BSE instruments

### mock/mock_broker.py
- Mock broker for testing
- In-memory order book
- Simulated fills and rejections

## AbstractBroker Interface

Located in `base.py`

### Core Methods

```python
class AbstractBroker(ABC):
    # CONNECTION MANAGEMENT
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker"""

    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to broker"""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected"""

    # ACCOUNT OPERATIONS
    @abstractmethod
    def get_account_balance(self) -> Dict:
        """Get account balances and buying power"""

    @abstractmethod
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""

    # ORDER OPERATIONS
    @abstractmethod
    def place_order(self, order: Dict) -> Dict:
        """Place order with broker"""

    @abstractmethod
    def get_order_status(self, order_id: str) -> str:
        """Query order status"""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order"""

    @abstractmethod
    def modify_order(self, order_id: str, updates: Dict) -> Dict:
        """Modify existing order"""

    # MARGIN OPERATIONS
    @abstractmethod
    def get_order_margin_impact(self, order: Dict) -> Dict:
        """Calculate margin requirement for order"""
```

## BrokerFactory

Located in `factory.py`

### Usage

```python
from brokers import BrokerFactory

# Create IBKR broker
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4002,
    "client_id": 1,
    "account_id": "DU123456"
}

broker = BrokerFactory.create_broker(config)
broker.connect()

# Place order
order = broker.place_order({
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 100,
    "order_type": "MARKET"
})

print(f"Order ID: {order['order_id']}")
```

### Supported Brokers

**BrokerFactory.create_broker(config)**

- `config["broker"] = "IBKR"` → Returns IBKRBroker
- `config["broker"] = "Zerodha"` → Returns ZerodhaBroker
- `config["broker"] = "Mock"` → Returns MockBroker

## IBKR Broker

Located in `ibkr/ibkr_broker.py`

### Features

- Uses `ib_insync` library
- Connects via TWS or IB Gateway
- Supports multiple asset classes
- Real-time position tracking
- Margin preview with whatIfOrder
- Handles connection retries

### Configuration

```python
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",        # TWS/Gateway host
    "port": 4002,                # Paper: 4002, Live: 4001
    "client_id": 1,              # Unique client ID
    "account_id": "DU123456",    # Account number
    "readonly": False            # Optional
}
```

### Asset Classes Supported

**Stocks (STK)**
```python
order = {
    "symbol": "AAPL",
    "secType": "STK",
    "exchange": "SMART",
    "currency": "USD",
    "side": "BUY",
    "quantity": 100,
    "order_type": "MARKET"
}
```

**Futures (FUT)**
```python
order = {
    "symbol": "GC",              # Gold futures
    "secType": "FUT",
    "exchange": "NYMEX",
    "currency": "USD",
    "lastTradeDateOrContractMonth": "202412",
    "side": "BUY",
    "quantity": 1,
    "order_type": "MARKET"
}
```

**Options (OPT)**
```python
order = {
    "symbol": "SPY",
    "secType": "OPT",
    "exchange": "SMART",
    "currency": "USD",
    "lastTradeDateOrContractMonth": "20241220",
    "strike": 450.0,
    "right": "C",                # C=Call, P=Put
    "multiplier": "100",
    "side": "BUY",
    "quantity": 1,
    "order_type": "MARKET"
}
```

**Forex (CASH)**
```python
order = {
    "symbol": "EUR",
    "secType": "CASH",
    "exchange": "IDEALPRO",
    "currency": "USD",           # EUR/USD
    "side": "BUY",
    "quantity": 20000,
    "order_type": "MARKET"
}
```

**Crypto (CRYPTO)**
```python
order = {
    "symbol": "BTC",
    "secType": "CRYPTO",
    "exchange": "PAXOS",
    "currency": "USD",
    "side": "BUY",
    "cashQty": 10000.00,         # USD amount for crypto
    "order_type": "MARKET"
}
```

### Order Types

**Market Order**
```python
{
    "order_type": "MARKET",
    "tif": "DAY"                 # Time in force
}
```

**Limit Order**
```python
{
    "order_type": "LIMIT",
    "limit_price": 450.00,
    "tif": "GTC"                 # Good til cancelled
}
```

**Stop Order**
```python
{
    "order_type": "STOP",
    "stop_price": 440.00,
    "tif": "DAY"
}
```

**Stop-Limit Order**
```python
{
    "order_type": "STOP_LIMIT",
    "stop_price": 440.00,
    "limit_price": 439.00,
    "tif": "GTC"
}
```

### Margin Preview

IBKR supports margin impact calculation before placing orders:

```python
margin_impact = broker.get_order_margin_impact({
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 100,
    "order_type": "MARKET"
})

print(f"Initial Margin: ${margin_impact['initial_margin']}")
print(f"Maintenance Margin: ${margin_impact['maintenance_margin']}")
```

Uses IBKR's `whatIfOrder` API internally.

### Connection Handling

**Intelligent Client ID Retry**
- If connection fails with client_id error
- Automatically tries client_ids 1-10
- Finds available client_id
- Prevents "duplicate client_id" errors

**Reconnection Logic**
- Automatic reconnection on disconnect
- Exponential backoff retry
- Preserves order state

### Key Methods

**connect()**
- Establishes IB connection
- Validates account access
- Sets up event handlers

**place_order(order_dict)**
- Creates IB contract
- Places order via `ib.placeOrder()`
- Returns order_id

**get_account_balance()**
- Queries account values
- Returns equity, cash, margin

**get_open_positions()**
- Fetches current positions
- Returns list of position dicts

**cancel_order(order_id)**
- Cancels pending order
- Returns success/failure

## Zerodha Broker

Located in `zerodha/zerodha_broker.py`

### Features

- Uses `kiteconnect` library
- NSE/BSE exchanges
- WebSocket for real-time data
- Margin API support

### Configuration

```python
config = {
    "broker": "Zerodha",
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "access_token": "your_access_token",
    "user_id": "your_user_id"
}
```

### Asset Classes Supported

**Equity**
```python
order = {
    "symbol": "RELIANCE",
    "exchange": "NSE",
    "side": "BUY",
    "quantity": 10,
    "order_type": "MARKET",
    "product": "CNC"             # Delivery
}
```

**Futures**
```python
order = {
    "symbol": "NIFTY24NOVFUT",
    "exchange": "NFO",
    "side": "BUY",
    "quantity": 50,              # Lot size = 50
    "order_type": "MARKET",
    "product": "NRML"            # Normal
}
```

**Options**
```python
order = {
    "symbol": "NIFTY2411924000CE",
    "exchange": "NFO",
    "side": "BUY",
    "quantity": 50,
    "order_type": "MARKET",
    "product": "NRML"
}
```

### Order Products

- **CNC** - Cash and Carry (delivery)
- **MIS** - Margin Intraday Square-off
- **NRML** - Normal (F&O)

### Lot Sizes

Zerodha requires orders in lot size multiples:
- Nifty 50 = 50 shares per lot
- Bank Nifty = 25 shares per lot
- Stocks = 1 share per lot

## Mock Broker

Located in `mock/mock_broker.py`

### Features

- In-memory order book
- Simulated fills
- Configurable delays
- Random rejections for testing
- No real money

### Configuration

```python
config = {
    "broker": "Mock",
    "initial_balance": 1000000.00,
    "fill_delay_seconds": 1.0,
    "rejection_rate": 0.05       # 5% rejection rate
}
```

### Usage

Perfect for testing without broker connection:

```python
broker = BrokerFactory.create_broker({"broker": "Mock"})
broker.connect()

order = broker.place_order({
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 100,
    "order_type": "MARKET"
})

# Simulates fill after 1 second
time.sleep(2)
status = broker.get_order_status(order["order_id"])
print(status)  # "FILLED"
```

## Order Enums

Located in `base.py`

### OrderSide
```python
class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"
```

### OrderType
```python
class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
```

### OrderStatus
```python
class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
```

### TimeInForce
```python
class TimeInForce(Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
```

## Exceptions

Located in `exceptions.py`

### BrokerConnectionError
Raised when connection to broker fails:
```python
try:
    broker.connect()
except BrokerConnectionError as e:
    print(f"Connection failed: {e}")
```

### OrderRejectedError
Raised when broker rejects order:
```python
try:
    broker.place_order(order)
except OrderRejectedError as e:
    print(f"Order rejected: {e.reason}")
```

### InsufficientFundsError
Raised when account has insufficient buying power:
```python
try:
    broker.place_order(large_order)
except InsufficientFundsError as e:
    print(f"Insufficient funds: {e}")
```

### InvalidSymbolError
Raised when symbol is not recognized:
```python
try:
    broker.place_order({"symbol": "INVALID", ...})
except InvalidSymbolError as e:
    print(f"Invalid symbol: {e}")
```

### BrokerAPIError
General broker API error:
```python
try:
    broker.get_account_balance()
except BrokerAPIError as e:
    print(f"API error: {e}")
```

### BrokerTimeoutError
Raised when broker operation times out:
```python
try:
    broker.place_order(order)
except BrokerTimeoutError as e:
    print(f"Timeout: {e}")
```

## Configuration

### Environment Variables

**IBKR Configuration**
```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=4002                    # Paper trading
IBKR_CLIENT_ID=1

# Credentials
IBKR_PAPER_USERNAME=your_username
IBKR_PAPER_PASSWORD=your_password
IBKR_LIVE_USERNAME=your_username
IBKR_LIVE_PASSWORD=your_password
IBKR_TOTP_SECRET=your_2fa_secret
```

**Zerodha Configuration**
```bash
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_ACCESS_TOKEN=your_access_token
ZERODHA_USER_ID=your_user_id
```

**Mock Broker**
```bash
USE_MOCK_BROKER=true              # Enable mock broker
```

## Error Handling

### Connection Errors
```python
broker = BrokerFactory.create_broker(config)

try:
    broker.connect()
except BrokerConnectionError as e:
    # Log error, retry later
    logger.error(f"Connection failed: {e}")
```

### Order Placement Errors
```python
try:
    order = broker.place_order(order_dict)
except OrderRejectedError as e:
    # Handle rejection
    logger.error(f"Order rejected: {e.reason}")
except InsufficientFundsError:
    # Insufficient margin
    logger.error("Insufficient funds")
except BrokerAPIError as e:
    # General API error
    logger.error(f"API error: {e}")
```

### Timeout Handling
```python
try:
    status = broker.get_order_status(order_id)
except BrokerTimeoutError:
    # Retry or mark as unknown
    logger.warning("Status query timed out")
```

## Testing

### Unit Tests

Test with Mock Broker:
```python
import pytest
from brokers import BrokerFactory

def test_order_placement():
    broker = BrokerFactory.create_broker({"broker": "Mock"})
    broker.connect()

    order = broker.place_order({
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": 100,
        "order_type": "MARKET"
    })

    assert order["order_id"] is not None
    assert order["status"] == "SUBMITTED"
```

### Integration Tests

Test with real IBKR connection:
```python
def test_ibkr_connection():
    config = {
        "broker": "IBKR",
        "host": "127.0.0.1",
        "port": 4002,
        "client_id": 1
    }

    broker = BrokerFactory.create_broker(config)
    assert broker.connect() == True

    balance = broker.get_account_balance()
    assert balance["equity"] > 0
```

## Dependencies

**IBKR:**
- `ib-insync>=0.9.86`
- Python 3.8+

**Zerodha:**
- `kiteconnect>=5.0.1`
- Python 3.8+

**Mock:**
- No external dependencies
- Pure Python

## Performance Considerations

**Connection Latency:**
- IBKR: 50-200ms (local TWS)
- Zerodha: 100-500ms (cloud API)
- Mock: <1ms (in-memory)

**Order Placement:**
- IBKR: 50-500ms
- Zerodha: 200-1000ms
- Mock: 1-2ms

**Position Queries:**
- IBKR: 50-100ms
- Zerodha: 100-300ms
- Mock: <1ms

## Related Documentation

- [Account Data Service](account_data_service.md) - Uses brokers for polling
- [Cerebro Service](cerebro_service.md) - Uses brokers for margin calculations
- [Execution Service](execution_service.md) - Uses brokers for order placement

## Common Issues

### IBKR Connection Failures

**"Socket connection broken"**
- Ensure TWS/IB Gateway is running
- Check port is correct (4002 for paper, 4001 for live)
- Verify API connections enabled in TWS settings

**"Duplicate client_id"**
- Use different client_id
- Or enable intelligent retry (auto tries IDs 1-10)
- Check for other processes using same client_id

**"Account not available"**
- Verify account number is correct
- Check account is active
- Ensure account has trading permissions

### Zerodha Connection Failures

**"Invalid access token"**
- Refresh access token (expires daily)
- Re-authenticate via login flow
- Check API key and secret

**"Order rejected - lot size"**
- Verify quantity is multiple of lot size
- Check contract specifications
- Use appropriate lot size for symbol

### Mock Broker Issues

**Orders not filling**
- Wait for fill_delay_seconds
- Check order status after delay
- Ensure order was submitted successfully

## Security Considerations

- Never log broker credentials
- Use environment variables for secrets
- Encrypt stored credentials
- Rotate API keys regularly
- Monitor unauthorized access
- Use read-only mode when possible

## Future Enhancements

1. **Additional Brokers**
   - Alpaca (US stocks/crypto)
   - Binance (crypto)
   - TD Ameritrade (US stocks/options)

2. **Enhanced Features**
   - Order batching
   - Multi-leg orders
   - Bracket orders (entry + stop + target)
   - Trailing stops

3. **Performance**
   - Connection pooling
   - Async order placement
   - Parallel position queries

4. **Monitoring**
   - Broker health checks
   - Latency tracking
   - Error rate monitoring
