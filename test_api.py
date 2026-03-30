#!/usr/bin/env python3

import asyncio
import json
from binance import AsyncClient

async def test_api():
    client = await AsyncClient.create(testnet=True)  # Use testnet to avoid live trading issues
    
    # Test with a common symbol
    symbol = "BTCUSDT"
    period = "5m"
    limit = 20
    
    print(f"Testing futures_global_longshort_ratio for {symbol}")
    
    try:
        # Call the method
        result = await client.futures_global_longshort_ratio(symbol=symbol, period=period, limit=limit)
        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)}")
        if result:
            print(f"First entry type: {type(result[0])}")
            print(f"First entry keys: {result[0].keys() if isinstance(result[0], dict) else 'Not a dict'}")
            print(f"First entry content: {json.dumps(result[0], indent=2)}")
    except Exception as e:
        print(f"Error calling futures_global_longshort_ratio: {e}")
    
    await client.close_connection()

if __name__ == "__main__":
    asyncio.run(test_api())