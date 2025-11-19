# Development Setup Guide

Quick setup guide for getting the Mathematricks Trader project running locally.

## 🚀 Quick Start

Run the automated setup script:

```bash
./dev/setup_project.sh
```

This script will:
1. ✅ Check and install Homebrew (if needed)
2. ✅ Check and install Python 3.11 (if needed)
3. ✅ Check and install MongoDB (if needed)
4. ✅ Start MongoDB service
5. ✅ Create Python virtual environment
6. ✅ Install all Python dependencies
7. ✅ Import MongoDB collections (strategies, accounts, etc.)
8. ✅ Create .env configuration template

## 📋 Manual Setup (Alternative)

If you prefer manual setup or the script fails:

### 1. Install Prerequisites

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11
brew install python@3.11

# Install MongoDB
brew tap mongodb/brew
brew install mongodb-community

# Start MongoDB
brew services start mongodb-community
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Import MongoDB Collections

```bash
# Import collections (adjust timestamp as needed)
cd dev/downloads/exported_collections

mongoimport --db=mathematricks_trading --collection=strategies --file=strategies_*.json --jsonArray --drop
mongoimport --db=mathematricks_trading --collection=current_allocation --file=current_allocation_*.json --jsonArray --drop
mongoimport --db=mathematricks_trading --collection=portfolio_tests --file=portfolio_tests_*.json --jsonArray --drop
mongoimport --db=mathematricks_trading --collection=trading_accounts --file=trading_accounts_*.json --jsonArray --drop
```

### 4. Configure Environment

Create `.env` file in project root:

```bash
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0

# GCP Configuration
GCP_PROJECT_ID=mathematricks-trader
GCP_CREDENTIALS_PATH=path/to/credentials.json

# Service Configuration
DEFAULT_ACCOUNT_ID=Mock_Paper

# Environment
ENVIRONMENT=development
```

## 🏃 Running the Project

```bash
# Activate virtual environment
source venv/bin/activate

# Start the demo
python mvp_demo_start.py
```

## 🛠️ Development Tools

### Export Collections

Export MongoDB collections for sharing:

```bash
./dev/downloads/export_collections.sh
```

### View Logs

```bash
# Real-time log viewing
tail -f logs/cerebro_service.log
tail -f logs/execution_service.log
tail -f logs/signal_ingestion.log
```

### MongoDB Management

```bash
# Connect to MongoDB shell
mongosh mathematricks_trading

# List collections
show collections

# Query a collection
db.strategies.find().pretty()

# Check document count
db.strategies.countDocuments()
```

## 📊 System Architecture

The system consists of three main services:

1. **Signal Ingestion** - Receives and validates trading signals
2. **Cerebro Service** - Portfolio management and position sizing
3. **Execution Service** - Order placement and execution

## 🐛 Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
brew services list | grep mongodb

# Start MongoDB
brew services start mongodb-community

# Check logs
tail -f /opt/homebrew/var/log/mongodb/mongo.log
```

### Python Import Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Port Conflicts

If ports 27017 (MongoDB) or other service ports are in use:

```bash
# Check what's using a port
lsof -i :27017

# Kill process if needed
kill -9 <PID>
```

## 📝 Additional Notes

- Default MongoDB port: `27017`
- Default account for testing: `Mock_Paper`
- Logs directory: `./logs/`
- Virtual environment: `./venv/`