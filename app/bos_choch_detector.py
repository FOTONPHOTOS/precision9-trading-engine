"""
BOS/CHoCH Detector - Structure Shift Detection

BOS (Break of Structure):
- Price breaks previous high/low in direction of trend
- Confirms trend continuation
- Bullish BOS: Price breaks above previous swing high
- Bearish BOS: Price breaks below previous swing low

CHoCH (Change of Character):
- Price breaks previous high/low AGAINST the trend
- Signals potential trend reversal
- Bullish CHoCH: Price breaks above previous high in downtrend
- Bearish CHoCH: Price breaks below previous low in uptrend

These are CRITICAL for identifying trend shifts before they happen.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class StructureShift:
    """BOS or CHoCH event"""
    type: str  # 'BOS' or 'CHoCH'
    direction: str  # 'bullish' or 'bearish'
    timestamp: datetime
    break_price: float
    previous_level: float
    break_strength: float  # Percentage of break
    confidence: float  # 0-1

    # Context
    trend_before: str  # 'uptrend', 'downtrend', 'neutral'
    trend_after: str  # What trend is expected after this break

    # Implications
    signal: str  # 'CONTINUATION' or 'REVERSAL'
    importance: str  # 'HIGH', 'MEDIUM', 'LOW'


class BOSCHoCHDetector:
    """
    Detects Break of Structure and Change of Character

    Algorithm:
    1. Identify swing highs and lows
    2. Track current trend direction
    3. Detect when price breaks previous swing levels
    4. Classify as BOS (continuation) or CHoCH (reversal)
    """

    def __init__(self):
        self.min_break_confirmation = 0.002  # 0.2% minimum to confirm break

    def detect(
        self,
        swing_highs: List[Dict],
        swing_lows: List[Dict],
        current_price: float,
        df: pd.DataFrame
    ) -> List[StructureShift]:
        """
        Detect all BOS and CHoCH events

        Args:
            swing_highs: List of swing high dictionaries
            swing_lows: List of swing low dictionaries
            current_price: Current market price
            df: OHLC dataframe

        Returns:
            List of StructureShift objects
        """

        if not swing_highs or not swing_lows:
            return []

        shifts = []

        # Determine current trend
        trend = self._determine_trend(swing_highs, swing_lows)

        # Check for breaks of recent swing highs
        for i, swing in enumerate(swing_highs):
            if i == 0:  # Skip most recent swing
                continue

            previous_swing = swing_highs[i-1]

            # Check if price broke above this swing
            break_candle = self._find_break_candle(df, swing, previous_swing, 'high')

            if break_candle is not None:
                break_price = float(break_candle['close'])
                break_strength = (break_price - swing['price']) / swing['price']

                # Is this BOS or CHoCH?
                if trend == 'uptrend':
                    # Breaking high in uptrend = BOS (continuation)
                    shift_type = 'BOS'
                    signal = 'CONTINUATION'
                    expected_trend = 'uptrend'
                    importance = 'MEDIUM'
                else:
                    # Breaking high in downtrend = CHoCH (reversal)
                    shift_type = 'CHoCH'
                    signal = 'REVERSAL'
                    expected_trend = 'uptrend'
                    importance = 'HIGH'

                confidence = min(1.0, break_strength / 0.01)  # 1% break = 100% confidence

                shifts.append(StructureShift(
                    type=shift_type,
                    direction='bullish',
                    timestamp=break_candle['timestamp'],
                    break_price=break_price,
                    previous_level=swing['price'],
                    break_strength=break_strength,
                    confidence=confidence,
                    trend_before=trend,
                    trend_after=expected_trend,
                    signal=signal,
                    importance=importance
                ))

        # Check for breaks of recent swing lows
        for i, swing in enumerate(swing_lows):
            if i == 0:  # Skip most recent swing
                continue

            previous_swing = swing_lows[i-1]

            # Check if price broke below this swing
            break_candle = self._find_break_candle(df, swing, previous_swing, 'low')

            if break_candle is not None:
                break_price = float(break_candle['close'])
                break_strength = (swing['price'] - break_price) / swing['price']

                # Is this BOS or CHoCH?
                if trend == 'downtrend':
                    # Breaking low in downtrend = BOS (continuation)
                    shift_type = 'BOS'
                    signal = 'CONTINUATION'
                    expected_trend = 'downtrend'
                    importance = 'MEDIUM'
                else:
                    # Breaking low in uptrend = CHoCH (reversal)
                    shift_type = 'CHoCH'
                    signal = 'REVERSAL'
                    expected_trend = 'downtrend'
                    importance = 'HIGH'

                confidence = min(1.0, break_strength / 0.01)  # 1% break = 100% confidence

                shifts.append(StructureShift(
                    type=shift_type,
                    direction='bearish',
                    timestamp=break_candle['timestamp'],
                    break_price=break_price,
                    previous_level=swing['price'],
                    break_strength=break_strength,
                    confidence=confidence,
                    trend_before=trend,
                    trend_after=expected_trend,
                    signal=signal,
                    importance=importance
                ))

        # Sort by time
        shifts.sort(key=lambda x: x.timestamp, reverse=True)

        return shifts

    def _determine_trend(
        self,
        swing_highs: List[Dict],
        swing_lows: List[Dict]
    ) -> str:
        """Determine current trend from swings"""

        if len(swing_highs) >= 2:
            if swing_highs[-1]['price'] > swing_highs[-2]['price']:
                higher_highs = True
            else:
                higher_highs = False
        else:
            higher_highs = None

        if len(swing_lows) >= 2:
            if swing_lows[-1]['price'] > swing_lows[-2]['price']:
                higher_lows = True
            else:
                higher_lows = False
        else:
            higher_lows = None

        # Uptrend: Higher highs AND higher lows
        if higher_highs and higher_lows:
            return 'uptrend'
        # Downtrend: Lower highs AND lower lows
        elif higher_highs == False and higher_lows == False:
            return 'downtrend'
        else:
            return 'neutral'

    def _find_break_candle(
        self,
        df: pd.DataFrame,
        swing: Dict,
        previous_swing: Dict,
        level_type: str
    ) -> Optional[pd.Series]:
        """
        Find the candle that broke a swing level

        Returns the candle that first closed above/below the level
        """

        # Find swing index in dataframe
        swing_index = None
        for i, row in df.iterrows():
            if row['timestamp'] == swing['timestamp']:
                swing_index = i
                break

        if swing_index is None:
            return None

        # Look at candles after the swing
        for i in range(swing_index + 1, len(df)):
            candle = df.iloc[i]

            if level_type == 'high':
                # Check if candle closed above swing high
                if float(candle['close']) > swing['price'] * (1 + self.min_break_confirmation):
                    return candle
            else:  # low
                # Check if candle closed below swing low
                if float(candle['close']) < swing['price'] * (1 - self.min_break_confirmation):
                    return candle

        return None

    def get_most_recent_shift(self, shifts: List[StructureShift]) -> Optional[StructureShift]:
        """Get the most recent structure shift"""
        if not shifts:
            return None
        return shifts[0]  # Already sorted by time

    def get_active_shifts(
        self,
        shifts: List[StructureShift],
        hours_ago: float = 6.0
    ) -> List[StructureShift]:
        """Get structure shifts from last N hours"""

        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours_ago)

        active = []
        for shift in shifts:
            if shift.timestamp.to_pydatetime() >= cutoff:
                active.append(shift)

        return active


def print_structure_shifts(shifts: List[StructureShift]):
    """Pretty print structure shifts"""

    print("\n" + "="*80)
    print("BOS/CHoCH DETECTION - STRUCTURE SHIFT ANALYSIS")
    print("="*80)

    if not shifts:
        print("\nNo structure shifts detected in recent data")
        return

    print(f"\nTotal Structure Shifts: {len(shifts)}")

    bos_shifts = [s for s in shifts if s.type == 'BOS']
    choch_shifts = [s for s in shifts if s.type == 'CHoCH']

    print(f"BOS (Continuations): {len(bos_shifts)}")
    print(f"CHoCH (Reversals): {len(choch_shifts)}")

    # Show recent shifts
    print(f"\n{'='*80}")
    print("RECENT STRUCTURE SHIFTS")
    print(f"{'='*80}")

    for i, shift in enumerate(shifts[:10], 1):
        now = datetime.utcnow()
        time_ago = (now - shift.timestamp.to_pydatetime()).total_seconds() / 60

        print(f"\n{i}. {shift.type} - {shift.direction.upper()} ({shift.importance} importance)")
        print(f"   Time: {time_ago:.0f} mins ago")
        print(f"   Break Price: ${shift.break_price:.2f}")
        print(f"   Previous Level: ${shift.previous_level:.2f}")
        print(f"   Break Strength: {shift.break_strength:.2%}")
        print(f"   Confidence: {shift.confidence:.0%}")
        print(f"   Signal: {shift.signal}")
        print(f"   Trend Before: {shift.trend_before} -> After: {shift.trend_after}")

        if shift.type == 'CHoCH':
            print(f"   [ALERT] Potential trend reversal detected!")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    from realtime_swing_detector import fetch_binance_data
    from test_complete_arsenal import find_swing_highs, find_swing_lows
    from datetime import timedelta

    print("BOS/CHoCH Detector - Standalone Test")
    print("Detecting structure shifts...")

    df = fetch_binance_data("SOLUSDT", "15m", 100)
    current_price = float(df.iloc[-1]['close'])

    # Filter to recent data
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=6)
    recent = df[df['timestamp'] >= cutoff].copy()

    # Find swings
    swing_highs = find_swing_highs(recent, lookback=2)
    swing_lows = find_swing_lows(recent, lookback=2)

    print(f"Found {len(swing_highs)} swing highs, {len(swing_lows)} swing lows")

    # Detect shifts
    detector = BOSCHoCHDetector()
    shifts = detector.detect(swing_highs, swing_lows, current_price, recent)

    print(f"\nDetected {len(shifts)} structure shifts")

    # Print results
    print_structure_shifts(shifts)

    # Show most recent
    most_recent = detector.get_most_recent_shift(shifts)
    if most_recent:
        print(f"Most Recent Shift: {most_recent.type} {most_recent.direction} @ ${most_recent.break_price:.2f}")
