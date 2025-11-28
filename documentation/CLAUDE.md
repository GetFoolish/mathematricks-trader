# Claude Code Project Instructions

## General Rules
- read all the files in [text](dev/portfolio_builder/llm_brief)
- for python use the venv: /Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks-trader/venv/bin/python
- for environment variables, use: /Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks-trader/.env
- Use this file to keep track of your to-do list, and keep updating it here as work gets done.
- Before you start working on something, make sure that you work with the user to come up with tests for what you are trying to achieve. Once the tests are approved by the USER, then start developing the project to achieve the tests. Make sure you get the user to also include 'Integration Tests' as needed. Also, the test files should only have 'imported code' and never any hard-coded code in it. The tests are meant to test the underlying 'codebase' ONLY and not achieve anything else.
- Before you move to the next to-do or next set of problems, ask the user if they want to do a git commit and git push.
- Use logging in /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs folder and create log files for debugging. But once you're done, set logging to INFO and make sure that it is only important information a human would need.
- Write small tests in bash to make sure that your code is working, and that the logic is accurate and the math is accurate.
- Be very organized in your work. If you rewrite a function, make sure you remove the old one. If u make a new file, ask yourself, what is the best place to keep this file, and put the file in the right place. I don't want a messy repo by the time you are done with your work.
- Always, before we push code to github or CICD deployment, lets first test everything we have developed locally. and if everything is approved and working properly, only then we will go into deployment
- Do not take shortcuts, always write real code, which can be used in production, as opposed to dummy code. If u want to test something with dummy code, write a quick 'bash test' and run it without saving it to the project, cause that makes the project messy.
- If there is a situation where you think it'll be better to ask the user for direction, please give them options to chose from, explain each decision, and let them decide.
- If you give me commands to run, always give them to me in a way that i can copy paste it. Right now, there are extra spaces when i copy it from your window.

---

A few things to check in the calculations:
1) When an order comes in, it needs to do position sizing keeping in mind some sort of P95 of total allocation and size trying to maximize deployment. rigth now, i think it just takes the full allocation gives it all to one order. some sort of math to predict how many positions does the straetgy have open typically or average.
2) when an order is sent, it needs to get confirmation that the order was placed and filled or is placed and awiting fill and then calculate the balance amount the strategy has available for allcoation.
3) when an order comes in, it needs to check how much of it's own margin is already deployed. and how much is left. and then decide to approve or not.

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
You're absolutely right! Let me document what we accomplished and what's still pending:

## Phase 2 & Phase 3 - COMPLETED ✅

### Why We Started This (The Original Problem)
The portfolio equity CSV was missing the `margin_used_pct` column, and when we added it, we discovered it was fundamentally broken:

- **2017**: margin_used_pct = 85%
- **2025**: margin_used_pct = 0.5%

**Root Cause**: Margin data from strategies is in absolute dollars (e.g., $85k), but portfolio equity grew 110x (from $100k → $11.4M). The margin dollars stayed constant while equity grew, making the percentage drop artificially.

### The Solution - COMPLETED ✅

#### Phase 3 - Margin Constraint in Optimization ✅
- **Location**: [allocator.py](services/cerebro_service/portfolio_constructor/max_hybrid/allocator.py)
- **Implementation**: Added constraint to scipy optimizer
- **Constraint**: `max(portfolio_margin) <= account_equity × max_leverage × 0.8`
- **Results**: CAGR 5.46%, Sharpe 3.82, Max DD -1.49%
- **Status**: WORKING - ensures portfolio is tradeable within margin limits

#### Phase 2 - Backtest Engine Margin Calculation ✅
- **Files Modified**:
  - ✅ [load_strategies_from_folder.py](tools/load_strategies_from_folder.py) - Unified structure + synthetic data generation
  - ✅ [construct_portfolio.py](services/cerebro_service/research/construct_portfolio.py) - Read new unified structure
  - ✅ [backtest_engine.py](services/cerebro_service/research/backtest_engine.py) - Fixed margin% calculation using account_equity normalization

- **Implementation**: Correct margin calculation methodology:
  1. Calculate per-strategy margin as % of their account equity: `strategy_margin_pct = strategy_margin / strategy_account_equity`
  2. Weight by allocation to get portfolio margin %: `portfolio_margin_pct = sum(weight × strategy_margin_pct)`
  3. Apply to current portfolio equity: `portfolio_margin_dollars = portfolio_margin_pct × current_equity`

- **Results**: Portfolio equity CSV now has all required columns:
  - `date` - Trading date
  - `equity` - Portfolio equity in dollars
  - `returns_pct` - Daily return percentage (3 decimals)
  - `margin_used` - Total margin in dollars
  - `margin_used_pct` - Margin as % of equity (now consistent: 0.2% to 15% throughout backtest) ✅
  - `notional_value` - Total notional in dollars

### NEEDS WORK (Next):
- **Margin Parameters** - 1-15% usage is low, may need to adjust synthetic data parameters for more realistic margin usage
- **Phase 2 Signal Evaluator** - Update [signal_evaluator.py](services/cerebro_service/portfolio_constructor/max_hybrid/signal_evaluator.py) to use real margin data instead of hardcoded 50% assumption
- **Frontend Strategies Tab** - Update to handle new unified document structure
- **Live Mode Testing** - Send sample signals every 15 seconds and validate signal processing

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
