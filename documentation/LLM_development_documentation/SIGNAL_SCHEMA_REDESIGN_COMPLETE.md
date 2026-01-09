# Signal Schema Redesign v2 - Implementation Complete

## Overview
Successfully implemented all 3 phases of the Signal Schema Redesign v2, adding support for:
- Signal legs with unique identifiers (leg_id, leg_type, parent_signal_id)
- Partial exit support with position status tracking (OPEN → PARTIAL → CLOSED)
- Cumulative P&L tracking across multiple partial exits

## Phase 1: Frontend Renaming & Aggregation (✅ COMPLETED)

### Files Modified:
- `frontend-admin/src/pages/Activity.tsx`
- `frontend-admin/server/api.js`
- `frontend-admin/src/services/api.ts`

### Changes:
1. **Activity Page Tabs**: Renamed "Signals/Positions" to "Signal Legs/Trading Signals"
2. **Trading Signals API Endpoint**: Created `/api/v1/activity/trading-signals` that aggregates ENTRY signals with their associated EXIT signals
3. **Frontend Service**: Added `getTradingSignals()` method to API client
4. **Trading Signals Tab UI**: New tab showing aggregated view of complete trades (ENTRY + all EXITs)

## Phase 2: Schema Enhancement (✅ COMPLETED)

### Files Modified:
- `services/signal_ingestion/mongodb_watcher.py`

### Files Created:
- `scripts/migrations/backfill_leg_fields.js`

### Changes:

#### 2.1 Signal Ingestion Service (`mongodb_watcher.py`)
Modified `_build_signal_store_doc()` to add three new fields:

```python
# Determine leg_type from signal_type or first leg's action
leg_type = 'ENTRY' | 'EXIT' | 'SCALE_IN' | 'SCALE_OUT' | 'UNKNOWN'

# Generate unique leg_id
leg_id = f"{signal_id}__{leg_type.lower()}"

# For EXIT signals, get parent_signal_id from entry_signal_id
parent_signal_id = raw_signal_doc.get('entry_signal_id') if leg_type == 'EXIT' else None
```

**New Fields Added to signal_store:**
- `leg_id`: Unique identifier for this signal leg (format: `{signal_id}__{leg_type}`)
- `leg_type`: Type of leg (ENTRY, EXIT, SCALE_IN, SCALE_OUT, UNKNOWN)
- `parent_signal_id`: For EXIT signals, references the ENTRY signal's signal_id

#### 2.2 Migration Script (`backfill_leg_fields.js`)
Created Node.js migration script to backfill existing signals with new leg fields:
- Iterates through all signals in signal_store collection
- Determines leg_type from raw.signal_type or first leg action
- Generates leg_id as `{signal_id}__{leg_type.lower()}`
- For EXIT signals, fetches parent_signal_id from referenced entry signal
- Updates each document with new fields
- Skips signals that already have leg fields

**Run Migration:**
```bash
cd scripts/migrations
node backfill_leg_fields.js
```

## Phase 3: Partial Exit Support (✅ COMPLETED)

### Files Modified:
- `services/execution_service/execution_main.py`
- `frontend-admin/src/pages/Activity.tsx`
- `frontend-admin/server/api.js`

### Changes:

#### 3.1 Execution Service - Partial Exit Logic (`execution_main.py`)

Modified `update_signal_store_with_execution()` function (lines 563-856) to implement:

**Position Status State Machine:**
```
OPEN → PARTIAL → CLOSED
```

**Logic:**
1. When EXIT signal is executed:
   - Calculate P&L for this specific exit
   - Fetch all exit signals for the entry position
   - Sum total_exit_quantity across all exits
   - Calculate cumulative P&L across all exits

2. Determine position status:
   - `total_exit_quantity >= entry_quantity` → **CLOSED** (fully exited)
   - `total_exit_quantity > 0` → **PARTIAL** (partially exited)
   - `total_exit_quantity == 0` → **OPEN** (no exits yet)

3. Update ENTRY signal with:
   - `position.status`: Current status (OPEN/PARTIAL/CLOSED)
   - `position.pnl`: Cumulative P&L across all exits
   - `position.partial_exit_count`: Number of exit signals
   - `position.remaining_quantity`: Quantity still open
   - `position.exit_signals`: Array of all exit signal ObjectIds

**New Schema Fields:**
```javascript
position: {
  status: "OPEN" | "PARTIAL" | "CLOSED",
  pnl: {
    gross: number,      // Cumulative across all exits
    net: number,        // Cumulative after commissions
    percent: number,    // Based on entry cost basis
    commission: number, // Total commissions
    holding_seconds: number
  },
  partial_exit_count: number,    // Number of partial exits
  remaining_quantity: number,    // Remaining quantity after exits
  exit_signals: [ObjectId],      // All exit signal references
  opened_at: Date,
  closed_at: Date                // Only set when CLOSED
}
```

#### 3.2 Frontend - Display Partial Status (`Activity.tsx`, `api.js`)

**Activity.tsx:**
- Updated status badge styling to explicitly handle PARTIAL status with yellow background
- Added display of remaining quantity for PARTIAL positions: `PARTIAL (5 left)`

**api.js:**
- Updated `/api/v1/activity/trading-signals` endpoint to include:
  - `partial_exit_count`: Number of partial exits
  - `remaining_quantity`: Remaining quantity after partial exits

**Status Badge Colors:**
- **OPEN**: Green (`bg-green-900/30 text-green-400`)
- **PARTIAL**: Yellow (`bg-yellow-900/30 text-yellow-400`) with remaining quantity
- **CLOSED**: Gray (`bg-gray-700 text-gray-300`)

## Schema Documentation

### signal_store Collection - Complete v2 Schema

```javascript
{
  // === IDENTITY (Phase 2) ===
  "signal_id": "ABC123",
  "leg_id": "ABC123__entry",           // NEW: Unique leg identifier
  "leg_type": "ENTRY" | "EXIT" | ...,  // NEW: Leg type
  "parent_signal_id": "ABC122",        // NEW: For EXIT legs
  "strategy_id": "momentum_v1",
  "environment": "staging",

  // === EXECUTION ===
  "execution": {
    "status": "FILLED",
    "orders": [{
      "order_id": "...",
      "quantity_filled": 100,
      "avg_fill_price": 150.25
    }],
    "total_quantity_filled": 100,
    "weighted_avg_price": 150.25
  },

  // === POSITION (Phase 3) ===
  "position": {
    "status": "OPEN" | "PARTIAL" | "CLOSED",  // NEW: Three-state system
    "opened_at": Date,
    "closed_at": Date,
    "pnl": {
      "gross": 245.50,           // Cumulative across all exits
      "net": 242.50,             // After all commissions
      "percent": 1.62,           // Based on entry cost basis
      "commission": 3.00,        // Total commissions
      "holding_seconds": 3600
    },
    "partial_exit_count": 2,     // NEW: Number of exits
    "remaining_quantity": 50,    // NEW: Remaining qty
    "exit_signals": [ObjectId]   // All exit references
  },

  // === RAW SIGNAL DATA ===
  "raw": { ... },

  // === TIMESTAMPS ===
  "created_at": Date,
  "updated_at": Date
}
```

## Testing Checklist

Before deploying to production:

- [ ] Run migration script on staging database: `node scripts/migrations/backfill_leg_fields.js`
- [ ] Verify all existing signals have leg_id, leg_type fields
- [ ] Test ENTRY signal creation - verify leg fields are populated
- [ ] Test EXIT signal creation - verify parent_signal_id is set
- [ ] Test partial exit scenario:
  - [ ] Enter position with 100 shares
  - [ ] Exit 30 shares → Verify status = PARTIAL, remaining_quantity = 70
  - [ ] Exit 40 shares → Verify status = PARTIAL, remaining_quantity = 30, cumulative P&L updated
  - [ ] Exit 30 shares → Verify status = CLOSED, remaining_quantity = 0, final cumulative P&L
- [ ] Verify frontend displays PARTIAL status with yellow styling
- [ ] Verify remaining quantity is shown on PARTIAL positions
- [ ] Verify cumulative P&L is calculated correctly across multiple exits

## Rollback Plan

If issues arise:

1. **Phase 3 Rollback** (Partial Exit Support):
   ```bash
   git revert <phase-3-commit>
   ```
   - Restores original OPEN → CLOSED logic
   - Frontend will still work (falls back to yellow for PARTIAL)

2. **Phase 2 Rollback** (Leg Fields):
   - Revert `mongodb_watcher.py` changes
   - New signals won't have leg fields, but system will continue working
   - Existing signals with leg fields remain harmless

3. **Phase 1 Rollback** (Frontend Changes):
   - Revert Activity.tsx, api.js, api.ts changes
   - Restores original "Signals" and "Positions" tabs

## Migration Timeline

1. **Deploy Phase 1** (Frontend only) - Safe, no backend changes
2. **Deploy Phase 2** (Leg fields) - Run migration on database
3. **Test Phase 2** - Verify new signals have leg fields
4. **Deploy Phase 3** (Partial exits) - Test with multi-exit scenarios
5. **Monitor** - Watch for partial exit positions in production

## Notes

- All changes are backward compatible with v1 schema
- Existing signals without leg fields will work (migration adds them)
- Frontend gracefully handles missing fields
- Cumulative P&L calculation is efficient (one DB query per exit)
- Mock broker balance updates are accurate for partial exits

## Implementation Date
2026-01-09

## Status
✅ ALL PHASES COMPLETE - READY FOR TESTING
