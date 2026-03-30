"""
Range Regime Engine (RRE) and Mean Reversion Brain (MRB)
=========================================================
Implementation based on the engineering spec provided. This module contains:
- The core Range Regime Engine for detecting and classifying market ranges.
- The Mean Reversion Brain that activates only in specific range conditions.

This system is designed to be integrated into the main Arsenal trading loop,
replacing the older `RangeTrapDetector` and providing a gated, non-blocking
mean-reversion strategy.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import logging
import time
import numpy as np

logger = logging.getLogger(__name__)

# Local imports from the existing Arsenal project structure
# These will be resolved when integrated into the main application
# from fvg_detector import FVG  # Assuming FVG is the dataclass/type
# from order_block_detector import OrderBlock  # Assuming this is the type

def clamp(x, a, b):
    """Clamps a value between a and b."""
    return max(a, min(b, x))

from rre_common_types import RangeAnalysis, RangeGeometry

# --- Core Detectors ---

class StructuralRangeDetector:
    """Analyzes swing points to identify potential range boundaries."""
    def detect(self, swings: List[Dict], current_price: float) -> Tuple[Optional[RangeGeometry], int]:
        """
        Detects range geometry based on the mean of recent swing points for stability.
        """
        if len(swings) < 6: # Need at least 3 highs and 3 lows
            return None, 0

        # Sort swings by timestamp to get the most recent ones
        sorted_swings = sorted(swings, key=lambda s: s.get('timestamp', 0))
        
        recent_highs = [s['price'] for s in sorted_swings if s['type'] == 'high'][-3:]
        recent_lows = [s['price'] for s in sorted_swings if s['type'] == 'low'][-3:]

        if len(recent_highs) < 2 or len(recent_lows) < 2:
            return None, 0
            
        # OPTIMIZATION: Use the mean of recent swings for a more stable boundary
        high_level = np.mean(recent_highs)
        low_level = np.mean(recent_lows)

        if high_level <= low_level:
            return None, 0

        width_pct = (high_level - low_level) / current_price * 100
        midline = (high_level + low_level) / 2
        
        # USER FEEDBACK: Sanity check the midline
        # Ensure midline is actually near current price
        if abs(midline - current_price) > (high_level - low_level):
            logger.info(f"[RRE] Geometry rejected: Price ${current_price} is too far from midline ${midline}")
            return None, 0 # Price is way outside the calculated center

        # Count touches within a tolerance
        tolerance = (high_level - low_level) * 0.1 # 10% tolerance
        touch_count = sum(1 for s in swings if (abs(s['price'] - high_level) < tolerance) or (abs(s['price'] - low_level) < tolerance))

        geom = RangeGeometry(low=low_level, high=high_level, width_pct=width_pct, midline=midline)
        return geom, touch_count

class VolatilityDetector:
    """Scores volatility compression using ATR percentile."""
    def score(self, atr_percentile: float) -> float:
        # Low ATR percentile suggests compression, which is indicative of a range.
        return clamp(1.0 - atr_percentile, 0.0, 1.0)

class TrendDetector:
    """Scores trend weakness using ADX."""
    def score(self, adx_value: float, adx_threshold: int = 25) -> float:
        # ADX below threshold suggests a weak or non-existent trend.
        return clamp(1.0 - (adx_value / adx_threshold), 0.0, 1.0)

class MicrostructureDetector:
    """Scores market chop based on taker ratio and CVD slope."""
    def score(self, taker_ratio: Optional[float], cvd_slope: Optional[float]) -> float:
        # Taker ratio near 1.0 indicates balanced buying/selling.
        taker_score = 0.0
        if taker_ratio is not None:
            taker_score = 1.0 - abs(taker_ratio - 1.0) * 5 # Amplify deviation
            taker_score = max(0.0, taker_score)  # Ensure non-negative

        # CVD slope near 0 indicates no strong directional pressure.
        cvd_score = 0.0
        if cvd_slope is not None:
            cvd_score = 1.0 - clamp(abs(cvd_slope) / 1.0, 0.0, 1.0)

        # If only one is available, weight it more heavily
        if taker_ratio is not None and cvd_slope is not None:
            # Both available: use standard weights
            combined_score = (taker_score * 0.6) + (cvd_score * 0.4)
        elif taker_ratio is not None:
            # Only taker ratio available: full weight to taker
            combined_score = taker_score
        elif cvd_slope is not None:
            # Only CVD available: full weight to CVD
            combined_score = cvd_score
        else:
            # Neither available: return 0
            combined_score = 0.0

        return clamp(combined_score, 0.0, 1.0)

class BoundaryQualityDetector:
    """Scores the quality of range boundaries based on HVN and Order Block overlap."""
    def score(self, hvn_zones: List[Dict], order_blocks: List[Any], geom: Optional[RangeGeometry]) -> float:
        if not geom or (not hvn_zones and not order_blocks): # Allow if at least one is present
            return 0.0
        
        low_hits = 0
        high_hits = 0
        tolerance = (geom.high - geom.low) * 0.15 # 15% of range width

        # Check for HVN/OB confluence at range low
        for hvn in hvn_zones:
            if abs(hvn['price'] - geom.low) < tolerance:
                low_hits += 1 # Count HVN as a hit
        for ob in order_blocks:
            if ob.type == 'bullish' and abs(ob.entry_zone_low - geom.low) < tolerance:
                low_hits += 1 # Count OB as a hit
        
        # Check for HVN/OB confluence at range high
        for hvn in hvn_zones:
            if abs(hvn['price'] - geom.high) < tolerance:
                high_hits += 1
        for ob in order_blocks:
            if ob.type == 'bearish' and abs(ob.entry_zone_high - geom.high) < tolerance:
                high_hits += 1
                        
        return clamp((low_hits + high_hits) / 4.0, 0.0, 1.0) # Normalize by a higher factor if multiple sources

# --- Main RRE Engine ---

class RREngine:
    """The main Range Regime Engine class."""
    DEFAULT_WEIGHTS = dict(structural=0.35, boundary=0.25, vol=0.15, trend=0.10, micro=0.15)

    def __init__(self, symbol: str, config: Optional[Dict] = None):
        self.symbol = symbol
        self.config = config or {}
        # USER FEEDBACK: Allow dynamic weights
        self.weights = {**self.DEFAULT_WEIGHTS, **self.config.get('weights', {})}

        self.struct_detector = StructuralRangeDetector()
        self.vol_detector = VolatilityDetector()
        self.trend_detector = TrendDetector()
        self.micro_detector = MicrostructureDetector()
        self.boundary_detector = BoundaryQualityDetector()
        
        self.state = 'NOT_RANGE'
        self.state_history: List[Tuple[float, str]] = []
        self.score_history: List[Tuple[float, float]] = []
        self.last_state_change_time = time.time()
        
        # Sensitivity attributes
        self.sensitivity_level = 'default'
        self.demote_thresh = self.config.get('demote_thresh', 25)
        self.tight_thresh = self.config.get('tight_thresh', 85)
        self.est_thresh = self.config.get('est_thresh', 55)
        self.early_thresh = self.config.get('early_thresh', 30)

    def set_sensitivity(self, level: str):
        """
        Adjusts the engine's sensitivity for different market sessions.
        'high' for Asian session (low liquidity), 'default' for others.
        """
        self.sensitivity_level = level
        if level == 'high':
            logger.info("[RRE] Setting sensitivity to HIGH for Asian session.")
            self.weights = {
                'structural': 0.30, 
                'boundary': 0.20, 
                'vol': 0.20,      # Increased weight
                'trend': 0.10, 
                'micro': 0.20     # Increased weight
            }
            self.demote_thresh = 20 # Lower threshold
            self.tight_thresh = 80  # Lower threshold
            self.est_thresh = 50    # Lower threshold
            self.early_thresh = 25  # Lower threshold
        else: # 'default'
            logger.info("[RRE] Setting sensitivity to DEFAULT.")
            self.weights = self.DEFAULT_WEIGHTS
            self.demote_thresh = self.config.get('demote_thresh', 25)
            self.tight_thresh = self.config.get('tight_thresh', 85)
            self.est_thresh = self.config.get('est_thresh', 55)
            self.early_thresh = self.config.get('early_thresh', 30)

    def analyze(
        self,
        swings: List[Dict],
        hvn_zones: List[Dict],
        order_blocks: List[Any],
        atr_percentile: float,
        adx_value: float,
        taker_ratio: Optional[float],
        cvd_slope: Optional[float],
        stop_hunt_prob: float,
        current_price: float
    ) -> RangeAnalysis:
        """
        Computes the comprehensive range analysis.
        """
        geom, touch_count = self.struct_detector.detect(swings, current_price)

        # Calculate feature scores
        structural_score = 0.0
        if geom:
            # OPTIMIZATION: Move min range size check into the detector itself
            # This is now handled by the improved detector logic.
            # Higher score for more touches and narrower (but not too narrow) width
            # OPTIMIZATION: Refine scoring logic
            touch_score = clamp(touch_count / 8.0, 0.0, 1.0) # More granularity
            width_score = clamp(1.0 - (geom.width_pct / 6.0), 0.0, 1.0) # Less aggressive penalty
            structural_score = (touch_score * 0.6) + (width_score * 0.4)

        boundary_score = self.boundary_detector.score(hvn_zones, order_blocks, geom)
        vol_score = self.vol_detector.score(atr_percentile)
        trend_score = self.trend_detector.score(adx_value)
        micro_score = self.micro_detector.score(taker_ratio, cvd_slope)
        
        evidence = dict(
            structural=structural_score,
            boundary=boundary_score,
            vol=vol_score,
            trend=trend_score,
            micro=micro_score,
            stop_hunt_prob=stop_hunt_prob
        )

        # --- Educational Logging: Evidence Breakdown ---
        logger.info("[RRE] Evidence Breakdown:")
        logger.info(f"  - Structural Score: {structural_score:.2f} (Touches: {touch_count}, Width: {geom.width_pct if geom else 'N/A'}%)")
        logger.info(f"  - Boundary Quality: {boundary_score:.2f} (HVN/OB Overlap)")
        logger.info(f"  - Volatility Score: {vol_score:.2f} (ATR Percentile: {atr_percentile:.2f})")
        logger.info(f"  - Trend Score     : {trend_score:.2f} (ADX: {adx_value:.2f})")
        logger.info(f"  - Microstructure  : {micro_score:.2f} (Taker Ratio & CVD Slope)")

        # Calculate weighted score using the dynamically set weights
        w = self.weights
        score = (
            structural_score * w['structural'] +
            boundary_score * w['boundary'] +
            vol_score * w['vol'] +
            trend_score * w['trend'] +
            micro_score * w['micro']
        ) * 100.0
        
        logger.info(f"[RRE] Final Weighted Score: {score:.1f}/100")

        # Update state machine
        now = time.time()
        self.score_history.append((now, score))
        self.score_history = [h for h in self.score_history if now - h[0] <= 1800] # 30 min history
        
        persistence_seconds = 0
        if self.state != 'NOT_RANGE':
            persistence_seconds = now - self.last_state_change_time

        new_state = self._decide_state(score, touch_count, persistence_seconds, stop_hunt_prob)

        if not geom and new_state not in ['NOT_RANGE', 'RANGE_TRAP']:
            logger.info(f"[RRE] State downgraded from {new_state} to NOT_RANGE due to lack of valid geometry.")
            new_state = 'NOT_RANGE'

        if new_state != self.state:
            self.state = new_state
            self.last_state_change_time = now
            self.state_history.append((now, new_state))

        is_trapped = new_state == 'RANGE_TRAP'
        trap_reason = "Stop hunt probability is high." if is_trapped else ""
        trap_severity = min(stop_hunt_prob, 1.0)

        return RangeAnalysis(
            range_score=score,
            range_state=new_state,
            geometry=geom,
            boundary_quality=boundary_score,
            persistence_seconds=persistence_seconds,
            touch_count=touch_count,
            is_trapped=is_trapped,
            trap_reason=trap_reason,
            trap_severity=trap_severity,
            evidence=evidence
        )

    def _decide_state(self, score: float, touch_count: int, persistence: float, stop_hunt_prob: float) -> str:
        """The state machine logic with hysteresis."""
        # --- Demotion Logic ---
        if self.state != 'NOT_RANGE' and score < self.demote_thresh:
            return 'NOT_RANGE'

        # --- Promotion Logic ---
        if score >= self.tight_thresh:
            return 'TIGHT_RANGE'
        if score >= self.est_thresh:
            if touch_count >= 3 or persistence > self.config.get('promote_seconds', 600):
                return 'ESTABLISHED_RANGE'
            else:
                return 'EARLY_RANGE_FORMING'
        if score >= self.early_thresh:
            # Use a moving average for smoother transition
            recent_scores = [s for t, s in self.score_history if time.time() - t < 120]
            if len(recent_scores) > 2 and np.mean(recent_scores) > self.early_thresh:
                 return 'EARLY_RANGE_FORMING'
            return self.state

        return 'NOT_RANGE'

# --- Mean Reversion Brain ---

@dataclass
class MRBDecision:
    should_trade: bool
    side: Optional[str] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""

class MeanReversionBrain:
    """
    The MRB, designed to be gated by the RRE.
    It does NOT block the main system. It only provides trade opportunities
    when conditions are perfect.
    """
    def __init__(self, symbol: str, config: Optional[Dict] = None):
        self.symbol = symbol
        self.config = config or {}
        self.state = 'STANDBY'  # STANDBY, ARMED
        self.armed_since: Optional[float] = None
        self.last_trade_time: float = 0
        self.is_active = True # Default to being active

    def set_active(self, is_active: bool):
        """Enable or disable the Mean Reversion Brain."""
        logger.info(f"[MRB] Setting active status to: {is_active}")
        self.is_active = is_active
        if not is_active:
            self.state = 'STANDBY' # Force to standby when disabled
            self.armed_since = None

    def decide(self, rre_analysis: RangeAnalysis, current_price: float, horus_confirmation: bool) -> MRBDecision:
        """
        Main decision function for the MRB.
        """
        if not self.is_active:
            return MRBDecision(should_trade=False, reason="MRB is disabled.")
            
        logger.info("[MRB] --- Mean Reversion Brain Analysis ---")
        is_armed = self._check_activation(rre_analysis)
        if not is_armed:
            logger.info(f"[MRB] State: {self.state}. RRE state is '{rre_analysis.range_state}'. MRB is not armed.")
            return MRBDecision(should_trade=False, reason=f"MRB not armed. RRE State: {rre_analysis.range_state}")
        
        logger.info(f"[MRB] State: ARMED. RRE State is '{rre_analysis.range_state}'. Checking for entry...")
        if not rre_analysis.geometry:
            logger.info("[MRB] REJECT: No valid range geometry provided by RRE.")
            return MRBDecision(should_trade=False, reason="No range geometry.")
            
        geom = rre_analysis.geometry # Assign geom here after the check

        # USER FEEDBACK: Add "Expansion" Detection
        price_deviation = abs(current_price - geom.midline) / (geom.high - geom.low) if (geom.high - geom.low) > 0 else 0
        if price_deviation > 0.6: # Price is > 60% away from midline (i.e., outside the range)
            self.state = 'STANDBY'
            self.armed_since = None
            logger.warning(f"[MRB] Disarming due to Expansion Detection. Price deviation {price_deviation:.2f} > 0.6")
            return MRBDecision(should_trade=False, reason="Price has expanded out of range.")

        # --- Timeout & Cooldown Logic ---
        timeout = self.config.get('mrb_arm_timeout_seconds', 3600 * 4)
        if self.armed_since and (time.time() - self.armed_since > timeout):
            self.state = 'STANDBY' # Disarm on timeout
            logger.warning("[MRB] REJECT: Armed state has timed out.")
            return MRBDecision(should_trade=False, reason="MRB armed state timed out.")

        cooldown = self.config.get('mrb_trade_cooldown_seconds', 600)
        if (time.time() - self.last_trade_time) < cooldown:
            logger.info(f"[MRB] REJECT: In trade cooldown.")
            return MRBDecision(should_trade=False, reason=f"MRB in trade cooldown.")

        # --- Entry Logic ---
        side = None
        # OPTIMIZATION: Make Entry Zones Adaptive
        entry_zone_pct = self.config.get('mrb_entry_zone_pct', 0.1) # Outer 10% of the range
        entry_zone_offset = (geom.high - geom.low) * entry_zone_pct
        
        lower_entry_zone = geom.low + entry_zone_offset
        upper_entry_zone = geom.high - entry_zone_offset

        if current_price <= lower_entry_zone:
            side = 'LONG'
        elif current_price >= upper_entry_zone:
            side = 'SHORT'
        
        if not side:
            return MRBDecision(should_trade=False, reason="Price not at boundary zones.")
        
        logger.info(f"[MRB] Price is at {side} boundary. Checking confluence...")

        # --- Confluence Checks ---
        min_boundary_quality = self.config.get('min_boundary_quality', 0.4)
        if rre_analysis.boundary_quality < min_boundary_quality:
            return MRBDecision(should_trade=False, reason=f"Boundary quality ({rre_analysis.boundary_quality:.2f}) < {min_boundary_quality}.")
        
        logger.info(f"[MRB] ✓ Boundary quality is sufficient ({rre_analysis.boundary_quality:.2f}).")

        if not horus_confirmation:
            return MRBDecision(should_trade=False, reason="Horus micro-structure confirmation failed.")
        
        logger.info("[MRB] ✓ Horus confirmation received.")

        # --- Trade Calculation ---
        logger.info(f"[MRB] SUCCESS: All checks passed. Generating {side} trade plan.")
        self.last_trade_time = time.time()
        atr_buffer_pct = self.config.get('mrb_sl_buffer_pct', 0.1) # 10% of range width as buffer
        atr_buffer = (geom.high - geom.low) * atr_buffer_pct
        
        if side == 'LONG':
            sl = geom.low - atr_buffer
            tp1 = geom.midline
            tp2 = geom.high
        else: # SHORT
            sl = geom.high + atr_buffer
            tp1 = geom.midline
            tp2 = geom.low
            
        confidence = (rre_analysis.range_score / 100.0) * rre_analysis.boundary_quality
        
        reason = f"MRB {side} entry from {current_price:.2f} in {rre_analysis.range_state} (Score: {rre_analysis.range_score:.1f})"
        logger.info(f"[MRB] Trade Plan: SL=${sl:.2f}, TP1=${tp1:.2f}, TP2=${tp2:.2f}, Confidence={confidence:.2f}")
        
        return MRBDecision(
            should_trade=True,
            side=side,
            entry=current_price,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            confidence=confidence,
            reason=reason
        )

    def _check_activation(self, analysis: RangeAnalysis) -> bool:
        """
        Checks if the MRB should be in an 'ARMED' state.
        This is the primary gate.
        """
        if not self.is_active:
            return False

        is_tradeable_range = analysis.range_state in ('ESTABLISHED_RANGE', 'TIGHT_RANGE')
        
        if is_tradeable_range and not analysis.is_trapped:
            if self.state != 'ARMED':
                self.state = 'ARMED'
                self.armed_since = time.time()
            return True
        else: # Disarm if no longer in a tradeable range or if it's a trap
            if self.state == 'ARMED':
                self.state = 'STANDBY'
                self.armed_since = None
            return False
