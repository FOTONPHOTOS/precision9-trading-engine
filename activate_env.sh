#!/bin/bash
# Arsenal VPS Python Environment Setup

echo "=========================================="
echo "Arsenal VPS Trading System Setup"
echo "=========================================="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Navigate to the script directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ -f "myenv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source myenv/bin/activate
    echo "Arsenal VPS environment activated!"
    echo "Python version: $(python --version)"
    echo "To deactivate, run: deactivate"
else
    echo "No virtual environment found."
    echo ""
    echo "To create one, run:"
    echo "  python3 -m venv myenv"
    echo "  source myenv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    echo "Using system Python (python3)"
fi