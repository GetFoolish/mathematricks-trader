#!/usr/bin/env python3
"""
Progressive 4-Mode Signal Testing Framework

Tests signals progressively through all 4 modes:
1. mock_mock → Fast validation (seconds)
2. mock_live → Data quality check (1-2 min)
3. paper_live → Real IBKR paper account (5-10 min)
4. live_live → Production (requires manual approval)

Usage:
    python tests/signal_testing_v2/run_all_modes.py --all
    python tests/signal_testing_v2/run_all_modes.py --mode mock_mock
    python tests/signal_testing_v2/run_all_modes.py --up-to paper_live
    python tests/signal_testing_v2/run_all_modes.py --test signals/basic/simple_entry_exit.json --mode mock_mock
    python tests/signal_testing_v2/run_all_modes.py --category basic --mode mock_live
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import subprocess
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import from relative path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from test_framework import (
    SignalTestRunner,
    TestResult,
    ModeConfig,
    get_mode_config
)


class ProgressiveTestRunner:
    """Runs signal tests progressively through multiple modes"""
    
    MODES_IN_ORDER = ['mock_mock', 'mock_live', 'paper_live', 'live_live']
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.signal_dir = Path(__file__).parent / "signals"
    
    def run_all_modes(
        self, 
        signal_file: Optional[Path] = None,
        category: Optional[str] = None,
        up_to_mode: Optional[str] = None,
        single_mode: Optional[str] = None
    ):
        """
        Run tests through multiple modes progressively
        
        Args:
            signal_file: Specific signal file to test
            category: Test category (basic, edge_cases, etc.)
            up_to_mode: Stop after this mode (e.g., 'paper_live')
            single_mode: Run only this mode
        """
        print("="*80)
        print("🧪 Progressive 4-Mode Signal Testing Framework")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Determine which modes to run
        if single_mode:
            if single_mode not in self.MODES_IN_ORDER:
                print(f"❌ Invalid mode: {single_mode}. Valid modes: {', '.join(self.MODES_IN_ORDER)}")
                return False
            modes_to_run = [single_mode]
        elif up_to_mode:
            if up_to_mode not in self.MODES_IN_ORDER:
                print(f"❌ Invalid mode: {up_to_mode}. Valid modes: {', '.join(self.MODES_IN_ORDER)}")
                return False
            idx = self.MODES_IN_ORDER.index(up_to_mode)
            modes_to_run = self.MODES_IN_ORDER[:idx+1]
        else:
            modes_to_run = self.MODES_IN_ORDER
        
        print(f"\n📋 Test Plan: {' → '.join(modes_to_run)}")
        
        # Get test files
        if signal_file:
            test_files = [signal_file]
        elif category:
            category_path = self.signal_dir / category
            if not category_path.exists():
                print(f"❌ Category not found: {category}")
                return False
            test_files = list(category_path.glob("*.json"))
        else:
            # Run all signal files
            test_files = list(self.signal_dir.rglob("*.json"))
        
        print(f"📊 Found {len(test_files)} test signal(s)")
        
        # Run tests for each mode
        all_passed = True
        for mode in modes_to_run:
            print(f"\n{'='*80}")
            print(f"🚀 Running tests in {mode.upper()} mode")
            print(f"{'='*80}")
            
            mode_config = get_mode_config(mode)
            runner = SignalTestRunner(mode_config)
            
            mode_passed = True
            for test_file in test_files:
                print(f"\n📝 Testing: {test_file.relative_to(self.signal_dir)}")
                
                result = runner.run_test(test_file)
                self.results.append(result)
                
                if result.success:
                    print(f"   ✅ {mode}: PASSED in {result.duration:.2f}s")
                else:
                    print(f"   ❌ {mode}: FAILED - {result.error}")
                    mode_passed = False
                    all_passed = False
            
            if not mode_passed:
                print(f"\n⚠️  {mode} mode had failures. Stopping progressive testing.")
                break
            
            # Pause between modes (except last)
            if mode != modes_to_run[-1]:
                print(f"\n⏸️  Pausing 3 seconds before next mode...")
                time.sleep(3)
        
        # Print summary
        self._print_summary(modes_to_run)
        
        return all_passed
    
    def _print_summary(self, modes_run: List[str]):
        """Print test execution summary"""
        print("\n" + "="*80)
        print("📊 TEST EXECUTION SUMMARY")
        print("="*80)
        
        # Group results by mode
        results_by_mode = {}
        for result in self.results:
            if result.mode not in results_by_mode:
                results_by_mode[result.mode] = []
            results_by_mode[result.mode].append(result)
        
        # Print results for each mode
        total_tests = len(self.results)
        total_passed = sum(1 for r in self.results if r.success)
        
        for mode in modes_run:
            if mode not in results_by_mode:
                continue
            
            mode_results = results_by_mode[mode]
            passed = sum(1 for r in mode_results if r.success)
            total = len(mode_results)
            
            status = "✅" if passed == total else "❌"
            print(f"\n{status} {mode.upper()}: {passed}/{total} passed")
            
            # Show failures
            failures = [r for r in mode_results if not r.success]
            if failures:
                print(f"   Failures:")
                for f in failures:
                    print(f"      - {f.test_name}: {f.error}")
        
        print(f"\n{'='*80}")
        print(f"Total: {total_passed}/{total_tests} tests passed")
        
        if total_passed == total_tests:
            print("✅ All tests passed!")
        else:
            print(f"❌ {total_tests - total_passed} test(s) failed")
        
        print("="*80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Progressive 4-mode signal testing framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests through all modes
  python run_all_modes.py --all

  # Run only mock_mock mode
  python run_all_modes.py --mode mock_mock

  # Run up to paper_live (skip live_live)
  python run_all_modes.py --up-to paper_live

  # Run specific test in all modes
  python run_all_modes.py --test signals/basic/simple_entry_exit.json --all

  # Run category in specific mode
  python run_all_modes.py --category basic --mode mock_live
        """
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all tests through all modes'
    )
    
    parser.add_argument(
        '--mode',
        choices=['mock_mock', 'mock_live', 'paper_live', 'live_live'],
        help='Run tests in only this mode'
    )
    
    parser.add_argument(
        '--up-to',
        choices=['mock_mock', 'mock_live', 'paper_live', 'live_live'],
        help='Run tests up to and including this mode'
    )
    
    parser.add_argument(
        '--test',
        type=Path,
        help='Specific signal file to test (relative to signals/)'
    )
    
    parser.add_argument(
        '--category',
        choices=['basic', 'edge_cases', 'multi_leg', 'position_management', 'risk', 'real_world', 'data_quality', 'stress'],
        help='Test category to run'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.mode and args.up_to:
        print("❌ Cannot use both --mode and --up-to")
        sys.exit(1)
    
    if not (args.all or args.mode or args.up_to):
        print("❌ Must specify --all, --mode, or --up-to")
        parser.print_help()
        sys.exit(1)
    
    # Run tests
    runner = ProgressiveTestRunner()
    
    success = runner.run_all_modes(
        signal_file=args.test,
        category=args.category,
        up_to_mode=args.up_to,
        single_mode=args.mode
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
