"""
Simulation Framework: Full Integration Test for Market Regime Engine
===================================================================

This script performs an end-to-end validation of the MasterRegimeClassifier
against real historical data, using the full simulation framework.

Author: Arsenal Trading System
"""

import pandas as pd
import logging

from .data_fetcher import DataFetcher
from .scenario_identifier import ScenarioIdentifier, MarketScenario
from .engine import Simulator
from market_regime_engine.classifier import MasterRegimeClassifier
from market_regime_engine.definitions import MarketRegime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


def run_test_on_scenario(simulator: Simulator, scenario: MarketScenario, classifier: MasterRegimeClassifier, expected_regime: MarketRegime):
    """Helper function to run the simulator on a given scenario and assert the outcome."""
    logger.info("-" * 80)
    logger.info(f"Testing Scenario: {scenario.scenario_type} from {scenario.start_time} to {scenario.end_time}")
    
    # Run the simulation with the classifier's analyze method as the callback
    simulator.run(
        scenario_start_time=scenario.start_time,
        scenario_end_time=scenario.end_time,
        callback=classifier.analyze
    )
    
    results = simulator.get_results()
    
    if results.empty:
        logger.error("TEST FAILED: Simulation produced no results for this scenario.")
        return False

    # Analyze the results
    # We check the regime classification for the majority of the period
    regime_counts = results['current_regime'].value_counts(normalize=True)
    logger.info(f"Regime Distribution:\n{regime_counts}")
    
    # The dominant regime should be the one we expect
    dominant_regime = regime_counts.idxmax()
    
    if dominant_regime == expected_regime:
        logger.info(f"SUCCESS: Dominant regime was correctly identified as {expected_regime.name}.")
        return True
    else:
        logger.error(f"TEST FAILED: Expected dominant regime to be {expected_regime.name}, but got {dominant_regime.name}.")
        return False

if __name__ == '__main__':
    logger.info("--- Starting Full Market Regime Engine Integration Test ---")

    # 1. Fetch a large dataset
    fetcher = DataFetcher()
    # Using 5m data for a balance of detail and speed
    data = fetcher.fetch_and_enrich_data("SOLUSDT", "5m", 3000)

    if data is None:
        logger.critical("Could not fetch data. Aborting test.")
        exit()

    # 2. Identify Scenarios
    identifier = ScenarioIdentifier()
    consolidation_scenarios = identifier.find_consolidation_periods(data, min_duration_hours=4)
    trending_scenarios = identifier.find_trending_periods(data, min_duration_hours=4)

    if not consolidation_scenarios and not trending_scenarios:
        logger.critical("Could not find any suitable consolidation or trending scenarios in the last ~10 days of data. Aborting test.")
        exit()

    # 3. Initialize Simulator and Classifier
    simulator = Simulator(data=data)
    classifier = MasterRegimeClassifier(hysteresis_period=3)

    test_results = []

    # 4. Run tests on found scenarios
    if consolidation_scenarios:
        # Test the first found consolidation scenario
        success = run_test_on_scenario(simulator, consolidation_scenarios[0], classifier, MarketRegime.CONSOLIDATING)
        test_results.append(success)
    
    if trending_scenarios:
        # Test the first found trending scenario
        scenario = trending_scenarios[0]
        expected_regime = MarketRegime.TRENDING_UP if scenario.scenario_type == 'TRENDING_UP' else MarketRegime.TRENDING_DOWN
        success = run_test_on_scenario(simulator, scenario, classifier, expected_regime)
        test_results.append(success)

    # 5. Final Report
    logger.info("=" * 80)
    logger.info("INTEGRATION TEST SUMMARY")
    logger.info("=" * 80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r is True)
    
    if total_tests > 0 and passed_tests == total_tests:
        logger.info(f"SUCCESS: All {total_tests} scenario tests passed.")
        logger.info("The MasterRegimeClassifier is behaving as expected on historical data.")
    else:
        logger.error(f"FAILURE: {total_tests - passed_tests} out of {total_tests} scenario tests failed.")
        logger.error("The MasterRegimeClassifier is NOT yet ready for live deployment.")

    logger.info("--- Full Market Regime Engine Integration Test Complete ---")
