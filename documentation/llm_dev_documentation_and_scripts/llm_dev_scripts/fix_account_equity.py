#!/usr/bin/env python3
"""
Fix account_equity in all signal files to ensure position size is 3-15% of account equity.
"""
import json
import os
import random
from pathlib import Path

# Directories to process
SIGNAL_DIRS = [
    "tests/signals_testing/sample_signals",
    "tests/signals_testing/sample_signals_edgecases",
    "tests/signals_testing/sample_signals_old"
]

def calculate_position_size(signal_legs):
    """Calculate total position size in dollars from signal legs."""
    total_size = 0
    for leg in signal_legs:
        quantity = leg.get('quantity', 0)
        price = leg.get('price', 0)
        
        # For forex, the notional value is quantity * price
        # For stocks/options, it's also quantity * price
        leg_size = abs(quantity * price)
        total_size += leg_size
    
    return total_size

def set_account_equity(signal):
    """Set account_equity based on position size being 3-15% of equity."""
    if 'signal_legs' not in signal or not signal['signal_legs']:
        # If no signal legs, use a default
        signal['account_equity'] = 500000
        return
    
    position_size = calculate_position_size(signal['signal_legs'])
    
    if position_size == 0:
        # If position size is 0, set a default
        signal['account_equity'] = 500000
        return
    
    # Random percentage between 3% and 15%
    position_pct = random.uniform(0.03, 0.15)
    
    # Calculate account equity: position_size / percentage
    account_equity = position_size / position_pct
    
    # Round to nearest 1000 for cleaner numbers
    account_equity = round(account_equity / 1000) * 1000
    
    # Ensure minimum of 10,000
    account_equity = max(10000, account_equity)
    
    signal['account_equity'] = account_equity
    
    # Print for verification
    print(f"  Signal: {signal.get('signalID', signal.get('entry_name', 'unknown'))}")
    print(f"    Position size: ${position_size:,.2f}")
    print(f"    Account equity: ${account_equity:,.0f}")
    print(f"    Position %: {(position_size / account_equity * 100):.2f}%")

def process_json_file(file_path):
    """Process a single JSON file."""
    print(f"\nProcessing: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            signals = json.load(f)
        
        # Handle both single signal and array of signals
        if isinstance(signals, dict):
            signals = [signals]
        
        # Set seed for reproducibility per file
        random.seed(hash(file_path.name))
        
        # Process each signal
        for signal in signals:
            set_account_equity(signal)
        
        # Write back to file
        with open(file_path, 'w') as f:
            json.dump(signals, f, indent=2)
        
        print(f"✅ Updated {file_path}")
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")

def main():
    """Process all JSON files in the signal directories."""
    print("=" * 80)
    print("Fixing account_equity in all signal files")
    print("=" * 80)
    
    total_files = 0
    
    for signal_dir in SIGNAL_DIRS:
        dir_path = Path(signal_dir)
        
        if not dir_path.exists():
            print(f"⚠️  Directory not found: {signal_dir}")
            continue
        
        # Find all JSON files
        json_files = sorted(dir_path.glob("*.json"))
        
        print(f"\n📁 Processing directory: {signal_dir}")
        print(f"   Found {len(json_files)} JSON files")
        
        for json_file in json_files:
            process_json_file(json_file)
            total_files += 1
    
    print("\n" + "=" * 80)
    print(f"✅ Completed! Processed {total_files} files")
    print("=" * 80)

if __name__ == "__main__":
    main()
