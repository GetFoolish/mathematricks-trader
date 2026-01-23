# Architecture Change: Trading Orders Consolidation

## Overview
**Date**: January 23, 2026  
**Status**: Implemented

## Summary
Eliminated the `trading_orders` collection and consolidated all order data into the `signal_store` collection. All signal-related data (raw signal, cerebro decision, orders, execution) is now stored in a single document per signal.

## Motivation
1. **Simplification**: Single source of truth for all signal data
2. **Performance**: Reduced database queries and joins
3. **Lag Tracking**: Simplified timing analysis with all data in one place
4. **Maintainability**: Easier to reason about data flow

## Changes

### 1. Schema Updates

#### signal_store Collection
Added new fields to each leg:
```javascript
{
  legs: [
    {
      leg_id: "sig_xxx__entry_0",
      leg_type: "ENTRY",
      leg_index: 0,
      
      // NEW: Processing timestamps
      processing_timestamps: {
        signal_received: ISODate,              // When raw signal was received
        signal_ingestion_processed: ISODate,   // When signal_ingestion created leg
        cerebro_processed: ISODate,            // When cerebro made decision
        execution_started: ISODate,            // When execution service started
        execution_completed: ISODate           // When execution completed
      },
      
      // NEW: Calculated lag information
      processing_lag: {
        service_lags: {
          signal_ingestion: 0.5,  // ms
          cerebro: 120.3,          // ms
          execution: 45.2          // ms
        },
        total_lag_ms: 170.1,             // End-to-end time
        sum_of_service_lags_ms: 166.0,   // Sum of individual services
        unaccounted_lag_ms: 4.1,         // Network/queue overhead
        stages: [...],
        summary: "signal_ingestion (0.5ms) → cerebro (120.3ms) → execution (45.2ms) | Total: 170.1ms (unaccounted: 4.1ms)"
      },
      
      // Existing fields
      raw: {...},
      decision: {...},
      
      // UPDATED: Execution now includes full order details
      execution: {
        status: "FILLED",
        orders: [                    // All orders for this leg (previously in trading_orders)
          {
            order_id: "sig_xxx_fund1_IBKR_ORD",
            broker_order_id: "12345",
            fund_id: "fund1",
            account_id: "IBKR_MAIN",
            quantity_requested: 100,
            quantity_filled: 100,
            avg_fill_price: 150.25,
            filled_at: ISODate,
            fills: [...]
          }
        ],
        total_quantity_filled: 100,
        weighted_avg_price: 150.25,
        total_cost_basis: 15025.00
      }
    }
  ]
}
```

### 2. Service Changes

#### Signal Ingestion Service
- ✅ Adds `processing_timestamps.signal_received` and `processing_timestamps.signal_ingestion_processed` when creating legs
- No other changes required

#### Cerebro Service
- ✅ Adds `processing_timestamps.cerebro_processed` when making decision
- ✅ **REMOVED**: `trading_orders_collection.insert_one()` calls
- ✅ **CHANGED**: Calls execution service API with full order data (not just order_id)

#### Execution Service
- ✅ **REMOVED**: All `trading_orders_collection` reads and writes
- ✅ **CHANGED**: Receives order data directly from cerebro (not from database)
- ✅ Adds `processing_timestamps.execution_started` and `processing_timestamps.execution_completed`
- ✅ Stores all order data in `signal_store.legs[].execution.orders[]`
- ✅ Calculates and stores `processing_lag` using lag_calculator utility

#### New Utility: lag_calculator.py
- Calculates individual service lags
- Calculates total end-to-end lag
- Identifies unaccounted lag (network, queueing overhead)
- Generates human-readable summary

### 3. Frontend Changes

#### New Component: ProcessingLagDisplay.tsx
- Displays service-by-service timing breakdown
- Shows total lag and unaccounted lag
- Color-codes lag values (green < 10ms, yellow < 100ms, orange < 1s, red >= 1s)
- Compact and expanded views

#### ActivityNew.tsx Updates
- ✅ Imports ProcessingLagDisplay component
- ✅ Added timing section to leg expansion
- ✅ Shows execution orders inline (previously in trading-orders tab)
- ⚠️ **TODO**: Remove or repurpose trading-orders tab

### 4. API Changes Required
- ⚠️ **TODO**: Update API endpoints to remove trading_orders queries
- ⚠️ **TODO**: Update /api/v1/trading-orders endpoint or remove it

## Migration Notes

### Database Migration
**No migration required** for existing data:
- Old `trading_orders` documents can be left in place (not used)
- New signals will automatically use the new schema
- To clean up: `db.trading_orders.drop()` (after verification)

### Testing
Run signal tests to verify:
```bash
./.venv/bin/python tests/run_test_suite.py --clean --signal-testing --mode mock_mock --signal_count 2
```

Expected results:
- ✅ Signals processed successfully
- ✅ `processing_timestamps` populated in signal_store legs
- ✅ `processing_lag` calculated and stored
- ✅ No documents created in trading_orders
- ✅ All order data in signal_store.legs[].execution.orders

## Benefits

### Performance
- **Fewer database queries**: Single document read instead of joining multiple collections
- **Atomic updates**: All signal data updates happen in one collection
- **Better caching**: Frontend can cache entire signal state in one object

### Maintainability
- **Single source of truth**: All signal data in one place
- **Simpler debugging**: Check one document to see entire signal lifecycle
- **Clearer data flow**: Raw signal → Decision → Execution all in same doc

### Observability
- **Built-in timing**: Every signal has complete timing breakdown
- **Lag analysis**: Easy to identify bottlenecks
- **Audit trail**: Complete history in one document

## Rollback Plan
If issues arise:
1. Revert cerebro to create trading_orders documents
2. Revert execution service to read from trading_orders
3. Frontend will continue to work (reads from signal_store OR trading_orders)

## Next Steps
1. ✅ Test with mock_mock signals
2. ⚠️ Test with mock_live signals (IBKR paper)
3. ⚠️ Update API endpoints to remove trading_orders
4. ⚠️ Remove or repurpose trading-orders tab in frontend
5. ⚠️ Drop trading_orders collection after verification
6. ⚠️ Update all documentation

## Files Modified

### Backend
- `services/signal_ingestion/mongodb_watcher.py`
- `services/cerebro_service/cerebro_main.py`
- `services/execution_service/execution_main.py`
- `services/common/lag_calculator.py` (new)

### Frontend
- `frontend-admin/src/components/ProcessingLagDisplay.tsx` (new)
- `frontend-admin/src/pages/ActivityNew.tsx`

### Documentation
- `ARCHITECTURE_FIX_CHANGE_STREAMS.md` (this file)
