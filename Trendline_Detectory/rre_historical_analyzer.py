"""
RRE Historical Analyzer
=======================

This module provides a historical analysis tool for the Range Regime Engine (RRE).
It runs on startup, analyzing the last two weeks of market data to identify
past ranges, providing a quick way to validate and tune the RRE's performance
without waiting for live market conditions.
"""

import pandas as pd

# Import pandas_ta with error handling for systems where it might not be available
try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
    print("pandas_ta library loaded successfully")
except ImportError:
    ta = None
    PANDAS_TA_AVAILABLE = False
    print("Warning: pandas_ta library not available. Some technical analysis features may be limited.")

from datetime import datetime, timedelta
import logging
from typing import List, Dict

# Assuming the following modules are in the same directory or accessible
from range_regime_engine import RREngine
from realtime_swing_detector import fetch_binance_data
from test_ultimate_arsenal import find_swing_highs, find_swing_lows
from fvg_detector import FVGDetector
from order_block_detector import OrderBlockDetector
from volume_profile_detector import VolumeProfileDetector

logger = logging.getLogger(__name__)

class RREHistoricalAnalyzer:
    """
    Analyzes historical data using the RRE to identify past market ranges.
    """

    def __init__(self, rre_engine: RREngine, client, symbol: str, timeframe: str = "5m"):
        self.rre = rre_engine
        self.client = client
        self.symbol = symbol
        self.timeframe = timeframe
        self.fvg_detector = FVGDetector()
        self.ob_detector = OrderBlockDetector()
        self.volume_profile_detector = VolumeProfileDetector()

    async def run_analysis(self, days_to_analyze: int = 14):
        """
        Fetches historical data and runs the RRE analysis over it.

        Args:
            days_to_analyze (int): The number of past days to analyze.
        """
        print("\n" + "="*100)
        print(" RRE HISTORICAL ANALYSIS STARTED ".center(100, "="))
        print(f"Analyzing last {days_to_analyze} days of '{self.symbol}' data...")
        print("="*100)

        try:
            # Fetch 14 days of 5-minute data. Limit is typically 1500 per request.
            # 1 day = 288 5-min candles. 14 days = 4032 candles. Need multiple fetches.
            limit_per_fetch = 1500
            num_fetches = (days_to_analyze * 288 // limit_per_fetch) + 1
            
            all_klines = []
            end_ts = None
            for _ in range(num_fetches):
                if end_ts:
                    klines_df = await fetch_binance_data(self.client, self.symbol, self.timeframe, limit_per_fetch, endTime=end_ts)
                else:
                    klines_df = await fetch_binance_data(self.client, self.symbol, self.timeframe, limit_per_fetch)
                
                if klines_df.empty:
                    break
                
                all_klines.insert(0, klines_df)
                end_ts = int(klines_df.index[0].timestamp() * 1000)

            if not all_klines:
                logger.error("[RRE-Hist] Could not fetch any historical data.")
                return

            df_history = pd.concat(all_klines).drop_duplicates()
            df_history = df_history.sort_index()
            
            logger.info(f"[RRE-Hist] Fetched {len(df_history)} historical candles from {df_history.index[0]} to {df_history.index[-1]}.")

        except Exception as e:
            logger.error(f"[RRE-Hist] Failed to fetch historical data: {e}")
            return

        # Pre-calculate indicators for the entire dataframe for efficiency
        if PANDAS_TA_AVAILABLE and ta is not None:
            df_history.ta.adx(length=14, append=True)
            df_history.ta.atr(length=14, append=True)
        else:
            # Create empty columns when pandas_ta is not available
            df_history['ADX_14'] = 0
            df_history['ATR_14'] = 0

        # --- Historical RRE Analysis with Strategic Sampling ---
        # Run RRE analysis with better sampling to avoid excessive logging while still
        # testing the actual RRE algorithm performance historically
        logger.info(f"[RRE-Hist] Starting historical RRE performance analysis...")
        logger.info(f"[RRE-Hist] Analyzing historical data with strategic sampling...")

        # Calculate sample points at larger intervals to identify actual range periods
        # Instead of every 5 minutes, sample every 2 hours (24 data points per day instead of 288)
        sample_interval = 24  # Every 2 hours (24 * 5min intervals = 120 minutes)

        # --- Analysis Loop ---
        detected_ranges = []
        current_range_start = None
        last_state = 'NOT_RANGE'

        # Start analysis after a warmup period to ensure indicators are valid
        warmup_period = 50
        logger.info(f"[RRE-Hist] Starting analysis loop with a {warmup_period}-candle warmup...")

        for i in range(warmup_period, len(df_history), sample_interval):  # Use sample_interval instead of 1
            # Create a rolling window of the past data for each step
            window_df = df_history.iloc[max(0, i - 288):i] # Use a 24-hour lookback window (288 5-min candles)

            if len(window_df) < 50: # Ensure enough data for detectors
                continue

            # --- Prepare inputs for RRE at this point in time ---
            current_price = window_df['close'].iloc[-1]

            # Detectors - Use larger lookback to find more significant swings
            swing_highs = find_swing_highs(window_df, lookback=10)  # Larger lookback for significant swings
            swing_lows = find_swing_lows(window_df, lookback=10)
            all_swings = swing_highs + swing_lows

            active_obs = self.ob_detector.get_active_order_blocks(
                self.ob_detector.detect(window_df, current_price),
                current_price
            )
            volume_profile_zones = self.volume_profile_detector.analyze(window_df)

            # Indicators
            adx_value = window_df['ADX_14'].iloc[-1]
            current_atr = window_df['ATRr_14'].iloc[-1]
            atr_series = window_df['ATRr_14'].dropna()
            atr_percentile = (atr_series.lt(current_atr).sum() / len(atr_series)) if len(atr_series) > 0 else 0.5

            # --- Run RRE Analysis ---
            range_analysis = self.rre.analyze(
                swings=all_swings,
                hvn_zones=volume_profile_zones.get('hvns', []) if volume_profile_zones else [],
                order_blocks=active_obs,
                atr_percentile=atr_percentile,
                adx_value=adx_value,
                taker_ratio=1.0,  # Placeholder: Historical taker ratio is not available
                cvd_slope=0.0,    # Placeholder: Historical CVD is not available
                stop_hunt_prob=0.0, # Placeholder
                current_price=current_price
            )

            current_state = range_analysis.range_state
            current_time = window_df.index[-1]

            # --- State Change Logic ---
            # Only start recording ranges if they have valid geometry AND meet minimum size requirements
            has_valid_geometry = (range_analysis.geometry is not None and
                                hasattr(range_analysis.geometry, 'is_valid') and
                                range_analysis.geometry.is_valid and
                                range_analysis.geometry.low < range_analysis.geometry.high)  # Ensure valid range bounds

            # Calculate range percentage size if geometry exists
            range_size_pct = 0.0
            if has_valid_geometry and range_analysis.geometry.high > 0:
                range_size_pct = ((range_analysis.geometry.high - range_analysis.geometry.low) / range_analysis.geometry.low) * 100

            # Minimum range size threshold (in percentage) - adjust based on trading requirements
            min_range_size_pct = 0.8  # At least 0.8% range for mean reversion to be viable
            has_minimum_size = range_size_pct >= min_range_size_pct

            if (current_state in ['ESTABLISHED_RANGE', 'TIGHT_RANGE'] and
                last_state == 'NOT_RANGE' and
                has_valid_geometry and has_minimum_size):
                # A new range with valid geometry and sufficient size has started
                current_range_start = current_time
                current_range_geometry = range_analysis.geometry  # Store the geometry at range start
                logger.info(f"[RRE-Hist] New Range with valid geometry and sufficient size ({range_size_pct:.2f}%) detected at {current_time}, Score: {range_analysis.range_score:.1f}")

            elif (current_state == 'NOT_RANGE' and
                  last_state in ['ESTABLISHED_RANGE', 'TIGHT_RANGE'] and
                  current_range_start is not None):
                # The previous range has just ended (broken out)
                # Record it with the geometry from when it started (not when it ended)
                # Only if it met minimum size requirements when it began
                if 'current_range_geometry' in locals():
                    # Calculate the size of the range that was being tracked
                    recorded_range_size_pct = ((current_range_geometry.high - current_range_geometry.low) / current_range_geometry.low) * 100
                    if recorded_range_size_pct >= min_range_size_pct:
                        detected_ranges.append({
                            'start': current_range_start,
                            'end': current_time,
                            'duration_hours': (current_time - current_range_start).total_seconds() / 3600,
                            'geometry': current_range_geometry  # Use the geometry from when range began
                        })
                        logger.info(f"[RRE-Hist] Range Ended (Breakout) at {current_time}, Size: {recorded_range_size_pct:.2f}%")
                    else:
                        logger.info(f"[RRE-Hist] Small range discarded (size: {recorded_range_size_pct:.2f}%) at {current_time}")
                    current_range_geometry = None
                else:
                    # If we somehow don't have initial geometry, use current but this shouldn't happen
                    if has_valid_geometry and range_size_pct >= min_range_size_pct:
                        detected_ranges.append({
                            'start': current_range_start,
                            'end': current_time,
                            'duration_hours': (current_time - current_range_start).total_seconds() / 3600,
                            'geometry': range_analysis.geometry
                        })
                        logger.info(f"[RRE-Hist] Range Ended without initial geometry at {current_time}, Size: {range_size_pct:.2f}%")
                    else:
                        logger.info(f"[RRE-Hist] Small range without initial geometry discarded at {current_time}")

                current_range_start = None

            last_state = current_state

        self._print_report(detected_ranges)

    def _print_report(self, detected_ranges: List[Dict]):
        """Prints the final human-readable report."""
        print("\n" + "="*100)
        print(" RRE HISTORICAL ANALYSIS REPORT ".center(100, "="))
        print("="*100)

        if not detected_ranges:
            print("\nNo significant ranges were detected in the last 14 days.")
            print("This could mean the RRE is not sensitive enough, or the market was trending.")
            return

        print(f"\nDetected {len(detected_ranges)} potential range events in the last 14 days:\n")

        # Filter out ranges that don't have valid geometry
        valid_ranges = []
        invalid_geometry_count = 0

        for r in detected_ranges:
            if r['geometry'] is not None and hasattr(r['geometry'], 'is_valid') and r['geometry'].is_valid:
                valid_ranges.append(r)
            else:
                invalid_geometry_count += 1

        if not valid_ranges:
            print("No ranges with valid geometry were detected.")
            print("This could indicate the market was trending or the RRE sensitivity needs adjustment.")
            if invalid_geometry_count > 0:
                print(f"Note: {invalid_geometry_count} range events were detected but had invalid geometry.")
            return

        print(f"Of these, {len(valid_ranges)} had valid range geometry (filtered out {invalid_geometry_count} with invalid geometry):\n")

        df_report = pd.DataFrame(valid_ranges)
        df_report['Start Time'] = df_report['start'].dt.strftime('%Y-%m-%d %H:%M')
        df_report['End Time (Breakout)'] = df_report['end'].dt.strftime('%Y-%m-%d %H:%M')
        df_report['Duration (Hours)'] = df_report['duration_hours'].round(2)
        df_report['Range'] = df_report['geometry'].apply(lambda g: f"${g.low:.2f} - ${g.high:.2f}" if g and hasattr(g, 'is_valid') and g.is_valid else "N/A")
        df_report['Width (%)'] = df_report['geometry'].apply(lambda g: f"{g.width_pct:.2f}%" if g and hasattr(g, 'is_valid') and g.is_valid else "N/A")

        # Only display columns that have valid data
        columns_to_show = ['Start Time', 'End Time (Breakout)', 'Duration (Hours)', 'Range', 'Width (%)']
        print(df_report[columns_to_show].to_string(index=False))

        print("\n" + "="*100)
        print(" Please correlate this report with your charts to validate RRE performance. ".center(100, "="))
        print("="*100)
