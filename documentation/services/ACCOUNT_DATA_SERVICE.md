# Account Data Service

## Overview

The Account Data Service manages trading accounts with real-time balance and position data. It polls brokers at regular intervals, provides account state to other services, and triggers event-driven updates.

**Main File:** `services/account_data_service/account_data_main.py`  
**Poller:** `services/account_data_service/broker_poller.py`  
**Port:** 8082  
**Framework:** FastAPI

## Purpose

- **Account Management** - Create, read, update, delete trading accounts
- **Balance Polling** - Fetch account balances from brokers every 5 minutes
- **Position Tracking** - Monitor open positions and P&L
- **Event-Driven Updates** - Poll immediately when positions change
- **Margin Information** - Provide margin availability for position sizing
- **Fund State Aggregation** - Aggregate balances across multiple accounts

## Architecture

### How It Works

```
Broker API → BrokerPoller → trading_accounts → Account Data Service → API Clients
                ↓                 (MongoDB)                              (Cerebro, etc.)
          MongoDB Watcher
          (Position Changes)
```

### Key Components

1. **TradingAccountRepository**
   - CRUD operations for accounts
   - MongoDB abstraction layer
   - Balance and position updates

2. **BrokerPoller**
   - Background polling service
   - Scheduled polling every 5 minutes
   - Event-driven polling on position changes

3. **MongoPositionWatcher**
   - Watches `trading_accounts.open_positions` via Change Streams
   - Triggers immediate poll when positions updated
   - Ensures fresh data after order fills

4. **FastAPI Server**
   - RESTful endpoints for account data
   - Margin preview API
   - Fund-level aggregations

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017/` |
| `ACCOUNT_POLL_INTERVAL` | Polling interval in seconds | `300` (5 minutes) |
| `ACCOUNT_DATA_SERVICE_PORT` | Service port | `8082` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Configuration File

File: `services/account_data_service/config.py`

```python
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'mathematricks_trading'
POLL_INTERVAL_SECONDS = int(os.getenv('ACCOUNT_POLL_INTERVAL', '300'))
PORT = int(os.getenv('ACCOUNT_DATA_SERVICE_PORT', '8082'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
```

## MongoDB Collections

### Main Collection: `trading_accounts`

```javascript
{
  _id: "IBKR_Paper",
  account_id: "IBKR_Paper",
  account_name: "IBKR Paper Trading Account",
  broker: "IBKR",
  account_number: "DU1234567",
  
  authentication_details: {
    auth_type: "TWS",
    host: "127.0.0.1",
    port: 7497,
    client_id: 100
  },
  
  balances: {
    base_currency: "USD",
    equity: 100000.0,
    cash_balance: 95000.0,
    margin_used: 5000.0,
    margin_available: 95000.0,
    unrealized_pnl: 250.0,
    realized_pnl: 1200.0,
    margin_utilization_pct: 5.0,
    last_updated: ISODate("2026-02-02T12:34:56Z")
  },
  
  open_positions: [
    {
      instrument: "AAPL",
      instrument_type: "STOCK",
      quantity: 100,
      avg_price: 150.0,
      current_price: 152.5,
      market_value: 15250.0,
      unrealized_pnl: 250.0,
      unrealized_pnl_pct: 1.67,
      last_updated: ISODate("2026-02-02T12:34:56Z")
    }
  ],
  
  polling_state: {
    last_poll_timestamp: ISODate("2026-02-02T12:34:56Z"),
    next_poll_timestamp: ISODate("2026-02-02T12:39:56Z"),
    consecutive_failures: 0,
    last_error: null
  },
  
  created_at: ISODate("2026-01-01T00:00:00Z"),
  updated_at: ISODate("2026-02-02T12:34:56Z")
}
```

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "account_data_service",
  "version": "2.0-simplified",
  "mongodb": "connected",
  "poller_running": true
}
```

### `POST /api/v1/accounts`
Create a new trading account.

**Request:**
```json
{
  "account_id": "IBKR_Main",
  "account_name": "IBKR Main Account",
  "broker": "IBKR",
  "account_number": "U1234567",
  "authentication_details": {
    "auth_type": "TWS",
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 100
  }
}
```

**Response:**
```json
{
  "account_id": "IBKR_Main",
  "message": "Account created and polling started"
}
```

### `GET /api/v1/accounts`
Get all trading accounts.

**Response:**
```json
{
  "accounts": [
    {
      "account_id": "IBKR_Paper",
      "account_name": "IBKR Paper Trading",
      "broker": "IBKR",
      "balances": { ... },
      "open_positions": [ ... ]
    }
  ]
}
```

### `GET /api/v1/accounts/{account_id}`
Get single account details.

**Response:**
```json
{
  "account_id": "IBKR_Paper",
  "account_name": "IBKR Paper Trading",
  "broker": "IBKR",
  "balances": {
    "equity": 100000.0,
    "cash_balance": 95000.0,
    "margin_available": 95000.0
  },
  "open_positions": [ ... ]
}
```

### `POST /api/v1/accounts/{account_id}/sync`
Force immediate sync from broker.

**Response:**
```json
{
  "account_id": "IBKR_Paper",
  "status": "synced",
  "balances": { ... },
  "positions": [ ... ]
}
```

### `DELETE /api/v1/accounts/{account_id}`
Delete account and stop polling.

**Response:**
```json
{
  "message": "Account IBKR_Paper deleted and polling stopped"
}
```

### `GET /api/v1/account/{account_name}/state`
Get account state (legacy endpoint, use `/api/v1/accounts/{account_id}` instead).

**Response:**
```json
{
  "account_name": "IBKR_Paper",
  "equity": 100000.0,
  "cash": 95000.0,
  "margin_used": 5000.0,
  "margin_available": 95000.0,
  "positions": [ ... ]
}
```

### `GET /api/v1/account/{account_name}/margin`
Get margin information for account.

**Response:**
```json
{
  "account_name": "IBKR_Paper",
  "margin_available": 95000.0,
  "margin_used": 5000.0,
  "margin_utilization_pct": 5.0
}
```

### `POST /api/v1/account/{account_name}/margin-preview`
Preview margin requirement for potential order.

**Request:**
```json
{
  "instrument": "AAPL",
  "instrument_type": "STOCK",
  "side": "BUY",
  "quantity": 100,
  "price": 150.0
}
```

**Response:**
```json
{
  "account_name": "IBKR_Paper",
  "instrument": "AAPL",
  "margin_required": 7500.0,
  "margin_available": 95000.0,
  "margin_sufficient": true,
  "margin_after": 87500.0
}
```

### `GET /api/v1/fund/state`
Get aggregated state for all accounts in a fund.

**Query Parameters:**
- `fund_id` (optional): Filter by fund ID

**Response:**
```json
{
  "fund_id": "main_fund",
  "total_equity": 250000.0,
  "total_cash": 200000.0,
  "total_margin_available": 240000.0,
  "accounts": [
    {
      "account_id": "IBKR_Paper",
      "equity": 100000.0,
      "margin_available": 95000.0
    }
  ]
}
```

## Key Functions

### BrokerPoller Class

#### `start()`
Start background polling and position watching.

**Flow:**
1. Start scheduled polling thread
2. Start MongoDB position watcher
3. Begin polling all accounts

#### `poll_account(account_id)`
Poll a single account from broker.

**Flow:**
1. Get broker instance from `BrokerFactory`
2. Connect to broker
3. Fetch account balances
4. Fetch open positions
5. Update `trading_accounts` collection
6. Update `polling_state` with timestamp
7. Disconnect from broker

#### `_poll_loop()`
Background thread that polls all accounts on schedule.

**Flow:**
1. Sleep until next poll time
2. Iterate all active accounts
3. Call `poll_account()` for each
4. Log results
5. Repeat

### MongoPositionWatcher Class

#### `_watch_for_position_changes()`
Watch MongoDB for position updates via Change Streams.

**Pipeline:**
```python
pipeline = [
    {
        '$match': {
            'operationType': {'$in': ['update', 'replace']},
            '$or': [
                {'updateDescription.updatedFields.open_positions': {'$exists': True}},
                {'updateDescription.updatedFields': {'$regex': '^open_positions\\.'}}
            ]
        }
    }
]
```

**On Position Change:**
1. Extract `account_id` from change event
2. Log position change detection
3. Call `position_change_callback(account_id)`
4. Callback triggers immediate poll via `poll_account_now()`

## Polling Strategies

### Scheduled Polling
- **Interval:** Every 5 minutes (configurable)
- **Purpose:** Keep balances fresh even without trades
- **Use Case:** Portfolio monitoring, margin calculations

### Event-Driven Polling
- **Trigger:** Position change in MongoDB
- **Purpose:** Immediate updates after order fills
- **Use Case:** Post-execution balance sync

### On-Demand Polling
- **Trigger:** API call to `/api/v1/accounts/{account_id}/sync`
- **Purpose:** Manual refresh before important operations
- **Use Case:** Pre-trade margin validation

## Example Usage

### Creating an Account

```python
import requests

account_data = {
    "account_id": "IBKR_Live",
    "account_name": "IBKR Live Trading",
    "broker": "IBKR",
    "account_number": "U9876543",
    "authentication_details": {
        "auth_type": "TWS",
        "host": "127.0.0.1",
        "port": 7496,
        "client_id": 200
    }
}

response = requests.post(
    'http://localhost:8082/api/v1/accounts',
    json=account_data
)

print(response.json())
# {"account_id": "IBKR_Live", "message": "Account created and polling started"}
```

### Getting Account State

```python
import requests

response = requests.get('http://localhost:8082/api/v1/accounts/IBKR_Paper')
account = response.json()

print(f"Equity: ${account['balances']['equity']:,.2f}")
print(f"Margin Available: ${account['balances']['margin_available']:,.2f}")
print(f"Open Positions: {len(account['open_positions'])}")
```

### Forcing a Sync

```python
import requests

response = requests.post('http://localhost:8082/api/v1/accounts/IBKR_Paper/sync')
result = response.json()

print(f"Synced! Equity: ${result['balances']['equity']:,.2f}")
```

### Margin Preview

```python
import requests

preview_data = {
    "instrument": "TSLA",
    "instrument_type": "STOCK",
    "side": "BUY",
    "quantity": 50,
    "price": 200.0
}

response = requests.post(
    'http://localhost:8082/api/v1/account/IBKR_Paper/margin-preview',
    json=preview_data
)

result = response.json()
print(f"Margin Required: ${result['margin_required']:,.2f}")
print(f"Sufficient: {result['margin_sufficient']}")
```

## Troubleshooting

### Problem: Poller not updating balances
**Symptoms:** `last_poll_timestamp` not changing
**Solutions:**
- Check poller is running: `GET /health` → `poller_running: true`
- Check broker connections in logs
- Verify account authentication details are correct
- Check `polling_state.consecutive_failures` counter

### Problem: Position updates delayed
**Cause:** Event-driven polling not working
**Solutions:**
- Verify MongoDB Change Stream is connected
- Check `MongoPositionWatcher` logs for connection issues
- Test manually: Update a position in MongoDB and watch logs

### Problem: Margin calculations incorrect
**Cause:** Stale balance data
**Solutions:**
- Force sync before margin check: `POST /api/v1/accounts/{id}/sync`
- Reduce `ACCOUNT_POLL_INTERVAL` for more frequent updates
- Use event-driven polling (automatic)

### Problem: "Broker connection failed"
**Symptoms:** `consecutive_failures` increasing
**Debug:**
- Check broker (IBKR Gateway) is running
- Verify `authentication_details.port` matches gateway port
- Check `client_id` is not in use by another connection
- Test connection manually: `broker.connect()`

### Problem: NaN or Inf values in balances
**Cause:** Broker returning invalid data
**Solutions:**
- Check broker API logs
- Sanitize response data (handled by `NaNSafeJSONEncoder`)
- Verify broker account has positions (empty accounts may return NaN)

### Problem: Fund aggregation missing accounts
**Cause:** Accounts not linked to fund in MongoDB
**Solution:**
- Check `funds` collection for account references
- Verify `account_id` matches exactly
- Query accounts without fund filter first to debug

## Performance Notes

- **Polling Overhead:** ~200-500ms per account per poll
- **MongoDB Updates:** Atomic updates to avoid race conditions
- **Change Stream Latency:** ~10-50ms from position update to poll trigger
- **Concurrent Polling:** Accounts polled sequentially (no parallel polls)
- **Connection Reuse:** Broker connections created per-poll (no persistent connections)

## Dependencies

- `fastapi` - Web framework
- `pymongo` - MongoDB driver
- `uvicorn` - ASGI server
- Custom modules:
  - `brokers.BrokerFactory` - Broker abstraction
  - `repository.TradingAccountRepository` - Data layer
  - `broker_poller.BrokerPoller` - Polling engine
  - `models.CreateAccountRequest` - Pydantic models

## Related Services

- **Cerebro Service** - Consumes account state for position sizing
- **Execution Service** - Syncs balances before order submission
- **Portfolio Builder** - Uses account data for portfolio construction

## Data Models

### CreateAccountRequest (Pydantic)
```python
class CreateAccountRequest(BaseModel):
    account_id: str
    account_name: str
    broker: str
    account_number: str
    authentication_details: AuthenticationDetails

class AuthenticationDetails(BaseModel):
    auth_type: str  # "TWS", "Gateway", "API"
    host: str
    port: int
    client_id: int
```

### MarginPreviewRequest (Pydantic)
```python
class MarginPreviewRequest(BaseModel):
    instrument: str
    instrument_type: str  # "STOCK", "OPTION", "FUTURE", etc.
    side: str  # "BUY", "SELL"
    quantity: int
    price: float
```

## Logging

### Files
- `logs/account_data_service.log` - Service logs

### Log Format
```
|INFO|Account IBKR_Paper polled successfully|2026-02-02 12:34:56|file:broker_poller.py:line No.123
```

### Key Log Events
- Account polling started/completed
- Position changes detected
- Broker connection failures
- Balance updates
- Polling errors

## Safety Features

### Error Handling
- Consecutive failure tracking
- Automatic retry with exponential backoff
- Broker connection timeout (30s)
- MongoDB connection resilience

### Data Validation
- NaN/Inf sanitization in responses
- Balance consistency checks
- Position quantity validation
- Margin calculation bounds checking
