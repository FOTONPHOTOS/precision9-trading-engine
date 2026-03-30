
import pandas as pd
import numpy as np
from typing import List

def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """Calculates the Relative Strength Index (RSI). Returns the last RSI value."""
    if len(closes) < period + 1:  # Need at least period+1 values for proper RSI calculation
        # If not enough data, return neutral RSI of 50
        return 50.0
    
    closes_series = pd.Series(closes)
    delta = closes_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    # Replace any zero values in loss to avoid division by zero
    loss = loss.replace(0, 0.001)
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Return the last RSI value
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates the Average True Range (ATR)."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(period).mean()
    return atr.iloc[-1]
