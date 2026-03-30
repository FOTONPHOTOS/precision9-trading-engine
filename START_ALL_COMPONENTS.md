# Arsenal VPS Trading System - Component Startup Guide

This is the correct procedure to start each component of your live trading system with real-time visibility.

## Step 1: Start Helios Server (Central Intelligence)
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python helios_server.py
```

Wait for Helios to fully initialize (look for "BTC Arsenal Engine is running" message) before proceeding to the next step.

## Step 2: Start Aegis/Eyes of Horus (Risk Management)
In a new terminal:
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python eyes_of_horus/main.py --live
```

## Step 3: Start Trading Bots (Per Symbol)
For each symbol you want to trade, start a separate bot in a new terminal:

For ETHUSDT:
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python live_arsenal_horus_integrated.py --live --symbol ETHUSDT
```

For BTCUSDT:
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python live_arsenal_horus_integrated.py --live --symbol BTCUSDT
```

For SOLUSDT:
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python live_arsenal_horus_integrated.py --live --symbol SOLUSDT
```

For XRPUSDT:
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python live_arsenal_horus_integrated.py --live --symbol XRPUSDT
```

For BNBUSDT:
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python live_arsenal_horus_integrated.py --live --symbol BNBUSDT
```

For LINKUSDT:
```bash
cd /root/Desktop/Arsenal\ VPS/app
source ../myenv/bin/activate
python live_arsenal_horus_integrated.py --live --symbol LINKUSDT
```

## Important Notes:
- Start Helios first and wait for it to fully initialize
- Start Aegis second and wait for it to connect properly
- Then start your trading bots (they'll connect to Helios and Aegis)
- Each component shows real-time logs in its own terminal
- To stop a component, press `Ctrl+C` in its terminal
- Make sure your .env file has the correct API keys and BYBIT_TESTNET=false

## Troubleshooting:
- If you see errors mentioning "localhost:8000", those are related to dashboard connections which are now fixed to use port 8009
- If you see errors about pandas-ta, those are now handled gracefully
- The system is designed to work even if some optional components are unavailable

Your live trading system is now ready to run with all components properly integrated and showing real-time logs!