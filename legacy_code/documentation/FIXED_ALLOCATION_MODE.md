# Fixed Allocation Mode - MaxHybrid Portfolio Constructor

## Overview

The MaxHybrid portfolio constructor now supports **two modes**:

1. **Fixed Allocation Mode** (RECOMMENDED for live trading) ✅
   - Uses pre-calculated allocations from your backtest
   - No re-optimization on every signal
   - Fast and predictable
   - Allocations stay constant until you explicitly update them

2. **Dynamic Optimization Mode** (for research/backtesting)
   - Re-runs full optimization on every signal
   - Uses backtest data from MongoDB
   - Slower (16+ seconds per signal)
   - Allocations may vary between signals

## Current Configuration

**Mode**: FIXED ALLOCATION MODE (enabled by default)

**Configuration File**: `services/cerebro_service/portfolio_allocations.json`

**Current Allocations** (from MaxHybrid backtest 2025-04-10):
```json
{
  "chong_vansh_strategy": 81.91%,
  "SPX_1-D_Opt": 57.79%,
  "Com1-Met": 43.09%,
  "Com3-Mkt": 17.07%,
  "Forex": 13.23%,
  "Com2-Ag": 10.38%,
  "SPY": 6.54%,
  "TLT": 0.0%,
  "Com4-Misc": 0.0%
}
```

**Total Allocation**: 230% (max_leverage = 2.3)

**Expected Metrics** (from backtest):
- Sharpe Ratio: 7.15 (annualized)
- CAGR: 62.46%
- Max Drawdown: -3.21%

---

## How It Works

### Fixed Allocation Mode Flow

```
1. Signal arrives (e.g., "Com4-Misc")
   ↓
2. Cerebro calls MaxHybridConstructor.evaluate_signal()
   ↓
3. Constructor checks use_fixed_allocations=True
   ↓
4. Looks up "Com4-Misc" in portfolio_allocations.json
   ↓
5. Finds allocation = 0.0%
   ↓
6. Returns REJECT (0% allocation)
```

**Processing Time**: < 1 second (instant lookup)

**Key Difference**: NO re-optimization, NO loading backtest data, NO scipy.optimize

---

### Dynamic Optimization Mode Flow (OLD behavior)

```
1. Signal arrives (e.g., "Com4-Misc")
   ↓
2. Load 9 strategies × 2,449 days from MongoDB (~2 seconds)
   ↓
3. Calculate mean returns, covariance matrix
   ↓
4. Run scipy optimization (14+ seconds)
   ↓
5. Get allocations (may differ from backtest!)
   ↓
6. Return decision
```

**Processing Time**: 16+ seconds per signal

**Issue**: Uses static backtest data, doesn't incorporate live performance

---

## Updating Allocations

### When to Update

- **Monthly rebalancing**: Re-run MaxHybrid backtest with latest data
- **Strategy changes**: Add/remove strategies
- **Performance issues**: Strategy underperforming vs backtest
- **Regime changes**: Market conditions shift significantly

### How to Update

**Option 1: Manual Update** (Quick)

Edit `portfolio_allocations.json` directly:

```json
{
  "allocations": {
    "chong_vansh_strategy": 85.0,  // Increased from 81.91
    "SPX_1-D_Opt": 55.0,           // Decreased from 57.79
    "Com4-Misc": 5.0,              // Enabled (was 0%)
    ...
  }
}
```

Restart Cerebro service to load new allocations.

**Option 2: Re-run Backtest** (Recommended)

```bash
# 1. Run MaxHybrid backtest with latest data
cd services/cerebro_service/research
python construct_portfolio.py --constructor max_hybrid

# 2. Extract allocations from latest output
# Check: portfolio_constructor/max_hybrid/outputs/MaxHybrid_YYYYMMDD_HHMMSS_allocations.csv
# Use the LAST ROW (most recent window)

# 3. Update portfolio_allocations.json with new values

# 4. Restart Cerebro service
pkill -f cerebro_service
python services/cerebro_service/main.py
```

---

## Switching Between Modes

### Enable Fixed Allocation Mode

In `services/cerebro_service/main.py`:

```python
PORTFOLIO_CONSTRUCTOR = MaxHybridConstructor(
    ...
    use_fixed_allocations=True,  # ✅ Fixed mode
    allocations_config_path=None  # Uses default JSON
)
```

### Enable Dynamic Optimization Mode

```python
PORTFOLIO_CONSTRUCTOR = MaxHybridConstructor(
    ...
    use_fixed_allocations=False,  # ❌ Dynamic mode
)
```

**Note**: Dynamic mode requires strategy histories in MongoDB!

---

## Validation & Testing

### Test Fixed Allocations

```bash
# Send test signals
python live_signal_tester.py --interval 10 --count 3
```

**Expected Output**:
```
✅ Signal #1: Com4-Misc → REJECTED (0% allocation)
✅ Signal #2: SPY → APPROVED (6.54% allocation)
✅ Signal #3: chong_vansh_strategy → APPROVED (81.91% allocation)
```

**Check Logs**:
```bash
tail -100 logs/cerebro_service.log | grep "FIXED ALLOCATION MODE"
```

Should see:
```
🔒 FIXED ALLOCATION MODE - Using pre-calculated allocations
   Loaded allocations: {'chong_vansh_strategy': 81.91, 'SPX_1-D_Opt': 57.79, ...}
```

---

## Advantages of Fixed Allocation Mode

✅ **Fast**: < 1 second vs 16+ seconds per signal  
✅ **Predictable**: Same allocation every time (no optimizer variance)  
✅ **Transparent**: You know exactly what allocations are used  
✅ **Controlled**: You decide when to update (not automatic)  
✅ **Testable**: Backtest results = live results (assuming same data)  

---

## Important Notes

### 📊 Mean Daily Return Calculation Issue

**Current Problem**: The optimizer calculates mean daily return across ALL days, including days with no margin usage.

**Example**:
- Strategy has positions 20 days/month
- Returns: +2% on trade days, 0% on idle days
- Current calculation: (20 × 2% + 10 × 0%) / 30 = 1.33% per day
- **Should be**: 2% per day (only on active days)

**Impact**: Strategies with infrequent trading get penalized

**Solution**: 
1. Filter returns where `margin_used > 0`
2. Calculate mean return only on active trading days
3. Re-run backtest with corrected calculation
4. Update `portfolio_allocations.json`

### 🎯 Zero Allocation Strategies

**Com4-Misc** and **TLT** both get 0% allocation because:
- Low returns relative to other strategies
- High correlation with allocated strategies
- Don't improve portfolio Sharpe/CAGR

**This is the optimizer working correctly** - not a bug!

If you want to trade these strategies:
1. Give them manual allocations (e.g., 2-5%)
2. Remove other strategies to make room
3. Adjust `max_leverage` to allow more total allocation

---

## Files Changed

1. **`services/cerebro_service/portfolio_allocations.json`** (NEW)
   - Fixed allocation configuration

2. **`services/cerebro_service/portfolio_constructor/max_hybrid/strategy.py`**
   - Added `use_fixed_allocations` parameter
   - Added `_load_fixed_allocations()` method
   - Modified `allocate_portfolio()` to check mode

3. **`services/cerebro_service/main.py`**
   - Updated `initialize_portfolio_constructor()` to enable fixed mode

---

## Next Steps

1. ✅ **Test live signals** with fixed allocations enabled
2. ⚠️ **Fix mean return calculation** (filter for margin_used > 0)
3. ⏸️ **Re-run backtest** with corrected calculation
4. 📝 **Update allocations** with new backtest results
5. 🚀 **Deploy to production**

---

## Questions?

**Q: What if a new strategy is added?**  
A: Add it to `portfolio_allocations.json` with desired allocation. Reduce other strategies to stay under `max_leverage`.

**Q: What if allocations don't sum to 230%?**  
A: That's OK! The system uses whatever allocations you provide. You can allocate 100%, 150%, or 230% total.

**Q: Can I have different allocations for different accounts?**  
A: Not currently - all accounts use the same `portfolio_allocations.json`. Future enhancement: account-specific configs.

**Q: How do I know if the allocations are working?**  
A: Check logs for "🔒 FIXED ALLOCATION MODE" message and verify signals are approved/rejected with expected percentages.
