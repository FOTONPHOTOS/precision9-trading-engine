from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pandas as pd
import logging

from rre_common_types import RangeAnalysis
from symbol_specific_config import SymbolSpecificConfig
from microstructure_contradiction_detector import MicrostructureContradictionDetector
from advanced_volatility_analyzer import AdvancedVolatilityAnalyzer
from liquidity_sweep_detector import StopHuntWarning # NEW: Import StopHuntWarning


logger = logging.getLogger(__name__)


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
    range_trap_analysis: "RangeAnalysis"
    stop_hunt_warning: StopHuntWarning # NEW

    # Confluence
    confluence_score: int
    timestamp: datetime # NEW

    # HTF Context
    htf_context: Dict[str, Any] # NEW

    # Structural Integrity
    structural_integrity_score: float # NEW
    structural_integrity_reasons: List[str] # NEW

    # Raw Data
    price_data: pd.DataFrame # NEW

    # --- Fields with default values MUST come after non-default fields ---
    htf2_context: Optional[Dict[str, Any]] = None # NEW
    volume_profile_zones: Optional[Dict[str, Any]] = None # NEW
    # Sentiment/Flow (for internal use by brain)
    lci_score: Optional[float] = None # NEW
    taker_ratio: Optional[float] = None # NEW


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

    def __init__(self, symbol="SOLUSDT"):
        self.symbol = symbol.upper()
        
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
        self.contradiction_detector = MicrostructureContradictionDetector(self.symbol)
        
        # NEW: Advanced volatility analyzer
        self.volatility_analyzer = AdvancedVolatilityAnalyzer(self.symbol)
        
        self.is_active = True # Default to being active

    def set_active(self, is_active: bool):
        """Enable or disable the Trend Continuation Brain."""
        logger.info(f"[TCB] Setting active status to: {is_active}")
        self.is_active = is_active

    def _get_signal_strength(self, confidence: float) -> str:
        """Maps a numerical confidence score to a descriptive string."""
        if confidence >= self.very_strong_confidence:
            return 'VERY_STRONG'
        elif confidence >= self.strong_confidence:
            return 'STRONG'
        elif confidence >= self.standard_confidence:
            return 'MODERATE'
        else:
            return 'WEAK'

    def _create_blocked_decision(self, current_price: float, block_reason: str, reasoning_chain: List[str]) -> IntelligentDecision:
        """Create a decision that blocks trading"""
        return IntelligentDecision(
            direction='NEUTRAL', 
            confidence=0.0, 
            signal_strength='BLOCKED',
            entry_zone=(0,0), 
            stop_loss=0, 
            take_profits=[], 
            risk_reward=0,
            position_size_multiplier=0, 
            reasoning_chain=reasoning_chain, 
            should_trade=False,
            urgency='DO_NOT_TRADE', 
            analysis_quality=0.0,
            decision_timestamp=datetime.utcnow(),
            blockers=[block_reason], 
            opportunities=[], 
            warnings=[],
            max_risk_percent=0.0,
            market_intel=None,
            swing_highs=[],
            swing_lows=[]
        )

    def analyze(self, market_intel: MarketIntelligence, btc_context: Optional[dict] = None, correlation_score: Optional[float] = None, lci_score: Optional[float] = None, gls_score: Optional[float] = None, breakout_signal: Optional[any] = None, top_trader_ls_ratio: Optional[float] = None, taker_ratio: Optional[float] = None, taker_ratio_ma: Optional[float] = None) -> IntelligentDecision:
        """
        New analysis function that first classifies the market state (Continuation vs. Reversal)
        and then applies the appropriate tactical logic.
        """
        if not self.is_active:
            return self._create_blocked_decision(market_intel.current_price, "Trend Continuation Brain is disabled for this session.", [])

        self.reasoning_chain = []
        self.confidence = 0.5 # Start with neutral confidence

        # [STEP 0] Microstructure Contradiction Check (COMMENTED OUT)
        # self.reasoning_chain.append("[STEP 0] Checking for Microstructure Contradictions...\n")

        # # Prepare market data for contradiction check
        # market_data = {
        #     'ltf_trend': market_intel.trend_direction,
        #     'ltf_strength': market_intel.trend_strength,
        #     'ltf_momentum': self._calculate_rough_momentum(market_intel),  # NEW method
        #     'trade_flow_analysis': {
        #         'taker_ratio': taker_ratio or 1.0,
        #         'taker_ratio_ma': taker_ratio_ma or 1.0,
        #         'aggressive_buy_pressure': 0,  # Placeholder - would need real data
        #         'aggressive_sell_pressure': 0  # Placeholder - would need real data
        #     },
        #     'order_blocks': market_intel.order_blocks or [],
        #     'fvgs': market_intel.fvgs or [],
        #     'range_trap_analysis': market_intel.range_trap_analysis
        # }

        # contradiction_analysis = self.contradiction_detector.detect_contradictions(market_data)
        # contradiction_severity = contradiction_analysis['severity_score']
        # contradictions_found = contradiction_analysis['contradictions_found']

        # if contradictions_found:
        #     self.reasoning_chain.append(f"  - [CONTRADICTIONS DETECTED]:")
        #     for contradiction in contradictions_found:
        #         self.reasoning_chain.append(f"    - {contradiction}")
        #     self.reasoning_chain.append(f"  - Contradiction Severity: {contradiction_severity:.2f}")

        #     # Apply confidence reduction based on contradiction severity
        #     confidence_reduction = contradiction_analysis['confidence_reduction']
        #     self.confidence = max(0.15, self.confidence - confidence_reduction)
        #     self.reasoning_chain.append(f"  - Confidence reduced by {confidence_reduction:.2f} due to contradictions. New confidence: {self.confidence:.2f}")

        #     # If contradictions are severe, block the trade entirely
        #     if self.contradiction_detector.should_avoid_scalping(contradiction_analysis):
        #         self.reasoning_chain.append("  - [CRITICAL] High contradiction severity detected. BLOCKING TRADE.")
        #         return self._create_blocked_decision(market_intel.current_price, f"High microstructure contradiction severity: {contradiction_severity:.2f}", self.reasoning_chain)
        # else:
        #     self.reasoning_chain.append("  - No significant microstructure contradictions detected. Proceeding with analysis.")

        # [NEW STEP 0.1] Whale vs. Retail Divergence Check (OVERRIDE)
        self.reasoning_chain.append("[STEP 0.1] Checking for Whale vs. Retail Divergence...\n")
        if lci_score is not None and top_trader_ls_ratio is not None:
            retail_is_long = lci_score > 0.6
            retail_is_short = lci_score < 0.4
            whales_are_long = top_trader_ls_ratio > 1.1
            whales_are_short = top_trader_ls_ratio < 0.9

            # Bearish Divergence: Retail is long, but whales are not.
            if retail_is_long and not whales_are_long:
                reason = f"Retail is bullish (LCI: {lci_score:.2f}) but Whales are neutral or bearish (L/S Ratio: {top_trader_ls_ratio:.2f})"
                self.reasoning_chain.append(f"  - [!] BEARISH DIVERGENCE DETECTED: {reason}")
                return self._create_blocked_decision(market_intel.current_price, f"Whale/Retail Bearish Divergence", self.reasoning_chain)

            # Bullish Divergence: Retail is short, but whales are not.
            if retail_is_short and not whales_are_short:
                reason = f"Retail is bearish (LCI: {lci_score:.2f}) but Whales are neutral or bullish (L/S Ratio: {top_trader_ls_ratio:.2f})"
                self.reasoning_chain.append(f"  - [!] BULLISH DIVERGENCE DETECTED: {reason}")
                return self._create_blocked_decision(market_intel.current_price, f"Whale/Retail Bullish Divergence", self.reasoning_chain)

            self.reasoning_chain.append("  - No significant divergence found. Proceeding with analysis.")
        else:
            self.reasoning_chain.append("  - Insufficient data for divergence check.")

        # [STEP 1] ESTABLISH HTF CONTEXT
        self.reasoning_chain.append("\n[STEP 1] Establishing HTF Context (15M Chart)...\n")
        htf = market_intel.htf_context
        # Check if HTF context exists and has valid swing range (high > low)
        if not (htf and htf.get('fib_levels')):
            if htf and htf.get('price_location', '').startswith('Invalid'):
                # Handle invalid HTF context case where swing high <= swing low
                self.reasoning_chain.append(f"  - Invalid HTF Context: {htf['price_location']}")
                return self._create_blocked_decision(market_intel.current_price, "Invalid HTF Context - No Valid Swing Range", self.reasoning_chain)
            return self._create_blocked_decision(market_intel.current_price, "Missing HTF Context", self.reasoning_chain)

        # Validate that swing high is actually higher than swing low to prevent the $15.53 to $15.53 issue
        htf_swing_high = htf.get('htf_swing_high')
        htf_swing_low = htf.get('htf_swing_low')
        if htf_swing_high is None or htf_swing_low is None or htf_swing_high <= htf_swing_low:
            self.reasoning_chain.append(f"  - Invalid HTF Swing Range: High (${htf_swing_high}) <= Low (${htf_swing_low})")
            return self._create_blocked_decision(market_intel.current_price, "Invalid HTF Swing Range", self.reasoning_chain)

        self.reasoning_chain.append(f"  - HTF Swing Range: ${htf_swing_low:.2f} to ${htf_swing_high:.2f}")
        self.reasoning_chain.append(f"  - Current Price Location: {htf['price_location']}")

        # [NEW STEP 1.0.1] ESTABLISH HTF2 CONTEXT (4H Chart) for Broader Perspective
        self.reasoning_chain.append("\n[STEP 1.0.1] Establishing HTF2 Context (4H Chart) for Broader Perspective...\n")
        htf2 = market_intel.htf2_context
        if not (htf2 and htf2.get('fib_levels')):
            if htf2 and htf2.get('price_location', '').startswith('Invalid'):
                # Handle invalid HTF2 context case where swing high <= swing low
                self.reasoning_chain.append(f"  - Invalid HTF2 Context: {htf2['price_location']}")
                # Continue with only HTF context if HTF2 is invalid
                self.reasoning_chain.append("  - Continuing with 15M HTF context only.")
            else:
                # HTF2 context not available, continue with HTF context only
                self.reasoning_chain.append("  - HTF2 context not available, using 15M HTF context only.")
        else:
            # Validate HTF2 context
            htf2_swing_high = htf2.get('htf2_swing_high')
            htf2_swing_low = htf2.get('htf2_swing_low')
            if htf2_swing_high is None or htf2_swing_low is None or htf2_swing_high <= htf2_swing_low:
                self.reasoning_chain.append(f"  - Invalid HTF2 Swing Range: High (${htf2_swing_high}) <= Low (${htf2_swing_low})")
                self.reasoning_chain.append("  - Continuing with 15M HTF context only.")
            else:
                self.reasoning_chain.append(f"  - HTF2 4H Swing Range: ${htf2_swing_low:.2f} to ${htf2_swing_high:.2f}")
                self.reasoning_chain.append(f"  - Current Price Location in 4H Context: {htf2['price_location']}")

                # NEW: Use HTF2 context to adjust micro-structure interpretations
                # Check if current price is near important 4H levels (OTE levels, swing points)
                fib_levels = htf2.get("fib_levels", {})
                ote_high = fib_levels.get("ote_high")
                ote_low = fib_levels.get("ote_low")

                if ote_high and abs(market_intel.current_price - ote_high) / market_intel.current_price < 0.02:  # Within 2% of OTE high
                    self.reasoning_chain.append(f"  - [4H HTF2] Price near 4H OTE High (${ote_high:.2f}) - Potential reversal area, reducing confidence in SHORT attempts")
                    if market_intel.trend_direction == 'downtrend':
                        # If LTF trend is downtrend but we're at 4H OTE High, micro BOS might reverse
                        self.confidence = max(0.10, self.confidence - 0.15)  # Reduce confidence in continuation
                elif ote_low and abs(market_intel.current_price - ote_low) / market_intel.current_price < 0.02:  # Within 2% of OTE low
                    self.reasoning_chain.append(f"  - [4H HTF2] Price near 4H OTE Low (${ote_low:.2f}) - Potential reversal area, reducing confidence in LONG attempts")
                    if market_intel.trend_direction == 'uptrend':
                        # If LTF trend is uptrend but we're at 4H OTE Low, micro BOS might reverse
                        self.confidence = max(0.10, self.confidence - 0.15)  # Reduce confidence in continuation

                # Check for 4H structural alignment
                htf2_trend_aligned = False
                if market_intel.trend_direction == 'downtrend' and 'Premium' in htf2['price_location']:
                    # Price in premium at 4H level during LTF downtrend - alignment
                    htf2_trend_aligned = True
                    self.reasoning_chain.append("  - [4H HTF2] LTF downtrend aligned with 4H premium - structural alignment")
                elif market_intel.trend_direction == 'uptrend' and 'Discount' in htf2['price_location']:
                    # Price in discount at 4H level during LTF uptrend - alignment
                    htf2_trend_aligned = True
                    self.reasoning_chain.append("  - [4H HTF2] LTF uptrend aligned with 4H discount - structural alignment")

                # If HTF2 and LTF are aligned, increase confidence in continuation setups
                if htf2_trend_aligned:
                    self.confidence = min(0.95, self.confidence + 0.05)
                    self.reasoning_chain.append("  - [4H HTF2] LTF and 4H alignment - increasing continuation confidence by 5%")

        # [NEW STEP 1.1] Stop Hunt Risk Assessment
        self.reasoning_chain.append("\n[STEP 1.1] Stop Hunt Risk Assessment...\n")
        stop_hunt_warning = market_intel.stop_hunt_warning
        if stop_hunt_warning:
            # Check if stop hunt mode is actually active, not just if probability exists
            is_stop_hunt_active = getattr(stop_hunt_warning, 'is_stop_hunt_mode', getattr(stop_hunt_warning, 'stop_hunt_probability', 0.0) > 0.5)
            stop_hunt_prob = getattr(stop_hunt_warning, 'stop_hunt_probability', 0.0)
            hunt_type = getattr(stop_hunt_warning, 'hunt_type', 'UNKNOWN').upper()
            range_context = getattr(stop_hunt_warning, 'range_context', 'UNKNOWN').upper()

            if is_stop_hunt_active and stop_hunt_prob > 0.50:  # Even moderate risk should be considered
                self.reasoning_chain.append(f"  - [!] STOP HUNT RISK DETECTED: {stop_hunt_prob:.0%}")
                self.reasoning_chain.append(f"  - Hunt Type: {hunt_type}, Range Context: {range_context}")

                # NEW: Check for potential reversal opportunities after stop hunt
                # This happens when retail is trapped in one direction and the market reverses
                lci_score = getattr(market_intel, 'lci_score', 0.5)  # Get LCI score if available
                taker_ratio = getattr(market_intel, 'taker_ratio', None)  # Get taker ratio if available

                potential_reversal_signal = False
                reversal_direction = None

                # Check for reversal after directional hunts based on LCI/taker divergence
                if hunt_type == 'DIRECTIONAL_LONG' and lci_score is not None and lci_score > 0.65 and taker_ratio is not None:  # Hunting longs, retail is crowded long
                    # If we see aggressive selling (taker ratio < 0.85) that confirms the hunt,
                    # but then taker ratio starts normalizing (> 0.85) or increasing, potential reversal
                    if taker_ratio < 0.85:
                        # Hunt confirmed, but if taker ratio begins to recover, look for reversal
                        potential_reversal_signal = True
                        reversal_direction = 'SHORT'  # Shorts were hunted, now longs might form
                    elif taker_ratio > 1.0:
                        # Taker ratio showing aggressive buying - strong reversal signal
                        potential_reversal_signal = True
                        reversal_direction = 'LONG'  # Hunted longs, now aggressive buying
                        self.reasoning_chain.append(f"  - [REVERSAL SIGNAL] Aggressive buying (taker_ratio: {taker_ratio:.2f}) after long hunt")

                elif hunt_type == 'DIRECTIONAL_SHORT' and lci_score is not None and lci_score < 0.35 and taker_ratio is not None:  # Hunting shorts, retail is crowded short
                    # If we see aggressive buying (taker ratio > 1.15) that confirms the hunt,
                    # but then taker ratio starts normalizing (< 1.15) or decreasing, potential reversal
                    if taker_ratio > 1.15:
                        # Hunt confirmed, but if taker ratio begins to recover, look for reversal
                        potential_reversal_signal = True
                        reversal_direction = 'LONG'  # Longs were hunted, now shorts might form
                    elif taker_ratio < 0.9:
                        # Taker ratio showing aggressive selling - strong reversal signal
                        potential_reversal_signal = True
                        reversal_direction = 'SHORT'  # Hunted shorts, now aggressive selling
                        self.reasoning_chain.append(f"  - [REVERSAL SIGNAL] Aggressive selling (taker_ratio: {taker_ratio:.2f}) after short hunt")

                # Determine if the intended trade direction conflicts with the stop hunt
                trend_direction = market_intel.trend_direction.upper()

                # Use range context for additional safety
                is_tight_range = 'TIGHT_RANGE' in range_context

                if hunt_type == 'DIRECTIONAL_LONG':
                    # Hunting longs - for micro-scalping, focus on immediate LTF opportunities
                    if trend_direction == 'UPTREND':
                        # In an uptrend with long hunting, look for immediate LTF setups
                        # This could provide quick longing opportunities as the hunt fails
                        self.reasoning_chain.append(f"  - [INFO] UPTREND with DIRECTIONAL_LONG hunt - Looking for LTF long opportunities")

                        # For micro-scalping, look for immediate reversal signs:
                        recent_patterns = market_intel.candle_patterns[-5:] if len(market_intel.candle_patterns) >= 5 else market_intel.candle_patterns
                        bullish_momentum_count = sum(1 for p in recent_patterns if p.get('type') == 'BULLISH_BREAK')

                        # If bullish momentum is emerging despite the hunt, micro opportunity for longs
                        if bullish_momentum_count >= 1 and potential_reversal_signal and reversal_direction == 'LONG':
                            self.reasoning_chain.append(f"  - [MICRO OPPORTUNITY] Bullish momentum during DIRECTIONAL_LONG hunt - LONG opportunity")
                            # Don't block long trades, may slightly increase confidence for micro move
                            if not is_tight_range:  # Only if not in tight range
                                self.confidence = min(0.70, self.confidence + 0.08)  # Slight boost for micro move
                                self.reasoning_chain.append(f"  - [CONFIDENCE ADJUSTMENT] Adding 8% confidence for LTF micro opportunity")
                        elif stop_hunt_prob > 0.80 or (is_tight_range and stop_hunt_prob > 0.60):
                            # Still block if probability is extremely high or in tight range
                            self.reasoning_chain.append(f"  - [CRITICAL] Directional LONG hunt during UPTREND in {range_context} (High probability: {stop_hunt_prob:.0%}) - BLOCKING LONG trade")
                            return self._create_blocked_decision(market_intel.current_price, f"Directional LONG hunt during UPTREND ({stop_hunt_prob:.0%})", self.reasoning_chain)
                        else:
                            # For micro-scalping, don't overly penalize - LTF moves happen fast
                            base_reduction = 0.15  # Lower reduction for micro moves
                            range_penalty = 0.10 if is_tight_range else 0.0
                            confidence_reduction = base_reduction + range_penalty
                            self.confidence = max(0.10, self.confidence - confidence_reduction)
                            self.reasoning_chain.append(f"  - [INFO] Reducing confidence by {confidence_reduction:.0%} - LONG trade during counter-trend LONG hunt")
                    elif trend_direction == 'DOWNTREND':
                        # In a downtrend, hunting longs might provide shorting opportunities
                        self.reasoning_chain.append(f"  - [INFO] DOWNTREND with DIRECTIONAL_LONG hunt - Looking for LTF short opportunities as hunt expires")
                        # For micro-scalping, don't overly penalize trend-aligned hunt
                        if is_tight_range:
                            confidence_reduction = 0.10  # Lower reduction for micro moves
                            self.confidence = max(0.10, self.confidence - confidence_reduction)
                            self.reasoning_chain.append(f"  - [INFO] In {range_context}, reducing confidence by {confidence_reduction:.0%} for micro strategy")
                        # Otherwise, minimal confidence reduction for trend-aligned hunt
                    else:
                        # Neutral trend - moderate confidence reduction for micro strategy
                        base_reduction = 0.18  # Lower for micro moves
                        range_penalty = 0.08 if is_tight_range else 0.0
                        confidence_reduction = base_reduction + range_penalty
                        # NEW: If there's a potential reversal signal, adjust accordingly
                        if potential_reversal_signal and reversal_direction:
                            # If our neutral position aligns with reversal direction, reduce penalty
                            if (reversal_direction == 'LONG' and self.confidence < 0.7) or (reversal_direction == 'SHORT' and self.confidence < 0.7):
                                confidence_reduction = max(0.08, confidence_reduction - 0.08)  # Greater adjustment for micro moves
                                self.reasoning_chain.append(f"  - [REVERSAL CONSIDERATION] Adjusting penalty for potential reversal to {reversal_direction}")
                        self.confidence = max(0.10, self.confidence - confidence_reduction)
                        self.reasoning_chain.append(f"  - [INFO] Reducing confidence by {confidence_reduction:.0%} due to directional hunt")


                elif hunt_type == 'DIRECTIONAL_SHORT':
                    # Hunting shorts - for micro-scalping, focus on immediate LTF opportunities
                    if trend_direction == 'DOWNTREND':
                        # In a downtrend with short hunting, look for immediate LTF setups
                        # This could provide quick shorting opportunities as the hunt fails
                        self.reasoning_chain.append(f"  - [INFO] DOWNTREND with DIRECTIONAL_SHORT hunt - Looking for LTF short opportunities")

                        # For micro-scalping, look for immediate reversal signs:
                        recent_patterns = market_intel.candle_patterns[-5:] if len(market_intel.candle_patterns) >= 5 else market_intel.candle_patterns
                        bearish_momentum_count = sum(1 for p in recent_patterns if p.get('type') == 'BEARISH_BREAK')

                        # If bearish momentum is emerging despite the hunt, micro opportunity for shorts
                        if bearish_momentum_count >= 1 and potential_reversal_signal and reversal_direction == 'SHORT':
                            self.reasoning_chain.append(f"  - [MICRO OPPORTUNITY] Bearish momentum during DIRECTIONAL_SHORT hunt - SHORT opportunity")
                            # Don't block short trades, may slightly increase confidence for micro move
                            if not is_tight_range:  # Only if not in tight range
                                self.confidence = min(0.70, self.confidence + 0.08)  # Slight boost for micro move
                                self.reasoning_chain.append(f"  - [CONFIDENCE ADJUSTMENT] Adding 8% confidence for LTF micro opportunity")
                        elif stop_hunt_prob > 0.80 or (is_tight_range and stop_hunt_prob > 0.60):
                            # Still block if probability is extremely high or in tight range
                            self.reasoning_chain.append(f"  - [CRITICAL] Directional SHORT hunt during DOWNTREND in {range_context} (High probability: {stop_hunt_prob:.0%}) - BLOCKING SHORT trade")
                            return self._create_blocked_decision(market_intel.current_price, f"Directional SHORT hunt during DOWNTREND ({stop_hunt_prob:.0%})", self.reasoning_chain)
                        else:
                            # For micro-scalping, don't overly penalize - LTF moves happen fast
                            base_reduction = 0.15  # Lower reduction for micro moves
                            range_penalty = 0.10 if is_tight_range else 0.0
                            confidence_reduction = base_reduction + range_penalty
                            self.confidence = max(0.10, self.confidence - confidence_reduction)
                            self.reasoning_chain.append(f"  - [INFO] Reducing confidence by {confidence_reduction:.0%} - SHORT trade during counter-trend SHORT hunt")
                    elif trend_direction == 'UPTREND':
                        self.reasoning_chain.append(f"  - [INFO] UPTREND with DIRECTIONAL_SHORT hunt - Looking for LTF long opportunities as hunt expires")
                        # For micro-scalping, don't overly penalize trend-aligned hunt
                        if is_tight_range:
                            confidence_reduction = 0.10  # Lower reduction for micro moves
                            self.confidence = max(0.10, self.confidence - confidence_reduction)
                            self.reasoning_chain.append(f"  - [INFO] In {range_context}, reducing confidence by {confidence_reduction:.0%} for micro strategy")
                        # Otherwise, minimal confidence reduction for trend-aligned hunt
                    else:
                        # Neutral trend - moderate confidence reduction for micro strategy
                        base_reduction = 0.18  # Lower for micro moves
                        range_penalty = 0.08 if is_tight_range else 0.0
                        confidence_reduction = base_reduction + range_penalty
                        # NEW: If there's a potential reversal signal, adjust accordingly
                        if potential_reversal_signal and reversal_direction:
                            # If our neutral position aligns with reversal direction, reduce penalty
                            if (reversal_direction == 'LONG' and self.confidence < 0.7) or (reversal_direction == 'SHORT' and self.confidence < 0.7):
                                confidence_reduction = max(0.08, confidence_reduction - 0.08)  # Greater adjustment for micro moves
                                self.reasoning_chain.append(f"  - [REVERSAL CONSIDERATION] Adjusting penalty for potential reversal to {reversal_direction}")
                        self.confidence = max(0.10, self.confidence - confidence_reduction)
                        self.reasoning_chain.append(f"  - [INFO] Reducing confidence by {confidence_reduction:.0%} due to directional hunt")


                elif hunt_type == 'BI_DIRECTIONAL':
                    # Market is likely chopping/messing with both sides
                    self.reasoning_chain.append(f"  - [CRITICAL] BI-DIRECTIONAL stop hunt detected - Market is manipulating both sides")
                    if stop_hunt_prob > 0.70 or is_tight_range:
                        self.reasoning_chain.append(f"  - [CRITICAL] Bi-directional hunt in {range_context} - BLOCKING all trades")
                        return self._create_blocked_decision(market_intel.current_price, f"Bi-directional stop hunt ({stop_hunt_prob:.0%})", self.reasoning_chain)
                    else:
                        confidence_reduction = 0.40  # High reduction for bi-directional chaos
                        self.confidence = max(0.10, self.confidence - confidence_reduction)
                        self.reasoning_chain.append(f"  - [INFO] Reducing confidence by {confidence_reduction:.0%} due to bi-directional hunt")

                else:  # General stop hunt (not directional)
                    # For general stop hunt mode, reduce confidence regardless of direction
                    if stop_hunt_prob > 0.80 or is_tight_range:
                        self.reasoning_chain.append(f"  - [CRITICAL] General stop hunt probability extremely high ({stop_hunt_prob:.0%}) - BLOCKING trade")
                        return self._create_blocked_decision(market_intel.current_price, f"General high stop hunt probability ({stop_hunt_prob:.0%})", self.reasoning_chain)
                    else:
                        base_reduction = 0.30
                        range_penalty = 0.15 if is_tight_range else 0.0
                        confidence_reduction = base_reduction + range_penalty
                        self.confidence = max(0.10, self.confidence - confidence_reduction)
                        self.reasoning_chain.append(f"  - [INFO] Reducing confidence by {confidence_reduction:.0%} due to general stop hunt")

            else:
                # Stop hunt probability is low
                if stop_hunt_prob > 0.30:
                    self.reasoning_chain.append(f"  - Low stop hunt probability ({stop_hunt_prob:.0%}). Risk is manageable.")
                else:
                    self.reasoning_chain.append("  - Stop Hunt Mode: INACTIVE. No stop hunt risk.")
        else:
            self.reasoning_chain.append("  - No stop hunt warning object available.")

        # [STEP 2] CLASSIFY MARKET STATE (THE NEW CRUCIAL STEP)
        self.reasoning_chain.append("\n[STEP 2] Classifying Market State...\n")
        market_state = self._classify_market_state(market_intel)
        self.reasoning_chain.append(f"  - STATE: {market_state}")

        # NEW: Adjust confidence based on contradictions detected during classification
        # Check for recent momentum contradictions that were logged in reasoning_chain
                # contradiction_detected = any(
                #     "contradicts" in reason.lower() or
                #     "losing momentum" in reason.lower() or
                #     "contradiction" in reason.lower() or
                #     "indecision" in reason.lower() or
                #     "turning point" in reason.lower()
                #     for reason in self.reasoning_chain
                # )
        
                # if contradiction_detected:
                #     # NEW: Assess if contradictions are due to ranging market vs. genuine structural issues
                #     # Check if HTF context shows ranging (Equilibrium) which normalizes contradictions
                #     htf_ranging = htf and ("Equilibrium" in htf.get('price_location', '') or
                #                            (htf.get('htf_swing_high') and htf.get('htf_swing_low') and
                #                             (htf['htf_swing_high'] - htf['htf_swing_low']) / market_intel.current_price < 0.02))  # Less than 2% range
        
                #     # Check if price is near swing extremes where contradictions are normal
                #     htf_near_extremes = False
                #     if htf and htf.get('htf_swing_high') and htf.get('htf_swing_low'):
                #         htf_range = htf['htf_swing_high'] - htf['htf_swing_low']
                #         distance_to_high = abs(market_intel.current_price - htf['htf_swing_high'])
                #         distance_to_low = abs(market_intel.current_price - htf['htf_swing_low'])
        
                #         # If within 1% of either swing extreme, contradictions are expected
                #         htf_near_extremes = (distance_to_high / market_intel.current_price < 0.01 or
                #                              distance_to_low / market_intel.current_price < 0.01)
        
                #     # Check if 4H context also shows ranging behavior
                #     htf2_ranging = htf2 and ("Equilibrium" in htf2.get('price_location', '') or
                #                                     (htf2.get('htf2_swing_high') and htf2.get('htf2_swing_low') and
                #                                      (htf2['htf2_swing_high'] - htf2['htf2_swing_low']) / market_intel.current_price < 0.05))  # Less than 5% range
        
                #     if htf_ranging or htf2_ranging or htf_near_extremes:
                #         # In ranging markets, contradictions are normal - reduce confidence more moderately
                #         confidence_reduction = 0.10  # Reduce by 10% instead of 25%
                #         self.confidence = max(0.20, self.confidence - confidence_reduction)  # Set minimum confidence higher
                #         self.reasoning_chain.append(f"  - [INFO] Trend contradictions detected in ranging market. Moderate confidence reduction by {confidence_reduction:.0%} to {self.confidence:.2f}")
                #     else:
                #         # Reduce confidence significantly when trend contradictions are detected in trending markets
                #         confidence_reduction = 0.25  # Reduce by 25%
                #         self.confidence = max(0.15, self.confidence - confidence_reduction)  # Set minimum confidence
                #         self.reasoning_chain.append(f"  - [INFO] Trend contradictions detected in trending market. Reducing confidence by {confidence_reduction:.0%} to {self.confidence:.2f}")
        # [STEP 3] FORMULATE THESIS & EXECUTE TACTICS
        self.reasoning_chain.append("\n[STEP 3] Formulating Thesis & Executing Tactics...\n")

        if market_state == "REVERSAL_SETUP":
            self.reasoning_chain.append("  - TACTIC: Executing Sniper Reversal Logic (Healthy Retracement).")
            return self._execute_reversal_tactic(market_intel, btc_context, correlation_score, lci_score, gls_score, breakout_signal)

        elif market_state == "CONTINUATION_SETUP":
            # NEW: Additional check for continuation setups - if there were contradictions, reconsider
            contradiction_detected = False
            if contradiction_detected:
                self.reasoning_chain.append("  - TACTIC: Continuation setup detected but with trend contradictions. Proceeding with caution.")
            else:
                self.reasoning_chain.append("  - TACTIC: Executing Trend Continuation Logic.")
            # Execute the chosen tactic
            return self._execute_continuation_tactic(market_intel, btc_context, correlation_score, lci_score, gls_score, self.confidence, breakout_signal, taker_ratio, taker_ratio_ma)

        elif market_state == "THREATENING_REVERSAL":
            self.reasoning_chain.append("  - TACTIC: THREATENING REVERSAL DETECTED. Blocking trade for safety.")
            return self._create_blocked_decision(market_intel.current_price, "Threatening Reversal Detected", self.reasoning_chain)

        else: # UNCLEAR
            self.reasoning_chain.append("  - TACTIC: Market state is unclear. Standing aside.")
            return self._create_blocked_decision(market_intel.current_price, "Unclear Market State", self.reasoning_chain)

    def _calculate_rough_momentum(self, market_intel: MarketIntelligence) -> float:
        """Calculate a rough momentum score from available data"""
        if not market_intel.candle_patterns:
            return 0.0

        # Count bullish vs bearish patterns in recent candles
        recent_patterns = market_intel.candle_patterns[-5:]  # Last 5 patterns
        bullish_count = sum(1 for p in recent_patterns if 'BULLISH' in str(p.get('type', '')).upper())
        bearish_count = sum(1 for p in recent_patterns if 'BEARISH' in str(p.get('type', '')).upper())

        if bullish_count + bearish_count == 0:
            return 0.0

        # Calculate momentum score: +1 for all bullish, -1 for all bearish
        momentum_score = (bullish_count - bearish_count) / (bullish_count + bearish_count)
        return momentum_score

    def _classify_market_state(self, market_intel: MarketIntelligence) -> str:
        """
        Classifies the current market state with a more nuanced understanding of trend continuation.
        A pullback into a discount/premium zone during a strong trend is a CONTINUATION setup, not a reversal.
        """
        htf = market_intel.htf_context
        price = market_intel.current_price
        
        htf_trend_direction = market_intel.trend_direction.upper()

        is_in_discount = "Discount" in htf['price_location']
        is_in_premium = "Premium" in htf['price_location']
        is_in_equilibrium = "Equilibrium" in htf['price_location']

        # NEW: Check for Doji patterns from structural integrity analysis
        # Doji patterns often indicate indecision and potential reversal, especially in contradiction to HTF context
        has_doji_pattern = any("doji" in r.lower() for r in market_intel.structural_integrity_reasons if "doji" in r.lower() or "indecision" in r.lower() or "turning point" in r.lower())
        
        # NEW: Check for recent momentum contradiction with trend
        recent_patterns = market_intel.candle_patterns[-3:] if len(market_intel.candle_patterns) >= 3 else market_intel.candle_patterns
        recent_bullish_breaks = sum(1 for p in recent_patterns if p.get('type') == 'BULLISH_BREAK')
        recent_bearish_breaks = sum(1 for p in recent_patterns if p.get('type') == 'BEARISH_BREAK')
        
        # Check for specific candlestick patterns indicating weakness/reversal
        has_threatening_bearish_pattern = any("evening star" in r.lower() or "shooting star" in r.lower() for r in market_intel.structural_integrity_reasons if "bearish" in r.lower())
        has_threatening_bullish_pattern = any("morning star" in r.lower() or "hammer" in r.lower() for r in market_intel.structural_integrity_reasons if "bullish" in r.lower())

        # NEW: Check for HTF context (for reference only - LTF dominates in micro-scalping)
        # For micro-scalping (0.5%-1% moves), LTF signals are primary, HTF is just context
        htf_bias_is_long = "Discount" in htf['price_location']  # In discount zone, HTF suggests move up
        ltf_trend_is_long = market_intel.trend_direction == 'uptrend'
        
        # Note HTF/LTF alignment but don't create brick wall - LTF is primary for micro moves
        htf_context_aligned = ((htf_bias_is_long and ltf_trend_is_long) or (not htf_bias_is_long and not ltf_trend_is_long))
        htf_context_conflict = not htf_context_aligned  # This is just misalignment, not a brick wall
        if htf_context_conflict:
            self.reasoning_chain.append("  - [INFO] HTF/LTF contexts misaligned - LTF dominates for micro-scalping.")
        
        # NEW: Check for recent momentum reversal after stop hunt
        # This is where we can capitalize on reversals after directional hunts
        stop_hunt_warning = market_intel.stop_hunt_warning
        lci_score = getattr(market_intel, 'lci_score', 0.5)
        taker_ratio = getattr(market_intel, 'taker_ratio', 1.0)
        
        # NEW: Detect potential reversal after directional hunt
        potential_stop_hunt_reversal = False
        stop_hunt_reversal_direction = None
        
        if stop_hunt_warning:
            hunt_type = getattr(stop_hunt_warning, 'hunt_type', 'UNKNOWN').upper()
            
            # If we have a directional hunt with high probability, look for reversal opportunities
            # Only proceed if taker_ratio is available
            if taker_ratio is not None and lci_score is not None:
                if (hunt_type == 'DIRECTIONAL_LONG' and lci_score > 0.65 and taker_ratio > 1.0) or \
                   (hunt_type == 'DIRECTIONAL_SHORT' and lci_score < 0.35 and taker_ratio < 1.0):
                    # Potential reversal after directional hunt
                    potential_stop_hunt_reversal = True
                    stop_hunt_reversal_direction = 'LONG' if hunt_type == 'DIRECTIONAL_SHORT' else 'SHORT'
                    self.reasoning_chain.append(f"  - [REVERSAL OPPORTUNITY] Potential reversal detected after {hunt_type.lower()} with LCI={lci_score:.2f}, taker_ratio={taker_ratio:.2f}")
            else:
                self.reasoning_chain.append(f"  - [INFO] Skip stop hunt reversal check: taker_ratio data unavailable")

        # Check for momentum contradiction with overall trend
        momentum_trend_conflict = False
        if market_intel.trend_direction == 'downtrend' and recent_bullish_breaks >= 2:
            momentum_trend_conflict = True
            self.reasoning_chain.append(f"  - [WARNING] Recent momentum ({recent_bullish_breaks} bullish breaks) contradicts downtrend.")
        elif market_intel.trend_direction == 'uptrend' and recent_bearish_breaks >= 2:
            momentum_trend_conflict = True
            self.reasoning_chain.append(f"  - [WARNING] Recent momentum ({recent_bearish_breaks} bearish breaks) contradicts uptrend.")

        # NEW: Dynamic contextual weighting for micro-scalping (LTF focus)
        # Since this is micro-scalping (0.5%-1% moves, 0.3% SL), LTF signals dominate
        # HTF factors get reduced weight since they're for larger moves
        base_trend_strength = market_intel.trend_strength  # Value between 0 and 1
        
        # Calculate conflict severity score for contradictory factors (LTF-focused)
        conflict_severity_score = 0
        if has_doji_pattern:
            # Doji patterns - can indicate indecision, but context matters
            # In a clear trend, a Doji might just be temporary pause
            doji_impact = 12  # Lower impact for micro moves in trend
            conflict_severity_score += doji_impact
            self.reasoning_chain.append(f"  - [LTF SIGNAL] Doji pattern detected, impact: +{doji_impact} points")
        if momentum_trend_conflict:
            # LTF momentum contradiction - very important, but consider trend strength
            # If overall trend is strong and this is just a temporary counter move, lower impact
            base_momentum_impact = 25
            # Reduce impact if trend is strong (>70%) and momentum conflict is minor
            if market_intel.trend_strength > 0.70 and recent_bullish_breaks < 3: # For downtrend example
                base_momentum_impact = 15  # Lower impact if trend is strong
            momentum_impact = base_momentum_impact
            conflict_severity_score += momentum_impact
            self.reasoning_chain.append(f"  - [LTF CONFLICT] Momentum contradiction detected, impact: +{momentum_impact} points (adjusting for trend strength)")
        if htf_context_conflict:
            # HTF conflicts - much less weight for micro-scalping since LTF dominates
            htf_impact = 5  # Even lower impact for micro moves - LTF trend is primary
            conflict_severity_score += htf_impact
            self.reasoning_chain.append(f"  - [HTF-LTF INFO] HTF/LTF misaligned, impact: +{htf_impact} points (LTF dominates micro moves)")
        if has_threatening_bearish_pattern or has_threatening_bullish_pattern:
            # Threatening patterns - important for LTF
            threat_impact = 18  # Fixed impact
            conflict_severity_score += threat_impact
            self.reasoning_chain.append(f"  - [LTF CONFLICT] Threatening pattern detected, impact: +{threat_impact} points")

        # NEW: Calculate confluence score for confirming LTF factors
        # Look for confirming momentum patterns
        confirming_momentum_count = 0
        if market_intel.trend_direction == 'downtrend':
            confirming_momentum_count = sum(1 for p in recent_patterns if p.get('type') == 'BEARISH_BREAK')
        else:  # uptrend
            confirming_momentum_count = sum(1 for p in recent_patterns if p.get('type') == 'BULLISH_BREAK')
        
        confluence_score = 0
        if confirming_momentum_count >= 1:  # Even 1 confirming break helps
            # Confirming momentum breaks - important for micro moves
            momentum_confluence = 15 * min(2, confirming_momentum_count)  # 15 per break, max 30 for 2+
            confluence_score += momentum_confluence
            self.reasoning_chain.append(f"  - [LTF CONFIRMATION] {confirming_momentum_count} confirming momentum breaks, impact: +{momentum_confluence} points")
        
        # Consider trend strength as confluence (strong trends continue more often)
        if market_intel.trend_strength > 0.70:
            trend_strength_confluence = int(10 * market_intel.trend_strength)  # 7-10 points for strong trends
            confluence_score += trend_strength_confluence
            self.reasoning_chain.append(f"  - [TREND STRENGTH] Strong trend ({market_intel.trend_strength:.0%}), impact: +{trend_strength_confluence} points")
        
        # HTF/LTF alignment confluence (less important for micro moves)
        if not htf_context_conflict and market_intel.trend_direction == 'downtrend' and is_in_premium:
            # Downtrend + in premium zone = some confluence for continuation
            htf_confluence = 8  # Slightly higher impact
            confluence_score += htf_confluence
            self.reasoning_chain.append(f"  - [HTF-LTF INFO] HTF/LTF aligned in premium zone, impact: +{htf_confluence} points")
        elif not htf_context_conflict and market_intel.trend_direction == 'uptrend' and is_in_discount:
            # Uptrend + in discount zone = some confluence for continuation
            htf_confluence = 8  # Slightly higher impact
            confluence_score += htf_confluence
            self.reasoning_chain.append(f"  - [HTF-LTF INFO] HTF/LTF aligned in discount zone, impact: +{htf_confluence} points")

        # NEW: Apply dynamic adjustment based on stop hunt reversal opportunities
        # These are important even for micro moves when they align with LTF
        if potential_stop_hunt_reversal:
            # If we detect a reversal opportunity after a stop hunt, increase confidence in reversal
            if stop_hunt_reversal_direction and (
                (stop_hunt_reversal_direction == 'LONG' and market_intel.trend_direction == 'downtrend') or
                (stop_hunt_reversal_direction == 'SHORT' and market_intel.trend_direction == 'uptrend')
            ):
                # This is a prime reversal opportunity after directional hunt
                hunt_impact = 25  # Lower impact for micro moves than before
                self.reasoning_chain.append(f"  - [REVERSAL OPPORTUNITY] Capitalizing on {stop_hunt_reversal_direction} reversal after directional hunt, impact: +{hunt_impact} points")
                conflict_severity_score += hunt_impact  # Opportunity after manipulation

        # --- PRIMARY LOGIC: LTF-focused for micro-scalping ---
        # Net pressure = conflict - confluence (higher net = more reversal pressure)
        net_pressure_score = max(0, conflict_severity_score - confluence_score)
        
        if htf_trend_direction == "DOWNTREND":
            # In a downtrend, we are primarily looking for shorts.
            # A move into a premium zone is the classic continuation setup.
            if is_in_premium:
                # NEW: Enhanced checks for reversal threats with micro-scalping appropriate thresholds
                if has_threatening_bullish_pattern or has_doji_pattern:
                    # Very strong reversal signals
                    return "THREATENING_REVERSAL"
                elif net_pressure_score >= 22:  # Moderate net conflicts suggest reversal setup
                    return "REVERSAL_SETUP"
                elif net_pressure_score >= 10:  # Low-moderate conflicts
                    # Check if trend strength and momentum confluence offset minor conflicts
                    if market_intel.trend_strength > 0.70 and confluence_score >= 18:
                        # Strong trend continues despite minor conflicts
                        return "CONTINUATION_SETUP"  
                    else:
                        return "UNCLEAR"  # Not clear enough either way
                else:
                    # More confluence than conflicts
                    return "CONTINUATION_SETUP"
            
            # A move into a discount zone during a downtrend is a DEEP pullback.
            # This is NOT a signal to go long. It's a signal to be cautious or look for shorts if structure realigns.
            # For our trend-following brain, we'll treat this as a potential continuation as well, but perhaps with less conviction.
            if is_in_discount:
                # NEW: Check for contradictions with adjusted thresholds for micro-scalping
                if net_pressure_score >= 40:  # High net conflicts suggest reversal
                    return "THREATENING_REVERSAL"
                elif net_pressure_score >= 22:  # Moderate net conflicts suggest reversal setup
                    return "REVERSAL_SETUP"
                elif net_pressure_score >= 10:  # Low-moderate conflicts
                    # Check if trend strength and momentum confluence offset minor conflicts
                    if market_intel.trend_strength > 0.70 and confluence_score >= 18:
                        # Strong trend continues despite minor conflicts
                        return "CONTINUATION_SETUP"  
                    else:
                        return "UNCLEAR"  # Not clear enough either way
                else:
                    # More confluence than conflicts
                    return "CONTINUATION_SETUP"

        elif htf_trend_direction == "UPTREND":
            # In an uptrend, we are primarily looking for longs.
            # A move into a discount zone is the classic continuation setup.
            if is_in_discount:
                # NEW: Enhanced checks for reversal threats with micro-scalping appropriate thresholds
                if has_threatening_bearish_pattern or has_doji_pattern:
                    # Very strong reversal signals
                    return "THREATENING_REVERSAL"
                elif net_pressure_score >= 22:  # Moderate net conflicts suggest reversal setup
                    return "REVERSAL_SETUP"
                elif net_pressure_score >= 10:  # Low-moderate conflicts
                    # Check if trend strength and momentum confluence offset minor conflicts
                    if market_intel.trend_strength > 0.70 and confluence_score >= 18:
                        # Strong trend continues despite minor conflicts
                        return "CONTINUATION_SETUP"  
                    else:
                        return "UNCLEAR"  # Not clear enough either way
                else:
                    # More confluence than conflicts
                    return "CONTINUATION_SETUP"

            # A move into a premium zone during an uptrend is a DEEP rally.
            # This is NOT a signal to go short. It's a signal to be cautious.
            if is_in_premium:
                # NEW: Check for contradictions with adjusted thresholds for micro-scalping
                if net_pressure_score >= 40:  # High net conflicts suggest reversal
                    return "THREATENING_REVERSAL"
                elif net_pressure_score >= 22:  # Moderate net conflicts suggest reversal setup
                    return "REVERSAL_SETUP"
                elif net_pressure_score >= 10:  # Low-moderate conflicts
                    # Check if trend strength and momentum confluence offset minor conflicts
                    if market_intel.trend_strength > 0.70 and confluence_score >= 18:
                        # Strong trend continues despite minor conflicts
                        return "CONTINUATION_SETUP"  
                    else:
                        return "UNCLEAR"  # Not clear enough either way
                else:
                    # More confluence than conflicts
                    return "CONTINUATION_SETUP"

        # --- Fallback for Equilibrium or other states ---
        # If we are in equilibrium, the most recent LTF trend dictates the potential.
        # NEW: But also consider weighted contradiction factors
        if is_in_equilibrium and market_intel.trend_direction in ['uptrend', 'downtrend']:
            if conflict_severity_score >= 60:
                return "THREATENING_REVERSAL"  # High conflicts suggest major change
            elif conflict_severity_score >= 40:
                return "REVERSAL_SETUP"  # Moderate conflicts suggest opportunity
            elif has_doji_pattern or htf_context_conflict or momentum_trend_conflict:
                return "UNCLEAR"  # Mixed signals
            return "CONTINUATION_SETUP"

        # For decision making, consider the balance between conflicts and confluence
        # Using more balanced thresholds for micro-scalping
        if net_pressure_score >= 40:  # High net conflicts suggest reversal
            return "THREATENING_REVERSAL"
        elif net_pressure_score >= 22:  # Moderate net conflicts suggest reversal setup
            return "REVERSAL_SETUP"
        elif net_pressure_score >= 10:  # Low-moderate conflicts with some confluence
            # Check if trend strength and momentum confluence offset minor conflicts
            if market_intel.trend_strength > 0.70 and confluence_score >= 20:
                return "CONTINUATION_SETUP"  # Strong trend continues despite minor conflicts
            else:
                return "UNCLEAR"  # Not clear enough either way
        else:
            return "CONTINUATION_SETUP"  # More confluence than conflicts

    def _has_strong_reversal_signals(self, market_intel: MarketIntelligence) -> bool:
        """Check for strong reversal patterns that warrant threat status"""
        # Look for strong reversal patterns in structural integrity
        integrity_reasons = market_intel.structural_integrity_reasons or []
        
        strong_reversal_indicators = [
            'doji' in reason.lower() and 'potential reversal' in reason.lower()
            for reason in integrity_reasons
        ]
        
        # Check for threatening candlestick patterns
        threatening_patterns = [
            any(pattern in r.lower() for pattern in ['doji', 'engulfing', 'shooting star', 'hammer'])
            for r in integrity_reasons
            if 'bearish' in r.lower() or 'bullish' in r.lower()
        ]
        
        return sum(strong_reversal_indicators) >= 1 or sum(threatening_patterns) >= 1

    def _has_confirming_momentum(self, market_intel, direction: str) -> bool:
        """Simple: are recent breaks confirming the trend?"""
        recent_patterns = market_intel.candle_patterns[-3:] if market_intel.candle_patterns else []
        
        if direction == 'bearish':
            bearish_breaks = sum(1 for p in recent_patterns if 'BEARISH' in str(p.get('type', '')).upper())
            return bearish_breaks >= 2
        else:  # bullish
            bullish_breaks = sum(1 for p in recent_patterns if 'BULLISH' in str(p.get('type', '')).upper())
            return bullish_breaks >= 2

    def _has_exhaustion_signals(self, market_intel, trend_direction: str) -> bool:
        """Check for signs of trend exhaustion"""
        # Check for momentum divergence - opposite momentum building up
        recent_patterns = market_intel.candle_patterns[-5:] if market_intel.candle_patterns else []
        
        opposing_momentum = 0
        if trend_direction == 'downtrend':
            # Look for bullish momentum in downtrend
            opposing_momentum = sum(1 for p in recent_patterns if 'BULLISH' in str(p.get('type', '')).upper())
        else:  # uptrend
            # Look for bearish momentum in uptrend
            opposing_momentum = sum(1 for p in recent_patterns if 'BEARISH' in str(p.get('type', '')).upper())
        
        # Also check for multiple opposing sweeps
        opposing_sweeps = 0
        if market_intel.liquidity_sweeps:
            for sweep in market_intel.liquidity_sweeps[-3:]:  # Recent sweeps
                if (trend_direction == 'downtrend' and 'bullish' in str(sweep.type).lower()) or \
                   (trend_direction == 'uptrend' and 'bearish' in str(sweep.type).lower()):
                    opposing_sweeps += 1
        
        # If we have 2+ opposing signals, there might be exhaustion
        return opposing_momentum >= 2 or opposing_sweeps >= 1

    def _execute_reversal_tactic(self, market_intel: MarketIntelligence, btc_context: Optional[dict], correlation_score: Optional[float], lci_score: Optional[float], gls_score: Optional[float], breakout_signal: Optional[any] = None) -> IntelligentDecision:
        """Executes the patient, sniper logic for reversal setups in HTF discount/premium zones."""
        
        # NEW: Check if this reversal is after a directional stop hunt to optimize thesis
        stop_hunt_warning = market_intel.stop_hunt_warning
        hunt_type = getattr(stop_hunt_warning, 'hunt_type', 'NONE').upper()
        lci_score_val = lci_score if lci_score is not None else getattr(market_intel, 'lci_score', 0.5)
        taker_ratio = getattr(market_intel, 'taker_ratio', 1.0)
        
        # Determine thesis based on current conditions vs post-hunt reversal opportunities
        if hunt_type == 'DIRECTIONAL_LONG' and lci_score_val > 0.65 and taker_ratio is not None and taker_ratio < 0.85:
            # Longs were hunted, aggressive selling confirmed, look for SHORT reversal opportunity
            thesis = "SHORT"
            self.reasoning_chain.append(f"  - THESIS: After DIRECTIONAL_LONG hunt (LCI={lci_score_val:.2f}, taker={taker_ratio:.2f}), seeking {thesis} reversal opportunity.")
        elif hunt_type == 'DIRECTIONAL_SHORT' and lci_score_val is not None and lci_score_val < 0.35 and taker_ratio is not None and taker_ratio > 1.15:
            # Shorts were hunted, aggressive buying confirmed, look for LONG reversal opportunity  
            thesis = "LONG"
            self.reasoning_chain.append(f"  - THESIS: After DIRECTIONAL_SHORT hunt (LCI={lci_score_val:.2f}, taker={taker_ratio:.2f}), seeking {thesis} reversal opportunity.")
        else:
            # Normal reversal logic based on HTF context
            thesis = "LONG" if "Discount" in market_intel.htf_context['price_location'] else "SHORT"
            self.reasoning_chain.append(f"  - THESIS: Price is in a {market_intel.htf_context['price_location']} zone. Seeking a {thesis} reversal.")
        
        # Increase confidence when this is a validated post-hunt reversal opportunity
        if hunt_type in ['DIRECTIONAL_LONG', 'DIRECTIONAL_SHORT']:
            self.confidence += 0.25  # Higher boost for validated post-hunt reversal
            self.reasoning_chain.append(f"  - [REVERSAL OPPORTUNITY] Increased confidence for post-hunt reversal after {hunt_type.lower()}")
        else:
            self.confidence += 0.15  # Standard boost for normal reversal

        # Tier 1: Look for the strongest signal (CHOCH)
        has_ltf_confirmation = False
        ltf_reasons = market_intel.structural_integrity_reasons if market_intel.structural_integrity_reasons else []
        confirmation_strength = 0.0
        
        if not has_ltf_confirmation:
            if thesis == 'LONG':
                for reason in ltf_reasons:
                    if "bullish" in reason.lower() and "choch" in reason.lower():
                        confirmation_strength = 0.25
                        self.reasoning_chain.append(f"  - CONFIRMATION (STRONG): Bullish Change of Character found on LTF.")
                        has_ltf_confirmation = True
                        break
            elif thesis == 'SHORT':
                for reason in ltf_reasons:
                    if "bearish" in reason.lower() and "choch" in reason.lower():
                        confirmation_strength = 0.25
                        self.reasoning_chain.append(f"  - CONFIRMATION (STRONG): Bearish Change of Character found on LTF.")
                        has_ltf_confirmation = True
                        break

        # Tier 2: If no CHOCH, look for a confirming Break of Structure (BOS)
        if not has_ltf_confirmation:
            if thesis == 'LONG':
                for reason in ltf_reasons:
                    if "bullish" in reason.lower() and "bos" in reason.lower():
                        confirmation_strength = 0.15
                        self.reasoning_chain.append(f"  - CONFIRMATION (MEDIUM): Bullish Break of Structure found on LTF.")
                        has_ltf_confirmation = True
                        break
            elif thesis == 'SHORT':
                for reason in ltf_reasons:
                    if "bearish" in reason.lower() and "bos" in reason.lower():
                        confirmation_strength = 0.15
                        self.reasoning_chain.append(f"  - CONFIRMATION (MEDIUM): Bearish Break of Structure found on LTF.")
                        has_ltf_confirmation = True
                        break

        # Tier 3: Reaction from a Volume-Confirmed POI
        if not has_ltf_confirmation and market_intel.volume_profile_zones:
            poc = market_intel.volume_profile_zones.get('poc', 0)
            hvns = market_intel.volume_profile_zones.get('hvns', [])
            current_price = market_intel.current_price

            # Check if price is reacting from POC or HVN
            reacted_from_volume_zone = False
            if poc and abs(current_price - poc) / current_price < 0.001: # Price near POC
                reacted_from_volume_zone = True
            for hvn in hvns:
                if abs(current_price - hvn['price']) / current_price < 0.001: # Price near HVN
                    reacted_from_volume_zone = True
                    break
            
            if reacted_from_volume_zone:
                confirmation_strength = 0.10
                self.reasoning_chain.append(f"  - CONFIRMATION (MEDIUM): Price reacting from a Volume Profile zone (POC/HVN).")
                has_ltf_confirmation = True

        # Tier 4: HTF Fib Retracement Reaction
        if not has_ltf_confirmation and market_intel.htf_context and market_intel.htf_context.get('fib_levels'):
            fib_levels = market_intel.htf_context['fib_levels']
            current_price = market_intel.current_price
            
            reacted_from_fib = False
            for level_name, fib_price in fib_levels.items():
                if "fib_" in level_name and abs(current_price - fib_price) / current_price < 0.001: # Price near a Fib level
                    reacted_from_fib = True
                    break
            
            if reacted_from_fib:
                confirmation_strength = 0.08
                self.reasoning_chain.append(f"  - CONFIRMATION (MEDIUM-WEAK): Price reacting from a key HTF Fibonacci level.")
                has_ltf_confirmation = True

        # Tier 5: If still no strong confirmation, check for a very high integrity score
        if not has_ltf_confirmation and market_intel.structural_integrity_score > 90:
            confirmation_strength = 0.05
            self.reasoning_chain.append(f"  - CONFIRMATION (WEAK): LTF structure is very clean (Score > 90).")
            has_ltf_confirmation = True

        # Apply confidence boost and handle failure
        if has_ltf_confirmation:
            self.confidence += confirmation_strength
        else:
            self.reasoning_chain.append("  - NO CONFIRMATION: No strong LTF structural event found to confirm thesis. Standing aside.")
            return self._create_blocked_decision(market_intel.current_price, "No LTF Confirmation", self.reasoning_chain)
        # ... (add other confluences like BTC, LCI etc. here) ...

        # Formulate Plan
        sniper_data = self._calculate_sniper_entry_and_stop(market_intel, thesis)

        if not sniper_data:
            self.reasoning_chain.append(f"    [REJECT] No volume-confirmed Point of Interest (OB/FVG) found for entry/SL.")
            return self._create_blocked_decision(market_intel.current_price, "Could not formulate a valid sniper entry/exit plan", self.reasoning_chain)

        entry_price = sniper_data['entry']
        stop_loss = sniper_data['stop']
        self.reasoning_chain.append(f"    [ANCHOR] Trade anchored to {sniper_data['poi_type']} at ${sniper_data['poi_level']:.2f}")
        self.reasoning_chain.append(f"    [SNIPER ENTRY] Targeting entry at ${entry_price:.2f}")
        self.reasoning_chain.append(f"    [TIGHT STOP] Stop loss placed at ${stop_loss:.2f}")

        self.reasoning_chain.append(f"\n    [TP STRUCTURE] Analyzing targets for {thesis}...")
        risk = abs(entry_price - stop_loss)
        if risk == 0:
            return self._create_blocked_decision(market_intel.current_price, "Risk is zero, cannot calculate R:R", self.reasoning_chain)

        tp1 = self._scan_high_impact_zones(market_intel, thesis, entry_price, self.reasoning_chain)

        if tp1 is None:
            self.reasoning_chain.append(f"    [REJECT] Could not determine a valid Take Profit level (TP1).")
            return self._create_blocked_decision(market_intel.current_price, "Could not determine TP1", self.reasoning_chain)

        if self.confidence >= 0.65:
            if thesis == 'LONG':
                further_swings = [s['price'] for s in market_intel.swing_highs if s['price'] > tp1 * 1.005]
                tp2 = min(further_swings) if further_swings else tp1 * 1.015
            else:  # thesis == 'SHORT'
                further_swings = [s['price'] for s in market_intel.swing_lows if s['price'] < tp1 * 0.995]
                tp2 = max(further_swings) if further_swings else tp1 * 0.985
            targets = [tp1, tp2]
            self.reasoning_chain.append(f"    [2-TP MODE] TP1: ${tp1:.2f} (50%), TP2: ${tp2:.2f} (50%)")
        else:
            targets = [tp1]
            self.reasoning_chain.append(f"    [1-TP MODE] Using single TP: ${tp1:.2f} (100%)")

        reward_tp1 = abs(targets[0] - entry_price)
        rr_tp1 = reward_tp1 / risk
        if len(targets) == 2:
            reward_tp2 = abs(targets[1] - entry_price)
            rr_tp2 = reward_tp2 / risk
            rr = (rr_tp1 * 0.5) + (rr_tp2 * 0.5)
            self.reasoning_chain.append(f"    TP1 RR: {rr_tp1:.2f}:1, TP2 RR: {rr_tp2:.2f}:1")
            self.reasoning_chain.append(f"    Blended RR: {rr:.2f}:1")
        else:
            rr = rr_tp1
            self.reasoning_chain.append(f"    Single TP RR: {rr:.2f}:1")

        entry_exit_data = {
            'entry_zone': (entry_price, entry_price),
            'stop_loss': stop_loss,
            'take_profits': targets,
            'risk_reward': rr,
        }
        if not entry_exit_data:
            return self._create_blocked_decision(market_intel.current_price, "Could not formulate a valid sniper entry/exit plan", self.reasoning_chain)

        return self._build_final_decision(market_intel, thesis, entry_exit_data, lci_score, gls_score)

    def _execute_continuation_tactic(self, market_intel: MarketIntelligence, btc_context: Optional[dict], correlation_score: Optional[float], lci_score: Optional[float], gls_score: Optional[float], confidence: float, breakout_signal: Optional[any] = None, taker_ratio: Optional[float] = None, taker_ratio_ma: Optional[float] = None) -> IntelligentDecision:
        """Executes the aggressive, momentum logic for trend continuation setups, with scalping optimization."""
        thesis = f"Price has reacted from HTF zone and shows continuation structure. Seeking aggressive {market_intel.trend_direction.upper()} entry."
        logger.info(f"  - THESIS: {thesis}")

        direction = 'SHORT' if market_intel.trend_direction == 'downtrend' else 'LONG'

        # --- TACTIC SELECTION ---
        # Choose between aggressive momentum scalp or precise sniper entry
        is_momentum_scalp = confidence < 0.75 and market_intel.trend_strength >= 0.60
        is_sniper_entry = confidence >= 0.75

        # Default values
        stop_loss = None
        take_profits = []
        blended_rr = 0

        # --- TACTIC EXECUTION ---
        if is_momentum_scalp:
            self.reasoning_chain.append(f"\n    [MOMENTUM SCALP ENTRY] Calculating aggressive entry and fixed R:R TP...")
            # NEW: Check if we're scaling into a reversal opportunity after directional hunt
            is_reversal_opportunity = False
            if hasattr(market_intel, 'stop_hunt_warning') and market_intel.stop_hunt_warning:
                hunt_type = getattr(market_intel.stop_hunt_warning, 'hunt_type', 'NONE').upper()
                if (hunt_type == 'DIRECTIONAL_LONG' and thesis == 'SHORT') or (hunt_type == 'DIRECTIONAL_SHORT' and thesis == 'LONG'):
                    is_reversal_opportunity = True
                    self.reasoning_chain.append(f"    - [REVERSAL SCALP] Scaling into reversal opportunity after {hunt_type.lower()}")
            
            entry_price = market_intel.current_price # Enter immediately
            
            # Tight stop behind the most recent micro-swing
            if thesis == 'LONG' or thesis == 'UPTREND':
                if not market_intel.swing_lows: 
                    return self._create_blocked_decision(market_intel.current_price, "No recent swing low for scalp SL", self.reasoning_chain)
                stop_loss = market_intel.swing_lows[-1]['price'] * 0.999 # 0.1% buffer
                # Ensure stop loss is below entry price for LONG (in case swing low is at or above current price)
                entry_price = market_intel.current_price
                stop_loss = min(stop_loss, entry_price * 0.997)  # Ensure at least 0.3% below entry
            else: # SHORT or DOWNTREND
                if not market_intel.swing_highs: 
                    return self._create_blocked_decision(market_intel.current_price, "No recent swing high for scalp SL", self.reasoning_chain)
                # For SHORT, ensure stop loss is above entry price to properly protect the position
                swing_high_based_sl = market_intel.swing_highs[-1]['price'] * 1.001
                # Make sure stop loss is above the entry price for SHORT (since losses happen when price goes up)
                entry_price = market_intel.current_price
                stop_loss = max(swing_high_based_sl, entry_price * 1.003)  # At least 0.3% above entry
            
            risk = abs(entry_price - stop_loss)
            if risk == 0 or risk < (entry_price * 0.0005): # Minimum 0.05% risk
                self.reasoning_chain.append(f"    [REJECT] Scalp SL too tight or zero risk. Invalid trade plan.")
                return self._create_blocked_decision(market_intel.current_price, "Scalp SL too tight", self.reasoning_chain)

            # Fixed 1.5R Take Profit for scalping
            reward_ratio = 1.5
            if thesis == 'LONG' or thesis == 'UPTREND':
                tp1 = entry_price + (risk * reward_ratio)
            else:
                tp1 = entry_price - (risk * reward_ratio)
            
            targets = [tp1]
            rr = reward_ratio

            self.reasoning_chain.append(f"    [SCALPING TP] Using fixed {reward_ratio}R target: ${tp1:.2f}")
            self.reasoning_chain.append(f"    [AGGRESSIVE ENTRY] Entry: ${entry_price:.2f}, SL: ${stop_loss:.2f}, TP: ${tp1:.2f}")
            self.reasoning_chain.append(f"    [FINAL RR] {rr:.2f}:1")

            # For momentum scalp, apply capping logic to targets
            max_sl_pct = 0.003  # 0.3%
            min_tp_pct = 0.005  # 0.5%
            max_tp_pct = 0.01   # 1.0%
            fallback_tp_pct = 0.007 # 0.7%

            # Capping Stop Loss (momentum scalp specific)
            max_sl_distance = market_intel.current_price * max_sl_pct
            if direction == 'LONG':
                # SL should be below entry, so max(current_price - distance, calculated_sl) - ensures SL doesn't go above safe distance below
                # Ensure that stop_loss doesn't go above entry_price for LONG trades
                capped_sl = max(market_intel.current_price - max_sl_distance, stop_loss)
                # Additional safety: ensure stop loss is below entry price for LONG
                if entry_price is not None:
                    capped_sl = min(capped_sl, entry_price * 0.999)  # Cap below entry for LONG
            else: # SHORT
                # SL should be above entry, so min(current_price + distance, calculated_sl) - ensures SL doesn't go too far above
                capped_sl = min(market_intel.current_price + max_sl_distance, stop_loss)  # Fixed: should use min to cap the distance above
                # Additional safety: ensure stop loss is above entry price for SHORT
                if entry_price is not None:
                    capped_sl = max(capped_sl, entry_price * 1.001)  # Cap above entry for SHORT
            stop_loss = capped_sl
            logger.info(f"[RISK_CAP] SL capped at {max_sl_pct*100:.1f}% from entry: ${stop_loss:.2f}")

            # Capping Take Profit (momentum scalp specific)
            final_targets = []
            for tp in targets:
                min_tp_value = market_intel.current_price * (1 + min_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - min_tp_pct)
                max_tp_value = market_intel.current_price * (1 + max_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - max_tp_pct)
                fallback_tp_value = market_intel.current_price * (1 + fallback_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - fallback_tp_pct)

                capped_tp = tp
                if direction == 'LONG':
                    if tp < min_tp_value:
                        capped_tp = min_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted up to minimum {min_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                    elif tp > max_tp_value:
                        capped_tp = max_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted down to maximum {max_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                else: # SHORT
                    if tp > min_tp_value:
                        capped_tp = min_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted down to minimum {min_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                    elif tp < max_tp_value:
                        capped_tp = max_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted up to maximum {max_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                final_targets.append(capped_tp)
            targets = final_targets

            # Fallback for TP if no POI was found (or if it was too close)
            if not targets or abs(targets[0] - market_intel.current_price) < market_intel.current_price * min_tp_pct:
                fallback_tp = market_intel.current_price * (1 + fallback_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - fallback_tp_pct)
                targets = [fallback_tp]
                logger.info(f"[RISK_CAP] No suitable TP found or too close. Using {fallback_tp_pct*100:.1f}% fallback TP: ${targets[0]:.2f}")

            # Recalculate RR after capping (for momentum scalp)
            risk_per_unit = abs(entry_price - stop_loss)  # Use entry_price instead of market_intel.current_price
            reward_per_unit_tp1 = abs(targets[0] - entry_price)
            if risk_per_unit > 0:
                rr_tp1 = reward_per_unit_tp1 / risk_per_unit
            else:
                rr_tp1 = 999.0 # Effectively infinite RR if SL is at entry

            if len(targets) > 1:
                reward_per_unit_tp2 = abs(targets[1] - entry_price)
                if risk_per_unit > 0:
                    rr_tp2 = reward_per_unit_tp2 / risk_per_unit
                else:
                    rr_tp2 = 999.0
                blended_rr = (rr_tp1 * 0.5) + (rr_tp2 * 0.5)
                logger.info(f"[FINAL RR] TP1 RR: {rr_tp1:.2f}:1, TP2 RR: {rr_tp2:.2f}:1")
            else:
                blended_rr = rr_tp1
                logger.info(f"[FINAL RR] {blended_rr:.2f}:1")

            logger.info(f"[AGGRESSIVE ENTRY] Entry: ${entry_price:.2f}, SL: ${stop_loss:.2f}, TP: ${targets[0]:.2f}")
            logger.info(f"[FINAL RR] {blended_rr:.2f}:1")

            # Create entry_exit_data dictionary to pass to _build_final_decision
            entry_exit_data = {
                'entry_zone': (entry_price, entry_price),
                'stop_loss': stop_loss,
                'take_profits': targets,
                'risk_reward': blended_rr,
            }
            
            # Use the helper method to build the final decision
            return self._build_final_decision(market_intel, direction, entry_exit_data, lci_score, gls_score)

        else: # Standard Sniper Entry/Exit
            self.reasoning_chain.append(f"\n    [ENTRY & SL LOGIC] Using Sniper method...")
            sniper_data = self._calculate_sniper_entry_and_stop(market_intel, thesis)

            if not sniper_data:
                return self._create_blocked_decision(market_intel.current_price, "Could not formulate a valid sniper entry/exit plan", self.reasoning_chain)

            entry_price = sniper_data['entry']
            stop_loss = sniper_data['stop']
            self.reasoning_chain.append(f"    [ANCHOR] Trade anchored to {sniper_data['poi_type']} at ${sniper_data['poi_level']:.2f}")
            self.reasoning_chain.append(f"    [SNIPER ENTRY] Targeting entry at ${entry_price:.2f}")
            self.reasoning_chain.append(f"    [TIGHT STOP] Stop loss placed at ${stop_loss:.2f}")

            self.reasoning_chain.append(f"\n    [TP STRUCTURE] Analyzing targets for {direction}...")
            risk = abs(entry_price - stop_loss)
            min_risk_threshold = entry_price * 0.0005 # 0.05% minimum risk
            if risk < min_risk_threshold:
                self.reasoning_chain.append(f"    [REJECT] Calculated risk (${risk:.4f}) is below minimum threshold of ${min_risk_threshold:.4f}. Invalid trade plan.")
                return self._create_blocked_decision(market_intel.current_price, "Risk is too small, cannot calculate R:R", self.reasoning_chain)

            tp1 = self._scan_high_impact_zones(market_intel, direction, entry_price, self.reasoning_chain)

            if tp1 is None:
                self.reasoning_chain.append(f"    [REJECT] Could not determine a valid Take Profit level (TP1).")
                return self._create_blocked_decision(market_intel.current_price, "Could not determine TP1", self.reasoning_chain)

            if self.confidence >= 0.65:
                if direction == 'LONG':
                    further_swings = [s['price'] for s in market_intel.swing_highs if s['price'] > tp1 * 1.005]
                    tp2 = min(further_swings) if further_swings else tp1 * 1.015
                else:
                    further_swings = [s['price'] for s in market_intel.swing_lows if s['price'] < tp1 * 0.995]
                    tp2 = max(further_swings) if further_swings else tp1 * 0.985
                targets = [tp1, tp2]
                self.reasoning_chain.append(f"    [2-TP MODE] TP1: ${tp1:.2f} (50%), TP2: ${tp2:.2f} (50%)")
            else:
                targets = [tp1]
                self.reasoning_chain.append(f"    [1-TP MODE] Using single TP: ${tp1:.2f} (100%)")

            reward_tp1 = abs(targets[0] - entry_price)
            rr_tp1 = reward_tp1 / risk
            if len(targets) == 2:
                reward_tp2 = abs(targets[1] - entry_price)
                rr_tp2 = reward_tp2 / risk
                rr = (rr_tp1 * 0.5) + (rr_tp2 * 0.5)
                self.reasoning_chain.append(f"    TP1 RR: {rr_tp1:.2f}:1, TP2 RR: {rr_tp2:.2f}:1")
                self.reasoning_chain.append(f"    Blended RR: {rr:.2f}:1")
            else:
                rr = rr_tp1
                self.reasoning_chain.append(f"    Single TP RR: {rr:.2f}:1")

            # --- APPLY SL/TP CAPPING AND FALLBACKS ---
            max_sl_pct = 0.003  # 0.3%
            min_tp_pct = 0.005  # 0.5%
            max_tp_pct = 0.01   # 1.0%
            fallback_tp_pct = 0.007 # 0.7%

            # Capping Stop Loss
            max_sl_distance = market_intel.current_price * max_sl_pct
            if direction == 'LONG':
                # SL should be below entry, so max(current_price - distance, calculated_sl)
                # Ensure that stop_loss doesn't go above entry_price for LONG trades
                capped_sl = max(market_intel.current_price - max_sl_distance, stop_loss)
                # Additional safety: ensure stop loss is below entry price for LONG
                if entry_price is not None:
                    capped_sl = min(capped_sl, entry_price * 0.999)  # Cap below entry for LONG
            else: # SHORT
                # SL should be above entry, so min(current_price + distance, calculated_sl)
                capped_sl = min(market_intel.current_price + max_sl_distance, stop_loss)  # Fixed: should use min to cap the distance above
                # Additional safety: ensure stop loss is above entry price for SHORT
                if entry_price is not None:
                    capped_sl = max(capped_sl, entry_price * 1.001)  # Cap above entry for SHORT
            stop_loss = capped_sl
            logger.info(f"[RISK_CAP] SL capped at {max_sl_pct*100:.1f}% from entry: ${stop_loss:.2f}")

            # Capping Take Profit
            final_targets = []
            for tp in targets:
                min_tp_value = market_intel.current_price * (1 + min_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - min_tp_pct)
                max_tp_value = market_intel.current_price * (1 + max_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - max_tp_pct)
                fallback_tp_value = market_intel.current_price * (1 + fallback_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - fallback_tp_pct)

                capped_tp = tp
                if direction == 'LONG':
                    if tp < min_tp_value:
                        capped_tp = min_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted up to minimum {min_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                    elif tp > max_tp_value:
                        capped_tp = max_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted down to maximum {max_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                else: # SHORT
                    if tp > min_tp_value:
                        capped_tp = min_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted down to minimum {min_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                    elif tp < max_tp_value:
                        capped_tp = max_tp_value
                        logger.info(f"[RISK_CAP] TP adjusted up to maximum {max_tp_pct*100:.1f}% from entry: ${capped_tp:.2f}")
                final_targets.append(capped_tp)
            targets = final_targets

            # Fallback for TP if no POI was found (or if it was too close)
            if not targets or abs(targets[0] - market_intel.current_price) < market_intel.current_price * min_tp_pct:
                fallback_tp = market_intel.current_price * (1 + fallback_tp_pct) if direction == 'LONG' else market_intel.current_price * (1 - fallback_tp_pct)
                targets = [fallback_tp]
                logger.info(f"[RISK_CAP] No suitable TP found or too close. Using {fallback_tp_pct*100:.1f}% fallback TP: ${targets[0]:.2f}")

            # Recalculate RR after capping, ensuring correct risk calculation based on trade direction
            if direction == 'LONG':
                # For LONG, stop loss should be below entry price
                risk_per_unit = entry_price - stop_loss
            else:  # SHORT
                # For SHORT, stop loss should be above entry price  
                risk_per_unit = stop_loss - entry_price
            
            # Ensure we have a positive risk value
            risk_per_unit = abs(risk_per_unit)
            
            # Validate that risk is positive and meaningful
            if risk_per_unit <= 0:
                self.reasoning_chain.append(f"    [REJECT] Invalid risk calculation: entry={entry_price}, stop_loss={stop_loss}, risk={risk_per_unit}")
                return self._create_blocked_decision(market_intel.current_price, "Invalid risk calculation", self.reasoning_chain)

            reward_per_unit_tp1 = abs(targets[0] - entry_price)
            rr_tp1 = reward_per_unit_tp1 / risk_per_unit

            if len(targets) > 1:
                reward_per_unit_tp2 = abs(targets[1] - entry_price)
                rr_tp2 = reward_per_unit_tp2 / risk_per_unit
                blended_rr = (rr_tp1 + rr_tp2) / 2
                logger.info(f"[FINAL RR] TP1 RR: {rr_tp1:.2f}:1, TP2 RR: {rr_tp2:.2f}:1")
            else:
                blended_rr = rr_tp1
                logger.info(f"[FINAL RR] {blended_rr:.2f}:1")

            logger.info(f"[AGGRESSIVE ENTRY] Entry: ${entry_price:.2f}, SL: ${stop_loss:.2f}, TP: ${targets[0]:.2f}")
            logger.info(f"[FINAL RR] {blended_rr:.2f}:1")

            # Create entry_exit_data dictionary to pass to _build_final_decision
            entry_exit_data = {
                'entry_zone': (entry_price, entry_price),
                'stop_loss': stop_loss,
                'take_profits': targets,
                'risk_reward': blended_rr,
            }
            
            # Use the helper method to build the final decision
            return self._build_final_decision(market_intel, direction, entry_exit_data, lci_score, gls_score)

    def _calculate_sniper_entry_and_stop(self, market_intel: MarketIntelligence, direction: str) -> Optional[Dict]:
        """
        Finds a high-probability, volume-confirmed Point of Interest (POI) to define
        a sniper entry and then applies the Hybrid Risk Model for the stop loss.
        Uses flexible filtering to find nearby POIs.
        """
        poi = None
        current_price = market_intel.current_price
        volume_zones = market_intel.volume_profile_zones
        max_distance_pct = 0.005  # 0.5%

        # NEW: Add initial check for any POIs to provide clearer feedback
        if not market_intel.order_blocks and not market_intel.fvgs:
            self.reasoning_chain.append("    - [SNIPER REJECT] No Order Blocks or FVGs were found in the current market analysis.")
            return None

        def is_volume_confirmed(poi_top: float, poi_bottom: float) -> bool:
            if not volume_zones:
                return False
            poc = volume_zones.get('poc', 0)
            hvns = volume_zones.get('hvns', [])
            if poc >= poi_bottom and poc <= poi_top:
                self.reasoning_chain.append(f"    - [VOLUME CONFIRMED] POI overlaps with Point of Control (POC) at ${poc:.2f}")
                return True
            for hvn in hvns:
                hvn_price = hvn['price']
                if hvn_price >= poi_bottom and hvn_price <= poi_top:
                    self.reasoning_chain.append(f"    - [VOLUME CONFIRMED] POI overlaps with High-Volume Node (HVN) at ${hvn_price:.2f}")
                    return True
            return False

        min_sl_pct = 0.001  # 0.1%
        max_sl_pct = 0.003  # 0.3%

        if direction == 'LONG' or direction == 'UPTREND':
            bullish_obs = [ob for ob in market_intel.order_blocks if ob.type == 'bullish' and abs(current_price - ob.entry_zone_high) / current_price < max_distance_pct]
            bullish_fvgs = [fvg for fvg in market_intel.fvgs if fvg.gap_type == 'bullish' and abs(current_price - fvg.gap_end) / current_price < max_distance_pct]
            potential_pois = sorted(bullish_obs + bullish_fvgs, key=lambda x: x.entry_zone_high if hasattr(x, 'entry_zone_high') else x.gap_end, reverse=True)
            
            if not potential_pois:
                self.reasoning_chain.append(f"    - [SNIPER REJECT] No bullish POIs (Order Blocks or FVGs) found within {max_distance_pct:.1%} of the current price (${current_price:.2f}).")
                return None

            for poi in potential_pois:
                poi_top = poi.entry_zone_high if hasattr(poi, 'entry_zone_high') else poi.gap_end
                poi_bottom = poi.entry_zone_low if hasattr(poi, 'entry_zone_low') else poi.gap_start
                poi_type = "Bullish OB" if hasattr(poi, 'entry_zone_high') else "Bullish FVG"
                if is_volume_confirmed(poi_top, poi_bottom):
                    self.confidence += 0.1
                    buffer = abs(poi_top - poi_bottom) * 0.1
                    entry_price = poi_top
                    structural_sl = poi_bottom - buffer
                    sl_pct_distance = abs(structural_sl - entry_price) / entry_price
                    final_sl = structural_sl
                    if sl_pct_distance > max_sl_pct:
                        self.reasoning_chain.append(f"    - [RISK WARNING] Structural SL ({sl_pct_distance:.2%}) exceeds max risk ({max_sl_pct:.2%}). Using fallback.")
                        if direction == 'LONG' or direction == 'UPTREND':
                            final_sl = entry_price * (1 - max_sl_pct)
                        else:  # SHORT or DOWNTREND
                            final_sl = entry_price * (1 + max_sl_pct)
                    elif sl_pct_distance < min_sl_pct:
                        self.reasoning_chain.append(f"    - [RISK WARNING] Structural SL ({sl_pct_distance:.2%}) is too tight. Using minimum risk ({min_sl_pct:.2%}).")
                        if direction == 'LONG' or direction == 'UPTREND':
                            final_sl = entry_price * (1 - min_sl_pct)
                        else:  # SHORT or DOWNTREND
                            final_sl = entry_price * (1 + min_sl_pct)
                    else:
                        self.reasoning_chain.append(f"    - [RISK OK] Structural SL ({sl_pct_distance:.2%}) is within risk band ({min_sl_pct:.2%}-{max_sl_pct:.2%}).")
                    
                    # Additional safety check to ensure correct relationship between SL and entry price
                    if direction == 'LONG' or direction == 'UPTREND':
                        # For LONG, SL must be below entry
                        if final_sl >= entry_price:
                            final_sl = entry_price * 0.999  # Ensure SL is below entry
                            self.reasoning_chain.append(f"    - [SAFETY] SL corrected to below entry for LONG: ${final_sl:.4f}")
                    else:  # SHORT or DOWNTREND
                        # For SHORT, SL must be above entry
                        if final_sl <= entry_price:
                            final_sl = entry_price * 1.001  # Ensure SL is above entry
                            self.reasoning_chain.append(f"    - [SAFETY] SL corrected to above entry for SHORT: ${final_sl:.4f}")
                    
                    return {'entry': entry_price, 'stop': final_sl, 'poi_type': poi_type, 'poi_level': entry_price}
                else:
                    self.reasoning_chain.append(f"    - [REJECTED POI] {poi_type} at ${poi_top:.2f} lacks volume confirmation.")
        elif direction == 'SHORT' or direction == 'DOWNTREND':
            bearish_obs = [ob for ob in market_intel.order_blocks if ob.type == 'bearish' and abs(current_price - ob.entry_zone_low) / current_price < max_distance_pct]
            bearish_fvgs = [fvg for fvg in market_intel.fvgs if fvg.gap_type == 'bearish' and abs(current_price - fvg.gap_start) / current_price < max_distance_pct]
            potential_pois = sorted(bearish_obs + bearish_fvgs, key=lambda x: x.entry_zone_low if hasattr(x, 'entry_zone_low') else x.gap_start)

            if not potential_pois:
                self.reasoning_chain.append(f"    - [SNIPER REJECT] No bearish POIs (Order Blocks or FVGs) found within {max_distance_pct:.1%} of the current price (${current_price:.2f}).")
                return None

            for poi in potential_pois:
                poi_top = poi.entry_zone_high if hasattr(poi, 'entry_zone_high') else poi.gap_end
                poi_bottom = poi.entry_zone_low if hasattr(poi, 'entry_zone_low') else poi.gap_start
                poi_type = "Bearish OB" if hasattr(poi, 'entry_zone_low') else "Bearish FVG"
                if is_volume_confirmed(poi_top, poi_bottom):
                    self.confidence += 0.1
                    buffer = abs(poi_top - poi_bottom) * 0.1
                    entry_price = poi_bottom
                    structural_sl = poi_top + buffer
                    sl_pct_distance = abs(structural_sl - entry_price) / entry_price
                    final_sl = structural_sl
                    if sl_pct_distance > max_sl_pct:
                        self.reasoning_chain.append(f"    - [RISK WARNING] Structural SL ({sl_pct_distance:.2%}) exceeds max risk ({max_sl_pct:.2%}). Using fallback.")
                        if direction == 'LONG' or direction == 'UPTREND':
                            final_sl = entry_price * (1 - max_sl_pct)
                        else:  # SHORT or DOWNTREND
                            final_sl = entry_price * (1 + max_sl_pct)
                    elif sl_pct_distance < min_sl_pct:
                        self.reasoning_chain.append(f"    - [RISK WARNING] Structural SL ({sl_pct_distance:.2%}) is too tight. Using minimum risk ({min_sl_pct:.2%}).")
                        if direction == 'LONG' or direction == 'UPTREND':
                            final_sl = entry_price * (1 - min_sl_pct)
                        else:  # SHORT or DOWNTREND
                            final_sl = entry_price * (1 + min_sl_pct)
                    else:
                        self.reasoning_chain.append(f"    - [RISK OK] Structural SL ({sl_pct_distance:.2%}) is within risk band ({min_sl_pct:.2%}-{max_sl_pct:.2%}).")
                    
                    # Additional safety check to ensure correct relationship between SL and entry price
                    if direction == 'LONG' or direction == 'UPTREND':
                        # For LONG, SL must be below entry
                        if final_sl >= entry_price:
                            final_sl = entry_price * 0.999  # Ensure SL is below entry
                            self.reasoning_chain.append(f"    - [SAFETY] SL corrected to below entry for LONG: ${final_sl:.4f}")
                    else:  # SHORT or DOWNTREND
                        # For SHORT, SL must be above entry
                        if final_sl <= entry_price:
                            final_sl = entry_price * 1.001  # Ensure SL is above entry
                            self.reasoning_chain.append(f"    - [SAFETY] SL corrected to above entry for SHORT: ${final_sl:.4f}")
                    
                    return {'entry': entry_price, 'stop': final_sl, 'poi_type': poi_type, 'poi_level': entry_price}
                else:
                    self.reasoning_chain.append(f"    - [REJECTED POI] {poi_type} at ${poi_bottom:.2f} lacks volume confirmation.")
        
        # NEW: Add a final fallback message if no volume-confirmed POIs were found after checking all potential ones.
        self.reasoning_chain.append(f"    - [SNIPER REJECT] All potential POIs were checked, but none had sufficient volume confirmation.")
        return None

    def _apply_original_volatility_calculation(self, market_intel):
        """Helper method to apply the original volatility calculation as fallback"""
        # Calculate volatility from recent swing movements since candle_patterns don't contain OHLC data
        if market_intel.swing_highs or market_intel.swing_lows:
            # Calculate average range from recent swings if available
            recent_swings = []

            # Get recent swing highs and lows (up to last 5 of each)
            recent_highs = market_intel.swing_highs[-5:] if len(market_intel.swing_highs) > 0 else []
            recent_lows = market_intel.swing_lows[-5:] if len(market_intel.swing_lows) > 0 else []

            # Calculate ranges from swings
            for swing in recent_highs:
                if 'high' in swing and 'low' in swing:
                    recent_swings.append(swing['high'] - swing['low'])
                elif 'price' in swing and 'low' in swing:
                    recent_swings.append(swing['price'] - swing['low'])
                elif 'high' in swing and 'price' in swing:
                    recent_swings.append(swing['high'] - swing['price'])
                elif 'price' in swing and 'close' in swing:
                    recent_swings.append(abs(swing['price'] - swing['close']))

            for swing in recent_lows:
                if 'high' in swing and 'low' in swing:
                    recent_swings.append(swing['high'] - swing['low'])
                elif 'price' in swing and 'high' in swing:
                    recent_swings.append(swing['high'] - swing['price'])
                elif 'price' in swing and 'close' in swing:
                    recent_swings.append(abs(swing['close'] - swing['price']))

            # If we don't have swings with proper high/low data, try to get from recent candle_patterns (for break distances)
            if not recent_swings and market_intel.candle_patterns and len(market_intel.candle_patterns) >= 3:
                recent_patterns = market_intel.candle_patterns[-5:]
                for p in recent_patterns:
                    if 'break_distance' in p:
                        recent_swings.append(p['break_distance'])
                    elif 'break_pct' in p and market_intel.current_price:
                        # Calculate approximate range from percentage
                        recent_swings.append((p['break_pct'] / 100) * market_intel.current_price)

            if recent_swings:
                avg_range = sum(recent_swings) / len(recent_swings)
                current_price = market_intel.current_price
                if current_price > 0:
                    volatility_pct = (avg_range / current_price) * 100
                    if volatility_pct > 5.0:  # Very high volatility
                        self.reasoning_chain.append(f"  - [VOLATILITY WARNING] Very high volatility ({volatility_pct:.2f}%), reducing confidence for scalp")
                        self.confidence = max(0.10, self.confidence - 0.10)  # Reduce by 10%
                    elif volatility_pct < 0.5:  # Extremely low volatility
                        self.reasoning_chain.append(f"  - [VOLATILITY ASSESSMENT] Extremely low volatility ({volatility_pct:.2f}%), checking trend context...")
                        # CRITICAL FIX: In a strong trend, low volatility often indicates a pullback opportunity, not danger!
                        if market_intel.trend_strength > 0.6 and market_intel.trend_direction in ['uptrend', 'downtrend']:
                            self.reasoning_chain.append(f"  - [VOLATILITY OPPORTUNITY] Strong trend ({market_intel.trend_strength:.0%}) with low volatility = pullback opportunity!")
                            self.confidence = min(1.0, self.confidence + 0.08)  # Boost confidence for pullback opportunity
                        elif market_intel.trend_strength < 0.4:  # Weak trend + low volatility = truly stagnant
                            self.reasoning_chain.append(f"  - [VOLATILITY WARNING] Weak trend with low volatility = ranging/market may be stagnant")
                            self.confidence = max(0.15, self.confidence - 0.05)  # Reduce by 5%
                        else:
                            # Moderate trend + low volatility = either continuation pullback or weakening trend
                            self.reasoning_chain.append(f"  - [VOLATILITY INFO] Moderate trend with low volatility, monitoring for continuation signals")
                            # No adjustment needed, let other factors determine
                    elif volatility_pct < 1.0:  # Low volatility (new threshold)
                        self.reasoning_chain.append(f"  - [VOLATILITY ASSESSMENT] Low volatility ({volatility_pct:.2f}%), checking trend context...")
                        # Similar logic for low but not extremely low volatility
                        if market_intel.trend_strength > 0.6 and market_intel.trend_direction in ['uptrend', 'downtrend']:
                            self.reasoning_chain.append(f"  - [VOLATILITY OPPORTUNITY] Strong trend with low volatility = potential pullback/retracement opportunity")
                            self.confidence = min(1.0, self.confidence + 0.05)  # Small boost
                        else:
                            self.reasoning_chain.append(f"  - [VOLATILITY INFO] Low volatility without strong trend, adjusting approach")
                            self.confidence = max(0.15, self.confidence - 0.03)  # Smaller reduction

    def _calculate_continuation_entry_and_stop(self, market_intel: MarketIntelligence, direction: str) -> Optional[Dict]:
        """Calculates an aggressive entry for a trend continuation move."""
        self.reasoning_chain.append(f"\n    [ENTRY & SL LOGIC] Using Continuation method...")
        # For a continuation, we enter more aggressively near the current price
        # and place the stop behind the most recent minor swing.
        if direction == 'LONG' or direction == 'UPTREND':
            if not market_intel.swing_lows: return None
            # Stop goes behind the most recent minor swing low
            stop_loss = market_intel.swing_lows[-1]['price'] * 0.999
            # Entry is a small pullback from current price
            entry_price = market_intel.current_price * 0.998
        elif direction == 'SHORT' or direction == 'DOWNTREND':
            if not market_intel.swing_highs: return None
            # Stop goes above the most recent minor swing high
            stop_loss = market_intel.swing_highs[-1]['price'] * 1.001
            # Entry is a small pullback from current price
            entry_price = market_intel.current_price * 1.002
        else:
            return None

        # TP is based on Fib extensions of the HTF leg
        htf_high = market_intel.htf_context['htf_swing_high']
        htf_low = market_intel.htf_context['htf_swing_low']
        fib_extensions = self._calculate_fib_extensions(htf_high, htf_low, direction)
        targets = [fib_extensions['ext_1.272'], fib_extensions['ext_1.618']]

        risk = abs(entry_price - stop_loss)
        if risk == 0: return None
        reward = abs(targets[0] - entry_price)
        rr = reward / risk

        self.reasoning_chain.append(f"    [AGGRESSIVE ENTRY] Targeting entry at ${entry_price:.2f}")
        self.reasoning_chain.append(f"    [TIGHT STOP] Stop loss placed at ${stop_loss:.2f}")
        self.reasoning_chain.append(f"    [FIB EXTENSION TP] Targeting ${targets[0]:.2f}")

        return {
            'entry_zone': (entry_price, entry_price),
            'stop_loss': stop_loss,
            'take_profits': targets,
            'risk_reward': rr,
        }

    def _calculate_fib_extensions(self, high: float, low: float, direction: str) -> Dict[str, float]:
        """Calculates Fibonacci extension levels."""
        swing_range = high - low
        extensions = {}
        levels = [1.272, 1.618, 2.0]
        if direction == 'LONG':
            for level in levels:
                extensions[f"ext_{level}"] = high + (swing_range * level)
        else: # SHORT
            for level in levels:
                extensions[f"ext_{level}"] = low - (swing_range * level)
        return extensions

    def _build_final_decision(self, market_intel, direction, entry_exit_data, lci_score, gls_score) -> IntelligentDecision:
        """Helper to construct the final IntelligentDecision object."""
        position_size_multiplier = 1.0
        if lci_score and gls_score:
            total_risk_factor = (lci_score + gls_score) / 2
            if total_risk_factor > 0.7: position_size_multiplier = 0.5
            elif total_risk_factor > 0.5: position_size_multiplier = 0.75

        return IntelligentDecision(
            direction=direction,
            confidence=self.confidence,
            signal_strength=self._get_signal_strength(self.confidence),
            entry_zone=entry_exit_data.get('entry_zone', (0,0)),
            stop_loss=entry_exit_data.get('stop_loss', 0),
            take_profits=entry_exit_data.get('take_profits', []),
            risk_reward=entry_exit_data.get('risk_reward', 0),
            position_size_multiplier=position_size_multiplier,
            reasoning_chain=self.reasoning_chain,
            should_trade=True,
            urgency='SETUP_FORMING',
            market_intel=market_intel,
            decision_timestamp=datetime.utcnow(),
            blockers=[], opportunities=[], warnings=[],
            max_risk_percent=1.0, analysis_quality=1.0 # Add missing args
        )

    def _scan_high_impact_zones(
        self,
        market_intel: MarketIntelligence,
        direction: str,
        entry_price: float,
        reasoning_chain: List[str]
    ) -> Optional[float]:
        """
        Scans for high-impact zones within a defined percentage range (Hybrid Risk Model)
        and applies a dynamic, ATR-based nudge to the Take Profit level.
        """
        # --- HYBRID RISK MODEL PARAMETERS ---
        min_tp_pct = 0.005      # 0.5%
        max_tp_pct = 0.01       # 1.0%
        fallback_tp_pct = 0.007 # 0.7%

        # Define the absolute price search range
        if direction == 'LONG' or direction == 'UPTREND':
            min_tp_price = entry_price * (1 + min_tp_pct)
            max_tp_price = entry_price * (1 + max_tp_pct)
            fallback_tp = entry_price * (1 + fallback_tp_pct)
        else: # SHORT or DOWNTREND
            min_tp_price = entry_price * (1 - min_tp_pct)
            max_tp_price = entry_price * (1 - max_tp_pct)
            fallback_tp = entry_price * (1 - fallback_tp_pct)
        
        reasoning_chain.append(f"    - [TP SEARCH] Scanning for high-impact zones between ${min_tp_price:.2f} ({min_tp_pct:.2%}) and ${max_tp_price:.2f} ({max_tp_pct:.2%}).")

        zones = []
        if direction == 'LONG' or direction == 'UPTREND':
            # Scan for resistance zones within the defined range
            for pool in market_intel.liquidity_pools:
                if pool['type'] == 'resistance' and min_tp_price <= pool['level'] <= max_tp_price:
                    zones.append(('liquidity_pool', pool['level'], 100 if pool.get('recent_sweeps', 0) == 0 else 50))
            for fvg in market_intel.fvgs:
                if fvg.gap_type == 'bearish' and min_tp_price <= fvg.gap_start <= max_tp_price:
                    zones.append(('fvg', fvg.gap_start, 100 if fvg.fill_status == 'UNFILLED' else 40))
            for ob in market_intel.order_blocks:
                if ob.type == 'bearish' and min_tp_price <= ob.entry_zone_low <= max_tp_price:
                    if ob.quality_score > 0.60:
                        zones.append(('order_block', ob.entry_zone_low, int(ob.quality_score * 100)))
            for swing in market_intel.swing_highs:
                if min_tp_price <= swing['price'] <= max_tp_price:
                    zones.append(('swing_high', swing['price'], 60))
        else:  # SHORT or DOWNTREND
            # Scan for support zones within the defined range
            for pool in market_intel.liquidity_pools:
                if pool['type'] == 'support' and max_tp_price <= pool['level'] <= min_tp_price:
                    zones.append(('liquidity_pool', pool['level'], 100 if pool.get('recent_sweeps', 0) == 0 else 50))
            for fvg in market_intel.fvgs:
                if fvg.gap_type == 'bullish' and max_tp_price <= fvg.gap_end <= min_tp_price:
                    zones.append(('fvg', fvg.gap_end, 100 if fvg.fill_status == 'UNFILLED' else 40))
            for ob in market_intel.order_blocks:
                if ob.type == 'bullish' and max_tp_price <= ob.entry_zone_high <= min_tp_price:
                    if ob.quality_score > 0.60:
                        zones.append(('order_block', ob.entry_zone_high, int(ob.quality_score * 100)))
            for swing in market_intel.swing_lows:
                if max_tp_price <= swing['price'] <= min_tp_price:
                    zones.append(('swing_low', swing['price'], 60))

        if not zones:
            reasoning_chain.append(f"    - [TP FALLBACK] No high-impact zones found in range. Using fallback TP at ${fallback_tp:.2f} ({fallback_tp_pct:.2%}).")
            return fallback_tp

        zones.sort(key=lambda x: x[2], reverse=True)
        best_zone = zones[0]
        zone_type, zone_price, zone_score = best_zone

        # BUG FIX: The previous ATR-based nudge was volatile and produced incorrect values.
        # This is replaced with a stable, percentage-based nudge.
        # Nudge is 0.1% of the zone price, providing a small buffer for TP.
        nudge_pct = 0.001 
        nudge_amount = zone_price * nudge_pct

        if direction == 'LONG' or direction == 'UPTREND':
            # Nudge TP down slightly to increase fill probability
            nudged_tp = zone_price - nudge_amount
        else: # SHORT or DOWNTREND
            # Nudge TP up slightly to increase fill probability
            nudged_tp = zone_price + nudge_amount

        reasoning_chain.append(f"    - [TP FOUND] Zone: {zone_type} at ${zone_price:.2f} (score: {zone_score})")
        reasoning_chain.append(f"    - [TP NUDGED] Nudged TP to ${nudged_tp:.2f} (Zone-based nudge: ${nudge_amount:.4f}) to increase fill probability.")
        
        # CRITICAL VALIDATION: Ensure nudged TP is still profitable
        if direction == 'LONG' or direction == 'UPTREND':
            if nudged_tp <= entry_price:
                reasoning_chain.append(f"    - [TP REJECT] Nudged TP (${nudged_tp:.2f}) is at or below entry (${entry_price:.2f}). Using original zone price.")
                return zone_price
        else: # SHORT or DOWNTREND
            if nudged_tp >= entry_price:
                reasoning_chain.append(f"    - [TP REJECT] Nudged TP (${nudged_tp:.2f}) is at or above entry (${entry_price:.2f}). Using original zone price.")

# ADD MISSING FUNCTION:
def print_intelligent_decision(decision: IntelligentDecision):
    """Pretty print the decision with full reasoning"""
    
    print("\n" + "="*80)
    print("INTELLIGENT STRATEGY BRAIN - FINAL DECISION")
    print("="*80)

    # Reasoning Chain
    print("\n" + "="*80)
    print("CHAIN OF THOUGHT REASONING")
    print("="*80)
    for line in decision.reasoning_chain:
        print(line)

    print("\n" + "="*80)
    print("TRADING DECISION")
    print("="*80)

    status_icon = "[GO]" if decision.should_trade else "[BLOCKED]"
    print(f"\n{status_icon} TRADE SIGNAL: {decision.direction}")
    print(f"Confidence: {decision.confidence:.0%}")
    print(f"Signal Strength: {decision.signal_strength}")
    print(f"Urgency: {decision.urgency}")

    if decision.should_trade:
        print(f"\n[ENTRY/EXIT]")
        print(f"Entry Zone: ${decision.entry_zone[0]:.2f} - ${decision.entry_zone[1]:.2f}")
        print(f"Stop Loss: ${decision.stop_loss:.2f}")
        print(f"Take Profits:")
        for i, tp in enumerate(decision.take_profits, 1):
            print(f"  TP{i}: ${tp:.2f}")
        print(f"Risk/Reward: {decision.risk_reward:.2f}:1")

        print(f"\n[POSITION SIZING]")
        print(f"Position Size: {decision.position_size_multiplier:.0%} of normal")
        print(f"Max Risk: {decision.max_risk_percent:.1f}%")
    else:
        print(f"\n[NO TRADE]")
        print(f"Reason: {'Blocked by critical safety check' if decision.blockers else 'Confidence too low'}")

    print(f"\n[ANALYSIS QUALITY]")
    print(f"Quality Score: {decision.analysis_quality:.0%}")
    print(f"Timestamp: {decision.decision_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n" + "="*80)
