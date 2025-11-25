# Dashboard Creator Service

## Overview

The Dashboard Creator Service generates pre-computed dashboard JSONs for clients and strategy developers. It aggregates data from multiple sources, calculates performance metrics, and updates dashboards on a scheduled basis.

## Location

`/services/dashboard_creator/`

## Key Responsibilities

1. Generate client-facing dashboards with fund-level metrics
2. Generate strategy developer dashboards with signal performance
3. Schedule automatic dashboard updates
4. Provide API endpoints for on-demand dashboard refresh
5. Aggregate data from MongoDB collections
6. Calculate performance metrics (win rate, PnL, etc.)
7. Format data for frontend consumption

## Main Files

### main.py
- FastAPI service entry point
- API endpoints
- Service lifecycle management
- Scheduler coordination

### generators/client_dashboard.py
- Generates client dashboard JSON
- Fund-level metrics aggregation
- Account allocation breakdown
- Risk metrics calculation

### generators/signal_sender_dashboard.py
- Generates strategy developer dashboard
- Strategy-specific performance metrics
- Signal fill analysis
- Win rate / loss rate calculations

### schedulers/background_jobs.py
- APScheduler job definitions
- Dashboard refresh scheduling
- Periodic update management

### api/strategy_developer_api.py
- Strategy developer specific endpoints
- Signal history queries
- Performance reports

## REST API Endpoints

**Port:** 8004

### Dashboard Endpoints

#### Get Client Dashboard
```
GET /api/dashboards/client

Response: 200 OK
{
  "fund_name": "Mathematricks Fund",
  "as_of_date": "2024-11-24T10:30:00Z",
  "overview": {
    "total_aum": 5000000.00,
    "total_equity": 5250000.00,
    "total_pnl": 250000.00,
    "total_pnl_pct": 5.0,
    "margin_utilization": 35.5,
    "number_of_strategies": 5,
    "open_positions": 23
  },
  "accounts": [
    {
      "account_name": "IBKR Main Account",
      "broker": "IBKR",
      "equity": 1000000.00,
      "cash": 500000.00,
      "margin_used": 250000.00,
      "unrealized_pnl": 50000.00
    }
  ],
  "strategy_performance": [
    {
      "strategy_name": "SPX 1-Day Options",
      "allocation": 0.25,
      "pnl": 75000.00,
      "pnl_pct": 15.0,
      "win_rate": 67.0,
      "number_of_trades": 125,
      "sharpe_ratio": 1.85
    }
  ],
  "risk_metrics": {
    "max_drawdown": 8.5,
    "var_95": 25000.00,
    "portfolio_beta": 0.85
  },
  "recent_signals": [ ... ]
}
```

#### Get Signal Sender Dashboard
```
GET /api/dashboards/signal-sender?strategy_name=SPX 1-Day Options

Response: 200 OK
{
  "strategy_name": "SPX 1-Day Options",
  "developer_name": "John Doe",
  "as_of_date": "2024-11-24T10:30:00Z",
  "performance": {
    "total_signals_sent": 250,
    "signals_filled": 235,
    "signals_rejected": 15,
    "fill_rate": 94.0,
    "total_pnl": 75000.00,
    "win_rate": 67.0,
    "avg_win": 550.00,
    "avg_loss": -280.00,
    "profit_factor": 1.96,
    "sharpe_ratio": 1.85
  },
  "signal_history": [
    {
      "signal_id": "sig_1732450800_5678",
      "sent_at": "2024-11-24T10:30:00Z",
      "symbol": "SPY",
      "side": "BUY",
      "quantity_requested": 100,
      "quantity_filled": 100,
      "fill_price": 235.15,
      "status": "FILLED",
      "pnl": 450.00
    }
  ],
  "lag_metrics": {
    "avg_signal_to_fill_seconds": 12.5,
    "median_signal_to_fill_seconds": 10.0,
    "max_signal_to_fill_seconds": 45.0
  },
  "current_positions": [
    {
      "symbol": "SPY",
      "quantity": 100,
      "entry_price": 235.15,
      "current_price": 237.00,
      "unrealized_pnl": 185.00
    }
  ]
}
```

#### Force Dashboard Refresh
```
POST /api/dashboards/refresh

Response: 200 OK
{
  "message": "Dashboards refreshed successfully",
  "client_dashboard_updated": true,
  "signal_sender_dashboards_updated": 5,
  "timestamp": "2024-11-24T10:30:00Z"
}
```

#### Health Check
```
GET /health

Response: 200 OK
{
  "status": "healthy",
  "service": "dashboard_creator",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

## Dashboard Generation Logic

### Client Dashboard Generation

**Data Sources:**
- `trading_accounts` collection → Account balances and positions
- `signal_store` collection → Signal performance data
- `positions` collection → Open positions
- `strategies` collection → Strategy metadata

**Calculations:**
1. **Fund-Level Metrics**
   - Total AUM = Sum of all account equities
   - Total PnL = Sum of realized + unrealized PnL
   - Margin Utilization = (Total Margin Used / Total Margin Available) × 100

2. **Strategy Performance**
   - Per-strategy PnL from execution confirmations
   - Win rate = (Winning trades / Total trades) × 100
   - Sharpe ratio from historical returns

3. **Risk Metrics**
   - Max drawdown from equity curve
   - VaR (Value at Risk) calculation
   - Portfolio beta vs benchmark

### Signal Sender Dashboard Generation

**Data Sources:**
- `signal_store` collection → All signals for strategy
- `execution_confirmations` collection → Fill details
- `positions` collection → Current positions

**Calculations:**
1. **Signal Metrics**
   - Fill rate = (Filled signals / Total signals) × 100
   - Rejection reasons breakdown
   - Signal lag = Time from signal receipt to fill

2. **Performance Metrics**
   - Total PnL = Sum of all trade PnLs
   - Win rate = (Winning trades / Total trades) × 100
   - Profit factor = Gross profit / Gross loss
   - Average win/loss

3. **Lag Metrics**
   - Signal to fill latency statistics
   - Percentile breakdown (50th, 95th, 99th)

## Scheduling

### Background Jobs

Located in `schedulers/background_jobs.py`

**APScheduler Jobs:**

1. **Client Dashboard Refresh**
   - Frequency: Every 5 minutes
   - Job: `refresh_client_dashboard()`
   - Runs during market hours

2. **Signal Sender Dashboard Refresh**
   - Frequency: Every 15 minutes
   - Job: `refresh_signal_sender_dashboards()`
   - Updates all active strategies

3. **End-of-Day Summary**
   - Frequency: Daily at 16:30 EST
   - Job: `generate_eod_summary()`
   - Sends daily performance summary

**Scheduler Configuration:**
```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Client dashboard every 5 minutes
scheduler.add_job(
    refresh_client_dashboard,
    'interval',
    minutes=5,
    id='client_dashboard_refresh'
)

# Signal sender dashboards every 15 minutes
scheduler.add_job(
    refresh_signal_sender_dashboards,
    'interval',
    minutes=15,
    id='signal_sender_dashboard_refresh'
)

scheduler.start()
```

## MongoDB Collections

### signal_store (Read)
Reads signal data for performance analysis:
```json
{
  "signal_id": "sig_1732450800_5678",
  "strategy_name": "SPX 1-Day Options",
  "received_time": "2024-11-24T10:30:00Z",
  "cerebro_decision": { ... },
  "execution_status": "FILLED",
  "filled_at": "2024-11-24T10:30:12Z"
}
```

### execution_confirmations (Read)
Reads fill data for PnL calculations:
```json
{
  "signal_id": "sig_1732450800_5678",
  "avg_fill_price": 235.15,
  "filled_quantity": 100,
  "commission": 1.00,
  "total_value": 23515.00
}
```

### positions (Read)
Reads current positions for dashboard display:
```json
{
  "strategy_name": "SPX 1-Day Options",
  "symbol": "SPY",
  "quantity": 100,
  "unrealized_pnl": 185.00
}
```

### trading_accounts (Read)
Reads account data for fund-level metrics:
```json
{
  "account_name": "IBKR Main Account",
  "balances": {
    "equity": 1000000.00,
    "unrealized_pnl": 50000.00
  }
}
```

## Configuration

### Environment Variables
```bash
# MongoDB connection
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0

# Service port
DASHBOARD_CREATOR_PORT=8004

# Scheduler settings (hardcoded in background_jobs.py)
CLIENT_DASHBOARD_REFRESH_MINUTES=5
SIGNAL_SENDER_DASHBOARD_REFRESH_MINUTES=15

# Dashboard output (optional)
DASHBOARD_OUTPUT_DIR=/path/to/dashboard_output
```

## Error Handling

1. **MongoDB Query Failures**
   - Logs error with query details
   - Returns cached dashboard if available
   - Retries on next scheduled run

2. **Missing Data**
   - Handles missing strategies gracefully
   - Shows "N/A" for unavailable metrics
   - Logs warning for investigation

3. **Calculation Errors**
   - Validates input data
   - Handles division by zero
   - Returns null for invalid metrics

4. **Scheduler Failures**
   - APScheduler handles job failures
   - Jobs retry on next schedule
   - Logs all failures

## Logging

Logs to:
- Console (real-time output)
- `logs/dashboard_creator.log` (service-specific)

Log format:
```
|LEVEL|Message|Timestamp|file:filename.py:line No.LineNumber|
```

Example log entries:
```
|INFO|Dashboard Creator service started on port 8004|2024-11-24T10:00:00|main.py:25|
|INFO|Refreshing client dashboard|2024-11-24T10:05:00|client_dashboard.py:45|
|INFO|Client dashboard updated. Strategies: 5, Positions: 23|2024-11-24T10:05:03|client_dashboard.py:150|
|INFO|Refreshing signal sender dashboards for 5 strategies|2024-11-24T10:15:00|signal_sender_dashboard.py:30|
|WARNING|No execution data found for strategy: Test Strategy|2024-11-24T10:15:02|signal_sender_dashboard.py:120|
```

## Dependencies

- **FastAPI/Uvicorn** - REST API framework
- **MongoDB** - Data source
- **APScheduler** - Background job scheduling
- **Pandas** - Data aggregation and analysis
- **NumPy** - Numerical calculations
- **Python packages**:
  - `fastapi>=0.121.0`
  - `uvicorn>=0.38.0`
  - `pymongo>=4.6.1`
  - `apscheduler>=3.11.1`
  - `pandas>=2.3.3`
  - `numpy>=2.3.4`

## Startup Command

```bash
# Via mvp_demo_start.py
python mvp_demo_start.py

# Manual startup
cd services/dashboard_creator
uvicorn main:app --host 0.0.0.0 --port 8004

# With reload for development
uvicorn main:app --reload --port 8004
```

## Health Checks

Check service status:
```bash
# Via status script
python mvp_demo_status.py

# Direct API call
curl http://localhost:8004/health

# Check if port is listening
lsof -i :8004
```

View logs:
```bash
tail -f logs/dashboard_creator.log
```

## Usage Examples

### Fetch Client Dashboard
```python
import requests

response = requests.get("http://localhost:8004/api/dashboards/client")
dashboard = response.json()

print(f"Total AUM: ${dashboard['overview']['total_aum']:,.2f}")
print(f"Total PnL: ${dashboard['overview']['total_pnl']:,.2f}")
print(f"Number of Strategies: {dashboard['overview']['number_of_strategies']}")
```

### Fetch Strategy Developer Dashboard
```python
import requests

response = requests.get(
    "http://localhost:8004/api/dashboards/signal-sender",
    params={"strategy_name": "SPX 1-Day Options"}
)

dashboard = response.json()
print(f"Fill Rate: {dashboard['performance']['fill_rate']:.1f}%")
print(f"Win Rate: {dashboard['performance']['win_rate']:.1f}%")
print(f"Total PnL: ${dashboard['performance']['total_pnl']:,.2f}")
```

### Force Refresh
```python
import requests

response = requests.post("http://localhost:8004/api/dashboards/refresh")
result = response.json()
print(f"Dashboards refreshed at {result['timestamp']}")
```

## Frontend Integration

The Dashboard Creator service provides JSON data consumed by:

1. **Admin Frontend** (`frontend-admin/`)
   - Displays client dashboard
   - Shows all strategies and accounts
   - Real-time updates via periodic polling

2. **Client Dashboard** (future)
   - Client-facing view
   - Limited to specific account data
   - Custom branding per client

3. **Strategy Developer Portal** (future)
   - Developer-specific dashboard
   - Signal performance tracking
   - Historical analysis

## Performance Considerations

- Dashboard generation time: 1-5 seconds (depends on data volume)
- Client dashboard: ~2-3 seconds
- Signal sender dashboards: ~1-2 seconds per strategy
- Scheduled updates don't block API requests
- Dashboards cached in memory between updates

## Related Documentation

- [Signal Ingestion Service](signal_ingestion.md) - Provides signal data
- [Execution Service](execution_service.md) - Provides fill data
- [Account Data Service](account_data_service.md) - Provides account balances
- [Portfolio Builder](portfolio_builder.md) - Provides strategy metadata

## Common Issues

### Dashboards Not Updating
- Check scheduler is running (look for APScheduler logs)
- Verify MongoDB connectivity
- Check for errors in `dashboard_creator.log`
- Force refresh via API: `POST /api/dashboards/refresh`

### Missing Strategy Data
- Ensure strategy exists in `strategies` collection
- Check signal_store for strategy signals
- Verify strategy_name matches exactly (case-sensitive)
- Look for warnings in logs

### Incorrect Metrics
- Verify data in MongoDB collections
- Check calculation logic in generators
- Test with known data set
- Compare with manual calculations

### High Memory Usage
- Dashboard caching may use significant memory
- Large number of signals affects aggregation
- Consider implementing pagination
- Archive old signals to separate collection

## Future Enhancements

1. **Real-time Updates**
   - WebSocket support for live dashboard updates
   - Eliminate polling from frontend

2. **Custom Dashboards**
   - User-configurable widgets
   - Drag-and-drop dashboard builder

3. **Alerts and Notifications**
   - Threshold-based alerts
   - Daily summary emails
   - Push notifications

4. **Historical Comparison**
   - Compare current vs previous periods
   - Year-over-year analysis
   - Benchmark comparison

5. **Export Features**
   - PDF report generation
   - CSV data export
   - Excel workbook creation
