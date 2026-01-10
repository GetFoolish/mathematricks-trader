# Signal Ingestion Service

The Signal Ingestion Service is the entry point for all trading signals in the Mathematricks Trading System. It monitors incoming signals from external sources (TradingView webhooks, manual submissions, test scripts) and creates consolidated signal documents for downstream processing.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Key Components](#key-components)
- [Signal Schema](#signal-schema)
- [Data Flow](#data-flow)
- [Configuration](#configuration)
- [Usage](#usage)
- [Monitoring & Logs](#monitoring--logs)
- [Error Handling](#error-handling)
- [Development](#development)

---

## Overview

### Purpose
- **Monitor** `trading_signals_raw` collection via MongoDB Change Streams
- **Validate** incoming signal format and required fields
- **Create** consolidated signal documents in `signal_store` collection
- **Link** EXIT/SCALE signals to their parent ENTRY signals
- **Notify** via Telegram when signals are processed
- **Filter** signals by environment (staging vs production)

### Technology Stack
- **Python 3.11+**
- **PyMongo** (MongoDB driver with Change Streams)
- **MongoDB** (database)
- **Telegram Bot API** (notifications)
- **Docker** (containerization)

### Location
```
services/signal_ingestion/
├── signal_ingestion_main.py    # Main entry point
├── mongodb_watcher.py           # Change Stream watcher
├── signal_standardizer.py       # Signal format standardization
├── config.py                    # Configuration
├── requirements.txt             # Python dependencies
└── Dockerfile                   # Container image
```

---

## Architecture

### Service Model
The Signal Ingestion Service runs as a **long-lived background process** that:

1. Establishes a MongoDB Change Stream connection to `trading_signals_raw`
2. Listens for INSERT and UPDATE operations
3. Processes each new signal document
4. Creates/updates documents in `signal_store` with consolidated schema
5. Sends Telegram notifications for important events
6. Handles connection failures with automatic retry

### Design Philosophy
- **Event-driven**: Uses MongoDB Change Streams (no polling)
- **Idempotent**: Safe to restart without duplicating work
- **Resilient**: Automatic reconnection on failures
- **Environment-aware**: Filters staging vs production signals

---

## Key Components

### 1. `signal_ingestion_main.py`
**Purpose**: Main entry point and service orchestration

**Key Functions**:
```python
def main():
    """
    Start Signal Ingestion Service
    - Parses CLI arguments (--staging flag)
    - Initializes MongoDB connection
    - Starts Change Stream watcher
    - Runs indefinitely with error recovery
    """
```

**CLI Arguments**:
```bash
python signal_ingestion_main.py [--staging]

Options:
  --staging     Run in staging mode (filters for staging=true signals)
```

**Environment Variables**:
- `MONGODB_URI` - MongoDB connection string (Docker: `mongodb://mongodb:27017`)
- `MONGODB_URI_LOCAL` - Local development override (Mac: `mongodb://localhost:27018/?directConnection=true`)
- `TELEGRAM_ENABLED` - Enable/disable Telegram notifications (default: `true`)
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Telegram chat ID for notifications

---

### 2. `mongodb_watcher.py`
**Purpose**: MongoDB Change Stream watcher and signal processing logic

**Class**: `SignalStoreWatcher`

**Key Methods**:

#### `start_watching()`
Establishes Change Stream connection and processes signals:
```python
def start_watching(self):
    """
    Start MongoDB Change Stream on trading_signals_raw collection

    Filters:
    - operationType: insert, update
    - environment: staging or production (based on --staging flag)

    Resume Strategy:
    - Saves resume tokens for fault tolerance
    - Automatically resumes from last processed signal on restart
    """
```

#### `process_signal_document()`
Main signal processing logic:
```python
def process_signal_document(self, raw_signal_doc):
    """
    Process a single signal document

    Steps:
    1. Validate required fields (signalID, strategy_name, signal_type, etc.)
    2. Determine signal type (ENTRY, EXIT, SCALE)
    3. For ENTRY: Create new signal_store document
    4. For EXIT/SCALE: Find parent signal and append new leg
    5. Update signal_store with consolidated schema
    6. Send Telegram notification

    Returns:
        bool: True if processed successfully, False otherwise
    """
```

#### `create_signal_store_entry()`
Creates new signal document for ENTRY signals:
```python
def create_signal_store_entry(self, raw_signal_doc):
    """
    Create new signal_store document with consolidated schema v3

    Schema:
    {
        "signal_id": "sig_xxx",           # Unique signal ID
        "base_signal_id": "sig_xxx",      # Same as signal_id for ENTRY
        "strategy_id": "strategy_name",   # Strategy name
        "instrument": "AAPL",             # Primary instrument
        "signal_type": "MULTI_LEG",       # Always MULTI_LEG in v3
        "legs": [                         # Array of signal legs
            {
                "leg_type": "ENTRY",
                "leg_index": 0,
                "raw": {...},             # Original signal data
                "decision": null,         # Filled by Cerebro
                "execution": null         # Filled by Execution Service
            }
        ],
        "position": {                     # Aggregated position state
            "entry_quantity": 0,
            "exit_quantity": 0,
            "remaining_quantity": 0,
            "status": "PENDING"           # PENDING/OPEN/PARTIAL/CLOSED
        },
        "environment": "staging",
        "created_at": "2024-01-09T...",
        "updated_at": "2024-01-09T..."
    }
    """
```

#### `append_leg_to_signal()`
Appends EXIT/SCALE leg to existing signal:
```python
def append_leg_to_signal(self, raw_signal_doc):
    """
    Find parent signal and append new leg

    Lookup Strategy:
    1. Get entry_signal_id from EXIT/SCALE signal
    2. Query signal_store: {"base_signal_id": entry_signal_id}
    3. Validate instrument match (prevents wrong EXIT associations)
    4. Append new leg to legs[] array
    5. Update position.exit_quantity and position.remaining_quantity
    6. Update position.status (OPEN → PARTIAL → CLOSED)

    Returns:
        bool: True if leg appended successfully, False if parent not found
    """
```

---

### 3. `signal_standardizer.py`
**Purpose**: Standardize signal format from various sources

**Key Functions**:

#### `standardize_signal()`
```python
def standardize_signal(raw_signal):
    """
    Convert raw signal to standard format

    Handles:
    - Legacy 'signal' field → modern 'signal_legs' field
    - Missing timestamps (auto-generates)
    - Missing signalID (auto-generates: sig_{timestamp}_{random})
    - Environment detection (staging vs production)

    Returns:
        dict: Standardized signal document
    """
```

---

## Signal Schema

### Input: `trading_signals_raw` Collection
Signals arrive in this collection from external sources (TradingView webhook, test scripts).

**ENTRY Signal Example**:
```json
{
    "signalID": "sig_spy_001",
    "signal_type": "ENTRY",
    "strategy_name": "SPY",
    "entry_name": "$SPY_1",
    "signal_legs": [
        {
            "instrument": "SPY",
            "instrument_type": "STOCK",
            "action": "BUY",
            "direction": "LONG",
            "quantity": 100,
            "order_type": "MARKET",
            "price": 450.25,
            "stop_loss": 445.00,
            "take_profit": 460.00
        }
    ],
    "account_equity": 100000,
    "environment": "staging",
    "staging": true,
    "signal_sent_EPOCH": 1704844800,
    "created_at": "2024-01-09T12:00:00Z"
}
```

**EXIT Signal Example**:
```json
{
    "signalID": "sig_spy_002",
    "signal_type": "EXIT",
    "strategy_name": "SPY",
    "entry_signal_id": "sig_spy_001",  // Links to ENTRY
    "signal_legs": [
        {
            "instrument": "SPY",
            "instrument_type": "STOCK",
            "action": "SELL",
            "direction": "LONG",
            "quantity": 100,
            "order_type": "MARKET",
            "price": 455.50
        }
    ],
    "environment": "staging",
    "staging": true,
    "signal_sent_EPOCH": 1704931200,
    "created_at": "2024-01-10T12:00:00Z"
}
```

---

### Output: `signal_store` Collection
The Signal Ingestion Service creates/updates documents in the **consolidated schema v3** format.

**Consolidated Signal Document** (after ENTRY + EXIT):
```json
{
    "_id": ObjectId("..."),
    "signal_id": "sig_spy_001",
    "base_signal_id": "sig_spy_001",
    "strategy_id": "SPY",
    "instrument": "SPY",
    "signal_type": "MULTI_LEG",
    "legs": [
        {
            "leg_type": "ENTRY",
            "leg_index": 0,
            "raw": {
                "signalID": "sig_spy_001",
                "signal_legs": [{...}],
                "account_equity": 100000
            },
            "decision": {
                "strategy_allocation": 0.15,
                "allocated_capital": 15000,
                "legs": [
                    {
                        "quantity": 33,
                        "account_id": "OANDA_MOCK",
                        "fund_id": "fund_001"
                    }
                ],
                "cerebro_timestamp": "2024-01-09T12:00:05Z"
            },
            "execution": {
                "orders": [
                    {
                        "order_id": "ord_123",
                        "account_id": "OANDA_MOCK",
                        "quantity_filled": 33,
                        "avg_fill_price": 450.30,
                        "status": "FILLED"
                    }
                ],
                "total_quantity_filled": 33,
                "execution_timestamp": "2024-01-09T12:00:10Z"
            }
        },
        {
            "leg_type": "EXIT",
            "leg_index": 1,
            "raw": {
                "signalID": "sig_spy_002",
                "entry_signal_id": "sig_spy_001",
                "signal_legs": [{...}]
            },
            "decision": {
                "legs": [
                    {
                        "quantity": -33,
                        "account_id": "OANDA_MOCK"
                    }
                ],
                "cerebro_timestamp": "2024-01-10T12:00:05Z"
            },
            "execution": {
                "orders": [
                    {
                        "order_id": "ord_124",
                        "quantity_filled": 33,
                        "avg_fill_price": 455.60,
                        "status": "FILLED",
                        "pnl": 174.90  // (455.60 - 450.30) * 33
                    }
                ],
                "total_quantity_filled": 33,
                "execution_timestamp": "2024-01-10T12:00:10Z"
            }
        }
    ],
    "position": {
        "entry_quantity": 33,
        "exit_quantity": 33,
        "remaining_quantity": 0,
        "status": "CLOSED"
    },
    "environment": "staging",
    "created_at": "2024-01-09T12:00:01Z",
    "updated_at": "2024-01-10T12:00:11Z"
}
```

---

## Data Flow

### Flow Diagram
```
┌──────────────────────────┐
│ EXTERNAL SIGNAL SOURCE   │
│ - TradingView Webhook    │
│ - Manual Submission      │
│ - Test Scripts           │
└──────────┬───────────────┘
           │ INSERT
           ↓
┌──────────────────────────────────────────┐
│ MongoDB: trading_signals_raw             │
│ {                                        │
│   signalID: "sig_spy_001",              │
│   signal_type: "ENTRY",                 │
│   strategy_name: "SPY",                 │
│   signal_legs: [{...}]                  │
│ }                                        │
└──────────┬───────────────────────────────┘
           │ Change Stream Event
           ↓
┌──────────────────────────────────────────┐
│ Signal Ingestion Service                 │
│ - mongodb_watcher.py                     │
│ - Detects new signal                     │
│ - Validates format                       │
│ - Determines signal type (ENTRY/EXIT)    │
└──────────┬───────────────────────────────┘
           │
           ├─ ENTRY Signal
           │  ↓
           │  Create new signal_store document
           │  with legs[0] = ENTRY leg
           │
           └─ EXIT Signal
              ↓
              Find parent signal by entry_signal_id
              Append legs[1] = EXIT leg
              Update position{} aggregates

           ↓
┌──────────────────────────────────────────┐
│ MongoDB: signal_store                    │
│ {                                        │
│   signal_id: "sig_spy_001",             │
│   legs: [                                │
│     { leg_type: "ENTRY", raw: {...} }   │
│   ],                                     │
│   position: { status: "PENDING" }       │
│ }                                        │
└──────────┬───────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│ Cerebro Service                          │
│ - Watches signal_store for new legs     │
│ - Adds decision{} to legs[]             │
└──────────────────────────────────────────┘
```

### Step-by-Step Process

#### 1. Signal Arrival
- External source inserts document into `trading_signals_raw`
- Document must contain: `signalID`, `signal_type`, `strategy_name`, `signal_legs`

#### 2. Change Stream Detection
```python
# Signal Ingestion Service watches for INSERT events
pipeline = [
    {
        "$match": {
            "operationType": {"$in": ["insert", "update"]},
            "fullDocument.environment": environment  # Filter by staging/production
        }
    }
]
```

#### 3. Signal Processing
```python
# Process each detected signal
for change in change_stream:
    raw_signal_doc = change['fullDocument']

    # Validate required fields
    if not validate_signal(raw_signal_doc):
        logger.error("Invalid signal format")
        continue

    # Determine signal type
    signal_type = raw_signal_doc.get('signal_type', 'ENTRY').upper()

    if signal_type == 'ENTRY':
        create_signal_store_entry(raw_signal_doc)
    elif signal_type in ['EXIT', 'SCALE']:
        append_leg_to_signal(raw_signal_doc)
```

#### 4. ENTRY Signal → Create New Document
```python
signal_store_doc = {
    "signal_id": raw_signal_doc['signalID'],
    "base_signal_id": raw_signal_doc['signalID'],
    "strategy_id": raw_signal_doc['strategy_name'],
    "instrument": raw_signal_doc['signal_legs'][0]['instrument'],
    "signal_type": "MULTI_LEG",
    "legs": [
        {
            "leg_type": "ENTRY",
            "leg_index": 0,
            "raw": raw_signal_doc,
            "decision": None,
            "execution": None
        }
    ],
    "position": {
        "entry_quantity": 0,
        "exit_quantity": 0,
        "remaining_quantity": 0,
        "status": "PENDING"
    },
    "environment": raw_signal_doc.get('environment', 'staging'),
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc)
}

signal_store_collection.insert_one(signal_store_doc)
```

#### 5. EXIT Signal → Append to Existing Document
```python
entry_signal_id = raw_signal_doc.get('entry_signal_id')
exit_instrument = raw_signal_doc['signal_legs'][0]['instrument']

# Find parent signal
parent_signal = signal_store_collection.find_one({
    "base_signal_id": entry_signal_id,
    "instrument": exit_instrument  # Validate instrument match
})

if not parent_signal:
    logger.error(f"Parent signal not found for EXIT: {entry_signal_id}")
    return False

# Append new leg
new_leg = {
    "leg_type": "EXIT",
    "leg_index": len(parent_signal['legs']),
    "raw": raw_signal_doc,
    "decision": None,
    "execution": None
}

signal_store_collection.update_one(
    {"_id": parent_signal["_id"]},
    {
        "$push": {"legs": new_leg},
        "$set": {"updated_at": datetime.now(timezone.utc)}
    }
)
```

#### 6. Telegram Notification
```python
if telegram_enabled:
    send_telegram_notification(
        f"📊 {signal_type} Signal Received\n"
        f"Strategy: {strategy_name}\n"
        f"Instrument: {instrument}\n"
        f"Signal ID: {signal_id}"
    )
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# MongoDB Connection
MONGODB_URI=mongodb://mongodb:27017/mathematricks_trading
MONGODB_URI_LOCAL=mongodb://localhost:27018/?directConnection=true&replicaSet=rs0

# Telegram Notifications
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Service Mode (set via CLI --staging flag)
# No environment variable needed
```

### Docker Compose Configuration

```yaml
# docker-compose.yml
services:
  signal-ingestion:
    build: ./services/signal_ingestion
    container_name: mathematricks-trader-signal-ingestion-1
    command: python signal_ingestion_main.py --staging
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - TELEGRAM_ENABLED=${TELEGRAM_ENABLED}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
    depends_on:
      - mongodb
    networks:
      - tradenet
    restart: unless-stopped
```

### Staging vs Production Mode

**Staging Mode** (default):
```bash
python signal_ingestion_main.py --staging
```
- Filters for signals with `environment: "staging"` or `staging: true`
- Use for development and testing

**Production Mode**:
```bash
python signal_ingestion_main.py
```
- Filters for signals with `environment: "production"` or `staging: false`
- Use for live trading

---

## Usage

### Starting the Service

#### Via Docker Compose (Recommended)
```bash
# Start all services including signal ingestion
make start

# View signal ingestion logs
make logs-signal-ingestion

# Restart signal ingestion only
docker restart mathematricks-trader-signal-ingestion-1
```

#### Standalone (Development)
```bash
# Install dependencies
cd services/signal_ingestion
pip install -r requirements.txt

# Run in staging mode
python signal_ingestion_main.py --staging

# Run in production mode
python signal_ingestion_main.py
```

### Sending Test Signals

#### Using Test Script
```bash
# Send single test signal
python tests/signals_testing/send_test_signal.py --file tests/signals_testing/sample_signals/spy_realistic.json

# Run full test suite
python tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals
```

#### Manual MongoDB Insertion
```python
from pymongo import MongoClient
from datetime import datetime, timezone

client = MongoClient('mongodb://localhost:27018/?directConnection=true')
db = client['mathematricks_trading']

# Insert ENTRY signal
entry_signal = {
    "signalID": "sig_manual_001",
    "signal_type": "ENTRY",
    "strategy_name": "Test_Strategy",
    "signal_legs": [
        {
            "instrument": "AAPL",
            "instrument_type": "STOCK",
            "action": "BUY",
            "direction": "LONG",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 175.50
        }
    ],
    "environment": "staging",
    "staging": True,
    "signal_sent_EPOCH": int(datetime.now(timezone.utc).timestamp()),
    "created_at": datetime.now(timezone.utc)
}

result = db.trading_signals_raw.insert_one(entry_signal)
print(f"Inserted signal: {result.inserted_id}")
```

### Verifying Signal Processing

#### Check signal_store Collection
```bash
# Via MongoDB shell
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading

> db.signal_store.find({signal_id: "sig_manual_001"}).pretty()
```

#### Check Logs
```bash
# View service logs
docker logs mathematricks-trader-signal-ingestion-1 --tail 100 -f

# Expected output:
# ✅ ENTRY signal processed: sig_manual_001
# 📊 Created signal_store document
# 📱 Telegram notification sent
```

---

## Monitoring & Logs

### Log Files
Logs are written to:
- **Docker**: `docker logs mathematricks-trader-signal-ingestion-1`
- **Local**: `logs/signal_ingestion.log` (if configured)

### Log Format
```
2024-01-09 12:00:01 INFO  [signal_ingestion] Starting Signal Ingestion Service (staging mode)
2024-01-09 12:00:02 INFO  [signal_ingestion] Connected to MongoDB: mathematricks_trading
2024-01-09 12:00:02 INFO  [signal_ingestion] Watching trading_signals_raw collection...
2024-01-09 12:00:10 INFO  [signal_ingestion] ✅ ENTRY signal detected: sig_spy_001
2024-01-09 12:00:10 INFO  [signal_ingestion] 📊 Created signal_store document
2024-01-09 12:00:10 INFO  [signal_ingestion] 📱 Telegram notification sent
2024-01-09 12:05:15 INFO  [signal_ingestion] ✅ EXIT signal detected: sig_spy_002
2024-01-09 12:05:15 INFO  [signal_ingestion] 🔗 Appended EXIT leg to signal: sig_spy_001
2024-01-09 12:05:15 INFO  [signal_ingestion] 📊 Updated position status: CLOSED
```

### Telegram Notifications
Configure Telegram to receive real-time notifications:

```bash
# Set in .env file
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

**Notification Example**:
```
📊 ENTRY Signal Received
Strategy: SPY
Instrument: SPY
Quantity: 100
Signal ID: sig_spy_001
```

### Health Checks

#### Check if Service is Running
```bash
docker ps | grep signal-ingestion

# Expected output:
# mathematricks-trader-signal-ingestion-1   Up 5 minutes
```

#### Check MongoDB Connection
```python
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27018/?directConnection=true')
print(client.server_info())  # Should print server version
```

### Key Metrics to Monitor
1. **Signal Processing Rate**: Signals processed per minute
2. **Error Rate**: Failed signal processing attempts
3. **Change Stream Connection**: Uptime and reconnection attempts
4. **MongoDB Lag**: Time between signal insertion and processing
5. **Memory Usage**: Monitor for memory leaks

---

## Error Handling

### Common Errors and Solutions

#### 1. Parent Signal Not Found (EXIT Signal)
**Error**:
```
ERROR: Parent signal not found for EXIT: sig_spy_001
```

**Cause**: EXIT signal references an entry_signal_id that doesn't exist in signal_store

**Solution**:
- Verify ENTRY signal was processed successfully
- Check that entry_signal_id matches exactly
- Verify instrument match between ENTRY and EXIT

#### 2. Duplicate Signal ID
**Error**:
```
ERROR: Duplicate signal_id: sig_spy_001 already exists
```

**Cause**: Attempting to insert ENTRY signal with existing signal_id

**Solution**:
- Use unique signalID for each signal
- Check if signal already processed
- Clear test data if needed: `python scripts/junk/clear_test_data.py`

#### 3. MongoDB Connection Failed
**Error**:
```
ERROR: Failed to connect to MongoDB: Connection refused
```

**Cause**: MongoDB container not running or wrong connection string

**Solution**:
```bash
# Check MongoDB status
docker ps | grep mongodb

# Start MongoDB if not running
make start

# Verify connection string in .env
MONGODB_URI=mongodb://mongodb:27017/mathematricks_trading
```

#### 4. Change Stream Connection Lost
**Error**:
```
WARNING: Change Stream connection lost, reconnecting...
```

**Cause**: Network interruption or MongoDB restart

**Solution**:
- Service automatically reconnects with resume token
- No manual intervention needed
- Verify network connectivity if reconnection fails repeatedly

#### 5. Invalid Signal Format
**Error**:
```
ERROR: Invalid signal format: missing required field 'signal_legs'
```

**Cause**: Signal missing required fields

**Solution**:
Ensure signal contains:
- `signalID`
- `signal_type` (ENTRY/EXIT/SCALE)
- `strategy_name`
- `signal_legs` array with at least one leg
- `environment` field

---

## Development

### Running Tests

#### Unit Tests
```bash
cd services/signal_ingestion
pytest tests/
```

#### Integration Tests
```bash
# Clear test data
python scripts/junk/clear_test_data.py

# Run full test suite
python tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals

# Verify results
cat test_results/test_run_*.json
```

### Adding New Signal Types

To support a new signal type (e.g., `SCALE_IN`):

1. **Update `mongodb_watcher.py`**:
```python
def process_signal_document(self, raw_signal_doc):
    signal_type = raw_signal_doc.get('signal_type', 'ENTRY').upper()

    if signal_type == 'ENTRY':
        return self.create_signal_store_entry(raw_signal_doc)
    elif signal_type in ['EXIT', 'SCALE', 'SCALE_IN']:  # Add new type
        return self.append_leg_to_signal(raw_signal_doc)
```

2. **Update `signal_standardizer.py`**:
```python
VALID_SIGNAL_TYPES = ['ENTRY', 'EXIT', 'SCALE', 'SCALE_IN']

def validate_signal_type(signal_type):
    return signal_type.upper() in VALID_SIGNAL_TYPES
```

3. **Test New Signal Type**:
```bash
python tests/signals_testing/send_test_signal.py --file tests/signals_testing/sample_signals/scale_in_signal.json
```

### Debugging

#### Enable Debug Logging
```python
# In signal_ingestion_main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Inspect Change Stream Events
```python
# Add to mongodb_watcher.py
def start_watching(self):
    for change in change_stream:
        logger.debug(f"Change event: {change}")  # Print full event
        # ... rest of processing
```

#### Test Signal Processing Directly
```python
from mongodb_watcher import SignalStoreWatcher

watcher = SignalStoreWatcher(mongodb_uri, environment='staging')

# Test signal processing
test_signal = {
    "signalID": "sig_test_001",
    "signal_type": "ENTRY",
    "strategy_name": "Test",
    "signal_legs": [{"instrument": "AAPL", "action": "BUY", "quantity": 10}]
}

result = watcher.process_signal_document(test_signal)
print(f"Processing result: {result}")
```

---

## Related Documentation
- [Cerebro Service](cerebro_service.md) - Position sizing and decision making
- [Execution Service](execution_service.md) - Order execution
- [Signals Testing](signals_testing.md) - Test signal creation and validation
- [Setup Guide](../Setup.md) - Initial setup and configuration
