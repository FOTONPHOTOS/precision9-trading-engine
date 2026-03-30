#!/usr/bin/env python3
"""
System Status Checker for Arsenal VPS
Checks if all components of the trading system are running properly.
"""

import requests
import socket
import subprocess
import sys
from typing import Dict, List

def check_port(port: int, host: str = "localhost") -> bool:
    """Check if a port is open on the specified host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)  # Timeout after 2 seconds
            result = s.connect_ex((host, port))
            return result == 0
    except:
        return False

def check_process_count(name: str) -> int:
    """Count processes containing the specified name."""
    try:
        result = subprocess.run(['pgrep', '-f', name], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            return len([pid for pid in pids if pid])  # Filter out empty strings
        return 0
    except Exception:
        return 0

def main():
    print(" ARSENAL VPS SYSTEM STATUS CHECK")
    print("="*50)
    
    # Check if main services are running
    print("\n SERVICE CONNECTIVITY:")
    
    # Helios Server (should be on port 8009)
    helios_up = check_port(8009)
    print(f"   Helios Server (Port 8009): {' UP' if helios_up else ' DOWN'}")
    
    # Aegis WebSocket Server (should be on port 8765)
    aegis_up = check_port(8765)
    print(f"    Aegis/Eyes of Horus (Port 8765): {' UP' if aegis_up else ' DOWN'}")
    
    print("\n  PROCESS COUNTS:")
    
    # Count different types of processes
    helios_processes = check_process_count("helios_server.py")
    print(f"   Helios Server Processes: {helios_processes}")
    
    aegis_processes = check_process_count("eyes_of_horus/main.py")
    print(f"    Aegis/Eyes of Horus Processes: {aegis_processes}")
    
    bot_processes = check_process_count("live_arsenal_horus_integrated.py")
    print(f"   Arsenal/Horus Trading Bot Processes: {bot_processes}")
    
    main_processes = check_process_count("main.py")
    print(f"    General Main Processes: {main_processes}")
    
    print("\n DETECTED SYMBOLS BEING TRADED:")
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "LINKUSDT"]
    for symbol in symbols:
        symbol_processes = check_process_count(f"--symbol {symbol}")
        if symbol_processes > 0:
            print(f"    • {symbol}:  ({symbol_processes} instance{'s' if symbol_processes > 1 else ''})")
        else:
            print(f"    • {symbol}:  (0 instances)")
    
    print("\n SUMMARY:")
    total_processes = helios_processes + aegis_processes + bot_processes + main_processes
    
    if helios_up and aegis_up and bot_processes >= 1:
        print("   OVERALL STATUS:  SYSTEM OPERATIONAL")
        print(f"   Active Components: Helios, Aegis, {bot_processes} trading bot{'s' if bot_processes > 1 else ''}")
        print("   Live trading system is running on your VPS!")
    else:
        print("   OVERALL STATUS:  PARTIAL OR NON-FUNCTIONAL")
        if not helios_up:
            print("    - Helios server is not responding")
        if not aegis_up:
            print("    - Aegis/Eyes of Horus is not responding")
        if bot_processes == 0:
            print("    - No trading bots are currently running")
    
    print("\n TIPS:")
    if not aegis_up or bot_processes == 0:
        print("  • If services are down, you may need to restart them individually:")
        print("    1. cd /root/Desktop/Arsenal VPS/app && source ../myenv/bin/activate && python helios_server.py")
        print("    2. In another terminal: cd /root/Desktop/Arsenal VPS/app && source ../myenv/bin/activate && python eyes_of_horus/main.py --live")
        print("    3. Then start your trading bots")
    
    print(f"\n System check complete. Total processes checked: {total_processes}")

if __name__ == "__main__":
    main()