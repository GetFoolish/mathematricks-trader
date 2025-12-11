# Signal Ingestion Service

## Overview

The Signal Ingestion Service monitors MongoDB for incoming trading signals and routes them to other microservices via Google Cloud Pub/Sub. It acts as the entry point for all trading signals into the Mathematricks Trader system.

## Location

`/services/signal_ingestion/`

## Key Responsibilities

1. Monitor MongoDB for new trading signals using Change Streams
2. Standardize incoming signals to a consistent format
3. Generate unique signal IDs
4. Publish signals to Pub/Sub for downstream processing
5. Store signal metadata in the signal_store collection
6. Handle service interruptions by catching up on missed signals

## Main Files

### signal_ingestion_main.py
- Entry point for the service
- Service orchestration and lifecycle management
- Coordinates MongoDB watcher and Pub/Sub publishing

### mongodb_watcher.py
- Implements MongoDB Change Streams listener
- Detects new signals in real-time
- Handles reconnection and retry logic
- Catches up on missed signals when service restarts

### signal_standardizer.py
- Converts raw signals to standardized format
- Generates unique signal_id with format: `sig_{timestamp}_{random}`
- Validates signal structure
- Enriches signals with metadata

## Key Classes

### SignalIngestionService
Main service class that orchestrates the signal flow:
- Manages MongoDB connection
- Coordinates signal processing
- Publishes to Pub/Sub
- Handles errors and logging

### MongoDBWatcher
Watches MongoDB for new signals:
- Uses MongoDB Change Streams API
- Detects insertions in `trading_signals_raw` collection
- Handles connection failures gracefully
- Implements exponential backoff for retries

### SignalStandardizer
Standardizes signal format:
- Generates signal_id
- Validates required fields
- Enriches with timestamps
- Ensures consistent structure

## Workflow

1. MongoDB Change Stream watches `trading_signals_raw` collection
2. When new signal arrives, `MongoDBWatcher` detects it
3. `SignalStandardizer` converts to standardized format
4. Signal metadata saved to `signal_store` collection
5. Signal published to Pub/Sub topic `standardized-signals`
6. On startup, catches up on any missed signals while service was down

## MongoDB Collections

### trading_signals_raw (Read)
Raw signals from external sources (TradingView webhooks, email collectors, etc.)

Example document:
```json
{
  "_id": "abc123",
  "strategy_name": "SPX 1-Day Options",
  "timestamp": "2024-11-24T10:30:00Z",
  "signal": [
    {
      "instrument": "SPY",
      "action": "ENTRY",
      "direction": "LONG",
      "quantity": 10,
      "order_type": "MARKET"
    }
  ],
  "environment": "staging"
}
```

### signal_store (Write)
Signal metadata with Cerebro decisions and order IDs:
```json
{
  "signal_id": "sig_1732450800_5678",
  "received_time": "2024-11-24T10:30:00Z",
  "signal_data": { ... },
  "cerebro_decision": { ... },
  "order_id": "ord_123",
  "status": "PROCESSING"
}
```

## Pub/Sub Integration

### Published Topics

**standardized-signals**
- Sends standardized signals to Cerebro Service
- Message format: JSON with signal_id, signal_data, metadata

## Configuration

### Environment Variables
```bash
# MongoDB connection (local with replica set)
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0

# OR MongoDB Atlas (cloud)
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/

# Service configuration
environment=staging  # or "production"
```

### Service Mode
The `environment` setting controls which signals to process:
- `staging` - Process only signals with `environment: "staging"`
- `production` - Process only signals with `environment: "production"`

## API Endpoints

This is a background service with no REST API endpoints.

## Error Handling

1. **MongoDB Connection Failures**
   - Exponential backoff retry
   - Logs connection errors
   - Sends Telegram notifications

2. **Malformed Signals**
   - Logs validation errors
   - Skips invalid signals
   - Does not publish to Pub/Sub

3. **Pub/Sub Failures**
   - Retries publishing
   - Logs publish errors
   - Signals marked as failed in signal_store

## Logging

Logs to:
- Console (real-time output)
- `logs/signal_ingestion.log` (service-specific)
- `logs/signal_processing.log` (unified signal journey)

Log level: **DEBUG** (includes detailed diagnostics for MongoDB connections and change streams)

Log format:
```
|LEVEL|Message|Timestamp|file:filename.py:line No.LineNumber|
```

Example log entries:
```
|DEBUG|🔧 Initializing MongoDBWatcher with URL: mongodb+srv://...|2024-11-24T10:30:00|mongodb_watcher.py:34|
|DEBUG|🔗 MongoDB URL: mongodb+srv://...|2024-11-24T10:30:00|mongodb_watcher.py:217|
|INFO|Watching for signals in trading_signals_raw|2024-11-24T10:30:00|mongodb_watcher.py:45|
|DEBUG|🔔 Change stream event received! Type: insert|2024-11-24T10:30:01|mongodb_watcher.py:222|
|INFO|New signal detected: sig_1732450800_5678|2024-11-24T10:30:01|mongodb_watcher.py:78|
|INFO|Published signal to standardized-signals topic|2024-11-24T10:30:02|signal_ingestion_main.py:120|
```

## Dependencies

- **Google Cloud Pub/Sub** - Message queue for inter-service communication
- **MongoDB with Replica Set** - Required for Change Streams
- **Telegram notifier** - For critical error notifications
- **Python packages**:
  - `pymongo>=4.6.1`
  - `google-cloud-pubsub>=2.18.4`
  - `python-dotenv>=1.0.0`

## Startup Command

```bash
# Standard startup (via mvp_demo_start.py)
python services/signal_ingestion/signal_ingestion_main.py

# Manual startup with environment
python services/signal_ingestion/signal_ingestion_main.py --environment staging
```

## Health Checks

Check service status:
```bash
python mvp_demo_status.py
```

View logs:
```bash
tail -f logs/signal_ingestion.log
```

## Related Documentation

- [Cerebro Service](cerebro_service.md) - Processes signals from this service
- [Execution Service](execution_service.md) - Executes orders from processed signals
- [Testing Signals](signals_testing.md) - How to send test signals

## Common Issues

### Service Not Detecting Signals

**Check MongoDB Connection:**
1. View debug logs to verify which MongoDB URL is being used:
   ```bash
   grep "🔧 Initializing MongoDBWatcher" logs/SignalListener.log
   grep "🔗 MongoDB URL" logs/SignalListener.log
   ```

2. Common issue: Service connecting to `localhost` instead of cloud MongoDB
   - Verify `MONGODB_URI` in `.env` file points to correct instance
   - Restart service after updating `.env` to pick up new connection string

**Other checks:**
- Verify MongoDB is running with replica set: `mongod --replSet rs0` (for local)
- Check `trading_signals_raw` collection exists in the correct database
- Verify `environment` setting matches signal environment
- Look for change stream events in DEBUG logs: `🔔 Change stream event received`

### Pub/Sub Publishing Failures
- Ensure Pub/Sub emulator is running
- Check `PUBSUB_EMULATOR_HOST` environment variable
- Verify topic `standardized-signals` exists

### Missed Signals
- Check service uptime in logs
- Look for connection errors in `signal_ingestion.log`
- Service will catch up on startup automatically

### MongoDB Connection Troubleshooting

**Symptom:** Change stream connects but never receives events

**Diagnosis:**
```bash
# Check which MongoDB URL the service is using
tail -f logs/SignalListener.log | grep "MongoDB URL"

# Manually test MongoDB connection
python3 -c "
from pymongo import MongoClient
import os
from dotenv import load_dotenv
load_dotenv()
client = MongoClient(os.getenv('MONGODB_URI'), tls=True, tlsAllowInvalidCertificates=True)
print('Connected to:', client.address)
print('Databases:', client.list_database_names())
"
```

**Solution:** Ensure `.env` file has correct `MONGODB_URI` and restart service
