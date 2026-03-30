#!/bin/bash

# Arsenal VPS Trading System Startup Script (Real-Time Mode)
# This script starts all components of the Arsenal trading system with real-time output

echo "🚀 Starting Arsenal VPS Trading System (Real-Time Mode)..."

# Navigate to the project directory
cd /root/Desktop/Arsenal\ VPS

# Activate the Python virtual environment
source myenv/bin/activate

echo "🔑 Loading environment variables..."
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. Please ensure your API keys are configured."
else
    echo "✅ Environment file found and loaded"
    export $(grep -v '^#' .env | xargs)  # Load environment variables
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo "🧠 Starting Helios server (real-time output)..."
cd app
echo "Starting Helios..." &
python helios_server.py &
HELIOS_PID=$!
echo "🧠 Helios server started with PID: $HELIOS_PID (Following logs with 'tail -f logs/helios.log &')"
# Start Helios in background to allow other components to start

sleep 5  # Give Helios time to initialize

echo "👁️  Starting Eyes of Horus (real-time output)..."
python eyes_of_horus/main.py --live &
AEGIS_PID=$!
echo "👁️  Aegis/Eyes of Horus started with PID: $AEGIS_PID"

# Wait a bit more for initialization
sleep 10

# Start the trading bots for different symbols in the background but monitor them
SYMBOLS=("ETHUSDT" "BTCUSDT" "SOLUSDT" "XRPUSDT" "BNBUSDT" "LINKUSDT")

for symbol in "${SYMBOLS[@]}"; do
    echo "📈 Starting bot for $symbol (real-time output)..."
    python live_arsenal_horus_integrated.py --live --symbol "$symbol" &
    BOT_PID=$!
    echo "📈 Bot for $symbol started with PID: $BOT_PID"
    
    # Wait a bit between starting each bot to avoid conflicts
    sleep 3
done

echo "✅ Arsenal VPS Trading System launched successfully!"
echo ""
echo "📋 Running processes:"
ps aux | grep -E "(helios_server|main\.py|live_arsenal_horus_integrated)" | grep -v grep

echo ""
echo "💡 To view live logs in real-time, use 'tail -f' on the individual log files in /root/Desktop/Arsenal VPS/logs/"
echo ""
echo "🔧 To stop the system, use 'kill' command followed by the PIDs shown above"
echo ""
echo "💡 System is now running live trading operations with real-time feedback!"

# Keep the script running to maintain the processes
echo ""
echo "⏳ Keeping processes alive... Press Ctrl+C to stop all."
wait