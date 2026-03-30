#!/usr/bin/env python3
"""
Test Bybit V5 API with proper signature generation
Based on: https://bybit-exchange.github.io/docs/v5/guide
"""

import hmac
import hashlib
import time
import requests
import os

# API Keys (trimmed of whitespace)
API_KEY = "6Bn3GZevnFnz1oREDY".strip()
API_SECRET = "akZALhRbAFeWokv2e26CQfYwXvCE6BmkN0Xz".strip()

print(f"\n{'='*60}")
print("   BYBIT V5 API TEST")
print(f"{'='*60}")
print(f"\nAPI Key: '{API_KEY}' (length: {len(API_KEY)})")
print(f"Secret: '{API_SECRET}' (length: {len(API_SECRET)})")

def generate_signature(timestamp, api_key, params=''):
    """Generate V5 signature as per Bybit docs"""
    param_str = f"{timestamp}{api_key}"
    if params:
        param_str += params
    return hmac.new(
        api_key.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_v5_api(testnet=False):
    """Test V5 API endpoints"""
    base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
    mode = "TESTNET" if testnet else "MAINNET"
    
    print(f"\n{'='*60}")
    print(f"Testing {mode}")
    print(f"{'='*60}\n")
    
    # Get server time
    print("[1/4] Getting server time...")
    try:
        response = requests.get(f"{base_url}/v5/market/time")
        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0:
                server_time = data.get('result', {}).get('timeSecond', 'N/A')
                print(f"    ✅ Server time: {server_time}")
            else:
                print(f"    ❌ Failed: {data.get('retMsg', 'Unknown')}")
                return False
        else:
            print(f"    ❌ HTTP Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False
    
    # Get wallet balance with V5 signature
    print("\n[2/4] Getting wallet balance (V5 auth)...")
    try:
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        
        # V5 signature format
        param_str = f"{timestamp}{API_KEY}{recv_window}"
        signature = hmac.new(
            API_SECRET.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "X-BAPI-API-KEY": API_KEY,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{base_url}/v5/account/wallet-balance?accountType=UNIFIED",
            headers=headers
        )
        
        print(f"    Request URL: {response.url}")
        print(f"    HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            ret_code = data.get('retCode')
            ret_msg = data.get('retMsg', 'Unknown')
            
            print(f"    Response retCode: {ret_code}")
            print(f"    Response retMsg: {ret_msg}")
            
            if ret_code == 0:
                print(f"    ✅ Balance query successful!")
                balances = data.get('result', {}).get('list', [])
                if balances:
                    for balance_info in balances:
                        coins = balance_info.get('coin', [])
                        for coin in coins:
                            wallet_balance = float(coin.get('walletBalance', 0))
                            if wallet_balance > 0:
                                print(f"       💰 {coin.get('coin')}: ${wallet_balance:,.2f}")
                return True
            elif ret_code == 10003:
                print(f"    ❌ API Key invalid or expired")
                return False
            elif ret_code == 10004:
                print(f"    ❌ Signature error - check API secret")
                return False
            elif ret_code == 401:
                print(f"    ❌ Authentication failed")
                return False
        else:
            print(f"    ❌ HTTP Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"    Error response: {error_data}")
            except:
                print(f"    Error response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_env(testnet=False):
    """Update .env file"""
    env_path = '/root/arsenal_git_ready/.env'
    
    print(f"\n{'='*60}")
    print(f"Updating {env_path}...")
    print(f"{'='*60}\n")
    
    with open(env_path, 'w') as f:
        f.write("# Arsenal VPS Trading System - API Configuration\n")
        f.write(f"# Configured: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("# Bybit API Configuration\n")
        f.write(f"BYBIT_API_KEY={API_KEY}\n")
        f.write(f"BYBIT_API_SECRET={API_SECRET}\n")
        f.write(f"BYBIT_TESTNET={str(testnet).lower()}\n\n")
        f.write("# Binance API (optional)\n")
        f.write("# BINANCE_API_KEY=\n")
        f.write("# BINANCE_API_SECRET=\n")
    
    print(f"    ✅ .env updated!")
    print(f"    Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    print(f"    Mode: {'TESTNET' if testnet else 'LIVE'}\n")

# Test
print("\n" + "="*60)
print("Starting V5 API Tests...")
print("="*60)

# Test mainnet first (most likely for real keys)
mainnet_ok = test_v5_api(testnet=False)

if not mainnet_ok:
    print("\nTrying testnet...")
    testnet_ok = test_v5_api(testnet=True)
    if testnet_ok:
        update_env(testnet=True)
else:
    update_env(testnet=False)
    print("\n✅ Keys are valid! Check .env file.")
