# IBKR Testing Completion Guide

**Date:** 2026-01-17  
**Status:** Ready for Final Testing

---

## What We Just Fixed

### Issue
MongoDB account configuration kept reverting from `broker: "IBKR"` back to `broker: "Mock"` when services restarted.

### Root Cause
Mock broker's `_ensure_account_exists()` method overwrote the account config every time it connected, including when used as a secondary broker in `mock_live` mode (real IBKR data + mock fills).

### Solution
Added `read_only` mode to Mock broker:
- When `read_only=True`, Mock broker skips MongoDB writes
- Applied to all hybrid mode setups (`mock_live`/`paper_real`)
- IBKR config now persists across restarts

### Files Changed
1. `services/brokers/mock/mock_broker.py` - Added read_only flag
2. `services/execution_service/execution_main.py` - Use read-only mock in paper_real mode
3. `services/account_data_service/broker_poller.py` - Use read-only mock in paper_real mode

---

## Testing Checklist

### Step 1: Verify MongoDB Config Persists

```bash
# Set IBKR config in MongoDB
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval '
db.trading_accounts.updateOne(
  {account_id: "IBKR-TESTING-ACCOUNT"},
  {$set: {
    broker: "IBKR",
    mode: "paper_real",
    authentication_details: {
      auth_type: "IBKR",
      host: "host.docker.internal",
      port: 4002,
      client_id: 1,
      initial_equity: 1000000
    }
  }}
)'

# Restart all services
docker restart mathematricks-trader-execution-service-1 \
               mathematricks-trader-account-data-service-1

# Wait 5 seconds
sleep 5

# Verify config persisted (should still show broker: "IBKR")
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval '
db.trading_accounts.findOne(
  {account_id: "IBKR-TESTING-ACCOUNT"}, 
  {broker: 1, mode: 1, _id: 0}
)'
```

**Expected Output:**
```json
{ broker: 'IBKR', mode: 'paper_real' }
```

✅ **Pass Criteria:** Broker field stays as "IBKR" after restart

---

### Step 2: Verify IBKR Connection in Logs

```bash
# Check execution-service logs for IBKR broker initialization
docker logs mathematricks-trader-execution-service-1 2>&1 | \
  grep -E "Initialized IBKR broker|read-only mode|Connected to IBKR_Adapter" | tail -10
```

**Expected Output:**
```
Initialized IBKR broker: host.docker.internal:4002 (client_id=1)
Mock Broker initialized for account IBKR-TESTING-ACCOUNT (read-only mode - no MongoDB writes)
✅ Connected to IBKR_Adapter for IBKR-TESTING-ACCOUNT
```

✅ **Pass Criteria:**
- IBKR broker shows `host.docker.internal:4002`
- Mock broker shows "read-only mode"
- Connected to IBKR_Adapter (not Mock_Adapter)

---

### Step 3: Test End-to-End Signal Flow (mock_live mode)

```bash
# Send 1 test signal
.venv/bin/python tests/signals_testing/run_full_test.py \
  --folder tests/signals_testing/sample_signals_ibkr \
  --signal_count 1 \
  --delay 5
```

**Check execution logs for real IBKR price:**
```bash
docker logs mathematricks-trader-execution-service-1 2>&1 | tail -30 | \
  grep -E "\[paper_real\] Order enriched with real price"
```

**Expected Output:**
```
[paper_real] Order enriched with real price: 230.5
```

✅ **Pass Criteria:**
- Price is realistic (AAPL ~$230, not 100.0)
- Log shows `[paper_real]` or `[mock_live]` mode
- Order filled instantly (mock execution)
- Check IB Gateway VNC: NO orders should appear (fills are mock)

---

### Step 4: Test paper_live Mode (Real IBKR Orders)

**⚠️ WARNING:** This sends REAL orders to IBKR paper trading account!

```bash
# Switch to paper_live mode
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval '
db.trading_accounts.updateOne(
  {account_id: "IBKR-TESTING-ACCOUNT"},
  {$set: {mode: "paper_live"}}
)'

# Restart execution-service to reload config
docker restart mathematricks-trader-execution-service-1
sleep 5

# Send 1 test signal
.venv/bin/python tests/signals_testing/run_full_test.py \
  --folder tests/signals_testing/sample_signals_ibkr \
  --signal_count 1 \
  --delay 5
```

**Verify in IB Gateway (VNC):**
- Open VNC Viewer → localhost:5900 (password: ibgateway)
- Check "Orders" tab → Should see the order
- Check "Positions" tab → Should show position after fill

✅ **Pass Criteria:**
- Order appears in IB Gateway
- Position appears after fill
- Execution logs show real fills (not instant)

---

### Step 5: Run Broker Unit Tests

```bash
# Test IBKR broker library directly (requires IB Gateway running)
.venv/bin/python services/brokers/test_ibkr_integration.py
```

**Expected Output:**
```
1. Creating IBKR broker instance... ✓
2. Connecting to IBKR TWS... ✓
3. Verifying connection status... ✓
4. Fetching account balance... ✓
5. Fetching margin information... ✓
6. Fetching open positions... ✓
7. Fetching open orders... ✓
8. Testing order placement... ✓
9. Checking order status... ✓
10. Cancelling test order... ✓
11. Disconnecting from IBKR... ✓

✅ ALL TESTS PASSED - IBKR BROKER IS PRODUCTION READY
```

✅ **Pass Criteria:** All 11 tests pass

---

## Mode Reference

### Current System (After Fix)

| Mode | Market Data | Execution | MongoDB Writes | Use Case |
|------|-------------|-----------|----------------|----------|
| `mock` | Mock/simulated | Mock (instant) | ✅ Yes | Pure testing, no external dependencies |
| `paper_real` (mock_live) | Real IBKR | Mock (instant) | ❌ No (read-only) | Strategy testing with real market data, zero risk |
| `live` | Real IBKR | Real IBKR | N/A | Production trading - REAL MONEY |

### Account Configuration

**For mock_live testing (current setup):**
```json
{
  "account_id": "IBKR-TESTING-ACCOUNT",
  "broker": "IBKR",
  "mode": "paper_real",
  "authentication_details": {
    "auth_type": "IBKR",
    "host": "host.docker.internal",
    "port": 4002,
    "client_id": 1,
    "initial_equity": 1000000
  }
}
```

**For paper_live testing (real IBKR paper orders):**
```json
{
  "account_id": "IBKR-TESTING-ACCOUNT",
  "broker": "IBKR",
  "mode": "paper_live",
  "authentication_details": {
    "auth_type": "IBKR",
    "host": "host.docker.internal",
    "port": 4002,
    "client_id": 1,
    "initial_equity": 1000000
  }
}
```

---

## Troubleshooting

### Problem: Config still reverting to Mock

**Check 1:** Verify read_only flag is being set
```bash
docker logs mathematricks-trader-execution-service-1 | grep "read-only mode"
```

**Check 2:** Ensure clear_test_data.py isn't running
```bash
ps aux | grep clear_test_data
```

**Fix:** Manually set config again and verify no other processes are writing to MongoDB

---

### Problem: IB Gateway shows "Disconnected"

**Check 1:** Verify execution-service has correct host
```bash
docker logs mathematricks-trader-execution-service-1 | grep "host.docker.internal"
```

**Check 2:** Test connection from inside Docker
```bash
docker exec mathematricks-trader-execution-service-1 nc -zv host.docker.internal 4002
```

**Fix:** If host.docker.internal doesn't work, get your Mac IP:
```bash
ipconfig getifaddr en0  # Get Mac IP
# Update MongoDB with your Mac's actual IP instead of host.docker.internal
```

---

### Problem: Orders not appearing in IB Gateway (paper_live mode)

**Check 1:** Verify mode is paper_live
```bash
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval '
db.trading_accounts.findOne({account_id: "IBKR-TESTING-ACCOUNT"}, {mode: 1})'
```

**Check 2:** Check execution logs for errors
```bash
docker logs mathematricks-trader-execution-service-1 | grep -i error | tail -20
```

**Fix:** Ensure IB Gateway API is enabled (Configuration → API → Enable ActiveX)

---

## Success Criteria Summary

✅ **All systems working when:**

1. MongoDB config persists across service restarts
2. Execution-service connects to IBKR at `host.docker.internal:4002`
3. Mock broker logs show "read-only mode"
4. Signals get real IBKR prices (not 100.0)
5. Mock_live: Orders filled instantly, no IB Gateway orders
6. Paper_live: Orders appear in IB Gateway, real fills
7. Broker unit tests pass all 11 tests

---

## Next Steps (After Testing Complete)

### Immediate
- [ ] Run all 5 testing steps above
- [ ] Document any failures
- [ ] Fix any issues found
- [ ] Re-run tests until all pass

### Future Enhancements (see multi_mode_trading_accounts_redesign.md)
- [ ] Implement 4-mode system: mock, mock_live, paper_live, live
- [ ] Add broker-specific mode support
- [ ] Refactor connection_config schema
- [ ] Update frontend for mode selection
- [ ] Add live mode safeguards

---

## Quick Command Reference

```bash
# View current account config
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval \
  'db.trading_accounts.findOne({account_id: "IBKR-TESTING-ACCOUNT"}, {broker:1, mode:1, authentication_details:1})'

# Set mock_live mode
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval \
  'db.trading_accounts.updateOne({account_id: "IBKR-TESTING-ACCOUNT"}, {$set: {mode: "paper_real", broker: "IBKR"}})'

# Set paper_live mode
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval \
  'db.trading_accounts.updateOne({account_id: "IBKR-TESTING-ACCOUNT"}, {$set: {mode: "paper_live", broker: "IBKR"}})'

# Restart services
docker restart mathematricks-trader-execution-service-1 mathematricks-trader-account-data-service-1

# Check execution logs
docker logs mathematricks-trader-execution-service-1 --tail 50 | grep -E "IBKR|Mock|Connected"

# Send test signal
.venv/bin/python tests/signals_testing/run_full_test.py \
  --folder tests/signals_testing/sample_signals_ibkr --signal_count 1

# Clear test data
.venv/bin/python scripts/junk/clear_test_data.py

# Run broker unit tests
.venv/bin/python services/brokers/test_ibkr_integration.py
```

---

**Status:** Ready for final testing 🚀  
**Last Updated:** 2026-01-17
