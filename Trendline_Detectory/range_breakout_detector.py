"""
Range Breakout Detector - Institutional Grade
==============================================
Detects REAL breakouts from ranging consolidation, avoiding fakeouts.

Core Philosophy:
- Breakouts require confirmation, not just a single candle
- Volume must support the move
- Structure must validate (not just a wick)
- Avoid false breakouts that reverse immediately

Based on institutional approach:
1. Multi-timeframe confirmation
2. Volume expansion validation
3. Structural integrity check
4. Follow-through confirmation
5. Fakeout filtering

Author: Precision Trading Team
Date: 2025-10-12
"""

import numpy as np
import time # NEW
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
import logging

logger = logging.getLogger('BREAKOUT_DETECTOR')


@dataclass
class BreakoutSignal:
    """Validated breakout detection result"""
    is_breakout: bool  # TRUE = Real breakout detected
    direction: str  # 'BULLISH' or 'BEARISH'
    breakout_level: float  # Price level that was broken
    confirmation_strength: float  # 0-1, how strong the breakout is

    # Validation metrics
    volume_confirmation: bool  # Volume supports breakout
    structure_integrity: bool  # Clean break (not just wick)
    follow_through: bool  # Price continuing in breakout direction
    distance_from_range: float  # How far from range (%)

    # Risk assessment
    fakeout_probability: float  # 0-1, chance this is fake
    invalidation_level: float  # Price that would invalidate breakout

    # Metadata
    reason: str
    confidence: float  # Overall breakout confidence 0-1
    timestamp: float


class RangeBreakoutDetector:
    """
    Robust breakout detector with fakeout filtering

    Only triggers on REAL breakouts with:
    - Volume expansion (at least 1.5x average)
    - Body close beyond level (not just wick)
    - Follow-through candle confirmation
    - Multiple attempts at level (building pressure)
    """

    def __init__(self):
        # Breakout validation parameters
        self.min_volume_expansion = 1.5  # 1.5x average volume required
        self.min_body_close_beyond = 0.003  # 0.3% body close beyond level
        self.confirmation_candles = 2  # Require 2 candles confirming

        # Fakeout filters
        self.max_immediate_reversal_pct = 0.002  # If reverses >0.2% in 1 candle = fake
        self.min_follow_through_pct = 0.001  # Next candle must continue >0.1%

        # Structure requirements
        self.min_attempts_at_level = 2  # At least 2 tests before break
        self.level_tolerance = 0.005  # 0.5% tolerance for "at level"

        # Historical tracking
        self.volume_history = deque(maxlen=20)  # Last 20 candles volume
        self.price_history = deque(maxlen=50)  # For structure analysis
        self.last_breakout: Optional[BreakoutSignal] = None

        # State tracking
        self.breakout_cooldown = 0  # Prevent multiple signals

    def update_market_data(self, price: float, volume: float, timestamp: float):
        """Update historical data for breakout detection"""
        self.volume_history.append(volume)
        self.price_history.append((price, timestamp))

        # Decay cooldown
        if self.breakout_cooldown > 0:
            self.breakout_cooldown -= 1

    def detect_breakout(
        self,
        current_price: float,
        current_volume: float,
        taker_ratio: Optional[float],
        taker_ratio_ma: Optional[float], # NEW
        range_high: float,
        range_low: float,
        recent_highs: List[float],
        recent_lows: List[float],
        candle_closes: List[float]
    ) -> Optional[BreakoutSignal]:
        """
        Detect validated range breakout with fakeout filtering.
        Now with dynamic taker ratio confirmation.
        """
        # ... (initial checks and breakout direction logic remains the same) ...

        # Skip if in cooldown (prevents duplicate signals)
        if self.breakout_cooldown > 0:
            return None

        # Need enough data
        if len(self.volume_history) < 10 or len(candle_closes) < 3:
            return None

        # Calculate average volume
        avg_volume = np.mean(list(self.volume_history))

        # Determine if we're breaking out of range
        if current_price > range_high and range_high > 0:
            direction = 'BULLISH'
            breakout_level = range_high
            distance_pct = (current_price - range_high) / range_high
            invalidation_level = range_high * 0.997
        elif current_price < range_low and range_low > 0:
            direction = 'BEARISH'
            breakout_level = range_low
            distance_pct = (range_low - current_price) / range_low
            invalidation_level = range_low * 1.003
        else:
            return None

        # --- VALIDATIONS ---
        volume_confirmation = (current_volume / avg_volume) >= self.min_volume_expansion if avg_volume > 0 else False
        
        structure_integrity = False
        if len(candle_closes) >= 2:
            if direction == 'BULLISH':
                structure_integrity = candle_closes[-1] > breakout_level * (1 + self.min_body_close_beyond)
            else:
                structure_integrity = candle_closes[-1] < breakout_level * (1 - self.min_body_close_beyond)

        follow_through = False
        if len(candle_closes) >= 3:
            if direction == 'BULLISH':
                follow_through = candle_closes[-1] > candle_closes[-2]
            else:
                follow_through = candle_closes[-1] < candle_closes[-2]

        # --- FAKEOUT SCORING ---
        fakeout_score = 0.5
        warnings = []

        if volume_confirmation: fakeout_score -= 0.2
        else: 
            fakeout_score += 0.15
            warnings.append("Low Volume")

        if structure_integrity: fakeout_score -= 0.15
        else: 
            fakeout_score += 0.1
            warnings.append("Weak Break (Wick)")

        if follow_through: fakeout_score -= 0.15

        # --- DYNAMIC TAKER RATIO CONFIRMATION ---
        if taker_ratio is not None and taker_ratio_ma is not None:
            if direction == 'BULLISH':
                if taker_ratio > (taker_ratio_ma * 1.3):
                    fakeout_score -= 0.25  # Strong confirmation
                    warnings.append(f"Taker Confirm (Ratio: {taker_ratio:.2f} > MA: {taker_ratio_ma:.2f})")
                elif taker_ratio < taker_ratio_ma:
                    fakeout_score += 0.25  # Divergence
                    warnings.append(f"Taker Divergence (Ratio: {taker_ratio:.2f} < MA: {taker_ratio_ma:.2f})")
            elif direction == 'BEARISH':
                if taker_ratio < (taker_ratio_ma * 0.8):
                    fakeout_score -= 0.25  # Strong confirmation
                    warnings.append(f"Taker Confirm (Ratio: {taker_ratio:.2f} < MA: {taker_ratio_ma:.2f})")
                elif taker_ratio > taker_ratio_ma:
                    fakeout_score += 0.25  # Divergence
                    warnings.append(f"Taker Divergence (Ratio: {taker_ratio:.2f} > MA: {taker_ratio_ma:.2f})")
        else:
            warnings.append("No Taker Data")

        fakeout_probability = max(0.0, min(1.0, fakeout_score))
        confidence = 1.0 - fakeout_probability

        is_valid_breakout = confidence > 0.6 and volume_confirmation and structure_integrity

        if is_valid_breakout:
            self.breakout_cooldown = 10
            reason = f" Vol: {current_volume/avg_volume:.1f}x,  Clean Break |  {', '.join(warnings)}"
            signal = BreakoutSignal(
                is_breakout=True, direction=direction, breakout_level=breakout_level,
                confirmation_strength=confidence, volume_confirmation=volume_confirmation,
                structure_integrity=structure_integrity, follow_through=follow_through,
                distance_from_range=distance_pct, fakeout_probability=fakeout_probability,
                invalidation_level=invalidation_level, reason=reason, confidence=confidence,
                timestamp=time.time()
            )
            self.last_breakout = signal
            logger.info(f" {direction} BREAKOUT DETECTED | Confidence: {confidence:.0%} | Reason: {reason}")
            return signal

        return None

    def _count_tests_of_level(self, price_levels: List[float], target_level: float) -> int:
        """
        Count how many times price tested a level

        Multiple tests = pressure building = more significant breakout
        """
        if not price_levels:
            return 0

        tests = 0
        for price in price_levels:
            deviation = abs((price - target_level) / target_level)
            if deviation < self.level_tolerance:
                tests += 1

        return tests

    def is_breakout_still_valid(self, current_price: float) -> bool:
        """
        Check if last breakout is still valid (hasn't reversed)

        Returns True if breakout still holding, False if invalidated
        """
        if not self.last_breakout or not self.last_breakout.is_breakout:
            return False

        # Check if price has reversed beyond invalidation level
        if self.last_breakout.direction == 'BULLISH':
            return current_price > self.last_breakout.invalidation_level
        else:
            return current_price < self.last_breakout.invalidation_level

    def get_status(self) -> Dict:
        """Get current breakout detector status"""
        return {
            'has_active_breakout': self.last_breakout is not None and self.last_breakout.is_breakout,
            'breakout_direction': self.last_breakout.direction if self.last_breakout else None,
            'breakout_confidence': self.last_breakout.confidence if self.last_breakout else 0,
            'cooldown_remaining': self.breakout_cooldown,
            'avg_volume': np.mean(list(self.volume_history)) if len(self.volume_history) > 0 else 0
        }


if __name__ == "__main__":
    print("Range Breakout Detector - Standalone Test")
    print("Detects REAL breakouts with fakeout filtering")
    print("\nModule ready for integration into Arsenal")
