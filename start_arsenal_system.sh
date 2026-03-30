#!/bin/bash

# Arsenal VPS Trading System Startup Script
# This script starts all components of the Arsenal trading system

echo " Starting Arsenal VPS Trading System..."

# Navigate to the project directory
cd /root/Desktop/Arsenal\ VPS

# Activate the Python virtual environment
source myenv/bin/activate

echo " Checking environment variables..."
if [ ! -f ".env" ]; then
    echo "  Warning: .env file not found. Please ensure your API keys are configured."
else
    echo " Environment file found"
    source .env
fi

# Start the Helios server (central brain)
echo " Starting Helios server..."
cd app
python helios_server.py > /root/Desktop/Arsenal\ VPS/logs/helios.log 2>&1 &
HELIOS_PID=$!
echo " Helios server started with PID: $HELIOS_PID"

# Start Eyes of Horus (market analysis engine)
echo "  Starting Eyes of Horus..."
sleep 5  # Give Helios time to initialize
python eyes_of_horus/main.py --live > /root/Desktop/Arsenal\ VPS/logs/aegis.log 2>&1 &
AEGIS_PID=$!
echo "  Aegis/Eyes of Horus started with PID: $AEGIS_PID"

# Wait a bit more for initialization
sleep 10

# Start the trading bots for different symbols
SYMBOLS=("ETHUSDT" "BTCUSDT" "SOLUSDT" "XRPUSDT" "BNBUSDT" "LINKUSDT")

for symbol in "${SYMBOLS[@]}"; do
    echo " Starting bot for $symbol..."
    python live_arsenal_horus_integrated.py --live --symbol "$symbol" > /root/Desktop/Arsenal\ VPS/logs/bot_$symbol.log 2>&1 &
    BOT_PID=$!
    echo " Bot for $symbol started with PID: $BOT_PID"
    
    # Wait a bit between starting each bot to avoid conflicts
    sleep 3
done

echo " Arsenal VPS Trading System launched successfully!"
echo ""
echo " Running processes:"
ps aux | grep -E "(helios_server|main\.py|live_arsenal)" | grep -v grep

echo ""
echo " Logs are available in /root/Desktop/Arsenal VPS/logs/"
echo ""
echo " To stop the system: kill $(pgrep -f helios_server), $(pgrep -f main.py), $(pgrep -f live_arsenal_horus_integrated.py)"
echo ""
echo " System is now running live trading operations!"