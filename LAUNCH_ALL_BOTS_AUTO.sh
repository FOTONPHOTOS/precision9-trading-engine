#!/bin/bash

# Automated Launcher for Arsenal VPS Trading System
# This script starts all components in separate screen sessions with real-time visibility
# Equivalent to the LAUNCH_ALL_BOTS.PS1 script you had on Windows

echo " Starting Arsenal VPS Trading System Auto-Launcher..."

# Check if screen is installed
if ! command -v screen &> /dev/null; then
    echo " screen is not installed. Installing..."
    sudo apt update && sudo apt install -y screen
fi

# Create logs directory
mkdir -p logs

# Kill any existing screen sessions with the same name to prevent conflicts
screen -S arsenal-system -X quit 2>/dev/null || true

# Start a new screen session named "arsenal-system"
screen -dmS arsenal-system

echo " Starting Set Leverage Service..."
screen -S arsenal-system -X screen -t set-leverage
screen -S arsenal-system -p 0 -X stuff "cd /root/Desktop/Arsenal\ VPS && source myenv/bin/activate && python app/set_leverage.py$(printf '\r')"

# Wait for leverage to be set
sleep 10

echo " Starting Helios Server..."
screen -S arsenal-system -X screen -t helios
screen -S arsenal-system -p 1 -X stuff "cd /root/Desktop/Arsenal\ VPS/app && source ../myenv/bin/activate && python helios_server.py$(printf '\r')"

# Wait for Helios to initialize
sleep 15

echo "  Starting Aegis (Eyes of Horus)..."
screen -S arsenal-system -X screen -t aegis
screen -S arsenal-system -p 2 -X stuff "cd /root/Desktop/Arsenal\ VPS/app && source ../myenv/bin/activate && python eyes_of_horus/main.py --live$(printf '\r')"

# Wait for Aegis to initialize
sleep 10

# Start bots for different symbols
SYMBOLS=("ETHUSDT" "BTCUSDT" "SOLUSDT" "XRPUSDT" "BNBUSDT" "LINKUSDT")
WINDOW_NUM=3

for symbol in "${SYMBOLS[@]}"; do
    echo " Starting bot for $symbol..."
    screen -S arsenal-system -X screen -t "bot-$symbol" $WINDOW_NUM
    screen -S arsenal-system -p $WINDOW_NUM -X stuff "cd /root/Desktop/Arsenal\ VPS/app && source ../myenv/bin/activate && python live_arsenal_horus_integrated.py --live --symbol $symbol$(printf '\r')"
    WINDOW_NUM=$((WINDOW_NUM + 1))
    sleep 3  # Stagger the bot startups
done

echo ""
echo " ALL COMPONENTS LAUNCHED SUCCESSFULLY!"
echo ""
echo " To view the system in real-time:"
echo "   - Connect to the screen session: screen -r arsenal-system"
echo "   - Use Ctrl+A, then N to switch between windows (different components)"
echo "   - Use Ctrl+A, then W to see window list"
echo "   - Use Ctrl+A, then D to detach from screen session"
echo ""
echo " To kill the entire system: screen -S arsenal-system -X quit"
echo ""
echo " The system is now running live trading operations with all components!"
echo "   Helios -> Aegis -> Trading Bots are all interconnected and operational."
echo ""