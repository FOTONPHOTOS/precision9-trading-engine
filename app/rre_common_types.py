"""
RRE Common Types
================

This file defines common data structures used by both the Range Regime Engine (RRE)
and the consumers of its analysis, like the TrendContinuationBrain.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class RangeGeometry:
    """Describes the geometric properties of a detected range."""
    low: float
    high: float
    width_pct: float
    midline: float
    is_valid: bool = True

@dataclass
class RangeAnalysis:
    """The comprehensive output of the RRE, replacing the old RangeTrapAnalysis."""
    range_score: float
    range_state: str  # e.g., 'NOT_RANGE', 'ESTABLISHED_RANGE'
    geometry: Optional[RangeGeometry]
    boundary_quality: float
    persistence_seconds: float
    touch_count: int
    is_trapped: bool = False
    trap_reason: str = ""
    trap_severity: float = 0.0  # NEW: Severity of the trap (0.0 to 1.0)
    evidence: Dict[str, Any] = field(default_factory=dict)
