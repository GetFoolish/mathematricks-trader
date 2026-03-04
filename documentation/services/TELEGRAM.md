# Telegram Notifier Service

## Overview

The Telegram Notifier is a utility service that sends notifications to Telegram channels for trading signals, order executions, and system events. It's used by other services (Execution, Cerebro) to provide real-time alerts.

**Main File:** `services/telegram/notifier.py`  
**Type:** Library module (not a standalone service)  
**Used by:** Execution Service, Cerebro Service

## Purpose

- **Signal Notifications** - Alert when new signals are received
- **Execution Notifications** - Confirm order fills and rejections
- **Position Updates** - Report P&L changes and position status
- **System Alerts** - Notify about errors and service issues
- **Environment Separation** - Different channels for production vs staging

## Architecture

### How It Works

```
Service (Execution/Cerebro) → TelegramNotifier → Telegram Bot API → Telegram Channel
                                                     (HTTP POST)
```

### Key Components

1. **TelegramNotifier Class**
   - Singleton instance per service
   - Environment-aware channel routing
   - HTML message formatting
   - Error handling and logging

2. **Message Formatters**
   - `notify_signal_received()` - New signal alerts
   - `notify_trade_executed()` - Order execution results
   - `notify_position_update()` - Position P&L changes
   - Generic `send_message()` - Custom messages

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_ENABLED` | Enable/disable notifications | `true` |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `683723231:AAHj0iJ...` |
| `TELEGRAM_CHAT_ID` | Production channel ID | `-365852442` |
| `TELEGRAM_STAGING_CHAT_ID` | Staging channel ID | `-01003237770899` |

### Setup Instructions

1. **Create Telegram Bot:**
   ```
   1. Message @BotFather on Telegram
   2. Send /newbot
   3. Follow prompts to name your bot
   4. Copy the bot token
   ```

2. **Get Chat ID:**
   ```
   1. Create a Telegram channel
   2. Add your bot as admin
   3. Send a message to the channel
   4. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
   5. Find "chat":{"id":-123456789} in response
   ```

3. **Add to .env:**
   ```bash
   TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=683723231:AAHj0iJEUNyZ4kq_mgvlvX-LoUBWvg16DtE
   TELEGRAM_CHAT_ID=-365852442
   TELEGRAM_STAGING_CHAT_ID=-01003237770899
   ```

## Message Types

### Signal Received Notification

**Triggered by:** Execution Service when signal arrives

**Message Format:**
```
🔔 NEW SIGNAL

📊 Strategy: MaxCAGR_v2
🆔 Signal ID: SIGNAL_123
⚡ Lag: 0.234s [Sent: 2026-02-02 12:34:55 UTC, Recd: 2026-02-02 12:34:55 UTC]

📈 Instrument: AAPL
💰 Action: BUY 100 shares @ $150.00

⏳ Processing signal...
```

**Code:**
```python
telegram.notify_signal_received(
    signal_data={
        'signalID': 'SIGNAL_123',
        'strategy_name': 'MaxCAGR_v2',
        'signal': [{
            'instrument': 'AAPL',
            'action': 'BUY',
            'quantity': 100,
            'price': 150.0
        }]
    },
    lag_seconds=0.234,
    sent_timestamp='2026-02-02T12:34:55Z',
    received_timestamp=datetime.utcnow()
)
```

### Trade Executed Notification

**Triggered by:** Execution Service after order fills

**Message Format:**
```
✅ TRADES EXECUTED

📊 Strategy: MaxCAGR_v2
🆔 Signal ID: SIGNAL_123
🕐 Time: 2026-02-02 12:35:02

📈 Orders:
✅ AAPL - BUY 100 @ IBKR
✅ MSFT - BUY 50 @ IBKR

📊 Summary:
✅ Successful: 2
❌ Failed: 0
```

**Code:**
```python
telegram.notify_trade_executed(
    signal_id='SIGNAL_123',
    strategy_name='MaxCAGR_v2',
    orders=[
        {
            'ticker': 'AAPL',
            'order_side': 'BUY',
            'quantity': 100,
            'broker': 'IBKR'
        },
        {
            'ticker': 'MSFT',
            'order_side': 'BUY',
            'quantity': 50,
            'broker': 'IBKR'
        }
    ],
    execution_results=[
        {'status': 'filled'},
        {'status': 'filled'}
    ]
)
```

### Position Update Notification

**Triggered by:** Execution Service when position closes

**Message Format:**
```
📊 POSITION UPDATE

📊 Strategy: MaxCAGR_v2
📈 Instrument: AAPL

💰 P&L: $250.00 (+1.67%)
📉 Entry: $150.00
📈 Exit: $152.50
📊 Quantity: 100 shares

✅ Status: CLOSED
```

**Code:**
```python
telegram.notify_position_update(
    strategy_name='MaxCAGR_v2',
    instrument='AAPL',
    position_status='CLOSED',
    pnl=250.0,
    pnl_pct=1.67,
    entry_price=150.0,
    exit_price=152.50,
    quantity=100
)
```

### Custom Message

**Message Format:**
```
🚨 SYSTEM ALERT

Service: execution-service
Error: Broker connection lost
Time: 2026-02-02 12:45:00
```

**Code:**
```python
telegram.send_message(
    message="""
🚨 SYSTEM ALERT

Service: execution-service
Error: Broker connection lost
Time: 2026-02-02 12:45:00
    """,
    parse_mode='HTML'
)
```

## API Reference

### TelegramNotifier Class

#### `__init__(bot_token, chat_id, enabled, environment)`

Initialize Telegram notifier.

**Parameters:**
- `bot_token` (str, optional): Bot token (defaults to env var)
- `chat_id` (str, optional): Chat ID (defaults to env-based selection)
- `enabled` (bool, optional): Enable notifications (default: True)
- `environment` (str, optional): 'production' or 'staging' (default: 'production')

**Example:**
```python
from telegram.notifier import TelegramNotifier

# Use environment variables
telegram = TelegramNotifier()

# Or override settings
telegram = TelegramNotifier(
    bot_token='123:ABC',
    chat_id='-456',
    enabled=True,
    environment='staging'
)
```

#### `send_message(message, parse_mode='HTML')`

Send a message to Telegram.

**Parameters:**
- `message` (str): Message text (supports HTML or Markdown)
- `parse_mode` (str, optional): 'HTML' or 'Markdown' (default: 'HTML')

**Returns:** `bool` - True if sent successfully

**Example:**
```python
success = telegram.send_message(
    message="<b>Alert:</b> System restarted",
    parse_mode='HTML'
)
```

#### `notify_signal_received(signal_data, lag_seconds, sent_timestamp, received_timestamp)`

Notify when a new signal is received.

**Parameters:**
- `signal_data` (dict): Signal data with `signalID`, `strategy_name`, `signal`
- `lag_seconds` (float, optional): Time lag in seconds
- `sent_timestamp` (str, optional): ISO timestamp when signal was sent
- `received_timestamp` (datetime, optional): When signal was received

**Returns:** `bool` - True if sent successfully

#### `notify_trade_executed(signal_id, strategy_name, orders, execution_results)`

Notify when trades are executed.

**Parameters:**
- `signal_id` (str): Signal ID
- `strategy_name` (str): Strategy name
- `orders` (list): List of order dicts
- `execution_results` (list): List of execution result dicts

**Returns:** `bool` - True if sent successfully

#### `notify_position_update(strategy_name, instrument, position_status, pnl, pnl_pct, entry_price, exit_price, quantity)`

Notify when position is updated.

**Parameters:**
- `strategy_name` (str): Strategy name
- `instrument` (str): Instrument symbol
- `position_status` (str): Position status (OPEN, CLOSED, etc.)
- `pnl` (float): Profit/Loss amount
- `pnl_pct` (float): Profit/Loss percentage
- `entry_price` (float): Entry price
- `exit_price` (float, optional): Exit price
- `quantity` (int): Position quantity

**Returns:** `bool` - True if sent successfully

## Integration Examples

### In Execution Service

```python
from telegram.notifier import TelegramNotifier

# Initialize (once at startup)
telegram = TelegramNotifier()

# On signal received
if telegram.enabled:
    telegram.notify_signal_received(
        signal_data=signal_data,
        lag_seconds=lag,
        sent_timestamp=signal_data.get('timestamp'),
        received_timestamp=datetime.utcnow()
    )

# On order filled
if telegram.enabled:
    telegram.notify_trade_executed(
        signal_id=order['signal_id'],
        strategy_name=order['strategy_id'],
        orders=[order],
        execution_results=[result]
    )
```

### In Cerebro Service

```python
from telegram.notifier import TelegramNotifier

telegram = TelegramNotifier()

# On signal approval
if telegram.enabled and decision.status == 'APPROVED':
    telegram.send_message(
        f"""
✅ SIGNAL APPROVED

Strategy: {signal['strategy_name']}
Signal ID: {signal['signalID']}
Quantity: {decision.quantity}
        """
    )

# On signal rejection
if telegram.enabled and decision.status == 'REJECTED':
    telegram.send_message(
        f"""
❌ SIGNAL REJECTED

Strategy: {signal['strategy_name']}
Reason: {decision.reason}
        """
    )
```

## Message Formatting

### HTML Formatting

Telegram supports HTML tags:

```python
message = """
<b>Bold Text</b>
<i>Italic Text</i>
<code>Monospace</code>
<pre>Code Block</pre>
<a href="http://example.com">Link</a>
"""
```

### Emoji Usage

Common emojis for trading notifications:

```python
EMOJIS = {
    'signal': '🔔',
    'strategy': '📊',
    'instrument': '📈',
    'money': '💰',
    'time': '🕐',
    'success': '✅',
    'failure': '❌',
    'warning': '⚠️',
    'alert': '🚨',
    'lightning': '⚡'
}
```

### Escaping Special Characters

For HTML mode, escape: `<`, `>`, `&`

```python
def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
```

## Troubleshooting

### Problem: Messages not sending
**Symptoms:** `telegram.send_message()` returns False
**Debug:**
1. Check `TELEGRAM_ENABLED=true` in .env
2. Verify bot token is valid
3. Check chat ID is correct (with minus sign)
4. Ensure bot is admin in channel
5. Check service logs for error details

### Problem: "Chat not found" error
**Cause:** Invalid chat ID or bot not added to channel
**Solution:**
- Verify chat ID format: `-123456789` (note the minus sign)
- Add bot as channel admin
- Send a test message to channel first

### Problem: HTML parsing errors
**Cause:** Invalid HTML tags in message
**Solutions:**
- Use only supported tags: `<b>`, `<i>`, `<code>`, `<pre>`, `<a>`
- Escape special characters: `<`, `>`, `&`
- Switch to Markdown if HTML issues persist

### Problem: Rate limiting (429 Too Many Requests)
**Cause:** Sending too many messages too quickly
**Solutions:**
- Telegram limit: 30 messages/second per bot
- Implement message queue with rate limiting
- Batch multiple signals into one message
- Reduce notification frequency

### Problem: Wrong environment channel
**Cause:** Environment detection failing
**Solutions:**
- Explicitly set environment: `TelegramNotifier(environment='staging')`
- Check environment variable: `os.getenv('ENVIRONMENT')`
- Verify staging chat ID is set

## Performance Notes

- **API Call Time:** ~100-500ms per message
- **Non-blocking:** Async operation doesn't block service
- **Error Handling:** Failed sends logged but don't crash service
- **Retry Logic:** No automatic retries (implement if needed)

## Security Considerations

### Token Security
- Never commit bot token to git
- Use environment variables only
- Rotate tokens periodically
- Restrict bot permissions

### Message Content
- Avoid sending sensitive data (passwords, API keys)
- Don't include PII (personally identifiable information)
- Sanitize user inputs to prevent injection

### Channel Access
- Make channels private
- Limit admin access
- Monitor unauthorized access
- Revoke old bot tokens

## Advanced Features

### Message Threading
For high-volume notifications:

```python
import threading

def send_async(telegram, message):
    threading.Thread(
        target=lambda: telegram.send_message(message),
        daemon=True
    ).start()

# Non-blocking send
send_async(telegram, "Signal received")
```

### Batching Messages
Reduce API calls by combining messages:

```python
class BatchNotifier:
    def __init__(self, telegram, batch_interval=5):
        self.telegram = telegram
        self.batch = []
        self.batch_interval = batch_interval
        self.start_batch_timer()
    
    def add_message(self, message):
        self.batch.append(message)
    
    def flush_batch(self):
        if self.batch:
            combined = "\n\n".join(self.batch)
            self.telegram.send_message(combined)
            self.batch = []
```

### Custom Keyboards
For interactive notifications (future):

```python
keyboard = {
    "inline_keyboard": [
        [
            {"text": "Approve", "callback_data": "approve_signal"},
            {"text": "Reject", "callback_data": "reject_signal"}
        ]
    ]
}

telegram.send_message(
    message="New signal received",
    reply_markup=json.dumps(keyboard)
)
```

## Dependencies

- `requests` - HTTP client for Telegram API
- `logging` - Error and debug logging

## Related Services

- **Execution Service** - Primary user of telegram notifier
- **Cerebro Service** - Uses for decision notifications
- **Account Data Service** - Could use for balance alerts (future)

## Logging

Telegram notifier logs to service logger:

```
INFO - Telegram notifications enabled for PRODUCTION environment (chat_id: -365852442)
DEBUG - Telegram message sent successfully
ERROR - Failed to send Telegram message: 400 Bad Request
```

## Future Enhancements

### Webhook Support
Receive updates from Telegram:
- User commands (/status, /balance)
- Interactive approvals
- Real-time queries

### Rich Media
Send charts and images:
- P&L charts
- Equity curves
- Performance snapshots

### Alert Rules
Configurable alerts:
- Threshold-based (PnL > $X)
- Frequency limits (max 1/hour)
- Priority levels (critical only)

### Multi-Channel Support
Route different notifications:
- Signals → #signals channel
- Errors → #alerts channel
- Performance → #reports channel
