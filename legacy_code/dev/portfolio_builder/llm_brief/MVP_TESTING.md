MVP End-to-End Testing Guide

  Prerequisites

  Make sure you have:
  - MongoDB connection working (check .env has
  MONGODB_URI)
  - Interactive Brokers TWS/Gateway running on port 7497
   (for execution testing)
  - CSV files with strategy backtest data ready

  ---
  TEST 1: Load Strategy Data

  What this does: Loads all strategy backtest data from
  CSV files into MongoDB

  Command:
  cd /Users/vandanchopra/Vandan_Personal_Folder/CODE_STU
  FF/Projects/MathematricksTrader
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/venv/bin/python
  tools/load_strategies_from_folder.py
  dev/portfolio_combiner/real_strategy_data/

  Expected Output:
  ======================================================
  ==========================
  LOADING STRATEGIES FROM:
  dev/portfolio_combiner/real_strategy_data/
  ======================================================
  ==========================
  Found 9 CSV files

  📊 Processing: Com1-Met
  ------------------------------------------------------
  ------
     Data points: XXX
     Mean return: 0.0XXX% daily
     Volatility: 0.XXX% daily
     Sharpe (annual): X.XX
     Max Drawdown: -XX.XX%
     ✅ Loaded into MongoDB

  [... repeats for all 9 strategies ...]

  ✅ COMPLETE: Loaded 9/9 strategies
  ======================================================
  ==========================

  📋 Strategies in MongoDB:
     [✓] SPX_1-D_Opt - ACTIVE
     [✓] Com1-Met - ACTIVE
     [✓] Com2-Ag - ACTIVE
     [... etc ...]

  Verification: Check MongoDB has the data:
  mongosh "your_mongodb_uri_here"
  use mathematricks_trading
  db.strategy_configurations.countDocuments()
  db.strategy_backtest_data.countDocuments()

  Should show 9 documents in each collection.

  ---
  TEST 2: Run Portfolio Optimization

  What this does: Analyzes correlations, maximizes
  Sharpe ratio, creates allocation recommendation

  Command:
  cd /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/services/cerebro_service
  al

  Expected Output:
  ======================================================
  ==========================
  STARTING DAILY PORTFOLIO OPTIMIZATION
  ======================================================
  ==========================
  Fetching strategy backtest data from MongoDB...
  Loaded 9 strategies for optimization
  Running portfolio optimization (maximize Sharpe
  ratio)...
  Calculating portfolio metrics...
  Calculating correlation matrix...
  ✅ Saved optimization run: OPT_20251012_210000
  ✅ Created new allocation recommendation:
  ALLOC_20251012_210000
     Status: PENDING_APPROVAL
     Total allocation: 92.05%
     Expected Sharpe (annual): 2.15
  ======================================================
  ==========================
  OPTIMIZATION COMPLETE
  ======================================================
  ==========================
  Run ID: OPT_20251012_210000
  Allocation ID: ALLOC_20251012_210000
  Strategies optimized: 9
  Execution time: 150ms
  Status: Awaiting portfolio manager approval
  ======================================================
  ==========================

  Note the Allocation ID - you'll need it for the next
  step (e.g., ALLOC_20251012_210000)

  ---
  TEST 3: Start All Services

  What this does: Starts the entire MVP stack (Pub/Sub,
  all microservices, frontend)

  Command:
  cd /Users/vandanchopra/Vandan_Personal_Folder/CODE_STU
  FF/Projects/MathematricksTrader
  ./run_mvp_demo.sh

  Expected Output:
  ==========================================
  MATHEMATRICKS MVP DEMO
  ==========================================

  Checking prerequisites...
  ✓ Python venv found
  ✓ .env file found

  Step 1: Starting Pub/Sub emulator...
  ✓ Pub/Sub emulator started (PID: XXXXX)

  Step 2: Creating Pub/Sub topics and subscriptions...
  ✓ Created topic: standardized-signals
  ✓ Created topic: trading-orders
  [... etc ...]

  Step 3: Starting AccountDataService (port 8002)...
  ✓ AccountDataService started (PID: XXXXX)

  Step 4: Starting CerebroService...
  ✓ CerebroService started (PID: XXXXX)
     ✅ Loaded ACTIVE portfolio allocation (ID:
  TEST_ALLOC_20251011_180000)
     Total strategies: 5
     Total allocation: 92.05%

  Step 5: Starting ExecutionService...
  ✓ ExecutionService started (PID: XXXXX)

  Step 6: Starting signal_collector (staging mode)...
  ✓ signal_collector started (PID: XXXXX)

  Step 7: Starting Admin Frontend (port 5173)...
  ✓ Admin Frontend started (PID: XXXXX)

  ==========================================
  ✓ ALL SERVICES RUNNING!
  ==========================================

  Services:
    • Pub/Sub Emulator: localhost:8085
    • AccountDataService: http://localhost:8002
    • CerebroService: http://localhost:8001
    • ExecutionService: Background (consumes from 
  Pub/Sub)
    • signal_collector: Monitoring
  staging.mathematricks.fund
    • Admin Frontend: http://localhost:5173

  Admin Dashboard:
    Open browser: http://localhost:5173
    Login: username=admin, password=admin

  Wait 5 seconds for all services to fully start.

  ---
  TEST 4: Approve Allocation via Frontend

  Steps:

  1. Open browser: http://localhost:5173
  2. Login:
    - Username: admin
    - Password: admin
  3. Navigate to Allocations page: Click "Allocations"
  in sidebar
  4. Check for Pending Recommendation:
    - Should see a card with status "PENDING_APPROVAL"
    - Shows the allocation ID from TEST 2
    - Shows expected Sharpe ratio, leverage, etc.
  5. Click "Approve" button
    - Enter your name (e.g., "Vandan")
    - Confirm approval
  6. Verify in logs:
  tail -f
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/logs/cerebro_service.log

  Should see:
  Portfolio allocations reloaded: 9 strategies
  ✅ Loaded ACTIVE portfolio allocation (ID:
  ALLOC_20251012_210000)
     Total strategies: 9
     Total allocation: 92.05%
       • SPX_1-D_Opt: 45.5%
       • Forex: 30.2%
       • Com1-Met: 24.3%
       [... etc ...]

  ---
  TEST 5: Send Test Signal & Observe Processing

  Setup: Open 3 terminal windows for log monitoring

  Terminal 1 - Signal Collection:
  tail -f
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/logs/signal_collector.log

  Terminal 2 - Position Sizing:
  tail -f
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/logs/cerebro_service.log

  Terminal 3 - Execution:
  tail -f /Users/vandanchopra/Vandan_Personal_Folder/COD
  E_STUFF/Projects/MathematricksTrader/logs/execution_se
  rvice.log

  Send Test Signal (Terminal 4):
  cd /Users/vandanchopra/Vandan_Personal_Folder/CODE_STU
  FF/Projects/MathematricksTrader
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/venv/bin/python
  signal_sender.py --staging --signalId 'test_com1_001'
  --signal '{"strategy_name": "Com1-Met", "ticker": 
  "AAPL", "action": "BUY", "price": 150.25, "quantity": 
  1}'

  ---
  Expected Flow in Logs:

  Terminal 1 (signal_collector.log):

  🔥 REAL-TIME SIGNAL DETECTED!
  📊 Strategy: Com1-Met
  🆔 Signal ID: test_com1_001
  📡 Signal: {'ticker': 'AAPL', 'action': 'BUY',
  'price': 150.25}
  ──────────────────────────────────────────────────────
  ──────

  🚀 Routing to MVP microservices (Cerebro → Execution)
  ✅ Signal published to Cerebro: 15
     → Signal ID: Com1_Met_20251012_220504_test_com1_001
     → Instrument: AAPL
     → Action: BUY

  Terminal 2 (cerebro_service.log):

  Received signal:
  Com1_Met_20251012_220504_test_com1_001
  Processing signal
  Com1_Met_20251012_220504_test_com1_001

  ======================================================
  ================
  📊 POSITION SIZING CALCULATION for AAPL
  ======================================================
  ================
  Strategy: Com1-Met
  Account State:
    • Equity: $251,786.30
    • Margin Used: $3.04
    • Margin Available: $251,783.26
    • Current Margin Utilization: 0.00%

  Portfolio Allocation:
    • Strategy Allocation: 24.3% of portfolio
    • Allocated Capital: $251,786.30 × 24.3% =
  $61,184.11

  Quantity Calculation:
    • Price per share: $150.25
    • Quantity: $61,184.11 / $150.25 = 407.26 shares

  Margin Requirements:
    • Margin Requirement: 50% (stocks)
    • Margin Required: $61,184.11 × 0.5 = $30,592.06

  Margin Check:
    • Current Margin Used: $3.04
    • New Position Margin: $30,592.06
    • Total Margin After: $30,595.10
    • Margin Utilization After: 12.15%
    • Max Allowed: 40%

  ✅ DECISION: APPROVED
    • Final Quantity: 407.26 shares
    • Capital Allocated: $61,184.11
    • Margin Required: $30,592.06
    • Final Margin Utilization: 12.15%
  ======================================================
  ================

  🎯 CEREBRO DECISION | Signal:
  Com1_Met_20251012_220504_test_com1_001 | Strategy:
  Com1-Met | Symbol: AAPL | Action: BUY | Allocation:
  24.3% | Position Size: 407.26 shares | Price: $150.25
  | Capital: $61,184 | Margin: 12.2% | Decision:
  APPROVED

  Published trading order
  Com1_Met_20251012_220504_test_com1_001_ORD for signal 
  Com1_Met_20251012_220504_test_com1_001: 16

  Terminal 3 (execution_service.log):

  Received trading order:
  Com1_Met_20251012_220504_test_com1_001_ORD - adding to
   queue
  Processing order from queue: 
  Com1_Met_20251012_220504_test_com1_001_ORD

  placeOrder: New order
  Trade(contract=Stock(symbol='AAPL', exchange='SMART',
  currency='USD'), order=MarketOrder(orderId=10,
  action='BUY', totalQuantity=407),
  orderStatus=OrderStatus(status='PendingSubmit',
  filled=0.0, remaining=0.0))

  orderStatus: Trade(status='PreSubmitted', filled=0.0,
  remaining=407.0)

  Submitted order
  Com1_Met_20251012_220504_test_com1_001_ORD to IBKR

  orderStatus: Trade(status='Filled', filled=407.0, 
  remaining=0.0, avgFillPrice=150.28)

  Published execution confirmation: 17
  ✅ Order Com1_Met_20251012_220504_test_com1_001_ORD
  executed: FILLED
  Published account update: 18

  ---
  TEST 6: Verify Math is Correct

  From Terminal 2 output above, verify:

  1. Strategy Allocation: Should match approved
  allocation (e.g., Com1-Met = 24.3%)
  2. Allocated Capital: Equity × Allocation% = $251,786
  × 24.3% = $61,184 ✅
  3. Quantity: Allocated Capital / Price = $61,184 /
  $150.25 = 407 shares ✅
  4. Margin Required: Allocated Capital × 50% = $30,592
  ✅
  5. Margin Utilization: Margin Required / Equity =
  $30,592 / $251,786 = 12.15% ✅
  6. Below Limit: 12.15% < 40% ✅

  ---
  TEST 7: Check Frontend Activity

  1. Open browser: http://localhost:5173/activity (or
  port 5174 if 5173 was taken)
  2. Should see:
    - Recent signal received
    - Position sizing decision
    - Order submitted
    - Execution confirmation

  Note: If Activity page is empty, that's because it
  hasn't been fully implemented yet. Check MongoDB
  instead:

  mongosh "your_mongodb_uri_here"
  use mathematricks_trading
  db.cerebro_decisions.find().sort({_id:
  -1}).limit(1).pretty()
  db.trading_orders.find().sort({_id:
  -1}).limit(1).pretty()
  db.execution_confirmations.find().sort({_id:
  -1}).limit(1).pretty()

  ---
  TEST 8: Send Multiple Signals for Different Strategies

  Test with different strategies to verify allocations:

  # SPX_1-D_Opt (should have ~45.5% allocation)
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/venv/bin/python
  signal_sender.py --staging --signalId 'test_spx_001'
  --signal '{"strategy_name": "SPX_1-D_Opt", "ticker": 
  "SPX", "action": "BUY", "price": 5750.0, "quantity": 
  1}'

  # Forex (should have ~30.2% allocation)
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/venv/bin/python
  signal_sender.py --staging --signalId 'test_forex_001'
   --signal '{"strategy_name": "Forex", "ticker": 
  "EURUSD", "action": "BUY", "price": 1.0850, 
  "quantity": 1}'

  Watch Terminal 2 and verify each strategy gets correct
   allocation %

  ---
  STOP SERVICES When Done

  cd /Users/vandanchopra/Vandan_Personal_Folder/CODE_STU
  FF/Projects/MathematricksTrader
  ./stop_mvp_demo.sh

  ---
  Troubleshooting

  Issue: Frontend shows no strategies

  Check:
  curl http://localhost:8002/api/v1/strategies

  If empty response, strategies didn't load. Re-run TEST
   1.

  Issue: No allocation to approve

  Check MongoDB:
  mongosh "your_mongodb_uri"
  use mathematricks_trading
  db.portfolio_allocations.find({status:
  "PENDING_APPROVAL"}).pretty()

  If empty, re-run TEST 2.

  Issue: CerebroService shows "No allocation found"

  CerebroService didn't reload. Manually trigger:
  curl -X POST
  http://localhost:8001/api/v1/reload-allocations

  Issue: Signal not reaching CerebroService

  Check signal_collector is connected:
  grep "Change Stream connected"
  /Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/
  Projects/MathematricksTrader/logs/signal_collector.log

  Should show: ✅ Change Stream connected - waiting for 
  staging signals only...

  ---
  Success Criteria

  You've successfully tested MVP when:

  - ✅ All 9 strategies loaded into MongoDB
  - ✅ Optimization created allocation recommendation
  - ✅ Frontend showed pending allocation
  - ✅ Approved allocation via frontend
  - ✅ CerebroService reloaded with new allocations
  - ✅ Test signal processed through all services
  - ✅ Position size calculated correctly based on
  allocation
  - ✅ Order submitted to IBKR and filled
  - ✅ Math verified: Equity × Allocation% / Price =
  Quantity