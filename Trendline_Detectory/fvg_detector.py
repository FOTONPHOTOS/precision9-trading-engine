"""
Fair Value Gap (FVG) Detector - Smart Money Concepts
====================================================

Detects imbalance gaps where price moved too fast, creating inefficiencies.
These gaps often act as magnets for price to return and "fill the gap".

FVG Types:
- Bullish FVG: Gap below current price (demand zone)
- Bearish FVG: Gap above current price (supply zone)

Author: Precision9 Team - Market Structure Arsenal
Date: 2025-10-09
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class FairValueGap:
    """Represents a detected Fair Value Gap"""
    gap_type: str  # 'bullish' or 'bearish'
    gap_start: float  # Lower bound of gap
    gap_end: float  # Upper bound of gap
    gap_size: float  # Size in price
    gap_size_pct: float  # Size as percentage
    formation_time: datetime
    formation_index: int

    # Gap characteristics
    strength: float  # 0-1, based on size and volume
    fill_status: str  # 'unfilled', 'partial', 'complete'
    fill_percentage: float  # 0-100%
    touch_count: int  # How many times price touched

    # Context
    volume_spike: bool  # Was there volume spike during formation
    trend_context: str  # 'uptrend', 'downtrend', 'range'
    mitigation_zone: Tuple[float, float]  # 50% fill zone (key area)

    # Quality metrics
    quality_score: float  # 0-1 overall quality
    retest_probability: float  # 0-1 probability of retest


class FVGDetector:
    """
    Detects Fair Value Gaps (FVGs) in market data

    FVG Formation:
    - 3 candles pattern
    - Candle 1 and Candle 3 don't overlap
    - Gap between them = FVG

    Bullish FVG: Candle 1 high < Candle 3 low
    Bearish FVG: Candle 1 low > Candle 3 high
    """

    def __init__(self,
                 min_gap_size_pct: float = 0.1,
                 max_gap_size_pct: float = 5.0,
                 min_volume_ratio: float = 1.2):
        """
        Initialize FVG Detector

        Args:
            min_gap_size_pct: Minimum gap size as % of price (filter noise)
            max_gap_size_pct: Maximum gap size (filter extreme gaps)
            min_volume_ratio: Minimum volume ratio for strength
        """
        self.min_gap_size_pct = min_gap_size_pct
        self.max_gap_size_pct = max_gap_size_pct
        self.min_volume_ratio = min_volume_ratio

        self.detected_fvgs = []

    def detect(self, df: pd.DataFrame, current_price: Optional[float] = None) -> List[FairValueGap]:
        """
        Detect all FVGs in the dataframe

        Args:
            df: DataFrame with OHLCV data
            current_price: Current market price (for fill status)

        Returns:
            List of detected Fair Value Gaps
        """
        if len(df) < 3:
            logger.warning("Need at least 3 candles to detect FVGs")
            return []

        if current_price is None:
            current_price = df.iloc[-1]['close']

        fvgs = []

        # Iterate through all possible 3-candle patterns
        for i in range(2, len(df)):
            candle_1 = df.iloc[i-2]
            candle_2 = df.iloc[i-1]  # Middle candle (impulse move)
            candle_3 = df.iloc[i]

            # Check for Bullish FVG (gap below)
            if candle_1['high'] < candle_3['low']:
                gap_start = candle_1['high']
                gap_end = candle_3['low']
                gap_type = 'bullish'

                fvg = self._create_fvg(
                    gap_type, gap_start, gap_end,
                    candle_1, candle_2, candle_3,
                    i, current_price, df
                )

                if fvg and self._is_valid_fvg(fvg):
                    fvgs.append(fvg)

            # Check for Bearish FVG (gap above)
            elif candle_1['low'] > candle_3['high']:
                gap_start = candle_3['high']
                gap_end = candle_1['low']
                gap_type = 'bearish'

                fvg = self._create_fvg(
                    gap_type, gap_start, gap_end,
                    candle_1, candle_2, candle_3,
                    i, current_price, df
                )

                if fvg and self._is_valid_fvg(fvg):
                    fvgs.append(fvg)

        # Calculate fill status for all FVGs
        for fvg in fvgs:
            self._update_fill_status(fvg, df, current_price)

        # Sort by formation time (most recent first)
        fvgs.sort(key=lambda x: x.formation_index, reverse=True)

        logger.info(f"Detected {len(fvgs)} FVGs ({sum(1 for f in fvgs if f.gap_type == 'bullish')} bullish, {sum(1 for f in fvgs if f.gap_type == 'bearish')} bearish)")

        self.detected_fvgs = fvgs
        return fvgs

    def _create_fvg(self,
                    gap_type: str,
                    gap_start: float,
                    gap_end: float,
                    candle_1: pd.Series,
                    candle_2: pd.Series,
                    candle_3: pd.Series,
                    formation_index: int,
                    current_price: float,
                    df: pd.DataFrame) -> Optional[FairValueGap]:
        """Create FVG object with all metrics"""

        gap_size = abs(gap_end - gap_start)
        gap_mid = (gap_start + gap_end) / 2
        gap_size_pct = (gap_size / gap_mid) * 100

        # Calculate volume spike
        avg_volume = df['volume'].rolling(10).mean().iloc[formation_index]
        candle_2_volume = candle_2['volume']
        volume_spike = candle_2_volume > (avg_volume * self.min_volume_ratio) if avg_volume > 0 else False

        # Calculate strength
        strength = self._calculate_strength(gap_size_pct, volume_spike, candle_2)

        # Determine trend context
        trend_context = self._determine_trend_context(df, formation_index)

        # Mitigation zone (50% of gap - key area)
        mitigation_zone = (
            gap_start + gap_size * 0.4,
            gap_start + gap_size * 0.6
        )

        # Quality score
        quality_score = self._calculate_quality_score(
            gap_size_pct, volume_spike, trend_context, gap_type
        )

        # Retest probability
        retest_probability = self._calculate_retest_probability(
            gap_type, current_price, gap_start, gap_end, quality_score
        )

        return FairValueGap(
            gap_type=gap_type,
            gap_start=min(gap_start, gap_end),
            gap_end=max(gap_start, gap_end),
            gap_size=gap_size,
            gap_size_pct=gap_size_pct,
            formation_time=candle_3.name,
            formation_index=formation_index,
            strength=strength,
            fill_status='unfilled',
            fill_percentage=0.0,
            touch_count=0,
            volume_spike=volume_spike,
            trend_context=trend_context,
            mitigation_zone=mitigation_zone,
            quality_score=quality_score,
            retest_probability=retest_probability
        )

    def _is_valid_fvg(self, fvg: FairValueGap) -> bool:
        """Validate FVG meets minimum criteria"""
        if fvg.gap_size_pct < self.min_gap_size_pct:
            return False
        if fvg.gap_size_pct > self.max_gap_size_pct:
            return False
        if fvg.quality_score < 0.2:  # Minimum quality threshold (was 0.3)
            return False
        return True

    def _calculate_strength(self, gap_size_pct: float, volume_spike: bool, candle: pd.Series) -> float:
        """Calculate FVG strength (0-1)"""
        strength = 0.0

        # Gap size component (50%)
        size_score = min(gap_size_pct / 2.0, 1.0) * 0.5
        strength += size_score

        # Volume component (30%)
        if volume_spike:
            strength += 0.3
        else:
            strength += 0.1

        # Candle body size component (20%)
        body_size = abs(candle['close'] - candle['open'])
        candle_range = candle['high'] - candle['low']
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        strength += body_ratio * 0.2

        return min(strength, 1.0)

    def _determine_trend_context(self, df: pd.DataFrame, index: int) -> str:
        """Determine trend context at FVG formation"""
        if index < 20:
            return 'unclear'

        # Simple trend detection using 20-period moving average
        lookback = df.iloc[max(0, index-20):index+1]
        if len(lookback) < 10:
            return 'unclear'

        ma = lookback['close'].mean()
        current_price = df.iloc[index]['close']

        if current_price > ma * 1.01:
            return 'uptrend'
        elif current_price < ma * 0.99:
            return 'downtrend'
        else:
            return 'range'

    def _calculate_quality_score(self,
                                 gap_size_pct: float,
                                 volume_spike: bool,
                                 trend_context: str,
                                 gap_type: str) -> float:
        """Calculate overall FVG quality (0-1)"""
        score = 0.0

        # Gap size (40%)
        if 0.2 <= gap_size_pct <= 2.0:  # Sweet spot
            score += 0.4
        elif 0.1 <= gap_size_pct < 0.2 or 2.0 < gap_size_pct <= 3.0:
            score += 0.25
        else:
            score += 0.1

        # Volume spike (30%)
        if volume_spike:
            score += 0.3
        else:
            score += 0.1

        # Trend alignment (30%)
        if (gap_type == 'bullish' and trend_context == 'uptrend') or \
           (gap_type == 'bearish' and trend_context == 'downtrend'):
            score += 0.3  # FVG with trend
        elif trend_context == 'range':
            score += 0.15  # Neutral
        else:
            score += 0.05  # FVG against trend (weaker)

        return min(score, 1.0)

    def _calculate_retest_probability(self,
                                     gap_type: str,
                                     current_price: float,
                                     gap_start: float,
                                     gap_end: float,
                                     quality_score: float) -> float:
        """Calculate probability of price returning to fill gap"""

        # Distance from current price
        if gap_type == 'bullish':
            # Bullish FVG below current price
            if current_price < gap_start:
                distance_pct = 0  # Already below gap
            else:
                distance_pct = ((current_price - gap_end) / current_price) * 100
        else:
            # Bearish FVG above current price
            if current_price > gap_end:
                distance_pct = 0  # Already above gap
            else:
                distance_pct = ((gap_start - current_price) / current_price) * 100

        # Probability decreases with distance
        if distance_pct < 0.5:
            distance_factor = 0.9
        elif distance_pct < 1.0:
            distance_factor = 0.7
        elif distance_pct < 2.0:
            distance_factor = 0.5
        elif distance_pct < 5.0:
            distance_factor = 0.3
        else:
            distance_factor = 0.1

        # Quality factor
        probability = quality_score * distance_factor

        return min(probability, 0.95)

    def _update_fill_status(self, fvg: FairValueGap, df: pd.DataFrame, current_price: float):
        """Update fill status based on price action after formation"""

        # Get candles after FVG formation
        candles_after = df.iloc[fvg.formation_index + 1:]

        if len(candles_after) == 0:
            return

        # Track how much of gap has been filled
        gap_range = fvg.gap_end - fvg.gap_start

        if fvg.gap_type == 'bullish':
            # Check how far price has penetrated into gap from above
            lowest_close = candles_after['close'].min()
            lowest_low = candles_after['low'].min()

            # Count touches
            touches = sum((candles_after['low'] <= fvg.gap_end) & (candles_after['low'] >= fvg.gap_start))
            fvg.touch_count = touches

            if lowest_low <= fvg.gap_start:
                # Completely filled
                fvg.fill_status = 'complete'
                fvg.fill_percentage = 100.0
            elif lowest_low < fvg.gap_end:
                # Partially filled
                fvg.fill_status = 'partial'
                fill_amount = fvg.gap_end - lowest_low
                fvg.fill_percentage = (fill_amount / gap_range) * 100
            else:
                # Unfilled
                fvg.fill_status = 'unfilled'
                fvg.fill_percentage = 0.0

        else:  # bearish
            # Check how far price has penetrated into gap from below
            highest_close = candles_after['close'].max()
            highest_high = candles_after['high'].max()

            # Count touches
            touches = sum((candles_after['high'] >= fvg.gap_start) & (candles_after['high'] <= fvg.gap_end))
            fvg.touch_count = touches

            if highest_high >= fvg.gap_end:
                # Completely filled
                fvg.fill_status = 'complete'
                fvg.fill_percentage = 100.0
            elif highest_high > fvg.gap_start:
                # Partially filled
                fvg.fill_status = 'partial'
                fill_amount = highest_high - fvg.gap_start
                fvg.fill_percentage = (fill_amount / gap_range) * 100
            else:
                # Unfilled
                fvg.fill_status = 'unfilled'
                fvg.fill_percentage = 0.0

    def get_active_fvgs(self, current_price: float, max_distance_pct: float = 5.0) -> List[FairValueGap]:
        """Get FVGs that are still active (unfilled or partially filled, near price)"""
        active = []

        for fvg in self.detected_fvgs:
            # Skip completely filled FVGs
            if fvg.fill_status == 'complete':
                continue

            # Check distance from current price
            if fvg.gap_type == 'bullish':
                distance_pct = ((current_price - fvg.gap_end) / current_price) * 100
            else:
                distance_pct = ((fvg.gap_start - current_price) / current_price) * 100

            if abs(distance_pct) <= max_distance_pct:
                active.append(fvg)

        return active

    def get_summary(self) -> Dict:
        """Get summary of detected FVGs"""
        if not self.detected_fvgs:
            return {
                'total_fvgs': 0,
                'bullish_fvgs': 0,
                'bearish_fvgs': 0,
                'unfilled': 0,
                'partial': 0,
                'complete': 0
            }

        return {
            'total_fvgs': len(self.detected_fvgs),
            'bullish_fvgs': sum(1 for f in self.detected_fvgs if f.gap_type == 'bullish'),
            'bearish_fvgs': sum(1 for f in self.detected_fvgs if f.gap_type == 'bearish'),
            'unfilled': sum(1 for f in self.detected_fvgs if f.fill_status == 'unfilled'),
            'partial': sum(1 for f in self.detected_fvgs if f.fill_status == 'partial'),
            'complete': sum(1 for f in self.detected_fvgs if f.fill_status == 'complete'),
            'avg_quality': np.mean([f.quality_score for f in self.detected_fvgs]),
            'avg_strength': np.mean([f.strength for f in self.detected_fvgs])
        }


def print_fvg_analysis(fvgs: List[FairValueGap], current_price: float):
    """Pretty print FVG analysis"""
    print("\n" + "="*80)
    print("FAIR VALUE GAP (FVG) ANALYSIS")
    print("="*80)

    if not fvgs:
        print("\nNo FVGs detected")
        return

    print(f"\nTotal FVGs Detected: {len(fvgs)}")
    print(f"Current Price: ${current_price:.2f}")

    # Separate by type
    bullish_fvgs = [f for f in fvgs if f.gap_type == 'bullish']
    bearish_fvgs = [f for f in fvgs if f.gap_type == 'bearish']

    # Show bullish FVGs (demand zones)
    if bullish_fvgs:
        print(f"\n{'='*80}")
        print(f"BULLISH FVGs (Demand Zones) - {len(bullish_fvgs)} found")
        print("="*80)

        for i, fvg in enumerate(bullish_fvgs[:5], 1):
            print(f"\n{i}. Bullish FVG @ ${fvg.gap_start:.2f} - ${fvg.gap_end:.2f}")
            print(f"   Formed: {fvg.formation_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"   Size: ${fvg.gap_size:.2f} ({fvg.gap_size_pct:.2f}%)")
            print(f"   Status: {fvg.fill_status.upper()} ({fvg.fill_percentage:.1f}% filled)")
            print(f"   Quality: {fvg.quality_score:.0%} | Strength: {fvg.strength:.0%}")
            print(f"   Retest Probability: {fvg.retest_probability:.0%}")
            print(f"   Mitigation Zone: ${fvg.mitigation_zone[0]:.2f} - ${fvg.mitigation_zone[1]:.2f}")
            print(f"   Touch Count: {fvg.touch_count}")
            print(f"   Volume Spike: {'YES' if fvg.volume_spike else 'NO'}")
            print(f"   Trend Context: {fvg.trend_context.upper()}")

            # Distance from current price
            distance = current_price - fvg.gap_end
            distance_pct = (distance / current_price) * 100
            print(f"   Distance: ${distance:+.2f} ({distance_pct:+.2f}%)")

    # Show bearish FVGs (supply zones)
    if bearish_fvgs:
        print(f"\n{'='*80}")
        print(f"BEARISH FVGs (Supply Zones) - {len(bearish_fvgs)} found")
        print("="*80)

        for i, fvg in enumerate(bearish_fvgs[:5], 1):  # Show top 5
            print(f"\n{i}. Bearish FVG @ ${fvg.gap_start:.2f} - ${fvg.gap_end:.2f}")
            print(f"   Formed: {fvg.formation_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"   Size: ${fvg.gap_size:.2f} ({fvg.gap_size_pct:.2f}%)")
            print(f"   Status: {fvg.fill_status.upper()} ({fvg.fill_percentage:.1f}% filled)")
            print(f"   Quality: {fvg.quality_score:.0%} | Strength: {fvg.strength:.0%}")
            print(f"   Retest Probability: {fvg.retest_probability:.0%}")
            print(f"   Mitigation Zone: ${fvg.mitigation_zone[0]:.2f} - ${fvg.mitigation_zone[1]:.2f}")
            print(f"   Touch Count: {fvg.touch_count}")
            print(f"   Volume Spike: {'YES' if fvg.volume_spike else 'NO'}")
            print(f"   Trend Context: {fvg.trend_context.upper()}")

            # Distance from current price
            distance = fvg.gap_start - current_price
            distance_pct = (distance / current_price) * 100
            print(f"   Distance: ${distance:+.2f} ({distance_pct:+.2f}%)")

    print("\n" + "="*80)


if __name__ == "__main__":
    import requests

    # Fetch real market data
    def fetch_binance_data(symbol: str = "SOLUSDT", interval: str = '15m', limit: int = 500):
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

        return df

    # Test FVG detector
    print("Fetching SOLUSDT data...")
    df = fetch_binance_data()
    current_price = float(df.iloc[-1]['close'])

    print(f"Analyzing {len(df)} candles...")

    detector = FVGDetector(min_gap_size_pct=0.1)
    fvgs = detector.detect(df, current_price)

    # Print analysis
    print_fvg_analysis(fvgs, current_price)

    # Print summary
    summary = detector.get_summary()
    print(f"\n{'='*80}")
    print("SUMMARY")
    print("="*80)
    for key, value in summary.items():
        print(f"{key}: {value}")
