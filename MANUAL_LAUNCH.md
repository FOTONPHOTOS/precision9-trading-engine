# Arsenal VPS Trading System - Manual Launch Guide

## Quick Reference

### Environment Setup
```bash
cd /root/arsenal_git_ready
source myenv/bin/activate
```

---

## Step-by-Step Manual Launch

### Step 1: Activate Virtual Environment
```bash
cd /root/arsenal_git_ready
source myenv/bin/activate
```

---

### Step 2: Start Helios Server (Central Intelligence)
**Terminal 1:**
```bash
cd /root/arsenal_git_ready/app
python helios_server.py
```
**Wait for:** `"BTC Arsenal Engine is running"` message (~15 seconds)

---

### Step 3: Start Aegis / Eyes of Horus (Risk Management)
**Terminal 2:**
```bash
cd /root/arsenal_git_ready/app
python eyes_of_horus/main.py --live
```
**Wait for:** Connection confirmation (~10 seconds)

---

### Step 4: Start Trading Bots (One Per Symbol)

**For BTCUSDT - Terminal 3:**
```bash
cd /root/arsenal_git_ready/app
python live_arsenal_horus_integrated.py --live --symbol BTCUSDT
```

**For ETHUSDT - Terminal 4:**
```bash
cd /root/arsenal_git_ready/app
python live_arsenal_horus_integrated.py --live --symbol ETHUSDT
```

**For SOLUSDT - Terminal 5:**
```bash
cd /root/arsenal_git_ready/app
python live_arsenal_horus_integrated.py --live --symbol SOLUSDT
```

**For XRPUSDT - Terminal 6:**
```bash
cd /root/arsenal_git_ready/app
python live_arsenal_horus_integrated.py --live --symbol XRPUSDT
```

**For BNBUSDT - Terminal 7:**
```bash
cd /root/arsenal_git_ready/app
python live_arsenal_horus_integrated.py --live --symbol BNBUSDT
```

**For LINKUSDT - Terminal 8:**
```bash
cd /root/arsenal_git_ready/app
python live_arsenal_horus_integrated.py --live --symbol LINKUSDT
```

---

## Using Screen (Recommended for Background Running)

### Start Everything in Screen Sessions

```bash
cd /root/arsenal_git_ready

# Create main screen session
screen -dmS arsenal-system

# Start Helios in window 0
screen -S arsenal-system -X screen -t helios 0
screen -S arsenal-system -p 0 -X stuff "cd /root/arsenal_git_ready/app && source ../myenv/bin/activate && python helios_server.py$(printf '\r')"

# Wait for Helios
sleep 15

# Start Aegis in window 1
screen -S arsenal-system -X screen -t aegis 1
screen -S arsenal-system -p 1 -X stuff "cd /root/arsenal_git_ready/app && source ../myenv/bin/activate && python eyes_of_horus/main.py --live$(printf '\r')"

# Wait for Aegis
sleep 10

# Start trading bots in separate windows
screen -S arsenal-system -X screen -t bot-btc 2
screen -S arsenal-system -p 2 -X stuff "cd /root/arsenal_git_ready/app && source ../myenv/bin/activate && python live_arsenal_horus_integrated.py --live --symbol BTCUSDT$(printf '\r')"

screen -S arsenal-system -X screen -t bot-eth 3
screen -S arsenal-system -p 3 -X stuff "cd /root/arsenal_git_ready/app && source ../myenv/bin/activate && python live_arsenal_horus_integrated.py --live --symbol ETHUSDT$(printf '\r')"

# Add more symbols as needed...
```

### Screen Commands
| Action | Command |
|--------|---------|
| Attach to session | `screen -r arsenal-system` |
| Next window | `Ctrl+A`, then `N` |
| Previous window | `Ctrl+A`, then `P` |
| List windows | `Ctrl+A`, then `W` |
| Detach (keep running) | `Ctrl+A`, then `D` |
| Kill session | `screen -S arsenal-system -X quit` |

---

## Verify Running Components

```bash
# Check Python processes
ps aux | grep python

# Check if Helios is running (port 8009)
netstat -tlnp | grep 8009

# Check logs
ls -la logs/
```

---

## Stop All Components

### If Running in Screen:
```bash
screen -S arsenal-system -X quit
```

### If Running in Separate Terminals:
Press `Ctrl+C` in each terminal, or:
```bash
pkill -f "helios_server.py"
pkill -f "eyes_of_horus/main.py"
pkill -f "live_arsenal_horus_integrated.py"
```

---

## Troubleshooting

### Port Already in Use
```bash
# Kill processes on port 8009
fuser -k 8009/tcp
```

### Module Not Found
```bash
# Ensure virtual environment is activated
source myenv/bin/activate

# Reinstall dependencies if needed
pip install -r requirements.txt
```

### API Connection Errors
- Check `.env` file has valid Bybit API keys
- Verify `BYBIT_TESTNET=false` for live trading
- Check internet connection

---

## Component Startup Order

```
1. Helios Server     → Wait 15 seconds
2. Aegis/Eyes        → Wait 10 seconds
3. Trading Bots      → Start one per symbol (3 sec between each)
```

**Never start trading bots before Helios and Aegis are fully initialized!**
