# Mathematricks Trading Services Documentation

Comprehensive documentation for all microservices in the Mathematricks algorithmic trading platform.

## Overview

The Mathematricks trading system consists of 7 core services that work together to receive signals, make portfolio decisions, execute trades, and monitor performance.

```
┌─────────────────┐
│  Trading Signal │
│    (Webhook)    │
└────────┬────────┘
         │
         v
┌─────────────────┐      ┌──────────────┐
│     Signal      │      │   Portfolio  │
│   Ingestion     │─────>│   Builder    │
│  (mongodb_watcher)     │   (Research)  │
└────────┬────────┘      └──────────────┘
         │
         v
┌─────────────────┐      ┌──────────────┐
│     Cerebro     │<────>│  Account     │
│    Service      │      │  Data Service│
│ (Decision Making)      │  (Broker Poll)│
└────────┬────────┘      └──────────────┘
         │
         v
┌─────────────────┐      ┌──────────────┐
│   Execution     │      │  Dashboard   │
│    Service      │      │   Creator    │
│ (Order Routing) │      │  (Reporting) │
└─────────────────┘      └──────────────┘
         │
         v
┌─────────────────┐
│    Telegram     │
│   Notifier      │
│ (Notifications) │
└─────────────────┘
```

## Services

### 1. Signal Ingestion Service
**File:** [SIGNAL_INGESTION.md](./SIGNAL_INGESTION.md)  
**Port:** N/A (MongoDB Change Stream listener)  
**Purpose:** Entry point for all trading signals

Watches MongoDB for new signals via Change Streams, normalizes signal data, links ENTRY→EXIT signals, and forwards to Cerebro for processing.

**Key Features:**
- Real-time signal processing via MongoDB Change Streams
- Consolidated schema (one document per signal)
- Automatic catchup on missed signals
- Signal linking (ENTRY/EXIT/SCALE)

---

### 2. Cerebro Service
**File:** [CEREBRO_SERVICE.md](./CEREBRO_SERVICE.md)  
**Port:** 8001  
**Purpose:** Intelligent core for portfolio management and risk assessment

Makes portfolio decisions, validates risk constraints, sizes positions, and generates execution orders.

**Key Features:**
- Portfolio construction algorithms (MaxCAGR, MaxSharpe, MaxHybrid)
- Hard margin limits (40% max utilization)
- Multi-account capital distribution
- Detailed decision math recording
- Signal type classification (ENTRY/EXIT detection)

**API Endpoints:**
- `POST /api/v1/process-signal` - Process trading signal
- `GET /health` - Health check
- `GET /status` - Service status

---

### 3. Execution Service
**File:** [EXECUTION_SERVICE.md](./EXECUTION_SERVICE.md)  
**Port:** 8083  
**Purpose:** Order execution and broker connectivity

Connects to brokers (IBKR, Zerodha, Mock), executes orders, reports fills, and manages gateway lifecycle.

**Key Features:**
- Broker pool management (pre-initialized connections)
- IBKR Gateway container management
- Order queue with sequential processing
- Event-driven execution via Change Streams
- Market hours validation

**API Endpoints:**
- `POST /api/v1/execute-order` - Execute order
- `POST /api/v1/sync-account-balance` - Sync broker balances
- `GET /market_status` - Check market hours
- `GET /health` - Health check (503 until broker pool ready)

---

### 4. Account Data Service
**File:** [ACCOUNT_DATA_SERVICE.md](./ACCOUNT_DATA_SERVICE.md)  
**Port:** 8082  
**Purpose:** Account balance and position management

Polls brokers for balances and positions, provides margin data for position sizing, and triggers event-driven updates.

**Key Features:**
- Scheduled polling (every 5 minutes)
- Event-driven polling (on position changes)
- Margin preview calculations
- Fund-level aggregation
- Position tracking

**API Endpoints:**
- `POST /api/v1/accounts` - Create account
- `GET /api/v1/accounts` - List all accounts
- `GET /api/v1/accounts/{account_id}` - Get account details
- `POST /api/v1/accounts/{account_id}/sync` - Force sync
- `GET /api/v1/account/{account_name}/margin` - Get margin info
- `POST /api/v1/account/{account_name}/margin-preview` - Preview margin requirement
- `GET /api/v1/fund/state` - Get fund aggregation

---

### 5. Portfolio Builder Service
**File:** [PORTFOLIO_BUILDER.md](./PORTFOLIO_BUILDER.md)  
**Port:** 8003  
**Purpose:** Strategy management and portfolio optimization

Handles strategy CRUD, backtest uploads, portfolio testing, and public submissions.

**Key Features:**
- CSV backtest processing
- Metrics calculation (CAGR, Sharpe, drawdown)
- Portfolio optimization algorithms
- Tearsheet generation (QuantStats)
- Public strategy submission workflow
- Allocation approval lifecycle

**API Endpoints:**
- `GET /api/v1/strategies` - List all strategies
- `GET /api/v1/strategies/{strategy_id}` - Get strategy details
- `POST /api/v1/strategies` - Create strategy
- `POST /api/v1/strategies/{strategy_id}/upload-backtest` - Upload backtest CSV
- `GET /api/v1/allocations/current` - Get approved allocations
- `POST /api/v1/allocations/approve` - Approve allocation
- `POST /api/v1/public/submit-strategy` - Submit strategy (public)
- `GET /api/v1/admin/submissions` - List submissions (admin)

---

### 6. Dashboard Creator Service
**File:** [DASHBOARD_CREATOR.md](./DASHBOARD_CREATOR.md)  
**Port:** 8004  
**Purpose:** Pre-computed dashboard JSON generation

Generates cached dashboards for clients and strategy developers with periodic background updates.

**Key Features:**
- Client dashboard (investor overview)
- Signal sender dashboard (strategy developer stats)
- Widget generation (balances, health, statements)
- Background scheduler (APScheduler)
- Cached responses for fast API access

**API Endpoints:**
- `GET /api/v1/dashboards/client` - Client dashboard (cached)
- `GET /api/v1/dashboards/signal-sender/{strategy_id}` - Strategy dashboard
- `POST /api/v1/dashboards/regenerate` - Force regeneration
- `GET /health` - Health check

**Refresh Intervals:**
- Client dashboard: 5 minutes
- Signal sender dashboard: 1 minute
- Widgets: 10-30 seconds

---

### 7. Telegram Notifier
**File:** [TELEGRAM.md](./TELEGRAM.md)  
**Type:** Library module (not standalone service)  
**Purpose:** Real-time notifications via Telegram

Sends alerts for signals, executions, position updates, and system events.

**Key Features:**
- Environment-aware channel routing (production/staging)
- HTML-formatted messages
- Signal lag reporting
- Trade execution confirmations
- Position P&L updates

**Notification Types:**
- Signal received
- Trade executed
- Position updated
- Custom alerts

**Integration:** Used by Execution Service and Cerebro Service

---

## MongoDB Collections

### Core Collections

| Collection | Purpose | Primary Service |
|------------|---------|-----------------|
| `trading_signals_raw` | Raw webhook signals | Signal Ingestion |
| `signal_store` | Consolidated signal lifecycle | All services |
| `trading_orders` | Order queue | Cerebro → Execution |
| `trading_accounts` | Account balances/positions | Account Data |
| `strategies` | Strategy configs + backtests | Portfolio Builder |
| `funds` | Fund architecture | Cerebro |
| `portfolio_tests` | Portfolio optimization results | Portfolio Builder |
| `portfolio_allocations` | Allocation tracking | Portfolio Builder |
| `dashboard_snapshots` | Cached dashboard JSONs | Dashboard Creator |
| `uploaded_strategies` | Public submissions | Portfolio Builder |

## Environment Variables

### Common Variables

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27018
MONGODB_URI_LOCAL=mongodb://localhost:27018/?directConnection=true

# Service URLs
ACCOUNT_DATA_SERVICE_URL=http://localhost:8082
EXECUTION_SERVICE_URL=http://localhost:8083
CEREBRO_SERVICE_URL=http://localhost:8001

# Telegram
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=-365852442
TELEGRAM_STAGING_CHAT_ID=-01003237770899

# Feature Flags
USE_MOCK_BROKER=false
ALLOW_LIVE_TRADING=false
```

### Service-Specific Variables

See individual service documentation for complete lists.

## Service Dependencies

```
Signal Ingestion
  └─> Cerebro Service

Cerebro Service
  ├─> Account Data Service (balance queries)
  ├─> Execution Service (order creation)
  └─> Portfolio Builder (strategy configs)

Execution Service
  ├─> Account Data Service (balance sync)
  └─> Telegram Notifier (notifications)

Account Data Service
  └─> Broker APIs (IBKR, Zerodha, Mock)

Portfolio Builder
  └─> (standalone, no runtime dependencies)

Dashboard Creator
  └─> (reads from all MongoDB collections)

Telegram Notifier
  └─> Telegram Bot API
```

## Getting Started

### Starting All Services (Docker)

```bash
# From project root
docker-compose up

# Or individually
docker-compose up cerebro-service
docker-compose up execution-service
docker-compose up account-data-service
docker-compose up portfolio-builder
docker-compose up dashboard-creator
```

### Starting Services Locally

```bash
# Signal Ingestion
cd services/signal_ingestion
python signal_ingestion_main.py

# Cerebro
cd services/cerebro_service
python cerebro_main.py

# Execution
cd services/execution_service
python execution_main.py --use-mock-broker

# Account Data
cd services/account_data_service
python account_data_main.py

# Portfolio Builder
cd services/portfolio_builder
python main.py

# Dashboard Creator
cd services/dashboard_creator
python dashboard_creator_main.py
```

### Health Check All Services

```bash
# Check all services are healthy
curl http://localhost:8001/health  # Cerebro
curl http://localhost:8082/health  # Account Data
curl http://localhost:8083/health  # Execution (503 until ready)
curl http://localhost:8003/health  # Portfolio Builder
curl http://localhost:8004/health  # Dashboard Creator
```

## Signal Flow Example

### ENTRY Signal Flow

```
1. Webhook → trading_signals_raw (MongoDB)
2. Signal Ingestion detects via Change Stream
3. Creates signal_store document with ENTRY leg
4. Forwards to Cerebro Service
5. Cerebro:
   - Gets fund allocations
   - Fetches account balances
   - Runs portfolio constructor
   - Validates margin
   - Creates decision
   - Updates signal_store.legs[0].decision
   - Creates trading_orders
6. Execution Service detects via Change Stream
7. Routes order to broker from pool
8. Waits for fill
9. Updates signal_store.legs[0].execution
10. Updates trading_accounts.open_positions
11. Sends Telegram notification
```

### EXIT Signal Flow

```
1. EXIT signal arrives
2. Signal Ingestion:
   - Finds parent ENTRY signal
   - Appends EXIT leg to same signal_store document
3. Cerebro:
   - Looks up actual filled quantity from ENTRY execution
   - Creates EXIT order for filled quantity (not raw signal quantity)
4. Execution Service:
   - Executes EXIT order
   - Updates position to CLOSED
   - Calculates P&L
5. Dashboard Creator:
   - Picks up closed position
   - Updates client dashboard
```

## Common Workflows

### Adding a New Strategy

```bash
# 1. Create strategy via Portfolio Builder
curl -X POST http://localhost:8003/api/v1/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "NewStrategy_v1",
    "name": "New Strategy",
    "asset_class": "STOCK",
    "instruments": ["AAPL", "MSFT"]
  }'

# 2. Upload backtest CSV
curl -X POST http://localhost:8003/api/v1/strategies/NewStrategy_v1/upload-backtest \
  -F "file=@backtest.csv"

# 3. Strategy is now ready to receive signals
```

### Manual Signal Processing

```bash
# 1. Insert signal into trading_signals_raw
# 2. Signal Ingestion will pick it up automatically
# 3. Track progress via signal_store:

# Check signal status
mongo mathematricks_trading --eval '
  db.signal_store.find({signal_id: "SIGNAL_123"}).pretty()
'

# Check decision
mongo mathematricks_trading --eval '
  db.signal_store.find(
    {signal_id: "SIGNAL_123"},
    {"legs.decision": 1}
  ).pretty()
'

# Check execution
mongo mathematricks_trading --eval '
  db.signal_store.find(
    {signal_id: "SIGNAL_123"},
    {"legs.execution": 1}
  ).pretty()
'
```

### Debugging Failed Signals

```bash
# 1. Check signal_store for decision status
# 2. Look for REJECTED decisions
# 3. Read decision.reason and decision.math
# 4. Check service logs:

# Cerebro logs
tail -f logs/cerebro_service.log | grep "SIGNAL_123"

# Execution logs
tail -f logs/execution_service.log | grep "SIGNAL_123"

# Signal processing log (unified)
tail -f logs/signal_processing.log | grep "SIGNAL_123"
```

## Troubleshooting

### Service Won't Start

1. **Check MongoDB connection:**
   ```bash
   mongo mongodb://localhost:27018 --eval "db.adminCommand('ping')"
   ```

2. **Check port conflicts:**
   ```bash
   lsof -i :8001  # Cerebro
   lsof -i :8082  # Account Data
   lsof -i :8083  # Execution
   ```

3. **Check environment variables:**
   ```bash
   cat .env | grep MONGODB_URI
   ```

### Signals Not Processing

1. **Check Signal Ingestion is running:**
   - Look for "Change Stream connected" log message

2. **Check Cerebro is running:**
   - `curl http://localhost:8001/health`

3. **Check MongoDB Change Streams are enabled:**
   - Requires MongoDB 4.0+ with replica set

### Orders Not Executing

1. **Check Execution Service health:**
   - `curl http://localhost:8083/health`
   - Should return `{"ready": true}`, not 503

2. **Check broker pool:**
   - Look for "Broker Pool Initialized" in logs
   - Verify gateway containers are running: `docker ps | grep ibgateway`

3. **Check trading_orders collection:**
   - Are orders stuck in PENDING_EXECUTION?
   - Check order status and error messages

## Performance Benchmarks

| Service | Startup Time | Processing Time | Memory Usage |
|---------|--------------|-----------------|--------------|
| Signal Ingestion | ~5s | ~10ms per signal | ~50MB |
| Cerebro | ~10s | ~50-100ms per signal | ~150MB |
| Execution | ~60s (broker pool) | ~100-500ms per order | ~200MB |
| Account Data | ~5s | ~200ms per poll | ~100MB |
| Portfolio Builder | ~5s | ~500ms per upload | ~200MB |
| Dashboard Creator | ~5s | ~500ms per regeneration | ~100MB |

## Security Considerations

### Credentials
- Never commit .env file to git
- Use environment variables for all secrets
- Rotate Telegram bot tokens regularly
- Secure MongoDB with authentication in production

### Network
- Use internal Docker network for service communication
- Expose only necessary ports to host
- Use TLS for external MongoDB connections
- Implement rate limiting on public APIs

### Live Trading
- `ALLOW_LIVE_TRADING` must be explicitly enabled
- Double confirmation for live broker orders
- Separate client_id for paper vs live accounts
- Test thoroughly in paper trading first

## Contributing

When adding new features:

1. **Update service documentation** - Add to relevant .md file
2. **Update this README** - If adding new service or major feature
3. **Add logging** - Use consistent format across services
4. **Add health checks** - Implement /health endpoint
5. **Add error handling** - Graceful degradation preferred
6. **Update MongoDB collections** - Document schema changes
7. **Add tests** - Unit tests + integration tests

## Support

For questions or issues:

1. Check service-specific documentation first
2. Review logs in `logs/` directory
3. Check MongoDB for data consistency
4. Verify environment variables are set correctly
5. Test individual components in isolation

## License

[Add license information]

## Version History

- **v3.0 (Feb 2026)** - Consolidated schema, unified signal_store
- **v2.0 (Jan 2026)** - Multi-account fund architecture
- **v1.0 (Dec 2025)** - Initial microservices implementation
