#!/bin/bash
# Master script to launch the complete Arsenal VPS trading system

echo "Starting complete Arsenal VPS trading system..."

# Launch Helios Server (Central Intelligence Hub) in background
echo "Starting Helios Server..."
cd /root/Desktop/Arsenal\ VPS/app
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python helios_server.py > helios_server.log 2>&1 &

HELIOS_PID=$!
echo "Helios Server started with PID: $HELIOS_PID"

# Wait a bit for Helios to initialize
sleep 5

# Launch Eyes of Horus in background
echo "Starting Eyes of Horus..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python eyes_of_horus/main.py --live > eyes_of_horus.log 2>&1 &

EYES_PID=$!
echo "Eyes of Horus started with PID: $EYES_PID"

# Wait a bit more
sleep 3

# Launch main trading bot for BTCUSDT in background
echo "Starting BTCUSDT trading bot..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol BTCUSDT > trading_bot_btc.log 2>&1 &

BTC_PID=$!
echo "BTCUSDT trading bot started with PID: $BTC_PID"

# Wait a bit more
sleep 3

# Launch main trading bot for ETHUSDT in background
echo "Starting ETHUSDT trading bot..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol ETHUSDT > trading_bot_eth.log 2>&1 &

ETH_PID=$!
echo "ETHUSDT trading bot started with PID: $ETH_PID"

# Wait a bit more
sleep 3

# Launch main trading bot for SOLUSDT in background
echo "Starting SOLUSDT trading bot..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol SOLUSDT > trading_bot_sol.log 2>&1 &

SOL_PID=$!
echo "SOLUSDT trading bot started with PID: $SOL_PID"

# Wait a bit more
sleep 3

# Launch main trading bot for BNBUSDT in background
echo "Starting BNBUSDT trading bot..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol BNBUSDT > trading_bot_bnb.log 2>&1 &

BNB_PID=$!
echo "BNBUSDT trading bot started with PID: $BNB_PID"

# Wait a bit more
sleep 3

# Launch main trading bot for XRPUSDT in background
echo "Starting XRPUSDT trading bot..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol XRPUSDT > trading_bot_xrp.log 2>&1 &

XRP_PID=$!
echo "XRPUSDT trading bot started with PID: $XRP_PID"

# Wait a bit more
sleep 3

# Launch main trading bot for LINKUSDT in background
echo "Starting LINKUSDT trading bot..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol LINKUSDT > trading_bot_link.log 2>&1 &

LINK_PID=$!
echo "LINKUSDT trading bot started with PID: $LINK_PID"

# Wait a bit more
sleep 3

# Launch main trading bot for DOGEUSDT in background
echo "Starting DOGEUSDT trading bot..."
nohup /root/Desktop/Arsenal\ VPS/venv/bin/python live_arsenal_horus_integrated.py --live --symbol DOGEUSDT > trading_bot_doge.log 2>&1 &

DOGE_PID=$!
echo "DOGEUSDT trading bot started with PID: $DOGE_PID"

echo "All components started!"
echo "Helios Server PID: $HELIOS_PID"
echo "Eyes of Horus PID: $EYES_PID"
echo "BTCUSDT Bot PID: $BTC_PID"
echo "ETHUSDT Bot PID: $ETH_PID"
echo "SOLUSDT Bot PID: $SOL_PID"
echo "BNBUSDT Bot PID: $BNB_PID"
echo "XRPUSDT Bot PID: $XRP_PID"
echo "LINKUSDT Bot PID: $LINK_PID"
echo "DOGEUSDT Bot PID: $DOGE_PID"

echo ""
echo "To check logs, use:"
echo "  tail -f /root/Desktop/Arsenal VPS/app/helios_server.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/eyes_of_horus.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/trading_bot_btc.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/trading_bot_eth.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/trading_bot_sol.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/trading_bot_bnb.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/trading_bot_xrp.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/trading_bot_link.log"
echo "  tail -f /root/Desktop/Arsenal VPS/app/trading_bot_doge.log"

echo ""
echo "To stop all components, use:"
echo "  kill $HELIOS_PID $EYES_PID $BTC_PID $ETH_PID $SOL_PID $BNB_PID $XRP_PID $LINK_PID $DOGE_PID"