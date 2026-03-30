#!/usr/bin/env python3
"""
Mean Reversion Engine - Arsenal Version (FIXED)
================================================
Activates during choppy/ranging markets to profit from price oscillation.

FIXES APPLIED:
1. Lowered Z-score threshold from 2.0 to 1.2 (more sensitive)
2. Lowered VWAP deviation from 1.5% to 0.8% (catches smaller moves)
3. Made thresholds OR instead of AND (either condition triggers)
4. Added lookback_period as parameter (was hardcoded)
5. More realistic TP/SL for tight ranges

Core Philosophy:
- Don't chase direction during chop
- Sell volatility, not momentum
- Fade extremes back to equilibrium
- Use statistical edge, not hope

Based on institutional approach:
1. Z-Score deviation measurement
2. VWAP fair value tracking
3. Liquidity spread confirmation
4. Regime-filtered activation
5. Tight risk management

Author: Precision Trading Team
Date: 2025-10-12
"""

import numpy as np
import logging
from collections import deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger('MEAN_REVERSION')
logger.setLevel(logging.DEBUG)

@dataclass
class MeanReversionSignal:
    """Mean reversion trade signal"""
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    mean_price: float  # Fair value target
    stop_loss: float
    take_profit: float  # Usually near mean

    # Statistical metrics
    z_score: float
    deviation_percent: float
    vwap_deviation: float

    # Confidence & risk
    confidence: float  # 0-1
    risk_reward_ratio: float

    # Metadata
    reason: str
    timestamp: float
    expected_reversion_time: float  # Seconds to mean


@dataclass
class MarketMean:
    """Fair value / equilibrium tracker"""
    vwap: float
    rolling_mean: float  # Simple moving average
    rolling_std: float
    median: float

    # Advanced metrics
    half_life: float  # Mean reversion speed
    z_score: float

    timestamp: float
    quality: float # How reliable is this calculation? (0-1)


class MeanReversionEngine:
    """
    Institutional mean reversion engine - FIXED VERSION

    Activates only during choppy/ranging regimes
    Fades extremes back to statistical equilibrium

    Profit Source: Price oscillation, not direction
    """

    def __init__(self, symbol: str = "SOLUSDT"):
        self.symbol = symbol

        # Fair value tracking
        self.price_history = deque(maxlen=100)  # Last 100 prices
        self.volume_history = deque(maxlen=100)  # For VWAP
        self.vwap_history = deque(maxlen=50)  # VWAP values

        # Statistical parameters - FIXED (more sensitive)
        self.lookback_period = 50  # Reverted to 50 as per user request
        self.z_score_threshold = 1.2  # LOWERED from 2.0 (was too strict)
        self.vwap_deviation_threshold = 0.005  # LOWERED from 0.015 (0.5% vs 1.5%)

        # Risk management
        self.stop_multiplier = 0.5  # % of deviation as stop
        self.target_is_mean = True  # TP at mean, not beyond

        # Half-life tracking (mean reversion speed)
        self.half_life_samples = deque(maxlen=20)
        self.avg_half_life = 300.0  # Seconds (default 5 min)

        # Regime validation
        self.is_active = False  # Only active in ranging mode
        self.last_signal: Optional[MeanReversionSignal] = None

        # Performance tracking
        self.mean_reversion_trades = []
        self.win_rate = 0.0
        self.signals_generated = 0

        logger.info(f"Mean Reversion Engine initialized for {symbol}")
        logger.info(f"  Z-score threshold: {self.z_score_threshold} (LOWERED for sensitivity)")
        logger.info(f"  VWAP deviation: {self.vwap_deviation_threshold*100:.1f}% (LOWERED for sensitivity)")

    def update_price(self, price: float, volume: float):
        """Update price history for mean calculation"""
        self.price_history.append(price)
        self.volume_history.append(volume)

        # Calculate and store VWAP
        if len(self.price_history) >= self.lookback_period:
            vwap = self._calculate_vwap()
            self.vwap_history.append(vwap)

    def calculate_market_mean(self) -> Optional[MarketMean]:
        """
        Calculate current fair value / equilibrium. Now more resilient.
        Will calculate with partial data if necessary, returning a quality score.
        """
        min_required_data = 20
        if len(self.price_history) < min_required_data:
            return None

        prices = list(self.price_history)
        
        # Quality is based on how full the history buffer is
        quality = len(prices) / self.price_history.maxlen

        # Use the most recent `lookback_period` of data available
        prices_for_calc = prices[-self.lookback_period:]

        vwap = self._calculate_vwap()
        rolling_mean = np.mean(prices_for_calc)
        rolling_std = np.std(prices_for_calc)
        median = np.median(prices_for_calc)

        current_price = prices[-1]
        z_score = (current_price - rolling_mean) / rolling_std if rolling_std > 0 else 0

        half_life = self._estimate_half_life(prices_for_calc)

        return MarketMean(
            vwap=vwap,
            rolling_mean=rolling_mean,
            rolling_std=rolling_std,
            median=median,
            half_life=half_life,
            z_score=z_score,
            timestamp=time.time(),
            quality=quality # Add quality to the output
        )

    def generate_signal(self, current_price: float, market_mean: MarketMean,
                       chop_confidence: float = 0.0) -> Tuple[Optional[MeanReversionSignal], str]:
        """
        Generate mean reversion signal - FIXED VERSION

        Returns:
            Tuple of (MeanReversionSignal or None, reason_string)
        """
        if not self.is_active:
            reason = "Mean reversion not active - skipping signal generation"
            logger.debug(reason)
            return None, reason

        if not market_mean:
            reason = "No market mean calculated yet - need more data"
            logger.debug(reason)
            return None, reason

        # Calculate deviation from mean
        mean_price = market_mean.vwap  # Use VWAP as primary mean
        deviation = current_price - mean_price
        deviation_percent = abs(deviation / mean_price)

        # Calculate Z-score
        z_score = market_mean.z_score

        # DIAGNOSTIC LOGGING (helps debug why signals don't generate)
        logger.debug(f"MR Check: Price=${current_price:.2f}, Mean=${mean_price:.2f}, "
                    f"Z={z_score:.2f}, Dev={deviation_percent*100:.2f}%")

        # FIXED: Check conditions with OR instead of AND
        # Either high Z-score OR high deviation can trigger
        z_score_met = abs(z_score) >= self.z_score_threshold
        deviation_met = deviation_percent >= self.vwap_deviation_threshold

        if not z_score_met and not deviation_met:
            reason = (f"Not stretched enough: Z={abs(z_score):.2f} (need {self.z_score_threshold}), "
                      f"Dev={deviation_percent*100:.2f}% (need {self.vwap_deviation_threshold*100:.1f}%)")
            logger.debug(reason)
            return None, reason  # Not stretched enough

        # At least one condition met - proceed with signal generation
        logger.info(f"Mean reversion opportunity detected!")
        logger.info(f"  Z-score: {z_score:.2f} {'' if z_score_met else ''}")
        logger.info(f"  Deviation: {deviation_percent*100:.2f}% {'' if deviation_met else ''}")

        # Calculate confidence FIRST (needed for quality-based TP/SL)
        # Higher Z-score = higher confidence
        # Higher chop confidence = higher confidence
        z_confidence = min(abs(z_score) / 2.5, 1.0)  # Z>2.5 = 100%
        confidence = (z_confidence * 0.6) + (chop_confidence * 0.4)

        # TIGHT TP/SL LOGIC FOR MEAN REVERSION
        # Quality-based TP distance: High quality (>0.7) = 0.46%, Low quality (<0.5) = 0.26%
        # SL: Same distance as TP (1:1 RR) - tight range needs tight stops
        if confidence >= 0.70:
            tp_distance_percent = 0.0046  # 0.46% for high quality
        elif confidence >= 0.60:
            tp_distance_percent = 0.0040  # 0.40% for good quality
        elif confidence >= 0.50:
            tp_distance_percent = 0.0033  # 0.33% for moderate quality
        else:
            tp_distance_percent = 0.0026  # 0.26% for lower quality

        # 1:1 RR - SL at same distance as TP
        sl_distance_percent = tp_distance_percent

        # Determine direction (fade the extreme)
        if deviation > 0:
            # Price above mean → SHORT (expect reversion down)
            direction = 'SHORT'
            entry_price = current_price

            # Tight TP below entry (targeting small reversion move)
            take_profit = entry_price * (1 - tp_distance_percent)

            # Tight SL above entry (1:1 RR)
            stop_loss = entry_price * (1 + sl_distance_percent)

        else:
            # Price below mean → LONG (expect reversion up)
            direction = 'LONG'
            entry_price = current_price

            # Tight TP above entry
            take_profit = entry_price * (1 + tp_distance_percent)

            # Tight SL below entry (1:1 RR)
            stop_loss = entry_price * (1 - sl_distance_percent)

        # Calculate risk/reward (should be ~1:1)
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr_ratio = reward / risk if risk > 0 else 1.0

        # Build reason
        reasons = []
        if z_score_met:
            reasons.append(f"Z-score {z_score:.2f} ({'above' if z_score > 0 else 'below'} {self.z_score_threshold})")
        if deviation_met:
            reasons.append(f"Price {deviation_percent*100:.2f}% from VWAP (>{self.vwap_deviation_threshold*100:.1f}%)")
        reasons.append(f"Expected reversion to ${mean_price:.2f}")
        reason = ", ".join(reasons)

        # Estimate time to reversion (based on half-life)
        expected_time = market_mean.half_life

        signal = MeanReversionSignal(
            direction=direction,
            entry_price=entry_price,
            mean_price=mean_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            z_score=z_score,
            deviation_percent=deviation_percent,
            vwap_deviation=deviation_percent,
            confidence=confidence,
            risk_reward_ratio=rr_ratio,
            reason=reason,
            timestamp=time.time(),
            expected_reversion_time=expected_time
        )

        self.last_signal = signal
        self.signals_generated += 1

        # Calculate actual percentages for logging
        tp_pct = abs(take_profit - entry_price) / entry_price * 100
        sl_pct = abs(stop_loss - entry_price) / entry_price * 100

        logger.warning("="*80)
        logger.warning(f" MEAN REVERSION SIGNAL #{self.signals_generated}: {direction}")
        logger.warning("="*80)
        logger.warning(f"   Entry: ${entry_price:.2f}")
        logger.warning(f"   Target: ${take_profit:.2f} ({tp_pct:.2f}% from entry) - TIGHT TP")
        logger.warning(f"   Stop: ${stop_loss:.2f} ({sl_pct:.2f}% from entry) - TIGHT SL")
        logger.warning(f"   Mean Price (VWAP): ${mean_price:.2f} (reference only)")
        logger.warning("")
        logger.warning(f"   Z-Score: {z_score:.2f} | RR: {rr_ratio:.2f}:1 | Confidence: {confidence:.1%}")
        logger.warning(f"   Signal Quality: {'HIGH' if confidence >= 0.7 else 'GOOD' if confidence >= 0.6 else 'MODERATE' if confidence >= 0.5 else 'ACCEPTABLE'}")
        logger.warning("")
        logger.warning(f"   Reason: {reason}")
        logger.warning("="*80)
        logger.warning("   MEAN REVERSION MODE: Single TP exit (no TP1/TP2 splits)")
        logger.warning("   This is a tight-range fade - quick in, quick out")
        logger.warning("="*80)

        return signal, reason

    def _calculate_vwap(self) -> float:
        """
        Calculate Volume Weighted Average Price

        VWAP = Sum(Price * Volume) / Sum(Volume)

        This is the institutional "fair value" reference
        """
        if not self.price_history or not self.volume_history:
            return 0.0

        prices = list(self.price_history)[-self.lookback_period:]
        volumes = list(self.volume_history)[-self.lookback_period:]

        if len(prices) != len(volumes):
            # Pad volumes if needed
            volumes = volumes[:len(prices)]

        if sum(volumes) == 0:
            return np.mean(prices)  # Fallback to simple mean

        vwap = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)
        return vwap

    def _estimate_half_life(self, prices: List[float]) -> float:
        """
        Estimate mean reversion half-life

        Half-life = time for deviation to decay by 50%

        Uses autocorrelation to estimate reversion speed
        """
        if len(prices) < 10:
            return self.avg_half_life  # Use default

        try:
            # Calculate first-order autocorrelation
            mean = np.mean(prices)
            deviations = [p - mean for p in prices]

            # Lag-1 autocorrelation
            numerator = sum(deviations[i] * deviations[i+1] for i in range(len(deviations)-1))
            denominator = sum(d**2 for d in deviations[:-1])

            if denominator == 0:
                return self.avg_half_life

            rho = numerator / denominator

            # Half-life formula: -ln(2) / ln(rho)
            if 0 < rho < 1:
                half_life_bars = -np.log(2) / np.log(rho)
                # Convert bars to seconds (assume 1 bar = 15 seconds on 15s timeframe)
                half_life_seconds = half_life_bars * 15

                # Store and update average
                self.half_life_samples.append(half_life_seconds)
                self.avg_half_life = np.mean(list(self.half_life_samples))

                return half_life_seconds

        except Exception as e:
            logger.debug(f"Half-life calculation error: {e}")

        return self.avg_half_life

    def activate(self, reason: str = "Choppy market detected", silent: bool = False):
        """Activate mean reversion mode"""
        if not self.is_active:
            self.is_active = True
            if not silent:
                logger.warning(f" MEAN REVERSION MODE ACTIVATED: {reason}")
                logger.warning("   Strategy: Fade extremes back to equilibrium")
                logger.warning("   Profit source: Price oscillation, not direction")
                logger.warning(f"   Thresholds: Z>{self.z_score_threshold}, Deviation>{self.vwap_deviation_threshold*100:.1f}%")

    def deactivate(self, reason: str = "Trending market detected"):
        """Deactivate mean reversion mode"""
        if self.is_active:
            self.is_active = False
            logger.warning(f" MEAN REVERSION MODE DEACTIVATED: {reason}")
            logger.warning("   Returning to directional strategy")
            if self.signals_generated > 0:
                logger.warning(f"   Mean Reversion Stats: {self.signals_generated} signals generated")

    def get_status(self) -> Dict:
        """Get current mean reversion engine status"""
        market_mean = self.calculate_market_mean()

        return {
            'active': self.is_active,
            'current_mean': market_mean.vwap if market_mean else 0,
            'z_score': market_mean.z_score if market_mean else 0,
            'half_life_seconds': self.avg_half_life,
            'total_mr_trades': len(self.mean_reversion_trades),
            'signals_generated': self.signals_generated,
            'win_rate': self.win_rate,
            'last_signal': {
                'direction': self.last_signal.direction,
                'entry': self.last_signal.entry_price,
                'target': self.last_signal.mean_price,
                'confidence': self.last_signal.confidence
            } if self.last_signal else None
        }


if __name__ == "__main__":
    print("Mean Reversion Engine - Arsenal Version (FIXED)")
    print("Lowered thresholds for better signal generation in tight ranges")
    print("\nModule ready for integration into Arsenal")
