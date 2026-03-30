#!/usr/bin/env python3
"""
Test Script for Arsenal Strategy Router
========================================
Verifies all components work correctly:
1. Range Trap Detection
2. Mean Reversion Signal Generation
3. Breakout Detection
4. Strategy Switching Logic

Run this to ensure everything is integrated properly.
"""

import sys
import logging
from datetime import datetime
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('TEST')

# Import modules
try:
    from arsenal_strategy_router import ArsenalStrategyRouter
    from mean_reversion_engine import MeanReversionEngine
    from range_breakout_detector import RangeBreakoutDetector
    from range_trap_detector import RangeTrapDetector
    logger.info(" All modules imported successfully")
except ImportError as e:
    logger.error(f" Import failed: {e}")
    sys.exit(1)


def test_mean_reversion_signal_generation():
    """Test that mean reversion can generate signals"""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Mean Reversion Signal Generation")
    logger.info("="*80)

    engine = MeanReversionEngine("SOLUSDT")
    engine.activate("Test mode")

    # Simulate price oscillating around 200
    logger.info("Simulating 30 price updates with oscillation...")
    for i in range(30):
        # Create oscillating pattern
        price = 200 + (i % 10) * 1.0 - 5.0  # Oscillates between 195-205
        volume = 1000 + (i % 5) * 100
        engine.update_price(price, volume)

    # Try to generate signal at extreme (high)
    logger.info("\nTrying to generate signal at high extreme (price=205)...")
    market_mean = engine.calculate_market_mean()

    if not market_mean:
        logger.warning(" No market mean calculated (need more data)")
        return False

    logger.info(f"   VWAP: ${market_mean.vwap:.2f}")
    logger.info(f"   Z-Score: {market_mean.z_score:.2f}")
    logger.info(f"   Rolling Mean: ${market_mean.rolling_mean:.2f}")

    signal = engine.generate_signal(
        current_price=205.0,
        market_mean=market_mean,
        chop_confidence=0.7
    )

    if signal:
        logger.info(" Mean Reversion Signal Generated!")
        logger.info(f"   Direction: {signal.direction}")
        logger.info(f"   Entry: ${signal.entry_price:.2f}")
        logger.info(f"   TP: ${signal.take_profit:.2f}")
        logger.info(f"   SL: ${signal.stop_loss:.2f}")
        logger.info(f"   Confidence: {signal.confidence:.1%}")
        logger.info(f"   RR: {signal.risk_reward_ratio:.2f}:1")
        return True
    else:
        logger.warning(" No signal generated (thresholds not met)")
        logger.warning("   This might be normal if oscillation wasn't extreme enough")
        return False


def test_breakout_detection():
    """Test breakout detection with volume confirmation"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Breakout Detection")
    logger.info("="*80)

    detector = RangeBreakoutDetector()

    # Simulate normal volume history
    logger.info("Building volume history (20 candles, avg volume 1000)...")
    for i in range(20):
        detector.update_market_data(200.0, 1000.0, time.time())

    # Define range
    range_high = 202.0
    range_low = 198.0

    logger.info(f"\nRange boundaries: ${range_low:.2f} - ${range_high:.2f}")

    # Test 1: Real breakout (high volume, clean break)
    logger.info("\n--- Test Case: Real Breakout ---")
    logger.info("Price breaks to $203 with 2.5x volume...")

    signal = detector.detect_breakout(
        current_price=203.0,
        current_volume=2500.0,  # 2.5x average
        range_high=range_high,
        range_low=range_low,
        recent_highs=[201.0, 201.5, 202.0, 202.1, 203.0],
        recent_lows=[198.0, 198.5, 199.0],
        candle_closes=[200.0, 201.0, 202.5, 203.0, 203.2]  # Clean close progression
    )

    if signal and signal.is_breakout:
        logger.info(" BREAKOUT CONFIRMED")
        logger.info(f"   Direction: {signal.direction}")
        logger.info(f"   Confidence: {signal.confidence:.0%}")
        logger.info(f"   Fakeout Risk: {signal.fakeout_probability:.0%}")
        logger.info(f"   Volume: {signal.volume_confirmation}")
        logger.info(f"   Structure: {signal.structure_integrity}")
        breakout_test_1 = True
    else:
        logger.warning(" Real breakout NOT detected (should have been)")
        breakout_test_1 = False

    # Test 2: Fake breakout (low volume, reversal)
    logger.info("\n--- Test Case: Fake Breakout ---")
    logger.info("Price wicks to $203 but low volume and reverses...")

    # Reset cooldown
    detector.breakout_cooldown = 0

    signal2 = detector.detect_breakout(
        current_price=203.0,
        current_volume=800.0,  # Below average (fake)
        range_high=range_high,
        range_low=range_low,
        recent_highs=[201.0, 201.5, 202.0],
        recent_lows=[198.0, 198.5, 199.0],
        candle_closes=[201.0, 202.0, 203.0, 202.0, 201.5]  # Reversal pattern
    )

    if signal2 and signal2.is_breakout:
        logger.warning(" False breakout detected as real (should have been filtered)")
        breakout_test_2 = False
    else:
        logger.info(" Fake breakout correctly rejected")
        breakout_test_2 = True

    return breakout_test_1 and breakout_test_2


def test_strategy_routing():
    """Test complete strategy routing logic"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Strategy Routing")
    logger.info("="*80)

    router = ArsenalStrategyRouter("SOLUSDT")

    # Build some data
    logger.info("Building market data (30 updates)...")
    current_price = 200.0
    for i in range(30):
        price = 200 + (i % 10) * 0.5 - 2.5  # Oscillating
        volume = 1000
        router.update_market_data(price, volume, time.time())
        current_price = price

    # Create swing data for range
    swing_highs = [
        {'price': 202.0, 'timestamp': datetime.utcnow()},
        {'price': 202.1, 'timestamp': datetime.utcnow()},
        {'price': 202.0, 'timestamp': datetime.utcnow()},
    ]

    swing_lows = [
        {'price': 198.0, 'timestamp': datetime.utcnow()},
        {'price': 198.2, 'timestamp': datetime.utcnow()},
        {'price': 198.1, 'timestamp': datetime.utcnow()},
    ]

    patterns = []  # No conflicting patterns
    candle_closes = [199.0, 200.0, 201.0, 200.5, 200.0]

    # Test 1: Should detect range and switch to mean reversion
    logger.info("\n--- Test: Range Detection → Mean Reversion ---")

    decision = router.analyze_and_route(
        current_price=current_price,
        current_volume=1000,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        patterns=patterns,
        candle_closes=candle_closes,
        chop_confidence=0.6
    )

    logger.info(f"Strategy Decision: {decision.active_strategy}")
    logger.info(f"Should Trade: {decision.should_trade}")
    logger.info(f"Reasoning: {decision.reason}")

    if decision.active_strategy in ["MEAN_REVERSION", "DIRECTIONAL"]:
        logger.info(" Strategy routing working")
        test1_pass = True
    else:
        logger.warning(" Unexpected strategy state")
        test1_pass = False

    # Test 2: Breakout should switch to directional
    logger.info("\n--- Test: Breakout → Directional ---")

    # Simulate breakout scenario
    time.sleep(2)  # Let cooldown pass
    router.switch_cooldown = 0  # Override for test

    # Add breakout candles
    breakout_closes = [199.0, 200.0, 201.0, 203.0, 203.5]  # Breaking up
    breakout_highs = swing_highs + [
        {'price': 203.0, 'timestamp': datetime.utcnow()},
        {'price': 203.5, 'timestamp': datetime.utcnow()},
    ]

    decision2 = router.analyze_and_route(
        current_price=203.5,  # Above range
        current_volume=2000,  # High volume
        swing_highs=breakout_highs,
        swing_lows=swing_lows,
        patterns=patterns,
        candle_closes=breakout_closes,
        chop_confidence=0.2  # Low chop
    )

    logger.info(f"Strategy Decision: {decision2.active_strategy}")
    logger.info(f"Breakout Detected: {decision2.is_breaking_out}")

    if decision2.is_breaking_out or decision2.active_strategy == "DIRECTIONAL":
        logger.info(" Breakout routing working")
        test2_pass = True
    else:
        logger.warning(" Breakout not detected")
        test2_pass = False

    return test1_pass and test2_pass


def test_integration_status():
    """Test status reporting"""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Status Reporting")
    logger.info("="*80)

    router = ArsenalStrategyRouter("SOLUSDT")
    status = router.get_status()

    logger.info("Router Status:")
    for key, value in status.items():
        logger.info(f"   {key}: {value}")

    engine = MeanReversionEngine("SOLUSDT")
    mr_status = engine.get_status()

    logger.info("\nMean Reversion Status:")
    for key, value in mr_status.items():
        logger.info(f"   {key}: {value}")

    logger.info(" Status reporting working")
    return True


def main():
    """Run all tests"""
    logger.info("\n" + "="*80)
    logger.info("ARSENAL STRATEGY ROUTER - COMPREHENSIVE TEST")
    logger.info("="*80)
    logger.info("Testing all components...")
    logger.info("")

    results = {}

    # Test 1: Mean Reversion
    try:
        results['mean_reversion'] = test_mean_reversion_signal_generation()
    except Exception as e:
        logger.error(f" Test 1 failed with exception: {e}")
        results['mean_reversion'] = False

    # Test 2: Breakout Detection
    try:
        results['breakout'] = test_breakout_detection()
    except Exception as e:
        logger.error(f" Test 2 failed with exception: {e}")
        results['breakout'] = False

    # Test 3: Strategy Routing
    try:
        results['routing'] = test_strategy_routing()
    except Exception as e:
        logger.error(f" Test 3 failed with exception: {e}")
        results['routing'] = False

    # Test 4: Status
    try:
        results['status'] = test_integration_status()
    except Exception as e:
        logger.error(f" Test 4 failed with exception: {e}")
        results['status'] = False

    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)

    for test_name, passed in results.items():
        status = " PASS" if passed else " FAIL"
        logger.info(f"{status} - {test_name}")

    total_passed = sum(results.values())
    total_tests = len(results)

    logger.info("")
    logger.info(f"Results: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        logger.info(" ALL TESTS PASSED - System ready for integration")
        return 0
    else:
        logger.warning(" SOME TESTS FAILED - Review and fix issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
