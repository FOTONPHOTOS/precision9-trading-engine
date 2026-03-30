#!/bin/bash
# Script to check running Arsenal VPS processes

echo "Checking running Arsenal VPS processes..."

# Check for running Python processes related to Arsenal
ps aux | grep -E "(helios_server|eyes_of_horus|live_arsenal_horus_integrated)" | grep -v grep

echo ""
echo "To kill all Arsenal processes, run:"
echo "pkill -f 'helios_server\|eyes_of_horus/main.py\|live_arsenal_horus_integrated'"