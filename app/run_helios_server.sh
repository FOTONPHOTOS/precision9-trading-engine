#!/bin/bash
# Script to run Helios Server (Central Intelligence Hub) with proper Python environment

echo "Starting Helios Server (Central Intelligence Hub)..."

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
python3 helios_server.py