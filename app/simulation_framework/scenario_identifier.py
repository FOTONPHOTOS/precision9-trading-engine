"""
Simulation Framework: Scenario Identifier
=========================================

Analyzes historical data to find specific market scenarios for testing.

Author: Arsenal Trading System
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MarketScenario:
    """Represents a specific period of interest in historical data."""
    scenario_type: str # e.g., 'CONSOLIDATION', 'TRENDING_UP', 'TRENDING_DOWN'
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    duration_hours: float
    details: Dict[str, any]

class ScenarioIdentifier:
    """
    Scans historical market data to find periods that match specific criteria,
    such as consolidation, strong trends, or regime transitions.
    """

    def find_consolidation_periods(
        self,
        df: pd.DataFrame,
        min_duration_hours: float = 2.0,
        min_range_pct: float = 0.8,
        max_range_pct: float = 4.0,
        adx_threshold: float = 20.0
    ) -> List[MarketScenario]:
        """
        Finds periods of consolidation (ranging markets) using a more robust iterative approach.
        """
        logger.info(f"Scanning for consolidation periods (min {min_duration_hours}h, range {min_range_pct}%-{max_range_pct}%, ADX < {adx_threshold})...")
        
        scenarios = []
        min_candles = int((min_duration_hours * 3600) / (df.index[1] - df.index[0]).total_seconds())
        
        in_scenario = False
        start_index = 0

        for i in range(len(df)):
            # Check if the current candle is a potential start of a range
            if not in_scenario and df['ADX_14'].iloc[i] < adx_threshold:
                in_scenario = True
                start_index = i
            
            # If we are in a scenario, check if it has ended
            elif in_scenario:
                # A scenario ends if ADX goes too high or we reach the end of the data
                if df['ADX_14'].iloc[i] >= adx_threshold or i == len(df) - 1:
                    end_index = i
                    # Check if the identified period is long enough
                    if (end_index - start_index) >= min_candles:
                        period_df = df.iloc[start_index:end_index]
                        range_high = period_df['high'].max()
                        range_low = period_df['low'].min()
                        actual_range_pct = ((range_high - range_low) / range_low) * 100

                        # Check if the range percentage is within our desired bounds
                        if min_range_pct <= actual_range_pct <= max_range_pct:
                            start_time = period_df.index[0]
                            end_time = period_df.index[-1]
                            scenario = MarketScenario(
                                scenario_type='CONSOLIDATION',
                                start_time=start_time,
                                end_time=end_time,
                                duration_hours=(end_time - start_time).total_seconds() / 3600,
                                details={
                                    'range_high': range_high,
                                    'range_low': range_low,
                                    'avg_range_pct': actual_range_pct,
                                    'avg_adx': period_df['ADX_14'].mean()
                                }
                            )
                            scenarios.append(scenario)
                    
                    # Reset for the next potential scenario
                    in_scenario = False

        logger.info(f"Found {len(scenarios)} consolidation scenarios.")
        return scenarios

    def find_trending_periods(
        self,
        df: pd.DataFrame,
        min_duration_hours: float = 3.0,
        adx_threshold: float = 25.0,
        ema_separation_pct: float = 0.1
    ) -> List[MarketScenario]:
        """
        Finds periods of strong, sustained trends.

        Args:
            df: Enriched historical data DataFrame.
            min_duration_hours: The minimum duration for a period to be considered a trend.
            adx_threshold: The ADX value must be consistently above this.
            ema_separation_pct: The minimum separation between EMA21 and EMA100.

        Returns:
            A list of MarketScenario objects representing trending periods.
        """
        logger.info(f"Scanning for trending periods (min {min_duration_hours}h, ADX > {adx_threshold})...")
        scenarios = []
        min_window_size = int((min_duration_hours * 3600) / (df.index[1] - df.index[0]).total_seconds())

        ema_sep = abs(df['EMA_21'] - df['EMA_100']) / df['EMA_100'] * 100

        is_trending_up = (
            (df['ADX_14'] > adx_threshold) &
            (df['close'] > df['EMA_21']) &
            (df['EMA_21'] > df['EMA_100']) &
            (ema_sep > ema_separation_pct)
        )
        
        is_trending_down = (
            (df['ADX_14'] > adx_threshold) &
            (df['close'] < df['EMA_21']) &
            (df['EMA_21'] < df['EMA_100']) &
            (ema_sep > ema_separation_pct)
        )

        for trend_condition, trend_type in [(is_trending_up, 'TRENDING_UP'), (is_trending_down, 'TRENDING_DOWN')]:
            in_scenario = False
            start_index = None
            for i in range(len(trend_condition)):
                if trend_condition.iloc[i] and not in_scenario:
                    in_scenario = True
                    start_index = i
                elif not trend_condition.iloc[i] and in_scenario:
                    in_scenario = False
                    if start_index is not None and (i - start_index) >= min_window_size:
                        start_time = df.index[start_index]
                        end_time = df.index[i-1]
                        period_df = df.iloc[start_index:i]
                        scenario = MarketScenario(
                            scenario_type=trend_type,
                            start_time=start_time,
                            end_time=end_time,
                            duration_hours=(end_time - start_time).total_seconds() / 3600,
                            details={
                                'start_price': period_df['open'].iloc[0],
                                'end_price': period_df['close'].iloc[-1],
                                'avg_adx': period_df['ADX_14'].mean()
                            }
                        )
                        scenarios.append(scenario)
                    start_index = None

        logger.info(f"Found {len(scenarios)} trending scenarios.")
        return scenarios

if __name__ == '__main__':
    from data_fetcher import DataFetcher
    logger.info("--- Running ScenarioIdentifier Standalone Test ---")

    # 1. Fetch data first
    fetcher = DataFetcher()
    data = fetcher.fetch_and_enrich_data("SOLUSDT", "15m", 1000)

    if data is not None:
        identifier = ScenarioIdentifier()
        
        # 2. Find consolidation periods
        consolidation_scenarios = identifier.find_consolidation_periods(data)
        if consolidation_scenarios:
            print("\n--- Found Consolidation Scenarios ---")
            for s in consolidation_scenarios[:3]: # Print first 3
                print(f"  - Type: {s.scenario_type}")
                print(f"    Duration: {s.duration_hours:.2f} hours")
                print(f"    Time: {s.start_time} -> {s.end_time}")
                print(f"    Details: {s.details}")

        # 3. Find trending periods
        trending_scenarios = identifier.find_trending_periods(data)
        if trending_scenarios:
            print("\n--- Found Trending Scenarios ---")
            for s in trending_scenarios[:3]: # Print first 3
                print(f"  - Type: {s.scenario_type}")
                print(f"    Duration: {s.duration_hours:.2f} hours")
                print(f"    Time: {s.start_time} -> {s.end_time}")
                print(f"    Details: {s.details}")
    else:
        logger.error("Could not fetch data, cannot run scenario identification.")

    logger.info("--- ScenarioIdentifier Standalone Test Complete ---")
