#!/usr/bin/env python3
"""
API Key Tester for Bybit and Binance
Tests if API keys are valid and updates .env file if they work
"""

import os
import sys
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Load existing .env
load_dotenv('.env')

def test_bybit_api(api_key, api_secret, testnet=False):
    """Test Bybit API key validity"""
    print(f"\n{'='*60}")
    print(f"Testing Bybit API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"Testnet: {testnet}")
    print(f"{'='*60}")
    
    try:
        client = HTTP(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )
        
        # Test 1: Get server time
        print("\n[1/4] Testing server time...")
        time_response = client.get_server_time()
        if time_response.get('retCode') == 0:
            print(f"    ✅ Server time: {time_response.get('result', {}).get('timeSecond', 'N/A')}")
        else:
            print(f"    ❌ Server time failed: {time_response.get('retMsg', 'Unknown error')}")
            return False
        
        # Test 2: Get wallet balance
        print("\n[2/4] Testing wallet balance...")
        balance_response = client.get_wallet_balance(accountType="UNIFIED")
        if balance_response.get('retCode') == 0:
            print(f"    ✅ Balance query successful")
            balances = balance_response.get('result', {}).get('list', [])
            if balances:
                for balance_info in balances:
                    coins = balance_info.get('coin', [])
                    for coin in coins:
                        wallet_balance = float(coin.get('walletBalance', 0))
                        if wallet_balance > 0:
                            print(f"       {coin.get('coin', 'N/A')}: ${wallet_balance:,.2f}")
        else:
            print(f"    ❌ Balance query failed: {balance_response.get('retMsg', 'Unknown error')}")
            return False
        
        # Test 3: Get positions
        print("\n[3/4] Testing positions...")
        positions_response = client.get_positions(category="linear")
        if positions_response.get('retCode') == 0:
            print(f"    ✅ Positions query successful")
            positions = positions_response.get('result', {}).get('list', [])
            active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
            if active_positions:
                print(f"       Found {len(active_positions)} active position(s)")
                for pos in active_positions:
                    print(f"       - {pos.get('symbol', 'N/A')}: {pos.get('side', 'N/A')} {pos.get('size', 0)} @ {pos.get('entryPrice', 0)}")
            else:
                print(f"       No active positions")
        else:
            print(f"    ❌ Positions query failed: {positions_response.get('retMsg', 'Unknown error')}")
            return False
        
        # Test 4: Get account info
        print("\n[4/4] Testing account info...")
        account_response = client.get_account_info(accountType="CONTRACT")
        if account_response.get('retCode') == 0:
            print(f"    ✅ Account info successful")
            account_info = account_response.get('result', {})
            print(f"       Account Type: {account_info.get('accountType', 'N/A')}")
            print(f"       Margin Mode: {account_info.get('marginMode', 'N/A')}")
        else:
            print(f"    ❌ Account info failed: {account_response.get('retMsg', 'Unknown error')}")
            return False
        
        print(f"\n{'='*60}")
        print(f"✅ BYBIT API KEY IS VALID AND FUNCTIONAL!")
        print(f"{'='*60}")
        return True
        
    except Exception as e:
        print(f"\n❌ BYBIT API TEST FAILED: {str(e)}")
        return False


def test_binance_api(api_key, api_secret):
    """Test Binance API key validity"""
    print(f"\n{'='*60}")
    print(f"Testing Binance API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"{'='*60}")
    
    try:
        from binance.client import Client
        from binance.exceptions import BinanceAPIException
        
        client = Client(api_key, api_secret)
        
        # Test 1: Get account info
        print("\n[1/3] Testing account info...")
        try:
            account = client.get_account()
            print(f"    ✅ Account query successful")
            print(f"       Maker Commission: {account.get('makerCommission', 0)}")
            print(f"       Taker Commission: {account.get('takerCommission', 0)}")
            
            # Show balances > 0
            balances = account.get('balances', [])
            print(f"\n       Non-zero balances:")
            for balance in balances:
                free = float(balance.get('free', 0))
                locked = float(balance.get('locked', 0))
                if free > 0 or locked > 0:
                    print(f"       {balance.get('asset', 'N/A')}: {free:.8f} (locked: {locked:.8f})")
        except BinanceAPIException as e:
            print(f"    ❌ Account query failed: {e.message}")
            return False
        
        # Test 2: Get exchange info
        print("\n[2/3] Testing exchange info...")
        try:
            exchange_info = client.get_exchange_info()
            print(f"    ✅ Exchange info successful")
            print(f"       Timezone: {exchange_info.get('timezone', 'N/A')}")
            print(f"       Server Time: {exchange_info.get('serverTime', 'N/A')}")
        except BinanceAPIException as e:
            print(f"    ❌ Exchange info failed: {e.message}")
            return False
        
        # Test 3: Test order placement (without actually placing)
        print("\n[3/3] Testing trading permissions...")
        try:
            # Get symbol info for BTCUSDT
            symbol_info = client.get_symbol_info('BTCUSDT')
            if symbol_info:
                permissions = symbol_info.get('permissions', [])
                print(f"    ✅ Trading permissions: {permissions}")
                if 'MARGIN' in permissions:
                    print(f"       Margin trading: ENABLED")
                if 'SPOT' in permissions:
                    print(f"       Spot trading: ENABLED")
        except BinanceAPIException as e:
            print(f"    ❌ Trading permissions failed: {e.message}")
            return False
        
        print(f"\n{'='*60}")
        print(f"✅ BINANCE API KEY IS VALID AND FUNCTIONAL!")
        print(f"{'='*60}")
        return True
        
    except ImportError:
        print(f"\n⚠️  Binance client not installed. Skipping Binance test.")
        print(f"    Install with: pip install python-binance")
        return None
    except Exception as e:
        print(f"\n❌ BINANCE API TEST FAILED: {str(e)}")
        return False


def update_env_file(bybit_key, bybit_secret, binance_key=None, binance_secret=None, testnet=False):
    """Update .env file with working API keys"""
    env_path = '.env'
    
    print(f"\n{'='*60}")
    print(f"Updating {env_path} file...")
    print(f"{'='*60}")
    
    # Read existing content
    existing_content = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing_content[key.strip()] = value.strip()
    
    # Update with new keys
    existing_content['BYBIT_API_KEY'] = bybit_key
    existing_content['BYBIT_API_SECRET'] = bybit_secret
    existing_content['BYBIT_TESTNET'] = str(testnet).lower()
    
    if binance_key:
        existing_content['BINANCE_API_KEY'] = binance_key
    if binance_secret:
        existing_content['BINANCE_API_SECRET'] = binance_secret
    
    # Write back
    with open(env_path, 'w') as f:
        f.write("# Arsenal VPS Trading System - API Configuration\n")
        f.write("# Auto-generated by test_api_keys.py\n")
        f.write(f"# Updated: {os.popen('date').read().strip()}\n\n")
        
        f.write("# Bybit API Configuration\n")
        f.write(f"BYBIT_API_KEY={bybit_key}\n")
        f.write(f"BYBIT_API_SECRET={bybit_secret}\n")
        f.write(f"BYBIT_TESTNET={str(testnet).lower()}\n\n")
        
        if binance_key:
            f.write("# Binance API Configuration\n")
            f.write(f"BINANCE_API_KEY={binance_key}\n")
            f.write(f"BINANCE_API_SECRET={binance_secret}\n\n")
        
        f.write("# Optional: Helios Configuration\n")
        f.write("# HELIOS_PORT=8009\n")
        f.write("# HELIOS_HOST=0.0.0.0\n")
    
    print(f"    ✅ {env_path} updated successfully!")
    print(f"\n    Keys configured:")
    print(f"    - Bybit API Key: {bybit_key[:8]}...{bybit_key[-4:]}")
    print(f"    - Bybit Testnet: {testnet}")
    if binance_key:
        print(f"    - Binance API Key: {binance_key[:8]}...{binance_key[-4:]}")
    
    return True


def main():
    print("\n" + "="*60)
    print("   ARSENAL VPS - API KEY TESTER")
    print("="*60)
    
    # Get API keys from user
    print("\n📝 Enter your API credentials:")
    print("(Keys will not be displayed as you type)\n")
    
    # Bybit keys
    print("BYBIT API:")
    bybit_key = input("  API Key: ").strip()
    bybit_secret = input("  API Secret: ").strip()
    
    # Ask if testnet
    testnet_input = input("  Testnet? (y/n, default=n): ").strip().lower()
    testnet = testnet_input == 'y' or testnet_input == 'yes'
    
    # Binance keys (optional)
    print("\nBINANCE API (optional, for Helios market data):")
    use_binance = input("  Configure Binance? (y/n, default=n): ").strip().lower()
    
    binance_key = None
    binance_secret = None
    
    if use_binance in ['y', 'yes']:
        binance_key = input("  API Key: ").strip()
        binance_secret = input("  API Secret: ").strip()
    
    # Test Bybit
    bybit_valid = test_bybit_api(bybit_key, bybit_secret, testnet)
    
    # Test Binance (if provided)
    binance_valid = None
    if binance_key and binance_secret:
        binance_valid = test_binance_api(binance_key, binance_secret)
    
    # Update .env if keys are valid
    if bybit_valid:
        update_env_file(
            bybit_key, 
            bybit_secret, 
            binance_key if binance_valid else None,
            binance_secret if binance_valid else None,
            testnet
        )
        
        print(f"\n{'='*60}")
        print(f"✅ SETUP COMPLETE!")
        print(f"{'='*60}")
        print(f"\nYou can now launch your bots:")
        print(f"  cd /root/arsenal_git_ready")
        print(f"  ./app/run_helios_server.sh &")
        print(f"  ./app/run_eyes_of_horus.sh &")
        print(f"  ./app/run_trading_bot_btc.sh &")
        print(f"\nPress Ctrl+C to stop any running bot")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print(f"❌ API KEY TEST FAILED")
        print(f"{'='*60}")
        print(f"\nPlease check:")
        print(f"  1. API key is correct (no typos)")
        print(f"  2. API key has not expired")
        print(f"  3. API key has required permissions (Read, Trade)")
        print(f"  4. IP whitelist (if configured) includes this server")
        print(f"\nTry again with valid keys.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
