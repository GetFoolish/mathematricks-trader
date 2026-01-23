#!/usr/bin/env python3
"""
Archive progressive folder to legacy
Run this script to complete the refactoring
"""
import shutil
from pathlib import Path

project_root = Path(__file__).parent.parent
source = project_root / 'tests' / 'progressive'
dest = project_root / 'tests' / 'legacy' / 'progressive'

if source.exists():
    if dest.exists():
        print(f"⚠️  Destination already exists: {dest}")
        print("   Removing existing destination...")
        shutil.rmtree(dest)
    
    print(f"📦 Moving {source} → {dest}")
    shutil.move(str(source), str(dest))
    print("✅ Progressive folder archived to legacy/")
else:
    print(f"ℹ️  Source folder not found: {source}")
    print("   Already moved or doesn't exist")
