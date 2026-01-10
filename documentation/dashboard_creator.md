# Dashboard Creator Service

The Dashboard Creator Service pre-computes dashboard JSONs for external websites (client websites, strategy developer portals) and provides real-time updates via Server-Sent Events (SSE).

## Overview

### Purpose
- **Pre-compute Dashboards**: Generate dashboard JSONs on schedule
- **Client Dashboards**: Portfolio metrics for clients
- **Signal Sender Dashboards**: Performance metrics for strategy developers
- **Widgets**: Individual widgets (fund balances, account statements)
- **SSE Streams**: Real-time updates via Server-Sent Events

### Technology Stack
- **FastAPI** (REST API + SSE)
- **APScheduler** (background jobs)
- **PyMongo** (MongoDB queries)

### Location
```
services/dashboard_creator/
├── dashboard_creator_main.py           # FastAPI app
├── generators/
│   ├── client_dashboard.py            # Client dashboard JSON
│   ├── signal_sender_dashboard.py     # Strategy developer dashboard
│   ├── fund_balances_widget.py        # Fund balance widget
│   └── account_statement_widget.py    # Account statement widget
└── schedulers/
    └── background_jobs.py              # Scheduled regeneration
```

---

## Features

### 1. Client Dashboard
**Purpose**: Show portfolio overview to clients

**Includes**:
- Total fund equity
- Realized P&L
- Unrealized P&L
- Open positions count
- Recent signals
- Strategy allocation chart

**Schedule**: Regenerates every 5 minutes

**API Endpoint**:
```http
GET /api/v1/dashboards/client

Response:
{
    "dashboard_type": "client",
    "generated_at": "2024-01-09T12:00:00Z",
    "data": {
        "fund_equity": 1000000.00,
        "realized_pnl": 25000.00,
        "unrealized_pnl": 5000.00,
        "open_positions_count": 3,
        "strategies": [...],
        "recent_activity": [...]
    }
}
```

### 2. Signal Sender Dashboard
**Purpose**: Show strategy performance to strategy developers

**Includes**:
- Signal count (total, accepted, rejected)
- Win rate
- Average P&L per signal
- Recent signals
- Monthly performance

**Schedule**: Regenerates every 1 minute

**API Endpoint**:
```http
GET /api/v1/dashboards/signal-sender/{strategy_id}

Example: GET /api/v1/dashboards/signal-sender/SPY

Response:
{
    "dashboard_type": "signal_sender",
    "strategy_id": "SPY",
    "generated_at": "2024-01-09T12:00:00Z",
    "data": {
        "total_signals": 100,
        "accepted_signals": 95,
        "rejected_signals": 5,
        "win_rate": 0.65,
        "avg_pnl_per_signal": 150.50,
        "recent_signals": [...]
    }
}
```

### 3. Widgets
**Purpose**: Individual embeddable widgets

**Available Widgets**:
- Fund Balances: Show equity across all funds
- Account Statement: Recent trades with P&L

**API Endpoint**:
```http
GET /api/v1/widgets/fund-balances
GET /api/v1/widgets/account-statement
```

### 4. SSE Stream
**Purpose**: Real-time updates via Server-Sent Events

**API Endpoint**:
```http
GET /api/v1/widgets/events

# Client connects and receives updates:
data: {"type": "fund_balance_update", "fund_equity": 1005000.00}
data: {"type": "new_signal", "signal_id": "sig_spy_001"}
```

---

## Usage

### Starting the Service

```bash
# Via Docker Compose
make start

# Access API at: http://localhost:8004

# Standalone
cd services/dashboard_creator
uvicorn dashboard_creator_main:app --host 0.0.0.0 --port 8004
```

### Fetching Dashboards

```bash
# Client dashboard
curl http://localhost:8004/api/v1/dashboards/client

# Signal sender dashboard
curl http://localhost:8004/api/v1/dashboards/signal-sender/SPY

# Force regeneration
curl -X POST http://localhost:8004/api/v1/dashboards/regenerate
```

### SSE Client (JavaScript)
```javascript
const eventSource = new EventSource('http://localhost:8004/api/v1/widgets/events');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Dashboard update:', data);

    if (data.type === 'fund_balance_update') {
        updateFundBalance(data.fund_equity);
    }
};
```

---

## Configuration

```yaml
# docker-compose.yml
services:
  dashboard-creator:
    build: ./services/dashboard_creator
    command: uvicorn dashboard_creator_main:app --host 0.0.0.0 --port 8004
    environment:
      - MONGODB_URI=${MONGODB_URI}
    ports:
      - "8004:8004"
    depends_on:
      - mongodb
    restart: unless-stopped
```

---

## Related Documentation
- [Frontend](frontend.md) - Admin dashboard
- [Signal Ingestion](signal_ingestion_service.md) - Signal processing
