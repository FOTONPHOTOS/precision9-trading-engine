"""
15M Resistance Zone / Lower High Swing Detector

Finds the LAST resistance zone or lower high swing on 15M chart
"""

import pandas as pd
import requests
from datetime import datetime, timedelta


def fetch_binance_data(symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    response = requests.get(url, params=params)
    klines = response.json()

    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df


def get_current_price(symbol: str) -> float:
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {'symbol': symbol}
    response = requests.get(url, params=params)
    return float(response.json()['price'])


def detect_15m_swing_highs(symbol: str = "SOLUSDT", lookback_bars: int = 5):
    """
    Detect swing highs on 15M chart

    Args:
        lookback_bars: How many bars on each side to compare (5 for 15M = ~75 mins each side)
    """

    print("\n" + "="*80)
    print("15M RESISTANCE ZONE / LOWER HIGH SWING DETECTOR")
    print("="*80)

    now = datetime.utcnow()
    nigeria_time = now + timedelta(hours=1)
    print(f"\nCurrent time: {nigeria_time.strftime('%Y-%m-%d %H:%M:%S')} (Nigeria UTC+1)")

    # Fetch 15M data
    print(f"\n[FETCHING 15M DATA]")
    df = fetch_binance_data(symbol, '15m', limit=100)

    print(f"  Fetched {len(df)} candles")
    print(f"  Time range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    # Get current price
    current_price = get_current_price(symbol)
    print(f"\n[CURRENT PRICE] ${current_price:.2f}")

    # Detect swing highs
    print(f"\n[DETECTING SWING HIGHS ON 15M]")
    print(f"  Lookback: {lookback_bars} bars each side (~{lookback_bars * 15} minutes)")

    swing_highs = []

    for i in range(lookback_bars, len(df) - lookback_bars):
        current_high = df.iloc[i]['high']

        # Check if highest in the window
        is_swing_high = all(
            current_high >= df.iloc[j]['high']
            for j in range(i - lookback_bars, i + lookback_bars + 1)
            if j != i
        )

        if is_swing_high:
            swing_highs.append({
                'index': i,
                'timestamp': df.iloc[i]['timestamp'],
                'price': current_high,
                'candle_close': df.iloc[i]['close'],
                'candle_open': df.iloc[i]['open']
            })

    print(f"  Found {len(swing_highs)} swing highs")

    if not swing_highs:
        print("\n  No swing highs detected with current parameters")
        return

    # Display all swing highs
    print(f"\n{'='*80}")
    print("ALL SWING HIGHS (15M CHART)")
    print("="*80)

    for i, swing in enumerate(swing_highs, 1):
        nigeria_t = swing['timestamp'] + timedelta(hours=1)
        time_ago = (now - swing['timestamp'].to_pydatetime()).total_seconds() / 60

        print(f"\n{i}. {nigeria_t.strftime('%Y-%m-%d %H:%M')} ({time_ago:.0f} mins ago)")
        print(f"   High: ${swing['price']:.2f}")
        print(f"   Close: ${swing['candle_close']:.2f}")
        print(f"   Candle: {'Bullish' if swing['candle_close'] > swing['candle_open'] else 'Bearish'}")

    # Find LAST swing high (most recent)
    last_swing = swing_highs[-1]

    print(f"\n{'='*80}")
    print("LAST RESISTANCE ZONE / LOWER HIGH SWING")
    print("="*80)

    nigeria_t = last_swing['timestamp'] + timedelta(hours=1)
    time_ago = (now - last_swing['timestamp'].to_pydatetime()).total_seconds() / 60

    print(f"\nTime: {nigeria_t.strftime('%Y-%m-%d %H:%M')} Nigeria time")
    print(f"UTC: {last_swing['timestamp'].strftime('%Y-%m-%d %H:%M')}")
    print(f"Time ago: {time_ago:.0f} minutes ({time_ago/60:.1f} hours)")

    print(f"\n[PRICE DETAILS]")
    print(f"  Swing High: ${last_swing['price']:.2f}")
    print(f"  Candle Close: ${last_swing['candle_close']:.2f}")
    print(f"  Candle Open: ${last_swing['candle_open']:.2f}")

    candle_type = "Bullish (green)" if last_swing['candle_close'] > last_swing['candle_open'] else "Bearish (red)"
    print(f"  Candle Type: {candle_type}")

    # Check if this is a lower high (downtrend confirmation)
    print(f"\n[LOWER HIGH ANALYSIS]")
    if len(swing_highs) >= 2:
        previous_swing = swing_highs[-2]
        is_lower_high = last_swing['price'] < previous_swing['price']

        print(f"  Previous swing high: ${previous_swing['price']:.2f}")
        print(f"  This swing high: ${last_swing['price']:.2f}")
        print(f"  Difference: ${last_swing['price'] - previous_swing['price']:.2f}")

        if is_lower_high:
            print(f"  Status: LOWER HIGH - Downtrend continuation")
        else:
            print(f"  Status: HIGHER HIGH - Potential uptrend")
    else:
        print(f"  Not enough swing highs to determine if lower high")

    # Current position relative to resistance
    print(f"\n[CURRENT POSITION]")
    print(f"  Current price: ${current_price:.2f}")
    print(f"  Last resistance: ${last_swing['price']:.2f}")

    distance = current_price - last_swing['price']
    distance_pct = (distance / current_price) * 100

    print(f"  Distance: ${distance:.2f} ({distance_pct:+.2f}%)")

    if distance > 0:
        print(f"  Status: ABOVE last resistance (broken or retesting)")
    elif abs(distance_pct) < 0.5:
        print(f"  Status: AT resistance zone (high probability rejection)")
    else:
        print(f"  Status: BELOW resistance ({abs(distance_pct):.2f}% away)")

    # Check all recent swing highs for resistance zone
    print(f"\n{'='*80}")
    print("RESISTANCE ZONE ANALYSIS (Last 5 Swings)")
    print("="*80)

    recent_swings = swing_highs[-5:] if len(swing_highs) >= 5 else swing_highs

    print(f"\nRecent swing highs forming resistance zone:")
    for i, swing in enumerate(reversed(recent_swings), 1):
        nigeria_t = swing['timestamp'] + timedelta(hours=1)
        time_ago = (now - swing['timestamp'].to_pydatetime()).total_seconds() / 60
        print(f"  {i}. {nigeria_t.strftime('%H:%M')} @ ${swing['price']:.2f} ({time_ago:.0f}m ago)")

    # Calculate resistance zone range
    prices = [s['price'] for s in recent_swings]
    zone_high = max(prices)
    zone_low = min(prices)
    zone_mid = (zone_high + zone_low) / 2

    print(f"\nResistance Zone:")
    print(f"  Upper: ${zone_high:.2f}")
    print(f"  Mid: ${zone_mid:.2f}")
    print(f"  Lower: ${zone_low:.2f}")
    print(f"  Width: ${zone_high - zone_low:.2f}")

    # Trading implications
    print(f"\n{'='*80}")
    print("TRADING IMPLICATIONS")
    print("="*80)

    print(f"\nLast Resistance: ${last_swing['price']:.2f}")
    print(f"Current Price: ${current_price:.2f}")

    if distance_pct > 0.5:
        print(f"\nStatus: Price ABOVE resistance")
        print(f"  - Potential breakout")
        print(f"  - Watch for retest of ${last_swing['price']:.2f} as new support")
        print(f"  - If holds above, bullish continuation likely")
    elif distance_pct > -0.5:
        print(f"\nStatus: Price AT resistance zone")
        print(f"  - High probability rejection point")
        print(f"  - SHORT opportunity if rejection confirmed")
        print(f"  - Watch for reversal patterns (bearish engulfing, shooting star)")
    else:
        print(f"\nStatus: Price BELOW resistance")
        print(f"  - Resistance at ${last_swing['price']:.2f}")
        print(f"  - {abs(distance_pct):.2f}% away")
        print(f"  - SHORT bias until resistance breaks")
        print(f"  - Watch for price to rally toward resistance for short entry")

    print("\n" + "="*80)


if __name__ == "__main__":
    detect_15m_swing_highs("SOLUSDT", lookback_bars=5)
