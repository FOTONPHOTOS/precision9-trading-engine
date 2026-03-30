"""
Simulation Framework: Technical Indicators
========================================

In-house implementations of technical indicators to remove external dependencies.

Author: Arsenal Trading System
"""

import pandas as pd

def calculate_ema(data: pd.Series, length: int) -> pd.Series:
    """Calculates the Exponential Moving Average (EMA)."""
    return data.ewm(span=length, adjust=False).mean()

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """Calculates the Average True Range (ATR)."""
    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/length, adjust=False).mean()
    return atr

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """Calculates the Average Directional Index (ADX)."""
    plus_dm = high.diff()
    minus_dm = low.diff().mul(-1)
    
    plus_dm[plus_dm < 0] = 0
    plus_dm[plus_dm < minus_dm] = 0
    
    minus_dm[minus_dm < 0] = 0
    minus_dm[minus_dm < plus_dm] = 0
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.ewm(alpha=1/length, adjust=False).mean()
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/length, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/length, adjust=False).mean() / atr)
    
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di)).abs()
    adx = dx.ewm(alpha=1/length, adjust=False).mean()
    
    return adx
