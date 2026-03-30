"""
Real-Time Swing Detector - Finds the MOST RECENT Swing High/Low

Critical Fix:
- Don't look 6 hours back
- Find swings in the LAST 1-2 hours only
- Detect breaks immediately
- Catch new swings forming AFTER breaks
"""

import pandas as pd
import asyncio # Added for async operations
import logging
from binance import AsyncClient # Added for AsyncClient
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

async def fetch_binance_data(client: AsyncClient, symbol: str, interval: str, limit: int = 100, retries: int = 3, delay: int = 5, endTime: int = None) -> pd.DataFrame:
    """
    Fetches historical k-line data from Binance using an AsyncClient with a retry mechanism.
    """
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    if endTime is not None:
        params['endTime'] = endTime
    
    for attempt in range(retries):
        try:
            klines = await client.get_klines(**params)

            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df
        
        except Exception as e: # Catch broader exceptions for async client
            logging.warning(f"Failed to fetch Binance data on attempt {attempt + 1}/{retries}. Error: {e}")
            if attempt < retries - 1:
                logging.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay) # Use asyncio.sleep for async
            else:
                logging.error("All attempts to fetch Binance data failed. Returning empty DataFrame.")
                # We will not re-raise the exception, allowing the application to continue.
                # The calling function will handle the empty DataFrame.

    return pd.DataFrame() # Return an empty DataFrame if all retries fail


async def get_current_price(client: AsyncClient, symbol: str, retries: int = 3, delay: int = 5) -> float:
    """
    Fetches the current price for a symbol from Binance using an AsyncClient with a retry mechanism.
    """
    for attempt in range(retries):
        try:
            ticker = await client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        
        except Exception as e:
            logging.warning(f"Failed to fetch current price on attempt {attempt + 1}/{retries}. Error: {e}")
            if attempt < retries - 1:
                logging.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logging.error("All attempts to fetch the current price failed.")
                return None # Return None on failure
    
    return None # Should be reached only after all retries fail


def detect_candle_close_patterns(df: pd.DataFrame, lookback_bars: int = 20):
    """
    Detect early break signals from candle close patterns with emphasis on recent momentum.

    Bullish Break Signal: Bullish candle closes ABOVE a previous bearish candle's high
    Bearish Break Signal: Bearish candle closes BELOW a previous bullish candle's low

    These patterns often precede trend line breaks and serve as early warnings.

    Args:
        df: DataFrame with OHLC data
        lookback_bars: How many bars to look back for pattern matching

    Returns:
        List of detected patterns with timestamps, prices, and signal type
    """
    patterns = []

    for i in range(lookback_bars, len(df)):
        current_candle = df.iloc[i]
        current_open = current_candle['open']
        current_close = current_candle['close']
        current_high = current_candle['high']
        current_low = current_candle['low']

        # Determine if current candle is bullish or bearish
        is_bullish = current_close > current_open
        is_bearish = current_close < current_open

        if not (is_bullish or is_bearish):
            continue  # Skip doji candles

        # Look back for opposite-direction candles
        for j in range(max(0, i - lookback_bars), i):
            prev_candle = df.iloc[j]
            prev_open = prev_candle['open']
            prev_close = prev_candle['close']
            prev_high = prev_candle['high']
            prev_low = prev_candle['low']

            prev_is_bullish = prev_close > prev_open
            prev_is_bearish = prev_close < prev_open

            # BULLISH BREAK SIGNAL: Current bullish candle closes ABOVE previous bearish candle's high
            if is_bullish and prev_is_bearish:
                if current_close > prev_high:
                    # Calculate the strength of the break
                    break_distance = current_close - prev_high
                    break_pct = (break_distance / prev_high) * 100

                    # Check if this is a significant break (> 0.1%)
                    if break_pct > 0.1:
                        # NEW: Add momentum strength indicator based on bar distance
                        momentum_strength = 1.0 + (0.1 * max(0, 5 - (i - j)))  # Closer bars = stronger momentum
                        patterns.append({
                            'type': 'BULLISH_BREAK',
                            'timestamp': current_candle.name, # Use the index (timestamp)
                            'current_close': current_close,
                            'prev_high': prev_high,
                            'prev_timestamp': prev_candle.name, # Use the index (timestamp)
                            'break_distance': break_distance,
                            'break_pct': break_pct,
                            'bars_apart': i - j,
                            'momentum_strength': momentum_strength  # NEW: For weighting recent patterns
                        })
                        break  # Found pattern for this candle, move to next

            # BEARISH BREAK SIGNAL: Current bearish candle closes BELOW previous bullish candle's low
            elif is_bearish and prev_is_bullish:
                if current_close < prev_low:
                    # Calculate the strength of the break
                    break_distance = prev_low - current_close
                    break_pct = (break_distance / prev_low) * 100

                    # Check if this is a significant break (> 0.1%)
                    if break_pct > 0.1:
                        # NEW: Add momentum strength indicator based on bar distance
                        momentum_strength = 1.0 + (0.1 * max(0, 5 - (i - j)))  # Closer bars = stronger momentum
                        patterns.append({
                            'type': 'BEARISH_BREAK',
                            'timestamp': current_candle.name, # Use the index (timestamp)
                            'current_close': current_close,
                            'prev_low': prev_low,
                            'prev_timestamp': prev_candle.name, # Use the index (timestamp)
                            'break_distance': break_distance,
                            'break_pct': break_pct,
                            'bars_apart': i - j,
                            'momentum_strength': momentum_strength  # NEW: For weighting recent patterns
                        })
                        break  # Found pattern for this candle, move to next

    # NEW: Sort patterns by timestamp to help identify momentum direction changes
    patterns.sort(key=lambda x: x['timestamp'], reverse=False)  # Oldest first
    
    # NEW: Add a function to detect recent momentum changes
    if len(patterns) >= 3:
        recent_patterns = patterns[-3:]  # Last 3 patterns
        bullish_count = sum(1 for p in recent_patterns if p['type'] == 'BULLISH_BREAK')
        bearish_count = sum(1 for p in recent_patterns if p['type'] == 'BEARISH_BREAK')
        
        # Add a momentum reversal indicator if recent patterns contradict the trend
        if bullish_count == 3:  # 3 consecutive bullish breaks
            patterns.append({
                'type': 'MOMENTUM_REVERSAL_BULLISH',
                'timestamp': current_candle.name,
                'pattern_count': 3,
                'description': '3 consecutive bullish break patterns detected'
            })
        elif bearish_count == 3:  # 3 consecutive bearish breaks
            patterns.append({
                'type': 'MOMENTUM_REVERSAL_BEARISH',
                'timestamp': current_candle.name,
                'pattern_count': 3,
                'description': '3 consecutive bearish break patterns detected'
            })

    return patterns


def detect_candlestick_patterns(df: pd.DataFrame):
    """
    Detect various candlestick patterns using TA-Lib or custom implementation.
    Focus on key reversal patterns like engulfing, harami, doji, etc.
    """
    patterns = []
    
    # Check if TA-Lib is available
    try:
        import talib
        has_talib = True
    except ImportError:
        logging.warning("TA-Lib not available. Using custom candlestick pattern detection.")
        has_talib = False
    
    if has_talib and len(df) >= 2:
        # Extract OHLC values for TA-Lib
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        # Detect engulfing patterns
        bearish_engulfing = talib.CDLENGULFING(opens, highs, lows, closes)
        
        # Look for bearish engulfing patterns (negative values indicate bearish patterns)
        for i in range(len(bearish_engulfing)):
            if bearish_engulfing[i] < 0:  # Bearish engulfing
                patterns.append({
                    'type': 'BEARISH_ENGULFING',
                    'timestamp': df.index[i],
                    'pattern_value': bearish_engulfing[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
            elif bearish_engulfing[i] > 0:  # Bullish engulfing
                patterns.append({
                    'type': 'BULLISH_ENGULFING',
                    'timestamp': df.index[i],
                    'pattern_value': bearish_engulfing[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
        
        # Detect other important candlestick patterns
        # Doji
        doji = talib.CDLDOJI(opens, highs, lows, closes)
        for i in range(len(doji)):
            if doji[i] != 0:
                pattern_type = 'BULLISH_DOJI' if doji[i] > 0 else 'BEARISH_DOJI'
                patterns.append({
                    'type': pattern_type,
                    'timestamp': df.index[i],
                    'pattern_value': doji[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
        
        # Harami
        harami = talib.CDLHARAMI(opens, highs, lows, closes)
        for i in range(len(harami)):
            if harami[i] != 0:
                pattern_type = 'BULLISH_HARAMI' if harami[i] > 0 else 'BEARISH_HARAMI'
                patterns.append({
                    'type': pattern_type,
                    'timestamp': df.index[i],
                    'pattern_value': harami[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
        
        # Morning Star (potential bullish reversal)
        morning_star = talib.CDLMORNINGSTAR(opens, highs, lows, closes)
        for i in range(len(morning_star)):
            if morning_star[i] > 0:
                patterns.append({
                    'type': 'MORNING_STAR_BULLISH',
                    'timestamp': df.index[i],
                    'pattern_value': morning_star[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
        
        # Evening Star (potential bearish reversal)
        evening_star = talib.CDLEVENINGSTAR(opens, highs, lows, closes)
        for i in range(len(evening_star)):
            if evening_star[i] < 0:
                patterns.append({
                    'type': 'EVENING_STAR_BEARISH',
                    'timestamp': df.index[i],
                    'pattern_value': evening_star[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
        
        # Piercing Pattern (bullish reversal during downtrend)
        piercing = talib.CDLPIERCING(opens, highs, lows, closes)
        for i in range(len(piercing)):
            if piercing[i] > 0:
                patterns.append({
                    'type': 'PIERCING_PATTERN_BULLISH',
                    'timestamp': df.index[i],
                    'pattern_value': piercing[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
        
        # Dark Cloud Cover (bearish reversal during uptrend)
        dark_cloud = talib.CDLDARKCLOUDCOVER(opens, highs, lows, closes)
        for i in range(len(dark_cloud)):
            if dark_cloud[i] < 0:
                patterns.append({
                    'type': 'DARK_CLOUD_COVER_BEARISH',
                    'timestamp': df.index[i],
                    'pattern_value': dark_cloud[i],
                    'candle_open': df.iloc[i]['open'],
                    'candle_close': df.iloc[i]['close'],
                    'candle_high': df.iloc[i]['high'],
                    'candle_low': df.iloc[i]['low']
                })
    
    # If TA-Lib is not available, implement custom detection for key patterns
    else:
        # Custom detection for bearish engulfing pattern
        # A bearish engulfing occurs when: 
        # 1. Previous candle is bullish (close > open)
        # 2. Current candle is bearish (open > close) 
        # 3. Current candle's open > previous candle's close
        # 4. Current candle's close < previous candle's open
        
        for i in range(1, len(df)):
            current_candle = df.iloc[i]
            prev_candle = df.iloc[i-1]
            
            # Bearish Engulfing Pattern
            current_is_bearish = current_candle['open'] > current_candle['close']
            prev_is_bullish = prev_candle['close'] > prev_candle['open']
            current_engulfs_prev = (current_candle['open'] > prev_candle['close'] and 
                                   current_candle['close'] < prev_candle['open'])
            
            if current_is_bearish and prev_is_bullish and current_engulfs_prev:
                # Check if it's a strong engulfing (current candle body is significantly larger)
                current_body = abs(current_candle['open'] - current_candle['close'])
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                engulfing_strength = current_body / prev_body if prev_body > 0 else 0
                
                if engulfing_strength >= 0.8:  # At least 80% of previous candle engulfed
                    patterns.append({
                        'type': 'BEARISH_ENGULFING_CUSTOM',
                        'timestamp': current_candle.name,
                        'candle_open': current_candle['open'],
                        'candle_close': current_candle['close'],
                        'candle_high': current_candle['high'],
                        'candle_low': current_candle['low'],
                        'prev_candle_open': prev_candle['open'],
                        'prev_candle_close': prev_candle['close'],
                        'engulfing_ratio': engulfing_strength,
                        'engulfing_strength_pct': (current_body / prev_body) * 100 if prev_body > 0 else 0
                    })
            
            # Bullish Engulfing Pattern
            current_is_bullish = current_candle['close'] > current_candle['open']
            prev_is_bearish = prev_candle['open'] > prev_candle['close']
            current_engulfs_prev_bullish = (current_candle['close'] > prev_candle['open'] and 
                                           current_candle['open'] < prev_candle['close'])
            
            if current_is_bullish and prev_is_bearish and current_engulfs_prev_bullish:
                # Check if it's a strong engulfing (current candle body is significantly larger)
                current_body = abs(current_candle['close'] - current_candle['open'])
                prev_body = abs(prev_candle['open'] - prev_candle['close'])
                engulfing_strength = current_body / prev_body if prev_body > 0 else 0
                
                if engulfing_strength >= 0.8:  # At least 80% of previous candle engulfed
                    patterns.append({
                        'type': 'BULLISH_ENGULFING_CUSTOM',
                        'timestamp': current_candle.name,
                        'candle_open': current_candle['open'],
                        'candle_close': current_candle['close'],
                        'candle_high': current_candle['high'],
                        'candle_low': current_candle['low'],
                        'prev_candle_open': prev_candle['open'],
                        'prev_candle_close': prev_candle['close'],
                        'engulfing_ratio': engulfing_strength,
                        'engulfing_strength_pct': (current_body / prev_body) * 100 if prev_body > 0 else 0
                    })
            
            # Doji pattern (open and close are very close)
            current_body = abs(current_candle['close'] - current_candle['open'])
            max_body_size = (current_candle['high'] - current_candle['low']) * 0.1  # Doji if body < 10% of range
            
            if current_body <= max_body_size:
                patterns.append({
                    'type': 'DOJI_CUSTOM',
                    'timestamp': current_candle.name,
                    'candle_open': current_candle['open'],
                    'candle_close': current_candle['close'],
                    'candle_high': current_candle['high'],
                    'candle_low': current_candle['low'],
                    'body_size': current_body,
                    'is_bullish': current_candle['close'] >= current_candle['open']
                })
    
    return patterns


def find_most_recent_swing_high(
    symbol: str = "SOLUSDT",
    timeframe: str = '15m',
    lookback_hours: float = 2.0,
    swing_bars: int = 3
):
    """
    Find the MOST RECENT swing high, not one from 6 hours ago!

    Args:
        timeframe: '5m' or '15m'
        lookback_hours: Only look this far back (default 2 hours)
        swing_bars: Bars on each side to compare (3 for recent swings)
    """

    print("\n" + "="*80)
    print("REAL-TIME SWING DETECTOR - MOST RECENT RESISTANCE")
    print("="*80)

    now = datetime.utcnow()
    nigeria_time = now + timedelta(hours=1)
    print(f"\nCurrent time: {nigeria_time.strftime('%Y-%m-%d %H:%M:%S')} (Nigeria UTC+1)")

    # Fetch data
    print(f"\n[FETCHING {timeframe.upper()} DATA]")
    df = fetch_binance_data(symbol, timeframe, limit=100)

    # Filter to recent data only
    cutoff_time = now - timedelta(hours=lookback_hours)
    recent = df[df['timestamp'] >= cutoff_time].copy()

    print(f"  Total candles fetched: {len(df)}")
    print(f"  Recent candles (last {lookback_hours} hours): {len(recent)}")
    print(f"  Time range: {recent['timestamp'].iloc[0]} to {recent['timestamp'].iloc[-1]}")

    # Get current price
    current_price = get_current_price(symbol)
    print(f"\n[CURRENT PRICE] ${current_price:.2f}")

    # Detect swing highs in RECENT data
    print(f"\n[DETECTING SWING HIGHS - Last {lookback_hours} hours]")
    print(f"  Swing detection: {swing_bars} bars on each side")

    swing_highs = []

    for i in range(swing_bars, len(recent) - swing_bars):
        current_high = recent.iloc[i]['high']

        # Check if highest in window
        is_swing_high = all(
            current_high >= recent.iloc[j]['high']
            for j in range(i - swing_bars, i + swing_bars + 1)
            if j != i
        )

        if is_swing_high:
            swing_highs.append({
                'index': i,
                'timestamp': recent.iloc[i]['timestamp'],
                'price': current_high,
                'close': recent.iloc[i]['close'],
                'open': recent.iloc[i]['open'],
                'low': recent.iloc[i]['low']
            })

    print(f"  Found {len(swing_highs)} swing highs in last {lookback_hours} hours")

    # DETECT CANDLE CLOSE PATTERNS (Early Break Signals)
    print(f"\n[DETECTING CANDLE CLOSE PATTERNS - Early Break Signals]")
    print(f"  Looking for candles closing beyond opposite-direction candles...")

    patterns = detect_candle_close_patterns(recent, lookback_bars=20)
    print(f"  Found {len(patterns)} break signal patterns")

    if not swing_highs:
        print(f"\n  No swing highs found in last {lookback_hours} hours")
        print(f"  Try increasing lookback_hours or decreasing swing_bars")
        return

    # Display all recent swings
    print(f"\n{'='*80}")
    print(f"ALL SWING HIGHS (Last {lookback_hours} hours)")
    print("="*80)

    for i, swing in enumerate(swing_highs, 1):
        nigeria_t = swing['timestamp'] + timedelta(hours=1)
        time_ago = (now - swing['timestamp'].to_pydatetime()).total_seconds() / 60

        print(f"\n{i}. {nigeria_t.strftime('%Y-%m-%d %H:%M')} ({time_ago:.0f} mins ago)")
        print(f"   High: ${swing['price']:.2f}")
        print(f"   Close: ${swing['close']:.2f}")
        print(f"   Range: ${swing['price'] - swing['low']:.2f}")

    # Display candle close patterns
    if patterns:
        print(f"\n{'='*80}")
        print(f"CANDLE CLOSE BREAK PATTERNS (Early Warning Signals)")
        print("="*80)
        print(f"\nFound {len(patterns)} patterns in recent data")

        # Show most recent 5 patterns
        recent_patterns = sorted(patterns, key=lambda x: x['timestamp'], reverse=True)[:5]

        for i, pattern in enumerate(recent_patterns, 1):
            nigeria_t = pattern['timestamp'] + timedelta(hours=1)
            time_ago = (now - pattern['timestamp'].to_pydatetime()).total_seconds() / 60

            print(f"\n{i}. {pattern['type']} - {nigeria_t.strftime('%Y-%m-%d %H:%M')} ({time_ago:.0f} mins ago)")

            if pattern['type'] == 'BULLISH_BREAK':
                print(f"   Bullish candle closed at: ${pattern['current_close']:.2f}")
                print(f"   Breaking above bearish candle high: ${pattern['prev_high']:.2f}")
                print(f"   Break strength: ${pattern['break_distance']:.2f} ({pattern['break_pct']:.3f}%)")
                print(f"   Bars apart: {pattern['bars_apart']}")
                print(f"   Signal: EARLY BULLISH BREAKOUT WARNING")

            elif pattern['type'] == 'BEARISH_BREAK':
                print(f"   Bearish candle closed at: ${pattern['current_close']:.2f}")
                print(f"   Breaking below bullish candle low: ${pattern['prev_low']:.2f}")
                print(f"   Break strength: ${pattern['break_distance']:.2f} ({pattern['break_pct']:.3f}%)")
                print(f"   Bars apart: {pattern['bars_apart']}")
                print(f"   Signal: EARLY BEARISH BREAKDOWN WARNING")

        # Analyze patterns near swing levels
        most_recent_pattern = recent_patterns[0]
        print(f"\n{'='*80}")
        print("PATTERN VALIDATION WITH SWING LEVELS")
        print("="*80)

        # Get the most recent swing high for comparison
        most_recent_swing = swing_highs[-1]

        # Check if pattern is near swing level (within 0.5%)
        if most_recent_pattern['type'] == 'BULLISH_BREAK':
            pattern_price = most_recent_pattern['current_close']
            swing_price = most_recent_swing['price']
            distance_pct = abs((pattern_price - swing_price) / swing_price) * 100

            print(f"\nMost recent pattern: BULLISH_BREAK at ${pattern_price:.2f}")
            print(f"Most recent swing high: ${swing_price:.2f}")
            print(f"Distance: {distance_pct:.2f}%")

            if distance_pct < 0.5:
                print(f"\n*** DOUBLE VALIDATION SIGNAL ***")
                print(f"Pattern confirms swing high breakout at ${swing_price:.2f}")
                print(f"Strong bullish signal - trend may be reversing!")
            elif pattern_price > swing_price:
                print(f"\nPattern is ABOVE swing high - confirming breakout")
            else:
                print(f"\nPattern is below swing high - watching for break")

        elif most_recent_pattern['type'] == 'BEARISH_BREAK':
            pattern_price = most_recent_pattern['current_close']
            # For bearish, we'd want swing low comparison (not implemented yet)
            print(f"\nMost recent pattern: BEARISH_BREAK at ${pattern_price:.2f}")
            print(f"Signal: Bearish pressure building")

    # Get MOST RECENT swing high
    most_recent_swing = swing_highs[-1]

    print(f"\n{'='*80}")
    print("MOST RECENT SWING HIGH (CURRENT RESISTANCE)")
    print("="*80)

    nigeria_t = most_recent_swing['timestamp'] + timedelta(hours=1)
    time_ago = (now - most_recent_swing['timestamp'].to_pydatetime()).total_seconds() / 60

    print(f"\nTime: {nigeria_t.strftime('%Y-%m-%d %H:%M')} Nigeria time")
    print(f"Time ago: {time_ago:.0f} minutes ({time_ago/60:.1f} hours)")

    print(f"\n[PRICE DETAILS]")
    print(f"  Swing High: ${most_recent_swing['price']:.2f}")
    print(f"  Candle Close: ${most_recent_swing['close']:.2f}")
    print(f"  Candle Open: ${most_recent_swing['open']:.2f}")

    # Check if broken
    print(f"\n[BREAK ANALYSIS]")
    print(f"  Most recent swing high: ${most_recent_swing['price']:.2f}")
    print(f"  Current price: ${current_price:.2f}")

    # Check candles AFTER the swing to see if it was broken
    swing_index = most_recent_swing['index']
    candles_after = recent.iloc[swing_index + 1:]
    was_broken = False

    if len(candles_after) > 0:
        highest_close_after = candles_after['close'].max()
        was_broken = highest_close_after > most_recent_swing['price']

        print(f"  Highest close after swing: ${highest_close_after:.2f}")

        if was_broken:
            print(f"  Status: BROKEN - Price closed above ${most_recent_swing['price']:.2f}")
            print(f"  This resistance is NO LONGER VALID")

            # Check if current price is still above or has come back down
            if current_price > most_recent_swing['price']:
                print(f"  Current status: Still above broken resistance")
                print(f"  Watch for ${most_recent_swing['price']:.2f} as new SUPPORT (retest)")
            else:
                print(f"  Current status: Came back below broken resistance")
                print(f"  This could be a FAILED BREAKOUT or RETEST")

        else:
            print(f"  Status: INTACT - Price has NOT closed above ${most_recent_swing['price']:.2f}")
            print(f"  This is the ACTIVE RESISTANCE")
    else:
        print(f"  No candles after swing yet (swing just formed)")

    # Current position
    distance = current_price - most_recent_swing['price']
    distance_pct = (distance / current_price) * 100

    print(f"\n[CURRENT POSITION]")
    print(f"  Current price: ${current_price:.2f}")
    print(f"  Resistance: ${most_recent_swing['price']:.2f}")
    print(f"  Distance: ${distance:.2f} ({distance_pct:+.2f}%)")

    if abs(distance_pct) < 0.3:
        print(f"  Status: AT RESISTANCE - Critical level!")
    elif distance > 0:
        print(f"  Status: ABOVE resistance")
    else:
        print(f"  Status: BELOW resistance ({abs(distance_pct):.2f}% away)")

    # Lower high analysis
    if len(swing_highs) >= 2:
        previous_swing = swing_highs[-2]

        print(f"\n[LOWER HIGH ANALYSIS]")
        print(f"  Previous swing: ${previous_swing['price']:.2f}")
        print(f"  Current swing: ${most_recent_swing['price']:.2f}")
        print(f"  Difference: ${most_recent_swing['price'] - previous_swing['price']:.2f}")

        if most_recent_swing['price'] < previous_swing['price']:
            print(f"  Status: LOWER HIGH - Downtrend continuation")
        else:
            print(f"  Status: HIGHER HIGH - Potential trend reversal")

    # Trading implications
    print(f"\n{'='*80}")
    print("TRADING IMPLICATIONS")
    print("="*80)

    # Check for recent bullish break patterns
    recent_bullish_breaks = [p for p in patterns if p['type'] == 'BULLISH_BREAK']
    recent_bearish_breaks = [p for p in patterns if p['type'] == 'BEARISH_BREAK']

    if recent_bullish_breaks:
        latest_bullish = sorted(recent_bullish_breaks, key=lambda x: x['timestamp'], reverse=True)[0]
        time_ago = (now - latest_bullish['timestamp'].to_pydatetime()).total_seconds() / 60
        if time_ago < 30:  # Pattern within last 30 minutes
            print(f"\n*** EARLY BULLISH BREAK SIGNAL DETECTED ({time_ago:.0f} mins ago) ***")
            print(f"Candle closed at ${latest_bullish['current_close']:.2f}, breaking above ${latest_bullish['prev_high']:.2f}")

    if recent_bearish_breaks:
        latest_bearish = sorted(recent_bearish_breaks, key=lambda x: x['timestamp'], reverse=True)[0]
        time_ago = (now - latest_bearish['timestamp'].to_pydatetime()).total_seconds() / 60
        if time_ago < 30:  # Pattern within last 30 minutes
            print(f"\n*** EARLY BEARISH BREAK SIGNAL DETECTED ({time_ago:.0f} mins ago) ***")
            print(f"Candle closed at ${latest_bearish['current_close']:.2f}, breaking below ${latest_bearish['prev_low']:.2f}")

    if was_broken and current_price > most_recent_swing['price']:
        print(f"\nResistance @ ${most_recent_swing['price']:.2f} was BROKEN")
        print(f"  - Watch for NEW swing high to form above ${most_recent_swing['price']:.2f}")
        print(f"  - Old resistance becomes new SUPPORT on retest")
        print(f"  - Bullish bias if holds above ${most_recent_swing['price']:.2f}")

        # Check if pattern confirms the break
        if recent_bullish_breaks:
            latest_bullish = sorted(recent_bullish_breaks, key=lambda x: x['timestamp'], reverse=True)[0]
            print(f"\n  PATTERN CONFIRMATION:")
            print(f"  Bullish break pattern detected at ${latest_bullish['current_close']:.2f}")
            print(f"  This provides SECOND VALIDATION of the trend break!")

    elif was_broken and current_price < most_recent_swing['price']:
        print(f"\nResistance @ ${most_recent_swing['price']:.2f} was broken but FAILED")
        print(f"  - Price came back below resistance (false breakout)")
        print(f"  - Resistance still valid at ${most_recent_swing['price']:.2f}")
        print(f"  - SHORT bias, expect rejection if retests")

    else:
        print(f"\nActive Resistance: ${most_recent_swing['price']:.2f}")
        print(f"Current Price: ${current_price:.2f}")

        if distance_pct > -0.5:
            print(f"  - Price NEAR resistance (watch for rejection)")
            print(f"  - SHORT opportunity if rejection confirmed")

            # Check for bearish pattern near resistance
            if recent_bearish_breaks:
                latest_bearish = sorted(recent_bearish_breaks, key=lambda x: x['timestamp'], reverse=True)[0]
                time_ago = (now - latest_bearish['timestamp'].to_pydatetime()).total_seconds() / 60
                if time_ago < 30:
                    print(f"\n  WARNING: Bearish break pattern detected {time_ago:.0f} mins ago")
                    print(f"  This suggests resistance may hold - SHORT setup forming!")

        else:
            print(f"  - Price {abs(distance_pct):.2f}% below resistance")
            print(f"  - Wait for rally to ${most_recent_swing['price']:.2f} for short entry")

            # Check for bullish patterns that might push toward resistance
            if recent_bullish_breaks:
                latest_bullish = sorted(recent_bullish_breaks, key=lambda x: x['timestamp'], reverse=True)[0]
                time_ago = (now - latest_bullish['timestamp'].to_pydatetime()).total_seconds() / 60
                if time_ago < 30:
                    print(f"\n  ALERT: Bullish break pattern detected {time_ago:.0f} mins ago")
                    print(f"  Price may be moving toward resistance at ${most_recent_swing['price']:.2f}")
                    print(f"  Watch for potential breakout if reaches ${most_recent_swing['price']:.2f}")

    print("\n" + "="*80)


if __name__ == "__main__":
    # Run on 15M with 4-hour lookback (to catch the swing around $219)
    print("\n=== 15M TIMEFRAME (Last 4 Hours) ===")
    find_most_recent_swing_high("SOLUSDT", timeframe='15m', lookback_hours=4.0, swing_bars=2)

    # Also check 5M for more recent precision
    print("\n\n=== 5M TIMEFRAME (Last 2 Hours) ===")
    find_most_recent_swing_high("SOLUSDT", timeframe='5m', lookback_hours=2.0, swing_bars=2)