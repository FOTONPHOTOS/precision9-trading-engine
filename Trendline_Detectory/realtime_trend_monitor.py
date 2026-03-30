"""
Real-Time Trend Monitor
=======================

Tells you EXACTLY what trend the market is in RIGHT NOW

Features:
1. Analyzes last 45 minutes of data
2. Detects current active trendline
3. Shows trend direction, strength, and status
4. Warns if trend is about to break
5. Identifies if market is ranging
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from current_trend_detector import CurrentTrendDetector


def fetch_binance_data(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    """Fetch data from Binance"""
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
    """Get current market price"""
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {'symbol': symbol}
    response = requests.get(url, params=params)
    return float(response.json()['price'])


def analyze_realtime_trend(symbol: str = "SOLUSDT", minutes: int = 45):
    """
    Analyze current trend in real-time

    Args:
        symbol: Trading pair
        minutes: Look back this many minutes (45 default)
    """
    print("\n" + "="*80)
    print("REAL-TIME TREND MONITOR")
    print("="*80)
    print(f"Analyzing: {symbol}")
    print(f"Time window: Last {minutes} minutes")

    now = datetime.utcnow()
    print(f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    nigeria_time = now + timedelta(hours=1)
    print(f"Nigeria time: {nigeria_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Fetch 5M data (45 minutes = 9 candles on 5M, but fetch more for context)
    print(f"\n[FETCHING DATA]")
    df_5m = fetch_binance_data(symbol, '5m', limit=200)

    # Get last 45 minutes
    cutoff_time = df_5m['timestamp'].max() - timedelta(minutes=minutes)
    recent_data = df_5m[df_5m['timestamp'] >= cutoff_time].reset_index(drop=True)

    print(f"  Fetched {len(df_5m)} candles total")
    print(f"  Analyzing {len(recent_data)} candles from last {minutes} minutes")
    print(f"  Data range: {recent_data['timestamp'].iloc[0]} to {recent_data['timestamp'].iloc[-1]}")

    # Get current price
    current_price = get_current_price(symbol)
    print(f"\n[CURRENT PRICE] ${current_price:.2f}")

    # Initialize detector
    detector = CurrentTrendDetector(
        swing_lookback=3,
        min_touches=2,
        max_touches=4
    )

    # Detect trend direction on recent data
    print(f"\n[ANALYZING LAST {minutes} MINUTES]")

    # Use the full 5M data but focus analysis on recent candles
    sequences = detector.find_all_trend_sequences(
        df_5m,
        date_filter=None,  # No date filter, use all data
        max_sequences=5    # Find more sequences
    )

    if not sequences:
        print("\n[RESULT] NO CLEAR TREND DETECTED")
        print("  Market appears to be RANGING or insufficient data")
        return

    # Find the MOST RECENT active trendline
    print(f"\n[TREND SEQUENCES FOUND] {len(sequences)} total")

    active_trendline = None
    sequence_with_active = None

    # Check sequences in order (most recent first)
    for seq in sequences:
        # Check if initial trendline is active and recent
        if seq.trendline.state.value == 'active':
            last_touch = seq.trendline.swing_points[-1].timestamp
            # Consider active if last touch within data range
            if last_touch >= recent_data['timestamp'].iloc[0]:
                active_trendline = seq.trendline
                sequence_with_active = seq
                break

        # Check if new trend after break is active
        if seq.new_trend_after_break and seq.new_trend_after_break.state.value == 'active':
            last_touch = seq.new_trend_after_break.swing_points[-1].timestamp
            if last_touch >= recent_data['timestamp'].iloc[0]:
                active_trendline = seq.new_trend_after_break
                sequence_with_active = seq
                break

    if not active_trendline:
        # Use most recent trendline even if not strictly "active"
        print("\n[SEARCHING] No strictly active trend, using most recent...")
        latest_seq = sequences[0]
        if latest_seq.new_trend_after_break:
            active_trendline = latest_seq.new_trend_after_break
        else:
            active_trendline = latest_seq.trendline
        sequence_with_active = latest_seq

    # Print current trend analysis
    print("\n" + "="*80)
    print("CURRENT TREND ANALYSIS")
    print("="*80)

    tl = active_trendline

    # Trend direction
    trend_name = "DOWNTREND (Resistance)" if tl.line_type == 'resistance' else "UPTREND (Support)"
    print(f"\n[TREND DIRECTION] {trend_name}")
    print(f"[STATE] {tl.state.value.upper()}")
    print(f"[QUALITY] R² = {tl.r_squared:.4f} (1.0 = perfect)")

    # Slope analysis
    if tl.slope > 0:
        slope_desc = "ASCENDING (bullish bias)" if tl.line_type == 'support' else "ASCENDING (weakening resistance)"
    elif tl.slope < 0:
        slope_desc = "DESCENDING (bearish bias)" if tl.line_type == 'resistance' else "DESCENDING (weakening support)"
    else:
        slope_desc = "HORIZONTAL"

    print(f"[SLOPE] {tl.slope:.6f} - {slope_desc}")

    # Touch points
    print(f"\n[TRENDLINE TOUCH POINTS] {len(tl.swing_points)} touches")
    for i, swing in enumerate(tl.swing_points, 1):
        nigeria_time = swing.timestamp + timedelta(hours=1)
        time_ago = (now - swing.timestamp.to_pydatetime()).total_seconds() / 60
        print(f"  {i}. {nigeria_time.strftime('%H:%M')} @ ${swing.price:.2f} ({time_ago:.0f} mins ago)")

    # Calculate distance from current price to trendline
    # Use most recent index in dataframe
    latest_index = len(df_5m) - 1
    expected_price = tl.price_at_index(latest_index)
    distance = current_price - expected_price
    distance_pct = (distance / current_price) * 100

    print(f"\n[CURRENT POSITION]")
    print(f"  Current price: ${current_price:.2f}")
    print(f"  Trendline at current position: ${expected_price:.2f}")
    print(f"  Distance: ${distance:.2f} ({distance_pct:+.2f}%)")

    # Proximity analysis
    if tl.line_type == 'resistance':
        if distance > 0:
            print(f"  Status: ABOVE resistance (broken or testing)")
        elif abs(distance_pct) < 0.5:
            print(f"  Status: AT resistance (high probability rejection)")
        else:
            print(f"  Status: BELOW resistance (trend intact)")
    else:  # support
        if distance < 0:
            print(f"  Status: BELOW support (broken or testing)")
        elif abs(distance_pct) < 0.5:
            print(f"  Status: AT support (high probability bounce)")
        else:
            print(f"  Status: ABOVE support (trend intact)")

    # Break warning
    print(f"\n[BREAK ANALYSIS]")
    if tl.state.value == 'broken':
        print(f"  WARNING: Trendline was BROKEN at {tl.break_timestamp.strftime('%H:%M')}")
        print(f"  Break price: ${tl.break_price:.2f}")

        # Check if new trend formed
        if sequence_with_active and sequence_with_active.new_trend_after_break:
            print(f"\n  NEW TREND FORMED: {sequence_with_active.new_trend_after_break.line_type.upper()}")
    else:
        # Check how close to breaking
        if tl.line_type == 'resistance':
            if distance_pct > -0.2:  # Within 0.2% of resistance
                print(f"  WARNING: Price is VERY CLOSE to breaking resistance")
                print(f"  Break if closes above ${expected_price:.2f}")
            else:
                print(f"  Trendline intact, no immediate break threat")
        else:  # support
            if distance_pct < 0.2:  # Within 0.2% of support
                print(f"  WARNING: Price is VERY CLOSE to breaking support")
                print(f"  Break if closes below ${expected_price:.2f}")
            else:
                print(f"  Trendline intact, no immediate break threat")

    # Trading implications
    print(f"\n[TRADING IMPLICATIONS]")
    if tl.line_type == 'resistance' and tl.state.value == 'active':
        print(f"  - Market in DOWNTREND")
        print(f"  - Resistance at ${expected_price:.2f}")
        print(f"  - SHORT bias until resistance breaks")
        print(f"  - Watch for rejection if price approaches ${expected_price:.2f}")
    elif tl.line_type == 'support' and tl.state.value == 'active':
        print(f"  - Market in UPTREND")
        print(f"  - Support at ${expected_price:.2f}")
        print(f"  - LONG bias until support breaks")
        print(f"  - Watch for bounce if price approaches ${expected_price:.2f}")

    # Recent price action
    print(f"\n[RECENT PRICE ACTION - Last 45 mins]")
    high_45m = recent_data['high'].max()
    low_45m = recent_data['low'].min()
    open_45m = recent_data['open'].iloc[0]
    close_45m = recent_data['close'].iloc[-1]
    change_45m = close_45m - open_45m
    change_pct_45m = (change_45m / open_45m) * 100

    print(f"  Open (45m ago): ${open_45m:.2f}")
    print(f"  High: ${high_45m:.2f}")
    print(f"  Low: ${low_45m:.2f}")
    print(f"  Close (now): ${close_45m:.2f}")
    print(f"  Change: ${change_45m:+.2f} ({change_pct_45m:+.2f}%)")

    # Momentum
    if change_pct_45m > 1.0:
        print(f"  Momentum: STRONG BULLISH")
    elif change_pct_45m > 0.3:
        print(f"  Momentum: MODERATE BULLISH")
    elif change_pct_45m > -0.3:
        print(f"  Momentum: NEUTRAL/RANGING")
    elif change_pct_45m > -1.0:
        print(f"  Momentum: MODERATE BEARISH")
    else:
        print(f"  Momentum: STRONG BEARISH")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY - WHAT TREND ARE WE IN?")
    print("="*80)

    if tl.line_type == 'resistance':
        print(f"\nCurrent Trend: DOWNTREND")
        print(f"Key Level: RESISTANCE @ ${expected_price:.2f}")
        print(f"Bias: BEARISH (expect lower prices)")
    else:
        print(f"\nCurrent Trend: UPTREND")
        print(f"Key Level: SUPPORT @ ${expected_price:.2f}")
        print(f"Bias: BULLISH (expect higher prices)")

    print(f"\nPrice now: ${current_price:.2f}")
    print(f"Distance from trend: {distance_pct:+.2f}%")

    if abs(distance_pct) < 0.5:
        print(f"Status: AT KEY LEVEL - Watch for reaction!")
    elif tl.line_type == 'resistance' and distance > 0:
        print(f"Status: ABOVE resistance - Potential breakout or retest")
    elif tl.line_type == 'support' and distance < 0:
        print(f"Status: BELOW support - Potential breakdown or retest")
    else:
        print(f"Status: Trend intact, away from key level")

    print("\n" + "="*80)


if __name__ == "__main__":
    analyze_realtime_trend("SOLUSDT", minutes=45)
