# Dashboard Creator Service

## Overview

The Dashboard Creator Service generates pre-computed dashboard JSONs for clients and strategy developers. It aggregates data from multiple collections, computes metrics, and caches results in MongoDB for fast API access.

**Main File:** `services/dashboard_creator/dashboard_creator_main.py`  
**Port:** 8004  
**Framework:** FastAPI

## Purpose

- **Client Dashboard** - Investor-facing performance overview
- **Signal Sender Dashboard** - Strategy developer metrics and activity
- **Widget Generation** - Reusable dashboard components
- **Background Scheduling** - Periodic dashboard updates (1-5 minutes)
- **Data Caching** - Pre-computed JSONs for fast retrieval
- **Server-Sent Events (SSE)** - Real-time widget updates (optional)

## Architecture

### How It Works

```
MongoDB Collections → Dashboard Generators → dashboard_snapshots → API Endpoints
    (Raw Data)           (Aggregation)          (Cached JSON)       (Fast Retrieval)
         ↓
  Background Scheduler
  (Every 1-5 minutes)
```

### Key Components

1. **Dashboard Generators**
   - `client_dashboard.py` - Client-facing overview
   - `signal_sender_dashboard.py` - Strategy developer stats
   - `fund_balances_widget.py` - Account balances widget
   - `account_statement_widget.py` - Transaction history
   - `system_health_widget.py` - Service status monitoring

2. **Background Scheduler**
   - APScheduler integration
   - Configurable intervals per dashboard type
   - Event emission for real-time updates

3. **Cache Layer**
   - `dashboard_snapshots` collection
   - Separate documents per dashboard type
   - `updated_at` timestamp for staleness detection

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | Required |

### Refresh Intervals

Configured in `schedulers/background_jobs.py`:

```python
REFRESH_INTERVALS = {
    'client_dashboard': 300,        # 5 minutes
    'signal_sender_dashboard': 60,  # 1 minute
    'fund_balances': 30,            # 30 seconds
    'system_health': 10             # 10 seconds
}
```

## MongoDB Collections

### Input Collections

#### `signal_store`
Signal lifecycle tracking:
```javascript
{
  signal_id: "SIGNAL_123",
  strategy_id: "MaxCAGR_v2",
  legs: [
    {
      decision: { status: "APPROVED" },
      execution: { status: "FILLED", avg_fill_price: 150.0 }
    }
  ],
  position: { status: "CLOSED", pnl: 250.0 }
}
```

#### `trading_accounts`
Account balances and positions:
```javascript
{
  account_id: "IBKR_Paper",
  balances: {
    equity: 100000.0,
    unrealized_pnl: 250.0
  },
  open_positions: [...]
}
```

#### `strategies`
Strategy configurations and metrics:
```javascript
{
  strategy_id: "MaxCAGR_v2",
  backtest: {
    metrics: {
      cagr: 0.15,
      sharpe_ratio: 1.8
    }
  }
}
```

#### `funds`
Fund architecture:
```javascript
{
  fund_id: "main_fund",
  approved_allocation: {
    "MaxCAGR_v2": 0.60,
    "MeanReversion_v1": 0.40
  },
  accounts: ["IBKR_Paper", "IBKR_Live"]
}
```

### Output Collection: `dashboard_snapshots`

```javascript
{
  _id: ObjectId,
  dashboard_type: "client" | "signal_sender" | "widget",
  strategy_id: "MaxCAGR_v2",  // For signal_sender dashboards
  widget_id: "fund_balances",  // For widgets
  
  // Dashboard JSON (varies by type)
  data: {
    // For client dashboard
    overview: {
      total_equity: 250000.0,
      total_pnl: 5250.0,
      active_strategies: 5
    },
    
    // For signal_sender dashboard
    signals_today: 12,
    approved_rate: 0.85,
    avg_fill_time_ms: 250,
    
    // For widgets
    balances: [...]
  },
  
  updated_at: ISODate,
  expires_at: ISODate  // For TTL index (optional)
}
```

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "DashboardCreatorService",
  "version": "1.0.0",
  "mongodb_connected": true,
  "scheduler_running": true
}
```

### `GET /api/v1/dashboards/client`
Get client dashboard (cached, updates every 5 minutes).

**Response:**
```json
{
  "overview": {
    "total_equity": 250000.0,
    "total_pnl": 5250.0,
    "total_pnl_pct": 2.14,
    "active_strategies": 5,
    "active_positions": 8
  },
  "performance": {
    "daily_pnl": 125.0,
    "weekly_pnl": 850.0,
    "monthly_pnl": 2100.0
  },
  "strategies": [
    {
      "strategy_id": "MaxCAGR_v2",
      "allocation": 0.60,
      "pnl": 3150.0,
      "sharpe_ratio": 1.8
    }
  ],
  "recent_signals": [
    {
      "signal_id": "SIGNAL_123",
      "strategy": "MaxCAGR_v2",
      "status": "FILLED",
      "timestamp": "2026-02-02T12:34:56Z"
    }
  ]
}
```

### `GET /api/v1/dashboards/signal-sender/{strategy_id}`
Get signal sender dashboard (cached, updates every 1 minute).

**Response:**
```json
{
  "strategy_id": "MaxCAGR_v2",
  "strategy_name": "Max CAGR Strategy v2",
  
  "activity_summary": {
    "signals_today": 12,
    "signals_this_week": 58,
    "signals_this_month": 245
  },
  
  "approval_stats": {
    "approved_rate": 0.85,
    "rejected_rate": 0.10,
    "pending_rate": 0.05
  },
  
  "execution_stats": {
    "fill_rate": 0.98,
    "avg_fill_time_ms": 250,
    "avg_slippage_bps": 2.5
  },
  
  "recent_signals": [
    {
      "signal_id": "SIGNAL_123",
      "timestamp": "2026-02-02T12:34:56Z",
      "decision": "APPROVED",
      "execution": "FILLED",
      "pnl": 125.0
    }
  ],
  
  "performance": {
    "total_pnl": 3150.0,
    "win_rate": 0.65,
    "sharpe_ratio": 1.8
  }
}
```

### `POST /api/v1/dashboards/regenerate`
Force regeneration of all dashboards (bypass cache).

**Response:**
```json
{
  "status": "success",
  "regenerated": [
    "client_dashboard",
    "signal_sender_dashboard_MaxCAGR_v2"
  ],
  "timestamp": "2026-02-02T12:34:56Z"
}
```

## Dashboard Generators

### Client Dashboard

**File:** `generators/client_dashboard.py`

**Data Sources:**
- `trading_accounts` - Total equity, PnL
- `funds` - Fund allocations
- `signal_store` - Recent signals, position status
- `strategies` - Strategy metrics

**Aggregations:**
```python
# Total equity across all accounts
total_equity = sum(account['balances']['equity'] for account in accounts)

# Daily PnL (positions opened/closed today)
daily_pnl = sum(signal['position']['pnl'] for signal in todays_signals)

# Active strategies (those with open positions)
active_strategies = len(set(signal['strategy_id'] for signal in open_signals))
```

### Signal Sender Dashboard

**File:** `generators/signal_sender_dashboard.py`

**Data Sources:**
- `signal_store` - Filtered by `strategy_id`
- `strategies` - Strategy configuration

**Aggregations:**
```python
# Approval rate
approved = len([s for s in signals if s['decision']['status'] == 'APPROVED'])
total = len(signals)
approval_rate = approved / total

# Fill rate
filled = len([s for s in signals if s['execution']['status'] == 'FILLED'])
executed = len([s for s in signals if 'execution' in s])
fill_rate = filled / executed

# Avg fill time
fill_times = [signal['processing_lag'] for signal in signals if 'processing_lag' in signal]
avg_fill_time_ms = sum(fill_times) / len(fill_times) * 1000
```

### Fund Balances Widget

**File:** `generators/fund_balances_widget.py`

**Output:**
```json
{
  "widget_id": "fund_balances",
  "balances": [
    {
      "fund_id": "main_fund",
      "total_equity": 250000.0,
      "accounts": [
        {
          "account_id": "IBKR_Paper",
          "equity": 100000.0,
          "unrealized_pnl": 250.0
        }
      ]
    }
  ]
}
```

### System Health Widget

**File:** `generators/system_health_widget.py`

**Checks:**
- Service connectivity (Cerebro, Execution, Account Data)
- MongoDB connection
- Change Stream status
- Recent error logs

**Output:**
```json
{
  "widget_id": "system_health",
  "services": {
    "cerebro": { "status": "healthy", "response_time_ms": 25 },
    "execution": { "status": "healthy", "broker_pool_ready": true },
    "account_data": { "status": "healthy", "poller_running": true }
  },
  "mongodb": { "status": "connected", "ping_ms": 5 },
  "overall_status": "healthy"
}
```

## Background Scheduler

**File:** `schedulers/background_jobs.py`

### Scheduler Configuration

Uses `APScheduler` with `BackgroundScheduler`:

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Client dashboard - every 5 minutes
scheduler.add_job(
    func=generate_client_dashboard,
    trigger='interval',
    seconds=300,
    id='client_dashboard',
    replace_existing=True
)

# Signal sender dashboards - every 1 minute
for strategy_id in active_strategies:
    scheduler.add_job(
        func=lambda: generate_signal_sender_dashboard(strategy_id),
        trigger='interval',
        seconds=60,
        id=f'signal_sender_{strategy_id}',
        replace_existing=True
    )

scheduler.start()
```

### Event Emission (SSE)

For real-time updates (future feature):

```python
import asyncio
import queue

widget_update_events = queue.Queue()

# In generator functions
def generate_fund_balances_widget():
    widget_data = {...}
    widget_update_events.put({
        'widget_id': 'fund_balances',
        'data': widget_data
    })
    return widget_data
```

## Example Usage

### Getting Client Dashboard

```python
import requests

response = requests.get('http://localhost:8004/api/v1/dashboards/client')
dashboard = response.json()

print(f"Total Equity: ${dashboard['overview']['total_equity']:,.2f}")
print(f"Total PnL: ${dashboard['overview']['total_pnl']:,.2f}")
print(f"Active Strategies: {dashboard['overview']['active_strategies']}")
```

### Getting Signal Sender Dashboard

```python
import requests

strategy_id = "MaxCAGR_v2"
response = requests.get(f'http://localhost:8004/api/v1/dashboards/signal-sender/{strategy_id}')
dashboard = response.json()

print(f"Signals Today: {dashboard['activity_summary']['signals_today']}")
print(f"Approval Rate: {dashboard['approval_stats']['approved_rate']:.1%}")
print(f"Fill Rate: {dashboard['execution_stats']['fill_rate']:.1%}")
```

### Force Regeneration

```python
import requests

response = requests.post('http://localhost:8004/api/v1/dashboards/regenerate')
result = response.json()

print(f"Regenerated {len(result['regenerated'])} dashboards")
```

## Troubleshooting

### Problem: Dashboard shows stale data
**Cause:** Scheduler not running or cache not refreshing
**Solutions:**
- Check `/health` endpoint: `scheduler_running` should be `true`
- Force regenerate: `POST /api/v1/dashboards/regenerate`
- Restart service

### Problem: Missing strategy in signal sender dashboards
**Cause:** Strategy not in scheduler job list
**Solutions:**
- Add strategy to `active_strategies` list in `background_jobs.py`
- Restart service to pick up new strategies
- Check strategy exists in `strategies` collection

### Problem: Dashboard returns 500 error
**Cause:** Missing data or aggregation error
**Debug:**
- Check service logs for stack trace
- Verify required collections exist and have data
- Test generator function directly: `generate_client_dashboard()`

### Problem: NaN or Inf values in dashboard
**Cause:** Division by zero or invalid calculations
**Solutions:**
- Check for empty arrays before computing averages
- Handle zero denominators: `pnl / equity if equity > 0 else 0`
- Sanitize floats: `value if not math.isnan(value) else 0`

### Problem: Slow dashboard load times
**Cause:** Large aggregations or missing indexes
**Solutions:**
- Add MongoDB indexes on frequently queried fields
- Limit query ranges (e.g., last 30 days only)
- Use projection to fetch only required fields
- Increase cache TTL to reduce regeneration frequency

## Performance Notes

- **Client Dashboard Generation:** ~500ms (depends on account count)
- **Signal Sender Dashboard:** ~200ms (single strategy)
- **Widget Generation:** ~50-100ms
- **API Response Time:** ~5-10ms (from cache)
- **MongoDB Queries:** ~10-50ms per aggregation

## Dependencies

- `fastapi` - Web framework
- `pymongo` - MongoDB driver
- `apscheduler` - Background task scheduling
- `uvicorn` - ASGI server

## Related Services

- **Cerebro Service** - Provides decision data
- **Execution Service** - Provides execution data
- **Account Data Service** - Provides balance data
- **Portfolio Builder** - Provides strategy metrics

## Caching Strategy

### TTL (Time-To-Live)
- Client dashboard: 5 minutes
- Signal sender dashboard: 1 minute
- Widgets: 10-30 seconds

### Cache Invalidation
- On-demand via `/api/v1/dashboards/regenerate`
- Scheduled regeneration by background jobs
- Manual MongoDB update (advanced)

### Staleness Detection

Frontend can check `updated_at` field:

```javascript
const response = await fetch('/api/v1/dashboards/client');
const dashboard = await response.json();

const age = Date.now() - new Date(dashboard.updated_at).getTime();
if (age > 300000) {  // 5 minutes
    console.warn('Dashboard data is stale');
}
```

## Future Enhancements

### Real-Time Updates via SSE
- Server-Sent Events for widget updates
- Eliminates polling from frontend
- Sub-second latency

### Custom Dashboard Builder
- Drag-and-drop widget placement
- Personalized layouts
- Per-user preferences

### Alert Thresholds
- Notify when metrics exceed limits
- Email/Telegram alerts
- Custom triggers per dashboard type

## Logging

### Files
- Console output (no file logging in Docker)

### Log Format
```
|INFO|Dashboard regenerated: client_dashboard|2026-02-02 12:34:56|file:background_jobs.py:line No.45
```

### Key Log Events
- Dashboard generation started/completed
- Scheduler job execution
- MongoDB connection status
- API request handling
- Error stack traces

## Safety Features

### Error Handling
- Graceful degradation if data missing
- Default values for missing fields
- Exception catching in generators
- Rollback to cached data on error

### Data Validation
- Check for None/null before calculations
- Validate date ranges
- Filter out invalid signals
- Sanitize NaN/Inf values

### Scheduler Resilience
- Missed execution policy: "fire_and_forget"
- Job coalescing: prevent overlapping runs
- Max instances: 1 per job
- Graceful shutdown on service stop
