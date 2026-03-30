"""
Advanced Volatility Analyzer for Scalping Systems

This module provides sophisticated volatility analysis that considers:
- Multiple timeframes
- Contextual trend strength
- Mean reversion vs trend continuation signals
- Dynamic volatility thresholds
- Symbol-specific volatility patterns

The system needs to distinguish between:
1. Low volatility during trend continuation (good for pullback scalps)
2. Low volatility during ranging (often bad for direction scalps)
3. High volatility during breakouts (good opportunities)
4. High volatility during reversal zones (sometimes good, sometimes dangerous)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class VolatilityAnalysis:
    """Complete volatility analysis result"""
    volatility_score: float  # 0-1: overall volatility assessment
    volatility_regime: str   # LOW, MODERATE, HIGH, EXTREME
    trend_volatility_alignment: str  # BULLISH_ALIGNMENT, BEARISH_ALIGNMENT, RANGE, CONFLICT
    volatility_trend: str    # UP, DOWN, FLAT, CHOPPY
    volatility_confidence: float  # How reliable is the volatility signal (0-1)
    volatility_opportunity_score: float  # 0-1: How good is the current volatility for scalping
    volatility_warning: str  # Any volatility-based warnings
    volatility_context: Dict  # Additional context data


class AdvancedVolatilityAnalyzer:
    """
    Advanced volatility analyzer for scalping systems
    """

    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol.upper()
        self._set_symbol_specific_params()

    def _set_symbol_specific_params(self):
        """Set volatility parameters based on symbol characteristics"""
        # Default parameters
        self.min_volatility_threshold = 0.3  # Below this is considered very low
        self.max_volatility_threshold = 2.5  # Above this is considered very high
        self.volatility_lookback_periods = 20  # How many periods for volatility calculation
        self.smoothing_periods = 5  # For smoothing volatility signals
        self.trend_volatility_alignment_period = 50  # For trend alignment
        
        # Symbol-specific parameters based on historical performance data
        if self.symbol == 'BTCUSDT':
            # BTC: 35% win rate - tends to have smoother volatility patterns
            self.min_volatility_threshold = 0.4  # Slightly higher threshold
            self.max_volatility_threshold = 2.8  # Higher threshold for BTC's moves
            self.volatility_lookback_periods = 25  # Slightly longer lookback
            self.trend_volatility_alignment_period = 60  # More data for trend alignment
        elif self.symbol == 'ETHUSDT':
            # ETH: 26.3% win rate - more volatile, needs different thresholds
            self.min_volatility_threshold = 0.5
            self.max_volatility_threshold = 3.2
            self.volatility_lookback_periods = 20
        elif self.symbol == 'SOLUSDT':
            # SOL: 20% win rate - very volatile, different patterns
            self.min_volatility_threshold = 0.8
            self.max_volatility_threshold = 4.0
            self.volatility_lookback_periods = 15  # Shorter to catch SOL's quick moves
        elif self.symbol == 'XRPUSDT':
            # XRP: 27.3% win rate
            self.min_volatility_threshold = 0.6
            self.max_volatility_threshold = 3.0
        elif self.symbol == 'LINKUSDT':
            # LINK: 22.2% win rate
            self.min_volatility_threshold = 0.4
            self.max_volatility_threshold = 2.5
        elif self.symbol == 'BNBUSDT':
            # BNB: 12.5% win rate - most restrictive
            self.min_volatility_threshold = 0.7
            self.max_volatility_threshold = 2.0

    def analyze(self, df: pd.DataFrame, trend_direction: str = 'ranging', 
                trend_strength: float = 0.5, current_price: float = None) -> VolatilityAnalysis:
        """
        Perform comprehensive volatility analysis
        """
        if df is None or df.empty:
            return self._create_default_analysis()
        
        # Calculate various volatility metrics
        volatility_metrics = self._calculate_volatility_metrics(df, current_price)
        
        # Analyze volatility trend
        volatility_trend = self._analyze_volatility_trend(df)
        
        # Check alignment between trend and volatility
        alignment = self._analyze_trend_volatility_alignment(
            df, trend_direction, trend_strength, volatility_metrics['current_volatility']
        )
        
        # Calculate opportunity score based on volatility
        opportunity_score = self._calculate_volatility_opportunity_score(
            volatility_metrics, alignment, trend_direction, trend_strength
        )
        
        # Generate warning if necessary
        warning = self._generate_volatility_warning(
            volatility_metrics, alignment, trend_direction, trend_strength
        )
        
        # Calculate confidence in volatility signals
        confidence = self._calculate_volatility_confidence(volatility_metrics)
        
        # Determine volatility regime
        regime = self._determine_volatility_regime(volatility_metrics['current_volatility'])
        
        return VolatilityAnalysis(
            volatility_score=volatility_metrics['current_volatility'],
            volatility_regime=regime,
            trend_volatility_alignment=alignment,
            volatility_trend=volatility_trend,
            volatility_confidence=confidence,
            volatility_opportunity_score=opportunity_score,
            volatility_warning=warning,
            volatility_context=volatility_metrics
        )

    def _calculate_volatility_metrics(self, df: pd.DataFrame, current_price: float = None) -> Dict:
        """
        Calculate multiple volatility metrics
        """
        # Basic volatility metrics
        returns = np.log(df['close'] / df['close'].shift(1)).dropna()
        
        # Current volatility (ATR-based and return-based)
        atr = self._calculate_atr(df, period=14)
        current_atr_vol = atr.iloc[-1] / df['close'].iloc[-1] * 100 if len(atr) > 0 else 0.5
        
        # Standard deviation of returns
        rolling_returns = returns.tail(self.volatility_lookback_periods)
        current_std_vol = rolling_returns.std() * np.sqrt(72) * 100 if len(rolling_returns) > 0 else 0.5  # Annualized
        
        # Range-based volatility (high-low)
        range_vol = ((df['high'] - df['low']) / df['close'] * 100).rolling(window=self.volatility_lookback_periods).mean()
        current_range_vol = range_vol.iloc[-1] if len(range_vol) > 0 else 0.5
        
        # Weighted average of different volatility measures
        current_volatility = (current_atr_vol * 0.4 + current_std_vol * 0.3 + current_range_vol * 0.3)
        
        # Historical volatility context
        historical_mean = df['close'].rolling(window=100).apply(
            lambda x: np.log(x / x.shift(1)).std() * np.sqrt(72) * 100
        ).mean()
        
        historical_std = df['close'].rolling(window=100).apply(
            lambda x: np.log(x / x.shift(1)).std() * np.sqrt(72) * 100
        ).std()
        
        # Smoothed volatility
        smoothed_vol = df['close'].rolling(window=self.smoothing_periods).apply(
            lambda x: np.log(x / x.shift(1)).std() * np.sqrt(72) * 100
        ).iloc[-1]
        
        return {
            'current_volatility': current_volatility,
            'atr_volatility': current_atr_vol,
            'std_volatility': current_std_vol,
            'range_volatility': current_range_vol,
            'historical_mean': historical_mean,
            'historical_std': historical_std,
            'smoothed_volatility': smoothed_vol,
            'volatility_ratio': current_volatility / max(historical_mean, 0.1),  # Current vs historical
        }

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range
        """
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()

    def _analyze_volatility_trend(self, df: pd.DataFrame) -> str:
        """
        Analyze if volatility is trending up, down, or flat
        """
        # Calculate volatility over different periods
        volatility_5 = self._calculate_period_volatility(df, 5)
        volatility_20 = self._calculate_period_volatility(df, 20)
        volatility_50 = self._calculate_period_volatility(df, 50)
        
        if volatility_5 > volatility_20 and volatility_20 > volatility_50:
            return 'UP'
        elif volatility_5 < volatility_20 and volatility_20 < volatility_50:
            return 'DOWN'
        else:
            return 'FLAT'

    def _calculate_period_volatility(self, df: pd.DataFrame, period: int) -> float:
        """
        Calculate volatility over a specific period
        """
        if len(df) < period:
            period = len(df)
        recent_returns = np.log(df['close'].tail(period) / df['close'].tail(period).shift(1)).dropna()
        return recent_returns.std() * np.sqrt(72) * 100 if len(recent_returns) > 0 else 0.5

    def _analyze_trend_volatility_alignment(self, df: pd.DataFrame, trend_direction: str, 
                                          trend_strength: float, current_volatility: float) -> str:
        """
        Analyze the relationship between trend and volatility
        """
        # Get historical context
        historical_mean_vol = df['close'].rolling(window=100).apply(
            lambda x: np.log(x / x.shift(1)).std() * np.sqrt(72) * 100
        ).mean()
        
        is_high_vol = current_volatility > historical_mean_vol * 1.2
        is_low_vol = current_volatility < historical_mean_vol * 0.8
        
        # Based on trend and volatility relationship
        if trend_direction == 'uptrend':
            if trend_strength > 0.7:  # Strong uptrend
                if is_low_vol:
                    return 'BULLISH_ALIGNMENT'  # Low vol in strong trend = pullback opportunity
                else:
                    return 'BULLISH_STRENGTH'  # High vol confirms strong trend
            else:  # Weak uptrend
                if is_high_vol:
                    return 'CONFLICT'  # High vol with weak trend = uncertainty
                else:
                    return 'WEAK_BULLISH'  # Low vol with weak trend = weak signal
        elif trend_direction == 'downtrend':
            if trend_strength > 0.7:  # Strong downtrend
                if is_low_vol:
                    return 'BEARISH_ALIGNMENT'  # Low vol in strong trend = pullback opportunity
                else:
                    return 'BEARISH_STRENGTH'  # High vol confirms strong trend
            else:  # Weak downtrend
                if is_high_vol:
                    return 'CONFLICT'  # High vol with weak trend = uncertainty
                else:
                    return 'WEAK_BEARISH'  # Low vol with weak trend = weak signal
        else:  # Ranging
            if is_high_vol:
                return 'RANGE_BREAKOUT_IMMINENT'  # High vol in range = breakout likely
            else:
                return 'RANGE'  # Low vol in range = continued ranging

    def _calculate_volatility_opportunity_score(self, volatility_metrics: Dict, 
                                             alignment: str, trend_direction: str, 
                                             trend_strength: float) -> float:
        """
        Calculate how good current volatility is for scalping opportunities
        """
        score = 0.5  # Base score
        
        current_vol = volatility_metrics['current_volatility']
        historical_mean = volatility_metrics['historical_mean']
        
        # Volatility level adjustment
        if self.min_volatility_threshold * 0.7 <= current_vol <= self.max_volatility_threshold * 0.8:
            # Good volatility range for scalping
            score += 0.2
        elif current_vol < self.min_volatility_threshold * 0.7:
            # Very low volatility - could be good for pullbacks in trending markets
            if trend_strength > 0.6 and trend_direction in ['uptrend', 'downtrend']:
                score += 0.1  # Low vol in strong trend = pullback opportunity
            else:
                score -= 0.1  # Low vol with weak trend = not ideal
        elif current_vol > self.max_volatility_threshold * 0.8:
            # High volatility - opportunity but risk
            score += 0.15
        
        # Alignment adjustment
        if alignment in ['BULLISH_ALIGNMENT', 'BEARISH_ALIGNMENT']:
            # Pullback in trend = good opportunity
            score += 0.15
        elif alignment in ['BULLISH_STRENGTH', 'BEARISH_STRENGTH']:
            # Strong trend with high vol = good momentum opportunity
            score += 0.1
        elif alignment == 'RANGE_BREAKOUT_IMMINENT':
            # Range with increasing vol = breakout opportunity
            score += 0.1
        elif alignment == 'CONFLICT':
            # Uncertainty - reduce score
            score -= 0.15
        
        # Trend strength adjustment
        if trend_strength > 0.7:
            score += 0.1  # Strong trend = more confidence in direction
        elif trend_strength < 0.3:
            score -= 0.05  # Weak trend = less directional confidence
        
        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, score))

    def _generate_volatility_warning(self, volatility_metrics: Dict, alignment: str, 
                                   trend_direction: str, trend_strength: float) -> str:
        """
        Generate appropriate volatility warning based on analysis
        """
        current_vol = volatility_metrics['current_volatility']
        historical_mean = volatility_metrics['historical_mean']
        
        # Check if volatility is extremely low
        if current_vol < self.min_volatility_threshold * 0.5:
            if trend_strength > 0.6 and trend_direction in ['uptrend', 'downtrend']:
                # Extremely low vol in strong trend = possible reversal or pause
                return f"EXTREME LOW VOLATILITY in strong {trend_direction}: Potential pullback opportunity, not necessarily a warning"
            else:
                return f"EXTREME LOW VOLATILITY ({current_vol:.2f}%): Market may be stagnant"
        
        # Check if volatility is extremely high
        elif current_vol > self.max_volatility_threshold * 1.2:
            return f"EXTREME HIGH VOLATILITY ({current_vol:.2f}%): High risk environment, proceed with caution"
        
        # Check for volatility compression (rapid decrease)
        elif current_vol < historical_mean * 0.5 and historical_mean > self.min_volatility_threshold:
            if trend_strength > 0.6:
                return f"VOLATILITY COMPRESSION in strong trend: Potential explosive move coming, good for scalping"
            else:
                return f"VOLATILITY COMPRESSION: Possible ranging continuation"
        
        # No significant warning
        return "VOLATILITY CONDITIONS NORMAL"

    def _calculate_volatility_confidence(self, volatility_metrics: Dict) -> float:
        """
        Calculate confidence in volatility readings
        """
        # Higher confidence if volatility is stable and within normal ranges
        current_vol = volatility_metrics['current_volatility']
        historical_mean = volatility_metrics['historical_mean']
        historical_std = volatility_metrics['historical_std']
        
        if historical_std == 0:
            return 0.5
            
        # Calculate how many standard deviations current vol is from mean
        z_score = abs(current_vol - historical_mean) / historical_std
        
        # Confidence decreases as volatility becomes more extreme
        confidence = max(0.2, 1.0 - min(z_score * 0.15, 0.5))
        
        return confidence

    def _determine_volatility_regime(self, current_volatility: float) -> str:
        """
        Determine the volatility regime
        """
        if current_volatility < self.min_volatility_threshold * 0.7:
            return 'EXTREME_LOW'
        elif current_volatility < self.min_volatility_threshold:
            return 'LOW'
        elif current_volatility < self.max_volatility_threshold * 0.7:
            return 'MODERATE'
        elif current_volatility < self.max_volatility_threshold:
            return 'HIGH'
        else:
            return 'EXTREME_HIGH'

    def _create_default_analysis(self) -> VolatilityAnalysis:
        """
        Create default analysis when no data is available
        """
        return VolatilityAnalysis(
            volatility_score=0.5,
            volatility_regime='MODERATE',
            trend_volatility_alignment='RANGE',
            volatility_trend='FLAT',
            volatility_confidence=0.3,
            volatility_opportunity_score=0.5,
            volatility_warning='INSUFFICIENT DATA',
            volatility_context={}
        )


# Example usage function
def analyze_market_volatility(df: pd.DataFrame, symbol: str = "BTCUSDT", 
                            trend_direction: str = "ranging", trend_strength: float = 0.5) -> VolatilityAnalysis:
    """
    Convenience function to analyze volatility for market conditions
    """
    analyzer = AdvancedVolatilityAnalyzer(symbol)
    current_price = df['close'].iloc[-1] if not df.empty else None
    return analyzer.analyze(df, trend_direction, trend_strength, current_price)


if __name__ == "__main__":
    print("Advanced Volatility Analyzer Module")
    print("="*50)
    print("This module provides sophisticated volatility analysis for scalping systems")
    print("It considers multiple timeframes, trend alignment, and symbol-specific patterns")
    print("to provide more appropriate volatility assessments for microstructural scalping.")