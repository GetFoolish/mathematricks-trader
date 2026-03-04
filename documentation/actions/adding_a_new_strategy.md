# Adding a New Strategy - Complete Frontend Guide

This guide walks you through adding a new trading strategy to the Mathematricks system using the **Admin Frontend UI** (http://localhost:5173). 

---

## 🎯 Overview

When adding a new strategy, you'll progress through these steps:

1. **Add Strategy + Backtest Data** - Upload strategy with performance metrics
2. **Choose Funds** - Decide which funds will trade this strategy
3. **Configure Trading Accounts** - Set up broker accounts for each mode
4. **Run Fund Allocation** - Generate optimal portfolio weights
5. **Approve Allocation** - Lock in the portfolio allocation
6. **Test Mock_Mock** - Verify signal flow (no broker needed)
7. **Test Mock_Live** - Test with live market data (IB Gateway required)
8. **Test Paper_Live** - Run IBKR paper trading
9. **Go Live_Live** - Production trading with real money

---

## 📋 Prerequisites

Before starting:
- ✅ **Docker services running**: `make start-dev`
- ✅ **MongoDB running**: Port 27018
- ✅ **Admin frontend running**: `cd frontend-admin && npm run dev`
- ✅ **IB Gateway**: Connected for paper_live/live_live modes
- ✅ **Strategy backtest data**: CSV file with OHLC bars and positions

---

## Step 1: Add Strategy + Backtest Data

### Navigation
1. Open **http://localhost:5173** in your browser
2. Login (use any credentials for MVP)
3. Click **"Fresh Strategies"** in the sidebar

### Upload Strategy

Click the **"Upload Strategy"** button (top right) to open the 3-step wizard:

#### Step 1.1: Upload CSV File
- **File Format**: Your backtest CSV should contain:
  - `Date` - Timestamp for each bar
  - `Open`, `High`, `Low`, `Close` - OHLC price data
  - `Position` - Position size at each bar (-1 short, 0 flat, 1 long)
  - Optional: `Portfolio Value`, `Returns`, `Drawdown`
  
- **Example Format**:
  ```csv
  Date,Open,High,Low,Close,Position,Portfolio Value
  2023-01-01,100.0,102.0,99.5,101.5,1,100000
  2023-01-02,101.5,103.0,101.0,102.5,1,101500
  ```

- **Click** "Choose File" and select your CSV
- **Preview**: System will show first 5 rows
- **Click** "Next"

#### Step 1.2: Map Columns
The system auto-detects standard column names but allows you to remap if needed:

- **Required Mappings**:
  - `Date` → Your date/timestamp column
  - `Close` → Your closing price column
  - `Position` → Your position column
  
- **Optional Mappings**:
  - `Open`, `High`, `Low` (for candlestick charts)
  - `Portfolio Value` (for equity curve)
  - `Returns`, `Drawdown` (for performance metrics)

- **Click** "Next"

#### Step 1.3: Developer Info
Fill in strategy metadata:

**Strategy Details**:
- **Strategy Name**: `FloridaForex_Developer` (use consistent naming)
- **Description**: `Forex trading strategy from Google Sheets`
- **Asset Class**: Select `forex` from dropdown
- **Instrument Type**: `FX` (or `EQUITY`, `FUTURES`, etc.)
- **Base Currency**: `CAD` (should match your IBKR account base currency)

**Developer Contact**:
- **Developer Name**: `Leslie Smith` (your developer's name)
- **Email**: `leslie@example.com`
- **Phone**: `+1-555-0100` (optional)

**Signal Source**:
- **Source Type**: Select `Google Sheets` from dropdown
- **Source URL**: `https://docs.google.com/spreadsheets/d/1234567890abcdef/edit` (your sheet URL)
- **Update Frequency**: `Real-time` or `Every 5 minutes`

**Click** "Submit" to upload.

### Approval Process

After upload, the strategy appears in the **"PENDING APPROVAL"** tab:

1. **Review Metrics**: System auto-calculates:
   - CAGR (Compound Annual Growth Rate)
   - Sharpe Ratio
   - Max Drawdown
   - Win Rate
   - Total Trades

2. **View Tearsheet**: Click "Tearsheet" button to see full performance report

3. **Approve Strategy**:
   - Click **"Approve"** button
   - Modal opens with strategy details
   - **Select Trading Mode**: Choose `PAPER` to start
   - **Set Initial Status**: Choose `ACTIVE`
   - **Add Notes**: "Initial approval for paper trading"
   - Click **"Approve Strategy"**

The strategy now moves to the **"Strategies"** page.

---

## Step 2: Choose Funds to Trade This Strategy

### Navigation
Click **"Strategies"** in the sidebar to see all approved strategies.

### Understand Fund Structure

A **Fund** represents a pool of capital that can trade multiple strategies. Think of it as:
- A trading account (e.g., "Forex Fund", "Equity Fund")
- Has total equity (e.g., $100,000)
- Can allocate percentages to different strategies (e.g., 60% to Strategy A, 40% to Strategy B)

**Question to ask yourself**: 
- Do I want this strategy in an **existing fund** with other strategies?
- Or should I create a **new dedicated fund** for just this strategy?

### Option A: Use Existing Fund

If you have an existing fund (e.g., "Main Trading Fund"):
1. Go to **"Allocations"** page
2. In **Part 4: Research Lab**, you'll add this strategy to allocation tests
3. Skip to [Step 4: Run Fund Allocation](#step-4-run-fund-allocation)

### Option B: Create New Fund

Navigate to **"Fund Setup"** in the sidebar to open the fund wizard:

#### Step 2.1: Create Fund Details
- **Fund ID**: `forex-developer-fund` (lowercase, hyphenated)
- **Fund Name**: `Developer Forex Strategy Fund`
- **Description**: `Dedicated fund for Leslie's Google Sheets forex strategy`
- **Base Currency**: `CAD` (must match strategy and IBKR account)
- **Total Equity**: `100000` (starting capital in CAD)
- **Status**: Select `ACTIVE`

**Click** "Add Fund" to save.

The fund wizard tracks your funds in a temporary list. You can:
- Edit fund details (pencil icon)
- Delete fund (trash icon)
- Add multiple funds before moving to accounts

**Click** "Next: Configure Accounts" when ready.

---

## Step 3: Add Trading Accounts to the Strategy

Trading accounts are broker connections that execute orders. Each account has:
- **Broker** (Mock, IBKR, Kraken, Coinbase)
- **Account Number** (from your broker)
- **Asset Classes** (what it can trade: equity, forex, crypto, etc.)
- **Client IDs** (for IBKR connection management)

### Step 3.1: Configure Account in Fund Wizard

You should now be on **"Step 2: Configure Accounts"** in the fund wizard.

**For each fund** you created:

1. **Select Fund**: Choose `forex-developer-fund` from dropdown

2. **Click** "Add Account" to open account form:

   **Basic Info**:
   - **Account ID**: `FOREX-DEV-ACCOUNT` (unique identifier)
   - **Broker**: Select `IBKR` from dropdown
   - **Broker Account Number**: `DU9876543` (your IBKR paper account number)
   - **Account Type**: Select `paper` (for paper_live testing)

   **Asset Classes** (check all that apply):
   - ☑ Forex (check this for forex strategies)
   - ☐ Equity
   - ☐ Futures
   - ☐ Options
   - ☐ Crypto
   - ☐ Commodities

   **IBKR Client IDs** (important for connection management):
   - **Execution Client ID**: `3` (must be in range 1-99)
   - **Account Data Client ID**: `103` (must be in range 100-199)
   
   > **Why Two Client IDs?**  
   > The system has separate services:
   > - **Execution Service** (1-99): Sends orders to IBKR
   > - **Account Data Service** (100-199): Polls account balances/positions
   >
   > Each needs its own client ID to connect to IB Gateway simultaneously.

   **IBKR Settings**:
   - **Gateway Host**: `127.0.0.1` (localhost)
   - **Gateway Port**: `4004` (for paper trading, use `4001` for live)
   - **Trading Permissions**: 
     - ☑ FOREX
     - ☑ STK (if needed)

3. **Click** "Save Account"

4. **Repeat** for other funds if needed

**Click** "Next: Review" when all accounts configured.

### Step 3.2: Review and Export

Review your fund and account configuration:

- **Fund Summary**: Shows fund_id, name, currency, total_equity
- **Accounts Summary**: Shows all accounts with their brokers and asset classes

**Click** "Create Funds & Accounts" to save to MongoDB.

Success! Your funds and accounts are now created.

---

## Step 4: Run Fund Allocation

Allocation determines what percentage of each fund goes to which strategy. The system uses portfolio optimization to maximize risk-adjusted returns.

### Navigation
Go to **"Allocations"** page (sidebar).

### Understanding Allocation Parts

The Allocations page has 4 sections:

1. **Part 1: Current Allocation** - What's currently approved and live
2. **Part 2: Allocation Editor** - Manual editing or test approval
3. **Part 3: Portfolio Tests** - History of allocation tests
4. **Part 4: Research Lab** - Create new allocation tests

### Run New Allocation Test

Scroll to **Part 4: Research Lab** at the bottom.

#### Step 4.1: Select Strategies
- **Strategy Pool**: You'll see a list of all ACTIVE strategies
- **Check strategies** you want to include in allocation:
  - ☑ `FloridaForex_Developer` (your new strategy)
  - ☑ Any other active strategies

> **Tip**: If this is a dedicated fund, select only your one strategy.  
> If this is a multi-strategy fund, select all strategies you want considered.

#### Step 4.2: Select Constructor
Choose portfolio construction method:

- **MaxCAGR**: Maximize absolute returns (aggressive)
- **MaxHybrid**: Balance returns with risk (recommended)
- **MaxSharpe**: Maximize risk-adjusted returns (conservative)

**Select** `max_hybrid` for most use cases.

#### Step 4.3: Run Test
Click **"Run Portfolio Test"** button.

**What Happens**:
1. System sends request to Portfolio Builder service
2. Builder calculates optimal allocations using:
   - Strategy backtests
   - Correlation matrix
   - Risk metrics
   - Selected constructor algorithm
3. Creates a new portfolio test
4. Auto-scrolls to **Part 3: Portfolio Tests**

#### Step 4.4: View Results
In **Part 3: Portfolio Tests**, you'll see your new test:

- **Test ID**: Auto-generated (e.g., `test_20240115_143022`)
- **Created**: Timestamp
- **Constructor**: `max_hybrid`
- **Strategies Included**: Count of strategies
- **Allocation Breakdown**: Click to expand and see percentages

**Example Allocation**:
```
FloridaForex_Developer: 100.0%
```

Or for multi-strategy fund:
```
FloridaForex_Developer: 60.0%
MomentumEquity_v2: 25.0%
MeanReversion_v3: 15.0%
```

---

## Step 5: Approve Allocation

Once you're happy with a portfolio test, approve it to make it the **current allocation**.

### Approve from Portfolio Tests (Part 3)

1. **Expand Test**: Click test row to expand allocation details
2. **Click** "Approve" button
3. **Approval Modal** opens:
   - **Select Fund**: Choose `forex-developer-fund`
   - **Approve By**: Your name (e.g., "Admin")
   - **Notes**: "Initial allocation for forex strategy"
4. **Click** "Approve Allocation"

**What Happens**:
- The allocation is saved to `funds.approved_allocation`
- **Part 1: Current Allocation** updates to show this allocation
- Future signals will use these percentages for position sizing

### Verify Current Allocation

Scroll to **Part 1: Current Allocation** at the top:

You should see:
- **Fund**: `forex-developer-fund`
- **Total Equity**: $100,000
- **Allocation**:
  - `FloridaForex_Developer`: 100%
- **Approved At**: Timestamp
- **Approved By**: Your name

---

## Step 6: Test Mock_Mock Mode

Now test the complete signal flow without needing IB Gateway or real brokers.

### What is Mock_Mock?
- **Account Type**: Mock (simulated broker)
- **Data Source**: Mock (synthetic data)
- **Purpose**: Fast testing of signal ingestion → Cerebro → Execution
- **Duration**: Seconds
- **Gateway Required**: ❌ No

### Run Mock_Mock Test

Option A: **Use Test Suite**

```bash
# From project root
python tests/run_test_suite.py \
  --mode mock_mock \
  --signal-testing \
  --signals-folder tests/sample_signals/forex
```

Option B: **Send Individual Signal**

Create a test signal file `tests/sample_signals/forex/test_signal.json`:

```json
{
  "strategy_id": "FloridaForex_Developer",
  "signal_id": "test_mock_001",
  "timestamp": "2024-01-15T14:30:00Z",
  "mode": "mock_mock",
  "account_type": "mock",
  "data_source": "mock",
  "environment": "development",
  
  "legs": [
    {
      "leg_id": 1,
      "action": "BUY",
      "symbol": "EUR.CAD",
      "quantity": 10000,
      "order_type": "MARKET",
      "instrument_type": "CASH"
    }
  ],
  
  "metadata": {
    "signal_source": "google_sheets",
    "developer": "Leslie Smith",
    "notes": "Test signal for mock_mock mode"
  }
}
```

Send signal:
```bash
curl -X POST http://localhost:3000/api/signals \
  -H "Content-Type: application/json" \
  -d @tests/sample_signals/forex/test_signal.json
```

### Verify Execution

Check the **Activity** page in the frontend:

1. **Navigate**: Click "Activity" in sidebar
2. **View Signals Tab**: Should see your signal with status `EXECUTED`
3. **View Orders Tab**: Should see order created by Cerebro
4. **View Executions Tab**: Should see execution confirmation

**Expected Flow**:
```
Signal Received → Signal Standardized → Order Created → Order Executed → Position Opened
```

**Logs to Check**:
```bash
# Signal ingestion
docker logs mathematricks-trader-signal-ingestion-1

# Cerebro (order creation)
docker logs mathematricks-trader-cerebro-1

# Execution service
docker logs mathematricks-trader-execution-1
```

### Success Criteria ✅
- Signal appears in `signal_store` collection (MongoDB)
- Order created in `trading_orders` collection
- Order status: `EXECUTED`
- Execution logged in `signal_store.legs[].execution`
- No errors in service logs

---

## Step 7: Test Mock_Live Mode

Test with **live market data** but still using mock execution (no real orders).

### What is Mock_Live?
- **Account Type**: Mock (simulated broker)
- **Data Source**: Live (real-time from IBKR)
- **Purpose**: Test strategy with real market prices
- **Duration**: 1-2 minutes
- **Gateway Required**: ✅ Yes (port 4004)

### Prerequisites
1. **IB Gateway Running**: 
   ```bash
   # Check if running
   docker ps | grep ibgateway
   
   # Start if needed
   make start-ibgateway-paper
   ```

2. **Verify Connection**:
   ```bash
   python test_local_ibgateway.py --mode paper
   ```

### Update Strategy Mode

Before testing, update strategy settings:

1. **Navigate**: Go to "Strategies" page
2. **Find Strategy**: `FloridaForex_Developer`
3. **Click** pencil icon to edit
4. **Update**:
   - **Trading Mode**: Keep as `PAPER`
   - **Status**: Keep as `ACTIVE`
   - **Mode Settings**: Ensure `mock_live` is enabled
5. **Click** "Save"

### Send Mock_Live Signal

Update your signal JSON with `mock_live` mode:

```json
{
  "strategy_id": "FloridaForex_Developer",
  "signal_id": "test_mock_live_001",
  "timestamp": "2024-01-15T14:35:00Z",
  "mode": "mock_live",
  "account_type": "mock",
  "data_source": "live",
  "environment": "staging",
  
  "legs": [
    {
      "leg_id": 1,
      "action": "BUY",
      "symbol": "EUR.CAD",
      "quantity": 10000,
      "order_type": "MARKET",
      "instrument_type": "CASH"
    }
  ]
}
```

Send signal:
```bash
python tests/send_test_signal.py --file tests/sample_signals/forex/test_mock_live.json
```

### Verify Live Data

Check execution logs for **real market prices**:

```bash
docker logs mathematricks-trader-execution-1 --tail 50
```

Look for:
```
[EXECUTION] Symbol: EUR.CAD, Price: 1.4523 (LIVE from IBKR)
[EXECUTION] Order executed at market price
```

### Success Criteria ✅
- Signal executed successfully
- Prices come from IBKR live data (not synthetic)
- Order still executes in mock broker (no real IBKR order)
- Account data service can poll IBKR for account info

---

## Step 8: Test Paper_Live Mode

Run **IBKR paper trading** - real orders but with simulated money.

### What is Paper_Live?
- **Account Type**: Paper (IBKR paper account)
- **Data Source**: Live (real-time from IBKR)
- **Purpose**: Full IBKR integration testing without real money
- **Duration**: Days/weeks (monitor real-time)
- **Gateway Required**: ✅ Yes (port 4004)

### Prerequisites

1. **IBKR Paper Account**: Must have valid paper trading account
2. **Trading Permissions**: Enable FOREX in TWS/Gateway
3. **Account Setup**: Your `FOREX-DEV-ACCOUNT` must be configured with:
   - `account_type: "paper"`
   - `broker_account_number: "DU9876543"` (your actual paper account)

### Update Strategy for Paper Mode

1. **Navigate**: Go to "Strategies" page
2. **Find Strategy**: `FloridaForex_Developer`
3. **Click** pencil icon to edit
4. **Update**:
   - **Trading Mode**: Change to `PAPER`
   - **Accounts**: Ensure `FOREX-DEV-ACCOUNT` is in `accounts.paper` array
5. **Click** "Save"

### Send Paper_Live Signal

```json
{
  "strategy_id": "FloridaForex_Developer",
  "signal_id": "test_paper_live_001",
  "timestamp": "2024-01-15T09:30:00Z",
  "mode": "paper_live",
  "account_type": "paper",
  "data_source": "live",
  "environment": "staging",
  
  "legs": [
    {
      "leg_id": 1,
      "action": "BUY",
      "symbol": "EUR.CAD",
      "quantity": 10000,
      "order_type": "MARKET",
      "instrument_type": "CASH"
    }
  ]
}
```

Send signal during **market hours** (9:30 AM - 4:00 PM ET for forex):
```bash
python tests/send_test_signal.py --file tests/sample_signals/forex/test_paper_live.json
```

### Monitor Execution

**In Frontend**:
1. **Activity Page**: Watch order status change from `PENDING` → `SUBMITTED` → `FILLED`
2. **Dashboard**: Check positions and P&L update

**In IBKR TWS**:
1. Login to your paper trading account
2. Go to **Portfolio** → **Positions**
3. Verify EUR.CAD position appears
4. Check **Orders** tab for fill confirmation

**Logs**:
```bash
# Watch execution in real-time
docker logs -f mathematricks-trader-execution-1

# Look for:
# [IBKR] Order submitted: OrderId=123, Status=PreSubmitted
# [IBKR] Order filled: OrderId=123, AvgPrice=1.4523
```

### Let It Run

**Recommended Duration**: 3-7 days

Monitor:
- Signal reception every update (e.g., every 5 minutes)
- Order execution latency
- Position tracking accuracy
- Account balance updates
- Forex residuals handling (CAD conversions)

**Daily Checks**:
1. **Dashboard**: Review P&L, open positions, margin usage
2. **Allocations**: Check if rebalancing occurred
3. **Logs**: Scan for errors or warnings
4. **IBKR TWS**: Verify positions match frontend

### Success Criteria ✅
- Signals execute successfully during market hours
- Orders appear in IBKR TWS paper account
- Fills confirmed and positions tracked
- Account balances update correctly
- Forex residuals convert to CAD base currency
- No errors in logs for 72+ hours
- P&L matches IBKR TWS

---

## Step 9: Go Live_Live (Production)

**⚠️ WARNING: This mode uses REAL MONEY. Only proceed when paper_live is 100% validated.**

### What is Live_Live?
- **Account Type**: Live (real IBKR account)
- **Data Source**: Live (real-time from IBKR)
- **Purpose**: Production trading with actual capital
- **Gateway Required**: ✅ Yes (port 4001)
- **Reversible**: ❌ Orders execute immediately with real money

### Prerequisites Checklist

Before going live, ensure:

- ✅ **Paper trading successful**: 7+ days with no issues
- ✅ **All tests passed**: mock_mock, mock_live, paper_live
- ✅ **Risk limits set**: Max position size, daily loss limits
- ✅ **Monitoring setup**: Alerts for errors, margin calls
- ✅ **IBKR live account funded**: Sufficient capital for strategy
- ✅ **Trading permissions**: FOREX enabled on live account
- ✅ **Emergency stop procedure**: Know how to halt trading
- ✅ **`ALLOW_LIVE_TRADING=true`**: Set in `.env` file

### Enable Live Trading

**1. Update Environment Variable**:
```bash
# Edit .env file
nano .env

# Add or update:
ALLOW_LIVE_TRADING=true

# Restart services
docker-compose down
docker-compose up -d
```

**2. Switch IB Gateway to Live**:
```bash
# Stop paper gateway
docker stop ibgateway-paper

# Start live gateway (port 4001)
make start-ibgateway-live
```

**3. Update Trading Account**:

Navigate to **"Accounts"** page:
1. Find `FOREX-DEV-ACCOUNT`
2. Click **Edit** (pencil icon)
3. Update:
   - **Account Type**: Change to `live`
   - **Broker Account Number**: Change to your **live** account (e.g., `U1234567`)
   - **Gateway Port**: Change to `4001`
4. Click **Save**

**4. Update Strategy Mode**:

Navigate to **"Strategies"** page:
1. Find `FloridaForex_Developer`
2. Click **Edit**
3. Update:
   - **Trading Mode**: Change to `LIVE`
   - **Accounts**: Ensure account is in `accounts.live` array
4. Click **Save**

**5. Approve for Live Allocation**:

Navigate to **"Allocations"** page:
1. Go to **Part 2: Allocation Editor**
2. Load your approved allocation test
3. Select Fund: `forex-developer-fund`
4. Click **"Approve for Live"**
5. Confirmation modal:
   - ⚠️ Warning: "This will enable LIVE trading with real money"
   - Type: `CONFIRM LIVE` to proceed
   - Click **"Enable Live Trading"**

### Send First Live Signal

**Start Small**:
```json
{
  "strategy_id": "FloridaForex_Developer",
  "signal_id": "live_001",
  "timestamp": "2024-01-15T09:30:00Z",
  "mode": "live_live",
  "account_type": "live",
  "data_source": "live",
  "environment": "production",
  
  "legs": [
    {
      "leg_id": 1,
      "action": "BUY",
      "symbol": "EUR.CAD",
      "quantity": 1000,  // Start with 10% of target size
      "order_type": "MARKET",
      "instrument_type": "CASH"
    }
  ],
  
  "metadata": {
    "notes": "First live trade - reduced size for safety"
  }
}
```

### Monitor Live Trading

**Critical Monitoring** (first 24 hours):

1. **Watch Every Signal**:
   - Activity page → Signals tab
   - Verify each signal executes as expected
   - Check execution prices vs expected

2. **IBKR TWS**:
   - Keep TWS open with **live account**
   - Monitor positions, orders, executions
   - Set up alerts for:
     - Order rejections
     - Margin warnings
     - Large slippage

3. **Dashboard Alerts**:
   - Enable email/SMS alerts for:
     - Failed orders
     - Position limits exceeded
     - Daily loss limit hit
     - Service errors

4. **Service Health**:
   ```bash
   # Monitor logs continuously
   docker logs -f mathematricks-trader-execution-1
   docker logs -f mathematricks-trader-cerebro-1
   docker logs -f mathematricks-trader-account-data-1
   ```

5. **Database Checks**:
   ```bash
   # Verify signal processing
   docker exec -it mathematricks-trader-mongodb-1 mongosh --port 27018
   
   use mathematricks_trading
   
   # Check latest signals
   db.signal_store.find({strategy_id: "FloridaForex_Developer"}).sort({timestamp: -1}).limit(5)
   
   # Check orders
   db.trading_orders.find({strategy_id: "FloridaForex_Developer"}).sort({created_at: -1}).limit(5)
   ```

### Gradual Scaling

**Week 1**: 10% of target position size
**Week 2**: 25% of target position size  
**Week 3**: 50% of target position size  
**Week 4**: 75% of target position size  
**Week 5+**: 100% of target position size (if all metrics good)

Update position sizes by editing signals or using the **Strategy Settings** → **Position Sizing** multiplier.

### Emergency Stop

If anything goes wrong:

**Immediate Stop**:
```bash
# Stop execution service (prevents new orders)
docker stop mathematricks-trader-execution-1

# Or pause strategy
# In frontend: Strategies page → Edit → Status: INACTIVE
```

**Close All Positions**:
```bash
# Send flatten signal
python tests/send_flatten_signal.py --strategy FloridaForex_Developer --mode live_live
```

**Disable Live Trading**:
```bash
# Edit .env
ALLOW_LIVE_TRADING=false

# Restart services
docker-compose restart
```

### Success Criteria ✅
- All signals execute as expected
- Fills at reasonable prices (low slippage)
- Positions match between system and IBKR
- Account balances accurate
- P&L tracking matches IBKR
- No service errors for 7+ days
- Risk limits respected
- Developer happy with results 🎉

---

## 🔧 Troubleshooting

### Common Issues

#### Issue: Strategy Not Appearing in Allocation Research Lab

**Cause**: Strategy status is not `ACTIVE` or `include_in_optimization` is false.

**Fix**:
1. Go to "Strategies" page
2. Find your strategy
3. Edit:
   - **Status**: Set to `ACTIVE`
   - **Include in Optimization**: Toggle ON (checkmark)
4. Save

#### Issue: Account Client ID Conflict

**Error**: `Client ID 1 already in use`

**Cause**: Another account or service is using the same client_id.

**Fix**:
1. Go to "Accounts" page
2. Edit your account
3. Update client IDs to unused values:
   - **Execution Client ID**: 1-99 range (e.g., 5)
   - **Account Data Client ID**: 100-199 range (e.g., 105)
4. Restart execution service:
   ```bash
   docker restart mathematricks-trader-execution-1
   docker restart mathematricks-trader-account-data-1
   ```

#### Issue: Orders Not Executing in Paper_Live

**Cause**: IB Gateway not connected or wrong port.

**Check**:
```bash
# Verify gateway running
docker ps | grep ibgateway

# Test connection
python test_local_ibgateway.py --mode paper

# Check logs
docker logs ibgateway-paper --tail 50
```

**Fix**:
```bash
# Restart gateway
docker restart ibgateway-paper

# Or start if not running
make start-ibgateway-paper
```

#### Issue: Forex Residuals Not Converting to CAD

**Cause**: Base currency mismatch or residual handler not running.

**Fix**:
1. Verify strategy `base_currency` matches fund and account currency (all `CAD`)
2. Check residual handler logs:
   ```bash
   docker logs mathematricks-trader-execution-1 | grep RESIDUAL
   ```
3. Ensure IBKR account has CAD as base currency in TWS

#### Issue: Allocation Not Updating After Approval

**Cause**: Cache not invalidated or wrong fund selected.

**Fix**:
1. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
2. Verify in MongoDB:
   ```bash
   docker exec -it mathematricks-trader-mongodb-1 mongosh --port 27018
   use mathematricks_trading
   db.funds.findOne({fund_id: "forex-developer-fund"}, {approved_allocation: 1})
   ```
3. If still wrong, re-approve from Allocations page

---

## 📚 Reference Links

### Documentation
- [README.md](../../README.md) - System architecture overview
- [4-Mode Trading System](../../README.md#-4-mode-trading-system) - Mode details
- [MongoDB Schemas](../mongodb_schemas.md) - Database structure
- [IBKR Integration](../IBKR_INTEGRATION_SUMMARY.md) - Broker setup

### Frontend Pages
- **Dashboard** (`/`) - Portfolio metrics, P&L, positions
- **Strategies** (`/strategies`) - CRUD for strategies
- **Fresh Strategies** (`/strategy-approval`) - Upload and approve backtest
- **Accounts** (`/accounts`) - Trading account management
- **Allocations** (`/allocations`) - Portfolio allocation workflow
- **Activity** (`/activity`) - Signals, orders, executions

### API Endpoints
- **Signal Receiver**: `http://localhost:3000/api/signals` (POST)
- **Account Data API**: `http://localhost:8002/api/v1/`
- **Cerebro API**: `http://localhost:8082/api/v1/`
- **Execution API**: `http://localhost:8083/api/v1/`

### Service Logs
```bash
# All services
docker-compose logs -f

# Individual services
docker logs -f mathematricks-trader-signal-ingestion-1
docker logs -f mathematricks-trader-cerebro-1
docker logs -f mathematricks-trader-execution-1
docker logs -f mathematricks-trader-account-data-1
```

---

## ✅ Summary Checklist

Use this checklist to track your progress:

- [ ] **Step 1**: Strategy uploaded and approved in "Fresh Strategies"
- [ ] **Step 2**: Fund created (new or existing identified)
- [ ] **Step 3**: Trading account configured with correct client IDs
- [ ] **Step 4**: Portfolio allocation test run in Research Lab
- [ ] **Step 5**: Allocation approved and visible in Current Allocation
- [ ] **Step 6**: Mock_mock test passed (signal flow verified)
- [ ] **Step 7**: Mock_live test passed (live data working)
- [ ] **Step 8**: Paper_live running for 3-7 days successfully
- [ ] **Step 9**: Live_live enabled with gradual scaling plan

---

## 🎉 Congratulations!

You've successfully added a new strategy to the Mathematricks trading system. Your strategy is now:

- ✅ Configured in the database
- ✅ Allocated capital from fund(s)
- ✅ Connected to broker account(s)
- ✅ Tested through all 4 modes
- ✅ Running in production (if you reached Step 9)

**Next Steps**:
- Monitor performance on Dashboard
- Adjust allocations as needed
- Add more strategies to diversify
- Review tearsheets weekly

**Questions?** Check the [documentation](../../README.md) or contact the development team.

---

*Last Updated: 2024-01-15*  
*Version: 1.0*
