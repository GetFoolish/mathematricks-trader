# Mathematricks Trader - Setup Guide

Complete setup guide for the Mathematricks Trading System. This guide will walk you through installation, configuration, and verification of all services.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Starting Services](#starting-services)
- [Verification](#verification)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## Prerequisites

### System Requirements
- **Operating System**: macOS, Linux, or Windows (with WSL2)
- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 10GB free space
- **Internet**: Required for Docker images and broker APIs

### Required Software

#### 1. Docker Desktop
```bash
# macOS (Homebrew)
brew install --cask docker

# Linux
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Windows
# Download from https://www.docker.com/products/docker-desktop
```

**Verify Installation**:
```bash
docker --version
# Expected: Docker version 24.0.0 or higher

docker-compose --version
# Expected: Docker Compose version 2.20.0 or higher
```

#### 2. Python 3.11+
```bash
# macOS (Homebrew)
brew install python@3.11

# Linux (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Verify
python3 --version
# Expected: Python 3.11.x or higher
```

#### 3. Node.js 18+ (for Frontend)
```bash
# macOS (Homebrew)
brew install node@18

# Linux
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify
node --version
# Expected: v18.x.x or higher

npm --version
# Expected: 9.x.x or higher
```

#### 4. Git
```bash
# macOS
brew install git

# Linux
sudo apt install git

# Verify
git --version
```

---

## Installation

### 1. Clone Repository
```bash
# SSH (recommended)
git clone git@github.com:GetFoolish/mathematricks-trader.git

# HTTPS
git clone https://github.com/GetFoolish/mathematricks-trader.git

# Navigate to project
cd mathematricks-trader
```

### 2. Create Environment File
```bash
# Copy sample environment file
cp .env.sample .env

# Edit with your credentials
vim .env  # or nano, code, etc.
```

### 3. Configure Environment Variables

Edit `.env` file with your credentials:

```bash
# ============================================
# MONGODB CONFIGURATION
# ============================================
# Docker internal connection (used by services running in Docker)
MONGODB_URI=mongodb://mongodb:27017/mathematricks_trading

# Mac local connection (used by scripts running on host)
# IMPORTANT: Must use directConnection=true for MongoDB replica set
MONGODB_URI_LOCAL=mongodb://localhost:27018/?directConnection=true&replicaSet=rs0

# ============================================
# INTERACTIVE BROKERS CONFIGURATION
# ============================================
# Paper Trading Account (recommended for testing)
IBKR_PAPER_USERNAME=your_paper_username
IBKR_PAPER_PASSWORD=your_paper_password

# Live Trading Account (use with caution!)
IBKR_LIVE_USERNAME=your_live_username
IBKR_LIVE_PASSWORD=your_live_password

# TOTP Secret (for 2FA authentication)
# Get from IB website: Account Management > Security > Secure Login System
IBKR_TOTP_SECRET=your_totp_secret_here

# IB Gateway Configuration
IBKR_HOST=ib-gateway        # Docker service name
IBKR_PORT=4002              # 4001=live, 4002=paper
IBKR_CLIENT_ID=1

# ============================================
# ZERODHA KITE CONNECT (Optional)
# ============================================
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_ACCESS_TOKEN=your_access_token

# ============================================
# TELEGRAM NOTIFICATIONS
# ============================================
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321

# ============================================
# SERVICE CONFIGURATION
# ============================================
# Account Data Service
ACCOUNT_DATA_SERVICE_URL=http://account-data-service:8082
POLL_INTERVAL_SECONDS=30

# Mock Broker Mode (for testing without real brokers)
USE_MOCK_BROKER=true

# Default Account (fallback)
DEFAULT_ACCOUNT_ID=Mock_Paper

# Signal Testing
SIGNAL_TEST_SEED=1          # Seed for reproducible test signal shuffling
```

### 4. Install Python Dependencies

**For Local Development** (optional):
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

**For Docker** (recommended):
Dependencies are automatically installed in Docker images, no local installation needed.

### 5. Install Frontend Dependencies

```bash
cd frontend-admin

# Install npm packages
npm install

# Return to project root
cd ..
```

---

## Configuration

### 1. Telegram Bot Setup (Optional but Recommended)

#### Create Telegram Bot:
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow prompts to create bot
4. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### Get Chat ID:
1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find `"chat":{"id": 987654321}` in the response
4. Copy the chat ID

#### Update `.env`:
```bash
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 2. Interactive Brokers Setup (Optional)

#### Paper Trading Account:
1. Go to [IBKR Client Portal](https://www.interactivebrokers.com)
2. Register for paper trading account
3. Enable API access: Account Management > Settings > API > Enable ActiveX and Socket Clients
4. Set up Secure Login System (2FA) and save TOTP secret
5. Update `.env` with credentials

#### IB Gateway VNC Access:
```bash
# Access IB Gateway UI via VNC
# URL: vnc://localhost:5900
# Password: (check docker-compose.yml)

# Or use any VNC client
open vnc://localhost:5900
```

### 3. MongoDB Replica Set Initialization

MongoDB will automatically initialize as a replica set on first start. If you need to manually initialize:

```bash
# Start MongoDB
docker-compose up -d mongodb

# Wait 10 seconds for MongoDB to start
sleep 10

# Initialize replica set
docker exec -it mathematricks-trader-mongodb-1 mongosh --eval "
rs.initiate({
    _id: 'rs0',
    members: [{_id: 0, host: 'mongodb:27017'}]
})
"

# Verify replica set status
docker exec -it mathematricks-trader-mongodb-1 mongosh --eval "rs.status()"
```

---

## Starting Services

### Option 1: Using Makefile (Recommended)

```bash
# Start all services
make start

# View status
make status

# View logs (all services)
make logs

# View logs (specific service)
make logs-cerebro
make logs-execution
make logs-signal-ingestion

# Restart services
make restart

# Stop all services
make stop
```

### Option 2: Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart specific service
docker-compose restart cerebro-service
```

### Service Startup Order

The system automatically handles startup order via Docker Compose `depends_on`:

```
1. MongoDB (port 27017 internal, 27018 external)
2. IB Gateway (ports 4001/4002, VNC 5900)
3. Account Data Service (port 8082)
4. Signal Ingestion
5. Cerebro Service
6. Execution Service
7. Dashboard Creator (port 8004)
8. Portfolio Builder (port 8003)
9. Frontend (port 5173 + 8000)
```

---

## Verification

### 1. Check Service Status

```bash
# Via Makefile
make status

# Via Docker
docker ps

# Expected output (all services running):
CONTAINER ID   IMAGE                             STATUS
abc123...      mathematricks-trader-mongodb-1    Up 2 minutes
def456...      mathematricks-trader-cerebro      Up 1 minute
ghi789...      mathematricks-trader-execution    Up 1 minute
...
```

### 2. Verify MongoDB Connection

```bash
# Via Makefile
make mongo-shell

# Or manually
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading

# Inside MongoDB shell:
> show collections
> db.trading_accounts.countDocuments({})
> exit
```

### 3. Check Service Logs

```bash
# Signal Ingestion
make logs-signal-ingestion
# Expected: "Started watching trading_signals_raw collection"

# Cerebro
make logs-cerebro
# Expected: "Started watching signal_store collection"

# Execution
make logs-execution
# Expected: "Started watching trading_orders collection"

# Account Data Service
curl http://localhost:8082/health
# Expected: {"status": "healthy"}
```

### 4. Access Frontend

```bash
# Frontend UI (React)
open http://localhost:5173

# API Backend (Express)
curl http://localhost:8000/api/strategies

# Portfolio Builder (Streamlit)
open http://localhost:8003

# Dashboard Creator API
curl http://localhost:8004/api/v1/dashboards/client
```

### 5. Verify Database Seed Data

```bash
# Check if seed data loaded
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading

> db.strategies.countDocuments({})
# Expected: 9 (if seed data loaded)

> db.trading_accounts.countDocuments({})
# Expected: 5-6 accounts

> db.funds.countDocuments({})
# Expected: 1-2 funds

> db.portfolio_allocations.find({status: "ACTIVE"}).pretty()
# Expected: 1 active allocation
```

---

## Testing

### 1. Clear Test Data

```bash
# Via Makefile
make clear-test-data

# Or manually
python scripts/junk/clear_test_data.py
```

### 2. Send Test Signal

```bash
# Via Makefile (sends simple AAPL signal)
make send-test-signal

# Or manually
python tests/signals_testing/send_test_signal.py --file tests/signals_testing/sample_signals/spy_realistic.json
```

### 3. Run Full Test Suite

```bash
# Via Makefile (clears data + runs all test signals)
make test-signals

# Or manually
python scripts/junk/clear_test_data.py
python tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals --delay 10
```

### 4. Verify Test Results

```bash
# Check test results
cat test_results/test_run_*.json

# Check MongoDB
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading

> db.signal_store.countDocuments({})
# Expected: Number of signals sent

> db.trading_orders.countDocuments({status: "FILLED"})
# Expected: Filled orders count

> db.trading_accounts.findOne({account_id: "OANDA_MOCK"}, {balances: 1, open_positions: 1})
# Expected: Updated balances and positions
```

### 5. View Test Signals in Frontend

```bash
# Open Frontend
open http://localhost:5173

# Navigate to Activity page
# Expected: See all test signals, orders, and executions
```

---

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
**Error**: `Bind for 0.0.0.0:27018 failed: port is already allocated`

**Solution**:
```bash
# Find process using port
lsof -i :27018  # macOS/Linux
netstat -ano | findstr :27018  # Windows

# Kill process or change port in docker-compose.yml
```

#### 2. MongoDB Connection Failed
**Error**: `Failed to connect to MongoDB: Connection refused`

**Solution**:
```bash
# Check MongoDB status
docker ps | grep mongodb

# Restart MongoDB
docker restart mathematricks-trader-mongodb-1

# Check logs
docker logs mathematricks-trader-mongodb-1

# Verify MongoDB is listening
docker exec -it mathematricks-trader-mongodb-1 mongosh --eval "db.serverStatus()"
```

#### 3. IB Gateway Not Connecting
**Error**: `Failed to connect to IB Gateway`

**Solution**:
```bash
# Check IB Gateway status
docker ps | grep ib-gateway

# Access IB Gateway via VNC to verify login
open vnc://localhost:5900

# Check credentials in .env
# Verify IBKR account has API access enabled
```

#### 4. Services Not Starting
**Error**: Various service startup failures

**Solution**:
```bash
# Check Docker resource limits
# Docker Desktop > Settings > Resources > Increase CPU/Memory

# Rebuild images
docker-compose build --no-cache

# Clear Docker cache
docker system prune -a
```

#### 5. Frontend Not Loading
**Error**: `Cannot GET /`

**Solution**:
```bash
# Check if frontend is running
docker ps | grep frontend

# Rebuild frontend
cd frontend-admin
npm install
npm run build

# Or restart frontend service
docker-compose restart frontend
```

#### 6. Logs Not Showing Data
**Error**: Services running but not processing signals

**Solution**:
```bash
# Check if services are in correct environment
# Verify --staging flag matches signal environment

# Check MongoDB Change Streams
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading
> db.getReplicationInfo()
# Ensure replica set is initialized

# Restart services
make restart
```

---

## Next Steps

### 1. Configure Strategies

```bash
# Access Frontend
open http://localhost:5173

# Navigate to Strategies page
# Create new strategies or edit existing ones
```

### 2. Set Up Portfolio Allocations

```bash
# Access Portfolio Builder
open http://localhost:8003

# Run optimization
# Copy allocation to clipboard
# Navigate to Frontend > Allocations
# Paste and approve allocation
```

### 3. Configure Funds and Accounts

```bash
# Frontend > Fund Setup
# Create funds
# Assign accounts to funds
# Configure asset class support
```

### 4. Send Live Signals

```bash
# Option 1: TradingView Webhook
# Configure webhook URL: http://your-server:8080/webhook/signal

# Option 2: Manual Signal Submission
# Use send_test_signal.py with production environment
python send_test_signal.py --file your_signal.json  # Remove staging: true
```

### 5. Monitor System

```bash
# View real-time dashboard
open http://localhost:5173

# Check logs
make logs

# Monitor MongoDB
make mongo-shell
```

---

## Documentation

Comprehensive documentation for each service:

- **[Signal Ingestion Service](documentation/signal_ingestion_service.md)** - Signal processing and consolidation
- **[Cerebro Service](documentation/cerebro_service.md)** - Intelligent position sizing
- **[Account Data Service](documentation/account_data_service.md)** - Real-time account data
- **[Execution Service](documentation/execution_service.md)** - Order execution and brokers
- **[Frontend](documentation/frontend.md)** - Admin dashboard
- **[Dashboard Creator](documentation/dashboard_creator.md)** - Pre-computed dashboards
- **[Signals Testing](documentation/signals_testing.md)** - Test infrastructure

---

## Production Deployment

### Security Checklist

- [ ] Change default passwords
- [ ] Enable HTTPS/TLS
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerts
- [ ] Enable backup automation
- [ ] Review broker API permissions
- [ ] Set up logging aggregation
- [ ] Configure rate limiting
- [ ] Enable authentication/authorization
- [ ] Set up disaster recovery

### Deployment Options

#### Option 1: Docker Swarm
```bash
docker swarm init
docker stack deploy -c docker-compose.yml mathematricks
```

#### Option 2: Kubernetes
```bash
# Convert docker-compose to k8s manifests
kompose convert

# Apply manifests
kubectl apply -f .
```

#### Option 3: Cloud Platforms
- **AWS**: ECS, EKS, or EC2 with Docker Compose
- **Google Cloud**: GKE or Compute Engine
- **Azure**: AKS or Container Instances

---

## Support

### Getting Help

1. **Documentation**: Check service-specific docs in `documentation/` folder
2. **Logs**: Review service logs using `make logs-<service-name>`
3. **MongoDB**: Query database directly to debug issues
4. **GitHub Issues**: Report bugs or request features

### Useful Commands

```bash
# Quick reference
make help                  # Show all Makefile commands
make status                # Check service status
make logs                  # View all logs
make clear-test-data       # Clear test data
make test-signals          # Run test suite
make export-seed-data      # Export MongoDB snapshot
make reseed-db             # Restore from seed data
```

---

## License

This project is proprietary software. All rights reserved.

---

## Acknowledgments

Built with:
- FastAPI, PyMongo, ib-insync, kiteconnect
- React, TypeScript, TailwindCSS, Vite
- Docker, MongoDB, IB Gateway

---

**Happy Trading! 📈**
