"""
Simulation Framework: Core Simulation Engine
============================================

Replays historical data to test trading logic components offline.

Author: Arsenal Trading System
"""

import pandas as pd
from typing import List, Dict, Callable, Any
import logging
from dataclasses import asdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class Simulator:
    """
    A backtesting engine that replays historical market data candle by candle.
    
    It takes a historical dataset and a component to test (via a callback),
    and feeds the data to the component one step at a time, collecting the results.
    """

    def __init__(self, data: pd.DataFrame):
        """
        Initializes the Simulator with a full historical dataset.

        Args:
            data: The enriched historical data (from DataFetcher).
        """
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Data must be a non-empty pandas DataFrame.")
        self.full_data = data
        self.results = []

    def run(
        self,
        scenario_start_time: pd.Timestamp,
        scenario_end_time: pd.Timestamp,
        # The callback is the component we want to test. 
        # It must accept the historical data up to the current candle.
        # It must return a dictionary of results.
        callback: Callable[[pd.DataFrame], Any],
        warmup_period: int = 100 # Number of candles before scenario starts for indicator stability
    ):
        """
        Runs the simulation for a specific scenario.

        Args:
            scenario_start_time: The timestamp to start the simulation test.
            scenario_end_time: The timestamp to end the simulation test.
            callback: The function to call on each candle. This function represents
                      the logic component being tested (e.g., the MasterRegimeClassifier).
            warmup_period: Number of candles to include before the scenario starts
                           to ensure indicators like EMAs are stable.
        """
        logger.info(f"Starting simulation for scenario: {scenario_start_time} -> {scenario_end_time}")

        # Find the integer index for the start time, including the warmup period
        try:
            start_idx_loc = self.full_data.index.get_loc(scenario_start_time)
            start_idx = max(0, start_idx_loc - warmup_period)
            end_idx_loc = self.full_data.index.get_loc(scenario_end_time)
        except KeyError as e:
            logger.error(f"Timestamp not found in data index: {e}")
            return

        # Create the slice of data for this specific run
        scenario_data = self.full_data.iloc[start_idx:end_idx_loc + 1]
        
        if len(scenario_data) < warmup_period:
            logger.warning("Scenario is too short or too early in the dataset to satisfy warmup period.")
            return

        self.results = []
        logger.info(f"Simulating {len(scenario_data) - warmup_period} candles...")

        # Iterate candle by candle, starting after the warmup period
        for i in range(warmup_period, len(scenario_data)):
            # This DataFrame represents all the market data available *up to this point in time*
            current_market_view = scenario_data.iloc[:i+1]
            
            # Call the logic component we are testing
            try:
                result_obj = callback(current_market_view)
                
                # Convert dataclass to dict for storage
                result_dict = asdict(result_obj)
                
                # Store the timestamp and the result from the component
                self.results.append(result_dict)

            except Exception as e:
                logger.error(f"Error in simulation callback at timestamp {current_market_view.index[-1]}: {e}", exc_info=True)
                # Continue simulation even if one step fails
                continue

        logger.info("Simulation complete.")

    def get_results(self) -> pd.DataFrame:
        """
        Returns the collected results of the simulation as a DataFrame.
        """
        if not self.results:
            return pd.DataFrame()
        
        results_df = pd.DataFrame(self.results)
        results_df.set_index('timestamp', inplace=True)
        return results_df

if __name__ == '__main__':
    from data_fetcher import DataFetcher
    from scenario_identifier import ScenarioIdentifier
    logger.info("--- Running Simulator Standalone Test ---")

    # Example of a simple callback function to test
    # In reality, this would be a call to our MasterRegimeClassifier.analyze()
    def simple_test_callback(df: pd.DataFrame) -> Dict[str, Any]:
        """A dummy callback that just returns the latest ADX value."""
        if df.empty:
            return {}
        latest_adx = df['ADX_14'].iloc[-1]
        return {'adx_value': latest_adx, 'is_trending': latest_adx > 25}

    # 1. Fetch data
    fetcher = DataFetcher()
    data = fetcher.fetch_and_enrich_data("SOLUSDT", "15m", 1000)

    if data is not None:
        # 2. Find a scenario to test
        identifier = ScenarioIdentifier()
        trending_scenarios = identifier.find_trending_periods(data, min_duration_hours=5)
        
        if trending_scenarios:
            # 3. Run the simulator on the first found scenario
            test_scenario = trending_scenarios[0]
            
            simulator = Simulator(data=data)
            simulator.run(
                scenario_start_time=test_scenario.start_time,
                scenario_end_time=test_scenario.end_time,
                callback=simple_test_callback
            )
            
            # 4. Get and display results
            results = simulator.get_results()
            
            if not results.empty:
                print("\n--- Simulation Results ---")
                print(f"Ran on a {test_scenario.scenario_type} scenario for {test_scenario.duration_hours:.2f} hours.")
                print("Callback returned the following data:")
                print(results.head())
                
                # Analysis of results
                trending_candles = results['is_trending'].sum()
                total_candles = len(results)
                print(f"\nAnalysis: The market was considered 'trending' in {trending_candles}/{total_candles} candles.")
            else:
                logger.warning("Simulation produced no results.")
        else:
            logger.warning("No trending scenarios found in the data to run simulation.")
    else:
        logger.error("Could not fetch data, cannot run simulation.")

    logger.info("--- Simulator Standalone Test Complete ---")
