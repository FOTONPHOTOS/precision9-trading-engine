"""
MARKET REASONING DICTIONARY
============================

Provides 100% DETAILED, HUMAN-READABLE market analysis breakdowns.

Instead of:
  "Found 25 patterns"

You get:
  PATTERNS DETECTED:
  1. BULLISH BREAK @ $182.45 (3 candles ago) - Strong momentum (+2.3%)
  2. BEARISH BREAK @ $183.10 (8 candles ago) - Rejection from resistance
  3. BULLISH BREAK @ $181.90 (12 candles ago) - Bounce from support

This module creates a "reasoning dictionary" - a smart, detailed breakdown
of what the market is actually doing, so you can follow along manually.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd


@dataclass
class SwingLevelBreakdown:
    """Detailed breakdown of a swing level"""
    price: float
    candles_ago: int
    strength: str  # 'WEAK', 'MEDIUM', 'STRONG', 'VERY_STRONG'
    test_count: int
    last_interaction: str  # 'TESTED', 'BROKEN', 'HOLDING'
    distance_from_current: float  # Percentage
    is_critical: bool  # Is this a make-or-break level?


@dataclass
class PatternBreakdown:
    """Detailed breakdown of a pattern"""
    pattern_type: str
    price: float
    candles_ago: int
    strength_percent: float
    direction: str  # 'BULLISH', 'BEARISH'
    context: str  # What was happening at the time?
    significance: str  # 'LOW', 'MEDIUM', 'HIGH'


@dataclass
class LiquidityBreakdown:
    """Detailed breakdown of liquidity"""
    level: float
    pool_type: str  # 'SUPPORT', 'RESISTANCE'
    size: str  # 'SMALL', 'MEDIUM', 'LARGE', 'MASSIVE'
    status: str  # 'UNTAPPED', 'PARTIALLY_TAPPED', 'SWEPT'
    sweep_probability: float
    distance_from_current: float
    is_magnet: bool  # Is price likely to be drawn here?


class MarketReasoningDictionary:
    """
    Creates comprehensive, human-readable market analysis

    Each section provides:
    - Specific price levels
    - Context (when, how many times, strength)
    - Distance from current price
    - Significance (why it matters)
    - Clear explanations in plain English
    """

    def __init__(self):
        self.current_price = 0.0
        self.current_time = datetime.utcnow()

    def analyze_swing_structure(
        self,
        swing_highs: List[Dict],
        swing_lows: List[Dict],
        current_price: float,
        df: pd.DataFrame
    ) -> Dict:
        """
        Create detailed swing structure breakdown

        Returns: Dict with:
        - resistance_levels: List[SwingLevelBreakdown]
        - support_levels: List[SwingLevelBreakdown]
        - key_zones: Identified critical zones
        - market_position: Where price is relative to structure
        """

        self.current_price = current_price
        latest_index = len(df) - 1

        # Analyze resistance levels (swing highs)
        resistance_levels = []
        for swing in swing_highs[:10]:  # Top 10 most important
            candles_ago = latest_index - swing['index']

            # Calculate distance from current price
            distance_pct = ((swing['price'] - current_price) / current_price) * 100

            # Determine strength (how many times tested)
            test_count = self._count_tests_at_level(df, swing['price'], 0.003)

            if test_count >= 4:
                strength = 'VERY_STRONG'
            elif test_count == 3:
                strength = 'STRONG'
            elif test_count == 2:
                strength = 'MEDIUM'
            else:
                strength = 'WEAK'

            # Determine last interaction
            if abs(distance_pct) < 0.2:
                last_interaction = 'TESTING NOW'
            elif current_price > swing['price']:
                last_interaction = 'BROKEN ABOVE'
            else:
                last_interaction = 'HOLDING AS RESISTANCE'

            # Is this critical? (within 1% and strong)
            is_critical = abs(distance_pct) < 1.0 and test_count >= 3

            resistance_levels.append(SwingLevelBreakdown(
                price=swing['price'],
                candles_ago=candles_ago,
                strength=strength,
                test_count=test_count,
                last_interaction=last_interaction,
                distance_from_current=distance_pct,
                is_critical=is_critical
            ))

        # Analyze support levels (swing lows)
        support_levels = []
        for swing in swing_lows[:10]:  # Top 10 most important
            candles_ago = latest_index - swing['index']

            # Calculate distance from current price
            distance_pct = ((swing['price'] - current_price) / current_price) * 100

            # Determine strength
            test_count = self._count_tests_at_level(df, swing['price'], 0.003)

            if test_count >= 4:
                strength = 'VERY_STRONG'
            elif test_count == 3:
                strength = 'STRONG'
            elif test_count == 2:
                strength = 'MEDIUM'
            else:
                strength = 'WEAK'

            # Determine last interaction
            if abs(distance_pct) < 0.2:
                last_interaction = 'TESTING NOW'
            elif current_price < swing['price']:
                last_interaction = 'BROKEN BELOW'
            else:
                last_interaction = 'HOLDING AS SUPPORT'

            # Is this critical?
            is_critical = abs(distance_pct) < 1.0 and test_count >= 3

            support_levels.append(SwingLevelBreakdown(
                price=swing['price'],
                candles_ago=candles_ago,
                strength=strength,
                test_count=test_count,
                last_interaction=last_interaction,
                distance_from_current=distance_pct,
                is_critical=is_critical
            ))

        # Identify key zones
        key_zones = self._identify_key_zones(resistance_levels, support_levels, current_price)

        # Determine market position
        market_position = self._determine_market_position(
            resistance_levels, support_levels, current_price
        )

        return {
            'resistance_levels': resistance_levels,
            'support_levels': support_levels,
            'key_zones': key_zones,
            'market_position': market_position
        }

    def analyze_patterns(
        self,
        patterns: List[Dict],
        current_price: float,
        df: pd.DataFrame
    ) -> Dict:
        """
        Create detailed pattern breakdown

        Returns: Dict with:
        - bullish_patterns: List[PatternBreakdown]
        - bearish_patterns: List[PatternBreakdown]
        - pattern_bias: Overall bias from patterns
        - recent_momentum: What patterns say about momentum
        """

        latest_index = len(df) - 1

        bullish_patterns = []
        bearish_patterns = []

        for pattern in patterns:
            candles_ago = latest_index - pattern.get('index', 0)
            pattern_type = pattern['type']

            # Get pattern context
            if candles_ago < 5:
                context = "Just happened - Fresh signal"
            elif candles_ago < 15:
                context = "Recent - Still relevant"
            elif candles_ago < 30:
                context = "Moderate age - Losing relevance"
            else:
                context = "Old - May be stale"

            # Determine significance
            strength = pattern.get('break_pct', 0) or pattern.get('strength', 0)

            if strength > 3.0:
                significance = 'HIGH'
            elif strength > 1.5:
                significance = 'MEDIUM'
            else:
                significance = 'LOW'

            breakdown = PatternBreakdown(
                pattern_type=pattern_type,
                price=pattern.get('current_close', pattern.get('price', 0)),
                candles_ago=candles_ago,
                strength_percent=strength,
                direction='BULLISH' if 'BULLISH' in pattern_type else 'BEARISH',
                context=context,
                significance=significance
            )

            if 'BULLISH' in pattern_type:
                bullish_patterns.append(breakdown)
            else:
                bearish_patterns.append(breakdown)

        # Determine pattern bias
        pattern_bias = self._calculate_pattern_bias(bullish_patterns, bearish_patterns)

        # Determine recent momentum
        recent_momentum = self._calculate_recent_momentum(bullish_patterns, bearish_patterns)

        return {
            'bullish_patterns': bullish_patterns,
            'bearish_patterns': bearish_patterns,
            'pattern_bias': pattern_bias,
            'recent_momentum': recent_momentum
        }

    def analyze_smart_money_zones(
        self,
        fvgs: List,
        order_blocks: List,
        current_price: float
    ) -> Dict:
        """
        Create detailed smart money zones breakdown

        Returns: Dict with:
        - active_fvgs: List with details
        - active_obs: List with details
        - nearest_zones: What's closest to price
        - zone_confluence: Where multiple zones overlap
        """

        # FVG Analysis
        active_fvgs = []
        for fvg in fvgs:
            distance_pct = ((fvg.gap_start - current_price) / current_price) * 100

            # Only include if within 5%
            if abs(distance_pct) > 5.0:
                continue

            fvg_detail = {
                'type': fvg.gap_type.upper(),
                'range': (fvg.gap_start, fvg.gap_end),
                'size': fvg.gap_end - fvg.gap_start,
                'distance_pct': distance_pct,
                'quality': fvg.quality_score,
                'status': fvg.fill_status,
                'is_magnet': fvg.fill_status == 'UNFILLED' and fvg.quality_score > 0.70
            }

            active_fvgs.append(fvg_detail)

        # Order Block Analysis
        active_obs = []
        for ob in order_blocks:
            distance_pct = ((ob.high - current_price) / current_price) * 100

            # Only include if within 3%
            if abs(distance_pct) > 3.0:
                continue

            ob_detail = {
                'type': ob.type.upper(),
                'range': (ob.low, ob.high),
                'entry_zone': (ob.entry_zone_low, ob.entry_zone_high),
                'distance_pct': distance_pct,
                'quality': ob.quality_score,
                'is_respected': hasattr(ob, 'was_respected') and ob.was_respected,
                'is_critical': ob.quality_score > 0.75
            }

            active_obs.append(ob_detail)

        # Find nearest zones
        nearest_zones = self._find_nearest_zones(active_fvgs, active_obs, current_price)

        # Find zone confluence (where multiple zones overlap)
        zone_confluence = self._find_zone_confluence(active_fvgs, active_obs)

        return {
            'active_fvgs': active_fvgs,
            'active_obs': active_obs,
            'nearest_zones': nearest_zones,
            'zone_confluence': zone_confluence
        }

    def analyze_liquidity_landscape(
        self,
        liquidity_pools: List,
        liquidity_sweeps: List,
        current_price: float
    ) -> Dict:
        """
        Create detailed liquidity landscape breakdown

        Returns: Dict with:
        - liquidity_breakdown: List[LiquidityBreakdown]
        - magnet_levels: Prices likely to be drawn to
        - swept_levels: Recently swept liquidity
        - trap_zones: Areas of potential stop hunting
        """

        liquidity_breakdown = []

        for pool in liquidity_pools:
            distance_pct = ((pool.level - current_price) / current_price) * 100

            # Determine if this is a magnet (untapped + strong)
            is_magnet = (pool.recent_sweeps == 0 and
                        pool.pool_size in ['LARGE', 'MASSIVE'] and
                        abs(distance_pct) < 2.0)

            # Status
            if pool.recent_sweeps >= 2:
                status = 'SWEPT'
            elif pool.recent_sweeps == 1:
                status = 'PARTIALLY_TAPPED'
            else:
                status = 'UNTAPPED'

            liquidity_breakdown.append(LiquidityBreakdown(
                level=pool.level,
                pool_type=pool.type.upper(),
                size=pool.pool_size,
                status=status,
                sweep_probability=pool.sweep_probability,
                distance_from_current=distance_pct,
                is_magnet=is_magnet
            ))

        # Identify magnet levels
        magnet_levels = [lb for lb in liquidity_breakdown if lb.is_magnet]

        # Identify recently swept levels
        swept_levels = []
        for sweep in liquidity_sweeps:
            if (datetime.utcnow() - sweep.timestamp.to_pydatetime()).total_seconds() < 3600:
                swept_levels.append({
                    'level': sweep.swept_level,
                    'type': sweep.type.upper(),
                    'time_ago_minutes': int((datetime.utcnow() - sweep.timestamp.to_pydatetime()).total_seconds() / 60),
                    'intent': sweep.smart_money_intent,
                    'danger': sweep.danger_level
                })

        # Identify trap zones (areas with multiple sweeps)
        trap_zones = self._identify_trap_zones(swept_levels)

        return {
            'liquidity_breakdown': liquidity_breakdown,
            'magnet_levels': magnet_levels,
            'swept_levels': swept_levels,
            'trap_zones': trap_zones
        }

    def create_trade_reasoning(
        self,
        decision_direction: str,
        decision_confidence: float,
        swing_analysis: Dict,
        pattern_analysis: Dict,
        smart_money_analysis: Dict,
        liquidity_analysis: Dict,
        stop_hunt_warning: any,
        trap_analysis: any
    ) -> Dict:
        """
        Create DETAILED trade reasoning breakdown

        Returns: Dict with:
        - trade_thesis: Main reason for the trade
        - supporting_factors: List of factors supporting the trade (numbered)
        - risk_factors: List of factors against the trade (numbered)
        - key_levels: Critical levels to watch
        - execution_plan: Step-by-step execution plan
        """

        trade_thesis = self._build_trade_thesis(
            decision_direction,
            decision_confidence,
            swing_analysis,
            pattern_analysis,
            smart_money_analysis
        )

        supporting_factors = self._build_supporting_factors(
            decision_direction,
            swing_analysis,
            pattern_analysis,
            smart_money_analysis,
            liquidity_analysis
        )

        risk_factors = self._build_risk_factors(
            decision_direction,
            swing_analysis,
            stop_hunt_warning,
            trap_analysis
        )

        key_levels = self._identify_key_levels(
            decision_direction,
            swing_analysis,
            smart_money_analysis,
            liquidity_analysis
        )

        execution_plan = self._build_execution_plan(
            decision_direction,
            key_levels,
            liquidity_analysis
        )

        return {
            'trade_thesis': trade_thesis,
            'supporting_factors': supporting_factors,
            'risk_factors': risk_factors,
            'key_levels': key_levels,
            'execution_plan': execution_plan
        }

    # ===== HELPER METHODS =====

    def _count_tests_at_level(self, df: pd.DataFrame, level: float, tolerance: float) -> int:
        """Count how many times price tested a level"""
        tests = 0
        for _, row in df.iterrows():
            high = row['high']
            low = row['low']
            if low <= level * (1 + tolerance) and high >= level * (1 - tolerance):
                tests += 1
        return tests

    def _identify_key_zones(
        self,
        resistance_levels: List[SwingLevelBreakdown],
        support_levels: List[SwingLevelBreakdown],
        current_price: float
    ) -> List[Dict]:
        """Identify critical zones where major decisions will be made"""
        key_zones = []

        # Find nearest strong resistance
        strong_resistances = [r for r in resistance_levels
                             if r.strength in ['STRONG', 'VERY_STRONG']
                             and r.price > current_price]
        if strong_resistances:
            nearest_r = min(strong_resistances, key=lambda x: abs(x.distance_from_current))
            key_zones.append({
                'type': 'RESISTANCE',
                'level': nearest_r.price,
                'importance': 'CRITICAL' if nearest_r.is_critical else 'HIGH',
                'reason': f"Strong resistance tested {nearest_r.test_count} times"
            })

        # Find nearest strong support
        strong_supports = [s for s in support_levels
                          if s.strength in ['STRONG', 'VERY_STRONG']
                          and s.price < current_price]
        if strong_supports:
            nearest_s = min(strong_supports, key=lambda x: abs(x.distance_from_current))
            key_zones.append({
                'type': 'SUPPORT',
                'level': nearest_s.price,
                'importance': 'CRITICAL' if nearest_s.is_critical else 'HIGH',
                'reason': f"Strong support tested {nearest_s.test_count} times"
            })

        return key_zones

    def _determine_market_position(
        self,
        resistance_levels: List[SwingLevelBreakdown],
        support_levels: List[SwingLevelBreakdown],
        current_price: float
    ) -> Dict:
        """Determine where price is in the market structure"""

        # Find nearest levels
        resistances_above = [r for r in resistance_levels if r.price > current_price]
        supports_below = [s for s in support_levels if s.price < current_price]

        if resistances_above:
            nearest_resistance = min(resistances_above, key=lambda x: x.distance_from_current)
            distance_to_resistance = nearest_resistance.distance_from_current
        else:
            nearest_resistance = None
            distance_to_resistance = 999.0

        if supports_below:
            nearest_support = min(supports_below, key=lambda x: abs(x.distance_from_current))
            distance_to_support = abs(nearest_support.distance_from_current)
        else:
            nearest_support = None
            distance_to_support = 999.0

        # Determine position
        if distance_to_resistance < 0.5:
            position = "AT_RESISTANCE"
            context = f"Price testing resistance at ${nearest_resistance.price:.2f}"
        elif distance_to_support < 0.5:
            position = "AT_SUPPORT"
            context = f"Price testing support at ${nearest_support.price:.2f}"
        elif distance_to_resistance < distance_to_support:
            position = "NEAR_RESISTANCE"
            context = f"Price {distance_to_resistance:.1f}% from resistance"
        elif distance_to_support < distance_to_resistance:
            position = "NEAR_SUPPORT"
            context = f"Price {distance_to_support:.1f}% from support"
        else:
            position = "MID_RANGE"
            context = "Price in middle of range"

        return {
            'position': position,
            'context': context,
            'distance_to_resistance': distance_to_resistance,
            'distance_to_support': distance_to_support,
            'nearest_resistance': nearest_resistance.price if nearest_resistance else None,
            'nearest_support': nearest_support.price if nearest_support else None
        }

    def _calculate_pattern_bias(
        self,
        bullish_patterns: List[PatternBreakdown],
        bearish_patterns: List[PatternBreakdown]
    ) -> Dict:
        """Calculate overall bias from patterns"""

        # Weight recent patterns more heavily
        bullish_score = sum(
            p.strength_percent * (1.0 if p.candles_ago < 10 else 0.5)
            for p in bullish_patterns
        )

        bearish_score = sum(
            p.strength_percent * (1.0 if p.candles_ago < 10 else 0.5)
            for p in bearish_patterns
        )

        if bullish_score > bearish_score * 1.5:
            bias = "STRONG_BULLISH"
        elif bullish_score > bearish_score:
            bias = "BULLISH"
        elif bearish_score > bullish_score * 1.5:
            bias = "STRONG_BEARISH"
        elif bearish_score > bullish_score:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return {
            'bias': bias,
            'bullish_score': bullish_score,
            'bearish_score': bearish_score
        }

    def _calculate_recent_momentum(
        self,
        bullish_patterns: List[PatternBreakdown],
        bearish_patterns: List[PatternBreakdown]
    ) -> str:
        """Determine recent momentum from patterns"""

        # Only look at last 10 candles
        recent_bullish = [p for p in bullish_patterns if p.candles_ago < 10]
        recent_bearish = [p for p in bearish_patterns if p.candles_ago < 10]

        if recent_bullish and not recent_bearish:
            return "STRONG_BULLISH_MOMENTUM"
        elif recent_bearish and not recent_bullish:
            return "STRONG_BEARISH_MOMENTUM"
        elif len(recent_bullish) > len(recent_bearish):
            return "BULLISH_MOMENTUM"
        elif len(recent_bearish) > len(recent_bullish):
            return "BEARISH_MOMENTUM"
        else:
            return "CHOPPY"

    def _find_nearest_zones(
        self,
        active_fvgs: List[Dict],
        active_obs: List[Dict],
        current_price: float
    ) -> Dict:
        """Find nearest FVG and OB to current price"""

        # Find nearest FVG
        if active_fvgs:
            nearest_fvg = min(active_fvgs, key=lambda x: abs(x['distance_pct']))
        else:
            nearest_fvg = None

        # Find nearest OB
        if active_obs:
            nearest_ob = min(active_obs, key=lambda x: abs(x['distance_pct']))
        else:
            nearest_ob = None

        return {
            'nearest_fvg': nearest_fvg,
            'nearest_ob': nearest_ob
        }

    def _find_zone_confluence(
        self,
        active_fvgs: List[Dict],
        active_obs: List[Dict]
    ) -> List[Dict]:
        """Find areas where FVGs and OBs overlap"""
        confluences = []

        for fvg in active_fvgs:
            for ob in active_obs:
                # Check if they overlap
                fvg_range = fvg['range']
                ob_range = ob['range']

                if (fvg_range[0] <= ob_range[1] and fvg_range[1] >= ob_range[0]):
                    confluences.append({
                        'level': (max(fvg_range[0], ob_range[0]) + min(fvg_range[1], ob_range[1])) / 2,
                        'types': [fvg['type'], ob['type']],
                        'strength': 'HIGH' if fvg['quality'] > 0.7 and ob['quality'] > 0.7 else 'MEDIUM'
                    })

        return confluences

    def _identify_trap_zones(self, swept_levels: List[Dict]) -> List[Dict]:
        """Identify areas with multiple recent sweeps (trap zones)"""
        trap_zones = []

        # Group sweeps by proximity (within 0.5%)
        grouped = {}
        for sweep in swept_levels:
            level = sweep['level']
            found_group = False

            for group_level in grouped.keys():
                if abs((level - group_level) / level) < 0.005:
                    grouped[group_level].append(sweep)
                    found_group = True
                    break

            if not found_group:
                grouped[level] = [sweep]

        # Identify traps (2+ sweeps in same area)
        for level, sweeps in grouped.items():
            if len(sweeps) >= 2:
                trap_zones.append({
                    'level': level,
                    'sweep_count': len(sweeps),
                    'danger': 'HIGH' if len(sweeps) >= 3 else 'MEDIUM',
                    'recommendation': 'AVOID - Smart money hunting stops here'
                })

        return trap_zones

    def _build_trade_thesis(
        self,
        direction: str,
        confidence: float,
        swing_analysis: Dict,
        pattern_analysis: Dict,
        smart_money_analysis: Dict
    ) -> str:
        """Build main trade thesis"""

        if direction == 'LONG':
            thesis = f"LONG bias with {confidence:.0%} confidence. "

            # Add key reason
            if pattern_analysis['pattern_bias']['bias'] in ['BULLISH', 'STRONG_BULLISH']:
                thesis += "Recent bullish patterns show upward momentum. "

            if swing_analysis['market_position']['position'] == 'AT_SUPPORT':
                thesis += f"Price testing support at ${swing_analysis['market_position']['nearest_support']:.2f}. "

            if smart_money_analysis['nearest_zones']['nearest_fvg']:
                fvg = smart_money_analysis['nearest_zones']['nearest_fvg']
                if fvg['type'] == 'BULLISH' and fvg['is_magnet']:
                    thesis += "Bullish FVG above acting as price magnet. "

        elif direction == 'SHORT':
            thesis = f"SHORT bias with {confidence:.0%} confidence. "

            if pattern_analysis['pattern_bias']['bias'] in ['BEARISH', 'STRONG_BEARISH']:
                thesis += "Recent bearish patterns show downward pressure. "

            if swing_analysis['market_position']['position'] == 'AT_RESISTANCE':
                thesis += f"Price testing resistance at ${swing_analysis['market_position']['nearest_resistance']:.2f}. "

            if smart_money_analysis['nearest_zones']['nearest_fvg']:
                fvg = smart_money_analysis['nearest_zones']['nearest_fvg']
                if fvg['type'] == 'BEARISH' and fvg['is_magnet']:
                    thesis += "Bearish FVG below acting as price magnet. "

        else:
            thesis = f"NEUTRAL - No clear direction. Market is choppy or conflicted."

        return thesis

    def _build_supporting_factors(
        self,
        direction: str,
        swing_analysis: Dict,
        pattern_analysis: Dict,
        smart_money_analysis: Dict,
        liquidity_analysis: Dict
    ) -> List[str]:
        """Build numbered list of supporting factors"""

        factors = []

        # Pattern support
        if direction == 'LONG':
            bullish_patterns = pattern_analysis['bullish_patterns']
            if bullish_patterns:
                recent = [p for p in bullish_patterns if p.candles_ago < 15]
                factors.append(f"PATTERNS: {len(recent)} bullish breaks in last 15 candles")

        elif direction == 'SHORT':
            bearish_patterns = pattern_analysis['bearish_patterns']
            if bearish_patterns:
                recent = [p for p in bearish_patterns if p.candles_ago < 15]
                factors.append(f"PATTERNS: {len(recent)} bearish breaks in last 15 candles")

        # Smart money support
        fvgs = [f for f in smart_money_analysis['active_fvgs']
                if (direction == 'LONG' and f['type'] == 'BULLISH') or
                   (direction == 'SHORT' and f['type'] == 'BEARISH')]
        if fvgs:
            magnets = [f for f in fvgs if f['is_magnet']]
            if magnets:
                factors.append(f"SMART MONEY: {len(magnets)} unfilled FVG(s) acting as magnets")

        # Liquidity support
        magnets = liquidity_analysis['magnet_levels']
        if magnets:
            if direction == 'LONG':
                upside_magnets = [m for m in magnets if m.distance_from_current > 0]
                if upside_magnets:
                    factors.append(f"LIQUIDITY: {len(upside_magnets)} untapped pool(s) above - price drawn upward")
            elif direction == 'SHORT':
                downside_magnets = [m for m in magnets if m.distance_from_current < 0]
                if downside_magnets:
                    factors.append(f"LIQUIDITY: {len(downside_magnets)} untapped pool(s) below - price drawn downward")

        return factors

    def _build_risk_factors(
        self,
        direction: str,
        swing_analysis: Dict,
        stop_hunt_warning: any,
        trap_analysis: any
    ) -> List[str]:
        """Build numbered list of risk factors"""

        risks = []

        # Stop hunt risk
        if stop_hunt_warning.is_stop_hunt_mode:
            if stop_hunt_warning.hunt_type == 'BI_DIRECTIONAL':
                risks.append(f"STOP HUNT: Bi-directional manipulation active ({stop_hunt_warning.severity:.0%})")
            else:
                risks.append(f"STOP HUNT: {stop_hunt_warning.hunt_type} detected ({stop_hunt_warning.severity:.0%})")

        # Range trap risk
        if trap_analysis.is_trapped:
            risks.append(f"RANGE TRAP: Trapped in {trap_analysis.trap_severity:.0%} severity range")

        # Proximity to opposing level
        if direction == 'LONG':
            if swing_analysis['market_position']['distance_to_resistance'] < 1.0:
                risks.append(f"RESISTANCE: Only {swing_analysis['market_position']['distance_to_resistance']:.1f}% to resistance - limited upside")

        elif direction == 'SHORT':
            if swing_analysis['market_position']['distance_to_support'] < 1.0:
                risks.append(f"SUPPORT: Only {swing_analysis['market_position']['distance_to_support']:.1f}% to support - limited downside")

        return risks

    def _identify_key_levels(
        self,
        direction: str,
        swing_analysis: Dict,
        smart_money_analysis: Dict,
        liquidity_analysis: Dict
    ) -> Dict:
        """Identify key levels for the trade"""

        if direction == 'LONG':
            # Entry: Current support
            entry = swing_analysis['market_position']['nearest_support']

            # Stop: Below support
            if entry:
                stop = entry * 0.985
            else:
                stop = self.current_price * 0.985

            # Targets: Resistance and magnets
            targets = []
            if swing_analysis['market_position']['nearest_resistance']:
                targets.append(swing_analysis['market_position']['nearest_resistance'])

            for magnet in liquidity_analysis['magnet_levels']:
                if magnet.distance_from_current > 0:
                    targets.append(magnet.level)

        elif direction == 'SHORT':
            # Entry: Current resistance
            entry = swing_analysis['market_position']['nearest_resistance']

            # Stop: Above resistance
            if entry:
                stop = entry * 1.015
            else:
                stop = self.current_price * 1.015

            # Targets: Support and magnets
            targets = []
            if swing_analysis['market_position']['nearest_support']:
                targets.append(swing_analysis['market_position']['nearest_support'])

            for magnet in liquidity_analysis['magnet_levels']:
                if magnet.distance_from_current < 0:
                    targets.append(magnet.level)

        else:
            entry = self.current_price
            stop = self.current_price
            targets = []

        return {
            'entry': entry,
            'stop': stop,
            'targets': sorted(targets, reverse=(direction=='SHORT'))[:3]  # Top 3
        }

    def _build_execution_plan(
        self,
        direction: str,
        key_levels: Dict,
        liquidity_analysis: Dict
    ) -> List[str]:
        """Build step-by-step execution plan"""

        plan = []

        if direction in ['LONG', 'SHORT']:
            plan.append(f"1. ENTRY: Wait for price near ${key_levels['entry']:.2f}")
            plan.append(f"2. STOP LOSS: Place at ${key_levels['stop']:.2f}")

            if key_levels['targets']:
                for i, target in enumerate(key_levels['targets'], 1):
                    plan.append(f"{i+2}. TP{i}: Take profit at ${target:.2f}")

            # Add liquidity context
            trap_zones = liquidity_analysis['trap_zones']
            if trap_zones:
                plan.append(f"{len(plan)+1}. AVOID: Stay away from ${trap_zones[0]['level']:.2f} (trap zone)")

        else:
            plan.append("WAIT: No clear trade setup - monitor for better conditions")

        return plan


def print_detailed_analysis(
    reasoning_dict: MarketReasoningDictionary,
    swing_analysis: Dict,
    pattern_analysis: Dict,
    smart_money_analysis: Dict,
    liquidity_analysis: Dict,
    trade_reasoning: Dict
):
    """
    Print comprehensive, detailed market analysis

    This is what the user sees - 100s of reasoning lines
    """

    print("\n" + "="*100)
    print("COMPREHENSIVE MARKET REASONING DICTIONARY")
    print("="*100)
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Current Price: ${reasoning_dict.current_price:.2f}")
    print("="*100)

    # SWING STRUCTURE SECTION
    print("\n" + "="*100)
    print("[SWING STRUCTURE - SUPPORT & RESISTANCE LEVELS]")
    print("="*100)

    print("\nRESISTANCE LEVELS (Overhead):")
    if swing_analysis['resistance_levels']:
        for i, r in enumerate(swing_analysis['resistance_levels'][:5], 1):
            critical_flag = " [CRITICAL!]" if r.is_critical else ""
            print(f"  {i}. ${r.price:.2f} - {r.strength} ({r.test_count} tests)")
            print(f"     Distance: {r.distance_from_current:+.2f}% | Status: {r.last_interaction}{critical_flag}")
            print(f"     Formed {r.candles_ago} candles ago")
    else:
        print("  No significant resistance levels nearby")

    print("\nSUPPORT LEVELS (Below):")
    if swing_analysis['support_levels']:
        for i, s in enumerate(swing_analysis['support_levels'][:5], 1):
            critical_flag = " [CRITICAL!]" if s.is_critical else ""
            print(f"  {i}. ${s.price:.2f} - {s.strength} ({s.test_count} tests)")
            print(f"     Distance: {s.distance_from_current:+.2f}% | Status: {s.last_interaction}{critical_flag}")
            print(f"     Formed {s.candles_ago} candles ago")
    else:
        print("  No significant support levels nearby")

    print("\nMARKET POSITION:")
    mp = swing_analysis['market_position']
    print(f"  Position: {mp['position']}")
    print(f"  Context: {mp['context']}")
    if mp['nearest_resistance']:
        print(f"  Next Resistance: ${mp['nearest_resistance']:.2f} ({mp['distance_to_resistance']:+.1f}%)")
    if mp['nearest_support']:
        print(f"  Next Support: ${mp['nearest_support']:.2f} ({mp['distance_to_support']:+.1f}%)")

    if swing_analysis['key_zones']:
        print("\nKEY ZONES TO WATCH:")
        for zone in swing_analysis['key_zones']:
            print(f"  • {zone['type']} @ ${zone['level']:.2f} - {zone['importance']} IMPORTANCE")
            print(f"    Reason: {zone['reason']}")

    # PATTERN ANALYSIS SECTION
    print("\n" + "="*100)
    print("[CANDLE PATTERNS - WHAT THE MARKET IS SHOWING]")
    print("="*100)

    print("\nBULLISH PATTERNS:")
    if pattern_analysis['bullish_patterns']:
        for i, p in enumerate(pattern_analysis['bullish_patterns'][:5], 1):
            print(f"  {i}. {p.pattern_type} @ ${p.price:.2f}")
            print(f"     Strength: {p.strength_percent:.2f}% | {p.candles_ago} candles ago")
            print(f"     Context: {p.context} | Significance: {p.significance}")
    else:
        print("  No bullish patterns detected recently")

    print("\nBEARISH PATTERNS:")
    if pattern_analysis['bearish_patterns']:
        for i, p in enumerate(pattern_analysis['bearish_patterns'][:5], 1):
            print(f"  {i}. {p.pattern_type} @ ${p.price:.2f}")
            print(f"     Strength: {p.strength_percent:.2f}% | {p.candles_ago} candles ago")
            print(f"     Context: {p.context} | Significance: {p.significance}")
    else:
        print("  No bearish patterns detected recently")

    print("\nPATTERN BIAS:")
    pb = pattern_analysis['pattern_bias']
    print(f"  Overall Bias: {pb['bias']}")
    print(f"  Bullish Score: {pb['bullish_score']:.1f} | Bearish Score: {pb['bearish_score']:.1f}")
    print(f"  Recent Momentum: {pattern_analysis['recent_momentum']}")

    # SMART MONEY SECTION
    print("\n" + "="*100)
    print("[SMART MONEY ZONES - WHERE INSTITUTIONS ARE ACTIVE]")
    print("="*100)

    print("\nFAIR VALUE GAPS (FVGs):")
    if smart_money_analysis['active_fvgs']:
        for i, fvg in enumerate(smart_money_analysis['active_fvgs'][:5], 1):
            magnet_flag = " [PRICE MAGNET!]" if fvg['is_magnet'] else ""
            print(f"  {i}. {fvg['type']} FVG: ${fvg['range'][0]:.2f} - ${fvg['range'][1]:.2f}{magnet_flag}")
            print(f"     Distance: {fvg['distance_pct']:+.2f}% | Quality: {fvg['quality']:.0%} | Status: {fvg['status']}")
    else:
        print("  No active FVGs within 5%")

    print("\nORDER BLOCKS (OBs):")
    if smart_money_analysis['active_obs']:
        for i, ob in enumerate(smart_money_analysis['active_obs'][:5], 1):
            critical_flag = " [CRITICAL!]" if ob['is_critical'] else ""
            print(f"  {i}. {ob['type']} OB: ${ob['range'][0]:.2f} - ${ob['range'][1]:.2f}{critical_flag}")
            print(f"     Entry Zone: ${ob['entry_zone'][0]:.2f} - ${ob['entry_zone'][1]:.2f}")
            print(f"     Distance: {ob['distance_pct']:+.2f}% | Quality: {ob['quality']:.0%}")
    else:
        print("  No active Order Blocks within 3%")

    if smart_money_analysis['zone_confluence']:
        print("\nZONE CONFLUENCE (FVG + OB Overlap):")
        for i, conf in enumerate(smart_money_analysis['zone_confluence'][:3], 1):
            print(f"  {i}. ${conf['level']:.2f} - {' + '.join(conf['types'])} - {conf['strength']} STRENGTH")

    # LIQUIDITY SECTION
    print("\n" + "="*100)
    print("[LIQUIDITY LANDSCAPE - WHERE THE MONEY IS]")
    print("="*100)

    print("\nLIQUIDITY POOLS:")
    if liquidity_analysis['liquidity_breakdown']:
        for i, liq in enumerate(liquidity_analysis['liquidity_breakdown'][:8], 1):
            magnet_flag = " [MAGNET - Price will be drawn here!]" if liq.is_magnet else ""
            print(f"  {i}. {liq.pool_type} @ ${liq.level:.2f} - {liq.size} SIZE{magnet_flag}")
            print(f"     Distance: {liq.distance_from_current:+.2f}% | Status: {liq.status}")
            print(f"     Sweep Probability: {liq.sweep_probability:.0%}")
    else:
        print("  No significant liquidity pools mapped")

    if liquidity_analysis['swept_levels']:
        print("\nRECENTLY SWEPT LIQUIDITY (Last hour):")
        for i, sweep in enumerate(liquidity_analysis['swept_levels'][:5], 1):
            print(f"  {i}. {sweep['type']} sweep @ ${sweep['level']:.2f}")
            print(f"     Time: {sweep['time_ago_minutes']} minutes ago | Intent: {sweep['intent']} | Danger: {sweep['danger']}")

    if liquidity_analysis['trap_zones']:
        print("\nTRAP ZONES (DANGER - Avoid these areas!):")
        for i, trap in enumerate(liquidity_analysis['trap_zones'], 1):
            print(f"  {i}. ${trap['level']:.2f} - {trap['sweep_count']} sweeps - {trap['danger']} DANGER")
            print(f"     {trap['recommendation']}")

    # TRADE REASONING SECTION
    print("\n" + "="*100)
    print("[TRADE REASONING - WHY THIS TRADE MAKES SENSE (OR DOESN'T)]")
    print("="*100)

    print("\nTRADE THESIS:")
    print(f"  {trade_reasoning['trade_thesis']}")

    if trade_reasoning['supporting_factors']:
        print("\nSUPPORTING FACTORS:")
        for i, factor in enumerate(trade_reasoning['supporting_factors'], 1):
            print(f"  {i}. {factor}")

    if trade_reasoning['risk_factors']:
        print("\nRISK FACTORS:")
        for i, risk in enumerate(trade_reasoning['risk_factors'], 1):
            print(f"  {i}. {risk}")

    print("\nKEY LEVELS FOR EXECUTION:")
    kl = trade_reasoning['key_levels']
    if kl['entry']:
        print(f"  Entry: ${kl['entry']:.2f}")
    if kl['stop']:
        print(f"  Stop Loss: ${kl['stop']:.2f}")
    if kl['targets']:
        print(f"  Targets: {', '.join([f'${t:.2f}' for t in kl['targets']])}")

    print("\nEXECUTION PLAN:")
    for step in trade_reasoning['execution_plan']:
        print(f"  {step}")

    print("\n" + "="*100)
    print("END OF DETAILED REASONING DICTIONARY")
    print("="*100 + "\n")
