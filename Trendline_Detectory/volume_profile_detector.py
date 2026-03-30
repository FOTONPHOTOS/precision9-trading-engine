import pandas as pd
import sys
from typing import Dict, Optional

# Add the path to the cloned library
MARKET_PROFILE_LIB_PATH = "G:/python files/precision9/Simulation Environment/Trendline_Detectory/libs/py-market-profile/src"
if MARKET_PROFILE_LIB_PATH not in sys.path:
    sys.path.append(MARKET_PROFILE_LIB_PATH)

from market_profile import MarketProfile

class VolumeProfileDetector:
    """
    Analyzes the volume profile of a given dataset to identify key levels
    of institutional interest, such as the Point of Control (POC) and High-Volume Nodes (HVNs).
    """

    def __init__(self, period: str = '1D'):
        self.period = period # Default to daily profile

    def analyze(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Generates the volume profile and extracts key zones.

        Args:
            df: The OHLCV DataFrame with lowercase columns.

        Returns:
            A dictionary containing the POC and a list of HVNs, or None if analysis fails.
        """
        if df.empty or len(df) < 20:
            return None

        try:
            # The market_profile library expects specific column names
            profile_df = df.copy()
            profile_df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
            
            # The library expects a DatetimeIndex
            if not isinstance(profile_df.index, pd.DatetimeIndex):
                 profile_df.index = pd.to_datetime(profile_df.index)

            # 1. Initialize MarketProfile
            mp = MarketProfile(profile_df, tick_size=1.0)
            
            # 2. Create a slice covering the entire dataframe to build the profile
            mp_slice = mp[profile_df.index[0]:profile_df.index[-1]]

            # 3. Extract the data from the slice object
            poc = mp_slice.poc_price
            
            # The hvn/lvn attributes are pandas Series, convert them to the expected dict format
            hvns = [{'price': price, 'volume': volume} for price, volume in mp_slice.high_value_nodes.items()]
            lvns = [{'price': price, 'volume': volume} for price, volume in mp_slice.low_value_nodes.items()]

            return {
                'poc': poc,
                'hvns': hvns,
                'lvns': lvns
            }
        except Exception as e:
            # The library can be sensitive to data format, so catch errors gracefully
            print(f"[VolumeProfileDetector] Error: {e}")
            return None
