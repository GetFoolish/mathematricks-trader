# Live Testing Debug Report

**Date**: October 20, 2025  
**Status**: Issues Identified and Fixed

---

## Investigation Summary

When running `python live_signal_tester.py --interval 10 --count 5`, the test revealed two critical issues preventing the signal flow from completing:

### Issue 1: Services Not Running ❌
**Problem**: No services were listening on required ports (3002, 8001, 8002, 8003)  
**Root Cause**: User had not started `./run_mvp_demo.sh`  
**Status**: User needs to start services

### Issue 2: SignalDecision Type Error ❌ → ✅ FIXED
**Problem**: `TypeError: SignalDecision.__init__() got an unexpected keyword argument 'signal_id'`

**Root Cause**: 
- In `services/cerebro_service/portfolio_constructor/max_hybrid/strategy.py`, the `evaluate_signal()` method was returning `SignalDecision` with incorrect parameters
- Was passing: `signal_id`, `strategy_id`, `action="take"`, `size_pct`, `timestamp`
- Expected params: `action`, `quantity`, `reason`, `allocated_capital`, `margin_required`, `metadata`

**Fix Applied**:
```python
# BEFORE (WRONG):
return SignalDecision(
    signal_id=signal.signal_id,
    strategy_id=strategy_id,
    action="take",
    size_pct=allocation_pct,
    reason=f"MaxHybrid allocation: {allocation_pct:.1f}%",
    timestamp=datetime.now(),
    metadata=metadata
)

# AFTER (CORRECT):
return SignalDecision(
    action="APPROVE",
    quantity=signal.quantity,
    reason=f"MaxHybrid allocation: {allocation_pct:.1f}%",
    allocated_capital=allocated_capital,
    margin_required=estimated_margin,
    metadata=metadata
)
```

### Issue 3: Account Data Service 404 ❌ → ✅ FIXED
**Problem**: `404 Client Error: Not Found for url: http://localhost:8002/api/v1/account/DU1234567/state`

**Root Cause**: 
- Account state collection in MongoDB was empty
- No default test accounts existed
- Service was designed to reject requests for non-existent accounts

**Fix Applied**:
Added automatic test account creation in `services/account_data_service/main.py` startup event:
```python
# Initialize default test accounts if they don't exist
test_accounts = ["DU1234567", "IBKR_Main"]
for account_name in test_accounts:
    existing = account_state_collection.find_one(
        {"account": account_name},
        sort=[("timestamp", -1)]
    )
    
    if not existing:
        logger.info(f"Creating default account state for {account_name}")
        default_state = {
            "account": account_name,
            "equity": 100000.0,  # $100K starting capital
            "cash_balance": 100000.0,
            "margin_used": 0.0,
            "margin_available": 200000.0,  # 2x leverage available
            "timestamp": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "positions": [],
            "open_orders": []
        }
        account_state_collection.insert_one(default_state)
        account_state_cache[account_name] = default_state
```

---

## Signal Flow Analysis

From the logs, we can see the signal flow **was partially working**:

### ✅ What Was Working:
1. **Signal Submission**: Signals successfully sent to `https://staging.mathematricks.fund/api/signals`
   - TLT_20251020_175340_001 ✅
   - Com3-Mkt_20251020_175406_002 ✅

2. **Signal Collection**: `signal_collector.py` was receiving signals from MongoDB

3. **Pub/Sub Delivery**: Signals were being published and received by Cerebro Service

4. **Portfolio Evaluation**: MaxHybrid constructor was running and making decisions:
   ```
   WARNING - No strategy histories available
   INFO - Signal REJECTED: TLT | No allocation
   ```

### ❌ What Was Broken:
1. **SignalDecision Creation**: Crashed when trying to create SignalDecision object with wrong parameters
2. **Decision Storage**: Because of the crash, no decisions were saved to MongoDB
3. **Account State**: Account Data Service couldn't provide account info (404)

---

## Expected Behavior After Fixes

Once services are restarted with fixes:

1. **Account Data Service** will auto-create test accounts `DU1234567` and `IBKR_Main` with $100K equity
2. **Cerebro Service** will successfully create SignalDecision objects with correct parameters
3. **Signal Flow** should complete:
   - Cloud endpoint → MongoDB signals collection
   - signal_collector.py → Pub/Sub
   - Cerebro Service → MaxHybrid evaluation → SignalDecision
   - Decision stored in `cerebro_decisions` collection
   - If APPROVED, sent to Execution Service via Pub/Sub

4. **live_signal_tester.py** should show:
   - ✅ Account state fetched successfully
   - ✅ Cerebro decision found
   - ✅ Complete math breakdown displayed

---

## Additional Observations

### Strategy Histories Issue
The logs show:
```
WARNING - No strategy histories available
INFO - Signal REJECTED: TLT | No allocation
```

This is expected because:
1. MaxHybrid constructor needs historical performance data to optimize portfolio
2. No strategy history in MongoDB yet (first-time run)
3. Without history, optimizer has nothing to work with → allocates 0% to all strategies

**To Fix**: Need to ensure strategies collection in MongoDB has backtest data with equity curves. This was done via `tools/load_strategies_from_folder.py` but may need to be re-run or verified.

---

## Next Steps

1. **Start Services**: Run `./run_mvp_demo.sh` in Terminal 1
2. **Verify Services**: Check all 4 services are running with `./check_services.sh`
3. **Re-run Test**: `python live_signal_tester.py --interval 10 --count 5`
4. **Expected Result**: Full signal flow with complete math displayed
5. **If Still Rejecting**: Check if strategies collection has data with equity curves

---

## Files Modified

1. `services/cerebro_service/portfolio_constructor/max_hybrid/strategy.py`
   - Fixed `evaluate_signal()` return statements (2 locations)
   - Changed to use correct SignalDecision parameters

2. `services/account_data_service/main.py`
   - Added default account initialization in `startup_event()`
   - Creates test accounts DU1234567 and IBKR_Main with $100K equity

---

## Testing Checklist

- [ ] Services start without errors
- [ ] Account state returns 200 (not 404)
- [ ] Cerebro receives and processes signals
- [ ] SignalDecision created successfully (no TypeError)
- [ ] Decisions saved to MongoDB
- [ ] live_signal_tester shows complete flow
- [ ] Math breakdown displays correctly
