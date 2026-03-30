"""
Arsenal Strategy Router - Intelligent Mode Switching
===================================================
Automatically switches between directional trading and mean reversion
based on market conditions.

Flow:
1. Range Trap Detector identifies tight ranges
2. Mean Reversion Engine activated during ranging markets
3. Breakout Detector identifies when range breaks
4. Switch back to directional trading after breakout confirmation

This solves the problem: "Arsenal avoiding trades in range, but also missing opportunities"

Core Logic:
- RANGING MODE → Mean Reversion (fade extremes)
- BREAKOUT CONFIRMED → Directional Trading (trend following)
- UNCLEAR → Conservative (reduced size)

Author: Precision Trading Team
Date: 2025-10-12
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import time

# Import our custom modules
from range_trap_detector import RangeTrapDetector, RangeTrapAnalysis
from range_breakout_detector import RangeBreakoutDetector, BreakoutSignal
from mean_reversion_engine import MeanReversionEngine, MeanReversionSignal

logger = logging.getLogger('ARSENAL_ROUTER')


@dataclass
class StrategyDecision:
    """Current trading strategy decision"""
    active_strategy: str  # 'DIRECTIONAL', 'MEAN_REVERSION', 'STANDBY'
    should_trade: bool  # Can we trade right now?

    # Strategy-specific signals
    mean_reversion_signal: Optional[MeanReversionSignal] = None
    directional_enabled: bool = True

    # Market state
    is_ranging: bool = False
    is_breaking_out: bool = False
    trap_severity: float = 0.0

    # Reasoning
    reason: str = ""
    confidence: float = 0.0


class ArsenalStrategyRouter:
    """
    Intelligent strategy router for Arsenal

    Manages automatic switching between:
    1. Directional Trading (trend following)
    2. Mean Reversion (ranging market fading)
    3. Standby (dangerous conditions)
    """

    def __init__(self, symbol: str = "SOLUSDT"):
        self.symbol = symbol

        # Initialize all detectors
        self.trap_detector = RangeTrapDetector()
        self.breakout_detector = RangeBreakoutDetector()
        self.mean_reversion = MeanReversionEngine(symbol)

        # State tracking
        self.current_strategy = "DIRECTIONAL"  # Start with directional
        self.last_switch_time = 0
        self.switch_cooldown = 60  # 60 seconds between switches

        # Market state
        self.range_high: Optional[float] = None
        self.range_low: Optional[float] = None
        self.in_range_mode = False
        self.breakout_confirmed = False

        # Performance tracking
        self.strategy_switches = 0
        self.mean_reversion_trades = 0
        self.directional_trades = 0

        logger.info("="*80)
        logger.info("ARSENAL STRATEGY ROUTER INITIALIZED")
        logger.info("="*80)
        logger.info(f"Symbol: {symbol}")
        logger.info("Strategies Available:")
        logger.info("  1. DIRECTIONAL - Trend following (default)")
        logger.info("  2. MEAN_REVERSION - Ranging market fading")
        logger.info("  3. STANDBY - Dangerous conditions")
        logger.info("="*80)

    def update_market_data(self, price: float, volume: float, timestamp: float):
        """
        Update all sub-modules with latest market data

        Call this on every new price update
        """
        # Update mean reversion engine
        self.mean_reversion.update_price(price, volume)

        # Update breakout detector
        self.breakout_detector.update_market_data(price, volume, timestamp)

    def analyze_and_route(
        self,
        current_price: float,
        current_volume: float,
        swing_highs: list,
        swing_lows: list,
        patterns: list,
        candle_closes: list,
        chop_confidence: float = 0.0,
        trend_direction: str = "ranging",
        trend_strength: float = 0.0
    ) -> StrategyDecision:
        """
        Main routing logic - analyzes market and determines strategy
        """

        # STEP 1: Detect range trap (now with trend context)
        trap_analysis = self.trap_detector.analyze(
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            patterns=patterns,
            current_price=current_price,
            lookback_hours=4.0,
            trend_direction=trend_direction,
            trend_strength=trend_strength
        )

        # Update range boundaries
        if swing_highs and swing_lows:
            recent_highs = [s['price'] for s in swing_highs[-3:]]
            recent_lows = [s['price'] for s in swing_lows[-3:]]
            self.range_high = max(recent_highs) if recent_highs else current_price * 1.02
            self.range_low = min(recent_lows) if recent_lows else current_price * 0.98

        # STEP 2: Check for breakout (if we were in range mode)
        breakout_signal = None
        if self.in_range_mode and self.range_high and self.range_low:
            # Get recent price highs and lows for breakout validation
            recent_price_highs = [s['price'] for s in swing_highs[-10:]] if len(swing_highs) >= 10 else [s['price'] for s in swing_highs]
            recent_price_lows = [s['price'] for s in swing_lows[-10:]] if len(swing_lows) >= 10 else [s['price'] for s in swing_lows]

            breakout_signal = self.breakout_detector.detect_breakout(
                current_price=current_price,
                current_volume=current_volume,
                range_high=self.range_high,
                range_low=self.range_low,
                recent_highs=recent_price_highs,
                recent_lows=recent_price_lows,
                candle_closes=candle_closes
            )

            # If breakout confirmed, exit range mode
            if breakout_signal and breakout_signal.is_breakout:
                self.breakout_confirmed = True

        # STEP 3: Route strategy based on conditions
        decision = self._make_routing_decision(
            trap_analysis=trap_analysis,
            breakout_signal=breakout_signal,
            current_price=current_price,
            chop_confidence=chop_confidence
        )

        # Log strategy switches
        if decision.active_strategy != self.current_strategy:
            self._log_strategy_switch(self.current_strategy, decision.active_strategy, decision.reason)
            self.current_strategy = decision.active_strategy
            self.last_switch_time = time.time()
            self.strategy_switches += 1

        return decision

    def _make_routing_decision(
        self,
        trap_analysis: RangeTrapAnalysis,
        breakout_signal: Optional[BreakoutSignal],
        current_price: float,
        chop_confidence: float
    ) -> StrategyDecision:
        """
        Core routing logic

        Priority:
        1. If trapped in range + no breakout → MEAN REVERSION
        2. If breakout confirmed → DIRECTIONAL
        3. If high trap severity but not trapped → STANDBY
        4. Default → DIRECTIONAL
        """

        # Check cooldown (prevent rapid switching)
        time_since_switch = time.time() - self.last_switch_time
        if time_since_switch < self.switch_cooldown and self.current_strategy != "STANDBY":
            # Stay with current strategy (unless emergency standby)
            return self._continue_current_strategy(trap_analysis, current_price, chop_confidence)

        # SCENARIO 1: BREAKOUT CONFIRMED - Switch to directional
        if breakout_signal and breakout_signal.is_breakout and breakout_signal.confidence > 0.5: # Lowered from 0.6 for scalping
            logger.warning(f" BREAKOUT DETECTED - Switching from {self.current_strategy} to DIRECTIONAL")

            # Deactivate mean reversion
            if self.mean_reversion.is_active:
                self.mean_reversion.deactivate(f"Breakout confirmed: {breakout_signal.direction}")

            self.in_range_mode = False
            self.breakout_confirmed = True

            return StrategyDecision(
                active_strategy="DIRECTIONAL",
                should_trade=True,
                directional_enabled=True,
                mean_reversion_signal=None,
                is_ranging=False,
                is_breaking_out=True,
                trap_severity=trap_analysis.trap_severity,
                reason=f"Breakout confirmed: {breakout_signal.direction} at ${breakout_signal.breakout_level:.2f}",
                confidence=breakout_signal.confidence
            )

        # SCENARIO 2: TRAPPED IN RANGE - Switch to mean reversion
        if trap_analysis.is_trapped:
            logger.warning(f" RANGE DETECTED - Switching from {self.current_strategy} to MEAN REVERSION")

            # Activate mean reversion if not already active
            if not self.mean_reversion.is_active:
                self.mean_reversion.activate(
                    reason=f"Range trap detected: {trap_analysis.range_size_pct:.2f}% range"
                )

            self.in_range_mode = True
            self.breakout_confirmed = False

            # Try to generate mean reversion signal
            market_mean = self.mean_reversion.calculate_market_mean()
            mr_signal = None
            reason = f"Ranging market: {trap_analysis.trap_reason}"
            if market_mean:
                mr_signal, reason_str = self.mean_reversion.generate_signal(
                    current_price=current_price,
                    market_mean=market_mean,
                    chop_confidence=chop_confidence
                )
                if not mr_signal:
                    reason = reason_str # Overwrite with specific reason from engine

            return StrategyDecision(
                active_strategy="MEAN_REVERSION",
                should_trade=bool(mr_signal),  # Only trade if MR signal exists
                directional_enabled=False,  # Block directional signals
                mean_reversion_signal=mr_signal,
                is_ranging=True,
                is_breaking_out=False,
                trap_severity=trap_analysis.trap_severity,
                reason=reason,
                confidence=1.0 - trap_analysis.trap_severity  # Inverse of danger
            )

        # SCENARIO 3: HIGH TRAP SEVERITY (but not trapped) - Reduce activity
        if trap_analysis.trap_severity > 0.75: # Increased from 0.5 for scalping
            logger.info(f" High trap severity ({trap_analysis.trap_severity:.0%}) - STANDBY mode")

            # Keep mean reversion available but with caution
            if not self.mean_reversion.is_active:
                self.mean_reversion.activate(reason="Caution: High trap severity")

            return StrategyDecision(
                active_strategy="STANDBY",
                should_trade=False,  # Don't trade in unclear conditions
                directional_enabled=False,
                mean_reversion_signal=None,
                is_ranging=False,
                is_breaking_out=False,
                trap_severity=trap_analysis.trap_severity,
                reason=f"High trap severity: {trap_analysis.trap_reason}",
                confidence=0.3
            )

        # SCENARIO 4: NORMAL CONDITIONS - Directional trading
        # Deactivate mean reversion if active
        if self.mean_reversion.is_active:
            self.mean_reversion.deactivate("Normal market conditions")

        self.in_range_mode = False

        return StrategyDecision(
            active_strategy="DIRECTIONAL",
            should_trade=True,
            directional_enabled=True,
            mean_reversion_signal=None,
            is_ranging=False,
            is_breaking_out=False,
            trap_severity=trap_analysis.trap_severity,
            reason="Normal market conditions - directional trading enabled",
            confidence=0.8
        )

    def _continue_current_strategy(
        self,
        trap_analysis: RangeTrapAnalysis,
        current_price: float,
        chop_confidence: float
    ) -> StrategyDecision:
        """
        Continue with current strategy (during cooldown)

        Still checks for mean reversion signals if in MR mode
        """
        if self.current_strategy == "MEAN_REVERSION":
            # Generate MR signal if conditions are met
            market_mean = self.mean_reversion.calculate_market_mean()
            mr_signal = None
            reason = f"Continuing mean reversion mode (cooldown: {self.switch_cooldown - int(time.time() - self.last_switch_time)}s)"
            if market_mean and self.mean_reversion.is_active:
                mr_signal, reason_str = self.mean_reversion.generate_signal(
                    current_price=current_price,
                    market_mean=market_mean,
                    chop_confidence=chop_confidence
                )
                if not mr_signal:
                    reason = reason_str # Overwrite with specific reason

            return StrategyDecision(
                active_strategy="MEAN_REVERSION",
                should_trade=bool(mr_signal),
                directional_enabled=False,
                mean_reversion_signal=mr_signal,
                is_ranging=True,
                is_breaking_out=False,
                trap_severity=trap_analysis.trap_severity,
                reason=reason,
                confidence=0.6
            )

        elif self.current_strategy == "DIRECTIONAL":
            return StrategyDecision(
                active_strategy="DIRECTIONAL",
                should_trade=True,
                directional_enabled=True,
                mean_reversion_signal=None,
                is_ranging=False,
                is_breaking_out=False,
                trap_severity=trap_analysis.trap_severity,
                reason="Continuing directional trading",
                confidence=0.7
            )

        else:  # STANDBY
            return StrategyDecision(
                active_strategy="STANDBY",
                should_trade=False,
                directional_enabled=False,
                mean_reversion_signal=None,
                is_ranging=False,
                is_breaking_out=False,
                trap_severity=trap_analysis.trap_severity,
                reason="Continuing standby mode (high uncertainty)",
                confidence=0.3
            )

    def _log_strategy_switch(self, old_strategy: str, new_strategy: str, reason: str):
        """Log strategy switches with clear formatting"""
        logger.warning("")
        logger.warning("="*80)
        logger.warning("STRATEGY SWITCH")
        logger.warning("="*80)
        logger.warning(f"   FROM: {old_strategy}")
        logger.warning(f"   TO: {new_strategy}")
        logger.warning(f"   REASON: {reason}")
        logger.warning(f"   Switch Count: {self.strategy_switches + 1}")
        logger.warning("="*80)
        logger.warning("")

    def get_status(self) -> Dict:
        """Get current router status"""
        return {
            'current_strategy': self.current_strategy,
            'in_range_mode': self.in_range_mode,
            'breakout_confirmed': self.breakout_confirmed,
            'range_high': self.range_high,
            'range_low': self.range_low,
            'strategy_switches': self.strategy_switches,
            'mean_reversion_active': self.mean_reversion.is_active,
            'mean_reversion_signals': self.mean_reversion.signals_generated,
            'time_since_last_switch': time.time() - self.last_switch_time
        }


if __name__ == "__main__":
    print("Arsenal Strategy Router - Intelligent Mode Switching")
    print("Automatically handles range detection, mean reversion, and breakout trading")
    print("\nModule ready for integration into intelligent_strategy_brain.py")
