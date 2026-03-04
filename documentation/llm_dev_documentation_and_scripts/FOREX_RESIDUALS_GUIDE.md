# Forex Trading & Currency Residuals Guide

## Problem: Currency Residuals in Forex Trading

When trading forex pairs with a different base currency account, you end up with residual balances in multiple currencies.

### Example Scenario

**Account Base Currency**: CAD  
**Trading Pair**: JPY/CHF  
**Trade Sequence**:

```
1. ENTRY: BUY JPY/CHF 25,000
   → Account: -25,000 JPY (borrowed), +25,000 CHF (bought)
   
2. EXIT: SELL JPY/CHF 25,000  
   → Account: +25,000 JPY (returned), -25,000 CHF (sold)
   
Result: ±0 net position, but now you have JPY and CHF balances instead of CAD
```

## IBKR Forex Mechanics

### How IBKR Handles Forex

Interactive Brokers uses a **multi-currency ledger system**:
- Each currency has its own cash balance
- Forex trades move balances between currencies
- No automatic conversion to base currency
- You maintain balances in multiple currencies

### Base Currency

Your IBKR account has a designated **base currency** (CAD in your case):
- Account value reported in base currency
- P&L calculated in base currency  
- Currency conversions use real-time FX rates
- Margin requirements in base currency

## Solutions

### Solution 1: Trade Against USD (Recommended for CAD Base)

Instead of trading exotic pairs directly, trade each currency against USD, then USD/CAD.

**Original Strategy**: Trade JPY/CHF

**Modified Strategy**:
```
Entry:
1. BUY JPY/USD 25,000  → Get JPY position
2. SELL CHF/USD 25,000 → Get USD from CHF

Exit:
3. SELL JPY/USD 25,000 → Close JPY, get USD
4. BUY CHF/USD 25,000  → Close USD, get CHF back

Cleanup (convert USD to CAD):
5. BUY USD/CAD {net_usd_amount} → Convert USD profits to CAD
```

**Benefits**:
- More liquid (USD pairs have tighter spreads)
- Easier to convert back to CAD base
- Clearer P&L tracking

### Solution 2: Direct Pair + Cleanup Trades

Trade the original pair, then convert residuals back to base currency.

**Strategy**: Trade JPY/CHF with CAD base

```
Entry:
1. BUY JPY/CHF 25,000  → Position opened

Exit:
2. SELL JPY/CHF 25,000 → Position closed (now have JPY + CHF residuals)

Cleanup:
3. SELL JPY/CAD {jpy_balance} → Convert JPY to CAD
4. SELL CHF/CAD {chf_balance} → Convert CHF to CAD
```

**Implementation** (Google Apps Script):

```javascript
// In processSignal function
if (signalType === 'EXIT' && config.instrumentType === 'FOREX') {
  const cleanupSignals = generateForexResidualCleanup(symbol, absoluteQuantity, action);
  
  cleanupSignals.forEach(cleanup => {
    sendSignal({
      ...params,
      symbol: cleanup.instrument,  // e.g., JPY/CAD
      action: cleanup.action,       // SELL (convert to CAD)
      quantity: cleanup.quantity,
      signalType: 'CLEANUP'
    });
  });
}
```

### Solution 3: IBKR Auto FX Conversion (Not Recommended)

IBKR offers automatic FX conversion features, but:
- Less control over execution
- May incur wider spreads
- Harder to track in your system
- **Not recommended** for algorithmic trading

### Solution 4: Keep Multi-Currency Balances

Accept multi-currency balances and only convert periodically:

**Pros**:
- Simplest implementation
- Natural hedging across currencies
- Lower transaction costs

**Cons**:
- Complex accounting
- FX risk on residual balances
- Harder to track true P&L

## Recommended Approach for Your System

### For Google Sheets Strategy (Forex with CAD Base)

**Use Solution 2: Direct Pair + Automatic Cleanup**

1. **Trade the desired pair** (JPY/CHF) as signaled by your developer
2. **On EXIT signals**, automatically generate cleanup trades
3. **Convert residuals to CAD** using XXX/CAD pairs

### Implementation Steps

**1. Update Strategy Configuration**:

```javascript
// In Google Apps Script properties
base_currency: 'CAD'
instrument_type: 'FOREX'
```

**2. Cleanup Logic** (already in template):

```javascript
function generateForexResidualCleanup(baseSymbol, quantity, action) {
  const config = getConfig();
  const baseCurrency = config.baseCurrency;  // CAD
  
  // Parse pair: JPY/CHF → ['JPY', 'CHF']
  const currencies = baseSymbol.split('/');
  const cleanupSignals = [];
  
  currencies.forEach(currency => {
    if (currency === baseCurrency) return;
    
    // Convert foreign currency to base
    cleanupSignals.push({
      instrument: `${currency}/${baseCurrency}`,  // JPY/CAD, CHF/CAD
      action: 'SELL',  // Sell foreign for base
      quantity: Math.abs(quantity),
      signalType: 'CLEANUP'
    });
  });
  
  return cleanupSignals;
}
```

**3. Example Flow**:

```
Developer's Google Sheet Signal: EXIT JPY/CHF 25,000

Auto-generated signals:
1. EXIT JPY/CHF 25,000        (main exit)
2. CLEANUP JPY/CAD 25,000     (convert JPY → CAD)
3. CLEANUP CHF/CAD 25,000     (convert CHF → CAD)

Result: All balances back in CAD
```

## MongoDB Schema for Forex Signals

```javascript
// trading_signals_raw
{
  strategy_name: "FloridaForex",
  signal_type: "EXIT",
  signal_legs: [
    {
      instrument: "JPY/CHF",
      instrument_type: "FOREX",
      action: "SELL",
      direction: "SHORT",
      quantity: 25000,
      order_type: "MARKET",
      price: 0,
      environment: "staging"
    }
  ],
  // ... rest of fields
}

// Auto-generated cleanup signals
{
  strategy_name: "FloridaForex",
  signal_type: "CLEANUP",
  parent_signal_id: "sig_forex_exit_12345",  // Link to parent
  signal_legs: [
    {
      instrument: "JPY/CAD",
      instrument_type: "FOREX",
      action: "SELL",
      direction: "SHORT",
      quantity: 25000,
      order_type: "MARKET",
      environment: "staging"
    }
  ]
}
```

## Testing Procedure

### Phase 1: Paper Trading (paper_live)

```javascript
// Google Sheet settings
Trading Mode: staging
Environment: paper_live
```

Test sequence:
1. Send ENTRY signal for JPY/CHF
2. Verify position opens in IBKR paper account
3. Send EXIT signal
4. Verify cleanup signals automatically generated
5. Check final balances - should be all CAD

### Phase 2: Monitor Currency Balances

```python
# Check IBKR account balances
python scripts/check_currency_balances.py --account IBKR-PAPER

# Expected output after cleanup:
# CAD: 1,000,543.21
# JPY: 0.00
# CHF: 0.00
# USD: 0.00
```

### Phase 3: Production (live_live)

After 1-2 weeks of successful paper trading:

```javascript
// Google Sheet settings
Trading Mode: production
Environment: live_live
```

## Monitoring & Alerts

### Key Metrics to Track

1. **Currency Balance Drift**
   - Alert if non-CAD balance > $1000 for > 24 hours
   - Indicates cleanup trades failed

2. **Cleanup Success Rate**
   - Track: cleanup_signals_sent vs cleanup_trades_filled
   - Target: >99% success rate

3. **FX Conversion Costs**
   - Monitor spreads on XXX/CAD pairs
   - Compare to direct pair spreads

### Dashboard Queries

```javascript
// MongoDB query: Find strategies with currency residuals
db.trading_accounts.aggregate([
  {$match: {account_id: "DEVELOPER_STRATEGY_ACCOUNT"}},
  {$unwind: "$balances.currency_balances"},
  {$match: {
    "balances.currency_balances.currency": {$ne: "CAD"},
    "balances.currency_balances.balance": {$gt: 100}
  }}
])
```

## Common Issues & Solutions

### Issue 1: Cleanup Trades Rejected

**Symptom**: Cleanup signals sent but no fills  
**Cause**: Insufficient balance in currency  
**Solution**: Add balance check before cleanup

```javascript
// Before sending cleanup
const currencyBalance = await getCurrencyBalance(currency);
if (currencyBalance < quantity) {
  Logger.log(`⚠️  Insufficient ${currency} balance for cleanup`);
  // Adjust quantity or skip
}
```

### Issue 2: Large Residual Balances

**Symptom**: Significant non-CAD balances accumulating  
**Cause**: Cleanup signals not executing  
**Solution**: Manual cleanup script

```python
# scripts/forex_cleanup.py
python scripts/forex_cleanup.py --account DEVELOPER_STRATEGY_ACCOUNT --target-currency CAD
```

### Issue 3: Slippage on Cleanup Trades

**Symptom**: Higher costs on XXX/CAD vs main trades  
**Cause**: Lower liquidity in CAD pairs  
**Solution**: Use USD as intermediate (Solution 1)

## Alternative: USD as Intermediate Currency

If CAD pairs have poor liquidity:

```
1. Trade JPY/CHF (main strategy)
2. On EXIT, convert to USD:
   - SELL JPY/USD
   - SELL CHF/USD
3. Keep USD balance (more liquid than CAD)
4. Weekly/monthly: Convert USD → CAD for reporting
```

## Summary

**Recommended for CAD Base Account**:
- Use **Solution 2** (Direct Pair + Cleanup)
- Implement automatic cleanup signals on EXIT
- Convert residuals to CAD via XXX/CAD pairs
- Test thoroughly in paper_live mode first
- Monitor currency balances daily
- Set up alerts for balance drift

**Google Apps Script**: Already configured with `generateForexResidualCleanup()` function

**System Support**: No changes needed - cleanup signals treated as normal signals through the entire pipeline
