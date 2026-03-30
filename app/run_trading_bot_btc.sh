#!/bin/bash
# Script to run Main Trading Bot (for BTCUSDT symbol) with proper Python environment

echo "Starting Main Trading Bot for BTCUSDT..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the app directory
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -f "../myenv/bin/activate" ]; then
    source ../myenv/bin/activate
    echo "Virtual environment activated."
else
    echo "Warning: No virtual environment found. Using system Python."
fi

# Add current directory and libs to PYTHONPATH so Python can find local modules
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/libs/smart-money-concepts:$PYTHONPATH"

# Run using python3 (system Python or venv)
python3 live_arsenal_horus_integrated.py --live --symbol BTCUSDT