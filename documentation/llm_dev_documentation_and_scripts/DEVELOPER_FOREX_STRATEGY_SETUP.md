# Developer Forex Strategy Setup Guide

Complete guide to set up your developer's Google Sheets forex strategy in the Mathematricks trading system.

## Overview

Your developer provides forex signals via Google Sheets → Google Apps Script → Your signal receiver. The system will:

1. Receive signals from Google Sheets
2. Process through your 4-mode pipeline
3. Execute on IBKR (paper first, then live)
4. Handle forex residuals automatically (convert to CAD base currency)

## Prerequisites

- ✅ MongoDB running (port 27018)
- ✅ Docker services running (`make start-dev`)
- ✅ IB Gateway connected (for paper_live/live_live modes)
- ✅ Google Sheet with strategy signals
- ✅ CAD base currency IBKR account

## Phase 1: Setup Infrastructure

### Step 1: Create Fund

Connect to MongoDB and create a fund for this strategy:

```bash
# Connect to MongoDB
docker exec -it mathematricks-trader-mongodb-1 mongosh --port 27018

# Switch to database
use mathematricks_trading
```

```javascript
// Create fund with 100% allocation to forex strategy
db.funds.insertOne({
  fund_id: "forex-developer-fund",
  name: "Developer Forex Strategy Fund",
  description: "Google Sheets forex strategy fund",
  total_equity: 100000,  // Starting capital
  currency: "CAD",       // Base currency for IBKR account
  accounts: ["FOREX-DEV-ACCOUNT"],
  status: "ACTIVE",
  
  // 100% allocation to this strategy
  approved_allocation: {
    portfolio_test_id: "forex_dev_allocation",
    allocations: {
      "FloridaForex_Developer": 100.0  // 100% allocation
    },
    approved_at: new Date(),
    approved_by: "setup_script",
    notes: "Google Sheets forex strategy - 100% allocation"
  },
  
  created_at: new Date(),
  updated_at: new Date()
})
```

**Verify:**
```javascript
db.funds.findOne({fund_id: "forex-developer-fund"})
```

### Step 2: Create Strategy

```javascript
// Create strategy configuration
db.strategies.insertOne({
  strategy_id: "FloridaForex_Developer",
  strategy_name: "Developer Forex Strategy (Google Sheets)",
  description: "Forex trading strategy managed via Google Sheets",
  asset_class: "forex",
  status: "ACTIVE",
  trading_mode: "PAPER",  // Start in PAPER mode
  
  // Mode-aware accounts (v5 schema)
  accounts: {
    mock: ["FOREX-DEV-ACCOUNT"],      // For mock_mock, mock_live
    paper: ["FOREX-DEV-ACCOUNT"],     // For paper_live
    live: ["FOREX-DEV-ACCOUNT"]       // For live_live (later)
  },
  
  // Strategy metadata
  developer: "Your Developer Name",
  signal_source: "Google Sheets",
  instrument_type: "FOREX",
  base_currency: "CAD",
  
  created_at: new Date(),
  updated_at: new Date()
})
```

**Verify:**
```javascript
db.strategies.findOne({strategy_id: "FloridaForex_Developer"})
```

### Step 3: Create Trading Account

```javascript
// Create trading account (paper mode first)
db.trading_accounts.insertOne({
  account_id: "FOREX-DEV-ACCOUNT",
  fund_id: "forex-developer-fund",
  broker: "IBKR",
  broker_account_number: "DU1234567",  // Your IBKR paper account
  
  account_name: "Forex Developer Paper Account",
  account_number: "DU1234567",
  account_type: "paper",
  mode: ["paper_live"],  // Start with paper trading
  
  asset_classes: {
    forex: ["all"]  // Allow all forex pairs
  },
  
  authentication_details: {
    auth_type: "IBKR",
    host: "127.0.0.1",
    port: 4004,  // Paper trading port
    client_id: 1,
    ibkr_client_id: 1,
    ibkr_host: "ib-gateway-ibkr-testing-account",
    ibkr_port: 4004
  },
  
  balances: {
    account_id: "FOREX-DEV-ACCOUNT",
    equity: 100000,
    cash_balance: 100000,
    margin_used: 0,
    margin_available: 100000,
    buying_power: 100000,
    currency: "CAD",
    last_updated: new Date()
  },
  
  open_positions: [],
  status: "ACTIVE",
  
  created_at: new Date(),
  updated_at: new Date()
})
```

**Verify:**
```javascript
db.trading_accounts.findOne({account_id: "FOREX-DEV-ACCOUNT"})
```

### Step 4: Verify Setup

```javascript
// Check fund → strategy → account linkage

// 1. Fund has correct allocation
db.funds.findOne(
  {fund_id: "forex-developer-fund"},
  {"approved_allocation.allocations": 1, accounts: 1}
)
// Expected: FloridaForex_Developer: 100.0, accounts: ["FOREX-DEV-ACCOUNT"]

// 2. Strategy has correct account
db.strategies.findOne(
  {strategy_id: "FloridaForex_Developer"},
  {accounts: 1}
)
// Expected: accounts.paper: ["FOREX-DEV-ACCOUNT"]

// 3. Account is linked to fund
db.trading_accounts.findOne(
  {account_id: "FOREX-DEV-ACCOUNT"},
  {fund_id: 1, account_type: 1, mode: 1}
)
// Expected: fund_id: "forex-developer-fund", account_type: "paper", mode: ["paper_live"]
```

## Phase 2: Configure Google Apps Script

### Step 1: Add Script to Google Sheet

1. Open your developer's Google Sheet
2. Extensions → Apps Script
3. Copy the template from: `mathematricks-trader/signal-senders/GoogleSheets_Strategy_Template.js`
4. Paste into Apps Script editor

### Step 2: Set Script Properties

Project Settings → Script Properties → Add properties:

| Property | Value |
|----------|-------|
| `passphrase` | `your_secure_passphrase_here` |
| `strategy_name` | `FloridaForex_Developer` |
| `api_url` | `https://staging.mathematricks.fund/api/v1/signals` |
| `instrument_type` | `FOREX` |
| `base_currency` | `CAD` |
| `order_type` | `MARKET` |

### Step 3: Add Passphrase to Signal Receiver

Add your passphrase to the signal receiver:

**File:** `mathematricks-trader/docker-compose.yml`

```yaml
signal-receiver:
  environment:
    - WEBHOOK_PASSPHRASES=yahoo123,your_secure_passphrase_here
```

Restart signal receiver:
```bash
docker-compose restart signal-receiver
```

### Step 4: Configure Sheet Cells

In your "SignalController" sheet:

| Cell | Value | Description |
|------|-------|-------------|
| C3 | 100000 | Account equity (matches trading_accounts) |
| E1 | staging | Trading mode (staging/production) |
| E2 | paper_live | Environment (mock_mock/mock_live/paper_live/live_live) |

### Step 5: Set Up Triggers

Apps Script → Triggers (⏰ icon):

**Trigger 1: onChange**
- Function: `captureOnChange`
- Event source: From spreadsheet
- Event type: On change
- Purpose: Captures sheet changes

**Trigger 2: Time-driven**
- Function: `whenToTrigger`
- Event source: Time-driven
- Type: Minutes timer
- Every: 1 minute
- Purpose: Processes signals 5 min after changes

## Phase 3: Test Paper Trading (paper_live)

### Test Sequence

**1. Test Signal Flow**

In Google Sheet, update a signal:
- Set Model Position = 25000 for JPY/CHF
- Wait 5 minutes for auto-trigger
- OR manually run: Apps Script → Run → `runNow()`

**2. Monitor Signal Flow**

```bash
# Watch signal receiver
docker logs mathematricks-trader-signal-receiver-1 -f

# Watch signal ingestion
docker logs mathematricks-trader-signal-ingestion-1 -f

# Watch cerebro processing
docker logs mathematricks-trader-cerebro-service-1 -f

# Watch execution
docker logs mathematricks-trader-execution-service-1 -f
```

**3. Check MongoDB**

```javascript
// Check raw signal
db.trading_signals_raw.find({
  strategy_name: "FloridaForex_Developer"
}).sort({received_at: -1}).limit(1)

// Check processed signal
db.signal_store.find({
  strategy_id: "FloridaForex_Developer"
}).sort({created_at: -1}).limit(1).pretty()

// Check decision
db.signal_store.findOne(
  {strategy_id: "FloridaForex_Developer"},
  {"legs.decision": 1}
)

// Check execution
db.signal_store.findOne(
  {strategy_id: "FloridaForex_Developer"},
  {"legs.execution": 1}
)
```

**4. Verify IBKR Paper Account**

```bash
# Check positions in IBKR
python scripts/llm_dev_scripts/close_ibkr_positions.py --port 4004
```

**5. Test EXIT with Residual Cleanup**

In Google Sheet:
- Set Model Position = 0 for JPY/CHF (exit)
- Wait for auto-trigger

Expected: 3 signals sent:
1. EXIT JPY/CHF 25000 (main exit)
2. CLEANUP JPY/CAD 25000 (convert JPY → CAD)
3. CLEANUP CHF/CAD 25000 (convert CHF → CAD)

Verify in signal history:
```javascript
db.signal_store.find({
  strategy_id: "FloridaForex_Developer",
  "legs.leg_type": "CLEANUP"
}).pretty()
```

## Phase 4: Monitor Paper Trading

### Run for 1-2 Weeks

Monitor daily:

**1. Check Account Balances**
```javascript
db.trading_accounts.findOne(
  {account_id: "FOREX-DEV-ACCOUNT"},
  {balances: 1, open_positions: 1}
)
```

**2. Check Currency Residuals**

Goal: All balances should be in CAD after cleanup signals

```javascript
// Check for non-CAD balances (should be near 0)
db.trading_accounts.aggregate([
  {$match: {account_id: "FOREX-DEV-ACCOUNT"}},
  {$project: {
    "balances.currency_balances": 1
  }}
])
```

**3. Review Signal Performance**

```javascript
// Count signals by type
db.signal_store.aggregate([
  {$match: {strategy_id: "FloridaForex_Developer"}},
  {$unwind: "$legs"},
  {$group: {
    _id: "$legs.leg_type",
    count: {$sum: 1},
    total_pnl: {$sum: "$position.pnl.gross"}
  }}
])
```

**4. Admin Dashboard**

View in browser: http://localhost:5173
- Signals tab → Filter by strategy
- Positions tab → Current positions
- Accounts tab → Account balance

### Key Metrics to Track

✅ **Signal Success Rate**: >95% signals should be APPROVED  
✅ **Execution Success Rate**: >99% orders should be FILLED  
✅ **Cleanup Success Rate**: 100% cleanup signals should execute  
✅ **Currency Balances**: CAD balance stable, other currencies near 0  
✅ **P&L Tracking**: Position P&L matches expected  

## Phase 5: Move to Live Trading (live_live)

⚠️ **ONLY AFTER 1-2 WEEKS OF SUCCESSFUL PAPER TRADING**

### Checklist Before Going Live

- [ ] Tested in paper_live for at least 2 weeks
- [ ] No signal processing errors
- [ ] Currency cleanup working correctly
- [ ] P&L tracking accurate
- [ ] Developer confirms strategy is working
- [ ] Risk limits configured
- [ ] Emergency stop procedure documented

### Step 1: Update Google Apps Script

Change environment mode:
```javascript
// In SignalController sheet
E1: production  (was: staging)
E2: live_live   (was: paper_live)
```

### Step 2: Update Trading Account

```javascript
// Update account to live mode
db.trading_accounts.updateOne(
  {account_id: "FOREX-DEV-ACCOUNT"},
  {
    $set: {
      account_type: "live",
      mode: ["live_live"],
      broker_account_number: "U1234567",  // Your LIVE account (starts with U)
      "authentication_details.port": 4001,  // Live port
      "authentication_details.ibkr_port": 4001
    }
  }
)
```

### Step 3: Update Strategy Accounts

```javascript
// Update strategy to use live account
db.strategies.updateOne(
  {strategy_id: "FloridaForex_Developer"},
  {
    $set: {
      trading_mode: "LIVE",
      "accounts.live": ["FOREX-DEV-ACCOUNT"]
    }
  }
)
```

### Step 4: Verify IB Gateway on Live Port

```bash
# Check IB Gateway is on port 4001 (LIVE)
docker port ib-gateway-ibkr-testing-account 4001

# Test connection
python scripts/llm_dev_scripts/close_ibkr_positions.py --port 4001
```

### Step 5: Test with Small Position

1. Send 1 small test signal in live mode
2. Monitor execution carefully
3. Verify fill in IBKR account
4. Close position manually if needed

### Step 6: Monitor Closely

```bash
# Real-time logs
docker logs mathematricks-trader-execution-service-1 -f | grep "live_live"

# Check every trade
db.signal_store.find({
  strategy_id: "FloridaForex_Developer",
  mode: "live_live"
}).sort({created_at: -1})
```

## Emergency Procedures

### Stop All Trading

**1. Disable Strategy in Google Sheet:**
- Set "Is On?" column to 0 for all pairs

**2. Pause Strategy in MongoDB:**
```javascript
db.strategies.updateOne(
  {strategy_id: "FloridaForex_Developer"},
  {$set: {status: "PAUSED"}}
)
```

**3. Close All Positions:**
```bash
# Paper account
python scripts/llm_dev_scripts/close_ibkr_positions.py --port 4004

# Live account (use with caution!)
python scripts/llm_dev_scripts/close_ibkr_positions.py --port 4001
```

### Rollback to Paper Trading

```javascript
// 1. Update account
db.trading_accounts.updateOne(
  {account_id: "FOREX-DEV-ACCOUNT"},
  {
    $set: {
      account_type: "paper",
      mode: ["paper_live"],
      "authentication_details.port": 4004,
      "authentication_details.ibkr_port": 4004
    }
  }
)

// 2. Update strategy
db.strategies.updateOne(
  {strategy_id: "FloridaForex_Developer"},
  {
    $set: {
      trading_mode: "PAPER",
      "accounts.live": []
    }
  }
)

// 3. Update Google Sheet
// E1: staging
// E2: paper_live
```

## Monitoring Dashboard

### Daily Checks

**1. Currency Balances:**
```javascript
db.trading_accounts.findOne(
  {account_id: "FOREX-DEV-ACCOUNT"},
  {"balances.currency_balances": 1}
)
```

**2. Open Positions:**
```javascript
db.trading_accounts.findOne(
  {account_id: "FOREX-DEV-ACCOUNT"},
  {open_positions: 1}
)
```

**3. Recent Signals:**
```javascript
db.signal_store.find({
  strategy_id: "FloridaForex_Developer",
  created_at: {$gte: new Date(Date.now() - 24*60*60*1000)}
}).count()
```

**4. Failed Signals:**
```javascript
db.signal_store.find({
  strategy_id: "FloridaForex_Developer",
  "legs.decision.status": "REJECTED"
}).sort({created_at: -1}).limit(5)
```

## Troubleshooting

### Signal Not Processing

**Check signal receiver:**
```bash
docker logs mathematricks-trader-signal-receiver-1 --tail 100
```

**Verify passphrase:**
```javascript
db.trading_signals_raw.findOne({
  strategy_name: "FloridaForex_Developer"
}, {passphrase: 1})
// Should match your Script Property
```

### Cleanup Signals Not Executing

**Check signal history:**
```javascript
db.signal_store.find({
  strategy_id: "FloridaForex_Developer",
  "legs.leg_type": "CLEANUP"
}).pretty()
```

**Verify cleanup logic:**
Check Google Apps Script logs (View → Logs)

### Position Mismatch

**Compare model vs actual:**
```bash
# Get actual positions from IBKR
python scripts/check_positions.py --account FOREX-DEV-ACCOUNT

# Get model positions from sheet
# (check Google Sheet SignalController)
```

### IBKR Connection Issues

**Check IB Gateway:**
```bash
docker ps | grep ib-gateway
docker logs ib-gateway-ibkr-testing-account
```

**Test connection:**
```python
python scripts/test_ibkr_connection.py --port 4004
```

## Summary

### Setup Checklist

- [x] MongoDB collections created (fund, strategy, account)
- [x] Google Apps Script configured
- [x] Passphrase added to signal receiver
- [x] Triggers set up in Google Sheet
- [x] Paper trading tested (1-2 weeks)
- [ ] Live trading configured (after successful paper testing)

### Key Files

- **Google Apps Script:** `signal-senders/GoogleSheets_Strategy_Template.js`
- **Forex Residuals Guide:** `documentation/brokers/FOREX_RESIDUALS_GUIDE.md`
- **Close Positions Script:** `scripts/llm_dev_scripts/close_ibkr_positions.py`

### Support

- **Logs:** `make logs` or `docker-compose logs -f [service]`
- **Admin Dashboard:** http://localhost:5173
- **MongoDB:** `docker exec -it mathematricks-trader-mongodb-1 mongosh --port 27018`

---

**🎯 Goal**: Run in `paper_live` mode for 1-2 weeks, then transition to `live_live` mode for production trading.
