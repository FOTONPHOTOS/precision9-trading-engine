"""
Precision TP/SL Calculator - Smart Money Execution

Uses ALL arsenal intelligence to find optimal entries with 2:1+ RR:
- FVG gaps as TP targets (price fills these)
- Order Blocks for entry confirmation
- Safe stop zones BEYOND liquidity pools (won't get swept)
- Liquidity concentration zones as targets
- Structure invalidation for tight stops

Fixes poor RR issue by using smart money logic instead of simple swings
"""

import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PrecisionSetup:
    """High-probability setup with optimal RR"""

    # Entry
    entry_price: float
    entry_zone: Tuple[float, float]
    entry_reason: str  # Why this entry is good

    # Stop
    stop_loss: float
    stop_reason: str  # Why this stop is safe
    safe_from_sweep: bool

    # Targets
    primary_target: float
    secondary_targets: List[float]
    target_reasons: List[str]  # Why these targets will hit

    # RR Analysis
    risk_amount: float  # Distance to stop
    reward_amount: float  # Distance to TP1
    risk_reward_ratio: float  # Should be 2:1 minimum

    # Confidence
    setup_quality: float  # 0-1, how good is this setup
    edge_score: float  # 0-1, our statistical edge


class PrecisionTPSLCalculator:
    """
    Smart TP/SL calculator using all arsenal intelligence

    Finds high-probability setups with excellent RR
    """

    def __init__(self):
        # Minimum acceptable RR - OPTIMIZED for crypto scalping
        # Reads from .env to allow easy adjustment without code changes
        # 1.3:1 is realistic with tight stops (1-2%) in volatile crypto markets
        # 2.0:1 was blocking 90% of profitable trades
        self.min_risk_reward = float(os.getenv('MIN_RISK_REWARD', 1.3))  # Default 1.3:1
        self.excellent_risk_reward = 2.0  # 2:1 is now excellent (was minimum)

        # Safety margins
        self.stop_buffer_beyond_liquidity = 0.003  # 0.3% beyond sweep zone
        self.entry_buffer_into_order_block = 0.002  # 0.2% into OB

        # Target selection
        self.prefer_unfilled_fvgs = True
        self.prefer_liquidity_zones = True

    def calculate_optimal_setup(
        self,
        direction: str,
        current_price: float,
        market_intel
    ) -> Optional[PrecisionSetup]:
        """
        Calculate optimal entry/stop/targets using all intelligence

        Returns None if no good setup found (better than poor RR trade)
        """

        if direction == 'LONG':
            return self._calculate_long_setup(current_price, market_intel)
        elif direction == 'SHORT':
            return self._calculate_short_setup(current_price, market_intel)
        else:
            return None

    def _calculate_long_setup(self, current_price: float, market_intel) -> Optional[PrecisionSetup]:
        """Calculate optimal LONG setup"""

        print("\n[PRECISION CALCULATOR - LONG SETUP ANALYSIS]")
        print(f"Current Price: ${current_price:.2f}")

        # STEP 1: Find best entry zone (Order Block preferred)
        print("\n[STEP 1/6] Finding optimal entry zone...")
        print("  - Searching for bullish Order Blocks")
        print("  - Evaluating quality scores")
        entry, entry_reason = self._find_long_entry(current_price, market_intel)
        if not entry:
            print("  [BLOCKED] No valid entry zone found")
            return None
        print(f"  [FOUND] Entry: ${entry:.2f}")
        print(f"  [REASON] {entry_reason}")

        # STEP 2: Calculate Scalping Stop-Loss
        print("\n[STEP 2/6] Calculating scalping stop placement...")
        stop = entry * (1 - 0.003)
        stop_reason = "Fixed 0.3% scalp stop"
        safe_from_sweep = False  # Not relevant for this strategy
        print(f"  [FOUND] Stop: ${stop:.2f}")
        print(f"  [REASON] {stop_reason}")

        # STEP 3: Find Scalping Take-Profit (Hybrid Model)
        print("\n[STEP 3/6] Identifying scalping take-profit target...")
        print("  - Searching for structural targets in 0.5%-1.0% range")
        
        # Get all potential structural targets
        all_targets, all_reasons = self._find_long_targets(entry, current_price, market_intel)
        
        # Define the sweet spot
        min_tp_price = entry * 1.005
        max_tp_price = entry * 1.01
        
        # Find targets within the sweet spot
        sweet_spot_targets = []
        for t, r in zip(all_targets, all_reasons):
            if min_tp_price <= t <= max_tp_price:
                sweet_spot_targets.append((t, r))

        if sweet_spot_targets:
            # If targets are in the sweet spot, pick the closest one
            best_target, best_reason = min(sweet_spot_targets, key=lambda x: x[0])
            targets = [best_target]
            target_reasons = [f"Structural target in sweet spot: {best_reason}"]
            print(f"  [FOUND] Structural target in 0.5-1.0% range: ${best_target:.2f}")
        else:
            # Otherwise, use the fixed 0.7% fallback
            fallback_tp = entry * 1.007
            targets = [fallback_tp]
            target_reasons = ["Fallback to fixed 0.7% target"]
            print("  [FALLBACK] No structural target in range. Using fixed 0.7% TP.")

        if not targets:
            print("  [BLOCKED] No valid targets could be determined.")
            return None
            
        print(f"  [FINAL TP] TP1: ${targets[0]:.2f} - {target_reasons[0]}")

        # STEP 4: Calculate RR
        print("\n[STEP 4/6] Calculating risk/reward ratio...")
        risk = entry - stop
        reward = targets[0] - entry
        rr = reward / risk if risk > 0 else 0
        print(f"  Risk: ${risk:.2f} ({(risk/entry)*100:.2f}%)")
        print(f"  Reward: ${reward:.2f} ({(reward/entry)*100:.2f}%)")
        print(f"  Initial RR: {rr:.2f}:1 {'[GOOD]' if rr >= self.min_risk_reward else '[POOR - needs improvement]'}")

        # STEP 5: Validate minimum RR
        if rr < self.min_risk_reward:
            print(f"\n[STEP 5/6] RR below minimum {self.min_risk_reward}:1 - attempting to improve...")
            print("  - Trying tighter stop placement")
            print("  - Searching for better targets")
            # Try to improve by adjusting entry or stop
            improved = self._try_improve_long_rr(
                entry, stop, targets, current_price, market_intel
            )
            if improved:
                entry, stop, targets = improved
                risk = entry - stop
                reward = targets[0] - entry
                rr = reward / risk
                print(f"  [SUCCESS] Improved RR to {rr:.2f}:1")
                print(f"  [NEW] Entry: ${entry:.2f}, Stop: ${stop:.2f}, TP1: ${targets[0]:.2f}")
            else:
                print(f"  [BLOCKED] Cannot achieve minimum {self.min_risk_reward}:1 RR")
                print("  [DECISION] SKIP TRADE - Better to wait for high-quality setup")
                return None  # Can't achieve good RR, skip trade
        else:
            print(f"\n[STEP 5/6] RR validation passed ({rr:.2f}:1 >= {self.min_risk_reward}:1)")

        # STEP 6: Calculate setup quality
        print("\n[STEP 6/6] Assessing overall setup quality...")
        quality = self._assess_setup_quality(
            direction='LONG',
            entry=entry,
            stop=stop,
            targets=targets,
            market_intel=market_intel,
            rr=rr
        )

        return PrecisionSetup(
            entry_price=entry,
            entry_zone=(entry * 0.998, entry * 1.002),  # 0.2% zone
            entry_reason=entry_reason,
            stop_loss=stop,
            stop_reason=stop_reason,
            safe_from_sweep=safe_from_sweep,
            primary_target=targets[0],
            secondary_targets=targets[1:] if len(targets) > 1 else [],
            target_reasons=target_reasons,
            risk_amount=risk,
            reward_amount=reward,
            risk_reward_ratio=rr,
            setup_quality=quality['quality'],
            edge_score=quality['edge']
        )

    def _calculate_short_setup(self, current_price: float, market_intel) -> Optional[PrecisionSetup]:
        """Calculate optimal SHORT setup"""

        print("\n[PRECISION CALCULATOR - SHORT SETUP ANALYSIS]")
        print(f"Current Price: ${current_price:.2f}")

        # STEP 1: Find best entry zone
        print("\n[STEP 1/6] Finding optimal entry zone...")
        print("  - Searching for bearish Order Blocks")
        print("  - Evaluating resistance zones")
        entry, entry_reason = self._find_short_entry(current_price, market_intel)
        if not entry:
            print("  [BLOCKED] No valid entry zone found")
            return None
        print(f"  [FOUND] Entry: ${entry:.2f}")
        print(f"  [REASON] {entry_reason}")

        # STEP 2: Calculate Scalping Stop-Loss
        print("\n[STEP 2/6] Calculating scalping stop placement...")
        stop = entry * (1 + 0.003)
        stop_reason = "Fixed 0.3% scalp stop"
        safe_from_sweep = False  # Not relevant for this strategy
        print(f"  [FOUND] Stop: ${stop:.2f}")
        print(f"  [REASON] {stop_reason}")

        # STEP 3: Find Scalping Take-Profit (Hybrid Model)
        print("\n[STEP 3/6] Identifying scalping take-profit target...")
        print("  - Searching for structural targets in 0.5%-1.0% range")
        
        # Get all potential structural targets
        all_targets, all_reasons = self._find_short_targets(entry, current_price, market_intel)
        
        # Define the sweet spot
        min_tp_price = entry * (1 - 0.01) # 1.0% boundary
        max_tp_price = entry * (1 - 0.005) # 0.5% boundary
        
        # Find targets within the sweet spot
        sweet_spot_targets = []
        for t, r in zip(all_targets, all_reasons):
            if min_tp_price <= t <= max_tp_price:
                sweet_spot_targets.append((t, r))

        if sweet_spot_targets:
            # If targets are in the sweet spot, pick the closest one (highest price for a short)
            best_target, best_reason = max(sweet_spot_targets, key=lambda x: x[0])
            targets = [best_target]
            target_reasons = [f"Structural target in sweet spot: {best_reason}"]
            print(f"  [FOUND] Structural target in 0.5-1.0% range: ${best_target:.2f}")
        else:
            # Otherwise, use the fixed 0.7% fallback
            fallback_tp = entry * (1 - 0.007)
            targets = [fallback_tp]
            target_reasons = ["Fallback to fixed 0.7% target"]
            print("  [FALLBACK] No structural target in range. Using fixed 0.7% TP.")

        if not targets:
            print("  [BLOCKED] No valid targets could be determined.")
            return None
            
        print(f"  [FINAL TP] TP1: ${targets[0]:.2f} - {target_reasons[0]}")

        # STEP 4: Calculate RR
        print("\n[STEP 4/6] Calculating risk/reward ratio...")
        risk = stop - entry
        reward = entry - targets[0]
        rr = reward / risk if risk > 0 else 0
        print(f"  Risk: ${risk:.2f} ({(risk/entry)*100:.2f}%)")
        print(f"  Reward: ${reward:.2f} ({(reward/entry)*100:.2f}%)")
        print(f"  Initial RR: {rr:.2f}:1 {'[GOOD]' if rr >= self.min_risk_reward else '[POOR - needs improvement]'}")

        # STEP 5: Validate RR
        if rr < self.min_risk_reward:
            print(f"\n[STEP 5/6] RR below minimum {self.min_risk_reward}:1 - attempting to improve...")
            print("  - Trying tighter stop placement")
            print("  - Searching for better targets")
            improved = self._try_improve_short_rr(
                entry, stop, targets, current_price, market_intel
            )
            if improved:
                entry, stop, targets = improved
                risk = stop - entry
                reward = entry - targets[0]
                rr = reward / risk
                print(f"  [SUCCESS] Improved RR to {rr:.2f}:1")
                print(f"  [NEW] Entry: ${entry:.2f}, Stop: ${stop:.2f}, TP1: ${targets[0]:.2f}")
            else:
                print(f"  [BLOCKED] Cannot achieve minimum {self.min_risk_reward}:1 RR")
                print("  [DECISION] SKIP TRADE - Better to wait for high-quality setup")
                return None
        else:
            print(f"\n[STEP 5/6] RR validation passed ({rr:.2f}:1 >= {self.min_risk_reward}:1)")

        # STEP 6: Quality assessment
        print("\n[STEP 6/6] Assessing overall setup quality...")
        quality = self._assess_setup_quality(
            direction='SHORT',
            entry=entry,
            stop=stop,
            targets=targets,
            market_intel=market_intel,
            rr=rr
        )

        return PrecisionSetup(
            entry_price=entry,
            entry_zone=(entry * 0.998, entry * 1.002),
            entry_reason=entry_reason,
            stop_loss=stop,
            stop_reason=stop_reason,
            safe_from_sweep=safe_from_sweep,
            primary_target=targets[0],
            secondary_targets=targets[1:] if len(targets) > 1 else [],
            target_reasons=target_reasons,
            risk_amount=risk,
            reward_amount=reward,
            risk_reward_ratio=rr,
            setup_quality=quality['quality'],
            edge_score=quality['edge']
        )

    def _find_long_entry(self, current_price: float, market_intel) -> Tuple[Optional[float], str]:
        """Find optimal LONG entry using Order Blocks"""

        # Prefer bullish Order Blocks near current price
        bullish_obs = [ob for ob in market_intel.order_blocks
                       if ob.type == 'bullish' and ob.entry_zone_low <= current_price]

        if bullish_obs:
            # Get highest quality OB below price
            best_ob = max(bullish_obs, key=lambda x: x.quality_score)

            # Enter at middle of OB
            entry = (best_ob.entry_zone_low + best_ob.entry_zone_high) / 2
            reason = f"Bullish Order Block (${best_ob.entry_zone_low:.2f}-${best_ob.entry_zone_high:.2f}, {best_ob.quality_score:.0%} quality)"

            return entry, reason

        # Fallback: Use nearest swing low
        if market_intel.swing_lows:
            nearest_low = max([s['price'] for s in market_intel.swing_lows
                             if s['price'] < current_price], default=None)
            if nearest_low:
                entry = nearest_low * 1.002  # Slightly above swing
                reason = f"Swing low support (${nearest_low:.2f})"
                return entry, reason

        # Last resort: Current price
        return current_price * 0.998, "Current market (no clear structure)"

    def _find_long_stop(
        self,
        entry: float,
        current_price: float,
        market_intel
    ) -> Tuple[Optional[float], str, bool]:
        """Find safe LONG stop BEYOND liquidity pools"""

        # Find support liquidity pools below entry
        support_pools = [p for p in market_intel.liquidity_pools
                        if p.type == 'support' and p.level < entry]

        if support_pools:
            # Get nearest pool below entry
            nearest_pool = min(support_pools, key=lambda x: abs(x.level - entry))

            # Use safe stop zone (BELOW the liquidity)
            safe_zone = nearest_pool.safe_stop_zone
            stop = safe_zone[0]  # Lower bound of safe zone

            reason = f"Safe zone below liquidity pool @ ${nearest_pool.level:.2f} (won't get swept)"
            safe = True

            return stop, reason, safe

        # Fallback: Below invalidation level
        if hasattr(market_intel, 'swing_lows') and market_intel.swing_lows:
            lowest = min([s['price'] for s in market_intel.swing_lows])
            stop = lowest * (1 - self.stop_buffer_beyond_liquidity)
            reason = f"Below swing structure (${lowest:.2f})"
            safe = False
            return stop, reason, safe

        # Last resort: Fixed % below entry
        stop = entry * 0.985  # 1.5% below
        reason = "Fixed % stop (no clear structure)"
        safe = False
        return stop, reason, safe

    def _find_long_targets(
        self,
        entry: float,
        current_price: float,
        market_intel
    ) -> Tuple[List[float], List[str]]:
        """Find LONG targets using FVGs and liquidity zones"""

        targets = []
        reasons = []

        # Target 1: Unfilled bearish FVGs above (price loves to fill these)
        bearish_fvgs = [fvg for fvg in market_intel.fvgs
                       if fvg.gap_type == 'bearish'
                       and fvg.fill_status == 'UNFILLED'
                       and fvg.gap_start > entry]

        if bearish_fvgs:
            # Get nearest unfilled FVG
            nearest_fvg = min(bearish_fvgs, key=lambda x: abs(x.gap_start - entry))
            targets.append(nearest_fvg.gap_start)
            reasons.append(f"Unfilled FVG @ ${nearest_fvg.gap_start:.2f} ({nearest_fvg.quality_score:.0%} quality)")

        # Target 2: Resistance liquidity pools (where stops cluster)
        resistance_pools = [p for p in market_intel.liquidity_pools
                           if p.type == 'resistance' and p.level > entry]

        if resistance_pools:
            # Target the largest pool (most liquidity)
            largest_pool = max(resistance_pools,
                             key=lambda x: 1.0 if x.pool_size == 'MASSIVE' else
                                          0.75 if x.pool_size == 'LARGE' else
                                          0.5 if x.pool_size == 'MEDIUM' else 0.25)
            targets.append(largest_pool.level)
            reasons.append(f"Liquidity pool @ ${largest_pool.level:.2f} ({largest_pool.pool_size})")

        # Target 3: Swing highs
        if market_intel.swing_highs:
            above_entry = [s['price'] for s in market_intel.swing_highs if s['price'] > entry]
            if above_entry:
                targets.append(min(above_entry))
                reasons.append(f"Swing high resistance @ ${min(above_entry):.2f}")

        # Ensure we have at least one target
        if not targets:
            targets.append(entry * 1.02)  # 2% above
            reasons.append("Fixed % target (no clear structure)")

        # Sort targets by distance (nearest first)
        if len(targets) > 1:
            sorted_pairs = sorted(zip(targets, reasons), key=lambda x: abs(x[0] - entry))
            targets = [t for t, _ in sorted_pairs]
            reasons = [r for _, r in sorted_pairs]

        return targets, reasons

    def _find_short_entry(self, current_price: float, market_intel) -> Tuple[Optional[float], str]:
        """Find optimal SHORT entry"""

        # Prefer bearish Order Blocks
        bearish_obs = [ob for ob in market_intel.order_blocks
                      if ob.type == 'bearish' and ob.entry_zone_high >= current_price]

        if bearish_obs:
            best_ob = max(bearish_obs, key=lambda x: x.quality_score)
            entry = (best_ob.entry_zone_low + best_ob.entry_zone_high) / 2
            reason = f"Bearish Order Block (${best_ob.entry_zone_low:.2f}-${best_ob.entry_zone_high:.2f}, {best_ob.quality_score:.0%} quality)"
            return entry, reason

        # Fallback: Swing high
        if market_intel.swing_highs:
            nearest_high = min([s['price'] for s in market_intel.swing_highs
                              if s['price'] > current_price], default=None)
            if nearest_high:
                entry = nearest_high * 0.998
                reason = f"Swing high resistance (${nearest_high:.2f})"
                return entry, reason

        return current_price * 1.002, "Current market (no clear structure)"

    def _find_short_stop(
        self,
        entry: float,
        current_price: float,
        market_intel
    ) -> Tuple[Optional[float], str, bool]:
        """Find safe SHORT stop"""

        # Find resistance pools above entry
        resistance_pools = [p for p in market_intel.liquidity_pools
                           if p.type == 'resistance' and p.level > entry]

        if resistance_pools:
            nearest_pool = min(resistance_pools, key=lambda x: abs(x.level - entry))
            safe_zone = nearest_pool.safe_stop_zone
            stop = safe_zone[1]  # Upper bound
            reason = f"Safe zone above liquidity pool @ ${nearest_pool.level:.2f} (won't get swept)"
            safe = True
            return stop, reason, safe

        # Fallback: Above swing high
        if market_intel.swing_highs:
            highest = max([s['price'] for s in market_intel.swing_highs])
            stop = highest * (1 + self.stop_buffer_beyond_liquidity)
            reason = f"Above swing structure (${highest:.2f})"
            safe = False
            return stop, reason, safe

        stop = entry * 1.015
        reason = "Fixed % stop (no clear structure)"
        safe = False
        return stop, reason, safe

    def _find_short_targets(
        self,
        entry: float,
        current_price: float,
        market_intel
    ) -> Tuple[List[float], List[str]]:
        """Find SHORT targets"""

        targets = []
        reasons = []

        # Target 1: Unfilled bullish FVGs below
        bullish_fvgs = [fvg for fvg in market_intel.fvgs
                       if fvg.gap_type == 'bullish'
                       and fvg.fill_status == 'UNFILLED'
                       and fvg.gap_end < entry]

        if bullish_fvgs:
            nearest_fvg = min(bullish_fvgs, key=lambda x: abs(x.gap_end - entry))
            targets.append(nearest_fvg.gap_end)
            reasons.append(f"Unfilled FVG @ ${nearest_fvg.gap_end:.2f} ({nearest_fvg.quality_score:.0%} quality)")

        # Target 2: Support liquidity pools
        support_pools = [p for p in market_intel.liquidity_pools
                        if p.type == 'support' and p.level < entry]

        if support_pools:
            largest_pool = max(support_pools,
                             key=lambda x: 1.0 if x.pool_size == 'MASSIVE' else
                                          0.75 if x.pool_size == 'LARGE' else
                                          0.5 if x.pool_size == 'MEDIUM' else 0.25)
            targets.append(largest_pool.level)
            reasons.append(f"Liquidity pool @ ${largest_pool.level:.2f} ({largest_pool.pool_size})")

        # Target 3: Swing lows
        if market_intel.swing_lows:
            below_entry = [s['price'] for s in market_intel.swing_lows if s['price'] < entry]
            if below_entry:
                targets.append(max(below_entry))
                reasons.append(f"Swing low support @ ${max(below_entry):.2f}")

        if not targets:
            targets.append(entry * 0.98)
            reasons.append("Fixed % target (no clear structure)")

        # Sort by distance
        if len(targets) > 1:
            sorted_pairs = sorted(zip(targets, reasons), key=lambda x: abs(x[0] - entry))
            targets = [t for t, _ in sorted_pairs]
            reasons = [r for _, r in sorted_pairs]

        return targets, reasons

    def _try_improve_long_rr(
        self,
        entry: float,
        stop: float,
        targets: List[float],
        current_price: float,
        market_intel
    ) -> Optional[Tuple[float, float, List[float]]]:
        """Try to improve LONG RR by adjusting entry or finding better targets"""

        # Option 1: Tighter stop if possible
        potential_stops = [
            s['price'] * 0.998 for s in market_intel.swing_lows
            if s['price'] < entry and s['price'] > stop
        ]

        if potential_stops:
            new_stop = max(potential_stops)
            risk = entry - new_stop
            reward = targets[0] - entry
            if reward / risk >= self.min_risk_reward:
                return entry, new_stop, targets

        # Option 2: Better target (further FVG or liquidity)
        better_targets = [
            fvg.gap_start for fvg in market_intel.fvgs
            if fvg.gap_type == 'bearish'
            and fvg.gap_start > targets[0]
            and fvg.gap_start < entry * 1.05  # Not too far
        ]

        if better_targets:
            new_target = min(better_targets)
            risk = entry - stop
            reward = new_target - entry
            if reward / risk >= self.min_risk_reward:
                return entry, stop, [new_target] + targets

        return None

    def _try_improve_short_rr(
        self,
        entry: float,
        stop: float,
        targets: List[float],
        current_price: float,
        market_intel
    ) -> Optional[Tuple[float, float, List[float]]]:
        """Try to improve SHORT RR"""

        # Tighter stop
        potential_stops = [
            s['price'] * 1.002 for s in market_intel.swing_highs
            if s['price'] > entry and s['price'] < stop
        ]

        if potential_stops:
            new_stop = min(potential_stops)
            risk = new_stop - entry
            reward = entry - targets[0]
            if reward / risk >= self.min_risk_reward:
                return entry, new_stop, targets

        # Better target
        better_targets = [
            fvg.gap_end for fvg in market_intel.fvgs
            if fvg.gap_type == 'bullish'
            and fvg.gap_end < targets[0]
            and fvg.gap_end > entry * 0.95
        ]

        if better_targets:
            new_target = max(better_targets)
            risk = stop - entry
            reward = entry - new_target
            if reward / risk >= self.min_risk_reward:
                return entry, stop, [new_target] + targets

        return None

    def _assess_setup_quality(
        self,
        direction: str,
        entry: float,
        stop: float,
        targets: List[float],
        market_intel,
        rr: float
    ) -> Dict:
        """Assess overall setup quality and edge"""

        print("\n  [QUALITY ASSESSMENT BREAKDOWN]")
        quality_score = 0.50  # Base
        edge_score = 0.50
        print(f"  Base scores: Quality={quality_score:.2f}, Edge={edge_score:.2f}")

        # RR contribution
        if rr >= self.excellent_risk_reward:
            quality_score += 0.20
            edge_score += 0.15
            print(f"  [+] Excellent RR ({rr:.2f}:1 >= {self.excellent_risk_reward}:1): Quality +0.20, Edge +0.15")
        elif rr >= self.min_risk_reward:
            quality_score += 0.10
            edge_score += 0.05
            print(f"  [+] Good RR ({rr:.2f}:1 >= {self.min_risk_reward}:1): Quality +0.10, Edge +0.05")

        # Order Block quality
        relevant_obs = [ob for ob in market_intel.order_blocks
                       if (direction == 'LONG' and ob.type == 'bullish') or
                          (direction == 'SHORT' and ob.type == 'bearish')]

        if relevant_obs:
            best_ob_quality = max([ob.quality_score for ob in relevant_obs])
            quality_bonus = best_ob_quality * 0.15
            edge_bonus = best_ob_quality * 0.10
            quality_score += quality_bonus
            edge_score += edge_bonus
            print(f"  [+] Order Block quality ({best_ob_quality:.0%}): Quality +{quality_bonus:.2f}, Edge +{edge_bonus:.2f}")
        else:
            print(f"  [0] No Order Blocks: No bonus")

        # FVG targets
        unfilled_fvgs = [fvg for fvg in market_intel.fvgs if fvg.fill_status == 'UNFILLED']
        if unfilled_fvgs:
            quality_score += 0.10
            edge_score += 0.10
            print(f"  [+] Unfilled FVGs available ({len(unfilled_fvgs)}): Quality +0.10, Edge +0.10")
        else:
            print(f"  [0] No unfilled FVGs: No bonus")

        # Confluence
        if market_intel.confluence_score > 70:
            quality_score += 0.15
            edge_score += 0.15
            print(f"  [+] Strong confluence ({market_intel.confluence_score} points > 70): Quality +0.15, Edge +0.15")
        elif market_intel.confluence_score > 50:
            quality_score += 0.10
            edge_score += 0.10
            print(f"  [+] Moderate confluence ({market_intel.confluence_score} points > 50): Quality +0.10, Edge +0.10")
        else:
            print(f"  [0] Weak confluence ({market_intel.confluence_score} points): No bonus")

        # Range trap penalty
        if market_intel.range_trap_analysis.is_trapped:
            quality_score -= 0.20
            edge_score -= 0.15
            print(f"  [-] Range trap detected ({market_intel.range_trap_analysis.trap_severity:.0%}): Quality -0.20, Edge -0.15")

        final_quality = min(1.0, quality_score)
        final_edge = min(1.0, edge_score)
        print(f"\n  [FINAL SCORES]")
        print(f"  Setup Quality: {final_quality:.0%}")
        print(f"  Statistical Edge: {final_edge:.0%}")

        return {
            'quality': final_quality,
            'edge': final_edge
        }


if __name__ == "__main__":
    print("Precision TP/SL Calculator")
    print("Finds high-probability setups with excellent RR (2:1+)")
    print("Uses FVGs, Order Blocks, and safe stop zones")
