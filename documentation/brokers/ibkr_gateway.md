# IBKR (Interactive Brokers) Gateway Documentation

Complete guide for Interactive Brokers integration via IB Gateway and TWS (Trader Workstation).

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [IBKR Gateway vs TWS](#ibkr-gateway-vs-tws)
- [Port Configuration](#port-configuration)
- [Paper Trading Setup](#paper-trading-setup)
- [Live Trading Setup](#live-trading-setup)
- [4-Mode Integration](#4-mode-integration)
- [Configuration](#configuration)
- [Docker Container Setup](#docker-container-setup)
- [Connection Management](#connection-management)
- [Order Management](#order-management)
- [Market Data](#market-data)
- [Supported Instruments](#supported-instruments)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The IBKR broker integration uses the `ib_insync` library to connect to Interactive Brokers Gateway or TWS for:

- ✅ Multi-asset trading (stocks, options, futures, forex, crypto)
- ✅ Real-time market data
- ✅ Paper trading (virtual money)
- ✅ Live trading (real money)
- ✅ Advanced order types
- ✅ Margin calculations

**Implementation:** [services/brokers/ibkr/ibkr_broker.py](../../services/brokers/ibkr/ibkr_broker.py)

## Features

### Supported Markets

| Market | Examples | Status |
|--------|----------|--------|
| **US Stocks** | AAPL, TSLA, GOOGL | ✅ Full support |
| **Options** | AAPL calls/puts, spreads | ✅ Full support (multi-leg) |
| **Futures** | ES, NQ, CL, GC | ✅ Full support |
| **Forex** | EURUSD, GBPJPY | ✅ Full support |
| **Crypto** | BTC, ETH | ✅ Via PAXOS exchange |
| **ETFs** | SPY, QQQ, IWM | ✅ Full support |

### Order Types

- Market orders
- Limit orders
- Stop orders
- Stop-limit orders
- Multi-leg option orders

### Real-Time Data

- Bid/ask spreads
- Last price
- Market depth (Level 2)
- Delayed or live data (depends on subscription)

### Advanced Features

- `whatIfOrder()` - Preview margin impact before placing order
- Automatic contract qualification
- Multi-leg option strategies
- Fractional crypto trading

## IBKR Gateway vs TWS

### IB Gateway (Recommended)

**Lightweight API server** - No GUI, minimal resources:

```
Pros:
✅ Lightweight (< 200MB RAM)
✅ Headless (no GUI needed)
✅ Stable for automation
✅ Docker-compatible
✅ Auto-restart on connection loss

Cons:
❌ No charts/GUI
❌ Manual startup (or Docker)
```

**Download:** https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

### TWS (Trader Workstation)

**Full trading platform** - GUI with charts:

```
Pros:
✅ Full GUI interface
✅ Charts and analysis tools
✅ Built-in monitoring
✅ Easy manual trading

Cons:
❌ Heavy (> 1GB RAM)
❌ Requires display
❌ More complex setup
```

**Download:** https://www.interactivebrokers.com/en/trading/tws.php

### Recommendation

- **Development/Production:** Use IB Gateway (headless, stable)
- **Manual Trading/Monitoring:** Use TWS (full GUI)

## Port Configuration

IBKR uses different ports for paper vs live accounts:

### IB Gateway Ports

| Account Type | Port | Environment | Risk Level |
|-------------|------|-------------|------------|
| **Paper** | **4004** | Simulated | ✅ Zero (virtual money) |
| **Live** | **4001** | Production | ⚠️ HIGH (real money) |

### TWS Ports

| Account Type | Port | Environment | Risk Level |
|-------------|------|-------------|------------|
| **Paper** | **7497** | Simulated | ✅ Zero (virtual money) |
| **Live** | **7496** | Production | ⚠️ HIGH (real money) |

### Configuration Examples

```python
# Paper trading via IB Gateway (RECOMMENDED)
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4004,  # Paper account
    "client_id": 1,
    "account_id": "DU123456"  # Paper account ID
}

# Live trading via IB Gateway (⚠️ REAL MONEY)
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4001,  # Live account
    "client_id": 1,
    "account_id": "U123456"  # Live account ID
}

# Paper trading via TWS
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 7497,  # TWS Paper
    "client_id": 1,
    "account_id": "DU123456"
}
```

## Paper Trading Setup

### Step 1: Open IBKR Paper Account

1. Go to https://www.interactivebrokers.com
2. Log into Client Portal
3. Navigate to **Settings → Trading → Paper Trading**
4. Enable paper trading account
5. Note your paper account ID (starts with "DU")

### Step 2: Install IB Gateway

Download and install:
```bash
# macOS
open https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-macos-x64.dmg

# Linux
wget https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh
chmod +x ibgateway-stable-standalone-linux-x64.sh
./ibgateway-stable-standalone-linux-x64.sh
```

### Step 3: Configure IB Gateway

1. Launch IB Gateway
2. Select **Paper Trading** mode
3. Enter your IBKR username and password
4. Go to **Configuration → API → Settings**:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Read-Only API: **NO** (we need trading permissions)
   - ✅ Port: **4004** (default for paper)
   - ✅ Trusted IPs: Add `127.0.0.1`
   - ✅ Master API client ID: Leave empty or set to 0

### Step 4: Test Connection

```python
from services.brokers.ibkr import IBKRBroker

config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4004,
    "client_id": 1,
    "account_id": "DU123456"  # Your paper account ID
}

broker = IBKRBroker(config)

if broker.connect():
    print("✅ Connected to IBKR Paper Trading")
    balance = broker.get_account_balance()
    print(f"Paper Account Balance: ${balance['equity']:,.2f}")
    broker.disconnect()
else:
    print("❌ Connection failed")
```

### Step 5: MongoDB Account Document

Add paper account to `trading_accounts` collection:

```json
{
  "account_id": "IBKR_Paper",
  "account_name": "IBKR Paper Trading Account",
  "broker": "IBKR",
  "account_number": "DU123456",
  "account_type": "paper",
  "data_source": "live",
  "mode": "paper_live",
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4004,
    "client_id": 1
  },
  "balances": {
    "equity": 1000000.0,
    "cash_balance": 1000000.0,
    "margin_used": 0.0,
    "margin_available": 1000000.0,
    "buying_power": 4000000.0,
    "unrealized_pnl": 0.0,
    "realized_pnl": 0.0,
    "last_updated": "2025-01-07T12:00:00Z"
  },
  "open_positions": [],
  "status": "ACTIVE",
  "created_at": "2025-01-07T12:00:00Z",
  "updated_at": "2025-01-07T12:00:00Z"
}
```

### Step 6: Test Paper Trading

```bash
# Run paper trading test
python tests/run_test_suite.py \
  --signal-testing \
  --environment staging \
  --account-type paper \
  --data-source live \
  --file tests/sample_signals/stock_trading.json \
  --signal-count 3
```

## Live Trading Setup

> ⚠️ **DANGER: LIVE TRADING USES REAL MONEY**  
> Only proceed if you have thoroughly tested in paper trading and understand the risks.

### Step 1: Fund Live Account

1. Open live IBKR account
2. Complete verification
3. Fund account (minimum $10,000 for margin)
4. Note your live account ID (starts with "U")

### Step 2: Configure IB Gateway for Live

1. Launch IB Gateway
2. Select **Live Trading** mode
3. Enter credentials
4. Go to **Configuration → API → Settings**:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Read-Only API: **NO**
   - ✅ Port: **4001** (default for live)
   - ✅ Trusted IPs: `127.0.0.1`
   - ⚠️ **WARNING: Double-check this is port 4001, not 4004!**

### Step 3: Configure Live Account

```python
# ⚠️ LIVE TRADING CONFIGURATION - REAL MONEY AT RISK
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4001,  # LIVE PORT - DOUBLE CHECK!
    "client_id": 1,
    "account_id": "U123456"  # Live account ID (starts with U)
}
```

### Step 4: MongoDB Live Account

```json
{
  "account_id": "IBKR_Live",
  "account_name": "IBKR Live Trading Account",
  "broker": "IBKR",
  "account_number": "U123456",
  "account_type": "live",
  "data_source": "live",
  "mode": "live_live",
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4001,  // ⚠️ LIVE PORT
    "client_id": 1
  },
  "risk_limits": {
    "max_position_size": 10000,
    "max_daily_loss": 5000,
    "max_open_positions": 10
  },
  "status": "ACTIVE"
}
```

### Step 5: Safety Checks

Before going live:

1. ✅ Test extensively in paper mode (minimum 1 month)
2. ✅ Verify all strategies are profitable in paper
3. ✅ Set risk limits in MongoDB
4. ✅ Enable monitoring and alerts
5. ✅ Start with small position sizes
6. ✅ Monitor first trades manually
7. ✅ Have kill switch ready

### Step 6: Live Trading Test

```bash
# ⚠️ THIS WILL PLACE REAL ORDERS WITH REAL MONEY
python tests/run_test_suite.py \
  --signal-testing \
  --environment production \
  --account-type live \
  --data-source live \
  --file tests/sample_signals/conservative_test.json \
  --signal-count 1  # Start with just 1 order!
```

## 4-Mode Integration

IBKR broker is used in three of the four trading modes:

### mock_live Mode

Mock account with live IBKR pricing:

```json
{
  "account_id": "Mock_Live",
  "broker": "Mock",
  "account_type": "mock",
  "data_source": "live",
  "mode": "mock_live",
  "authentication_details": {
    "ibkr_host": "127.0.0.1",
    "ibkr_port": 4004,  // Paper port for pricing
    "ibkr_client_id": 2
  }
}
```

**BrokerModeAdapter** wraps Mock + IBKR:
- Orders → Mock broker (instant fills)
- Pricing → IBKR (real market data)

### paper_live Mode

IBKR paper account with live data:

```json
{
  "account_id": "IBKR_Paper",
  "broker": "IBKR",
  "account_type": "paper",
  "data_source": "live",
  "mode": "paper_live",
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4004,  // Paper port
    "client_id": 1
  }
}
```

**Direct IBKR connection:**
- Orders → IBKR paper account
- Pricing → IBKR live data

### live_live Mode

IBKR live account (production):

```json
{
  "account_id": "IBKR_Live",
  "broker": "IBKR",
  "account_type": "live",
  "data_source": "live",
  "mode": "live_live",
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4001,  // ⚠️ LIVE PORT
    "client_id": 1
  }
}
```

**Direct IBKR connection:**
- Orders → IBKR live account (real money)
- Pricing → IBKR live data

## Configuration

### Basic Configuration

```python
from services.brokers.ibkr import IBKRBroker

config = {
    "broker": "IBKR",
    "host": "127.0.0.1",  # IB Gateway/TWS host
    "port": 4004,          # Port (see table above)
    "client_id": 1,        # Unique client ID (1-32)
    "account_id": "DU123456"  # Your IBKR account ID
}

broker = IBKRBroker(config)
```

### Advanced Configuration

```python
config = {
    "broker": "IBKR",
    "host": "127.0.0.1",
    "port": 4004,
    "client_id": 1,
    "account_id": "DU123456",
    "market_data_type": 1  # Optional: 1=Live, 3=Delayed, 4=Delayed Frozen
}
```

### Market Data Types

| Type | Description | Cost | Use Case |
|------|-------------|------|----------|
| **1** | Live | Requires subscription | Production trading |
| **2** | Frozen | Deprecated | (Avoid) |
| **3** | Delayed | Free (10-15 min delay) | Testing/development |
| **4** | Delayed Frozen | Free (most compatible) | Paper accounts |

If not specified, the broker auto-detects:
- Paper accounts (port 4004/7497): Tries 1 (live), falls back to 3, then 4
- Live accounts (port 4001/7496): Requests 1 (live)

## Docker Container Setup

Running IB Gateway in a Docker container for headless automation:

### Using Docker Compose

Create `docker-compose.ibgateway.yml`:

```yaml
version: '3.8'

services:
  ibgateway:
    image: ghcr.io/gnzsnz/ib-gateway:latest
    container_name: ibgateway
    ports:
      - "4004:4004"  # Paper trading port
      - "4001:4001"  # Live trading port (optional)
    environment:
      - TRADING_MODE=paper  # or 'live'
      - TWS_USERID=${IBKR_USERNAME}
      - TWS_PASSWORD=${IBKR_PASSWORD}
      - VNC_SERVER_PASSWORD=vncpassword
      - TWOFA_TIMEOUT_ACTION=restart
    volumes:
      - ibgateway-data:/root/Jts
    restart: unless-stopped

volumes:
  ibgateway-data:
```

### Environment Variables

Create `.env` file:

```bash
# IBKR Credentials
IBKR_USERNAME=your_username
IBKR_PASSWORD=your_password

# Account IDs
IBKR_PAPER_ACCOUNT=DU123456
IBKR_LIVE_ACCOUNT=U123456
```

### Start Container

```bash
# Start IB Gateway container
docker-compose -f docker-compose.ibgateway.yml up -d

# View logs
docker-compose -f docker-compose.ibgateway.yml logs -f ibgateway

# Stop container
docker-compose -f docker-compose.ibgateway.yml down
```

### VNC Access

If you need to view/configure the GUI:

```bash
# Access VNC at:
# vnc://localhost:5900
# Password: vncpassword
```

### Health Check

```python
from services.brokers.ibkr import IBKRBroker

broker = IBKRBroker({
    "broker": "IBKR",
    "host": "localhost",  # or container name if in same network
    "port": 4004,
    "client_id": 1,
    "account_id": "DU123456"
})

assert broker.connect(), "Failed to connect to IB Gateway container"
print("✅ IB Gateway container is healthy")
```

## Connection Management

### Basic Connection

```python
broker = IBKRBroker(config)

# Connect
if broker.connect():
    print("Connected")
else:
    print("Connection failed")

# Check connection
if broker.is_connected():
    print("Still connected")

# Disconnect
broker.disconnect()
```

### Auto-Retry on Client ID Conflict

IBKR broker automatically retries with different client IDs if the specified one is in use:

```python
# If client_id=1 is already in use, automatically tries 2, 3, 4, 5
broker = IBKRBroker({"client_id": 1, ...})
broker.connect()  # May connect with client_id=2 if 1 is busy

print(f"Connected with client_id: {broker.client_id}")
```

### Skip Position Sync (Fast Connection)

For market data only (no orders):

```python
# Skip waiting for positions/orders sync
broker.connect(skip_sync=True)
# Much faster connection (200ms vs 500ms)
```

### Connection Errors

```python
from services.brokers.exceptions import BrokerConnectionError

try:
    broker.connect()
except BrokerConnectionError as e:
    print(f"Connection failed: {e}")
    print(f"Broker: {e.broker_name}")
    print(f"Details: {e.details}")
```

## Order Management

### Place Market Order

```python
order = {
    'instrument': 'AAPL',
    'direction': 'LONG',
    'quantity': 100,
    'order_type': 'MARKET',
    'instrument_type': 'STOCK'
}

result = broker.place_order(order)

print(f"Order ID: {result['broker_order_id']}")
print(f"Status: {result['status']}")
print(f"Filled: {result['filled']}")
print(f"Avg Price: ${result['avg_fill_price']:.2f}")
```

### Place Limit Order

```python
order = {
    'instrument': 'TSLA',
    'direction': 'LONG',
    'quantity': 50,
    'order_type': 'LIMIT',
    'limit_price': 200.00,
    'instrument_type': 'STOCK'
}

result = broker.place_order(order)
```

### Multi-Leg Option Order

```python
# Buy call spread: Buy 150 call, sell 160 call
order = {
    'instrument': 'AAPL',
    'instrument_type': 'OPTION',
    'direction': 'LONG',
    'quantity': 1,
    'order_type': 'MARKET',
    'underlying': 'AAPL',
    'legs': [
        {
            'strike': 150,
            'expiry': '20250117',
            'right': 'CALL',
            'action': 'BUY',
            'quantity': 1
        },
        {
            'strike': 160,
            'expiry': '20250117',
            'right': 'CALL',
            'action': 'SELL',
            'quantity': 1
        }
    ]
}

result = broker.place_order(order)
print(f"Multi-leg order: {result['num_legs']} legs submitted")
```

### Forex Order

```python
order = {
    'instrument': 'EURUSD',
    'instrument_type': 'FOREX',
    'direction': 'LONG',
    'quantity': 10000,  # 10,000 EUR
    'order_type': 'MARKET'
}

result = broker.place_order(order)
```

### Futures Order

```python
order = {
    'instrument': 'GC',  # Gold futures
    'instrument_type': 'FUTURE',
    'direction': 'LONG',
    'quantity': 2,
    'order_type': 'MARKET',
    'expiry': '20250224',
    'exchange': 'COMEX'
}

result = broker.place_order(order)
```

### Crypto Order

```python
order = {
    'instrument': 'BTC',
    'instrument_type': 'CRYPTO',
    'direction': 'LONG',
    'quantity': 0.1,  # Fractional BTC
    'order_type': 'MARKET',
    'price': 42000.00  # For cash quantity calculation
}

result = broker.place_order(order)
```

### Cancel Order

```python
broker_order_id = result['broker_order_id']

if broker.cancel_order(broker_order_id):
    print("Order cancelled")
else:
    print("Cancel failed")
```

### Get Order Status

```python
status = broker.get_order_status(broker_order_id)

print(f"Status: {status['status']}")
print(f"Filled: {status['filled_quantity']}")
print(f"Remaining: {status['remaining_quantity']}")
print(f"Avg Price: ${status['avg_fill_price']:.2f}")

for fill in status['fills']:
    print(f"  Fill: {fill['quantity']} @ ${fill['price']:.2f}")
```

## Market Data

### Get Current Market Price

```python
# Get real-time price
price = broker.get_market_price('AAPL', 'STOCK')
print(f"AAPL: ${price:.2f}")

# Forex
price = broker.get_market_price('EURUSD', 'FOREX')
print(f"EURUSD: {price:.5f}")

# Crypto
price = broker.get_market_price('BTC', 'CRYPTO')
print(f"BTC: ${price:.2f}")
```

### Market Price with Retry

The broker automatically retries with exponential backoff:

```python
# Retries up to 5 times with 1s, 2s, 4s, 8s, 16s delays
price = broker.get_market_price('AAPL', 'STOCK')
# Logs detailed bid/ask/spread information
```

### Margin Impact Preview

Preview margin requirements before placing order:

```python
order = {
    'instrument': 'GC',
    'instrument_type': 'FUTURE',
    'direction': 'LONG',
    'quantity': 2,
    'order_type': 'MARKET',
    'expiry': '20250224',
    'exchange': 'COMEX'
}

# Get margin impact without placing order
margin = broker.get_order_margin_impact(order)

print(f"Initial Margin Required: ${margin['init_margin_change']:,.2f}")
print(f"Maintenance Margin: ${margin['maint_margin_change']:,.2f}")
print(f"Commission: ${margin['commission']:.2f}")

# Decide whether to place order based on margin
if margin['init_margin_change'] < max_margin:
    broker.place_order(order)
else:
    print("Order exceeds margin limits")
```

## Supported Instruments

### Stocks

```python
order = {
    'instrument': 'AAPL',
    'instrument_type': 'STOCK',
    'direction': 'LONG',
    'quantity': 100,
    'order_type': 'MARKET'
}
```

**Exchanges:** SMART (auto-routes to best), NYSE, NASDAQ, ARCA

### ETFs

```python
order = {
    'instrument': 'SPY',
    'instrument_type': 'ETF',
    'direction': 'LONG',
    'quantity': 50,
    'order_type': 'MARKET'
}
```

### Options

```python
# Single option
order = {
    'instrument': 'AAPL',
    'instrument_type': 'OPTION',
    'direction': 'LONG',
    'quantity': 1,
    'order_type': 'MARKET',
    'underlying': 'AAPL',
    'legs': [
        {
            'strike': 150,
            'expiry': '20250117',  # YYYYMMDD
            'right': 'CALL',  # or 'PUT'
            'action': 'BUY',
            'quantity': 1
        }
    ]
}
```

**Right values:** "C", "P", "CALL", "PUT"  
**Expiry format:** YYYYMMDD (e.g., "20250117")

### Futures

```python
order = {
    'instrument': 'ES',  # E-mini S&P 500
    'instrument_type': 'FUTURE',
    'direction': 'LONG',
    'quantity': 1,
    'order_type': 'MARKET',
    'expiry': '20250321',
    'exchange': 'CME'
}
```

**Common symbols:**
- ES: E-mini S&P 500
- NQ: E-mini Nasdaq
- CL: Crude Oil
- GC: Gold
- SI: Silver

### Forex

```python
order = {
    'instrument': 'EURUSD',  # 6-character pair
    'instrument_type': 'FOREX',
    'direction': 'LONG',
    'quantity': 10000,  # Whole units
    'order_type': 'MARKET'
}
```

**Precision:** IBKR uses whole units (0 decimals), not fractional

### Crypto

```python
order = {
    'instrument': 'BTC',
    'instrument_type': 'CRYPTO',
    'direction': 'LONG',
    'quantity': 0.5,  # Fractional allowed
    'order_type': 'MARKET',
    'price': 42000.00  # For cash quantity calculation
}
```

**Exchange:** PAXOS (IBKR's crypto exchange)  
**Note:** IBKR requires `cashQty` (USD amount) instead of quantity for crypto

## Troubleshooting

### Error 326: Client ID Already in Use

**Error:**
```
ConnectionRefusedError: clientId 1 is already in use
```

**Solution:**

IBKR broker auto-retries with different client IDs:
```python
# Automatically tries 1, 2, 3, 4, 5 until successful
broker.connect()
print(f"Connected with client_id: {broker.client_id}")
```

Or manually specify different ID:
```python
config["client_id"] = 2  # Use different ID
```

### Connection Refused

**Error:**
```
BrokerConnectionError: Failed to connect to IBKR at 127.0.0.1:4004
```

**Solution:**

1. Check IB Gateway/TWS is running:
```bash
ps aux | grep ibgateway
# or
ps aux | grep tws
```

2. Verify port:
```bash
netstat -an | grep 4004
# Should show LISTEN on port 4004
```

3. Check API settings in IB Gateway:
   - Configuration → API → Settings
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Port matches config
   - ✅ Trusted IPs includes 127.0.0.1

4. Restart IB Gateway

### Market Data Not Available

**Error:**
```
BrokerAPIError: No market data available for AAPL (STOCK) after 5 attempts
```

**Solution:**

1. Check market data subscription in TWS
2. Try different market data type:
```python
config["market_data_type"] = 3  # Delayed data (free)
```

3. Verify market hours (AAPL trades 9:30-16:00 ET)
4. For forex/crypto (24/5 or 24/7), check exchange status

### Order Rejected

**Error:**
```
OrderRejectedError: Order rejected by IBKR
```

**Common causes:**

1. **Insufficient buying power**
   ```python
   balance = broker.get_account_balance()
   print(f"Buying power: ${balance['buying_power']:,.2f}")
   ```

2. **Invalid symbol**
   ```python
   # Ensure symbol is correct
   # IBKR auto-qualifies contracts, but invalid symbols fail
   ```

3. **Market closed**
   ```python
   # Check market hours
   # Use extended hours if needed: order["tif"] = "GTC"
   ```

4. **Insufficient margin (futures/options)**
   ```python
   # Check margin requirements
   margin = broker.get_order_margin_impact(order)
   ```

### Timeout Errors

**Error:**
```
BrokerTimeoutError: Request timed out
```

**Solution:**

1. Increase timeout in ib_insync (default 60s)
2. Check network latency
3. Restart IB Gateway
4. For market data, use retry logic (built-in)

### Contract Qualification Failed

**Error:**
```
InvalidSymbolError: Failed to qualify contract: Stock('INVALID', 'SMART', 'USD')
```

**Solution:**

1. Verify symbol spelling
2. Check instrument type matches symbol
3. For futures/options, ensure expiry is valid
4. Use IBKR's Symbol Search in TWS to confirm

## Best Practices

### 1. Connection Management

```python
# Reuse connection instead of connect/disconnect repeatedly
broker.connect()
try:
    # Do multiple operations
    for signal in signals:
        broker.place_order(signal)
finally:
    broker.disconnect()
```

### 2. Error Handling

```python
from services.brokers.exceptions import *

try:
    result = broker.place_order(order)
except OrderRejectedError as e:
    logger.error(f"Order rejected: {e.rejection_reason}")
    # Handle rejection
except InsufficientFundsError as e:
    logger.error(f"Insufficient funds: {e}")
    # Reduce position size
except BrokerAPIError as e:
    logger.error(f"API error: {e}")
    # Retry or alert
```

### 3. Paper Testing First

```python
# ALWAYS test in paper mode before going live
assert config["port"] == 4004, "Must use paper port for testing"
assert "DU" in config["account_id"], "Must use paper account (DU...)"
```

### 4. Margin Checks

```python
# Check margin before placing order
margin = broker.get_order_margin_impact(order)
if margin['init_margin_change'] > available_margin:
    logger.warning("Insufficient margin, reducing size")
    order['quantity'] = order['quantity'] // 2
```

### 5. Monitor Fills

```python
# After placing order, verify fill
result = broker.place_order(order)
if result['status'] != 'Filled':
    # Wait and check status
    time.sleep(2)
    status = broker.get_order_status(result['broker_order_id'])
    if status['status'] == 'Filled':
        logger.info(f"Order filled: {status['filled_quantity']} @ ${status['avg_fill_price']}")
```

### 6. Quantity Precision

```python
# Use broker's precision for quantity
precision = broker.get_quantity_precision('AAPL', 'STOCK')
# precision = 0 for stocks (integers)

quantity = 100.7  # From calculation
quantity = round(quantity) if precision == 0 else round(quantity, precision)
# quantity = 101 (rounded to integer)
```

### 7. Use whatIfOrder for Safety

```python
# Preview margin impact before risky trades
if order['instrument_type'] in ['FUTURE', 'OPTION']:
    margin = broker.get_order_margin_impact(order)
    logger.info(f"Margin required: ${margin['init_margin_change']:,.2f}")
    
    # Only proceed if margin is acceptable
    if margin['init_margin_change'] < max_acceptable_margin:
        broker.place_order(order)
```

### 8. Log Everything

```python
import logging
logging.basicConfig(level=logging.INFO)

# IBKR broker logs extensively:
# - Connection attempts/retries
# - Market data requests
# - Order submissions
# - Fill confirmations
# - Errors/rejections
```

### 9. Set Up Monitoring

```python
# Monitor account balance
balance = broker.get_account_balance()
if balance['equity'] < min_equity_threshold:
    logger.critical(f"⚠️ Equity below threshold: ${balance['equity']:,.2f}")
    # Trigger alert, stop trading

# Monitor open positions
positions = broker.get_open_positions()
if len(positions) > max_positions:
    logger.warning(f"⚠️ Too many positions: {len(positions)}")
```

### 10. Graceful Shutdown

```python
import signal

def shutdown_handler(signum, frame):
    logger.info("Shutting down gracefully...")
    broker.disconnect()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)
```

## See Also

- [Abstract Broker Interface](../../services/brokers/base.py)
- [IBKR Broker Implementation](../../services/brokers/ibkr/ibkr_broker.py)
- [BrokerModeAdapter](../../services/brokers/adapters/mode_adapter.py)
- [Exception Definitions](../../services/brokers/exceptions.py)
- [IBKR API Documentation](https://interactivebrokers.github.io/tws-api/)
- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
