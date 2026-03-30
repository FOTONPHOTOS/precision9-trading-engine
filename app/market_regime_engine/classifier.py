"""
Market Regime Engine: Master Regime Classifier
===============================================

This is the core logic that synthesizes all market metrics into a single,
 decisive classification of the market's current regime.

Author: Arsenal Trading System
"""

import pandas as pd
from typing import List, Dict
import logging
logger = logging.getLogger('MASTER_REGIME_CLASSIFIER')
logger.setLevel(logging.DEBUG)

from collections import deque

from .definitions import MarketRegime, RegimeMetrics, RegimeClassification
from .metrics import calculate_all_metrics

# Import the swing analysis function from the main project
# This is a temporary dependency that will be resolved during final integration.
from trend_continuation_brain import MarketIntelligence

class MasterRegimeClassifier:
    """
    A stateful classifier that determines the market's current regime.
    
    It uses a weighted scoring model based on multiple metrics and incorporates
    a hysteresis buffer to prevent rapid flip-flopping between states.
    """

    def __init__(self, hysteresis_period: int = 3):
        """
        Initializes the classifier.

        Args:
            hysteresis_period: The number of consecutive, consistent signals
                               required to confirm a regime change.
        """
        self.current_regime: MarketRegime = MarketRegime.CONSOLIDATING
        self.hysteresis_period = hysteresis_period
        # A deque is a highly efficient list-like container for adding/removing from ends
        self.regime_history: deque = deque(maxlen=hysteresis_period)
        self.is_new_regime: bool = False

    def _calculate_regime_scores(self, metrics: RegimeMetrics) -> Dict[MarketRegime, float]:
        """Calculates a score for each possible regime based on a more balanced, weighted model."""
        logger.debug(f"RegimeMetrics: ADX={metrics.adx_value:.2f}, EMA100_Slope={metrics.ema_100_slope:.4f}, EMA_Sep_Pct={metrics.ema_separation_pct:.2f}%")
        logger.debug(f"RegimeMetrics: Price_vs_EMA21={metrics.price_vs_ema21}, EMA21_vs_EMA100={metrics.ema21_vs_ema100}, Structure_Trend={metrics.structure_trend}, Structure_Strength={metrics.structure_strength:.2f}")

        scores = {
            MarketRegime.CONSOLIDATING: 0.0,
            MarketRegime.TRENDING_UP: 0.0,
            MarketRegime.TRENDING_DOWN: 0.0
        }

        # --- Consolidation & Choppy Market Scoring ---
        # Strong boost if ADX is very low (clear range)
        if metrics.adx_value < 18:
            scores[MarketRegime.CONSOLIDATING] += 40
            logger.debug(f"CONSOLIDATING: Strong ADX Boost (<18): 40")
        # Major boost if ADX indicates chop/weak trend
        elif metrics.adx_value < 25:
            scores[MarketRegime.CONSOLIDATING] += 25 # Was previously 1-5 points, now a significant score
            logger.debug(f"CONSOLIDATING: Choppy ADX Boost (<25): 25")

        # Boost for flat EMAs
        if abs(metrics.ema_100_slope) < 0.0001: # Stricter check for flatness
            scores[MarketRegime.CONSOLIDATING] += 20
            logger.debug(f"CONSOLIDATING: Flat EMA100 Slope Boost: 20")

        if metrics.ema_separation_pct < 0.25: # Stricter check for tight EMAs
            scores[MarketRegime.CONSOLIDATING] += 20
            logger.debug(f"CONSOLIDATING: Low EMA Separation Boost: 20")

        # --- Trending Up Scoring (Stricter Confluence) ---
        # Condition: Structure must be 'uptrend' AND ADX must be > 25
        if metrics.structure_trend == 'uptrend' and metrics.adx_value > 25:
            # Base score for trend confirmed by momentum
            scores[MarketRegime.TRENDING_UP] += 40
            logger.debug(f"TRENDING_UP: Base Score (Structure + ADX > 25): 40")
            
            # Bonus for strong structure
            scores[MarketRegime.TRENDING_UP] += 30 * metrics.structure_strength
            logger.debug(f"TRENDING_UP: Structure Strength Bonus: {30 * metrics.structure_strength:.2f}")

            # EMA alignment provides a strong confirmation bonus
            if metrics.price_vs_ema21 == 'above' and metrics.ema21_vs_ema100 == 'above':
                scores[MarketRegime.TRENDING_UP] += 30
                logger.debug(f"TRENDING_UP: EMA Alignment Boost: 30")
            
            # Bonus for positive slope
            if metrics.ema_100_slope > 0:
                scores[MarketRegime.TRENDING_UP] += 15
                logger.debug(f"TRENDING_UP: EMA Slope Boost: 15")

        # --- Trending Down Scoring (Stricter Confluence) ---
        # Condition: Structure must be 'downtrend' AND ADX must be > 25
        if metrics.structure_trend == 'downtrend' and metrics.adx_value > 25:
            # Base score for trend confirmed by momentum
            scores[MarketRegime.TRENDING_DOWN] += 40
            logger.debug(f"TRENDING_DOWN: Base Score (Structure + ADX > 25): 40")

            # Bonus for strong structure
            scores[MarketRegime.TRENDING_DOWN] += 30 * metrics.structure_strength
            logger.debug(f"TRENDING_DOWN: Structure Strength Bonus: {30 * metrics.structure_strength:.2f}")

            # EMA alignment provides a strong confirmation bonus
            if metrics.price_vs_ema21 == 'below' and metrics.ema21_vs_ema100 == 'below':
                scores[MarketRegime.TRENDING_DOWN] += 30
                logger.debug(f"TRENDING_DOWN: EMA Alignment Boost: 30")

            # Bonus for negative slope
            if metrics.ema_100_slope < 0:
                scores[MarketRegime.TRENDING_DOWN] += 15
                logger.debug(f"TRENDING_DOWN: EMA Slope Boost: 15")

        return scores

    def analyze(self, df_history: pd.DataFrame, market_intel: MarketIntelligence) -> RegimeClassification:
        """
        Analyzes the latest market data and returns a definitive regime classification.
        """
        # 1. Calculate all metrics using the unified function and the authoritative market_intel
        metrics = calculate_all_metrics(df_history, market_intel)

        if metrics is None:
            return RegimeClassification(
                timestamp=df_history.index[-1],
                current_regime=self.current_regime,
                regime_scores={},
                metrics=None,
                is_new_regime=False,
                message="Insufficient data for metric calculation."
            )

        # 3. Score each potential regime
        scores = self._calculate_regime_scores(metrics)
        
        # 4. Apply range trap and stop hunt adjustments to regime scores
        # CRITICAL: If there's high trap severity, reduce consolidating score significantly
        if metrics.range_trap_active and metrics.range_trap_severity > 0.5:
            scores[MarketRegime.CONSOLIDATING] *= (1.0 - metrics.range_trap_severity * 0.7)  # Reduce consolidating score by 70% of trap severity
            logger.debug(f"RangeTrapDetector: Trapped, high severity. Reducing CONSOLIDATING score by {metrics.range_trap_severity * 0.7 * 100:.1f}%. ")
        elif metrics.range_trap_active and metrics.range_trap_severity > 0.3:
            scores[MarketRegime.CONSOLIDATING] *= (1.0 - metrics.range_trap_severity * 0.4)  # Reduce consolidating score by 40% of trap severity
            logger.debug(f"RangeTrapDetector: Trapped, medium severity. Reducing CONSOLIDATING score by {metrics.range_trap_severity * 0.4 * 100:.1f}%. ")
        
        # CRITICAL: If stop hunt mode is active, especially bi-directional, reduce consolidating score
        # Note: stop_hunt_analysis is not available here, so we cannot use it directly.
        # We need to pass stop_hunt_active and stop_hunt_severity to RegimeMetrics as well.
        # For now, we will comment out this part.
        # if stop_hunt_analysis and stop_hunt_analysis.is_stop_hunt_mode and stop_hunt_analysis.hunt_type == 'BI_DIRECTIONAL':
        #     scores[MarketRegime.CONSOLIDATING] *= 0.3  # Reduce consolidating score significantly if bi-directional manipulation
        # elif stop_hunt_analysis and stop_hunt_analysis.is_stop_hunt_mode:
        #     scores[MarketRegime.CONSOLIDATING] *= 0.6  # Reduce consolidating score moderately if stop hunt active
        
        # CRITICAL: If directional stop hunt is detected with breakout, boost trending scores instead of consolidating
        # Note: stop_hunt_analysis is not available here, so we cannot use it directly.
        # For now, we will comment out this part.
        # if stop_hunt_analysis and stop_hunt_analysis.is_tradeable_directional:
        #     if stop_hunt_analysis.hunt_type == 'DIRECTIONAL_SHORT':
        #         # Hunting longs with breakout = trending down
        #         scores[MarketRegime.TRENDING_DOWN] *= 1.3  # Boost trending down score
        #     elif stop_hunt_analysis.hunt_type == 'DIRECTIONAL_LONG':
        #         # Hunting shorts with breakout = trending up
        #         scores[MarketRegime.TRENDING_UP] *= 1.3  # Boost trending up score

        # 5. Determine the highest-scoring potential regime for this candle
        potential_regime = max(scores, key=scores.get)
        
        # 6. Apply Hysteresis Logic
        self.regime_history.append(potential_regime)
        self.is_new_regime = False

        if len(self.regime_history) == self.hysteresis_period and len(set(self.regime_history)) == 1:
            confirmed_regime = self.regime_history[0]
            if confirmed_regime != self.current_regime:
                self.is_new_regime = True
                self.current_regime = confirmed_regime
                self.regime_history.clear()

        # 7. Create and return the final classification report
        message = f"Regime: {self.current_regime.name}. Potential: {potential_regime.name}."
        if self.is_new_regime:
            message = f"REGIME CHANGE DETECTED: New regime is {self.current_regime.name}."
        
        # Add context about range trap and stop hunt if applicable
        if metrics.range_trap_active and metrics.range_trap_severity > 0.5:
            message += f" [WARNING: High range trap severity {metrics.range_trap_severity:.0%}]"
        # Note: stop_hunt_analysis is not available here, so we cannot use it directly.
        # For now, we will comment out this part.
        # if stop_hunt_analysis and stop_hunt_analysis.is_stop_hunt_mode:
        #     message += f" [WARNING: Stop hunt mode active - {stop_hunt_analysis.hunt_type}]"
        # if stop_hunt_analysis and stop_hunt_analysis.is_tradeable_directional:
        #     direction = "DOWN" if stop_hunt_analysis.hunt_type == 'DIRECTIONAL_SHORT' else "UP"
        #     message += f" [TREND OPPORTUNITY: Directional hunt with breakout to {direction}]"

        return RegimeClassification(
            timestamp=df_history.index[-1],
            current_regime=self.current_regime,
            regime_scores=scores,
            metrics=metrics,
            is_new_regime=self.is_new_regime,
            message=message
        )
