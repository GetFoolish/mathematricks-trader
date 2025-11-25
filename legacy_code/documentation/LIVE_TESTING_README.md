# Live Signal Tester - Max Hybrid Portfolio

## Overview
This script tests live signal processing with the **Max Hybrid Portfolio Management** technique. It sends trading signals every 10 seconds and shows detailed analysis of how each signal is processed, including all the math behind the decisions.

## What It Does

1. **Sends Trading Signals** - Generates and sends realistic trading signals to the system
2. **Monitors Processing** - Tracks signals through Cerebro → Execution pipeline
3. **Shows All Math** - Displays detailed calculations for:
   - Portfolio allocation percentages
   - Position sizing calculations
   - Margin requirements
   - Risk assessment
4. **Max Hybrid Logic** - Uses the optimized portfolio construction algorithm with:
   - 85% Sharpe ratio weighting / 15% CAGR weighting
   - 230% max leverage
   - -6% max drawdown constraint

## Requirements

### Services Must Be Running
Start all services first:
```bash
./run_mvp_demo.sh
```

Check service status:
```bash
./check_services.sh
```

### Required Services:
- ✅ Signal Ingestion Service (port 3002)
- ✅ Cerebro Service (port 8001) - **Using MaxHybrid constructor**
- ✅ Account Data Service (port 8002)
- ✅ Execution Service (port 8003)
- ✅ MongoDB (connection via .env)

## Usage

### Basic Test (5 signals, 10 second intervals)
```bash
python live_signal_tester.py --interval 10 --count 5
```

### Continuous Testing (infinite signals)
```bash
python live_signal_tester.py --interval 10
```

### Fast Testing (5 second intervals)
```bash
python live_signal_tester.py --interval 5 --count 10
```

### Custom Account
```bash
python live_signal_tester.py --account DU1234567 --interval 10
```

## Command Line Options

- `--interval` - Seconds between signals (default: 10)
- `--count` - Number of signals to send (default: infinite)
- `--account` - IBKR account name (default: DU1234567)
- `--passphrase` - API passphrase (default: yahoo123)

## Output Example

```
================================================================================
🎯 SIGNAL ANALYSIS - Com1-Met_20251020_123456_001
================================================================================

📨 INCOMING SIGNAL:
   Strategy: Com1-Met
   Instrument: AAPL
   Direction: LONG
   Action: BUY
   Price: $175.50
   Requested Quantity: 50

💰 ACCOUNT STATE (Before Signal):
   Account: DU1234567
   Total Equity: $1,000,000.00
   Available Funds: $800,000.00
   Margin Used: $150,000.00
   Margin Available: $850,000.00
   Margin Used %: 15.00%

🧠 CEREBRO DECISION (Max Hybrid Portfolio Logic):
   Decision: APPROVE
   Reason: MaxHybrid allocation: 45.2% (Total portfolio: 230.0%)
   Original Quantity: 50
   Final Quantity: 45

📊 RISK ASSESSMENT & MATH:
   Allocated Capital: $452,000.00
   Margin Required: $226,000.00

   🔢 Portfolio Construction Math:
      Strategy Allocation: 45.20%
      Portfolio Equity: $1,000,000.00
      Position Sizing: 1,000,000 × 45.20% = $452,000.00

📋 TRADING ORDER (Sent to Execution):
   Order ID: Com1-Met_20251020_123456_001_ORD
   Instrument: AAPL
   Direction: LONG
   Order Type: MARKET
   Price: $175.50
   Quantity: 45 shares
   Notional Value: $7,897.50
   Status: PENDING

================================================================================
```

## Test Strategies

The tester randomly selects from these strategies (must exist in MongoDB):
- Com1-Met
- Com2-Ag
- Com3-Mkt
- Com4-Misc
- Forex
- SPY
- TLT
- SPX_1-D_Opt

## Logs

All activity is logged to:
```
logs/live_signal_tester.log
```

## Troubleshooting

### Services Not Running
```bash
./check_services.sh
./run_mvp_demo.sh
```

### No Cerebro Decisions
- Check `logs/cerebro_service.log`
- Verify MongoDB connection
- Ensure strategy data exists in MongoDB

### No Execution Orders
- Signals may be rejected by Cerebro
- Check risk limits and margin constraints
- Review decision reason in output

## What to Watch For

1. **Allocation Distribution** - How MaxHybrid distributes capital across strategies
2. **Total Leverage** - Should stay near 230% (2.3x)
3. **Margin Usage** - Should respect the -6% drawdown constraint
4. **Position Sizing** - How equity × allocation% calculates capital
5. **Decision Reasons** - Why signals are approved/rejected

## Stop Testing

Press `Ctrl+C` to stop the tester gracefully.

## Next Steps

After testing:
1. Review `logs/live_signal_tester.log` for full history
2. Check MongoDB collections:
   - `signals` - Raw incoming signals
   - `cerebro_decisions` - Portfolio decisions
   - `trading_orders` - Orders sent to execution
3. Analyze allocation patterns across different strategies
