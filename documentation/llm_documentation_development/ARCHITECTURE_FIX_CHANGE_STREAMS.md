# Architecture Fix: Change Streams → Direct API Calls

## Summary of Changes

**Date:** January 23, 2026  
**Problem:** Infinite loops and 60+ second delays caused by MongoDB Change Streams triggering recursive signal processing  
**Solution:** Replace Change Streams with direct HTTP API calls for a linear, predictable flow

## Changes Made

### 1. Cerebro Service (`cerebro_main.py`)

#### Removed:
- `watch_signals()` function (MongoDB Change Stream watcher)
- Change Stream pipeline and reconnection logic
- Infinite loop that watched for signal_store updates

#### Added:
- **FastAPI HTTP server** running on port 8082
- **Health endpoints:**
  - `GET /health` - Health check
  - `GET /status` - Detailed status with signal counts
- **Process Signal endpoint:**
  - `POST /api/v1/process-signal`
  - Accepts: `{"signal_store_id": "...", "leg_index": 0}`
  - Fetches signal from MongoDB
  - Calls existing `process_signal_with_constructor()` function
  - Returns status and created orders
- **Execution API calls:**
  - After creating each order in `trading_orders` collection
  - Makes HTTP POST to `http://execution-service:8083/api/v1/execute-order`
  - Passes `{"order_id": "..."}`
  - Graceful error handling (order saved even if API call fails)

#### Updated Main:
```python
# Before: watch_signals() (blocking infinite loop)
# After: run_fastapi_server() (blocking HTTP server)
```

### 2. Execution Service (`execution_main.py`)

#### Removed:
- `watch_trading_orders()` function (MongoDB Change Stream watcher)
- Change Stream thread startup in main
- `service_status['change_stream_connected']` flag

#### Added:
- **Execute Order endpoint:**
  - `POST /api/v1/execute-order`
  - Accepts: `{"order_id": "..."}`
  - Fetches order from MongoDB
  - Checks if already processed (deduplication)
  - Adds to order queue for execution
  - Returns status (queued/already_processed)

#### Updated Main:
```python
# Before: Thread for watch_trading_orders()
# After: Direct API calls from cerebro, orders queued via HTTP
```

### 3. Signal Ingestion (`mongodb_watcher.py`)

#### Added:
- **Cerebro API call after leg insertion:**
  - After inserting/updating `signal_store` document
  - Makes HTTP POST to `http://cerebro-service:8082/api/v1/process-signal`
  - Passes `{"signal_store_id": "...", "leg_index": 0}`
  - 30-second timeout
  - Graceful error handling (signal saved even if API call fails)

#### Imports Added:
```python
import os
import requests
```

### 4. Docker Configuration (`docker-compose.yml`)

#### Cerebro Service:
- **Added port:** `8082:8082` (HTTP API endpoint)
- **Added env var:** `EXECUTION_SERVICE_URL=http://execution-service:8083`

#### Signal Ingestion Service:
- **Added env var:** `CEREBRO_SERVICE_URL=http://cerebro-service:8082`

## New Signal Flow (Linear)

```
1. trading_signals_raw (external input)
   ↓ (Change Stream - ONLY external input uses this)
2. signal_ingestion.mongodb_watcher
   ↓ (writes to signal_store)
3. signal_ingestion → HTTP POST → cerebro:8082/api/v1/process-signal
   ↓ (cerebro processes signal)
4. cerebro → writes to trading_orders collection
   ↓ (cerebro makes API call)
5. cerebro → HTTP POST → execution:8083/api/v1/execute-order
   ↓ (execution processes order)
6. execution → places order with broker
```

## Before vs After

### Before (Broken):
```
signal_ingestion → signal_store
                     ↓ (Change Stream fires)
                   cerebro processes
                     ↓ (writes decision)
                   Change Stream fires AGAIN ❌
                     ↓
                   cerebro processes AGAIN (infinite loop)
```

### After (Fixed):
```
signal_ingestion → signal_store → HTTP POST → cerebro (processes once) ✅
                                                  ↓
                                               trading_orders → HTTP POST → execution ✅
```

## Benefits

1. **No infinite loops** - Each signal processed exactly once
2. **No duplicate processing** - Linear flow with clear handoffs
3. **Fast processing** - Should complete in <1 second (was 60+ seconds)
4. **Debuggability** - Clear HTTP request/response logs
5. **Reliability** - Graceful error handling, can retry failed API calls
6. **Monitoring** - Health endpoints show service status

## Testing

### Start Services:
```bash
docker-compose up --build cerebro-service execution-service signal-ingestion
```

### Run Test:
```bash
./.venv/bin/python tests/run_test_suite.py --clean --signal-testing --mode mock_mock --signal_count 4
```

### Expected Results:
- **Processing time:** ~10-15 seconds (was 60+ seconds)
- **No duplicate logs** - Each signal processed once
- **Clean linear flow** - Logs show: Ingestion → Cerebro API → Execution API → Broker
- **No Change Stream explosions** - No multiple processing at same millisecond

### Check Health:
```bash
# Cerebro health
curl http://localhost:8082/health

# Execution health  
curl http://localhost:8083/health
```

## Rollback Plan

If issues occur, revert these files:
1. `services/cerebro_service/cerebro_main.py`
2. `services/execution_service/execution_main.py`
3. `services/signal_ingestion/mongodb_watcher.py`
4. `docker-compose.yml`

Commit hash before changes: [git log to find]

## Next Steps

1. ✅ Test with mock_mock mode (fast, safe)
2. ✅ Verify no duplicate processing
3. ✅ Check logs for clean linear flow
4. 🔄 Test with mock_live mode (real market data)
5. 🔄 Monitor for 24 hours in staging
6. 🔄 Deploy to production

## Architecture Decision Record

**Decision:** Replace MongoDB Change Streams with direct HTTP API calls for inter-service communication

**Rationale:**
- Change Streams are designed for **external consumers** watching database changes
- When services write to DB → trigger Change Stream → process → write to DB again, it creates infinite loops
- Direct API calls provide explicit, controlled flow with better error handling and monitoring

**Trade-offs:**
- ✅ **Pro:** Predictable linear flow, no infinite loops, faster processing
- ✅ **Pro:** Better error handling (HTTP status codes, retries)
- ✅ **Pro:** Health monitoring via HTTP endpoints
- ⚠️ **Con:** More code (API endpoints vs simple Change Stream watch)
- ⚠️ **Con:** Network latency (HTTP vs internal MongoDB Change Stream)
  - *Mitigation:* Services run in same Docker network, latency negligible

**Conclusion:** The trade-offs heavily favor direct API calls for reliability and debuggability. Network latency is negligible within Docker network.
