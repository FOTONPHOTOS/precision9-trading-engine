"""
15-Minute Focused Trendline Detector with Break Validation
============================================================

Key Changes Based on User Feedback:
1. PRIMARY FOCUS ON 15M CHART (not 1M with HTF context)
2. Detect SHORTER trendlines (2-3 touches, then watch for break)
3. VALIDATE BREAKS - candle close beyond line = trendline invalidated
4. Don't connect points after a breakout
5. Identify the swing point that marks transition (e.g., higher low before downtrend continues)

User's Critical Insight:
"the bot is using too many candles, from 1:20 am to 10:15 is more than 500 candles"
"the market broke out of the trendline at around 5:15... the 09:33, 10:06, 10:15 is just
the market coming down to touch same trend line that formed at 01:20, 03:31"

Solution:
- Work on 15M timeframe for structure detection
- Detect lower highs + lower lows for downtrend
- Stop trendline at first break
- Identify transition swings (higher lows that end reversals)
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime


class TrendType(Enum):
    DOWNTREND = "downtrend"  # Lower highs + lower lows
    UPTREND = "uptrend"      # Higher highs + higher lows
    RANGE = "range"


class TrendlineState(Enum):
    ACTIVE = "active"        # Trendline is valid, not broken
    BROKEN = "broken"        # Candle closed beyond line
    COMPLETED = "completed"  # Trend ended naturally


@dataclass
class SwingPoint15M:
    """Swing point detected on 15M timeframe"""
    index: int
    timestamp: pd.Timestamp
    price: float
    swing_type: str  # 'high' or 'low'
    volume: float

    def __repr__(self):
        return f"{self.swing_type.upper()} @ {self.timestamp.strftime('%m-%d %H:%M')} ${self.price:.2f}"


@dataclass
class Trendline15M:
    """Trendline with break validation"""
    swing_points: List[SwingPoint15M]  # The swing points forming the line
    line_type: str  # 'resistance' (for downtrend) or 'support' (for uptrend)
    slope: float
    intercept: float

    # State tracking
    state: TrendlineState
    break_index: Optional[int] = None  # Index where line was broken
    break_timestamp: Optional[pd.Timestamp] = None
    break_price: Optional[float] = None

    # Quality metrics
    r_squared: float = 0.0
    touch_count: int = 0

    def __repr__(self):
        state_str = self.state.value.upper()
        if self.state == TrendlineState.BROKEN:
            return f"{self.line_type.upper()} [{state_str} @ {self.break_timestamp.strftime('%H:%M')}]: {self.touch_count} touches"
        return f"{self.line_type.upper()} [{state_str}]: {self.touch_count} touches"

    def price_at_index(self, index: int) -> float:
        """Calculate expected price at given index"""
        return self.slope * index + self.intercept

    def is_broken_by_candle(self, candle_index: int, close_price: float, high_price: float, low_price: float) -> bool:
        """
        Check if this candle breaks the trendline

        Critical Rule: CANDLE CLOSE beyond line = BREAK (not just wick)
        """
        expected_price = self.price_at_index(candle_index)

        if self.line_type == 'resistance':
            # Resistance broken when candle CLOSES above line
            return close_price > expected_price
        else:  # support
            # Support broken when candle CLOSES below line
            return close_price < expected_price


@dataclass
class TrendStructure15M:
    """Complete trend structure on 15M"""
    trend_type: TrendType
    swing_highs: List[SwingPoint15M]
    swing_lows: List[SwingPoint15M]
    trendline: Optional[Trendline15M]

    # Transition identification
    transition_swing: Optional[SwingPoint15M] = None  # The swing that ended reversal

    def __repr__(self):
        return f"{self.trend_type.value.upper()}: {len(self.swing_highs)} highs, {len(self.swing_lows)} lows"


class FifteenMinuteSwingDetector:
    """Detects swing highs and lows on 15M timeframe"""

    def __init__(self, lookback_bars: int = 3):
        """
        Args:
            lookback_bars: How many bars on each side to compare (3-5 for 15M)
        """
        self.lookback = lookback_bars

    def detect_swings(self, df_15m: pd.DataFrame) -> Tuple[List[SwingPoint15M], List[SwingPoint15M]]:
        """
        Detect swing highs and lows on 15M chart

        Returns:
            (swing_highs, swing_lows)
        """
        swing_highs = []
        swing_lows = []

        for i in range(self.lookback, len(df_15m) - self.lookback):
            current_high = df_15m.iloc[i]['high']
            current_low = df_15m.iloc[i]['low']

            # Check for swing high
            is_swing_high = all(
                current_high > df_15m.iloc[j]['high']
                for j in range(i - self.lookback, i + self.lookback + 1)
                if j != i
            )

            if is_swing_high:
                swing_highs.append(SwingPoint15M(
                    index=i,
                    timestamp=df_15m.iloc[i]['timestamp'],
                    price=current_high,
                    swing_type='high',
                    volume=df_15m.iloc[i]['volume']
                ))

            # Check for swing low
            is_swing_low = all(
                current_low < df_15m.iloc[j]['low']
                for j in range(i - self.lookback, i + self.lookback + 1)
                if j != i
            )

            if is_swing_low:
                swing_lows.append(SwingPoint15M(
                    index=i,
                    timestamp=df_15m.iloc[i]['timestamp'],
                    price=current_low,
                    swing_type='low',
                    volume=df_15m.iloc[i]['volume']
                ))

        return swing_highs, swing_lows


class TrendStructureAnalyzer:
    """Analyzes trend structure: lower highs + lower lows = downtrend, etc."""

    def identify_trend_type(
        self,
        swing_highs: List[SwingPoint15M],
        swing_lows: List[SwingPoint15M],
        lookback_swings: int = 3
    ) -> TrendType:
        """
        Identify current trend type based on recent swings

        Downtrend: Series of lower highs + lower lows
        Uptrend: Series of higher highs + higher lows
        """
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return TrendType.RANGE

        # Look at recent swings
        recent_highs = swing_highs[-lookback_swings:]
        recent_lows = swing_lows[-lookback_swings:]

        # Check if highs are descending (lower highs)
        highs_descending = all(
            recent_highs[i+1].price < recent_highs[i].price
            for i in range(len(recent_highs) - 1)
        )

        # Check if lows are descending (lower lows)
        lows_descending = all(
            recent_lows[i+1].price < recent_lows[i].price
            for i in range(len(recent_lows) - 1)
        )

        # Check if highs are ascending (higher highs)
        highs_ascending = all(
            recent_highs[i+1].price > recent_highs[i].price
            for i in range(len(recent_highs) - 1)
        )

        # Check if lows are ascending (higher lows)
        lows_ascending = all(
            recent_lows[i+1].price > recent_lows[i].price
            for i in range(len(recent_lows) - 1)
        )

        if highs_descending and lows_descending:
            return TrendType.DOWNTREND
        elif highs_ascending and lows_ascending:
            return TrendType.UPTREND
        else:
            return TrendType.RANGE

    def find_transition_swing(
        self,
        swing_lows: List[SwingPoint15M],
        trend_type: TrendType
    ) -> Optional[SwingPoint15M]:
        """
        Find the swing that marks transition

        Example: In downtrend, find the higher low that ended the upward reversal
        before market continued down
        """
        if trend_type != TrendType.DOWNTREND or len(swing_lows) < 3:
            return None

        # Look for higher low (swing that's higher than previous)
        for i in range(len(swing_lows) - 2, 0, -1):
            if swing_lows[i].price > swing_lows[i-1].price:
                # This is a higher low - potential transition swing
                # Check if followed by lower low (continuation of downtrend)
                if i + 1 < len(swing_lows) and swing_lows[i+1].price < swing_lows[i].price:
                    return swing_lows[i]

        return None


class TrendlineBuilder:
    """Builds trendlines from swing points with break validation"""

    def __init__(self, min_touches: int = 2, max_touches: int = 4):
        """
        Args:
            min_touches: Minimum swing points to form trendline (2-3)
            max_touches: Maximum before expecting a break (3-4)
        """
        self.min_touches = min_touches
        self.max_touches = max_touches

    def build_trendline(
        self,
        swings: List[SwingPoint15M],
        df_15m: pd.DataFrame,
        line_type: str
    ) -> Optional[Trendline15M]:
        """
        Build trendline from swing points and validate for breaks

        Key: Stop at first break, don't extend beyond
        """
        if len(swings) < self.min_touches:
            return None

        # Try to find collinear swings (2-4 touches)
        best_line = None
        best_score = 0

        for num_touches in range(self.min_touches, min(self.max_touches + 1, len(swings) + 1)):
            # Try first N swings
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

            # Score: prefer 2-3 touches with high R²
            score = r_squared * 100 - (num_touches - 2) * 5  # Penalty for more touches

            if score > best_score:
                best_score = score
                best_line = Trendline15M(
                    swing_points=candidate_swings,
                    line_type=line_type,
                    slope=slope,
                    intercept=intercept,
                    state=TrendlineState.ACTIVE,
                    r_squared=r_squared,
                    touch_count=num_touches
                )

        if best_line is None:
            return None

        # Check for breaks after the last touch
        last_swing_index = best_line.swing_points[-1].index

        for i in range(last_swing_index + 1, len(df_15m)):
            candle = df_15m.iloc[i]

            if best_line.is_broken_by_candle(
                i,
                candle['close'],
                candle['high'],
                candle['low']
            ):
                # Trendline broken!
                best_line.state = TrendlineState.BROKEN
                best_line.break_index = i
                best_line.break_timestamp = candle['timestamp']
                best_line.break_price = candle['close']
                break

        return best_line


class FifteenMinuteTrendlineDetector:
    """
    Main detector focused on 15M timeframe

    Process:
    1. Detect swing highs and lows on 15M
    2. Identify trend type (lower highs + lower lows = downtrend)
    3. Build trendline from swings (2-3 touches)
    4. Validate for breaks (candle close beyond line)
    5. Identify transition swings
    """

    def __init__(self):
        self.swing_detector = FifteenMinuteSwingDetector(lookback_bars=3)
        self.structure_analyzer = TrendStructureAnalyzer()
        self.trendline_builder = TrendlineBuilder(min_touches=2, max_touches=4)

    def detect(self, df_15m: pd.DataFrame, recent_bars: int = 100) -> List[TrendStructure15M]:
        """
        Detect trend structures on 15M chart

        Args:
            df_15m: DataFrame with 15M candles
            recent_bars: Focus on recent N bars (default 100 = ~25 hours on 15M)

        Returns list of TrendStructure15M objects
        """
        print("\n" + "="*80)
        print("15-MINUTE TRENDLINE DETECTION WITH BREAK VALIDATION")
        print("="*80)

        # Focus on recent data only
        df_recent = df_15m.tail(recent_bars).reset_index(drop=True)
        print(f"\n[FOCUS] Analyzing most recent {len(df_recent)} candles (~{len(df_recent)*15/60:.1f} hours)")
        print(f"  Time range: {df_recent['timestamp'].iloc[0]} to {df_recent['timestamp'].iloc[-1]}")

        # Step 1: Detect all swings
        print("\n[STEP 1] Detecting swing points on 15M chart...")
        swing_highs, swing_lows = self.swing_detector.detect_swings(df_recent)
        print(f"  Found {len(swing_highs)} swing highs")
        print(f"  Found {len(swing_lows)} swing lows")

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            print("  [WARNING] Not enough swing points detected")
            return []

        # Step 2: Identify trend type
        print("\n[STEP 2] Analyzing trend structure...")
        trend_type = self.structure_analyzer.identify_trend_type(swing_highs, swing_lows, lookback_swings=3)
        print(f"  Identified trend: {trend_type.value.upper()}")

        # If still RANGE, try with just last 2 swings (more permissive)
        if trend_type == TrendType.RANGE and len(swing_highs) >= 2:
            # Check if last 2 highs are descending
            if swing_highs[-1].price < swing_highs[-2].price:
                print("  [ADJUSTED] Detected descending highs - treating as DOWNTREND")
                trend_type = TrendType.DOWNTREND
            elif swing_lows[-1].price > swing_lows[-2].price:
                print("  [ADJUSTED] Detected ascending lows - treating as UPTREND")
                trend_type = TrendType.UPTREND

        # Step 3: Build trendline based on trend type
        print("\n[STEP 3] Building trendline...")
        trendline = None

        if trend_type == TrendType.DOWNTREND:
            # For downtrend, connect lower highs (resistance)
            print("  Downtrend detected - connecting lower highs for resistance line")
            # Use recent swing highs only
            recent_swing_highs = [s for s in swing_highs if s.index >= len(df_recent) - 60]  # Last ~15 hours
            if len(recent_swing_highs) >= 2:
                trendline = self.trendline_builder.build_trendline(
                    recent_swing_highs,
                    df_recent,
                    'resistance'
                )
        elif trend_type == TrendType.UPTREND:
            # For uptrend, connect higher lows (support)
            print("  Uptrend detected - connecting higher lows for support line")
            recent_swing_lows = [s for s in swing_lows if s.index >= len(df_recent) - 60]
            if len(recent_swing_lows) >= 2:
                trendline = self.trendline_builder.build_trendline(
                    recent_swing_lows,
                    df_recent,
                    'support'
                )

        if trendline:
            print(f"  Built trendline: {trendline}")
            if trendline.state == TrendlineState.BROKEN:
                print(f"  [BREAK DETECTED] Line broken at {trendline.break_timestamp.strftime('%m-%d %H:%M')} @ ${trendline.break_price:.2f}")
        else:
            print("  [WARNING] Could not build trendline")

        # Step 4: Find transition swing
        print("\n[STEP 4] Finding transition swings...")
        transition_swing = self.structure_analyzer.find_transition_swing(swing_lows, trend_type)
        if transition_swing:
            print(f"  Found transition swing: {transition_swing}")

        # Return structure
        structure = TrendStructure15M(
            trend_type=trend_type,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            trendline=trendline,
            transition_swing=transition_swing
        )

        print("\n" + "="*80)
        print("DETECTION COMPLETE")
        print("="*80)

        return [structure]

    def print_detailed_results(self, structures: List[TrendStructure15M]):
        """Print detailed results"""

        for i, structure in enumerate(structures, 1):
            print(f"\n{'='*80}")
            print(f"TREND STRUCTURE #{i}")
            print(f"{'='*80}")

            print(f"\n[TREND TYPE] {structure.trend_type.value.upper()}")

            if structure.trendline:
                tl = structure.trendline
                print(f"\n[TRENDLINE] {tl.line_type.upper()}")
                print(f"  State: {tl.state.value.upper()}")
                print(f"  Touch Count: {tl.touch_count}")
                print(f"  R²: {tl.r_squared:.4f}")
                print(f"  Slope: {tl.slope:.6f}")

                print(f"\n[TOUCH POINTS]")
                for j, swing in enumerate(tl.swing_points, 1):
                    print(f"  {j}. {swing.timestamp.strftime('%Y-%m-%d %H:%M')} @ ${swing.price:.2f}")

                if tl.state == TrendlineState.BROKEN:
                    print(f"\n[BREAK DETAILS]")
                    print(f"  Broken at: {tl.break_timestamp.strftime('%Y-%m-%d %H:%M')}")
                    print(f"  Break price: ${tl.break_price:.2f}")
                    print(f"  Expected price at break: ${tl.price_at_index(tl.break_index):.2f}")

            if structure.transition_swing:
                print(f"\n[TRANSITION SWING]")
                print(f"  {structure.transition_swing}")
                print(f"  This swing marks the end of reversal before trend continuation")
