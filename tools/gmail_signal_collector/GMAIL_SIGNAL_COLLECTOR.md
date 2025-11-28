# Gmail Signal Collector - Cron Job Version

Single self-contained Python script that polls Gmail for trading signals and forwards them to the Mathematricks API. Designed to run as a cron job on a Raspberry Pi or any Linux server.

## Features

- ✅ **Single file** - No complex setup, just one Python script
- ✅ **Polling-based** - No webhook server needed, perfect for cron jobs
- ✅ **State tracking** - Avoids duplicate signal processing
- ✅ **Smart extraction** - Handles JSON and structured text signals
- ✅ **Dry-run mode** - Test without sending to API
- ✅ **Gmail OAuth2** - Secure authentication
- ✅ **Configurable** - All settings in `.env` file

## Quick Start

### 1. Install Dependencies

```bash
pip install google-auth google-auth-oauthlib google-api-python-client python-dotenv requests
```

### 2. Setup Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable **Gmail API**
4. Create **OAuth 2.0 Client ID** (Desktop app)
5. Download credentials (or copy Client ID and Secret)

### 3. Configure Environment

```bash
# Copy example config
cp .env.gmail.example .env

# Edit with your credentials
nano .env
```

Required settings:
- `GMAIL_CLIENT_ID` - From Google Cloud Console
- `GMAIL_CLIENT_SECRET` - From Google Cloud Console
- `MATHEMATRICKS_PASSPHRASE` - Your API passphrase
- `MATHEMATRICKS_API_URL` - API endpoint (default: https://mathematricks.fund/api/signals)

### 4. Authenticate

```bash
# Run once to authenticate with Gmail
python3 gmail_signal_collector.py --auth
```

This will:
- Open a browser for Gmail OAuth
- Save token to `token.json`
- Token refreshes automatically after first use

### 5. Test

```bash
# Test API connection
python3 gmail_signal_collector.py --test

# Dry run (check for signals without sending)
python3 gmail_signal_collector.py --dry-run

# Normal run (check for signals and send to API)
python3 gmail_signal_collector.py
```

## Cron Setup

Run every 5 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path)
*/5 * * * * cd /home/pi/mathematricks && /usr/bin/python3 gmail_signal_collector.py >> /var/log/gmail_signal.log 2>&1
```

Alternative schedules:
```bash
# Every minute
* * * * * cd /path/to/script && python3 gmail_signal_collector.py >> /var/log/gmail_signal.log 2>&1

# Every 10 minutes
*/10 * * * * cd /path/to/script && python3 gmail_signal_collector.py >> /var/log/gmail_signal.log 2>&1

# Every hour at :00
0 * * * * cd /path/to/script && python3 gmail_signal_collector.py >> /var/log/gmail_signal.log 2>&1
```

## How It Works

1. **Polls Gmail** - Searches for emails containing `SIGNAL_IDENTIFIER` keyword
2. **Extracts Signals** - Parses JSON or structured text formats
3. **Tracks State** - Stores processed message IDs in `.gmail_state.json`
4. **Forwards to API** - Sends formatted signals to Mathematricks API
5. **Logs Results** - Outputs summary of signals sent

## Signal Formats

### JSON Format (Recommended)

```
Subject: Trading Signal

{
  "ticker": "AAPL",
  "action": "BUY",
  "price": 150.50,
  "quantity": 100,
  "stop_loss": 145.00,
  "take_profit": 160.00
}
```

### Structured Text Format

```
Subject: SIGNAL - AAPL Buy

Ticker: AAPL
Action: BUY
Price: $150.50
Quantity: 100
Stop Loss: $145.00
Take Profit: $160.00
```

### Identifier Anywhere

The script searches for emails where subject OR body contains the `SIGNAL_IDENTIFIER` (default: "SIGNAL").

## Configuration Reference

### Required

- `GMAIL_CLIENT_ID` - OAuth2 Client ID from Google Cloud
- `GMAIL_CLIENT_SECRET` - OAuth2 Client Secret
- `MATHEMATRICKS_PASSPHRASE` - API authentication passphrase

### Optional

- `MATHEMATRICKS_API_URL` - API endpoint (default: https://mathematricks.fund/api/signals)
- `STRATEGY_NAME` - Strategy identifier (default: Gmail_Signal_Strategy)
- `SIGNAL_IDENTIFIER` - Keyword to identify signal emails (default: SIGNAL)
- `MAX_EMAILS_PER_RUN` - Max emails to process per run (default: 50)
- `LOOKBACK_HOURS` - How far back to search for emails (default: 24 hours)

## Files Created

- `token.json` - OAuth2 token (auto-refreshes)
- `.gmail_state.json` - Processed message tracking
- `.env` - Configuration (create from `.env.gmail.example`)

## Troubleshooting

### Authentication Issues

```bash
# Re-authenticate
rm token.json
python3 gmail_signal_collector.py --auth
```

### Test API Connection

```bash
# Sends a test signal
python3 gmail_signal_collector.py --test
```

### Check Logs

```bash
# View recent activity
tail -f /var/log/gmail_signal.log
```

### Dry Run

```bash
# See what would be sent without actually sending
python3 gmail_signal_collector.py --dry-run
```

## Security Notes

- `token.json` contains OAuth credentials - keep it secure
- `.env` contains API passphrase - never commit to git
- Use `.gitignore` to exclude sensitive files

## Comparison with Original Code

### Removed (Unnecessary for Cron)
- ❌ Flask webhook server
- ❌ Google Cloud Pub/Sub push notifications
- ❌ Multiple Python files
- ❌ Docker setup
- ❌ ngrok tunneling
- ❌ Complex deployment scripts

### Kept (Essential Features)
- ✅ Gmail OAuth2 authentication
- ✅ Signal detection and extraction
- ✅ JSON and text parsing
- ✅ API forwarding
- ✅ State management (avoid duplicates)

### Added (Cron-Friendly)
- ✅ Polling instead of push notifications
- ✅ Single self-contained file
- ✅ State file for duplicate prevention
- ✅ Dry-run mode
- ✅ Lookback window for reliability
- ✅ Better logging for cron

## License

Same as parent project (Mathematricks Trader)
