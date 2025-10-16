# Optimizer Mathematical Analysis

## Problem Identified

When increasing max drawdown from 20% to 35%, the CAGR **did not increase** as expected. This suggested a fundamental issue with the optimization objective.

## Root Cause: Arithmetic Mean vs Geometric Mean

### portfolio_optimizer.py (CORRECT ✓)
```python
def portfolio_negative_cagr(weights, daily_returns_list):
    portfolio_returns = calculate_portfolio_returns_series(weights, daily_returns_list)
    cagr = calculate_cagr(portfolio_returns)
    return -cagr  # Minimizes negative CAGR = maximizes CAGR

def calculate_cagr(portfolio_returns):
    total_return = (1 + portfolio_returns).prod()  # GEOMETRIC growth
    n_years = len(portfolio_returns) / 252
    cagr = (total_return ** (1 / n_years)) - 1
    return cagr
```

### MaxCAGRConstructor (INCORRECT ✗)
```python
def objective(weights):
    portfolio_return = np.dot(weights, mean_returns)  # ARITHMETIC mean
    return -portfolio_return
```

## Mathematical Difference

**Arithmetic Mean** (what we were using):
- Simple average: (r₁ + r₂ + ... + rₙ) / n
- Does NOT account for compounding
- Example: [+10%, -10%] → arithmetic mean = 0%

**Geometric Mean / CAGR** (what we should use):
- Compound growth: ((1+r₁)(1+r₂)...(1+rₙ))^(1/n) - 1
- Accounts for compounding and volatility drag
- Example: [+10%, -10%] → geometric mean = -0.5%
- **Always ≤ arithmetic mean** (equality only if no volatility)

## Volatility Drag Effect

For volatile strategies, CAGR < Mean Return due to:
```
CAGR ≈ Mean Return - (Variance / 2)
```

This means optimizing arithmetic mean does NOT maximize CAGR!

## Test Results Comparison

| Config | Optimizer | CAGR | Max DD | Sharpe | Notes |
|--------|-----------|------|--------|--------|-------|
| 20% DD | portfolio_optimizer.py | **122.37%** | -15.47% | 2.96 | ✓ Correct |
| 20% DD | MaxCAGRConstructor | 122.00% | -16.92% | 2.90 | ✗ Wrong objective |
| 35% DD | portfolio_optimizer.py | **122.37%** | -15.47% | 2.96 | ✓ Same result (already optimal) |
| 35% DD | MaxCAGRConstructor | 122.00% | -16.92% | 2.90 | ✗ No improvement |

### Key Observations:

1. **portfolio_optimizer.py**: Same result for both DD limits because 20% constraint was not binding (actual DD was -15.47%)
2. **MaxCAGRConstructor**: Wrong objective function led to suboptimal allocation
3. **Allocation Differences**:
   - Com3-Mkt: 23.63% vs 49.52% (25.89% difference!)
   - SPX_1-D_Opt: 76.37% vs 50.48% (25.89% difference!)

## Why CAGR Didn't Increase

When loosening DD constraint from 20% → 35%:
- **Expected**: Optimizer finds higher-CAGR allocation with higher DD
- **Actual**: No change because:
  - portfolio_optimizer.py: 20% constraint wasn't binding (-15.47% actual)
  - MaxCAGRConstructor: Wrong objective function (not actually maximizing CAGR)

## Solution

Replace arithmetic mean objective with actual CAGR calculation:

```python
def objective(weights):
    # Calculate portfolio returns time series
    portfolio_returns = np.dot(returns_df.values, weights)
    
    # Calculate CAGR (geometric mean)
    cumulative = np.cumprod(1 + portfolio_returns)
    total_return = cumulative[-1]
    n_years = len(portfolio_returns) / 252
    cagr = (total_return ** (1 / n_years)) - 1
    
    return -cagr  # Negative for minimization
```

This matches `portfolio_optimizer.py` implementation exactly.

## Impact

After fix, MaxCAGRConstructor should:
1. ✓ Match portfolio_optimizer.py results exactly
2. ✓ Produce same allocations (within optimization tolerance)
3. ✓ Have smooth equity curves (proper CAGR optimization reduces volatility drag)
4. ✓ Respond correctly to constraint changes (looser DD → higher CAGR if beneficial)
