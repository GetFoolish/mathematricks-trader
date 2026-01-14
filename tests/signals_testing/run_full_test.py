#!/usr/bin/env python3
"""
Run full testing suite for all realistic signals

This script:
1. Loads all signals from sample_signals/ folder
2. Shuffles them deterministically or randomly based on SIGNAL_TEST_SEED
3. Sends all signals with proper entry/exit pairing
4. Tracks results and generates summary report
5. Exports detailed results to JSON

Usage:
    # Run with reproducible seed (from .env)
    python run_full_test.py

    # Run with custom seed
    python run_full_test.py --seed 42

    # Run with randomized order each time
    python run_full_test.py --seed 0

    # Run only edge cases
    python run_full_test.py --folder sample_signals_edgecases/

    # Run specific folder with seed
    python run_full_test.py --folder sample_signals/ --seed 123

    # Run only first 5 ENTRY signals (+ their EXITs)
    python run_full_test.py --signal_count 5

    # Pause after each signal (interactive mode)
    python run_full_test.py --pause-and-play

    # Combine options: 3 signals, interactive, custom delay
    python run_full_test.py --signal_count 3 --pause-and-play --delay 2
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add current directory to path to import send_test_signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import send_test_signal


def run_test(folder_path: str = "sample_signals", seed: int = None, delay: int = None,
             output_dir: str = "../../test_results", signal_count: int = None, pause_and_play: bool = False):
    """
    Run full test suite from a signal folder

    Args:
        folder_path: Path to folder containing signal JSON files
        seed: Random seed (None=use SIGNAL_TEST_SEED from .env)
        delay: Delay between signals in seconds (None=use signal's wait value)
        output_dir: Directory to save test results
        signal_count: Limit number of ENTRY signals to process (None = all)
        pause_and_play: If True, pause after each signal and wait for Enter key
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for this test run
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    run_id = f"test_run_{timestamp}"
    
    print("\n" + "=" * 80)
    print(f"🚀 MATHEMATRICKS TRADER - FULL TEST SUITE")
    print("=" * 80)
    print(f"📁 Signal Folder:  {folder_path}")
    print(f"🆔 Run ID:         {run_id}")
    print(f"⏰ Started:        {now.isoformat()}")
    
    # Determine seed
    if seed is None:
        try:
            seed = int(os.getenv('SIGNAL_TEST_SEED', '1'))
        except ValueError:
            seed = 1
    
    print(f"🔀 Seed:           {seed} ({'reproducible' if seed > 0 else 'randomized' if seed == 0 else 'ordered'})")

    if delay is not None:
        print(f"⏱️  Delay:          {delay} seconds between signals")

    if signal_count is not None:
        print(f"📊 Signal Count:   {signal_count} ENTRY signals (+ their EXITs)")

    if pause_and_play:
        print(f"⏸️  Pause Mode:     Enabled (press Enter after each signal)")

    print("=" * 80 + "\n")
    
    # Run send_test_signal.process_folder directly
    start_time = time.time()
    try:
        # Call the function directly instead of subprocess
        signals_sent = send_test_signal.process_folder(folder_path, seed, delay_override=delay,
                                                       signal_count=signal_count, pause_and_play=pause_and_play)

        elapsed = time.time() - start_time

        # Build test results
        test_results = {
            "run_id": run_id,
            "timestamp": now.isoformat(),
            "folder": folder_path,
            "seed": seed,
            "delay": delay,
            "status": "success",
            "signals_sent": signals_sent,
            "duration_seconds": elapsed,
            "start_time": now.isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat()
        }

        print(f"\n✅ Test suite completed successfully")
        print(f"\n📊 Results Summary:")
        print(f"   Duration:     {elapsed:.2f} seconds")
        
    except Exception as e:
        test_results = {
            "run_id": run_id,
            "timestamp": now.isoformat(),
            "folder": folder_path,
            "seed": seed,
            "delay": delay,
            "status": "error",
            "signals_sent": 0,
            "error": str(e),
            "duration_seconds": time.time() - start_time,
            "start_time": now.isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat()
        }
        print(f"\n❌ Error running test suite: {e}")
        import traceback
        traceback.print_exc()

    # Save test results JSON
    results_file = os.path.join(output_dir, f"{run_id}_results.json")
    with open(results_file, 'w') as f:
        json.dump(test_results, f, indent=2)

    print(f"\n📄 Results saved to: {results_file}")

    # Print summary
    print("\n" + "=" * 80)
    print(f"✅ Test Run Complete")
    print("=" * 80)
    print(f"Status:        {test_results['status'].upper()}")
    print(f"Signals Sent:  {test_results.get('signals_sent', 'N/A')}")
    print(f"Duration:      {test_results['duration_seconds']:.2f}s")
    print(f"Results File:  {results_file}")
    print("=" * 80 + "\n")
    
    # Return exit code based on test status
    return 0 if test_results["status"] == "success" else 1


def main():
    parser = argparse.ArgumentParser(
        description="Run full testing suite for all signal files",
        epilog="""
Examples:

  1. Run realistic signals with default seed (from .env):
     python run_full_test.py
  
  2. Run realistic signals with specific reproducible seed:
     python run_full_test.py --seed 42
  
  3. Run with randomized order each time:
     python run_full_test.py --seed 0
  
  4. Run only edge-case signals:
     python run_full_test.py --folder sample_signals_edgecases/
  
  5. Run both realistic and edge cases (separate runs):
     python run_full_test.py --folder sample_signals/
     python run_full_test.py --folder sample_signals_edgecases/

  6. Clear test data and run full test with custom settings:
     .venv/bin/python scripts/junk/clear_test_data.py && .venv/bin/python tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals --delay 10 --signal_count 30 --pause-and-play

Test Results:
  - Saved to test_results/ folder at project root (not in tests/signals_testing/)
  - Contains results.json with structured test results
  - Run ID includes timestamp for easy identification
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--folder",
        dest="folder_path",
        default="sample_signals",
        help="Path to folder containing signal JSON files (default: sample_signals)"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        dest="seed",
        help="Seed for shuffling (positive=reproducible, 0=randomized). Overrides SIGNAL_TEST_SEED env var"
    )
    
    parser.add_argument(
        "--delay",
        type=int,
        dest="delay",
        default=6,
        help="Delay between signals in seconds (default: 6). Use 0 for signal's wait value"
    )
    
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default="../../test_results",
        help="Directory to save test results (default: ../../test_results - project root)"
    )

    parser.add_argument(
        "--signal_count",
        type=int,
        dest="signal_count",
        help="Limit total number of signals to send (ENTRY + EXIT combined)"
    )

    parser.add_argument(
        "--pause-and-play",
        action="store_true",
        dest="pause_and_play",
        help="Pause after each signal and wait for Enter key before continuing"
    )

    args = parser.parse_args()
    
    # Validate folder exists
    if not os.path.isdir(args.folder_path):
        print(f"❌ Folder not found: {args.folder_path}")
        sys.exit(1)
    
    # Convert delay=0 to None (use signal's wait value)
    delay = None if args.delay == 0 else args.delay
    
    # Run test
    exit_code = run_test(
        folder_path=args.folder_path,
        seed=args.seed,
        delay=delay,
        output_dir=args.output_dir,
        signal_count=args.signal_count,
        pause_and_play=args.pause_and_play
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
