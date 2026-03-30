"""
Horus-Enhanced Precision Entry System
======================================
Combines Arsenal's setup detection with Horus order flow intelligence for:
- Precision entry timing (wait for CVD acceleration + orderbook confirmation)
- Tighter stop placement (beyond liquidity zones, not arbitrary percentages)
- Better entry zones (avoid institutional walls)
- Higher win rate through multiple confirmations

Author: Arsenal Trading System + Horus Integration
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import logging

logger = logging.getLogger('HORUS_ENTRY')


@dataclass
class HorusEntryConditions:
    """Horus order flow conditions for precise entry timing"""

    # CVD Conditions
    cvd_confirmed: bool
    cvd_z_score: float # Changed from cvd_vs_average
    cvd_momentum: str  # 'accelerating', 'stable', 'decelerating'
    cvd_divergence: bool

    # Orderbook Conditions
    orderbook_confirmed: bool
    imbalance_ratio: float
    imbalance_direction: str  # 'LONG', 'SHORT', 'NEUTRAL'
    imbalance_strength: float

    # Liquidity Conditions
    liquidity_quality: str  # 'excellent', 'good', 'fair', 'poor'
    institutional_walls_detected: int
    nearest_wall_distance: Optional[float]  # Distance in %
    nearest_wall_side: Optional[str]  # 'support' or 'resistance'
    absorption_events_recent: int

    # Overall Assessment
    all_conditions_met: bool
    entry_quality_score: float  # 0-100
    blockers: List[str]
    warnings: List[str]

    # Optimal Entry Price (from Horus)
    optimal_entry: Optional[float]
    entry_confidence: float


@dataclass
class HorusStopPlacement:
    """Intelligent stop placement using Horus liquidity data"""

    # Stop Loss Levels
    optimal_stop: float
    aggressive_stop: float  # Tighter (higher risk)
    conservative_stop: float  # Wider (lower risk)

    # Reasoning
    stop_placement_logic: str
    liquidity_zone_below: Optional[float]  # For LONG
    liquidity_zone_above: Optional[float]  # For SHORT
    distance_from_entry_pct: float
    risk_reward_with_optimal: float

    # Quality
    placement_confidence: float  # 0-1


class HorusPrecisionEntrySystem:
    """
    Enhanced entry system using Horus order flow intelligence

    Ensures:
    1. Only enter when CVD confirms direction
    2. Only enter when orderbook shows strong imbalance
    3. Avoid entries near institutional walls
    4. Place stops beyond liquidity zones (tighter than Arsenal's default)
    5. Wait for optimal entry conditions
    """

    def __init__(self, horus_unified):
        """
        Args:
            horus_unified: Instance of ArsenalHorusUnified (already initialized)
        """
        import json
        import os
        self.horus = horus_unified
        self.symbol = horus_unified.symbol

        # --- Load Symbol-Specific Configuration ---
        config_path = os.path.join(os.path.dirname(__file__), 'horus_config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            default_params = config.get("DEFAULT", {})
            symbol_params = config.get(self.symbol, {})
            
            # Merge symbol-specific params over defaults
            params = {**default_params, **symbol_params}

            self.min_entry_quality = params.get("min_entry_quality", 50)
            self.min_imbalance_ratio = params.get("min_imbalance_ratio", 1.15)
            self.required_momentum = params.get("required_momentum", ["accelerating"])
            self.min_cvd_z_score = params.get("min_cvd_z_score", 1.5)
            
            profile_name = self.symbol if self.symbol in config else "DEFAULT"
            logger.info(f" Horus using '{profile_name}' sensitivity profile.")
            logger.info(f"   - Min Quality: {self.min_entry_quality}")
            logger.info(f"   - Min Imbalance Ratio: {self.min_imbalance_ratio}")
            logger.info(f"   - Required Momentum: {self.required_momentum}")
            logger.info(f"   - Min CVD Z-Score: {self.min_cvd_z_score}")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.critical(f"CRITICAL: Could not load or parse 'horus_config.json': {e}. Horus cannot operate without configuration.")
            raise RuntimeError(f"Could not load or parse 'horus_config.json': {e}") from e


        self.max_wall_distance_pct = 1.0  # This is a safety feature, not a sensitivity param, keep it constant for now

    async def evaluate_entry_conditions(
        self,
        arsenal_direction: str,
        arsenal_confidence: float,
        current_price: float
    ) -> HorusEntryConditions:
        """
        Evaluate if current market conditions support Arsenal's entry signal

        Args:
            arsenal_direction: 'LONG' or 'SHORT' from Arsenal
            arsenal_confidence: 0-1 confidence from Arsenal
            current_price: Current market price

        Returns:
            HorusEntryConditions with detailed assessment
        """

        logger.info(f"[HORUS ENTRY] Evaluating conditions for {arsenal_direction} setup...")

        # Get Horus market intelligence
        snapshot = await self.horus.get_full_snapshot()

        blockers = []
        warnings = []

        # === 1. CVD CONFIRMATION (using Z-Score) ===
        cvd_confirmed = False
        cvd_z_score = snapshot.cvd_z_score
        cvd_momentum = snapshot.cvd_momentum

        if arsenal_direction == 'LONG':
            if cvd_z_score >= self.min_cvd_z_score:
                if cvd_momentum in self.required_momentum:
                    cvd_confirmed = True
                    logger.info(f"  CVD: CONFIRMED (Z-Score: {cvd_z_score:.2f} >= {self.min_cvd_z_score}, Momentum: '{cvd_momentum}')")
                else:
                    warnings.append(f"CVD Z-Score ({cvd_z_score:.2f}) is valid, but momentum '{cvd_momentum}' not in {self.required_momentum}")
            else:
                blockers.append(f"CVD Z-Score {cvd_z_score:.2f} below threshold {self.min_cvd_z_score}")

        else:  # SHORT
            if cvd_z_score <= -self.min_cvd_z_score:
                if cvd_momentum in self.required_momentum:
                    cvd_confirmed = True
                    logger.info(f"  CVD: CONFIRMED (Z-Score: {cvd_z_score:.2f} <= -{self.min_cvd_z_score}, Momentum: '{cvd_momentum}')")
                else:
                    warnings.append(f"CVD Z-Score ({cvd_z_score:.2f}) is valid, but momentum '{cvd_momentum}' not in {self.required_momentum}")
            else:
                blockers.append(f"CVD Z-Score {cvd_z_score:.2f} above threshold -{self.min_cvd_z_score}")

        # Check for divergence
        if snapshot.has_divergence:
            div_type = snapshot.divergence_type
            if (arsenal_direction == 'LONG' and div_type == 'bearish') or \
               (arsenal_direction == 'SHORT' and div_type == 'bullish'):
                blockers.append(f"{div_type} divergence contradicts {arsenal_direction}")
                logger.warning(f"  DIVERGENCE: {div_type} detected!")

        # === 2. ORDERBOOK CONFIRMATION ===
        orderbook_confirmed = False
        imbalance = snapshot.imbalance_ratio
        ob_direction = snapshot.predicted_direction
        ob_confidence = snapshot.direction_confidence

        if arsenal_direction == 'LONG':
            # For LONG: Need bid-heavy orderbook (ratio > 1.25)
            if imbalance >= self.min_imbalance_ratio and ob_direction == 'LONG':
                orderbook_confirmed = True
                logger.info(f"  ORDERBOOK: CONFIRMED ({imbalance:.2f} bid/ask, {ob_confidence:.0%} confidence)")
            else:
                if imbalance < self.min_imbalance_ratio:
                    blockers.append(f"Orderbook imbalance only {imbalance:.2f} (need {self.min_imbalance_ratio})")
                elif ob_direction != 'LONG':
                    blockers.append(f"Orderbook suggests {ob_direction} not LONG")
                logger.warning(f"  ORDERBOOK: BLOCKED - Imbalance {imbalance:.2f}, suggests {ob_direction}")

        else:  # SHORT
            # For SHORT: Need ask-heavy orderbook (ratio < 0.8)
            if imbalance <= (1.0 / self.min_imbalance_ratio) and ob_direction == 'SHORT':
                orderbook_confirmed = True
                logger.info(f"  ORDERBOOK: CONFIRMED ({imbalance:.2f} bid/ask, {ob_confidence:.0%} confidence)")
            else:
                blockers.append(f"Orderbook imbalance {imbalance:.2f} contradicts SHORT")
                logger.warning(f"  ORDERBOOK: BLOCKED - Imbalance {imbalance:.2f}")

        # === 3. LIQUIDITY CONDITIONS ===
        liquidity_quality = snapshot.liquidity_quality
        inst_walls = snapshot.institutional_walls
        absorption = snapshot.recent_absorption

        # Check for nearby institutional walls
        nearest_wall_dist = None
        nearest_wall_side = None

        if inst_walls > 0:
            warnings.append(f"{inst_walls} institutional walls detected")
            logger.warning(f"  LIQUIDITY: {inst_walls} institutional walls detected")
            # TODO: Get actual wall distances from snapshot

        if liquidity_quality == 'poor':
            warnings.append("Poor liquidity - higher slippage risk")
            logger.warning(f"  LIQUIDITY: POOR quality")
        elif liquidity_quality == 'excellent':
            logger.info(f"  LIQUIDITY: EXCELLENT quality")

        if absorption > 0:
            logger.info(f"  ABSORPTION: {absorption} recent events (momentum building)")

        # === 4. CALCULATE ENTRY QUALITY SCORE ===
        quality_score = 0

        # CVD (0-35 points)
        if cvd_confirmed:
            quality_score += 25
            if cvd_momentum == 'accelerating':
                quality_score += 10

        # Orderbook (0-35 points)
        if orderbook_confirmed:
            quality_score += 25
            if snapshot.is_strong_imbalance:
                quality_score += 10

        # Liquidity (0-20 points)
        if liquidity_quality == 'excellent':
            quality_score += 15
        elif liquidity_quality == 'good':
            quality_score += 10
        elif liquidity_quality == 'fair':
            quality_score += 5

        if absorption > 0:
            quality_score += 5  # Absorption = momentum

        # Arsenal confidence (0-15 points)
        quality_score += arsenal_confidence * 15

        # Penalties
        if snapshot.has_divergence:
            quality_score -= 15
        if inst_walls > 0:
            quality_score -= 10
        if liquidity_quality == 'poor':
            quality_score -= 10

        quality_score = max(0, min(100, quality_score))

        # === 5. FINAL DECISION ===
        all_met = (
            cvd_confirmed and
            orderbook_confirmed and
            len(blockers) == 0 and
            quality_score >= self.min_entry_quality
        )

        # Calculate optimal entry (current price for now, can enhance later)
        optimal_entry = current_price
        entry_confidence = quality_score / 100

        logger.info(f"[HORUS ENTRY] Quality Score: {quality_score}/100")
        logger.info(f"[HORUS ENTRY] All Conditions Met: {all_met}")

        if blockers:
            logger.warning(f"[HORUS ENTRY] Blockers: {len(blockers)}")
            for blocker in blockers:
                logger.warning(f"  - {blocker}")

        if warnings:
            logger.warning(f"[HORUS ENTRY] Warnings: {len(warnings)}")
            for warning in warnings:
                logger.warning(f"  - {warning}")

        return HorusEntryConditions(
            cvd_confirmed=cvd_confirmed,
            cvd_z_score=cvd_z_score,
            cvd_momentum=cvd_momentum,
            cvd_divergence=snapshot.has_divergence,
            orderbook_confirmed=orderbook_confirmed,
            imbalance_ratio=imbalance,
            imbalance_direction=ob_direction,
            imbalance_strength=ob_confidence,
            liquidity_quality=liquidity_quality,
            institutional_walls_detected=inst_walls,
            nearest_wall_distance=nearest_wall_dist,
            nearest_wall_side=nearest_wall_side,
            absorption_events_recent=absorption,
            all_conditions_met=all_met,
            entry_quality_score=quality_score,
            blockers=blockers,
            warnings=warnings,
            optimal_entry=optimal_entry,
            entry_confidence=entry_confidence
        )

    async def calculate_optimal_stop(
        self,
        direction: str,
        entry_price: float,
        arsenal_stop: float
    ) -> HorusStopPlacement:
        """
        Calculate optimal stop placement using Horus liquidity data

        Places stops BEYOND liquidity zones for tighter stops that respect market structure

        Args:
            direction: 'LONG' or 'SHORT'
            entry_price: Planned entry price
            arsenal_stop: Arsenal's default stop

        Returns:
            HorusStopPlacement with optimal stop levels
        """

        logger.info(f"[HORUS STOP] Calculating optimal stop for {direction}...")
        logger.info(f"  Entry: ${entry_price:.2f}")
        logger.info(f"  Arsenal Stop: ${arsenal_stop:.2f} ({abs(entry_price - arsenal_stop) / entry_price * 100:.2f}%)")

        # Get liquidity snapshot
        snapshot = await self.horus.get_full_snapshot()

        # For now, use Arsenal's stop as baseline
        # TODO: Enhance with actual liquidity zone placement
        optimal_stop = arsenal_stop
        aggressive_stop = arsenal_stop  # Could be tighter
        conservative_stop = arsenal_stop  # Could be wider

        distance_pct = abs(entry_price - optimal_stop) / entry_price * 100

        # Calculate RR (assume 2:1 target for now)
        target_distance = abs(entry_price - optimal_stop) * 2
        if direction == 'LONG':
            estimated_target = entry_price + target_distance
        else:
            estimated_target = entry_price - target_distance

        rr_ratio = target_distance / abs(entry_price - optimal_stop)

        placement_logic = "Using Arsenal stop (liquidity enhancement TODO)"

        logger.info(f"  Optimal Stop: ${optimal_stop:.2f} ({distance_pct:.2f}% from entry)")
        logger.info(f"  Estimated RR: {rr_ratio:.2f}:1")

        return HorusStopPlacement(
            optimal_stop=optimal_stop,
            aggressive_stop=aggressive_stop,
            conservative_stop=conservative_stop,
            stop_placement_logic=placement_logic,
            liquidity_zone_below=None,  # TODO: Extract from Horus
            liquidity_zone_above=None,  # TODO: Extract from Horus
            distance_from_entry_pct=distance_pct,
            risk_reward_with_optimal=rr_ratio,
            placement_confidence=0.8  # Medium confidence without full liquidity data
        )

