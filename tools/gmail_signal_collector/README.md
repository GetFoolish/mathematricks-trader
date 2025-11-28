# Gmail Signal Collector

Polls Gmail for trading signals and forwards them to Mathematricks API.

## Quick Start

1. **Configure**:
   ```bash
   # .env file in project root already has:
   GMAIL_CLIENT_ID=...
   GMAIL_CLIENT_SECRET=...
   MATHEMATRICKS_API_URL=https://mathematricks.fund/api/signals
   MATHEMATRICKS_PASSPHRASE=...
   STRATEGY_NAME=Gmail_Signal_Integration
   SIGNAL_IDENTIFIER=LESLIE_SIGNAL
   ```

2. **Authenticate** (one-time):
   ```bash
   cd tools/gmail_signal_collector
   python3 gmail_signal_collector.py --auth
   ```

3. **Test**:
   ```bash
   python3 gmail_signal_collector.py --dry-run
   ```

4. **Run**:
   ```bash
   # Run once
   python3 gmail_signal_collector.py

   # Run continuously (daemon mode)
   ./start_gmail_daemon.sh

   # Stop daemon
   ./stop_gmail_daemon.sh

   # View logs
   tail -f ../../logs/gmail_signal_collector.log
   ```

## Signal Format

Send email with `LESLIE_SIGNAL` in subject or body:

**JSON format:**
```json
{
  "ticker": "AAPL",
  "action": "BUY",
  "price": 175.50,
  "quantity": 100,
  "stop_loss": 170.00,
  "take_profit": 180.00
}
```

**Text format:**
```
ticker: AAPL
action: BUY
price: 175.50
quantity: 100
```

## Files

- `gmail_signal_collector.py` - Main script
- `start_gmail_daemon.sh` - Start in background
- `stop_gmail_daemon.sh` - Stop daemon
- `GMAIL_SIGNAL_COLLECTOR.md` - Full documentation
- `token.json` - OAuth token (created on first auth)
- `.gmail_state.json` - Processed message tracking

## See Also

- `GMAIL_SIGNAL_COLLECTOR.md` - Complete documentation
- `GMAIL_EXTRACTION_SUMMARY.md` - What was extracted from old code
