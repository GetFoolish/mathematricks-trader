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
"""

import argparse
import json
import os
import sys
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def run_test(folder_path: str = "sample_signals", seed: int = None, output_dir: str = "test_results"):
    """
    Run full test suite from a signal folder
    
    Args:
        folder_path: Path to folder containing signal JSON files
        seed: Random seed (None=use SIGNAL_TEST_SEED from .env)
        output_dir: Directory to save test results
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
    print("=" * 80 + "\n")
    
    # Build send_test_signal.py command
    script_dir = os.path.dirname(os.path.abspath(__file__))
    send_script = os.path.join(script_dir, "send_test_signal.py")
    
    if not os.path.exists(send_script):
        print(f"❌ Error: send_test_signal.py not found at {send_script}")
        sys.exit(1)
    
    # Run send_test_signal.py with folder and seed
    cmd = [
        sys.executable,
        send_script,
        "--folder", folder_path,
        "--seed", str(seed)
    ]
    
    print(f"📡 Running: {' '.join(cmd)}\n")
    
    # Capture results
    test_results = {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "folder": folder_path,
        "seed": seed,
        "command": " ".join(cmd),
        "status": "running",
        "signals_sent": 0,
        "signals_failed": 0,
        "duration_seconds": 0,
        "start_time": now.isoformat()
    }
    
    # Execute send_test_signal.py
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        elapsed = time.time() - start_time
        test_results["duration_seconds"] = elapsed
        test_results["end_time"] = datetime.now(timezone.utc).isoformat()
        
        # Process output
        stdout = result.stdout
        stderr = result.stderr
        
        # Save raw output
        with open(os.path.join(output_dir, f"{run_id}_output.txt"), 'w') as f:
            f.write("=== STDOUT ===\n")
            f.write(stdout)
            f.write("\n\n=== STDERR ===\n")
            f.write(stderr)
        
        # Parse results from output
        # Count successful signals (look for "✅ Test Signal Inserted")
        success_count = stdout.count("✅ Test Signal Inserted Successfully")
        test_results["signals_sent"] = success_count
        
        if result.returncode == 0:
            test_results["status"] = "success"
            print(f"\n✅ Test suite completed successfully")
        else:
            test_results["status"] = "failed"
            print(f"\n❌ Test suite failed with exit code {result.returncode}")
            if stderr:
                print(f"\nErrors:\n{stderr}")
        
        # Print summary from output
        print(f"\n📊 Results Summary:")
        print(f"   Signals sent: {test_results['signals_sent']}")
        print(f"   Duration:     {test_results['duration_seconds']:.2f} seconds")
        
    except subprocess.TimeoutExpired:
        test_results["status"] = "timeout"
        test_results["error"] = "Test suite timeout (10 minutes)"
        print(f"\n❌ Test suite timed out after 10 minutes")
    except Exception as e:
        test_results["status"] = "error"
        test_results["error"] = str(e)
        print(f"\n❌ Error running test suite: {e}")
    
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
    print(f"Signals Sent:  {test_results['signals_sent']}")
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

Test Results:
  - Saved to test_results/ folder
  - Contains output.txt (raw command output) and results.json (structured results)
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
        "--output-dir",
        dest="output_dir",
        default="test_results",
        help="Directory to save test results (default: test_results)"
    )
    
    args = parser.parse_args()
    
    # Validate folder exists
    if not os.path.isdir(args.folder_path):
        print(f"❌ Folder not found: {args.folder_path}")
        sys.exit(1)
    
    # Run test
    exit_code = run_test(
        folder_path=args.folder_path,
        seed=args.seed,
        output_dir=args.output_dir
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
