"""
Tests for the MasterRegimeClassifier component of the Market Regime Engine.
"""

import unittest
import pandas as pd
from datetime import datetime, timedelta

from market_regime_engine.classifier import MasterRegimeClassifier
from market_regime_engine.definitions import MarketRegime

class TestMasterRegimeClassifier(unittest.TestCase):
    """Unit tests for the MasterRegimeClassifier class."""

    def setUp(self):
        """Set up a synthetic DataFrame with a clear regime change."""
        # This data simulates a market transitioning from consolidation to a strong uptrend.
        base_time = datetime(2023, 1, 1, 0, 0)
        data = []
        
        # Part 1: Consolidation (150 minutes)
        # ADX is low, EMAs are close and flat.
        for i in range(150):
            data.append({
                'timestamp': base_time + timedelta(minutes=i),
                'open': 100, 'high': 101, 'low': 99, 'close': 100,
                'ADX_14': 15, 'EMA_21': 100.1, 'EMA_100': 100.0, 'ATR_14': 1.0
            })

        # Part 2: Strong Uptrend (150 minutes)
        # ADX is high, EMAs are separating and angled up.
        for i in range(150):
            price = 100 + i * 0.2
            data.append({
                'timestamp': base_time + timedelta(minutes=150 + i),
                'open': price, 'high': price + 0.1, 'low': price - 0.1, 'close': price,
                'ADX_14': 40, 'EMA_21': price - 0.5, 'EMA_100': price - 2.0, 'ATR_14': 1.5
            })

        self.df = pd.DataFrame(data).set_index('timestamp')

    def test_regime_classification_and_hysteresis(self):
        """Test the entire classification process, including the state change."""
        # Hysteresis period of 3 means we need 3 consecutive signals to change regime.
        classifier = MasterRegimeClassifier(hysteresis_period=3)
        
        # --- Test the initial consolidation phase ---
        # Analyze the first 140 candles. The regime should be CONSOLIDATING.
        initial_period_df = self.df.iloc[:140]
        classification = classifier.analyze(initial_period_df)
        self.assertEqual(classification.current_regime, MarketRegime.CONSOLIDATING)
        self.assertFalse(classification.is_new_regime)

        # --- Test the transition ---
        # Now, we simulate the engine running candle by candle through the transition.
        
        # Candle 1 into the trend: Potential is TRENDING_UP, but current is still CONSOLIDATING
        transition_df_1 = self.df.iloc[:151] # 1st candle of the trend
        classification_1 = classifier.analyze(transition_df_1)
        self.assertEqual(classification_1.current_regime, MarketRegime.CONSOLIDATING)
        self.assertFalse(classification_1.is_new_regime)
        self.assertIn(MarketRegime.TRENDING_UP, classifier.regime_history)

        # Candle 2 into the trend: Still CONSOLIDATING, history is filling up
        transition_df_2 = self.df.iloc[:152] # 2nd candle of the trend
        classification_2 = classifier.analyze(transition_df_2)
        self.assertEqual(classification_2.current_regime, MarketRegime.CONSOLIDATING)
        self.assertFalse(classification_2.is_new_regime)

        # Candle 3 into the trend: REGIME CHANGE should occur now.
        transition_df_3 = self.df.iloc[:153] # 3rd candle of the trend
        classification_3 = classifier.analyze(transition_df_3)
        self.assertEqual(classification_3.current_regime, MarketRegime.TRENDING_UP)
        self.assertTrue(classification_3.is_new_regime)
        self.assertEqual(classification_3.message, "REGIME CHANGE DETECTED: New regime is TRENDING_UP.")

        # Candle 4 into the trend: Should remain TRENDING_UP, no longer a new regime.
        transition_df_4 = self.df.iloc[:154] # 4th candle of the trend
        classification_4 = classifier.analyze(transition_df_4)
        self.assertEqual(classification_4.current_regime, MarketRegime.TRENDING_UP)
        self.assertFalse(classification_4.is_new_regime)

if __name__ == '__main__':
    unittest.main()
