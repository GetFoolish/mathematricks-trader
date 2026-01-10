# Account Data Service

The Account Data Service is a FastAPI REST API that provides real-time account state information and margin calculations. It polls broker APIs in the background and serves data to Cerebro, Frontend, and other services.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Background Polling](#background-polling)
- [Configuration](#configuration)
- [Usage](#usage)

---

## Overview

### Purpose
- **REST API** for account state queries
- **Background Polling** of broker APIs (IBKR, Zerodha, Mock)
- **Margin Calculations** and previews
- **Real-time Updates** to trading_accounts collection

### Technology Stack
- **FastAPI** (REST API framework)
- **Uvicorn** (ASGI server)
- **PyMongo** (MongoDB driver)
- **APScheduler** (background jobs)

### Location
```
services/account_data_service/
├── account_data_main.py    # FastAPI app + background poller
├── repository.py           # MongoDB repository layer
├── models.py               # Pydantic models
├── config.py               # Configuration
├── broker_poller.py        # Broker API polling logic
└── requirements.txt        # Python dependencies
```

---

## Architecture

### Service Model
The Account Data Service runs two concurrent processes:

1. **FastAPI Server** (Port 8082)
   - Serves REST API endpoints
   - Queries MongoDB for account data
   - Performs margin calculations

2. **Background Poller** (every 30 seconds)
   - Connects to broker APIs (IBKR, Zerodha, Mock)
   - Fetches account balances, positions, margin
   - Updates trading_accounts collection

---

## API Endpoints

### Health Check
```http
GET /health

Response:
{
    "status": "healthy",
    "service": "account-data-service",
    "timestamp": "2024-01-09T12:00:00Z"
}
```

### List All Accounts
```http
GET /accounts

Response:
[
    {
        "account_id": "OANDA_MOCK",
        "fund_id": "fund_001",
        "broker": "OANDA",
        "balances": {
            "equity": 500000.00,
            "cash": 250000.00,
            "margin_used": 50000.00,
            "margin_available": 200000.00
        },
        "open_positions": [
            {
                "instrument": "SPY",
                "quantity": 100,
                "avg_entry_price": 450.25,
                "current_price": 455.50,
                "unrealized_pnl": 525.00
            }
        ]
    }
]
```

### Get Single Account
```http
GET /accounts/{account_id}

Example: GET /accounts/OANDA_MOCK

Response:
{
    "account_id": "OANDA_MOCK",
    "fund_id": "fund_001",
    "broker": "OANDA",
    "balances": {...},
    "open_positions": [...]
}
```

### Margin Preview
```http
POST /accounts/margin-preview

Request Body:
{
    "account_id": "OANDA_MOCK",
    "instrument": "SPY",
    "quantity": 100,
    "price": 450.25,
    "order_type": "MARKET"
}

Response:
{
    "margin_required": 9005.00,
    "margin_available": 200000.00,
    "margin_sufficient": true
}
```

---

## Background Polling

### Polling Logic

```python
def poll_broker_accounts():
    """
    Poll all broker APIs every 30 seconds

    For each account in trading_accounts:
    1. Determine broker type (IBKR/Zerodha/Mock)
    2. Connect to broker API
    3. Fetch account data:
       - Equity, cash, margin
       - Open positions
       - Realized/unrealized P&L
    4. Update trading_accounts collection
    """

    accounts = db.trading_accounts.find({})

    for account in accounts:
        broker_type = account['broker']

        if broker_type == 'IBKR':
            data = poll_ibkr_account(account)
        elif broker_type == 'ZERODHA':
            data = poll_zerodha_account(account)
        elif broker_type == 'MOCK':
            data = poll_mock_account(account)

        # Update MongoDB
        db.trading_accounts.update_one(
            {'account_id': account['account_id']},
            {'$set': {
                'balances': data['balances'],
                'open_positions': data['open_positions'],
                'last_updated': datetime.now(timezone.utc)
            }}
        )
```

### Polling Interval
- **Default**: Every 30 seconds
- **Configurable**: Set `POLL_INTERVAL_SECONDS` in `.env`

---

## Configuration

### Environment Variables

```bash
# .env file

# MongoDB Connection
MONGODB_URI=mongodb://mongodb:27017/mathematricks_trading

# Polling Configuration
POLL_INTERVAL_SECONDS=30

# Broker API Credentials (for polling)
IBKR_HOST=ib-gateway
IBKR_PORT=4002
IBKR_CLIENT_ID=1

ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
```

### Docker Compose

```yaml
services:
  account-data-service:
    build: ./services/account_data_service
    container_name: mathematricks-trader-account-data-service-1
    command: uvicorn account_data_main:app --host 0.0.0.0 --port 8082
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - POLL_INTERVAL_SECONDS=30
    ports:
      - "8082:8082"
    depends_on:
      - mongodb
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

# Standalone
cd services/account_data_service
uvicorn account_data_main:app --host 0.0.0.0 --port 8082
```

### Testing API Endpoints

```bash
# Health check
curl http://localhost:8082/health

# List all accounts
curl http://localhost:8082/accounts

# Get specific account
curl http://localhost:8082/accounts/OANDA_MOCK

# Margin preview
curl -X POST http://localhost:8082/accounts/margin-preview \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "OANDA_MOCK",
    "instrument": "SPY",
    "quantity": 100,
    "price": 450.25
  }'
```

### Monitoring

```bash
# View logs
docker logs mathematricks-trader-account-data-service-1 --tail 100 -f

# Expected output:
INFO:     Started server process [1]
INFO:     Uvicorn running on http://0.0.0.0:8082 (Press CTRL+C to quit)
INFO:     Background poller started (interval: 30s)
INFO:     Polled 5 accounts successfully
INFO:     Updated trading_accounts collection
```

---

## Related Documentation
- [Cerebro Service](cerebro_service.md) - Uses margin preview API
- [Frontend](frontend.md) - Displays account data
- [Brokers](brokers.md) - Broker API integrations
