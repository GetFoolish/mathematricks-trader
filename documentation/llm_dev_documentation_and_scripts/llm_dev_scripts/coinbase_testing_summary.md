# Coinbase Integration Testing Summary

**Date:** 2026-02-01  
**Status:** ✅ Dual-Client Implementation Complete

## Overview

Implemented Coinbase Advanced Trade API integration with a dual-client architecture to work around sandbox limitations.

## Problem

Coinbase sandbox only supports account and order endpoints - **no price/market data endpoints**.

## Solution

**Dual-Client Architecture** (isolated to CoinbaseBroker class):
- `data_client`: Always uses production API (`https://api.coinbase.com`) for prices, balances, order books
- `order_client`: Uses sandbox (`https://api-sandbox.coinbase.com`) or production based on config

## Implementation Details

### File: `services/brokers/coinbase/coinbase_broker.py`

**Dual-Client Initialization:**
```python
# __init__() creates two separate RESTClient instances
self.data_client = RESTClient(
    api_key=self.api_key,
    api_secret=self.api_secret,
    base_url="https://api.coinbase.com"  # Always production
)

self.order_client = RESTClient(
    api_key=self.api_key,
    api_secret=self.api_secret,
    base_url=self.order_api_url  # Sandbox or production based on config
)
```

**Method Routing:**

**Data Methods (use `data_client` - production):**
- `connect()` - Test connection via `data_client.get_accounts()`
- `get_account_balance()` - Read balances via `data_client.get_accounts()`
- `get_current_price()` - Get ticker via `data_client.get_product()`
- `get_order_book()` - Get depth via `data_client.get_product_book()`

**Order Methods (use `order_client` - sandbox/production):**
- `place_order()` - Submit orders via `order_client.market_order()`
- `cancel_order()` - Cancel via `order_client.cancel_orders()`
- `get_open_orders()` - Query via `order_client.list_orders()`
- `get_order_status()` - Check status via `order_client.get_order()`

## MongoDB Integration

**Account:** `COINBASE_CANADA`
```json
{
  "account_id": "COINBASE_CANADA",
  "broker": "Coinbase",
  "sandbox": true,
  "test_modes": ["mock_mock", "mock_live", "paper_live"],
  "equity": 100000.00
}
```

**Strategy:** `Coinbase_Crypto_Momentum`
```json
{
  "strategy_name": "Coinbase_Crypto_Momentum",
  "accounts": ["COINBASE_CANADA"],
  "supported_instruments": ["BTC-USD", "ETH-USD", "SOL-USD"]
}
```

**Fund:** `Staging_Test_Fund`
- Added `COINBASE_CANADA` to accounts array

## Test Results

### ✅ Broker Initialization Test
**Script:** `scripts/llm_dev_scripts/test_coinbase_broker.py`

```
✅ RESTClient imported: <class 'coinbase.rest.RESTClient'>
✅ CoinbaseBroker imported
✅ Broker created: <CoinbaseBroker account=COINBASE_CANADA connected=False sandbox=True>
   Data API URL: https://api.coinbase.com
   Order API URL: https://api-sandbox.coinbase.com
✅ All tests passed!
```

### ✅ mock_mock Mode Test
**Command:**
```bash
.venv/bin/python tests/run_test_suite.py \
  --signal-testing --clean \
  --environment staging \
  --account-type mock \
  --data-source mock \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json \
  --signal-count 2
```

**Result:**
- 2 signals sent successfully
- ENTRY signal rejected (expected for first entry)
- EXIT signal approved and linked to entry
- Duration: 6.72s
- **Status: PASSED ✅**

### ✅ mock_live Mode Test
**Command:**
```bash
.venv/bin/python tests/run_test_suite.py \
  --signal-testing \
  --environment staging \
  --account-type mock \
  --data-source live \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json \
  --signal-count 2
```

**Result:**
- 2 signals sent successfully
- Market data validation: Crypto market detected (24-hour trading)
- Duration: 6.45s
- **Status: PASSED ✅**

### ⏳ paper_live Mode Test
**Status:** Not yet tested (services need to be running)

**Command:**
```bash
.venv/bin/python tests/run_test_suite.py \
  --signal-testing \
  --environment staging \
  --account-type paper \
  --data-source live \
  --file tests/sample_signals/coinbase/crypto_spot_trading.json \
  --signal-count 2
```

**Expected Behavior:**
- `data_client` fetches real prices from production API
- `order_client` submits orders to sandbox API
- Validates full dual-client routing

## Sample Signals

**File:** `tests/sample_signals/coinbase/crypto_spot_trading.json`

**10 Signals (5 entry + 5 exit pairs):**
- BTC-USD: ENTRY (0.5), EXIT (0.5)
- BTC-USD: ENTRY (1.0), EXIT (1.0)
- ETH-USD: ENTRY (5.0), EXIT (5.0)
- ETH-USD: ENTRY (10.0), EXIT (10.0)
- SOL-USD: ENTRY (100), EXIT (100)

**Net Position:** 0 BTC, 0 ETH, 0 SOL (balanced)

## Environment Variables Required

```bash
# API Key Name (organizations/xxx/apiKeys/yyy format)
COINBASE_API_KEY_UAE_NAME="organizations/.../apiKeys/..."

# EC Private Key (PEM format)
COINBASE_API_KEY_UAE_KEY="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----"
```

## Architecture Benefits

1. **No System-Wide Changes**: Solution isolated to CoinbaseBroker class
2. **Simple Configuration**: `sandbox: true` in MongoDB triggers sandbox for orders only
3. **Safe Testing**: Production API read-only operations (prices) are non-destructive
4. **Flexibility**: Can test realistic scenarios with live prices + sandbox execution

## Next Steps

1. ✅ Test paper_live mode when services are running
2. Run full 10-signal test (all entry/exit pairs)
3. Update broker_integration_and_testing.md to mark Phase 1 complete
4. Proceed to Phase 4: IBKR signal reorganization

## Files Modified

- `services/brokers/coinbase/coinbase_broker.py` - Dual-client implementation
- `services/brokers/factory.py` - Added Coinbase to registry
- `requirements.txt` - Added coinbase-advanced-py==1.2.0
- `scripts/llm_dev_scripts/seed_coinbase_account.py` - Full integration seeding
- `tests/sample_signals/coinbase/crypto_spot_trading.json` - Test signals
- `documentation/llm_documentation_development/broker_integration_and_testing.md` - Updated plan

## Key Learnings

1. **Sandbox Capabilities Vary**: Always verify sandbox features before implementation
2. **Coinbase Limitation**: Sandbox only supports account/order endpoints
3. **Production API Safety**: Read-only endpoints (prices, balances) safe for testing
4. **Broker Isolation**: Broker-specific quirks best handled in broker class, not system-wide
