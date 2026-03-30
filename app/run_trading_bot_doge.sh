#!/bin/bash
# Script to run Main Trading Bot (for DOGEUSDT symbol) with proper Python environment

echo "Starting Main Trading Bot for DOGEUSDT..."

# Change to the app directory
cd /root/Desktop/Arsenal\ VPS/app

# Run using the specific Python executable from the virtual environment
/root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol DOGEUSDT