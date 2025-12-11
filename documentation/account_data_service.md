# Account Data Service

## Overview

The Account Data Service manages real-time trading account data, including balances, positions, and margin information. It continuously polls broker accounts to maintain up-to-date state and provides a REST API for other services to query account information.

## Location

`/services/account_data_service/`

## Key Responsibilities

1. Manage trading account definitions and configurations
2. Poll broker accounts for real-time balance and position data
3. Monitor position changes and trigger immediate updates
4. Provide REST API for account queries
5. Track connection status for each broker account
6. Calculate margin utilization and available buying power
7. Support fund-level aggregation across multiple accounts

## Main Files

### account_data_main.py
- FastAPI service entry point
- REST API endpoints for account management
- Service orchestration

### broker_poller.py
- Background polling thread
- Fetches account data from brokers at regular intervals
- Handles broker connection failures
- Triggers immediate polls on position changes

### repository.py
- MongoDB account repository
- CRUD operations for trading accounts
- Database queries and updates

### models.py
- Pydantic data models
- Account schemas
- Position schemas
- Balance schemas

### config.py
- Service configuration
- Environment variable management
- Polling interval settings

## Key Classes

### TradingAccountRepository
MongoDB repository for account operations:
- `create_account(account_doc)` - Create new trading account
- `get_account(account_id)` - Retrieve account by ID
- `list_accounts(broker, status)` - List filtered accounts
- `update_account(account_id, updates)` - Update account fields
- `delete_account(account_id)` - Soft-delete (set INACTIVE)

### BrokerPoller
Background thread that continuously polls accounts:
- Runs every `POLL_INTERVAL_SECONDS` (default: 30s)
- Connects to broker via BrokerFactory
- Updates balances and positions in MongoDB
- Handles connection failures gracefully
- Logs all polling activities

### MongoPositionWatcher
Watches for position changes:
- Uses MongoDB Change Streams
- Detects position updates from Execution Service
- Triggers immediate re-poll of affected accounts

## REST API Endpoints

**Port:** 8082

### Account Management

#### Create Account
```
POST /api/v1/accounts
Content-Type: application/json

{
  "account_name": "IBKR Main Account",
  "broker": "IBKR",
  "account_number": "U1234567",
  "authentication_details": {
    "auth_type": "TWS",
    "host": "127.0.0.1",
    "port": 4002,
    "client_id": 1
  }
}

Response: 201 Created
{
  "account_id": "acc_abc123",
  "account_name": "IBKR Main Account",
  "status": "ACTIVE"
}
```

#### List Accounts
```
GET /api/v1/accounts?broker=IBKR&status=ACTIVE

Response: 200 OK
{
  "accounts": [
    {
      "account_id": "acc_abc123",
      "account_name": "IBKR Main Account",
      "broker": "IBKR",
      "balances": { ... },
      "open_positions": [ ... ]
    }
  ]
}
```

#### Get Account Details
```
GET /api/v1/accounts/{account_id}

Response: 200 OK
{
  "account_id": "acc_abc123",
  "account_name": "IBKR Main Account",
  "broker": "IBKR",
  "account_number": "U1234567",
  "balances": {
    "base_currency": "USD",
    "equity": 1000000.00,
    "cash_balance": 500000.00,
    "margin_used": 250000.00,
    "margin_available": 250000.00,
    "unrealized_pnl": 50000.00,
    "realized_pnl": 100000.00,
    "margin_utilization_pct": 25.0,
    "last_updated": "2024-11-24T10:30:00Z"
  },
  "open_positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "side": "LONG",
      "avg_price": 230.50,
      "current_price": 235.00,
      "market_value": 23500.00,
      "unrealized_pnl": 450.00
    }
  ],
  "connection_status": "CONNECTED",
  "last_poll_time": "2024-11-24T10:30:00Z",
  "status": "ACTIVE"
}
```

#### Force Account Sync
```
POST /api/v1/accounts/{account_id}/sync

Response: 200 OK
{
  "message": "Account synced successfully",
  "balances": { ... },
  "positions": [ ... ]
}
```

#### Delete Account
```
DELETE /api/v1/accounts/{account_id}

Response: 200 OK
{
  "message": "Account deleted successfully",
  "account_id": "acc_abc123"
}
```

### Legacy Endpoints (For Cerebro Compatibility)

#### Get Account State
```
GET /api/v1/account/{account_name}/state

Response: 200 OK
{
  "account_name": "IBKR Main Account",
  "equity": 1000000.00,
  "cash_balance": 500000.00,
  "margin_available": 250000.00,
  "positions": [ ... ]
}
```

#### Get Margin Info
```
GET /api/v1/account/{account_name}/margin

Response: 200 OK
{
  "margin_used": 250000.00,
  "margin_available": 250000.00,
  "margin_utilization_pct": 25.0
}
```

#### Preview Margin Impact
```
POST /api/v1/account/{account_name}/margin-preview
Content-Type: application/json

{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "order_type": "MARKET"
}

Response: 200 OK
{
  "current_margin_used": 250000.00,
  "estimated_margin_impact": 23500.00,
  "new_margin_used": 273500.00,
  "margin_available_after": 226500.00
}
```

### Fund-Level Aggregation

#### Get Fund State
```
GET /api/v1/fund/state

Response: 200 OK
{
  "total_equity": 5000000.00,
  "total_cash": 2500000.00,
  "total_margin_used": 1250000.00,
  "total_unrealized_pnl": 250000.00,
  "accounts": [
    {
      "account_id": "acc_abc123",
      "account_name": "IBKR Main Account",
      "equity": 1000000.00
    }
  ]
}
```

## MongoDB Collections

### trading_accounts

Complete account document structure:
```json
{
  "_id": "acc_abc123",
  "account_name": "IBKR Main Account",
  "account_id": "acc_abc123",
  "broker": "IBKR",
  "account_number": "U1234567",
  "authentication_details": {
    "auth_type": "TWS",
    "host": "127.0.0.1",
    "port": 4002,
    "client_id": 1
  },
  "balances": {
    "base_currency": "USD",
    "equity": 1000000.00,
    "cash_balance": 500000.00,
    "margin_used": 250000.00,
    "margin_available": 250000.00,
    "unrealized_pnl": 50000.00,
    "realized_pnl": 100000.00,
    "margin_utilization_pct": 25.0,
    "last_updated": "2024-11-24T10:30:00Z"
  },
  "open_positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "side": "LONG",
      "avg_price": 230.50,
      "current_price": 235.00,
      "market_value": 23500.00,
      "unrealized_pnl": 450.00
    }
  ],
  "connection_status": "CONNECTED",
  "last_poll_time": "2024-11-24T10:30:00Z",
  "last_poll_success": true,
  "poll_error": null,
  "status": "ACTIVE",
  "created_at": "2024-11-01T00:00:00Z",
  "updated_at": "2024-11-24T10:30:00Z"
}
```

## Polling Behavior

### Automatic Polling
- Runs in background thread
- Default interval: 30 seconds (`POLL_INTERVAL_SECONDS`)
- Polls all ACTIVE accounts
- Updates balances and positions in MongoDB
- Logs polling results

### Triggered Polling
- MongoDB Change Stream watches `positions` collection
- When position changes detected, immediately re-polls affected accounts
- Ensures account state stays in sync with executions

### Connection Handling
- Attempts broker connection for each poll
- On failure, logs error and sets `connection_status: "DISCONNECTED"`
- Retries on next polling cycle
- Does not crash service on connection failures

## Configuration

### Environment Variables
```bash
# MongoDB connection
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0

# Polling settings
POLL_INTERVAL_SECONDS=30

# Service port
ACCOUNT_DATA_SERVICE_PORT=8082

# Broker credentials (for IBKR)
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=1
```

## Error Handling

1. **Broker Connection Failures**
   - Logs error with account details
   - Sets `connection_status: "DISCONNECTED"`
   - Continues polling other accounts
   - Retries on next cycle

2. **API Errors**
   - Returns appropriate HTTP status codes
   - Provides error messages in response
   - Logs full error details

3. **MongoDB Failures**
   - Retries with exponential backoff
   - Logs database errors
   - Returns 500 Internal Server Error to API clients

## Logging

Logs to:
- Console (real-time output)
- `logs/account_data_service.log` (service-specific)

Log format:
```
|LEVEL|Message|Timestamp|file:filename.py:line No.LineNumber|
```

Example log entries:
```
|INFO|Starting broker poller for 3 accounts|2024-11-24T10:00:00|broker_poller.py:45|
|INFO|Polling account: IBKR Main Account|2024-11-24T10:00:05|broker_poller.py:78|
|INFO|Account polled successfully. Equity: $1000000.00|2024-11-24T10:00:06|broker_poller.py:120|
|ERROR|Failed to connect to broker for account acc_abc123|2024-11-24T10:00:30|broker_poller.py:95|
```

## Dependencies

- **BrokerFactory** - For broker connections
- **MongoDB** - Account data storage
- **FastAPI/Uvicorn** - REST API framework
- **Pydantic** - Data validation
- **Python packages**:
  - `fastapi>=0.121.0`
  - `uvicorn>=0.38.0`
  - `pymongo>=4.6.1`
  - `pydantic>=2.12.4`
  - `python-dotenv>=1.0.0`

## Startup Command

```bash
# Via mvp_demo_start.py
python mvp_demo_start.py

# Manual startup
cd services/account_data_service
uvicorn account_data_main:app --host 0.0.0.0 --port 8082
```

## Health Checks

Check service status:
```bash
# Via status script
python mvp_demo_status.py

# Direct API call
curl http://localhost:8082/health

# Check if port is listening
lsof -i :8082
```

View logs:
```bash
tail -f logs/account_data_service.log
```

## Usage Examples

### Create IBKR Account via API
```python
import requests

account_data = {
    "account_name": "IBKR Main Account",
    "broker": "IBKR",
    "account_number": "U1234567",
    "authentication_details": {
        "auth_type": "TWS",
        "host": "127.0.0.1",
        "port": 4002,
        "client_id": 1
    }
}

response = requests.post(
    "http://localhost:8082/api/v1/accounts",
    json=account_data
)

print(response.json())
```

### Query Account from Cerebro Service
```python
import requests

# Get account state
response = requests.get(
    "http://localhost:8082/api/v1/account/IBKR Main Account/state"
)

account_state = response.json()
available_margin = account_state["margin_available"]
```

## Related Documentation

- [Brokers](brokers.md) - Broker abstraction layer used by this service
- [Cerebro Service](cerebro_service.md) - Queries this service for account data
- [Execution Service](execution_service.md) - Triggers position updates

## Common Issues

### Broker Connection Failures
- Verify broker is running (TWS/IB Gateway)
- Check IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID
- Ensure client_id is not already in use
- Check firewall/network settings

### Polling Not Updating
- Check `last_poll_time` in MongoDB
- Verify BrokerPoller thread is running
- Look for errors in logs
- Ensure MongoDB replica set is running

### Missing Account Data
- Verify account exists in `trading_accounts` collection
- Check account `status` is "ACTIVE"
- Ensure broker is connected
- Force sync via API: `POST /api/v1/accounts/{account_id}/sync`
