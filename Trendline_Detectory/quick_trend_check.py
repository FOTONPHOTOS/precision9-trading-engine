"""
Quick Trend Check - Last 45 Minutes ONLY

Simple, focused analysis of CURRENT trend
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


def analyze_last_45_minutes(symbol: str = "SOLUSDT"):
    """Simple analysis of last 45 minutes"""

    print("\n" + "="*80)
    print("QUICK TREND CHECK - LAST 45 MINUTES")
    print("="*80)

    now = datetime.utcnow()
    nigeria_time = now + timedelta(hours=1)
    print(f"\nCurrent time: {nigeria_time.strftime('%Y-%m-%d %H:%M:%S')} (Nigeria UTC+1)")

    # Fetch 5M data (45 mins = 9 candles)
    df = fetch_binance_data(symbol, '5m', limit=20)

    # Get last 45 minutes
    cutoff = df['timestamp'].max() - timedelta(minutes=45)
    recent = df[df['timestamp'] >= cutoff].copy()

    print(f"\nAnalyzing {len(recent)} candles from last 45 minutes")
    print(f"From: {(recent['timestamp'].iloc[0] + timedelta(hours=1)).strftime('%H:%M')}")
    print(f"To:   {(recent['timestamp'].iloc[-1] + timedelta(hours=1)).strftime('%H:%M')}")

    # Current price
    current_price = get_current_price(symbol)
    print(f"\n{'='*80}")
    print(f"CURRENT PRICE: ${current_price:.2f}")
    print(f"{'='*80}")

    # Price action analysis
    open_price = recent['open'].iloc[0]
    high_price = recent['high'].max()
    low_price = recent['low'].min()
    close_price = recent['close'].iloc[-1]

    change = close_price - open_price
    change_pct = (change / open_price) * 100

    print(f"\n[PRICE ACTION - Last 45 Minutes]")
    print(f"  Open (45m ago):  ${open_price:.2f}")
    print(f"  High:            ${high_price:.2f}")
    print(f"  Low:             ${low_price:.2f}")
    print(f"  Close (now):     ${close_price:.2f}")
    print(f"  Change:          ${change:+.2f} ({change_pct:+.2f}%)")

    # Detect swing highs and lows in last 45 mins
    highs = []
    lows = []

    for i in range(1, len(recent) - 1):
        # Swing high
        if (recent['high'].iloc[i] > recent['high'].iloc[i-1] and
            recent['high'].iloc[i] > recent['high'].iloc[i+1]):
            highs.append({
                'time': recent['timestamp'].iloc[i],
                'price': recent['high'].iloc[i]
            })

        # Swing low
        if (recent['low'].iloc[i] < recent['low'].iloc[i-1] and
            recent['low'].iloc[i] < recent['low'].iloc[i+1]):
            lows.append({
                'time': recent['timestamp'].iloc[i],
                'price': recent['low'].iloc[i]
            })

    print(f"\n[SWING POINTS]")
    print(f"  Swing Highs: {len(highs)}")
    for h in highs:
        t = (h['time'] + timedelta(hours=1)).strftime('%H:%M')
        print(f"    {t} @ ${h['price']:.2f}")

    print(f"  Swing Lows: {len(lows)}")
    for l in lows:
        t = (l['time'] + timedelta(hours=1)).strftime('%H:%M')
        print(f"    {t} @ ${l['price']:.2f}")

    # Trend determination
    print(f"\n{'='*80}")
    print("TREND ANALYSIS")
    print("="*80)

    # Check if making higher highs and higher lows
    if len(highs) >= 2 and len(lows) >= 2:
        higher_highs = highs[-1]['price'] > highs[0]['price']
        higher_lows = lows[-1]['price'] > lows[0]['price']
        lower_highs = highs[-1]['price'] < highs[0]['price']
        lower_lows = lows[-1]['price'] < lows[0]['price']

        if higher_highs and higher_lows:
            trend = "UPTREND"
            trend_desc = "Making higher highs and higher lows"
            bias = "BULLISH"
        elif lower_highs and lower_lows:
            trend = "DOWNTREND"
            trend_desc = "Making lower highs and lower lows"
            bias = "BEARISH"
        elif higher_highs and lower_lows:
            trend = "EXPANDING RANGE"
            trend_desc = "Increasing volatility, no clear direction"
            bias = "NEUTRAL"
        elif lower_highs and higher_lows:
            trend = "CONTRACTING RANGE"
            trend_desc = "Decreasing volatility, compression"
            bias = "NEUTRAL"
        else:
            trend = "RANGING"
            trend_desc = "No clear directional movement"
            bias = "NEUTRAL"
    else:
        # Simple trend based on price change
        if change_pct > 0.5:
            trend = "UPTREND"
            trend_desc = "Price moving higher"
            bias = "BULLISH"
        elif change_pct < -0.5:
            trend = "DOWNTREND"
            trend_desc = "Price moving lower"
            bias = "BEARISH"
        else:
            trend = "RANGING"
            trend_desc = "Sideways movement"
            bias = "NEUTRAL"

    print(f"\n[CURRENT TREND] {trend}")
    print(f"  Description: {trend_desc}")
    print(f"  Bias: {bias}")

    # Momentum
    print(f"\n[MOMENTUM]")
    if change_pct > 1.0:
        momentum = "STRONG BULLISH"
    elif change_pct > 0.3:
        momentum = "MODERATE BULLISH"
    elif change_pct > -0.3:
        momentum = "NEUTRAL"
    elif change_pct > -1.0:
        momentum = "MODERATE BEARISH"
    else:
        momentum = "STRONG BEARISH"

    print(f"  {momentum} ({change_pct:+.2f}%)")

    # Key levels
    print(f"\n[KEY LEVELS - Last 45 Minutes]")
    print(f"  Resistance: ${high_price:.2f}")
    print(f"  Support:    ${low_price:.2f}")
    print(f"  Range:      ${high_price - low_price:.2f} ({((high_price - low_price)/low_price)*100:.2f}%)")

    # Current position
    mid_point = (high_price + low_price) / 2
    position_in_range = ((current_price - low_price) / (high_price - low_price)) * 100

    print(f"\n[CURRENT POSITION]")
    print(f"  Price: ${current_price:.2f}")
    print(f"  Position in range: {position_in_range:.0f}%")

    if position_in_range > 80:
        print(f"  Status: NEAR TOP of range (resistance zone)")
    elif position_in_range > 60:
        print(f"  Status: UPPER RANGE (above mid-point)")
    elif position_in_range > 40:
        print(f"  Status: MID RANGE (neutral zone)")
    elif position_in_range > 20:
        print(f"  Status: LOWER RANGE (below mid-point)")
    else:
        print(f"  Status: NEAR BOTTOM of range (support zone)")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY - WHAT'S HAPPENING NOW?")
    print("="*80)

    print(f"\nTrend: {trend}")
    print(f"Momentum: {momentum}")
    print(f"Bias: {bias}")
    print(f"\nPrice Action:")
    print(f"  Started 45m ago @ ${open_price:.2f}")
    print(f"  Now @ ${current_price:.2f}")
    print(f"  Change: ${change:+.2f} ({change_pct:+.2f}%)")

    print(f"\nKey Levels:")
    print(f"  Immediate resistance: ${high_price:.2f}")
    print(f"  Immediate support: ${low_price:.2f}")

    if bias == "BULLISH":
        print(f"\nTrading Bias: LONG")
        print(f"  Watch for pullbacks to support around ${low_price:.2f}")
        print(f"  Target: Break above ${high_price:.2f}")
    elif bias == "BEARISH":
        print(f"\nTrading Bias: SHORT")
        print(f"  Watch for rallies to resistance around ${high_price:.2f}")
        print(f"  Target: Break below ${low_price:.2f}")
    else:
        print(f"\nTrading Bias: WAIT")
        print(f"  Market ranging, wait for breakout")
        print(f"  Break above ${high_price:.2f} = bullish")
        print(f"  Break below ${low_price:.2f} = bearish")

    print("\n" + "="*80)


if __name__ == "__main__":
    analyze_last_45_minutes("SOLUSDT")
