# Execution Service

## Overview

The Execution Service receives approved trading orders from the Cerebro Service and executes them with the appropriate broker. It manages the complete order lifecycle from placement to fill/rejection and publishes execution confirmations back to the system.

## Location

`/services/execution_service/`

## Key Responsibilities

1. Subscribe to trading orders from Cerebro Service
2. Place orders with appropriate broker via BrokerFactory
3. Track order status (Pending → Submitted → Filled/Rejected)
4. Handle partial fills and order modifications
5. Publish execution confirmations to other services
6. Store execution data in MongoDB for audit trail
7. Send Telegram notifications for important execution events
8. Handle broker-specific order parameters and validation

## Main Files

### execution_main.py
- Pub/Sub subscriber for trading orders
- Order placement orchestration
- Order lifecycle management
- Execution confirmation publishing
- Error handling and retry logic

## Key Functions

### process_order(order_data)
Main order processing function:
1. Validate order data
2. Get broker instance from BrokerFactory
3. Place order with broker
4. Track order status
5. Handle fills/rejections
6. Publish confirmation
7. Update MongoDB

### handle_order_fill(order_id, fill_data)
Processes filled orders:
- Updates position in MongoDB
- Calculates realized PnL for exits
- Sends Telegram notification
- Publishes to execution-confirmations topic

### handle_order_rejection(order_id, rejection_reason)
Handles rejected orders:
- Logs rejection details
- Updates signal_store with failure
- Sends Telegram alert
- Does not retry (manual intervention required)

## Order Processing Workflow

```
1. Receive Order from Pub/Sub
   - Topic: trading-orders
   - Message contains: signal_id, order details
   ↓
2. Validate Order Data
   - Check required fields
   - Validate symbol format
   - Verify account exists
   ↓
3. Get Broker Instance
   - BrokerFactory.create_broker(config)
   - Ensure connection established
   ↓
4. Place Order with Broker
   - Call broker.place_order(order_data)
   - Receive order_id from broker
   ↓
5. Track Order Status
   - Poll broker for status updates
   - Detect fills/partial fills
   - Handle rejections
   ↓
6. Process Order Result
   - FILLED → Update positions
   - REJECTED → Log and notify
   - PARTIAL → Continue tracking
   ↓
7. Publish Execution Confirmation
   - Pub/Sub: execution-confirmations
   ↓
8. Store in MongoDB
   - Collection: execution_confirmations
   - Update: signal_store with order_id
   ↓
9. Send Telegram Notification
   - Success: "Order filled: 100 SPY @ $235.00"
   - Failure: "Order rejected: Insufficient margin"
```

## MongoDB Collections

### execution_confirmations (Write)
Stores all order executions and rejections:
```json
{
  "_id": "exec_abc123",
  "order_id": "ord_broker_12345",
  "signal_id": "sig_1732450800_5678",
  "strategy_name": "SPX 1-Day Options",
  "account_id": "acc_abc123",
  "symbol": "SPY",
  "side": "BUY",
  "quantity": 100,
  "filled_quantity": 100,
  "order_type": "MARKET",
  "avg_fill_price": 235.15,
  "status": "FILLED",
  "submitted_at": "2024-11-24T10:30:10Z",
  "filled_at": "2024-11-24T10:30:12Z",
  "broker": "IBKR",
  "commission": 1.00,
  "total_value": 23515.00,
  "notes": "Filled in 2 seconds"
}
```

### signal_store (Update)
Updates signal with order_id:
```json
{
  "signal_id": "sig_1732450800_5678",
  "order_id": "ord_broker_12345",
  "execution_status": "FILLED",
  "filled_at": "2024-11-24T10:30:12Z"
}
```

### positions (Update)
Creates or updates positions:
```json
{
  "_id": "pos_abc123",
  "strategy_name": "SPX 1-Day Options",
  "account_id": "acc_abc123",
  "symbol": "SPY",
  "side": "LONG",
  "quantity": 100,
  "avg_entry_price": 235.15,
  "opened_at": "2024-11-24T10:30:12Z",
  "status": "OPEN",
  "order_ids": ["ord_broker_12345"]
}
```

## Pub/Sub Integration

### Subscribed Topics

**trading-orders**
Receives approved orders from Cerebro Service:
```json
{
  "signal_id": "sig_1732450800_5678",
  "order_type": "MARKET",
  "symbol": "SPY",
  "side": "BUY",
  "quantity": 100,
  "account_id": "acc_abc123",
  "strategy_name": "SPX 1-Day Options",
  "stop_loss": 230.00,
  "take_profit": 240.00
}
```

### Published Topics

**execution-confirmations**
Publishes execution results:
```json
{
  "signal_id": "sig_1732450800_5678",
  "order_id": "ord_broker_12345",
  "status": "FILLED",
  "filled_quantity": 100,
  "avg_fill_price": 235.15,
  "filled_at": "2024-11-24T10:30:12Z",
  "commission": 1.00
}
```

## Order Types Supported

### Market Orders
- Executes at current market price
- Fast execution
- No price guarantee

### Limit Orders
- Executes at specified price or better
- May not fill immediately
- Price protection

### Stop Orders
- Triggers when price reaches stop level
- Becomes market order
- Used for stop-loss

### Stop-Limit Orders
- Triggers at stop price
- Becomes limit order
- Combined protection

## Broker-Specific Handling

### IBKR Orders
- Uses `ib_insync` library
- Supports all asset classes
- Crypto orders use `cashQty` parameter
- Sets appropriate `tif` (time in force):
  - DAY - Regular trading hours
  - GTC - Good til cancelled
  - IOC - Immediate or cancel

### Zerodha Orders
- Uses `kiteconnect` library
- NSE/BSE exchanges
- Intraday vs delivery orders
- Product types: MIS, NRML, CNC

### Mock Broker
- Simulates order fills
- Configurable fill delay
- Random rejection for testing
- No real money involved

## Error Handling

1. **Broker Connection Failures**
   - Retries connection up to 3 times
   - Logs error details
   - Rejects order if connection fails
   - Sends Telegram alert

2. **Order Rejection by Broker**
   - Stores rejection reason
   - Updates signal_store with failure
   - Sends detailed Telegram notification
   - No automatic retry (requires manual review)

3. **Partial Fills**
   - Continues tracking until fully filled or cancelled
   - Updates position with partial quantity
   - Logs partial fill events

4. **Order Timeout**
   - Configurable timeout (default: 60 seconds)
   - Cancels order if not filled
   - Logs timeout event
   - Notifies via Telegram

## Configuration

### Environment Variables
```bash
# Broker configuration (inherited from .env)
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=1

# Mock broker flag
USE_MOCK_BROKER=false

# Telegram notifications
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# Execution settings (hardcoded in execution_main.py)
ORDER_TIMEOUT_SECONDS=60
MAX_RETRY_ATTEMPTS=3
```

### Command-Line Options
```bash
# Use mock broker for testing
python execution_main.py --use-mock-broker

# Standard execution
python execution_main.py
```

## Logging

Logs to:
- Console (real-time output)
- `logs/execution_service.log` (service-specific)
- `logs/signal_processing.log` (unified signal journey)

Log format:
```
Timestamp | [EXECUTION] | Message
```

Example log entries:
```
2024-11-24 10:30:10 | [EXECUTION] | Received order: sig_1732450800_5678
2024-11-24 10:30:10 | [EXECUTION] | Placing order: BUY 100 SPY MARKET
2024-11-24 10:30:11 | [EXECUTION] | Order submitted: ord_broker_12345
2024-11-24 10:30:12 | [EXECUTION] | Order filled: 100 @ $235.15
2024-11-24 10:30:12 | [EXECUTION] | Published execution confirmation
```

## Telegram Notifications

### Successful Execution
```
✅ Order Filled

Signal: sig_1732450800_5678
Strategy: SPX 1-Day Options
Order: BUY 100 SPY @ $235.15
Total: $23,515.00
Commission: $1.00
Time: 2 seconds
```

### Order Rejection
```
❌ Order Rejected

Signal: sig_1732450800_5678
Strategy: SPX 1-Day Options
Order: BUY 100 SPY
Reason: Insufficient margin
Account: IBKR Main Account
```

### Partial Fill
```
⚠️ Partial Fill

Signal: sig_1732450800_5678
Order: BUY 100 SPY
Filled: 50/100 @ $235.20
Remaining: 50
```

## Dependencies

- **Google Cloud Pub/Sub** - Order input/confirmation output
- **MongoDB** - Execution storage
- **BrokerFactory** - Broker abstraction (IBKR, Zerodha, Mock)
- **Telegram notifier** - Execution notifications
- **Python packages**:
  - `google-cloud-pubsub>=2.18.4`
  - `pymongo>=4.6.1`
  - `ib-insync>=0.9.86` (for IBKR)
  - `kiteconnect>=5.0.1` (for Zerodha)
  - `requests>=2.31.0`

## Startup Command

```bash
# Via mvp_demo_start.py
python mvp_demo_start.py

# Manual startup (live broker)
python services/execution_service/execution_main.py

# With mock broker (testing)
python services/execution_service/execution_main.py --use-mock-broker

# Background process
nohup python services/execution_service/execution_main.py > logs/execution_service.log 2>&1 &
```

## Health Checks

Check service status:
```bash
python mvp_demo_status.py
```

View logs:
```bash
# Service-specific logs
tail -f logs/execution_service.log

# Unified signal journey
tail -f logs/signal_processing.log | grep EXECUTION
```

Monitor Pub/Sub:
```bash
gcloud pubsub subscriptions describe trading-orders-sub
```

## Testing

### Send Test Order via Signal
```bash
cd tests/signals_testing
python send_test_signal.py --file equity_simple_signal_1.json
```

### Monitor Execution
```bash
# Watch execution logs
tail -f logs/execution_service.log

# Watch unified logs
tail -f logs/signal_processing.log
```

### Check Execution in MongoDB
```bash
mongosh
use mathematricks_trading
db.execution_confirmations.find().sort({submitted_at: -1}).limit(1)
```

### Verify Position Created
```bash
db.positions.find({status: "OPEN"})
```

## Performance Considerations

- Order placement latency: 50-500ms (depends on broker)
- IBKR typically fastest (~100ms)
- Zerodha variable (200-500ms)
- Mock broker instant (<10ms)
- Network latency to broker servers adds 10-50ms

## Related Documentation

- [Cerebro Service](cerebro_service.md) - Sends orders to Execution Service
- [Brokers](brokers.md) - Broker abstraction layer
- [Account Data Service](account_data_service.md) - Updates on fills
- [Testing Signals](signals_testing.md) - End-to-end testing

## Common Issues

### Orders Not Being Placed
- Check Pub/Sub subscription: `trading-orders`
- Verify Execution Service is running
- Check broker connection status
- Look for errors in `execution_service.log`

### Order Rejections
- **Insufficient margin** → Check account balance in Account Data Service
- **Invalid symbol** → Verify symbol format matches broker
- **Market closed** → Check trading hours for instrument
- **Connection error** → Verify broker is running (TWS/Gateway)

### Partial Fills Not Completing
- Check order timeout setting
- Verify order is still active with broker
- Look for cancellation messages in logs
- Check market liquidity for symbol

### Missing Execution Confirmations
- Verify `execution-confirmations` topic exists
- Check MongoDB writes are succeeding
- Look for publish errors in logs

### Telegram Notifications Not Sending
- Check `TELEGRAM_ENABLED=true` in .env
- Verify bot token and chat ID are correct
- Test Telegram API connectivity
- Check notifier logs

## Security Considerations

- Order parameters are validated before placement
- No order modification allowed once submitted
- All executions logged for audit trail
- Broker credentials not logged
- Position updates atomic (no race conditions)

## Recovery Procedures

### Service Crash During Order Placement
1. Check `signal_store` for pending orders
2. Query broker for order status
3. Manually reconcile positions if needed
4. Update MongoDB collections

### Duplicate Order Prevention
- Signal IDs are unique
- Check for existing order_id before placing
- MongoDB unique index on signal_id

### Failed Execution Confirmation Publish
- Retry publishing up to 3 times
- Log failure details
- Order still tracked in MongoDB
- Manual verification required
