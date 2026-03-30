"""
Trendline Confluence Module - Strategy Dictionary Brain Enhancement
===================================================================

Integrates advanced trendline detection and candle close pattern analysis
into the 500+ point confluence scoring system.

Key Features:
- Real-time swing high/low detection (1-4 hour lookback)
- Candle close pattern detection (early break signals)
- Lower high/higher low trend analysis
- Break validation and confirmation
- Time-windowed analysis (catches current structure, not outdated levels)

Author: Precision9 Team - Trendline Detection Integration
Date: 2025-10-09
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger('TrendlineConfluence')


class TrendlineConfluenceAnalyzer:
    """
    Analyzes swing points, trendlines, and candle patterns for confluence scoring
    """

    def __init__(self):
        self.swing_history = []
        self.pattern_history = []
        self.break_history = []

    def fetch_market_data(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """Fetch recent market data from Binance"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            response = requests.get(url, params=params, timeout=5)
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
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return pd.DataFrame()

    def detect_swing_highs(self, df: pd.DataFrame, swing_bars: int = 2) -> List[Dict]:
        """
        Detect swing highs using time-windowed analysis

        Args:
            df: DataFrame with OHLC data
            swing_bars: Bars on each side to compare (2-3 for recent swings)
        """
        swing_highs = []

        for i in range(swing_bars, len(df) - swing_bars):
            current_high = df.iloc[i]['high']

            # Check if highest in window
            is_swing_high = all(
                current_high >= df.iloc[j]['high']
                for j in range(i - swing_bars, i + swing_bars + 1)
                if j != i
            )

            if is_swing_high:
                swing_highs.append({
                    'index': i,
                    'timestamp': df.iloc[i]['timestamp'],
                    'price': current_high,
                    'close': df.iloc[i]['close'],
                    'open': df.iloc[i]['open'],
                    'low': df.iloc[i]['low']
                })

        return swing_highs

    def detect_swing_lows(self, df: pd.DataFrame, swing_bars: int = 2) -> List[Dict]:
        """Detect swing lows using time-windowed analysis"""
        swing_lows = []

        for i in range(swing_bars, len(df) - swing_bars):
            current_low = df.iloc[i]['low']

            # Check if lowest in window
            is_swing_low = all(
                current_low <= df.iloc[j]['low']
                for j in range(i - swing_bars, i + swing_bars + 1)
                if j != i
            )

            if is_swing_low:
                swing_lows.append({
                    'index': i,
                    'timestamp': df.iloc[i]['timestamp'],
                    'price': current_low,
                    'close': df.iloc[i]['close'],
                    'open': df.iloc[i]['open'],
                    'high': df.iloc[i]['high']
                })

        return swing_lows

    def detect_candle_close_patterns(self, df: pd.DataFrame, lookback_bars: int = 20) -> List[Dict]:
        """
        Detect early break signals from candle close patterns

        Bullish Break: Bullish candle closes ABOVE previous bearish candle's high
        Bearish Break: Bearish candle closes BELOW previous bullish candle's low
        """
        patterns = []

        for i in range(lookback_bars, len(df)):
            current = df.iloc[i]
            is_bullish = current['close'] > current['open']
            is_bearish = current['close'] < current['open']

            if not (is_bullish or is_bearish):
                continue

            # Look back for opposite-direction candles
            for j in range(max(0, i - lookback_bars), i):
                prev = df.iloc[j]
                prev_is_bullish = prev['close'] > prev['open']
                prev_is_bearish = prev['close'] < prev['open']

                # BULLISH BREAK
                if is_bullish and prev_is_bearish:
                    if current['close'] > prev['high']:
                        break_distance = current['close'] - prev['high']
                        break_pct = (break_distance / prev['high']) * 100

                        if break_pct > 0.1:  # Significant break
                            patterns.append({
                                'type': 'BULLISH_BREAK',
                                'timestamp': current['timestamp'],
                                'current_close': current['close'],
                                'prev_high': prev['high'],
                                'break_pct': break_pct,
                                'bars_apart': i - j
                            })
                            break

                # BEARISH BREAK
                elif is_bearish and prev_is_bullish:
                    if current['close'] < prev['low']:
                        break_distance = prev['low'] - current['close']
                        break_pct = (break_distance / prev['low']) * 100

                        if break_pct > 0.1:
                            patterns.append({
                                'type': 'BEARISH_BREAK',
                                'timestamp': current['timestamp'],
                                'current_close': current['close'],
                                'prev_low': prev['low'],
                                'break_pct': break_pct,
                                'bars_apart': i - j
                            })
                            break

        return patterns

    def analyze_trend_structure(self, swing_highs: List[Dict], swing_lows: List[Dict]) -> Dict[str, Any]:
        """
        Analyze trend structure using swing points

        Returns:
            Dictionary with trend analysis including:
            - trend_direction: 'UPTREND', 'DOWNTREND', 'NEUTRAL'
            - trend_strength: 0.0-1.0
            - structure_type: 'LOWER_HIGHS', 'HIGHER_LOWS', 'CONSOLIDATION'
        """
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                'trend_direction': 'NEUTRAL',
                'trend_strength': 0.0,
                'structure_type': 'INSUFFICIENT_DATA'
            }

        # Check for lower highs (downtrend)
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        is_lower_highs = all(
            recent_highs[i]['price'] > recent_highs[i+1]['price']
            for i in range(len(recent_highs)-1)
        )

        # Check for higher lows (uptrend)
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
        is_higher_lows = all(
            recent_lows[i]['price'] < recent_lows[i+1]['price']
            for i in range(len(recent_lows)-1)
        )

        # Determine trend
        if is_lower_highs and not is_higher_lows:
            trend_direction = 'DOWNTREND'
            structure_type = 'LOWER_HIGHS'
            trend_strength = 0.8
        elif is_higher_lows and not is_lower_highs:
            trend_direction = 'UPTREND'
            structure_type = 'HIGHER_LOWS'
            trend_strength = 0.8
        elif is_higher_lows and is_lower_highs:
            # Converging pattern - consolidation
            trend_direction = 'NEUTRAL'
            structure_type = 'CONSOLIDATION'
            trend_strength = 0.3
        else:
            trend_direction = 'NEUTRAL'
            structure_type = 'UNCLEAR'
            trend_strength = 0.2

        return {
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'structure_type': structure_type,
            'recent_highs_count': len(recent_highs),
            'recent_lows_count': len(recent_lows)
        }

    def calculate_confluence_points(self,
                                   swing_highs: List[Dict],
                                   swing_lows: List[Dict],
                                   patterns: List[Dict],
                                   current_price: float,
                                   direction: str) -> Dict[str, int]:
        """
        Calculate confluence points for Strategy Dictionary Brain

        Returns points for:
        - Swing structure alignment
        - Candle close pattern confirmation
        - Break signals
        - Trend structure
        """
        bullish_points = 0
        bearish_points = 0

        # SWING STRUCTURE POINTS (50 points max)
        trend_analysis = self.analyze_trend_structure(swing_highs, swing_lows)

        if trend_analysis['trend_direction'] == 'UPTREND':
            bullish_points += int(50 * trend_analysis['trend_strength'])
        elif trend_analysis['trend_direction'] == 'DOWNTREND':
            bearish_points += int(50 * trend_analysis['trend_strength'])

        # CANDLE CLOSE PATTERN POINTS (30 points max)
        # Recent patterns (last 30 minutes) are more valuable
        now = datetime.utcnow()
        recent_patterns = [
            p for p in patterns
            if (now - p['timestamp'].to_pydatetime()).total_seconds() < 1800
        ]

        for pattern in recent_patterns:
            if pattern['type'] == 'BULLISH_BREAK':
                # Award points based on break strength
                points = min(30, int(pattern['break_pct'] * 100))
                bullish_points += points
            elif pattern['type'] == 'BEARISH_BREAK':
                points = min(30, int(pattern['break_pct'] * 100))
                bearish_points += points

        # RESISTANCE/SUPPORT PROXIMITY POINTS (20 points max)
        # Price near swing levels adds conviction
        if swing_highs:
            nearest_high = min(swing_highs, key=lambda x: abs(x['price'] - current_price))
            distance_pct = abs((nearest_high['price'] - current_price) / current_price)

            if distance_pct < 0.005:  # Within 0.5%
                # Price near resistance - bearish if rejecting
                if current_price < nearest_high['price']:
                    bearish_points += 20
                else:  # Breakout above resistance - bullish
                    bullish_points += 20

        if swing_lows:
            nearest_low = min(swing_lows, key=lambda x: abs(x['price'] - current_price))
            distance_pct = abs((current_price - nearest_low['price']) / current_price)

            if distance_pct < 0.005:  # Within 0.5%
                # Price near support - bullish if holding
                if current_price > nearest_low['price']:
                    bullish_points += 20
                else:  # Breakdown below support - bearish
                    bearish_points += 20

        return {
            'bullish_points': bullish_points,
            'bearish_points': bearish_points,
            'total_points': bullish_points + bearish_points,
            'trend_structure': trend_analysis['structure_type'],
            'pattern_count': len(recent_patterns)
        }

    def get_comprehensive_analysis(self,
                                  symbol: str = "SOLUSDT",
                                  timeframe: str = '15m',
                                  lookback_hours: float = 4.0) -> Dict[str, Any]:
        """
        Get comprehensive trendline and pattern analysis

        Returns complete analysis for Strategy Dictionary Brain integration
        """
        try:
            # Fetch data
            df = self.fetch_market_data(symbol, timeframe, limit=100)
            if df.empty:
                return {'error': 'Failed to fetch data'}

            # Time-windowed analysis (only recent data)
            now = datetime.utcnow()
            cutoff_time = now - timedelta(hours=lookback_hours)
            recent = df[df['timestamp'] >= cutoff_time].copy()

            if len(recent) < 10:
                return {'error': 'Insufficient recent data'}

            # Get current price
            current_price = float(recent.iloc[-1]['close'])

            # Detect swing points
            swing_highs = self.detect_swing_highs(recent, swing_bars=2)
            swing_lows = self.detect_swing_lows(recent, swing_bars=2)

            # Detect candle close patterns
            patterns = self.detect_candle_close_patterns(recent, lookback_bars=20)

            # Analyze trend structure
            trend_analysis = self.analyze_trend_structure(swing_highs, swing_lows)

            # Get most recent swing levels
            most_recent_resistance = swing_highs[-1]['price'] if swing_highs else None
            most_recent_support = swing_lows[-1]['price'] if swing_lows else None

            # Calculate confluence points
            # Determine suggested direction based on patterns
            recent_patterns = [
                p for p in patterns
                if (now - p['timestamp'].to_pydatetime()).total_seconds() < 1800
            ]
            bullish_breaks = len([p for p in recent_patterns if p['type'] == 'BULLISH_BREAK'])
            bearish_breaks = len([p for p in recent_patterns if p['type'] == 'BEARISH_BREAK'])

            suggested_direction = 'NEUTRAL'
            if bullish_breaks > bearish_breaks:
                suggested_direction = 'LONG'
            elif bearish_breaks > bullish_breaks:
                suggested_direction = 'SHORT'

            confluence = self.calculate_confluence_points(
                swing_highs, swing_lows, patterns, current_price, suggested_direction
            )

            return {
                'success': True,
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'lookback_hours': lookback_hours,
                'swing_analysis': {
                    'most_recent_resistance': most_recent_resistance,
                    'most_recent_support': most_recent_support,
                    'total_swing_highs': len(swing_highs),
                    'total_swing_lows': len(swing_lows),
                    'resistance_distance_pct': ((most_recent_resistance - current_price) / current_price * 100) if most_recent_resistance else None,
                    'support_distance_pct': ((current_price - most_recent_support) / current_price * 100) if most_recent_support else None
                },
                'trend_analysis': trend_analysis,
                'pattern_analysis': {
                    'total_patterns': len(patterns),
                    'recent_patterns': len(recent_patterns),
                    'bullish_breaks': bullish_breaks,
                    'bearish_breaks': bearish_breaks,
                    'latest_pattern': patterns[-1] if patterns else None
                },
                'confluence_points': confluence,
                'suggested_direction': suggested_direction,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            return {'error': str(e)}


# Singleton instance for integration
_analyzer_instance = None

def get_trendline_analyzer() -> TrendlineConfluenceAnalyzer:
    """Get or create singleton trendline analyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = TrendlineConfluenceAnalyzer()
    return _analyzer_instance
