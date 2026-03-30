"""
Market Regime Engine: Core Definitions
======================================

Contains the enumerations and data classes that define the engine's language.

Author: Arsenal Trading System
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Dict

class MarketRegime(Enum):
    """Defines the possible, unambiguous states of the market."""
    CONSOLIDATING = auto()
    TRENDING_UP = auto()
    TRENDING_DOWN = auto()
    # In the future, we can add: BREAKOUT_UP, BREAKOUT_DOWN, REVERSAL

@dataclass
class RegimeMetrics:
    """Holds the calculated values of the objective metrics for a point in time."""
    # Market Structure Analysis
    structure_trend: str # 'uptrend', 'downtrend', 'neutral'
    structure_strength: float # 0.0 - 1.0
    
    # Volatility Character (ATR)
    atr_pct: float # ATR as a percentage of the close price
    atr_slope: float # The slope of the ATR over the last N bars
    
    # Moving Average Behavior
    price_vs_ema21: str # 'above', 'below', 'inside'
    ema21_vs_ema100: str # 'above', 'below', 'crossing'
    ema_separation_pct: float # The distance between the EMAs as a percentage
    ema_100_slope: float # The slope of the long-term EMA
    
    # ADX Trend Strength
    adx_value: float

    # Range Trap Analysis
    range_trap_active: bool
    range_trap_severity: float

@dataclass
class RegimeClassification:
    """Holds the final, decisive output of the MasterRegimeClassifier."""
    timestamp: any
    current_regime: MarketRegime
    regime_scores: Dict[MarketRegime, float] # The scores for each potential regime
    metrics: RegimeMetrics # The raw metrics used for the decision
    is_new_regime: bool # True if the regime changed on this candle
    message: str # A human-readable summary of the classification
