# Signal Schema Redesign v2 - Comprehensive Architecture Update

**Date**: 2026-01-09
**Status**: PLANNING (Not Yet Implemented)
**Priority**: MEDIUM (Future Enhancement)
**Prerequisite**: Fix P&L Duplication Issue (must be done first)

---

## Executive Summary

This document outlines a comprehensive redesign of the signal schema to:
1. **Clarify terminology** - Signals vs Signal-Legs vs Orders
2. **Improve data hierarchy** - Signal → Legs → Orders → Fills
3. **Fix duplicate storage** - Single Source of Truth for all data
4. **Enhance frontend UX** - Clear tabs for Signals, Legs, Orders, Positions

**Key Insight**: The current system is architecturally sound (one document per signal), but terminology and frontend display are confusing. This redesign focuses on **renaming and reorganizing** rather than fundamental schema changes.

---

## Current Architecture Analysis

### What Works Well ✅

1. **Signal Storage**: Already stores one document per signal (not per leg)
2. **Multi-Leg Support**: Legs already stored in `raw.legs[]` array
3. **Entry-Exit Linking**: EXIT signals reference ENTRY via `entry_signal_id`
4. **Multi-Fund Execution**: Orders array supports multiple funds correctly
5. **Position Lifecycle**: ENTRY signals track OPEN → CLOSED status

### What's Confusing ❌

1. **Frontend Tab Names**:
   - "Signals" tab → Shows individual signal documents (both ENTRY and EXIT) - **Misleading!**
   - "Positions" tab → Shows aggregated positions - **Should be called "Signals"!**

2. **Terminology Inconsistency**:
   - User thinks: "Signal" = complete trading decision (ENTRY + EXIT)
   - System stores: "Signal" = individual action (ENTRY **or** EXIT)
   - Result: Confusion about what a "signal" means

3. **Duplicate P&L Storage**:
   - P&L stored in both ENTRY and EXIT documents (architectural flaw)

---

## Proposed Architecture v2

### Core Concept: Clarify the Hierarchy

```
1. TRADING SIGNAL (User's Intent)
   ├─ Represents a complete trading decision
   ├─ May span multiple actions (ENTRY, EXIT, SCALE_IN, SCALE_OUT)
   └─ Currently: No single document represents this concept!

2. SIGNAL LEG (Action within a Signal)
   ├─ A specific action: ENTRY, EXIT, SCALE_IN, SCALE_OUT
   ├─ Currently: Stored as separate documents in signal_store
   └─ Proposal: Keep as separate documents, but rename fields/tabs

3. ORDER (Execution Instruction)
   ├─ Instruction sent to broker/exchange
   ├─ Currently: Stored in execution.orders[] array
   └─ Proposal: No changes needed (already correct)

4. FILL (Execution Confirmation)
   ├─ Partial or full order execution from broker
   ├─ Currently: Stored in execution.orders[].fills[] array
   └─ Proposal: No changes needed (already correct)
```

### Two Design Options

#### Option A: Keep Current Schema, Rename Frontend (RECOMMENDED)

**Pros**:
- ✅ No backend changes required
- ✅ No data migration needed
- ✅ Quick to implement (frontend only)
- ✅ Preserves existing functionality

**Cons**:
- ❌ Still stores ENTRY and EXIT as separate documents
- ❌ No single "Signal" document representing complete trade

**Changes**:
- Frontend: Rename tabs to clarify terminology
- Backend: No changes
- Migration: None needed

#### Option B: Create Aggregate Signal Documents (COMPLEX)

**Pros**:
- ✅ Single document per "trading signal" (user's mental model)
- ✅ Clear hierarchy: Signal → Legs → Orders → Fills
- ✅ Easier to query "all actions for signal X"

**Cons**:
- ❌ Major schema redesign required
- ❌ Complex migration (link ENTRY + EXIT documents)
- ❌ Changes Cerebro, Execution, Frontend
- ❌ Breaks existing integrations

**Changes**:
- New collection: `trading_signals` (aggregate view)
- Keep `signal_store` for individual legs
- Major migration script
- Update all services

---

## RECOMMENDED APPROACH: Option A - Rename & Reorganize

This is the pragmatic, low-risk approach that delivers 80% of the value with 20% of the effort.

### Phase 1: Fix Terminology (Frontend Only)

#### 1.1 Rename Frontend Tabs

**File**: `frontend-admin/src/pages/Activity.tsx`

**Current Tabs** (lines 110-140):
```typescript
"Signals" → Shows ENTRY and EXIT signal documents
"Orders & Executions" → Shows broker orders
"Positions" → Shows aggregated positions
```

**New Tabs** (Proposed):
```typescript
"Signal Legs" → Shows ENTRY, EXIT, SCALE_IN, SCALE_OUT actions
"Orders & Executions" → Shows broker orders (no change)
"Positions" → Shows complete trading signals (ENTRY + all EXITs)
```

**Rationale**:
- "Signal Legs" clarifies these are individual actions
- "Positions" better represents complete trades
- User mental model matches display

#### 1.2 Update API Endpoint Names

**File**: `frontend-admin/server/api.js`

**Current Endpoints**:
```javascript
GET /api/v1/activity/signals       // Returns ENTRY and EXIT documents
GET /api/v1/activity/orders        // Returns execution orders
GET /api/v1/activity/positions     // Returns aggregated positions
```

**Proposed Endpoints** (with aliases):
```javascript
GET /api/v1/activity/signal-legs   // New name for /signals
GET /api/v1/activity/signals       // Alias to /signal-legs (backward compat)

GET /api/v1/activity/orders        // No change

GET /api/v1/activity/positions     // No change (already correct)
GET /api/v1/activity/trades        // Alias to /positions (alternative name)
```

**Implementation**:
```javascript
// Add new endpoint with clear name
app.get('/api/v1/activity/signal-legs', async (req, res) => {
  // Same logic as current /signals endpoint
  // Returns ENTRY, EXIT, SCALE_IN, SCALE_OUT documents
});

// Keep old endpoint as alias (backward compatibility)
app.get('/api/v1/activity/signals', async (req, res) => {
  req.url = '/api/v1/activity/signal-legs';
  return app._router.handle(req, res);
});
```

#### 1.3 Add Signal Aggregation View (Optional Enhancement)

**File**: `frontend-admin/server/api.js`

**New Endpoint**: `GET /api/v1/activity/trading-signals`

**Purpose**: Returns complete trading signals (ENTRY + all associated EXITs)

**Implementation**:
```javascript
app.get('/api/v1/activity/trading-signals', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const environment = req.query.environment;

    // Get all ENTRY signals (these are "parent" signals)
    const query = {
      'raw.signal_type': 'ENTRY'
    };
    if (environment) query.environment = environment;

    const entrySignals = await signalStoreCollection
      .find(query)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    // For each ENTRY, fetch associated EXIT signals
    const tradingSignals = [];

    for (const entry of entrySignals) {
      const exitSignals = [];

      if (entry.position?.exit_signals?.length > 0) {
        const exitDocs = await signalStoreCollection
          .find({
            _id: { $in: entry.position.exit_signals.map(id => new ObjectId(id)) }
          })
          .toArray();

        exitSignals.push(...exitDocs);
      }

      // Build aggregated signal view
      tradingSignals.push({
        signal_id: entry.signal_id,  // Primary signal ID (ENTRY)
        entry_signal: serializeDocument(entry),
        exit_signals: exitSignals.map(serializeDocument),
        status: entry.position?.status || 'UNKNOWN',
        pnl: entry.position?.pnl || null,
        opened_at: entry.position?.opened_at,
        closed_at: entry.position?.closed_at,
        instrument: entry.raw?.legs?.[0]?.instrument,
        strategy_id: entry.strategy_id,
        environment: entry.environment
      });
    }

    res.json({
      status: 'success',
      count: tradingSignals.length,
      trading_signals: tradingSignals
    });
  } catch (error) {
    console.error('[API] Error fetching trading signals:', error);
    res.status(500).json({ detail: error.message });
  }
});
```

**Frontend Usage**:
```typescript
// New tab: "Trading Signals" (optional)
const { data: tradingSignalsData } = useQuery({
  queryKey: ['trading-signals', environmentFilter],
  queryFn: () => apiClient.getTradingSignals(50, environmentFilter),
  refetchInterval: 5000,
});

// Display: Each row shows complete trade (ENTRY + EXITs)
// Expandable to show individual legs
```

---

## Phase 2: Add Signal-Leg Identifiers (Backend Enhancement)

### 2.1 Add Leg ID Field

**Current**: Each signal document has `signal_id` (e.g., `sig_spy_001`)

**Proposed**: Add `leg_id` field to clarify this is a leg

**Schema Update**:
```python
{
  "_id": ObjectId("..."),
  "signal_id": "sig_spy_001",           # Original signal ID (from TradingView)
  "leg_id": "sig_spy_001__entry",       # NEW: Unique leg identifier
  "leg_type": "ENTRY",                  # NEW: ENTRY, EXIT, SCALE_IN, SCALE_OUT
  "leg_sequence": 0,                    # NEW: 0=first leg, 1=second, etc.

  "parent_signal_id": null,             # NEW: For ENTRY legs, null
                                        #      For EXIT legs, points to ENTRY signal_id

  "raw": {
    "signal_type": "ENTRY",             # Keep for backward compat
    "legs": [...],
    ...
  },
  ...
}
```

**Benefits**:
- Clear identification of individual legs
- Easy to query all legs for a signal: `signal_id = "sig_spy_001"`
- Backward compatible (keep existing `signal_id`)

**Implementation**:
```python
# In signal_ingestion_service/mongodb_watcher.py
def create_signal_store_document(raw_signal_doc):
    signal_id = raw_signal_doc.get('signalID')
    signal_type = raw_signal_doc.get('signal_type')

    # Generate unique leg_id
    leg_id = f"{signal_id}__{signal_type.lower()}"

    # Determine parent signal
    parent_signal_id = None
    if signal_type == 'EXIT':
        # Link to ENTRY signal
        entry_name = raw_signal_doc.get('entry_signal_id')
        if entry_name:
            entry_signal = signal_store.find_one({
                'raw.entry_name': entry_name
            })
            if entry_signal:
                parent_signal_id = entry_signal['signal_id']

    signal_doc = {
        "_id": ObjectId(),
        "signal_id": signal_id,
        "leg_id": leg_id,                    # NEW
        "leg_type": signal_type,             # NEW
        "leg_sequence": 0,                   # NEW (calculate from existing legs)
        "parent_signal_id": parent_signal_id, # NEW

        "strategy_id": raw_signal_doc.get('strategy_name'),
        "environment": raw_signal_doc.get('environment', 'production'),

        "raw": {
            "_id": raw_signal_doc['_id'],
            "received_at": raw_signal_doc.get('received_at'),
            "sent_epoch": raw_signal_doc.get('signal_sent_EPOCH'),
            "signal_type": signal_type,
            "entry_name": raw_signal_doc.get('entry_name'),
            "legs": raw_signal_doc.get('signal_legs', []),
            ...
        },

        "decision": None,
        "execution": None,
        "position": {},

        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    return signal_doc
```

### 2.2 Update Indexes

**File**: `services/signal_ingestion_service/mongodb_watcher.py`

**Add Indexes**:
```python
# Existing index
signal_store.create_index([("signal_id", 1)])

# NEW indexes for leg queries
signal_store.create_index([("leg_id", 1)], unique=True)
signal_store.create_index([("parent_signal_id", 1)])
signal_store.create_index([("signal_id", 1), ("leg_type", 1)])
```

---

## Phase 3: Enhanced Position Tracking (Optional)

### 3.1 Add Position State Machine

**Current**: Only tracks OPEN/CLOSED

**Proposed**: Track full position lifecycle

**States**:
```python
class PositionStatus(Enum):
    PENDING = "PENDING"           # Signal received, not yet executed
    OPEN = "OPEN"                 # Position opened (ENTRY filled)
    PARTIALLY_CLOSED = "PARTIAL"  # Some exits filled, position still open
    CLOSED = "CLOSED"             # Fully closed (all exits filled)
    CANCELLED = "CANCELLED"       # Signal cancelled before execution
    FAILED = "FAILED"             # Execution failed
```

**Schema Update**:
```python
"position": {
    "status": "OPEN" | "PARTIAL" | "CLOSED" | "CANCELLED" | "FAILED",

    "opened_at": datetime,
    "closed_at": datetime,

    "entry_legs": [ObjectId("...")],      # All ENTRY legs
    "exit_legs": [ObjectId("...")],       # All EXIT legs

    "quantity_opened": 100,               # Total quantity entered
    "quantity_closed": 50,                # Total quantity exited
    "quantity_remaining": 50,             # quantity_opened - quantity_closed

    "pnl": {
        "realized": {...},                # P&L from closed quantity
        "unrealized": {...},              # P&L from remaining quantity (if PARTIAL)
        "total": {...}                    # realized + unrealized
    }
}
```

### 3.2 Support Partial Exits

**Current**: Assumes full position close on EXIT

**Proposed**: Track partial exits and cumulative P&L

**Example**:
```
ENTRY: Buy 100 SPY @ $580 → position.quantity_opened = 100
EXIT:  Sell 30 SPY @ $585  → position.quantity_closed = 30, status = "PARTIAL"
EXIT:  Sell 70 SPY @ $590  → position.quantity_closed = 100, status = "CLOSED"
```

**Implementation**:
```python
def calculate_partial_pnl(entry_signal, exit_signal):
    """Calculate P&L for partial exit"""
    entry_price = entry_signal['execution']['weighted_avg_price']
    entry_qty = entry_signal['execution']['total_quantity_filled']

    exit_price = exit_signal['execution']['weighted_avg_price']
    exit_qty = exit_signal['execution']['total_quantity_filled']

    # P&L only for closed quantity
    realized_pnl = (exit_price - entry_price) * exit_qty

    # Update ENTRY signal position
    position = entry_signal.get('position', {})

    current_closed_qty = position.get('quantity_closed', 0)
    new_closed_qty = current_closed_qty + exit_qty

    remaining_qty = entry_qty - new_closed_qty

    # Determine new status
    if remaining_qty > 0:
        status = "PARTIAL"
    else:
        status = "CLOSED"

    # Cumulative realized P&L
    current_realized_pnl = position.get('pnl', {}).get('realized', {}).get('net', 0)
    new_realized_pnl = current_realized_pnl + realized_pnl

    return {
        "status": status,
        "quantity_closed": new_closed_qty,
        "quantity_remaining": remaining_qty,
        "pnl": {
            "realized": {
                "net": new_realized_pnl,
                "gross": ...,
                "commission": ...
            },
            "unrealized": {...} if remaining_qty > 0 else None
        }
    }
```

---

## Files Requiring Changes

### Frontend Changes (Phase 1)

| File | Changes | Effort |
|------|---------|--------|
| `frontend-admin/src/pages/Activity.tsx` | Rename tabs: "Signals" → "Signal Legs", update display logic | 2 hours |
| `frontend-admin/src/services/api.ts` | Add `getTradingSignals()` method, update types | 1 hour |
| `frontend-admin/src/types/index.ts` | Add `TradingSignal` type, update `Signal` type | 30 min |
| `frontend-admin/server/api.js` | Add `/trading-signals` endpoint, rename `/signals` → `/signal-legs` | 2 hours |

### Backend Changes (Phase 2)

| File | Changes | Effort |
|------|---------|--------|
| `services/signal_ingestion_service/mongodb_watcher.py` | Add `leg_id`, `leg_type`, `parent_signal_id` fields | 2 hours |
| `services/cerebro_service/cerebro_main.py` | Update queries to use new fields | 1 hour |
| `services/execution_service/execution_main.py` | Update position tracking logic, add partial exit support | 4 hours |

### Migration Scripts

| Script | Purpose | Effort |
|--------|---------|--------|
| `scripts/add_leg_identifiers.js` | Backfill `leg_id`, `leg_type` for existing signals | 2 hours |
| `scripts/link_parent_signals.js` | Populate `parent_signal_id` for EXIT signals | 2 hours |

---

## Sample Signal JSON Updates

### Before (Current)

```json
{
  "strategy_name": "SPY",
  "signal_type": "ENTRY",
  "signalID": "sig_spy_001",
  "entry_name": "$ENTRY_1",
  "signal_legs": [
    {
      "instrument": "SPY",
      "action": "BUY",
      "quantity": 50
    }
  ]
}
```

### After (Proposed - No Changes!)

Sample signals **DO NOT need to change**. The changes are internal (schema enhancement).

TradingView still sends the same JSON format. Signal ingestion service adds the new fields automatically.

---

## Implementation Timeline

### Phase 1: Quick Wins (1 week)
- [ ] Fix P&L duplication issue (prerequisite)
- [ ] Rename frontend tabs
- [ ] Add `/trading-signals` endpoint
- [ ] Update frontend to use new endpoint

### Phase 2: Schema Enhancement (2 weeks)
- [ ] Add `leg_id`, `leg_type`, `parent_signal_id` fields
- [ ] Update signal ingestion to populate new fields
- [ ] Migrate existing signals (backfill script)
- [ ] Update Cerebro and Execution services

### Phase 3: Enhanced Features (3 weeks)
- [ ] Add position state machine (PARTIAL status)
- [ ] Support partial exits
- [ ] Add cumulative P&L tracking
- [ ] Update frontend to display partial positions

**Total Estimated Effort**: 6 weeks (can be done incrementally)

---

## Testing Strategy

### Unit Tests

```python
# Test signal leg creation
def test_create_entry_leg():
    signal = create_signal_leg(signal_type='ENTRY', ...)
    assert signal['leg_id'] == 'sig_test_001__entry'
    assert signal['leg_type'] == 'ENTRY'
    assert signal['parent_signal_id'] is None

def test_create_exit_leg():
    entry_signal = create_signal_leg(signal_type='ENTRY', ...)
    exit_signal = create_signal_leg(
        signal_type='EXIT',
        parent_signal_id=entry_signal['signal_id']
    )
    assert exit_signal['leg_id'] == 'sig_test_001__exit'
    assert exit_signal['parent_signal_id'] == entry_signal['signal_id']

# Test partial exit
def test_partial_exit():
    entry = create_entry_signal(quantity=100, price=580)
    exit1 = create_exit_signal(quantity=30, price=585)

    position = calculate_position_status(entry, [exit1])
    assert position['status'] == 'PARTIAL'
    assert position['quantity_remaining'] == 70

    exit2 = create_exit_signal(quantity=70, price=590)
    position = calculate_position_status(entry, [exit1, exit2])
    assert position['status'] == 'CLOSED'
    assert position['quantity_remaining'] == 0
```

### Integration Tests

```python
def test_full_signal_lifecycle():
    # 1. Send ENTRY signal
    entry_response = send_signal({
        'signal_type': 'ENTRY',
        'signalID': 'test_001',
        'entry_name': '$TEST_1'
    })

    # 2. Verify leg_id created
    entry = get_signal_leg('test_001__entry')
    assert entry is not None
    assert entry['leg_type'] == 'ENTRY'

    # 3. Send EXIT signal
    exit_response = send_signal({
        'signal_type': 'EXIT',
        'signalID': 'test_002',
        'entry_signal_id': '$TEST_1'
    })

    # 4. Verify parent link
    exit_sig = get_signal_leg('test_002__exit')
    assert exit_sig['parent_signal_id'] == 'test_001'

    # 5. Fetch trading signal (aggregate view)
    trading_signal = get_trading_signal('test_001')
    assert trading_signal['entry_signal']['signal_id'] == 'test_001'
    assert len(trading_signal['exit_signals']) == 1
    assert trading_signal['status'] == 'CLOSED'
```

---

## Risk Assessment

### Low Risk (Phase 1)
- ✅ Frontend tab renaming (cosmetic change)
- ✅ Add new API endpoint (backward compatible)
- ✅ Frontend display updates (no backend impact)

### Medium Risk (Phase 2)
- ⚠️ Schema changes (add new fields)
  - Mitigation: Backward compatible (old code ignores new fields)
- ⚠️ Migration script (backfill existing data)
  - Mitigation: Test on staging first, can run incrementally

### High Risk (Phase 3)
- 🚨 Partial exit logic (changes core business logic)
  - Mitigation: Extensive testing, feature flag to enable/disable
- 🚨 Position state machine (affects multiple services)
  - Mitigation: Phased rollout, monitor carefully

---

## Rollback Plan

### Phase 1 Rollback
- Revert frontend tab names
- Remove `/trading-signals` endpoint
- Update frontend to use old endpoints

### Phase 2 Rollback
- New fields are additive, no rollback needed
- Old code ignores new fields automatically

### Phase 3 Rollback
- Feature flag to disable partial exit logic
- Fall back to current "full close only" behavior
- Database state remains consistent

---

## Future Enhancements (Beyond This Document)

### Multi-Leg Strategy Support
- Complex options strategies (spreads, iron condors)
- Each leg could be a separate order with different instruments
- Already supported in schema (`raw.legs[]` array)

### Signal Versioning
- Track signal modifications (stop loss updates, position size changes)
- Add `version` field and `modifications[]` array

### Signal Templates
- Pre-defined signal patterns
- Users can create reusable templates
- Store in `signal_templates` collection

### Advanced P&L Analytics
- Leg-level P&L tracking (for multi-leg strategies)
- Time-weighted P&L
- Risk-adjusted returns

---

## Conclusion

This redesign focuses on **clarifying terminology and improving UX** without breaking existing functionality. The current schema is fundamentally sound; we're enhancing it incrementally.

**Recommended Path**:
1. **Start with Phase 1** (frontend only, quick wins)
2. **Monitor user feedback** before proceeding to Phase 2
3. **Only implement Phase 3** if partial exits are actually needed

**Key Principle**: Evolutionary architecture - improve incrementally, validate with users, avoid big bang rewrites.

---

## Appendix: Terminology Glossary

| Term | Definition | Current Implementation |
|------|------------|----------------------|
| **Trading Signal** | Complete trading decision (may span ENTRY + multiple EXITs) | No single document (conceptual only) |
| **Signal Leg** | Individual action within a signal (ENTRY, EXIT, etc.) | Stored as separate documents in `signal_store` |
| **Signal ID** | Unique identifier from TradingView (e.g., `sig_spy_001`) | Field: `signal_id` |
| **Leg ID** | Unique identifier for a leg (e.g., `sig_spy_001__entry`) | Proposed: `leg_id` field |
| **Order** | Execution instruction sent to broker | Stored in `execution.orders[]` |
| **Fill** | Partial or full order execution | Stored in `execution.orders[].fills[]` |
| **Position** | Lifecycle state of a trading signal (OPEN/CLOSED) | Stored in `position` subdocument of ENTRY leg |

---

## References

- [Fix P&L Duplication Issue](./Fix_PnL_Duplication_Issue.md) - Must be implemented first
- [Real-Time Balance Tracking Plan](../.claude/plans/synthetic-discovering-sundae.md) - Related work
- Signal Ingestion Service - `services/signal_ingestion_service/`
- Cerebro Service - `services/cerebro_service/`
- Execution Service - `services/execution_service/`
