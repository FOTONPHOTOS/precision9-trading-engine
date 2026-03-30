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
        self.contradiction_threshold = 0.8  # Higher threshold - more permissive (less blocking trades)
        self.warning_threshold = 0.6       # Higher threshold - more permissive
        
        # Symbol-specific contradiction thresholds based on analysis
        if self.symbol == 'BTCUSDT':
            # BTC: 35% win rate - more permissive contradiction detection
            self.contradiction_threshold = 0.85  # Very permissive to allow more trades
            self.warning_threshold = 0.65
        elif self.symbol == 'XRPUSDT':
            # XRP: 27.3% win rate - moderately permissive
            self.contradiction_threshold = 0.80
            self.warning_threshold = 0.60
        elif self.symbol == 'ETHUSDT':
            # ETH: 26.3% win rate - moderately permissive, low confluence works
            self.contradiction_threshold = 0.75  # Slightly less permissive due to low win rate
            self.warning_threshold = 0.55
        elif self.symbol == 'LINKUSDT':
            # LINK: 22.2% win rate - needs high trend strength, be more selective
            self.contradiction_threshold = 0.70  # More restrictive
            self.warning_threshold = 0.50
        elif self.symbol == 'SOLUSDT':
            # SOL: 20% win rate - very restrictive, but contradiction detection should be lenient
            # since SOL needs high confluence and high trend strength
            self.contradiction_threshold = 0.85  # Be more permissive about contradictions
            self.warning_threshold = 0.70       # But still cautious
        elif self.symbol == 'BNBUSDT':
            # BNB: 12.5% win rate - WORST performer, almost impossible to trade
            self.contradiction_threshold = 0.95  # Only block on extreme contradictions
            self.warning_threshold = 0.80       # Very high threshold
        
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
        if contradiction_score > self.contradiction_threshold:
            contradiction_analysis['recommendation'] = 'AVOID'
            contradiction_analysis['confidence_reduction'] = 0.5
        elif contradiction_score > self.warning_threshold:
            contradiction_analysis['recommendation'] = 'PROCEED_CAUTIOUSLY'
            contradiction_analysis['confidence_reduction'] = 0.25
        else:
            contradiction_analysis['recommendation'] = 'PROCEED'
            contradiction_analysis['confidence_reduction'] = 0.0
            
        return contradiction_analysis
    
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
        
        if ltf_trend == 'uptrend' and ltf_momentum < 0:
            detected = True
            description = f"Trend-Momentum Contradiction: Uptrend ({ltf_strength:.0%}) vs Negative momentum ({ltf_momentum:.2f})"
            weight = min(0.3, ltf_strength)  # Contradiction weight based on trend strength
        elif ltf_trend == 'downtrend' and ltf_momentum > 0:
            detected = True
            description = f"Trend-Momentum Contradiction: Downtrend ({ltf_strength:.0%}) vs Positive momentum ({ltf_momentum:.2f})"
            weight = min(0.3, ltf_strength)
            
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
        
        if ltf_trend == 'uptrend':
            # If trending up but taker ratio < 1, flow contradicts trend
            if taker_ratio < 0.8 and aggressive_sell_pressure > aggressive_buy_pressure * 1.2:
                detected = True
                description = f"Flow-Structure Contradiction: Uptrend but bearish order flow (taker_ratio: {taker_ratio:.2f})"
                weight = 0.25
        elif ltf_trend == 'downtrend':
            # If trending down but taker ratio > 1.2, flow contradicts trend
            if taker_ratio > 1.2 and aggressive_buy_pressure > aggressive_sell_pressure * 1.2:
                detected = True
                description = f"Flow-Structure Contradiction: Downtrend but bullish order flow (taker_ratio: {taker_ratio:.2f})"
                weight = 0.25
                
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
                weight = 0.2 * (total_bearish / (total_bullish + total_bearish))
                
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
                weight = 0.2 * (total_bullish / (total_bullish + total_bearish))
                
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
        
        if is_trapped and ltf_trend in ['uptrend', 'downtrend'] and trap_severity > 0.5:
            detected = True
            description = f"Range-Trend Contradiction: Trending signal in confirmed range trap (severity: {trap_severity:.0%})"
            weight = min(0.3, trap_severity)  # Weight by trap severity
            
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