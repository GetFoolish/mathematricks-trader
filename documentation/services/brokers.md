# Broker Service Architecture

This document describes the broker abstraction layer that enables multi-broker support across the Mathematricks Trading System.

## Overview

The broker service provides a unified interface for interacting with multiple brokers (IBKR, Binance, Oanda, etc.) while supporting three trading modes: `paper_mock`, `paper_live`, and `live`.

**Location**: `services/brokers/`

**Key Components**:
- **AbstractBroker** - Base class defining broker interface
- **BrokerFactory** - Creates broker instances from configuration
- **BrokerModeAdapter** - Routes orders based on trading mode
- **Broker Implementations** - IBKR, Mock, Binance, Bybit, Alpaca, Oanda

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Execution Service                        │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │           BrokerModeAdapter                        │    │
│  │  (Routes based on mode: paper_mock/paper_live/live)│    │
│  └──────────┬──────────────────────────┬──────────────┘    │
│             │                          │                    │
│    ┌────────▼────────┐        ┌───────▼────────┐          │
│    │  Real Broker    │        │  Mock Broker   │          │
│    │  (IBKR, etc.)   │        │  (Simulated)   │          │
│    └─────────────────┘        └────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Mode-Based Routing

| Mode | Market Data | Orders Routed To | Use Case |
|------|-------------|------------------|----------|
| `paper_mock` | Mock | Mock Broker | Development/testing |
| `paper_live` | Real Broker | Mock Broker | Strategy testing with real data |
| `live` | Real Broker | Real Broker | Production trading |

---

## AbstractBroker Interface

All broker implementations inherit from `AbstractBroker` (in `services/brokers/base.py`):

```python
class AbstractBroker(ABC):
    """Base class for all broker implementations"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from broker"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status"""
        pass
    
    @abstractmethod
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Place an order"""
        pass
    
    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get order status"""
        pass
    
    @abstractmethod
    def get_account_balance(self, account_id: str = None) -> Dict[str, Any]:
        """Get account balance"""
        pass
    
    @abstractmethod
    def get_positions(self, account_id: str = None) -> List[Dict[str, Any]]:
        """Get open positions"""
        pass
    
    @abstractmethod
    def get_market_price(self, symbol: str, instrument_type: str) -> float:
        """Get current market price (for paper_live mode)"""
        pass
```

---

## Broker Implementations

### 1. IBKR Broker (`ibkr/ibkr_broker.py`)

**Status**: ✅ Fully implemented  
**Library**: `ib_insync`  
**Supports**: Stocks, Options, Forex, Futures, Crypto

**Configuration**:
```python
{
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4002,  # Paper: 4002, Live: 4001
    "client_id": 1,
    "account_id": "DU1234567"
}
```

**Features**:
- Real-time market data (type 1) with smart fallback (→ 3 → 4)
- Contract qualification and validation
- Multi-asset support (stocks, options, forex, futures, crypto)
- Spread and data quality metrics
- Connection monitoring and auto-reconnect

**Key Methods**:
- `get_market_price()` - Fetches live prices for paper_live mode
- `_create_contract()` - Creates IB contract objects
- `_qualify_contract()` - Validates contracts with IBKR

**See Also**: [IBKR Gateway Setup](../brokers/ibkr_gateway.md)

---

### 2. Mock Broker (`mock/mock_broker.py`)

**Status**: ✅ Fully implemented  
**Library**: None (pure Python simulation)  
**Supports**: All instrument types (simulated)

**Features**:
- Instant order fills at specified price
- Simulated account balances
- Position tracking
- Configurable slippage and commission
- Read-only mode for paper_live

**Configuration**:
```python
{
    "broker": "Mock",
    "account_id": "Mock_Paper",
    "initial_balance": 100000.0,
    "read_only": True  # Set to True in paper_live mode
}
```

**Behavior**:
- **Normal mode**: Updates balances, accepts all orders
- **Read-only mode** (paper_live): Simulates fills but marks account as read-only for balance queries

**Use Cases**:
- Development without broker connectivity
- Weekend/after-hours testing
- Paper trading with instant fills
- Backend for paper_live mode

---

### 3. Binance Broker (`binance/binance_broker.py`)

**Status**: ⚠️ Partial implementation  
**Library**: `python-binance`  
**Supports**: Crypto spot trading

**Configuration**:
```python
{
    "broker": "Binance",
    "api_key": "...",
    "api_secret": "...",
    "testnet": True  # Use testnet for paper trading
}
```

---

### 4. Other Brokers

- **Bybit** (`bybit/`) - Crypto derivatives
- **Alpaca** (`alpaca/`) - US stocks commission-free
- **Oanda** (`oanda/`) - Forex trading

**Status**: Stub implementations (to be completed)

---

## BrokerFactory

Creates broker instances from configuration dictionaries.

**Location**: `services/brokers/factory.py`

**Usage**:
```python
from brokers import BrokerFactory

# Create IBKR broker
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4002,
    "client_id": 1
}
broker = BrokerFactory.create_broker(config)
broker.connect()
```

**Supported Brokers**:
- `IBKR` → `IBKRBroker`
- `Mock` → `MockBroker`
- `Binance` → `BinanceBroker`
- `Bybit` → `BybitBroker`
- `Alpaca` → `AlpacaBroker`
- `Oanda` → `OandaBroker`

---

## BrokerModeAdapter

Routes orders to appropriate broker based on trading mode.

**Location**: `services/brokers/adapters/mode_adapter.py`

**Initialization**:
```python
from brokers.adapters import BrokerModeAdapter

adapter = BrokerModeAdapter(
    mode="paper_live",
    real_broker=ibkr_broker,
    mock_broker=mock_broker
)
```

**Key Method**: `place_order()`

```python
def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
    if self.mode == "live":
        # Real money - send to real broker
        return self.real_broker.place_order(order)
    
    elif self.mode == "paper_live":
        # Enrich with real pricing, then send to mock
        enriched_order = self._enrich_with_real_pricing(order)
        return self.mock_broker.place_order(enriched_order)
    
    elif self.mode == "paper_mock":
        # Use mock pricing
        return self.mock_broker.place_order(order)
```

**Paper Live Flow**:
1. Get real market price from real broker
2. Add price to order: `order['price'] = real_price`
3. Send enriched order to mock broker
4. Mock broker fills instantly at real price

---

## Broker Pool Architecture

The execution service maintains a **broker pool** to support multiple accounts/brokers simultaneously.

**Location**: `services/execution_service/execution_main.py`

```python
# Broker pool: {account_id: broker_instance}
broker_pool = {
    "IBKR-TESTING-ACCOUNT": ibkr_broker,
    "Mock_Paper": mock_broker,
    "Binance-Main": binance_broker
}

def get_broker_for_account(account_id: str):
    """Route to correct broker based on account"""
    return broker_pool.get(account_id)
```

**Benefits**:
- Multi-broker support in single service
- Route orders to correct broker automatically
- Different modes per account (one account in paper_live, another in live)

---

## Order Data Format

All brokers accept standardized order format:

```javascript
{
  "order_id": "ord_20260119_123456",
  "account": "IBKR-TESTING-ACCOUNT",
  "instrument": "AAPL",
  "instrument_type": "STOCK",
  "action": "BUY",  // or "SELL", "EXIT"
  "quantity": 10,
  "order_type": "MARKET",  // or "LIMIT"
  "price": 230.50,  // Optional, for limit orders or paper_live enrichment
  "limit_price": 231.00,  // For limit orders
  "stop_price": 229.00,  // For stop orders
  "time_in_force": "DAY"  // "DAY", "GTC", "IOC", "FOK"
}
```

**Broker Response**:
```javascript
{
  "broker_order_id": "123456789",
  "broker_confirmation_id": "IB_CONF_987654",
  "status": "FILLED",  // "SUBMITTED", "FILLED", "PARTIAL_FILL", "REJECTED"
  "filled": 10,
  "remaining": 0,
  "avg_fill_price": 230.52,
  "fills": [
    {
      "time": "2026-01-19T14:30:05Z",
      "price": 230.52,
      "quantity": 10,
      "commission": 1.50,
      "execution_id": "exec_001"
    }
  ]
}
```

---

## Precision Service

Manages quantity precision (decimal places) for different instruments/brokers.

**Location**: `services/cerebro_service/precision_service.py`

**Purpose**: Determine how many decimal places to use for order quantities:
- Stocks: 0 decimals (whole shares)
- Crypto: 8 decimals (e.g., 0.00123456 BTC)
- Forex: 0-2 decimals

**Storage**: MongoDB collection `precision_cache`

**Usage**:
```python
from services.cerebro_service.precision_service import get_precision_service

precision_service = get_precision_service()

# Get precision for AAPL on IBKR
precision = precision_service.get_precision(
    source="IBKR-TESTING-ACCOUNT",
    symbol="AAPL",
    broker_instance=broker
)
# Returns: 0 (whole shares)

# Round quantity to correct precision
quantity = precision_service.round_to_precision(10.5, precision)
# Returns: 10 (rounded to 0 decimal places)
```

**Caching**: Precision values are cached for 24 hours to minimize broker queries.

---

## Exception Handling

**Location**: `services/brokers/exceptions.py`

All brokers raise standardized exceptions:

```python
try:
    result = broker.place_order(order)
except BrokerConnectionError as e:
    # Broker is disconnected
    logger.error(f"Connection lost: {e}")
    
except OrderRejectedError as e:
    # Order rejected by broker
    logger.error(f"Order rejected: {e.rejection_reason}")
    
except InvalidSymbolError as e:
    # Symbol not found or invalid
    logger.error(f"Invalid symbol: {e}")
    
except InsufficientFundsError as e:
    # Not enough buying power
    logger.error(f"Insufficient funds: {e}")
    
except BrokerTimeoutError as e:
    # Request timed out
    logger.error(f"Timeout: {e}")
    
except BrokerAPIError as e:
    # Generic API error
    logger.error(f"API error: {e.error_code} - {e}")
```

---

## Testing Brokers

### Unit Tests

**Location**: `tests/unit/test_brokers/`

```bash
# Test all brokers
pytest tests/unit/test_brokers/

# Test specific broker
pytest tests/unit/test_brokers/test_ibkr_broker.py
pytest tests/unit/test_brokers/test_mock_broker.py
```

### Integration Tests

**Requirements**:
- IB Gateway running (for IBKR tests)
- Paper trading account configured

```bash
# Run integration tests
pytest tests/integration/test_broker_integration.py
```

### Manual Testing

Use quick test script:
```bash
# Send test signal (uses configured broker)
./scripts/quick_test.sh send AAPL

# Watch logs
./scripts/quick_test.sh logs
```

---

## Adding New Brokers

To add a new broker:

1. **Create broker class** in `services/brokers/<broker_name>/`
2. **Inherit from AbstractBroker** and implement all methods
3. **Add to BrokerFactory** in `factory.py`
4. **Add configuration** to `trading_accounts` in MongoDB
5. **Test** with paper_mock mode first

**Example Structure**:
```
services/brokers/
  <broker_name>/
    __init__.py
    <broker_name>_broker.py
    README.md  # Broker-specific docs
```

**Minimal Implementation**:
```python
from services.brokers.base import AbstractBroker

class NewBroker(AbstractBroker):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Initialize broker client
    
    def connect(self) -> bool:
        # Connect to broker API
        pass
    
    def place_order(self, order: Dict) -> Dict:
        # Place order via broker API
        pass
    
    # ... implement all abstract methods
```

---

## Configuration Reference

### MongoDB Account Configuration

```javascript
{
  "account_id": "IBKR-TESTING-ACCOUNT",
  "broker": "IBKR",
  "mode": "paper_live",
  "market_data_type": 1,
  "status": "ACTIVE",
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4002,
    "client_id": 1
  },
  "strategy_ids": ["UPRO_NewYork", "SPY_NewYork"],
  "balance": 100000.0,
  "open_positions": []
}
```

### Environment Variables

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017/

# Telegram (optional)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Live Trading Safety
ALLOW_LIVE_TRADING=false  # Must be true for live mode

# IBKR (handled via MongoDB authentication_details)
# No environment variables needed for IBKR
```

---

## Troubleshooting

### Connection Issues

**IBKR Broker**:
```bash
# Check IB Gateway is running
docker ps | grep ibgateway

# Check connection in logs
docker logs mathematricks-trader-execution-service-1 | grep "Connected to IBKR"
```

**Solution**: Ensure IB Gateway is running and port is correct (4002 for paper, 4001 for live)

### Order Rejections

**Common Causes**:
1. Invalid symbol
2. Insufficient funds
3. Market closed (for market orders)
4. Contract not qualified

**Debug**:
```bash
# Check execution logs
tail -f logs/execution_service.log | grep "rejected"
```

### Mock Broker Not Filling

**Check**: Ensure order has `price` field set (especially in paper_live mode)

```python
# Order should have price from BrokerModeAdapter
order['price'] = 230.50  # Set by _enrich_with_real_pricing()
```

---

## Performance Considerations

1. **Connection Pooling**: Brokers maintain persistent connections (no reconnect per order)
2. **Precision Caching**: Precision queries cached for 24 hours in MongoDB
3. **Async Design**: Broker operations are non-blocking where possible
4. **Timeout Handling**: All broker calls have timeouts (default: 30s)

---

## See Also

- [IBKR Gateway Setup](../brokers/ibkr_gateway.md)
- [Trading Modes](../concepts/trading_modes.md)
- [Execution Service](../execution_service.md)
- [IBKR Integration Summary](../IBKR_INTEGRATION_SUMMARY.md)
