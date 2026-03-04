# Mathematricks Trading System

A production-grade algorithmic trading system supporting multi-asset strategies across stocks, options, forex, futures, and crypto. Built for institutional-quality risk management, portfolio optimization, and multi-mode execution (mock → paper → live).

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [4-Mode Trading System](#-4-mode-trading-system)
- [System Architecture](#-system-architecture)
- [Services](#-services)
- [Brokers](#-brokers)
- [Testing](#-testing)
- [MongoDB Schemas](#-mongodb-schemas)
- [Documentation](#-documentation)

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.9+
- MongoDB 5.0+ (runs via Docker)
- IBKR Account (optional, for live trading)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd mathematricks-trader

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Start services (uses local MongoDB by default)
make start-dev

# Verify system
python tests/run_test_suite.py --system
```

### MongoDB Deployment Options

The system supports two MongoDB deployment targets:

**Local MongoDB (Docker)** - Default for development:
```bash
make start              # Start with local MongoDB (default)
make start-dev          # Dev mode - always uses local MongoDB
make restart            # Restart with local MongoDB (default)
```

**Cloud MongoDB (Atlas)** - For production/staging:
```bash
make start DEPLOY=cloud    # Start with cloud MongoDB
make restart DEPLOY=cloud  # Restart with cloud MongoDB
```

**Note:** `make start-dev` always uses local MongoDB (no cloud option needed for development)

### Send Your First Signal

```bash
# Test signal (mock mode)
python tests/send_test_signal.py --file tests/sample_signals/simple_stock.json

# View in admin dashboard
open http://localhost:3001
```

---

## 🎯 4-Mode Trading System

The system supports **4 execution modes** for progressive testing from development to production:

| Mode | Account Type | Data Source | Use Case | Gateway Required |
|------|--------------|-------------|----------|------------------|
| **mock_mock** | Mock | Mock | Fast development, unit testing | No |
| **mock_live** | Mock | Live (IBKR) | Strategy testing with real market data | Yes (port 4004) |
| **paper_live** | Paper (IBKR) | Live (IBKR) | IBKR paper trading (simulated execution) | Yes (port 4004) |
| **live_live** | Live (IBKR) | Live (IBKR) | Production trading - **REAL MONEY** | Yes (port 4001) |

### Mode Components

Each mode is composed of:
- **Account Type** (`account_type`): Where orders execute (`mock`, `paper`, `live`)
- **Data Source** (`data_source`): Where market data comes from (`mock`, `live`)

### Mode Selection in Signals

Signals specify their execution mode via three fields:

```json
{
  "mode": "paper_live",
  "account_type": "paper",
  "data_source": "live",
  "environment": "staging"
}
```

### Progressive Testing Workflow

```
1. mock_mock (seconds)
   ↓ Test signal flow, validate schema
   
2. mock_live (1-2 min)
   ↓ Test with real market data
   
3. paper_live (days/weeks)
   ↓ Full IBKR paper trading
   
4. live_live (production)
   ✓ Real money trading
```

**Example Test Sequence:**

```bash
# 1. Mock mode (no IBKR needed)
python tests/run_test_suite.py --mode mock_mock \
  --file tests/sample_signals/simple_stock.json

# 2. Mock with live data (requires IB Gateway)
python tests/run_test_suite.py --mode mock_live \
  --file tests/sample_signals/simple_stock.json

# 3. Paper trading (IBKR paper account)
python tests/run_test_suite.py --mode paper_live \
  --file tests/sample_signals/simple_stock.json

# 4. Production (requires ALLOW_LIVE_TRADING=true)
python tests/run_test_suite.py --mode live_live \
  --file tests/sample_signals/simple_stock.json
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Signals                          │
│          (TradingView, Google Sheets, Python Scripts)            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP POST
                            ▼
                    ┌───────────────┐
                    │ Signal Receiver│ (Port 3000)
                    │  (Netlify Fn) │
                    └───────┬───────┘
                            │ Insert
                            ▼
                ┌──────────────────────┐
                │ trading_signals_raw   │ (MongoDB)
                └──────────┬───────────┘
                           │ Change Stream
                           ▼
                ┌──────────────────┐
                │ signal_ingestion │
                │ Standardization  │
                └──────────┬───────┘
                           │ Create/Update
                           ▼
                ┌──────────────────┐
                │  signal_store    │ (MongoDB)
                └──────────┬───────┘
                           │ Change Stream
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Cerebro Service (Port 8082)                │
│  • Portfolio construction (MaxCAGR, MaxHybrid)                │
│  • Position sizing & scaling                                  │
│  • Risk management & margin checks                            │
│  • Fund allocation logic                                      │
└──────────────────────────┬───────────────────────────────────┘
                           │ Create
                           ▼
                ┌──────────────────┐
                │  trading_orders  │ (MongoDB)
                └──────────┬───────┘
                           │ Change Stream
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                 Execution Service (Port 8083)                 │
│  • Broker connection management                               │
│  • Order routing (Mock, IBKR, Coinbase, Kraken)              │
│  • 4-mode execution (mock_mock → live_live)                   │
│  • Execution confirmations                                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ Execute
                           ▼
                ┌──────────────────┐
                │   Brokers        │
                │  (IBKR, etc.)    │
                └──────────────────┘

Background Services:
━━━━━━━━━━━━━━━━━
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Account Data Svc │────▶│ Portfolio Builder│────▶│ Dashboard Creator│
│  (Poll brokers)  │     │  (Optimization)  │     │  (Pre-compute)   │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### Data Flow

1. **Signal Ingestion**: External signal → `trading_signals_raw` → Standardization → `signal_store`
2. **Decision Making**: Cerebro watches `signal_store` → Portfolio logic → Creates `trading_orders`
3. **Execution**: Execution service watches `trading_orders` → Broker API → Updates `signal_store.legs[x].execution`
4. **Account Updates**: Account data service polls brokers → Updates `trading_accounts`
5. **Monitoring**: Dashboard creator generates snapshots → `dashboard_snapshots`, `widget_data`

---

## 🔧 Services

Detailed documentation for each service: [`documentation/services/`](./documentation/services/)

### Core Services

| Service | Port | Purpose | Documentation |
|---------|------|---------|--------------|
| **[signal_ingestion](./documentation/services/signal_ingestion.md)** | - | Monitors `trading_signals_raw`, standardizes signals, creates/updates `signal_store` documents | [📄 Docs](./documentation/services/signal_ingestion.md) |
| **[cerebro_service](./documentation/services/cerebro_service.md)** | 8082 | Portfolio construction, position sizing, risk management, fund allocation logic | [📄 Docs](./documentation/services/cerebro_service.md) |
| **[execution_service](./documentation/services/execution_service.md)** | 8083 | Broker connections, order routing, 4-mode execution support | [📄 Docs](./documentation/services/execution_service.md) |
| **[account_data_service](./documentation/services/account_data_service.md)** | 8081 | Real-time account state: balances, positions, margin polling from brokers | [📄 Docs](./documentation/services/account_data_service.md) |

### Supporting Services

| Service | Port | Purpose | Documentation |
|---------|------|---------|--------------|
| **[portfolio_builder](./documentation/services/portfolio_builder.md)** | 8003 | Strategy management, backtest uploads, portfolio optimization | [📄 Docs](./documentation/services/portfolio_builder.md) |
| **[dashboard_creator](./documentation/services/dashboard_creator.md)** | 8004 | Pre-computed dashboard JSONs, widget updates, scheduled jobs | [📄 Docs](./documentation/services/dashboard_creator.md) |
| **[telegram](./documentation/services/telegram.md)** | - | Notification service for signals, trades, position updates | [📄 Docs](./documentation/services/telegram.md) |

### Service Commands

```bash
# Start all services (production - no signal receiver)
make start

# Start with development tools (includes signal receiver)
make start-dev

# Stop all services
make stop

# View logs
make logs
make logs-cerebro
make logs-execution
make logs-signal-receiver

# Restart specific service
docker-compose restart cerebro-service

# Check service health
curl http://localhost:8082/health  # Cerebro
curl http://localhost:8083/health  # Execution
```

---

## 🏦 Brokers

Detailed documentation for each broker: [`documentation/brokers/`](./documentation/brokers/)

### Supported Brokers

| Broker | Markets | Status | Documentation |
|--------|---------|--------|---------------|
| **[IBKR](./documentation/brokers/ibkr_gateway.md)** | US Stocks, Options, Futures, Forex | ✅ Production | [📄 Setup Guide](./documentation/brokers/ibkr_gateway.md) |
| **[Mock](./documentation/brokers/mock.md)** | All instruments (testing) | ✅ Production | [📄 Docs](./documentation/brokers/mock.md) |
| **[Coinbase](./documentation/brokers/coinbase.md)** | Crypto Spot (BTC, ETH, SOL, etc.) | ✅ Production | [📄 Docs](./documentation/brokers/coinbase.md) |

### Broker Interface

All brokers implement `AbstractBroker` with standardized methods:

**Connection:**
- `connect()`, `disconnect()`, `is_connected()`

**Orders:**
- `place_order()`, `cancel_order()`, `get_order_status()`

**Account Data:**
- `get_account_balance()`, `get_open_positions()`, `get_margin_info()`

### Adding a New Broker

See: [Creating Custom Broker Adapters](./documentation/brokers/CUSTOM_BROKER_GUIDE.md)

---

## 🧪 Testing

Comprehensive test framework with system validation, signal testing, and integration tests.

### Test Runner
##### THIS IS THE TEST WE USE MOST OFTEN: 

#### IBKR TEST - Local (Docker)
signal_count=10 && echo "Starting comprehensive test with $signal_count signals across 3 modes..." && echo -e "\n=== TEST 1: mock_mock with --clean ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --clean --local --environment staging --account-type mock --data-source mock --file tests/sample_signals/ibkr/tech_stocks_realistic.json --signal-count $signal_count && echo -e "\n=== TEST 2: mock_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --local --environment staging --account-type mock --data-source live --file tests/sample_signals/ibkr/tech_stocks_realistic.json --signal-count $signal_count && echo -e "\n=== TEST 3: paper_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --local --environment staging --account-type paper --data-source live --file tests/sample_signals/ibkr/tech_stocks_realistic.json --signal-count $signal_count

#### IBKR TEST - Cloud (Netlify)
signal_count=10 && echo "Starting comprehensive test with $signal_count signals across 3 modes..." && echo -e "\n=== TEST 1: mock_mock with --clean ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --clean --cloud --environment staging --account-type mock --data-source mock --file tests/sample_signals/ibkr/tech_stocks_realistic.json --signal-count $signal_count && echo -e "\n=== TEST 2: mock_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --cloud --environment staging --account-type mock --data-source live --file tests/sample_signals/ibkr/tech_stocks_realistic.json --signal-count $signal_count && echo -e "\n=== TEST 3: paper_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --cloud --environment staging --account-type paper --data-source live --file tests/sample_signals/ibkr/tech_stocks_realistic.json --signal-count $signal_count

#### COINBASE TEST - Local (Docker)
source .venv/bin/activate && signal_count=10 && echo "Starting Coinbase Crypto test with $signal_count signals across 3 modes..." && echo -e "\n=== TEST 1: mock_mock with --clean ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --clean --local --environment staging --account-type mock --data-source mock --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count $signal_count && echo -e "\n=== TEST 2: mock_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --local --environment staging --account-type mock --data-source live --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count $signal_count && echo -e "\n=== TEST 3: paper_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --local --environment staging --account-type paper --data-source live --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count $signal_count

#### COINBASE TEST - Cloud (Netlify)
source .venv/bin/activate && signal_count=10 && echo "Starting Coinbase Crypto test with $signal_count signals across 3 modes..." && echo -e "\n=== TEST 1: mock_mock with --clean ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --clean --cloud --environment staging --account-type mock --data-source mock --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count $signal_count && echo -e "\n=== TEST 2: mock_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --cloud --environment staging --account-type mock --data-source live --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count $signal_count && echo -e "\n=== TEST 3: paper_live ===" && .venv/bin/python tests/run_test_suite.py --signal-testing --cloud --environment staging --account-type paper --data-source live --file tests/sample_signals/coinbase/crypto_spot_trading.json --signal-count $signal_count

**Main test suite:** [`tests/run_test_suite.py`](./tests/run_test_suite.py)

```bash
# System validation (MongoDB, Docker, Python, IB Gateway)
python tests/run_test_suite.py --system

# Clean test data (reset accounts, clear collections)
python tests/run_test_suite.py --clean

# Test signal flow - mock mode
python tests/run_test_suite.py \
  --mode mock_mock \
  --file tests/sample_signals/simple_stock.json

# Test signal flow - paper trading
python tests/run_test_suite.py \
  --mode paper_live \
  --file tests/sample_signals/simple_stock.json

# Run all tests
python tests/run_test_suite.py --all
```

### Test Categories

**System Tests** (`tests/system/`):
- MongoDB connectivity
- Docker service health
- Python environment validation
- IB Gateway connection

**Unit Tests** (`tests/unit/`):
- Backtest upload handler
- Market data parsing
- Metrics calculation

**Integration Tests** (`tests/integration/`):
- Full signal flow (ingestion → cerebro → execution)
- Multi-leg signals (entry + exit)
- Position reconciliation

**Signal Tests** (`tests/sample_signals/`):
- Stock signals (simple, multi-leg, scaling)
- Option signals (single-leg, spreads)
- Forex signals (with residual cleanup)
- Crypto signals

### Manual Signal Testing

```bash
# Send test signal
python tests/send_test_signal.py --file tests/sample_signals/simple_stock.json

# With specific mode
python tests/send_test_signal.py \
  --file tests/sample_signals/simple_stock.json \
  --mode paper_live \
  --environment staging

# From inline JSON
python tests/send_test_signal.py --inline '{
  "strategy_name": "TEST",
  "signal_type": "ENTRY",
  "signal_legs": [{"instrument": "AAPL", "action": "BUY", "quantity": 10}]
}'
```

### Test Documentation

- [Test Framework Guide](./tests/README.md)
- [Writing Test Signals](./documentation/SIGNAL_TESTING_GUIDE.md)
- [4-Mode Testing Guide](./documentation/4_MODE_TESTING.md)

---

## 💾 MongoDB Schemas

Database: `mathematricks_trading` (Port: 27018)

### Signal Collections

#### `trading_signals_raw`

Raw signals received from external sources (before standardization).

```javascript
{
  _id: ObjectId,
  strategy_name: "MyStrategy",          // Required
  signal_sent_EPOCH: 1770055525,        // Required
  signalID: "signal_12345",             // Required (unique)
  passphrase: "your_passphrase",        // Required (validated)
  account_equity: 100000,               // Account size
  
  // Signal data (at least one required)
  signal_legs: [                        // NEW format (preferred)
    {
      instrument: "AAPL",
      instrument_type: "STOCK",         // STOCK | FOREX | OPTION | FUTURE | CRYPTO
      action: "BUY",                    // BUY | SELL
      direction: "LONG",                // LONG | SHORT
      quantity: 10,
      order_type: "MARKET",             // MARKET | LIMIT | STOP
      price: 150.25,
      environment: "staging"            // staging | production
    }
  ],
  signal: [],                           // LEGACY format (auto-converted)
  
  // Routing (determines execution path)
  signal_type: "ENTRY",                 // ENTRY | EXIT | SCALE_IN | SCALE_OUT
  environment: "staging",               // staging | production
  mode: "mock_mock",                    // mock_mock | mock_live | paper_live | live_live
  account_type: "mock",                 // mock | paper | live
  data_source: "mock",                  // mock | live
  
  // System metadata
  received_at: ISODate,
  signal_processed: false,
  mathematricks_signal_id: ObjectId    // Link to signal_store
}
```

#### `signal_store`

Consolidated signal lifecycle tracking (single document per signal with legs array).

```javascript
{
  _id: ObjectId,
  signal_id: "signal_12345",
  strategy_id: "MyStrategy",
  environment: "staging",
  mode: "paper_live",
  instrument: "AAPL",
  
  // LEGS ARRAY (Consolidated schema v3)
  legs: [
    {
      leg_id: "signal_12345__entry_0",
      leg_type: "ENTRY",                // ENTRY | EXIT | SCALE_IN | SCALE_OUT
      leg_index: 0,
      
      raw: {                            // Original signal data
        _id: ObjectId,
        received_at: ISODate,
        sent_epoch: 1770055525,
        signal_legs: [...]
      },
      
      decision: {                       // Cerebro decision
        status: "APPROVED",             // APPROVED | REJECTED
        reason: "Fund allocation: 60%",
        timestamp: ISODate,
        legs: [                         // Scaled quantities
          {
            instrument: "AAPL",
            action: "BUY",
            quantity: 100,              // SCALED (was 10)
            margin_required: 15000
          }
        ],
        math: "..."                     // Detailed calculation log
      },
      
      execution: {                      // Execution results
        status: "FILLED",               // PENDING | FILLED | REJECTED
        orders: [
          {
            order_id: "order_123",
            fund_id: "my-fund",
            account_id: "IBKR-ACCOUNT",
            quantity_filled: 100,
            avg_fill_price: 150.30,
            filled_at: ISODate
          }
        ],
        total_quantity_filled: 100,
        weighted_avg_price: 150.30
      }
    },
    {
      leg_id: "signal_12346__exit_1",
      leg_type: "EXIT",
      leg_index: 1,
      // ... same structure
    }
  ],
  
  // Position summary
  position: {
    status: "CLOSED",                   // PENDING | OPEN | CLOSED
    entry_quantity: 100,
    exit_quantity: 100,
    pnl: {
      gross: 500,
      net: 495,
      percent: 3.3,
      commission: 5
    }
  },
  
  created_at: ISODate,
  updated_at: ISODate,
  processing_complete: true
}
```

### Account & Fund Collections

#### `funds`

Fund management with approved allocations.

```javascript
{
  _id: ObjectId,
  fund_id: "my-fund",
  name: "My Trading Fund",
  total_equity: 1000000,                // Sum of all account equities
  currency: "USD",
  accounts: ["IBKR-ACCOUNT-1", "IBKR-ACCOUNT-2"],
  status: "ACTIVE",
  
  // Allocation snapshot (v5.2)
  approved_allocation: {
    portfolio_test_id: "test_001",
    allocations: {
      "Strategy1": 60.0,                // % allocation
      "Strategy2": 40.0
    },
    approved_at: ISODate,
    approved_by: "admin"
  },
  
  created_at: ISODate,
  updated_at: ISODate
}
```

#### `strategies`

Strategy configuration with mode-aware accounts.

```javascript
{
  _id: ObjectId,
  strategy_id: "MyStrategy",
  strategy_name: "My Strategy Name",
  asset_class: "equity",
  status: "ACTIVE",                     // ACTIVE | PAUSED | ARCHIVED
  trading_mode: "PAPER",                // PAPER | LIVE
  
  // Mode-aware accounts (v5)
  accounts: {
    mock: ["MOCK-ACCOUNT"],             // For mock_mock, mock_live
    paper: ["IBKR-PAPER-ACCOUNT"],      // For paper_live
    live: ["IBKR-LIVE-ACCOUNT"]         // For live_live
  },
  
  // Backtest metrics
  metrics: {
    sharpe_ratio: 1.5,
    max_drawdown: -0.15,
    total_return: 0.45
  },
  
  created_at: ISODate,
  updated_at: ISODate
}
```

#### `trading_accounts`

Broker account configuration and state.

```javascript
{
  _id: ObjectId,
  account_id: "IBKR-ACCOUNT",
  fund_id: "my-fund",                   // Link to fund
  broker: "IBKR",                       // IBKR | Mock | Coinbase | Kraken
  account_type: "paper",                // mock | paper | live
  mode: ["paper_live"],                 // Supported modes
  
  asset_classes: {
    equity: ["all"],
    options: ["SPY", "QQQ"],
    futures: [],
    crypto: []
  },
  
  authentication_details: {
    auth_type: "IBKR",
    host: "127.0.0.1",
    port: 4004,                         // 4004=paper, 4001=live
    client_id: 1
  },
  
  balances: {
    equity: 500000,
    cash_balance: 300000,
    margin_used: 50000,
    margin_available: 450000,
    buying_power: 1000000,
    last_updated: ISODate
  },
  
  open_positions: [
    {
      instrument: "AAPL",
      quantity: 100,
      avg_price: 150,
      current_price: 155,
      unrealized_pnl: 500,
      strategy_id: "MyStrategy"
    }
  ],
  
  status: "ACTIVE",
  created_at: ISODate,
  updated_at: ISODate
}
```

### Order Collection

#### `trading_orders`

Order lifecycle tracking.

```javascript
{
  _id: ObjectId,
  order_id: "order_12345",
  signal_store_id: ObjectId,            // Link to signal_store
  fund_id: "my-fund",
  account_id: "IBKR-ACCOUNT",
  strategy_id: "MyStrategy",
  
  instrument: "AAPL",
  instrument_type: "STOCK",
  action: "BUY",
  quantity: 100,
  order_type: "MARKET",
  limit_price: null,
  
  status: "FILLED",                     // PENDING | FILLED | REJECTED | CANCELLED
  quantity_filled: 100,
  avg_fill_price: 150.30,
  
  mode: "paper_live",
  broker_order_id: "IB_123456",
  
  created_at: ISODate,
  filled_at: ISODate,
  updated_at: ISODate
}
```

### Complete Schema Documentation

See: [MongoDB Schemas Reference](./documentation/MONGODB_SCHEMAS.md)

---

## 📚 Documentation

### Service Documentation

- [Signal Ingestion Service](./documentation/services/signal_ingestion.md)
- [Cerebro Service](./documentation/services/cerebro_service.md)
- [Execution Service](./documentation/services/execution_service.md)
- [Account Data Service](./documentation/services/account_data_service.md)
- [Portfolio Builder](./documentation/services/portfolio_builder.md)
- [Dashboard Creator](./documentation/services/dashboard_creator.md)

### Broker Documentation

- [IBKR Gateway Setup](./documentation/brokers/ibkr_gateway.md)
- [Mock Broker](./documentation/brokers/mock.md)
- [Coinbase](./documentation/brokers/coinbase.md)
- [Forex Residuals Guide](./documentation/brokers/FOREX_RESIDUALS_GUIDE.md)

### Guides

- [4-Mode Testing Guide](./documentation/4_MODE_TESTING.md)
- [Signal Testing Guide](./documentation/SIGNAL_TESTING_GUIDE.md)
- [Fund/Strategy/Account Setup](./documentation/FUND_SETUP_GUIDE.md)
- [Google Sheets Integration](./documentation/GOOGLE_SHEETS_INTEGRATION.md)

---

## 🔐 Security

### API Authentication

**Signal Receiver:**
- Passphrase validation (configurable via `WEBHOOK_PASSPHRASES` env var)
- Supports multiple passphrases (comma-separated)

**Position Endpoints:**
- `X-API-Key` header validation
- Strategy-specific API keys stored in `strategies` collection

### Production Checklist

- [ ] Set unique, strong passphrases
- [ ] Use different passphrases for staging vs production
- [ ] Enable Telegram alerts for live trading
- [ ] Test thoroughly in `paper_live` mode before `live_live`
- [ ] Set position size limits in fund configuration
- [ ] Monitor logs daily
- [ ] Set up backup MongoDB replica set

---

## 🐛 Troubleshooting

### Common Issues

**MongoDB Connection Failed:**
```bash
# Check MongoDB is running
docker ps | grep mongodb

# Check port 27018
docker-compose logs mongodb
```

**IB Gateway Not Connecting:**
```bash
# Check container status
docker ps | grep ib-gateway

# Check logs
docker logs ib-gateway-ibkr-testing-account

# Auto-detect port
python scripts/llm_dev_scripts/close_ibkr_positions.py --help
```

**Signal Not Processing:**
```bash
# Check signal-ingestion logs
make logs-signal-ingestion

# Verify signal in MongoDB
mongosh --port 27018
use mathematricks_trading
db.trading_signals_raw.findOne({signalID: "your_signal_id"})
```

**Order Not Executing:**
```bash
# Check execution service logs
make logs-execution

# Verify broker connection
curl http://localhost:8083/health
```

---

## 📊 Monitoring

### Logs

```bash
# All services
make logs

# Specific service
make logs-cerebro
make logs-execution
make logs-signal-receiver

# Follow logs (real-time)
docker-compose logs -f cerebro-service
```

### Admin Dashboard

**URL:** http://localhost:3001

**Features:**
- Real-time signal tracking
- Position monitoring
- Account balances
- System health
- Order history

### Telegram Alerts

Configure Telegram for real-time notifications:

```bash
# .env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 🤝 Contributing

### Development Workflow

1. Create feature branch
2. Write tests
3. Update documentation
4. Test in `mock_mock` mode
5. Test in `mock_live` mode
6. Submit PR

### Adding a New Service

See: [Service Development Guide](./documentation/SERVICE_DEVELOPMENT_GUIDE.md)

### Adding a New Broker

See: [Custom Broker Guide](./documentation/brokers/CUSTOM_BROKER_GUIDE.md)