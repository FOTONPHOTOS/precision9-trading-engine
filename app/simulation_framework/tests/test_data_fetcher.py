"""
Tests for the DataFetcher component of the Simulation Framework.
"""

import unittest
import pandas as pd
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from simulation_framework.data_fetcher import DataFetcher

# Increase sample data to 500 to ensure enough data remains after indicator calculation
SAMPLE_KLINES = []
start_time = int(datetime(2023, 1, 1).timestamp() * 1000)
for i in range(500):
    SAMPLE_KLINES.append([
        start_time + i * 60000, # Timestamp (1 minute intervals)
        f"{166.10 + i*0.01}", f"{166.20 + i*0.01}", f"{166.00 + i*0.01}", f"{166.15 + i*0.01}", "1000.0",
        start_time + i * 60000 + 59999,
        "166150.0", 100, "500.0", "83075.0", "0"
    ])

class TestDataFetcher(unittest.TestCase):
    """Unit tests for the DataFetcher class."""

    def setUp(self):
        """Set up the test environment."""
        self.test_cache_dir = "test_cache"
        self.fetcher = DataFetcher(cache_dir=self.test_cache_dir)
        # Clean up any old test cache files
        if os.path.exists(self.fetcher.cache_dir):
            for f in os.listdir(self.fetcher.cache_dir):
                os.remove(os.path.join(self.fetcher.cache_dir, f))

    def tearDown(self):
        """Tear down the test environment."""
        if os.path.exists(self.fetcher.cache_dir):
            for f in os.listdir(self.fetcher.cache_dir):
                os.remove(os.path.join(self.fetcher.cache_dir, f))
            os.rmdir(self.fetcher.cache_dir)

    @patch('requests.get')
    def test_fetch_and_enrich_data_success(self, mock_get):
        """Test successful fetching, enriching, and caching of data."""
        # Configure the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_KLINES
        mock_get.return_value = mock_response

        # Define parameters
        symbol = "TESTUSDT"
        timeframe = "1m"
        limit = 400 # Use a limit less than the sample data size

        # Run the function
        df = self.fetcher.fetch_and_enrich_data(symbol, timeframe, limit, force_redownload=True)

        # 1. Verify the DataFrame is returned and is not empty
        self.assertIsNotNone(df)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)

        # 2. Verify all required indicator columns were added
        expected_columns = ['EMA_21', 'EMA_100', 'ATR_14', 'ADX_14']
        for col in expected_columns:
            self.assertIn(col, df.columns)

        # 3. Verify that NaN values from indicator calculation were dropped
        self.assertFalse(df.isnull().values.any())

        # 4. Verify the data was cached
        expected_filepath = self.fetcher._get_filepath(symbol, timeframe, limit)
        self.assertTrue(os.path.exists(expected_filepath))

    def test_caching_logic(self):
        """Test that the fetcher correctly loads data from the cache if it exists."""
        symbol = "CACHEUSDT"
        timeframe = "5m"
        limit = 50
        filepath = self.fetcher._get_filepath(symbol, timeframe, limit)

        # Create a more realistic dummy cache file with a timestamp column
        timestamps = pd.to_datetime([datetime(2023, 1, 1, 0, 0) + timedelta(minutes=5*i) for i in range(3)])
        dummy_df = pd.DataFrame({'close': [1, 2, 3]}, index=timestamps)
        dummy_df.index.name = 'timestamp'
        dummy_df.to_csv(filepath)

        # Run the fetcher without forcing re-download
        # No API mock is needed, as it should load directly from the created file.
        with patch('requests.get') as mock_get:
            df = self.fetcher.fetch_and_enrich_data(symbol, timeframe, limit)
            # Assert that the API was NOT called
            mock_get.assert_not_called()

        # Verify the DataFrame loaded from cache is the one we created
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)
        self.assertEqual(df.index.name, 'timestamp')

if __name__ == '__main__':
    unittest.main()
