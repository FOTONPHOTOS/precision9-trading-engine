"""
Market Regime Engine: Mean-Reversion Brain
=============================================

A specialized sub-brain for trading consolidating/ranging markets.

Author: Arsenal Trading System
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from mean_reversion_engine import MeanReversionEngine, MeanReversionSignal
from trend_continuation_brain import MarketIntelligence, IntelligentDecision

class MeanReversionBrain:
    """
    A specialized brain that activates only in consolidating markets.
    Its goal is to fade the edges of the identified range, providing a full
    chain-of-thought analysis for its decisions.
    """

    def __init__(self, symbol: str = "SOLUSDT"):
        self.mean_reversion_engine = MeanReversionEngine(symbol)
        # The engine is activated by default, but we suppress the startup message
        # to avoid confusion before the first analysis cycle.
        self.mean_reversion_engine.activate("MeanReversionBrain activated by Master Classifier.", silent=True)

    def analyze(self, market_intel: MarketIntelligence) -> Optional[IntelligentDecision]:
        """
        Analyzes the market from a mean-reversion perspective and generates a full decision object.
        Now properly considers range trap severity to avoid trading in dangerous ranges.
        """
        reasoning_chain = ["=== MEAN-REVERSION BRAIN - CHAIN OF THOUGHT ==="]
        
        current_price = market_intel.current_price
        trap_analysis = market_intel.range_trap_analysis
        trap_severity = trap_analysis.trap_severity
        is_trapped = trap_analysis.is_trapped
        
        reasoning_chain.append(f"Regime: CONSOLIDATING (Trap Severity: {trap_severity:.0%})")
        
        # CRITICAL: Check if range trap indicates dangerous conditions before proceeding
        if is_trapped:
            reasoning_chain.append(f"[BLOCKED] Range trap active - {trap_analysis.danger_level} danger level.")
            reasoning_chain.append(f"  Reason: {trap_analysis.trap_reason}")
            reasoning_chain.append(f"  Recommendation: {trap_analysis.recommendation}")
            return IntelligentDecision(
                should_trade=False, direction='NEUTRAL', confidence=0, signal_strength='NONE',
                entry_zone=(0,0), stop_loss=0, take_profits=[], risk_reward=0,
                position_size_multiplier=0, max_risk_percent=0, reasoning_chain=reasoning_chain,
                blockers=[f"Range trap active ({trap_analysis.danger_level} danger): {trap_analysis.trap_reason}"], 
                warnings=[], opportunities=[], urgency='WAIT',
                analysis_quality=0.2, decision_timestamp=datetime.utcnow()
            )
        
        # Even if not fully trapped, high severity ranges are dangerous for mean reversion
        if trap_severity > 0.5:  # High severity (>50%)
            reasoning_chain.append(f"[BLOCKED] High range trap severity ({trap_severity:.0%}) - too dangerous for mean reversion.")
            reasoning_chain.append(f"  Recommendation: {trap_analysis.recommendation}")
            return IntelligentDecision(
                should_trade=False, direction='NEUTRAL', confidence=0, signal_strength='NONE',
                entry_zone=(0,0), stop_loss=0, take_profits=[], risk_reward=0,
                position_size_multiplier=0, max_risk_percent=0, reasoning_chain=reasoning_chain,
                blockers=[f"High range trap severity: {trap_severity:.0%}"], 
                warnings=[], opportunities=[], urgency='WAIT',
                analysis_quality=0.3, decision_timestamp=datetime.utcnow()
            )
        
        # For medium severity, reduce confidence but allow trading if good signal
        elif trap_severity > 0.3:  # Medium severity (>30%)
            reasoning_chain.append(f"[CAUTION] Medium range trap severity ({trap_severity:.0%}) - proceed with reduced size.")
            reasoning_chain.append(f"  Recommendation: {trap_analysis.recommendation}")
        
        reasoning_chain.append(f"Strategy: Fade price extremes back to the calculated mean (if safe).")

        market_mean = self.mean_reversion_engine.calculate_market_mean()
        if not market_mean:
            reasoning_chain.append("[BLOCKED] Could not calculate a stable market mean.")
            return IntelligentDecision(
                should_trade=False, direction='NEUTRAL', confidence=0, signal_strength='NONE',
                entry_zone=(0,0), stop_loss=0, take_profits=[], risk_reward=0,
                position_size_multiplier=0, max_risk_percent=0, reasoning_chain=reasoning_chain,
                blockers=["Could not calculate market mean."], warnings=[], opportunities=[], urgency='WAIT',
                analysis_quality=0.2, decision_timestamp=datetime.utcnow()
            )

        mr_signal, reason = self.mean_reversion_engine.generate_signal(
            current_price=current_price,
            market_mean=market_mean,
            chop_confidence=trap_severity  # Using trap_severity instead of just calling it chop_confidence
        )

        if not mr_signal:
            reasoning_chain.append(f"[NO TRADE] {reason}")
            return IntelligentDecision(
                should_trade=False, direction='NEUTRAL', confidence=0, signal_strength='NONE',
                entry_zone=(0,0), stop_loss=0, take_profits=[], risk_reward=0,
                position_size_multiplier=0, max_risk_percent=0, reasoning_chain=reasoning_chain,
                blockers=[reason], warnings=[], opportunities=[], urgency='WAIT',
                analysis_quality=0.5, decision_timestamp=datetime.utcnow()
            )

        # --- A valid signal was found, now build the full decision --- 
        reasoning_chain.append(f"[OPPORTUNITY] {reason}")
        reasoning_chain.append(f"  - Direction: {mr_signal.direction}")
        reasoning_chain.append(f"  - Z-Score: {mr_signal.z_score:.2f}")
        reasoning_chain.append(f"  - Deviation: {mr_signal.deviation_percent:.2%}")
        
        # Adjust position size based on trap severity even if we have a good signal
        base_position_size = 0.75
        if trap_severity > 0.3:  # Medium severity
            final_position_size = base_position_size * 0.5  # Reduce to 50% of normal
            reasoning_chain.append(f"  - Position size reduced to {final_position_size:.0%} due to medium trap severity")
        else:
            final_position_size = base_position_size

        # Build the final decision object
        decision = IntelligentDecision(
            should_trade=True,
            direction=mr_signal.direction,
            confidence=mr_signal.confidence,
            signal_strength='MEAN_REVERSION',
            entry_zone=(mr_signal.entry_price, mr_signal.entry_price),
            stop_loss=mr_signal.stop_loss,
            take_profits=[mr_signal.take_profit], # MR trades typically have one target: the mean
            risk_reward=mr_signal.risk_reward_ratio,
            position_size_multiplier=final_position_size,
            max_risk_percent=0.5,
            reasoning_chain=reasoning_chain,
            blockers=[],
            warnings=["Mean Reversion trade is inherently counter-trend."],
            opportunities=[f"Price is {mr_signal.deviation_percent:.2%} away from the mean."],
            urgency='IMMEDIATE',
            analysis_quality=0.8, # High quality if signal is generated
            decision_timestamp=datetime.utcnow()
        )
        
        return decision