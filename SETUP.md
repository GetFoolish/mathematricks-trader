# Mathematricks Trader - Setup Guide

This guide will help you set up the Mathematricks Trader application on your local machine using Docker.

## Quick Setup (Recommended for New Developers)

### One-Command Setup

**Mac/Linux:**
```bash
./setup.sh
```

**Windows:**
```powershell
.\setup.ps1
```

This automated script will:
- ✓ Check all prerequisites (Docker, docker-compose)
- ✓ Build all Docker containers
- ✓ Start all 11 services
- ✓ Initialize MongoDB with seed data
- ✓ Create Pub/Sub topics
- ✓ Verify everything is running
- ✓ Display service URLs and next steps

### Setup with Test Signal

To verify the entire trading pipeline works:

**Mac/Linux:**
```bash
./setup.sh --TestSignal
```

**Windows:**
```powershell
.\setup.ps1 -TestSignal
```

This will:
- Run the full setup
- Send a test ENTRY+EXIT signal for AAPL
- Display logs showing signal flow through all services
- Validate end-to-end functionality

---

## Manual Setup (Detailed Instructions)

If you prefer to set up manually or need to troubleshoot, follow the detailed instructions below.

## Prerequisites

Before you begin, ensure you have the following installed on your machine:

- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop)
  - Docker Compose is included with Docker Desktop
- **Git** - [Download here](https://git-scm.com/downloads)
- **Python 3.11+** (Optional - only needed if you want to run scripts locally outside Docker)
- **MongoDB Compass** (Optional - for viewing database) - [Download here](https://www.mongodb.com/products/compass)

## Step 1: Clone the Repository

```bash
git clone https://github.com/GetFoolish/mathematricks-trader.git
cd mathematricks-trader
git checkout mathematricks-trader-v4a-dockerized
```

## Step 2: Configure Environment Variables

Copy the sample environment file and configure it with your credentials:

```bash
cp .env.sample .env
```

Edit the `.env` file and update the following values:

### Required Configuration

```bash
# IBKR Paper Trading Credentials
IBKR_PAPER_USERNAME=your_paper_username
IBKR_PAPER_PASSWORD=your_paper_password

# IBKR Live Trading Credentials (optional)
IBKR_LIVE_USERNAME=your_live_username
IBKR_LIVE_PASSWORD=your_live_password

# TOTP Secret (from IBKR Mobile Authenticator setup)
IBKR_TOTP_SECRET=your_totp_secret

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_STAGING_CHAT_ID=your_staging_chat_id_here
```

### Keep These Values (Do Not Change)

These values are pre-configured for Docker and should work as-is:

```bash
# MongoDB URIs
MONGODB_URI=mongodb://mongodb:27017  # Docker internal
MONGODB_URI_LOCAL=mongodb://localhost:27018/?directConnection=true  # Mac/local scripts

# Pub/Sub Emulator
PUBSUB_EMULATOR_HOST=pubsub-emulator:8085
PUBSUB_PROJECT_ID=mathematricks-trader

# Account Data Service
ACCOUNT_DATA_SERVICE_URL=http://account-data-service:8082
```

## Step 3: Build and Start Services

Build the Docker containers:

```bash
make rebuild
```

Start all services:

```bash
make start
```

This will:
- Start MongoDB with automatic seed data initialization (9 collections, 84 documents)
- Start all trading services (cerebro, execution, signal ingestion, etc.)
- Start the Pub/Sub emulator
- Start IB Gateway
- Start the frontend dashboard

## Step 4: Verify Everything is Running

Check the status of all services:

```bash
make status
```

You should see all services in "Up" state.

## Step 5: View Logs

Monitor service logs to ensure everything is working correctly:

```bash
# View all logs
make logs

# View specific service logs
make logs-cerebro           # Cerebro service (main trading logic)
make logs-execution         # Execution service (order placement)
make logs-signal-ingestion  # Signal ingestion
make logs-account-data      # Account data service
make logs-portfolio         # Portfolio builder
make logs-dashboard         # Dashboard creator
```

## Connecting to MongoDB

### Using MongoDB Compass

Connection string for MongoDB Compass:

```
mongodb://localhost:27018/?directConnection=true
```

Database name: `mathematricks_trading`

### From Local Scripts (Mac/Linux)

The `send_test_signal.py` script automatically connects to Docker MongoDB using `MONGODB_URI_LOCAL`.

Example:

```bash
# Activate your Python virtual environment (if using one)
source venv/bin/activate

# Send a test signal
python tests/signals_testing/send_test_signal.py --file tests/signals_testing/sample_signals/equity_simple_signal_1.json
```

## Available Make Commands

### Service Management

```bash
make start          # Start all services
make stop           # Stop all services
make restart        # Restart all services
make status         # Check service status
make rebuild        # Rebuild all containers
make clean          # Stop and remove all containers and volumes (⚠️ DATA LOSS!)
```

### Logs

```bash
make logs                     # View all logs
make logs-cerebro             # Cerebro service logs
make logs-execution           # Execution service logs
make logs-signal-ingestion    # Signal ingestion logs
make logs-account-data        # Account data service logs
make logs-portfolio           # Portfolio builder logs
make logs-dashboard           # Dashboard creator logs
```

### Restart Individual Services

```bash
make restart-cerebro          # Restart cerebro service
make restart-execution        # Restart execution service
make restart-signal-ingestion # Restart signal ingestion
make restart-account-data     # Restart account data service
make restart-portfolio        # Restart portfolio builder
make restart-dashboard        # Restart dashboard creator
```

## Port Mappings

The following ports are exposed on your localhost:

| Service | Port | Description |
|---------|------|-------------|
| MongoDB | 27018 | MongoDB database (replica set) |
| Pub/Sub Emulator | 8085 | Google Pub/Sub emulator |
| Portfolio Builder | 8003 | Portfolio builder service |
| Dashboard Creator | 8004 | Dashboard creator service |
| IB Gateway (Paper) | 4002 | Interactive Brokers paper trading API |
| IB Gateway (Live) | 4001 | Interactive Brokers live trading API |
| IB Gateway VNC | 5900 | VNC access to IB Gateway |
| Frontend | 5173 | Web dashboard |

## MongoDB Seed Data

On first startup, the system automatically:

1. Checks if the MongoDB database is empty
2. If empty, restores seed data from `seed_data/mongodb_dump/`
3. Populates 9 collections with sample trading data

**Note:** Seed data is only loaded once. On subsequent startups, your existing data is preserved.

## Troubleshooting

### Services not starting

```bash
# Check logs for errors
make logs

# Rebuild containers
make rebuild
make start
```

### MongoDB connection issues

1. Verify MongoDB is running:
   ```bash
   make status | grep mongodb
   ```

2. Check MongoDB logs:
   ```bash
   docker-compose logs mongodb
   ```

3. Verify port 27018 is not in use:
   ```bash
   lsof -i :27018
   ```

### Port conflicts

If you already have MongoDB running on port 27017, that's fine! Docker MongoDB uses port 27018 to avoid conflicts.

### Clean slate restart

If you want to completely reset everything (⚠️ **THIS DELETES ALL DATA**):

```bash
make clean
make rebuild
make start
```

## Next Steps

1. **Test Signal Sending**: Try sending a test signal using the provided scripts
2. **Monitor Logs**: Keep an eye on service logs to ensure everything is working
3. **Access Dashboard**: Open http://localhost:5173 to view the trading dashboard
4. **Configure Strategies**: Update strategies in MongoDB using the portfolio builder

## Getting Help

- Check service logs: `make logs-<service>`
- Verify environment variables in `.env`
- Ensure all prerequisites are installed
- Review the main README.md for additional documentation

---

**Happy Trading!** 🚀
