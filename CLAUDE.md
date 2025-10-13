# Claude Code Project Instructions

## General Rules
- read all the files in [text](dev/portfolio_builder/llm_brief)
- for python use the venv: /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/venv/bin/python
- for environment variables, use: /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env
- Use this file to keep track of your to-do list, and keep updating it here as work gets done.
- Before you move to the next to-do or next set of problems, ask the user if they want to do a git commit and git push.
- Use logging in /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs folder and create log files for debugging. But once you're done, set logging to INFO and make sure that it is only important information a human would need.
- Write small tests in bash to make sure that your code is working, and that the logic is accurate and the math is accurate.
- Be very organized in your work. If you rewrite a function, make sure you remove the old one. If u make a new file, ask yourself, what is the best place to keep this file, and put the file in the right place. I don't want a messy repo by the time you are done with your work.
- Always, before we push code to github or CICD deployment, lets first test everything we have developed locally. and if everything is approved and working properly, only then we will go into deployment
- Do not take shortcuts, always write real code, which can be used in production, as opposed to dummy code. If u want to test something with dummy code, write a quick 'bash test' and run it without saving it to the project, cause that makes the project messy.
- If there is a situation where you think it'll be better to ask the user for direction, please give them options to chose from, explain each decision, and let them decide.
- If you give me commands to run, always give them to me in a way that i can copy paste it. Right now, there are extra spaces when i copy it from your window.

---

## Current Status: Milestone 1.0 ✅ COMPLETE

### Completed Features (Milestone 1.0)
- ✅ **Core Trading Loop MVP** - Signal → Cerebro → Execution → IBKR TWS working end-to-end
- ✅ **SignalIngestionService** - signal_collector.py + Pub/Sub bridge with better signal IDs
- ✅ **CerebroService** - 5% position sizing, 40% margin limit, detailed calculation logs
- ✅ **ExecutionService** - IBKR TWS integration with queue-based threading (asyncio fix)
- ✅ **AccountDataService** - REST API (port 8002) + Pub/Sub consumers
- ✅ **Signal/Order IDs** - Format: `{strategy}_{YYYYMMDD}_{HHMMSS}_{id}` and `{signal_id}_ORD`
- ✅ **Fractional Shares Fix** - Rounds to whole numbers for IBKR API
- ✅ **MongoDB Atlas** - All collections working (signals, orders, confirmations, decisions)
- ✅ **Cloud Pub/Sub** - Emulator running locally with all topics/subscriptions
- ✅ **Testing** - Full end-to-end tested with real IBKR TWS Paper Trading account

### Current Architecture
```
TradingView → staging.mathematricks.fund → MongoDB → signal_collector.py → Pub/Sub →
CerebroService (position sizing) → Pub/Sub → ExecutionService → IBKR TWS
                    ↓                                ↓
              AccountDataService ←─────────────────────
              (REST API + Pub/Sub)
```

### How to Run
```bash
./run_mvp_demo.sh              # Start all services
./stop_mvp_demo.sh             # Stop all services
```

Send test signal:
```bash
python signal_sender.py --ticker AAPL --action BUY --price 150.25
```

---

## Next: Milestone 1.2 - Simple MPT-Based Portfolio Optimization

**Goal:** Replace flat 5% position sizing with intelligent MPT-based allocations.

### Phase A: Backend - Portfolio Optimizer

#### 1. Fix Small Bug
- [ ] Fix ExecutionService get_account_state() bug at line 234
  - Issue: `'MarketOrder' object has no attribute 'order'`
  - Location: services/execution_service/main.py:234

#### 2. Create Portfolio Optimizer Module
- [ ] Create `services/cerebro_service/portfolio_optimizer.py`
  - [ ] Implement correlation matrix calculation from daily returns
  - [ ] Implement scipy maximize Sharpe ratio optimization
  - [ ] Apply constraints:
    - Each strategy weight ≥ 0% (no shorts)
    - Sum of weights ≤ 200% (max 2x leverage)
    - Optional: max 50% per single strategy
  - [ ] Function: `optimize_portfolio(strategies: Dict) -> Dict[str, float]`
    - Input: strategy_id → backtest metrics
    - Output: strategy_id → recommended allocation %

#### 3. MongoDB Collections for Portfolio Data
- [ ] Create `strategy_backtest_data` collection schema
  ```python
  {
    "strategy_id": str,
    "daily_returns": [float],  # Array of daily returns
    "mean_return_daily": float,
    "volatility_daily": float,
    "sharpe_ratio": float,
    "max_drawdown": float,
    "margin_per_unit": float,
    "backtest_period": {"start": date, "end": date},
    "created_at": datetime,
    "updated_at": datetime
  }
  ```

- [ ] Create `portfolio_allocations` collection schema
  ```python
  {
    "allocation_id": str,  # Format: ALLOC_{YYYYMMDD}_{HHMMSS}
    "allocations": {  # Dict of strategy_id: weight %
      "SPX_1-D_Opt": 30.0,
      "Forex": 25.0,
      ...
    },
    "status": str,  # ACTIVE | PENDING_APPROVAL | ARCHIVED
    "metrics": {
      "expected_sharpe": float,
      "expected_volatility": float,
      "total_allocation_pct": float,
      "leverage_ratio": float
    },
    "approved_by": str,  # user_id or "system"
    "approved_at": datetime,
    "created_at": datetime
  }
  ```

- [ ] Create `portfolio_optimization_runs` collection schema
  ```python
  {
    "run_id": str,  # Format: OPT_{YYYYMMDD}_{HHMMSS}
    "recommended_allocations": {...},
    "correlation_matrix": [[float]],
    "strategy_returns": {...},
    "strategy_volatility": {...},
    "optimization_method": str,  # "maximize_sharpe"
    "constraints_used": {...},
    "status": str,  # COMPLETED | FAILED
    "error_message": str,  # If failed
    "created_at": datetime
  }
  ```

#### 4. Backtest Data Ingestion Tool
- [ ] Create `tools/ingest_backtest_data.py`
  - [ ] Read strategy CSV files from `dev/portfolio_combiner/outputs/latest/strategy_performance_data/`
  - [ ] Parse daily returns, calculate metrics
  - [ ] Insert into `strategy_backtest_data` collection
  - [ ] Usage: `python tools/ingest_backtest_data.py --data-dir <path>`

#### 4a. Strategy Configuration Management (Backend)
- [ ] Add `strategy_configurations` collection to MongoDB schemas
  ```python
  {
    "strategy_id": str,  # Unique identifier (e.g., "SPX_1-D_Opt")
    "strategy_name": str,  # Human-readable name
    "status": str,  # ACTIVE | INACTIVE | TESTING
    "trading_mode": str,  # LIVE | PAPER
    "account": str,  # IBKR_Main | IBKR_Futures | Binance_Main
    "include_in_optimization": bool,  # Whether to include in portfolio optimization
    "risk_limits": {
      "max_position_size": float,
      "max_daily_loss": float
    },
    "developer_contact": str,  # Email/Slack
    "notes": str,  # Free-text notes
    "created_at": datetime,
    "updated_at": datetime
  }
  ```

- [ ] Update `services/mongodb_schemas.md` with strategy_configurations schema

- [ ] Create strategy configuration helper module
  - [ ] Create `services/cerebro_service/strategy_config.py`
  - [ ] Function: `load_strategy_configs() -> Dict[str, Dict]`
  - [ ] Function: `get_strategy_config(strategy_id: str) -> Dict`
  - [ ] Function: `is_strategy_active(strategy_id: str) -> bool`

#### 5. Enhance Cerebro Position Sizing
- [ ] Modify `services/cerebro_service/main.py`
  - [ ] Add function to load active allocation from MongoDB on startup
  - [ ] Modify `calculate_position_size()`:
    ```python
    # Old: allocated_capital = account_equity * 0.05
    # New:
    strategy_allocation_pct = active_allocation.get(signal.strategy_id, 0)
    if strategy_allocation_pct == 0:
        logger.warning(f"No allocation for {signal.strategy_id}, rejecting")
        return {"approved": False, "reason": "NO_ALLOCATION"}
    allocated_capital = account_equity * (strategy_allocation_pct / 100)
    ```
  - [ ] Update position sizing logs to show allocation %
  - [ ] Still apply 40% margin limit checks

#### 6. Daily Optimization Scheduler
- [ ] Create `services/cerebro_service/scheduler.py`
  - [ ] Use APScheduler
  - [ ] Schedule optimization to run daily at midnight
  - [ ] Function: `run_daily_optimization()`
    1. Fetch all strategy backtest data from MongoDB
    2. Run portfolio_optimizer.optimize_portfolio()
    3. Save results to `portfolio_optimization_runs`
    4. Create new allocation with status=PENDING_APPROVAL
    5. Log results
  - [ ] Add to cerebro_service/main.py startup

### Phase B: Backend - Portfolio Allocation & Strategy Management APIs

#### 7. Add Portfolio Allocation API Endpoints
Location: `services/account_data_service/main.py` (or create new PortfolioService)

- [ ] GET `/api/portfolio/allocations/current`
  - Returns currently ACTIVE allocation
  - Response: `{"allocation_id": str, "allocations": {...}, "metrics": {...}}`

- [ ] GET `/api/portfolio/allocations/latest-recommendation`
  - Returns latest PENDING_APPROVAL allocation
  - Response: `{"allocation_id": str, "allocations": {...}, "metrics": {...}}`

- [ ] POST `/api/portfolio/allocations/approve`
  - Body: `{"allocation_id": str, "approved_by": str}`
  - Sets allocation to ACTIVE, archives old ACTIVE
  - Notifies Cerebro to reload allocation

- [ ] PUT `/api/portfolio/allocations/custom`
  - Body: `{"allocations": {...}, "approved_by": str}`
  - Portfolio manager manually edits and approves
  - Creates new ACTIVE allocation

- [ ] GET `/api/portfolio/allocations/history`
  - Returns past allocations with pagination
  - Query params: `limit`, `offset`

- [ ] GET `/api/portfolio/optimization/latest`
  - Returns latest optimization run with correlation matrix
  - For displaying in frontend

#### 7a. Add Strategy Management API Endpoints
Location: `services/account_data_service/main.py`

- [ ] GET `/api/strategies`
  - List all strategies with configurations
  - Query params: `status` (filter), `account` (filter), `search` (text search)
  - Response: `[{"strategy_id": str, "strategy_name": str, "status": str, ...}, ...]`

- [ ] GET `/api/strategies/{strategy_id}`
  - Get single strategy configuration
  - Include backtest data if available (join with strategy_backtest_data)
  - Response: `{"strategy_id": str, ..., "backtest": {...}}`

- [ ] POST `/api/strategies`
  - Create new strategy configuration
  - Body: `{"strategy_id": str, "strategy_name": str, "status": str, "account": str, ...}`
  - Validates that strategy_id is unique
  - Response: `{"strategy_id": str, "created_at": datetime}`

- [ ] PUT `/api/strategies/{strategy_id}`
  - Update strategy configuration
  - Body: `{"status": str, "account": str, "trading_mode": str, ...}`
  - Response: `{"strategy_id": str, "updated_at": datetime}`

- [ ] DELETE `/api/strategies/{strategy_id}`
  - Delete strategy configuration
  - Only allow if strategy has no active allocations
  - Response: `{"success": true}`

- [ ] POST `/api/strategies/{strategy_id}/sync-backtest`
  - Trigger backtest data ingestion/sync for this strategy
  - Calls ingestion tool in background
  - Response: `{"status": "processing", "job_id": str}`

### Phase C: Integration & Service Updates

#### 7b. Integrate Strategy Configuration into Services

**SignalIngestionService Integration:**
- [ ] Modify `signal_collector.py` integration point
  - [ ] Before processing signal, load strategy config
  - [ ] Check if `strategy.status == ACTIVE`
  - [ ] If INACTIVE, reject signal with log: "Strategy {id} is INACTIVE"
  - [ ] If TESTING, add special tag to signal for tracking

**CerebroService Integration:**
- [ ] Modify `services/cerebro_service/main.py`
  - [ ] Load strategy configs on startup
  - [ ] When processing signal, check strategy config:
    - [ ] Get trading_mode (LIVE vs PAPER)
    - [ ] Get account assignment
    - [ ] Get risk_limits
  - [ ] Add strategy metadata to order:
    ```python
    order_data = {
      ...
      "account": strategy_config["account"],
      "trading_mode": strategy_config["trading_mode"],
      "risk_limits": strategy_config["risk_limits"]
    }
    ```
  - [ ] In position sizing, respect risk_limits.max_position_size

**Portfolio Optimizer Integration:**
- [ ] Modify `portfolio_optimizer.py`
  - [ ] Before optimization, filter strategies:
    ```python
    active_strategies = {
      sid: data
      for sid, data in strategies.items()
      if strategy_configs[sid]["status"] == "ACTIVE"
      and strategy_configs[sid]["include_in_optimization"]
    }
    ```
  - [ ] Log which strategies are excluded and why
  - [ ] Only optimize the filtered set

**ExecutionService Integration:**
- [ ] Modify `services/execution_service/main.py`
  - [ ] When receiving order, check `order_data["trading_mode"]`
  - [ ] If PAPER mode:
    - [ ] Log order details
    - [ ] DO NOT submit to broker
    - [ ] Create mock execution confirmation
    - [ ] Publish to account-updates with "PAPER" tag
  - [ ] If LIVE mode:
    - [ ] Route to correct account from `order_data["account"]`
    - [ ] Submit to broker as normal

#### 7c. Strategy Config → Backtest Sync Workflow
- [ ] Create background job handler for `/api/strategies/{id}/sync-backtest`
  - [ ] Accept CSV file upload or path to existing CSV
  - [ ] Call `ingest_backtest_data.py` tool with strategy_id parameter
  - [ ] Update strategy_configurations with last_sync timestamp
  - [ ] Return success/failure status

### Phase D: Testing & Validation

#### 8. Test Data Ingestion
- [ ] Run ingestion tool on portfolio_combiner data
  ```bash
  python tools/ingest_backtest_data.py --data-dir dev/portfolio_combiner/outputs/run_*/strategy_performance_data/
  ```
- [ ] Verify data in MongoDB (use MongoDB Compass or mongosh)
- [ ] Check: 7-14 strategies ingested with daily returns

#### 9. Test Optimization
- [ ] Manually trigger optimization:
  ```bash
  python -c "from services.cerebro_service.scheduler import run_daily_optimization; run_daily_optimization()"
  ```
- [ ] Verify:
  - [ ] Correlation matrix calculated correctly
  - [ ] Optimization converges
  - [ ] Allocations sum to reasonable total (100-200%)
  - [ ] Results saved to MongoDB
- [ ] Check logs for any warnings/errors

#### 10. Test Allocation Approval Workflow
- [ ] Use curl or Postman to test APIs:
  ```bash
  # Get latest recommendation
  curl http://localhost:8002/api/portfolio/allocations/latest-recommendation

  # Approve it
  curl -X POST http://localhost:8002/api/portfolio/allocations/approve \
    -H "Content-Type: application/json" \
    -d '{"allocation_id": "ALLOC_...", "approved_by": "admin"}'

  # Verify it's now current
  curl http://localhost:8002/api/portfolio/allocations/current
  ```

#### 11. Test Position Sizing with Allocations
- [ ] Restart Cerebro (it should load new ACTIVE allocation)
- [ ] Send test signal for a strategy
- [ ] Verify in logs:
  - Position sizing uses correct allocation %
  - Capital allocated = equity × allocation %
  - Margin checks still working

#### 12. Test Strategy Configuration Management
- [ ] **Test Strategy CRUD APIs:**
  ```bash
  # Create strategy
  curl -X POST http://localhost:8002/api/strategies \
    -H "Content-Type: application/json" \
    -d '{"strategy_id": "SPX_1-D_Opt", "strategy_name": "SPX Options", "status": "TESTING", "account": "IBKR_Main", "trading_mode": "PAPER", "include_in_optimization": true}'

  # Get all strategies
  curl http://localhost:8002/api/strategies

  # Update strategy
  curl -X PUT http://localhost:8002/api/strategies/SPX_1-D_Opt \
    -H "Content-Type: application/json" \
    -d '{"status": "ACTIVE", "trading_mode": "LIVE"}'

  # Get single strategy
  curl http://localhost:8002/api/strategies/SPX_1-D_Opt
  ```

- [ ] **Test Signal Rejection for INACTIVE Strategy:**
  - [ ] Set strategy status to INACTIVE
  - [ ] Send signal for that strategy
  - [ ] Verify signal is rejected with log: "Strategy {id} is INACTIVE"

- [ ] **Test PAPER vs LIVE Mode:**
  - [ ] Set strategy to PAPER mode
  - [ ] Send signal
  - [ ] Verify order is logged but NOT submitted to broker
  - [ ] Switch to LIVE mode
  - [ ] Send signal
  - [ ] Verify order IS submitted to broker

- [ ] **Test Optimization Filtering:**
  - [ ] Create 3 strategies: A (ACTIVE + include_opt), B (ACTIVE + no opt), C (INACTIVE + include_opt)
  - [ ] Run portfolio optimization
  - [ ] Verify only strategy A is included in optimization
  - [ ] Check logs for exclusion reasons for B and C

- [ ] **Test Account Routing:**
  - [ ] Set strategy to account: IBKR_Futures
  - [ ] Send signal
  - [ ] Verify ExecutionService routes to correct account

---

## Next: Milestone 1.3 - Simple Admin Frontend

### Phase A: Setup & Project Structure

#### 1. Create Frontend Project
- [ ] Create `frontend/` directory at project root
- [ ] Initialize Vite + React + TypeScript:
  ```bash
  cd frontend
  npm create vite@latest . -- --template react-ts
  npm install
  ```
- [ ] Install dependencies:
  ```bash
  npm install tailwindcss postcss autoprefixer
  npm install recharts react-query axios react-router-dom
  npm install @headlessui/react @heroicons/react
  ```
- [ ] Setup TailwindCSS config
- [ ] Create basic folder structure:
  ```
  frontend/
    src/
      components/
      pages/
      api/
      hooks/
      types/
      utils/
  ```

#### 2. Setup API Client
- [ ] Create `src/api/client.ts` using axios
- [ ] Create `src/api/portfolio.ts` with functions:
  - getCurrentAllocation()
  - getLatestRecommendation()
  - approveAllocation()
  - customAllocation()
  - getAllocationHistory()
  - getLatestOptimization()
- [ ] Create `src/api/trading.ts`:
  - getAccountState()
  - getRecentSignals()
  - getRecentOrders()
- [ ] Create `src/api/strategies.ts`:
  - getAllStrategies(filters)
  - getStrategy(strategyId)
  - createStrategy(data)
  - updateStrategy(strategyId, data)
  - deleteStrategy(strategyId)
  - syncBacktest(strategyId)

### Phase B: Pages & Components

#### 3. Login Page
- [ ] Create `src/pages/LoginPage.tsx`
- [ ] Simple username/password form
- [ ] Store JWT token in localStorage
- [ ] Create protected route wrapper

#### 4. Dashboard Home Page
- [ ] Create `src/pages/DashboardPage.tsx`
- [ ] Display portfolio metrics:
  - Current Equity (from AccountDataService)
  - Today's P&L ($ and %)
  - Margin Used / Max (% bar chart)
  - Open Positions count
- [ ] Recent activity feed (last 10 signals/orders)
- [ ] Use React Query for data fetching

#### 5. Allocations Page
- [ ] Create `src/pages/AllocationsPage.tsx`
- [ ] Current Allocations Table:
  - Strategy Name | Allocation % | Capital $ | Status
- [ ] Recommended Allocations Section (if pending):
  - Comparison table
  - Approve / Edit & Approve / Reject buttons
- [ ] Correlation Matrix Heatmap (Recharts)
- [ ] Allocation History table

#### 6. Trading Activity Page
- [ ] Create `src/pages/ActivityPage.tsx`
- [ ] Recent Signals table
- [ ] Recent Orders & Executions table
- [ ] Cerebro Decisions log (collapsible details)

#### 6a. Strategy Management Page
- [ ] Create `src/pages/StrategiesPage.tsx`
- [ ] **Strategies Table Component:**
  - [ ] Columns: Strategy ID, Name, Status, Account, Mode, Include in Optimization, Actions
  - [ ] Status badge (Green=ACTIVE, Yellow=TESTING, Gray=INACTIVE)
  - [ ] Mode badge (Blue=LIVE, Gray=PAPER)
  - [ ] Inline toggles for Status and Mode (update on change)
  - [ ] Account dropdown (update on change)
  - [ ] Include in Optimization checkbox (update on change)
  - [ ] Actions: Edit, Sync Backtest, Delete buttons
  - [ ] Search bar (filter by strategy ID or name)
  - [ ] Filter dropdowns (Status, Account, Mode)
- [ ] **Add New Strategy Button:**
  - [ ] Opens modal with form
  - [ ] Fields: Strategy ID*, Name*, Status*, Account*, Mode*, Include in Opt, Risk Limits, Dev Contact, Notes
  - [ ] Validation: Required fields, unique strategy_id
  - [ ] Submit → POST /api/strategies
- [ ] **Edit Strategy Modal:**
  - [ ] Same form as Add, pre-populated
  - [ ] Submit → PUT /api/strategies/{id}
- [ ] **Delete Confirmation Modal:**
  - [ ] Warning: "Are you sure? This cannot be undone"
  - [ ] Check for active allocations before allowing delete
- [ ] **Sync Backtest Feature:**
  - [ ] Click "Sync Backtest" → shows progress indicator
  - [ ] Calls POST /api/strategies/{id}/sync-backtest
  - [ ] Shows success/error toast notification
- [ ] **Expandable Row for Backtest Data:**
  - [ ] Click "View Backtest Data" → row expands
  - [ ] Shows: Sharpe Ratio, Max Drawdown, Win Rate, Volatility, Backtest Period
  - [ ] If no backtest data, show warning: "No backtest data available"

#### 7. Layout & Navigation
- [ ] Create `src/components/Layout.tsx`
- [ ] Sidebar navigation with links:
  - [ ] Dashboard (/)
  - [ ] Allocations (/allocations)
  - [ ] **Strategies (/strategies)** ← NEW
  - [ ] Trading Activity (/activity)
  - [ ] Logout
- [ ] Top bar with user info
- [ ] Router setup in `src/main.tsx`
  - [ ] Add route for /strategies → StrategiesPage

### Phase C: Testing & Polish

#### 8. Local Development
- [ ] Run frontend dev server:
  ```bash
  cd frontend && npm run dev
  ```
- [ ] Test all pages with live backend
- [ ] Verify API calls working
- [ ] Check responsive design

#### 9. Build & Deploy (Local)
- [ ] Build static assets:
  ```bash
  npm run build
  ```
- [ ] Test production build locally
- [ ] Document how to deploy to Cloud Storage (for Milestone 1.4)

---

## Later: Milestone 1.4 - GCP Deployment
(Detailed todos to be added when we reach this milestone)

---

## Development Commands

### Start All Services
```bash
./run_mvp_demo.sh
```

### View Logs
```bash
tail -f logs/cerebro_service.log
tail -f logs/execution_service.log
tail -f logs/account_data_service.log
```

### Test Signal Send
```bash
python signal_sender.py --ticker AAPL --action BUY --price 150.25
```

### MongoDB Access
```bash
mongosh "mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_trading"
```

### Stop All Services
```bash
./stop_mvp_demo.sh
```
