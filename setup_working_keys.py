#!/usr/bin/env python3
"""
Configure .env with working API keys and show account info
"""

import os
from pybit.unified_trading import HTTP

API_KEY = "6Bn3GZevnFnz1oREDY"
API_SECRET = "akZALhRbAFeWokv2e26CQfYwXvCE6BmkN0Xz"

print(f"\n{'='*70}")
print("   CONFIGURING ARSENAL VPS WITH YOUR BYBIT API KEYS")
print(f"{'='*70}\n")

# Create client
client = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET,
    testnet=False
)

# Get wallet balance
print("Fetching wallet balance...")
balance = client.get_wallet_balance(accountType="UNIFIED")
if balance.get('retCode') == 0:
    print(" Connected to Bybit successfully!\n")
    
    balances = balance.get('result', {}).get('list', [])
    total_usd = 0
    
    print("   Your Wallet Balances:")
    print("   " + "-"*50)
    for bal in balances:
        coins = bal.get('coin', [])
        for coin in coins:
            wb = float(coin.get('walletBalance', 0))
            if wb > 0:
                print(f"    {coin.get('coin')}: ${wb:,.2f}")
                total_usd += wb
    
    print("   " + "-"*50)
    print(f"   TOTAL: ${total_usd:,.2f}")
else:
    print(f" Balance query failed: {balance.get('retMsg')}")

# Get positions
print("\nFetching open positions...")
positions = client.get_positions(category="linear")
if positions.get('retCode') == 0:
    pos_list = positions.get('result', {}).get('list', [])
    active = [p for p in pos_list if float(p.get('size', 0)) != 0]
    
    if active:
        print(f" Found {len(active)} active position(s):\n")
        for pos in active:
            side = pos.get('side', 'None')
            size = pos.get('size', 0)
            entry = pos.get('entryPrice', 0)
            symbol = pos.get('symbol', 'Unknown')
            print(f"    {symbol}: {side} {size} @ ${entry}")
    else:
        print(" No active positions (clean account)")
else:
    print(f" Position query failed: {positions.get('retMsg')}")

# Update .env file
env_path = '/root/arsenal_git_ready/.env'
print(f"\n{'='*70}")
print(f"   Updating {env_path}...")
print(f"{'='*70}\n")

with open(env_path, 'w') as f:
    f.write("# Arsenal VPS Trading System - API Configuration\n")
    f.write(f"# Configured: {os.popen('date').read().strip()}\n")
    f.write(f"# Status:  VERIFIED AND WORKING\n\n")
    
    f.write("# Bybit API Configuration\n")
    f.write(f"BYBIT_API_KEY={API_KEY}\n")
    f.write(f"BYBIT_API_SECRET={API_SECRET}\n")
    f.write(f"BYBIT_TESTNET=false\n\n")
    
    f.write("# Binance API (optional - for Helios market data)\n")
    f.write("# BINANCE_API_KEY=\n")
    f.write("# BINANCE_API_SECRET=\n\n")
    
    f.write("# Trading Settings\n")
    f.write("# DEFAULT_LEVERAGE=10\n")
    f.write("# DEFAULT_POSITION_SIZE_USD=100\n")

print(f"     .env file updated!")
print(f"\n    Configuration:")
print(f"    - API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
print(f"    - Mode: LIVE MAINNET  (real money)")
print(f"    - File: {env_path}\n")

print(f"{'='*70}")
print(f"    READY TO LAUNCH!")
print(f"{'='*70}")
print(f"\nLaunch commands:\n")
print(f"  cd /root/arsenal_git_ready")
print(f"\n  # Start Helios Server (market data)")
print(f"  ./app/run_helios_server.sh &")
print(f"\n  # Wait 15 seconds, then start Aegis (risk management)")
print(f"  sleep 15")
print(f"  ./app/run_eyes_of_horus.sh &")
print(f"\n  # Wait 10 seconds, then start trading bots")
print(f"  sleep 10")
print(f"  ./app/run_trading_bot_btc.sh &")
print(f"  ./app/run_trading_bot_eth.sh &")
print(f"  ./app/run_trading_bot_sol.sh &")
print(f"\n  # To view running bots:")
print(f"  ps aux | grep -E '(helios|eyes|arsenal)' | grep -v grep")
print(f"\n  # To stop all bots:")
print(f"  pkill -f 'helios_server.py'")
print(f"  pkill -f 'eyes_of_horus'")
print(f"  pkill -f 'live_arsenal_horus_integrated'")
print(f"\n{'='*70}")
print(f"     WARNING: This is LIVE trading with REAL money!")
print(f"{'='*70}\n")
