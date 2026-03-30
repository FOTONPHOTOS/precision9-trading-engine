'''
Binance Data Engine
=====================

This module is responsible for fetching, caching, and processing a wide range
of market data from Binance, including Open Interest (OI), Funding Rates (FR),
Taker Volume, and Long/Short Ratios to produce indices like LCI and GLS.

'''

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging
import asyncio
from binance import AsyncClient

logger = logging.getLogger(__name__)

# --- Index Calculation Logic ---

def sigmoid(x):
    """Sigmoid function to normalize a value between 0 and 1."""
    return 1 / (1 + np.exp(-x))

def compute_lci(symbol: str, global_long_short_ratio: Optional[float]) -> float:
    """ 
    Calculates the Local Crowd Index (LCI) for a given symbol using the
    direct Global Long/Short Account Ratio.

    LCI measures how crowded or one-sided the market positioning is.
    A high LCI (> 0.7) suggests longs are crowded.
    A low LCI (< 0.3) suggests shorts are crowded.
    """
    if global_long_short_ratio is None:
        logger.warning(f"Long/Short Ratio not available for {symbol}. Returning neutral LCI of 0.5.")
        return 0.5

    # The long/short ratio gives us a direct measure of crowd sentiment.
    # A ratio of 1.0 is neutral. > 1 means more longs, < 1 means more shorts.
    # We can map this ratio to our 0-1 LCI scale.
    
    # Simple linear mapping: Cap the ratio to a reasonable range [0.5, 2.5] to avoid extreme LCI values.
    # A ratio of 0.5 (twice as many shorts as longs) will map to LCI ~0.1
    # A ratio of 2.5 (2.5x more longs than shorts) will map to LCI ~0.9
    capped_ratio = max(0.5, min(global_long_short_ratio, 2.5))
    
    # Interpolate the capped ratio onto the LCI scale [0.1, 0.9]
    lci = np.interp(capped_ratio, [0.5, 2.5], [0.1, 0.9])

    if lci > 0.75:
        sentiment = f"heavily crowded long (L/S Ratio: {global_long_short_ratio:.2f})"
    elif lci > 0.55:
        sentiment = f"leaning long (L/S Ratio: {global_long_short_ratio:.2f})"
    elif lci < 0.25:
        sentiment = f"heavily crowded short (L/S Ratio: {global_long_short_ratio:.2f})"
    elif lci < 0.45:
        sentiment = f"leaning short (L/S Ratio: {global_long_short_ratio:.2f})"
    else:
        sentiment = f"neutral (L/S Ratio: {global_long_short_ratio:.2f})"

    logger.info(f"[LCI] Crowd sentiment for {symbol} is {sentiment}. LCI set to {lci:.2f}")
    return lci

def compute_gls(btc_oi_history: pd.Series, btc_fr_history: pd.Series) -> float:
    """
    Calculates the Global Leverage Stress (GLS) index using BTC data.
    
    GLS measures the overall systemic risk and leverage in the market.
    A high GLS suggests all bots should behave more cautiously.
    """
    if btc_oi_history.empty or len(btc_oi_history) < 24 or btc_fr_history.empty:
        logger.warning("Insufficient data to calculate GLS. Returning neutral 0.5.")
        return 0.5

    pct_oi_change_btc = (btc_oi_history.iloc[-1] - btc_oi_history.iloc[-24]) / btc_oi_history.iloc[-24] if btc_oi_history.iloc[-24] != 0 else 0
    abs_funding_btc_norm = abs(btc_fr_history.iloc[-1] / btc_fr_history.mean()) if btc_fr_history.mean() != 0 else 1
    
    # Raw GLS score calculation (weights from the plan)
    gls_raw = (0.4 * pct_oi_change_btc) + (0.6 * abs_funding_btc_norm)
    
    # Normalize the raw score to be between 0 and 1
    gls_normalized = sigmoid(gls_raw)

    logger.debug(f"GLS calculated: {gls_normalized:.2f} (Raw: {gls_raw:.2f})")
    return gls_normalized


class BinanceDataEngine:
    """
    A stateful engine to manage fetching and caching of various Binance market data.
    NOW USES A LIVE BINANCE CLIENT.
    """
    def __init__(self, symbol: str, client: AsyncClient, cache_ttl_seconds: int = 300):
        self.symbol = symbol
        self.client = client
        self.cache_ttl = pd.Timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, Any] = {
            "data": None,
            "timestamp": None
        }

    async def _fetch_data(self) -> Optional[Dict[str, Any]]:
        """Fetches live OI and Funding Rate from Binance."""
        try:
            # Check for method availability before calling
            tasks = []
            task_types = []

            # Check for Open Interest method
            if hasattr(self.client, 'futures_open_interest'):
                oi_task = self.client.futures_open_interest(symbol=self.symbol)
                tasks.append(oi_task)
                task_types.append('oi')
            else:
                logger.warning(f"futures_open_interest not available for {self.symbol}")
                return None  # Can't proceed without open interest data

            # Check for Funding Rate method
            if hasattr(self.client, 'futures_funding_rate'):
                fr_task = self.client.futures_funding_rate(symbol=self.symbol)
                tasks.append(fr_task)
                task_types.append('fr')
            else:
                logger.warning(f"futures_funding_rate not available for {self.symbol}")
                return None  # Can't proceed without funding rate data

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Map results back to their types
            oi_result = None
            fr_result = None
            for i, task_type in enumerate(task_types):
                if task_type == 'oi':
                    oi_result = results[i]
                elif task_type == 'fr':
                    fr_result = results[i]

            if isinstance(oi_result, Exception):
                logger.error(f"Failed to fetch Open Interest for {self.symbol}: {oi_result}")
                return None
            if isinstance(fr_result, Exception):
                logger.error(f"Failed to fetch Funding Rate for {self.symbol}: {fr_result}")
                return None

            # The funding rate endpoint returns a list, we want the latest
            if not fr_result:
                logger.error(f"No funding rate data returned for {self.symbol}")
                return None

            latest_funding_rate = sorted(fr_result, key=lambda x: int(x['fundingTime']), reverse=True)[0]

            return {
                "open_interest": float(oi_result['openInterest']),
                "funding_rate": float(latest_funding_rate['fundingRate'])
            }
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching OI/FR data for {self.symbol}: {e}", exc_info=True)
            return None # Return None on failure

    async def get_data(self) -> Optional[Dict[str, Any]]:
        """Retrieves data from cache or fetches new data if cache is stale."""
        now = pd.Timestamp.utcnow()
        if self._cache["timestamp"] is None or (now - self._cache["timestamp"]) > self.cache_ttl:
            logger.info(f"OI/FR cache for {self.symbol} is stale. Fetching new data.")
            self._cache["data"] = await self._fetch_data()
            self._cache["timestamp"] = now
        
        return self._cache["data"]

    async def get_historical_data(self, period: str = "5m", limit: int = 50) -> Dict[str, pd.Series]:
        """
        Fetches historical OI and FR data.
        NOTE: python-binance does not have a direct endpoint for historical funding rates.
        This implementation will fetch historical OI and for funding rate, it will use the last 1000 funding rates.
        This is a limitation of the library.
        """
        try:
            # Check for available methods and use alternatives if not available
            tasks = []
            task_types = []

            # Fetch historical Open Interest
            if hasattr(self.client, 'futures_open_interest_hist'):
                oi_hist_task = self.client.futures_open_interest_hist(symbol=self.symbol, period=period, limit=limit)
                tasks.append(oi_hist_task)
                task_types.append('oi')
            else:
                logger.warning(f"futures_open_interest_hist not available for {self.symbol}")
                tasks.append(None)
                task_types.append('oi')

            # Fetch funding rate history - standard method may not accept limit parameter
            if hasattr(self.client, 'futures_funding_rate'):
                # Standard call without limit parameter that may not be supported
                fr_hist_task = self.client.futures_funding_rate(symbol=self.symbol)
                tasks.append(fr_hist_task)
                task_types.append('fr')
            else:
                logger.warning(f"futures_funding_rate not available for {self.symbol}")
                tasks.append(None)
                task_types.append('fr')

            # Execute only the tasks that exist
            active_tasks = [task for task in tasks if task is not None]
            if not active_tasks:
                logger.warning(f"No available methods for historical data for {self.symbol}")
                return {"oi_history": pd.Series(dtype=np.float64), "fr_history": pd.Series(dtype=np.float64)}

            results = await asyncio.gather(*active_tasks, return_exceptions=True)

            oi_series = pd.Series(dtype=np.float64)
            fr_series = pd.Series(dtype=np.float64)

            # Process results
            active_idx = 0
            for i, task_type in enumerate(task_types):
                if tasks[i] is not None:  # This task was executed
                    result = results[active_idx]
                    active_idx += 1

                    if isinstance(result, Exception):
                        if task_type == 'oi':
                            logger.error(f"Failed to fetch historical Open Interest for {self.symbol}: {result}")
                        elif task_type == 'fr':
                            logger.error(f"Failed to fetch historical Funding Rate for {self.symbol}: {result}")
                    else:
                        if task_type == 'oi':
                            oi_df = pd.DataFrame(result)
                            if 'sumOpenInterestValue' in oi_df.columns:
                                oi_series = pd.to_numeric(oi_df['sumOpenInterestValue'])
                            elif 'sumOpenInterest' in oi_df.columns:
                                oi_series = pd.to_numeric(oi_df['sumOpenInterest'])
                            else:
                                logger.warning(f"Open interest data doesn't contain expected columns: {list(oi_df.columns)}")
                        elif task_type == 'fr':
                            # The funding rate endpoint returns a list, we want the column with rates
                            fr_df = pd.DataFrame(result)
                            if 'fundingRate' in fr_df.columns:
                                fr_series = pd.to_numeric(fr_df['fundingRate'])
                            else:
                                logger.warning(f"Funding rate data doesn't contain expected columns: {list(fr_df.columns)}")

            return {
                "oi_history": oi_series,
                "fr_history": fr_series
            }

        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching historical OI/FR data for {self.symbol}: {e}", exc_info=True)
            return {"oi_history": pd.Series(dtype=np.float64), "fr_history": pd.Series(dtype=np.float64)}

    async def get_taker_long_short_ratio(self, period: str = "5m") -> Optional[float]:
        """Fetches the latest taker buy/sell ratio for the symbol."""
        try:
            # Check which method is available in the library
            if hasattr(self.client, 'futures_global_longshort_ratio'):
                ratio_hist = await self.client.futures_global_longshort_ratio(symbol=self.symbol, period=period, limit=1)
            elif hasattr(self.client, 'futures_get_global_long_short_ratio'):
                ratio_hist = await self.client.futures_get_global_long_short_ratio(symbol=self.symbol, period=period, limit=1)
            elif hasattr(self.client, 'futures_get_global_long_short_account_ratio'):
                ratio_hist = await self.client.futures_get_global_long_short_account_ratio(symbol=self.symbol, period=period, limit=1)
            else:
                logger.warning(f"No long/short ratio method available for {self.symbol}")
                return None

            if not ratio_hist or len(ratio_hist) == 0:
                logger.warning(f"Taker Long/Short Ratio data not available for {self.symbol}")
                return None

            # Extract the correct field from the response
            first_record = ratio_hist[0]
            if isinstance(first_record, dict):
                # Common field names in Binance API responses
                value_field = 'value' if 'value' in first_record else 'avgPositionRatio' if 'avgPositionRatio' in first_record else 'longShortRatio' if 'longShortRatio' in first_record else 'buySellRatio' if 'buySellRatio' in first_record else 'longAccount'

                if value_field in first_record:
                    latest_ratio = float(first_record[value_field])
                    return latest_ratio
                else:
                    logger.warning(f"Unknown field name in ratio response for {self.symbol}. Keys: {list(first_record.keys())}")
                    return None
            else:
                logger.warning(f"Unexpected response format for {self.symbol} ratio data: {type(first_record)}")
                return None

        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching Taker Long/Short Ratio for {self.symbol}: {e}", exc_info=True)
            return None

    async def get_taker_ratio_analysis(self, period: str = "5m", limit: int = 20) -> Optional[Dict[str, float]]:
        """Fetches the latest taker ratio and its moving average."""
        try:
            # Try different methods that may be available in python-binance
            # Method 1: futures_global_longshort_ratio
            if hasattr(self.client, 'futures_global_longshort_ratio'):
                ratio_hist = await self.client.futures_global_longshort_ratio(symbol=self.symbol, period=period, limit=limit)
            elif hasattr(self.client, 'futures_get_global_long_short_ratio'):
                # Alternative name in some versions
                ratio_hist = await self.client.futures_get_global_long_short_ratio(symbol=self.symbol, period=period, limit=limit)
            elif hasattr(self.client, 'futures_get_global_long_short_account_ratio'):
                # Another possible name
                ratio_hist = await self.client.futures_get_global_long_short_account_ratio(symbol=self.symbol, period=period, limit=limit)
            else:
                logger.warning(f"No long-short ratio method available for {self.symbol}. Returning None.")
                return None

            if not ratio_hist or len(ratio_hist) < limit:
                logger.warning(f"Insufficient Taker Long/Short Ratio history for {self.symbol} to calculate MA (received {len(ratio_hist) if ratio_hist else 0}, need {limit}).")
                # Still return whatever we have, don't require the exact limit
                if not ratio_hist or len(ratio_hist) == 0:
                    return None

            # Determine the correct field name based on API response
            first_record = ratio_hist[0] if ratio_hist else {}
            if isinstance(first_record, dict):
                # Common field names in Binance API responses
                value_field = 'value' if 'value' in first_record else 'avgPositionRatio' if 'avgPositionRatio' in first_record else 'longShortRatio' if 'longShortRatio' in first_record else 'buySellRatio' if 'buySellRatio' in first_record else 'longAccount'

                if value_field not in first_record:
                    logger.warning(f"Unknown field name in ratio response for {self.symbol}. Keys: {list(first_record.keys())}")
                    return None

                # Create pandas Series with the extracted values
                ratios = pd.Series([float(r[value_field]) for r in ratio_hist])
            else:
                # If it's not a dict, assume it's a direct value or format we can't handle
                logger.warning(f"Unexpected response format for {self.symbol} ratio data: {type(first_record)}")
                return None

            # Calculate moving average using the actual data length
            ratio_ma = ratios.rolling(window=len(ratios), min_periods=1).mean()  # Use actual length, not hard limit

            if pd.isna(ratio_ma.iloc[-1]):
                logger.warning(f"Could not calculate Taker Ratio MA for {self.symbol}.")
                return None

            latest_ratio = ratios.iloc[-1]
            latest_ma = ratio_ma.iloc[-1]

            logger.info(f"[Taker Analysis] {self.symbol} | Latest Ratio: {latest_ratio:.2f}, MA: {latest_ma:.2f}")

            return {
                "latest_ratio": latest_ratio,
                "ratio_ma": latest_ma
            }

        except Exception as e:
            logger.error(f"An unexpected error occurred during Taker Ratio Analysis for {self.symbol}: {e}", exc_info=True)
            return None

    async def get_long_short_ratios(self, period: str = "5m") -> Optional[Dict[str, float]]:
        """Fetches the latest global and top trader long/short account ratios."""
        logger.info(f"Fetching Global and Top Trader Long/Short Ratios for {self.symbol}...")
        try:
            # Use the correct API methods that are available in python-binance
            # Check what methods are available first
            tasks = []

            # Global long/short ratio
            if hasattr(self.client, 'futures_global_longshort_ratio'):
                global_task = self.client.futures_global_longshort_ratio(symbol=self.symbol, period=period, limit=1)
                tasks.append(global_task)
            else:
                logger.warning(f"futures_global_longshort_ratio not available for {self.symbol}")
                tasks.append(None)

            # Top trader long/short ratio
            if hasattr(self.client, 'futures_top_longshort_account_ratio'):
                top_trader_task = self.client.futures_top_longshort_account_ratio(symbol=self.symbol, period=period, limit=1)
                tasks.append(top_trader_task)
            elif hasattr(self.client, 'futures_top_longshort_position_ratio'):
                # Alternative method name
                top_trader_task = self.client.futures_top_longshort_position_ratio(symbol=self.symbol, period=period, limit=1)
                tasks.append(top_trader_task)
            else:
                logger.warning(f"Neither futures_top_longshort_account_ratio nor futures_top_longshort_position_ratio available for {self.symbol}")
                tasks.append(None)

            # Only gather the tasks that exist
            active_tasks = [task for task in tasks if task is not None]

            if len(active_tasks) == 0:
                logger.warning(f"None of the long/short ratio methods are available for {self.symbol}")
                return None

            results = await asyncio.gather(*active_tasks, return_exceptions=True)

            ratios = {'global': None, 'top_trader': None}

            # Process results based on which tasks were actually run
            task_index = 0
            # Handle global ratio
            if hasattr(self.client, 'futures_global_longshort_ratio'):
                global_result = results[task_index]
                task_index += 1
                if isinstance(global_result, Exception) or not global_result or len(global_result) == 0:
                    logger.warning(f"Could not fetch Global Long/Short Ratio: {global_result}")
                else:
                    # Extract the correct field name based on API response
                    first_record = global_result[0]
                    if isinstance(first_record, dict):
                        # Possible field names in the response
                        value_field = 'value' if 'value' in first_record else 'longShortRatio' if 'longShortRatio' in first_record else 'avgPositionRatio' if 'avgPositionRatio' in first_record else 'longAccount'
                        if value_field in first_record:
                            ratios['global'] = float(first_record[value_field])
                        else:
                            logger.warning(f"Global ratio response doesn't contain expected fields: {list(first_record.keys())}")

            # Handle top trader ratio
            has_top_trader = hasattr(self.client, 'futures_top_longshort_account_ratio') or hasattr(self.client, 'futures_top_longshort_position_ratio')
            if has_top_trader and task_index < len(results):
                top_trader_result = results[task_index]
                if isinstance(top_trader_result, Exception) or not top_trader_result or len(top_trader_result) == 0:
                    logger.warning(f"Could not fetch Top Trader Long/Short Ratio: {top_trader_result}")
                else:
                    first_record = top_trader_result[0]
                    if isinstance(first_record, dict):
                        # Possible field names in the response
                        value_field = 'value' if 'value' in first_record else 'longShortRatio' if 'longShortRatio' in first_record else 'avgPositionRatio' if 'avgPositionRatio' in first_record else 'longAccount'
                        if value_field in first_record:
                            ratios['top_trader'] = float(first_record[value_field])
                        else:
                            logger.warning(f"Top trader ratio response doesn't contain expected fields: {list(first_record.keys())}")

            logger.info(f"Fetched Ratios: Global={ratios.get('global'):.2f}, Top Trader={ratios.get('top_trader'):.2f}")
            return ratios

        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching Long/Short Ratios for {self.symbol}: {e}", exc_info=True)
            return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    async def main():
        print("--- Binance Data Engine Demo (with LIVE data) ---")
        
        client = await AsyncClient.create()
        
        # Initialize engine for a symbol
        sol_engine = BinanceDataEngine(symbol="SOLUSDT", client=client)
        
        # Fetch data (will use live data)
        sol_data = await sol_engine.get_data()
        print(f"Fetched LIVE OI/FR data for SOLUSDT: {sol_data}")
        
        # Fetch historical data
        historical_data = await sol_engine.get_historical_data(limit=100)
        print(f"Fetched historical OI history count: {len(historical_data['oi_history'])}")
        print(f"Fetched historical FR history count: {len(historical_data['fr_history'])}")

        # Fetch Taker Long/Short Ratio
        taker_ratio = await sol_engine.get_taker_long_short_ratio(period="5m")
        if taker_ratio is not None:
            print(f"Fetched 5m Taker Buy/Sell Ratio for SOLUSDT: {taker_ratio:.4f}")
        else:
            print("Could not fetch Taker Buy/Sell Ratio.")

        # --- NEW: Fetch Global and Top Trader Ratios ---
        long_short_ratios = await sol_engine.get_long_short_ratios(period="5m")
        if long_short_ratios:
            print(f"Fetched 5m Long/Short Ratios for SOLUSDT: {long_short_ratios}")
        else:
            print("Could not fetch Long/Short Ratios.")

        if not historical_data['oi_history'].empty and not historical_data['fr_history'].empty:
            # Calculate GLS (using BTC data)
            btc_engine = BinanceDataEngine(symbol="BTCUSDT", client=client)
            btc_hist = await btc_engine.get_historical_data(limit=100)
            if not btc_hist['oi_history'].empty and not btc_hist['fr_history'].empty:
                gls = compute_gls(btc_oi_history=btc_hist['oi_history'], btc_fr_history=btc_hist['fr_history'])
                print(f"Global Leverage Stress (GLS) Index: {gls:.2f}")
            else:
                print("Could not calculate GLS due to missing BTC historical data.")

            # Calculate LCI (Note: The actual LCI calculation uses long/short ratio, not historical data)
            # This is just for the demo - in the actual system, LCI is calculated using long/short ratios
            lci = compute_lci(symbol="SOLUSDT", global_long_short_ratio=long_short_ratios.get('global') if long_short_ratios else None)
            print(f"Local Crowd Index (LCI) for SOLUSDT: {lci:.2f}")
        else:
            print("Could not calculate indices due to missing historical data.")

        await client.close_connection()

    asyncio.run(main())