#!/usr/bin/env python3
"""
Send test signals directly to local MongoDB
Supports array format with sequential signal sending and wait times

Usage:
    # From file (recommended)
    python send_test_signal.py --file simple_signal_equity_1.json
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
import logging
from pymongo import MongoClient
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def setup_logging():
    """Setup dual logging to console and file"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('send_test_signal')
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    
    # File handler
    file_handler = logging.FileHandler('logs/testing.log', mode='a')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


# Initialize logger
logger = setup_logging()


def send_signal(payload: dict, signal_type: str = "single", previous_entry_id: str = None):
    """
    Insert signal directly into MongoDB signal_store collection

    Args:
        payload: Signal JSON matching webhook format
        signal_type: Type of signal ("entry", "exit", or "single")
        previous_entry_id: MongoDB ObjectId of previous ENTRY signal (for EXIT signals)
    """
    # Connect to MongoDB
    # Use MONGODB_URI_LOCAL for Mac scripts, fallback to MONGODB_URI for Docker
    mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI')
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
        # Replace any variable reference (starting with $) with the resolved ID
        entry_ref = payload.get("entry_signal_id", "")
        if entry_ref.startswith("$"):
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
    # ALWAYS use current timestamp (override any hardcoded values from JSON)
    signal_doc["signal_sent_EPOCH"] = int(now_utc.timestamp())

    if "signalID" not in signal_doc:
        # Simple auto-generated ID: just timestamp_random
        # User can provide their own signalID in the signal file for custom IDs
        timestamp = signal_doc["signal_sent_EPOCH"]
        random_id = random.randint(1000, 9999)
        signal_doc["signalID"] = f"sig_{timestamp}_{random_id}"

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
                # Sort by _id descending to get the NEWEST entry with this signal_id
                # (avoids picking up stale entries from previous test runs)
                signal_store_doc = db.signal_store.find_one(
                    {"signal_id": signal_id},
                    sort=[("_id", -1)]
                )
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
    # Use MONGODB_URI_LOCAL for Mac scripts, fallback to MONGODB_URI for Docker
    mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI')
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


def shuffle_signals(entry_signals: list, exit_signals_by_entry: dict, seed: int) -> list:
    """
    Shuffle signals realistically: entries and exits are interleaved randomly,
    but an exit never comes before its corresponding entry.

    Algorithm:
    1. Shuffle entries to get random entry order
    2. For each entry, assign its exit a random position AFTER the entry
    3. Build final list respecting these constraints

    Args:
        entry_signals: List of (signal, source_file) tuples for ENTRY signals
        exit_signals_by_entry: Dict mapping (source_file, entry_name) -> list of (exit_signal, source_file)
        seed: Random seed (0=random time-based, positive=reproducible, negative=no shuffle)

    Returns:
        List of (signal, source_file) tuples in the shuffled order
    """
    if seed < 0:
        # No shuffle - just pair entries with exits sequentially
        ordered = []
        for entry_sig, entry_source in entry_signals:
            ordered.append((entry_sig, entry_source))
            entry_name = entry_sig.get("entry_name")
            key = (entry_source, entry_name)
            if entry_name and key in exit_signals_by_entry:
                for exit_sig, exit_source in exit_signals_by_entry[key]:
                    ordered.append((exit_sig, exit_source))
        return ordered

    # Initialize random with seed
    rng = random.Random(seed if seed > 0 else None)

    # Shuffle entries
    shuffled_entries = list(entry_signals)
    rng.shuffle(shuffled_entries)

    # Collect all exits with their constraints
    # Each exit must come after its entry's position
    exits_with_constraints = []  # List of (exit_sig, exit_source, entry_index)

    for entry_idx, (entry_sig, entry_source) in enumerate(shuffled_entries):
        entry_name = entry_sig.get("entry_name")
        key = (entry_source, entry_name)
        if entry_name and key in exit_signals_by_entry:
            for exit_sig, exit_source in exit_signals_by_entry[key]:
                exits_with_constraints.append((exit_sig, exit_source, entry_idx))

    # Shuffle exits
    rng.shuffle(exits_with_constraints)

    # Build final list by interleaving
    # We'll insert signals one by one, respecting constraints
    # Use a simple greedy approach: for each slot, pick randomly from available signals

    total_signals = len(shuffled_entries) + len(exits_with_constraints)
    result = []
    entries_placed = set()  # Track which entry indices have been placed
    remaining_entries = list(range(len(shuffled_entries)))
    remaining_exits = list(exits_with_constraints)

    rng.shuffle(remaining_entries)

    for _ in range(total_signals):
        # Determine what's available to place
        available_entries = remaining_entries[:]
        available_exits = [
            (i, ex) for i, ex in enumerate(remaining_exits)
            if ex[2] in entries_placed  # Exit's entry has been placed
        ]

        # Build choice pool
        choices = []
        if available_entries:
            choices.append(('entry', available_entries[0]))
        if available_exits:
            choices.append(('exit', available_exits[0]))

        if not choices:
            break

        # Random choice between entry and exit (if both available)
        choice_type, choice_data = rng.choice(choices)

        if choice_type == 'entry':
            entry_idx = choice_data
            entry_sig, entry_source = shuffled_entries[entry_idx]
            result.append((entry_sig, entry_source))
            entries_placed.add(entry_idx)
            remaining_entries.remove(entry_idx)
        else:
            exit_list_idx, (exit_sig, exit_source, _) = choice_data
            result.append((exit_sig, exit_source))
            remaining_exits.pop(exit_list_idx)

    return result


def process_folder(folder_path: str, seed: int = 1, delay_override: int = None,
                   signal_count: int = None, pause_and_play: bool = False):
    """
    Load and send all JSON signal files from a folder

    IMPORTANT: This function ensures ENTRY signals are always sent before their
    corresponding EXIT signals, even when shuffling is enabled.

    Args:
        folder_path: Path to folder containing *.json signal files
        seed: Seed for shuffling (0=random, positive=reproducible, negative=no shuffle)
        delay_override: Override wait time between signals (seconds). None = use signal's wait value
        signal_count: Limit total number of signals to send (None = all).
        pause_and_play: If True, pause after each signal and wait for Enter key
    """
    import glob

    # Log separator for new test run
    logger.info("\n" + "-" * 100)
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] NEW SIGNAL SEND STARTED")
    logger.info("-" * 100 + "\n")

    # Validate folder exists
    if not os.path.isdir(folder_path):
        logger.info(f"❌ Folder not found: {folder_path}")
        sys.exit(1)

    # Find all .json files in folder
    json_files = sorted(glob.glob(os.path.join(folder_path, "*.json")))

    if not json_files:
        logger.info(f"❌ No .json files found in: {folder_path}")
        sys.exit(1)

    logger.info("\n" + "=" * 80)
    logger.info(f"📁 Loading signals from folder: {folder_path}")
    logger.info(f"   Found {len(json_files)} signal files")
    logger.info("=" * 80)

    # Load all signals from all files, separating ENTRY and EXIT
    # Use (source_file, entry_name) as key to avoid collisions across files
    entry_signals = []  # List of (signal, source_file)
    exit_signals_by_entry = {}  # Maps (source_file, entry_name) -> list of (exit_signal, source_file)

    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                file_signals = json.load(f)

            source_file = os.path.basename(json_file)

            # Handle both array and single signal formats
            if not isinstance(file_signals, list):
                file_signals = [file_signals]

            for sig in file_signals:
                signal_type = sig.get("signal_type", "ENTRY").upper()

                if signal_type == "ENTRY":
                    entry_signals.append((sig, source_file))
                elif signal_type == "EXIT":
                    # Group EXIT signals by (source_file, entry_signal_id) to avoid cross-file collisions
                    entry_ref = sig.get("entry_signal_id", "$PREVIOUS")
                    key = (source_file, entry_ref)
                    if key not in exit_signals_by_entry:
                        exit_signals_by_entry[key] = []
                    exit_signals_by_entry[key].append((sig, source_file))

            print(f"✓ Loaded {len(file_signals)} signal(s) from {source_file}")

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {os.path.basename(json_file)}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error reading {os.path.basename(json_file)}: {e}")
            sys.exit(1)

    total_entries = len(entry_signals)
    total_exits = sum(len(exits) for exits in exit_signals_by_entry.values())
    print(f"\n📊 Total signals loaded: {total_entries + total_exits} ({total_entries} ENTRY, {total_exits} EXIT)")

    # Shuffle signals with realistic interleaving
    if seed >= 0:
        shuffle_type = "reproducible" if seed > 0 else "randomized"
        print(f"🔀 Shuffling signals ({shuffle_type}, seed={seed})")
        print(f"   Entries and exits interleaved randomly, exits always after their entry")
    else:
        print(f"📌 Signal order preserved (seed={seed})")

    ordered_signals = shuffle_signals(entry_signals, exit_signals_by_entry, seed)

    if pause_and_play:
        print(f"⏸️  Pause-and-play enabled: will pause after each signal")

    print("=" * 80 + "\n")

    # Limit total number of signals if signal_count specified
    if signal_count is not None and signal_count > 0:
        if signal_count < len(ordered_signals):
            ordered_signals = ordered_signals[:signal_count]
            print(f"✂️  Limited to first {signal_count} total signals")
        else:
            print(f"📊 Signal count {signal_count} >= total signals {len(ordered_signals)}, using all")

    # Send all signals in the correct order
    total_wait_time = 0
    entry_id_registry = {}
    signals_sent = 0

    for i, (signal_payload, source_file) in enumerate(ordered_signals, 1):
        # Validate signal
        _validate_signal_payload(signal_payload, allow_signal_type=True)

        # Get signal type for display
        signal_type = signal_payload.get("signal_type", "UNKNOWN").upper()
        logger.info(f"{'🔵' if signal_type == 'ENTRY' else '🔴'} [{source_file}] Signal {i}/{len(ordered_signals)} ({signal_type})...")

        # For EXIT signals, resolve variable reference before sending
        resolved_entry_id = None
        if signal_type == "EXIT":
            entry_ref = signal_payload.get("entry_signal_id", "$PREVIOUS")
            if entry_ref and entry_ref.startswith("$"):
                if entry_ref in entry_id_registry:
                    resolved_entry_id = entry_id_registry[entry_ref]
                    logger.info(f"   ✓ Resolved {entry_ref} → {resolved_entry_id[:12]}...")
                elif entry_ref != "$PREVIOUS":
                    logger.info(f"   ⚠️  WARNING: Variable {entry_ref} not found in registry")

        # Send signal
        result = send_signal(signal_payload, signal_type=signal_type.lower(), previous_entry_id=resolved_entry_id)
        signals_sent += 1

        # Capture ENTRY signal_id and register named variable
        if signal_type == "ENTRY" and result and result.get("signal_id"):
            entry_signal_id = result["signal_id"]  # This is the signalID string, NOT MongoDB ObjectId

            # Register named variable if provided (e.g., "$ENTRY_1")
            entry_name = signal_payload.get("entry_name")
            if entry_name:
                entry_id_registry[entry_name] = entry_signal_id
                logger.info(f"   ✓ Registered {entry_name} → {entry_signal_id}")

            # Always keep $PREVIOUS for backward compatibility
            entry_id_registry["$PREVIOUS"] = entry_signal_id

        # Pause and play mode: wait for user input after each signal
        if pause_and_play and i < len(ordered_signals):
            try:
                input(f"   ⏸️  Press ENTER to continue to next signal ({i}/{len(ordered_signals)})...")
            except EOFError:
                # Handle non-interactive mode gracefully
                pass
        else:
            # Wait if specified
            wait_seconds = signal_payload.get("wait", 0)

            # Apply delay override if provided
            if delay_override is not None:
                wait_seconds = delay_override

            if wait_seconds > 0 and i < len(ordered_signals):  # Don't wait after last signal
                print(f"   ⏳ Waiting {wait_seconds} seconds before next signal...")
                time.sleep(wait_seconds)
                total_wait_time += wait_seconds

        print()  # Blank line between signals

    print("\n" + "=" * 80)
    print(f"✅ All {signals_sent} Signals Sent Successfully")
    print("=" * 80)
    if total_wait_time > 0:
        print(f"⏱️  Total wait time: {total_wait_time} seconds")
    print("")

    return signals_sent


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

  4. Send all signals from folder (with reproducible shuffle):
     python send_test_signal.py --folder sample_signals/
     python send_test_signal.py --folder sample_signals/ --seed 42

  5. Send signals with randomized order each run:
     python send_test_signal.py --folder sample_signals/ --seed 0

  6. List available strategies:
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
        "--file", "-f",
        dest="file_path",
        help="Path to JSON signal file (alternative to @filename syntax)"
    )
    parser.add_argument(
        "--folder",
        dest="folder_path",
        help="Path to folder containing JSON signal files (*.json) - all files processed in order"
    )
    parser.add_argument(
        "--seed",
        type=int,
        dest="seed",
        help="Seed for signal shuffling (positive=reproducible, 0=randomized). Overrides SIGNAL_TEST_SEED env var"
    )
    parser.add_argument(
        "--delay",
        type=int,
        dest="delay_override",
        help="Override wait time between signals in seconds (default: use signal's wait value)"
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

    # Handle --folder option
    if args.folder_path:
        # Get seed from CLI override or environment variable
        seed = args.seed
        if seed is None:
            try:
                seed = int(os.getenv('SIGNAL_TEST_SEED', '1'))
            except ValueError:
                seed = 1
        
        process_folder(args.folder_path, seed, delay_override=args.delay_override)
        return

    # Handle --file option
    if args.file_path:
        try:
            with open(args.file_path, 'r') as f:
                json_str = f.read()
        except FileNotFoundError:
            print(f"❌ File not found: {args.file_path}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            sys.exit(1)
    elif args.json_payload:
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
    else:
        parser.error("JSON payload is required (use --file or @filename or pass JSON string)")

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
        entry_id_registry = {}  # Maps variable names (e.g., "$ENTRY_1") to signal_store IDs

        for i, signal_payload in enumerate(payload, 1):
            # Validate signal
            _validate_signal_payload(signal_payload, allow_signal_type=True)

            # Get signal type for display
            signal_type = signal_payload.get("signal_type", "UNKNOWN").upper()
            print(f"\n{'🔵' if signal_type == 'ENTRY' else '🔴'} Sending signal {i}/{len(payload)} ({signal_type})...")

            # For EXIT signals, resolve variable reference before sending
            resolved_entry_id = None
            if signal_type == "EXIT":
                entry_ref = signal_payload.get("entry_signal_id", "$PREVIOUS")
                if entry_ref and entry_ref.startswith("$"):
                    if entry_ref in entry_id_registry:
                        resolved_entry_id = entry_id_registry[entry_ref]
                        print(f"✓ Resolved {entry_ref} → {resolved_entry_id[:12]}...")
                    elif entry_ref != "$PREVIOUS":
                        print(f"⚠️ WARNING: Variable {entry_ref} not found in registry")

            # Send signal (pass signal_type lowercase and resolved_entry_id)
            result = send_signal(signal_payload, signal_type=signal_type.lower(), previous_entry_id=resolved_entry_id)

            # Capture ENTRY signal_id and register named variable
            if signal_type == "ENTRY" and result and result.get("signal_id"):
                entry_signal_id = result["signal_id"]  # This is the signalID string, NOT MongoDB ObjectId

                # Register named variable if provided (e.g., "$ENTRY_1")
                entry_name = signal_payload.get("entry_name")
                if entry_name:
                    entry_id_registry[entry_name] = entry_signal_id
                    print(f"✓ Registered {entry_name} → {entry_signal_id}")

                # Always keep $PREVIOUS for backward compatibility
                entry_id_registry["$PREVIOUS"] = entry_signal_id

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
