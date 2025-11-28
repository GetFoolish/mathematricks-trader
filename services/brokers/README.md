# Shared Broker Library

Multi-broker trading library for the Mathematricks Trading System. Provides a unified interface for order execution and account data retrieval across different brokers.

## Supported Brokers

| Broker | Markets | Status |
|--------|---------|--------|
| **IBKR** (Interactive Brokers) | US Stocks, Options, Futures, Forex | ✅ Implemented |
| **Zerodha** (Kite Connect) | Indian Stocks, Derivatives, Commodities | ✅ Implemented |

## Quick Start

### 1. Install Dependencies

```bash
# For IBKR
pip install ib_insync

# For Zerodha
pip install kiteconnect
```

### 2. Create a Broker Instance

```python
from brokers import BrokerFactory

# IBKR Example
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 7497,  # Paper trading
    "client_id": 1,
    "account_id": "DU123456"
}

broker = BrokerFactory.create_broker(config)
broker.connect()
```

### 3. Place Orders

```python
# Market order
order_result = broker.place_order({
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 100,
    "order_type": "MARKET"
})

print(f"Order ID: {order_result['broker_order_id']}")
```

### 4. Get Account Data

```python
# Account balance
balance = broker.get_account_balance()
print(f"Equity: ${balance['equity']:,.2f}")

# Open positions
positions = broker.get_open_positions()
for pos in positions:
    print(f"{pos['symbol']}: {pos['quantity']} @ ${pos['avg_price']}")

# Margin info
margin = broker.get_margin_info()
print(f"Margin Used: {margin['margin_utilization_pct']:.1f}%")
```

## Architecture

### AbstractBroker Interface

All brokers implement the `AbstractBroker` interface:

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
```

### Exception Hierarchy

```
BrokerError (base)
├── BrokerConnectionError
├── BrokerAPIError
├── AuthenticationError
├── BrokerTimeoutError
├── OrderRejectedError
├── OrderNotFoundError
├── InsufficientFundsError
├── InvalidSymbolError
└── MarketClosedError
```

## Broker Configurations

### IBKR (Interactive Brokers)

```python
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 7497,      # 7497=TWS Paper, 7496=TWS Live, 4002=Gateway Paper, 4001=Gateway Live
    "client_id": 1,    # Unique client ID (1-32)
    "account_id": "DU123456"
}
```

**Supported Instruments:**
- Stocks: `{"symbol": "AAPL", "instrument_type": "STOCK"}`
- Options: `{"underlying": "AAPL", "instrument_type": "OPTION", "legs": [...]}`
- Futures: `{"symbol": "CL", "instrument_type": "FUTURE", "expiry": "20250317"}`
- Forex: `{"symbol": "EURUSD", "instrument_type": "FOREX"}`

### Zerodha (Kite Connect)

```python
config = {
    "broker": "Zerodha",
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "access_token": "your_access_token",  # Obtain via manual login flow
    "user_id": "AB1234"
}
```

**Supported Instruments:**
- Stocks: `{"symbol": "RELIANCE", "exchange": "NSE", "product": "CNC"}`
- Intraday: `{"symbol": "RELIANCE", "exchange": "NSE", "product": "MIS"}`
- Futures/Options: `{"symbol": "NIFTY25JAN23500CE", "exchange": "NFO", "product": "NRML"}`

**Note:** Zerodha requires manual login flow to obtain `access_token`. See: https://kite.trade/docs/connect/v3/user/

## Adding a New Broker

Follow these steps to add support for a new broker:

### 1. Create Broker Directory

```bash
mkdir services/brokers/your_broker
touch services/brokers/your_broker/__init__.py
touch services/brokers/your_broker/your_broker_broker.py
```

### 2. Implement AbstractBroker

```python
# services/brokers/your_broker/your_broker_broker.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base import AbstractBroker
from exceptions import BrokerConnectionError, OrderRejectedError, ...

class YourBrokerBroker(AbstractBroker):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Initialize your broker's API client
        self.api_client = YourBrokerAPI(config['api_key'])

    def connect(self) -> bool:
        # Implement connection logic
        try:
            self.api_client.authenticate()
            return True
        except Exception as e:
            raise BrokerConnectionError(f"Failed to connect: {e}", broker_name="YourBroker")

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        # Implement order placement
        result = self.api_client.place_order(...)
        return {
            "broker_order_id": result.order_id,
            "status": "SUBMITTED",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Order submitted"
        }

    # Implement all other abstract methods...
```

### 3. Register with Factory

```python
# services/brokers/your_broker/__init__.py
from .your_broker_broker import YourBrokerBroker
__all__ = ['YourBrokerBroker']

# services/brokers/factory.py
from your_broker import YourBrokerBroker

class BrokerFactory:
    BROKERS = {
        "IBKR": IBKRBroker,
        "Zerodha": ZerodhaBroker,
        "YourBroker": YourBrokerBroker,  # Add here
    }
```

### 4. Update Package Exports

```python
# services/brokers/__init__.py
from .your_broker import YourBrokerBroker

__all__ = [
    ...
    'YourBrokerBroker',
]
```

### 5. Test Your Broker

```python
# Create test file: tests/test_your_broker.py
from brokers import BrokerFactory

def test_your_broker_connection():
    config = {
        "broker": "YourBroker",
        "api_key": "test_key",
        ...
    }
    broker = BrokerFactory.create_broker(config)
    assert broker.connect() == True

def test_your_broker_order():
    broker = ...
    result = broker.place_order({
        "symbol": "TEST",
        "side": "BUY",
        "quantity": 1,
        "order_type": "MARKET"
    })
    assert result['broker_order_id'] is not None
```

## Integration with Services

### ExecutionService

```python
from brokers import BrokerFactory

# Load broker config from MongoDB or environment
config = db['broker_configurations'].find_one({"account_id": "IBKR_Main"})
broker = BrokerFactory.create_broker(config)
broker.connect()

# Place order from Pub/Sub message
def process_order(order_data):
    result = broker.place_order({
        "symbol": order_data['instrument'],
        "side": order_data['direction'],
        "quantity": order_data['quantity'],
        "order_type": "MARKET"
    })
    return result
```

### AccountDataService

```python
from brokers import BrokerFactory

# Multi-broker support
brokers = {
    "IBKR_Main": BrokerFactory.create_broker(ibkr_config),
    "Zerodha_India": BrokerFactory.create_broker(zerodha_config)
}

for name, broker in brokers.items():
    broker.connect()

# Get account state from all brokers
def get_total_account_state():
    total_equity = 0
    for broker in brokers.values():
        balance = broker.get_account_balance()
        total_equity += balance['equity']

    return {"total_equity": total_equity}
```

## Error Handling

Always wrap broker calls in try-except blocks:

```python
from brokers.exceptions import (
    BrokerConnectionError,
    OrderRejectedError,
    InsufficientFundsError
)

try:
    result = broker.place_order(order)
except BrokerConnectionError as e:
    logger.error(f"Connection lost: {e}")
    # Attempt reconnect
    broker.connect()
except OrderRejectedError as e:
    logger.error(f"Order rejected: {e.rejection_reason}")
    # Handle rejection (notify user, retry, etc.)
except InsufficientFundsError as e:
    logger.error(f"Insufficient funds: required={e.required}, available={e.available}")
    # Reduce order size or skip
except BrokerAPIError as e:
    logger.error(f"API error: {e.error_code}")
    # General API error handling
```

## Testing

### Unit Tests

```bash
cd services/brokers
pytest tests/
```

### Integration Tests

```bash
# Requires TWS/Gateway running for IBKR
# Requires valid access token for Zerodha
pytest tests/integration/
```

### Mock Broker for Testing

```python
from brokers.base import AbstractBroker

class MockBroker(AbstractBroker):
    """Mock broker for testing without real broker connection"""
    def __init__(self, config):
        super().__init__(config)
        self.orders = {}

    def connect(self):
        return True

    def place_order(self, order):
        order_id = f"MOCK_{len(self.orders) + 1}"
        self.orders[order_id] = order
        return {
            "broker_order_id": order_id,
            "status": "FILLED",
            "timestamp": "2025-01-01T00:00:00Z"
        }

# Use in tests
BrokerFactory.register_broker("Mock", MockBroker)
broker = BrokerFactory.create_broker({"broker": "Mock"})
```

## FAQ

### Q: How do I handle broker-specific features?

A: Use type checking to access broker-specific methods:

```python
from brokers import IBKRBroker, ZerodhaBroker

broker = BrokerFactory.create_broker(config)

if isinstance(broker, IBKRBroker):
    # IBKR-specific: Set up market data subscription
    broker.ib.reqMarketDataType(4)  # Delayed frozen data
elif isinstance(broker, ZerodhaBroker):
    # Zerodha-specific: Get holdings
    holdings = broker.kite.holdings()
```

### Q: How do I use multiple brokers simultaneously?

A: Create multiple broker instances:

```python
brokers = {
    "US": BrokerFactory.create_broker(ibkr_config),
    "India": BrokerFactory.create_broker(zerodha_config)
}

for broker in brokers.values():
    broker.connect()

# Route orders to appropriate broker
def place_order(symbol, market):
    broker = brokers[market]
    return broker.place_order({...})
```

### Q: How do I switch brokers without code changes?

A: Use environment variables:

```python
from brokers import create_broker_from_env

# Reads BROKER_NAME from environment
broker = create_broker_from_env()
```

## Support

For issues or questions:
- Check logs in `logs/execution_service.log` or `logs/account_data_service.log`
- Review broker-specific documentation:
  - IBKR: https://ib-insync.readthedocs.io/
  - Zerodha: https://kite.trade/docs/connect/v3/
- File an issue in the repository

## License

Internal use only - Mathematricks Trading System
