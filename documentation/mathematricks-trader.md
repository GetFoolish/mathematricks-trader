# Mathematricks Trader

## Overview

Mathematricks Trader is a sophisticated algorithmic trading platform that aggregates signals from multiple strategy developers, performs intelligent portfolio risk management, executes orders through multiple brokers (IBKR, Zerodha, Mock), and provides real-time dashboards to stakeholders.

## Key Characteristics

- **Microservices Architecture** - 6+ independent services communicate via Pub/Sub
- **Multi-Broker Support** - IBKR, Zerodha, and Mock broker for testing
- **MongoDB-Based Persistence** - All signals, decisions, and executions stored
- **Real-Time Communication** - Google Cloud Pub/Sub for inter-service messaging
- **Position Management** - Real-time tracking with margin constraint enforcement
- **Portfolio Optimization** - Multiple algorithms (Max Sharpe, Max CAGR, Hybrid)
- **Comprehensive Dashboards** - Client and strategy developer views

## Project Structure

```
mathematricks-trader/
├── mvp_demo_start.py          # Orchestrates all service startup
├── mvp_demo_status.py         # Health check for all services
├── mvp_demo_stop.py           # Graceful shutdown of all services
├── requirements.txt           # Python dependencies (144 packages)
├── .env                       # Configuration (DO NOT COMMIT!)
├── .env.sample               # Template for .env
│
├── services/                 # Core microservices
│   ├── account_data_service/ # Account polling and balance tracking
│   ├── signal_ingestion/     # Signal monitoring and routing
│   ├── cerebro_service/      # Position sizing and risk management
│   ├── execution_service/    # Order execution with brokers
│   ├── portfolio_builder/    # Strategy management and optimization
│   ├── dashboard_creator/    # Dashboard generation
│   ├── brokers/             # Unified broker abstraction
│   └── telegram/            # Notification service
│
├── frontend-admin/          # React/Vue admin dashboard (port 5173)
├── tests/signals_testing/   # Signal testing framework
├── logs/                    # Service logs and PID files
├── documentation/           # This documentation
└── google-cloud-sdk/        # GCP SDK with Pub/Sub emulator
```

## Documentation Index

### Service Documentation
- [Signal Ingestion Service](signal_ingestion.md) - Monitors MongoDB for signals
- [Account Data Service](account_data_service.md) - Polls broker accounts
- [Cerebro Service](cerebro_service.md) - Position sizing and risk management
- [Execution Service](execution_service.md) - Places orders with brokers
- [Portfolio Builder](portfolio_builder.md) - Strategy management and optimization
- [Dashboard Creator](dashboard_creator.md) - Dashboard generation
- [Brokers Abstraction Layer](brokers.md) - Unified broker interface

### Testing Documentation
- [Signals Testing](signals_testing.md) - How to send test signals

## Root Folder Files

### mvp_demo_start.py

**Purpose:** Orchestrates startup of all services with proper dependency ordering.

**What it does:**
1. Checks prerequisites (Python venv, .env file, MongoDB)
2. Starts IB Gateway Docker container (if using IBKR)
3. Starts Google Cloud Pub/Sub emulator
4. Creates Pub/Sub topics and subscriptions
5. Starts each service in correct order:
   - Account Data Service (port 8082)
   - Portfolio Builder (port 8003)
   - Dashboard Creator (port 8004)
   - Cerebro Service (background)
   - Execution Service (background)
   - Signal Ingestion Service (background)
   - Admin Frontend (port 5173)

**Usage:**
```bash
# Paper trading (default)
python mvp_demo_start.py

# Live trading
python mvp_demo_start.py --live

# With mock broker (testing)
python mvp_demo_start.py --use-mock-broker
```

**Output:**
```
Starting Mathematricks Trader MVP Demo...

1. Checking prerequisites...
   ✓ Python venv activated
   ✓ .env file found
   ✓ MongoDB replica set running

2. Starting IB Gateway (Docker)...
   ✓ Container started

3. Starting Pub/Sub emulator...
   ✓ Emulator running on localhost:8085

4. Creating Pub/Sub topics...
   ✓ standardized-signals
   ✓ trading-orders
   ✓ execution-confirmations

5. Starting services...
   ✓ Account Data Service (port 8082)
   ✓ Portfolio Builder (port 8003)
   ✓ Dashboard Creator (port 8004)
   ✓ Cerebro Service
   ✓ Execution Service
   ✓ Signal Ingestion Service
   ✓ Admin Frontend (port 5173)

All services started successfully!

Admin Dashboard: http://localhost:5173
Username: admin
Password: admin
```

### mvp_demo_status.py

**Purpose:** Health check for all running services.

**What it checks:**
- Service process status and uptime
- Port listening status for API services
- MongoDB connection
- IB Gateway Docker status
- Pub/Sub emulator status
- Recent log entries from each service
- Memory usage per service

**Usage:**
```bash
python mvp_demo_status.py
```

**Output:**
```
Mathematricks Trader System Status
==================================

1️⃣  CORE SERVICES

📋 Signal Ingestion Service
   Process: ✅ Running (PID: 12345)
   Uptime: 2:30:45
   Memory: 125.5 MB
   Last Activity: 2024-11-24 10:30:00

📋 Cerebro Service
   Process: ✅ Running (PID: 12346)
   Uptime: 2:30:40
   Memory: 180.3 MB
   Last Activity: 2024-11-24 10:30:05

📋 Execution Service
   Process: ✅ Running (PID: 12347)
   Uptime: 2:30:35
   Memory: 95.2 MB
   Last Activity: 2024-11-24 10:30:12

2️⃣  API SERVICES

📋 Account Data Service
   Process: ✅ Running (PID: 12348)
   Port 8082: ✅ Listening
   Uptime: 2:31:00
   Memory: 110.5 MB

📋 Portfolio Builder
   Process: ✅ Running (PID: 12349)
   Port 8003: ✅ Listening
   Uptime: 2:30:55
   Memory: 98.7 MB

📋 Dashboard Creator
   Process: ✅ Running (PID: 12350)
   Port 8004: ✅ Listening
   Uptime: 2:30:50
   Memory: 102.3 MB

3️⃣  INFRASTRUCTURE

📋 MongoDB
   Status: ✅ Connected
   Replica Set: rs0

📋 IB Gateway (Docker)
   Status: ✅ Running
   Container: ib-gateway-paper

📋 Pub/Sub Emulator
   Status: ✅ Running
   Port 8085: ✅ Listening

📋 Admin Frontend
   Status: ✅ Running (PID: 12351)
   Port 5173: ✅ Listening

Summary: 6/6 services running, 0 issues detected
```

### mvp_demo_stop.py

**Purpose:** Gracefully shutdown all services.

**What it does:**
1. Stops services in reverse order
2. Sends SIGTERM (graceful shutdown) first
3. Falls back to SIGKILL if process doesn't stop
4. Removes PID files
5. Stops Docker containers
6. Stops Pub/Sub emulator
7. Cleans up ports

**Usage:**
```bash
python mvp_demo_stop.py
```

**Output:**
```
Stopping Mathematricks Trader services...

1. Stopping Admin Frontend...
   ✓ Stopped (PID: 12351)

2. Stopping Signal Ingestion Service...
   ✓ Stopped (PID: 12345)

3. Stopping Execution Service...
   ✓ Stopped (PID: 12347)

4. Stopping Cerebro Service...
   ✓ Stopped (PID: 12346)

5. Stopping Dashboard Creator...
   ✓ Stopped (PID: 12350)

6. Stopping Portfolio Builder...
   ✓ Stopped (PID: 12349)

7. Stopping Account Data Service...
   ✓ Stopped (PID: 12348)

8. Stopping Pub/Sub emulator...
   ✓ Stopped

9. Stopping IB Gateway (Docker)...
   ✓ Stopped

All services stopped successfully!
```

## Environment Variables (.env)

The `.env` file contains all configuration for the system. **DO NOT commit this file to git as it contains sensitive information.**

### Database & Infrastructure
```bash
# MongoDB connection (requires replica set for Change Streams)
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0

# Google Cloud project ID
GCP_PROJECT_ID=mathematricks-trader
```

### IBKR (Interactive Brokers) Configuration
```bash
# Connection settings
IBKR_HOST=127.0.0.1
IBKR_PORT=4002                    # Paper=4002, Live=4001 (via Docker)
IBKR_CLIENT_ID=1

# Credentials (DO NOT SHARE)
IBKR_PAPER_USERNAME=your_username
IBKR_PAPER_PASSWORD=your_password
IBKR_LIVE_USERNAME=your_username
IBKR_LIVE_PASSWORD=your_password
IBKR_TOTP_SECRET=your_2fa_secret  # For 2FA authentication
```

### Telegram Notifications
```bash
# Enable/disable Telegram notifications
TELEGRAM_ENABLED=true

# Bot credentials (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Staging environment chat (optional)
TELEGRAM_STAGING_CHAT_ID=staging_chat_id
```

### Risk Management
```bash
# Maximum position size as % of account equity
MAX_POSITION_SIZE_PCT=10

# Maximum allocation to any single broker
MAX_BROKER_ALLOCATION_PCT=40
```

### Service Configuration
```bash
# Account Data Service URL (used by Cerebro)
ACCOUNT_DATA_SERVICE_URL=http://localhost:8082

# Service ports
ACCOUNT_DATA_SERVICE_PORT=8082
PORTFOLIO_BUILDER_PORT=8003
DASHBOARD_CREATOR_PORT=8004

# Mock broker for testing (set by mvp_demo_start.py)
USE_MOCK_BROKER=false

# Logging level
LOG_LEVEL=INFO
```

## System Architecture

### Signal Flow

```
Strategy Developer (TradingView/Email/API)
   ↓
[MongoDB: trading_signals_raw]
   ↓
Signal Ingestion Service (Change Stream Watcher)
   ↓
[Standardize Format + Generate signal_id]
   ↓
[MongoDB: signal_store]
   ↓
[Pub/Sub: standardized-signals]
   ↓
Cerebro Service (Subscriber)
   ↓
[Query Account Data Service for balances]
   ↓
[Calculate Position Size + Margin Constraints]
   ↓
[Generate Trading Order Decision]
   ↓
[MongoDB: Update signal_store with decision]
   ↓
[Pub/Sub: trading-orders]
   ↓
Execution Service (Subscriber)
   ↓
[BrokerFactory → Place Order with Broker]
   ↓
[Broker Execution/Fill]
   ↓
[MongoDB: execution_confirmations + positions]
   ↓
[Pub/Sub: execution-confirmations]
   ↓
[Account Data Service polls and updates]
   ↓
Dashboard Creator Generates Reports
   ↓
[Frontend: Admin Dashboard + Client Dashboard]
```

### Service Dependencies

```
┌─────────────────────────────────────┐
│      Signal Ingestion Service       │
│  (Monitors MongoDB, publishes to    │
│   Pub/Sub)                          │
└──────────────┬──────────────────────┘
               │ Pub/Sub: standardized-signals
               ↓
┌─────────────────────────────────────┐
│        Cerebro Service              │
│  (Position sizing, risk mgmt)       │
│  Queries ↓                          │
│  ┌──────────────────────────┐      │
│  │ Account Data Service      │      │
│  │ (Polls brokers)           │      │
│  └──────────────────────────┘      │
└──────────────┬──────────────────────┘
               │ Pub/Sub: trading-orders
               ↓
┌─────────────────────────────────────┐
│      Execution Service              │
│  (Places orders via BrokerFactory)  │
└──────────────┬──────────────────────┘
               │ Pub/Sub: execution-confirmations
               ↓
┌─────────────────────────────────────┐
│      Dashboard Creator              │
│  (Aggregates data from MongoDB)     │
└──────────────┬──────────────────────┘
               │ JSON dashboards
               ↓
┌─────────────────────────────────────┐
│      Admin Frontend                 │
│  (React/Vue dashboard)              │
└─────────────────────────────────────┘
```

## MongoDB Schema

### Database: `mathematricks_trading`

**Key Collections:**

1. **trading_signals_raw**
   - Raw incoming signals before processing
   - Written by: External systems (TradingView, email collectors)
   - Read by: Signal Ingestion Service

2. **signal_store**
   - Signal metadata with Cerebro decisions and order IDs
   - Written by: Signal Ingestion, Cerebro, Execution services
   - Read by: All services for signal tracking

3. **trading_accounts**
   - Account definitions and real-time balance/position data
   - Written by: Account Data Service (polling updates)
   - Read by: Cerebro, Dashboard Creator

4. **positions**
   - Open positions by strategy and account
   - Written by: Execution Service (on fills)
   - Read by: Cerebro (conflict checking), Dashboard Creator

5. **strategies**
   - Strategy configuration and metadata
   - Written by: Portfolio Builder
   - Read by: Dashboard Creator, Cerebro

6. **current_allocation**
   - Current portfolio allocation percentages
   - Written by: Portfolio Builder (approved allocations)
   - Read by: Cerebro (position sizing)

7. **execution_confirmations**
   - All order executions and rejections
   - Written by: Execution Service
   - Read by: Dashboard Creator

8. **portfolio_tests**
   - Backtest results and optimization runs
   - Written by: Portfolio Builder
   - Read by: Portfolio Builder (historical analysis)

## Google Cloud Pub/Sub Topics

### standardized-signals
- **Publisher:** Signal Ingestion Service
- **Subscriber:** Cerebro Service
- **Message:** Standardized signal with signal_id

### trading-orders
- **Publisher:** Cerebro Service
- **Subscriber:** Execution Service
- **Message:** Approved order with position size

### execution-confirmations
- **Publisher:** Execution Service
- **Subscriber:** Dashboard Creator, Account Data Service
- **Message:** Fill confirmation with execution details

## Port Allocation

| Service | Port | Protocol |
|---------|------|----------|
| Account Data Service | 8082 | HTTP |
| Portfolio Builder | 8003 | HTTP |
| Dashboard Creator | 8004 | HTTP |
| Admin Frontend | 5173 | HTTP |
| Pub/Sub Emulator | 8085 | gRPC |
| MongoDB | 27017 | MongoDB Wire Protocol |
| IB Gateway (Paper) | 4002 | TWS API |
| IB Gateway (Live) | 4001 | TWS API |

## Logging Strategy

All services log to:
1. **Console** - Real-time output during development
2. **logs/{service_name}.log** - Service-specific logs
3. **logs/signal_processing.log** - Unified signal journey log

### Log Format
```
|LEVEL|Message|Timestamp|file:filename.py:line No.LineNumber|
```

### Signal Processing Log Format
```
Timestamp | [SERVICE_NAME] | Message

Example:
2024-11-24 10:30:00 | [SIGNAL_INGESTION] | New signal: sig_1732450800_5678
2024-11-24 10:30:05 | [CEREBRO] | Decision=APPROVED | Qty=100
2024-11-24 10:30:12 | [EXECUTION] | Order filled: 100 @ $235.15
```

## Quick Start Guide

### Prerequisites

1. **Python 3.8+**
   ```bash
   python --version
   ```

2. **MongoDB with Replica Set**
   ```bash
   # Start MongoDB with replica set
   mongod --replSet rs0 --dbpath /path/to/data --port 27017

   # Initialize replica set (first time only)
   mongosh
   > rs.initiate()
   ```

3. **Docker** (for IB Gateway)
   ```bash
   docker --version
   ```

4. **Environment File**
   ```bash
   cp .env.sample .env
   # Edit .env with your credentials
   ```

### Step-by-Step Startup

**1. Install Dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure Environment**
```bash
# Edit .env with your credentials
nano .env
```

**3. Start All Services**
```bash
# Paper trading (default)
python mvp_demo_start.py

# Or with mock broker (no real money)
python mvp_demo_start.py --use-mock-broker
```

**4. Check Status**
```bash
python mvp_demo_status.py
```

**5. Open Admin Dashboard**
```
Open browser: http://localhost:5173
Username: admin
Password: admin
```

**6. Send Test Signal**
```bash
cd tests/signals_testing
python send_test_signal.py --file sample_signals/equity_simple_signal_1.json
```

**7. Monitor Signal Flow**
```bash
# Watch unified signal journey
tail -f logs/signal_processing.log

# Or watch specific service
tail -f logs/cerebro_service.log
```

**8. Stop All Services**
```bash
python mvp_demo_stop.py
```

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.121.0 | REST API framework |
| uvicorn | 0.38.0 | ASGI server |
| pymongo | 4.6.1 | MongoDB driver |
| google-cloud-pubsub | 2.18.4 | Pub/Sub client |
| ib-insync | 0.9.86 | IBKR API |
| kiteconnect | 5.0.1 | Zerodha API |
| pandas | 2.3.3 | Data analysis |
| numpy | 2.3.4 | Numerical computing |
| scipy | 1.16.3 | Optimization |
| pydantic | 2.12.4 | Data validation |
| APScheduler | 3.11.1 | Job scheduling |

Full list: See `requirements.txt` (144 packages)

## Common Operations

### View Logs
```bash
# All logs
ls -lh logs/

# Unified signal journey
tail -f logs/signal_processing.log

# Specific service
tail -f logs/signal_ingestion.log
tail -f logs/cerebro_service.log
tail -f logs/execution_service.log
```

### Check MongoDB Data
```bash
mongosh
use mathematricks_trading

# Recent signals
db.signal_store.find().sort({received_time: -1}).limit(10)

# Open positions
db.positions.find({status: "OPEN"})

# Account balances
db.trading_accounts.find({}, {balances: 1, open_positions: 1})

# Recent executions
db.execution_confirmations.find().sort({filled_at: -1}).limit(10)
```

### Manual Service Control
```bash
# Start individual service
cd services/cerebro_service
python cerebro_main.py

# Start with nohup (background)
nohup python cerebro_main.py > logs/cerebro.log 2>&1 &

# Find process ID
ps aux | grep cerebro_main

# Kill process
kill -SIGTERM <PID>
```

### Restart Specific Service
```bash
# Example: Restart Cerebro
kill $(cat logs/pids/cerebro_service.pid)
sleep 2
nohup python services/cerebro_service/cerebro_main.py > logs/cerebro_service.log 2>&1 &
echo $! > logs/pids/cerebro_service.pid
```

## Troubleshooting

### Services Not Starting

**Issue:** mvp_demo_start.py fails

**Check:**
1. Python venv activated
2. .env file exists with correct values
3. MongoDB is running with replica set
4. No port conflicts (8082, 8003, 8004, 5173)
5. Docker is running (for IB Gateway)

### Signals Not Processing

**Issue:** Signals sent but not appearing in logs

**Check:**
1. Signal Ingestion Service is running
2. MongoDB Change Streams are working (requires replica set)
3. Signal has correct `environment` field (staging/production)
4. Check `trading_signals_raw` collection in MongoDB

### Orders Not Executing

**Issue:** Signals approved but orders not placed

**Check:**
1. Execution Service is running
2. Broker connection is active (check logs)
3. Account has sufficient margin
4. Symbol is valid for broker
5. Market is open for the instrument

### MongoDB Connection Errors

**Issue:** Services can't connect to MongoDB

**Solutions:**
```bash
# Check MongoDB is running
mongosh

# Check replica set status
mongosh
> rs.status()

# If not initialized
> rs.initiate()
```

### Pub/Sub Errors

**Issue:** Services can't publish/subscribe

**Check:**
1. Pub/Sub emulator is running
2. `PUBSUB_EMULATOR_HOST` environment variable is set
3. Topics exist:
   ```bash
   gcloud pubsub topics list
   ```

### Broker Connection Failures

**Issue:** Can't connect to IBKR

**Check:**
1. TWS or IB Gateway is running
2. Port is correct (4002 for paper, 4001 for live)
3. API connections enabled in TWS settings
4. client_id not already in use
5. Firewall not blocking connection

## Performance Benchmarks

### Signal Processing Latency
- Signal Ingestion: 10-50ms
- Cerebro Decision: 300-500ms (includes account query)
- Order Execution: 50-500ms (broker dependent)
- **Total End-to-End: 500ms - 2s**

### System Capacity
- Signals per second: 10-20 (limited by sequential Cerebro processing)
- Concurrent positions: 100+ (limited by broker)
- Strategies supported: 50+ (no hard limit)
- Accounts supported: 20+ (polling overhead increases linearly)

## Security Best Practices

1. **Never commit .env file**
   - Add to .gitignore
   - Use .env.sample for templates

2. **Protect MongoDB**
   - Enable authentication
   - Use strong passwords
   - Limit network access

3. **Secure API endpoints**
   - Use authentication (not implemented yet)
   - Rate limiting (not implemented yet)
   - HTTPS in production

4. **Broker credentials**
   - Store in environment variables
   - Never log credentials
   - Rotate API keys regularly

5. **Telegram bot token**
   - Keep secret
   - Restrict bot permissions
   - Monitor unauthorized access

## Future Enhancements

### High Priority
1. Authentication for API services
2. WebSocket support for real-time dashboards
3. Improved error recovery and retry logic
4. Comprehensive testing suite
5. Production deployment scripts

### Medium Priority
1. Multi-tenant support (multiple clients)
2. Advanced risk analytics
3. Custom alert rules
4. Historical performance comparison
5. Enhanced backtesting engine

### Low Priority
1. Additional broker integrations (Alpaca, Binance)
2. Machine learning for position sizing
3. Automated rebalancing
4. Tax reporting
5. Mobile app

## Support and Maintenance

### Log Rotation
Implement log rotation to prevent disk space issues:
```bash
# Use logrotate
sudo nano /etc/logrotate.d/mathematricks-trader
```

### Database Backups
Regular MongoDB backups:
```bash
# Dump database
mongodump --db mathematricks_trading --out /backups/$(date +%Y%m%d)

# Restore database
mongorestore --db mathematricks_trading /backups/20241124/mathematricks_trading
```

### Monitoring
- Set up system monitoring (Prometheus, Grafana)
- Alert on service failures
- Track key metrics (latency, error rate, throughput)

## License

Copyright 2024 Mathematricks. All rights reserved.

## Contact

For support or questions, please contact the development team.

---

**Last Updated:** 2024-11-24

**Version:** 1.0.0

**Maintainers:** Mathematricks Development Team
