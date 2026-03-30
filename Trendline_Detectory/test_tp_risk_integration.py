"""
Test TP Structure & Risk Manager Integration
==============================================
Verifies the complete Phase 2 integration:
1. Arsenal brain generates 1-TP or 2-TP structures
2. Executor converts to Bybit signal format
3. Risk Manager launches with correct parameters
"""

import asyncio
import logging
from datetime import datetime
from intelligent_strategy_brain import IntelligentDecision
from bybit_arsenal_executor import ArsenalBybitExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('INTEGRATION_TEST')


def create_test_decision_2tp_mode():
    """
    Create test decision with 2-TP structure
    (High-impact zone found at 1:1 RR)
    """
    return IntelligentDecision(
        direction='SHORT',
        confidence=0.85,
        signal_strength='VERY_STRONG',
        entry_zone=(205.80, 206.00),
        stop_loss=209.27,  # $3.47 risk
        take_profits=[201.50, 198.62],  # TP1 at 1:1+ zone, TP2 at final target
        risk_reward=1.67,  # Blended RR
        position_size_multiplier=1.0,
        max_risk_percent=1.0,
        reasoning_chain=[
            "Detected DIRECTIONAL_SHORT stop hunt with BREAKOUT_DOWN",
            "Found liquidity pool at $201.50 (TP1)",
            "TP Structure: 2-TP MODE",
            "Blended RR: 1.67:1 (passes 1.2:1 minimum)"
        ],
        blockers=[],
        warnings=[],
        opportunities=[
            "Directional stop hunt (SHORT) with breakout",
            "Excellent confluence (210 points)",
            "Multiple bearish sweeps with breakout below sweep zone"
        ],
        should_trade=True,
        urgency='IMMEDIATE',
        analysis_quality=0.95,
        decision_timestamp=datetime.utcnow()
    )


def create_test_decision_heightened_security():
    """
    Create test decision with 1-TP structure (HEIGHTENED SECURITY)
    (No high-impact zone at 1:1 RR, but confidence >= 75%)
    """
    return IntelligentDecision(
        direction='LONG',
        confidence=0.78,
        signal_strength='STRONG',
        entry_zone=(205.00, 205.30),
        stop_loss=202.50,  # $2.50 risk
        take_profits=[210.00],  # Single TP (heightened security mode)
        risk_reward=2.0,
        position_size_multiplier=1.0,
        max_risk_percent=1.0,
        reasoning_chain=[
            "Strong bullish confluence detected",
            "No high-impact zone at 1:1 RR",
            "Confidence >= 75% - HEIGHTENED SECURITY MODE",
            "Single TP with aggressive reversal detection"
        ],
        blockers=[],
        warnings=["Heightened security mode - aggressive monitoring required"],
        opportunities=[
            "Good confluence (156 points)",
            "Bullish structure with no manipulation"
        ],
        should_trade=True,
        urgency='IMMEDIATE',
        analysis_quality=0.88,
        decision_timestamp=datetime.utcnow()
    )


def test_conversion_2tp_mode():
    """
    Test Case 1: 2-TP Mode Conversion
    """
    logger.info("="*80)
    logger.info("TEST 1: 2-TP MODE CONVERSION")
    logger.info("="*80)

    executor = ArsenalBybitExecutor("SOLUSDT")
    decision = create_test_decision_2tp_mode()
    current_price = 205.87

    # Convert to Bybit signal
    bybit_signal, heightened_security, tp1_price, tp2_price = executor.convert_arsenal_to_bybit_signal(
        decision, current_price
    )

    logger.info("\nRESULTS:")
    logger.info(f"  Direction: {bybit_signal.direction}")
    logger.info(f"  Entry: ${bybit_signal.entry_price:.2f}")
    logger.info(f"  Stop Loss: ${bybit_signal.stop_loss:.2f}")
    logger.info(f"  TP1: ${tp1_price:.2f}" if tp1_price else "  TP1: None")
    logger.info(f"  TP2: ${tp2_price:.2f}")
    logger.info(f"  TP3: ${bybit_signal.take_profit_3:.2f}")
    logger.info(f"  Heightened Security: {heightened_security}")
    logger.info(f"  RR Ratio: {bybit_signal.risk_reward_ratio:.2f}:1")

    # Verify expectations
    logger.info("\nVERIFICATION:")
    assert heightened_security == False, "[X] Should NOT be heightened security for 2-TP mode"
    logger.info("  [OK] Heightened security: False (correct)")

    assert tp1_price == 201.50, f"[X] TP1 should be 201.50, got {tp1_price}"
    logger.info(f"  [OK] TP1: ${tp1_price:.2f}")

    assert tp2_price == 198.62, f"[X] TP2 should be 198.62, got {tp2_price}"
    logger.info(f"  [OK] TP2: ${tp2_price:.2f}")

    assert bybit_signal.risk_reward_ratio >= 1.2, "[X] Blended RR should be >= 1.2:1"
    logger.info(f"  [OK] Blended RR: {bybit_signal.risk_reward_ratio:.2f}:1 (>= 1.2:1)")

    logger.info("\n TEST 1 PASSED!\n")
    return True


def test_conversion_heightened_security():
    """
    Test Case 2: Heightened Security Mode (1-TP)
    """
    logger.info("="*80)
    logger.info("TEST 2: HEIGHTENED SECURITY MODE (1-TP)")
    logger.info("="*80)

    executor = ArsenalBybitExecutor("SOLUSDT")
    decision = create_test_decision_heightened_security()
    current_price = 205.15

    # Convert to Bybit signal
    bybit_signal, heightened_security, tp1_price, tp2_price = executor.convert_arsenal_to_bybit_signal(
        decision, current_price
    )

    logger.info("\nRESULTS:")
    logger.info(f"  Direction: {bybit_signal.direction}")
    logger.info(f"  Entry: ${bybit_signal.entry_price:.2f}")
    logger.info(f"  Stop Loss: ${bybit_signal.stop_loss:.2f}")
    logger.info(f"  TP1: {tp1_price if tp1_price else 'None (Heightened Security)'}")
    logger.info(f"  TP2: ${tp2_price:.2f}")
    logger.info(f"  Heightened Security: {heightened_security}")
    logger.info(f"  RR Ratio: {bybit_signal.risk_reward_ratio:.2f}:1")

    # Verify expectations
    logger.info("\nVERIFICATION:")
    assert heightened_security == True, "[X] Should be heightened security for 1-TP mode"
    logger.info("  [OK] Heightened security: True (correct)")

    assert tp1_price is None, f"[X] TP1 should be None for heightened security, got {tp1_price}"
    logger.info("  [OK] TP1: None (correct for heightened security)")

    assert tp2_price == 210.00, f"[X] TP2 should be 210.00, got {tp2_price}"
    logger.info(f"  [OK] TP2: ${tp2_price:.2f}")

    assert bybit_signal.risk_reward_ratio >= 1.2, "[X] RR should be >= 1.2:1"
    logger.info(f"  [OK] RR: {bybit_signal.risk_reward_ratio:.2f}:1 (>= 1.2:1)")

    logger.info("\n TEST 2 PASSED!\n")
    return True


def test_risk_manager_parameters_2tp():
    """
    Test Case 3: Risk Manager receives correct parameters for 2-TP mode
    """
    logger.info("="*80)
    logger.info("TEST 3: RISK MANAGER PARAMETERS (2-TP MODE)")
    logger.info("="*80)

    executor = ArsenalBybitExecutor("SOLUSDT")
    decision = create_test_decision_2tp_mode()
    current_price = 205.87

    # Convert to signal
    bybit_signal, heightened_security, tp1_price, tp2_price = executor.convert_arsenal_to_bybit_signal(
        decision, current_price
    )

    logger.info("\nRISK MANAGER WOULD RECEIVE:")
    logger.info(f"  trade_id: {bybit_signal.signal_id}")
    logger.info(f"  direction: {decision.direction}")
    logger.info(f"  entry_price: ${bybit_signal.entry_price:.2f}")
    logger.info(f"  stop_loss: ${bybit_signal.stop_loss:.2f}")
    logger.info(f"  tp1: ${tp1_price:.2f}" if tp1_price else "  tp1: None")
    logger.info(f"  tp2: ${tp2_price:.2f}")
    logger.info(f"  heightened_security: {heightened_security}")

    logger.info("\nEXPECTED BEHAVIOR:")
    logger.info("  - Breakeven trigger at 75% to TP1 ($201.50)")
    logger.info("  - Standard reversal detection (candle + volume)")
    logger.info("  - Trailing stops after TP1 hit")
    logger.info("  - TP1: 50% exit, TP2: 50% exit")

    # Verify
    logger.info("\nVERIFICATION:")
    assert heightened_security == False, "[X] Should not be heightened security"
    logger.info("  [OK] Standard risk management (not heightened)")

    assert tp1_price is not None, "[X] TP1 should exist for 2-TP mode"
    logger.info(f"  [OK] TP1 exists: ${tp1_price:.2f}")

    logger.info("\n TEST 3 PASSED!\n")
    return True


def test_risk_manager_parameters_heightened():
    """
    Test Case 4: Risk Manager receives correct parameters for heightened security
    """
    logger.info("="*80)
    logger.info("TEST 4: RISK MANAGER PARAMETERS (HEIGHTENED SECURITY)")
    logger.info("="*80)

    executor = ArsenalBybitExecutor("SOLUSDT")
    decision = create_test_decision_heightened_security()
    current_price = 205.15

    # Convert to signal
    bybit_signal, heightened_security, tp1_price, tp2_price = executor.convert_arsenal_to_bybit_signal(
        decision, current_price
    )

    logger.info("\nRISK MANAGER WOULD RECEIVE:")
    logger.info(f"  trade_id: {bybit_signal.signal_id}")
    logger.info(f"  direction: {decision.direction}")
    logger.info(f"  entry_price: ${bybit_signal.entry_price:.2f}")
    logger.info(f"  stop_loss: ${bybit_signal.stop_loss:.2f}")
    logger.info(f"  tp1: {tp1_price if tp1_price else 'None (Heightened Security)'}")
    logger.info(f"  tp2: ${tp2_price:.2f}")
    logger.info(f"  heightened_security: {heightened_security}")

    logger.info("\nEXPECTED BEHAVIOR:")
    logger.info("  - AGGRESSIVE reversal detection (3m candle closing against position)")
    logger.info("  - LONG: First 3m RED candle closing BELOW most recent GREEN → Close 50% + SL to BE")
    logger.info("  - NO breakeven trigger (no TP1)")
    logger.info("  - Trailing stops towards TP2 only")
    logger.info("  - TP2: 100% exit")

    # Verify
    logger.info("\nVERIFICATION:")
    assert heightened_security == True, "[X] Should be heightened security"
    logger.info("  [OK] Heightened security mode: True")

    assert tp1_price is None, "[X] TP1 should be None in heightened security"
    logger.info("  [OK] TP1: None (correct)")

    logger.info("\n TEST 4 PASSED!\n")
    return True


def main():
    """Run all integration tests"""
    logger.info("\n" + "="*80)
    logger.info("TP STRUCTURE & RISK MANAGER INTEGRATION TESTS")
    logger.info("="*80)
    logger.info("\nThese tests verify:")
    logger.info("  1. Arsenal brain → Executor conversion for 2-TP mode")
    logger.info("  2. Arsenal brain → Executor conversion for heightened security (1-TP)")
    logger.info("  3. Risk Manager receives correct parameters for 2-TP mode")
    logger.info("  4. Risk Manager receives correct parameters for heightened security")
    logger.info("\n")

    try:
        # Run all tests
        test1_passed = test_conversion_2tp_mode()
        test2_passed = test_conversion_heightened_security()
        test3_passed = test_risk_manager_parameters_2tp()
        test4_passed = test_risk_manager_parameters_heightened()

        # Summary
        logger.info("="*80)
        logger.info("[SUCCESS] ALL INTEGRATION TESTS PASSED!")
        logger.info("="*80)
        logger.info("\nPhase 2 Integration Complete:")
        logger.info("  [OK] 2-TP mode conversion working")
        logger.info("  [OK] Heightened security mode conversion working")
        logger.info("  [OK] Risk Manager integration ready for 2-TP mode")
        logger.info("  [OK] Risk Manager integration ready for heightened security")
        logger.info("\nSystem is ready for paper trading validation!")
        logger.info("="*80)

    except AssertionError as e:
        logger.error(f"\n[FAIL] TEST FAILED: {e}")
        return False
    except Exception as e:
        logger.error(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
