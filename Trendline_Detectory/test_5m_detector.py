"""
Test 5M Trendline Detector

The sweet spot between:
- 1M (too many swings, too noisy)
- 15M (too coarse for precision)
"""

import pandas as pd
import requests
from five_minute_trendline_detector import FiveMinuteTrendlineDetector


def fetch_binance_data(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    """Fetch data from Binance"""
    print(f"\n[DATA FETCH] Getting {interval} candles for {symbol}...")

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

    print(f"  Fetched {len(df)} candles")
    print(f"  Time range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    return df


def main():
    print("\n" + "="*80)
    print("5-MINUTE TRENDLINE DETECTOR TEST")
    print("="*80)

    symbol = "SOLUSDT"

    # Fetch data (get more 5M data to capture earlier swings)
    df_15m = fetch_binance_data(symbol, '15m', limit=200)
    df_5m = fetch_binance_data(symbol, '5m', limit=1000)

    print(f"\n[DATA SUMMARY]")
    print(f"  15M: {len(df_15m)} candles (~{len(df_15m)*15/60/24:.1f} days)")
    print(f"  5M: {len(df_5m)} candles (~{len(df_5m)*5/60:.1f} hours)")

    # Initialize detector
    detector = FiveMinuteTrendlineDetector(
        swing_lookback=3,  # 3 bars on each side for 5M
        min_touches=2,     # Minimum 2 touches
        max_touches=3      # Maximum 3 touches before expecting break
    )

    # Run detection (use more bars to capture Oct 9 trendline starting at 00:20 UTC)
    # Let's use all available 5M data
    trendlines = detector.detect(df_15m, df_5m, recent_5m_bars=500)

    # Print results for each trendline
    for i, trendline in enumerate(trendlines, 1):
        print(f"\n{'='*80}")
        print(f"TRENDLINE #{i}")
        print(f"{'='*80}")
        detector.print_results(trendline)

    print("\n" + "="*80)
    print("VERIFICATION INSTRUCTIONS")
    print("="*80)
    print("\n1. Open TradingView -> SOLUSDT -> 5M timeframe")
    print("2. Navigate to the times shown above")
    print("3. You should see TWO trendlines:")
    print("   - INITIAL trend (resistance for downtrend)")
    print("   - NEW trend after break (support for uptrend)")
    print("4. Verify if both lines match your manual analysis")
    print("\nExpected: Initial trend breaks, then new opposite trend forms")


if __name__ == "__main__":
    main()
