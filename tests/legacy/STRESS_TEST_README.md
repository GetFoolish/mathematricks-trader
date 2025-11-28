# Trading Stress Test

## Overview

`stress_test_trading.py` simulates continuous realistic trading activity to stress test the entire trading system. It sends random entry and exit signals from all active strategies, tracks open positions, and handles graceful shutdown.

## Features

✅ **Random Signal Generation**: Sends entry/exit signals from 7 active strategies
✅ **Position Tracking**: Maintains state of all open positions
✅ **Realistic Timing**: Random hold periods (30s - 3min) before exits
✅ **P&L Calculation**: Tracks simulated profit/loss for each trade
✅ **Graceful Shutdown**: Ctrl+C closes all positions and cancels TWS orders
✅ **Continuous Operation**: Runs indefinitely until interrupted
✅ **Smart Position Management**: Limits max concurrent positions

## Usage

### Basic Usage
```bash
# Default: 12 second interval, max 5 positions
python tests/stress_test_trading.py
```

### Custom Configuration
```bash
# Faster testing: 10 second interval, max 3 positions
python tests/stress_test_trading.py --interval 10 --max-positions 3

# Slower testing: 20 second interval, max 8 positions
python tests/stress_test_trading.py --interval 20 --max-positions 8
```

## How It Works

### Signal Flow
1. **Entry Signals**: Randomly picks strategy → instrument → direction (LONG/SHORT)
2. **Signal Sent**: Posts to `staging.mathematricks.fund/api/signals`
3. **Position Tracked**: Stores in memory with entry price, time, quantity
4. **Exit Decision**: After 30s minimum, probability increases with time
5. **Exit Signal**: Sends matching exit signal with P&L calculation

### Shutdown Process (Ctrl+C)
1. Catches SIGINT/SIGTERM signal
2. Sends exit signals for all open positions
3. Waits 5 seconds for processing
4. Connects to IBKR TWS (clientId=999)
5. Cancels ALL pending orders in TWS
6. Prints final statistics
7. Clean exit

## Active Strategies

The test uses these 7 strategies with their real allocations:

| Strategy | Allocation | Instruments |
|----------|-----------|-------------|
| chong_vansh_strategy | 81.91% | SPY, QQQ, IWM |
| SPX_1-D_Opt | 57.79% | SPY, SPX |
| Com1-Met | 43.09% | GLD, SLV, GDX |
| Com3-Mkt | 17.07% | DBA, DBB, DBC |
| Forex | 13.23% | UUP, FXE, FXY |
| Com2-Ag | 10.38% | DBA, CORN, WEAT |
| SPY | 6.54% | SPY |

## Example Output

```
================================================================================
🚀 TRADING STRESS TEST STARTED
================================================================================
Configuration:
  • Interval: 12 seconds
  • Max Positions: 5
  • Active Strategies: 7
  • Cloud Endpoint: https://staging.mathematricks.fund/api/signals

⚠️  Press Ctrl+C to stop and cleanup
================================================================================

✅ Connected to IBKR TWS for position management

🔄 Cycle 1 - 08:45:23
================================================================================
📈 ENTRY SIGNAL: chong_vansh_strategy | SPY | LONG
   Signal ID: chong_vansh_strategy_20251022_084523_ENTRY_0001
   Quantity: 45 @ $458.32
================================================================================
✅ Entry signal sent - Now tracking 1 open positions
⏳ Waiting 14 seconds until next cycle...

🔄 Cycle 2 - 08:45:37
================================================================================
📈 ENTRY SIGNAL: Com1-Met | GLD | SHORT
   Signal ID: Com1-Met_20251022_084537_ENTRY_0002
   Quantity: 78 @ $192.45
================================================================================
✅ Entry signal sent - Now tracking 2 open positions
⏳ Waiting 11 seconds until next cycle...

🔄 Cycle 3 - 08:45:48
================================================================================
📉 EXIT SIGNAL: chong_vansh_strategy | SPY
   Original Signal: chong_vansh_strategy_20251022_084523_ENTRY_0001
   Exit Signal: chong_vansh_strategy_20251022_084548_EXIT_0003
   Entry: $458.32 → Exit: $461.20
   🟢 P&L: +0.63%
================================================================================
✅ Exit signal sent - 1 positions remaining

^C
================================================================================
🛑 SHUTDOWN SIGNAL RECEIVED - Closing all positions...
================================================================================

================================================================================
📊 STRESS TEST STATUS
================================================================================
Total Signals Sent: 15
Total Entries: 8
Total Exits: 7
Open Positions: 1

📋 Current Open Positions:
   • GLD SHORT x78 @ $192.45 (145s)
================================================================================

📤 Sending exit signals for 1 open positions...
================================================================================
📉 EXIT SIGNAL: Com1-Met | GLD
   Original Signal: Com1-Met_20251022_084537_ENTRY_0002
   Exit Signal: Com1-Met_20251022_085210_EXIT_0016
   Entry: $192.45 → Exit: $191.80
   🟢 P&L: +0.34%
================================================================================
✅ Exit signal sent - 0 positions remaining

⏳ Waiting 5 seconds for signals to be processed...
🛑 Cancelling all pending orders in TWS...
✅ All orders successfully cancelled
✅ Disconnected from IBKR

================================================================================
✅ CLEANUP COMPLETE
================================================================================
Final Statistics:
  • Total Signals Sent: 16
  • Total Entries: 8
  • Total Exits: 8
================================================================================
```

## Prerequisites

1. **All Services Running**:
   ```bash
   ./run_mvp_demo.sh
   ```

2. **TWS Connected**: Paper trading account on localhost:7497

3. **Environment Variables**: `.env` file with MongoDB and GCP settings

## Monitoring

### Logs
- Console: Real-time colored output
- File: `logs/stress_test.log`

### Check Services
```bash
# Execution service log
tail -f logs/execution_service.log

# Cerebro service log  
tail -f logs/cerebro_service.log

# Signal collector log
tail -f logs/signal_collector.log
```

### MongoDB
Check execution confirmations:
```javascript
db.execution_confirmations.find().sort({timestamp: -1}).limit(10)
db.trading_orders.find().sort({timestamp: -1}).limit(10)
```

## Troubleshooting

### Test won't start
- Check all services running: `ps aux | grep "main.py"`
- Verify TWS running: `ps aux | grep "TWS"`
- Test cloud endpoint: `curl https://staging.mathematricks.fund/api/signals`

### Orders not appearing in TWS
- Check execution_service.log for errors
- Verify IBKR connection in logs
- Ensure paper trading account active

### Cleanup fails
- Manually cancel orders in TWS
- Check `logs/stress_test.log` for errors
- Reconnect TWS if needed

## Tips

- **Start Small**: Use `--interval 20 --max-positions 2` for initial testing
- **Monitor TWS**: Keep TWS open to see orders in real-time
- **Check Logs**: Always monitor execution_service.log during tests
- **Clean State**: Cancel all TWS orders before starting new test
- **Paper Account**: Only use with paper trading account!

## Safety Features

🛡️ **Position Limits**: Prevents runaway position accumulation
🛡️ **Graceful Shutdown**: Always cleans up on exit
🛡️ **Order Cancellation**: Automatically cancels TWS orders on Ctrl+C
🛡️ **Error Handling**: Continues running even if individual signals fail
🛡️ **Realistic Timing**: Prevents market manipulation patterns
