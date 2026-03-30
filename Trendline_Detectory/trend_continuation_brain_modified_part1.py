"""
Intelligent Strategy Brain - Sophisticated AI-Like Reasoning

Combines ALL arsenal tools with chain-of-thought reasoning:
- Range Trap Detection
- Liquidity Sweeps
- Order Blocks
- FVGs
- Swing Structure
- Candle Patterns
- BOS/CHoCH
- Confluence Scoring

Goals:
1. Think like a sophisticated AI
2. Chain-of-thought reasoning
3. Avoid analysis paralysis
4. Balance safety with opportunity
5. Generate actionable signals

Decision Hierarchy:
- CRITICAL blockers (range trap, stop hunt mode) → NO TRADE
- HIGH warnings (multiple issues) → Reduce confidence 50%
- MEDIUM warnings (some issues) → Reduce confidence 25%
- LOW warnings (minor issues) → Reduce confidence 10%
- OPPORTUNITIES (confluences) → Boost confidence
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

# Import the new contradiction detector
from microstructure_contradiction_detector import MicrostructureContradictionDetector

# NEW: Import for symbol-specific configuration
from symbol_specific_config import SymbolSpecificConfig


@dataclass
class MarketIntelligence:
    """Complete market intelligence report"""

    # Price Action
    current_price: float
    trend_direction: str
    trend_strength: float

    # Structure
    swing_highs: List[Dict]
    swing_lows: List[Dict]
    candle_patterns: List[Dict]

    # Smart Money
    fvgs: List
    order_blocks: List
    liquidity_sweeps: List
    liquidity_pools: List

    # Risk Assessment
    range_trap_analysis: any
    stop_hunt_warning: any

    # Confluence
    confluence_score: int

    # Timestamp
    timestamp: datetime
    structural_integrity_score: Optional[float] = None
    structural_integrity_reasons: Optional[List[str]] = None
    htf_context: Optional[Dict] = None
    volume_profile_zones: Optional[Dict] = None


@dataclass
class IntelligentDecision:
    """Final intelligent decision with reasoning"""

    # Signal
    direction: str  # 'LONG', 'SHORT', 'NEUTRAL'
    confidence: float  # 0-1
    signal_strength: str  # 'WEAK', 'MODERATE', 'STRONG', 'VERY_STRONG'

    # Entry/Exit
    entry_zone: Tuple[float, float]
    stop_loss: float
    take_profits: List[float]
    risk_reward: float

    # Position Sizing
    position_size_multiplier: float  # 0.25-1.0
    max_risk_percent: float  # 0.5-2.0%

    # Reasoning (Chain of Thought)
    reasoning_chain: List[str]
    blockers: List[str]
    warnings: List[str]
    opportunities: List[str]

    # Verdict
    should_trade: bool
    urgency: str  # 'IMMEDIATE', 'SETUP_FORMING', 'WAIT', 'DO_NOT_TRADE'

    # Meta
    analysis_quality: float  # How good is this analysis?
    decision_timestamp: datetime
    market_intel: Optional[MarketIntelligence] = None # NEW

    # Structure Data (for Risk Manager)
    swing_highs: List[Dict] = field(default_factory=list)
    swing_lows: List[Dict] = field(default_factory=list)


class TrendContinuationBrain:
    """
    Sophisticated AI-like reasoning engine with dynamic symbol-specific adaptations

    Thinks through market conditions step-by-step,
    identifies opportunities vs risks,
    and makes intelligent decisions.
    """

    def __init__(self, symbol="SOLUSDT", ignore_stop_hunt: bool = False):
        self.symbol = symbol.upper()
        self.ignore_stop_hunt = ignore_stop_hunt
        
        # NEW: Add dynamic symbol-specific configuration
        self.symbol_config = SymbolSpecificConfig(self.symbol)
        
        # Use symbol-specific thresholds (dynamic based on known data or adaptive defaults)
        self.min_confidence_to_trade = self.symbol_config.get_threshold('min_confidence_to_trade')
        self.standard_confidence = self.symbol_config.get_threshold('strong_confidence')  # Renamed for clarity
        self.strong_confidence = self.symbol_config.get_threshold('strong_confidence')
        self.very_strong_confidence = self.symbol_config.get_threshold('very_strong_confidence')
        self.min_confluence_points = self.symbol_config.get_threshold('min_confluence_points')
        self.good_confluence = self.symbol_config.get_threshold('good_confluence')
        self.excellent_confluence = self.symbol_config.get_threshold('excellent_confluence')
        self.max_acceptable_trap_severity = self.symbol_config.get_threshold('max_acceptable_trap_severity')
        self.max_acceptable_stop_hunt_severity = self.symbol_config.get_threshold('max_acceptable_stop_hunt_severity')

        # NEW: Microstructure contradiction detector
        self.contradiction_detector = MicrostructureContradictionDetector()
