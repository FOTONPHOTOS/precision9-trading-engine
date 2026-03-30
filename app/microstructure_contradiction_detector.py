"""
MICROSTRUCTURE CONTRADICTION DETECTOR - SCALPING FOCUSED

Detects contradictions between different microstructure signals that
could lead to failed scalping attempts. This is the first line of
defense against low-probability trades that waste resources.

Focus: Identify when LTF signals conflict with order flow, liquidity,
or market microstructure before attempting scalps.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class MicrostructureContradictionDetector:
    """
    Advanced detector to identify contradictions between different
    microstructure signals that could undermine scalping attempts.
    """

    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol.upper()
        self._set_symbol_specific_thresholds()
        
    def _set_symbol_specific_thresholds(self):
        """Set contradiction thresholds based on symbol-specific analysis"""
        # Default values for symbols not in the known list
        # For scalping, be very permissive - only block on extreme contradictions
        self.contradiction_threshold = 0.95  # Very high threshold - extremely permissive
        self.warning_threshold = 0.85       # High threshold - very permissive
        
        # For scalping bots, even the "bad" performing symbols should get many opportunities
        # since scalping is about taking small profits frequently, not avoiding all risks
        if self.symbol == 'BTCUSDT':
            # BTC: 35% win rate - scalping should still get many opportunities
            self.contradiction_threshold = 0.95  # Be very permissive for scalping
            self.warning_threshold = 0.85
        elif self.symbol == 'XRPUSDT':
            # XRP: 27.3% win rate - allow many scalp opportunities
            self.contradiction_threshold = 0.93
            self.warning_threshold = 0.80
        elif self.symbol == 'ETHUSDT':
            # ETH: 26.3% win rate - allow many scalp opportunities
            self.contradiction_threshold = 0.93
            self.warning_threshold = 0.80
        elif self.symbol == 'LINKUSDT':
            # LINK: 22.2% win rate - allow many scalp opportunities
            self.contradiction_threshold = 0.92
            self.warning_threshold = 0.78
        elif self.symbol == 'SOLUSDT':
            # SOL: 20% win rate - allow many scalp opportunities despite poor performance
            self.contradiction_threshold = 0.92
            self.warning_threshold = 0.78
        elif self.symbol == 'BNBUSDT':
            # BNB: 12.5% win rate - even here, scalping bot should get opportunities
            self.contradiction_threshold = 0.90  # Even for worst performer, allow scalping
            self.warning_threshold = 0.75

    def detect_contradictions(self, market_data: Dict) -> Dict:
        """
        Detect contradictions in microstructure signals
        Returns a contradiction analysis with severity score
        """
        contradiction_analysis = {
            'severity_score': 0.0,
            'contradictions_found': [],
            'recommendation': 'PROCEED',
            'confidence_reduction': 0.0
        }

        # Check each contradiction type
        trend_momentum_contradiction = self._check_trend_momentum_contradiction(market_data)
        flow_structure_contradiction = self._check_flow_structure_contradiction(market_data)
        liquidity_trend_contradiction = self._check_liquidity_trend_contradiction(market_data)
        range_trend_contradiction = self._check_range_trend_contradiction(market_data)

        # Aggregate contradiction score
        total_contradictions = (
            trend_momentum_contradiction['weight'] +
            flow_structure_contradiction['weight'] +
            liquidity_trend_contradiction['weight'] +
            range_trend_contradiction['weight']
        )

        # Normalize to 0-1 scale
        contradiction_score = min(1.0, total_contradictions / 2.0)  # Max possible is 2.0

        contradiction_analysis['severity_score'] = contradiction_score

        # Add detected contradictions to the list
        if trend_momentum_contradiction['detected']:
            contradiction_analysis['contradictions_found'].append(trend_momentum_contradiction['description'])
        if flow_structure_contradiction['detected']:
            contradiction_analysis['contradictions_found'].append(flow_structure_contradiction['description'])
        if liquidity_trend_contradiction['detected']:
            contradiction_analysis['contradictions_found'].append(liquidity_trend_contradiction['description'])
        if range_trend_contradiction['detected']:
            contradiction_analysis['contradictions_found'].append(range_trend_contradiction['description'])

        # Determine recommendation based on severity
        # For scalping, keep confidence reduction minimal to allow more opportunities
        if contradiction_score > self.contradiction_threshold:
            contradiction_analysis['recommendation'] = 'AVOID'
            contradiction_analysis['confidence_reduction'] = 0.3  # Reduced from 0.5 for scalping
        elif contradiction_score > self.warning_threshold:
            contradiction_analysis['recommendation'] = 'PROCEED_CAUTIOUSLY'
            contradiction_analysis['confidence_reduction'] = 0.15  # Reduced from 0.25 for scalping
        else:
            contradiction_analysis['recommendation'] = 'PROCEED'
            contradiction_analysis['confidence_reduction'] = 0.0

        return contradiction_analysis

    def _get_symbol_contradiction_weight(self, contradiction_type: str) -> float:
        """
        Get symbol-specific contradiction weight based on symbol's characteristics
        For scalping, keep weights very low to allow more trades
        """
        if self.symbol == 'BTCUSDT':
            # BTC scalping - allow many opportunities even with contradictions
            if contradiction_type == 'trend_momentum':
                return 0.1  # Very low weight - don't block much
            elif contradiction_type == 'flow_structure':
                return 0.08
            elif contradiction_type == 'liquidity_trend':
                return 0.08
            elif contradiction_type == 'range_trend':
                return 0.15  # Even range-trend contradictions shouldn't block much
            else:
                return 0.08
                
        elif self.symbol == 'XRPUSDT':
            # XRP scalping - allow many opportunities
            if contradiction_type == 'trend_momentum':
                return 0.09
            elif contradiction_type == 'flow_structure':
                return 0.07
            elif contradiction_type == 'liquidity_trend':
                return 0.07
            elif contradiction_type == 'range_trend':
                return 0.13
            else:
                return 0.07
                
        elif self.symbol == 'ETHUSDT':
            # ETH scalping - allow many opportunities
            if contradiction_type == 'trend_momentum':
                return 0.09
            elif contradiction_type == 'flow_structure':
                return 0.07
            elif contradiction_type == 'liquidity_trend':
                return 0.07
            elif contradiction_type == 'range_trend':
                return 0.13
            else:
                return 0.07
                
        elif self.symbol == 'LINKUSDT':
            # LINK scalping - allow many opportunities
            if contradiction_type == 'trend_momentum':
                return 0.08
            elif contradiction_type == 'flow_structure':
                return 0.06
            elif contradiction_type == 'liquidity_trend':
                return 0.06
            elif contradiction_type == 'range_trend':
                return 0.12
            else:
                return 0.06
                
        elif self.symbol == 'SOLUSDT':
            # SOL scalping - allow many opportunities
            if contradiction_type == 'trend_momentum':
                return 0.08
            elif contradiction_type == 'flow_structure':
                return 0.06
            elif contradiction_type == 'liquidity_trend':
                return 0.06
            elif contradiction_type == 'range_trend':
                return 0.12
            else:
                return 0.06
                
        elif self.symbol == 'BNBUSDT':
            # BNB scalping - even allow some opportunities
            if contradiction_type == 'trend_momentum':
                return 0.07  # Still keep very low
            elif contradiction_type == 'flow_structure':
                return 0.05
            elif contradiction_type == 'liquidity_trend':
                return 0.05
            elif contradiction_type == 'range_trend':
                return 0.10
            else:
                return 0.05
        else:
            # Default for unknown symbols - scalping friendly
            if contradiction_type == 'trend_momentum':
                return 0.09
            elif contradiction_type == 'flow_structure':
                return 0.07
            elif contradiction_type == 'liquidity_trend':
                return 0.07
            elif contradiction_type == 'range_trend':
                return 0.13
            else:
                return 0.07

    def _check_trend_momentum_contradiction(self, market_data: Dict) -> Dict:
        """
        Check if LTF trend contradicts momentum signals
        """
        ltf_trend = market_data.get('ltf_trend', 'sideways')
        ltf_momentum = market_data.get('ltf_momentum', 0.0)
        ltf_strength = market_data.get('ltf_strength', 0.5)

        detected = False
        description = ""
        weight = 0.0

        # Get symbol-specific contradiction weights
        max_contradiction_weight = self._get_symbol_contradiction_weight('trend_momentum')
        
        if ltf_trend == 'uptrend' and ltf_momentum < 0:
            detected = True
            description = f"Trend-Momentum Contradiction: Uptrend ({ltf_strength:.0%}) vs Negative momentum ({ltf_momentum:.2f})"
            weight = min(max_contradiction_weight, ltf_strength)  # Contradiction weight based on trend strength
        elif ltf_trend == 'downtrend' and ltf_momentum > 0:
            detected = True
            description = f"Trend-Momentum Contradiction: Downtrend ({ltf_strength:.0%}) vs Positive momentum ({ltf_momentum:.2f})"
            weight = min(max_contradiction_weight, ltf_strength)

        return {
            'detected': detected,
            'description': description,
            'weight': weight
        }

    def _check_flow_structure_contradiction(self, market_data: Dict) -> Dict:
        """
        Check if order flow contradicts price structure
        """
        flow_data = market_data.get('trade_flow_analysis', {})
        ltf_trend = market_data.get('ltf_trend', 'sideways')

        taker_ratio = flow_data.get('taker_ratio', 1.0)
        aggressive_buy_pressure = flow_data.get('aggressive_buy_pressure', 0)
        aggressive_sell_pressure = flow_data.get('aggressive_sell_pressure', 0)

        detected = False
        description = ""
        weight = 0.0

        # Get symbol-specific contradiction weights
        max_contradiction_weight = self._get_symbol_contradiction_weight('flow_structure')

        if ltf_trend == 'uptrend':
            # If trending up but taker ratio < 1, flow contradicts trend
            if taker_ratio < 0.8 and aggressive_sell_pressure > aggressive_buy_pressure * 1.2:
                detected = True
                description = f"Flow-Structure Contradiction: Uptrend but bearish order flow (taker_ratio: {taker_ratio:.2f})"
                weight = min(max_contradiction_weight, 0.5)
        elif ltf_trend == 'downtrend':
            # If trending down but taker ratio > 1.2, flow contradicts trend
            if taker_ratio > 1.2 and aggressive_buy_pressure > aggressive_sell_pressure * 1.2:
                detected = True
                description = f"Flow-Structure Contradiction: Downtrend but bullish order flow (taker_ratio: {taker_ratio:.2f})"
                weight = min(max_contradiction_weight, 0.5)

        return {
            'detected': detected,
            'description': description,
            'weight': weight
        }

    def _check_liquidity_trend_contradiction(self, market_data: Dict) -> Dict:
        """
        Check if liquidity-based signals contradict trend
        """
        ltf_trend = market_data.get('ltf_trend', 'sideways')
        order_blocks = market_data.get('order_blocks', [])
        fvgs = market_data.get('fvgs', [])

        detected = False
        description = ""
        weight = 0.0

        # Get symbol-specific contradiction weights
        max_contradiction_weight = self._get_symbol_contradiction_weight('liquidity_trend')

        # Count liquidity signals in direction of trend vs opposite
        if ltf_trend == 'uptrend':
            bullish_liquidity = len([ob for ob in order_blocks if getattr(ob, 'type', None) == 'bullish'])
            bearish_liquidity = len([ob for ob in order_blocks if getattr(ob, 'type', None) == 'bearish'])
            bullish_fvgs = len([fvg for fvg in fvgs if getattr(fvg, 'gap_type', None) == 'bullish'])
            bearish_fvgs = len([fvg for fvg in fvgs if getattr(fvg, 'gap_type', None) == 'bearish'])

            total_bullish = bullish_liquidity + bullish_fvgs
            total_bearish = bearish_liquidity + bearish_fvgs

            if total_bearish > total_bullish and total_bearish > 0:
                detected = True
                description = f"Liquidity-Trend Contradiction: Uptrend vs {total_bearish} bearish liquidity signals vs {total_bullish} bullish"
                weight = min(max_contradiction_weight * (total_bearish / (total_bullish + total_bearish)), max_contradiction_weight)

        elif ltf_trend == 'downtrend':
            bullish_liquidity = len([ob for ob in order_blocks if getattr(ob, 'type', None) == 'bullish'])
            bearish_liquidity = len([ob for ob in order_blocks if getattr(ob, 'type', None) == 'bearish'])
            bullish_fvgs = len([fvg for fvg in fvgs if getattr(fvg, 'gap_type', None) == 'bullish'])
            bearish_fvgs = len([fvg for fvg in fvgs if getattr(fvg, 'gap_type', None) == 'bearish'])

            total_bullish = bullish_liquidity + bullish_fvgs
            total_bearish = bearish_liquidity + bearish_fvgs

            if total_bullish > total_bearish and total_bullish > 0:
                detected = True
                description = f"Liquidity-Trend Contradiction: Downtrend vs {total_bullish} bullish liquidity signals vs {total_bearish} bearish"
                weight = min(max_contradiction_weight * (total_bullish / (total_bullish + total_bearish)), max_contradiction_weight)

        return {
            'detected': detected,
            'description': description,
            'weight': weight
        }

    def _check_range_trend_contradiction(self, market_data: Dict) -> Dict:
        """
        Check if trend signal contradicts range state
        """
        ltf_trend = market_data.get('ltf_trend', 'sideways')
        range_trap_analysis = market_data.get('range_trap_analysis')

        is_trapped = getattr(range_trap_analysis, 'is_trapped', False) if range_trap_analysis else False
        trap_severity = getattr(range_trap_analysis, 'trap_severity', 0.0) if range_trap_analysis else 0.0

        detected = False
        description = ""
        weight = 0.0

        # Get symbol-specific contradiction weights
        max_contradiction_weight = self._get_symbol_contradiction_weight('range_trend')

        if is_trapped and ltf_trend in ['uptrend', 'downtrend'] and trap_severity > 0.5:
            detected = True
            description = f"Range-Trend Contradiction: Trending signal in confirmed range trap (severity: {trap_severity:.0%})"
            weight = min(max_contradiction_weight, trap_severity)  # Weight by trap severity

        return {
            'detected': detected,
            'description': description,
            'weight': weight
        }

    def should_avoid_scalping(self, contradiction_analysis: Dict) -> bool:
        """
        Determine if scalping should be avoided based on contradiction analysis
        """
        return contradiction_analysis['recommendation'] == 'AVOID'

    def get_confidence_multiplier(self, contradiction_analysis: Dict) -> float:
        """
        Get confidence multiplier based on contradiction severity
        """
        reduction = contradiction_analysis['confidence_reduction']
        return max(0.1, 1.0 - reduction)  # Never go below 10% confidence