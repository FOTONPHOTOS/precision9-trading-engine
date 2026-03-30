"""
Enhanced Volatility Calculator for Precision9 Trading System
===========================================================

Provides multiple volatility measurements for more accurate market assessment:
- ATR (Average True Range) - Most reliable for crypto
- Standard Deviation of Returns - Traditional measure
- Realized Volatility - Based on actual price movement
- Multiple timeframe analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class EnhancedVolatilityCalculator:
    """
    Calculates multiple volatility measures to provide a comprehensive view
    of market volatility conditions.
    """
    
    def __init__(self):
        self.min_periods = 14  # Minimum periods for calculations
        self.lookback_periods = {
            'short': 14,    # 14 periods for quick response
            'medium': 21,   # 21 periods for balanced view  
            'long': 50      # 50 periods for trend volatility
        }
    
    def calculate_all_volatility_measures(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate all volatility measures from a DataFrame
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Dictionary with various volatility measures
        """
        if len(df) < self.min_periods:
            logger.warning(f"Insufficient data for volatility calculation. Need {self.min_periods}, got {len(df)}")
            return self.get_default_volatility_values()
        
        results = {}
        
        # 1. ATR (Average True Range) - Most reliable for crypto
        results['atr'] = self.calculate_atr(df)
        results['atr_pct'] = results['atr'] / df['close'].iloc[-1] * 100 if df['close'].iloc[-1] > 0 else 0
        
        # 2. Standard Deviation of Returns
        results['std_returns'] = self.calculate_std_returns(df)
        results['std_returns_pct'] = results['std_returns'] * 100
        
        # 3. Realized Volatility (based on log returns)
        results['realized_vol'] = self.calculate_realized_volatility(df)
        results['realized_vol_pct'] = results['realized_vol'] * 100
        
        # 4. Bollinger Bands Width (volatility indicator)
        results['bb_width'] = self.calculate_bollinger_band_width(df)
        
        # 5. Multiple timeframe analysis
        results['volatility_score'] = self.calculate_composite_volatility_score(results)
        
        # 6. Volatility regime classification
        results['volatility_regime'] = self.classify_volatility_regime(results['volatility_score'])
        
        return results
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average True Range - the most reliable volatility measure for crypto
        """
        try:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            
            true_range = np.max([high_low, high_close, low_close], axis=0)
            atr = pd.Series(true_range).rolling(window=period).mean().iloc[-1]
            return float(atr) if not np.isnan(atr) else 0.0
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.0
    
    def calculate_std_returns(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate standard deviation of returns
        """
        try:
            returns = df['close'].pct_change().dropna()
            if len(returns) < period:
                period = len(returns)
            
            std_returns = returns.tail(period).std()
            return float(std_returns) if not np.isnan(std_returns) else 0.0
        except Exception as e:
            logger.error(f"Error calculating std returns: {e}")
            return 0.0
    
    def calculate_realized_volatility(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate realized volatility using log returns
        """
        try:
            log_returns = np.log(df['close'] / df['close'].shift(1)).dropna()
            if len(log_returns) < period:
                period = len(log_returns)
            
            realized_vol = log_returns.tail(period).std() * np.sqrt(252)  # Annualized
            return float(realized_vol) if not np.isnan(realized_vol) else 0.0
        except Exception as e:
            logger.error(f"Error calculating realized volatility: {e}")
            return 0.0
    
    def calculate_bollinger_band_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate Bollinger Band Width as a volatility measure
        """
        try:
            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            upper_band = sma + (std * 2)
            lower_band = sma - (std * 2)
            bb_width = ((upper_band - lower_band) / sma).iloc[-1] * 100
            return float(bb_width) if not np.isnan(bb_width) else 0.0
        except Exception as e:
            logger.error(f"Error calculating Bollinger Band Width: {e}")
            return 0.0
    
    def calculate_composite_volatility_score(self, volatility_measures: Dict[str, float]) -> float:
        """
        Create a composite volatility score from multiple measures
        Higher scores indicate higher volatility
        """
        try:
            # Weight different volatility measures appropriately
            atr_score = volatility_measures.get('atr_pct', 0) * 0.3    # ATR is most reliable
            std_score = volatility_measures.get('std_returns_pct', 0) * 0.25  # Standard measure
            realized_score = volatility_measures.get('realized_vol_pct', 0) * 0.25  # Realized volatility
            bb_score = volatility_measures.get('bb_width', 0) * 0.2    # Bollinger Bands
            
            # Ensure all values are positive and reasonable
            atr_score = max(0, min(100, atr_score))  # Cap at reasonable values
            std_score = max(0, min(100, std_score))
            realized_score = max(0, min(100, realized_score))
            bb_score = max(0, min(100, bb_score))
            
            composite_score = (atr_score + std_score + realized_score + bb_score) / 4
            return min(100, composite_score)  # Cap the final score
        except Exception as e:
            logger.error(f"Error calculating composite volatility score: {e}")
            return 0.0
    
    def classify_volatility_regime(self, volatility_score: float) -> str:
        """
        Classify the current volatility regime
        """
        if volatility_score < 1.0:
            return "VERY_LOW"
        elif volatility_score < 2.0:
            return "LOW"
        elif volatility_score < 4.0:
            return "MODERATE"
        elif volatility_score < 8.0:
            return "HIGH"
        else:
            return "VERY_HIGH"
    
    def get_default_volatility_values(self) -> Dict[str, float]:
        """
        Return default values when insufficient data is available
        """
        return {
            'atr': 0.0,
            'atr_pct': 1.0,  # Conservative estimate
            'std_returns': 0.01,
            'std_returns_pct': 1.0,
            'realized_vol': 0.015,
            'realized_vol_pct': 1.5,
            'bb_width': 2.0,
            'volatility_score': 1.5,
            'volatility_regime': 'LOW'
        }
    
    def analyze_volatility_trend(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Analyze volatility trend over time to detect changes
        """
        try:
            # Calculate volatility for different periods
            short_vol = self.calculate_composite_volatility_score(
                self.calculate_all_volatility_measures(df.tail(self.lookback_periods['short']))
            )
            
            medium_vol = self.calculate_composite_volatility_score(
                self.calculate_all_volatility_measures(df.tail(self.lookback_periods['medium']))
            )
            
            long_vol = self.calculate_composite_volatility_score(
                self.calculate_all_volatility_measures(df.tail(self.lookback_periods['long']))
            )
            
            # Determine trend
            current_vs_medium = short_vol - medium_vol
            current_vs_long = short_vol - long_vol
            
            if current_vs_medium > 0.5 and current_vs_long > 0.5:
                trend = "INCREASING"
            elif current_vs_medium < -0.5 and current_vs_long < -0.5:
                trend = "DECREASING"
            else:
                trend = "STABLE"
            
            return {
                'current_volatility': short_vol,
                'medium_term_volatility': medium_vol,
                'long_term_volatility': long_vol,
                'volatility_trend': trend,
                'volatility_acceleration': current_vs_medium  # Change in volatility
            }
        except Exception as e:
            logger.error(f"Error analyzing volatility trend: {e}")
            return {
                'current_volatility': 1.5,
                'medium_term_volatility': 1.5,
                'long_term_volatility': 1.5,
                'volatility_trend': 'STABLE',
                'volatility_acceleration': 0.0
            }


def integrate_volatility_analysis(df: pd.DataFrame, market_intel: any):
    """
    Integrate enhanced volatility analysis into the existing system
    """
    vol_calculator = EnhancedVolatilityCalculator()
    
    # Calculate all volatility measures
    volatility_measures = vol_calculator.calculate_all_volatility_measures(df)
    volatility_trend = vol_calculator.analyze_volatility_trend(df)
    
    # Update market intelligence with proper volatility data
    volatility_analysis = {
        'measures': volatility_measures,
        'trend': volatility_trend,
        'current_volatility_pct': volatility_measures['volatility_score'],
        'volatility_regime': volatility_measures['volatility_regime'],
        'is_extreme_volatility': volatility_measures['volatility_regime'] in ['VERY_HIGH', 'VERY_LOW']
    }
    
    # Add to market intelligence for use in decision making
    # This would be passed to the brain for decision making
    return volatility_analysis


if __name__ == "__main__":
    # Example usage - would need real data to test properly
    print("Enhanced Volatility Calculator ready for integration")
    print("This will provide more accurate volatility measures for the trading system")