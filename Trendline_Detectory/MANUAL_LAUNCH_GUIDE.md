# Manual Launch Guide for Arsenal Ecosystem

This guide provides the individual commands to manually launch each component of the Arsenal ecosystem for debugging and testing purposes.

---

 & "G:\python files\precision9\myenv_clean\Scripts\python.exe" -m pip install --force-reinstall--no-cache-dir python-binance

## 1. Core Services

These should be running before you start the main Arsenal bot.

### A. Launch the Helios Server

This provides the master BTC context.

```powershell
# Set working directory
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' helios_server.py
```

### B. Launch the Aegis Risk Manager

This service listens for, executes, and manages trades.

```powershell
# Set working directory
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory\eyes_of_horus'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' main.py
```

---

## 2. Main Arsenal Bot (Debugging)

Use these commands for testing specific symbols with the `--fast` flag, which speeds up Horus initialization.

### Template

```powershell
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_arsenal_horus_integrated.py --fast --symbol <SYMBOL_HERE>
```

### Examples

**BNBUSDT (Fast Mode):**
```powershell
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_arsenal_horus_integrated.py --fast --symbol BNBUSDT
```

**ETHUSDT (Fast Mode):**
```powershell
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_arsenal_horus_integrated.py --fast --symbol ZKUSDT
```

**SOLUSDT (Fast Mode):**
```powershell
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_arsenal_horus_integrated.py --fast --symbol SOLUSDT
```

---

## 3. Main Arsenal Bot (Live Mode)

Use these commands to run in live trading mode. This will execute real trades.

### Template

```powershell
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_arsenal_horus_integrated.py --live --symbol <SYMBOL_HERE>
```

### Example

**BNBUSDT (Live Mode):**
```powershell
cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_arsenal_horus_integrated.py --live --symbol LINKUSDT
```

cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
& 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_arsenal_horus_integrated.py --fast --symbol  XRPUSDT


launch all: 

.\launch_all_bots.ps1

NEW SYSTEM
   1 cd 'G:\python files\precision9'

   2 .\launch_scalping_system.ps1

  Or if you want to run it manually, use:

   1 cd 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'
   & 'G:\python files\precision9\myenv_clean\Scripts\python.exe' live_scalping_microstructure_system.py --live --symbol XRPUSDT