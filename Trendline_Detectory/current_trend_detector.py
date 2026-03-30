"""
Current Trend Detector - Find the Active Trend Market is in RIGHT NOW
======================================================================

Key Insight from User:
"we are after the most recent trend that is continuing the market also not
that this can also enter the previous day if the trend is long, that is why
swing point detection is important"

Approach:
1. Work BACKWARDS from most recent data
2. Find the current/active trendline the market is in NOW
3. Trace back to where this trend started (even if previous day)
4. Detect if current trend is breaking
5. Identify new trend forming after break
6. Can detect MULTIPLE trend sequences in chronological order
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class TrendlineState(Enum):
    ACTIVE = "active"
    BROKEN = "broken"


@dataclass
class SwingPoint:
    index: int
    timestamp: pd.Timestamp
    price: float
    swing_type: str  # 'high' or 'low'

    def __repr__(self):
        return f"{self.swing_type.upper()} @ {self.timestamp.strftime('%m-%d %H:%M')} ${self.price:.2f}"


@dataclass
class TrendSequence:
    """A complete trend sequence: trendline + optional break + optional new trend"""
    trendline: 'Trendline'
    new_trend_after_break: Optional['Trendline'] = None

    def __repr__(self):
        if self.new_trend_after_break:
            return f"SEQUENCE: {self.trendline.line_type.upper()} → BREAK → {self.new_trend_after_break.line_type.upper()}"
        return f"SEQUENCE: {self.trendline.line_type.upper()} ({self.trendline.state.value})"


@dataclass
class Trendline:
    swing_points: List[SwingPoint]
    line_type: str  # 'resistance' or 'support'
    slope: float
    intercept: float
    state: TrendlineState
    r_squared: float

    # Break tracking
    break_index: Optional[int] = None
    break_timestamp: Optional[pd.Timestamp] = None
    break_price: Optional[float] = None

    def price_at_index(self, index: int) -> float:
        return self.slope * index + self.intercept

    def __repr__(self):
        touches = len(self.swing_points)
        if self.state == TrendlineState.BROKEN:
            return f"{self.line_type.upper()} [BROKEN @ {self.break_timestamp.strftime('%H:%M')}]: {touches} touches"
        return f"{self.line_type.upper()} [ACTIVE]: {touches} touches"


class CurrentTrendDetector:
    """
    Detects the CURRENT trend market is in, working backwards from most recent data
    """

    def __init__(self, swing_lookback: int = 3, min_touches: int = 2, max_touches: int = 4):
        self.swing_lookback = swing_lookback
        self.min_touches = min_touches
        self.max_touches = max_touches

    def detect_swings(self, df: pd.DataFrame, swing_type: str) -> List[SwingPoint]:
        """Detect swing highs or lows"""
        swings = []

        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            if swing_type == 'high':
                current_price = df.iloc[i]['high']
                is_swing = all(
                    current_price >= df.iloc[j]['high']
                    for j in range(i - self.swing_lookback, i + self.swing_lookback + 1)
                    if j != i
                )
            else:  # low
                current_price = df.iloc[i]['low']
                is_swing = all(
                    current_price <= df.iloc[j]['low']
                    for j in range(i - self.swing_lookback, i + self.swing_lookback + 1)
                    if j != i
                )

            if is_swing:
                swings.append(SwingPoint(
                    index=i,
                    timestamp=df.iloc[i]['timestamp'],
                    price=current_price,
                    swing_type=swing_type
                ))

        return swings

    def detect_current_trend_direction(self, df: pd.DataFrame, lookback_candles: int = 50) -> Tuple[str, List[SwingPoint]]:
        """
        Detect current trend direction by looking at recent swing points

        Returns:
            (trend_direction, relevant_swings)
            trend_direction: 'downtrend' or 'uptrend'
        """
        # Look at recent data
        recent = df.tail(lookback_candles).reset_index(drop=True)

        # Detect recent swing highs and lows
        recent_highs = self.detect_swings(recent, 'high')
        recent_lows = self.detect_swings(recent, 'low')

        print(f"\n[TREND DIRECTION ANALYSIS]")
        print(f"  Recent data: Last {lookback_candles} candles")
        print(f"  Found {len(recent_highs)} swing highs, {len(recent_lows)} swing lows")

        if len(recent_highs) < 2 and len(recent_lows) < 2:
            # Not enough swings, use simple price comparison
            if recent['close'].iloc[-1] < recent['close'].iloc[0]:
                return 'downtrend', recent_highs
            else:
                return 'uptrend', recent_lows

        # Check if recent highs are descending (lower highs = downtrend)
        if len(recent_highs) >= 2:
            last_two_highs = recent_highs[-2:]
            if last_two_highs[-1].price < last_two_highs[-2].price:
                print(f"  Detected DOWNTREND: Last high ${last_two_highs[-1].price:.2f} < Previous high ${last_two_highs[-2].price:.2f}")
                return 'downtrend', recent_highs

        # Check if recent lows are ascending (higher lows = uptrend)
        if len(recent_lows) >= 2:
            last_two_lows = recent_lows[-2:]
            if last_two_lows[-1].price > last_two_lows[-2].price:
                print(f"  Detected UPTREND: Last low ${last_two_lows[-1].price:.2f} > Previous low ${last_two_lows[-2].price:.2f}")
                return 'uptrend', recent_lows

        # Default to downtrend if price is lower
        if recent['close'].iloc[-1] < recent['close'].iloc[0]:
            return 'downtrend', recent_highs
        else:
            return 'uptrend', recent_lows

    def build_trendline(
        self,
        swings: List[SwingPoint],
        df: pd.DataFrame,
        line_type: str,
        start_index: int = 0
    ) -> Optional[Trendline]:
        """
        Build trendline from swing points and check for breaks

        Args:
            swings: Swing points to connect
            df: Full dataframe
            line_type: 'resistance' or 'support'
            start_index: Where to start looking for swings (for multi-sequence detection)
        """
        if len(swings) < self.min_touches:
            return None

        # Try different numbers of touches (2, 3, 4)
        for num_touches in range(self.min_touches, min(self.max_touches + 1, len(swings) + 1)):
            candidate_swings = swings[:num_touches]

            # Fit line
            indices = np.array([s.index for s in candidate_swings])
            prices = np.array([s.price for s in candidate_swings])

            A = np.vstack([indices, np.ones(len(indices))]).T
            slope, intercept = np.linalg.lstsq(A, prices, rcond=None)[0]

            # Calculate R²
            y_pred = slope * indices + intercept
            ss_res = np.sum((prices - y_pred) ** 2)
            ss_tot = np.sum((prices - np.mean(prices)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

            # Must be good fit (R² > 0.9)
            if r_squared < 0.9:
                continue

            # Create trendline
            trendline = Trendline(
                swing_points=candidate_swings,
                line_type=line_type,
                slope=slope,
                intercept=intercept,
                state=TrendlineState.ACTIVE,
                r_squared=r_squared
            )

            # Check for breaks after last touch
            last_index = candidate_swings[-1].index

            for i in range(last_index + 1, len(df)):
                candle = df.iloc[i]
                expected = trendline.price_at_index(i)

                is_broken = False
                if line_type == 'resistance':
                    is_broken = candle['close'] > expected
                else:  # support
                    is_broken = candle['close'] < expected

                if is_broken:
                    trendline.state = TrendlineState.BROKEN
                    trendline.break_index = i
                    trendline.break_timestamp = candle['timestamp']
                    trendline.break_price = candle['close']
                    break

            return trendline

        return None

    def find_all_trend_sequences(
        self,
        df: pd.DataFrame,
        date_filter: Optional[str] = None,
        max_sequences: int = 3
    ) -> List[TrendSequence]:
        """
        Find MULTIPLE trend sequences in chronological order

        Args:
            df: 5M dataframe
            date_filter: Optional date string "YYYY-MM-DD" to focus on specific day
            max_sequences: Maximum number of sequences to detect

        Returns:
            List of TrendSequence objects
        """
        print("\n" + "="*80)
        print("CURRENT TREND DETECTOR - MULTIPLE SEQUENCES")
        print("="*80)

        # Apply date filter if provided
        if date_filter:
            print(f"\n[DATE FILTER] Focusing on trends active on or after {date_filter}")
            filter_date = pd.to_datetime(date_filter)
            # Include previous day to capture long trends
            start_date = filter_date - timedelta(days=1)
            df_filtered = df[df['timestamp'] >= start_date].reset_index(drop=True)
            print(f"  Using data from {df_filtered['timestamp'].iloc[0]} onwards")
        else:
            df_filtered = df.reset_index(drop=True)

        print(f"  Total candles: {len(df_filtered)}")
        print(f"  Time range: {df_filtered['timestamp'].iloc[0]} to {df_filtered['timestamp'].iloc[-1]}")

        # Step 1: Detect all swing highs and lows
        print("\n[STEP 1] Detecting ALL swing points...")
        all_swing_highs = self.detect_swings(df_filtered, 'high')
        all_swing_lows = self.detect_swings(df_filtered, 'low')
        print(f"  Found {len(all_swing_highs)} swing HIGHS")
        print(f"  Found {len(all_swing_lows)} swing LOWS")

        # Step 2: Find current trend direction
        print("\n[STEP 2] Detecting CURRENT trend direction...")
        current_trend, relevant_swings = self.detect_current_trend_direction(df_filtered, lookback_candles=50)
        print(f"  Current trend: {current_trend.upper()}")

        # Step 3: Find all trend sequences
        sequences = []
        processed_indices = set()

        print(f"\n[STEP 3] Finding up to {max_sequences} trend sequences...")

        # Start with current trend
        if current_trend == 'downtrend':
            # Work backwards through swing highs
            available_highs = [s for s in all_swing_highs if s.index not in processed_indices]

            for seq_num in range(max_sequences):
                if not available_highs:
                    break

                print(f"\n  [SEQUENCE {seq_num + 1}] Looking for DOWNTREND (resistance)...")

                # Build trendline from available highs
                trendline = self.build_trendline(available_highs, df_filtered, 'resistance')

                if not trendline:
                    break

                print(f"    Found: {trendline}")

                # Mark these swings as processed
                for swing in trendline.swing_points:
                    processed_indices.add(swing.index)

                # If broken, look for uptrend after break
                new_trend = None
                if trendline.state == TrendlineState.BROKEN:
                    print(f"    Break detected @ {trendline.break_timestamp.strftime('%H:%M')}")
                    print(f"    Looking for UPTREND after break...")

                    # Get swing lows after break
                    lows_after_break = [s for s in all_swing_lows if s.index >= trendline.break_index]
                    if len(lows_after_break) >= 2:
                        # Adjust indices for building trendline
                        break_offset = trendline.break_index
                        adjusted_lows = []
                        for low in lows_after_break:
                            adjusted = SwingPoint(
                                index=low.index - break_offset,
                                timestamp=low.timestamp,
                                price=low.price,
                                swing_type=low.swing_type
                            )
                            adjusted_lows.append(adjusted)

                        # Build uptrend trendline
                        data_after_break = df_filtered.iloc[break_offset:].reset_index(drop=True)
                        new_trend = self.build_trendline(adjusted_lows, data_after_break, 'support')

                        if new_trend:
                            print(f"    Found new uptrend: {new_trend}")
                            # Adjust indices back
                            for swing in new_trend.swing_points:
                                swing.index += break_offset
                            if new_trend.break_index is not None:
                                new_trend.break_index += break_offset

                # Create sequence
                sequence = TrendSequence(
                    trendline=trendline,
                    new_trend_after_break=new_trend
                )
                sequences.append(sequence)

                # Update available highs (remove processed)
                available_highs = [s for s in all_swing_highs if s.index not in processed_indices]

        else:  # uptrend
            # Similar logic for uptrend starting point
            available_lows = [s for s in all_swing_lows if s.index not in processed_indices]

            for seq_num in range(max_sequences):
                if not available_lows:
                    break

                print(f"\n  [SEQUENCE {seq_num + 1}] Looking for UPTREND (support)...")

                trendline = self.build_trendline(available_lows, df_filtered, 'support')

                if not trendline:
                    break

                print(f"    Found: {trendline}")

                for swing in trendline.swing_points:
                    processed_indices.add(swing.index)

                # If broken, look for downtrend after
                new_trend = None
                if trendline.state == TrendlineState.BROKEN:
                    print(f"    Break detected @ {trendline.break_timestamp.strftime('%H:%M')}")
                    print(f"    Looking for DOWNTREND after break...")

                    highs_after_break = [s for s in all_swing_highs if s.index >= trendline.break_index]
                    if len(highs_after_break) >= 2:
                        break_offset = trendline.break_index
                        adjusted_highs = []
                        for high in highs_after_break:
                            adjusted = SwingPoint(
                                index=high.index - break_offset,
                                timestamp=high.timestamp,
                                price=high.price,
                                swing_type=high.swing_type
                            )
                            adjusted_highs.append(adjusted)

                        data_after_break = df_filtered.iloc[break_offset:].reset_index(drop=True)
                        new_trend = self.build_trendline(adjusted_highs, data_after_break, 'resistance')

                        if new_trend:
                            print(f"    Found new downtrend: {new_trend}")
                            for swing in new_trend.swing_points:
                                swing.index += break_offset
                            if new_trend.break_index is not None:
                                new_trend.break_index += break_offset

                sequence = TrendSequence(
                    trendline=trendline,
                    new_trend_after_break=new_trend
                )
                sequences.append(sequence)

                available_lows = [s for s in all_swing_lows if s.index not in processed_indices]

        print("\n" + "="*80)
        print(f"FOUND {len(sequences)} TREND SEQUENCE(S)")
        print("="*80)

        return sequences

    def print_sequence(self, sequence: TrendSequence, seq_number: int):
        """Print detailed information about a trend sequence"""
        print(f"\n{'='*80}")
        print(f"TREND SEQUENCE #{seq_number}")
        print(f"{'='*80}")

        # Print initial trendline
        tl = sequence.trendline
        print(f"\n[INITIAL TREND] {tl.line_type.upper()}")
        print(f"  State: {tl.state.value.upper()}")
        print(f"  Touches: {len(tl.swing_points)}")
        print(f"  R²: {tl.r_squared:.4f}")

        print(f"\n  Touch Points (Nigeria Time UTC+1):")
        for i, swing in enumerate(tl.swing_points, 1):
            nigeria_time = swing.timestamp + timedelta(hours=1)
            print(f"    {i}. {nigeria_time.strftime('%Y-%m-%d %H:%M')} @ ${swing.price:.2f}")

        if tl.state == TrendlineState.BROKEN:
            nigeria_break = tl.break_timestamp + timedelta(hours=1)
            print(f"\n  BREAK @ {nigeria_break.strftime('%Y-%m-%d %H:%M')} - Price: ${tl.break_price:.2f}")

        # Print new trend if exists
        if sequence.new_trend_after_break:
            nt = sequence.new_trend_after_break
            print(f"\n[NEW TREND AFTER BREAK] {nt.line_type.upper()}")
            print(f"  State: {nt.state.value.upper()}")
            print(f"  Touches: {len(nt.swing_points)}")
            print(f"  R²: {nt.r_squared:.4f}")

            print(f"\n  Touch Points (Nigeria Time UTC+1):")
            for i, swing in enumerate(nt.swing_points, 1):
                nigeria_time = swing.timestamp + timedelta(hours=1)
                print(f"    {i}. {nigeria_time.strftime('%Y-%m-%d %H:%M')} @ ${swing.price:.2f}")

            if nt.state == TrendlineState.BROKEN:
                nigeria_break = nt.break_timestamp + timedelta(hours=1)
                print(f"\n  BREAK @ {nigeria_break.strftime('%Y-%m-%d %H:%M')} - Price: ${nt.break_price:.2f}")
