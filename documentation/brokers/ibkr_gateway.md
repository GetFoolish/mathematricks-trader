# IBKR Gateway Setup Guide

Complete guide for setting up and using Interactive Brokers Gateway for paper and live trading.

## Overview

Interactive Brokers Gateway (IB Gateway) is a lightweight application that provides API access to IBKR's trading platform without requiring the full Trader Workstation (TWS).

**Use Cases**:
- Automated trading via API
- Headless server deployments
- Paper trading for testing
- Live trading in production

---

## Prerequisites

1. **IBKR Account**:
   - Paper trading account (for testing)
   - Live trading account (for production)
   - API access enabled

2. **Account Configuration**:
   - Enable API connections in IBKR Account Management
   - Set up socket port (4002 for paper, 4001 for live)
   - Configure trusted IP addresses (optional but recommended)

---

## Installation

### Option 1: Docker (Recommended)

Uses the `ghcr.io/gnzsnz/ib-gateway` Docker image with IBC (IB Controller) for automated login.

**Docker Compose** (already configured in project):
```yaml
# docker-compose.yml
ibgateway:
  image: ghcr.io/gnzsnz/ib-gateway:stable
  container_name: mathematricks-trader-ibgateway-1
  ports:
    - "4002:4002"  # Paper trading port
    - "5900:5900"  # VNC for monitoring (optional)
  environment:
    - TWS_USERID=${IBKR_USERNAME}
    - TWS_PASSWORD=${IBKR_PASSWORD}
    - TRADING_MODE=paper
    - VNC_SERVER_PASSWORD=ibgateway  # For VNC access
  restart: unless-stopped
```

**Start IB Gateway**:
```bash
# Start with Docker Compose
docker-compose up -d ibgateway

# Check status
docker ps | grep ibgateway

# View logs
docker logs mathematricks-trader-ibgateway-1 -f
```

**VNC Monitoring** (optional):
```bash
# Connect via VNC to see IB Gateway GUI
# Host: localhost:5900
# Password: ibgateway (from environment variable)
```

---

### Option 2: Standalone Installation

Download from IBKR website:
- [IB Gateway Download](https://www.interactivebrokers.com/en/index.php?f=16457)

**Installation Steps**:
1. Download IB Gateway for your OS
2. Install following prompts
3. Configure for paper or live trading
4. Start IB Gateway and login

---

## Configuration

### Paper Trading Setup

**Port**: `4002`  
**TRADING_MODE**: `paper`

**MongoDB Account Configuration**:
```javascript
{
  "account_id": "IBKR-TESTING-ACCOUNT",
  "broker": "IBKR",
  "mode": "paper_live",  // Use real data, mock fills
  "market_data_type": 1,  // Live market data
  "status": "ACTIVE",
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4002,  // Paper trading port
    "client_id": 1,
    "account_id": "DU1234567"  // Your IBKR paper account ID
  },
  "strategy_ids": ["UPRO_NewYork", "SPY_NewYork"]
}
```

**Environment Variables** (.env):
```bash
# IBKR Gateway Credentials
IBKR_USERNAME=your_username
IBKR_PASSWORD=your_password
TRADING_MODE=paper

# Market Data Subscription
# Set to 1 if you have live data subscription
# Set to 3 for delayed data (free)
MARKET_DATA_TYPE=1
```

---

### Live Trading Setup

**⚠️ WARNING: LIVE TRADING INVOLVES REAL MONEY**

**Port**: `4001` (different from paper!)  
**TRADING_MODE**: `live`

**MongoDB Account Configuration**:
```javascript
{
  "account_id": "IBKR-LIVE-ACCOUNT",
  "broker": "IBKR",
  "mode": "live",  // REAL TRADING MODE
  "market_data_type": 1,
  "status": "ACTIVE",
  "authentication_details": {
    "host": "127.0.0.1",
    "port": 4001,  // LIVE trading port (NOT 4002!)
    "client_id": 1,
    "account_id": "U1234567"  // Your IBKR live account ID (starts with U)
  }
}
```

**Environment Variables** (.env):
```bash
# Enable live trading (safety flag)
ALLOW_LIVE_TRADING=true

# IBKR Gateway Credentials
IBKR_USERNAME=your_live_username
IBKR_PASSWORD=your_live_password
TRADING_MODE=live

# Docker Compose Configuration
IBKR_PORT=4001  # Live port
```

**Safety Checklist**:
- [ ] Tested extensively in paper_live mode
- [ ] Verified all order flows work correctly
- [ ] Set position size limits
- [ ] Configured Telegram alerts
- [ ] Double-checked port is 4001 (not 4002!)
- [ ] Account ID starts with 'U' (not 'DU')
- [ ] Set `ALLOW_LIVE_TRADING=true` in .env

---

## Port Configuration

| Mode | Port | Account ID Prefix | Risk |
|------|------|-------------------|------|
| **Paper Trading** | 4002 | DU (e.g., DU1234567) | Zero - simulated money |
| **Live Trading** | 4001 | U (e.g., U1234567) | **REAL MONEY** |

**Critical**: Using wrong port can result in:
- Paper trades going to live account (financial loss!)
- Live trades being rejected
- Connection failures

**Verify Port**:
```bash
# Check which port is configured in MongoDB
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --quiet --eval \
  'db.trading_accounts.findOne({account_id: "IBKR-TESTING-ACCOUNT"}).authentication_details.port'

# Should return: 4002 (for paper)
```

---

## Connection Testing

### Test Paper Trading Connection

```bash
# 1. Start IB Gateway (if not running)
docker-compose up -d ibgateway

# 2. Wait for startup (30-60 seconds)
sleep 60

# 3. Test connection
docker logs mathematricks-trader-ibgateway-1 | grep "API connection"

# Expected: "API connection successful"
```

### Test from Python

```python
from ib_insync import IB

ib = IB()

# Test paper trading connection
ib.connect('127.0.0.1', 4002, clientId=1)

if ib.isConnected():
    print("✅ Connected to IBKR Paper Trading")
    print(f"Accounts: {ib.managedAccounts()}")
else:
    print("❌ Connection failed")

ib.disconnect()
```

### Use Pre-Flight Check

```bash
# Run automated checks (includes IB Gateway connection test)
python3 scripts/preflight_check.py
```

Expected output:
```
======================================================================
CHECK: 3. IB Gateway Connected
======================================================================
✅ PASS: IB Gateway listening on 127.0.0.1:4002
```

---

## Market Data Subscriptions

IBKR requires market data subscriptions for real-time prices.

### Market Data Types

| Type | Name | Subscription Required | Cost | Use Case |
|------|------|----------------------|------|----------|
| **1** | Live/Real-time | Yes | $$$ | Production, paper_live testing |
| **2** | Frozen | No | Free | Not useful (stale) |
| **3** | Delayed (15 min) | No | Free | Fallback for paper_live |
| **4** | Delayed Frozen | No | Free | Last resort |

### Check Your Subscription

1. Login to [IBKR Account Management](https://www.interactivebrokers.com/portal)
2. Go to **Settings** → **Market Data Subscriptions**
3. Check if you have subscriptions for:
   - **US Securities Snapshot and Futures** (for US stocks)
   - **US Equity and Options Add-On Streaming** (for real-time streaming)

### Smart Fallback (Type 1 → 3 → 4)

The system automatically falls back to delayed data if live data is unavailable:

```python
# In ibkr_broker.py
market_data_type = account.get('market_data_type', 1)

# Request type 1 (live)
ib.reqMarketDataType(1)

# If type 1 fails (no subscription), automatically try type 3 (delayed)
# If type 3 fails, try type 4 (delayed frozen)
```

**Configuration**:
```javascript
// MongoDB trading_accounts
{
  "market_data_type": 1,  // Request live data (will fallback to 3, then 4)
}
```

**Logs to Watch**:
```
Requesting market data type: 1 (live/real-time)
⚠️ Market data type 1 not available, falling back to type 3 (delayed)
✅ Market data type 3 (delayed) available
```

---

## Troubleshooting

### Connection Refused

**Symptom**: `Connection refused on 127.0.0.1:4002`

**Causes**:
1. IB Gateway not running
2. Wrong port (4002 vs 4001)
3. IB Gateway not fully started yet

**Solutions**:
```bash
# Check if IB Gateway is running
docker ps | grep ibgateway

# Check logs for startup completion
docker logs mathematricks-trader-ibgateway-1 | tail -20

# Restart IB Gateway
docker-compose restart ibgateway

# Wait 60 seconds for full startup
sleep 60
```

---

### "Invalid clientId" Error

**Symptom**: `Client ID already in use`

**Cause**: Another application is using the same client ID

**Solution**: Use different client IDs for each connection:
- Execution Service: client_id = 1
- Account Data Service: client_id = 2
- Other services: client_id = 3, 4, 5, etc.

```javascript
// In MongoDB authentication_details
{
  "client_id": 1  // Unique per service
}
```

---

### "No market data subscription" Error

**Symptom**: Bid/ask/last all return `nan` or `null`

**Cause**: No market data subscription for type 1

**Solutions**:
1. **Get subscription**: Subscribe to market data in IBKR Account Management
2. **Use delayed data**: System automatically falls back to type 3 (delayed)
3. **Check fallback worked**:
   ```bash
   docker logs mathematricks-trader-execution-service-1 | grep "market data type"
   ```

---

### Authentication Failures

**Symptom**: `Login failed: Invalid username or password`

**Solutions**:
1. **Check credentials** in .env:
   ```bash
   # Verify environment variables
   docker exec mathematricks-trader-ibgateway-1 env | grep TWS
   ```

2. **Reset IBC config**:
   ```bash
   # Restart with fresh config
   docker-compose down ibgateway
   docker-compose up -d ibgateway
   ```

3. **Two-Factor Authentication**: If enabled on IBKR account, you may need to configure IB Key in IBC settings

---

### "API connection disabled" Error

**Cause**: API access not enabled in IBKR account settings

**Solution**:
1. Login to [IBKR Account Management](https://www.interactivebrokers.com/portal)
2. Go to **Settings** → **API** → **Settings**
3. Enable **ActiveX and Socket Clients**
4. Set socket port: `4002` (paper) or `4001` (live)
5. Add trusted IPs (optional): `127.0.0.1` for local testing
6. Save changes and restart IB Gateway

---

## VNC Access (Monitoring)

View IB Gateway GUI via VNC (useful for debugging):

**Connect**:
1. Install VNC viewer (e.g., TigerVNC, RealVNC)
2. Connect to: `localhost:5900`
3. Password: `ibgateway` (from docker-compose.yml)

**What You'll See**:
- IB Gateway login screen
- Connection status
- Error messages (if any)
- Market data permissions

---

## Best Practices

### Paper Trading
1. **Always test with paper first** before going live
2. Use `market_data_type: 1` to test with real data
3. Monitor logs during testing:
   ```bash
   ./scripts/quick_test.sh logs
   ```
4. Run pre-flight checks before each test session:
   ```bash
   python3 scripts/preflight_check.py
   ```

### Live Trading
1. **Never skip paper testing** - test thoroughly in paper_live mode
2. **Use different client IDs** for paper and live to avoid confusion
3. **Double-check port**: 4001 for live, 4002 for paper
4. **Set ALLOW_LIVE_TRADING=true** explicitly (safety mechanism)
5. **Start small**: Use minimum position sizes initially
6. **Monitor closely**: Watch Telegram alerts and logs
7. **Have kill switch**: Be ready to change mode back to paper_live

### Security
1. **Never commit credentials**: Use .env file (in .gitignore)
2. **Restrict API access**: Configure trusted IPs in IBKR settings
3. **Separate accounts**: Use different credentials for paper and live
4. **Monitor access**: Check IBKR Activity Logs regularly

---

## IB Gateway Lifecycle

### Startup Sequence

1. Docker container starts
2. IBC (IB Controller) launches
3. IB Gateway application starts
4. Auto-login with credentials from environment
5. API server starts listening on port 4002/4001
6. Ready for connections (~60 seconds total)

**Monitor Startup**:
```bash
docker logs -f mathematricks-trader-ibgateway-1
```

Expected logs:
```
Starting IB Controller...
Launching IB Gateway...
Login successful
API server started on port 4002
Gateway ready
```

---

### Restart Procedure

```bash
# Graceful restart
docker-compose restart ibgateway

# Full reset (if issues persist)
docker-compose down ibgateway
docker-compose up -d ibgateway

# Wait for startup
sleep 60

# Verify connection
python3 scripts/preflight_check.py
```

---

### Automatic Restarts

Docker Compose is configured with `restart: unless-stopped`:
- Gateway auto-restarts if it crashes
- Persists across system reboots
- Stops only with explicit `docker-compose down`

---

## Market Hours

IB Gateway provides data based on market hours:

| Market | Hours (ET) | Days |
|--------|------------|------|
| **US Stocks** | 9:30 AM - 4:00 PM | Mon-Fri |
| **Pre-market** | 4:00 AM - 9:30 AM | Mon-Fri |
| **After-hours** | 4:00 PM - 8:00 PM | Mon-Fri |
| **Forex** | 24/5 | Sun 5 PM - Fri 5 PM |
| **Crypto** | 24/7 | All days |

**Note**: Pre-market and after-hours have lower liquidity and wider spreads.

**Check Market Hours** (automated):
```bash
# Pre-flight check includes market hours validation
python3 scripts/preflight_check.py
```

---

## Testing Workflow (Tuesday Example)

Complete workflow for Tuesday market testing:

```bash
# 1. Ensure IB Gateway is running
docker ps | grep ibgateway

# 2. Run pre-flight checks (9:00 AM ET, before market open)
python3 scripts/preflight_check.py

# 3. Market opens at 9:30 AM ET - wait until 9:35 AM for prices to stabilize

# 4. Send test signal (9:35 AM)
./scripts/quick_test.sh send AAPL

# 5. Monitor logs
./scripts/quick_test.sh logs

# 6. Check Telegram for notifications

# 7. Verify execution in MongoDB
docker exec mathematricks-trader-mongodb-1 mongosh mathematricks_trading --eval \
  'db.signal_store.find({}).sort({created_at: -1}).limit(1).pretty()'

# 8. Test additional symbols (10:00 AM, 11:00 AM)
./scripts/quick_test.sh send SPY
./scripts/quick_test.sh send QQQ

# 9. Test exit signal (2:00 PM, before close)
./scripts/quick_test.sh exit AAPL

# 10. Cleanup after testing
python3 scripts/cleanup_test_data.py
```

---

## Advanced Configuration

### IBC Configuration

IBC (IB Controller) manages IB Gateway automation. Configuration via environment variables:

```yaml
# docker-compose.yml
environment:
  - TWS_USERID=${IBKR_USERNAME}
  - TWS_PASSWORD=${IBKR_PASSWORD}
  - TRADING_MODE=paper  # or 'live'
  - TWS_ACCEPT_INCOMING=accept  # Auto-accept incoming connections
  - READ_ONLY_API=no  # Allow order placement
  - AUTO_RESTART_TIME=11:59 PM  # Daily restart time
  - VNC_SERVER_PASSWORD=ibgateway
```

### Multiple Gateways

Run separate gateways for paper and live simultaneously:

```yaml
# docker-compose.yml
services:
  ibgateway-paper:
    image: ghcr.io/gnzsnz/ib-gateway:stable
    ports:
      - "4002:4002"
    environment:
      - TRADING_MODE=paper
  
  ibgateway-live:
    image: ghcr.io/gnzsnz/ib-gateway:stable
    ports:
      - "4001:4001"
    environment:
      - TRADING_MODE=live
```

---

## See Also

- [Trading Modes](../concepts/trading_modes.md) - paper_mock, paper_live, live
- [Broker Architecture](../services/brokers.md) - Multi-broker design
- [IBKR Integration Summary](../IBKR_INTEGRATION_SUMMARY.md) - Overview
- [Pre-Flight Checks](../../scripts/preflight_check.py) - Automated testing
