"""
5-Minute Trendline Detector with 15M Context
=============================================

Based on user feedback analysis:
1. Use 15M to identify overall trend direction
2. Drop down to 5M to draw precise trendlines
3. Detect 2-3 touch trendlines (not 500+ candles)
4. Validate breaks (candle close beyond line)

Why 5M?
- 1M has too many minor swings (too noisy)
- 15M is too coarse for precise entry/exit
- 5M is the sweet spot for trendline precision
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import pandas as pd
import numpy as np


class TrendlineState(Enum):
    ACTIVE = "active"
    BROKEN = "broken"


@dataclass
class SwingPoint5M:
    index: int
    timestamp: pd.Timestamp
    price: float
    swing_type: str  # 'high' or 'low'

    def __repr__(self):
        return f"{self.swing_type.upper()} @ {self.timestamp.strftime('%H:%M')} ${self.price:.2f}"


@dataclass
class Trendline5M:
    swing_points: List[SwingPoint5M]
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
        if self.state == TrendlineState.BROKEN:
            return f"{self.line_type.upper()} [BROKEN @ {self.break_timestamp.strftime('%H:%M')}]: {len(self.swing_points)} touches"
        return f"{self.line_type.upper()} [ACTIVE]: {len(self.swing_points)} touches"


class FiveMinuteTrendlineDetector:
    """Detects trendlines on 5M chart with 15M context"""

    def __init__(self, swing_lookback: int = 3, min_touches: int = 2, max_touches: int = 3):
        self.swing_lookback = swing_lookback
        self.min_touches = min_touches
        self.max_touches = max_touches

    def detect_trend_direction_15m(self, df_15m: pd.DataFrame, recent_bars: int = 20) -> str:
        """
        Quick trend direction check using 15M

        Returns: 'downtrend', 'uptrend', or 'range'
        """
        recent = df_15m.tail(recent_bars)

        # Simple: compare first and last closes
        if recent['close'].iloc[-1] < recent['close'].iloc[0]:
            # Price is lower - check for lower highs
            highs = recent['high'].values
            if highs[-1] < max(highs[:-1]):
                return 'downtrend'

        elif recent['close'].iloc[-1] > recent['close'].iloc[0]:
            # Price is higher - check for higher lows
            lows = recent['low'].values
            if lows[-1] > min(lows[:-1]):
                return 'uptrend'

        return 'range'

    def detect_swings_5m(self, df_5m: pd.DataFrame, swing_type: str) -> List[SwingPoint5M]:
        """
        Detect swing highs or lows on 5M

        Args:
            swing_type: 'high' or 'low'
        """
        swings = []

        for i in range(self.swing_lookback, len(df_5m) - self.swing_lookback):
            if swing_type == 'high':
                current_price = df_5m.iloc[i]['high']
                is_swing = all(
                    current_price >= df_5m.iloc[j]['high']
                    for j in range(i - self.swing_lookback, i + self.swing_lookback + 1)
                    if j != i
                )
            else:  # low
                current_price = df_5m.iloc[i]['low']
                is_swing = all(
                    current_price <= df_5m.iloc[j]['low']
                    for j in range(i - self.swing_lookback, i + self.swing_lookback + 1)
                    if j != i
                )

            if is_swing:
                swings.append(SwingPoint5M(
                    index=i,
                    timestamp=df_5m.iloc[i]['timestamp'],
                    price=current_price,
                    swing_type=swing_type
                ))

        return swings

    def build_trendline_from_swings(
        self,
        swings: List[SwingPoint5M],
        df_5m: pd.DataFrame,
        line_type: str
    ) -> Optional[Trendline5M]:
        """
        Build trendline connecting 2-3 swing points

        Key: STOP at first break, don't extend beyond
        """
        if len(swings) < self.min_touches:
            return None

        # Try 2 touches, then 3, then 4 (prefer shorter lines)
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

            # Check if good fit (R² > 0.95)
            if r_squared < 0.95:
                continue

            # Create trendline
            trendline = Trendline5M(
                swing_points=candidate_swings,
                line_type=line_type,
                slope=slope,
                intercept=intercept,
                state=TrendlineState.ACTIVE,
                r_squared=r_squared
            )

            # Check for breaks after last touch
            last_index = candidate_swings[-1].index

            for i in range(last_index + 1, len(df_5m)):
                candle = df_5m.iloc[i]
                expected = trendline.price_at_index(i)

                is_broken = False
                if line_type == 'resistance':
                    # Broken if close above line
                    is_broken = candle['close'] > expected
                else:  # support
                    # Broken if close below line
                    is_broken = candle['close'] < expected

                if is_broken:
                    trendline.state = TrendlineState.BROKEN
                    trendline.break_index = i
                    trendline.break_timestamp = candle['timestamp']
                    trendline.break_price = candle['close']
                    break

            return trendline

        return None

    def detect(self, df_15m: pd.DataFrame, df_5m: pd.DataFrame, recent_5m_bars: int = 200) -> List[Trendline5M]:
        """
        Main detection pipeline - NOW DETECTS BOTH INITIAL TREND AND NEW TREND AFTER BREAK

        Args:
            df_15m: 15M data for trend context
            df_5m: 5M data for precise trendline
            recent_5m_bars: Focus on recent N bars on 5M (200 bars = ~16 hours)

        Returns:
            List of Trendline5M objects (initial trend + new trend after break)
        """
        print("\n" + "="*80)
        print("5-MINUTE DUAL TRENDLINE DETECTION")
        print("="*80)
        print("[GOAL] Detect BOTH initial trend AND new trend that breaks it")

        detected_trendlines = []

        # Step 1: Get trend direction from 15M
        print("\n[STEP 1] Checking trend direction on 15M...")
        trend_direction = self.detect_trend_direction_15m(df_15m, recent_bars=20)
        print(f"  15M Trend: {trend_direction.upper()}")

        if trend_direction == 'range':
            print("  [WARNING] No clear trend detected")
            # Try to detect anyway using recent price action
            recent_5m = df_5m.tail(recent_5m_bars)
            if recent_5m['close'].iloc[-1] < recent_5m['close'].iloc[0]:
                trend_direction = 'downtrend'
                print(f"  [OVERRIDE] Recent 5M price action suggests DOWNTREND")

        # Step 2: Detect swings on 5M
        print("\n[STEP 2] Detecting swing points on 5M...")
        recent_5m = df_5m.tail(recent_5m_bars).reset_index(drop=True)
        print(f"  Analyzing recent {len(recent_5m)} candles (~{len(recent_5m)*5/60:.1f} hours)")
        print(f"  Time range: {recent_5m['timestamp'].iloc[0]} to {recent_5m['timestamp'].iloc[-1]}")

        # Detect BOTH swing highs and lows
        swing_highs = self.detect_swings_5m(recent_5m, 'high')
        swing_lows = self.detect_swings_5m(recent_5m, 'low')
        print(f"  Found {len(swing_highs)} swing HIGHS")
        print(f"  Found {len(swing_lows)} swing LOWS")

        # Step 3: Build initial trendline based on trend direction
        print("\n[STEP 3] Building INITIAL trendline...")

        initial_trendline = None
        if trend_direction == 'downtrend' and len(swing_highs) >= 2:
            print("  Downtrend - building RESISTANCE line from swing highs")
            initial_trendline = self.build_trendline_from_swings(swing_highs, recent_5m, 'resistance')
        elif trend_direction == 'uptrend' and len(swing_lows) >= 2:
            print("  Uptrend - building SUPPORT line from swing lows")
            initial_trendline = self.build_trendline_from_swings(swing_lows, recent_5m, 'support')

        if initial_trendline:
            print(f"  [INITIAL TREND] {initial_trendline}")
            print(f"  R²: {initial_trendline.r_squared:.4f}")
            detected_trendlines.append(initial_trendline)

            if initial_trendline.state == TrendlineState.BROKEN:
                print(f"  [BREAK DETECTED] @ {initial_trendline.break_timestamp.strftime('%H:%M')}")

                # Step 4: Detect NEW trend after break
                print("\n[STEP 4] Detecting NEW TREND after break...")

                # Get data after the break
                break_index = initial_trendline.break_index
                data_after_break = recent_5m.iloc[break_index:].reset_index(drop=True)

                print(f"  Analyzing {len(data_after_break)} candles after break")

                # If initial was downtrend (resistance), look for uptrend (support) after break
                if initial_trendline.line_type == 'resistance':
                    print("  Initial was DOWNTREND - looking for UPTREND after break...")
                    # Find swing lows in data after break
                    new_swings = [s for s in swing_lows if s.index >= break_index]
                    if len(new_swings) >= 2:
                        print(f"    Found {len(new_swings)} swing lows after break")
                        # Adjust indices relative to data_after_break
                        for swing in new_swings:
                            swing.index = swing.index - break_index

                        new_trendline = self.build_trendline_from_swings(new_swings, data_after_break, 'support')
                        if new_trendline:
                            print(f"  [NEW TREND] {new_trendline} (UPTREND)")
                            # Adjust indices back
                            for swing in new_trendline.swing_points:
                                swing.index = swing.index + break_index
                            if new_trendline.break_index is not None:
                                new_trendline.break_index += break_index
                            detected_trendlines.append(new_trendline)

                # If initial was uptrend (support), look for downtrend (resistance) after break
                elif initial_trendline.line_type == 'support':
                    print("  Initial was UPTREND - looking for DOWNTREND after break...")
                    new_swings = [s for s in swing_highs if s.index >= break_index]
                    if len(new_swings) >= 2:
                        print(f"    Found {len(new_swings)} swing highs after break")
                        for swing in new_swings:
                            swing.index = swing.index - break_index

                        new_trendline = self.build_trendline_from_swings(new_swings, data_after_break, 'resistance')
                        if new_trendline:
                            print(f"  [NEW TREND] {new_trendline} (DOWNTREND)")
                            for swing in new_trendline.swing_points:
                                swing.index = swing.index + break_index
                            if new_trendline.break_index is not None:
                                new_trendline.break_index += break_index
                            detected_trendlines.append(new_trendline)

        print("\n" + "="*80)
        print(f"DETECTED {len(detected_trendlines)} TRENDLINE(S)")
        print("="*80)
        return detected_trendlines

    def print_results(self, trendline: Optional[Trendline5M]):
        """Print detailed results"""

        if not trendline:
            print("\nNo trendline detected")
            return

        print("\n" + "="*80)
        print("TRENDLINE DETAILS")
        print("="*80)

        print(f"\n[TYPE] {trendline.line_type.upper()}")
        print(f"[STATE] {trendline.state.value.upper()}")
        print(f"[TOUCHES] {len(trendline.swing_points)}")
        print(f"[R²] {trendline.r_squared:.4f}")

        print(f"\n[TOUCH POINTS - UTC]")
        for i, swing in enumerate(trendline.swing_points, 1):
            print(f"  {i}. {swing.timestamp.strftime('%Y-%m-%d %H:%M')} @ ${swing.price:.2f}")

        print(f"\n[TOUCH POINTS - NIGERIA TIME UTC+1]")
        from datetime import timedelta
        for i, swing in enumerate(trendline.swing_points, 1):
            nigeria_time = swing.timestamp + timedelta(hours=1)
            print(f"  {i}. {nigeria_time.strftime('%Y-%m-%d %H:%M')} @ ${swing.price:.2f}")

        if trendline.state == TrendlineState.BROKEN:
            print(f"\n[BREAK DETAILS]")
            print(f"  UTC Time: {trendline.break_timestamp.strftime('%Y-%m-%d %H:%M')}")
            nigeria_break = trendline.break_timestamp + timedelta(hours=1)
            print(f"  Nigeria Time: {nigeria_break.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Price: ${trendline.break_price:.2f}")
            print(f"  Expected: ${trendline.price_at_index(trendline.break_index):.2f}")

        print(f"\n[KEY POINTS]")
        print(f"  - This trendline has {len(trendline.swing_points)} touches (not 500+ candles)")
        print(f"  - Built on 5M timeframe (optimal precision)")
        if trendline.state == TrendlineState.BROKEN:
            print(f"  - Line STOPPED at break, not extended to later touches")
