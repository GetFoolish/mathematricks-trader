# MVP Demo Guide - Mathematricks Trading System

## What You'll See

This demo shows the complete signal flow from TradingView → staging.mathematricks.fund → MongoDB → signal_collector → MVP microservices (Cerebro → Execution).

## Architecture

```
YOU send signal to staging.mathematricks.fund/api/signals
  ↓
Vercel webhook stores in MongoDB Atlas
  ↓
signal_collector.py (monitors MongoDB Change Streams)
  ↓
signal_processor.py (bridges to microservices via Pub/Sub)
  ↓
Pub/Sub → CerebroService (position sizing + risk management)
  ↓
Pub/Sub → ExecutionService (IBKR execution)
  ↓
Pub/Sub → AccountDataService (account state tracking)
```

## Prerequisites

1. **Google Cloud SDK** (for Pub/Sub emulator)
   ```bash
   # Check if installed
   gcloud version

   # If not installed: https://cloud.google.com/sdk/docs/install
   # Then install emulator:
   gcloud components install pubsub-emulator
   ```

2. **MongoDB Atlas** - Already configured ✓

3. **IBKR TWS/Gateway** (optional for demo - execution will log but not actually execute)

## Quick Start

### 1. Start All Services

```bash
./run_mvp_demo.sh
```

This will:
- Start Pub/Sub emulator on localhost:8085
- Create all topics and subscriptions
- Start AccountDataService on port 8002
- Start CerebroService (background)
- Start ExecutionService (background)
- Start signal_collector monitoring staging.mathematricks.fund

### 2. Send a Test Signal

Use the existing signal_sender.py:

```bash
python signal_sender.py --ticker SPY --action BUY --price 450.25
```

This sends to staging.mathematricks.fund, which stores in MongoDB.

### 3. Watch the Flow

Open 3 terminals and tail the logs:

**Terminal 1 - Signal Collection:**
```bash
tail -f logs/signal_collector.log
```
You'll see:
- Signal received from MongoDB Change Stream
- Routing to Mathematricks Trader (signal_processor)
- Publishing to Pub/Sub microservices

**Terminal 2 - Cerebro (Position Sizing):**
```bash
tail -f logs/cerebro_service.log
```
You'll see:
- Signal consumed from Pub/Sub
- Account state queried (equity, margin)
- Position size calculated (5% of equity = $5,000 ÷ price)
- Margin limit checked (40% max)
- Trading order created and published

**Terminal 3 - Execution:**
```bash
tail -f logs/execution_service.log
```
You'll see:
- Trading order consumed from Pub/Sub
- IBKR connection attempt (will fail if TWS not running - OK for demo)
- Would execute order if IBKR connected
- Account update published

### 4. Check MongoDB Results

Query MongoDB to see what was stored:

```bash
# In Python or MongoDB Compass
# Database: mathematricks_trading
# Collections:
#   - cerebro_decisions (position sizing decision)
#   - trading_orders (generated order)
#   - account_state (would be updated after execution)
```

### 5. Stop All Services

```bash
./stop_mvp_demo.sh
```

## Expected Log Output

### signal_collector.log
```
🔥 REAL-TIME SIGNAL DETECTED!
📊 Strategy: Test Strategy
⚡ Delay: 0.234 seconds
📡 Signal: {'ticker': 'SPY', 'action': 'BUY', 'price': 450.25}

🚀 Routing to MVP microservices (Cerebro → Execution)
✅ Signal published to Cerebro microservice: projects/mathematricks-trader/topics/standardized-signals/messages/12345
```

### cerebro_service.log
```
[Cerebro] Received signal: SC_1760132368.00181
[Cerebro] Account equity: $100,000.00
[Cerebro] Current margin used: $20,000.00 (20%)
[Cerebro] Allocated capital (5%): $5,000.00
[Cerebro] Position size: 11.10 shares @ $450.25
[Cerebro] Margin required: $2,500.00
[Cerebro] Margin after: 22.5% (within 40% limit) ✓
[Cerebro] APPROVED - Publishing order ORDER_xxx
```

### execution_service.log
```
[Execution] Received trading order: ORDER_xxx
[Execution] Instrument: SPY, Action: BUY, Quantity: 11.10
[Execution] Connecting to IBKR at 127.0.0.1:7497...
[Execution] ⚠️ IBKR not connected (demo mode)
[Execution] Would execute: BUY 11.10 SPY @ MARKET
```

## Troubleshooting

### Pub/Sub Emulator Won't Start

```bash
# Check if port 8085 is in use
lsof -i :8085

# Kill existing emulator
pkill -f pubsub-emulator

# Try again
./run_mvp_demo.sh
```

### Services Not Receiving Signals

```bash
# Check emulator is running
curl localhost:8085

# Check environment variable
echo $PUBSUB_EMULATOR_HOST  # Should be localhost:8085

# Restart with fresh emulator
./stop_mvp_demo.sh
./run_mvp_demo.sh
```

### Signal Not Appearing in signal_collector

- Make sure you're using `--staging` flag (run_mvp_demo.sh does this automatically)
- Check MongoDB Change Stream is working: signals should appear in `mathematricks_signals` database first

## What's Next

After successful demo:
1. Test with real IBKR paper trading account
2. Add more strategies to Cerebro's decision logic
3. Implement full MPT/cVaR calculations
4. Add dashboard services
5. Deploy to GCP

## Files Created

- `setup_pubsub_emulator.sh` - Setup Pub/Sub topics
- `run_mvp_demo.sh` - Start all services
- `stop_mvp_demo.sh` - Stop all services
- Modified: `src/execution/signal_processor.py` - Pub/Sub bridge

## Ready to Test!

Run `./run_mvp_demo.sh` and send a signal!
