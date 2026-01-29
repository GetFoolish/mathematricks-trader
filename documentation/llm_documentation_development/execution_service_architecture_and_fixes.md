# Execution Service Architecture & Fixes

**Document Purpose**: Define the architecture for execution-service broker initialization and list all tasks needed to make mock_mock, mock_live, and paper_live modes fully functional.

**Date**: January 28, 2026  
**Status**: Planning Phase

---

## Trading Modes Overview

The system supports four trading modes:

| Mode | Data Source | Broker Execution | External Dependencies | Use Case |
|------|-------------|------------------|----------------------|----------|
| **mock_mock** | Mock/Fake | Mock (instant) | None | Development, testing without any external services |
| **mock_live** | Live (IB Gateway) | Mock (instant) | IB Gateway (for data) | Strategy testing with real market data, zero risk |
| **paper_live** | Live (IB Gateway) | Paper (IB Paper) | IB Gateway (for data + execution) | Pre-production testing with IBKR paper account |
| **live_live** | Live (IB Gateway) | Live (IB Live) | IB Gateway (for data + execution) | Production trading, REAL MONEY |

### Key Insights:
- **mock_mock**: No IB Gateway needed - completely standalone
- **mock_live**: Requires IB Gateway for live market data, but executes on mock broker
- **paper_live**: Requires IB Gateway for both data and paper trading execution
- **live_live**: Requires IB Gateway for both data and live trading execution

---

## Current Problems

### Problem 1: Broker Pool Initialization Race Condition
**Symptom**: Orders arriving in first 60 seconds after execution-service restart get rejected with "No broker found for account"

**Root Cause**:
1. `initialize_broker_pool()` is called at module level (line 847 in execution_main.py)
2. Function waits for IB Gateway health checks (60s timeout)
3. FastAPI starts serving HTTP requests immediately in background thread
4. Orders can arrive before `broker_pool` is populated

**Timeline Evidence** (from logs):
```
14:20:11 - ORDER RECEIVED (MSFT) → REJECTED "No broker found"
14:20:17 - ORDER RECEIVED (TSLA) → REJECTED "No broker found"
14:20:19 - Gateway health check timeout, Broker pool initialized
14:20:23 - ORDER RECEIVED (AAPL) → Would succeed (pool ready)
```

**Impact**:
- ❌ mock_mock mode fails (shouldn't need gateway but waits for it anyway)
- ❌ mock_live mode fails during initialization window
- ❌ paper_live mode fails during initialization window
- Production deployment risk: orders rejected after service restarts

---

### Problem 2: Mode-Agnostic Initialization
**Symptom**: All modes wait for IB Gateway, even mock_mock which doesn't need it

**Root Cause**: Current initialization logic doesn't differentiate between broker types:
```python
# Current code - waits for ALL gateways regardless of mode
wait_for_gateways_ready()  # 60s timeout
initialize_broker_pool()   # Creates all brokers
```

**What Should Happen**:
- **mock_mock**: Instant startup (no external dependencies)
- **mock_live**: Wait for IB Gateway (needs live data source)
- **paper_live**: Wait for IB Gateway (needs data + execution)
- **live_live**: Wait for IB Gateway (needs data + execution)

---

### Problem 3: Broker Classification Confusion
**Current Issue**: No clear categorization of broker types by their external dependencies

**Broker Types by Dependency**:

1. **Pure Python (Instant)**:
   - Mock broker
   - No external services needed
   - Instantiation: <1ms

2. **REST API (Fast)**:
   - Binance, Alpaca, etc.
   - HTTP connection establishment
   - Instantiation: 1-5 seconds

3. **External Container (Slow)**:
   - IBKR (via IB Gateway)
   - Separate Docker container with 60s startup
   - Health checks required before connection
   - Instantiation: 60+ seconds

**Problem**: Current code doesn't distinguish between these categories

---

## Proposed Architecture

### Architecture: FastAPI Lifespan with Mode-Aware Initialization

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: Initialize brokers based on account modes
    Shutdown: Clean up broker connections
    """
    logger.info("🚀 Execution Service Starting...")
    
    # Determine which modes are active
    active_modes = get_active_trading_modes()
    
    # Phase 1: Instant brokers (mock_mock)
    if 'mock_mock' in active_modes:
        initialize_mock_brokers()  # Instant
        logger.info("✅ Mock brokers ready")
    
    # Phase 2: Wait for IB Gateway (if needed)
    if any(mode in active_modes for mode in ['mock_live', 'paper_live', 'live_live']):
        logger.info("⏳ Waiting for IB Gateway (needed for live data/execution)...")
        await wait_for_gateways_ready()  # 60s timeout
        logger.info("✅ IB Gateway ready")
        
        # Initialize IBKR brokers
        initialize_ibkr_brokers()
    
    # Phase 3: REST API brokers (lazy init on first use)
    # Binance, Alpaca, etc. - initialized on-demand
    
    logger.info(f"🎯 Execution Service Ready - Active modes: {active_modes}")
    
    yield  # FastAPI starts accepting requests NOW
    
    # Shutdown
    logger.info("🛑 Shutting down execution service...")
    cleanup_broker_pool()

app = FastAPI(lifespan=lifespan)
```

### Flow for Each Mode:

**mock_mock Mode**:
```
Service Start → Initialize mock broker (instant) → FastAPI ready (<1s)
                     ↓
               No IB Gateway needed
```

**mock_live Mode**:
```
Service Start → Wait for IB Gateway (60s) → Initialize IBKR connection (for data)
                                                  ↓
                                            Initialize mock broker (for execution)
                                                  ↓
                                            FastAPI ready (~60s)
```

**paper_live Mode**:
```
Service Start → Wait for IB Gateway (60s) → Initialize IBKR Paper broker
                                                  ↓
                                            FastAPI ready (~60s)
```

---

## Implementation Task List

### Phase 1: Core Architecture Refactor ✅ COMPLETED
**Goal**: Fix initialization race condition and support mode-aware startup

- [x] **Task 1.1**: Add `get_active_trading_modes()` function
  - IMPLEMENTED: Uses existing `load_gateway_config()` from gateway_config.yml
  - Returns list of account IDs to initialize

- [x] **Task 1.2**: Implement FastAPI lifespan context manager
  - IMPLEMENTED: `@asynccontextmanager async def lifespan(app: FastAPI)`
  - Moved initialization logic into lifespan startup phase
  - Ensures brokers ready BEFORE FastAPI accepts HTTP requests

- [x] **Task 1.3**: Create mode-aware initialization logic
  - IMPLEMENTED: Uses config-driven approach via gateway_config.yml
  - Initialization happens in lifespan, blocking FastAPI startup
  - IB Gateway containers automatically stopped on shutdown, recreated on startup

- [x] **Task 1.4**: Update `wait_for_gateways_ready()` 
  - Already implemented - only runs when IBKR accounts present
  - 60s timeout with health checks

- [x] **Task 1.5**: IB Gateway lifecycle management
  - Shutdown phase: Stops all `ib-gateway-*` containers
  - Startup phase: Recreates containers based on gateway_config.yml
  - Makes IB Gateway containers behave like "children" of execution-service

---

### Phase 2: Broker Pool Management
**Goal**: Properly manage broker lifecycle and state

- [ ] **Task 2.1**: Add broker state tracking
  - Track broker connection state: INITIALIZING, CONNECTED, DISCONNECTED, FAILED
  - Store state in `broker_pool_state` dict: `{account_name: state}`
  - Update state throughout initialization and operation

- [ ] **Task 2.2**: Create broker classification constants
  ```python
  INSTANT_BROKERS = {'mock'}
  IBKR_MODES = {'mock_live', 'paper_live', 'live_live'}
  REST_API_BROKERS = {'binance', 'alpaca'}  # Future
  ```

- [ ] **Task 2.3**: Implement proper broker instantiation per mode
  - **mock_mock**: Create MockBroker only, no IBKR connection
  - **mock_live**: Create IBKR connection (data) + MockBroker (execution)
  - **paper_live**: Create IBKR Paper connection (data + execution)
  - **live_live**: Create IBKR Live connection (data + execution)

- [ ] **Task 2.4**: Add broker cleanup on shutdown
  - Disconnect IBKR connections gracefully
  - Cancel pending orders
  - Log cleanup operations

---

### Phase 3: Health & Readiness Checks
**Goal**: Provide accurate service state information

- [ ] **Task 3.1**: Update `/health` endpoint
  - Keep simple: just checks if service is alive
  - Return `{"status": "healthy"}` if process is running

- [ ] **Task 3.2**: Create `/readiness` endpoint
  - Per-account readiness state
  - Return broker connection status
  ```json
  {
    "ready": true,
    "brokers": {
      "Mock_Paper": {"ready": true, "state": "CONNECTED", "mode": "mock_mock"},
      "IBKR-TESTING-ACCOUNT": {"ready": true, "state": "CONNECTED", "mode": "mock_live"},
      "IBKR-PAPER-ACCOUNT": {"ready": false, "state": "INITIALIZING", "mode": "paper_live"}
    }
  }
  ```

- [ ] **Task 3.3**: Create `/broker-status` endpoint
  - Detailed broker information
  - Connection details, last heartbeat, error messages
  - Useful for debugging connectivity issues

---

### Phase 4: Error Handling & Logging
**Goal**: Clear visibility into initialization and execution state

- [ ] **Task 4.1**: Enhanced startup logging
  ```
  🚀 Execution Service Starting...
  📋 Active modes detected: mock_mock, mock_live
  ⚡ Initializing mock brokers... Done (0.001s)
  ⏳ Waiting for IB Gateway (needed for mock_live)...
  ✅ IB Gateway ready (60.2s)
  🔌 Connecting to IBKR for mock_live mode...
  ✅ IBKR connection established
  🎯 Execution Service Ready - All brokers initialized
  ```

- [ ] **Task 4.2**: Improve rejection messages
  - Current: "No broker found for account IBKR-TESTING-ACCOUNT"
  - Better: "Broker for IBKR-TESTING-ACCOUNT not ready (state: INITIALIZING, retry in 30s)"

- [ ] **Task 4.3**: Add startup failure handling
  - If IB Gateway fails to start, log clear error
  - Don't crash service - allow mock_mock accounts to work
  - Set IBKR broker states to FAILED

---

### Phase 5: Testing & Validation
**Goal**: Verify all modes work correctly

- [ ] **Task 5.1**: Test mock_mock mode
  - Verify instant startup (no gateway wait)
  - Send test signal, confirm execution
  - Check logs for clean initialization

- [ ] **Task 5.2**: Test mock_live mode
  - Verify gateway wait occurs
  - Verify IBKR connection for data
  - Send test signal with live data
  - Confirm mock execution at live price

- [ ] **Task 5.3**: Test paper_live mode
  - Verify gateway wait occurs
  - Verify IBKR Paper broker connection
  - Send test signal
  - Confirm paper execution through IBKR

- [ ] **Task 5.4**: Test service restart scenarios
  - Restart execution-service while IB Gateway running
  - Restart both services simultaneously
  - Verify no orders rejected during initialization

- [ ] **Task 5.5**: Test health/readiness endpoints
  - Check `/health` during initialization
  - Check `/readiness` during initialization
  - Verify accurate broker states

---

### Phase 6: Documentation Updates
**Goal**: Keep documentation synchronized with implementation

- [ ] **Task 6.1**: Update execution_service.md
  - Document new lifespan-based initialization
  - Explain mode-aware startup behavior
  - Add troubleshooting section for initialization issues

- [ ] **Task 6.2**: Update trading_modes.md
  - Correct mode names (mock_mock, mock_live, paper_live, live_live)
  - Clarify IB Gateway requirements per mode
  - Update configuration examples

- [ ] **Task 6.3**: Create broker_initialization.md
  - Document broker pool architecture
  - Explain state tracking
  - Provide troubleshooting guide

---

## Testing Plan

### Test Scenario 1: mock_mock Mode (No Gateway)
**Setup**:
- Stop IB Gateway: `docker stop mathematricks-trader-ib-gateway-1`
- Configure account with mode: `mock_mock`
- Restart execution service

**Expected Behavior**:
- ✅ Service starts in <1 second
- ✅ No "waiting for gateway" logs
- ✅ Mock broker ready immediately
- ✅ Test signal executes successfully

---

### Test Scenario 2: mock_live Mode (With Gateway)
**Setup**:
- Start IB Gateway: `docker start mathematricks-trader-ib-gateway-1`
- Configure account with mode: `mock_live`
- Restart execution service

**Expected Behavior**:
- ✅ Service waits for IB Gateway (60s timeout)
- ✅ IBKR connection established for market data
- ✅ Mock broker created for execution
- ✅ Test signal with `tests/sample_signals/ibkr/tech_stocks_realistic.json`
- ✅ Orders filled at real market prices (from IBKR data)
- ✅ Execution via mock broker (instant, no real orders)

---

### Test Scenario 3: Service Restart During Trading
**Setup**:
- IB Gateway running
- Send signal at T+0s
- Restart execution-service at T+0s
- Send signal at T+30s (during initialization)
- Send signal at T+70s (after initialization)

**Expected Behavior**:
- ✅ Signal at T+30s: Rejected with clear reason "Broker initializing, retry in 30s"
- ✅ Signal at T+70s: Executed successfully
- ✅ All rejections logged to signal_store with rejection_reason
- ✅ Frontend shows rejection reasons

---

## Migration Path

### Current State → Target State

**Current** (Broken):
```python
# Module level - runs immediately
initialize_broker_pool()  # Blocks for 60s
# Meanwhile, FastAPI starts serving requests in background thread
```

**Target** (Fixed):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    modes = get_active_trading_modes()
    
    if 'mock_mock' in modes:
        initialize_mock_brokers()  # Instant
    
    if needs_ibkr_gateway(modes):
        await wait_for_gateways_ready()  # 60s
        initialize_ibkr_brokers()
    
    yield  # NOW FastAPI starts serving
    
    # Shutdown
    cleanup_broker_pool()

app = FastAPI(lifespan=lifespan)
```

---

## Open Questions

1. **REST API Brokers (Future)**:
   - Should Binance/Alpaca initialize eagerly or lazily?
   - Connection time: ~1-5 seconds
   - Recommendation: Lazy initialization on first order

2. **Gateway Restart Coordination**:
   - Should execution-service detect gateway restarts and reconnect?
   - Or should we restart execution-service when gateway restarts?
   - Current: Makefile `restart` restarts both together

3. **Broker Pool State Persistence**:
   - Should we persist broker states to MongoDB?
   - Useful for monitoring across service restarts
   - Or keep in-memory only?

4. **Partial Initialization**:
   - If one IBKR account fails to connect, should we:
     - A) Fail entire service startup?
     - B) Mark that account as FAILED, continue with others?
   - Recommendation: B - allow partial success

---

## Success Criteria

### mock_mock Mode:
- ✅ Service starts in <1 second
- ✅ No IB Gateway dependency
- ✅ Orders execute immediately
- ✅ Works offline, after-hours, weekends

### mock_live Mode:
- ✅ Service starts in ~60 seconds (gateway wait)
- ✅ Real market data from IBKR
- ✅ Mock execution (instant fills)
- ✅ Test with `tests/sample_signals/ibkr/tech_stocks_realistic.json`
- ✅ Zero rejection errors after initialization complete

### paper_live Mode:
- ✅ Service starts in ~60 seconds (gateway wait)
- ✅ Real market data from IBKR
- ✅ Paper trading execution through IBKR
- ✅ Orders appear in IBKR Paper Trading account
- ✅ Zero rejection errors after initialization complete

### All Modes:
- ✅ No orders rejected after initialization complete
- ✅ Clear logging of initialization progress
- ✅ Accurate health/readiness endpoints
- ✅ Proper shutdown cleanup
- ✅ Service restart safe (no race conditions)

---

## Implementation Priority

### P0 (Critical - Blocks Testing):
- Task 1.2: Implement FastAPI lifespan
- Task 1.3: Mode-aware initialization
- Task 2.3: Proper broker instantiation per mode
- Task 4.1: Enhanced startup logging
- Task 5.2: Test mock_live mode

### P1 (Important - Production Safety):
- Task 2.1: Broker state tracking
- Task 3.2: Readiness endpoint
- Task 4.2: Improved rejection messages
- Task 5.4: Test restart scenarios

### P2 (Nice to Have):
- Task 3.3: Broker status endpoint
- Task 6.1-6.3: Documentation updates

---

## Next Steps

1. Review this architecture document
2. Prioritize task list
3. Begin Phase 1 implementation (Core Architecture Refactor)
4. Test mock_live mode with `tech_stocks_realistic.json`
5. Iterate based on test results
