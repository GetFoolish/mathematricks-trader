# Trading Modes

This document explains the three trading modes supported by the Mathematricks Trading System.

## Overview

The system supports three modes to enable safe testing and progressive deployment:

| Mode | Market Data | Order Execution | Risk | Use Case |
|------|-------------|-----------------|------|----------|
| **paper_mock** | Mock/Fake | Mock (instant fill) | Zero | Development, unit testing |
| **paper_live** | Real/Live | Mock (instant fill) | Zero | Strategy testing with real market conditions |
| **live** | Real/Live | Real broker | **REAL MONEY** | Production trading |

---

## Mode Descriptions

### 1. paper_mock

**Market Data**: Mock/simulated prices  
**Order Execution**: Mock broker (instant fills at mock prices)  
**Balance Updates**: Mock (simulated)

**When to Use**:
- Development and debugging
- Unit/integration testing
- Testing strategies without market connectivity
- Weekend/after-hours testing when markets are closed

**Advantages**:
- No external dependencies (no IB Gateway needed)
- Works 24/7, even when markets are closed
- Completely deterministic behavior
- Fast iteration

**Limitations**:
- Prices are fake - don't reflect real market conditions
- No spread, slippage, or realistic fill behavior
- Can't test market data issues

**Configuration**:
```javascript
{
  "account_id": "Mock_Paper",
  "mode": "paper_mock",
  "broker": "Mock",
  "market_data_type": 4  // Mock/delayed data (not used in mock mode)
}
```

---

### 2. paper_live (Recommended for Testing)

**Market Data**: Real/live from broker (IBKR, Binance, etc.)  
**Order Execution**: Mock broker (instant fills at real market prices)  
**Balance Updates**: Mock (simulated)

**When to Use**:
- Testing strategies with real market data
- Validating order flow during market hours
- Testing market data quality (spreads, latency, connectivity)
- Pre-production validation
- **Tuesday market testing** ← Current focus

**Advantages**:
- Real market prices, spreads, and volatility
- Zero financial risk (orders not sent to real broker)
- Fast fills (mock broker executes instantly)
- Realistic testing environment
- Can test market data issues (nan prices, stale data, wide spreads)

**Limitations**:
- Requires broker connection (IB Gateway for IBKR)
- Only works during market hours for stock market
- Mock fills don't reflect real slippage/rejection scenarios

**Configuration**:
```javascript
{
  "account_id": "IBKR-TESTING-ACCOUNT",
  "mode": "paper_live",
  "broker": "IBKR",
  "market_data_type": 1,  // Live market data
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4002,  // IB Gateway Paper Trading port
    "client_id": 1
  }
}
```

**How It Works**:
1. Signal arrives → Cerebro processes it
2. Cerebro creates orders using real market data from IBKR
3. Execution service routes order to **BrokerModeAdapter**
4. Mode adapter:
   - Fetches **real price** from IBKR (via `get_market_price()`)
   - Enriches order with real price
   - Sends enriched order to **Mock broker** (not IBKR!)
5. Mock broker instantly fills order at real price
6. Position tracking updated in MongoDB
7. No real money at risk

**Logs to Watch**:
```
📊 Market data for AAPL: mid=$230.50, bid=$230.48, ask=$230.52, spread=$0.04 (0.017%), age=120ms
📈 [paper_live] Enriched BUY AAPL order: price=$230.50 (from real broker), quantity=1
✅ ORDER COMPLETED: AAPL | Filled: 1 @ $230.50 | Status: FILLED
```

---

### 3. live (Production)

**Market Data**: Real/live from broker  
**Order Execution**: Real broker (actual fills, commissions, slippage)  
**Balance Updates**: Real (from broker account)

**When to Use**:
- Production trading with real money
- **Only after extensive testing in paper_live mode**

**Advantages**:
- Actual trading results
- Real fill behavior (slippage, partial fills, rejections)
- Real commissions and fees

**Risks**:
- **REAL MONEY AT RISK**
- Order mistakes can result in financial loss
- Cannot undo executed trades

**Safety Features**:
1. **Environment Flag Required**:
   - Must set `ALLOW_LIVE_TRADING=true` in `.env`
   - Default is `false` (blocks live trading)

2. **Critical Logging**:
   ```
   ⚠️⚠️⚠️ LIVE MODE ORDER ⚠️⚠️⚠️
     Order ID: order_123
     Instrument: AAPL
     Action: BUY
     Quantity: 100
     Account: IBKR-LIVE-ACCOUNT
     ⚠️ REAL MONEY AT RISK ⚠️
   ```

3. **Telegram Alerts**: All live orders trigger Telegram notifications

**Configuration**:
```javascript
{
  "account_id": "IBKR-LIVE-ACCOUNT",
  "mode": "live",
  "broker": "IBKR",
  "market_data_type": 1,
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4001,  // IB Gateway LIVE port (not 4002!)
    "client_id": 1
  }
}
```

**Pre-Deployment Checklist**:
- [ ] Extensively tested in `paper_live` mode
- [ ] Validated order flow end-to-end
- [ ] Confirmed market data quality
- [ ] Set position size limits
- [ ] Configured Telegram alerts
- [ ] Set `ALLOW_LIVE_TRADING=true` in `.env`
- [ ] Triple-check IB Gateway port (4001 for live, 4002 for paper)
- [ ] Start with small position sizes

---

## Mode Switching

### How to Change Modes

**Via MongoDB**:
```javascript
db.trading_accounts.updateOne(
  { account_id: "IBKR-TESTING-ACCOUNT" },
  { 
    $set: { 
      mode: "paper_live",
      market_data_type: 1
    } 
  }
)
```

**Important**: Restart services after mode changes:
```bash
docker restart mathematricks-trader-cerebro-service-1
docker restart mathematricks-trader-execution-service-1
```

### Transition Path

**Recommended progression for new strategies**:

```
paper_mock → paper_live → live
   ↓            ↓           ↓
Development  Testing   Production
```

1. **paper_mock**: Develop and debug strategy logic
2. **paper_live**: Test with real market data during market hours
3. **live**: Deploy to production with small position sizes

---

## Architecture

### BrokerModeAdapter

The `BrokerModeAdapter` class (in `services/brokers/adapters/mode_adapter.py`) implements the mode logic:

```python
class BrokerModeAdapter:
    def __init__(self, mode: str, real_broker, mock_broker):
        self.mode = mode  # "paper_mock", "paper_live", or "live"
        self.real_broker = real_broker  # IBKR, Binance, etc.
        self.mock_broker = mock_broker  # MockBroker
    
    def place_order(self, order: Dict) -> Dict:
        if self.mode == "live":
            # Real money - send to real broker
            return self.real_broker.place_order(order)
        
        elif self.mode == "paper_live":
            # Enrich with real pricing, send to mock
            enriched_order = self._enrich_with_real_pricing(order)
            return self.mock_broker.place_order(enriched_order)
        
        elif self.mode == "paper_mock":
            # Use mock pricing
            return self.mock_broker.place_order(order)
```

### Market Data Flow

**paper_live mode**:
```
Signal → Cerebro → Create Order → Execution Service
                                        ↓
                                  BrokerModeAdapter
                                        ↓
                          ┌─────────────┴─────────────┐
                          ↓                           ↓
                    Real Broker                  Mock Broker
                  (get_market_price)           (place_order)
                          ↓                           ↓
                   Real price: $230.50         Fill at $230.50
                          └─────────────┬─────────────┘
                                        ↓
                                MongoDB (position tracking)
```

---

## Market Data Types (IBKR-specific)

When using IBKR as the real broker, `market_data_type` determines data quality:

| Type | Name | Subscription | Cost | paper_live Use |
|------|------|--------------|------|----------------|
| 1 | Live | Required | $$$ | **Yes** - real-time data |
| 2 | Frozen | No | Free | No - outdated |
| 3 | Delayed | No | Free | Fallback if type 1 fails |
| 4 | Delayed Frozen | No | Free | Last resort |

**Current Implementation**: Smart fallback (1 → 3 → 4)

The system automatically falls back to delayed data if live data is unavailable (e.g., no market data subscription).

---

## Best Practices

### For Development (paper_mock)
- Use for rapid iteration
- Test edge cases and error handling
- Run unit/integration tests

### For Testing (paper_live)
- **Always test during market hours** (9:30 AM - 4:00 PM ET for stocks)
- Start with high-liquidity symbols (SPY, AAPL, QQQ)
- Monitor spreads and data quality
- Run pre-flight checks before testing
- Use cleanup scripts between test sessions

### For Production (live)
- **Never skip paper_live testing**
- Start with minimum position sizes
- Monitor initial trades closely
- Have kill switch ready (can change mode back to paper_live)
- Monitor Telegram alerts
- Keep detailed logs

---

## Troubleshooting

### "nan" Prices in paper_live

**Symptom**: Logs show `bid=nan, ask=nan, last=nan`

**Causes**:
1. Markets are closed (weekend, after-hours, holiday)
2. No market data subscription (need live data subscription for type 1)
3. Symbol not supported by broker
4. IB Gateway not connected

**Solutions**:
1. Check market hours: 9:30 AM - 4:00 PM ET (weekdays)
2. Verify IB Gateway is running: `docker logs mathematricks-trader-execution-service-1`
3. Check market data subscription in IBKR account
4. Use high-liquidity symbols (AAPL, SPY, QQQ)

### Mode Not Taking Effect

**Solution**: Restart services after changing mode in MongoDB:
```bash
docker restart mathematricks-trader-cerebro-service-1
docker restart mathematricks-trader-execution-service-1
```

### Orders Not Executing in paper_live

**Check**:
1. Cerebro service logs: `docker logs mathematricks-trader-cerebro-service-1`
2. Execution service logs: `docker logs mathematricks-trader-execution-service-1`
3. Signal processing log: `tail -f logs/signal_processing.log`
4. Look for "paper_live" in logs (confirms mode is active)

---

## See Also

- [IBKR Integration Summary](../IBKR_INTEGRATION_SUMMARY.md)
- [Execution Service Documentation](../execution_service.md)
- [Account Data Service Documentation](../account_data_service.md)
