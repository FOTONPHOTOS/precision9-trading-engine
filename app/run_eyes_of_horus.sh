#!/bin/bash
# Script to run Eyes of Horus (Aegis - Market Analysis Engine) with proper Python environment

echo "Starting Eyes of Horus (Aegis - Market Analysis Engine)..."

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

# Add current directory to PYTHONPATH so Python can find local modules
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Run using python3 (system Python or venv)
python3 eyes_of_horus/main.py --live