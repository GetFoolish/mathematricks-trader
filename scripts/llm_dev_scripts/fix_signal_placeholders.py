#!/usr/bin/env python3
"""
Fix signal placeholder names to be unique across files

Changes:
- com1_met_realistic.json: $ENTRY_1 → $COM1_MET_1, etc.
- com2_ag_realistic.json: $ENTRY_1 → $COM2_AG_1, etc.
- florida_forex_realistic.json: $ENTRY_1 → $FLORIDA_FOREX_1, etc.
etc.

Usage:
    python scripts/junk/fix_signal_placeholders.py
"""

import json
import os
import re
from pathlib import Path

# Mapping of file names to their unique prefixes
FILE_PREFIX_MAP = {
    "com1_met_realistic.json": "COM1_MET",
    "com2_ag_realistic.json": "COM2_AG",
    "com3_mkt_realistic.json": "COM3_MKT",
    "com4_misc_realistic.json": "COM4_MISC",
    "florida_forex_realistic.json": "FLORIDA_FOREX",
    "spx_0de_opt_realistic.json": "SPX_0DE_OPT",
    "spx_1d_opt_realistic.json": "SPX_1D_OPT",
    "spy_realistic.json": "SPY",
    "tlt_realistic.json": "TLT",
}


def fix_signal_file(file_path: Path, prefix: str):
    """
    Update a signal file to use unique placeholder names

    Args:
        file_path: Path to the JSON signal file
        prefix: Unique prefix for this file (e.g., "COM1_MET")
    """
    print(f"\n📝 Processing {file_path.name}...")

    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()

    # Track replacements
    replacements = []

    # Replace all $ENTRY_N patterns with ${PREFIX}_N
    def replace_entry(match):
        number = match.group(1)
        old = match.group(0)
        new = f"${prefix}_{number}"
        if (old, new) not in replacements:
            replacements.append((old, new))
        return new

    # Replace in entry_name and entry_signal_id fields
    new_content = re.sub(r'\$ENTRY_(\d+)', replace_entry, content)

    # Write back
    with open(file_path, 'w') as f:
        f.write(new_content)

    # Report
    if replacements:
        print(f"  ✓ Made {len(replacements)} unique replacements:")
        for old, new in replacements:
            print(f"    {old} → {new}")
    else:
        print(f"  ℹ️  No changes needed")

    return len(replacements)


def main():
    """Fix all signal files"""
    signals_dir = Path("tests/signals_testing/sample_signals")

    if not signals_dir.exists():
        print(f"❌ Directory not found: {signals_dir}")
        return

    print("=" * 80)
    print("🔧 FIXING SIGNAL PLACEHOLDER NAMES")
    print("=" * 80)
    print(f"📁 Directory: {signals_dir}")
    print(f"📊 Files to process: {len(FILE_PREFIX_MAP)}")
    print("=" * 80)

    total_replacements = 0

    for filename, prefix in FILE_PREFIX_MAP.items():
        file_path = signals_dir / filename
        if not file_path.exists():
            print(f"\n⚠️  File not found: {filename}")
            continue

        replacements = fix_signal_file(file_path, prefix)
        total_replacements += replacements

    print("\n" + "=" * 80)
    print(f"✅ Done! Total replacements: {total_replacements}")
    print("=" * 80)
    print("\n💡 Next steps:")
    print("   1. Review the changes: git diff tests/signals_testing/sample_signals/")
    print("   2. Test: python tests/signals_testing/run_full_test.py")
    print("")


if __name__ == "__main__":
    main()
