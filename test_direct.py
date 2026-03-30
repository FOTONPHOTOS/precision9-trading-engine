#!/usr/bin/env python3
"""
Direct Bybit V5 API test using pybit library (official)
"""

import os
import sys

# Keys
API_KEY = "6Bn3GZevnFnz1oREDY"
API_SECRET = "akZALhRbAFeWokv2e26CQfYwXvCE6BmkN0Xz"

print(f"\n{'='*70}")
print("   BYBIT V5 API - DIRECT TEST WITH PYBIT (Official Library)")
print(f"{'='*70}")
print(f"\nAPI Key: '{API_KEY}'")
print(f"Length: {len(API_KEY)} characters")
print(f"\nAPI Secret: '{API_SECRET}'")  
print(f"Length: {len(API_SECRET)} characters")

# Check if lengths match Bybit's typical format
print(f"\n{'='*70}")
print("   KEY FORMAT CHECK")
print(f"{'='*70}")

# Bybit V5 keys are typically:
# - API Key: 20-30 characters
# - Secret: 40-50 characters
if len(API_KEY) < 20:
    print(f"\n  WARNING: API Key is shorter than typical Bybit keys")
    print(f"   Expected: 20-30 characters")
    print(f"   Got: {len(API_KEY)} characters")
    print(f"\n   Possible issues:")
    print(f"   1. Key was truncated when copying")
    print(f"   2. Key includes invisible characters")
    print(f"   3. This is an old V1/V2 key (V5 keys are longer)")

if len(API_SECRET) < 40:
    print(f"\n  WARNING: API Secret is shorter than typical Bybit secrets")
    print(f"   Expected: 40-50 characters")
    print(f"   Got: {len(API_SECRET)} characters")

print(f"\n{'='*70}")
print("   TESTING...")
print(f"{'='*70}")

from pybit.unified_trading import HTTP

# Test with different configurations
configs = [
    {"testnet": False, "name": "MAINNET"},
    {"testnet": True, "name": "TESTNET"},
]

for config in configs:
    testnet = config["testnet"]
    name = config["name"]
    
    print(f"\n{'='*70}")
    print(f"   Testing {name}")
    print(f"{'='*70}\n")
    
    try:
        # Create client with minimal config
        client = HTTP(
            api_key=API_KEY,
            api_secret=API_SECRET,
            testnet=testnet,
        )
        
        # Test 1: Public endpoint (no auth)
        print("[1/3] Testing public endpoint (server time)...")
        try:
            result = client.get_server_time()
            if result.get('retCode') == 0:
                print(f"     Public API works: {result.get('result', {}).get('timeSecond', 'N/A')}")
            else:
                print(f"     Public API failed: {result.get('retMsg')}")
        except Exception as e:
            print(f"     Error: {e}")
        
        # Test 2: Authenticated endpoint
        print(f"\n[2/3] Testing authenticated endpoint (wallet balance)...")
        try:
            result = client.get_wallet_balance(accountType="UNIFIED")
            ret_code = result.get('retCode')
            ret_msg = result.get('retMsg', 'Unknown')
            
            print(f"    retCode: {ret_code}")
            print(f"    retMsg: {ret_msg}")
            
            if ret_code == 0:
                print(f"     AUTHENTICATION SUCCESSFUL!")
                balances = result.get('result', {}).get('list', [])
                if balances:
                    for bal in balances:
                        coins = bal.get('coin', [])
                        for coin in coins:
                            wb = float(coin.get('walletBalance', 0))
                            if wb > 0:
                                print(f"        {coin.get('coin')}: ${wb:,.2f}")
                print(f"\n KEYS ARE VALID ON {name}!")
                break  # Exit the loop
            elif ret_code == 10003:
                print(f"     API Key invalid/expired")
            elif ret_code == 10004:
                print(f"     Signature error - Secret key mismatch")
                print(f"       Check if secret was copied correctly")
            elif ret_code == 401:
                print(f"     Authentication failed")
            else:
                print(f"     Error code {ret_code}")
                
        except Exception as e:
            print(f"     Exception: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Another auth endpoint
        print(f"\n[3/3] Testing positions endpoint...")
        try:
            result = client.get_positions(category="linear")
            ret_code = result.get('retCode')
            print(f"    retCode: {ret_code}")
            if ret_code == 0:
                print(f"     Positions query works!")
            else:
                print(f"     Positions failed: {result.get('retMsg')}")
        except Exception as e:
            print(f"     Exception: {e}")
            
    except Exception as e:
        print(f" Client creation failed: {e}")

print(f"\n{'='*70}")
print("   RESULT")
print(f"{'='*70}")
print(f"\n API keys did not authenticate successfully")
print(f"\nNext steps:")
print(f"1. Go to Bybit → API Management")
print(f"2. Delete this API key")
print(f"3. Create a NEW API key")
print(f"4. Make sure to copy the ENTIRE key and secret")
print(f"5. V5 API keys should be longer (20+ chars for key, 40+ for secret)")
print(f"\n")
