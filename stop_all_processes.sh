#!/bin/bash
# Script to stop all running Arsenal VPS processes

echo "Stopping all Arsenal VPS processes..."

# Kill processes related to Arsenal
pkill -f 'helios_server' 2>/dev/null
pkill -f 'eyes_of_horus/main.py' 2>/dev/null
pkill -f 'live_arsenal_horus_integrated' 2>/dev/null

echo "All Arsenal VPS processes have been stopped."