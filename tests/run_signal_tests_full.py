#!/usr/bin/env python3
"""
Run signal testing for specific trading mode

This script:
1. Loads all signals from sample_signals/ folder
2. Shuffles them deterministically or randomly based on SIGNAL_TEST_SEED
3. Sends all signals with proper entry/exit pairing
4. Tracks results and generates summary report

Designed for 4-mode testing: mock_mock, mock_live, paper_live, live_live

Usage:
    # Run with specific mode
    python run_signal_tests_full.py --mode mock_mock
    python run_signal_tests_full.py --mode mock_live
    python run_signal_tests_full.py --mode paper_live
    python run_signal_tests_full.py --mode live_live

    # Run with custom seed
    python run_signal_tests_full.py --mode mock_mock --seed 42

    # Run with randomized order each time
    python run_signal_tests_full.py --mode mock_mock --seed 0

    # Run specific folder
    python run_signal_tests_full.py --mode mock_mock --folder sample_signals/

    # Pause after each signal (interactive mode)
    python run_signal_tests_full.py --mode mock_mock --pause-and-play
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


def run_test(mode: str, folder_path: str = "sample_signals", seed: int = None, delay: int = None,
             output_dir: str = None, signal_count: int = None, pause_and_play: bool = False,
             file_filter: str = None, environment: str = 'staging', account_type: str = None, deployment_target: str = 'cloud'):
    """
    Run signal test suite from a signal folder for a specific mode

    Args:
        mode: Trading mode (mock_mock, mock_live, paper_live, live_live)
        folder_path: Path to folder containing signal JSON files
        seed: Random seed (None=use SIGNAL_TEST_SEED from .env)
        delay: Delay between signals in seconds (None=use signal's wait value)
        output_dir: Directory to save test results
        signal_count: Limit number of total signals to process (None = all)
        pause_and_play: If True, pause after each signal and wait for Enter key
        file_filter: Filter to specific JSON file name (e.g., 'tech_stocks_realistic.json')
    """
    # Validate mode
    valid_modes = ["mock_mock", "mock_live", "paper_live", "live_live"]
    if mode not in valid_modes:
        print(f"❌ Invalid mode: {mode}")
        print(f"   Valid modes: {', '.join(valid_modes)}")
        sys.exit(1)

    # Create output directory
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for this test run
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    run_id = f"signal_test_{mode}_{timestamp}"
    
    print("\n" + "=" * 80)
    print(f"🚀 SIGNAL TESTING - {mode.upper()}")
    print("=" * 80)
    print(f"🔧 Mode:           {mode}")
    print(f"📁 Signal Folder:  {folder_path}")
    if file_filter:
        print(f"📄 File Filter:    {file_filter}")
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
        print(f"📊 Signal Count:   {signal_count} total signals")

    if pause_and_play:
        print(f"⏸️  Pause Mode:     Enabled (press Enter after each signal)")

    print("=" * 80 + "\n")
    
    # Run send_test_signal.process_folder directly
    start_time = time.time()
    try:
        # Call the function directly instead of subprocess
        signals_sent = send_test_signal.process_folder(folder_path, seed, delay_override=delay,
                                                       signal_count=signal_count, pause_and_play=pause_and_play,
                                                       mode=mode, file_filter=file_filter,
                                                       environment=environment, account_type=account_type,
                                                       deployment_target=deployment_target)

        elapsed = time.time() - start_time

        # Build test results
        test_results = {
            "run_id": run_id,
            "mode": mode,
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

        print(f"\n✅ Signal testing for {mode} completed successfully")
        print(f"\n📊 Results Summary:")
        print(f"   Mode:         {mode}")
        print(f"   Signals Sent: {signals_sent}")
        print(f"   Duration:     {elapsed:.2f} seconds")
        
    except Exception as e:
        test_results = {
            "run_id": run_id,
            "mode": mode,
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
        print(f"\n❌ Error running signal testing for {mode}: {e}")
        import traceback
        traceback.print_exc()

    # Save test results JSON
    if output_dir:
        results_file = os.path.join(output_dir, f"{run_id}_results.json")
        with open(results_file, 'w') as f:
            json.dump(test_results, f, indent=2)

        print(f"\n📄 Results saved to: {results_file}")

    # Print summary
    print("\n" + "=" * 80)
    print(f"✅ {mode.upper()} Test Complete")
    print("=" * 80)
    print(f"Status:        {test_results['status'].upper()}")
    print(f"Signals Sent:  {test_results.get('signals_sent', 'N/A')}")
    print(f"Duration:      {test_results['duration_seconds']:.2f}s")
    print("=" * 80 + "\n")
    
    # Return exit code based on test status
    return 0 if test_results["status"] == "success" else 1


def main():
    parser = argparse.ArgumentParser(
        description="Run signal testing suite for a specific trading mode",
        epilog="""
Examples:

  1. Run mock_mock mode with default settings:
     python run_signal_tests_full.py --mode mock_mock
  
  2. Run mock_live with specific seed:
     python run_signal_tests_full.py --mode mock_live --seed 42
  
  3. Run paper_live with randomized order:
     python run_signal_tests_full.py --mode paper_live --seed 0
  
  4. Run live_live with pause-and-play:
     python run_signal_tests_full.py --mode live_live --pause-and-play

Trading Modes:
  - mock_mock:   Mock account, mock market data
  - mock_live:   Mock account, live market data
  - paper_live:  Paper account, live market data
  - live_live:   Live account, live market data

Test Results:
  - Saved to test_results/ folder
  - Contains results.json with structured test results
  - Run ID includes mode and timestamp for easy identification
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--mode",
        required=True,
        choices=["mock_mock", "mock_live", "paper_live", "live_live"],
        help="Trading mode to test"
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
        default="./test_results",
        help="Directory to save test results (default: ./test_results)"
    )

    parser.add_argument(
        "--signal-count",
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

    parser.add_argument(
        "--file",
        dest="file_filter",
        help="Filter to specific JSON file name (e.g., 'tech_stocks_realistic.json')"
    )

    parser.add_argument(
        "--environment",
        choices=["staging", "live"],
        default="staging",
        help="Environment for execution (staging=mock/paper, live=real money)"
    )

    parser.add_argument(
        "--account-type",
        dest="account_type",
        choices=["mock", "paper", "live"],
        help="Account type for execution (overrides defaults)"
    )

    parser.add_argument(
        "--deployment-target",
        dest="deployment_target",
        choices=["local", "cloud"],
        default="cloud",
        help="Where to send signals (local=localhost:3000, cloud=mathematricks.fund)"
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
        mode=args.mode,
        folder_path=args.folder_path,
        seed=args.seed,
        delay=delay,
        output_dir=args.output_dir,
        signal_count=args.signal_count,
        pause_and_play=args.pause_and_play,
        file_filter=args.file_filter,
        environment=args.environment,
        account_type=args.account_type,
        deployment_target=args.deployment_target
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
