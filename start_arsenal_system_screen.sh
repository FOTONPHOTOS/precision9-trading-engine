#!/bin/bash

# Arsenal VPS Trading System Startup Script (Screen Mode)
# Creates multiple screen windows for real-time monitoring

echo " Starting Arsenal VPS Trading System with Screen..."

# Navigate to the project directory
cd /root/Desktop/Arsenal VPS

# Activate the Python virtual environment
source myenv/bin/activate

echo " Loading environment variables..."
export $(grep -v '^#' .env | xargs)  # Load environment variables

# Create a new screen session named "arsenal-system"
screen -dmS arsenal-system

echo " Starting Helios server in screen window 0..."
screen -S arsenal-system -X screen -t Helios 0
screen -S arsenal-system -p 0 -X stuff "cd /root/Desktop/Arsenal VPS/app && source ../myenv/bin/activate && python helios_server.py$(printf \\r)"

sleep 5  # Give Helios time to initialize

echo "  Starting Eyes of Horus in screen window 1..."
screen -S arsenal-system -X screen -t Aegis 1
screen -S arsenal-system -p 1 -X stuff "cd /root/Desktop/Arsenal VPS/app && source ../myenv/bin/activate && python eyes_of_horus/main.py --live$(printf \\r)"

sleep 10  # Wait more for initialization

# Define the symbols to trade
SYMBOLS=("ETHUSDT" "BTCUSDT" "SOLUSDT" "XRPUSDT" "BNBUSDT" "LINKUSDT")
WINDOW_NUM=2

for symbol in "${SYMBOLS[@]}"; do
    echo " Starting bot for $symbol in screen window $WINDOW_NUM..."
    screen -S arsenal-system -X screen -t Bot_$symbol $WINDOW_NUM
    screen -S arsenal-system -p $WINDOW_NUM -X stuff "cd /root/Desktop/Arsenal VPS/app && source ../myenv/bin/activate && python live_arsenal_horus_integrated.py --live --symbol $symbol$(printf \\r)"
    
    WINDOW_NUM=$((WINDOW_NUM + 1))
    sleep 3  # Wait between starting each bot
done

echo ""
echo " Arsenal VPS Trading System launched in screen session!"
echo ""
echo " To view the system in real-time:"
echo "   - Connect to the screen session: screen -r arsenal-system"
echo "   - Use Ctrl+A, then N to switch between windows"
echo "   - Use Ctrl+A, then W to see window list"
echo "   - Use Ctrl+A, then D to detach from screen session"
echo ""
echo " All components are running in separate screen windows for real-time monitoring!"
echo "   You can detach and the processes will continue running."
echo ""
echo " To kill the entire session: screen -S arsenal-system -X quit"