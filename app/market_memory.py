"""
Market Memory System - Persistent Intelligence Storage

Gives the arsenal long-term memory and learning capabilities:
- Remembers market events (sweeps, traps, breakouts)
- Tracks decisions and outcomes
- Builds pattern recognition from history
- Survives restarts and extended runtime
- Learns "what" and "why" market does things

Database Tables:
- market_events: All significant market events
- trading_decisions: What was decided and why
- range_periods: Historical range trap periods
- sweep_sequences: Liquidity sweep patterns
- pattern_outcomes: How patterns resolved
- market_regimes: Bull/bear/range identification
"""

import sqlite3
import json
from datetime import datetime, timedelta
from timezone_utils import get_utc_now
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pandas as pd
from pathlib import Path


@dataclass
class MarketEvent:
    """A significant market event"""
    timestamp: datetime
    event_type: str  # 'sweep', 'trap', 'breakout', 'reversal', 'bos', 'choch'
    severity: float  # 0-1
    price_level: float
    direction: str  # 'bullish', 'bearish', 'neutral'
    context: Dict  # Additional context data


@dataclass
class TradingDecision:
    """A trading decision made by the brain"""
    timestamp: datetime
    decision_id: str
    direction: str
    confidence: float
    signal_strength: str
    should_trade: bool
    blockers: List[str]
    warnings: List[str]
    reasoning: str
    price_at_decision: float

    # Outcome tracking (filled later)
    outcome: Optional[str] = None  # 'correct', 'wrong', 'neutral', 'blocked'
    price_change_24h: Optional[float] = None


@dataclass
class RangePeriod:
    """A period where market was trapped in range"""
    start_time: datetime
    end_time: Optional[datetime]
    range_high: float
    range_low: float
    range_size_pct: float
    trap_severity: float
    sweep_count: int
    resolution: Optional[str]  # 'breakout_up', 'breakout_down', 'ongoing'


@dataclass
class MarketRegime:
    """Market regime identification"""
    start_time: datetime
    end_time: Optional[datetime]
    regime_type: str  # 'bull_trend', 'bear_trend', 'range', 'volatile', 'stop_hunt'
    confidence: float
    characteristics: Dict  # Key features of this regime


class MarketMemory:
    """
    Persistent memory system for market intelligence

    Stores all significant events and can retrieve historical context
    """

    def __init__(self, db_path: str = "market_memory.db"):
        """Initialize market memory database"""

        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self._create_tables()

        print(f"[MEMORY SYSTEM] Initialized at {self.db_path}")
        print(f"[MEMORY SYSTEM] Loading historical context...")

        # Load statistics
        stats = self.get_memory_stats()
        print(f"   Events in memory: {stats['total_events']}")
        print(f"   Decisions tracked: {stats['total_decisions']}")
        print(f"   Range periods: {stats['range_periods']}")
        print(f"   Days of history: {stats['days_of_history']:.1f}")

    def _create_tables(self):
        """Create database schema"""

        cursor = self.conn.cursor()

        # Market Events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                event_type TEXT NOT NULL,
                severity REAL,
                price_level REAL,
                direction TEXT,
                context_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Trading Decisions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                decision_id TEXT UNIQUE,
                direction TEXT,
                confidence REAL,
                signal_strength TEXT,
                should_trade BOOLEAN,
                blockers_json TEXT,
                warnings_json TEXT,
                reasoning TEXT,
                price_at_decision REAL,
                outcome TEXT,
                price_change_24h REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Range Periods Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS range_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                range_high REAL,
                range_low REAL,
                range_size_pct REAL,
                trap_severity REAL,
                sweep_count INTEGER,
                resolution TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sweep Sequences Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sweep_sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time DATETIME NOT NULL,
                sweep_count INTEGER,
                direction TEXT,
                severity REAL,
                context_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Pattern Outcomes Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                pattern_type TEXT,
                direction TEXT,
                price_at_pattern REAL,
                outcome TEXT,
                price_move_pct REAL,
                time_to_resolution_hours REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Market Regimes Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_regimes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                regime_type TEXT,
                confidence REAL,
                characteristics_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for fast queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON market_events(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON market_events(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_time ON trading_decisions(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranges_time ON range_periods(start_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_regimes_time ON market_regimes(start_time)")

        self.conn.commit()

    # =================================================================
    # RECORDING FUNCTIONS
    # =================================================================

    def record_event(self, event: MarketEvent):
        """Record a market event"""

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO market_events (timestamp, event_type, severity, price_level, direction, context_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.timestamp,
            event.event_type,
            event.severity,
            event.price_level,
            event.direction,
            json.dumps(event.context)
        ))
        self.conn.commit()

    def record_decision(self, decision: TradingDecision):
        """Record a trading decision"""

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO trading_decisions (
                timestamp, decision_id, direction, confidence, signal_strength,
                should_trade, blockers_json, warnings_json, reasoning, price_at_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.timestamp,
            decision.decision_id,
            decision.direction,
            decision.confidence,
            decision.signal_strength,
            decision.should_trade,
            json.dumps(decision.blockers),
            json.dumps(decision.warnings),
            decision.reasoning,
            decision.price_at_decision
        ))
        self.conn.commit()

    def start_range_period(self, period: RangePeriod):
        """Start tracking a range period"""

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO range_periods (
                start_time, range_high, range_low, range_size_pct, trap_severity, sweep_count
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            period.start_time,
            period.range_high,
            period.range_low,
            period.range_size_pct,
            period.trap_severity,
            period.sweep_count
        ))
        self.conn.commit()
        return cursor.lastrowid

    def end_range_period(self, period_id: int, end_time: datetime, resolution: str):
        """End a range period and record resolution"""

        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE range_periods
            SET end_time = ?, resolution = ?
            WHERE id = ?
        """, (end_time, resolution, period_id))
        self.conn.commit()

    def start_regime(self, regime: MarketRegime):
        """Start tracking a market regime"""

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO market_regimes (
                start_time, regime_type, confidence, characteristics_json
            ) VALUES (?, ?, ?, ?)
        """, (
            regime.start_time,
            regime.regime_type,
            regime.confidence,
            json.dumps(regime.characteristics)
        ))
        self.conn.commit()
        return cursor.lastrowid

    def end_regime(self, regime_id: int, end_time: datetime):
        """End a market regime"""

        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE market_regimes
            SET end_time = ?
            WHERE id = ?
        """, (end_time, regime_id))
        self.conn.commit()

    # =================================================================
    # CONTEXT RETRIEVAL FUNCTIONS
    # =================================================================

    def get_recent_events(self, hours: float = 24, event_type: Optional[str] = None) -> List[Dict]:
        """Get recent market events"""

        cutoff = get_utc_now() - timedelta(hours=hours)
        cursor = self.conn.cursor()

        if event_type:
            cursor.execute("""
                SELECT * FROM market_events
                WHERE timestamp >= ? AND event_type = ?
                ORDER BY timestamp DESC
            """, (cutoff, event_type))
        else:
            cursor.execute("""
                SELECT * FROM market_events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (cutoff,))

        events = []
        for row in cursor.fetchall():
            event = dict(row)
            event['context'] = json.loads(event['context_json'])
            events.append(event)

        return events

    def get_recent_decisions(self, hours: float = 24, should_trade_only: bool = False) -> List[Dict]:
        """Get recent trading decisions"""

        cutoff = get_utc_now() - timedelta(hours=hours)
        cursor = self.conn.cursor()

        if should_trade_only:
            cursor.execute("""
                SELECT * FROM trading_decisions
                WHERE timestamp >= ? AND should_trade = 1
                ORDER BY timestamp DESC
            """, (cutoff,))
        else:
            cursor.execute("""
                SELECT * FROM trading_decisions
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (cutoff,))

        decisions = []
        for row in cursor.fetchall():
            decision = dict(row)
            decision['blockers'] = json.loads(decision['blockers_json'])
            decision['warnings'] = json.loads(decision['warnings_json'])
            decisions.append(decision)

        return decisions

    def get_active_range_period(self) -> Optional[Dict]:
        """Get currently active range period (if any)"""

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM range_periods
            WHERE end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_current_regime(self) -> Optional[Dict]:
        """Get current market regime"""

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM market_regimes
            WHERE end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        if row:
            regime = dict(row)
            regime['characteristics'] = json.loads(regime['characteristics_json'])
            return regime
        return None

    def was_there_stop_hunt_recently(self, hours: float = 24) -> Tuple[bool, float]:
        """Check if there was stop hunt activity recently"""

        sweeps = self.get_recent_events(hours, 'sweep')

        if not sweeps:
            return False, 0.0

        # Count confirmed hunts
        confirmed = sum(1 for s in sweeps if s.get('context', {}).get('reversal_confirmed', False))
        severity = min(1.0, (len(sweeps) / 10) + (confirmed * 0.2))

        return len(sweeps) >= 3 or confirmed >= 2, severity

    def get_trap_history(self, days: int = 7) -> List[Dict]:
        """Get historical range trap periods"""

        cutoff = get_utc_now() - timedelta(days=days)
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM range_periods
            WHERE start_time >= ?
            ORDER BY start_time DESC
        """, (cutoff,))

        return [dict(row) for row in cursor.fetchall()]

    def get_market_context_summary(self, lookback_hours: float = 24) -> Dict:
        """
        Get comprehensive market context summary

        This is what the brain uses to understand "what" and "why"
        """

        cutoff = get_utc_now() - timedelta(hours=lookback_hours)

        # Get event counts by type
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT event_type, COUNT(*) as count, AVG(severity) as avg_severity
            FROM market_events
            WHERE timestamp >= ?
            GROUP BY event_type
        """, (cutoff,))

        event_summary = {row['event_type']: {
            'count': row['count'],
            'avg_severity': row['avg_severity']
        } for row in cursor.fetchall()}

        # Get decision statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total_decisions,
                SUM(CASE WHEN should_trade = 1 THEN 1 ELSE 0 END) as trade_decisions,
                SUM(CASE WHEN should_trade = 0 THEN 1 ELSE 0 END) as blocked_decisions,
                AVG(confidence) as avg_confidence
            FROM trading_decisions
            WHERE timestamp >= ?
        """, (cutoff,))

        decision_stats = dict(cursor.fetchone())

        # Active range?
        active_range = self.get_active_range_period()

        # Current regime?
        current_regime = self.get_current_regime()

        # Recent stop hunt activity?
        stop_hunt_active, stop_hunt_severity = self.was_there_stop_hunt_recently(lookback_hours)

        return {
            'lookback_hours': lookback_hours,
            'events_by_type': event_summary,
            'decision_stats': decision_stats,
            'active_range_period': active_range,
            'current_regime': current_regime,
            'stop_hunt_active': stop_hunt_active,
            'stop_hunt_severity': stop_hunt_severity,
            'context_summary': self._generate_context_narrative(
                event_summary,
                decision_stats,
                active_range,
                current_regime,
                stop_hunt_active
            )
        }

    def _generate_context_narrative(
        self,
        events: Dict,
        decisions: Dict,
        active_range: Optional[Dict],
        regime: Optional[Dict],
        stop_hunt: bool
    ) -> str:
        """Generate human-readable context narrative"""

        narrative = []

        # Regime
        if regime:
            duration = (get_utc_now() - datetime.fromisoformat(regime['start_time'])).total_seconds() / 3600
            narrative.append(f"Currently in {regime['regime_type']} regime for {duration:.1f} hours")

        # Active range trap
        if active_range:
            duration = (get_utc_now() - datetime.fromisoformat(active_range['start_time'])).total_seconds() / 3600
            narrative.append(f"TRAPPED in {active_range['range_size_pct']:.1f}% range for {duration:.1f} hours ({active_range['trap_severity']:.0%} severity)")

        # Stop hunt activity
        if stop_hunt:
            narrative.append("ACTIVE STOP HUNT MODE - Market hunting retail stops")

        # Event activity
        if 'sweep' in events:
            narrative.append(f"{events['sweep']['count']} liquidity sweeps detected (avg severity: {events['sweep']['avg_severity']:.0%})")

        if 'breakout' in events:
            narrative.append(f"{events['breakout']['count']} breakouts occurred")

        # Decision pattern
        if decisions['total_decisions'] > 0:
            block_rate = (decisions['blocked_decisions'] / decisions['total_decisions']) * 100
            narrative.append(f"{decisions['total_decisions']} decisions made, {block_rate:.0f}% blocked for safety")

        if not narrative:
            return "Normal market conditions - no significant patterns detected"

        return " | ".join(narrative)

    def get_memory_stats(self) -> Dict:
        """Get memory system statistics"""

        cursor = self.conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) as count FROM market_events")
        total_events = cursor.fetchone()['count']

        # Total decisions
        cursor.execute("SELECT COUNT(*) as count FROM trading_decisions")
        total_decisions = cursor.fetchone()['count']

        # Range periods
        cursor.execute("SELECT COUNT(*) as count FROM range_periods")
        range_periods = cursor.fetchone()['count']

        # Days of history
        cursor.execute("SELECT MIN(timestamp) as oldest FROM market_events")
        oldest = cursor.fetchone()['oldest']
        if oldest:
            days = (get_utc_now() - datetime.fromisoformat(oldest)).total_seconds() / 86400
        else:
            days = 0

        return {
            'total_events': total_events,
            'total_decisions': total_decisions,
            'range_periods': range_periods,
            'days_of_history': days
        }

    # =================================================================
    # LEARNING FUNCTIONS
    # =================================================================

    def learn_from_pattern_outcome(
        self,
        pattern_type: str,
        direction: str,
        price_at_pattern: float,
        outcome: str,
        price_move_pct: float,
        hours_to_resolution: float
    ):
        """Record pattern outcome for learning"""

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO pattern_outcomes (
                timestamp, pattern_type, direction, price_at_pattern,
                outcome, price_move_pct, time_to_resolution_hours
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            get_utc_now(),
            pattern_type,
            direction,
            price_at_pattern,
            outcome,
            price_move_pct,
            hours_to_resolution
        ))
        self.conn.commit()

    def get_pattern_success_rate(self, pattern_type: str, lookback_days: int = 30) -> Dict:
        """Get success rate for a specific pattern"""

        cutoff = get_utc_now() - timedelta(days=lookback_days)
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
                AVG(price_move_pct) as avg_move,
                AVG(time_to_resolution_hours) as avg_time
            FROM pattern_outcomes
            WHERE pattern_type = ? AND timestamp >= ?
        """, (pattern_type, cutoff))

        row = cursor.fetchone()
        if row['total'] == 0:
            return {'success_rate': 0.0, 'sample_size': 0}

        return {
            'success_rate': row['successes'] / row['total'],
            'sample_size': row['total'],
            'avg_move_pct': row['avg_move'],
            'avg_time_hours': row['avg_time']
        }

    def update_decision_outcome(self, decision_id: str, outcome: str, price_change: float):
        """Update a decision with its outcome"""

        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE trading_decisions
            SET outcome = ?, price_change_24h = ?
            WHERE decision_id = ?
        """, (outcome, price_change, decision_id))
        self.conn.commit()

    def close(self):
        """Close database connection"""
        self.conn.close()


def print_market_context(memory: MarketMemory, lookback_hours: float = 24):
    """Pretty print market context from memory"""

    print("\n" + "="*80)
    print("MARKET MEMORY - HISTORICAL CONTEXT")
    print("="*80)

    context = memory.get_market_context_summary(lookback_hours)

    print(f"\n[LOOKBACK PERIOD]")
    print(f"  {lookback_hours} hours of history analyzed")

    print(f"\n[CONTEXT NARRATIVE]")
    print(f"  {context['context_summary']}")

    print(f"\n[EVENT SUMMARY]")
    if context['events_by_type']:
        for event_type, stats in context['events_by_type'].items():
            print(f"  {event_type.upper()}: {stats['count']} events (avg severity: {stats['avg_severity']:.0%})")
    else:
        print(f"  No significant events")

    print(f"\n[DECISION HISTORY]")
    stats = context['decision_stats']
    if stats['total_decisions'] > 0:
        print(f"  Total Decisions: {stats['total_decisions']}")
        print(f"  Trade Signals: {stats['trade_decisions']}")
        print(f"  Blocked: {stats['blocked_decisions']}")
        print(f"  Avg Confidence: {stats['avg_confidence']:.0%}")
    else:
        print(f"  No decisions recorded yet")

    if context['active_range_period']:
        print(f"\n[ACTIVE RANGE TRAP]")
        rng = context['active_range_period']
        duration = (get_utc_now() - datetime.fromisoformat(rng['start_time'])).total_seconds() / 3600
        print(f"  TRAPPED for {duration:.1f} hours")
        print(f"  Range: ${rng['range_low']:.2f} - ${rng['range_high']:.2f} ({rng['range_size_pct']:.1f}%)")
        print(f"  Severity: {rng['trap_severity']:.0%}")
        print(f"  Sweeps in range: {rng['sweep_count']}")

    if context['current_regime']:
        print(f"\n[CURRENT REGIME]")
        regime = context['current_regime']
        duration = (get_utc_now() - datetime.fromisoformat(regime['start_time'])).total_seconds() / 3600
        print(f"  Type: {regime['regime_type']}")
        print(f"  Duration: {duration:.1f} hours")
        print(f"  Confidence: {regime['confidence']:.0%}")

    if context['stop_hunt_active']:
        print(f"\n[STOP HUNT WARNING]")
        print(f"  STATUS: ACTIVE")
        print(f"  Severity: {context['stop_hunt_severity']:.0%}")

    print("\n" + "="*80)


if __name__ == "__main__":
    print("Market Memory System - Testing")

    # Initialize memory
    memory = MarketMemory("test_memory.db")

    # Test recording event
    event = MarketEvent(
        timestamp=get_utc_now(),
        event_type='sweep',
        severity=0.75,
        price_level=219.50,
        direction='bullish',
        context={'reversal_confirmed': True, 'smart_money_intent': 'STOP_HUNT'}
    )
    memory.record_event(event)
    print("\nRecorded test event")

    # Test context retrieval
    print_market_context(memory, 24)

    memory.close()
    print("\nMemory system test complete")
