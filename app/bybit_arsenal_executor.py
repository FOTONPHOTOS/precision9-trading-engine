"""
Bybit Arsenal Executor
======================
Connects the Live Arsenal System to Bybit for trade execution
Includes full risk management and position monitoring
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from dataclasses import dataclass
from datetime import datetime

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'spectra_integrator_trading_test'))

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Import Bybit execution engine
from bybit_execution_engine import BybitExecutionEngine, TradingSignal as BybitSignal

from trend_continuation_brain import IntelligentDecision

# Import Real-Time Risk Manager
from real_time_risk_manager import RealTimeRiskManager

# Configure logging
logger = logging.getLogger('ARSENAL_BYBIT')


class ArsenalBybitExecutor:
    """
    Integration between Live Arsenal System and Bybit Execution
    """

    def __init__(self, symbol: str = "SOLUSDT"):
        self.symbol = symbol
        self.bybit_engine = None
        self.risk_manager = None  # Real-time risk management
        self.running = False

        # Performance tracking
        self.signals_received = 0
        self.signals_executed = 0
        self.signals_rejected = 0

        logger.info("="*80)
        logger.info("ARSENAL-BYBIT EXECUTION SYSTEM V2")
        logger.info("="*80)
        logger.info(f"Symbol: {symbol}")
        logger.info("Position: $100 with 10x leverage")
        logger.info("Risk: Arsenal + Real-Time Risk Manager + Bybit safety")
        logger.info("="*80)

    async def initialize(self):
        """Initialize Bybit execution engine and Risk Manager"""
        logger.info("Initializing Bybit Execution Engine...")

        self.bybit_engine = BybitExecutionEngine(symbol=self.symbol)
        await self.bybit_engine.initialize()

        logger.info("Initializing Real-Time Risk Manager...")
        # Risk Manager will use Bybit's client for market data
        # Note: Risk Manager needs Binance client for candle data (Bybit uses Binance for price data)
        try:
            from binance.client import Client as BinanceClient
            binance_api_key = os.getenv('BINANCE_API_KEY', '')
            binance_api_secret = os.getenv('BINANCE_API_SECRET', '')
            binance_client = BinanceClient(binance_api_key, binance_api_secret)
            self.risk_manager = RealTimeRiskManager(binance_client, self.bybit_engine, symbol=self.symbol)
            logger.info(" Real-Time Risk Manager initialized")
        except Exception as e:
            logger.warning(f" Risk Manager initialization failed: {e}")
            logger.warning("   Continuing without real-time risk management")
            self.risk_manager = None

        logger.info(" Arsenal-Bybit executor initialized successfully")
        logger.info(f" Account Balance: ${self.bybit_engine.account_balance:.2f}")
        logger.info(f" Available: ${self.bybit_engine.available_balance:.2f}")

        # --- TRADE RECOVERY LOGIC ---
        # If a position was found on the exchange during initialization, register it for management.
        if self.bybit_engine.position and self.risk_manager:
            await self._register_existing_trade(self.bybit_engine.position)

    async def _register_existing_trade(self, position: "Position"):
        """Creates a synthetic signal for an existing trade and registers it with the Risk Manager."""
        logger.warning("="*80)
        logger.warning(" EXISTING POSITION DETECTED - INITIATING TRADE RECOVERY")
        logger.warning("="*80)
        logger.warning(f"   - Symbol: {position.symbol}")
        logger.warning(f"   - Direction: {position.side}")
        logger.warning(f"   - Entry Price: ${position.entry_price:.2f}")
        logger.warning(f"   - Size: {position.size}")

        # Create a synthetic IntelligentDecision object to pass to the risk manager.
        # Some values will be defaults as we can't know the original signal.
        direction = "LONG" if position.side == "Buy" else "SHORT"
        entry_price = position.entry_price
        stop_loss = position.stop_loss

        # We have to create synthetic TPs. Let's use a standard 2.0 RRR.
        risk_per_unit = abs(entry_price - stop_loss)
        if direction == "LONG":
            tp2 = entry_price + (risk_per_unit * 2.0)
        else:
            tp2 = entry_price - (risk_per_unit * 2.0)

        # Since we don't know if it was a 1-TP or 2-TP trade, we'll treat it as a 1-TP trade
        # for maximum safety (Heightened Security mode).
        tp1 = None
        heightened_security = True

        logger.warning("   - Synthetic TP created at 2.0 R:R for management.")
        logger.warning("   - Activating HEIGHTENED SECURITY mode for this recovered trade.")

        # Register with Risk Manager
        try:
            self.risk_manager.add_trade(
                trade_id=f"RECOVERED_{position.position_id}",
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                tp1=tp1,
                tp2=tp2,
                position_size=position.size,
                heightened_security=heightened_security
            )

            # Start the risk manager's monitoring loop if it's not already running
            if not hasattr(self.risk_manager, '_monitoring_task') or self.risk_manager._monitoring_task is None:
                self.risk_manager._monitoring_task = asyncio.create_task(
                    self.risk_manager.start_monitoring()
                )
                logger.info(" Risk Manager monitoring loop started in background for recovered trade.")
            
            logger.warning(" RECOVERY COMPLETE: Existing trade is now under full risk management.")
            logger.warning("="*80)

        except Exception as e:
            logger.error(f" FAILED TO RECOVER TRADE: {e}")
            logger.error("   - The existing position will NOT be managed by the advanced risk manager.")

    def convert_arsenal_to_bybit_signal(self, decision: IntelligentDecision, current_price: float) -> tuple:
        """
        Convert Arsenal's IntelligentDecision to Bybit's TradingSignal format

        Arsenal V2 TP Structure:
        - 2-TP mode: [tp1, tp2] for 50/50 split
        - 1-TP mode: [tp2] for 100% position (heightened security)

        Returns:
            tuple: (BybitSignal, heightened_security: bool, tp1_price: Optional[float], tp2_price: float)
        """
        # Generate signal ID
        signal_id = f"ARSENAL_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Use precision TP/SL if available, otherwise use brain's levels
        entry = current_price
        stop_loss = decision.stop_loss

        # Arsenal provides list of take profits
        take_profits = decision.take_profits if decision.take_profits else []

        # Parse heightened_security flag from decision (if available)
        heightened_security = getattr(decision, 'heightened_security', False)

        # Handle new Arsenal V2 TP structure
        if len(take_profits) == 2:
            # 2-TP MODE: 50/50 split
            tp1 = take_profits[0]  # High-impact zone at/beyond 1:1 RR
            tp2 = take_profits[1]  # Final target
            # Extend TP3 beyond TP2 for trailing
            tp_distance = abs(tp2 - tp1)
            if decision.direction == 'LONG':
                tp3 = tp2 + (tp_distance * 0.5)
            else:
                tp3 = tp2 - (tp_distance * 0.5)
            heightened_security = False
            logger.info(f"   [2-TP MODE] TP1: ${tp1:.2f} (50%), TP2: ${tp2:.2f} (50%)")

        elif len(take_profits) == 1:
            # 1-TP MODE: HEIGHTENED SECURITY - 100% position at single TP
            tp2 = take_profits[0]  # Final target
            tp1 = None  # No TP1 in heightened security mode
            # Set tp3 for potential trailing
            tp_distance = abs(tp2 - entry)
            if decision.direction == 'LONG':
                tp3 = tp2 + (tp_distance * 0.3)
            else:
                tp3 = tp2 - (tp_distance * 0.3)
            heightened_security = True
            logger.info(f"   [1-TP MODE] HEIGHTENED SECURITY! TP: ${tp2:.2f} (100%)")

        elif len(take_profits) >= 3:
            # Legacy 3-TP mode (backwards compatibility)
            tp1, tp2, tp3 = take_profits[0], take_profits[1], take_profits[2]
            heightened_security = False
            logger.info(f"   [LEGACY 3-TP MODE] TP1: ${tp1:.2f}, TP2: ${tp2:.2f}, TP3: ${tp3:.2f}")

        else:
            # No TPs provided - create based on RR (fallback)
            risk = abs(entry - stop_loss)
            if decision.direction == 'LONG':
                tp1 = entry + risk * 1.5
                tp2 = entry + risk * 2.0
                tp3 = entry + risk * 2.5
            else:
                tp1 = entry - risk * 1.5
                tp2 = entry - risk * 2.0
                tp3 = entry - risk * 2.5
            heightened_security = False
            logger.warning(f"   [FALLBACK] No TPs provided, using RR-based targets")

        # Calculate actual RR ratio (use blended RR for 2-TP mode)
        risk = abs(entry - stop_loss)
        if len(take_profits) == 2 and tp1:
            # Blended RR: (TP1_RR × 0.5) + (TP2_RR × 0.5)
            reward_tp1 = abs(tp1 - entry)
            reward_tp2 = abs(tp2 - entry)
            rr_tp1 = reward_tp1 / risk if risk > 0 else 0
            rr_tp2 = reward_tp2 / risk if risk > 0 else 0
            rr_ratio = (rr_tp1 * 0.5) + (rr_tp2 * 0.5)
            logger.info(f"   [BLENDED RR] TP1: {rr_tp1:.2f}:1, TP2: {rr_tp2:.2f}:1 → {rr_ratio:.2f}:1")
        elif tp1:
            reward = abs(tp1 - entry)
            rr_ratio = reward / risk if risk > 0 else 0
        else:
            # Heightened security mode - use TP2 for RR
            reward = abs(tp2 - entry)
            rr_ratio = reward / risk if risk > 0 else 0

        # Extract confluence score from opportunities (robust parsing)
        confluence_score = 50  # Default
        if decision.opportunities:
            for opp in decision.opportunities:
                if 'confluence' in opp.lower():
                    try:
                        # Extract number from formats like "Excellent confluence (194 points)"
                        parts = opp.split('(')
                        if len(parts) > 1:
                            num_str = parts[1].split(' ')[0].strip()
                            confluence_score = int(num_str)
                            break
                    except (ValueError, IndexError):
                        pass  # Keep default

        # Convert to Bybit signal
        # Note: Bybit still uses 3-TP structure, but tp1 may be None for heightened security
        bybit_signal = BybitSignal(
            signal_id=signal_id,
            direction=decision.direction,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit_1=tp1 if tp1 is not None else tp2,  # In 1-TP mode, tp1 is None; use tp2 as the primary TP.
            take_profit_2=tp2,
            take_profit_3=tp3,
            confidence=decision.confidence,
            confluence_score=confluence_score,
            timestamp=datetime.utcnow().timestamp(),
            risk_reward_ratio=rr_ratio,
            position_size=decision.position_size_multiplier * 100  # Convert to percentage
        )

        # Return signal with metadata for Risk Manager
        return bybit_signal, heightened_security, tp1, tp2

    async def execute_arsenal_decision(self, decision: IntelligentDecision, current_price: float) -> bool:
        """
        Execute Arsenal decision on Bybit

        Args:
            decision: IntelligentDecision from Arsenal brain
            current_price: Current market price

        Returns:
            bool: True if executed successfully
        """
        self.signals_received += 1

        logger.info("="*80)
        logger.info(f" NEW ARSENAL DECISION")
        logger.info("="*80)
        logger.info(f"Direction: {decision.direction}")
        logger.info(f"Confidence: {decision.confidence:.1%}")
        logger.info(f"Signal Strength: {decision.signal_strength}")
        logger.info(f"Risk/Reward: {decision.risk_reward:.2f}:1")
        logger.info(f"Position Size: {decision.position_size_multiplier:.0%}")

        # Check if should trade
        if not decision.should_trade:
            logger.warning(" Arsenal brain decided NOT to trade")
            logger.warning(f"   Reason: {decision.blockers[0] if decision.blockers else 'Confidence/setup insufficient'}")
            self.signals_rejected += 1
            return False

        # Check urgency
        if decision.urgency == 'DO_NOT_TRADE':
            logger.warning(" Urgency level: DO_NOT_TRADE")
            self.signals_rejected += 1
            return False

        # Check if already in position
        if self.bybit_engine.position_status.value != "no_position":
            logger.warning(" Already in position - skipping signal")
            logger.warning(f"   Position Status: {self.bybit_engine.position_status.value}")
            self.signals_rejected += 1
            return False

        # Check daily drawdown
        risk_report = await self.bybit_engine.get_risk_report()
        if risk_report['daily_pnl'] <= -20:  # $20 max daily loss
            logger.error(" Daily drawdown limit reached (-$20)")
            self.signals_rejected += 1
            return False

        # Convert Arsenal decision to Bybit signal
        bybit_signal, heightened_security, tp1_price, tp2_price = self.convert_arsenal_to_bybit_signal(decision, current_price)

        logger.info("="*80)
        logger.info(" CONVERTED TO BYBIT SIGNAL")
        logger.info("="*80)
        logger.info(f"Signal ID: {bybit_signal.signal_id}")
        logger.info(f"Entry: ${bybit_signal.entry_price:.2f}")
        logger.info(f"Stop Loss: ${bybit_signal.stop_loss:.2f}")

        if heightened_security:
            logger.info(f" HEIGHTENED SECURITY MODE ACTIVE")
            logger.info(f"TP: ${bybit_signal.take_profit_2:.2f} (100% exit)")
            logger.info(f"Real-time reversal detection enabled (3m aggressive)")
        elif tp1_price:
            logger.info(f"TP1: ${bybit_signal.take_profit_1:.2f} (50% exit)")
            logger.info(f"TP2: ${bybit_signal.take_profit_2:.2f} (50% exit)")
        else:
            logger.info(f"TP1: ${bybit_signal.take_profit_1:.2f} (40% exit)")
            logger.info(f"TP2: ${bybit_signal.take_profit_2:.2f} (30% exit)")
            logger.info(f"TP3: ${bybit_signal.take_profit_3:.2f} (30% exit)")

        logger.info(f"Risk/Reward: {bybit_signal.risk_reward_ratio:.2f}:1")

        # Validate minimum RR
        min_rrr = float(os.getenv('MIN_RISK_REWARD', '1.2'))
        if bybit_signal.risk_reward_ratio < min_rrr:
            logger.error("="*80)
            logger.error(" TRADE REJECTED - RRR BELOW MINIMUM")
            logger.error(f"   Actual RRR: {bybit_signal.risk_reward_ratio:.2f}:1")
            logger.error(f"   Minimum Required: {min_rrr}:1")
            logger.error("="*80)
            self.signals_rejected += 1
            return False

        # Execute on Bybit
        logger.info("="*80)
        logger.info(" EXECUTING ON BYBIT")
        logger.info("="*80)

        success = await self.bybit_engine.execute_signal(bybit_signal)

        if success:
            self.signals_executed += 1
            logger.info(f" Signal executed successfully ({self.signals_executed}/{self.signals_received})")

            # Get actual filled position
            await self.bybit_engine.check_positions()
            actual_position = self.bybit_engine.position

            if actual_position:
                logger.info("="*80)
                logger.info(" POSITION OPENED")
                logger.info("="*80)
                logger.info(f"   Size: {actual_position.size} SOL")
                logger.info(f"   Entry: ${actual_position.entry_price:.2f}")
                logger.info(f"   Leverage: {actual_position.leverage}x")
                logger.info(f"   Stop Loss: ${actual_position.stop_loss:.2f}")
                logger.info(f"   Take Profit: ${actual_position.take_profit:.2f}")
                logger.info("="*80)

                # Launch Real-Time Risk Manager
                if self.risk_manager:
                    try:
                        logger.info("="*80)
                        logger.info(" LAUNCHING REAL-TIME RISK MANAGER")
                        logger.info("="*80)

                        # Add trade to risk manager
                        self.risk_manager.add_trade(
                            trade_id=bybit_signal.signal_id,
                            direction=decision.direction,
                            entry_price=actual_position.entry_price,
                            stop_loss=actual_position.stop_loss,
                            tp1=tp1_price,  # None if heightened security
                            tp2=tp2_price,
                            position_size=actual_position.size,
                            heightened_security=heightened_security,
                            swing_highs=decision.swing_highs,
                            swing_lows=decision.swing_lows
                        )

                        logger.info(f"   Trade ID: {bybit_signal.signal_id}")
                        logger.info(f"   Heightened Security: {'YES' if heightened_security else 'NO'}")
                        logger.info(f"   TP1: ${tp1_price:.2f}" if tp1_price else "   TP1: None (Heightened Security)")
                        logger.info(f"   TP2: ${tp2_price:.2f}")
                        logger.info(f"   Position Size: {actual_position.size} SOL")
                        logger.info("="*80)
                        logger.info(" Risk Manager actively monitoring trade")
                        logger.info("   - Breakeven movement: 75% to TP1 + 3m confirmation")
                        if heightened_security:
                            logger.info("   - Aggressive reversal detection: 3m candle closing against position")
                        else:
                            logger.info("   - Standard reversal detection: Candle + volume confirmation")
                        logger.info("   - Progressive trailing stops: 5m candles, 4 phases")
                        logger.info("="*80)

                        # Start monitoring in background (if not already running)
                        if not hasattr(self.risk_manager, '_monitoring_task') or self.risk_manager._monitoring_task is None:
                            self.risk_manager._monitoring_task = asyncio.create_task(
                                self.risk_manager.start_monitoring()
                            )
                            logger.info(" Risk Manager monitoring loop started in background")

                    except Exception as e:
                        logger.error(f" Failed to launch Risk Manager: {e}")
                        logger.error("   Trade will continue with Bybit's built-in risk management only")

            return True
        else:
            self.signals_rejected += 1
            logger.warning(f" Signal execution failed ({self.signals_rejected} rejected)")
            return False

    async def monitor_position_outcome(self):
        """Monitor position and sync with Arsenal"""
        while self.running:
            try:
                # Check Bybit position status
                await self.bybit_engine.check_positions()

                # Position monitoring happens inside bybit_engine
                # We just need to keep this running

                # If we have an active position, check more frequently
                # Otherwise, check less often to reduce log spam
                if self.bybit_engine.position_status.value != "no_position":
                    sleep_time = 2  # Check every 2 seconds when in position
                else:
                    sleep_time = 30  # Check every 30 seconds when no position

            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")
                sleep_time = 10  # Default to 10 seconds on error

            await asyncio.sleep(sleep_time)

    async def start(self):
        """Start monitoring loop"""
        self.running = True

        # Start position monitoring
        monitor_task = asyncio.create_task(self.monitor_position_outcome())

        logger.info(" Arsenal-Bybit executor running")

        # Keep running
        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("Monitoring cancelled")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("="*80)
        logger.info("SHUTDOWN INITIATED")
        logger.info("="*80)

        self.running = False

        # Print final statistics
        logger.info(f" Final Statistics:")
        logger.info(f"   Signals Received: {self.signals_received}")
        logger.info(f"   Signals Executed: {self.signals_executed}")
        logger.info(f"   Signals Rejected: {self.signals_rejected}")

        if self.signals_received > 0:
            execution_rate = (self.signals_executed / self.signals_received) * 100
            logger.info(f"   Execution Rate: {execution_rate:.1f}%")

        # Get final risk report
        if self.bybit_engine:
            risk_report = await self.bybit_engine.get_risk_report()
            logger.info(f"")
            logger.info(f" Final Account Status:")
            logger.info(f"   Balance: ${risk_report['account_balance']:.2f}")
            logger.info(f"   Daily P&L: ${risk_report['daily_pnl']:.2f} ({risk_report['daily_pnl_pct']:.1f}%)")
            logger.info(f"   Win Rate: {risk_report['win_rate']:.1f}%")

            # Shutdown Bybit engine
            await self.bybit_engine.shutdown()

        logger.info("="*80)
        logger.info("SHUTDOWN COMPLETE")
        logger.info("="*80)


async def test_executor():
    """Test the executor"""
    from intelligent_strategy_brain import IntelligentDecision

    executor = ArsenalBybitExecutor("SOLUSDT")
    await executor.initialize()

    # Create test decision
    test_decision = IntelligentDecision(
        direction='LONG',
        confidence=0.75,
        signal_strength='STRONG',
        entry_zone=(220.00, 220.50),
        stop_loss=218.00,
        take_profits=[223.00, 225.00, 227.00],
        risk_reward=2.5,
        position_size_multiplier=1.0,
        max_risk_percent=1.0,
        reasoning_chain=["Test signal"],
        blockers=[],
        warnings=[],
        opportunities=["Excellent confluence (150 points)"],
        should_trade=True,
        urgency='IMMEDIATE',
        analysis_quality=0.95,
        decision_timestamp=datetime.utcnow()
    )

    # Execute test signal
    # await executor.execute_arsenal_decision(test_decision, 220.25)

    # Keep running
    try:
        await executor.start()
    except KeyboardInterrupt:
        await executor.shutdown()


if __name__ == "__main__":
    asyncio.run(test_executor())
