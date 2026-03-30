"""
Tests for the Metrics Calculation component of the Market Regime Engine.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from market_regime_engine.metrics import (
    calculate_volatility_profile,
    calculate_ma_behavior,
    calculate_adx_metric
)

class TestMetrics(unittest.TestCase):
    """Unit tests for the metric calculation functions."""

    def setUp(self):
        """Set up a synthetic DataFrame with predictable indicator values."""
        data = []
        base_time = datetime(2023, 1, 1)
        for i in range(50):
            data.append({
                'timestamp': base_time + timedelta(minutes=i),
                'high': 100 + i * 0.1 + 0.1,
                'low': 100 + i * 0.1 - 0.1,
                'close': 100 + i * 0.1,
                'ATR_14': 0.2 + i * 0.01, # Steadily increasing ATR
                'EMA_21': 99 + i * 0.1,
                'EMA_100': 95 + i * 0.05, # Slower sloping EMA
                'ADX_14': 30 + i * 0.5 # Steadily increasing ADX
            })
        self.df = pd.DataFrame(data).set_index('timestamp')

    def test_calculate_volatility_profile(self):
        """Test the calculation of ATR percentage and slope."""
        volatility = calculate_volatility_profile(self.df, slope_length=10)
        
        # Check ATR percentage (latest ATR / latest close)
        latest_atr = 0.2 + 49 * 0.01
        latest_close = 100 + 49 * 0.1
        expected_atr_pct = (latest_atr / latest_close) * 100
        self.assertAlmostEqual(volatility['atr_pct'], expected_atr_pct, places=4)
        
        # Check ATR slope (should be positive as it's increasing)
        self.assertGreater(volatility['atr_slope'], 0)

    def test_calculate_ma_behavior(self):
        """Test the analysis of moving average behavior."""
        ma_behavior = calculate_ma_behavior(self.df, slope_length=10)
        
        # Check relationships
        self.assertEqual(ma_behavior['price_vs_ema21'], 'above')
        self.assertEqual(ma_behavior['ema21_vs_ema100'], 'above')
        
        # Check separation
        latest_ema21 = 99 + 49 * 0.1
        latest_ema100 = 95 + 49 * 0.05
        expected_sep_pct = (abs(latest_ema21 - latest_ema100) / latest_ema100) * 100
        self.assertAlmostEqual(ma_behavior['ema_separation_pct'], expected_sep_pct, places=4)
        
        # Check slope of long-term EMA (should be positive)
        self.assertGreater(ma_behavior['ema_100_slope'], 0)

    def test_calculate_adx_metric(self):
        """Test the extraction of the ADX value."""
        adx = calculate_adx_metric(self.df)
        expected_adx = 30 + 49 * 0.5
        self.assertEqual(adx, expected_adx)

if __name__ == '__main__':
    unittest.main()
