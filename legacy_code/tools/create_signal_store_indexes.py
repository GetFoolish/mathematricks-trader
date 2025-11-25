#!/usr/bin/env python3
"""
Create MongoDB indexes for signal-centric refactoring

Creates indexes on:
- trading_signals_raw: For efficient query of unprocessed signals
- signal_store: For efficient position tracking and PnL queries
"""
import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

# Load environment variables
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(ENV_PATH)

def create_indexes():
    """Create MongoDB indexes for signal-centric architecture"""

    # Connect to MongoDB
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/?replicaSet=rs0')

    try:
        # Only use TLS for remote MongoDB Atlas connections
        use_tls = 'mongodb+srv' in mongodb_uri or 'mongodb.net' in mongodb_uri
        if use_tls:
            client = MongoClient(mongodb_uri, tls=True, tlsAllowInvalidCertificates=True)
        else:
            client = MongoClient(mongodb_uri)

        # Test connection
        client.server_info()
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        sys.exit(1)

    db = client['mathematricks_trading']

    print("\n" + "="*80)
    print("Creating indexes for signal-centric architecture")
    print("="*80 + "\n")

    # =========================================================================
    # TRADING_SIGNALS_RAW INDEXES
    # =========================================================================

    print("📋 Creating indexes for trading_signals_raw collection...")

    trading_signals_raw = db['trading_signals_raw']

    # Index 1: Query unprocessed signals by environment
    index_name = trading_signals_raw.create_index([
        ("environment", ASCENDING),
        ("mathematricks_signal_id", ASCENDING)
    ], name="environment_processed_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 2: Query by received_at for catch-up
    index_name = trading_signals_raw.create_index([
        ("received_at", ASCENDING)
    ], name="received_at_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 3: Query by signalID for lookups
    index_name = trading_signals_raw.create_index([
        ("signalID", ASCENDING)
    ], name="signalID_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 4: Query by mathematricks_signal_id for reverse lookups
    index_name = trading_signals_raw.create_index([
        ("mathematricks_signal_id", ASCENDING)
    ], name="mathematricks_signal_id_idx")
    print(f"  ✅ Created index: {index_name}")

    # =========================================================================
    # SIGNAL_STORE INDEXES
    # =========================================================================

    print("\n📋 Creating indexes for signal_store collection...")

    signal_store = db['signal_store']

    # Index 1: Query open positions by strategy/instrument/direction (EXIT signals need this)
    index_name = signal_store.create_index([
        ("strategy_id", ASCENDING),
        ("instrument", ASCENDING),
        ("direction", ASCENDING),
        ("position_status", ASCENDING)
    ], name="open_positions_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 2: Query open positions by strategy (deployed capital calculation)
    index_name = signal_store.create_index([
        ("strategy_id", ASCENDING),
        ("position_status", ASCENDING)
    ], name="strategy_positions_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 3: Query by entry_signal_id (for EXIT signals to find their entry)
    index_name = signal_store.create_index([
        ("entry_signal_id", ASCENDING)
    ], name="entry_signal_id_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 4: Query by exit_signals array (for entry signals to find their exits)
    index_name = signal_store.create_index([
        ("exit_signals", ASCENDING)
    ], name="exit_signals_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 5: Query by raw_signal_id (link back to trading_signals_raw)
    index_name = signal_store.create_index([
        ("raw_signal_id", ASCENDING)
    ], name="raw_signal_id_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 6: Query by signal_id for lookups
    index_name = signal_store.create_index([
        ("signal_id", ASCENDING)
    ], name="signal_id_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 7: Query by environment and created_at for time-series analysis
    index_name = signal_store.create_index([
        ("environment", ASCENDING),
        ("created_at", DESCENDING)
    ], name="environment_created_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 8: Query filled OPEN positions (for deployed capital calculation)
    index_name = signal_store.create_index([
        ("strategy_id", ASCENDING),
        ("position_status", ASCENDING),
        ("execution.status", ASCENDING)
    ], name="filled_open_positions_idx")
    print(f"  ✅ Created index: {index_name}")

    # Index 9: Cerebro decision action for analytics
    index_name = signal_store.create_index([
        ("cerebro_decision.action", ASCENDING),
        ("created_at", DESCENDING)
    ], name="cerebro_action_idx")
    print(f"  ✅ Created index: {index_name}")

    print("\n" + "="*80)
    print("✅ All indexes created successfully!")
    print("="*80)

    # List all indexes
    print("\n📊 Trading Signals Raw Indexes:")
    for index in trading_signals_raw.list_indexes():
        print(f"  - {index['name']}")

    print("\n📊 Signal Store Indexes:")
    for index in signal_store.list_indexes():
        print(f"  - {index['name']}")

    print("\n")
    client.close()


if __name__ == "__main__":
    create_indexes()
