#!/usr/bin/env python3
"""
Test script to verify installation and dependencies
"""

import sys
import importlib
from pathlib import Path

print("="*60)
print("SOL Market Data Tool - Installation Test")
print("="*60)
print()

# Check Python version
print(f"Python Version: {sys.version}")
if sys.version_info < (3, 8):
    print(" ERROR: Python 3.8 or higher required")
    sys.exit(1)
else:
    print(" Python version OK")
print()

# Check required packages
packages = {
    'numpy': 'numpy',
    'pandas': 'pandas',
    'redis': 'redis (optional)',
    'matplotlib': 'matplotlib',
    'sklearn': 'scikit-learn',
    'scipy': 'scipy'
}

print("Checking dependencies:")
print("-"*30)

missing = []
for module, name in packages.items():
    try:
        importlib.import_module(module)
        print(f" {name}")
    except ImportError:
        print(f" {name} - NOT INSTALLED")
        if 'optional' not in name:
            missing.append(module)

print()

# Check directories
print("Checking directories:")
print("-"*30)

dirs = ['sol_training_data', 'logs']
for dir_name in dirs:
    dir_path = Path(dir_name)
    if dir_path.exists():
        print(f" {dir_name}/ exists")
    else:
        dir_path.mkdir(exist_ok=True)
        print(f" {dir_name}/ created")

print()

# Check files
print("Checking files:")
print("-"*30)

files = [
    'collector.py',
    'collector_standalone.py',
    'analyzer.py',
    'config.py',
    'requirements.txt',
    'README.md'
]

for file_name in files:
    if Path(file_name).exists():
        print(f" {file_name}")
    else:
        print(f" {file_name} - NOT FOUND")

print()

# Test imports
print("Testing imports:")
print("-"*30)

try:
    from config import COLLECTION_CONFIG
    print(f" Config loaded - Symbol: {COLLECTION_CONFIG.get('symbol', 'SOLUSDT')}")
except Exception as e:
    print(f" Config import failed: {e}")

print()

# Summary
print("="*60)
if missing:
    print(" INSTALLATION INCOMPLETE")
    print(f"Missing packages: {', '.join(missing)}")
    print("\nTo fix, run:")
    print("  pip install -r requirements.txt")
else:
    print(" INSTALLATION COMPLETE")
    print("\nYou can now:")
    print("  1. Start collector: python collector_standalone.py")
    print("  2. Or use launcher: ./launch.sh start")
    
print("="*60)