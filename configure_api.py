#!/usr/bin/env python3
"""
Configure and test Bybit API keys
"""

import os
from pybit.unified_trading import HTTP

# New API Keys provided
BYBIT_API_KEY = "6Bn3GZevnFnz1oREDY"
BYBIT_API_SECRET = "akZALhRbAFeWokv2e26CQfYwXvCE6BmkN0X"

def test_api_keys():
    """Test if API keys are valid"""
    print("\n" + "="*60)
    print("   TESTING BYBIT API KEYS")
    print("="*60)
    print(f"\nAPI Key: {BYBIT_API_KEY[:8]}...{BYBIT_API_KEY[-4:]}")
    print(f"Secret: {BYBIT_API_SECRET[:8]}...{BYBIT_API_SECRET[-4:]}")
    
    # Test both testnet and mainnet
    for testnet in [True, False]:
        print(f"\n{'='*60}")
        print(f"Testing {'TESTNET' if testnet else 'MAINNET'}...")
        print(f"{'='*60}\n")
        
        try:
            client = HTTP(
                api_key=BYBIT_API_KEY,
                api_secret=BYBIT_API_SECRET,
                testnet=testnet
            )
            
            # Test 1: Server time
            print("[1/4] Getting server time...")
            time_response = client.get_server_time()
            if time_response.get('retCode') == 0:
                print(f"     Server time: {time_response.get('result', {}).get('timeSecond', 'N/A')}")
            else:
                print(f"     Failed: {time_response.get('retMsg', 'Unknown error')}")
                continue
            
            # Test 2: Wallet balance
            print("\n[2/4] Getting wallet balance...")
            balance_response = client.get_wallet_balance(accountType="UNIFIED")
            ret_code = balance_response.get('retCode')
            
            if ret_code == 0:
                print(f"     Balance query successful!")
                balances = balance_response.get('result', {}).get('list', [])
                if balances:
                    for balance_info in balances:
                        coins = balance_info.get('coin', [])
                        for coin in coins:
                            wallet_balance = float(coin.get('walletBalance', 0))
                            if wallet_balance > 0:
                                print(f"        {coin.get('coin', 'N/A')}: ${wallet_balance:,.2f}")
                else:
                    print(f"       No balance data returned")
            else:
                print(f"     Balance failed: {balance_response.get('retMsg', 'Unknown error')}")
                if ret_code == 10003 or '401' in str(balance_response):
                    print("         API key invalid, expired, or wrong permissions")
                continue
            
            # Test 3: Positions
            print("\n[3/4] Getting positions...")
            positions_response = client.get_positions(category="linear")
            if positions_response.get('retCode') == 0:
                print(f"     Positions query successful!")
                positions = positions_response.get('result', {}).get('list', [])
                active = [p for p in positions if float(p.get('size', 0)) != 0]
                if active:
                    print(f"       Found {len(active)} active position(s):")
                    for pos in active:
                        print(f"       - {pos.get('symbol')}: {pos.get('side')} {pos.get('size')} @ {pos.get('entryPrice')}")
                else:
                    print(f"       No active positions")
            else:
                print(f"     Positions failed: {positions_response.get('retMsg')}")
                continue
            
            # Test 4: Account info
            print("\n[4/4] Getting account info...")
            account_response = client.get_account_info(accountType="CONTRACT")
            if account_response.get('retCode') == 0:
                print(f"     Account info successful!")
                acc = account_response.get('result', {})
                print(f"       Account Type: {acc.get('accountType', 'N/A')}")
                print(f"       Margin Mode: {acc.get('marginMode', 'N/A')}")
            else:
                print(f"     Account info failed: {account_response.get('retMsg')}")
                continue
            
            # SUCCESS!
            print(f"\n{'='*60}")
            print(f" API KEYS ARE VALID ON {'TESTNET' if testnet else 'MAINNET'}! ")
            print(f"{'='*60}\n")
            
            return testnet
            
        except Exception as e:
            print(f"     Error: {str(e)}")
            continue
    
    return None


def update_env(testnet):
    """Update .env file with working keys"""
    env_path = '/root/arsenal_git_ready/.env'
    
    print(f"\n{'='*60}")
    print(f"Updating {env_path}...")
    print(f"{'='*60}\n")
    
    with open(env_path, 'w') as f:
        f.write("# Arsenal VPS Trading System - API Configuration\n")
        f.write(f"# Auto-configured: {os.popen('date').read().strip()}\n\n")
        
        f.write("# Bybit API Configuration\n")
        f.write(f"BYBIT_API_KEY={BYBIT_API_KEY}\n")
        f.write(f"BYBIT_API_SECRET={BYBIT_API_SECRET}\n")
        f.write(f"BYBIT_TESTNET={str(testnet).lower()}\n\n")
        
        f.write("# Binance API Configuration (for Helios market data)\n")
        f.write("# BINANCE_API_KEY=your_key_here\n")
        f.write("# BINANCE_API_SECRET=your_secret_here\n\n")
        
        f.write("# Optional Settings\n")
        f.write("# HELIOS_PORT=8009\n")
        f.write("# HELIOS_HOST=0.0.0.0\n")
    
    print(f"     .env file updated successfully!")
    print(f"\n    Configuration:")
    print(f"    - API Key: {BYBIT_API_KEY[:8]}...{BYBIT_API_KEY[-4:]}")
    print(f"    - Mode: {'TESTNET' if testnet else 'LIVE MAINNET'} ")
    print(f"\n    File location: {env_path}\n")


def main():
    print("\n" + "="*60)
    print("   ARSENAL VPS - API KEY CONFIGURER")
    print("="*60)
    
    # Test the keys
    result = test_api_keys()
    
    if result is not None:
        update_env(result)
        
        print(f"{'='*60}")
        print(f" READY TO LAUNCH!")
        print(f"{'='*60}")
        print(f"\nLaunch commands:")
        print(f"  cd /root/arsenal_git_ready")
        print(f"  ")
        print(f"  # Start Helios Server (port 8009)")
        print(f"  ./app/run_helios_server.sh &")
        print(f"  ")
        print(f"  # Start Eyes of Horus - Aegis (port 8765)")
        print(f"  ./app/run_eyes_of_horus.sh &")
        print(f"  ")
        print(f"  # Start Trading Bots")
        print(f"  ./app/run_trading_bot_btc.sh &")
        print(f"  ./app/run_trading_bot_eth.sh &")
        print(f"  ./app/run_trading_bot_sol.sh &")
        print(f"  ")
        print(f"  # To stop all bots:")
        print(f"  pkill -f 'helios_server.py'")
        print(f"  pkill -f 'eyes_of_horus'")
        print(f"  pkill -f 'live_arsenal_horus_integrated'")
        print(f"  ")
        print(f"  # Check running processes:")
        print(f"  ps aux | grep -E '(helios|eyes|arsenal)' | grep -v grep")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print(f" API KEYS INVALID OR EXPIRED")
        print(f"{'='*60}")
        print(f"\nPossible issues:")
        print(f"  1. API key has expired")
        print(f"  2. API key was revoked")
        print(f"  3. IP whitelist blocking this server")
        print(f"  4. Insufficient API permissions")
        print(f"\nRequired permissions:")
        print(f"   Contract: Read & Write")
        print(f"   Account: Read")
        print(f"   Order: Read & Write")
        print(f"\nIP Whitelist: Add 185.206.180.70 or leave unrestricted\n")


if __name__ == "__main__":
    main()
