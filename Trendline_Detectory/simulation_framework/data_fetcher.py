"""
Simulation Framework: Data Fetcher
==================================

Component to download, enrich, and cache large amounts of historical 
market data from Binance.

Author: Arsenal Trading System
"""

import pandas as pd
import requests
import time
import os
import logging
from typing import Optional, Dict, List

from .indicators import calculate_ema, calculate_atr, calculate_adx

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Handles the downloading and caching of historical market data from Binance.
    
    - Fetches large datasets (e.g., 5000+ candles).
    - Enriches the data with necessary technical indicators (ATR, ADX, EMAs).
    - Caches the data in CSV files to prevent re-downloading.
    """

    def __init__(self, cache_dir: str = "data"):
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.cache_dir = os.path.join(os.path.dirname(__file__), cache_dir)
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info(f"Created cache directory: {self.cache_dir}")

    def _get_filepath(self, symbol: str, timeframe: str, limit: int) -> str:
        """Generate a standardized filepath for the cached data."""
        return os.path.join(self.cache_dir, f"{symbol}_{timeframe}_{limit}_candles.csv")

    def fetch_and_enrich_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 2000,
        force_redownload: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Main function to fetch, enrich, and cache historical data.

        Args:
            symbol: The trading symbol (e.g., "SOLUSDT").
            timeframe: The candle timeframe (e.g., "1m", "5m", "15m").
            limit: The number of candles to fetch.
            force_redownload: If True, will download the data even if a cached file exists.

        Returns:
            A pandas DataFrame with the enriched data, or None if an error occurs.
        """
        filepath = self._get_filepath(symbol, timeframe, limit)

        if not force_redownload and os.path.exists(filepath):
            logger.info(f"Loading data from cache: {filepath}")
            try:
                df = pd.read_csv(filepath, index_col='timestamp', parse_dates=True)
                return df
            except Exception as e:
                logger.warning(f"Could not read cached file {filepath}. Error: {e}. Re-downloading...")

        logger.info(f"Fetching {limit} candles for {symbol} on {timeframe} timeframe...")
        
        try:
            df = self._download_data(symbol, timeframe, limit)
            if df is None:
                return None

            logger.info("Data downloaded successfully. Enriching with technical indicators...")
            
            df_enriched = self._add_indicators(df)
            
            logger.info("Enrichment complete. Saving to cache...")
            df_enriched.to_csv(filepath)
            logger.info(f"Data saved to {filepath}")
            
            return df_enriched

        except Exception as e:
            logger.error(f"An unexpected error occurred in fetch_and_enrich_data: {e}", exc_info=True)
            return None

    def _download_data(self, symbol: str, timeframe: str, limit: int, retries: int = 3, delay: int = 5) -> Optional[pd.DataFrame]:
        """
        Downloads raw k-line data from Binance, handling pagination for large requests.
        Binance API limit is 1000 candles per request.
        """
        all_klines = []
        end_time = None
        requests_needed = (limit + 999) // 1000

        for _ in range(requests_needed):
            request_limit = min(limit - len(all_klines), 1000)
            if request_limit <= 0:
                break

            params = {'symbol': symbol, 'interval': timeframe, 'limit': request_limit}
            if end_time:
                params['endTime'] = end_time

            for attempt in range(retries):
                try:
                    response = requests.get(self.base_url, params=params, timeout=10)
                    response.raise_for_status()
                    klines = response.json()
                    
                    if not klines:
                        # No more data available
                        break

                    all_klines = klines + all_klines
                    end_time = klines[0][0] - 1 # Set end time for next request to be before the first candle of this batch
                    
                    # Pause to respect API rate limits
                    time.sleep(0.5)
                    break # Success, break retry loop

                except requests.exceptions.RequestException as e:
                    logger.warning(f"API request failed on attempt {attempt + 1}/{retries}. Error: {e}")
                    if attempt < retries - 1:
                        time.sleep(delay)
                    else:
                        logger.error("All attempts to fetch Binance data failed.")
                        return None
        
        if not all_klines:
            logger.warning("No data was downloaded.")
            return None

        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Convert columns to numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume', 'number_of_trades']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        return df.iloc[:limit] # Ensure we return exactly the number of candles requested

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds ATR, ADX, and EMAs to the DataFrame using in-house functions.
        """
        # Ensure data is sorted by time
        df.sort_index(inplace=True)

        # Add EMAs
        df['EMA_21'] = calculate_ema(df['close'], 21)
        df['EMA_100'] = calculate_ema(df['close'], 100)

        # Add ATR
        df['ATR_14'] = calculate_atr(df['high'], df['low'], df['close'], 14)

        # Add ADX
        df['ADX_14'] = calculate_adx(df['high'], df['low'], df['close'], 14)
        
        # Drop rows with NaN values created by the indicators
        df.dropna(inplace=True)
        
        logger.info("Added indicators: EMA_21, EMA_100, ATR_14, ADX_14")
        return df

if __name__ == '__main__':
    logger.info("--- Running DataFetcher Standalone Test ---")
    
    fetcher = DataFetcher()
    
    # Fetch data for multiple timeframes as requested in the plan
    lookbacks = {
        "1m": 5000,
        "3m": 3000,
        "5m": 2000,
        "15m": 1000
    }
    
    for timeframe, limit in lookbacks.items():
        logger.info(f"--- Processing {timeframe} data ---")
        enriched_data = fetcher.fetch_and_enrich_data(
            symbol="SOLUSDT",
            timeframe=timeframe,
            limit=limit,
            force_redownload=False # Set to True to always re-download
        )
        
        if enriched_data is not None:
            logger.info(f"Successfully fetched and enriched {len(enriched_data)} candles for {timeframe}.")
            logger.info("Sample of the data:")
            print(enriched_data.head())
            print(enriched_data.tail())
        else:
            logger.error(f"Failed to process data for {timeframe}.")
            
    logger.info("--- DataFetcher Standalone Test Complete ---")
