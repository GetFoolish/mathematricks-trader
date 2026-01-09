# Consolidated Signal Schema Implementation - Status

## Date: 2026-01-09

## Goal
Consolidate signal_store to use **ONE document per signal** with all legs (ENTRY/EXIT/SCALE_IN/SCALE_OUT) in a `legs` array.

## What Changed

###  ✅ COMPLETED

#### 1. Signal Ingestion Service (`mongodb_watcher.py`)
- **ENTRY signals**: Create NEW document with first leg
- **EXIT/SCALE signals**: Find parent document by `base_signal_id` and append leg to `legs` array
- Both catch-up mode and Change Stream updated

#### 2. Frontend API (`api.js`)
- `/api/v1/activity/trading-signals` endpoint updated to query consolidated documents
- Returns signals with `legs` array containing all ENTRY/EXIT/SCALE legs
- No longer queries separate documents and joins them

### ⏳ IN PROGRESS / TODO

#### 3. Execution Service (`execution_main.py`) - **CRITICAL**
**Current Problem**: Expects separate documents for ENTRY/EXIT signals

**Required Changes**:
```python
# OLD (separate documents):
signal_store_collection.update_one(
    {"_id": ObjectId(mathematricks_signal_id)},  # Updates separate EXIT document
    {"$set": execution_update}
)

# NEW (consolidated - update leg in array):
# Find parent document
parent_doc = signal_store_collection.find_one({"base_signal_id": entry_signal_id})

# Update specific leg's execution data
signal_store_collection.update_one(
    {
        "_id": parent_doc['_id'],
        "legs.leg_id": current_leg_id  # Match specific leg
    },
    {
        "$set": {
            "legs.$.execution": execution_data,  # Update matched leg
            "position.status": new_status,        # Update parent position
            "position.pnl": cumulative_pnl,
            "updated_at": datetime.utcnow()
        }
    }
)
```

**Functions to Update**:
- `update_signal_store_with_execution()` - Lines 563-856
  - Find parent document instead of separate EXIT document
  - Update leg in `legs` array using `$` positional operator
  - Calculate position status from ALL exit legs

#### 4. Cerebro Service (`cerebro_main.py`) - **CRITICAL**
**Current Problem**: Reads/writes `decision` field at document root

**Required Changes**:
- Read from `legs[].decision` instead of root `decision`
- Update specific leg's decision field
- May need to pass `leg_index` or `leg_id` to identify which leg to update

#### 5. Migration Script - **TODO**
Need script to consolidate existing separate documents into consolidated format:

```javascript
// Pseudocode:
// 1. Find all ENTRY signals (documents with leg_type='ENTRY')
// 2. For each ENTRY:
//    - Create legs array with ENTRY as first element
//    - Find all EXIT/SCALE signals that reference this ENTRY
//    - Append EXIT/SCALE documents as additional legs
//    - Update position status based on all legs
//    - Delete separate EXIT/SCALE documents
// 3. Add base_signal_id field to all documents
```

## New Schema Structure

```javascript
{
  "_id": ObjectId("..."),
  "signal_id": "sig_com1_met_009",      // Signal ID from ENTRY
  "base_signal_id": "sig_com1_met_009", // For finding by original signal
  "strategy_id": "Com1-Met",
  "environment": "staging",
  "instrument": "HG",

  // === LEGS ARRAY ===
  "legs": [
    {
      "leg_id": "sig_com1_met_009__entry_0",
      "leg_type": "ENTRY",
      "leg_index": 0,
      "raw": {
        "_id": ObjectId("..."),  // Reference to trading_signals_raw
        "signal_type": "ENTRY",
        "legs": [...]
      },
      "decision": {           // Populated by Cerebro
        "approved": true,
        "rejection_reason": null,
        ...
      },
      "execution": {          // Populated by Execution Service
        "status": "FILLED",
        "orders": [...],
        "total_quantity_filled": 168
      },
      "created_at": Date
    },
    {
      "leg_id": "sig_com1_met_010__exit_1",
      "leg_type": "EXIT",
      "leg_index": 1,
      "raw": {...},
      "decision": {...},
      "execution": {...},
      "created_at": Date
    }
  ],

  // === POSITION STATUS ===
  "position": {
    "status": "OPEN" | "PARTIAL" | "CLOSED",
    "entry_quantity": 168,
    "exit_quantity": 0,
    "remaining_quantity": 168,
    "pnl": {
      "gross": 0,
      "net": 0,
      "percent": 0
    },
    "opened_at": Date,
    "closed_at": null
  },

  "created_at": Date,
  "updated_at": Date
}
```

## Testing Plan

1. **Clear test data**: `python scripts/junk/clear_test_data.py`
2. **Run test**: `python tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals --delay 10 --signal_count 10`
3. **Verify**:
   - signal_store has ONE document per signal
   - Each document has multiple legs in `legs` array
   - Trading Signals tab shows all signals
   - Position status transitions correctly (OPEN → PARTIAL → CLOSED)

## Next Steps

1. **Update Execution Service** - Modify to work with legs array
2. **Update Cerebro Service** - Modify to work with legs array
3. **Create Migration Script** - Consolidate existing data
4. **Test** - Full end-to-end test

## Notes

- `trading_signals_raw` remains UNCHANGED (separate documents per signal as audit trail)
- Only `signal_store` uses consolidated schema
- Backward compatibility: May need to support both schemas during transition
