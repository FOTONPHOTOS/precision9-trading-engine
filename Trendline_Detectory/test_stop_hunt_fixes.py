"""
Test Stop Hunt Classification Fixes
====================================
Verifies that Arsenal correctly identifies:
1. DIRECTIONAL stop hunts (tradeable opportunities)
2. BI-DIRECTIONAL manipulation (block trades)
3. Range context (tight range vs breakout)
4. Candle intent (manipulation vs real moves)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from liquidity_sweep_detector import LiquiditySweepDetector, LiquiditySweep, LiquidityPool

def create_test_sweeps_directional_short():
    """
    Simulate the $212->$205 scenario:
    - Multiple bearish sweeps hunting longs at $210, $209, $208
    - Current price at $205.87 (broke down 3% below sweep zone)
    """
    current_time = datetime.now()

    sweeps = [
        # Bearish sweeps (hunting longs)
        LiquiditySweep(
            type='bearish_sweep',
            timestamp=current_time - timedelta(hours=1),
            sweep_high=211.0,
            sweep_low=209.5,
            close_price=209.8,
            swept_level=210.0,
            sweep_distance=1.0,
            volume=50000,
            reversal_confirmed=False,
            liquidity_grabbed=50000 * 210.0,
            smart_money_intent='STOP_HUNT',
            danger_level='MEDIUM'
        ),
        LiquiditySweep(
            type='bearish_sweep',
            timestamp=current_time - timedelta(minutes=40),
            sweep_high=209.8,
            sweep_low=208.2,
            close_price=208.5,
            swept_level=209.0,
            sweep_distance=0.8,
            volume=45000,
            reversal_confirmed=False,
            liquidity_grabbed=45000 * 209.0,
            smart_money_intent='STOP_HUNT',
            danger_level='MEDIUM'
        ),
        LiquiditySweep(
            type='bearish_sweep',
            timestamp=current_time - timedelta(minutes=20),
            sweep_high=208.7,
            sweep_low=206.9,
            close_price=207.2,
            swept_level=208.0,
            sweep_distance=1.1,
            volume=40000,
            reversal_confirmed=False,
            liquidity_grabbed=40000 * 208.0,
            smart_money_intent='STOP_HUNT',
            danger_level='MEDIUM'
        ),
    ]

    return sweeps


def create_test_sweeps_bidirectional():
    """
    Simulate bi-directional manipulation:
    - Sweeps on both sides within tight range
    - Price still in range
    """
    current_time = datetime.now()

    sweeps = [
        # Bearish sweep
        LiquiditySweep(
            type='bearish_sweep',
            timestamp=current_time - timedelta(minutes=30),
            sweep_high=207.5,
            sweep_low=206.5,
            close_price=206.8,
            swept_level=207.0,
            sweep_distance=0.5,
            volume=30000,
            reversal_confirmed=True,
            liquidity_grabbed=30000 * 207.0,
            smart_money_intent='STOP_HUNT',
            danger_level='HIGH'
        ),
        # Bullish sweep
        LiquiditySweep(
            type='bullish_sweep',
            timestamp=current_time - timedelta(minutes=20),
            sweep_high=206.2,
            sweep_low=204.8,
            close_price=206.2,
            swept_level=205.0,
            sweep_distance=0.2,
            volume=28000,
            reversal_confirmed=True,
            liquidity_grabbed=28000 * 205.0,
            smart_money_intent='STOP_HUNT',
            danger_level='HIGH'
        ),
        # Another bearish
        LiquiditySweep(
            type='bearish_sweep',
            timestamp=current_time - timedelta(minutes=10),
            sweep_high=207.0,
            sweep_low=206.3,
            close_price=206.5,
            swept_level=207.2,
            sweep_distance=0.5,
            volume=32000,
            reversal_confirmed=True,
            liquidity_grabbed=32000 * 207.2,
            smart_money_intent='STOP_HUNT',
            danger_level='HIGH'
        ),
        # Another bullish
        LiquiditySweep(
            type='bullish_sweep',
            timestamp=current_time - timedelta(minutes=5),
            sweep_high=206.3,
            sweep_low=205.3,
            close_price=206.3,
            swept_level=205.5,
            sweep_distance=0.8,
            volume=29000,
            reversal_confirmed=True,
            liquidity_grabbed=29000 * 205.5,
            smart_money_intent='STOP_HUNT',
            danger_level='HIGH'
        ),
    ]

    return sweeps


def create_candle_data_real_selling():
    """
    Create DataFrame with multiple consecutive red candles
    (Real selling pressure, not manipulation)
    """
    current_time = datetime.now().timestamp()

    candles = []
    price = 212.0

    # 10 consecutive red candles showing real selling
    for i in range(10):
        open_price = price
        close_price = price - np.random.uniform(0.3, 0.8)  # Drop 0.3-0.8 each candle
        high_price = open_price + np.random.uniform(0.05, 0.15)
        low_price = close_price - np.random.uniform(0.05, 0.15)

        candles.append({
            'timestamp': current_time - (600 * (10 - i)),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': np.random.uniform(10000, 20000)
        })

        price = close_price

    return pd.DataFrame(candles)


def create_candle_data_manipulation():
    """
    Create DataFrame with wick manipulation
    (Single big wicks with small bodies and reversals)
    """
    current_time = datetime.now().timestamp()

    candles = []
    price = 206.0

    # Candles with big wicks and small bodies
    for i in range(5):
        open_price = price
        close_price = price + np.random.uniform(-0.1, 0.1)  # Small body

        # Big wick down (sweep) but reversal
        if i % 2 == 0:
            high_price = open_price + 0.2
            low_price = open_price - 1.5  # Big wick down
        else:
            high_price = open_price + 1.5  # Big wick up
            low_price = open_price - 0.2

        candles.append({
            'timestamp': current_time - (300 * (5 - i)),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': np.random.uniform(15000, 25000)
        })

        price = close_price

    return pd.DataFrame(candles)


def test_directional_short_opportunity():
    """
    Test Case 1: Directional SHORT opportunity
    Expected: Should be classified as DIRECTIONAL_SHORT + BREAKOUT_DOWN + REAL_SELLING
    """
    print("="*80)
    print("TEST 1: DIRECTIONAL SHORT OPPORTUNITY (Like $212->$205)")
    print("="*80)

    detector = LiquiditySweepDetector()

    # Setup scenario
    sweeps = create_test_sweeps_directional_short()
    pools = []  # Not needed for this test
    current_price = 205.87  # Broke down 3% below $208 sweep zone
    df = create_candle_data_real_selling()

    # Run detection
    warning = detector.detect_stop_hunt_mode(
        sweeps=sweeps,
        pools=pools,
        current_price=current_price,
        df=df,
        lookback_hours=6.0
    )

    # Display results
    print(f"\nRESULTS:")
    print(f"  Hunt Type: {warning.hunt_type}")
    print(f"  Range Context: {warning.range_context}")
    print(f"  Is Tradeable Directional: {warning.is_tradeable_directional}")
    print(f"  Stop Hunt Mode: {warning.is_stop_hunt_mode}")
    print(f"  Safe to Trade: {warning.safe_to_trade}")
    print(f"  Severity: {warning.severity:.0%}")
    print(f"  Recommendation: {warning.recommendation}")

    # Verify expectations
    print(f"\nVERIFICATION:")
    assert warning.hunt_type == 'DIRECTIONAL_SHORT', f"[X] Hunt type should be DIRECTIONAL_SHORT, got {warning.hunt_type}"
    print(f"  [OK] Hunt type correct: DIRECTIONAL_SHORT")

    assert warning.range_context == 'BREAKOUT_DOWN', f"[X] Range context should be BREAKOUT_DOWN, got {warning.range_context}"
    print(f"  [OK] Range context correct: BREAKOUT_DOWN")

    assert warning.is_tradeable_directional == True, f"[X] Should be tradeable directional opportunity"
    print(f"  [OK] Tradeable directional: YES")

    assert warning.safe_to_trade == True, f"[X] Should be safe to trade"
    print(f"  [OK] Safe to trade: YES")

    print(f"\nTEST 1 PASSED! Arsenal would now TRADE this SHORT opportunity!")
    return True


def test_bidirectional_manipulation():
    """
    Test Case 2: Bi-directional manipulation in tight range
    Expected: Should be classified as BI_DIRECTIONAL + TIGHT_RANGE + block trade
    """
    print("\n" + "="*80)
    print("TEST 2: BI-DIRECTIONAL MANIPULATION (Should Block)")
    print("="*80)

    detector = LiquiditySweepDetector()

    # Setup scenario
    sweeps = create_test_sweeps_bidirectional()
    pools = []
    current_price = 206.0  # Still within sweep range (205-207.2)
    df = create_candle_data_manipulation()

    # Run detection
    warning = detector.detect_stop_hunt_mode(
        sweeps=sweeps,
        pools=pools,
        current_price=current_price,
        df=df,
        lookback_hours=6.0
    )

    # Display results
    print(f"\nRESULTS:")
    print(f"  Hunt Type: {warning.hunt_type}")
    print(f"  Range Context: {warning.range_context}")
    print(f"  Is Tradeable Directional: {warning.is_tradeable_directional}")
    print(f"  Stop Hunt Mode: {warning.is_stop_hunt_mode}")
    print(f"  Safe to Trade: {warning.safe_to_trade}")
    print(f"  Severity: {warning.severity:.0%}")
    print(f"  Recommendation: {warning.recommendation}")

    # Verify expectations
    print(f"\nVERIFICATION:")
    assert warning.hunt_type == 'BI_DIRECTIONAL', f"[X] Hunt type should be BI_DIRECTIONAL, got {warning.hunt_type}"
    print(f"  [OK] Hunt type correct: BI_DIRECTIONAL")

    assert warning.range_context in ['TIGHT_RANGE', 'IN_RANGE'], f"[X] Range context should be TIGHT_RANGE or IN_RANGE, got {warning.range_context}"
    print(f"  [OK] Range context correct: {warning.range_context}")

    assert warning.is_tradeable_directional == False, f"[X] Should NOT be tradeable"
    print(f"  [OK] Tradeable directional: NO")

    assert warning.safe_to_trade == False, f"[X] Should NOT be safe to trade"
    print(f"  [OK] Safe to trade: NO")

    print(f"\nTEST 2 PASSED! Arsenal correctly BLOCKS bi-directional manipulation!")
    return True


def test_classification_methods():
    """
    Test Case 3: Test individual classification methods
    """
    print("\n" + "="*80)
    print("TEST 3: INDIVIDUAL CLASSIFICATION METHODS")
    print("="*80)

    detector = LiquiditySweepDetector()

    # Test hunt direction classification
    print("\nTesting _classify_hunt_direction()...")
    sweeps = create_test_sweeps_directional_short()
    hunt_type = detector._classify_hunt_direction(sweeps, 205.87)
    print(f"  Result: {hunt_type}")
    assert hunt_type == 'DIRECTIONAL_SHORT', f"[X] Should be DIRECTIONAL_SHORT, got {hunt_type}"
    print(f"  [OK] Correctly identified DIRECTIONAL_SHORT")

    # Test range context
    print("\nTesting _check_range_context()...")
    range_context = detector._check_range_context(sweeps, 205.87)
    print(f"  Result: {range_context}")
    assert range_context == 'BREAKOUT_DOWN', f"[X] Should be BREAKOUT_DOWN, got {range_context}"
    print(f"  [OK] Correctly identified BREAKOUT_DOWN")

    # Test candle intent
    print("\nTesting _analyze_candle_intent()...")
    df = create_candle_data_real_selling()
    candle_intent = detector._analyze_candle_intent(df, sweeps)
    print(f"  Result: {candle_intent}")
    assert candle_intent in ['REAL_SELLING', 'UNCLEAR'], f"[X] Should be REAL_SELLING or UNCLEAR, got {candle_intent}"
    print(f"  [OK] Correctly identified {candle_intent}")

    print(f"\nTEST 3 PASSED! All classification methods working correctly!")
    return True


def main():
    print("\n" + "="*80)
    print("ARSENAL STOP HUNT CLASSIFICATION FIX - VERIFICATION TESTS")
    print("="*80)
    print("\nThese tests verify that Arsenal now correctly:")
    print("  1. Identifies DIRECTIONAL stop hunts as TRADE OPPORTUNITIES")
    print("  2. Identifies BI-DIRECTIONAL manipulation and BLOCKS trades")
    print("  3. Analyzes range context (tight range vs breakout)")
    print("  4. Analyzes candle intent (manipulation vs real moves)")

    try:
        # Run all tests
        test1_passed = test_directional_short_opportunity()
        test2_passed = test_bidirectional_manipulation()
        test3_passed = test_classification_methods()

        # Summary
        print("\n" + "="*80)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("="*80)
        print("\nArsenal Stop Hunt Fixes Verified:")
        print("  [OK] Directional SHORT opportunities correctly identified")
        print("  [OK] Bi-directional manipulation correctly blocked")
        print("  [OK] Range context analysis working")
        print("  [OK] Candle intent analysis working")
        print("\nArsenal should now capitalize on the $212->$205 type moves")
        print("instead of blocking them as manipulation.")

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
