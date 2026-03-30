"""
Tests for the Simulator Engine component of the Simulation Framework.
"""

import unittest
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

from simulation_framework.engine import Simulator

# A simple callback for testing purposes
def dummy_callback(df: pd.DataFrame) -> Dict[str, Any]:
    """Returns the close price and the row count of the data it receives."""
    return {
        'latest_close': df['close'].iloc[-1],
        'data_length': len(df)
    }

class TestSimulator(unittest.TestCase):
    """Unit tests for the Simulator class."""

    def setUp(self):
        """Set up a synthetic DataFrame for testing."""
        self.base_time = datetime(2023, 1, 1, 0, 0)
        data = []
        for i in range(200): # 200 minutes of data
            data.append({
                'timestamp': self.base_time + timedelta(minutes=i),
                'close': 100 + i
            })
        self.df = pd.DataFrame(data).set_index('timestamp')
        self.simulator = Simulator(data=self.df)

    def test_run_simulation_successfully(self):
        """Test a successful run of the simulator."""
        start_time = self.base_time + timedelta(minutes=50)
        end_time = self.base_time + timedelta(minutes=54) # 5 candles
        
        self.simulator.run(
            scenario_start_time=start_time,
            scenario_end_time=end_time,
            callback=dummy_callback,
            warmup_period=10 # Use 10 candles before the start time
        )
        
        results = self.simulator.get_results()
        
        # We expect 5 results, one for each candle in the scenario
        self.assertEqual(len(results), 5)
        
        # Check the first result
        # It corresponds to the candle at `start_time`
        # The data passed to the callback should include the warmup period.
        # The first iteration of the loop will have i = warmup_period (10).
        # The slice will be [:11], so the length is 11.
        self.assertEqual(results['data_length'].iloc[0], 11)
        self.assertEqual(results['latest_close'].iloc[0], 100 + 50)
        
        # Check the last result
        # The scenario data has length 15 (from index 40 to 54 inclusive).
        # The last iteration will pass the full scenario_data slice.
        self.assertEqual(results['data_length'].iloc[-1], 15)
        self.assertEqual(results['latest_close'].iloc[-1], 100 + 54)

    def test_invalid_timestamp_error(self):
        """Test that the simulator handles a timestamp not found in the data."""
        start_time = self.base_time + timedelta(minutes=50)
        invalid_end_time = self.base_time + timedelta(days=5) # A time outside our data range
        
        # This should log an error but not crash
        self.simulator.run(
            scenario_start_time=start_time,
            scenario_end_time=invalid_end_time,
            callback=dummy_callback
        )
        
        results = self.simulator.get_results()
        self.assertTrue(results.empty)

    def test_constructor_with_invalid_data(self):
        """Test that the constructor raises an error with invalid data."""
        with self.assertRaises(ValueError):
            Simulator(data=pd.DataFrame()) # Empty dataframe
            
        with self.assertRaises(ValueError):
            Simulator(data=None) # None dataframe

if __name__ == '__main__':
    unittest.main()
