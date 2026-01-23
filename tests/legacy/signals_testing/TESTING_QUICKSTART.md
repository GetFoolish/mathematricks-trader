# Testing Quick Start Guide

## Overview
Complete testing framework for Mathematricks Trader v5 with 98 signal files and automated test runner.

---

## 📋 What's Included

### Signal Files
- **Realistic Signals** (9 files, 90 signals)
  - Location: `sample_signals/`
  - All 9 strategies with all instruments
  - 3 complete trade cycles per strategy
  - Perfectly balanced positions (zero final position)
  - Fixed prices, fund_id="Mock-Fund-1"

- **Edge-Case Signals** (8 files, 8 signals)
  - Location: `sample_signals_edgecases/`
  - Error scenarios: insufficient margin, asset class mismatch, capital limits
  - Advanced features: stop-loss, partial fills, order rejection/recovery
  - Multi-fund: same strategy to multiple funds
  - Account failover: primary unavailable, route to secondary

### Scripts
- **send_test_signal.py** - Send individual or batch signals
- **run_full_test.py** - Execute all signals with automated reporting

### Configuration
- **.env** - SIGNAL_TEST_SEED for deterministic shuffling

---

## 🚀 Quick Start

### 1. Send All Realistic Signals (Reproducible Order)
```bash
python run_full_test.py
# Uses SIGNAL_TEST_SEED=1 from .env
# Results saved to test_results/test_run_YYYYMMDD_HHMMSS_*
```

### 2. Send All Signals with Randomized Order
```bash
python run_full_test.py --seed 0
# Different order every run (truly random)
```

### 3. Send All Signals with Custom Seed (Reproducible)
```bash
python run_full_test.py --seed 42
# Same order every time (reproducible with seed 42)
```

### 4. Send Only Edge-Case Signals
```bash
python run_full_test.py --folder sample_signals_edgecases/
```

### 5. Send Individual File
```bash
python send_test_signal.py --file sample_signals/com1_met_realistic.json
# Or use @filename syntax:
python send_test_signal.py @sample_signals/spy_realistic.json
```

### 6. Send Folder with Custom Seed (Advanced)
```bash
python send_test_signal.py --folder sample_signals/ --seed 123
```

---

## 📊 Results

Test results are saved to `test_results/` folder:
- `test_run_TIMESTAMP_output.txt` - Raw command output
- `test_run_TIMESTAMP_results.json` - Structured results with metadata

Example result:
```json
{
  "run_id": "test_run_20260105_143022",
  "timestamp": "2026-01-05T14:30:22.123456+00:00",
  "folder": "sample_signals",
  "seed": 1,
  "status": "success",
  "signals_sent": 90,
  "duration_seconds": 45.23,
  "start_time": "2026-01-05T14:30:22.123456+00:00",
  "end_time": "2026-01-05T14:31:07.356789+00:00"
}
```

---

## 🔀 Seed Behavior

### Seed Values
| Seed | Behavior | Use Case |
|------|----------|----------|
| `1`, `42`, `999` | Reproducible order every run | Baseline testing, debugging |
| `0` | Randomized order every run | Stress testing, edge case detection |
| Negative | Original file order (no shuffle) | Sequential testing by file |

### Setting Default Seed
Edit `.env`:
```bash
SIGNAL_TEST_SEED=1      # Reproducible (default)
SIGNAL_TEST_SEED=0      # Randomized
SIGNAL_TEST_SEED=42     # Reproducible with seed 42
```

Override from CLI:
```bash
python run_full_test.py --seed 0      # Overrides .env
python send_test_signal.py --folder sample_signals/ --seed 123
```

---

## 📐 Signal Structure

All signals follow this format:
```json
{
  "strategy_name": "Com1 - Met",
  "signal_type": "ENTRY",
  "signal_sent_EPOCH": 1736000400,
  "signalID": "sig_com1_met_001",
  "entry_name": "$ENTRY_1",
  "account_equity": 500000,
  "signal_legs": [
    {
      "instrument": "GC",
      "instrument_type": "FUTURE",
      "action": "BUY",
      "direction": "LONG",
      "quantity": 2,
      "order_type": "MARKET",
      "price": 2050.00,
      "stop_loss": 2040.00,
      "take_profit": 2065.00
    }
  ],
  "environment": "staging",
  "staging": true,
  "fund_id": "Mock-Fund-1",
  "wait": 60
}
```

---

## 🎯 Testing Strategies

### 1. Baseline Test (Reproducible)
```bash
# Run same signals in same order every time
python run_full_test.py --seed 1
# Compare results across runs - should be identical
```

### 2. Stress Test (Random Order)
```bash
# Run signals in different order each time
python run_full_test.py --seed 0
python run_full_test.py --seed 0
# Verify system handles any signal order
```

### 3. Edge Case Coverage
```bash
# Test error scenarios separately
python run_full_test.py --folder sample_signals_edgecases/
# Verify error handling is robust
```

### 4. Single Strategy Debug
```bash
# Test one strategy at a time
python send_test_signal.py @sample_signals/com1_met_realistic.json
# Monitor logs for detailed behavior
```

---

## 📖 Monitoring Test Results

While tests run, monitor service logs:
```bash
# In separate terminal
tail -f logs/signal_ingestion.log    # Signal receipt & validation
tail -f logs/cerebro_service.log      # Position sizing & calculations
tail -f logs/execution_service.log    # Order creation & placement
tail -f logs/portfolio_builder.log    # Fund/account management
```

---

## 🔧 Troubleshooting

### MongoDB Connection Error
```
❌ Failed to connect to MongoDB
```
**Solution:** Ensure MongoDB is running
```bash
make start  # or: docker-compose up -d mongodb
```

### Missing SIGNAL_TEST_SEED
```
⚠️  SIGNAL_TEST_SEED not set in .env
```
**Solution:** Add to .env:
```bash
echo "SIGNAL_TEST_SEED=1" >> .env
```

### No Signals Found in Folder
```
❌ No .json files found in: sample_signals/
```
**Solution:** Check folder path is correct from current directory

### Timeout After 10 Minutes
```
❌ Test suite timed out after 10 minutes
```
**Solution:** Some strategies may be slow - check service logs for bottlenecks

---

## 📚 Reference

- Full testing plan: `../documentation/LLM_development_documentation/v5-testing-framework-plan.md`
- Strategy inventory: `./STRATEGY_INVENTORY.md`
- Signal sample: `./sample_signals/com1_met_realistic.json`
- Scripts: `./send_test_signal.py`, `./run_full_test.py`

---

**Created:** 2026-01-05  
**Status:** Ready to test Phase 8 (Testing Framework)
