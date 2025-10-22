# Mathematricks Trader V1

Automated trading system that processes signals from TradingView, applies risk management, and executes orders across multiple brokers.

## Architecture

```
TradingView → Vercel → MongoDB → signal_collector.py → Mathematricks Trader → Brokers
```

## Features

### Core System
- ✅ **Multi-Broker Support**: IBKR, Zerodha, Binance, Vantage
- ✅ **Signal Processing**: Stocks, Options, Multi-leg, Stop-loss
- ✅ **Risk Management**: Position sizing, broker allocation limits
- ✅ **Compliance Checking**: Pre-trade validation
- ✅ **Portfolio Management**: Aggregated view across all brokers
- ✅ **Telegram Notifications**: Real-time alerts for signals and trades

### Reporting & Analytics
- 📊 **Signals History**: Filter and view all historical signals
- 📈 **Combined Performance**: System-wide equity curve and metrics
- 🔍 **Strategy Deepdive**: Per-strategy analysis
- 🔗 **Correlation Matrix**: Strategy correlation analysis
- 🚀 **Strategy Onboarding**: Coming soon

## Project Structure

```
mathematricks-trader-v1/
├── src/
│   ├── core/                 # Portfolio and signal models
│   ├── risk_management/      # Risk calculator & compliance
│   ├── order_management/     # Signal → Order conversion
│   ├── brokers/              # Broker integrations
│   ├── execution/            # Signal processor & portfolio manager
│   ├── reporting/            # Data storage & metrics
│   └── utils/                # Logger and utilities
├── telegram/                 # Telegram notifications
│   ├── __init__.py
│   └── notifier.py
├── frontend/                 # Streamlit dashboard
│   ├── app.py
│   └── pages/
├── logs/                     # System logs
├── tmp/                      # Development files
├── signal_collector.py       # Receives signals from MongoDB
├── signal_sender.py          # Test signal sender
├── main.py                   # System entry point
├── run_mathematricks_trader.py  # Unified launcher
├── requirements.txt
└── .env.sample
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.sample .env
# Edit .env with your API keys
```

### 3. Run the System

**Option 1: Run everything with a single command (recommended):**
```bash
python run_mathematricks_trader.py
```

**Option 2: Run components separately:**

Terminal 1 - Trading system:
```bash
python main.py
```

Terminal 2 - Signal collector:
```bash
python signal_collector.py
```

Terminal 3 - Dashboard:
```bash
streamlit run frontend/app.py
```

## Signal Flow

1. **Signal Received**: `signal_collector.py` receives signal from MongoDB
2. **Signal Parsed**: Converted to `TradingSignal` object
3. **Portfolio Fetched**: Get current positions from all brokers
4. **Risk Adjusted**: Calculate ideal portfolio
5. **Orders Generated**: Convert signal to broker-specific orders
6. **Compliance Check**: Validate updated portfolio
7. **Order Execution**: Send orders to appropriate brokers
8. **Data Storage**: Store signals, orders, positions in MongoDB

## Signal Types

### Stock Signal
```json
{
  "ticker": "AAPL",
  "action": "BUY",
  "price": 150.25
}
```

### Options Signal
```json
{
  "type": "options",
  "ticker": "AAPL",
  "strike": 150,
  "expiry": "2025-01-17",
  "action": "BUY_CALL"
}
```

### Multi-leg Order
```json
[
  {"ticker": "SPY", "action": "BUY", "qty": 100},
  {"ticker": "QQQ", "action": "SELL", "qty": 50}
]
```

### Stop-loss Signal
```json
{
  "trigger": "if AAPL < 145",
  "action": "SELL_ALL",
  "stop_loss": true
}
```

## Broker Configuration

### IBKR (Interactive Brokers)
- Requires TWS or IB Gateway running
- Set `IBKR_CLIENT_ID`, `IBKR_API_KEY`, `IBKR_API_SECRET`
- Toggle `IBKR_PAPER_TRADING`

### Zerodha
- Requires Kite Connect API
- Set `ZERODHA_API_KEY`, `ZERODHA_API_SECRET`, `ZERODHA_ACCESS_TOKEN`

### Binance
- Requires Binance API
- Set `BINANCE_API_KEY`, `BINANCE_API_SECRET`
- Toggle `BINANCE_TESTNET`

### Vantage FX
- Requires MetaTrader 5 or Vantage API
- Set `VANTAGE_API_KEY`, `VANTAGE_API_SECRET`, `VANTAGE_ACCOUNT_ID`
- Toggle `VANTAGE_DEMO`

## Telegram Notifications

The system sends real-time notifications to Telegram for:
- **Signal Received**: When a new signal arrives from TradingView
- **Trade Executed**: When orders are successfully placed
- **Compliance Violation**: When a signal fails compliance checks
- **Signal Failed**: When signal processing encounters errors
- **Position Closed**: When a position is exited (coming soon)
- **Daily Summary**: End-of-day performance report (coming soon)

### Setup Telegram

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow instructions
   - Copy the bot token provided

2. **Get Your Chat ID**:
   - Message [@userinfobot](https://t.me/userinfobot) on Telegram
   - Copy your chat ID

3. **Configure Environment**:
   ```bash
   # In your .env file
   TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

4. **Test Notifications**:
   - Start the system and send a test signal
   - You should receive formatted notifications in your Telegram chat

### Notification Format

All notifications are sent in HTML format with:
- 📊 Strategy name and signal ID
- 🕐 Timestamp
- ✅/❌ Status indicators
- 📋 Detailed trade information

## Risk Management

### V1 Features
- Position size limits (default: 10% per position)
- Broker allocation limits (default: 40% per broker)
- Pre-trade compliance checking

### Future Enhancements
- VaR (Value at Risk) calculations
- Correlation-based position sizing
- Dynamic leverage management
- Drawdown limits

## Development

### Testing Signals

```bash
# Send test signal
python signal_sender.py --signalId "test_001" --signal '{"ticker": "AAPL", "action": "BUY", "price": 150.25}'

# Run test suite
python signal_sender.py --test-suite
```

### MongoDB Collections

- `trading_signals`: All received signals
- `orders`: All executed orders
- `positions`: Position snapshots
- `pnl_history`: Daily PnL records
- `strategy_performance`: Per-strategy metrics

## Notes

- All broker integrations have mock implementations for V1
- To enable live trading, implement actual broker API calls
- Risk management has placeholder logic - enhance as needed
- Frontend uses MongoDB for data retrieval
- Keep development files in `tmp/` folder

## Future Roadmap

- [ ] Implement actual broker API integrations
- [ ] Advanced risk management algorithms
- [ ] Strategy backtesting module
- [ ] Real-time PnL tracking
- [ ] Email/SMS alerts
- [ ] Strategy onboarding interface
- [ ] Portfolio rebalancing automation
