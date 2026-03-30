"""
Arsenal Data Collector
======================
Collects real-time data from the Arsenal Trendline System:
- Swing highs/lows
- Pattern detections
- FVG zones
- Order Blocks
- Liquidity Sweeps and Pools
- Stop Hunt warnings
- Range Trap analysis
- Confluence scores

This data will be used for hybrid validation with Horus system.
"""

import asyncio
import json
import time
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('ARSENAL_COLLECTOR')


@dataclass
class ArsenalDataSnapshot:
    """Complete snapshot of Arsenal system data at a point in time"""
    timestamp: float

    # Current Market State
    current_price: float
    current_candle_timestamp: float

    # Swing Points
    swing_high: Optional[float]
    swing_low: Optional[float]
    swing_high_age: int  # bars ago
    swing_low_age: int  # bars ago

    # Pattern Detections
    patterns: List[Dict[str, Any]]  # {type, current_close, break_pct, ...}
    pattern_count: int

    # Fair Value Gaps
    bullish_fvgs: List[Dict[str, Any]]  # {gap_type, gap_start, gap_end, distance_pct}
    bearish_fvgs: List[Dict[str, Any]]
    fvg_count: int

    # Order Blocks
    bullish_obs: List[Dict[str, Any]]  # {type, low, high, quality_score, distance_pct}
    bearish_obs: List[Dict[str, Any]]
    ob_count: int

    # Liquidity Analysis
    liquidity_sweeps: List[Dict[str, Any]]  # {type, swept_level, smart_money_intent, danger_level}
    liquidity_pools: List[Dict[str, Any]]  # {level, status, pool_size, sweep_probability, distance_pct}
    untapped_pools_count: int
    tapped_pools_count: int

    # Stop Hunt Detection
    stop_hunt_active: bool
    stop_hunt_severity: str
    stop_hunt_recommendation: str
    stop_hunt_evidence: List[str]

    # Range Trap Analysis
    range_trap_detected: bool
    range_trap_severity: str
    range_trap_danger_level: str

    # Confluence Scores
    bullish_confluence: int
    bearish_confluence: int
    dominant_bias: str

    # Brain Decision (if available)
    brain_direction: Optional[str]
    brain_confidence: Optional[float]
    brain_signal_strength: Optional[str]
    brain_risk_reward: Optional[float]
    brain_should_trade: Optional[bool]

    # Data Quality
    modules_active: int
    analysis_quality: float

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class ArsenalDataCollector:
    """
    Collects real-time data from Arsenal Trendline System
    """

    def __init__(self):
        # Data storage
        self.latest_snapshot: Optional[ArsenalDataSnapshot] = None
        self.snapshot_history = deque(maxlen=1000)  # Keep last 1000 snapshots

        # Statistics
        self.snapshots_collected = 0
        self.collection_start_time = None

        # Collection control
        self.collecting = False

    def start_collection(self):
        """Start collecting data"""
        logger.info("="*80)
        logger.info("ARSENAL DATA COLLECTOR - STARTED")
        logger.info("="*80)

        self.collecting = True
        self.collection_start_time = time.time()

    def collect_snapshot(self,
                        current_price: float,
                        current_candle_timestamp: float,
                        swing_analysis: Dict,
                        patterns: List,
                        fvgs: List,
                        order_blocks: List,
                        liquidity_sweeps: List,
                        liquidity_pools: List,
                        stop_hunt_warning: Any,
                        range_trap: Any,
                        confluence: Dict,
                        brain_decision: Optional[Any] = None) -> ArsenalDataSnapshot:
        """
        Collect a snapshot of all Arsenal data

        Args:
            current_price: Current market price
            current_candle_timestamp: Timestamp of current candle
            swing_analysis: Dict with swing_high, swing_low, bars_since_high, bars_since_low
            patterns: List of pattern dataclasses
            fvgs: List of FairValueGap dataclasses
            order_blocks: List of OrderBlock dataclasses
            liquidity_sweeps: List of LiquiditySweep dataclasses
            liquidity_pools: List of LiquidityPool dataclasses
            stop_hunt_warning: StopHuntWarning dataclass
            range_trap: RangeTrapAnalysis dataclass
            confluence: Dict with bullish_score, bearish_score
            brain_decision: Optional IntelligentDecision dataclass

        Returns:
            ArsenalDataSnapshot
        """

        # Process patterns
        pattern_list = []
        for pattern in patterns:
            pattern_list.append({
                'type': pattern.get('type', 'unknown'),
                'current_close': pattern.get('current_close', 0),
                'break_pct': pattern.get('break_pct', 0),
                'timestamp': pattern.get('timestamp', 0)
            })

        # Process FVGs
        bullish_fvgs = []
        bearish_fvgs = []
        for fvg in fvgs:
            fvg_dict = {
                'gap_type': fvg.gap_type,
                'gap_start': fvg.gap_start,
                'gap_end': fvg.gap_end,
                'distance_pct': ((fvg.gap_end - current_price) / current_price) * 100
            }
            if fvg.gap_type == 'bullish':
                bullish_fvgs.append(fvg_dict)
            else:
                bearish_fvgs.append(fvg_dict)

        # Process Order Blocks
        bullish_obs = []
        bearish_obs = []
        for ob in order_blocks:
            ob_dict = {
                'type': ob.type,
                'low': ob.low,
                'high': ob.high,
                'quality_score': ob.quality_score if hasattr(ob, 'quality_score') else 0,
                'distance_pct': ((ob.high - current_price) / current_price) * 100
            }
            if ob.type == 'bullish':
                bullish_obs.append(ob_dict)
            else:
                bearish_obs.append(ob_dict)

        # Process Liquidity Sweeps
        sweep_list = []
        for sweep in liquidity_sweeps:
            sweep_list.append({
                'type': sweep.type,
                'swept_level': sweep.swept_level,
                'smart_money_intent': sweep.smart_money_intent,
                'danger_level': sweep.danger_level
            })

        # Process Liquidity Pools
        pool_list = []
        untapped_count = 0
        tapped_count = 0
        for pool in liquidity_pools:
            pool_dict = {
                'level': pool.level,
                'status': 'UNTAPPED' if pool.recent_sweeps == 0 else 'TAPPED',
                'pool_size': pool.pool_size,
                'sweep_probability': pool.sweep_probability,
                'distance_pct': ((pool.level - current_price) / current_price) * 100
            }
            pool_list.append(pool_dict)

            if pool.recent_sweeps == 0:
                untapped_count += 1
            else:
                tapped_count += 1

        # Process Stop Hunt Warning
        stop_hunt_active = stop_hunt_warning.is_stop_hunt_mode
        stop_hunt_severity = stop_hunt_warning.severity if hasattr(stop_hunt_warning, 'severity') else 'NONE'
        stop_hunt_recommendation = stop_hunt_warning.recommendation
        stop_hunt_evidence = list(stop_hunt_warning.evidence) if stop_hunt_warning.evidence else []

        # Process Range Trap
        range_trap_detected = range_trap.is_trapped
        range_trap_severity = range_trap.trap_severity if hasattr(range_trap, 'trap_severity') else 'NONE'
        range_trap_danger = range_trap.danger_level if hasattr(range_trap, 'danger_level') else 'NONE'

        # Process Confluence
        bullish_conf = confluence.get('bullish_score', 0)
        bearish_conf = confluence.get('bearish_score', 0)
        dominant_bias = 'BULLISH' if bullish_conf > bearish_conf else 'BEARISH' if bearish_conf > bullish_conf else 'NEUTRAL'

        # Process Brain Decision
        brain_dir = None
        brain_conf = None
        brain_strength = None
        brain_rr = None
        brain_trade = None

        if brain_decision:
            brain_dir = brain_decision.direction
            brain_conf = brain_decision.confidence
            brain_strength = brain_decision.signal_strength
            brain_rr = brain_decision.risk_reward
            brain_trade = brain_decision.should_trade

        # Count active modules (approximate)
        modules_active = 0
        if patterns: modules_active += 1
        if fvgs: modules_active += 1
        if order_blocks: modules_active += 1
        if liquidity_sweeps or liquidity_pools: modules_active += 1
        if stop_hunt_active: modules_active += 1
        if range_trap_detected: modules_active += 1
        if confluence: modules_active += 1

        # Calculate analysis quality (rough estimate)
        analysis_quality = min(1.0, modules_active / 7.0)  # 7 major modules

        # Create snapshot
        snapshot = ArsenalDataSnapshot(
            timestamp=time.time(),
            current_price=current_price,
            current_candle_timestamp=current_candle_timestamp,

            swing_high=swing_analysis.get('swing_high'),
            swing_low=swing_analysis.get('swing_low'),
            swing_high_age=swing_analysis.get('bars_since_high', 0),
            swing_low_age=swing_analysis.get('bars_since_low', 0),

            patterns=pattern_list,
            pattern_count=len(pattern_list),

            bullish_fvgs=bullish_fvgs,
            bearish_fvgs=bearish_fvgs,
            fvg_count=len(fvgs),

            bullish_obs=bullish_obs,
            bearish_obs=bearish_obs,
            ob_count=len(order_blocks),

            liquidity_sweeps=sweep_list,
            liquidity_pools=pool_list,
            untapped_pools_count=untapped_count,
            tapped_pools_count=tapped_count,

            stop_hunt_active=stop_hunt_active,
            stop_hunt_severity=stop_hunt_severity,
            stop_hunt_recommendation=stop_hunt_recommendation,
            stop_hunt_evidence=stop_hunt_evidence,

            range_trap_detected=range_trap_detected,
            range_trap_severity=range_trap_severity,
            range_trap_danger_level=range_trap_danger,

            bullish_confluence=bullish_conf,
            bearish_confluence=bearish_conf,
            dominant_bias=dominant_bias,

            brain_direction=brain_dir,
            brain_confidence=brain_conf,
            brain_signal_strength=brain_strength,
            brain_risk_reward=brain_rr,
            brain_should_trade=brain_trade,

            modules_active=modules_active,
            analysis_quality=analysis_quality
        )

        # Store snapshot
        if self.collecting:
            self.latest_snapshot = snapshot
            self.snapshot_history.append(snapshot)
            self.snapshots_collected += 1

            # Log every 20 snapshots
            if self.snapshots_collected % 20 == 0:
                logger.info(f"Collected {self.snapshots_collected} snapshots | "
                          f"Price: ${current_price:.2f} | "
                          f"FVGs: {len(fvgs)} | OBs: {len(order_blocks)} | "
                          f"Pools: {untapped_count}U/{tapped_count}T | "
                          f"Bias: {dominant_bias}")

        return snapshot

    def get_latest_snapshot(self) -> Optional[ArsenalDataSnapshot]:
        """Get the most recent data snapshot"""
        return self.latest_snapshot

    def get_snapshot_history(self, count: int = 100) -> List[ArsenalDataSnapshot]:
        """Get recent snapshot history"""
        return list(self.snapshot_history)[-count:]

    def export_data(self, filepath: str):
        """Export collected data to JSON file"""
        try:
            data = {
                'collection_info': {
                    'total_snapshots': self.snapshots_collected,
                    'collection_start_time': self.collection_start_time,
                    'collection_duration': time.time() - self.collection_start_time if self.collection_start_time else 0
                },
                'latest_snapshot': self.latest_snapshot.to_dict() if self.latest_snapshot else None,
                'snapshot_history': [s.to_dict() for s in self.snapshot_history]
            }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Arsenal data exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False

    def stop_collection(self):
        """Stop collecting data"""
        logger.info("="*80)
        logger.info("ARSENAL DATA COLLECTOR - STOPPED")
        logger.info("="*80)
        logger.info(f"Total snapshots collected: {self.snapshots_collected}")

        if self.collection_start_time:
            duration = time.time() - self.collection_start_time
            logger.info(f"Collection duration: {duration:.1f}s")
            if duration > 0:
                rate = self.snapshots_collected / duration
                logger.info(f"Average rate: {rate:.2f} snapshots/second")

        self.collecting = False
        logger.info("Arsenal collector stopped")
