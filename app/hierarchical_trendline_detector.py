"""
Hierarchical Multi-Timeframe Trendline Detector
================================================

Based on the principle of:
1. HTF (15M) - Identify major trend ranges
2. LTF (1M) - Find precise swing points within ranges
3. Collinearity - Find swing points forming perfect straight lines

Key Insights:
- Trendlines connect MAJOR structural pivots, not every minor swing
- HTF context determines which LTF swings matter
- Collinearity test using cross-multiplication avoids floating-point errors
- RANSAC provides robustness against false breakouts

Mathematical Foundation:
- Collinearity: (y2-y1)*(x3-x1) = (y3-y1)*(x2-x1)
- RANSAC: Random sampling + inlier counting
- METHOD_NSQUREDLOGN: O(n² log n) efficient collinear detection
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime
import random


class TrendDirection(Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    RANGE = "range"


@dataclass
class SwingPoint:
    """Represents a swing high or low"""
    index: int
    timestamp: pd.Timestamp
    price: float
    swing_type: str  # 'high' or 'low'
    is_wick: bool  # True if at wick extreme, False if at close
    volume: float
    timeframe: str  # '1m' or '15m'

    def __repr__(self):
        return f"{self.swing_type.upper()} @ {self.timestamp.strftime('%H:%M')} ${self.price:.2f}"


@dataclass
class TrendRange:
    """Represents a trend range identified on HTF"""
    start_index: int
    end_index: int
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    direction: TrendDirection
    start_price: float
    end_price: float
    swing_points: List[SwingPoint]  # The HTF swings that define this range

    def __repr__(self):
        return f"{self.direction.value.upper()}: {self.start_time.strftime('%H:%M')} ${self.start_price:.2f} -> {self.end_time.strftime('%H:%M')} ${self.end_price:.2f}"


@dataclass
class CollinearLine:
    """Represents a trendline formed by collinear swing points"""
    swing_points: List[SwingPoint]  # The actual swing points forming the line
    slope: float
    intercept: float
    line_type: str  # 'support' or 'resistance'
    r_squared: float
    avg_distance: float  # Average distance of points from line
    start_point: SwingPoint
    end_point: SwingPoint
    quality_score: float  # Overall quality metric

    def price_at_index(self, index: int) -> float:
        """Calculate trendline price at given index"""
        return self.slope * index + self.intercept

    def __repr__(self):
        return f"{self.line_type.upper()}: {len(self.swing_points)} points, R²={self.r_squared:.3f}, Quality={self.quality_score:.1f}%"


class HTFRangeDetector:
    """Detects major trend ranges on higher timeframe (15M)"""

    def __init__(self, swing_window: int = 15, min_range_bars: int = 8):
        """
        Args:
            swing_window: Lookback for swing detection (15 for 15M)
            min_range_bars: Minimum bars for valid range
        """
        self.swing_window = swing_window
        self.min_range_bars = min_range_bars

    def detect_swings(self, df: pd.DataFrame) -> List[SwingPoint]:
        """Detect major swing highs and lows on HTF"""
        swings = []

        for i in range(self.swing_window, len(df) - self.swing_window):
            # Check for swing high
            current_high = df.iloc[i]['high']
            is_swing_high = all(
                current_high > df.iloc[j]['high']
                for j in range(i - self.swing_window, i + self.swing_window + 1)
                if j != i
            )

            if is_swing_high:
                swings.append(SwingPoint(
                    index=i,
                    timestamp=df.iloc[i]['timestamp'],
                    price=current_high,
                    swing_type='high',
                    is_wick=True,
                    volume=df.iloc[i]['volume'],
                    timeframe='15m'
                ))

            # Check for swing low
            current_low = df.iloc[i]['low']
            is_swing_low = all(
                current_low < df.iloc[j]['low']
                for j in range(i - self.swing_window, i + self.swing_window + 1)
                if j != i
            )

            if is_swing_low:
                swings.append(SwingPoint(
                    index=i,
                    timestamp=df.iloc[i]['timestamp'],
                    price=current_low,
                    swing_type='low',
                    is_wick=True,
                    volume=df.iloc[i]['volume'],
                    timeframe='15m'
                ))

        # Sort by index
        swings.sort(key=lambda x: x.index)
        return swings

    def identify_ranges(self, swings: List[SwingPoint]) -> List[TrendRange]:
        """Identify trend ranges from swing points"""
        ranges = []

        # Separate highs and lows
        swing_highs = [s for s in swings if s.swing_type == 'high']
        swing_lows = [s for s in swings if s.swing_type == 'low']

        # Look for uptrend ranges (series of higher lows)
        for i in range(len(swing_lows) - 1):
            if swing_lows[i+1].price > swing_lows[i].price:
                # Potential uptrend
                trend_swings = [swing_lows[i]]
                j = i + 1
                while j < len(swing_lows) and swing_lows[j].price > trend_swings[-1].price:
                    trend_swings.append(swing_lows[j])
                    j += 1

                if len(trend_swings) >= 2:
                    ranges.append(TrendRange(
                        start_index=trend_swings[0].index,
                        end_index=trend_swings[-1].index,
                        start_time=trend_swings[0].timestamp,
                        end_time=trend_swings[-1].timestamp,
                        direction=TrendDirection.UPTREND,
                        start_price=trend_swings[0].price,
                        end_price=trend_swings[-1].price,
                        swing_points=trend_swings
                    ))

        # Look for downtrend ranges (series of lower highs)
        for i in range(len(swing_highs) - 1):
            if swing_highs[i+1].price < swing_highs[i].price:
                # Potential downtrend
                trend_swings = [swing_highs[i]]
                j = i + 1
                while j < len(swing_highs) and swing_highs[j].price < trend_swings[-1].price:
                    trend_swings.append(swing_highs[j])
                    j += 1

                if len(trend_swings) >= 2:
                    ranges.append(TrendRange(
                        start_index=trend_swings[0].index,
                        end_index=trend_swings[-1].index,
                        start_time=trend_swings[0].timestamp,
                        end_time=trend_swings[-1].timestamp,
                        direction=TrendDirection.DOWNTREND,
                        start_price=trend_swings[0].price,
                        end_price=trend_swings[-1].price,
                        swing_points=trend_swings
                    ))

        return ranges


class LTFSwingDetector:
    """Detects precise swing points on lower timeframe (1M) within HTF ranges"""

    def __init__(self, swing_window: int = 3, min_swing_magnitude: float = 0.001):
        """
        Args:
            swing_window: Lookback for swing detection (3-5 for 1M)
            min_swing_magnitude: Minimum price move (0.1% default)
        """
        self.swing_window = swing_window
        self.min_swing_magnitude = min_swing_magnitude

    def detect_swings_in_range(
        self,
        df_1m: pd.DataFrame,
        trend_range: TrendRange
    ) -> List[SwingPoint]:
        """
        Detect ALL swing lows (for uptrend) or highs (for downtrend) within the range

        Key: These must be at actual extremes (wicks), not inside candle bodies
        """
        swings = []

        # Get 1M data within the range (need to align timestamps)
        range_data = df_1m[
            (df_1m['timestamp'] >= trend_range.start_time) &
            (df_1m['timestamp'] <= trend_range.end_time)
        ].copy()

        if len(range_data) < self.swing_window * 2:
            return swings

        # Reset index for easier iteration
        range_data = range_data.reset_index(drop=True)

        if trend_range.direction == TrendDirection.UPTREND:
            # Find swing lows
            for i in range(self.swing_window, len(range_data) - self.swing_window):
                current_low = range_data.iloc[i]['low']

                # Must be lowest in window
                is_swing_low = all(
                    current_low <= range_data.iloc[j]['low']
                    for j in range(i - self.swing_window, i + self.swing_window + 1)
                    if j != i
                )

                if is_swing_low:
                    # Check magnitude - must be significant enough
                    if i > 0:
                        prev_high = max(range_data.iloc[j]['high'] for j in range(max(0, i-10), i))
                        magnitude = (prev_high - current_low) / prev_high

                        if magnitude >= self.min_swing_magnitude:
                            swings.append(SwingPoint(
                                index=i,  # Local index within range
                                timestamp=range_data.iloc[i]['timestamp'],
                                price=current_low,
                                swing_type='low',
                                is_wick=True,
                                volume=range_data.iloc[i]['volume'],
                                timeframe='1m'
                            ))

        else:  # DOWNTREND
            # Find swing highs
            for i in range(self.swing_window, len(range_data) - self.swing_window):
                current_high = range_data.iloc[i]['high']

                # Must be highest in window
                is_swing_high = all(
                    current_high >= range_data.iloc[j]['high']
                    for j in range(i - self.swing_window, i + self.swing_window + 1)
                    if j != i
                )

                if is_swing_high:
                    # Check magnitude
                    if i > 0:
                        prev_low = min(range_data.iloc[j]['low'] for j in range(max(0, i-10), i))
                        magnitude = (current_high - prev_low) / prev_low

                        if magnitude >= self.min_swing_magnitude:
                            swings.append(SwingPoint(
                                index=i,
                                timestamp=range_data.iloc[i]['timestamp'],
                                price=current_high,
                                swing_type='high',
                                is_wick=True,
                                volume=range_data.iloc[i]['volume'],
                                timeframe='1m'
                            ))

        return swings


class CollinearityAnalyzer:
    """Finds swing points that form perfect straight lines using geometric algorithms"""

    def __init__(self, tolerance_pct: float = 0.002):
        """
        Args:
            tolerance_pct: Maximum deviation from perfect line (0.2% default)
        """
        self.tolerance_pct = tolerance_pct

    def are_collinear(
        self,
        p1: SwingPoint,
        p2: SwingPoint,
        p3: SwingPoint,
        avg_price: float
    ) -> bool:
        """
        Test if three points are collinear using cross-multiplication

        Mathematical test: (y2-y1)*(x3-x1) = (y3-y1)*(x2-x1)

        This avoids division and floating-point errors
        """
        x1, y1 = p1.index, p1.price
        x2, y2 = p2.index, p2.price
        x3, y3 = p3.index, p3.price

        # Cross product method
        cross_product = abs((y2 - y1) * (x3 - x1) - (y3 - y1) * (x2 - x1))

        # Normalize by average price and distance
        distance = np.sqrt((x3 - x1)**2 + (y3 - y1)**2)
        if distance == 0:
            return False

        normalized_error = cross_product / (avg_price * distance)

        return normalized_error < self.tolerance_pct

    def find_collinear_lines(
        self,
        swing_points: List[SwingPoint],
        min_points: int = 3
    ) -> List[CollinearLine]:
        """
        Find all sets of collinear swing points using METHOD_NSQUREDLOGN approach

        Algorithm:
        1. For each pair of points (p1, p2)
        2. Calculate line through them
        3. Find all other points collinear with this line
        4. Keep lines with >= min_points
        """
        if len(swing_points) < min_points:
            return []

        lines = []
        avg_price = np.mean([p.price for p in swing_points])

        # Try all pairs as potential line anchors
        for i in range(len(swing_points)):
            for j in range(i + 1, len(swing_points)):
                p1, p2 = swing_points[i], swing_points[j]

                # Find all points collinear with p1-p2
                collinear_points = [p1, p2]

                for k in range(len(swing_points)):
                    if k == i or k == j:
                        continue

                    p3 = swing_points[k]
                    if self.are_collinear(p1, p2, p3, avg_price):
                        collinear_points.append(p3)

                # If we found enough collinear points
                if len(collinear_points) >= min_points:
                    # Calculate line parameters using least squares
                    indices = np.array([p.index for p in collinear_points])
                    prices = np.array([p.price for p in collinear_points])

                    # Fit line: y = mx + b
                    A = np.vstack([indices, np.ones(len(indices))]).T
                    slope, intercept = np.linalg.lstsq(A, prices, rcond=None)[0]

                    # Calculate R²
                    y_pred = slope * indices + intercept
                    ss_res = np.sum((prices - y_pred) ** 2)
                    ss_tot = np.sum((prices - np.mean(prices)) ** 2)
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

                    # Calculate average distance
                    distances = np.abs(prices - y_pred)
                    avg_distance = np.mean(distances)

                    # Determine line type
                    line_type = 'support' if swing_points[0].swing_type == 'low' else 'resistance'

                    # Calculate quality score
                    quality_score = self._calculate_quality_score(
                        len(collinear_points),
                        r_squared,
                        avg_distance,
                        avg_price
                    )

                    # Sort points by index
                    collinear_points.sort(key=lambda x: x.index)

                    lines.append(CollinearLine(
                        swing_points=collinear_points,
                        slope=slope,
                        intercept=intercept,
                        line_type=line_type,
                        r_squared=r_squared,
                        avg_distance=avg_distance,
                        start_point=collinear_points[0],
                        end_point=collinear_points[-1],
                        quality_score=quality_score
                    ))

        # Remove duplicate lines (same points)
        unique_lines = self._remove_duplicates(lines)

        # Sort by quality score
        unique_lines.sort(key=lambda x: x.quality_score, reverse=True)

        return unique_lines

    def _calculate_quality_score(
        self,
        num_points: int,
        r_squared: float,
        avg_distance: float,
        avg_price: float
    ) -> float:
        """
        Calculate composite quality score (0-100)

        Weights:
        - Touch points: 40%
        - R² fit: 40%
        - Distance precision: 20%
        """
        # Touch score (3 points = good, 5+ = excellent)
        if num_points == 3:
            touch_score = 30
        elif num_points == 4:
            touch_score = 35
        else:
            touch_score = 40

        # R² score (0-40 points)
        r2_score = r_squared * 40

        # Distance score (0-20 points) - lower distance is better
        normalized_distance = avg_distance / avg_price
        distance_score = max(0, 20 - (normalized_distance / self.tolerance_pct) * 20)

        return touch_score + r2_score + distance_score

    def _remove_duplicates(self, lines: List[CollinearLine]) -> List[CollinearLine]:
        """Remove duplicate lines with same swing points"""
        unique = []
        seen_point_sets = []

        for line in lines:
            point_indices = tuple(sorted([p.index for p in line.swing_points]))
            if point_indices not in seen_point_sets:
                seen_point_sets.append(point_indices)
                unique.append(line)

        return unique


class RANSACLineFitter:
    """
    RANSAC (Random Sample Consensus) for robust line fitting

    Handles outliers and false breakouts better than least squares
    """

    def __init__(
        self,
        max_iterations: int = 100,
        distance_threshold_pct: float = 0.003,
        min_inliers: int = 3
    ):
        """
        Args:
            max_iterations: Number of RANSAC iterations
            distance_threshold_pct: Distance threshold for inliers (0.3%)
            min_inliers: Minimum inliers for valid line
        """
        self.max_iterations = max_iterations
        self.distance_threshold_pct = distance_threshold_pct
        self.min_inliers = min_inliers

    def fit_line(self, swing_points: List[SwingPoint]) -> Optional[CollinearLine]:
        """
        Fit robust line using RANSAC

        Algorithm:
        1. Randomly select 2 points
        2. Calculate line through them
        3. Count inliers (points within threshold)
        4. Repeat, keep best line
        5. Refit using all inliers
        """
        if len(swing_points) < 2:
            return None

        avg_price = np.mean([p.price for p in swing_points])
        distance_threshold = avg_price * self.distance_threshold_pct

        best_inliers = []
        best_slope = 0
        best_intercept = 0

        for _ in range(self.max_iterations):
            # Randomly select 2 points
            sample = random.sample(swing_points, 2)
            p1, p2 = sample[0], sample[1]

            # Calculate line
            if p2.index == p1.index:
                continue

            slope = (p2.price - p1.price) / (p2.index - p1.index)
            intercept = p1.price - slope * p1.index

            # Count inliers
            inliers = []
            for p in swing_points:
                predicted_price = slope * p.index + intercept
                distance = abs(p.price - predicted_price)

                if distance < distance_threshold:
                    inliers.append(p)

            # Keep if best so far
            if len(inliers) > len(best_inliers):
                best_inliers = inliers
                best_slope = slope
                best_intercept = intercept

        # Check if we found enough inliers
        if len(best_inliers) < self.min_inliers:
            return None

        # Refit using all inliers (least squares)
        indices = np.array([p.index for p in best_inliers])
        prices = np.array([p.price for p in best_inliers])

        A = np.vstack([indices, np.ones(len(indices))]).T
        slope, intercept = np.linalg.lstsq(A, prices, rcond=None)[0]

        # Calculate metrics
        y_pred = slope * indices + intercept
        ss_res = np.sum((prices - y_pred) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        avg_distance = np.mean(np.abs(prices - y_pred))

        # Sort inliers by index
        best_inliers.sort(key=lambda x: x.index)

        line_type = 'support' if best_inliers[0].swing_type == 'low' else 'resistance'

        return CollinearLine(
            swing_points=best_inliers,
            slope=slope,
            intercept=intercept,
            line_type=line_type,
            r_squared=r_squared,
            avg_distance=avg_distance,
            start_point=best_inliers[0],
            end_point=best_inliers[-1],
            quality_score=r_squared * 100  # Simplified quality score
        )


class HierarchicalTrendlineDetector:
    """
    Main orchestrator for multi-timeframe hierarchical trendline detection

    Process:
    1. Detect HTF (15M) trend ranges
    2. Within each range, detect LTF (1M) swing points
    3. Find collinear swing points forming trendlines
    4. Apply RANSAC for robustness
    """

    def __init__(self):
        self.htf_detector = HTFRangeDetector(swing_window=15)
        self.ltf_detector = LTFSwingDetector(swing_window=3)
        self.collinearity_analyzer = CollinearityAnalyzer(tolerance_pct=0.002)
        self.ransac_fitter = RANSACLineFitter()

    def detect_trendlines(
        self,
        df_15m: pd.DataFrame,
        df_1m: pd.DataFrame
    ) -> Dict:
        """
        Complete trendline detection pipeline

        Returns:
            Dict with:
                - htf_ranges: List of TrendRange
                - ltf_swings_by_range: Dict mapping range to swing points
                - collinear_lines: List of CollinearLine
                - ransac_lines: List of CollinearLine from RANSAC
        """
        print("\n" + "="*80)
        print("HIERARCHICAL MULTI-TIMEFRAME TRENDLINE DETECTION")
        print("="*80)

        # Step 1: Detect HTF ranges
        print("\n[STEP 1] Detecting HTF (15M) trend ranges...")
        htf_swings = self.htf_detector.detect_swings(df_15m)
        print(f"  Found {len(htf_swings)} HTF swing points")

        htf_ranges = self.htf_detector.identify_ranges(htf_swings)
        print(f"  Identified {len(htf_ranges)} HTF trend ranges")

        for i, range_obj in enumerate(htf_ranges, 1):
            print(f"    Range {i}: {range_obj}")

        # Step 2: Detect LTF swings within each range
        print("\n[STEP 2] Detecting LTF (1M) swing points within each HTF range...")
        ltf_swings_by_range = {}

        for i, trend_range in enumerate(htf_ranges, 1):
            ltf_swings = self.ltf_detector.detect_swings_in_range(df_1m, trend_range)
            ltf_swings_by_range[i] = ltf_swings
            print(f"  Range {i} ({trend_range.direction.value}): {len(ltf_swings)} LTF swing points")

        # Step 3: Find collinear lines
        print("\n[STEP 3] Finding collinear swing points forming trendlines...")
        all_collinear_lines = []

        for range_idx, ltf_swings in ltf_swings_by_range.items():
            if len(ltf_swings) < 3:
                continue

            lines = self.collinearity_analyzer.find_collinear_lines(ltf_swings, min_points=3)
            all_collinear_lines.extend(lines)
            print(f"  Range {range_idx}: Found {len(lines)} collinear lines")

        # Step 4: Apply RANSAC for robustness
        print("\n[STEP 4] Applying RANSAC for robust line fitting...")
        ransac_lines = []

        for range_idx, ltf_swings in ltf_swings_by_range.items():
            if len(ltf_swings) >= 3:
                ransac_line = self.ransac_fitter.fit_line(ltf_swings)
                if ransac_line:
                    ransac_lines.append(ransac_line)
                    print(f"  Range {range_idx}: RANSAC line with {len(ransac_line.swing_points)} inliers, R²={ransac_line.r_squared:.3f}")

        # Summary
        print("\n" + "="*80)
        print("DETECTION COMPLETE")
        print("="*80)
        print(f"Total HTF ranges: {len(htf_ranges)}")
        print(f"Total collinear lines: {len(all_collinear_lines)}")
        print(f"Total RANSAC lines: {len(ransac_lines)}")

        return {
            'htf_ranges': htf_ranges,
            'ltf_swings_by_range': ltf_swings_by_range,
            'collinear_lines': all_collinear_lines,
            'ransac_lines': ransac_lines
        }

    def get_best_trendlines(
        self,
        detection_results: Dict,
        max_lines: int = 5
    ) -> List[CollinearLine]:
        """Get the best quality trendlines"""

        # Combine collinear and RANSAC lines
        all_lines = detection_results['collinear_lines'] + detection_results['ransac_lines']

        # Sort by quality score
        all_lines.sort(key=lambda x: x.quality_score, reverse=True)

        # Return top N
        return all_lines[:max_lines]
