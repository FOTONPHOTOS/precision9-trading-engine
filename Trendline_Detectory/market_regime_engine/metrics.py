"""
Market Regime Engine: Objective Metrics Calculation
===================================================

Contains the pure functions for calculating the metrics used for regime classification.

Author: Arsenal Trading System
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from .definitions import RegimeMetrics



def calculate_volatility_profile(df: pd.DataFrame, atr_length: int = 14, slope_length: int = 10) -> Dict[str, float]:
    """Calculates ATR percentage and slope."""
    if 'ATR_14' not in df.columns or len(df) < slope_length:
        return {'atr_pct': 0.0, 'atr_slope': 0.0}
    
    atr = df['ATR_14']
    close = df['close']
    
    atr_pct = (atr.iloc[-1] / close.iloc[-1]) * 100
    
    # Calculate slope using linear regression on the last N bars of the ATR
    y = atr.iloc[-slope_length:].values
    x = np.arange(len(y))
    slope = np.polyfit(x, y, 1)[0]
    
    return {'atr_pct': atr_pct, 'atr_slope': slope}

def calculate_ma_behavior(df: pd.DataFrame, slope_length: int = 20) -> Dict[str, any]: # Increased slope_length
    """Analyzes the behavior of price relative to EMAs."""
    if 'EMA_21' not in df.columns or 'EMA_100' not in df.columns or len(df) < slope_length:
        return {
            'price_vs_ema21': 'inside', 'ema21_vs_ema100': 'crossing',
            'ema_separation_pct': 0.0, 'ema_100_slope': 0.0
        }

    price = df['close'].iloc[-1]
    ema21 = df['EMA_21'].iloc[-1]
    ema100 = df['EMA_100'].iloc[-1]

    # Price vs EMA21
    if price > ema21: price_vs_ema21 = 'above'
    else: price_vs_ema21 = 'below'

    # EMA21 vs EMA100
    if ema21 > ema100: ema21_vs_ema100 = 'above'
    else: ema21_vs_ema100 = 'below'

    # EMA Separation
    ema_separation_pct = (abs(ema21 - ema100) / ema100) * 100

    # EMA100 Slope
    y = df['EMA_100'].iloc[-slope_length:].values
    x = np.arange(len(y))
    ema_100_slope = np.polyfit(x, y, 1)[0]

    return {
        'price_vs_ema21': price_vs_ema21,
        'ema21_vs_ema100': ema21_vs_ema100,
        'ema_separation_pct': ema_separation_pct,
        'ema_100_slope': ema_100_slope
    }

def calculate_adx_metric(df: pd.DataFrame) -> float:
    """Extracts the latest ADX value."""
    if 'ADX_14' not in df.columns or df.empty:
        return 20.0 # Return a neutral value
    return df['ADX_14'].iloc[-1]

from trend_continuation_brain import MarketIntelligence

def calculate_all_metrics(
    df: pd.DataFrame, 
    market_intel: MarketIntelligence # Use the main MarketIntel object
) -> Optional[RegimeMetrics]:
    """
    Calculates all metrics and returns a populated RegimeMetrics object.
    """
    if df.empty or len(df) < 100: # Need enough data for indicators
        return None

    # Use the authoritative analysis from the main brain
    structure = {
        'trend_direction': market_intel.trend_direction.lower(),
        'trend_strength': market_intel.trend_strength
    }
    
    volatility = calculate_volatility_profile(df)
    ma_behavior = calculate_ma_behavior(df)
    adx_value = calculate_adx_metric(df)

    return RegimeMetrics(
        structure_trend=structure['trend_direction'],
        structure_strength=structure['trend_strength'],
        atr_pct=volatility['atr_pct'],
        atr_slope=volatility['atr_slope'],
        price_vs_ema21=ma_behavior['price_vs_ema21'],
        ema21_vs_ema100=ma_behavior['ema21_vs_ema100'],
        ema_separation_pct=ma_behavior['ema_separation_pct'],
        ema_100_slope=ma_behavior['ema_100_slope'],
        adx_value=adx_value,
        range_trap_active=market_intel.range_trap_analysis.is_trapped,
        range_trap_severity=market_intel.range_trap_analysis.trap_severity
    )
