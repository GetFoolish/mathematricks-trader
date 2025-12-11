# Mathematricks Trading System - Architecture Overview

**Last Updated:** 2025-10-12

## Executive Summary

The Mathematricks Trading System is a microservices-based algorithmic trading platform that:
1. Receives trading signals from external sources (TradingView, custom strategies)
2. Performs intelligent position sizing using portfolio theory
3. Executes trades through Interactive Brokers
4. Provides a React admin dashboard for monitoring and control

## Core Databases

### MongoDB: `mathematricks_trading` (Main Database)
**Purpose:** Stores all operational data, configurations, and state

**Key Collections:**
- `strategy_configurations` - Strategy metadata, status, and settings
- `strategy_backtest_data` - Historical daily returns for portfolio optimization
- `portfolio_allocations` - Portfolio allocation recommendations and active allocations
- `portfolio_optimization_runs` - Historical optimization runs with correlation matrices
- `trading_orders` - Position-sized orders ready for execution
- `cerebro_decisions` - Position sizing decisions and risk assessment
- `account_state` - Real-time broker account data (equity, margin, positions)
- `execution_confirmations` - Trade fills and rejections from broker
- `standardized_signals` - Signals converted to internal format
- `raw_signals` - Original signals as received from external sources

### MongoDB Atlas: `mathematricks_signals` (Legacy)
**Purpose:** Stores signals from TradingView webhooks via Vercel edge function

**Key Collection:**
- `trading_signals` - Signals sent to staging.mathematricks.fund or mathematricks.fund

**Note:** The signal_collector.py reads from this database using Change Streams

---

## System Components

### 1. Signal Ingestion Flow

```
TradingView/Strategy → Vercel Webhook → MongoDB Atlas → signal_collector.py → Pub/Sub → CerebroService
                     (mathematricks.fund)  (mathematricks_signals)     (Change Streams)
```

**Components:**
- **Vercel Webhook:** `https://staging.mathematricks.fund/api/signals` (staging) or `https://mathematricks.fund/api/signals` (production)
- **signal_collector.py:** Monitors MongoDB Atlas for new signals using Change Streams, converts to standardized format, publishes to Pub/Sub
- **Pub/Sub Topic:** `standardized-signals` - Queue for incoming signals

**Key Insight:** We do NOT use signal_ingestion_service/main.py in the current architecture. The Vercel webhook writes directly to MongoDB Atlas, and signal_collector.py reads from there.

### 2. Position Sizing (Cerebro Service)

```
Pub/Sub (standardized-signals) → CerebroService → AccountDataService → MongoDB
                                     ↓
                                 Pub/Sub (trading-orders)
```

**Location:** `services/cerebro_service/main.py`

**Responsibilities:**
- Subscribes to `standardized-signals` Pub/Sub topic
- Loads active portfolio allocations from MongoDB
- Queries AccountDataService for current account state (equity, margin)
- Calculates position size based on strategy allocation %
- Enforces hard margin limit (40% max utilization)
- Checks 30% alpha slippage rule
- Creates trading orders and publishes to `trading-orders` Pub/Sub topic
- Saves decisions to `cerebro_decisions` collection

**Key Configuration (MVP):**
```python
MVP_CONFIG = {
    "max_margin_utilization_pct": 40,
    "default_position_size_pct": 5,
    "slippage_alpha_threshold": 0.30,
    "default_account": "IBKR_Main"
}
```

**Portfolio Allocation Logic:**
1. Loads ACTIVE allocation from `portfolio_allocations` collection
2. Gets strategy's allocation % (e.g., SPX_1-D_Opt = 17.13%)
3. Calculates position size: `Equity × Allocation% / Price`
4. Checks if margin utilization would exceed 40% after trade
5. Reduces position size if needed to fit within margin limit

### 3. Portfolio Optimization

**Location:** `services/cerebro_service/optimization_runner.py`

**Purpose:** Daily optimization to maximize Sharpe ratio given backtest data

**Workflow:**
1. Reads all strategy backtest data from `strategy_backtest_data` collection
2. Calculates correlation matrix between strategies
3. Runs scipy optimization to maximize portfolio Sharpe ratio
4. Saves optimization run to `portfolio_optimization_runs` collection
5. Creates new allocation with status=`PENDING_APPROVAL` in `portfolio_allocations`
6. Portfolio manager reviews and approves via frontend
7. Upon approval, allocation status changes to `ACTIVE` and CerebroService reloads

**Manual Trigger:**
```bash
cd services/cerebro_service
/path/to/venv/bin/python optimization_runner.py
```

**Constraints:**
- Max leverage: 2.0 (200% total allocation)
- Max single strategy: 0.5 (50% allocation)
- Risk-free rate: 0.0

### 4. Order Execution

```
Pub/Sub (trading-orders) → ExecutionService → Interactive Brokers TWS/Gateway
                                ↓
                           Pub/Sub (execution-confirmations)
                                ↓
                           AccountDataService
```

**Location:** `services/execution_service/main.py`

**Responsibilities:**
- Subscribes to `trading-orders` Pub/Sub topic
- Connects to Interactive Brokers TWS/Gateway (port 7497 for paper trading)
- Converts trading orders to IB API format
- Places orders with Interactive Brokers
- Monitors order status (fills, partial fills, rejections)
- Publishes execution confirmations to `execution-confirmations` Pub/Sub topic
- Publishes account updates to `account-updates` Pub/Sub topic

**Note:** TWS/Gateway must be running for execution to work. Service will connect but orders will fail if TWS is not available.

### 5. Account Data Service (REST API)

**Location:** `services/account_data_service/main.py`

**Port:** 8002

**Purpose:** Central REST API for account state, portfolio allocations, and strategy management

**Key Endpoints:**

#### Account State
- `GET /api/v1/account/{account_name}/state` - Current account state (equity, margin, positions)
- `GET /api/v1/account/{account_name}/margin` - Simplified margin info
- `POST /api/v1/account/{account_name}/sync` - Force sync with broker

#### Portfolio Allocations
- `GET /api/v1/portfolio/allocations/current` - Current ACTIVE allocation
- `GET /api/v1/portfolio/allocations/latest-recommendation` - Latest PENDING_APPROVAL allocation
- `POST /api/v1/portfolio/allocations/approve` - Approve allocation (archives old ACTIVE, activates new)
- `PUT /api/v1/portfolio/allocations/custom` - Create custom manual allocation
- `GET /api/v1/portfolio/allocations/history` - Allocation history

#### Portfolio Optimization
- `GET /api/v1/portfolio/optimization/latest` - Latest optimization run details

#### Strategy Management
- `GET /api/v1/strategies` - List all strategies
- `GET /api/v1/strategies/{strategy_id}` - Get strategy details + backtest data
- `POST /api/v1/strategies` - Create new strategy
- `PUT /api/v1/strategies/{strategy_id}` - Update strategy
- `DELETE /api/v1/strategies/{strategy_id}` - Soft delete (mark INACTIVE)
- `POST /api/v1/strategies/{strategy_id}/sync-backtest` - Update backtest data

**Pub/Sub Listeners:**
- `execution-confirmations-sub` - Updates account state from trade fills
- `account-updates-sub` - Updates account state from ExecutionService

### 6. Admin Frontend

**Location:** `frontend-admin/`

**Port:** 5173 (or 5174 if 5173 is in use)

**Technology:** React + TypeScript + Vite + TanStack Query + React Router

**Pages:**
- `/login` - Authentication (mock: username=admin, password=admin)
- `/dashboard` - Overview of account state, allocations, recent activity
- `/allocations` - Portfolio allocation management (view, approve, create custom)
- `/strategies` - Strategy configuration and backtest data
- `/activity` - Signal processing activity and trade history

**API Client:** `frontend-admin/src/services/api.ts`
- Connects to AccountDataService (http://localhost:8002)
- Connects to CerebroService (http://localhost:8001)
- Uses JWT tokens stored in localStorage (mock implementation for MVP)

---

## Service Startup & Shutdown

### Start All Services

**Script:** `run_mvp_demo.sh`

**What it does:**
1. Starts Pub/Sub emulator (localhost:8085)
2. Creates Pub/Sub topics and subscriptions
3. Starts AccountDataService (port 8002)
4. Starts CerebroService (port 8001)
5. Starts ExecutionService (background, connects to IBKR)
6. Starts signal_collector (monitors staging.mathematricks.fund)
7. Starts Admin Frontend (port 5173)

**Command:**
```bash
cd /path/to/MathematricksTrader
./run_mvp_demo.sh
```

**Staging Mode:** signal_collector starts with `--staging` flag, monitors staging.mathematricks.fund only

### Stop All Services

**Script:** `stop_mvp_demo.sh`

**Command:**
```bash
cd /path/to/MathematricksTrader
./stop_mvp_demo.sh
```

**What it does:** Kills all service PIDs in reverse order (frontend → signal_collector → execution → cerebro → account_data → pubsub)

---

## Key Tools & Scripts

### 1. Load Strategy Data

**Script:** `tools/load_strategies_from_folder.py`

**Purpose:** Bulk load strategy backtest data from CSV files into MongoDB

**Usage:**
```bash
/path/to/venv/bin/python tools/load_strategies_from_folder.py <path_to_csv_folder>
```

**Example:**
```bash
/path/to/venv/bin/python tools/load_strategies_from_folder.py dev/portfolio_combiner/real_strategy_data/
```

**What it does:**
1. Reads all CSV files in the specified folder
2. Auto-detects returns column (looks for "return" in column name)
3. Cleans percentage values (strips %, converts to decimal)
4. Calculates metrics: mean return, volatility, Sharpe ratio, max drawdown
5. Inserts into `strategy_configurations` collection (strategy metadata)
6. Inserts into `strategy_backtest_data` collection (daily returns + metrics)

**CSV Format Expected:**
```csv
Date,Daily Returns (%),
9/27/25,0.00%,
9/26/25,0.00%,
9/25/25,0.00%,
9/24/25,1.52%,
```

**Note:** Column names are flexible - script looks for any column containing "return" (case-insensitive)

### 2. Run Portfolio Optimization

**Script:** `services/cerebro_service/optimization_runner.py`

**Purpose:** Run portfolio optimization to generate allocation recommendations

**Usage:**
```bash
cd services/cerebro_service
/path/to/venv/bin/python optimization_runner.py
```

**What it does:**
1. Fetches all strategy backtest data from MongoDB
2. Calculates correlation matrix
3. Runs scipy optimization (maximize Sharpe ratio)
4. Saves optimization run to `portfolio_optimization_runs`
5. Creates new allocation with status=`PENDING_APPROVAL`
6. Waits for portfolio manager to approve via frontend

**Output:** Allocation ID (e.g., `ALLOC_20251012_180000`)

**Next Step:** Go to frontend `/allocations` page and approve the recommendation

### 3. Send Test Signals

**Script:** `signal_sender.py`

**Purpose:** Send test trading signals to staging or production webhook

**Usage:**
```bash
# Send single signal
/path/to/venv/bin/python signal_sender.py --staging --signalId 'test_001' --signal '{"strategy_name": "SPX_1-D_Opt", "ticker": "SPX", "action": "BUY", "price": 5750.0}'

# Run full test suite
/path/to/venv/bin/python signal_sender.py --staging --test-suite
```

**What it does:**
1. Sends signal to staging.mathematricks.fund/api/signals (or production)
2. Signal is stored in MongoDB Atlas (`mathematricks_signals.trading_signals`)
3. signal_collector.py picks it up via Change Streams
4. Converts to standardized format and publishes to Pub/Sub
5. CerebroService processes and creates trading order
6. ExecutionService executes with Interactive Brokers

**Staging vs Production:**
- `--staging` flag sends to staging.mathematricks.fund
- No flag sends to mathematricks.fund
- signal_collector.py filters by environment field in MongoDB

---

## Common Workflows

### Workflow 1: Add New Strategies & Run Optimization

**Goal:** Load strategy backtest data, run optimization, activate allocation

**Steps:**
1. Prepare CSV files with daily returns data
2. Load strategies:
   ```bash
   /path/to/venv/bin/python tools/load_strategies_from_folder.py /path/to/csvs/
   ```
3. Run optimization:
   ```bash
   cd services/cerebro_service && /path/to/venv/bin/python optimization_runner.py
   ```
4. Open frontend: http://localhost:5173/allocations
5. Review recommended allocation
6. Click "Approve" button
7. CerebroService automatically reloads allocations
8. New signals will now use the approved allocation %

### Workflow 2: Send Test Signal & Observe Processing

**Goal:** Send a signal and watch it flow through the entire system

**Steps:**
1. Start all services: `./run_mvp_demo.sh`
2. Open 3 terminal windows for logs:
   ```bash
   # Terminal 1: Signal collection
   tail -f logs/signal_collector.log

   # Terminal 2: Position sizing
   tail -f logs/cerebro_service.log

   # Terminal 3: Execution
   tail -f logs/execution_service.log
   ```
3. Send test signal:
   ```bash
   /path/to/venv/bin/python signal_sender.py --staging --signalId 'test_001' --signal '{"strategy_name": "Com1-Met", "ticker": "AAPL", "action": "BUY", "price": 150.25}'
   ```
4. Watch logs:
   - **signal_collector.log:** Signal received, standardized, published to Pub/Sub
   - **cerebro_service.log:** Position sizing calculation, margin check, order created
   - **execution_service.log:** Order submitted to IBKR, execution confirmation
5. Check frontend: http://localhost:5174/activity (note port might be 5174)

### Workflow 3: Manual Position Size Calculation

**Goal:** Understand position sizing math

**Example:**
- Strategy: Com1-Met
- Strategy Allocation: 13.25%
- Account Equity: $251,786
- Signal Price: $150.25

**Calculation:**
1. Allocated Capital = $251,786 × 13.25% = $33,362
2. Quantity = $33,362 / $150.25 = 222 shares
3. Margin Required = $33,362 × 50% = $16,681 (50% margin for stocks)
4. Margin Utilization After = $16,681 / $251,786 = 6.6%
5. Check: 6.6% < 40% limit → APPROVED

**See in logs:** `cerebro_service.log` shows full calculation for every signal

---

## Key Architecture Decisions

### 1. Why Two MongoDB Databases?

- **MongoDB Atlas (`mathematricks_signals`):** Legacy production database for TradingView webhooks via Vercel. Uses Change Streams for real-time signal notifications. Hosted on cloud.
- **Local MongoDB (`mathematricks_trading`):** Operational database for strategy configs, backtest data, portfolio allocations, orders, execution confirmations. Can be localhost or cloud.

**Design:** Separation allows Vercel webhook to write to simple cloud DB, while heavy operational data stays in main DB.

### 2. Why Pub/Sub Instead of Direct API Calls?

- **Decoupling:** Services don't need to know about each other
- **Resilience:** If ExecutionService crashes, orders queue up and get processed when it restarts
- **Scalability:** Can add multiple CerebroService instances for parallel processing
- **Async:** Non-blocking signal processing

### 3. Why Separate AccountDataService?

- **Single Source of Truth:** All services query AccountDataService for account state
- **State Management:** Listens to execution confirmations and account updates, keeps state synchronized
- **Frontend API:** Provides REST API for React frontend without CerebroService needing to handle HTTP

### 4. Why Soft Delete for Strategies?

- **Audit Trail:** Never lose historical data
- **Reactivation:** Can easily re-enable a strategy
- **Allocations:** Historical allocations still reference the strategy_id

---

## Debugging Guide

### Problem: Strategies don't show on frontend

**Symptoms:** Loaded strategies with `load_strategies_from_folder.py` but `/strategies` page is empty

**Root Causes:**
1. Frontend calling wrong API endpoint
2. AccountDataService not running
3. MongoDB connection issues
4. Strategy records not created properly

**Debug Steps:**
1. Check if strategies are in MongoDB:
   ```bash
   # Connect to MongoDB and check
   mongo <connection_string>
   use mathematricks_trading
   db.strategy_configurations.find().pretty()
   ```

2. Check if AccountDataService is running:
   ```bash
   curl http://localhost:8002/health
   curl http://localhost:8002/api/v1/strategies
   ```

3. Check frontend API configuration:
   - Open `frontend-admin/src/services/api.ts`
   - Verify `API_BASE_URL` is http://localhost:8002
   - Check browser console for CORS errors

4. Check browser DevTools Network tab:
   - Is request going to correct URL?
   - Is response 200 OK?
   - What's in the response body?

### Problem: Signals not being processed

**Symptoms:** Sent signal with signal_sender.py but nothing happens

**Root Causes:**
1. Services not running
2. Pub/Sub emulator not running
3. Wrong environment (staging vs production)
4. signal_collector not connected to MongoDB Atlas

**Debug Steps:**
1. Check all services are running:
   ```bash
   ps aux | grep -E "(signal_collector|cerebro|execution|account_data)"
   ```

2. Check Pub/Sub emulator:
   ```bash
   curl http://localhost:8085
   ```

3. Check signal reached MongoDB Atlas:
   ```bash
   # Connect to MongoDB Atlas
   mongo <atlas_connection_string>
   use mathematricks_signals
   db.trading_signals.find().sort({_id: -1}).limit(1).pretty()
   ```

4. Check signal_collector logs:
   ```bash
   tail -f logs/signal_collector.log | grep "REAL-TIME SIGNAL"
   ```

5. Check cerebro logs:
   ```bash
   tail -f logs/cerebro_service.log | grep "Received signal"
   ```

### Problem: ExecutionService can't connect to IBKR

**Symptoms:** `execution_service.log` shows connection errors

**Root Causes:**
1. TWS/IB Gateway not running
2. Wrong port (7497 for paper, 7496 for live)
3. API not enabled in TWS settings
4. Client ID conflict

**Debug Steps:**
1. Check TWS is running and API is enabled:
   - TWS → Edit → Global Configuration → API → Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Socket port: 7497 (paper) or 7496 (live)

2. Check ExecutionService configuration:
   - Open `services/execution_service/main.py`
   - Verify host and port match TWS settings

3. Check logs for connection errors:
   ```bash
   grep -i "connect" logs/execution_service.log
   ```

### Problem: Position size is 0 or rejected

**Symptoms:** CerebroService logs show "REJECTED" decision

**Root Causes:**
1. No active portfolio allocation
2. Strategy not in active allocation
3. Margin limit exceeded
4. Invalid price in signal
5. Account state not available

**Debug Steps:**
1. Check active allocation:
   ```bash
   curl http://localhost:8002/api/v1/portfolio/allocations/current
   ```

2. Check if strategy is in allocation:
   ```bash
   # Look for "allocations" object in response
   # Should have: {"Com1-Met": 13.25, "SPX_1-D_Opt": 17.13, ...}
   ```

3. Check cerebro logs for detailed calculation:
   ```bash
   tail -f logs/cerebro_service.log | grep -A 50 "POSITION SIZING"
   ```

4. Check account state:
   ```bash
   curl http://localhost:8002/api/v1/account/IBKR_Main/state
   ```

---

## Environment Variables

**File:** `.env` (in project root)

**Key Variables:**
- `MONGODB_URI` - Connection string for `mathematricks_trading` database
- `GCP_PROJECT_ID` - Google Cloud project ID (default: "mathematricks-trader")
- `PUBSUB_EMULATOR_HOST` - Pub/Sub emulator host (set by run_mvp_demo.sh to localhost:8085)
- `ACCOUNT_DATA_SERVICE_URL` - AccountDataService URL (default: http://localhost:8002)
- `CEREBRO_SERVICE_URL` - CerebroService URL (default: http://localhost:8001)
- `VITE_API_BASE_URL` - Frontend API base URL (default: http://localhost:8002)
- `VITE_CEREBRO_BASE_URL` - Frontend Cerebro API URL (default: http://localhost:8001)

---

## Next Steps for Development

### Immediate (MVP Complete)
- [x] Load strategies into MongoDB
- [x] Run portfolio optimization
- [ ] **DEBUG:** Fix frontend strategies display
- [ ] Test end-to-end signal flow
- [ ] Validate position sizing math

### Short Term
- [ ] Add proper authentication (replace mock login)
- [ ] Add activity feed with real-time signal updates
- [ ] Add visualization for portfolio allocation pie chart
- [ ] Add correlation matrix heatmap on allocations page
- [ ] Add strategy performance charts (equity curve, drawdown)

### Medium Term
- [ ] Auto-approval rules for allocations (e.g., if Sharpe > X, auto-approve)
- [ ] Email/Telegram notifications for fills
- [ ] Risk alerts (margin approaching limit)
- [ ] Multi-account support (route strategies to different accounts)
- [ ] Paper trading vs live toggle per strategy

### Long Term
- [ ] Machine learning for portfolio optimization
- [ ] Dynamic rebalancing based on realized vs expected performance
- [ ] Advanced risk models (CVaR, stress testing)
- [ ] Multi-broker support (add Binance, other brokers)

---

## Tech Stack Summary

**Backend:**
- Python 3.x with FastAPI (async REST APIs)
- Google Cloud Pub/Sub (message queue, emulator for local dev)
- MongoDB (data storage, Change Streams for real-time)
- Interactive Brokers API via ib_insync (trade execution)

**Frontend:**
- React 18 with TypeScript
- Vite (build tool and dev server)
- TanStack Query (data fetching and caching)
- React Router (navigation)
- Axios (HTTP client)

**Infrastructure:**
- Vercel Edge Functions (TradingView webhook endpoint)
- MongoDB Atlas (cloud database for signals)
- Google Cloud (Pub/Sub in production, emulator in dev)

**Optimization:**
- SciPy optimization library
- NumPy for matrix operations
- Pandas for backtest data processing

---

## File Structure Quick Reference

```
MathematricksTrader/
├── services/
│   ├── account_data_service/
│   │   └── main.py              # REST API for account, allocations, strategies
│   ├── cerebro_service/
│   │   ├── main.py              # Position sizing service
│   │   ├── optimization_runner.py  # Portfolio optimization runner
│   │   └── portfolio_optimizer.py  # Optimization algorithms
│   ├── execution_service/
│   │   └── main.py              # IBKR trade execution
│   └── signal_ingestion_service/
│       └── main.py              # [NOT USED] Alternative signal ingestion
├── frontend-admin/
│   ├── src/
│   │   ├── services/api.ts      # API client
│   │   ├── pages/               # React pages
│   │   └── contexts/            # Auth context
│   └── package.json
├── tools/
│   └── load_strategies_from_folder.py  # Bulk load strategy data
├── signal_collector.py          # Monitors MongoDB Atlas for signals
├── signal_sender.py             # Send test signals
├── run_mvp_demo.sh             # Start all services
├── stop_mvp_demo.sh            # Stop all services
├── .env                        # Environment variables
└── logs/                       # Service logs
```

---

## Glossary

- **Strategy:** A trading algorithm that generates signals (e.g., SPX_1-D_Opt, Com1-Met)
- **Signal:** A trading alert (BUY/SELL ticker at price)
- **Standardized Signal:** Signal converted to internal Mathematricks format
- **Trading Order:** Position-sized order ready for broker execution
- **Allocation:** Percentage of portfolio equity assigned to each strategy
- **Portfolio Optimization:** Mathematical process to find optimal allocations (maximize Sharpe ratio)
- **Position Sizing:** Calculating how many shares/contracts to trade based on allocation and capital
- **Margin Utilization:** Percentage of account equity used as margin for open positions
- **Sharpe Ratio:** Risk-adjusted return metric (higher is better)
- **Cerebro:** The intelligent core for risk management and position sizing
- **MVP:** Minimum Viable Product (current development phase)

---

**End of System Architecture Document**
