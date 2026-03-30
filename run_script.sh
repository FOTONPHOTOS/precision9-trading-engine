#!/bin/bash
# Generic script to run any Python script in the Arsenal VPS environment

# Check if a script name was provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <script_name.py>"
    echo "Example: $0 helios_server.py"
    exit 1
fi

SCRIPT_NAME=$1
SCRIPT_PATH="/root/Desktop/Arsenal VPS/app/$SCRIPT_NAME"

# Check if the script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script $SCRIPT_PATH does not exist"
    exit 1
fi

echo "Running $SCRIPT_NAME with Arsenal VPS Python environment..."
cd /root/Desktop/Arsenal\ VPS/app
/root/Desktop/Arsenal\ VPS/venv/bin/python "$SCRIPT_NAME"