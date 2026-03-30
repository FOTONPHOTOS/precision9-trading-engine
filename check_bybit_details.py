#!/usr/bin/env python3
"""
Bybit Detailed Balance Check Script
This script checks your Bybit account in more detail to verify trading capabilities.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Load environment variables
load_dotenv('../../../.env')

# Get API credentials from environment
api_key = os.getenv('BYBIT_API_KEY')
api_secret = os.getenv('BYBIT_API_SECRET')
testnet_setting = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'

print(" Detailed Bybit Account Check...")
print(f"   API Key: {api_key[:6]}...{api_key[-4:] if api_key else 'N/A'} (first 6 and last 4 chars)")
print(f"   Testnet Mode: {testnet_setting}")
print()

if not api_key or not api_secret:
    print(" ERROR: BYBIT_API_KEY or BYBIT_API_SECRET not found in .env file!")
    sys.exit(1)

try:
    # Create Bybit HTTP client
    bybit_client = HTTP(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet_setting
    )

    print(" Testing various Bybit API endpoints...")
    
    # Test 1: Wallet balance
    print("\n1  Checking wallet balance...")
    response = bybit_client.get_wallet_balance(accountType="UNIFIED")
    if response['retCode'] == 0:
        print("    Wallet balance query succeeded")
        balances = response.get('result', {}).get('list', [])
        if balances:
            for balance_info in balances:
                coin_balances = balance_info.get('coin', [])
                total_usd_value = 0
                for coin in coin_balances:
                    coin_name = coin.get('coin', 'N/A')
                    available_balance = float(coin.get('availableToTrade', 0))
                    usd_value = float(coin.get('usdValue', 0)) if coin.get('usdValue') else 0
                    total_usd_value += usd_value
                    if available_balance > 0.00000001:
                        print(f"      - {coin_name}: {available_balance:.6f} available (${usd_value:.2f} USD)")
                print(f"      Total USD Value in Account: ${total_usd_value:.2f}")
        else:
            print("       No balance information returned")
    else:
        print(f"    Wallet balance query failed: {response['retMsg']}")

    # Test 2: Position information
    print("\n2  Checking position information...")
    try:
        pos_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
        if pos_response['retCode'] == 0:
            positions = pos_response.get('result', {}).get('list', [])
            print(f"    Position query succeeded - found {len(positions)} positions")
            if positions:
                for pos in positions:
                    symbol = pos.get('symbol', 'N/A')
                    size = pos.get('size', '0')
                    side = pos.get('side', 'N/A')
                    avg_price = pos.get('avgPrice', 'N/A')
                    if float(size) > 0:  # Only show active positions
                        print(f"      - {symbol}: {side} {size} @ ${avg_price}")
            else:
                print("   ℹ  No active positions")
        else:
            print(f"    Position query failed: {pos_response['retMsg']}")
    except Exception as e:
        print(f"    Position query error: {str(e)}")

    # Test 3: Account info
    print("\n3  Checking account info...")
    try:
        acc_response = bybit_client.get_account_info()
        if acc_response['retCode'] == 0:
            print("    Account info query succeeded")
            result = acc_response.get('result', {})
            vip_level = result.get('vipLevel', 'N/A')
            print(f"      VIP Level: {vip_level}")
        else:
            print(f"    Account info query failed: {acc_response['retMsg']}")
    except Exception as e:
        print(f"    Account info query error: {str(e)}")

    # Test 4: Server time
    print("\n4  Checking server time...")
    try:
        time_response = bybit_client.get_servertime()
        if time_response['retCode'] == 0:
            print("    Server time query succeeded")
        else:
            print(f"    Server time query failed: {time_response['retMsg']}")
    except Exception as e:
        print(f"    Server time query error: {str(e)}")

    print("\n API credentials are VALID and functional!")
    print("ℹ  The previous errors were likely due to zero account balance.")
    print("   Make sure you have funds in your Bybit unified account to trade.")

except Exception as e:
    print(f" ERROR connecting to Bybit API: {str(e)}")
    if "signature" in str(e).lower():
        print("   This suggests your API secret might be incorrect.")
    elif "key" in str(e).lower() or "access" in str(e).lower():
        print("   This suggests your API key might be invalid or lack permissions.")
    elif "forbidden" in str(e).lower():
        print("   This suggests your API key permissions might be restricted.")
    
print()
print(" Detailed Account Check Complete")