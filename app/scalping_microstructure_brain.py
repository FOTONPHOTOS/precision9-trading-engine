"""
SCALPING MICROSTRUCTURE BRAIN - PROBABILISTIC MICRO-SCALPING INTELLIGENCE

Advanced architecture for microstructure-based scalping with:
- Real-time order flow analysis
- Limit order positioning (trap setting vs market chasing)
- Multi-timeframe hierarchy (LTF primary, HTF filter)
- Dynamic risk management based on microstructure

Goals:
1. Capture microstructure alpha before decay
2. Use limit orders to get better fills than market orders
3. Maintain 50%+ win rate with 2:1+ R:R
4. Max 1-hour trade duration (scalping focus)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import logging
from scipy import stats

logger = logging.getLogger(__name__)

@dataclass
class MicrostructureIntelligence:
    """Complete microstructure market intelligence report"""
    
    # Current State
    current_price: float
    timestamp: datetime
    ltf_trend: str  # 'uptrend', 'downtrend', 'sideways'
    ltf_strength: float  # 0.0 to 1.0
    ltf_momentum: float  # -1.0 to 1.0 (negative = bearish)
    
    # Microstructure Data
    order_book_snapshot: Optional[Dict] = None  # Bid/ask sizes, depth
    recent_trades: Optional[List[Dict]] = None  # Last 100 trades
    trade_flow_analysis: Optional[Dict] = None   # Buy/sell pressure
    
    # Swing Structure
    recent_swing_highs: List[Dict] = field(default_factory=list)
    recent_swing_lows: List[Dict] = field(default_factory=list)
    
    # Micro-Scalping Zones
    order_blocks: List[Dict] = field(default_factory=list)
    fvgs: List[Dict] = field(default_factory=list)
    liquidity_pools: List[Dict] = field(default_factory=list)
    
    # Momentum Patterns
    momentum_patterns: List[Dict] = field(default_factory=list)
    
    # HTF Context (Filter Only)
    htf_trend: Optional[str] = None
    htf_strength: Optional[float] = None
    range_state: Optional[str] = None  # 'range', 'breakout', 'trending'

@dataclass
class ScalpingSignal:
    """Microstructure-based scalping signal with limit order placement"""
    
    direction: str  # 'LONG', 'SHORT'
    entry_zone: Tuple[float, float]  # Limit order placement zone
    stop_loss: float  # Safety stop (market order if limit fails)
    take_profit: float  # Primary target
    confidence: float  # 0.0 to 1.0
    expected_duration: float  # Expected time in minutes
    risk_reward: float  # Expected R:R ratio
    microstructure_reasons: List[str]  # Specific micro factors
    market_regime: str  # 'trending', 'ranging', 'volatile'
    
    # For order execution
    limit_order_price: float  # Where to place the trap
    order_size_multiplier: float  # Dynamic sizing based on confidence

class ScalpingMicrostructureBrain:
    """
    Advanced probabilistic scalping intelligence system
    Focuses on microstructure patterns and limit order positioning
    """
    
    def __init__(self):
        self.min_confidence_to_trade = 0.20  # Lowered threshold for better opportunity capture (from 0.35 to 0.20 to match old system)
        self.min_rr_ratio = 1.0  # Lowered minimum R:R to 1.0 to give system breathing room (like Arsenal)
        self.max_duration_minutes = 60  # 1-hour max for scalping
        
        # Scalping-specific thresholds
        self.min_momentum_strength = 0.05  # Lowered minimum momentum for entry (more opportunities)
        self.max_contradiction_score = 0.6  # Increased maximum contradiction allowed (more opportunities)
        
        # Microstructure sensitivity parameters
        self.order_flow_threshold = 1.5  # Minimum order flow imbalance
        self.liquidity_threshold = 0.7  # Minimum liquidity confirmation
        self.momentum_confirmation = 1   # Lowered minimum confirming patterns needed

    def analyze_microstructure(self, market_data: Dict) -> Optional[ScalpingSignal]:
        """
        Complete microstructure analysis for scalping opportunities
        Uses limit order positioning strategy
        """
        try:
            # Create microstructure intelligence
            micro_intel = self._build_microstructure_intelligence(market_data)
            
            # Perform probabilistic analysis
            signal = self._probabilistic_scalping_analysis(micro_intel)
            
            if not signal:
                return None
                
            # Apply market regime filter
            if not self._validate_regime_alignment(signal, micro_intel):
                logger.debug(f"Signal rejected: Wrong market regime for {signal.direction}")
                return None
            
            # Calculate position sizing based on microstructure confidence
            signal.order_size_multiplier = self._calculate_microstructure_position_size(signal.confidence)
            
            return signal
            
        except Exception as e:
            logger.error(f"Microstructure analysis failed: {e}", exc_info=True)
            return None

    def _build_microstructure_intelligence(self, market_data: Dict) -> MicrostructureIntelligence:
        """Builds complete microstructure picture from all available data"""
        
        # Current market state
        current_price = float(market_data.get('current_price', market_data.get('close', market_data.get('price', 0))))
        timestamp = datetime.utcnow()
        
        # Extract technical data
        ltf_trend = market_data.get('ltf_trend', 'sideways')
        ltf_strength = market_data.get('ltf_strength', 0.5)
        ltf_momentum = market_data.get('ltf_momentum', 0.0)
        
        # Technical structure
        swing_highs = market_data.get('swing_highs', [])
        swing_lows = market_data.get('swing_lows', [])
        
        # Micro-scalping zones
        order_blocks = market_data.get('order_blocks', [])
        fvgs = market_data.get('fvgs', [])
        liquidity_pools = market_data.get('liquidity_pools', [])
        momentum_patterns = market_data.get('momentum_patterns', [])
        
        # HTF context (for filtering, not entry)
        htf_context = market_data.get('htf_context', {})
        htf_trend = htf_context.get('trend_direction')
        htf_strength = htf_context.get('trend_strength')
        
        # Range state
        range_trap = market_data.get('range_trap_analysis')
        range_state = 'range' if range_trap and getattr(range_trap, 'is_trapped', False) else 'trending'
        
        # Order flow analysis (from recent trades)
        recent_trades = market_data.get('recent_trades', [])
        trade_flow_analysis = self._analyze_trade_flow(recent_trades, current_price)
        
        return MicrostructureIntelligence(
            current_price=current_price,
            timestamp=timestamp,
            order_book_snapshot=market_data.get('orderbook'),
            recent_trades=recent_trades,
            trade_flow_analysis=trade_flow_analysis,
            ltf_trend=ltf_trend,
            ltf_strength=ltf_strength,
            ltf_momentum=ltf_momentum,
            recent_swing_highs=swing_highs,
            recent_swing_lows=swing_lows,
            order_blocks=order_blocks,
            fvgs=fvgs,
            liquidity_pools=liquidity_pools,
            momentum_patterns=momentum_patterns,
            htf_trend=htf_trend,
            htf_strength=htf_strength,
            range_state=range_state
        )

    def _analyze_trade_flow(self, recent_trades: List[Dict], current_price: float) -> Dict:
        """Analyzes recent trade flow for microstructure insights"""
        if not recent_trades:
            return {'buy_vol': 0, 'sell_vol': 0, 'imbalance_ratio': 1.0, 'taker_ratio': 1.0}
        
        # Calculate buy/sell volume in last 100 trades
        buy_volume = sum(float(trade['size']) for trade in recent_trades if trade['side'] == 'Buy')
        sell_volume = sum(float(trade['size']) for trade in recent_trades if trade['side'] == 'Sell')
        
        # Calculate taker ratio (aggressive vs passive)  
        aggressive_buys = sum(float(trade['size']) for trade in recent_trades 
                            if trade['side'] == 'Buy' and float(trade['price']) >= current_price)
        aggressive_sells = sum(float(trade['size']) for trade in recent_trades 
                             if trade['side'] == 'Sell' and float(trade['price']) <= current_price)
        
        total_aggressive = aggressive_buys + aggressive_sells
        taker_ratio = aggressive_buys / aggressive_sells if aggressive_sells > 0 else 999 if aggressive_buys > 0 else 1.0
        taker_percentage = (total_aggressive / (buy_volume + sell_volume + 0.0001)) if (buy_volume + sell_volume) > 0 else 0.0
        
        imbalance_ratio = buy_volume / sell_volume if sell_volume > 0 else 999 if buy_volume > 0 else 1.0
        
        return {
            'buy_vol': buy_volume,
            'sell_vol': sell_volume,
            'imbalance_ratio': imbalance_ratio,
            'taker_ratio': taker_ratio,
            'taker_percentage': taker_percentage,
            'aggressive_buy_pressure': aggressive_buys,
            'aggressive_sell_pressure': aggressive_sells
        }

    def _probabilistic_scalping_analysis(self, micro_intel: MicrostructureIntelligence) -> Optional[ScalpingSignal]:
        """Probabilistic analysis for microstructure-based scalping"""
        logger.debug("Starting probabilistic scalping analysis...")
        
        # Calculate microstructure probability scores
        trend_alignment_score = self._calculate_trend_alignment_score(micro_intel)
        logger.debug(f"Trend alignment score: {trend_alignment_score:.2f}")
        
        momentum_confirmation_score = self._calculate_momentum_confirmation_score(micro_intel)
        logger.debug(f"Momentum confirmation score: {momentum_confirmation_score:.2f}")
        
        liquidity_confirmation_score = self._calculate_liquidity_confirmation_score(micro_intel)
        logger.debug(f"Liquidity confirmation score: {liquidity_confirmation_score:.2f}")
        
        order_flow_score = self._calculate_order_flow_score(micro_intel)
        logger.debug(f"Order flow score: {order_flow_score:.2f}")
        
        contradiction_score = self._calculate_contradiction_score(micro_intel)
        logger.debug(f"Contradiction score: {contradiction_score:.2f}")
        
        # Combine all scores for overall confidence
        combined_confidence = self._combine_microstructure_scores(
            trend_alignment_score,
            momentum_confirmation_score,
            liquidity_confirmation_score, 
            order_flow_score,
            contradiction_score
        )
        
        logger.debug(f"Combined confidence: {combined_confidence:.2f}, min threshold: {self.min_confidence_to_trade}")
        
        if combined_confidence < self.min_confidence_to_trade:
            logger.info(f" REJECTED: Low confidence ({combined_confidence:.2f} < {self.min_confidence_to_trade})")
            return None
        
        # Determine direction based on microstructure dominance
        direction = self._determine_scalping_direction(micro_intel)
        if not direction:
            logger.info(" REJECTED: Could not determine scalping direction")
            return None
        
        logger.debug(f"Determined direction: {direction}")
        
        # Calculate limit order placement and targets
        signal = self._calculate_limit_order_signal(direction, micro_intel, combined_confidence)
        if not signal:
            logger.info(" REJECTED: Could not calculate limit order signal")
            return None
            
        # Update confidence with microstructure-adjusted values
        signal.confidence = combined_confidence
        logger.info(f" SIGNAL ACCEPTED: {direction} with confidence {combined_confidence:.2f}, R:R {signal.risk_reward:.2f}")
        
        return signal

    def _calculate_trend_alignment_score(self, micro_intel: MicrostructureIntelligence) -> float:
        """Score based on LTF trend alignment with microstructure"""
        if micro_intel.ltf_trend == 'uptrend' and micro_intel.ltf_momentum > 0:
            return min(1.0, micro_intel.ltf_strength + 0.1)
        elif micro_intel.ltf_trend == 'downtrend' and micro_intel.ltf_momentum < 0:
            return min(1.0, micro_intel.ltf_strength + 0.1)
        else:
            # Trend/momentum conflict - reduce score
            return max(0.1, micro_intel.ltf_strength - 0.3)

    def _calculate_momentum_confirmation_score(self, micro_intel: MicrostructureIntelligence) -> float:
        """Score based on momentum pattern confirmation"""
        bullish_patterns = len([p for p in micro_intel.momentum_patterns if p.get('type', '').startswith('BULLISH')])
        bearish_patterns = len([p for p in micro_intel.momentum_patterns if p.get('type', '').startswith('BEARISH')])
        
        if micro_intel.ltf_trend == 'uptrend':
            confirming_patterns = bullish_patterns
            total_patterns = bullish_patterns + bearish_patterns
        else:  # downtrend
            confirming_patterns = bearish_patterns
            total_patterns = bullish_patterns + bearish_patterns
            
        if total_patterns == 0:
            return 0.3  # Moderate score when no patterns
            
        # Enhanced scoring that rewards large number of confirming patterns
        confirmation_ratio = confirming_patterns / total_patterns if total_patterns > 0 else 0.3
        # Give extra weight to having many confirming patterns, especially if they dominate
        pattern_strength = min(1.0, (confirming_patterns / 10.0))  # Scale by 10 for normalization
        trend_alignment_bonus = 0.3 if confirmation_ratio > 0.6 else 0.0  # Bonus for majority alignment
        
        base_score = 0.3 + (confirmation_ratio * 0.4) + pattern_strength * 0.3 + trend_alignment_bonus
        return min(1.0, base_score)

    def _calculate_liquidity_confirmation_score(self, micro_intel: MicrostructureIntelligence) -> float:
        """Score based on liquidity pool confirmation"""
        if micro_intel.range_state == 'range':
            # In ranging markets, avoid directional trades
            return 0.1
            
        # Look for liquidity-based opportunities
        confirming_liquidity_factors = 0
        
        # Active order blocks in trend direction
        if micro_intel.ltf_trend == 'uptrend':
            bullish_obs = [ob for ob in micro_intel.order_blocks if getattr(ob, 'type', None) == 'bullish']
            if bullish_obs:
                confirming_liquidity_factors += 1
        else:  # downtrend
            bearish_obs = [ob for ob in micro_intel.order_blocks if getattr(ob, 'type', None) == 'bearish']
            if bearish_obs:
                confirming_liquidity_factors += 1
                
        # Unfilled FVGs in trend direction
        if micro_intel.ltf_trend == 'uptrend':
            bullish_fvgs = [fvg for fvg in micro_intel.fvgs if getattr(fvg, 'gap_type', None) == 'bullish']
            if bullish_fvgs:
                confirming_liquidity_factors += 1
        else:
            bearish_fvgs = [fvg for fvg in micro_intel.fvgs if getattr(fvg, 'gap_type', None) == 'bearish']
            if bearish_fvgs:
                confirming_liquidity_factors += 1
        
        # If no liquidity factors but other signals are strong, still allow trade
        # Base score is higher to account for markets with sparse liquidity signals
        base_score = 0.3 if confirming_liquidity_factors > 0 else 0.15  # Higher base to allow more trades
        return min(1.0, base_score + (confirming_liquidity_factors * 0.15))  # Adjusted to balance flexibility

    def _calculate_order_flow_score(self, micro_intel: MicrostructureIntelligence) -> float:
        """Score based on order flow analysis"""
        flow_data = micro_intel.trade_flow_analysis or {}
        
        imbalance = flow_data.get('imbalance_ratio', 1.0)
        taker_ratio = flow_data.get('taker_ratio', 1.0)
        taker_percentage = flow_data.get('taker_percentage', 0.0)
        
        # Normalize based on trend direction
        if micro_intel.ltf_trend == 'uptrend':
            flow_alignment = imbalance if imbalance > 1 else (1/imbalance if imbalance != 0 else 1.0)
        else:  # downtrend
            flow_alignment = (1/imbalance if imbalance != 0 else 1.0) if imbalance > 1 else imbalance
            
        # Higher scores for aligned aggressive flow
        if (micro_intel.ltf_trend == 'uptrend' and taker_ratio > 1) or (micro_intel.ltf_trend == 'downtrend' and taker_ratio < 1):
            aggressive_alignment = min(2.0, taker_ratio if micro_intel.ltf_trend == 'uptrend' else (1/taker_ratio))  # Allow higher values
        else:
            aggressive_alignment = min(2.0, 1/taker_ratio if micro_intel.ltf_trend == 'uptrend' else taker_ratio)  # Inverse if misaligned
        
        # Combine factors with adjusted weights to be more responsive
        # Give more weight to alignment and less to taker percentage to avoid overpenalization
        flow_score = min(1.0, (flow_alignment * 0.3) + (aggressive_alignment * 0.5) + (taker_percentage * 0.2))
        return flow_score

    def _calculate_contradiction_score(self, micro_intel: MicrostructureIntelligence) -> float:
        """Calculate contradiction score (lower is better)"""
        contradictions = 0
        
        # HTF-LTF conflict
        if micro_intel.htf_trend and micro_intel.htf_trend.replace('trend', '') != micro_intel.ltf_trend.replace('trend', ''):
            contradictions += 0.5  # Reduced impact - LTF dominates for scalping
            
        # Range state conflict
        if micro_intel.range_state == 'range' and micro_intel.ltf_trend in ['uptrend', 'downtrend']:
            contradictions += 0.5  # Reduced impact - allow some flexibility
            
        # Momentum-structure conflict
        if ((micro_intel.ltf_trend == 'uptrend' and micro_intel.ltf_momentum < 0) or 
            (micro_intel.ltf_trend == 'downtrend' and micro_intel.ltf_momentum > 0)):
            contradictions += 0.5  # Reduced impact - momentum can be temporary
            
        return min(0.8, contradictions)  # Max 0.8 (high contradiction) but more forgiving

    def _combine_microstructure_scores(self, trend_score: float, momentum_score: float, 
                                     liquidity_score: float, flow_score: float, 
                                     contradiction_score: float) -> float:
        """Combine all microstructure scores with contradiction adjustment"""
        
        # Base score from positive factors
        positive_score = (trend_score * 0.25 + 
                         momentum_score * 0.25 + 
                         liquidity_score * 0.25 + 
                         flow_score * 0.25)
        
        # Adjust for contradictions (reduce confidence)
        adjusted_score = positive_score * (1 - contradiction_score)
        
        return max(0.0, min(1.0, adjusted_score))

    def _determine_scalping_direction(self, micro_intel: MicrostructureIntelligence) -> Optional[str]:
        """Determine scalping direction based on microstructure dominance"""
        
        # Check if we're in a range (avoid directional trades)
        if micro_intel.range_state == 'range':
            logger.debug("Market in range - avoiding directional scalping")
            return None
            
        logger.debug(f"Checking direction for trend: {micro_intel.ltf_trend}, momentum: {micro_intel.ltf_momentum}")
        
        # Use trend direction as primary but confirm with microstructure
        if micro_intel.ltf_trend == 'uptrend':
            # Confirm with bullish microstructure factors
            flow_data = micro_intel.trade_flow_analysis or {}
            taker_ratio = flow_data.get('taker_ratio', 1.0)
            
            logger.debug(f"Uptrend check: momentum={micro_intel.ltf_momentum}, taker_ratio={taker_ratio}")
            
            if micro_intel.ltf_momentum > 0 and taker_ratio > 1.0:
                logger.debug(" LONG direction confirmed: positive momentum and bullish flow")
                return 'LONG'
            elif micro_intel.ltf_momentum > 0 and micro_intel.ltf_strength > 0.7:
                # If trend is very strong, allow trade with just momentum confirmation
                logger.debug(f" LONG direction accepted: strong trend ({micro_intel.ltf_strength}) and positive momentum")
                return 'LONG'
            elif taker_ratio > 1.2 and micro_intel.ltf_strength > 0.6:
                # If flow is clearly bullish and trend is strong, allow trade
                logger.debug(f" LONG direction accepted: bullish flow (taker_ratio={taker_ratio}) and strong trend")
                return 'LONG'
            elif micro_intel.ltf_strength > 0.8:
                # Very strong trend can override momentum/flow mismatch sometimes
                logger.debug(f" LONG direction accepted: very strong trend ({micro_intel.ltf_strength})")
                return 'LONG'
                
        elif micro_intel.ltf_trend == 'downtrend':
            # Confirm with bearish microstructure factors
            flow_data = micro_intel.trade_flow_analysis or {}
            taker_ratio = flow_data.get('taker_ratio', 1.0)
            
            logger.debug(f"Downtrend check: momentum={micro_intel.ltf_momentum}, taker_ratio={taker_ratio}")
            
            if micro_intel.ltf_momentum < 0 and taker_ratio < 1.0:
                logger.debug(" SHORT direction confirmed: negative momentum and bearish flow")
                return 'SHORT'
            elif micro_intel.ltf_momentum < 0 and micro_intel.ltf_strength > 0.7:
                # If trend is very strong, allow trade with just momentum confirmation
                logger.debug(f" SHORT direction accepted: strong trend ({micro_intel.ltf_strength}) and negative momentum")
                return 'SHORT'
            elif taker_ratio < 0.8 and micro_intel.ltf_strength > 0.6:
                # If flow is clearly bearish and trend is strong, allow trade
                logger.debug(f" SHORT direction accepted: bearish flow (taker_ratio={taker_ratio}) and strong trend")
                return 'SHORT'
            elif micro_intel.ltf_strength > 0.8:
                # Very strong trend can override momentum/flow mismatch sometimes
                logger.debug(f" SHORT direction accepted: very strong trend ({micro_intel.ltf_strength})")
                return 'SHORT'
                
        logger.debug(" Could not determine clear directional signal")
        return None

    def _calculate_limit_order_signal(self, direction: str, micro_intel: MicrostructureIntelligence, 
                                    confidence: float) -> Optional[ScalpingSignal]:
        """Calculate limit order placement and targets for scalping"""
        
        current_price = micro_intel.current_price
        logger.debug(f"Calculating limit order signal for {direction} at current price: {current_price}")
        
        # FIRST: Check if market is near relevant microstructure levels before proceeding
        # This ensures we only generate signals when market is already at opportunity zones
        proximity_ok = self._check_market_proximity_to_levels(direction, micro_intel)
        if not proximity_ok:
            logger.info(f" REJECTED: Market not near relevant {direction} levels, signal not generated")
            return None
        
        # Calculate where to place limit order (the trap)
        limit_price = self._calculate_limit_order_placement(direction, micro_intel)
        if not limit_price:
            logger.info(f" REJECTED: Could not calculate limit order placement for {direction}")
            return None
        logger.debug(f"Limit price set at: {limit_price}")
            
        # Calculate stop loss (safety) - must be away from entry for scalping
        stop_loss = self._calculate_scalping_stop_loss(direction, limit_price, micro_intel)
        if not stop_loss:
            logger.info(f" REJECTED: Could not calculate stop loss for {direction} at limit {limit_price}")
            return None
        logger.debug(f"Stop loss set at: {stop_loss}")
            
        # Calculate take profit target
        take_profit = self._calculate_scalping_take_profit(direction, limit_price, micro_intel)
        if not take_profit:
            logger.info(f" REJECTED: Could not calculate take profit for {direction} at limit {limit_price}")
            return None
        logger.debug(f"Take profit set at: {take_profit}")
            
        # Calculate expected R:R ratio
        entry = limit_price
        # For LONG positions: reward is (take_profit - entry), risk is (entry - stop_loss)  
        # For SHORT positions: reward is (entry - take_profit), risk is (stop_loss - entry)
        if direction == 'LONG':
            risk = abs(entry - stop_loss)  # entry - stop_loss (stop is below entry for long)
            reward = abs(take_profit - entry)  # take_profit - entry (take_profit is above entry for long)
        else:  # SHORT
            risk = abs(stop_loss - entry)  # stop_loss - entry (stop is above entry for short)
            reward = abs(entry - take_profit)  # entry - take_profit (take_profit is below entry for short)
        rr_ratio = reward / risk if risk > 0 else 0
        
        logger.debug(f"R:R calculation - Entry: {entry}, SL: {stop_loss}, TP: {take_profit}, Risk: {risk}, Reward: {reward}, RR: {rr_ratio:.2f}")
        
        if rr_ratio < self.min_rr_ratio:
            logger.info(f" REJECTED: Insufficient R:R ratio: {rr_ratio:.2f}, required: {self.min_rr_ratio}")
            return None
            
        # Calculate expected duration based on market volatility
        expected_duration = self._estimate_scalping_duration(micro_intel)
        
        # Gather reasons for the trade decision
        reasons = self._compile_microstructure_reasons(micro_intel)
        
        # Determine market regime
        regime = self._determine_market_regime(micro_intel)
        
        logger.debug(f" Signal created: {direction} Entry:{entry:.4f}, SL:{stop_loss:.4f}, TP:{take_profit:.4f}, RR:{rr_ratio:.2f}, Conf:{confidence:.2f}")
        
        return ScalpingSignal(
            direction=direction,
            entry_zone=(limit_price, limit_price),  # Single price for limit order
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            expected_duration=expected_duration,
            risk_reward=rr_ratio,
            microstructure_reasons=reasons,
            market_regime=regime,
            limit_order_price=limit_price,  # This is where the trap is set
            order_size_multiplier=1.0  # Will be adjusted later
        )

    def _calculate_limit_order_placement(self, direction: str, micro_intel: MicrostructureIntelligence) -> Optional[float]:
        """Strategically place limit order based on microstructure"""
        
        current_price = micro_intel.current_price
        
        if direction == 'LONG':
            # Look for support levels to place buy limit
            support_levels = []
            
            # Swing lows
            for swing in micro_intel.recent_swing_lows[-3:]:  # Last 3 swing lows
                price = getattr(swing, 'price', swing.get('price', current_price) if isinstance(swing, dict) else current_price)
                # Only consider supports that are reasonably close to current price (within 1% for scalping)
                if price < current_price and (current_price - price) / current_price <= 0.01:
                    support_levels.append(price)
                
            # Bullish order blocks
            for ob in micro_intel.order_blocks:
                price = getattr(ob, 'entry_zone_low', ob.get('entry_zone_low', current_price) if isinstance(ob, dict) else current_price)
                # Only consider if reasonably close to current price
                if price < current_price and (current_price - price) / current_price <= 0.01:
                    support_levels.append(price)
                    
            # Bullish FVGs (lower boundary)
            for fvg in micro_intel.fvgs:
                price = getattr(fvg, 'gap_end', fvg.get('gap_end', current_price) if isinstance(fvg, dict) else current_price)
                # Only consider if reasonably close to current price
                if price < current_price and (current_price - price) / current_price <= 0.01:
                    support_levels.append(price)
                    
            if support_levels:
                # Choose the highest support level (closest to current price for faster fill)
                selected_support = max(support_levels)
                # For scalping, place limit very close to the support to get filled quickly when market reaches it
                # Since we know market is already near this level (due to proximity check), place just above support
                return min(selected_support * 1.0002, current_price * 0.9998)  # Very close to support, below current price
            else:
                # If no nearby supports found, don't place order - we need to be very close to levels
                return None
                
        else:  # SHORT
            # Look for resistance levels to place sell limit
            resistance_levels = []
            
            # Swing highs
            for swing in micro_intel.recent_swing_highs[-3:]:
                price = getattr(swing, 'price', swing.get('price', current_price) if isinstance(swing, dict) else current_price)
                # Only consider resistances that are reasonably close to current price (within 1% for scalping)
                if price > current_price and (price - current_price) / current_price <= 0.01:
                    resistance_levels.append(price)
                
            # Bearish order blocks
            for ob in micro_intel.order_blocks:
                price = getattr(ob, 'entry_zone_high', ob.get('entry_zone_high', current_price) if isinstance(ob, dict) else current_price)
                # Only consider if reasonably close to current price
                if price > current_price and (price - current_price) / current_price <= 0.01:
                    resistance_levels.append(price)
                    
            # Bearish FVGs (upper boundary)
            for fvg in micro_intel.fvgs:
                if getattr(fvg, 'gap_type', None) == 'bearish':
                    price = getattr(fvg, 'gap_start', fvg.get('gap_start', current_price) if isinstance(fvg, dict) else current_price)
                    # Only consider if reasonably close to current price
                    if price > current_price and (price - current_price) / current_price <= 0.01:
                        resistance_levels.append(price)
                    
            if resistance_levels:
                # Choose the lowest resistance level (closest to current price for faster fill)
                selected_resistance = min(resistance_levels)
                # For scalping, place limit very close to the resistance to get filled quickly when market reaches it
                # Since we know market is already near this level (due to proximity check), place just below resistance
                return max(selected_resistance * 0.9998, current_price * 1.0002)  # Very close to resistance, above current price
            else:
                # If no nearby resistances found, don't place order - we need to be very close to levels
                return None
        
        return None

    def _calculate_scalping_stop_loss(self, direction: str, entry_price: float, 
                                    micro_intel: MicrostructureIntelligence) -> Optional[float]:
        """Calculate tight but safe stop loss for scalping"""
        
        # Use microstructure-based stop placement
        if direction == 'LONG':
            # Stop below nearest swing low or order block
            stop_candidates = []
            
            # Below recent swing lows
            for swing in micro_intel.recent_swing_lows[-2:]:
                stop_candidates.append(getattr(swing, 'price', entry_price) * 0.999)  # Small buffer
                
            # Below bullish order blocks
            for ob in micro_intel.order_blocks:
                if getattr(ob, 'type', None) == 'bullish':
                    stop_candidates.append(getattr(ob, 'entry_zone_low', entry_price) * 0.998)
                    
            if stop_candidates:
                # Use the highest (closest) stop for tight risk management
                return max(stop_candidates)
            else:
                # Fallback: fixed percentage stop
                return entry_price * 0.997  # 0.3% stop
                
        else:  # SHORT
            # Stop above nearest swing high or order block
            stop_candidates = []
            
            # Above recent swing highs
            for swing in micro_intel.recent_swing_highs[-2:]:
                stop_candidates.append(getattr(swing, 'price', entry_price) * 1.001)  # Small buffer
                
            # Above bearish order blocks
            for ob in micro_intel.order_blocks:
                if getattr(ob, 'type', None) == 'bearish':
                    stop_candidates.append(getattr(ob, 'entry_zone_high', entry_price) * 1.002)
                    
            if stop_candidates:
                # Use the lowest (closest) stop for tight risk management
                return min(stop_candidates)
            else:
                # Fallback: fixed percentage stop
                return entry_price * 1.003  # 0.3% stop
                
        return None

    def _calculate_scalping_take_profit(self, direction: str, entry_price: float, 
                                      micro_intel: MicrostructureIntelligence) -> Optional[float]:
        """Calculate target based on microstructure and liquidity zones"""
        
        if direction == 'LONG':
            # Look for resistance levels to take profits
            resistance_levels = []
            
            # Swing highs
            for swing in micro_intel.recent_swing_highs[-3:]:
                resistance_levels.append(swing.get('price', entry_price))
                
            # Bearish order blocks
            for ob in micro_intel.order_blocks:
                if getattr(ob, 'type', None) == 'bearish':
                    resistance_levels.append(getattr(ob, 'entry_zone_high', entry_price))
                    
            # Bearish FVGs (upper boundary)
            for fvg in micro_intel.fvgs:
                if getattr(fvg, 'gap_type', None) == 'bearish':
                    resistance_levels.append(getattr(fvg, 'gap_start', entry_price))
                    
            if resistance_levels:
                # Choose the closest resistance (lowest) for quick profit taking
                return min(resistance_levels) * 1.001  # Small buffer above resistance
            else:
                # Fallback: 0.5% target
                return entry_price * 1.005
                
        else:  # SHORT
            # Look for support levels to take profits
            support_levels = []
            
            # Swing lows
            for swing in micro_intel.recent_swing_lows[-3:]:
                support_levels.append(getattr(swing, 'price', entry_price))
                
            # Bullish order blocks
            for ob in micro_intel.order_blocks:
                if getattr(ob, 'type', None) == 'bullish':
                    support_levels.append(getattr(ob, 'entry_zone_low', entry_price))
                    
            # Bullish FVGs (lower boundary)
            for fvg in micro_intel.fvgs:
                if getattr(fvg, 'gap_type', None) == 'bullish':
                    support_levels.append(getattr(fvg, 'gap_end', entry_price))
                    
            if support_levels:
                # For SHORT positions, we want to take profit as price drops toward support
                # Only consider support levels that are below our entry price (logical for a short)
                valid_support_levels = [level for level in support_levels if level < entry_price]
                if valid_support_levels:
                    # Take profit near the highest support that is still below entry (closest to entry for quick profit)
                    take_profit_level = max(valid_support_levels)
                    # Take profit slightly ABOVE support level to capture profit as price reaches support
                    # and potentially reverses (we want to be filled before a strong reversal happens)
                    return take_profit_level * 1.001  # Slightly above support level
                else:
                    # If no valid supports below entry, use fallback below entry
                    return entry_price * 0.995  # 0.5% below entry for SHORT
            else:
                # Fallback: 0.5% below entry for SHORT
                return entry_price * 0.995  # 0.5% below for SHORT
                
        return None

    def _estimate_scalping_duration(self, micro_intel: MicrostructureIntelligence) -> float:
        """Estimate expected time in market based on volatility"""
        # Use LTF momentum and trade flow as indicators
        momentum_strength = abs(micro_intel.ltf_momentum)
        flow_aggression = micro_intel.trade_flow_analysis.get('taker_percentage', 0.3)
        
        # Higher momentum and aggression = faster moves = shorter duration
        base_duration = 15  # Base 15 minutes for scalping
        speed_factor = (momentum_strength + flow_aggression) / 2
        
        estimated_duration = max(3, base_duration * (1 - speed_factor * 0.5))  # 3-15 minutes
        return estimated_duration

    def _compile_microstructure_reasons(self, micro_intel: MicrostructureIntelligence) -> List[str]:
        """Compile reasons for the trade decision"""
        reasons = []
        
        if micro_intel.ltf_trend == 'uptrend':
            reasons.append(f"LTF uptrend confirmed ({micro_intel.ltf_strength:.0%} strength)")
        else:
            reasons.append(f"LTF downtrend confirmed ({micro_intel.ltf_strength:.0%} strength)")
            
        flow_data = micro_intel.trade_flow_analysis
        if flow_data:
            if flow_data['taker_ratio'] > 1.2:
                reasons.append(f"Strong buy pressure (taker ratio: {flow_data['taker_ratio']:.2f})")
            elif flow_data['taker_ratio'] < 0.8:
                reasons.append(f"Strong sell pressure (taker ratio: {flow_data['taker_ratio']:.2f})")
                
        if micro_intel.range_state == 'range':
            reasons.append("Range state detected - avoiding directional trades")
            
        return reasons

    def _determine_market_regime(self, micro_intel: MicrostructureIntelligence) -> str:
        """Determine market regime for position sizing"""
        momentum_strength = abs(micro_intel.ltf_momentum)
        flow_aggression = micro_intel.trade_flow_analysis.get('taker_percentage', 0.3)
        
        if momentum_strength > 0.7 and flow_aggression > 0.5:
            return 'trending'
        elif momentum_strength < 0.3 and flow_aggression < 0.3:
            return 'volatile'
        else:
            return 'normal'

    def _validate_regime_alignment(self, signal: ScalpingSignal, micro_intel: MicrostructureIntelligence) -> bool:
        """Validate that the signal aligns with market regime"""
        logger.debug(f"Validating regime alignment for {signal.direction} signal")
        
        # Skip if in ranging conditions
        if micro_intel.range_state == 'range':
            logger.debug(" Regime check failed: market in range")
            return False
            
        # Check that trend direction aligns with HTF when appropriate
        # For scalping, allow more flexibility as LTF dominates for short-term moves
        if micro_intel.htf_trend:
            logger.debug(f"HTF trend: {micro_intel.htf_trend}, strength: {micro_intel.htf_strength}, signal: {signal.direction}")
            if (micro_intel.htf_trend == 'downtrend' and signal.direction == 'LONG' and 
                micro_intel.htf_strength > 0.85):  # Increased threshold from 0.7 to 0.85
                # Against very strong HTF downtrend - avoid longs
                logger.debug(" Regime check failed: LONG against very strong HTF downtrend")
                return False
            elif (micro_intel.htf_trend == 'uptrend' and signal.direction == 'SHORT' and 
                  micro_intel.htf_strength > 0.85):  # Increased threshold from 0.7 to 0.85
                # Against very strong HTF uptrend - avoid shorts
                logger.debug(" Regime check failed: SHORT against very strong HTF uptrend")
                return False
                
        logger.debug(" Regime check passed")
        return True

    def _calculate_microstructure_position_size(self, confidence: float) -> float:
        """Calculate position size based on microstructure confidence"""
        # With the new proximity-based approach, when we do get signals, they should have high probability of success
        # So we can be more aggressive with sizing for higher confidence levels
        if confidence >= 0.85:  # Higher threshold for maximum position
            return 1.0  # Full position for very high confidence
        elif confidence >= 0.75:
            return 0.85   # Large position for high confidence
        elif confidence >= 0.65:
            return 0.7   # Medium-large position for good confidence
        elif confidence >= 0.55:
            return 0.55   # Medium position for decent confidence
        elif confidence >= 0.45:
            return 0.4   # Small-medium position for moderate confidence
        else:
            return 0.3   # Small position for low confidence

    def _check_market_proximity_to_levels(self, direction: str, micro_intel: MicrostructureIntelligence) -> bool:
        """Check if current market is near relevant microstructure levels for immediate opportunity"""
        current_price = micro_intel.current_price
        proximity_threshold = 0.005  # 0.5% proximity threshold for scalping
        
        if direction == 'LONG':
            # For longs, check if price is near recent swing lows, bullish order blocks, or bullish FVGs
            # This means current price should be near support levels where bounce might occur
            
            # Check swing lows
            for swing in micro_intel.recent_swing_lows[-3:]:
                price = getattr(swing, 'price', swing.get('price', current_price) if isinstance(swing, dict) else current_price)
                if abs(current_price - price) / current_price <= proximity_threshold:
                    logger.debug(f" Market near swing low support: ${price:.4f}, current: ${current_price:.4f}")
                    return True
            
            # Check bullish order blocks
            for ob in micro_intel.order_blocks:
                if getattr(ob, 'type', None) == 'bullish':
                    entry_low = getattr(ob, 'entry_zone_low', ob.get('entry_zone_low', current_price) if isinstance(ob, dict) else current_price)
                    if abs(current_price - entry_low) / current_price <= proximity_threshold:
                        logger.debug(f" Market near bullish order block support: ${entry_low:.4f}, current: ${current_price:.4f}")
                        return True
            
            # Check bullish FVGs
            for fvg in micro_intel.fvgs:
                if getattr(fvg, 'gap_type', None) == 'bullish':
                    gap_end = getattr(fvg, 'gap_end', fvg.get('gap_end', current_price) if isinstance(fvg, dict) else current_price)
                    if abs(current_price - gap_end) / current_price <= proximity_threshold:
                        logger.debug(f" Market near bullish FVG support: ${gap_end:.4f}, current: ${current_price:.4f}")
                        return True
        
        else:  # SHORT
            # For shorts, check if price is near recent swing highs, bearish order blocks, or bearish FVGs
            # This means current price should be near resistance levels where rejection might occur
            
            # Check swing highs
            for swing in micro_intel.recent_swing_highs[-3:]:
                price = getattr(swing, 'price', swing.get('price', current_price) if isinstance(swing, dict) else current_price)
                if abs(current_price - price) / current_price <= proximity_threshold:
                    logger.debug(f" Market near swing high resistance: ${price:.4f}, current: ${current_price:.4f}")
                    return True
            
            # Check bearish order blocks
            for ob in micro_intel.order_blocks:
                if getattr(ob, 'type', None) == 'bearish':
                    entry_high = getattr(ob, 'entry_zone_high', ob.get('entry_zone_high', current_price) if isinstance(ob, dict) else current_price)
                    if abs(current_price - entry_high) / current_price <= proximity_threshold:
                        logger.debug(f" Market near bearish order block resistance: ${entry_high:.4f}, current: ${current_price:.4f}")
                        return True
            
            # Check bearish FVGs
            for fvg in micro_intel.fvgs:
                if getattr(fvg, 'gap_type', None) == 'bearish':
                    gap_start = getattr(fvg, 'gap_start', fvg.get('gap_start', current_price) if isinstance(fvg, dict) else current_price)
                    if abs(current_price - gap_start) / current_price <= proximity_threshold:
                        logger.debug(f" Market near bearish FVG resistance: ${gap_start:.4f}, current: ${current_price:.4f}")
                        return True
        
        logger.debug(f" Market not near relevant {direction} microstructure levels (threshold: {proximity_threshold:.1%})")
        return False