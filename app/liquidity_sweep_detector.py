"""
Liquidity Sweep Detector - Stop Hunt & Liquidity Grab Detection

THE HORUS PROBLEM:
- Predicted SHORT → Market ripped through stop loss
- Predicted LONG → Market refused to go, reversed, destroyed stops
- Death by a thousand cuts - constant stop hunts

SOLUTION:
1. Detect when Smart Money is hunting stops (wick sweeps)
2. Identify liquidity pools (where retail stops cluster)
3. Provide "safe zones" for stops (beyond sweep areas)
4. Warn when market is in "stop hunt mode" - DO NOT TRADE

Liquidity Sweep Pattern:
- Price wicks above/below key level (triggers stops)
- Candle closes back inside range (sweep complete)
- Volume spike during sweep (stop orders executed)
- Reversal follows (Smart Money filled orders)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LiquiditySweep:
    """A liquidity sweep event"""
    type: str  # 'bullish_sweep' or 'bearish_sweep'
    timestamp: datetime
    sweep_high: float  # Highest point of wick
    sweep_low: float  # Lowest point of wick
    close_price: float  # Where candle closed
    swept_level: float  # The level that got swept
    sweep_distance: float  # How far above/below level
    volume: float  # Volume during sweep
    reversal_confirmed: bool  # Did price reverse after sweep?

    # Analysis
    liquidity_grabbed: float  # Estimated $ amount of stops triggered
    smart_money_intent: str  # 'STOP_HUNT', 'LIQUIDITY_GRAB', 'FALSE_BREAKOUT'
    danger_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'EXTREME'


@dataclass
class LiquidityPool:
    """Cluster of stops at a level"""
    level: float  # Price level
    type: str  # 'resistance' or 'support'
    stop_type: str  # 'LONG_STOPS' or 'SHORT_STOPS'
    pool_size: str  # 'SMALL', 'MEDIUM', 'LARGE', 'MASSIVE'
    sweep_probability: float  # 0-1 (how likely to get swept)
    safe_stop_zone: Tuple[float, float]  # Where to place stops safely

    # Evidence
    swing_touches: int  # How many times level was touched
    recent_sweeps: int  # How many sweeps at this level
    distance_from_price: float  # Percentage away


@dataclass
class StopHuntWarning:
    """Warning that market is in stop hunt mode"""
    stop_hunt_probability: float  # 0.0 to 1.0, represents the probability of being in a stop hunt
    severity: float  # 0-1
    evidence: List[str]  # Why we think it's stop hunt mode
    recommendation: str
    safe_to_trade: bool

    # NEW: Enhanced classification
    hunt_type: str  # 'DIRECTIONAL_LONG', 'DIRECTIONAL_SHORT', 'BI_DIRECTIONAL', 'NONE'
    range_context: str  # 'TIGHT_RANGE', 'BREAKOUT_UP', 'BREAKOUT_DOWN', 'IN_RANGE'
    is_tradeable_directional: bool  # True if directional hunt WITH breakout


class LiquiditySweepDetector:
    """
    Detects liquidity sweeps and stop hunts

    Protects against the Horus problem:
    - Identifies when Smart Money is hunting stops
    - Maps liquidity pools (where stops cluster)
    - Warns when trading is dangerous
    - Provides safe stop placement zones
    """

    def __init__(self):
        self.min_wick_size = 0.002  # 0.2% minimum wick to be a sweep (was 0.3%)
        self.sweep_confirmation_bars = 2  # Bars to confirm reversal
        self.stop_cluster_tolerance = 0.005  # 0.5% range for stop clustering

    def detect_sweeps(
        self,
        df: pd.DataFrame,
        swing_highs: List[Dict],
        swing_lows: List[Dict]
    ) -> List[LiquiditySweep]:
        """
        Detect all liquidity sweeps in the data

        Liquidity Sweep = Price wicks above/below level, then reverses
        """

        sweeps = []

        # Check each candle for sweep patterns
        for i in range(2, len(df)):
            candle = df.iloc[i]

            # Check for bullish sweep (wick below, close higher)
            bullish_sweep = self._detect_bullish_sweep(df, i, swing_lows)
            if bullish_sweep:
                sweeps.append(bullish_sweep)

            # Check for bearish sweep (wick above, close lower)
            bearish_sweep = self._detect_bearish_sweep(df, i, swing_highs)
            if bearish_sweep:
                sweeps.append(bearish_sweep)

        return sweeps

    def _detect_bullish_sweep(
        self,
        df: pd.DataFrame,
        index: int,
        swing_lows: List[Dict]
    ) -> Optional[LiquiditySweep]:
        """
        Detect bullish liquidity sweep (wick below support, close higher)

        This triggers LONG stops below support, then reverses up
        """

        candle = df.iloc[index]
        candle_low = float(candle['low'])
        candle_close = float(candle['close'])
        candle_open = float(candle['open'])

        # Calculate wick size
        body_low = min(candle_open, candle_close)
        wick_size = (body_low - candle_low) / candle_low

        # Need significant wick below body
        if wick_size < self.min_wick_size:
            return None

        # Find if this wick swept a swing low
        swept_level = None
        for swing in swing_lows:
            swing_price = swing['price']

            # Check if wick went below swing low but close is above
            if candle_low < swing_price and candle_close > swing_price:
                swept_level = swing_price
                break

        if swept_level is None:
            return None

        # Calculate sweep distance
        sweep_distance = (swept_level - candle_low) / swept_level

        # Check for reversal confirmation
        reversal_confirmed = False
        if index + self.sweep_confirmation_bars < len(df):
            next_candles = df.iloc[index+1:index+self.sweep_confirmation_bars+1]
            if all(float(c['close']) > swept_level for _, c in next_candles.iterrows()):
                reversal_confirmed = True

        # Estimate liquidity grabbed (simplified)
        volume = float(candle['volume'])
        liquidity_grabbed = volume * sweep_distance

        # Determine Smart Money intent
        if reversal_confirmed:
            intent = 'STOP_HUNT'  # Classic stop hunt pattern
            danger = 'HIGH'
        elif sweep_distance > 0.01:
            intent = 'LIQUIDITY_GRAB'  # Deep sweep = grabbing liquidity
            danger = 'EXTREME'
        else:
            intent = 'FALSE_BREAKOUT'  # Minor sweep
            danger = 'MEDIUM'

        return LiquiditySweep(
            type='bullish_sweep',
            timestamp=candle.name,
            sweep_high=float(candle['high']),
            sweep_low=candle_low,
            close_price=candle_close,
            swept_level=swept_level,
            sweep_distance=sweep_distance,
            volume=volume,
            reversal_confirmed=reversal_confirmed,
            liquidity_grabbed=liquidity_grabbed,
            smart_money_intent=intent,
            danger_level=danger
        )

    def _detect_bearish_sweep(
        self,
        df: pd.DataFrame,
        index: int,
        swing_highs: List[Dict]
    ) -> Optional[LiquiditySweep]:
        """
        Detect bearish liquidity sweep (wick above resistance, close lower)

        This triggers SHORT stops above resistance, then reverses down
        """

        candle = df.iloc[index]
        candle_high = float(candle['high'])
        candle_close = float(candle['close'])
        candle_open = float(candle['open'])

        # Calculate wick size
        body_high = max(candle_open, candle_close)
        wick_size = (candle_high - body_high) / candle_high

        # Need significant wick above body
        if wick_size < self.min_wick_size:
            return None

        # Find if this wick swept a swing high
        swept_level = None
        for swing in swing_highs:
            swing_price = swing['price']

            # Check if wick went above swing high but close is below
            if candle_high > swing_price and candle_close < swing_price:
                swept_level = swing_price
                break

        if swept_level is None:
            return None

        # Calculate sweep distance
        sweep_distance = (candle_high - swept_level) / swept_level

        # Check for reversal confirmation
        reversal_confirmed = False
        if index + self.sweep_confirmation_bars < len(df):
            next_candles = df.iloc[index+1:index+self.sweep_confirmation_bars+1]
            if all(float(c['close']) < swept_level for _, c in next_candles.iterrows()):
                reversal_confirmed = True

        # Estimate liquidity grabbed
        volume = float(candle['volume'])
        liquidity_grabbed = volume * sweep_distance

        # Determine Smart Money intent
        if reversal_confirmed:
            intent = 'STOP_HUNT'  # Classic stop hunt pattern
            danger = 'HIGH'
        elif sweep_distance > 0.01:
            intent = 'LIQUIDITY_GRAB'  # Deep sweep = grabbing liquidity
            danger = 'EXTREME'
        else:
            intent = 'FALSE_BREAKOUT'  # Minor sweep
            danger = 'MEDIUM'

        return LiquiditySweep(
            type='bearish_sweep',
            timestamp=candle.name,
            sweep_high=candle_high,
            sweep_low=float(candle['low']),
            close_price=candle_close,
            swept_level=swept_level,
            sweep_distance=sweep_distance,
            volume=volume,
            reversal_confirmed=reversal_confirmed,
            liquidity_grabbed=liquidity_grabbed,
            smart_money_intent=intent,
            danger_level=danger
        )

    def map_liquidity_pools(
        self,
        swing_highs: List[Dict],
        swing_lows: List[Dict],
        sweeps: List[LiquiditySweep],
        current_price: float
    ) -> List[LiquidityPool]:
        """
        Map liquidity pools - where retail stops cluster

        These are DANGER ZONES for stop placement
        """

        pools = []

        # Resistance pools (SHORT stops above)
        for swing in swing_highs:
            swing_price = swing['price']

            # Count touches
            touches = sum(1 for s in swing_highs if abs(s['price'] - swing_price) / swing_price < self.stop_cluster_tolerance)

            # Count recent sweeps at this level
            recent_sweeps = sum(1 for sweep in sweeps
                              if sweep.type == 'bearish_sweep'
                              and abs(sweep.swept_level - swing_price) / swing_price < self.stop_cluster_tolerance)

            # Determine pool size
            if touches >= 5:
                pool_size = 'MASSIVE'
                sweep_prob = 0.85
            elif touches >= 3:
                pool_size = 'LARGE'
                sweep_prob = 0.70
            elif touches >= 2:
                pool_size = 'MEDIUM'
                sweep_prob = 0.55
            else:
                pool_size = 'SMALL'
                sweep_prob = 0.35

            # Increase probability if already swept
            if recent_sweeps > 0:
                sweep_prob = min(0.95, sweep_prob + 0.15)

            # Safe stop zone (beyond the pool)
            buffer = swing_price * 0.005  # 0.5% buffer
            safe_stop_zone = (swing_price + buffer, swing_price + buffer * 2)

            # Distance from current price
            distance = (swing_price - current_price) / current_price * 100

            pools.append(LiquidityPool(
                level=swing_price,
                type='resistance',
                stop_type='SHORT_STOPS',
                pool_size=pool_size,
                sweep_probability=sweep_prob,
                safe_stop_zone=safe_stop_zone,
                swing_touches=touches,
                recent_sweeps=recent_sweeps,
                distance_from_price=distance
            ))

        # Support pools (LONG stops below)
        for swing in swing_lows:
            swing_price = swing['price']

            # Count touches
            touches = sum(1 for s in swing_lows if abs(s['price'] - swing_price) / swing_price < self.stop_cluster_tolerance)

            # Count recent sweeps
            recent_sweeps = sum(1 for sweep in sweeps
                              if sweep.type == 'bullish_sweep'
                              and abs(sweep.swept_level - swing_price) / swing_price < self.stop_cluster_tolerance)

            # Determine pool size
            if touches >= 5:
                pool_size = 'MASSIVE'
                sweep_prob = 0.85
            elif touches >= 3:
                pool_size = 'LARGE'
                sweep_prob = 0.70
            elif touches >= 2:
                pool_size = 'MEDIUM'
                sweep_prob = 0.55
            else:
                pool_size = 'SMALL'
                sweep_prob = 0.35

            # Increase probability if already swept
            if recent_sweeps > 0:
                sweep_prob = min(0.95, sweep_prob + 0.15)

            # Safe stop zone (beyond the pool)
            buffer = swing_price * 0.005  # 0.5% buffer
            safe_stop_zone = (swing_price - buffer * 2, swing_price - buffer)

            # Distance from current price
            distance = (swing_price - current_price) / current_price * 100

            pools.append(LiquidityPool(
                level=swing_price,
                type='support',
                stop_type='LONG_STOPS',
                pool_size=pool_size,
                sweep_probability=sweep_prob,
                safe_stop_zone=safe_stop_zone,
                swing_touches=touches,
                recent_sweeps=recent_sweeps,
                distance_from_price=distance
            ))

        # Sort by distance from price
        pools.sort(key=lambda x: abs(x.distance_from_price))

        return pools

    def _analyze_hunt_dynamics(
        self,
        recent_sweeps: List[LiquiditySweep],
        range_context: str
    ) -> Dict[str, Any]:
        """
        Analyzes the dynamics of recent sweeps to determine hunt direction and tradeability.
        Returns a dictionary with 'hunt_type' and 'is_tradeable'.
        """
        if not recent_sweeps:
            return {'hunt_type': 'NONE', 'is_tradeable': False, 'net_pressure_score': 0}

        now = datetime.utcnow()
        net_pressure_score = 0.0
        
        bullish_sweeps = [s for s in recent_sweeps if s.type == 'bullish_sweep']
        bearish_sweeps = [s for s in recent_sweeps if s.type == 'bearish_sweep']

        for sweep in recent_sweeps:
            # Time-decay factor (more recent sweeps have more weight)
            time_ago_hours = (now - sweep.timestamp).total_seconds() / 3600
            recency_weight = max(0, 1.0 - (time_ago_hours / 6.0)) # 6-hour lookback

            # Magnitude factor (larger sweeps have more weight)
            magnitude = sweep.liquidity_grabbed
            
            score = magnitude * recency_weight

            if sweep.type == 'bullish_sweep': # Hunting shorts
                net_pressure_score += score
            else: # Hunting longs
                net_pressure_score -= score
        
        # Determine Hunt Type
        if net_pressure_score > 10000:
            hunt_type = 'DIRECTIONAL_LONG'
        elif net_pressure_score < -10000:
            hunt_type = 'DIRECTIONAL_SHORT'
        elif abs(len(bullish_sweeps) - len(bearish_sweeps)) <= 1 and len(recent_sweeps) > 3:
            hunt_type = 'BI_DIRECTIONAL'
        else:
            hunt_type = 'NONE'

        # Determine Tradeability
        is_tradeable = False
        if hunt_type in ['DIRECTIONAL_LONG', 'DIRECTIONAL_SHORT']:
            # A clean, directional hunt is tradeable if it's not in a choppy, tight range
            if range_context not in ['TIGHT_RANGE', 'IN_RANGE']:
                is_tradeable = True

        return {
            'hunt_type': hunt_type,
            'is_tradeable': is_tradeable,
            'net_pressure_score': net_pressure_score
        }

    def _check_range_context(self, recent_sweeps: List[LiquiditySweep], current_price: float) -> str:
        """
        Analyzes recent sweeps to determine the broader range context.
        """
        if not recent_sweeps:
            return 'NO_CONTEXT'

        recent_sweep_prices = [s.swept_level for s in recent_sweeps]
        if not recent_sweep_prices:
            return 'NO_CONTEXT'
            
        price_range = max(recent_sweep_prices) - min(recent_sweep_prices)
        
        if price_range / current_price < 0.01: # Less than 1% range
            return 'TIGHT_RANGE'

        # Check for breakouts
        highest_sweep = max(recent_sweep_prices)
        lowest_sweep = min(recent_sweep_prices)

        if current_price > highest_sweep * 1.002:
            return 'BREAKOUT_UP'
        elif current_price < lowest_sweep * 0.998:
            return 'BREAKOUT_DOWN'

        return 'IN_RANGE'

    def detect_stop_hunt_mode(
        self,
        sweeps: List[LiquiditySweep],
        pools: List[Dict],
        current_price: float,
        lci_score: float,
        taker_ratio: Optional[float],
        symbol_24h_volume: Optional[float], # NEW
        df: Optional[pd.DataFrame] = None,
        lookback_hours: float = 6.0
    ) -> StopHuntWarning:
        """
        Detect if market is in "stop hunt mode" using time-weighted scoring and new data points.
        """
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=lookback_hours)
            recent_sweeps = [s for s in sweeps if s.timestamp >= cutoff]
            
            evidence = []
            severity = 0.0
            probability = 0.0

            # 1. Time-weighted score from recent sweeps
            if recent_sweeps:
                time_weighted_score = 0
                for sweep in recent_sweeps:
                    time_ago_hours = (now - sweep.timestamp).total_seconds() / 3600
                    recency_weight = max(0, 1.0 - (time_ago_hours / lookback_hours))
                    danger_multiplier = {'EXTREME': 1.5, 'HIGH': 1.0, 'MEDIUM': 0.5, 'LOW': 0.1}.get(sweep.danger_level, 0.2)
                    time_weighted_score += (0.1 * recency_weight * danger_multiplier)
                
                # Cap the score to prevent it from dominating everything else
                time_weighted_score = min(time_weighted_score, 0.40)
                if time_weighted_score > 0.05:
                    severity += time_weighted_score
                    evidence.append(f"Time-weighted sweep score is {time_weighted_score:.2f} based on {len(recent_sweeps)} recent sweeps.")

            # 2. Repeated sweeps at the same level (classic stop running)
            level_sweeps = {}
            for sweep in recent_sweeps:
                # Round level to group nearby sweeps
                level = round(sweep.swept_level / self.stop_cluster_tolerance) * self.stop_cluster_tolerance
                if level not in level_sweeps: level_sweeps[level] = []
                level_sweeps[level].append(sweep.timestamp)
            
            repeatedly_swept_levels = {lvl: ts for lvl, ts in level_sweeps.items() if len(ts) >= 2}
            if repeatedly_swept_levels:
                severity += 0.20
                evidence.append(f"{len(repeatedly_swept_levels)} level(s) have been swept multiple times.")

            # 3. LCI vs Taker Ratio Divergence (Crowd vs Aggression)
            if lci_score is not None and taker_ratio is not None:
                is_retail_long = lci_score > 0.60
                is_retail_short = lci_score < 0.40
                is_aggression_selling = taker_ratio < 0.90
                is_aggression_buying = taker_ratio > 1.10

                if is_retail_long and is_aggression_selling:
                    probability += 0.30
                    evidence.append(f"DIVERGENCE: Retail is crowded long (LCI: {lci_score:.2f}) while market is selling aggressively (Taker Ratio: {taker_ratio:.2f}). High risk of a long squeeze.")
                
                if is_retail_short and is_aggression_buying:
                    probability += 0.30
                    evidence.append(f"DIVERGENCE: Retail is crowded short (LCI: {lci_score:.2f}) while market is buying aggressively (Taker Ratio: {taker_ratio:.2f}). High risk of a short squeeze.")

            final_probability = min((severity + probability), 1.0)
            
            range_context = self._check_range_context(recent_sweeps, current_price)
            hunt_dynamics = self._analyze_hunt_dynamics(recent_sweeps, range_context)
            hunt_type = hunt_dynamics['hunt_type']
            is_tradeable = hunt_dynamics['is_tradeable']

            if hunt_type != 'NONE':
                evidence.append(f"Hunt Type: {hunt_type} (Pressure Score: {hunt_dynamics['net_pressure_score']:.2f})")
                if is_tradeable:
                    evidence.append("OPPORTUNITY: Hunt is directional and clear, offering a potential fading opportunity.")

            if not evidence:
                evidence.append("No significant stop hunt activity detected")

            return StopHuntWarning(
                stop_hunt_probability=final_probability,
                severity=severity,
                evidence=evidence,
                recommendation="Fade directional hunts, avoid bi-directional chop." if is_tradeable else "High risk of manipulation, trading not advised.",
                safe_to_trade=final_probability < 0.4,
                hunt_type=hunt_type,
                range_context=range_context,
                is_tradeable_directional=is_tradeable
            )
        except Exception as e:
            logger.error(f"Error in detect_stop_hunt_mode: {e}", exc_info=True)
            return StopHuntWarning(
                stop_hunt_probability=0.0, severity=0.0, evidence=["Detector failed"], 
                recommendation="SAFE DEFAULT", safe_to_trade=True, 
                hunt_type='NONE', range_context='NONE', is_tradeable_directional=False
            )


def print_liquidity_analysis(
    sweeps: List[LiquiditySweep],
    pools: List[LiquidityPool],
    warning: StopHuntWarning,
    current_price: float
):
    """Pretty print liquidity analysis"""

    print("\n" + "="*80)
    print("LIQUIDITY SWEEP ANALYSIS - STOP HUNT DETECTION")
    print("="*80)

    # Stop Hunt Warning
    status_icon = "[DANGER]" if warning.stop_hunt_probability > 0.8 else "[OK]" if warning.safe_to_trade else "[WARNING]"
    print(f"\n{status_icon} STOP HUNT MODE: {'ACTIVE' if warning.stop_hunt_probability > 0.5 else 'INACTIVE'}")
    print(f"Severity: {warning.severity:.0%}")
    print(f"Safe to Trade: {'NO' if not warning.safe_to_trade else 'YES' if warning.severity < 0.3 else 'CAUTION'}")

    print(f"\n[EVIDENCE]")
    for ev in warning.evidence:
        print(f"  - {ev}")

    print(f"\n[RECOMMENDATION]")
    print(f"  {warning.recommendation}")

    # Recent Sweeps
    if sweeps:
        print(f"\n{'='*80}")
        print(f"RECENT LIQUIDITY SWEEPS - {len(sweeps)} detected")
        print(f"{'='*80}")

        for i, sweep in enumerate(sweeps[:5], 1):
            now = datetime.utcnow()
            time_ago = (now - sweep.timestamp).total_seconds() / 60

            print(f"\n{i}. {sweep.type.upper().replace('_', ' ')} ({sweep.danger_level} danger)")
            print(f"   Time: {time_ago:.0f} mins ago")
            print(f"   Swept Level: ${sweep.swept_level:.2f}")
            print(f"   Sweep Distance: {sweep.sweep_distance:.2%}")
            print(f"   Intent: {sweep.smart_money_intent}")
            print(f"   Reversal Confirmed: {'YES' if sweep.reversal_confirmed else 'NO'}")

            if sweep.smart_money_intent == 'STOP_HUNT':
                print(f"   [ALERT] Classic stop hunt - stops triggered then reversed!")

    # Liquidity Pools
    if pools:
        print(f"\n{'='*80}")
        print(f"LIQUIDITY POOLS (Stop Clusters) - {len(pools)} found")
        print(f"{'='*80}")
        print(f"\nCurrent Price: ${current_price:.2f}")
        print(f"\n[WARNING] These are DANGER ZONES for stop placement!")

        for i, pool in enumerate(pools[:5], 1):
            print(f"\n{i}. {pool.type.upper()} @ ${pool.level:.2f} ({pool.pool_size} pool)")
            print(f"   Stop Type: {pool.stop_type}")
            print(f"   Sweep Probability: {pool.sweep_probability:.0%}")
            print(f"   Distance: {pool.distance_from_price:+.2f}%")
            print(f"   Touches: {pool.swing_touches}")
            print(f"   Recent Sweeps: {pool.recent_sweeps}")
            print(f"   SAFE STOP ZONE: ${pool.safe_stop_zone[0]:.2f} - ${pool.safe_stop_zone[1]:.2f}")

            if pool.sweep_probability > 0.70:
                print(f"   [DANGER] High sweep risk - avoid placing stops at this level!")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    print("Liquidity Sweep Detector - Horus Protection System")
    print("Detects stop hunts and liquidity grabs to prevent death by a thousand cuts")
    print("\nModule ready for integration")
