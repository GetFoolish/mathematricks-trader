# Frontend Issues - Fix Status

**Date:** 2026-01-09  
**Context:** Fixing frontend display issues after consolidated schema v3 implementation

## Issues Reported by User

1. ❌ Signal Legs showing 0 items
2. ❌ Trading signals showing as 'OPEN' even though balanced/closed  
3. ❌ Exit time not showing
4. ❌ P&L not showing
5. ❌ Need quantity progress bar visualization

## Progress

###✅ Issue 1: Signal Legs API - FIXED
**Problem:** API returned `data` field but frontend expected `signals` field

**Fix Applied:**
- File: `frontend-admin/server/api.js:165`
- Changed: `res.json({ status: 'success', count: signals.length, data: signals })`
- To: `res.json({ status: 'success', count: signals.length, signals })`

**Status:** ✅ COMPLETE - Signal Legs now shows 4 items

### ✅ Issue 2 (Partial): Cerebro Processing EXIT Signals - PARTIAL FIX
**Problems Found:**
1. Cerebro wasn't watching for 'update' operations (only 'insert')
2. Position lookup used wrong schema paths
3. Execution quantity lookup used wrong schema paths

**Fixes Applied:**
1. `cerebro_main.py:2440` - Added 'update' to operationType watch
2. `cerebro_main.py:2451` - Added `full_document='updateLookup'` parameter
3. `cerebro_main.py:906-918` - Updated `find_open_entry_signal()` to query consolidated schema
4. `cerebro_main.py:1756-1767` - Fixed execution quantity lookup from `legs[].execution`
5. `cerebro_main.py:1779-1783` - Fixed decision leg_results lookup from `legs[].decision`

**Status:** ⚠️ PARTIAL - EXIT signals now get APPROVED by cerebro, but orders created with wrong direction

**Remaining Issue:**
- EXIT orders being created with direction='LONG' instead of side='SELL'
- Execution service needs these to be marked as closing orders
- Location: cerebro order creation logic needs to set proper side/action for EXIT

### ❌ Issue 3 & 4: Position Status, Closed Time, P&L - NOT STARTED
**What's Needed:**
1. Execution service needs to recognize EXIT orders as position-closing orders
2. When EXIT executes, calculate P&L:
   - Entry price from `legs[0].execution.weighted_avg_price`
   - Exit price from `legs[1].execution.weighted_avg_price`
   - Quantity from `legs[0].execution.total_quantity_filled`
   - P&L = (exit_price - entry_price) * quantity
3. Update position.status from 'OPEN' → 'CLOSED'
4. Set position.closed_at timestamp
5. Store position.pnl

**Files to Update:**
- `services/execution_service/execution_main.py` - Position closing logic
- Possibly cerebro order creation to properly mark EXIT orders

### ❌ Issue 5: Quantity Progress Bar - NOT STARTED
**What's Needed:**
1. Update Trading Signals tab UI component
2. Add quantity column with progress bar visualization
3. Show: `filled/total` (e.g., "30/54")
4. Color: Orange if position OPEN/PARTIAL, Green if CLOSED
5. Progress bar fills proportionally to quantity closed

**Files to Update:**
- `frontend-admin/src/pages/Activity.tsx` - Trading Signals tab component

## Current State

**Working:**
- ✅ Signal ingestion creates consolidated documents
- ✅ ENTRY signals processed and executed correctly
- ✅ EXIT signals added to legs[] array
- ✅ Cerebro watches for updates and processes EXIT legs
- ✅ Cerebro approves EXIT signals
- ✅ Signal Legs tab shows all legs

**Not Working:**
- ❌ EXIT orders created with wrong direction (LONG instead of SELL)
- ❌ Execution service doesn't execute EXIT orders
- ❌ Position status stays OPEN after EXIT approved
- ❌ No P&L calculation
- ❌ No closed_at timestamp
- ❌ No progress bar visualization

## Next Steps

1. **HIGH PRIORITY:** Fix cerebro EXIT order creation
   - Find where orders are created for EXIT signals
   - Ensure they have side='SELL' or action='SELL' to close position
   - Cerebro likely around line 2300-2400 where orders are created

2. **HIGH PRIORITY:** Update execution service for EXIT handling
   - Recognize SELL orders as position-closing
   - Calculate P&L when closing
   - Update position.status to 'CLOSED'
   - Set position.closed_at timestamp

3. **MEDIUM PRIORITY:** Add quantity progress bar UI
   - Update Activity.tsx Trading Signals tab
   - Add visual progress indicator

## Testing Command
```bash
.venv/bin/python scripts/junk/clear_test_data.py && \
.venv/bin/python tests/signals_testing/run_full_test.py \
  --folder tests/signals_testing/sample_signals \
  --delay 5 \
  --signal_count 2
```

## Key Files Modified
1. `frontend-admin/server/api.js` - API endpoints for consolidated schema
2. `services/cerebro_service/cerebro_main.py` - Position lookup and EXIT processing  
3. `services/signal_ingestion/mongodb_watcher.py` - Already updated in previous work
4. `services/execution_service/execution_main.py` - Already updated for legs[] schema

## ONE SOURCE OF TRUTH Status
✅ Consolidated schema is working
✅ All data stored in single document with legs[] array
✅ ONE document per signal with multiple legs
✅ ENTRY leg has decision + execution
⚠️ EXIT leg has decision but missing execution (order direction issue)
