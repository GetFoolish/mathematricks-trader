# Execution Service & Brokers

The Execution Service is responsible for placing orders with brokers and updating position tracking. It uses a unified broker abstraction layer to support multiple broker APIs (IBKR, Zerodha, Mock).

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Execution Flow](#execution-flow)
- [Broker Abstraction](#broker-abstraction)
- [Supported Brokers](#supported-brokers)
- [Configuration](#configuration)
- [Usage](#usage)
- [Error Handling](#error-handling)

---

## Overview

### Purpose
- **Order Execution**: Place orders with broker APIs
- **Status Tracking**: Update order status (PENDING → SUBMITTED → FILLED/REJECTED)
- **Position Management**: Update account positions in real-time
- **P&L Calculation**: Calculate realized P&L on EXIT orders
- **Execution Recording**: Update signal_store with execution data

### Technology Stack
- **Python 3.11+**
- **PyMongo** (MongoDB Change Streams)
- **ib-insync** (Interactive Brokers API)
- **kiteconnect** (Zerodha API)
- **Docker** (containerization)

### Location
```
services/execution_service/
├── execution_main.py           # Main service with Change Stream watcher
└── [uses broker library]

services/brokers/                # Unified broker library
├── base.py                     # AbstractBroker interface
├── factory.py                  # BrokerFactory
├── exceptions.py               # Broker exceptions
├── ibkr/                       # Interactive Brokers
│   ├── client.py
│   └── order_builder.py
├── zerodha/                    # Zerodha Kite Connect
│   ├── client.py
│   └── order_builder.py
└── mock/                       # Mock broker for testing
    └── client.py
```

---

## Architecture

### Service Model

The Execution Service operates as a **MongoDB Change Stream watcher** that:

1. Watches `trading_orders` collection for PENDING orders
2. Creates broker instance via BrokerFactory
3. Places order via broker API
4. Updates order status based on broker response
5. Updates account positions in `trading_accounts`
6. Updates `signal_store.legs[].execution` with execution data

### Design Philosophy
- **Broker-Agnostic**: Unified interface for all brokers
- **Event-Driven**: Uses MongoDB Change Streams (no polling)
- **Fault-Tolerant**: Retries on transient failures
- **Position-Aware**: Maintains accurate position tracking

---

## Execution Flow

### Flow Diagram

```
┌──────────────────────────────────────────┐
│ Cerebro Service                          │
│ - Creates trading_orders (status=PENDING)│
└──────────┬───────────────────────────────┘
           │ INSERT
           ↓
┌──────────────────────────────────────────┐
│ MongoDB: trading_orders                  │
│ {                                        │
│   order_id: "ord_001",                  │
│   status: "PENDING",                    │
│   account_id: "OANDA_MOCK",            │
│   instrument: "SPY",                    │
│   quantity: 100,                        │
│   order_type: "MARKET"                  │
│ }                                        │
└──────────┬───────────────────────────────┘
           │ Change Stream Event
           ↓
┌──────────────────────────────────────────┐
│ Execution Service                        │
│ - Detects PENDING order                 │
│ - Creates broker instance via Factory   │
│ - Places order via broker API           │
└──────────┬───────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│ BrokerFactory                            │
│ - Determines broker type (IBKR/Zerodha) │
│ - Creates IBKRClient or ZerodhaClient   │
└──────────┬───────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│ Broker API (IBKR/Zerodha/Mock)          │
│ - Receives order                         │
│ - Returns order ID + status             │
└──────────┬───────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│ Execution Service                        │
│ - Updates order status → SUBMITTED      │
│ - Waits for fill confirmation           │
│ - Updates order status → FILLED         │
│ - Updates account positions             │
│ - Updates signal_store execution        │
└──────────────────────────────────────────┘
```

### Step-by-Step Process

#### 1. Order Detection
```python
# Watch trading_orders for PENDING orders
pipeline = [
    {
        "$match": {
            "operationType": {"$in": ["insert", "update"]},
            "fullDocument.status": "PENDING"
        }
    }
]

for change in change_stream:
    order_doc = change['fullDocument']
    process_order(order_doc)
```

#### 2. Broker Instance Creation
```python
from brokers.factory import BrokerFactory

def process_order(order_doc):
    account_id = order_doc['account_id']
    broker_type = get_broker_type(account_id)  # "IBKR", "ZERODHA", "MOCK"

    # Create broker instance
    broker = BrokerFactory.create_broker(
        broker_type=broker_type,
        account_id=account_id
    )
```

#### 3. Order Placement
```python
    # Place order via broker API
    try:
        broker_order_id = broker.place_order(
            instrument=order_doc['instrument'],
            action=order_doc['action'],  # BUY/SELL
            quantity=order_doc['quantity'],
            order_type=order_doc['order_type'],  # MARKET/LIMIT
            price=order_doc.get('price')
        )

        # Update order status to SUBMITTED
        db.trading_orders.update_one(
            {'order_id': order_doc['order_id']},
            {'$set': {
                'status': 'SUBMITTED',
                'broker_order_id': broker_order_id,
                'submitted_at': datetime.now(timezone.utc)
            }}
        )

    except BrokerError as e:
        # Mark order as REJECTED
        db.trading_orders.update_one(
            {'order_id': order_doc['order_id']},
            {'$set': {
                'status': 'REJECTED',
                'rejection_reason': str(e)
            }}
        )
```

#### 4. Fill Confirmation
```python
    # Wait for fill (or poll for status)
    fill_data = broker.wait_for_fill(broker_order_id, timeout=60)

    if fill_data['status'] == 'FILLED':
        # Update order status to FILLED
        db.trading_orders.update_one(
            {'order_id': order_doc['order_id']},
            {'$set': {
                'status': 'FILLED',
                'quantity_filled': fill_data['quantity_filled'],
                'avg_fill_price': fill_data['avg_fill_price'],
                'filled_at': datetime.now(timezone.utc)
            }}
        )

        # Update account positions
        update_account_position(
            account_id=order_doc['account_id'],
            instrument=order_doc['instrument'],
            quantity_change=fill_data['quantity_filled'],
            price=fill_data['avg_fill_price']
        )

        # Update signal_store execution data
        update_signal_store_execution(order_doc, fill_data)
```

#### 5. Position Update (ENTRY)
```python
def update_account_position(account_id, instrument, quantity_change, price):
    account = db.trading_accounts.find_one({'account_id': account_id})

    # Find existing position or create new
    position = next(
        (p for p in account['open_positions'] if p['instrument'] == instrument),
        None
    )

    if position is None:
        # New position
        new_position = {
            'instrument': instrument,
            'quantity': quantity_change,
            'avg_entry_price': price,
            'unrealized_pnl': 0.0
        }
        db.trading_accounts.update_one(
            {'account_id': account_id},
            {'$push': {'open_positions': new_position}}
        )
    else:
        # Update existing position (weighted average for entry price)
        new_quantity = position['quantity'] + quantity_change
        new_avg_price = (
            (position['quantity'] * position['avg_entry_price']) +
            (quantity_change * price)
        ) / new_quantity

        db.trading_accounts.update_one(
            {
                'account_id': account_id,
                'open_positions.instrument': instrument
            },
            {'$set': {
                'open_positions.$.quantity': new_quantity,
                'open_positions.$.avg_entry_price': new_avg_price
            }}
        )
```

#### 6. Position Update (EXIT) + P&L Calculation
```python
def update_account_position_exit(account_id, instrument, quantity_change, exit_price):
    account = db.trading_accounts.find_one({'account_id': account_id})
    position = next(
        (p for p in account['open_positions'] if p['instrument'] == instrument),
        None
    )

    # Calculate realized P&L
    pnl = (exit_price - position['avg_entry_price']) * quantity_change

    # Update position
    new_quantity = position['quantity'] - quantity_change

    if new_quantity == 0:
        # Fully closed - remove from open_positions
        db.trading_accounts.update_one(
            {'account_id': account_id},
            {
                '$pull': {'open_positions': {'instrument': instrument}},
                '$inc': {'balances.realized_pnl': pnl}
            }
        )
    else:
        # Partially closed
        db.trading_accounts.update_one(
            {
                'account_id': account_id,
                'open_positions.instrument': instrument
            },
            {
                '$set': {'open_positions.$.quantity': new_quantity},
                '$inc': {'balances.realized_pnl': pnl}
            }
        )
```

---

## Broker Abstraction

### AbstractBroker Interface

All brokers implement a common interface defined in `services/brokers/base.py`:

```python
from abc import ABC, abstractmethod

class AbstractBroker(ABC):
    """Base class for all broker implementations"""

    @abstractmethod
    def connect(self):
        """Establish connection to broker API"""
        pass

    @abstractmethod
    def disconnect(self):
        """Close connection to broker API"""
        pass

    @abstractmethod
    def place_order(
        self,
        instrument: str,
        action: str,  # "BUY" or "SELL"
        quantity: int,
        order_type: str = "MARKET",
        price: float = None,
        stop_loss: float = None,
        take_profit: float = None
    ) -> str:
        """
        Place order with broker

        Returns:
            str: Broker order ID
        """
        pass

    @abstractmethod
    def get_order_status(self, broker_order_id: str) -> dict:
        """
        Get order status from broker

        Returns:
            {
                "status": "FILLED|PENDING|REJECTED",
                "quantity_filled": 100,
                "avg_fill_price": 450.30
            }
        """
        pass

    @abstractmethod
    def get_account_balance(self) -> dict:
        """
        Get account balance from broker

        Returns:
            {
                "equity": 500000.00,
                "cash": 250000.00,
                "margin_used": 50000.00,
                "margin_available": 200000.00
            }
        """
        pass

    @abstractmethod
    def get_open_positions(self) -> list:
        """
        Get open positions from broker

        Returns:
            [
                {
                    "instrument": "SPY",
                    "quantity": 100,
                    "avg_entry_price": 450.25,
                    "current_price": 455.50,
                    "unrealized_pnl": 525.00
                }
            ]
        """
        pass
```

### BrokerFactory

The `BrokerFactory` creates the appropriate broker instance based on account configuration:

```python
from brokers.factory import BrokerFactory
from brokers.ibkr.client import IBKRClient
from brokers.zerodha.client import ZerodhaClient
from brokers.mock.client import MockBrokerClient

class BrokerFactory:
    """Factory for creating broker instances"""

    @staticmethod
    def create_broker(broker_type: str, account_id: str) -> AbstractBroker:
        """
        Create broker instance

        Args:
            broker_type: "IBKR", "ZERODHA", "MOCK"
            account_id: Account identifier

        Returns:
            AbstractBroker instance
        """
        if broker_type == "IBKR":
            return IBKRClient(account_id)
        elif broker_type == "ZERODHA":
            return ZerodhaClient(account_id)
        elif broker_type == "MOCK":
            return MockBrokerClient(account_id)
        else:
            raise ValueError(f"Unsupported broker type: {broker_type}")
```

---

## Supported Brokers

### 1. Interactive Brokers (IBKR)

**Library**: `ib-insync`
**Connection**: IB Gateway (Docker container)

**Configuration**:
```python
# services/brokers/ibkr/client.py
class IBKRClient(AbstractBroker):
    def __init__(self, account_id):
        self.account_id = account_id
        self.ib = IB()

    def connect(self):
        self.ib.connect(
            host=os.getenv('IBKR_HOST', 'ib-gateway'),
            port=int(os.getenv('IBKR_PORT', '4002')),  # 4001=live, 4002=paper
            clientId=int(os.getenv('IBKR_CLIENT_ID', '1'))
        )

    def place_order(self, instrument, action, quantity, order_type="MARKET", price=None):
        contract = Stock(instrument, 'SMART', 'USD')
        order = MarketOrder(action, quantity) if order_type == "MARKET" else LimitOrder(action, quantity, price)

        trade = self.ib.placeOrder(contract, order)
        return trade.order.orderId
```

### 2. Zerodha Kite Connect

**Library**: `kiteconnect`
**API**: Zerodha Kite Connect REST API

**Configuration**:
```python
# services/brokers/zerodha/client.py
from kiteconnect import KiteConnect

class ZerodhaClient(AbstractBroker):
    def __init__(self, account_id):
        self.account_id = account_id
        self.kite = KiteConnect(api_key=os.getenv('ZERODHA_API_KEY'))

    def connect(self):
        access_token = os.getenv('ZERODHA_ACCESS_TOKEN')
        self.kite.set_access_token(access_token)

    def place_order(self, instrument, action, quantity, order_type="MARKET", price=None):
        order_params = {
            'tradingsymbol': instrument,
            'exchange': 'NSE',
            'transaction_type': action,
            'quantity': quantity,
            'order_type': order_type,
            'product': 'CNC'
        }

        if order_type == "LIMIT":
            order_params['price'] = price

        order_id = self.kite.place_order(**order_params)
        return order_id
```

### 3. Mock Broker (Testing)

**Purpose**: Simulated broker for testing without real money

**Features**:
- Instant fills at specified price
- Simulated account balances
- Position tracking in memory
- No external API calls

**Configuration**:
```python
# services/brokers/mock/client.py
class MockBrokerClient(AbstractBroker):
    def __init__(self, account_id):
        self.account_id = account_id
        self.positions = {}
        self.balance = 1000000.00  # $1M starting balance

    def place_order(self, instrument, action, quantity, order_type="MARKET", price=None):
        # Simulate instant fill
        fill_price = price if price else self.get_market_price(instrument)
        order_id = f"mock_{uuid.uuid4().hex[:8]}"

        # Update simulated position
        if action == "BUY":
            self.positions[instrument] = self.positions.get(instrument, 0) + quantity
        elif action == "SELL":
            self.positions[instrument] = self.positions.get(instrument, 0) - quantity

        return order_id
```

---

## Configuration

### Environment Variables

```bash
# .env file

# MongoDB Connection
MONGODB_URI=mongodb://mongodb:27017/mathematricks_trading

# Mock Broker Mode
USE_MOCK_BROKER=true  # Force all orders to Mock broker

# IBKR Configuration
IBKR_HOST=ib-gateway
IBKR_PORT=4002         # 4001=live, 4002=paper
IBKR_CLIENT_ID=1

# Zerodha Configuration
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_ACCESS_TOKEN=your_access_token
```

### Docker Compose

```yaml
services:
  execution-service:
    build: ./services/execution_service
    container_name: mathematricks-trader-execution-service-1
    command: python execution_main.py --staging
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - USE_MOCK_BROKER=${USE_MOCK_BROKER}
      - IBKR_HOST=${IBKR_HOST}
      - IBKR_PORT=${IBKR_PORT}
    ports:
      - "5679:5679"  # Python debugger
    depends_on:
      - mongodb
      - ib-gateway
    networks:
      - tradenet
    restart: unless-stopped
```

---

## Usage

### Starting the Service

```bash
# Via Docker Compose
make start

# View execution service logs
make logs-execution

# Restart execution service only
docker restart mathematricks-trader-execution-service-1

# Standalone (Development)
cd services/execution_service
python execution_main.py --staging
```

### Monitoring Execution

#### Check Order Status
```bash
# MongoDB shell
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading

> db.trading_orders.find({order_id: "ord_001"}).pretty()

# Expected output:
{
    "order_id": "ord_001",
    "status": "FILLED",
    "broker_order_id": "mock_abc123",
    "quantity_filled": 100,
    "avg_fill_price": 450.30,
    "filled_at": "2024-01-09T12:00:10Z"
}
```

#### Check Account Positions
```bash
> db.trading_accounts.find({account_id: "OANDA_MOCK"}).pretty()

# Expected output:
{
    "account_id": "OANDA_MOCK",
    "open_positions": [
        {
            "instrument": "SPY",
            "quantity": 100,
            "avg_entry_price": 450.30
        }
    ]
}
```

---

## Error Handling

### Common Errors

#### 1. Broker Connection Failed
```
ERROR: Failed to connect to broker: Connection refused
```

**Solution**:
- Check IB Gateway status: `docker ps | grep ib-gateway`
- Verify IBKR credentials in `.env`
- Ensure IB Gateway is accepting connections (check VNC: `localhost:5900`)

#### 2. Insufficient Margin
```
ERROR: Order rejected: Insufficient margin
```

**Solution**:
- Verify account has sufficient buying power
- Check margin requirements: `curl http://localhost:8082/accounts/margin-preview`
- Reduce position size

#### 3. Invalid Instrument Symbol
```
ERROR: Invalid instrument: XYZ
```

**Solution**:
- Verify instrument symbol format (e.g., "SPY" not "S&P 500")
- Check broker-specific symbol requirements
- Use correct exchange prefix if needed

---

## Related Documentation
- [Cerebro Service](cerebro_service.md) - Creates trading orders
- [Account Data Service](account_data_service.md) - Account state
- [Signal Ingestion](signal_ingestion_service.md) - Signal processing
