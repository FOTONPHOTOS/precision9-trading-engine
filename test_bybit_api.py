#!/usr/bin/env python3
"""
Bybit API Test Script
This script tests your Bybit API credentials to see if they work properly.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Load environment variables
load_dotenv('../../../.env')  # Navigate to project root to find .env

# Get API credentials from environment
api_key = os.getenv('BYBIT_API_KEY')
api_secret = os.getenv('BYBIT_API_SECRET')
testnet_setting = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'

print(" Testing Bybit API Connection...")
print(f"   API Key: {api_key}")
print(f"   API Secret: {'*' * len(api_secret) if api_secret else 'None'}")  # Hide secret for security
print(f"   Testnet Mode: {testnet_setting}")
print()

if not api_key or not api_secret:
    print(" ERROR: BYBIT_API_KEY or BYBIT_API_SECRET not found in .env file!")
    print("   Please check your .env file and ensure both BYBIT_API_KEY and BYBIT_API_SECRET are properly set.")
    sys.exit(1)

try:
    # Create Bybit HTTP client
    bybit_client = HTTP(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet_setting  # Use testnet if enabled, otherwise mainnet
    )

    print(" Attempting to connect to Bybit API...")
    
    # Test connection by fetching account balance
    response = bybit_client.get_wallet_balance(accountType="UNIFIED")
    
    if response['retCode'] == 0:
        print(" SUCCESS: Connected to Bybit API!")
        print(f"   Response Code: {response['retCode']} ({response['retMsg']})")
        
        # Display balance information
        balances = response.get('result', {}).get('list', [])
        if balances:
            print("\n Account Balances:")
            for balance_info in balances:
                coin_balances = balance_info.get('coin', [])
                for coin in coin_balances:
                    if float(coin.get('availableToTrade', 0)) > 0.00000001:  # Only show non-zero balances
                        print(f"   - {coin.get('coin', 'N/A')}: {coin.get('availableToTrade', 'N/A')} ({coin.get('usdValue', 'N/A')} USD)")
        else:
            print("   No balance information returned")
    else:
        print(f" API Error: {response['retMsg']} (Code: {response['retCode']})")
        if response['retCode'] == '10003':  # Invalid API key
            print("   This suggests your API key is invalid or truncated.")
        elif response['retCode'] in ['10001', '10002']:  # Invalid signature or request
            print("   This suggests your API secret is incorrect or truncated.")
        
except Exception as e:
    print(f" ERROR: {str(e)}")
    print()
    print("  Common Issues:")
    print("   - Truncated API key or secret in .env file")
    print("   - Incorrect API key permissions")
    print("   - Wrong testnet/mainnet setting")
    print("   - Network connectivity issues")
    
print()
print(" API Test Complete")