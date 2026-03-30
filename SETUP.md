# Arsenal VPS Trading System - Setup Guide

## Quick Start

### 1. Install System Dependencies (Ubuntu/Debian)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential

# Install TA-Lib system library (required for ta-lib Python package)
wget https://github.com/ta-lib/ta-lib/releases/download/v0.4.0/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib-0.4.0-src/
./configure --prefix=/usr
make
sudo make install
cd ..
rm -rf ta-lib-0.4.0-src ta-lib-0.4.0-src.tar.gz
```

### 2. Set Up Python Environment

```bash
# Navigate to project directory
cd /root/arsenal_git_ready

# Create virtual environment
python3 -m venv myenv

# Activate virtual environment
source myenv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your API keys
nano .env
```

**Required variables in `.env`:**
```
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=false
```

### 4. Launch the System

**Option A: Using Launch Scripts (Recommended)**

```bash
# Terminal 1 - Helios Server
./app/run_helios_server.sh

# Terminal 2 - Eyes of Horus (Aegis)
./app/run_eyes_of_horus.sh

# Terminal 3+ - Trading Bots
./app/run_trading_bot_btc.sh
./app/run_trading_bot_eth.sh
./app/run_trading_bot_sol.sh
```

**Option B: Manual Launch**

```bash
# Activate environment
source myenv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="/root/arsenal_git_ready/app:$PYTHONPATH"

# Start components
cd app
python3 helios_server.py &
python3 eyes_of_horus/main.py --live &
python3 live_arsenal_horus_integrated.py --live --symbol BTCUSDT &
```

**Option C: Auto-Launch All**

```bash
./LAUNCH_ALL_BOTS_AUTO.sh
```

---

## Verification

### Check if Components are Running

```bash
# Check Python processes
ps aux | grep python3

# Check if Helios is running (port 8009)
netstat -tlnp | grep 8009

# Or use the provided script
./check_processes.sh
```

### Test API Connection

```bash
python3 check_bybit_details.py
```

---

## Troubleshooting

### ModuleNotFoundError

```bash
# Ensure virtual environment is activated
source myenv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### TA-Lib Installation Error

```bash
# Install system library first
sudo apt install -y libta-lib-dev

# Or build from source (see step 1)
```

### Port Already in Use

```bash
# Kill processes on port 8009
sudo fuser -k 8009/tcp

# Or kill all Python processes related to the bot
pkill -f "helios_server.py"
pkill -f "eyes_of_horus"
pkill -f "live_arsenal_horus_integrated.py"
```

### Permission Denied

```bash
# Make scripts executable
chmod +x *.sh app/*.sh
```

---

## Directory Structure

```
arsenal_git_ready/
├── app/                          # Main application code
│   ├── eyes_of_horus/           # Aegis risk management
│   ├── helios_server.py         # Central intelligence
│   ├── live_arsenal_horus_integrated.py  # Trading bot
│   └── run_*.sh                 # Launch scripts
├── Trendline_Detectory/          # Advanced detection module
├── config_tuning/                # Configuration files
├── SOL_Market_Data_Tool/         # Solana data utilities
├── .env                          # Environment variables (DO NOT COMMIT)
├── .env.example                  # Example environment file
├── requirements.txt              # Python dependencies
├── LAUNCH_ALL_BOTS_AUTO.sh      # Auto-launch script
└── README.md                     # Documentation
```

---

## For Open Source/Portfolio Use

This repository is ready for:
- ✅ GitHub/GitLab deployment
- ✅ Job portfolio showcase
- ✅ Open source contribution

**Note:** The `.gitignore` excludes:
- Virtual environments
- API keys (`.env`)
- Database files
- Log files
- Large data files

---

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review `README.md` for architecture details
3. Check individual component documentation
