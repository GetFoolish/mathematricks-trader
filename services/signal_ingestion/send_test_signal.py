#!/usr/bin/env python3
"""
Send test signals directly to local MongoDB
Supports array format with sequential signal sending and wait times

Usage:
    # From file (recommended)
    python send_test_signal.py @simple_signal_equity_1.json

    # List available strategies
    python send_test_signal.py --list-strategies

Format:
    Array of signals with signal_type, signal_legs, and wait fields
    See sample files in services/signal_ingestion/sample_signals/
"""
import argparse
import json
import os
import sys
import random
import time
from pymongo import MongoClient
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def send_signal(payload: dict, signal_type: str = "single", previous_entry_id: str = None):
    """
    Insert signal directly into MongoDB signal_store collection

    Args:
        payload: Signal JSON matching webhook format
        signal_type: Type of signal ("entry", "exit", or "single")
        previous_entry_id: MongoDB ObjectId of previous ENTRY signal (for EXIT signals)
    """
    # Connect to MongoDB
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/?replicaSet=rs0')
    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        # Test connection
        client.server_info()
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print(f"   URI: {mongodb_uri}")
        sys.exit(1)

    db = client['mathematricks_trading']

    # Inject entry_signal_id if this is an EXIT signal and we have a previous ENTRY
    if signal_type == "exit" and previous_entry_id:
        # Check if payload has $PREVIOUS marker
        if payload.get("entry_signal_id") == "$PREVIOUS":
            payload["entry_signal_id"] = previous_entry_id
            print(f"✓ Injected entry_signal_id: {previous_entry_id[:12]}...")

    # Add metadata for local testing
    # Determine environment (staging by default for local testing)
    environment = "staging" if payload.get("staging", True) else "production"

    # Use timezone-aware UTC datetime
    now_utc = datetime.now(timezone.utc)

    # Normalize signal_legs → signal for MongoDB (mongodb_watcher expects 'signal' field)
    normalized_payload = payload.copy()
    if "signal_legs" in normalized_payload and "signal" not in normalized_payload:
        normalized_payload["signal"] = normalized_payload.pop("signal_legs")

    signal_doc = {
        **normalized_payload,
        "created_at": now_utc,
        "received_at": now_utc,  # Required by signal_ingestion
        "source": "test_script",
        "test": True,
        "staging": payload.get("staging", True),
        "environment": environment  # Required by Change Stream filter
    }

    # Auto-generate fields if missing
    if "signal_sent_EPOCH" not in signal_doc:
        signal_doc["signal_sent_EPOCH"] = int(now_utc.timestamp())

    if "signalID" not in signal_doc:
        strategy = signal_doc.get("strategy_name", "unknown")
        # Handle signal_legs (new) or signal (legacy) as array or dict
        signal_raw = signal_doc.get("signal_legs") or signal_doc.get("signal", {})
        if isinstance(signal_raw, list):
            instrument = signal_raw[0].get("instrument") or signal_raw[0].get("ticker", "unknown") if len(signal_raw) > 0 else "unknown"
        else:
            instrument = signal_raw.get("instrument") or signal_raw.get("ticker", "unknown")
        timestamp = signal_doc["signal_sent_EPOCH"]
        random_id = random.randint(0, 100000)
        signal_doc["signalID"] = f"test_{strategy}_{instrument}_{timestamp}_{random_id}"

    # Insert into trading_signals_raw collection
    try:
        result = db.trading_signals_raw.insert_one(signal_doc)

        print("=" * 80)
        if signal_type != "single":
            print(f"✅ Test Signal Inserted Successfully ({signal_type.upper()})")
        else:
            print("✅ Test Signal Inserted Successfully")
        print("=" * 80)
        print(f"Signal ID:    {signal_doc['signalID']}")
        print(f"Strategy:     {signal_doc.get('strategy_name', 'N/A')}")

        # Support both signal_legs (new) and signal (legacy)
        signal_data = signal_doc.get('signal_legs') or signal_doc.get('signal', {})
        # Handle signal_legs/signal as array or dict
        if isinstance(signal_data, list):
            first_leg = signal_data[0] if len(signal_data) > 0 else {}
            action = first_leg.get('action', 'N/A')
            quantity = first_leg.get('quantity', 'N/A')
            instrument = first_leg.get('instrument') or first_leg.get('ticker', 'N/A')
            leg_count = f" ({len(signal_data)} legs)" if len(signal_data) > 1 else ""
        else:
            action = signal_data.get('action', 'N/A')
            quantity = signal_data.get('quantity', 'N/A')
            instrument = signal_data.get('instrument') or signal_data.get('ticker', 'N/A')
            leg_count = ""
        print(f"Action:       {action} {quantity} {instrument}{leg_count}")

        # Show signal type if present (new array format)
        if "signal_type" in signal_doc:
            print(f"Type:         {signal_doc['signal_type']}")

        print(f"Staging:      {'Yes' if signal_doc.get('staging') else 'No'}")
        print(f"MongoDB ID:   {result.inserted_id}")
        print(f"Timestamp:    {now_utc.isoformat()}")
        print("=" * 80)
        print("\n📡 Signal should be picked up by signal_ingestion via Change Stream")
        print("\n💡 Monitor logs:")
        print("   tail -f logs/signal_ingestion.log    # Should show signal received")
        print("   tail -f logs/cerebro_service.log      # Should show position sizing")
        print("   tail -f logs/execution_service.log    # Should show order placement")
        print("")

        # For ENTRY signals, wait for signal_store to be populated and return the MongoDB _id
        entry_store_id = None
        if signal_type == "entry":
            print("⏳ Waiting for signal_ingestion to process ENTRY signal...")
            signal_id = signal_doc['signalID']

            # Poll signal_store for up to 10 seconds
            for i in range(20):  # 20 attempts, 0.5s each = 10s total
                time.sleep(0.5)
                signal_store_doc = db.signal_store.find_one({"signal_id": signal_id})
                if signal_store_doc:
                    entry_store_id = str(signal_store_doc['_id'])
                    print(f"✓ ENTRY signal processed - signal_store ID: {entry_store_id[:12]}...")
                    break

            if not entry_store_id:
                print("⚠️  WARNING: ENTRY signal not found in signal_store after 10s")
                print("   EXIT signal pairing may fail!")

        # Return both MongoDB _id and signal_store _id
        return_value = {
            "raw_id": str(result.inserted_id),
            "signal_id": signal_doc['signalID'],
            "signal_store_id": entry_store_id  # Only set for ENTRY signals
        }

    except Exception as e:
        print(f"❌ Failed to insert signal: {e}")
        sys.exit(1)

    client.close()
    return return_value


def list_strategies():
    """List available strategies from MongoDB"""
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/?replicaSet=rs0')
    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        sys.exit(1)

    db = client['mathematricks_trading']
    strategies = list(db.strategies.find({}, {"name": 1, "accounts": 1}))

    if not strategies:
        print("⚠️  No strategies found in MongoDB")
        print("   Add strategies using the portfolio_builder service")
        return

    print("\n📋 Available Strategies:")
    print("=" * 80)
    for strat in strategies:
        accounts = strat.get('accounts', [])
        account_str = ', '.join(accounts) if accounts else 'No accounts configured'
        print(f"  • {strat['name']}")
        print(f"    Accounts: {account_str}")
    print("=" * 80)
    print("")

    client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Send test signal directly to MongoDB (mimics webhook)",
        epilog="""
Examples:

  1. Simple equity signal:
     python send_test_signal.py @simple_signal_equity_1.json

  2. Ladder signal (6 sequential trades):
     python send_test_signal.py @ladder_signal_equity_1.json

  3. Pairs trading signal (multi-leg):
     python send_test_signal.py @pairs_signal_equity_1.json

  4. List available strategies:
     python send_test_signal.py --list-strategies

Signal Format (Array):

  [
    {
      "strategy_name": "US_Equity",
      "passphrase": "test_password_123",
      "signal_type": "ENTRY",
      "signal_legs": [
        {
          "instrument": "AAPL",
          "instrument_type": "STOCK",
          "action": "BUY",
          "direction": "LONG",
          "quantity": 10,
          "order_type": "MARKET",
          "price": 150.00,
          "environment": "staging"
        }
      ],
      "wait": 10
    },
    {
      "strategy_name": "US_Equity",
      "signal_type": "EXIT",
      "signal_legs": [...]
    }
  ]

Required fields per signal:
  - strategy_name: Name of the strategy
  - signal_type: "ENTRY" or "EXIT"
  - signal_legs: Array of legs with instrument, action, direction, quantity

Optional fields per signal:
  - signalID: Unique ID (auto-generated if missing)
  - signal_sent_EPOCH: Unix timestamp (auto-generated if missing)
  - passphrase: Authentication (not checked locally)
  - staging: true/false (default: true)
  - wait: Seconds to wait after sending this signal (default: 0)

See sample files in services/signal_ingestion/sample_signals/
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "json_payload",
        nargs="?",
        help='JSON string or @filename (e.g., \'{"strategy_name": "Forex", ...}\' or @signal.json)'
    )
    parser.add_argument(
        "--list-strategies",
        action="store_true",
        help="List available strategies from MongoDB"
    )

    args = parser.parse_args()

    # List strategies mode
    if args.list_strategies:
        list_strategies()
        return

    # Require JSON payload
    if not args.json_payload:
        parser.error("JSON payload is required (unless using --list-strategies)")

    # Read JSON payload
    json_str = args.json_payload

    # Handle @filename syntax
    if json_str.startswith("@"):
        filename = json_str[1:]
        try:
            with open(filename, 'r') as f:
                json_str = f.read()
        except FileNotFoundError:
            print(f"❌ File not found: {filename}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            sys.exit(1)

    # Parse JSON
    try:
        payload = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        print(f"\nReceived: {json_str[:200]}...")
        sys.exit(1)

    # Check format: array of signals or single signal
    if isinstance(payload, list):
        # Array format: Sequential signals with wait_after
        print("\n" + "=" * 80)
        print(f"📋 Processing {len(payload)} sequential signals")
        print("=" * 80)

        total_wait_time = 0
        previous_entry_id = None

        for i, signal_payload in enumerate(payload, 1):
            # Validate signal
            _validate_signal_payload(signal_payload, allow_signal_type=True)

            # Get signal type for display
            signal_type = signal_payload.get("signal_type", "UNKNOWN").upper()
            print(f"\n{'🔵' if signal_type == 'ENTRY' else '🔴'} Sending signal {i}/{len(payload)} ({signal_type})...")

            # Send signal (pass signal_type lowercase and previous_entry_id)
            result = send_signal(signal_payload, signal_type=signal_type.lower(), previous_entry_id=previous_entry_id)

            # Capture ENTRY signal_store ID for next EXIT signal
            if signal_type == "ENTRY" and result and result.get("signal_store_id"):
                previous_entry_id = result["signal_store_id"]

            # Wait if specified
            wait_seconds = signal_payload.get("wait", 0)
            if wait_seconds > 0 and i < len(payload):  # Don't wait after last signal
                print(f"\n⏳ Waiting {wait_seconds} seconds before next signal...")
                time.sleep(wait_seconds)
                total_wait_time += wait_seconds

        print("\n" + "=" * 80)
        print(f"✅ All {len(payload)} Signals Sent Successfully")
        print("=" * 80)
        if total_wait_time > 0:
            print(f"⏱️  Total wait time: {total_wait_time} seconds")
        print("")

    else:
        # Single signal format
        _validate_signal_payload(payload)
        send_signal(payload, signal_type="single")


def _validate_signal_payload(payload: dict, allow_signal_type: bool = False):
    """
    Validate a single signal payload

    Args:
        payload: Signal JSON to validate
        allow_signal_type: If True, check for signal_type field (new array format)

    Raises:
        SystemExit: If validation fails
    """
    # Validate required fields
    if "strategy_name" not in payload:
        print("❌ Missing required field: strategy_name")
        sys.exit(1)

    # Check for signal_type if required (new array format)
    if allow_signal_type and "signal_type" not in payload:
        print("❌ Missing required field: signal_type (must be 'ENTRY' or 'EXIT')")
        sys.exit(1)

    # Support both "signal_legs" (new) and "signal" (legacy)
    signal_legs = payload.get("signal_legs") or payload.get("signal")

    if not signal_legs:
        print("❌ Missing required field: signal_legs (or 'signal' for legacy format)")
        sys.exit(1)

    # Handle signal_legs as array (new format) or dict (legacy)
    if isinstance(signal_legs, list):
        if len(signal_legs) == 0:
            print("❌ Signal legs array is empty")
            sys.exit(1)
        # Validate first leg
        signal_to_validate = signal_legs[0]
    else:
        # Legacy format: signal is a dict
        signal_to_validate = signal_legs

    # Check for instrument (new) or ticker (legacy)
    if "instrument" not in signal_to_validate and "ticker" not in signal_to_validate:
        print("❌ Missing required field in signal leg: instrument (or ticker for legacy format)")
        sys.exit(1)

    # Check other required fields
    required_signal_fields = ["action", "quantity"]
    for field in required_signal_fields:
        if field not in signal_to_validate:
            print(f"❌ Missing required field in signal leg: {field}")
            sys.exit(1)


if __name__ == "__main__":
    main()
