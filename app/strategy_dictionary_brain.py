"""
Trendline Detection Strategy Dictionary Brain
==============================================

Dedicated strategy brain for trendline-based trading analysis combining:
- Real-time swing high/low detection
- Candle close pattern analysis
- Lower high/higher low trend structure
- Break validation and confirmation
- Multi-timeframe confluence

This brain provides 100+ point confluence scoring specifically for trendline strategies.

Author: Precision9 Team - Trendline Strategy Brain
Date: 2025-10-09
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TrendlineStrategyBrain')


@dataclass
class TrendlineSignal:
    """Complete trendline trading signal"""
    symbol: str
    timestamp: datetime
    timeframe: str

    # Direction and Confidence
    direction: str  # 'LONG', 'SHORT', 'NEUTRAL'
    confidence: float  # 0.0-1.0
    conviction: str  # 'EXTREME', 'HIGH', 'MEDIUM', 'LOW'

    # Swing Levels
    current_price: float
    resistance: Optional[float]
    support: Optional[float]
    resistance_distance_pct: float
    support_distance_pct: float

    # Trend Analysis
    trend_direction: str  # 'UPTREND', 'DOWNTREND', 'NEUTRAL'
    trend_strength: float
    structure_type: str  # 'LOWER_HIGHS', 'HIGHER_LOWS', 'CONSOLIDATION'

    # Pattern Analysis
    latest_pattern: Optional[str]  # 'BULLISH_BREAK', 'BEARISH_BREAK', None
    pattern_strength: float
    bullish_breaks: int
    bearish_breaks: int

    # Confluence Scoring
    bullish_points: int
    bearish_points: int
    total_confluence_points: int

    # Trading Setup
    setup_type: str  # 'BREAKOUT', 'REJECTION', 'CONTINUATION', 'REVERSAL'
    entry_trigger: str
    stop_loss: Optional[float]
    take_profit: Optional[float]
    risk_reward_ratio: float

    # Warnings and Notes
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class TrendlineStrategyBrain:
    """
    Advanced strategy brain for trendline-based trading decisions
    """

    def __init__(self):
        self.signal_history = []
        self.performance_stats = {
            'total_signals': 0,
            'bullish_signals': 0,
            'bearish_signals': 0,
            'neutral_signals': 0
        }

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
        """Detect swing highs"""
        swing_highs = []

        for i in range(swing_bars, len(df) - swing_bars):
            current_high = df.iloc[i]['high']

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
                    'close': df.iloc[i]['close']
                })

        return swing_highs

    def detect_swing_lows(self, df: pd.DataFrame, swing_bars: int = 2) -> List[Dict]:
        """Detect swing lows"""
        swing_lows = []

        for i in range(swing_bars, len(df) - swing_bars):
            current_low = df.iloc[i]['low']

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
                    'close': df.iloc[i]['close']
                })

        return swing_lows

    def detect_candle_close_patterns(self, df: pd.DataFrame, lookback_bars: int = 20) -> List[Dict]:
        """Detect bullish/bearish break patterns"""
        patterns = []

        for i in range(lookback_bars, len(df)):
            current = df.iloc[i]
            is_bullish = current['close'] > current['open']
            is_bearish = current['close'] < current['open']

            if not (is_bullish or is_bearish):
                continue

            for j in range(max(0, i - lookback_bars), i):
                prev = df.iloc[j]
                prev_is_bullish = prev['close'] > prev['open']
                prev_is_bearish = prev['close'] < prev['open']

                # BULLISH BREAK
                if is_bullish and prev_is_bearish and current['close'] > prev['high']:
                    break_pct = ((current['close'] - prev['high']) / prev['high']) * 100
                    if break_pct > 0.1:
                        patterns.append({
                            'type': 'BULLISH_BREAK',
                            'timestamp': current['timestamp'],
                            'price': current['close'],
                            'strength': break_pct,
                            'bars_apart': i - j
                        })
                        break

                # BEARISH BREAK
                elif is_bearish and prev_is_bullish and current['close'] < prev['low']:
                    break_pct = ((prev['low'] - current['close']) / prev['low']) * 100
                    if break_pct > 0.1:
                        patterns.append({
                            'type': 'BEARISH_BREAK',
                            'timestamp': current['timestamp'],
                            'price': current['close'],
                            'strength': break_pct,
                            'bars_apart': i - j
                        })
                        break

        return patterns

    def analyze_trend_structure(self, swing_highs: List[Dict], swing_lows: List[Dict]) -> Dict[str, Any]:
        """Analyze trend structure from swings"""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                'trend_direction': 'NEUTRAL',
                'trend_strength': 0.0,
                'structure_type': 'INSUFFICIENT_DATA'
            }

        # Lower highs (downtrend)
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        is_lower_highs = all(
            recent_highs[i]['price'] > recent_highs[i+1]['price']
            for i in range(len(recent_highs)-1)
        )

        # Higher lows (uptrend)
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
        is_higher_lows = all(
            recent_lows[i]['price'] < recent_lows[i+1]['price']
            for i in range(len(recent_lows)-1)
        )

        # Determine trend
        if is_lower_highs and not is_higher_lows:
            return {
                'trend_direction': 'DOWNTREND',
                'trend_strength': 0.8,
                'structure_type': 'LOWER_HIGHS'
            }
        elif is_higher_lows and not is_lower_highs:
            return {
                'trend_direction': 'UPTREND',
                'trend_strength': 0.8,
                'structure_type': 'HIGHER_LOWS'
            }
        elif is_higher_lows and is_lower_highs:
            return {
                'trend_direction': 'NEUTRAL',
                'trend_strength': 0.3,
                'structure_type': 'CONSOLIDATION'
            }
        else:
            return {
                'trend_direction': 'NEUTRAL',
                'trend_strength': 0.2,
                'structure_type': 'UNCLEAR'
            }

    def calculate_confluence_score(self,
                                   swing_highs: List[Dict],
                                   swing_lows: List[Dict],
                                   patterns: List[Dict],
                                   current_price: float,
                                   trend_structure: Dict[str, Any]) -> Tuple[int, int]:
        """
        Calculate bullish/bearish confluence points (100+ total possible)

        Scoring Breakdown:
        - Trend Structure: 50 points max
        - Candle Patterns: 30 points max (recent 30 mins)
        - Swing Proximity: 20 points max (within 0.5% of level)
        """
        bullish_points = 0
        bearish_points = 0

        # TREND STRUCTURE POINTS (50 max)
        trend_dir = trend_structure.get('trend_direction')
        trend_strength = trend_structure.get('trend_strength', 0)

        if trend_dir == 'UPTREND':
            bullish_points += int(50 * trend_strength)
        elif trend_dir == 'DOWNTREND':
            bearish_points += int(50 * trend_strength)

        # CANDLE PATTERN POINTS (30 max, recent only)
        now = datetime.utcnow()
        recent_patterns = [
            p for p in patterns
            if (now - p['timestamp'].to_pydatetime()).total_seconds() < 1800
        ]

        for pattern in recent_patterns:
            points = min(30, int(pattern['strength'] * 100))
            if pattern['type'] == 'BULLISH_BREAK':
                bullish_points += points
            elif pattern['type'] == 'BEARISH_BREAK':
                bearish_points += points

        # SWING PROXIMITY POINTS (20 max)
        if swing_highs:
            nearest_high = min(swing_highs, key=lambda x: abs(x['price'] - current_price))
            distance_pct = abs((nearest_high['price'] - current_price) / current_price)

            if distance_pct < 0.005:  # Within 0.5%
                if current_price < nearest_high['price']:
                    bearish_points += 20  # Rejection at resistance
                else:
                    bullish_points += 20  # Breakout above resistance

        if swing_lows:
            nearest_low = min(swing_lows, key=lambda x: abs(x['price'] - current_price))
            distance_pct = abs((current_price - nearest_low['price']) / current_price)

            if distance_pct < 0.005:
                if current_price > nearest_low['price']:
                    bullish_points += 20  # Holding support
                else:
                    bearish_points += 20  # Breakdown below support

        return bullish_points, bearish_points

    def determine_trading_setup(self,
                               direction: str,
                               current_price: float,
                               resistance: Optional[float],
                               support: Optional[float],
                               trend_structure: Dict,
                               patterns: List[Dict]) -> Dict[str, Any]:
        """Determine specific trading setup and parameters"""

        setup = {
            'setup_type': 'UNKNOWN',
            'entry_trigger': 'None',
            'stop_loss': None,
            'take_profit': None,
            'risk_reward_ratio': 0.0
        }

        if direction == 'LONG':
            # Check for breakout or bounce
            if resistance and current_price >= resistance * 0.998:
                # At resistance - potential breakout
                setup['setup_type'] = 'BREAKOUT'
                setup['entry_trigger'] = f'Close above ${resistance:.2f}'
                setup['stop_loss'] = resistance * 0.997  # Below broken resistance
                setup['take_profit'] = resistance * 1.005  # 0.5% target
            elif support and current_price <= support * 1.002:
                # At support - bounce play
                setup['setup_type'] = 'BOUNCE'
                setup['entry_trigger'] = f'Bounce from ${support:.2f}'
                setup['stop_loss'] = support * 0.997  # Below support
                setup['take_profit'] = current_price * 1.005
            else:
                # Trend continuation
                setup['setup_type'] = 'CONTINUATION'
                setup['entry_trigger'] = 'Pullback entry'
                setup['stop_loss'] = current_price * 0.997
                setup['take_profit'] = current_price * 1.007

        elif direction == 'SHORT':
            # Check for breakdown or rejection
            if support and current_price <= support * 1.002:
                # At support - breakdown
                setup['setup_type'] = 'BREAKDOWN'
                setup['entry_trigger'] = f'Close below ${support:.2f}'
                setup['stop_loss'] = support * 1.003  # Above broken support
                setup['take_profit'] = support * 0.995
            elif resistance and current_price >= resistance * 0.998:
                # At resistance - rejection
                setup['setup_type'] = 'REJECTION'
                setup['entry_trigger'] = f'Rejection at ${resistance:.2f}'
                setup['stop_loss'] = resistance * 1.003
                setup['take_profit'] = current_price * 0.995
            else:
                # Trend continuation
                setup['setup_type'] = 'CONTINUATION'
                setup['entry_trigger'] = 'Rallypullback entry'
                setup['stop_loss'] = current_price * 1.003
                setup['take_profit'] = current_price * 0.993

        # Calculate R:R
        if setup['stop_loss'] and setup['take_profit']:
            risk = abs(current_price - setup['stop_loss'])
            reward = abs(setup['take_profit'] - current_price)
            setup['risk_reward_ratio'] = reward / risk if risk > 0 else 0.0

        return setup

    def generate_signal(self,
                       symbol: str = "SOLUSDT",
                       timeframe: str = '15m',
                       lookback_hours: float = 4.0) -> TrendlineSignal:
        """
        Generate comprehensive trendline trading signal

        This is the main entry point for the strategy brain
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"TRENDLINE STRATEGY BRAIN - {symbol} {timeframe.upper()}")
        logger.info(f"{'='*80}\n")

        # Fetch data
        df = self.fetch_market_data(symbol, timeframe, limit=100)
        if df.empty:
            logger.error("Failed to fetch market data")
            return None

        # Time-windowed analysis
        now = datetime.utcnow()
        cutoff_time = now - timedelta(hours=lookback_hours)
        recent = df[df['timestamp'] >= cutoff_time].copy()

        if len(recent) < 10:
            logger.error("Insufficient recent data")
            return None

        current_price = float(recent.iloc[-1]['close'])
        logger.info(f"[PRICE] Current: ${current_price:.2f}")

        # Detect swing points
        swing_highs = self.detect_swing_highs(recent, swing_bars=2)
        swing_lows = self.detect_swing_lows(recent, swing_bars=2)

        resistance = swing_highs[-1]['price'] if swing_highs else None
        support = swing_lows[-1]['price'] if swing_lows else None

        logger.info(f"[SWINGS] Resistance: ${resistance:.2f if resistance else 0}, Support: ${support:.2f if support else 0}")

        # Detect patterns
        patterns = self.detect_candle_close_patterns(recent, lookback_bars=20)

        # Recent patterns only
        recent_patterns = [
            p for p in patterns
            if (now - p['timestamp'].to_pydatetime()).total_seconds() < 1800
        ]
        bullish_breaks = len([p for p in recent_patterns if p['type'] == 'BULLISH_BREAK'])
        bearish_breaks = len([p for p in recent_patterns if p['type'] == 'BEARISH_BREAK'])

        logger.info(f"[PATTERNS] Recent: {len(recent_patterns)} | Bullish: {bullish_breaks}, Bearish: {bearish_breaks}")

        # Analyze trend structure
        trend_structure = self.analyze_trend_structure(swing_highs, swing_lows)
        logger.info(f"[TREND] {trend_structure['trend_direction']} - {trend_structure['structure_type']} (Strength: {trend_structure['trend_strength']:.1%})")

        # Calculate confluence
        bullish_points, bearish_points = self.calculate_confluence_score(
            swing_highs, swing_lows, patterns, current_price, trend_structure
        )

        total_points = bullish_points + bearish_points
        logger.info(f"[CONFLUENCE] Bullish: {bullish_points} | Bearish: {bearish_points} | Total: {total_points}")

        # Determine direction and confidence
        if bullish_points > bearish_points + 10: # Lowered from 20 for scalping
            direction = 'LONG'
            confidence = min(0.95, bullish_points / 100)
        elif bearish_points > bullish_points + 10: # Lowered from 20 for scalping
            direction = 'SHORT'
            confidence = min(0.95, bearish_points / 100)
        else:
            direction = 'NEUTRAL'
            confidence = 0.3

        # Conviction level
        if confidence >= 0.80:
            conviction = 'EXTREME'
        elif confidence >= 0.55: # Lowered from 0.65 for scalping
            conviction = 'HIGH'
        elif confidence >= 0.45:
            conviction = 'MEDIUM'
        else:
            conviction = 'LOW'

        logger.info(f"[SIGNAL] Direction: {direction} | Confidence: {confidence:.1%} | Conviction: {conviction}")

        # Trading setup
        setup = self.determine_trading_setup(
            direction, current_price, resistance, support, trend_structure, patterns
        )

        logger.info(f"[SETUP] {setup['setup_type']} | Entry: {setup['entry_trigger']}")
        logger.info(f"[RISK] SL: ${setup['stop_loss']:.2f if setup['stop_loss'] else 0} | TP: ${setup['take_profit']:.2f if setup['take_profit'] else 0} | R:R {setup['risk_reward_ratio']:.2f}")

        # Warnings
        warnings = []
        if total_points < 50:
            warnings.append("Low confluence - wait for better setup")
        if abs(bullish_points - bearish_points) < 15:
            warnings.append("Conflicting signals - market indecision")
        if not patterns:
            warnings.append("No recent patterns detected")

        # Create signal
        signal = TrendlineSignal(
            symbol=symbol,
            timestamp=now,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            conviction=conviction,
            current_price=current_price,
            resistance=resistance,
            support=support,
            resistance_distance_pct=((resistance - current_price) / current_price * 100) if resistance else 0,
            support_distance_pct=((current_price - support) / current_price * 100) if support else 0,
            trend_direction=trend_structure['trend_direction'],
            trend_strength=trend_structure['trend_strength'],
            structure_type=trend_structure['structure_type'],
            latest_pattern=recent_patterns[-1]['type'] if recent_patterns else None,
            pattern_strength=recent_patterns[-1]['strength'] if recent_patterns else 0,
            bullish_breaks=bullish_breaks,
            bearish_breaks=bearish_breaks,
            bullish_points=bullish_points,
            bearish_points=bearish_points,
            total_confluence_points=total_points,
            setup_type=setup['setup_type'],
            entry_trigger=setup['entry_trigger'],
            stop_loss=setup['stop_loss'],
            take_profit=setup['take_profit'],
            risk_reward_ratio=setup['risk_reward_ratio'],
            warnings=warnings
        )

        # Update stats
        self.performance_stats['total_signals'] += 1
        if direction == 'LONG':
            self.performance_stats['bullish_signals'] += 1
        elif direction == 'SHORT':
            self.performance_stats['bearish_signals'] += 1
        else:
            self.performance_stats['neutral_signals'] += 1

        self.signal_history.append(signal)

        logger.info(f"\n{'='*80}")
        logger.info(f"SIGNAL GENERATED - {direction} @ {confidence:.1%}")
        logger.info(f"{'='*80}\n")

        return signal


if __name__ == "__main__":
    # Initialize strategy brain
    brain = TrendlineStrategyBrain()

    # Generate signal
    signal = brain.generate_signal(symbol="SOLUSDT", timeframe="15m", lookback_hours=4.0)

    if signal:
        print("\n" + "="*80)
        print("TRENDLINE STRATEGY SIGNAL")
        print("="*80)
        print(f"\nSymbol: {signal.symbol}")
        print(f"Time: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nDIRECTION: {signal.direction}")
        print(f"Confidence: {signal.confidence:.1%}")
        print(f"Conviction: {signal.conviction}")
        print(f"\nCurrent Price: ${signal.current_price:.2f}")
        print(f"Resistance: ${signal.resistance:.2f} ({signal.resistance_distance_pct:+.2f}%)")
        print(f"Support: ${signal.support:.2f} ({signal.support_distance_pct:+.2f}%)")
        print(f"\nTrend: {signal.trend_direction} ({signal.structure_type})")
        print(f"Trend Strength: {signal.trend_strength:.1%}")
        print(f"\nPattern: {signal.latest_pattern or 'None'}")
        print(f"Bullish Breaks: {signal.bullish_breaks}, Bearish Breaks: {signal.bearish_breaks}")
        print(f"\nConfluence: Bullish {signal.bullish_points}, Bearish {signal.bearish_points} (Total: {signal.total_confluence_points})")
        print(f"\nSetup: {signal.setup_type}")
        print(f"Entry: {signal.entry_trigger}")
        print(f"Stop Loss: ${signal.stop_loss:.2f if signal.stop_loss else 0}")
        print(f"Take Profit: ${signal.take_profit:.2f if signal.take_profit else 0}")
        print(f"R:R Ratio: {signal.risk_reward_ratio:.2f}")

        if signal.warnings:
            print(f"\nWARNINGS:")
            for warning in signal.warnings:
                print(f"  - {warning}")

        print("\n" + "="*80)
