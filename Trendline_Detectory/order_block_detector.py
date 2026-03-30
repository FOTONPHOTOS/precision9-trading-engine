"""
Order Block Detector - Smart Money Footprints

Order Blocks (OBs) are the last opposing candle before a strong impulse move.
They represent where large institutions placed orders.

Example:
- Last bearish candle before strong bullish impulse = BULLISH Order Block (demand)
- Last bullish candle before strong bearish impulse = BEARISH Order Block (supply)

These act as strong support/resistance zones where Smart Money re-enters.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class OrderBlock:
    """Order Block structure"""
    type: str  # 'bullish' or 'bearish'
    timestamp: datetime
    high: float
    low: float
    open: float
    close: float
    mitigated: bool  # Has price returned to this OB?
    touches: int  # How many times price touched this OB
    quality_score: float  # 0-1 (based on impulse strength)
    impulse_strength: float  # Size of impulse that followed
    distance_from_price: float  # Percentage distance

    # Key levels
    entry_zone_low: float
    entry_zone_high: float
    invalidation_level: float


class OrderBlockDetector:
    """
    Detects Order Blocks - last opposing candle before impulse moves

    Algorithm:
    1. Find strong impulse moves (>1% in 1-3 candles)
    2. Identify the last opposing candle before impulse
    3. That candle is the Order Block
    4. Track if price returns (mitigation)
    """

    def __init__(self):
        self.min_impulse_strength = 0.005  # 0.5% minimum impulse (was 0.8%)
        self.strong_impulse = 0.015  # 1.5% = strong impulse
        self.lookback_candles = 5  # Look back for opposing candles

    def detect(
        self,
        df: pd.DataFrame,
        current_price: Optional[float] = None
    ) -> List[OrderBlock]:
        """
        Detect all Order Blocks in the dataframe

        Returns:
            List of OrderBlock objects
        """

        if df is None or len(df) < 10:
            return []

        if current_price is None:
            current_price = float(df.iloc[-1]['close'])

        order_blocks = []

        # Scan for impulse moves
        for i in range(self.lookback_candles, len(df) - 1):

            # Check for bullish impulse (strong upward move)
            bullish_impulse = self._detect_bullish_impulse(df, i)
            if bullish_impulse:
                ob = self._find_bullish_order_block(df, i, bullish_impulse, current_price)
                if ob:
                    order_blocks.append(ob)

            # Check for bearish impulse (strong downward move)
            bearish_impulse = self._detect_bearish_impulse(df, i)
            if bearish_impulse:
                ob = self._find_bearish_order_block(df, i, bearish_impulse, current_price)
                if ob:
                    order_blocks.append(ob)

        # Remove duplicates (overlapping OBs)
        order_blocks = self._remove_duplicates(order_blocks)

        # Check mitigation status
        for ob in order_blocks:
            ob.touches = self._count_touches(df, ob, current_price)
            ob.mitigated = ob.touches > 0

        return order_blocks

    def _detect_bullish_impulse(self, df: pd.DataFrame, index: int) -> Optional[float]:
        """
        Detect bullish impulse starting at index

        Returns:
            Impulse strength if found, None otherwise
        """

        start_price = float(df.iloc[index]['low'])

        # Check next 1-3 candles for strong upward move
        for lookforward in range(1, 4):
            if index + lookforward >= len(df):
                break

            end_price = float(df.iloc[index + lookforward]['high'])
            impulse = (end_price - start_price) / start_price

            if impulse >= self.min_impulse_strength:
                return impulse

        return None

    def _detect_bearish_impulse(self, df: pd.DataFrame, index: int) -> Optional[float]:
        """
        Detect bearish impulse starting at index

        Returns:
            Impulse strength if found, None otherwise
        """

        start_price = float(df.iloc[index]['high'])

        # Check next 1-3 candles for strong downward move
        for lookforward in range(1, 4):
            if index + lookforward >= len(df):
                break

            end_price = float(df.iloc[index + lookforward]['low'])
            impulse = (start_price - end_price) / start_price

            if impulse >= self.min_impulse_strength:
                return impulse

        return None

    def _find_bullish_order_block(
        self,
        df: pd.DataFrame,
        impulse_start: int,
        impulse_strength: float,
        current_price: float
    ) -> Optional[OrderBlock]:
        """
        Find the last bearish candle before bullish impulse
        (This is where Smart Money accumulated before pushing price up)
        """

        # Look back for the last bearish candle
        for i in range(impulse_start - 1, max(0, impulse_start - self.lookback_candles), -1):
            candle = df.iloc[i]

            is_bearish = candle['close'] < candle['open']

            if is_bearish:
                # This is the Order Block
                high = float(candle['high'])
                low = float(candle['low'])

                # Entry zone is typically 50% of the candle
                mid = (high + low) / 2
                entry_zone_low = low
                entry_zone_high = mid

                # Invalidation is below the OB
                invalidation = low * 0.998

                # Quality based on impulse strength
                quality = min(1.0, impulse_strength / self.strong_impulse)

                # Distance from current price
                distance = ((entry_zone_low + entry_zone_high) / 2 - current_price) / current_price * 100

                return OrderBlock(
                    type='bullish',
                    timestamp=candle.name,
                    high=high,
                    low=low,
                    open=float(candle['open']),
                    close=float(candle['close']),
                    mitigated=False,
                    touches=0,
                    quality_score=quality,
                    impulse_strength=impulse_strength,
                    distance_from_price=distance,
                    entry_zone_low=entry_zone_low,
                    entry_zone_high=entry_zone_high,
                    invalidation_level=invalidation
                )

        return None

    def _find_bearish_order_block(
        self,
        df: pd.DataFrame,
        impulse_start: int,
        impulse_strength: float,
        current_price: float
    ) -> Optional[OrderBlock]:
        """
        Find the last bullish candle before bearish impulse
        (This is where Smart Money distributed before pushing price down)
        """

        # Look back for the last bullish candle
        for i in range(impulse_start - 1, max(0, impulse_start - self.lookback_candles), -1):
            candle = df.iloc[i]

            is_bullish = candle['close'] > candle['open']

            if is_bullish:
                # This is the Order Block
                high = float(candle['high'])
                low = float(candle['low'])

                # Entry zone is typically 50% of the candle
                mid = (high + low) / 2
                entry_zone_low = mid
                entry_zone_high = high

                # Invalidation is above the OB
                invalidation = high * 1.002

                # Quality based on impulse strength
                quality = min(1.0, impulse_strength / self.strong_impulse)

                # Distance from current price
                distance = ((entry_zone_low + entry_zone_high) / 2 - current_price) / current_price * 100

                return OrderBlock(
                    type='bearish',
                    timestamp=candle.name,
                    high=high,
                    low=low,
                    open=float(candle['open']),
                    close=float(candle['close']),
                    mitigated=False,
                    touches=0,
                    quality_score=quality,
                    impulse_strength=impulse_strength,
                    distance_from_price=distance,
                    entry_zone_low=entry_zone_low,
                    entry_zone_high=entry_zone_high,
                    invalidation_level=invalidation
                )

        return None

    def _remove_duplicates(self, order_blocks: List[OrderBlock]) -> List[OrderBlock]:
        """Remove overlapping order blocks (keep highest quality)"""

        if not order_blocks:
            return []

        # Sort by quality
        sorted_obs = sorted(order_blocks, key=lambda x: x.quality_score, reverse=True)

        filtered = []
        for ob in sorted_obs:
            # Check if this OB overlaps with any already added
            overlaps = False
            for existing in filtered:
                if self._blocks_overlap(ob, existing):
                    overlaps = True
                    break

            if not overlaps:
                filtered.append(ob)

        return filtered

    def _blocks_overlap(self, ob1: OrderBlock, ob2: OrderBlock) -> bool:
        """Check if two order blocks overlap"""

        # Different types don't overlap
        if ob1.type != ob2.type:
            return False

        # Check price overlap
        return not (ob1.high < ob2.low or ob1.low > ob2.high)

    def _count_touches(
        self,
        df: pd.DataFrame,
        ob: OrderBlock,
        current_price: float
    ) -> int:
        """Count how many times price touched this OB after formation"""

        touches = 0

        # Find OB index
        # Use searchsorted for a more robust lookup that finds the insertion point
        ob_index = df.index.searchsorted(ob.timestamp)
        if ob_index >= len(df) or df.index[ob_index] != ob.timestamp:
            # The exact timestamp was not found, handle this gracefully
            # This can happen if the OB was detected on a different data slice.
            # We can either give up or find the nearest timestamp. For now, we give up.
            return 0

        # Check candles after OB formation
        for i in range(ob_index + 1, len(df)):
            candle_high = float(df.iloc[i]['high'])
            candle_low = float(df.iloc[i]['low'])

            # Check if candle touched the OB zone
            if ob.type == 'bullish':
                if candle_low <= ob.entry_zone_high and candle_high >= ob.entry_zone_low:
                    touches += 1
            else:  # bearish
                if candle_low <= ob.entry_zone_high and candle_high >= ob.entry_zone_low:
                    touches += 1

        return touches

    def get_active_order_blocks(
        self,
        order_blocks: List[OrderBlock],
        current_price: float,
        max_distance_pct: float = 3.0
    ) -> List[OrderBlock]:
        """
        Get order blocks within specified distance from current price

        Active OBs are the ones price might react to
        """

        active = []
        for ob in order_blocks:
            abs_distance = abs(ob.distance_from_price)
            if abs_distance <= max_distance_pct:
                # Recalculate distance
                ob.distance_from_price = ((ob.entry_zone_low + ob.entry_zone_high) / 2 - current_price) / current_price * 100
                active.append(ob)

        # Sort by distance
        active.sort(key=lambda x: abs(x.distance_from_price))

        return active


def print_order_blocks(order_blocks: List[OrderBlock], current_price: float):
    """Pretty print order blocks"""

    print("\n" + "="*80)
    print("ORDER BLOCK ANALYSIS - SMART MONEY FOOTPRINTS")
    print("="*80)

    bullish_obs = [ob for ob in order_blocks if ob.type == 'bullish']
    bearish_obs = [ob for ob in order_blocks if ob.type == 'bearish']

    print(f"\nTotal Order Blocks: {len(order_blocks)}")
    print(f"Bullish OBs (Demand): {len(bullish_obs)}")
    print(f"Bearish OBs (Supply): {len(bearish_obs)}")
    print(f"Current Price: ${current_price:.2f}")

    if bullish_obs:
        print(f"\n{'='*80}")
        print(f"BULLISH ORDER BLOCKS (Buy Zones) - {len(bullish_obs)} found")
        print(f"{'='*80}")

        for i, ob in enumerate(bullish_obs[:5], 1):
            print(f"\n{i}. Bullish OB @ ${ob.low:.2f} - ${ob.high:.2f}")
            print(f"   Entry Zone: ${ob.entry_zone_low:.2f} - ${ob.entry_zone_high:.2f}")
            print(f"   Quality: {ob.quality_score:.0%} | Impulse: {ob.impulse_strength:.2%}")
            print(f"   Status: {'MITIGATED' if ob.mitigated else 'UNTOUCHED'} ({ob.touches} touches)")
            print(f"   Distance: {ob.distance_from_price:+.2f}%")
            print(f"   Invalidation: Below ${ob.invalidation_level:.2f}")

    if bearish_obs:
        print(f"\n{'='*80}")
        print(f"BEARISH ORDER BLOCKS (Sell Zones) - {len(bearish_obs)} found")
        print(f"{'='*80}")

        for i, ob in enumerate(bearish_obs[:5], 1):
            print(f"\n{i}. Bearish OB @ ${ob.low:.2f} - ${ob.high:.2f}")
            print(f"   Entry Zone: ${ob.entry_zone_low:.2f} - ${ob.entry_zone_high:.2f}")
            print(f"   Quality: {ob.quality_score:.0%} | Impulse: {ob.impulse_strength:.2%}")
            print(f"   Status: {'MITIGATED' if ob.mitigated else 'UNTOUCHED'} ({ob.touches} touches)")
            print(f"   Distance: {ob.distance_from_price:+.2f}%")
            print(f"   Invalidation: Above ${ob.invalidation_level:.2f}")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    from realtime_swing_detector import fetch_binance_data

    print("Order Block Detector - Standalone Test")
    print("Detecting Smart Money footprints...")

    df = fetch_binance_data("SOLUSDT", "15m", 100)
    current_price = float(df.iloc[-1]['close'])

    detector = OrderBlockDetector()
    obs = detector.detect(df, current_price)

    print(f"\nFound {len(obs)} Order Blocks")

    active_obs = detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)
    print(f"Active OBs (within 3%): {len(active_obs)}")

    print_order_blocks(active_obs, current_price)
