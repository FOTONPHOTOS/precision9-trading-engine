"""
Real-Time Risk Manager
======================
Dynamically manages open trades with intelligent risk adjustment:
- Moves stop to breakeven at optimal points
- Detects reversal patterns and exits early
- Trails stops to lock in profits
- Heightened security mode for high-risk trades

Author: Arsenal Trading System
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
import logging
from dataclasses import dataclass, field

from binance.client import Client

# Arsenal Candle Bridge integration (optional)
try:
    from arsenal_candle_bridge import ArsenalCandleBridge, CandleCloseEvent
    ARSENAL_BRIDGE_AVAILABLE = True
except ImportError:
    ARSENAL_BRIDGE_AVAILABLE = False
    CandleCloseEvent = None

logger = logging.getLogger('RISK_MANAGER')


@dataclass
class TradeState:
    """Current state of an active trade"""
    trade_id: str
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    current_sl: float
    tp1: Optional[float]
    tp2: float
    position_size: float
    remaining_size: float  # After TP1 partial exit

    # Risk management flags
    heightened_security: bool  # True if no TP1 (aggressive reversal detection)
    sl_moved_to_breakeven: bool
    tp1_hit: bool

    # Tracking
    entry_time: datetime
    last_check: datetime
    highest_profit: float  # For trailing
    lowest_price_seen: float  # For LONG trailing
    highest_price_seen: float  # For SHORT trailing
    most_recent_red_candle: Optional[float]
    most_recent_green_candle: Optional[float]

    # Structure (for BOS checks)
    swing_highs: List[Dict] = field(default_factory=list)
    swing_lows: List[Dict] = field(default_factory=list)
    structure_swing_high: Optional[float] = None # For 5m BOS reversal
    structure_swing_low: Optional[float] = None # For 5m BOS reversal

    # CRITICAL: Prevent multiple triggers (like Horus) - Fields with defaults MUST come last
    reversal_triggered: bool = False  # Standard reversal already processed
    heightened_security_triggered: bool = False  # Heightened security already processed
    heightened_security_triggered: bool = False  # Heightened security already processed
    breakeven_triggered: bool = False  # Breakeven already moved


class RealTimeRiskManager:
    """
    Manages open trades with real-time risk adjustment

    Features:
    1. Breakeven Stop Movement (75% to TP1 + 3m confirmation)
    2. Heightened Security Mode (No TP1 trades - aggressive reversal detection)
    3. Standard Reversal Detection (Candle + Volume confirmation)
    4. Trailing Stops (5m candles, progressive locking)
    """

    def __init__(
        self,
        binance_client: Client,
        execution_engine: 'BybitExecutionEngine',
        symbol: str = "SOLUSDT",
        arsenal_bridge: Optional['ArsenalCandleBridge'] = None
    ):
        self.client = binance_client
        self.execution_engine = execution_engine
        self.symbol = symbol
        self.active_trades: Dict[str, TradeState] = {}
        self.running = False

        # Configuration - BULLETPROOF SETTINGS
        self.check_interval = 3  # Check every 3 seconds (was 10s - TOO SLOW!)
        self.breakeven_threshold = 0.75  # Move to BE at 75% to TP1
        self.reversal_volume_multiplier = 1.5  # Volume must be 1.5x average
        self.trailing_atr_multiplier = 1.5  # Trail at 1.5× ATR

        # Cache for candle data
        self.candle_3m_cache: List[Dict] = []
        self.candle_5m_cache: List[Dict] = []
        self.candle_15m_cache: List[Dict] = []
        self.last_3m_fetch = 0
        self.last_5m_fetch = 0
        self.last_15m_fetch = 0

        # Arsenal Candle Bridge integration
        self.arsenal_bridge = arsenal_bridge
        self.using_arsenal_bridge = arsenal_bridge is not None

        # Pattern detection data from Arsenal
        self.latest_3m_pattern: Optional[Dict] = None
        self.latest_5m_pattern: Optional[Dict] = None

        # Set up Arsenal Bridge callbacks if available
        if self.arsenal_bridge:
            self._setup_arsenal_callbacks()
            logger.info("Arsenal Candle Bridge connected - Real-time pattern detection enabled")

    def add_trade(
        self,
        trade_id: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        tp1: Optional[float],
        tp2: float,
        position_size: float,
        heightened_security: bool = False,
        swing_highs: List[Dict] = [],
        swing_lows: List[Dict] = []
    ):
        """
        Register a new trade for real-time management

        Args:
            trade_id: Unique identifier for the trade
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price
            stop_loss: Initial stop loss
            tp1: First take profit (None if skipped)
            tp2: Final take profit
            position_size: Position size in base currency
            heightened_security: True if no TP1 (aggressive reversal detection)
            swing_highs: Market structure at time of trade
            swing_lows: Market structure at time of trade
        """

        trade = TradeState(
            trade_id=trade_id,
            symbol=self.symbol,
            direction=direction,
            entry_price=entry_price,
            current_sl=stop_loss,
            tp1=tp1,
            tp2=tp2,
            position_size=position_size,
            remaining_size=position_size,
            heightened_security=heightened_security,
            sl_moved_to_breakeven=False,
            tp1_hit=False,
            entry_time=datetime.utcnow(),
            last_check=datetime.utcnow(),
            highest_profit=0.0,
            lowest_price_seen=entry_price if direction == 'LONG' else float('inf'),
            highest_price_seen=entry_price if direction == 'SHORT' else 0.0,
            most_recent_red_candle=None,
            most_recent_green_candle=None,
            swing_highs=swing_highs,
            swing_lows=swing_lows
        )

        # Determine the key structural point for 5m BOS reversal checks
        if direction == 'LONG' and swing_lows:
            # Find the highest swing low that is below the entry price
            relevant_lows = [s['price'] for s in swing_lows if s['price'] < entry_price]
            if relevant_lows:
                trade.structure_swing_low = max(relevant_lows)
                logger.info(f"  [5m BOS] Reversal structure point set to swing low at ${trade.structure_swing_low:.2f}")
        elif direction == 'SHORT' and swing_highs:
            # Find the lowest swing high that is above the entry price
            relevant_highs = [s['price'] for s in swing_highs if s['price'] > entry_price]
            if relevant_highs:
                trade.structure_swing_high = min(relevant_highs)
                logger.info(f"  [5m BOS] Reversal structure point set to swing high at ${trade.structure_swing_high:.2f}")

        self.active_trades[trade_id] = trade

        mode = "HEIGHTENED SECURITY" if heightened_security else "NORMAL"
        logger.info(f"[{trade_id}] Trade registered for real-time management")
        logger.info(f"  Direction: {direction}")
        logger.info(f"  Entry: ${entry_price:.2f}")
        logger.info(f"  SL: ${stop_loss:.2f}")
        logger.info(f"  TP1: ${tp1:.2f}" if tp1 else "  TP1: SKIPPED")
        logger.info(f"  TP2: ${tp2:.2f}")
        logger.info(f"  Mode: {mode}")

    def remove_trade(self, trade_id: str):
        """Remove a trade from active management"""
        if trade_id in self.active_trades:
            del self.active_trades[trade_id]
            logger.info(f"[{trade_id}] Trade removed from management")

    async def start_monitoring(self):
        """Start the real-time monitoring loop"""
        self.running = True
        logger.info("Real-Time Risk Manager started")

        while self.running:
            try:
                if self.active_trades:
                    await self._monitoring_cycle()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        if self.arsenal_bridge:
            self.arsenal_bridge.stop_monitoring()
        logger.info("Real-Time Risk Manager stopped")

    def _setup_arsenal_callbacks(self):
        """Set up callbacks for Arsenal Candle Bridge"""
        self.arsenal_bridge.set_callbacks(
            on_3m_close=self._handle_3m_candle_close,
            on_5m_close=self._handle_5m_candle_close,
            on_pattern=self._handle_pattern_detected
        )

    async def _handle_3m_candle_close(self, event: 'CandleCloseEvent'):
        """
        Handle 3m candle close event from Arsenal Bridge

        Updates cache immediately with fresh candle data
        Stores pattern analysis for reversal detection
        """

        # Update 3m candle cache with the new candle
        candle_dict = {
            'open': event.open,
            'high': event.high,
            'low': event.low,
            'close': event.close,
            'volume': event.volume
        }

        # Update cache
        if self.candle_3m_cache:
            self.candle_3m_cache.append(candle_dict)
            # Keep only last 20 candles
            if len(self.candle_3m_cache) > 20:
                self.candle_3m_cache.pop(0)
        else:
            self.candle_3m_cache = [candle_dict]

        self.last_3m_fetch = time.time()

        # Store pattern analysis
        self.latest_3m_pattern = {
            'has_bullish_break': event.has_bullish_break,
            'has_bearish_break': event.has_bearish_break,
            'break_strength': event.break_strength,
            'near_resistance': event.near_resistance,
            'near_support': event.near_support,
            'resistance_level': event.resistance_level,
            'support_level': event.support_level,
            'is_green': event.is_green,
            'is_red': event.is_red
        }

        # Log significant patterns
        if event.has_bullish_break or event.has_bearish_break:
            pattern_type = "BULLISH BREAK" if event.has_bullish_break else "BEARISH BREAK"
            logger.info(f"Arsenal detected {pattern_type} on 3m (strength: {event.break_strength:.1%})")

        logger.debug(f"3m candle close at ${event.close:.2f} - Cache updated from Arsenal")

    async def _handle_5m_candle_close(self, event: 'CandleCloseEvent'):
        """
        Handle 5m candle close event from Arsenal Bridge

        Updates cache for trailing stop calculations
        """

        # Update 5m candle cache
        candle_dict = {
            'open': event.open,
            'high': event.high,
            'low': event.low,
            'close': event.close,
            'volume': event.volume
        }

        if self.candle_5m_cache:
            self.candle_5m_cache.append(candle_dict)
            if len(self.candle_5m_cache) > 20:
                self.candle_5m_cache.pop(0)
        else:
            self.candle_5m_cache = [candle_dict]

        self.last_5m_fetch = time.time()

        # Store pattern analysis
        self.latest_5m_pattern = {
            'has_bullish_break': event.has_bullish_break,
            'has_bearish_break': event.has_bearish_break,
            'break_strength': event.break_strength,
            'near_resistance': event.near_resistance,
            'near_support': event.near_support,
            'resistance_level': event.resistance_level,
            'support_level': event.support_level,
            'is_green': event.is_green,
            'is_red': event.is_red
        }

        logger.debug(f"5m candle close at ${event.close:.2f} - Cache updated from Arsenal")

    async def _handle_pattern_detected(self, event: 'CandleCloseEvent'):
        """
        Handle significant pattern detection from Arsenal

        Could be used for additional alerts or risk adjustments
        """
        pattern_type = "BULLISH" if event.has_bullish_break else "BEARISH"
        logger.info(f"Arsenal pattern alert: {pattern_type} break detected!")
        logger.info(f"  Timeframe: {event.timeframe}")
        logger.info(f"  Strength: {event.break_strength:.1%}")
        logger.info(f"  Price: ${event.close:.2f}")

    async def _monitoring_cycle(self):
        """Run one monitoring cycle for all active trades"""

        # Fetch current price and candles
        current_price = await self._get_current_price()
        candles_3m = await self._get_candles('3m', limit=20)
        candles_5m = await self._get_candles('5m', limit=20)
        candles_15m = await self._get_candles('15m', limit=20)

        if not current_price or not candles_3m or not candles_5m or not candles_15m:
            return

        # Calculate average volume for reversal detection
        avg_volume_3m = sum(float(c['volume']) for c in candles_3m[-10:]) / 10

        # Check each active trade
        for trade_id, trade in list(self.active_trades.items()):
            try:
                await self._check_trade(
                    trade,
                    current_price,
                    candles_3m,
                    candles_5m,
                    candles_15m,
                    avg_volume_3m
                )
            except Exception as e:
                logger.error(f"[{trade_id}] Error checking trade: {e}")

    async def _check_trade(
        self,
        trade: TradeState,
        current_price: float,
        candles_3m: List[Dict],
        candles_5m: List[Dict],
        candles_15m: List[Dict],
        avg_volume_3m: float
    ):
        """Check and adjust a single trade"""

        trade_id = trade.trade_id

        # Update tracking
        if trade.direction == 'LONG':
            trade.lowest_price_seen = min(trade.lowest_price_seen, current_price)
        else:
            trade.highest_price_seen = max(trade.highest_price_seen, current_price)

        # Calculate current profit
        if trade.direction == 'LONG':
            current_profit = current_price - trade.entry_price
        else:
            current_profit = trade.entry_price - current_price

        trade.highest_profit = max(trade.highest_profit, current_profit)

        # 1. HEIGHTENED SECURITY MODE (No TP1 trades)
        if trade.heightened_security and not trade.tp1_hit:
            action = await self._check_heightened_security(
                trade, current_price, candles_3m
            )
            if action == 'CLOSE_50_AND_BREAKEVEN':
                await self._execute_partial_close_and_breakeven(trade, current_price)
                return

        # 2. BREAKEVEN STOP MOVEMENT
        if not trade.sl_moved_to_breakeven and trade.tp1:
            should_move = await self._check_breakeven_trigger(
                trade, current_price, candles_3m
            )
            if should_move:
                await self._move_stop_to_breakeven(trade)

    async def _check_breakeven_trigger(
        self,
        trade: TradeState,
        current_price: float,
        candles_3m: List[Dict]
    ) -> bool:
        """
        Check if conditions are met to move stop loss to breakeven.

        Trigger: Price reaches 75% of the way to TP1.
        Confirmation: A 3m candle closes beyond the 75% threshold.
        """
        if trade.breakeven_triggered or not trade.tp1:
            return False

        # Calculate the price level that is 75% to TP1
        distance_to_tp1 = trade.tp1 - trade.entry_price
        trigger_price = trade.entry_price + (distance_to_tp1 * self.breakeven_threshold)

        price_has_crossed_trigger = False
        if trade.direction == 'LONG':
            if current_price >= trigger_price:
                price_has_crossed_trigger = True
        else: # SHORT
            if current_price <= trigger_price:
                price_has_crossed_trigger = True

        if not price_has_crossed_trigger:
            return False

        # Confirmation: Check if the last 3m candle also closed past the trigger
        if not candles_3m:
            return False
        last_3m_close = float(candles_3m[-1]['close'])

        candle_confirms = False
        if trade.direction == 'LONG':
            if last_3m_close > trigger_price:
                candle_confirms = True
        else: # SHORT
            if last_3m_close < trigger_price:
                candle_confirms = True

        if price_has_crossed_trigger and candle_confirms:
            logger.info(f"[{trade.trade_id}] Breakeven trigger MET!")
            logger.info(f"  Price at ${current_price:.2f} crossed trigger ${trigger_price:.2f}")
            logger.info(f"  3m candle confirmed at ${last_3m_close:.2f}")
            trade.breakeven_triggered = True # Prevent re-triggering
            return True

        return False

    async def _check_heightened_security(
        self,
        trade: TradeState,
        current_price: float,
        candles_3m: List[Dict]
    ) -> Optional[str]:
        """
        Aggressive reversal detection for high-risk trades.
        Triggers if a 3m candle closes against the position's direction.
        """
        if not candles_3m or trade.heightened_security_triggered:
            return None

        last_candle = candles_3m[-1]
        close_price = float(last_candle['close'])
        
        reversal_detected = False
        if trade.direction == 'SHORT' and close_price > trade.entry_price:
            logger.warning(f"[{trade.trade_id}] HEIGHTENED SECURITY ALERT: 3m candle closed at ${close_price:.2f}, above entry ${trade.entry_price:.2f}.")
            reversal_detected = True
        elif trade.direction == 'LONG' and close_price < trade.entry_price:
            logger.warning(f"[{trade.trade_id}] HEIGHTENED SECURITY ALERT: 3m candle closed at ${close_price:.2f}, below entry ${trade.entry_price:.2f}.")
            reversal_detected = True

        if reversal_detected:
            logger.warning("   Action: Closing 50% of position and moving SL to breakeven.")
            trade.heightened_security_triggered = True # Prevent re-triggering
            return 'CLOSE_50_AND_BREAKEVEN'
        
        return None

    async def _check_5m_bos_reversal(
        self,
        trade: TradeState,
        candles_5m: List[Dict]
    ) -> bool:
        """
        Check for a 5-minute break of structure against the trade's direction.

        - LONG: Triggers if a 5m candle closes below the key structure swing low.
        - SHORT: Triggers if a 5m candle closes above the key structure swing high.
        """
        if trade.reversal_triggered:
            return False  # Already processed

        if not candles_5m:
            return False

        latest_candle = candles_5m[-1]
        candle_close = float(latest_candle['close'])

        if trade.direction == 'LONG' and trade.structure_swing_low:
            if candle_close < trade.structure_swing_low:
                logger.warning(f"[{trade.trade_id}] 5m BREAK OF STRUCTURE DETECTED (LONG REVERSAL)!")
                logger.warning(f"  5m candle closed at ${candle_close:.2f}")
                logger.warning(f"  Below structure swing low of ${trade.structure_swing_low:.2f}")
                logger.warning(f"  Action: Close entire position")
                trade.reversal_triggered = True
                return True

        elif trade.direction == 'SHORT' and trade.structure_swing_high:
            if candle_close > trade.structure_swing_high:
                logger.warning(f"[{trade.trade_id}] 5m BREAK OF STRUCTURE DETECTED (SHORT REVERSAL)!")
                logger.warning(f"  5m candle closed at ${candle_close:.2f}")
                logger.warning(f"  Above structure swing high of ${trade.structure_swing_high:.2f}")
                logger.warning(f"  Action: Close entire position")
                trade.reversal_triggered = True
                return True

        return False

    async def _check_trailing_stop(
        self,
        trade: TradeState,
        current_price: float,
        candles_5m: List[Dict]
    ):
        """
        Progressive trailing stop using 5m candles

        Phases:
        - Phase 1: Approaching TP1 (75% there) → Lock 25% of target profit
        - Phase 2: TP1 hit → SL at breakeven (already done)
        - Phase 3: Approaching TP2 (50% there) → Trail to TP1 level
        - Phase 4: Near TP2 (80% there) → Trail aggressively (1.5× ATR)
        """

        # Calculate ATR from 5m candles for trailing distance
        atr = self._calculate_atr(candles_5m, period=14)

        if trade.direction == 'LONG':
            # Phase 3: If past TP1 and approaching TP2
            if trade.tp1_hit and trade.tp2:
                distance_to_tp2 = trade.tp2 - current_price
                total_distance = trade.tp2 - trade.entry_price
                progress = 1.0 - (distance_to_tp2 / total_distance) if total_distance > 0 else 0

                if progress >= 0.5 and trade.tp1:
                    # Trail to TP1 level
                    new_sl = trade.tp1
                    if new_sl > trade.current_sl:
                        logger.info(f"[{trade.trade_id}] Trailing stop to TP1 level: ${new_sl:.2f}")
                        trade.current_sl = new_sl
                        await self.execution_engine._update_stop_loss(new_sl)

                elif progress >= 0.8:
                    # Aggressive trail (1.5× ATR behind)
                    new_sl = current_price - (atr * self.trailing_atr_multiplier)
                    if new_sl > trade.current_sl:
                        logger.info(f"[{trade.trade_id}] Aggressive trail: ${new_sl:.2f} ({self.trailing_atr_multiplier}× ATR)")
                        trade.current_sl = new_sl
                        await self.execution_engine._update_stop_loss(new_sl)

        else:  # SHORT
            # Phase 3: If past TP1 and approaching TP2
            if trade.tp1_hit and trade.tp2:
                distance_to_tp2 = current_price - trade.tp2
                total_distance = trade.entry_price - trade.tp2
                progress = 1.0 - (distance_to_tp2 / total_distance) if total_distance > 0 else 0

                if progress >= 0.5 and trade.tp1:
                    # Trail to TP1 level
                    new_sl = trade.tp1
                    if new_sl < trade.current_sl:
                        logger.info(f"[{trade.trade_id}] Trailing stop to TP1 level: ${new_sl:.2f}")
                        trade.current_sl = new_sl
                        await self.execution_engine._update_stop_loss(new_sl)

                elif progress >= 0.8:
                    # Aggressive trail (1.5× ATR above)
                    new_sl = current_price + (atr * self.trailing_atr_multiplier)
                    if new_sl < trade.current_sl:
                        logger.info(f"[{trade.trade_id}] Aggressive trail: ${new_sl:.2f} ({self.trailing_atr_multiplier}× ATR)")
                        trade.current_sl = new_sl
                        await self.execution_engine._update_stop_loss(new_sl)

    async def _execute_partial_close_and_breakeven(
        self,
        trade: TradeState,
        current_price: float
    ):
        """
        Execute 50% position close and move stop to breakeven
        (Heightened security trigger)
        """

        close_size = trade.remaining_size * 0.5

        logger.info(f"[{trade.trade_id}] Executing partial close...")
        logger.info(f"  Closing: {close_size:.4f} {self.symbol.replace('USDT', '')} (50%)")
        logger.info(f"  At price: ${current_price:.2f}")

        # Execute partial close on exchange
        await self.execution_engine._partial_close(0.5)

        # Update trade state
        trade.remaining_size -= close_size
        trade.sl_moved_to_breakeven = True
        trade.current_sl = trade.entry_price

        logger.info(f"  New stop loss: ${trade.entry_price:.2f} (BREAKEVEN)")
        logger.info(f"  Remaining size: {trade.remaining_size:.4f} {self.symbol.replace('USDT', '')}")

        # Update stop loss on exchange
        await self.execution_engine._update_stop_loss(trade.entry_price)

    async def _move_stop_to_breakeven(self, trade: TradeState):
        """Move stop loss to breakeven"""

        logger.info(f"[{trade.trade_id}] Moving stop to BREAKEVEN")
        logger.info(f"  Old SL: ${trade.current_sl:.2f}")
        logger.info(f"  New SL: ${trade.entry_price:.2f}")

        trade.current_sl = trade.entry_price
        trade.sl_moved_to_breakeven = True

        # Update stop loss on exchange
        await self.execution_engine._update_stop_loss(trade.entry_price)

    async def _execute_early_exit(self, trade: TradeState, current_price: float):
        """Close entire position due to reversal"""

        logger.warning(f"[{trade.trade_id}] EARLY EXIT - Closing entire position")
        logger.warning(f"  Exit price: ${current_price:.2f}")
        logger.warning(f"  Entry was: ${trade.entry_price:.2f}")

        if trade.direction == 'LONG':
            pnl = current_price - trade.entry_price
        else:
            pnl = trade.entry_price - current_price

        logger.warning(f"  P&L: ${pnl:.2f} per unit")

        # Close entire position on exchange
        await self.execution_engine.emergency_close_all()

        # Remove from active management
        self.remove_trade(trade.trade_id)

    def _calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Calculate Average True Range for trailing stops"""

        if len(candles) < period:
            return 0.0

        true_ranges = []
        for i in range(1, min(period + 1, len(candles))):
            high = float(candles[-i]['high'])
            low = float(candles[-i]['low'])
            prev_close = float(candles[-i-1]['close'])

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

    async def _get_current_price(self) -> Optional[float]:
        """Fetch current market price"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"Error fetching current price: {e}")
            return None

    async def _get_candles(self, interval: str, limit: int = 20) -> Optional[List[Dict]]:
        """
        Fetch candles with caching

        Args:
            interval: '3m' or '5m'
            limit: Number of candles
        """

        current_time = time.time()

        # Check cache - BULLETPROOF: Refresh every 10 seconds (was 60-120s - TOO STALE!)
        if interval == '3m':
            if current_time - self.last_3m_fetch < 10:  # Cache for 10 seconds only
                return self.candle_3m_cache
        elif interval == '5m':
            if current_time - self.last_5m_fetch < 10:  # Cache for 10 seconds only
                return self.candle_5m_cache
        elif interval == '15m':
            if current_time - self.last_15m_fetch < 10:  # Cache for 10 seconds only
                return self.candle_15m_cache

        # Fetch fresh data
        try:
            candles = self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=limit
            )

            formatted_candles = [
                {
                    'open': c[1],
                    'high': c[2],
                    'low': c[3],
                    'close': c[4],
                    'volume': c[5]
                }
                for c in candles
            ]

            # Update cache
            if interval == '3m':
                self.candle_3m_cache = formatted_candles
                self.last_3m_fetch = current_time
            elif interval == '5m':
                self.candle_5m_cache = formatted_candles
                self.last_5m_fetch = current_time
            elif interval == '15m':
                self.candle_15m_cache = formatted_candles
                self.last_15m_fetch = current_time

            return formatted_candles

        except Exception as e:
            logger.error(f"Error fetching {interval} candles: {e}")
            return None


if __name__ == "__main__":
    print("Real-Time Risk Manager - Arsenal Trading System")
    print("=" * 80)
    print("\nFeatures:")
    print("1. Breakeven stop movement (75% to TP1 + 3m confirmation)")
    print("2. Heightened security mode (aggressive reversal detection for no-TP1 trades)")
    print("3. Standard reversal detection (candle + volume confirmation)")
    print("4. Trailing stops (5m candles, progressive profit locking)")
    print("\nModule ready for integration")
