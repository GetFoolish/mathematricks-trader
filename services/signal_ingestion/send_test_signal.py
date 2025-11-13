#!/usr/bin/env python3
"""
Send test signal directly to local MongoDB
Accepts JSON payload exactly like the webhook does

Usage:
    # Using JSON string
    python send_test_signal.py '{"strategy_name": "Forex", "signal_sent_EPOCH": 1234567890, "signalID": "test_123", "passphrase": "test_password_123", "signal": {"ticker": "AUDCAD", "action": "BUY", "quantity": 100000}}'

    # Using heredoc (easier for complex JSON)
    python send_test_signal.py "$(cat <<'EOF'
    {
        "strategy_name": "Forex",
        "signal_sent_EPOCH": $(date +%s),
        "signalID": "test_forex_$(date +%s)",
        "passphrase": "test_password_123",
        "signal": {
            "ticker": "AUDCAD",
            "action": "BUY",
            "quantity": 100000
        }
    }
    EOF
    )"

    # From file
    python send_test_signal.py @signal.json

    # List available strategies
    python send_test_signal.py --list-strategies
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


def send_signal(payload: dict, signal_type: str = "single"):
    """
    Insert signal directly into MongoDB signal_store collection

    Args:
        payload: Signal JSON matching webhook format
        signal_type: Type of signal ("entry", "exit", or "single")
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

    # Add metadata for local testing
    # Determine environment (staging by default for local testing)
    environment = "staging" if payload.get("staging", True) else "production"

    # Use timezone-aware UTC datetime
    now_utc = datetime.now(timezone.utc)

    signal_doc = {
        **payload,
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
        # Handle signal as array or dict
        signal_raw = signal_doc.get("signal", {})
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

        signal_data = signal_doc.get('signal', {})
        # Handle signal as array or dict
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

    except Exception as e:
        print(f"❌ Failed to insert signal: {e}")
        sys.exit(1)

    client.close()


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

  1. Simple JSON string:
     python send_test_signal.py '{"strategy_name": "Forex", "signal": {"ticker": "AUDCAD", "action": "BUY", "quantity": 100000}}'

  2. Using bash variables (recommended):
     SIGNAL_ID="test_forex_$RANDOM" && python send_test_signal.py '{
         "strategy_name": "Forex",
         "signal_sent_EPOCH": '$(date +%s)',
         "signalID": "'$SIGNAL_ID'",
         "passphrase": "test_password_123",
         "signal": {"ticker": "AUDCAD", "action": "BUY", "quantity": 100000}
     }'

  3. From a file (single signal):
     python send_test_signal.py @signal.json

  4. From a file with entry/exit pair:
     python send_test_signal.py @sample_forex_signal.json
     python send_test_signal.py @sample_forex_signal.json --wait 15

  5. List available strategies:
     python send_test_signal.py --list-strategies

Signal Formats:

  A. Single Signal (legacy):
     {
       "strategy_name": "Forex",
       "signal": [{"instrument": "AUDCAD", "action": "BUY", ...}]
     }

  B. Entry/Exit Pair (recommended for testing):
     {
       "entry": {
         "strategy_name": "Forex",
         "signal": [{"instrument": "AUDCAD", "action": "BUY", ...}]
       },
       "exit": {
         "strategy_name": "Forex",
         "signal": [{"instrument": "AUDCAD", "action": "SELL", ...}]
       }
     }
     (Sends entry, waits N seconds, then sends exit)

Required JSON fields (per signal):
  - strategy_name: Name of the strategy
  - signal: Array with instrument, action, quantity

Optional JSON fields:
  - signalID: Unique ID (auto-generated if missing)
  - signal_sent_EPOCH: Unix timestamp (auto-generated if missing)
  - passphrase: Authentication (not checked locally)
  - staging: true/false (default: true)
  - --wait N: Seconds between entry/exit (default: 10)
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
    parser.add_argument(
        "--wait",
        type=int,
        default=10,
        help="Seconds to wait between entry and exit signals (default: 10)"
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

    # Check if this is an entry/exit pair or a single signal
    has_entry_exit = "entry" in payload and "exit" in payload

    if has_entry_exit:
        # Entry/Exit format - validate and send both
        entry_payload = payload["entry"]
        exit_payload = payload["exit"]

        # Validate entry signal
        _validate_signal_payload(entry_payload)

        # Validate exit signal
        _validate_signal_payload(exit_payload)

        # Send entry signal
        print("\n🔵 Sending ENTRY signal...")
        send_signal(entry_payload, signal_type="entry")

        # Wait between signals
        wait_seconds = args.wait
        print(f"\n⏳ Waiting {wait_seconds} seconds before sending EXIT signal...")
        time.sleep(wait_seconds)

        # Send exit signal
        print("\n🔴 Sending EXIT signal...")
        send_signal(exit_payload, signal_type="exit")

        print("\n" + "=" * 80)
        print("✅ Entry/Exit Signal Pair Sent Successfully")
        print("=" * 80)
        print(f"⏱️  Total time: {wait_seconds} seconds between entry and exit")
        print("")

    else:
        # Single signal format (backward compatible)
        _validate_signal_payload(payload)
        send_signal(payload, signal_type="single")


def _validate_signal_payload(payload: dict):
    """
    Validate a single signal payload

    Args:
        payload: Signal JSON to validate

    Raises:
        SystemExit: If validation fails
    """
    # Validate required fields
    if "strategy_name" not in payload:
        print("❌ Missing required field: strategy_name")
        sys.exit(1)

    if "signal" not in payload:
        print("❌ Missing required field: signal")
        sys.exit(1)

    signal = payload["signal"]

    # Handle signal as array (new format) or dict (legacy)
    if isinstance(signal, list):
        if len(signal) == 0:
            print("❌ Signal array is empty")
            sys.exit(1)
        # Validate first leg
        signal_to_validate = signal[0]
    else:
        # Legacy format: signal is a dict
        signal_to_validate = signal

    # Check for instrument (new) or ticker (legacy)
    if "instrument" not in signal_to_validate and "ticker" not in signal_to_validate:
        print("❌ Missing required field in signal: instrument (or ticker for legacy format)")
        sys.exit(1)

    # Check other required fields
    required_signal_fields = ["action", "quantity"]
    for field in required_signal_fields:
        if field not in signal_to_validate:
            print(f"❌ Missing required field in signal: {field}")
            sys.exit(1)


if __name__ == "__main__":
    main()
