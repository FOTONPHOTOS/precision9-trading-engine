"""
Test Current Trend Detector with Multiple Sequences

Features:
1. Finds CURRENT trend market is in (even if started yesterday)
2. Detects MULTIPLE trend sequences
3. Date filtering to focus on recent trends
4. Shows initial trend + new trend after break
"""

import pandas as pd
import requests
from current_trend_detector import CurrentTrendDetector


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
    print("CURRENT TREND DETECTOR TEST - MULTIPLE SEQUENCES")
    print("="*80)

    symbol = "SOLUSDT"

    # Fetch 5M data (get more data to capture trends that started yesterday)
    df_5m = fetch_binance_data(symbol, '5m', limit=1000)

    print(f"\n[DATA SUMMARY]")
    print(f"  5M: {len(df_5m)} candles (~{len(df_5m)*5/60:.1f} hours)")
    print(f"  Covers: {df_5m['timestamp'].iloc[0].date()} to {df_5m['timestamp'].iloc[-1].date()}")

    # Initialize detector
    detector = CurrentTrendDetector(
        swing_lookback=3,  # 3 bars on each side for 5M
        min_touches=2,
        max_touches=4
    )

    # Find all trend sequences with date filter
    # Focus on Oct 9, but include Oct 8 to capture long trends
    date_filter = "2025-10-09"

    sequences = detector.find_all_trend_sequences(
        df_5m,
        date_filter=date_filter,
        max_sequences=10  # Find up to 10 trend sequences
    )

    # Print each sequence
    for i, sequence in enumerate(sequences, 1):
        detector.print_sequence(sequence, i)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nTotal sequences detected: {len(sequences)}")

    for i, seq in enumerate(sequences, 1):
        if seq.new_trend_after_break:
            print(f"\n{i}. {seq.trendline.line_type.upper()} -> BREAK -> {seq.new_trend_after_break.line_type.upper()}")
        else:
            print(f"\n{i}. {seq.trendline.line_type.upper()} ({seq.trendline.state.value})")

    print("\n" + "="*80)
    print("VERIFICATION INSTRUCTIONS")
    print("="*80)
    print("\n1. Open TradingView -> SOLUSDT -> 5M timeframe")
    print(f"2. Navigate to {date_filter}")
    print("3. You should see the trend sequences listed above")
    print("4. Each sequence shows:")
    print("   - Initial trendline (with touches)")
    print("   - Break point (if broken)")
    print("   - New trend after break (if formed)")
    print("\n5. The FIRST sequence is the CURRENT/ACTIVE trend market is in NOW")
    print("6. Trend may have started on previous day (that's expected for long trends)")


if __name__ == "__main__":
    main()
