#!/usr/bin/env python3
"""Quick test to check EXIT signal loading"""

import json
import sys
sys.path.insert(0, 'tests')
from send_test_signal import shuffle_signals

# Load signals
signals = json.load(open('tests/sample_signals/ibkr/tech_stocks_realistic.json'))
source_file = 'tech_stocks_realistic.json'

# Separate ENTRY and EXIT
entry_signals = []
exit_signals_by_entry = {}

for sig in signals:
    signal_type = sig.get('signal_type', 'ENTRY').upper()
    if signal_type == 'ENTRY':
        entry_signals.append((sig, source_file))
    elif signal_type == 'EXIT':
        entry_ref = sig.get('entry_name') or sig.get('entry_signal_id', '$PREVIOUS')
        key = (source_file, entry_ref)
        if key not in exit_signals_by_entry:
            exit_signals_by_entry[key] = []
        exit_signals_by_entry[key].append((sig, source_file))

print(f'✅ Loaded {len(entry_signals)} ENTRYs')
print(f'✅ Loaded {sum(len(v) for v in exit_signals_by_entry.values())} EXITs across {len(exit_signals_by_entry)} groups')
print(f'\n📋 EXIT groups:')
for key, exits in exit_signals_by_entry.items():
    print(f'   {key}: {len(exits)} exit(s)')

# Shuffle with seed=1
ordered = shuffle_signals(entry_signals, exit_signals_by_entry, seed=1)
print(f'\n✅ After shuffle: {len(ordered)} total signals')
print('\n📊 Signal order:')
for i, (sig, src) in enumerate(ordered, 1):
    stype = sig.get('signal_type', 'UNKNOWN')
    entry_name = sig.get('entry_name', 'N/A')
    signal_id = sig.get('signalID', 'N/A')
    print(f'  {i}. {stype:5s} | {entry_name:20s} | {signal_id}')
