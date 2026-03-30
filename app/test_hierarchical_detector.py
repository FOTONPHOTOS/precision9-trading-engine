"""
Test script for Hierarchical Trendline Detector

Tests the new multi-timeframe approach:
1. HTF (15M) range detection
2. LTF (1M) swing detection
3. Collinearity analysis
4. RANSAC fitting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
import requests
from hierarchical_trendline_detector import (
    HierarchicalTrendlineDetector,
    CollinearLine,
    SwingPoint
)


def fetch_binance_data(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    """Fetch historical candle data from Binance using requests"""

    print(f"\n[DATA FETCH] Getting {interval} candles for {symbol}...")

    url = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }

    response = requests.get(url, params=params)
    klines = response.json()

    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    # Convert to proper types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    print(f"  Fetched {len(df)} candles")
    print(f"  Time range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    return df


def print_trendline_details(line: CollinearLine, line_num: int):
    """Print detailed information about a trendline"""

    print(f"\n{'='*80}")
    print(f"TRENDLINE #{line_num} - {line.line_type.upper()}")
    print(f"{'='*80}")

    # Basic info
    print(f"\n[LINE EQUATION]")
    print(f"  y = {line.slope:.6f}x + {line.intercept:.2f}")
    print(f"  R² = {line.r_squared:.4f}")
    print(f"  Quality Score = {line.quality_score:.1f}%")
    print(f"  Avg Distance = ${line.avg_distance:.3f}")

    # Start and end
    print(f"\n[START POINT]")
    print(f"  Time: {line.start_point.timestamp.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Price: ${line.start_point.price:.2f}")
    print(f"  Index: {line.start_point.index}")

    print(f"\n[END POINT]")
    print(f"  Time: {line.end_point.timestamp.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Price: ${line.end_point.price:.2f}")
    print(f"  Index: {line.end_point.index}")

    # All touch points
    print(f"\n[TOUCH POINTS] ({len(line.swing_points)} points)")
    for i, point in enumerate(line.swing_points, 1):
        # Calculate expected price at this index
        expected_price = line.slope * point.index + line.intercept
        deviation = abs(point.price - expected_price)
        deviation_pct = (deviation / point.price) * 100

        print(f"  {i}. {point.timestamp.strftime('%Y-%m-%d %H:%M')} @ ${point.price:.2f} "
              f"(deviation: ${deviation:.3f} / {deviation_pct:.3f}%)")

    # Slope direction
    direction = "ASCENDING" if line.slope > 0 else "DESCENDING" if line.slope < 0 else "HORIZONTAL"
    print(f"\n[SLOPE] {direction} ({line.slope:.6f})")


def main():
    print("\n" + "="*80)
    print("HIERARCHICAL TRENDLINE DETECTOR TEST")
    print("="*80)

    # Fetch data
    symbol = "SOLUSDT"

    # Get 15M data (last 500 candles = ~5 days)
    df_15m = fetch_binance_data(symbol, '15m', limit=500)

    # Get 1M data (last 1000 candles = ~16 hours)
    df_1m = fetch_binance_data(symbol, '1m', limit=1000)

    print(f"\n[DATA SUMMARY]")
    print(f"  15M: {len(df_15m)} candles from {df_15m['timestamp'].iloc[0]} to {df_15m['timestamp'].iloc[-1]}")
    print(f"  1M: {len(df_1m)} candles from {df_1m['timestamp'].iloc[0]} to {df_1m['timestamp'].iloc[-1]}")

    # Initialize detector
    detector = HierarchicalTrendlineDetector()

    # Run detection
    results = detector.detect_trendlines(df_15m, df_1m)

    # Get best trendlines
    best_lines = detector.get_best_trendlines(results, max_lines=5)

    print("\n" + "="*80)
    print(f"TOP {len(best_lines)} TRENDLINES BY QUALITY")
    print("="*80)

    for i, line in enumerate(best_lines, 1):
        print_trendline_details(line, i)

    # Print verification instructions
    print("\n" + "="*80)
    print("VERIFICATION INSTRUCTIONS")
    print("="*80)
    print("\nTo verify these trendlines on your TradingView chart:")
    print("1. Open SOLUSDT chart")
    print("2. Switch to 1M timeframe")
    print("3. Draw trendlines using the coordinates above")
    print("4. Check if they align with the actual swing points")
    print("\nIMPORTANT: Adjust for your timezone (Nigeria is UTC+1)")

    # Additional analysis
    print("\n" + "="*80)
    print("HTF RANGES DETECTED")
    print("="*80)

    for i, range_obj in enumerate(results['htf_ranges'], 1):
        print(f"\nRange {i}: {range_obj}")
        ltf_swings = results['ltf_swings_by_range'].get(i, [])
        print(f"  LTF swings in range: {len(ltf_swings)}")
        if ltf_swings:
            print(f"  First swing: {ltf_swings[0]}")
            print(f"  Last swing: {ltf_swings[-1]}")


if __name__ == "__main__":
    main()
