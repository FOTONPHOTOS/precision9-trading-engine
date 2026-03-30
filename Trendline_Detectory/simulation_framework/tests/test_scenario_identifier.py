"""
Tests for the ScenarioIdentifier component of the Simulation Framework.
"""

import unittest
import pandas as pd
from datetime import datetime, timedelta

from simulation_framework.scenario_identifier import ScenarioIdentifier, MarketScenario

class TestScenarioIdentifier(unittest.TestCase):
    """Unit tests for the ScenarioIdentifier class."""

    def setUp(self):
        """Set up a synthetic DataFrame with clear regimes for testing."""
        self.identifier = ScenarioIdentifier()
        
        # --- Create Synthetic Data ---
        # This data will have three distinct, mathematically perfect regimes:
        # 1. Consolidation (2 hours)
        # 2. Strong Uptrend (3 hours)
        # 3. Consolidation (2 hours)
        
        base_time = datetime(2023, 1, 1, 0, 0)
        data = []
        
        # Regime 1: Consolidation (2 hours, 120 minutes)
        # Range: 100-102 (2%), ADX: 15
        for i in range(120):
            price = 101 + (i % 2) # Oscillates between 101 and 102
            data.append({
                'timestamp': base_time + timedelta(minutes=i),
                'open': price, 'high': 102, 'low': 100, 'close': price,
                'ADX_14': 15, 'EMA_21': 101, 'EMA_100': 101.1
            })

        # Regime 2: Strong Uptrend (3 hours, 180 minutes)
        # ADX: 40, Price > EMA21 > EMA100
        for i in range(180):
            price = 102 + i * 0.1
            ema_21 = price - 0.5
            ema_100 = price - 2.0
            data.append({
                'timestamp': base_time + timedelta(minutes=120 + i),
                'open': price, 'high': price + 0.1, 'low': price - 0.1, 'close': price,
                'ADX_14': 40, 'EMA_21': ema_21, 'EMA_100': ema_100
            })
            
        # Regime 3: Consolidation (2 hours, 120 minutes)
        # Range: 120-122.4 (2%), ADX: 18
        start_price_regime_3 = 102 + 179 * 0.1
        for i in range(120):
            price = start_price_regime_3 + (i % 2)
            data.append({
                'timestamp': base_time + timedelta(minutes=300 + i),
                'open': price, 'high': start_price_regime_3 + 2, 'low': start_price_regime_3, 'close': price,
                'ADX_14': 18, 'EMA_21': start_price_regime_3 + 1, 'EMA_100': start_price_regime_3 + 0.9
            })

        self.df = pd.DataFrame(data)
        self.df.set_index('timestamp', inplace=True)

    def test_find_consolidation_periods(self):
        """Test that consolidation periods are correctly identified."""
        # Use parameters that should precisely find our synthetic consolidation
        scenarios = self.identifier.find_consolidation_periods(
            self.df,
            min_duration_hours=1.5, # Our ranges are 2 hours long
            min_range_pct=1.5,
            max_range_pct=2.5,
            adx_threshold=19
        )
        
        # We should find exactly 2 consolidation scenarios
        self.assertEqual(len(scenarios), 2)
        
        # Check the first scenario
        s1 = scenarios[0]
        self.assertEqual(s1.scenario_type, 'CONSOLIDATION')
        self.assertAlmostEqual(s1.details['range_high'], 102, delta=0.1)
        self.assertAlmostEqual(s1.details['range_low'], 100, delta=0.1)
        self.assertAlmostEqual(s1.details['avg_adx'], 15, delta=0.1)

        # Check the second scenario
        s2 = scenarios[1]
        self.assertEqual(s2.scenario_type, 'CONSOLIDATION')
        self.assertAlmostEqual(s2.details['avg_adx'], 18, delta=0.1)

    def test_find_trending_periods(self):
        """Test that trending periods are correctly identified."""
        scenarios = self.identifier.find_trending_periods(
            self.df,
            min_duration_hours=2.5, # Our trend is 3 hours long
            adx_threshold=35,
            ema_separation_pct=0.1
        )
        
        # We should find exactly 1 trending scenario
        self.assertEqual(len(scenarios), 1)
        
        s1 = scenarios[0]
        self.assertEqual(s1.scenario_type, 'TRENDING_UP')
        self.assertAlmostEqual(s1.details['avg_adx'], 40, delta=0.1)
        self.assertGreater(s1.details['end_price'], s1.details['start_price'])

if __name__ == '__main__':
    unittest.main()
