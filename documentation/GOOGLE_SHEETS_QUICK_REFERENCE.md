# Google Sheets Strategy - Quick Reference

**Quick setup guide for strategy developers using Google Sheets**

---

## 📋 Prerequisites

- [ ] Google Sheet with signal data
- [ ] Mathematricks account / API access
- [ ] Passphrase from Mathematricks team

---

## 🚀 5-Minute Setup

### 1. Copy Script

1. Open your Google Sheet
2. **Extensions** → **Apps Script**
3. Copy code from: `mathematricks-trader/signal-senders/GoogleSheets_Strategy_Template.js`
4. Paste into Apps Script editor
5. **Save** (Ctrl+S)

### 2. Set Properties

**Project Settings** (⚙️) → **Script Properties** → **Add property**:

| Key | Value | Example |
|-----|-------|---------|
| `passphrase` | Your passphrase | `my_secret_passphrase_123` |
| `strategy_name` | Your strategy name | `MyForexStrategy` |
| `api_url` | API endpoint | `https://staging.mathematricks.fund/api/v1/signals` |
| `instrument_type` | Asset type | `FOREX` (or STOCK, OPTION, etc.) |
| `base_currency` | Base currency | `CAD` (or USD, EUR, etc.) |
| `order_type` | Order type | `MARKET` |

### 3. Set Up Sheet

**Sheet name:** `SignalController`

**Required columns:**

| A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| Pair ID | Is On? | Symbol | Model Pos | Last Known | Signal Status | Action | Qty | Actual Pos | Last Update |

**Configuration cells (top of sheet):**

| Cell | Value | Description |
|------|-------|-------------|
| C3 | 100000 | Account equity |
| E1 | staging | Environment (staging or production) |
| E2 | paper_live | Mode (mock_mock, mock_live, paper_live, live_live) |

### 4. Create Triggers

**Apps Script** → **Triggers** (⏰):

**Trigger 1:**
- Function: `captureOnChange`
- Event: From spreadsheet → On change

**Trigger 2:**
- Function: `whenToTrigger`
- Event: Time-driven → Minutes timer → Every 1 minute

### 5. Test

1. Set `Is On?` = 1 for a symbol
2. Set `Model Position` = 100 (or any value)
3. Wait 5 minutes (or run manually: **Apps Script** → **Run** → `runNow`)
4. Check `Signal Status` column - should say "Sent"

---

## 📊 Sheet Structure

### Example Data

| Pair ID | Is On? | Symbol | Model Pos | Last Known | Signal Status | Action | Qty | Actual Pos | Last Update |
|---------|--------|--------|-----------|------------|---------------|--------|-----|------------|-------------|
| AAPL-01 | 1 | AAPL | 100 | 0 | Sent (2024-02-02) | BUY | 100 | 100 | 2024-02-02 |
| SPY-02 | 1 | SPY | -50 | 0 | Sent (2024-02-02) | SELL | 50 | -50 | 2024-02-02 |
| TSLA-03 | 0 | TSLA | 0 | 0 | Disabled | - | - | 0 | - |

**Column Meanings:**
- **Is On?**: 1 = enabled, 0 = disabled
- **Model Position**: Desired position from your strategy
- **Last Known**: Previous model position (prevents duplicate signals)
- **Actual Position**: Real position at broker (auto-updated from API)

---

## 🔧 How It Works

### Signal Generation Logic

```
1. Every 1 minute, script checks if 5 minutes passed since last sheet change
2. For each row:
   - If "Is On?" = 0 → Skip
   - If Model Position = Actual Position → Skip (no change needed)
   - If already sent signal for this Model Position → Skip (no duplicate)
   - Otherwise:
     → Calculate: Action (BUY/SELL), Quantity (Model - Actual)
     → Send signal to Mathematricks API
     → Log to SignalHistory sheet
```

### Signal Types

| Scenario | Signal Type |
|----------|-------------|
| Model = 100, Actual = 0 | ENTRY (BUY 100) |
| Model = 0, Actual = 100 | EXIT (SELL 100) |
| Model = 150, Actual = 100 | SCALE_IN (BUY 50) |
| Model = 50, Actual = 100 | SCALE_OUT (SELL 50) |

### Forex: Automatic Cleanup

For forex strategies, on EXIT signals:
```
Original Signal: EXIT JPY/CHF 25,000

Auto-generated cleanup:
  1. SELL JPY/CAD 25,000 (convert JPY to base currency)
  2. SELL CHF/CAD 25,000 (convert CHF to base currency)

Result: All balances in base currency (CAD)
```

---

## 🎯 Trading Modes

| Mode | Testing Level | Gateway | Real Money? |
|------|---------------|---------|-------------|
| `mock_mock` | Development | No | No |
| `mock_live` | Strategy testing | Yes | No |
| `paper_live` | Paper trading | Yes | No (simulated) |
| `live_live` | Production | Yes | **YES - REAL MONEY** |

**Recommended progression:**
1. Start with `paper_live` for 1-2 weeks
2. Monitor performance, verify cleanup signals
3. When confident, switch to `live_live`

**How to switch modes:**
- Change cell **E2** from `paper_live` to `live_live`
- Contact Mathematricks team to update backend configuration

---

## 📋 Manual Functions

Run from **Apps Script** → **Run**:

| Function | Purpose |
|----------|---------|
| `runNow()` | Send signals immediately (don't wait 5 min) |
| `refreshPositions()` | Update Actual Position column from broker |
| `clearHistory()` | Clear SignalHistory sheet (testing only) |

---

## 🐛 Troubleshooting

### Signal Not Sending

**Check:**
1. **Is On?** column = 1 (not 0)
2. **Model Position** ≠ **Actual Position**
3. No recent signal for same Model Position (check SignalHistory)
4. Script Properties set correctly (passphrase, strategy_name, api_url)
5. Triggers enabled (⏰ icon in Apps Script)

**View Logs:**
- Apps Script → **View** → **Logs**

### Signal Rejected

**Common reasons:**
- Invalid passphrase → Check Script Properties
- Strategy not configured in Mathematricks system → Contact team
- Insufficient margin → Reduce position size
- Market closed → Check market hours

**Check response:**
- Look at **Signal Status** column for error message
- View **SignalHistory** sheet → **Ack Message** column

### Positions Not Updating

**Actual Position** column should update from broker API.

**If not updating:**
- Position tracking endpoint may not be enabled yet
- Contact Mathematricks team to enable

**Workaround:**
- Manually update **Actual Position** column from your broker dashboard

---

## 📞 Support

**Contact Mathematricks team if:**
- Passphrase not working
- Signals not appearing in system
- Need to change trading mode
- Questions about cleanup signals
- Emergency position closure needed

**Provide:**
- Strategy name
- Signal ID (from SignalHistory sheet)
- Error message (from Signal Status or Ack Message)
- Timestamp of issue

---

## ⚠️ Safety Guidelines

### Before Going Live

- [ ] Test in `paper_live` mode for at least 1-2 weeks
- [ ] Verify signals processing correctly
- [ ] Check cleanup signals executing (for forex)
- [ ] Confirm position sizes appropriate
- [ ] Set stop-loss limits in strategy
- [ ] Understand emergency stop procedure

### Emergency Stop

**Immediate action:**
1. Set **Is On?** = 0 for ALL symbols
2. Contact Mathematricks team: "EMERGENCY STOP - [Your Strategy Name]"

**To close all positions:**
1. Set **Model Position** = 0 for all symbols
2. Wait for EXIT signals to process
3. Verify positions closed

### Live Trading Checklist

- [ ] Tested thoroughly in paper mode
- [ ] Understand risk management
- [ ] Know how to stop trading
- [ ] Team contact information saved
- [ ] Position limits configured
- [ ] Market hours understood
- [ ] Cleanup signals tested (forex only)

---

## 📚 Additional Resources

**Full Documentation:**
- Setup Guide: `documentation/DEVELOPER_FOREX_STRATEGY_SETUP.md`
- Forex Residuals: `documentation/brokers/FOREX_RESIDUALS_GUIDE.md`
- Complete Script: `signal-senders/GoogleSheets_Strategy_Template.js`

**Admin Dashboard:**
- URL provided by Mathematricks team
- View signals, positions, P&L

---

**🎯 Goal:** Automate your trading strategy from Google Sheets with institutional-grade execution and risk management.

**🛡️ Safety:** Always test in paper mode first. Start small in live mode. Monitor closely.

**📈 Success:** Your signals → Mathematricks system → IBKR execution → Automated trading
