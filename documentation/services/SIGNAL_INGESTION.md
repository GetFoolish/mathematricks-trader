# Signal Ingestion Service

## Overview

The Signal Ingestion Service is responsible for receiving trading signals from external sources and preparing them for processing by the Cerebro Service. It acts as the entry point for all trading signals in the Mathematricks trading system.

**Main File:** `services/signal_ingestion/mongodb_watcher.py`  
**Entry Point:** `services/signal_ingestion/signal_ingestion_main.py`  
**Port:** N/A (MongoDB Change Stream listener)

## Purpose

- **Watch MongoDB** for new incoming signals via Change Streams
- **Normalize signal data** into the consolidated schema
- **Link signals** (ENTRY → EXIT relationships)
- **Forward signals** to Cerebro Service for decision-making
- **Catch up** on missed signals during downtime

## Architecture

### How It Works

```
Webhook → trading_signals_raw → MongoDBWatcher → signal_store → Cerebro Service
          (MongoDB)                (Change Stream)   (Consolidated)
```

### Key Components

1. **MongoDBWatcher Class**
   - Monitors `trading_signals_raw` collection via MongoDB Change Streams
   - Processes new signals in real-time
   - Handles reconnection and resume tokens for resilience

2. **Signal Store Builder**
   - Creates consolidated signal documents in `signal_store` collection
   - Links EXIT/SCALE signals to parent ENTRY signals
   - Builds leg-based structure for multi-leg strategies

3. **Catchup Mode**
   - Fetches missed signals on startup
   - Processes unprocessed signals (where `mathematricks_signal_id` doesn't exist)
   - Maintains order by `received_at` timestamp

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | Required |
| `CEREBRO_SERVICE_URL` | Cerebro service endpoint | `http://cerebro-service:8082` |
| `ENVIRONMENT` | Trading environment (production/staging) | `production` |

### MongoDB Collections

#### Input Collection: `trading_signals_raw`
Stores raw signals received from webhook:
```javascript
{
  _id: ObjectId,
  signalID: "SIGNAL_123",
  strategy_name: "MaxCAGR_v2",
  signal_type: "ENTRY" | "EXIT" | "SCALE_IN" | "SCALE_OUT",
  entry_signal_id: "SIGNAL_122",  // For EXIT signals
  signal: [
    {
      instrument: "AAPL",
      action: "BUY",
      quantity: 100,
      price: 150.0,
      order_type: "MARKET"
    }
  ],
  received_at: ISODate,
  signal_sent_EPOCH: 1234567890,
  environment: "production",
  account_type: "paper",
  data_source: "mock",
  mode: "mock_live",
  mathematricks_signal_id: ObjectId  // Link to signal_store (added by watcher)
}
```

#### Output Collection: `signal_store`
Consolidated signal storage with embedded legs:
```javascript
{
  _id: ObjectId,
  signal_id: "SIGNAL_123",
  base_signal_id: "SIGNAL_123",
  entry_name: "ENTRY_XYZ",
  strategy_id: "MaxCAGR_v2",
  environment: "production",
  instrument: "AAPL",
  
  // Array of legs (ENTRY, EXIT, SCALE_IN, SCALE_OUT)
  legs: [
    {
      leg_id: "SIGNAL_123__entry_0",
      leg_type: "ENTRY",
      leg_index: 0,
      raw: {
        _id: ObjectId,  // Reference to trading_signals_raw
        received_at: ISODate,
        legs: [...]
      },
      decision: {
        status: "APPROVED",  // Set by Cerebro
        reason: "Position sizing approved",
        quantity: 100,
        math: "..."
      },
      execution: {
        status: "FILLED",  // Set by Execution Service
        filled_quantity: 100,
        avg_price: 150.05
      },
      processing_timestamps: {
        signal_received: ISODate,
        signal_ingestion_processed: ISODate,
        cerebro_processed: ISODate,
        execution_started: ISODate,
        execution_completed: ISODate
      }
    }
  ],
  
  position: {
    status: "OPEN" | "CLOSED",
    entry_quantity: 100,
    exit_quantity: 0,
    remaining_quantity: 100
  },
  
  created_at: ISODate,
  updated_at: ISODate
}
```

## Key Functions

### `_build_signal_store_doc(raw_signal_doc, signal_array)`
Builds a new signal_store document for ENTRY signals.

**Parameters:**
- `raw_signal_doc`: Raw signal from trading_signals_raw
- `signal_array`: Array of leg data

**Returns:** Signal store document

### `_build_leg_data(raw_signal_doc, signal_array, leg_index)`
Builds leg data structure for a single leg.

**Parameters:**
- `raw_signal_doc`: Raw signal document
- `signal_array`: Array of instruments/actions
- `leg_index`: Index of this leg in the legs array

**Returns:** Leg object

### `watch_for_new_signals()`
Main loop that watches MongoDB Change Stream for new signals.

**Returns:** Status string (`'success'`, `'token_reset'`, `'error'`)

### `fetch_missed_signals()`
Catch-up mode: fetches unprocessed signals from MongoDB.

**Side Effects:** Creates signal_store documents and calls signal callback

## Signal Processing Flow

1. **Signal Received**
   - Webhook writes to `trading_signals_raw`
   - Change Stream detects insert operation

2. **Signal Classification**
   - Determines signal type (ENTRY, EXIT, SCALE_IN, SCALE_OUT)
   - Checks for parent signal reference (EXIT signals)

3. **Document Creation/Update**
   - **ENTRY**: Creates new signal_store document with first leg
   - **EXIT/SCALE**: Appends leg to existing parent document

4. **Forward to Cerebro**
   - Calls signal callback with formatted signal data
   - Includes `mathematricks_signal_id` for tracking

5. **Mark Processed**
   - Updates `trading_signals_raw` with `mathematricks_signal_id` link
   - Prevents duplicate processing

## Example Usage

### Starting the Service

```bash
# From project root
cd services/signal_ingestion
python signal_ingestion_main.py
```

### Processing Flow

```python
# Initialize watcher
watcher = MongoDBWatcher(
    mongodb_url="mongodb://localhost:27018",
    environment="production"
)

# Set callback for new signals
def on_new_signal(signal_data, received_time, is_catchup, mongodb_object_id):
    print(f"New signal: {signal_data['signalID']}")
    # Forward to Cerebro...

watcher.set_signal_callback(on_new_signal)

# Fetch missed signals (catchup mode)
watcher.fetch_missed_signals()

# Watch for new signals (blocking)
watcher.watch_for_new_signals()
```

## Troubleshooting

### Problem: Change Stream disconnects frequently
**Solution:** 
- Check MongoDB connection stability
- Verify resume token is being saved
- Check for invalid resume token errors (code 260)

### Problem: Duplicate signals in signal_store
**Cause:** Multiple watcher instances running
**Solution:**
- Ensure only one signal_ingestion service is running
- Check for duplicate signalID before creating ENTRY documents

### Problem: EXIT signals not linking to ENTRY
**Cause:** Missing or incorrect `entry_signal_id` field
**Solution:**
- Verify EXIT signals include `entry_signal_id` matching parent ENTRY's `entry_name`
- Check signal_store for matching `entry_name` or `base_signal_id`

### Problem: High processing lag
**Symptoms:** Large gap between `received_at` and `signal_ingestion_processed`
**Solutions:**
- Check MongoDB query performance
- Verify Change Stream is not falling behind
- Inspect MongoDB server load

### Problem: Signals not being processed
**Debug Steps:**
1. Check if Change Stream is connected: Look for "✅ Change Stream connected" log
2. Verify environment filter matches: Check `environment` field in raw signals
3. Test MongoDB connection: `mongo_client.admin.command('ping')`
4. Check for unprocessed signals: Query `trading_signals_raw` where `mathematricks_signal_id` doesn't exist

## Performance Notes

- **Change Streams** provide real-time updates with minimal latency (~10-50ms)
- **Resume tokens** allow seamless reconnection without data loss
- **Catchup mode** processes missed signals in chronological order
- **Consolidated schema** reduces database writes (one document per signal vs one per leg)

## Dependencies

- `pymongo` - MongoDB driver with Change Stream support
- `python-dateutil` - Timestamp parsing
- `requests` - HTTP client for Cerebro forwarding

## Related Services

- **Cerebro Service** - Receives signals for decision-making
- **Execution Service** - Executes approved orders
- **Webhook Receiver** - Writes raw signals to `trading_signals_raw`

## Schema Evolution

**Current Version:** v3 (Consolidated Schema)

**Previous Versions:**
- v1: Separate documents per leg
- v2: Separate signal_store and execution_confirmations collections

**Benefits of v3:**
- Single source of truth per signal
- Simplified querying and joins
- Better support for multi-leg strategies
- Easier tracking of signal lifecycle
