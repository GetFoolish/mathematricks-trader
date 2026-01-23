# Strategy Inventory for Testing

**Generated:** 2026-01-04
**Total Strategies:** 9
**Status:** Ready for Signal Generation

---

## Strategy Mapping Table

| # | Strategy Name | Asset Class | Current Accounts | Signal File | Status |
|---|---|---|---|---|---|
| 1 | Com1 - Met | commodities | Mock_Paper | `com1_met_realistic.json` | ⏳ |
| 2 | Com2 - Ag | unknown | Mock_Paper | `com2_ag_realistic.json` | ⏳ |
| 3 | Com3 - Mkt | unknown | Mock_Paper | `com3_mkt_realistic.json` | ⏳ |
| 4 | Com4 - Misc | unknown | Mock_Paper | `com4_misc_realistic.json` | ⏳ |
| 5 | FloridaForex | unknown | Mock_Paper | `florida_forex_realistic.json` | ⏳ |
| 6 | SPX 0DE Opt | unknown | Mock_Paper | `spx_0de_opt_realistic.json` | ⏳ |
| 7 | SPX 1 - D Opt | unknown | Mock_Paper | `spx_1d_opt_realistic.json` | ⏳ |
| 8 | SPY | unknown | Mock_Paper | `spy_realistic.json` | ⏳ |
| 9 | TLT | unknown | Mock_Paper | `tlt_realistic.json` | ⏳ |

---

## Detailed Strategy Analysis

### 1. Com1 - Met (Commodities - Metals)
- **Asset Class:** `commodities`
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** Gold (GC), Silver (SI), Copper (HG) futures
- **Realistic Prices (Jan 2026):**
  - GC (Gold): ~$2,050/oz (tick size: $0.10)
  - SI (Silver): ~$29.50/oz (tick size: $0.005)
  - HG (Copper): ~$4.20/lb (tick size: $0.0005)
- **Typical Quantities:** 1-3 contracts per trade
- **Expected Moves:** ±$10-50 per trade cycle

### 2. Com2 - Ag (Commodities - Agriculture)
- **Asset Class:** `unknown` (likely commodities)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** Corn (ZC), Wheat (ZW), Soybeans (ZS) futures
- **Realistic Prices (Jan 2026):**
  - ZC (Corn): ~$4.25/bu (tick size: $0.0025)
  - ZW (Wheat): ~$5.80/bu (tick size: $0.0025)
  - ZS (Soybeans): ~$11.20/bu (tick size: $0.0025)
- **Typical Quantities:** 1-5 contracts per trade
- **Expected Moves:** ±$0.10-0.30 per trade cycle

### 3. Com3 - Mkt (Commodities - Mixed Market)
- **Asset Class:** `unknown` (likely commodities)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** Mix of oil (CL), gold (GC), natural gas (NG)
- **Realistic Prices (Jan 2026):**
  - CL (Crude Oil): ~$78/bbl (tick size: $0.01)
  - GC (Gold): ~$2,050/oz (tick size: $0.10)
  - NG (Natural Gas): ~$3.15/MMBtu (tick size: $0.001)
- **Typical Quantities:** 1-2 contracts per trade
- **Expected Moves:** ±$2-5 per trade cycle

### 4. Com4 - Misc (Commodities - Miscellaneous)
- **Asset Class:** `unknown` (likely commodities)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** Less common commodities (cocoa, sugar, coffee futures)
- **Realistic Prices (Jan 2026):**
  - CC (Cocoa): ~$3,200/MT (tick size: $1)
  - SB (Sugar): ~$0.23/lb (tick size: $0.01)
  - KC (Coffee): ~$220/lb (tick size: $0.05)
- **Typical Quantities:** 1-2 contracts per trade
- **Expected Moves:** ±$50-200 per trade cycle

### 5. FloridaForex
- **Asset Class:** `unknown` (likely forex)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** Major forex pairs
- **Realistic Prices (Jan 2026):**
  - EURUSD: ~1.0850 (pip moves: ±5-15)
  - GBPUSD: ~1.2750 (pip moves: ±5-15)
  - AUDCAD: ~0.8950 (pip moves: ±5-20)
- **Typical Quantities:** 100k-500k units (1-5 standard lots)
- **Expected Moves:** ±50-200 pips per trade cycle

### 6. SPX 0DE Opt (S&P 500 Options - Zero DTE)
- **Asset Class:** `unknown` (likely options)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** SPY 0DTE options (same-day expiry)
- **Realistic Prices (Jan 2026):**
  - SPY: ~$580 (underlying)
  - Call/Put premiums: $0.05-5.00 per contract (highly volatile for 0DTE)
- **Typical Quantities:** 1-10 contracts per trade
- **Strike Selection:** At-the-money ±2-5% from current price
- **Expected Moves:** ±$200-1000 per trade cycle (highly leveraged)

### 7. SPX 1-D Opt (S&P 500 Options - 1 Day)
- **Asset Class:** `unknown` (likely options)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** SPY 1-day options
- **Realistic Prices (Jan 2026):**
  - SPY: ~$580 (underlying)
  - Call/Put premiums: $0.10-2.00 per contract
- **Typical Quantities:** 1-5 contracts per trade
- **Strike Selection:** At-the-money or slightly OTM
- **Expected Moves:** ±$100-500 per trade cycle

### 8. SPY (Equity)
- **Asset Class:** `unknown` (likely equity)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** SPY ETF shares
- **Realistic Prices (Jan 2026):**
  - SPY: ~$580 per share
- **Typical Quantities:** 10-100 shares per trade
- **Moves:** ±2-5% per trade cycle (±$12-29)
- **Expected Moves:** ±$120-2900 per trade cycle

### 9. TLT (Fixed Income)
- **Asset Class:** `unknown` (likely equity/ETF)
- **Current Accounts:** `Mock_Paper`
- **Typical Instruments:** TLT ETF (20+ year Treasury bonds)
- **Realistic Prices (Jan 2026):**
  - TLT: ~$92 per share
- **Typical Quantities:** 20-100 shares per trade
- **Moves:** ±1-3% per trade cycle (±$0.92-2.76)
- **Expected Moves:** ±$20-276 per trade cycle

---

## Asset Class Summary

| Asset Class | Strategies | Instruments | Typical Quantities | Typical Price Moves |
|---|---|---|---|---|
| **Commodities (Metals)** | Com1 | GC, SI, HG | 1-3 contracts | ±$10-50 |
| **Commodities (Ag)** | Com2 | ZC, ZW, ZS | 1-5 contracts | ±$0.10-0.30 |
| **Commodities (Mixed)** | Com3 | CL, GC, NG | 1-2 contracts | ±$2-5 |
| **Commodities (Misc)** | Com4 | CC, SB, KC | 1-2 contracts | ±$50-200 |
| **Forex** | FloridaForex | EURUSD, GBPUSD, AUDCAD | 100k-500k units | ±50-200 pips |
| **Options (0DTE)** | SPX 0DE Opt | SPY 0DTE calls/puts | 1-10 contracts | ±$200-1000 |
| **Options (1D)** | SPX 1-D Opt | SPY 1D calls/puts | 1-5 contracts | ±$100-500 |
| **Equity (SPY)** | SPY | SPY shares | 10-100 shares | ±2-5% |
| **Fixed Income** | TLT | TLT shares | 20-100 shares | ±1-3% |

---

## Questions to Resolve

### ❓ Question 1: Asset Class Confirmation
Some strategies show `asset_class: unknown`. Based on their names:
- **Com1 - Met** = Metals/Commodities ✅
- **Com2 - Ag** = Agriculture/Commodities (assumption)
- **Com3 - Mkt** = Mixed Market Commodities (assumption)
- **Com4 - Misc** = Miscellaneous Commodities (assumption)
- **FloridaForex** = Forex (assumption)
- **SPX 0DE Opt** = Options (assumption)
- **SPX 1-D Opt** = Options (assumption)
- **SPY** = Equity (assumption)
- **TLT** = Fixed Income/Equity (assumption)

**Action Needed:** Confirm these asset class assumptions or correct them.

### ❓ Question 2: Instrument Selection
For each strategy, we need to select specific instruments for test signals. Should we:
- A) Use ONE primary instrument per strategy (simplest)
- B) Rotate through 2-3 instruments per strategy (realistic)
- C) Use all possible instruments (comprehensive but complex)

**Recommendation:** Option B - Use 2-3 instruments per strategy, with each signal file containing trade cycles for different instruments.

### ❓ Question 3: Fund Assignment
All test signals should reference a specific fund. Options:
- A) Use "mathematricks-dev-fund" (created in Phase 5)
- B) Create dedicated "test-fund" for testing
- C) Create fund per strategy for isolation

**Recommendation:** Option A - Use "mathematricks-dev-fund" for all test signals to keep setup simple.

### ❓ Question 4: Account Failover Testing
Should sample signals test multi-account distribution? Currently all strategies only have `Mock_Paper` account. We could:
- A) Add a second test account (e.g., "Test_Account_1") to some strategies
- B) Keep simple (single Mock_Paper account per strategy)
- C) Do multi-account testing only in edge-case files

**Recommendation:** Option B for realistic signals (keep simple), Option C for edge cases.

---

## Next Steps

1. **Confirm Asset Classes** - Are the "unknown" asset_classes correctly assumed?
2. **Confirm Instrument Selection** - Should each strategy rotate through 2-3 instruments?
3. **Confirm Fund Assignment** - All test signals use "mathematricks-dev-fund"?
4. **Create Signal Templates** - Design JSON structure with entry/exit cycles
5. **Generate Signal Files** - Create 7-10 realistic signals per strategy file
6. **Interactive Review** - Review each file with you before finalizing

---

**Last Updated:** 2026-01-04 14:30 UTC
**Ready to Proceed:** Awaiting clarification on above questions
