# Arsenal VPS Trading System - Symbols and Launch Commands

## Environment Setup

Your trading system is now fully configured with Python 3.11.14 and all required dependencies.

### To activate the environment:
```bash
source /root/Desktop/Arsenal\ VPS/activate_env.sh
```

## Available Trading Components

### 1. Helios Server (Central Intelligence Hub)
```bash
/root/Desktop/Arsenal\ VPS/app/run_helios_server.sh
```

### 2. Eyes of Horus (Aegis - Market Analysis Engine)
```bash
/root/Desktop/Arsenal\ VPS/app/run_eyes_of_horus.sh
```

### 3. Main Trading Bots by Symbol
- **BTCUSDT**: `/root/Desktop/Arsenal\ VPS/app/run_trading_bot_btc.sh`
- **ETHUSDT**: `/root/Desktop/Arsenal\ VPS/app/run_trading_bot_eth.sh`
- **SOLUSDT**: `/root/Desktop/Arsenal\ VPS/app/run_trading_bot_sol.sh`
- **BNBUSDT**: `/root/Desktop/Arsenal\ VPS/app/run_trading_bot_bnb.sh`
- **XRPUSDT**: `/root/Desktop/Arsenal\ VPS/app/run_trading_bot_xrp.sh`
- **LINKUSDT**: `/root/Desktop/Arsenal\ VPS/app/run_trading_bot_link.sh`
- **DOGEUSDT**: `/root/Desktop/Arsenal\ VPS/app/run_trading_bot_doge.sh`

### 4. Complete System Launch
To launch all components at once:
```bash
/root/Desktop/Arsenal\ VPS/launch_complete_system.sh
```

## System Management

### Check Running Processes
```bash
/root/Desktop/Arsenal\ VPS/check_processes.sh
```

### Stop All Processes
```bash
/root/Desktop/Arsenal\ VPS/stop_all_processes.sh
```

## Supported Trading Symbols

The system includes data files for the following symbols:
- BTCUSDT (Bitcoin)
- ETHUSDT (Ethereum)
- SOLUSDT (Solana)
- BNBUSDT (Binance Coin)
- XRPUSDT (Ripple)
- LINKUSDT (Chainlink)
- DOGEUSDT (Dogecoin)

## Installed Dependencies

- Python 3.11.14
- TA-Lib (Technical Analysis Library)
- Pandas, NumPy
- Binance and Bybit API libraries
- Redis (for caching and data storage)
- FastAPI and Uvicorn (for web services)
- Smart Money Concepts
- YFinance and TA (alternative technical analysis libraries)
- All other dependencies listed in requirements.txt

## Notes
- The system handles missing pandas_ta gracefully (Python 3.11 compatibility issue)
- All scripts automatically use the correct Python environment
- The system is optimized for VPS deployment with proper logging and process management
- Each symbol has dedicated data files: arsenal_signals_[SYMBOL].jsonl