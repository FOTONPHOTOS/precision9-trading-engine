"""
Intelligent Strategy Brain WITH MEMORY - Enhanced Version

Same sophisticated AI reasoning, but now with:
- Persistent memory across restarts
- Historical context awareness
- Learning from past events
- Remembers "what" and "why" market does things
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import uuid

# Import base brain and memory system
from intelligent_strategy_brain import (
    IntelligentStrategyBrain,
    IntelligentDecision,
    MarketIntelligence
)
from market_memory import (
    MarketMemory,
    MarketEvent,
    TradingDecision,
    RangePeriod,
    MarketRegime,
    print_market_context
)


class IntelligentStrategyBrainWithMemory(IntelligentStrategyBrain):
    """
    Enhanced brain with persistent memory

    Remembers:
    - Previous market events
    - Past decisions and outcomes
    - Range trap periods
    - Stop hunt sequences
    - Market regime changes

    Uses this to make MORE intelligent decisions
    """

    def __init__(self, memory_db_path: str = "market_memory.db"):
        """Initialize brain with memory"""

        super().__init__()

        # Initialize memory system
        self.memory = MarketMemory(memory_db_path)

        # Active tracking
        self.current_range_period_id = None
        self.current_regime_id = None

        # Load historical context
        print("\n[BRAIN WITH MEMORY] Loading historical context...")
        self._load_historical_context()

    def _load_historical_context(self):
        """Load recent historical context on startup"""

        # Get context from last 24 hours
        context = self.memory.get_market_context_summary(24)

        print(f"\n[HISTORICAL CONTEXT - LAST 24 HOURS]")
        print(f"  {context['context_summary']}")

        # Check if we're still in an active range
        active_range = context['active_range_period']
        if active_range:
            duration_hours = (datetime.utcnow() - datetime.fromisoformat(active_range['start_time'])).total_seconds() / 3600
            print(f"\n[CONTINUING RANGE TRAP]")
            print(f"  Still trapped from {duration_hours:.1f} hours ago")
            print(f"  Range: {active_range['range_size_pct']:.1f}% ({active_range['trap_severity']:.0%} severity)")
            self.current_range_period_id = active_range['id']

        # Check current regime
        regime = context['current_regime']
        if regime:
            duration_hours = (datetime.utcnow() - datetime.fromisoformat(regime['start_time'])).total_seconds() / 3600
            print(f"\n[CONTINUING REGIME]")
            print(f"  {regime['regime_type']} for {duration_hours:.1f} hours")
            self.current_regime_id = regime['id']

        # Recent stop hunt activity
        if context['stop_hunt_active']:
            print(f"\n[RECENT STOP HUNT ACTIVITY]")
            print(f"  Severity: {context['stop_hunt_severity']:.0%}")
            print(f"  Caution: Market has been hunting stops recently")

    def analyze(self, market_intel: MarketIntelligence) -> IntelligentDecision:
        """
        Analyze market with MEMORY-ENHANCED reasoning

        Uses historical context to improve decisions
        """

        # STEP 1: Get base decision from parent class
        decision = super().analyze(market_intel)

        # STEP 2: Enhance with historical memory
        decision = self._enhance_with_memory(decision, market_intel)

        # STEP 3: Record this decision
        self._record_decision(decision, market_intel)

        # STEP 4: Record significant events
        self._record_market_events(market_intel)

        # STEP 5: Track regime changes
        self._track_regime_changes(market_intel)

        # STEP 6: Track range periods
        self._track_range_periods(market_intel)

        return decision

    def _enhance_with_memory(
        self,
        decision: IntelligentDecision,
        market_intel: MarketIntelligence
    ) -> IntelligentDecision:
        """Enhance decision with historical context"""

        # Get recent history
        recent_sweeps = self.memory.get_recent_events(6, 'sweep')
        recent_traps = self.memory.get_recent_events(24, 'trap')
        recent_decisions = self.memory.get_recent_decisions(24)

        # Memory-based adjustments
        reasoning_additions = []

        # 1. Pattern from recent stop hunts
        if len(recent_sweeps) >= 3:
            reasoning_additions.append(f"\n[MEMORY] {len(recent_sweeps)} sweeps in last 6h - elevated caution")
            # Reduce confidence slightly
            decision.confidence = max(0.20, decision.confidence - 0.05)
            decision.warnings.append(f"Memory: Recent stop hunt pattern detected")

        # 2. Persistent range trap
        if self.current_range_period_id:
            active_range = self.memory.get_active_range_period()
            if active_range:
                duration = (datetime.utcnow() - datetime.fromisoformat(active_range['start_time'])).total_seconds() / 3600
                reasoning_additions.append(f"\n[MEMORY] Trapped in range for {duration:.1f}h - extra caution")

                # If trapped for >12 hours, be very cautious
                if duration > 12:
                    decision.confidence = max(0.15, decision.confidence - 0.10)
                    decision.warnings.append(f"Memory: Extended range trap ({duration:.0f}h)")

        # 3. Recent blocked decisions
        blocked_count = sum(1 for d in recent_decisions if not d['should_trade'])
        if blocked_count >= 5:
            reasoning_additions.append(f"\n[MEMORY] {blocked_count} blocked decisions in 24h - difficult conditions")

        # 4. Check if similar setup happened before
        similar_context = self._find_similar_historical_context(market_intel)
        if similar_context:
            reasoning_additions.append(f"\n[MEMORY] Similar context detected: {similar_context['outcome']}")

            # Adjust based on historical outcome
            if similar_context['outcome'] == 'trap':
                decision.confidence = max(0.20, decision.confidence - 0.08)
                decision.warnings.append("Memory: Similar context led to trap before")
            elif similar_context['outcome'] == 'successful_breakout':
                decision.confidence = min(0.90, decision.confidence + 0.05)
                reasoning_additions.append(f"[MEMORY] Historical pattern suggests genuine breakout")

        # Add memory reasoning to chain
        if reasoning_additions:
            decision.reasoning_chain.extend([
                "\n[STEP 11] MEMORY-ENHANCED ADJUSTMENTS...",
                *reasoning_additions
            ])

        return decision

    def _find_similar_historical_context(self, market_intel: MarketIntelligence) -> Optional[Dict]:
        """Find similar historical market context"""

        # Get trap history
        trap_history = self.memory.get_trap_history(days=7)

        current_trap = market_intel.range_trap_analysis

        # Look for similar trap severity
        for past_trap in trap_history:
            if abs(past_trap['trap_severity'] - current_trap.trap_severity) < 0.15:
                # Similar trap - how did it resolve?
                return {
                    'severity': past_trap['trap_severity'],
                    'outcome': past_trap.get('resolution', 'unknown'),
                    'duration_hours': (
                        datetime.fromisoformat(past_trap['end_time']) -
                        datetime.fromisoformat(past_trap['start_time'])
                    ).total_seconds() / 3600 if past_trap.get('end_time') else 0
                }

        return None

    def _record_decision(self, decision: IntelligentDecision, market_intel: MarketIntelligence):
        """Record this decision to memory"""

        decision_id = f"dec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Extract reasoning summary (first 500 chars)
        reasoning_summary = "\n".join(decision.reasoning_chain[:10])

        trading_decision = TradingDecision(
            timestamp=datetime.utcnow(),
            decision_id=decision_id,
            direction=decision.direction,
            confidence=decision.confidence,
            signal_strength=decision.signal_strength,
            should_trade=decision.should_trade,
            blockers=decision.blockers,
            warnings=decision.warnings,
            reasoning=reasoning_summary,
            price_at_decision=market_intel.current_price
        )

        self.memory.record_decision(trading_decision)

    def _record_market_events(self, market_intel: MarketIntelligence):
        """Record significant market events"""

        # Record liquidity sweeps
        for sweep in market_intel.liquidity_sweeps:
            if hasattr(sweep, 'timestamp'):  # Recent sweep
                time_ago = (datetime.utcnow() - sweep.timestamp.to_pydatetime()).total_seconds()
                if time_ago < 300:  # Within last 5 minutes
                    event = MarketEvent(
                        timestamp=sweep.timestamp.to_pydatetime(),
                        event_type='sweep',
                        severity=0.8 if sweep.reversal_confirmed else 0.5,
                        price_level=sweep.swept_level,
                        direction=sweep.type,
                        context={
                            'reversal_confirmed': sweep.reversal_confirmed,
                            'smart_money_intent': sweep.smart_money_intent,
                            'danger_level': sweep.danger_level
                        }
                    )
                    self.memory.record_event(event)

        # Record range trap if severe
        trap = market_intel.range_trap_analysis
        if trap.is_trapped and trap.trap_severity > 0.70:
            event = MarketEvent(
                timestamp=datetime.utcnow(),
                event_type='trap',
                severity=trap.trap_severity,
                price_level=market_intel.current_price,
                direction='neutral',
                context={
                    'trap_reason': trap.trap_reason,
                    'danger_level': trap.danger_level,
                    'range_size_pct': trap.range_size_pct
                }
            )
            self.memory.record_event(event)

    def _track_regime_changes(self, market_intel: MarketIntelligence):
        """Track market regime changes"""

        current_regime = self.memory.get_current_regime()

        # Determine regime from market intel
        trap = market_intel.range_trap_analysis
        stop_hunt = market_intel.stop_hunt_warning
        trend = market_intel.trend_direction

        if stop_hunt.is_stop_hunt_mode:
            new_regime_type = 'stop_hunt'
        elif trap.is_trapped:
            new_regime_type = 'range'
        elif market_intel.trend_strength > 0.70:
            new_regime_type = f"{trend}_trend"
        else:
            new_regime_type = 'volatile'

        # Check if regime changed
        if not current_regime or current_regime['regime_type'] != new_regime_type:
            # End old regime
            if current_regime and not current_regime.get('end_time'):
                self.memory.end_regime(current_regime['id'], datetime.utcnow())

            # Start new regime
            new_regime = MarketRegime(
                start_time=datetime.utcnow(),
                end_time=None,
                regime_type=new_regime_type,
                confidence=market_intel.trend_strength if 'trend' in new_regime_type else trap.trap_severity,
                characteristics={
                    'trend_strength': market_intel.trend_strength,
                    'trap_severity': trap.trap_severity if trap.is_trapped else 0.0,
                    'stop_hunt_severity': stop_hunt.severity
                }
            )

            self.current_regime_id = self.memory.start_regime(new_regime)
            print(f"\n[REGIME CHANGE] Entered {new_regime_type} regime")

    def _track_range_periods(self, market_intel: MarketIntelligence):
        """Track range trap periods"""

        trap = market_intel.range_trap_analysis

        # If trapped and no active period, start one
        if trap.is_trapped and not self.current_range_period_id:
            # Find range bounds from swing highs/lows
            range_high = max([s['price'] for s in market_intel.swing_highs]) if market_intel.swing_highs else market_intel.current_price * 1.01
            range_low = min([s['price'] for s in market_intel.swing_lows]) if market_intel.swing_lows else market_intel.current_price * 0.99

            period = RangePeriod(
                start_time=datetime.utcnow(),
                end_time=None,
                range_high=range_high,
                range_low=range_low,
                range_size_pct=trap.range_size_pct,
                trap_severity=trap.trap_severity,
                sweep_count=len(market_intel.liquidity_sweeps),
                resolution=None
            )

            self.current_range_period_id = self.memory.start_range_period(period)
            print(f"\n[RANGE TRAP STARTED] ${range_low:.2f} - ${range_high:.2f} ({trap.range_size_pct:.1f}%)")

        # If not trapped but have active period, end it
        elif not trap.is_trapped and self.current_range_period_id:
            # Determine how it resolved
            recent_highs = [s['price'] for s in market_intel.swing_highs[-3:]] if len(market_intel.swing_highs) >= 3 else []
            recent_lows = [s['price'] for s in market_intel.swing_lows[-3:]] if len(market_intel.swing_lows) >= 3 else []

            if recent_highs and all(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs))):
                resolution = 'breakout_up'
            elif recent_lows and all(recent_lows[i] < recent_lows[i-1] for i in range(1, len(recent_lows))):
                resolution = 'breakout_down'
            else:
                resolution = 'dissolved'

            self.memory.end_range_period(self.current_range_period_id, datetime.utcnow(), resolution)
            print(f"\n[RANGE TRAP ENDED] Resolution: {resolution}")
            self.current_range_period_id = None

    def print_enhanced_decision(self, decision: IntelligentDecision):
        """Print decision with memory context"""

        # Print base decision
        from intelligent_strategy_brain import print_intelligent_decision
        print_intelligent_decision(decision)

        # Add memory context
        print("\n" + "="*80)
        print("MEMORY CONTEXT")
        print("="*80)

        # Show recent history
        context = self.memory.get_market_context_summary(24)
        print(f"\n{context['context_summary']}")

        # Recent decisions
        recent = self.memory.get_recent_decisions(6, should_trade_only=False)
        if recent:
            print(f"\n[RECENT DECISIONS - LAST 6 HOURS]")
            for dec in recent[:5]:
                time_ago = (datetime.utcnow() - datetime.fromisoformat(dec['timestamp'])).total_seconds() / 60
                status = "TRADED" if dec['should_trade'] else "BLOCKED"
                print(f"  {time_ago:.0f}m ago: {status} - {dec['direction']} ({dec['confidence']:.0%} confidence)")

        print("\n" + "="*80)

    def show_memory_summary(self):
        """Display comprehensive memory summary"""
        print_market_context(self.memory, lookback_hours=24)

    def close(self):
        """Close memory system"""
        print("\n[BRAIN WITH MEMORY] Saving state and closing...")
        self.memory.close()


if __name__ == "__main__":
    print("="*80)
    print("INTELLIGENT STRATEGY BRAIN WITH MEMORY")
    print("="*80)
    print("\nEnhanced brain with persistent memory capabilities")
    print("Remembers market context across restarts")
    print("Learns from historical patterns")
    print("\nModule ready for integration")
