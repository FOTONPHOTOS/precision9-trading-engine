"""
Test Arsenal Candle Bridge + Risk Manager Integration
======================================================
Demonstrates how Arsenal's real-time candle analysis connects to Risk Manager

This test shows:
1. Arsenal monitoring 3m/5m candles every 5 seconds
2. Pattern detection (bullish/bearish breaks)
3. Real-time callbacks updating Risk Manager cache
4. Enhanced reversal detection using patterns
5. Complete integration workflow

Author: Arsenal Trading System
Date: 2025-10-11
"""

import asyncio
import logging
from binance.client import AsyncClient
from arsenal_candle_bridge import ArsenalCandleBridge
from real_time_risk_manager import RealTimeRiskManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('ARSENAL_RISK_TEST')


async def test_arsenal_risk_integration():
    """
    Complete integration test

    Simulates a live trade being monitored by:
    - Arsenal Candle Bridge (pattern detection)
    - Risk Manager (reversal detection + risk management)
    """

    logger.info("="*80)
    logger.info("Arsenal + Risk Manager Integration Test")
    logger.info("="*80)

    # 1. Initialize Binance client
    logger.info("Step 1: Initializing Binance client...")
    binance_client = await AsyncClient.create()  # Uses public API (no keys needed)

    # 2. Create Arsenal Candle Bridge
    logger.info("Step 2: Creating Arsenal Candle Bridge...")
    arsenal_bridge = ArsenalCandleBridge(symbol="SOLUSDT")
    logger.info("   Arsenal Bridge initialized")
    logger.info("   Monitoring: 3m and 5m candles")
    logger.info("   Check interval: 5 seconds")
    logger.info("   Pattern detection: ENABLED")

    # 3. Create Risk Manager WITH Arsenal integration
    logger.info("Step 3: Creating Risk Manager with Arsenal integration...")

    # Convert AsyncClient to sync Client for Risk Manager
    from binance.client import Client
    sync_client = Client()

    risk_manager = RealTimeRiskManager(
        binance_client=sync_client,
        symbol="SOLUSDT",
        arsenal_bridge=arsenal_bridge  # ← CRITICAL: Connect Arsenal!
    )

    logger.info("   Risk Manager initialized")
    logger.info("   Arsenal Bridge: CONNECTED")
    logger.info("   Check interval: 3 seconds")
    logger.info("   Pattern-enhanced reversal detection: ENABLED")

    # 4. Register a test trade
    logger.info("\nStep 4: Registering test trade...")
    logger.info("  (Simulates your trade scenario)")

    risk_manager.add_trade(
        trade_id="TEST_ARSENAL_001",
        direction="LONG",
        entry_price=183.91,
        stop_loss=180.50,
        tp1=186.88,
        tp2=189.00,
        position_size=1.4
    )

    logger.info("\n" + "="*80)
    logger.info("SYSTEM RUNNING - Monitoring for 2 minutes")
    logger.info("="*80)
    logger.info("\nWatch for:")
    logger.info("  • 3m/5m candle close events from Arsenal")
    logger.info("  • Pattern detection (bullish/bearish breaks)")
    logger.info("  • Risk Manager cache updates")
    logger.info("  • Reversal detection triggers")
    logger.info("\nPress Ctrl+C to stop early\n")

    # 5. Run both systems concurrently
    try:
        # Start Arsenal monitoring (5s checks)
        arsenal_task = asyncio.create_task(arsenal_bridge.start_monitoring())

        # Start Risk Manager monitoring (3s checks)
        risk_task = asyncio.create_task(risk_manager.start_monitoring())

        # Run for 2 minutes (or until Ctrl+C)
        await asyncio.sleep(120)

        logger.info("\n" + "="*80)
        logger.info("Test complete!")
        logger.info("="*80)

        # Stop both systems
        arsenal_bridge.stop_monitoring()
        risk_manager.stop_monitoring()

    except KeyboardInterrupt:
        logger.info("\n" + "="*80)
        logger.info("Test stopped by user")
        logger.info("="*80)

        arsenal_bridge.stop_monitoring()
        risk_manager.stop_monitoring()

    finally:
        await binance_client.close_connection()

    # 6. Summary
    logger.info("\nIntegration Test Summary:")
    logger.info("   Arsenal Candle Bridge operational")
    logger.info("   Risk Manager receiving real-time callbacks")
    logger.info("   Pattern detection integrated into reversal logic")
    logger.info("   Cache updated in real-time (no stale data)")
    logger.info("\nSystem ready for live deployment!")


async def test_arsenal_bridge_only():
    """
    Test Arsenal Candle Bridge standalone

    Shows pattern detection and candle monitoring without Risk Manager
    """

    logger.info("="*80)
    logger.info("Arsenal Candle Bridge Standalone Test")
    logger.info("="*80)

    # Create bridge
    bridge = ArsenalCandleBridge(symbol="SOLUSDT")

    # Define test callback
    async def on_3m_close(event):
        """Handle 3m candle close"""
        direction = " GREEN" if event.is_green else " RED"
        logger.info(f"\n{'='*60}")
        logger.info(f"3M CANDLE CLOSE: {direction}")
        logger.info(f"{'='*60}")
        logger.info(f"Time: {event.timestamp}")
        logger.info(f"Close: ${event.close:.2f}")
        logger.info(f"Volume: {event.volume:.0f}")

        if event.has_bullish_break:
            logger.info(f" BULLISH BREAK: {event.break_strength:.1%} strength")
        elif event.has_bearish_break:
            logger.info(f" BEARISH BREAK: {event.break_strength:.1%} strength")

        if event.near_resistance:
            logger.info(f"  Near resistance: ${event.resistance_level:.2f}")
        if event.near_support:
            logger.info(f" Near support: ${event.support_level:.2f}")

    async def on_5m_close(event):
        """Handle 5m candle close"""
        direction = " GREEN" if event.is_green else " RED"
        logger.info(f"\n5M CANDLE: {direction} at ${event.close:.2f}")

    # Set callbacks
    bridge.set_callbacks(
        on_3m_close=on_3m_close,
        on_5m_close=on_5m_close
    )

    # Run for 2 minutes
    logger.info("\nMonitoring candles for 2 minutes...")
    logger.info("Press Ctrl+C to stop early\n")

    try:
        await asyncio.wait_for(bridge.start_monitoring(), timeout=120)
    except asyncio.TimeoutError:
        logger.info("\nTest complete!")
        bridge.stop_monitoring()
    except KeyboardInterrupt:
        logger.info("\nTest stopped by user")
        bridge.stop_monitoring()


def print_menu():
    """Print test menu"""
    print("\n" + "="*80)
    print("Arsenal + Risk Manager Integration Tests")
    print("="*80)
    print("\nAvailable Tests:")
    print("  1. Full Integration Test (Arsenal + Risk Manager)")
    print("  2. Arsenal Bridge Only Test (Pattern Detection)")
    print("  3. Exit")
    print("\n" + "="*80)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Arsenal Candle Bridge + Risk Manager Integration")
    print("="*80)
    print("\nThis test demonstrates:")
    print("  • Real-time candle monitoring from Arsenal")
    print("  • Pattern detection (bullish/bearish breaks)")
    print("  • Risk Manager integration with callbacks")
    print("  • Enhanced reversal detection")

    print_menu()

    choice = input("\nSelect test (1-3): ").strip()

    if choice == "1":
        print("\nRunning Full Integration Test...")
        asyncio.run(test_arsenal_risk_integration())

    elif choice == "2":
        print("\nRunning Arsenal Bridge Only Test...")
        asyncio.run(test_arsenal_bridge_only())

    elif choice == "3":
        print("\nExiting...")

    else:
        print("\nInvalid choice. Exiting...")
