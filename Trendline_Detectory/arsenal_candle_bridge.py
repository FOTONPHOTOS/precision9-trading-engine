"""
Arsenal Candle Bridge - Connects Arsenal's Candle Tools to Risk Manager
========================================================================

This bridge connects:
- Trendline Confluence Module (candle patterns, swing analysis)
- Arsenal CVD Collector (historical candles with CVD)
- Risk Manager (reversal detection, exit logic)

Instead of Risk Manager fetching its own stale candles, it now gets:
1. Real-time candle close events from trendline detector
2. Pattern detection (bullish/bearish breaks)
3. Swing structure analysis
4. Volume confirmation from CVD

Author: Precision9 Team
Date: 2025-10-11
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional, Callable
from dataclasses import dataclass
import logging

from trendline_confluence_module import get_trendline_analyzer

logger = logging.getLogger('ARSENAL_CANDLE_BRIDGE')


@dataclass
class CandleCloseEvent:
    """Real-time candle close event"""
    timestamp: datetime
    timeframe: str  # '3m' or '5m'
    open: float
    high: float
    low: float
    close: float
    volume: float

    # Pattern analysis
    is_green: bool
    is_red: bool
    has_bullish_break: bool
    has_bearish_break: bool
    break_strength: float  # 0.0-1.0

    # Swing analysis
    near_resistance: bool
    near_support: bool
    resistance_level: Optional[float]
    support_level: Optional[float]


class ArsenalCandleBridge:
    """
    Bridges Arsenal's candle analysis tools to Risk Manager

    Features:
    1. Real-time candle monitoring (3m and 5m)
    2. Pattern detection on every candle close
    3. Event callbacks for Risk Manager
    4. Swing structure updates
    """

    def __init__(self, symbol: str = "SOLUSDT"):
        self.symbol = symbol
        self.analyzer = get_trendline_analyzer()

        # Candle tracking
        self.last_3m_candle = None
        self.last_5m_candle = None
        self.last_3m_check = 0
        self.last_5m_check = 0

        # Event callbacks
        self.on_3m_candle_close: Optional[Callable] = None
        self.on_5m_candle_close: Optional[Callable] = None
        self.on_pattern_detected: Optional[Callable] = None

        # Running state
        self.running = False

    def set_callbacks(self,
                     on_3m_close: Optional[Callable] = None,
                     on_5m_close: Optional[Callable] = None,
                     on_pattern: Optional[Callable] = None):
        """
        Set event callbacks for Risk Manager

        Args:
            on_3m_close: Called when 3m candle closes
            on_5m_close: Called when 5m candle closes
            on_pattern: Called when bullish/bearish pattern detected
        """
        self.on_3m_candle_close = on_3m_close
        self.on_5m_candle_close = on_5m_close
        self.on_pattern_detected = on_pattern

    async def start_monitoring(self):
        """
        Start real-time candle monitoring

        Checks every 5 seconds for new candle closes
        """
        self.running = True
        logger.info("Arsenal Candle Bridge started")
        logger.info(f"  Symbol: {self.symbol}")
        logger.info(f"  Monitoring: 3m and 5m candles")
        logger.info(f"  Check interval: 5 seconds")

        while self.running:
            try:
                # Check 3m candles
                await self._check_3m_candles()

                # Check 5m candles
                await self._check_5m_candles()

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in candle monitoring: {e}")
                await asyncio.sleep(5)

    def stop_monitoring(self):
        """Stop candle monitoring"""
        self.running = False
        logger.info("Arsenal Candle Bridge stopped")

    async def _check_3m_candles(self):
        """Check for new 3m candle closes"""
        try:
            # Get comprehensive analysis (includes latest candle data)
            analysis = self.analyzer.get_comprehensive_analysis(
                symbol=self.symbol,
                timeframe='3m',
                lookback_hours=1.0  # Last hour only
            )

            if not analysis.get('success'):
                return

            # Fetch latest candle data
            df = self.analyzer.fetch_market_data(self.symbol, '3m', limit=2)
            if df.empty or len(df) < 2:
                return

            latest = df.iloc[-1]
            candle_timestamp = latest['timestamp']

            # Check if this is a new candle
            if self.last_3m_candle != candle_timestamp:
                self.last_3m_candle = candle_timestamp

                # Create candle event
                event = await self._create_candle_event(
                    latest, analysis, timeframe='3m'
                )

                # Trigger callback
                if self.on_3m_candle_close:
                    try:
                        await self.on_3m_candle_close(event)
                    except Exception as e:
                        logger.error(f"Error in 3m candle callback: {e}")

                # Log candle close
                direction = " GREEN" if event.is_green else " RED"
                logger.info(f"3m CANDLE CLOSE: {direction} at ${event.close:.2f}")

                if event.has_bullish_break:
                    logger.info(f"   BULLISH BREAK detected (strength: {event.break_strength:.1%})")
                elif event.has_bearish_break:
                    logger.info(f"   BEARISH BREAK detected (strength: {event.break_strength:.1%})")

        except Exception as e:
            logger.error(f"Error checking 3m candles: {e}")

    async def _check_5m_candles(self):
        """Check for new 5m candle closes"""
        try:
            analysis = self.analyzer.get_comprehensive_analysis(
                symbol=self.symbol,
                timeframe='5m',
                lookback_hours=2.0
            )

            if not analysis.get('success'):
                return

            df = self.analyzer.fetch_market_data(self.symbol, '5m', limit=2)
            if df.empty or len(df) < 2:
                return

            latest = df.iloc[-1]
            candle_timestamp = latest['timestamp']

            if self.last_5m_candle != candle_timestamp:
                self.last_5m_candle = candle_timestamp

                event = await self._create_candle_event(
                    latest, analysis, timeframe='5m'
                )

                if self.on_5m_candle_close:
                    try:
                        await self.on_5m_candle_close(event)
                    except Exception as e:
                        logger.error(f"Error in 5m candle callback: {e}")

                direction = " GREEN" if event.is_green else " RED"
                logger.debug(f"5m CANDLE CLOSE: {direction} at ${event.close:.2f}")

        except Exception as e:
            logger.error(f"Error checking 5m candles: {e}")

    async def _create_candle_event(self, candle_row, analysis: Dict, timeframe: str) -> CandleCloseEvent:
        """Create CandleCloseEvent from candle data and analysis"""

        open_price = float(candle_row['open'])
        close_price = float(candle_row['close'])
        high_price = float(candle_row['high'])
        low_price = float(candle_row['low'])
        volume = float(candle_row['volume'])

        is_green = close_price > open_price
        is_red = close_price < open_price

        # Check for pattern breaks
        patterns = analysis.get('pattern_analysis', {})
        latest_pattern = patterns.get('latest_pattern')

        has_bullish_break = False
        has_bearish_break = False
        break_strength = 0.0

        if latest_pattern:
            pattern_type = latest_pattern.get('type', '')
            if pattern_type == 'BULLISH_BREAK':
                has_bullish_break = True
                break_strength = min(1.0, latest_pattern.get('break_pct', 0) / 2.0)  # Normalize to 0-1
            elif pattern_type == 'BEARISH_BREAK':
                has_bearish_break = True
                break_strength = min(1.0, latest_pattern.get('break_pct', 0) / 2.0)

        # Get swing levels
        swing_analysis = analysis.get('swing_analysis', {})
        resistance = swing_analysis.get('most_recent_resistance')
        support = swing_analysis.get('most_recent_support')

        # Check proximity (within 0.5%)
        near_resistance = False
        near_support = False

        if resistance:
            distance_pct = abs((resistance - close_price) / close_price)
            near_resistance = distance_pct < 0.005

        if support:
            distance_pct = abs((close_price - support) / close_price)
            near_support = distance_pct < 0.005

        return CandleCloseEvent(
            timestamp=candle_row['timestamp'],
            timeframe=timeframe,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            is_green=is_green,
            is_red=is_red,
            has_bullish_break=has_bullish_break,
            has_bearish_break=has_bearish_break,
            break_strength=break_strength,
            near_resistance=near_resistance,
            near_support=near_support,
            resistance_level=resistance,
            support_level=support
        )

    async def get_latest_analysis(self, timeframe: str = '3m') -> Optional[Dict]:
        """
        Get latest Arsenal analysis for a timeframe

        Args:
            timeframe: '3m' or '5m'

        Returns:
            Complete analysis dictionary from trendline analyzer
        """
        try:
            analysis = self.analyzer.get_comprehensive_analysis(
                symbol=self.symbol,
                timeframe=timeframe,
                lookback_hours=4.0
            )
            return analysis if analysis.get('success') else None
        except Exception as e:
            logger.error(f"Error getting {timeframe} analysis: {e}")
            return None


# Test/Example usage
async def main():
    """Test the Arsenal Candle Bridge"""

    bridge = ArsenalCandleBridge(symbol="SOLUSDT")

    # Define callbacks for Risk Manager
    async def on_3m_close(event: CandleCloseEvent):
        """Handle 3m candle close"""
        direction = "GREEN" if event.is_green else "RED"
        print(f"\n{'='*60}")
        print(f"3M CANDLE CLOSE: {direction}")
        print(f"{'='*60}")
        print(f"Time: {event.timestamp}")
        print(f"Close: ${event.close:.2f}")
        print(f"Volume: {event.volume:.0f}")

        if event.has_bullish_break:
            print(f" BULLISH BREAK: {event.break_strength:.1%} strength")
        elif event.has_bearish_break:
            print(f" BEARISH BREAK: {event.break_strength:.1%} strength")

        if event.near_resistance:
            print(f" Near resistance: ${event.resistance_level:.2f}")
        if event.near_support:
            print(f" Near support: ${event.support_level:.2f}")

    async def on_5m_close(event: CandleCloseEvent):
        """Handle 5m candle close"""
        direction = "GREEN" if event.is_green else "RED"
        print(f"\n5M CANDLE: {direction} at ${event.close:.2f}")

    # Set callbacks
    bridge.set_callbacks(
        on_3m_close=on_3m_close,
        on_5m_close=on_5m_close
    )

    # Start monitoring
    print("Starting Arsenal Candle Bridge...")
    print("Monitoring 3m and 5m candles")
    print("Press Ctrl+C to stop\n")

    try:
        await bridge.start_monitoring()
    except KeyboardInterrupt:
        print("\nStopping...")
        bridge.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
