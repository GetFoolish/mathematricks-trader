# Execution Service

## Overview

The Execution Service is responsible for connecting to brokers, executing trading orders, and reporting back execution confirmations and account state. It manages the broker pool, handles order lifecycle, and ensures reliable order execution.

**Main File:** `services/execution_service/execution_main.py`  
**Port:** 8083  
**Framework:** FastAPI

## Purpose

- **Broker Connection Management** - Initialize and maintain connections to IBKR, Zerodha, Mock brokers
- **Order Execution** - Execute market, limit, and stop orders
- **Execution Confirmation** - Report fills, partial fills, and rejections
- **Account Synchronization** - Sync balances and positions with broker
- **Gateway Control** - Manage IBKR Gateway lifecycle for live accounts
- **Market Hours Validation** - Check if markets are open before execution

## Architecture

### How It Works

```
trading_orders → Execution Service → Broker API → Execution Confirmation
                      ↓                              ↓
                 Broker Pool                  signal_store.execution
                 (IBKR/Mock)                  (Fill Data)
```

### Key Components

1. **Broker Pool**
   - Pre-initialized broker connections
   - One broker instance per account
   - Configured via `gateway_config.yml`

2. **Order Queue**
   - Thread-safe order processing
   - Sequential execution to avoid race conditions
   - Background worker thread

3. **Gateway Controller**
   - Starts/stops IBKR Gateway containers
   - Manages client_id allocation
   - Health monitoring

4. **Change Stream Watcher**
   - Monitors `trading_orders` for new PENDING orders
   - Real-time order pickup
   - Resume token for resilience

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | Required |
| `ACCOUNT_DATA_SERVICE_URL` | Account data service endpoint | `http://localhost:8082` |
| `USE_MOCK_BROKER` | Force all orders to Mock broker | `false` |
| `TELEGRAM_ENABLED` | Enable Telegram notifications | `false` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - |
| `TELEGRAM_CHAT_ID` | Telegram chat ID | - |
| `ALLOW_LIVE_TRADING` | Enable live broker execution | `false` |

### Command-Line Arguments

```bash
python execution_main.py [--use-mock-broker]
```

**`--use-mock-broker`**: Route all orders to Mock_Paper broker (testing mode)

### Gateway Configuration

File: `services/execution_service/gateway_config.yml`

```yaml
always_start_accounts:
  - IBKR-TESTING-ACCOUNT
  - IBKR-PAPER-ACCOUNT

account_modes:
  IBKR-TESTING-ACCOUNT: paper_live
  IBKR-PAPER-ACCOUNT: paper_live
  IBKR-LIVE-ACCOUNT: live_live

client_id_mapping:
  IBKR-TESTING-ACCOUNT: 100
  IBKR-PAPER-ACCOUNT: 101
```

## MongoDB Collections

### Input: `trading_orders`
Monitors for new orders:
```javascript
{
  order_id: "ORDER_abc123",
  signal_id: "SIGNAL_123",
  mathematricks_signal_id: ObjectId("..."),
  account_id: "IBKR_Paper",
  
  instrument: "AAPL",
  side: "BUY",
  quantity: 100,
  order_type: "MARKET",
  price: 150.0,
  
  status: "PENDING_EXECUTION",  // Execution picks this up
  cerebro_decision: { ... },
  
  created_at: ISODate
}
```

### Output: `signal_store` (Updated)
Updates execution data in leg:
```javascript
{
  legs: [
    {
      leg_id: "SIGNAL_123__entry_0",
      execution: {
        status: "FILLED" | "PARTIAL" | "REJECTED" | "CANCELLED",
        broker_order_id: "12345",
        broker: "IBKR",
        account_id: "IBKR_Paper",
        
        submitted_quantity: 100,
        filled_quantity: 100,
        remaining_quantity: 0,
        
        avg_fill_price: 150.05,
        commission: 1.0,
        
        fills: [
          {
            timestamp: ISODate,
            quantity: 100,
            price: 150.05,
            commission: 1.0
          }
        ],
        
        submitted_at: ISODate,
        last_updated: ISODate,
        completed_at: ISODate
      },
      processing_timestamps: {
        execution_started: ISODate,
        execution_completed: ISODate
      },
      processing_lag: 1.234  // Seconds from signal received to execution complete
    }
  ]
}
```

### Updates: `trading_orders`
Updates order status:
```javascript
{
  status: "SUBMITTED" | "FILLED" | "PARTIAL" | "REJECTED",
  broker_order_id: "12345",
  filled_quantity: 100,
  avg_price: 150.05,
  updated_at: ISODate
}
```

### Updates: `trading_accounts`
Updates positions after fills:
```javascript
{
  account_id: "IBKR_Paper",
  open_positions: [
    {
      instrument: "AAPL",
      quantity: 100,
      avg_price: 150.05,
      current_price: 151.20,
      unrealized_pnl: 115.0
    }
  ]
}
```

## API Endpoints

### `GET /health`
Health check endpoint (503 until broker pool ready).

**Response:**
```json
{
  "status": "healthy",
  "ready": true,
  "broker_pool_size": 2,
  "brokers_connected": 2
}
```

### `GET /status`
Detailed service status.

**Response:**
```json
{
  "ready": true,
  "broker_pool": ["IBKR_Paper", "Mock_Paper"],
  "change_stream_connected": true,
  "pending_orders_processed": 45
}
```

### `GET /market_status`
Check market hours and broker connectivity.

**Response:**
```json
{
  "markets": {
    "STOCK": true,
    "OPTION": true,
    "CRYPTO": true,
    "FUTURE": false
  },
  "brokers": {
    "IBKR_Paper": {
      "connected": true,
      "broker_name": "IBKR"
    }
  },
  "canary_prices": {
    "SPY": 450.25
  }
}
```

### `POST /api/v1/execute-order`
Execute a trading order.

**Request:**
```json
{
  "order_id": "ORDER_abc123",
  "signal_id": "SIGNAL_123",
  "mathematricks_signal_id": "507f1f77bcf86cd799439011",
  "account_id": "IBKR_Paper",
  "instrument": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "order_type": "MARKET",
  "price": 150.0
}
```

**Response:**
```json
{
  "status": "queued",
  "order_id": "ORDER_abc123",
  "message": "Order queued for execution"
}
```

### `POST /api/v1/sync-account-balance`
Sync account balance from broker (called by Cerebro before position sizing).

**Request:**
```
POST /api/v1/sync-account-balance?account_id=IBKR_Paper&max_age_seconds=60
```

**Response:**
```json
{
  "account_id": "IBKR_Paper",
  "balances": {
    "equity": 100000.0,
    "cash_balance": 95000.0,
    "margin_used": 5000.0,
    "margin_available": 95000.0,
    "last_updated": "2026-02-02T12:34:56Z"
  },
  "source": "broker",
  "age_seconds": 0
}
```

## Key Functions

### `initialize_and_connect_brokers()`
Module-level initialization (runs once at startup).

**Flow:**
1. Load `gateway_config.yml`
2. Start IBKR Gateway containers (if needed)
3. Create broker instances via `BrokerFactory`
4. Connect to each broker
5. Mark broker pool as ready
6. Set `service_status['ready'] = True`

**Blocking:** Service won't accept requests until complete (~60s)

### `process_order_from_change_stream(order_data)`
Main order execution function.

**Flow:**
1. Extract order details
2. Validate order data
3. Get broker from pool
4. Submit order to broker
5. Wait for fill (blocking for up to 30s)
6. Update `signal_store` with execution data
7. Update `trading_orders` with status
8. Update `trading_accounts` with new position
9. Send Telegram notification

### `update_signal_store_execution(mathematricks_signal_id, execution_data, raw_signal_id)`
Updates signal_store with execution results.

**Flow:**
1. Find signal document
2. Find matching leg by `raw._id`
3. Update `leg.execution` field
4. Set `execution_started` and `execution_completed` timestamps
5. Calculate `processing_lag`

### `watch_trading_orders_for_execution()`
Change Stream watcher for new orders.

**Pipeline:**
```python
pipeline = [
    {
        '$match': {
            'operationType': 'insert',
            'fullDocument.status': 'PENDING_EXECUTION'
        }
    }
]
```

## Order Execution Flow

### Market Order Flow
1. **Receive Order** from `trading_orders` Change Stream
2. **Validate Order:**
   - Check broker connection
   - Validate instrument
   - Check market hours (if configured)
3. **Route to Broker:**
   - Look up broker from pool by `account_id`
   - Convert to broker-specific format
4. **Submit Order:**
   - Call `broker.place_order()`
   - Get `broker_order_id`
5. **Wait for Fill:**
   - Poll for order status (up to 30s for market orders)
   - Detect fills via broker API
6. **Record Execution:**
   - Update `signal_store.legs[i].execution`
   - Update `trading_orders.status`
   - Update `trading_accounts.open_positions`
7. **Notify:**
   - Send Telegram message with fill details
   - Log to `signal_processing.log`

### Multi-Leg Order Flow
For strategies with multiple legs (e.g., spreads):
1. Execute each leg sequentially
2. Track `leg_index` and `total_legs`
3. All legs share same `signal_id`
4. Each leg has separate `order_id`

## Broker Pool Management

### Initialization
```python
broker_pool = {}

# For each account in gateway_config.yml
for account_id in always_start_accounts:
    broker = BrokerFactory.create_broker(
        broker_name="IBKR",
        account_id=account_id,
        auth_details={
            'host': '127.0.0.1',
            'port': 7497,
            'client_id': 100
        }
    )
    broker.connect()
    broker_pool[account_id] = broker
```

### Connection Resilience
- Brokers auto-reconnect on disconnection
- Health checks every 60s
- Gateway controller restarts crashed containers

## Example Usage

### Starting the Service

```bash
# Standard mode (uses real broker connections)
python services/execution_service/execution_main.py

# Mock mode (all orders to Mock broker)
python services/execution_service/execution_main.py --use-mock-broker

# Docker mode
docker-compose up execution-service
```

### Executing an Order Manually

```python
import requests

order_data = {
    'order_id': 'TEST_ORDER_001',
    'account_id': 'IBKR_Paper',
    'instrument': 'AAPL',
    'side': 'BUY',
    'quantity': 100,
    'order_type': 'MARKET',
    'price': 150.0
}

response = requests.post(
    'http://localhost:8083/api/v1/execute-order',
    json=order_data
)

print(response.json())
# {"status": "queued", "order_id": "TEST_ORDER_001"}
```

### Checking Market Status

```python
import requests

response = requests.get('http://localhost:8083/market_status')
data = response.json()

if data['markets']['STOCK']:
    print("Stock market is OPEN")
else:
    print("Stock market is CLOSED")
```

## Troubleshooting

### Problem: Health check returns 503
**Cause:** Broker pool still initializing
**Solution:**
- Wait for "Broker Pool Initialized" log message
- Check gateway containers are running (`docker ps`)
- Verify IBKR Gateway is accepting connections

### Problem: Orders stuck in PENDING_EXECUTION
**Cause:** Change Stream not connected or execution service not running
**Solutions:**
- Check execution service logs for "Change Stream connected" message
- Verify MongoDB connection
- Restart execution service

### Problem: "No broker found for account_id"
**Cause:** Account not in broker pool
**Solutions:**
- Add account to `gateway_config.yml` under `always_start_accounts`
- Restart execution service
- For paper accounts, check if using `_paper_live` suffix

### Problem: IBKR orders rejected with "TWS session expired"
**Cause:** Gateway connection dropped
**Solutions:**
- Restart IBKR Gateway: `docker restart ibgateway-testing`
- Check Gateway logs: `docker logs ibgateway-testing`
- Verify `client_id` not in use by another connection

### Problem: Execution confirmations not updating signal_store
**Cause:** `mathematricks_signal_id` or `raw_signal_id` missing
**Debug:**
- Check order has `mathematricks_signal_id` field
- Verify signal exists in `signal_store`
- Inspect `update_signal_store_execution()` logs

### Problem: Position updates not reflected in trading_accounts
**Cause:** Account data service not polling or broker not reporting positions
**Solutions:**
- Trigger manual sync: `POST /api/v1/accounts/{account_id}/sync`
- Check broker API is returning positions
- Verify account data service is running

## Performance Notes

- **Broker Pool Initialization:** ~60 seconds for 2-3 accounts
- **Market Order Fill Time:** ~100-500ms (IBKR), instant (Mock)
- **Change Stream Latency:** ~10-50ms from order creation to pickup
- **Order Queue:** Processes orders sequentially (no parallel execution)

## Dependencies

- `fastapi` - Web framework
- `ib_insync` - IBKR API client
- `pymongo` - MongoDB driver
- `requests` - HTTP client
- Custom modules:
  - `brokers.BrokerFactory` - Broker abstraction
  - `gateway_controller.GatewayController` - IBKR Gateway management
  - `telegram.notifier.TelegramNotifier` - Notifications

## Related Services

- **Cerebro Service** - Creates orders for execution
- **Account Data Service** - Provides account balances
- **Signal Ingestion** - Original signal source
- **Portfolio Builder** - Strategy configurations

## Telegram Notifications

When `TELEGRAM_ENABLED=true`, execution service sends:

### On Order Submitted
```
✅ TRADES EXECUTED

📊 Strategy: MaxCAGR_v2
🆔 Signal ID: SIGNAL_123
🕐 Time: 2026-02-02 12:34:56

📈 Orders:
✅ AAPL - BUY 100 @ IBKR

📊 Summary:
✅ Successful: 1
❌ Failed: 0
```

### On Order Filled
```
💰 ORDER FILLED

📊 Strategy: MaxCAGR_v2
🆔 Order ID: ORDER_abc123

📈 Fill Details:
Instrument: AAPL
Quantity: 100
Avg Price: $150.05
Commission: $1.00

📊 Status: FILLED
```

## Safety Features

### Live Trading Protection
- `ALLOW_LIVE_TRADING` must be explicitly set to `true`
- Double confirmation for live account orders
- Separate client_id for live vs paper accounts

### Order Validation
- Instrument symbol validation
- Quantity > 0 check
- Broker connection check before submission
- Market hours validation (configurable)

### Error Handling
- Broker API errors caught and logged
- Orders marked as REJECTED on broker rejection
- Retry logic for transient broker errors (up to 3 attempts)

## Logging

### Files
- `logs/execution_service.log` - General service logs
- `logs/signal_processing.log` - Unified signal journey (includes execution)

### Log Levels
- **INFO:** Order submissions, fills, status changes
- **WARNING:** Broker connection issues, order rejections
- **ERROR:** Critical failures, unexpected exceptions
- **DEBUG:** Detailed broker API calls, order state transitions
