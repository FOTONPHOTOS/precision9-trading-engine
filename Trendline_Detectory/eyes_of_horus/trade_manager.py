import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
import traceback

from config import GUARDIAN_LOOP_INTERVAL, LEVERAGE_SETTINGS
from database import get_db_session, init_db
from models import ManagedTrade
from exchange_client import BybitClient
from websocket_server import WebSocketServer
from technical_analysis import calculate_rsi, calculate_atr
from filters import KalmanFilter
from horus_liquidity_analyzer import ArsenalLiquidityAnalyzer
from dashboard_client import Emitter

logger = logging.getLogger(__name__)

class TradeManager:
    """The central nervous system of Project Aegis.
    It orchestrates receiving signals, executing trades, and managing them with a
    dynamic, thesis-driven, multi-factor analysis engine.
    """

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.is_running = False
        self.bybit_client = BybitClient()
        self.websocket_server = WebSocketServer(host, port, self.handle_new_signal)
        self.managed_sessions: Dict[str, Dict[str, Any]] = {}
        self.symbol_cooldowns: Dict[str, datetime] = {}
        self.pending_limit_orders: Dict[str, Dict[str, Any]] = {}
        self.pending_orders_lock = asyncio.Lock()
        self.symbol_allocated_balance: Dict[str, float] = {}
        self.max_concurrent_symbols = 3 # User-defined for testing
        self.initial_total_balance = 0.0 # Store initial balance for fixed allocation

        # Dashboard Emitter
        self.emitter = Emitter("aegis", "trade_manager")

        # --- Adaptive Risk Management State ---
        self.state_file = "aegis_state.json"
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self.regime_filter_until: Optional[datetime] = None
        self.hyper_conservative_mode = False
        self.regime_filter_active_losses = 0
        # --- End Adaptive Risk Management State ---

        logger.info("Aegis Trade Manager initialized.")

    def _initialize_trade_session(self, trade: ManagedTrade):
        """Creates a new management session for a trade, including its Kalman Filter."""
        # Check if we need to merge the trade object into the current session context
        # This creates a new instance tied to the current session
        session_bound_trade = trade
        
        # If trade has a session, we need to detach and reattach it properly
        # This is a simplified approach to ensure the trade object is session-safe
        if trade.id and hasattr(trade, 'trade_id'):
            trade_id = trade.trade_id
            
        if trade_id in self.managed_sessions:
            logger.warning(f"[{trade_id}] Tried to initialize a session that already exists.")
            return

        logger.info(f"[{trade_id}] Initializing management session.")
        self.managed_sessions[trade_id] = {
            'trade': session_bound_trade,  # Use the potentially reattached object
            'trade_id_key': trade_id,  # Store the trade_id as a separate key to avoid detached instance issues
            'kf_price': KalmanFilter(process_variance=1e-5, measurement_variance=0.01, initial_value=session_bound_trade.entry_price),
            'kf_rsi': KalmanFilter(process_variance=1e-2, measurement_variance=0.1, initial_value=50),
            'kf_orderflow_ratio': KalmanFilter(process_variance=1e-2, measurement_variance=0.1, initial_value=1.0),
            'liquidity_analyzer': ArsenalLiquidityAnalyzer(self.bybit_client, session_bound_trade.symbol),
            'orderflow_violation_count': 0,
            'last_analysis': {},
            'price_deviation_from_entry': 0.0,
            'last_price': session_bound_trade.entry_price,
            'consolidation_detected': False,
            'consolidation_start_price': session_bound_trade.entry_price,
            'violation_without_price_confirmation': 0,
            'last_violation_decay': time.time(),
            'last_applied_penalty_level': 0,
            'last_minor_penalty_level': 0,
        }

    async def initialize(self):
        """Initializes all components: DB, Bybit client, and recovers active trades."""
        logger.info("Initializing Trade Manager components...")
        init_db()
        await self.bybit_client.initialize()

        # --- Set Leverage ---
        if LEVERAGE_SETTINGS:
            logger.info("Setting leverage for all symbols from config...")
            for symbol, leverage in LEVERAGE_SETTINGS.items():
                await self.bybit_client.set_leverage(symbol, leverage)
        else:
            logger.warning("No leverage settings found in config. Skipping leverage setup.")
        
        # Fetch total available balance once on startup
        current_total_available_balance = await self.bybit_client.get_available_balance()
        if current_total_available_balance < 1:
            logger.critical("Aegis started with near-zero available balance (< $1). Trading will be disabled until balance is updated.")
            self.is_running = True # Allow it to run, but it won't trade
        self.initial_total_balance = current_total_available_balance
        logger.info(f"Initial total available balance for Aegis: ${self.initial_total_balance:.2f}")

        # Load adaptive risk state from file
        self._load_state()

        # Call the new, robust reconciliation function
        await self._reconcile_positions()

        # Initialize recent signals tracking to prevent duplicate processing
        self.recent_signals = {}

        logger.info("Aegis initialization complete.")

    def _save_state(self):
        """Saves the adaptive risk management state to a JSON file."""
        state = {
            "consecutive_losses": self.consecutive_losses,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "regime_filter_until": self.regime_filter_until.isoformat() if self.regime_filter_until else None,
            "hyper_conservative_mode": self.hyper_conservative_mode,
            "regime_filter_active_losses": self.regime_filter_active_losses,
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=4)
            logger.info(f"Saved Aegis state to {self.state_file}")
            # Emit risk state update to dashboard
            asyncio.create_task(self.emitter.emit("risk_state_update", state))
        except IOError as e:
            logger.error(f"Failed to save Aegis state: {e}")

    def _load_state(self):
        """Loads the adaptive risk management state from a JSON file."""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.consecutive_losses = state.get("consecutive_losses", 0)
            cooldown_str = state.get("cooldown_until")
            self.cooldown_until = datetime.fromisoformat(cooldown_str) if cooldown_str else None
            filter_str = state.get("regime_filter_until")
            self.regime_filter_until = datetime.fromisoformat(filter_str) if filter_str else None
            self.hyper_conservative_mode = state.get("hyper_conservative_mode", False)
            self.regime_filter_active_losses = state.get("regime_filter_active_losses", 0)
            
            logger.info(f"Loaded Aegis state from {self.state_file}")
            # Log the loaded state for verification
            if self.cooldown_until and self.cooldown_until > datetime.now():
                 logger.info(f"  - Cooldown is active until: {self.cooldown_until}")
            if self.regime_filter_until and self.regime_filter_until > datetime.now():
                 logger.info(f"  - Regime filter is active until: {self.regime_filter_until}")

        except FileNotFoundError:
            logger.info(f"Aegis state file ({self.state_file}) not found. Starting with a fresh state.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load or parse Aegis state file: {e}. Starting with a fresh state.")

    async def _reconcile_positions(self):
        """
        The master reconciliation function called on startup.
        1. Fetches all open positions from the exchange.
        2. Fetches all 'active' trades from the local DB.
        3. Reconciles trades that were closed while Aegis was offline by checking exchange PnL history.
        4. Initializes sessions for trades that are confirmed to be still active.
        5. Discovers and imports any open positions on the exchange that Aegis was not tracking.
        """
        logger.info("--- Starting Position Reconciliation ---")
        try:
            with get_db_session() as db:
                exchange_positions = await self.bybit_client.get_all_open_positions()
                exchange_symbols = {p['symbol'] for p in exchange_positions}
                
                db_active_trades = db.query(ManagedTrade).filter(ManagedTrade.status == 'active').all()
                db_active_symbols = {t.symbol for t in db_active_trades}

                # Step 1: Reconcile trades that were active in our DB
                for trade in db_active_trades:
                    if trade.symbol not in exchange_symbols:
                        # This trade was closed while Aegis was offline. Find its real PnL.
                        logger.warning(f"[{trade.trade_id}] Position for {trade.symbol} was active in DB but is now closed. Reconciling with trade history...")
                        
                        history = await self.bybit_client.get_closed_pnl_history(symbol=trade.symbol, limit=20)
                        found_match = False
                        if history:
                            for closed_trade in history:
                                # Match by comparing entry timestamps. Bybit uses ms timestamps.
                                entry_time_diff_ms = abs(trade.entry_timestamp - int(closed_trade['createdTime']))
                                # If trades are within 2 minutes of each other, consider it a match.
                                if entry_time_diff_ms < timedelta(minutes=2).total_seconds() * 1000:
                                    logger.info(f"[{trade.trade_id}] Found match in closed PnL history! Updating with REAL data.")
                                    trade.status = 'closed'
                                    trade.exit_price = float(closed_trade['avgExitPrice'])
                                    trade.pnl = float(closed_trade['closedPnl'])
                                    trade.exit_timestamp = int(closed_trade['updatedTime'])
                                    trade.exit_reason = "RECONCILED_OFFLINE_CLOSE"
                                    found_match = True
                                    # We don't want to manage this trade anymore, so we don't initialize a session.
                                    break 
                        
                        if not found_match:
                            # Fallback if we can't find it in recent history
                            logger.error(f"[{trade.trade_id}] Could not find match in PnL history for {trade.symbol}. Closing with estimated PnL.")
                            # Use the existing _close_trade_in_db, but it needs a session.
                            # We can directly manipulate the object and commit at the end.
                            trade.status = 'closed'
                            trade.exit_reason = 'OFFLINE_CLOSE_UNCONFIRMED'
                            trade.exit_price = trade.current_stop_loss # Best guess
                            # Recalculate PNL based on this guess
                            if trade.direction == 'LONG':
                                trade.pnl = (trade.exit_price - trade.entry_price) * trade.qty
                            else:
                                trade.pnl = (trade.entry_price - trade.exit_price) * trade.qty
                            trade.pnl_percent = (trade.pnl / (trade.entry_price * trade.qty)) * 100 if trade.entry_price > 0 and trade.qty > 0 else 0

                    else:
                        # The trade is confirmed to be active on both DB and exchange, initialize a session for it.
                        logger.info(f"[{trade.trade_id}] Position for {trade.symbol} confirmed active. Initializing management session.")
                        self._initialize_trade_session(trade)

                # Step 2: Discover and import any unmanaged open positions
                unmanaged_symbols = exchange_symbols - db_active_symbols
                for symbol in unmanaged_symbols:
                    position_data = next((p for p in exchange_positions if p['symbol'] == symbol), None)
                    if position_data:
                        logger.info(f"[DISCOVERY] Found unmanaged open position for {symbol}. Importing now.")
                        await self._create_recovered_trade_record(position_data, db_session=db)

                db.commit()
                logger.info(f"--- Reconciliation Complete. {len(self.managed_sessions)} trades are now under active management. ---")
                
                # Emit a snapshot of all actively managed trades
                active_trades_for_dashboard = []
                for session_id, session in self.managed_sessions.items():
                    trade = session['trade'] # This should be the ManagedTrade object
                    active_trades_for_dashboard.append({
                        "trade_id": trade.trade_id,
                        "symbol": trade.symbol,
                        "direction": trade.direction,
                        "entry_price": trade.entry_price,
                        "qty": trade.qty,
                        "take_profit": trade.take_profit,
                        "stop_loss": trade.current_stop_loss,
                        "created_at": trade.created_at
                    })
                await self.emitter.emit("active_trades_snapshot", {"trades": active_trades_for_dashboard})

        except Exception as e:
            logger.error(f"CRITICAL ERROR during position reconciliation: {e}", exc_info=True)

    async def _create_recovered_trade_record(self, position_data: dict, db_session: Optional[Session] = None):
        """Creates a new ManagedTrade in the DB from an existing exchange position."""
        
        def operation(db: Session):
            trade_id = f"rec_{int(time.time() * 1000)}"
            symbol = position_data['symbol']
            direction = "LONG" if position_data['side'] == "Buy" else "SHORT"
            
            entry_price = float(position_data['avgPrice'])
            risk_per_unit = entry_price * 0.01
            original_stop_loss = entry_price - risk_per_unit if direction == "LONG" else entry_price + risk_per_unit
            original_take_profit = entry_price + (risk_per_unit * 1.5) if direction == "LONG" else entry_price - (risk_per_unit * 1.5)

            nudge_factor = 0.003
            nudge_amount = entry_price * nudge_factor
            nudged_sl, nudged_tp = (original_stop_loss - nudge_amount, original_take_profit - nudge_amount) if direction == 'LONG' else (original_stop_loss + nudge_amount, original_take_profit + nudge_amount)

            logger.info(f"[{trade_id}] Applying 0.3% Aegis nudge to recovered trade. Nudged SL: {nudged_sl:.4f}, Nudged TP: {nudged_tp:.4f}")

            # Defensively handle TP/SL, as they can be empty strings for manual trades
            tp_from_exchange = position_data.get('takeProfit')
            sl_from_exchange = position_data.get('stopLoss')

            take_profit = float(tp_from_exchange) if tp_from_exchange else nudged_tp
            current_stop_loss = float(sl_from_exchange) if sl_from_exchange else nudged_sl

            new_trade = ManagedTrade(
                trade_id=trade_id, symbol=symbol, status='active', direction=direction, entry_price=entry_price,
                qty=float(position_data['size']), initial_stop_loss=nudged_sl,
                current_stop_loss=current_stop_loss,
                take_profit=take_profit,
                entry_reasoning={"recovered_by": "Aegis"}, sl_moved_to_breakeven=False, swing_highs=[], swing_lows=[]
            )
            db.add(new_trade)
            db.commit()
            db.refresh(new_trade)
            
            # Detach and re-attach to fresh session for _initialize_trade_session
            new_trade_id = new_trade.trade_id
            db.expunge(new_trade)  # Remove from current session
            del new_trade  # Remove reference to detached object
            
            # Now re-fetch the trade to bind it to a fresh session for _initialize_trade_session
            fresh_trade = db.query(ManagedTrade).filter(ManagedTrade.trade_id == new_trade_id).first()
            if fresh_trade:
                self._initialize_trade_session(fresh_trade)
                logger.info(f"[{fresh_trade.trade_id}] Successfully recovered and created DB record for existing {symbol} position.")
            else:
                logger.error(f"[{new_trade_id}] Could not re-fetch trade after creation, cannot initialize management session.")

        if db_session:
            operation(db_session)
        else:
            with get_db_session() as db:
                operation(db)

    # --- Adaptive Risk Management Core Logic ---

    async def _run_regime_filter(self, symbol: str) -> str:
        """
        Analyzes market regime for a symbol to decide if a trade is safe.
        Returns "approve", "reduce", or "block".
        """
        try:
            klines = await self.bybit_client.get_klines(symbol, '5', 51) # 51 to have 50 periods
            if not klines or len(klines) < 50:
                logger.warning(f"[REGIME FILTER] Not enough kline data for {symbol} to analyze regime. Approving trade as a fallback.")
                return "approve"

            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)

            # 1. ATR Trend for Volatility
            tr1 = pd.DataFrame(df['high'] - df['low'])
            tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift()))
            tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift()))
            tr = pd.concat([tr1, tr2, tr3], axis=1, join='inner').max(axis=1)
            atr = tr.ewm(alpha=1/14, adjust=False).mean()
            df['atr'] = atr
            
            latest_atr = df['atr'].iloc[-1]
            median_atr = df['atr'].iloc[-50:-1].median()

            # 2. Directional Bias
            ma_short = df['close'].rolling(window=10).mean().iloc[-1]
            ma_long = df['close'].rolling(window=30).mean().iloc[-1]
            bias_aligned = ma_short > ma_long

            # 3. Decision Logic
            is_ranging = latest_atr < median_atr * 0.8

            logger.info(f"[REGIME FILTER] Analysis for {symbol}: ATR Ratio: {latest_atr/median_atr:.2f}, Bias Aligned: {bias_aligned}")

            if is_ranging:
                logger.warning(f"[REGIME FILTER] Decision for {symbol}: BLOCK (Market is ranging/compressing)")
                return "block"
            
            if bias_aligned:
                logger.info(f"[REGIME FILTER] Decision for {symbol}: APPROVE (Volatility and trend are aligned)")
                return "approve"
            else:
                logger.warning(f"[REGIME FILTER] Decision for {symbol}: REDUCE (Volatility is present, but trend bias is not aligned)")
                return "reduce"

        except Exception as e:
            logger.error(f"[REGIME FILTER] Error during analysis for {symbol}: {e}. Approving trade as a fallback.", exc_info=True)
            return "approve"

    def _activate_cooldown(self):
        """Activates the 1-hour trading cooldown."""
        self.cooldown_until = datetime.now() + timedelta(hours=1)
        self.consecutive_losses = 0  # Reset counter after activating
        self.regime_filter_active_losses = 0 # Also reset this
        logger.critical(f"[RISK MANAGER] 5 consecutive losses detected. Cooldown activated for 1 hour.")
        self._save_state()

    def _activate_regime_filter(self):
        """Activates the 3-hour regime filter."""
        self.regime_filter_until = datetime.now() + timedelta(hours=3)
        self.cooldown_until = None # Cooldown is over
        self.hyper_conservative_mode = False # Ensure this is reset
        logger.critical("[RISK MANAGER] Cooldown expired. Regime filter activated for 3 hours.")
        self._save_state()

    async def _can_trade(self, symbol: str) -> str:
        """
        Checks the current risk state to determine if a trade can proceed.
        Returns "approve", "reduce", or "block".
        """
        now = datetime.now()

        # 1. Check for active cooldown
        if self.cooldown_until and now < self.cooldown_until:
            remaining = (self.cooldown_until - now).total_seconds() / 60
            logger.warning(f"[RISK MANAGER] Trade blocked for {symbol}: Cooldown active for another {remaining:.1f} minutes.")
            return "block"

        # 2. Check if cooldown has just expired to activate the regime filter
        if self.cooldown_until and now >= self.cooldown_until:
            self._activate_regime_filter()
            # Block the current trade to allow the filter to be active for the *next* one
            logger.warning(f"[RISK MANAGER] Trade blocked for {symbol}: Cooldown just ended, activating regime filter. Next trade will be filtered.")
            return "block"

        # 3. Check for active regime filter
        if self.regime_filter_until and now < self.regime_filter_until:
            remaining = (self.regime_filter_until - now).total_seconds() / 60
            logger.info(f"[RISK MANAGER] Regime filter is active for another {remaining:.1f} minutes.")

            if self.hyper_conservative_mode:
                logger.warning(f"[RISK MANAGER] Trade blocked for {symbol}: Hyper-conservative mode is active.")
                return "block"
            
            # Run the filter logic
            return await self._run_regime_filter(symbol)

        # 4. Check if regime filter has expired
        if self.regime_filter_until and now >= self.regime_filter_until:
            logger.info("[RISK MANAGER] Regime filter has expired. Returning to normal trading.")
            self.regime_filter_until = None
            self.hyper_conservative_mode = False
            self.regime_filter_active_losses = 0
            self._save_state()

        # 5. If no special conditions, approve trade
        return "approve"

    async def handle_new_signal(self, signal_data: dict):
        """Callback for the WebSocket server to process a new limit order signal."""
        symbol = signal_data.get('symbol', 'SOLUSDT')
        trade_id = f"pending_{int(time.time() * 1000)}"

        # --- ADAPTIVE RISK MANAGER CHECK ---
        trade_decision = await self._can_trade(symbol)
        if trade_decision == "block":
            logger.critical(f"[{trade_id}] Trade for {symbol} BLOCKED by adaptive risk manager.")
            await self.emitter.emit("signal_rejected", {"symbol": symbol, "reason": "Blocked by risk manager"})
            return
        
        logger.info(f"[{trade_id}] Adaptive risk manager decision for {symbol}: {trade_decision.upper()}")
        await self.emitter.emit("signal_received", {"symbol": symbol, "decision": trade_decision, "trade_id": trade_id})

        # Initialize recent signals tracking if not already
        if not hasattr(self, 'recent_signals'):
            self.recent_signals = {}  # Dictionary to store timestamp with signal fingerprint

        # Create a signal fingerprint to detect duplicates
        signal_fingerprint = f"{symbol}_{decision.get('direction', '')}_{decision.get('entry_zone', [0])[0] if decision.get('entry_zone') else 0}"

        # Current time to track when this signal was received
        current_time = time.time()

        # Clean up signals older than 2 minutes
        expired_signals = []
        for fingerprint, timestamp in self.recent_signals.items():
            if current_time - timestamp > 120:  # 2 minutes in seconds
                expired_signals.append(fingerprint)
        for fingerprint in expired_signals:
            del self.recent_signals[fingerprint]

        # Check if this exact signal was recently processed (within 2 minutes)
        if signal_fingerprint in self.recent_signals:
            logger.warning(f"[{trade_id}] Duplicate signal detected for {signal_fingerprint} (received at {datetime.fromtimestamp(self.recent_signals[signal_fingerprint]).strftime('%H:%M:%S')}). Ignoring signal.")
            return

        # Add to recent signals with timestamp
        self.recent_signals[signal_fingerprint] = current_time

        # --- PRE-TRADE LEVERAGE VERIFICATION ---
        try:
            desired_leverage = LEVERAGE_SETTINGS.get(symbol)
            if not desired_leverage:
                logger.error(f"[{trade_id}] Leverage for {symbol} not found in config. Blocking trade.")
                return

            # Enforce 5x hard cap
            if desired_leverage > 5:
                logger.warning(f"[{trade_id}] Desired leverage {desired_leverage}x for {symbol} exceeds hard cap of 5x. Clamping to 5x.")
                desired_leverage = 5

            current_leverage = await self.bybit_client.get_leverage(symbol)

            if current_leverage is None:
                logger.error(f"[{trade_id}] Could not verify current leverage for {symbol}. Blocking trade.")
                return

            if int(current_leverage) != desired_leverage:
                logger.warning(f"[{trade_id}] Leverage mismatch for {symbol}. Current: {current_leverage}x, Desired: {desired_leverage}x. Attempting to correct...")
                success = await self.bybit_client.set_leverage(symbol, desired_leverage)
                if not success:
                    logger.critical(f"[{trade_id}] FAILED to set correct leverage for {symbol}. TRADE BLOCKED.")
                    return
                logger.info(f"[{trade_id}] Successfully corrected leverage for {symbol} to {desired_leverage}x.")

        except Exception as e:
            logger.error(f"[{trade_id}] An unexpected error occurred during pre-trade leverage check: {e}. Blocking trade.")
            return
        # --- END LEVERAGE VERIFICATION ---


        # --- CHECK FOR EXISTING ACTIVE POSITION FOR THIS SYMBOL ---
        # First check managed sessions
        with get_db_session() as temp_db:
            for session in self.managed_sessions.values():
                # Use the stored trade_id to avoid detached instance issues
                original_trade_id = session.get('trade_id_key')
                if not original_trade_id:
                    logger.warning(f"Could not access trade_id from session: trade_id_key not found")
                    continue

                # Re-fetch the trade from the current session to ensure it's properly attached
                trade_from_db = temp_db.query(ManagedTrade).filter(ManagedTrade.trade_id == original_trade_id).first()
                if trade_from_db and trade_from_db.symbol == symbol and trade_from_db.status == 'active':
                    logger.warning(f"[{trade_id}] Received signal for {symbol}, but a position is already active in managed sessions. Ignoring signal.")
                    return

        # Double-check with exchange to catch any positions not yet in managed sessions
        exchange_positions = await self.bybit_client.get_all_open_positions()
        for pos in exchange_positions:
            if pos['symbol'] == symbol and float(pos['size']) > 0:
                logger.warning(f"[{trade_id}] Position for {symbol} is active on exchange. Ignoring signal.")
                return

        # --- TIME VALIDATION CHECK ---
        # Verify that the signal is coming at an appropriate time (divisible by 5 minutes)
        current_time = datetime.now()
        minute = current_time.minute
        if minute % 5 != 0:
            logger.warning(f"[{trade_id}] Signal received at {current_time.strftime('%H:%M:%S')}, which is not on a 5-minute boundary. This may indicate an unexpected execution.")

        try:
            decision = signal_data.get('decision', {})
            logger.info(f"[{trade_id}] Processing new LIMIT order signal for: {decision.get('direction')} {symbol}")
            logger.debug(f"[{trade_id}] Full decision received: {decision}") # NEW LOGGING

            # The entry price for a sniper entry is a single price, not a zone.
            limit_price = decision['entry_zone'][0]

            # Count currently active managed sessions to determine allocation
            with get_db_session() as db:
                active_managed_sessions = {}
                for sid, s in self.managed_sessions.items():
                    original_trade_id = s.get('trade_id_key')
                    if not original_trade_id:
                        logger.warning(f"Could not access trade_id from session {sid}: trade_id_key not found")
                        continue
                    db_trade = db.query(ManagedTrade).filter(ManagedTrade.trade_id == original_trade_id).first()
                    if db_trade and db_trade.status == 'active':
                        active_managed_sessions[sid] = s
                active_symbols_count = len(active_managed_sessions)

            # --- REVISED DYNAMIC BALANCE ALLOCATION LOGIC ---
            # Get current available balance (free collateral)
            current_free_balance = await self.bybit_client.get_available_balance()
            if current_free_balance <= 1.0: # Check for a minimum of $1
                logger.error(f"[{trade_id}] Insufficient free balance to allocate. Current free balance: ${current_free_balance:.2f}. Aborting trade.")
                return

            # Calculate the number of remaining open slots for new trades
            remaining_slots = self.max_concurrent_symbols - active_symbols_count
            
            if remaining_slots <= 0:
                logger.warning(f"[{trade_id}] Max concurrent symbols ({self.max_concurrent_symbols}) reached. Cannot allocate balance for {symbol}. Aborting trade.")
                return
            
            # Allocate an equal share of the *free* balance to the new trade.
            # Use 90% of the share to leave a small buffer.
            allocated_balance_for_symbol = (current_free_balance / remaining_slots) * 0.90
            
            # --- APPLY ADAPTIVE RISK DECISION ---
            if trade_decision == "reduce":
                allocated_balance_for_symbol /= 2
                logger.critical(f"[{trade_id}] REDUCING allocation by 50% due to regime filter. New allocation: ${allocated_balance_for_symbol:.2f}")

            logger.info(f"[{trade_id}] Dynamic allocation: Current free balance=${current_free_balance:.2f}, "
                       f"Active symbols={active_symbols_count}/{self.max_concurrent_symbols}, "
                       f"Remaining slots={remaining_slots}, "
                       f"Allocating=${allocated_balance_for_symbol:.2f} to {symbol}")
            
            if allocated_balance_for_symbol <= 0:
                logger.error(f"[{trade_id}] Calculated allocated balance for {symbol} is zero or negative. Aborting trade.")
                return

            # Calculate quantity based on allocated balance
            qty_str = await self.bybit_client._calculate_and_validate_qty(symbol, limit_price, allocated_balance=allocated_balance_for_symbol)
            if qty_str == "0.0":
                logger.error(f"[{trade_id}] Calculated quantity is zero or too small for allocated balance. Aborting limit order.")
                return

            # Place the limit order with SL/TP
            order_result = await self.bybit_client.place_order(
                symbol=symbol,
                direction=decision['direction'],
                qty=qty_str,
                order_type="Limit",
                price=limit_price,
                stop_loss=decision['stop_loss'],
                take_profit=decision['take_profits'][0]
            )

            if not order_result or order_result.get('retCode') != 0:
                logger.error(f"[{trade_id}] Failed to place limit order: {order_result.get('retMsg')}")
                return

            order_id = order_result['result']['orderId']
            logger.info(f"[SUCCESS] [{trade_id}] Limit order {order_id} placed for {qty_str} {symbol} at ${limit_price:.2f}. Waiting for fill...")

            # Add to pending orders list for OCO management
            async with self.pending_orders_lock:
                self.pending_limit_orders[order_id] = {
                    "orderId": order_id,
                    "symbol": symbol,
                    "signal_decision": decision,
                    "timestamp": datetime.now()
                }
            logger.info(f"Added {order_id} to OCO watch list. Total pending: {len(self.pending_limit_orders)}")

        except Exception as e:
            logger.error(f"Error handling new signal: {e}", exc_info=True)

    async def _calculate_position_size(self, symbol: str, multiplier: float, direction: str) -> float:
        """Calculate the position size based on account balance and multiplier."""
        try:
            # Get the current price of the symbol
            klines = await self.bybit_client.get_klines(symbol, '1', 1)  # Get latest 1m kline
            if not klines or len(klines) == 0:
                logger.warning(f"Could not get price for {symbol}, using default quantity")
                return 1.0  # Default fallback

            current_price = float(klines[-1][4])  # Get close price from kline
            
            # Try to get account balance information using the same method as the working execution engine
            try:
                response = await self.bybit_client._send_request(
                    "GET", 
                    "/v5/account/wallet-balance", 
                    {"accountType": "UNIFIED"}
                )
                
                if response.get('retCode') == 0:
                    result = response.get('result', {})
                    wallet_list = result.get('list', [])
                    
                    if not wallet_list:
                        logger.warning("No wallet data returned from API")
                        raise ValueError("Could not determine account balance.")
                    
                    wallet = wallet_list[0]
                    
                    # First try to get USDT balance from coin array
                    coins = wallet.get('coin', [])
                    usdt_balance = None
                    
                    for coin in coins:
                        if coin.get('coin') == 'USDT':
                            # Try multiple fields for available balance
                            available_str = str(coin.get('availableToWithdraw', '0'))
                            wallet_balance_str = str(coin.get('walletBalance', '0'))
                            equity_str = str(coin.get('equity', '0'))
                            
                            # Convert to float safely
                            try:
                                available_float = float(available_str) if available_str and available_str != '0' else 0.0
                                wallet_float = float(wallet_balance_str) if wallet_balance_str and wallet_balance_str != '0' else 0.0
                                equity_float = float(equity_str) if equity_str and equity_str != '0' else 0.0
                                
                                # Use the highest non-zero value as available balance
                                if available_float > 0:
                                    usdt_balance = available_float
                                elif wallet_float > 0:
                                    usdt_balance = wallet_float
                                elif equity_float > 0:
                                    usdt_balance = equity_float
                                else:
                                    usdt_balance = 0.0
                                    
                                break
                            except (ValueError, TypeError) as e:
                                logger.error(f"Error parsing USDT balance: {e}")
                                continue
                                
                    # If USDT not found in coins, use total wallet balance
                    if usdt_balance is None or usdt_balance == 0:
                        total_available_str = str(wallet.get('totalAvailableBalance', '0'))
                        total_equity_str = str(wallet.get('totalEquity', '0'))
                        
                        try:
                            total_available_float = float(total_available_str) if total_available_str and total_available_str != '0' else 0.0
                            total_equity_float = float(total_equity_str) if total_equity_str and total_equity_str != '0' else 0.0
                            
                            # Use the highest non-zero value
                            if total_available_float > 0:
                                usdt_balance = total_available_float
                            elif total_equity_float > 0:
                                usdt_balance = total_equity_float
                            else:
                                usdt_balance = 0.0
                        except (ValueError, TypeError) as e:
                            logger.error(f"Error parsing total balance: {e}")
                            usdt_balance = 0.0
                    
                    if usdt_balance > 0:
                        # Use 90% of available balance with leverage (as per user's request)
                        balance_to_use = usdt_balance
                        position_percent = 90.0  # Use 90% as per user's request
                        
                        leverage = await self.bybit_client.get_leverage(symbol)
                        if leverage is None:
                            logger.warning(f"Could not fetch leverage for {symbol}. Defaulting to 2x.")
                            leverage = 2.0 # Default to 2x as per user's current setting
                        
                        risk_amount = balance_to_use * (position_percent / 100) * leverage
                        position_size = risk_amount / current_price
                        
                        # Apply the multiplier from the signal (this would represent the risk adjustment)
                        final_position_size = position_size * multiplier
                        
                        logger.info(f"[CALCULATE_SIZE] Balance: ${balance_to_use:.2f}, Leverage: {leverage}x, Risk amount: ${risk_amount:.2f}, Base size: {position_size:.4f}, Multiplier: {multiplier}, Final: {final_position_size:.4f}")
                        
                        # Ensure minimum order size per exchange requirements (Bybit minimum ~$5 worth)
                        min_order_value = 5.0
                        min_quantity = min_order_value / current_price
                        
                        # Ensure we meet minimum quantity requirements
                        final_position_size = max(final_position_size, min_quantity)
                        
                        return round(final_position_size, 4)  # Round to 4 decimal places for precision
                    else:
                        # Balance is 0, use fallback
                        logger.warning(f"Available balance is zero (${usdt_balance}). Using fallback calculation.")
                        raise ValueError("Could not determine account balance.")
                else:
                    error_msg = response.get('retMsg', 'Unknown error')
                    logger.warning(f"Could not fetch account balance: {error_msg}. Using fallback calculation.")
                    raise ValueError("Could not determine account balance.")
            except Exception as balance_error:
                logger.warning(f"Error fetching account balance: {balance_error}. Using fallback calculation.")
                raise ValueError("Could not determine account balance.")
                
        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise ValueError(f"Could not calculate position size for {symbol}")

    async def guardian_loop(self):
        """The main Aegis analysis loop that runs periodically to manage all trades and monitor the market."""
        logger.info("Aegis guardian loop started. Beginning real-time trade management and market analysis.")
        from config import GUARDIAN_LOOP_INTERVAL
        import traceback

        balance_emit_counter = 0
        BALANCE_EMIT_INTERVAL = 5 # Emit balance every 5 loops

        while self.is_running:
            try:
                # --- Active Trade Management & Discovery ---
                exchange_positions = await self.bybit_client.get_all_open_positions()
                exchange_symbols = {p['symbol'] for p in exchange_positions}

                with get_db_session() as db:
                    # Discover and import any new, unmanaged trades
                    # Access managed symbols from the database to avoid detached instance errors
                    # Get the trade IDs safely first
                    managed_trade_ids = []
                    for session_id, session in self.managed_sessions.items():
                        # Use the stored trade_id to avoid detached instance issues
                        original_trade_id = session.get('trade_id_key')
                        if original_trade_id:
                            managed_trade_ids.append(original_trade_id)
                        else:
                            logger.warning(f"Could not access trade_id for session {session_id}: trade_id_key not found")
                            continue
                            
                    if managed_trade_ids:
                        # Query for the latest symbol information from the db
                        managed_trades_from_db = db.query(ManagedTrade.trade_id, ManagedTrade.symbol).filter(ManagedTrade.trade_id.in_(managed_trade_ids)).all()
                        managed_symbols = {trade.symbol for trade in managed_trades_from_db}
                    else:
                        managed_symbols = set()
                    newly_discovered_symbols = exchange_symbols - managed_symbols
                    
                    if newly_discovered_symbols:
                        for symbol in newly_discovered_symbols:
                            position_data = next((p for p in exchange_positions if p['symbol'] == symbol), None)
                            if position_data:
                                logger.info(f"[DISCOVERY] Found new unmanaged position for {symbol}. Importing now.")
                                await self._create_recovered_trade_record(position_data, db_session=db)

                    # Manage all active, synced trades
                    # Use trade IDs to avoid accessing detached objects directly
                    active_trade_data = []
                    for session_id, session in self.managed_sessions.items():
                        # Use the stored trade_id to avoid detached instance issues
                        original_trade_id = session.get('trade_id_key')
                        if not original_trade_id:
                            logger.warning(f"Could not access trade_id from session {session_id}: trade_id_key not found")
                            continue
                            
                        # Re-fetch the trade from the current session to ensure it's properly attached
                        trade_from_db = db.query(ManagedTrade).filter(ManagedTrade.trade_id == original_trade_id).first()
                        if not trade_from_db:
                            logger.warning(f"[{original_trade_id}] Trade not found in current session, skipping management.")
                            continue
                        trade_id = trade_from_db.trade_id
                        trade_symbol = trade_from_db.symbol
                        if trade_symbol in exchange_symbols:
                            active_trade_data.append((session_id, session, trade_id, trade_from_db))

                    for session_id, session, trade_id, trade_from_db in active_trade_data:
                        # Update the session with the properly attached trade object to prevent detached instance errors
                        session['trade'] = trade_from_db
                        # Use the already fetched trade_from_db which is properly attached to the session
                        if not trade_from_db:
                            logger.warning(f"[{trade_id}] Trade not found in current session, skipping management.")
                            continue
                            
                        position_data = next((p for p in exchange_positions if p['symbol'] == trade_from_db.symbol), None)
                        if not position_data:
                            continue

                        current_price = float(position_data['markPrice'])
                        self._update_mae_mfe(trade_from_db, current_price)
                        smoothed_price = session['kf_price'].update(current_price)
                        
                        # Update session with price information for consolidation tracking
                        session['last_price'] = current_price
                        session['price_deviation_from_entry'] = abs(current_price - trade_from_db.entry_price) / trade_from_db.entry_price
                        
                        # Initialize previous prices array if not exists
                        if 'previous_prices' not in session:
                            session['previous_prices'] = []
                        
                        # Add current price to the rolling window
                        session['previous_prices'].append(current_price)
                        if len(session['previous_prices']) > 12:  # Keep last 12 price samples (60 seconds with 5s intervals)
                            session['previous_prices'] = session['previous_prices'][-12:]
                        
                        # Detect consolidation based on price range vs movement
                        if len(session['previous_prices']) >= 6:
                            price_range = max(session['previous_prices']) - min(session['previous_prices'])
                            avg_price = sum(session['previous_prices']) / len(session['previous_prices'])
                            volatility_pct = price_range / avg_price if avg_price > 0 else 0
                            
                            # If volatility is low, we might be in consolidation
                            if volatility_pct < 0.0015:  # Less than 0.15% volatility in recent prices
                                session['consolidation_detected'] = True
                                if session['consolidation_start_price'] == trade_from_db.entry_price:  # First time detecting consolidation
                                    session['consolidation_start_price'] = current_price
                                # Log consolidation detection for debugging
                                reasons_to_log = [f"Consolidation detected: range ${price_range:.4f}, volatility {volatility_pct*100:.3f}%"]
                                for reason in reasons_to_log:
                                    logger.debug(f"[{trade_from_db.trade_id}] {reason}")
                            else:
                                session['consolidation_detected'] = False
                                if session.get('consolidation_detected_prev', False):  # Log when consolidation ends
                                    logger.debug(f"[{trade_from_db.trade_id}] Consolidation period ended")
                        else:
                            session['consolidation_detected'] = False  # Can't determine until we have enough data
                            
                        # Track previous consolidation state for logging
                        session['consolidation_detected_prev'] = session.get('consolidation_detected', False)

                        trade_market_data = await self._fetch_market_data_for_symbol(trade_from_db.symbol)

                                        # --- NEW: Failsafe Stop Loss Logic ---
                        stop_loss_from_exchange = position_data.get('stopLoss', '')
                        if not stop_loss_from_exchange or float(stop_loss_from_exchange) == 0:
                            logger.warning(f"[{trade_from_db.trade_id}] Unprotected trade detected! Applying Arsenal-style failsafe stop loss.")
                            
                            # Get the latest hotspot data to calculate a smart SL
                            hotspots = session['liquidity_analyzer'].get_contextual_snapshot().get('wall_details', [])
                            failsafe_sl = self._calculate_arsenal_style_sl(trade_from_db.direction, current_price, hotspots)

                            # Check if this SL is too risky
                            potential_loss = abs(current_price - failsafe_sl) * trade_from_db.qty
                            position_value = current_price * trade_from_db.qty
                            potential_loss_pct = (potential_loss / position_value) * 100 if position_value > 0 else 0

                            if potential_loss_pct > 20.0:
                                logger.critical(f"[{trade_from_db.trade_id}] FAILSAFE TRIGGERED: Applying a smart stop loss would result in a {potential_loss_pct:.1f}% loss. Closing position immediately.")
                                await self._execute_early_exit(trade_from_db, current_price, "FAILSAFE_TOO_RISKY")
                                continue # Skip further analysis for this trade
                            else:
                                logger.info(f"[{trade_from_db.trade_id}] Applying structure-aware failsafe SL at ${failsafe_sl:.2f}")
                                await self._move_stop_loss(trade_from_db, failsafe_sl, "FAILSAFE_APPLIED", db)

                        # --- ENHANCED: Early Exit Optimization for TP/SL Region ---
                        # Analyze current market conditions for near-TP fakeout detection
                        await self._check_near_tp_fakeout_conditions(session, trade_from_db, current_price, db)

                        verdict, reason = await self.run_aegis_analysis(session, trade_market_data, smoothed_price)
                        
                        if verdict == "EARLY_EXIT":
                            logger.critical(f"[{trade_from_db.trade_id}] AEGIS VERDICT: EARLY EXIT. Reason: {reason}")
                            # Check if exit order is already pending to prevent multiple orders
                            if not session.get('pending_closure', False):
                                await self._execute_early_exit(trade_from_db, current_price, reason)
                            else:
                                logger.debug(f"[{trade_from_db.trade_id}] Skipping early exit - exit order already pending.")
                        elif verdict == "SECURE_PROFITS":
                            logger.info(f"[{trade_from_db.trade_id}] AEGIS VERDICT: SECURE PROFITS. Reason: {reason}")
                            
                            # Check if any exit order is already pending to avoid multiple orders
                            if session.get('pending_closure', False):
                                logger.debug(f"[{trade_from_db.trade_id}] Skipping profit securing - exit order already pending.")
                            else:
                                # Check if we're extremely close to TP and consider partial profit taking
                                distance_to_tp = abs(trade_from_db.take_profit - current_price)
                                total_target_distance = abs(trade_from_db.take_profit - trade_from_db.entry_price)
                                
                                # If we're within 20% of our target distance to TP, consider more aggressive profit protection
                                if total_target_distance > 0 and (distance_to_tp / total_target_distance) < 0.2:
                                    # We're within 20% of target - consider taking partial profits
                                    logger.info(f"[{trade_from_db.trade_id}] Very close to TP ({(1-distance_to_tp/total_target_distance)*100:.1f}% of way), considering partial take profit")
                                    
                                    # Check for adverse order flow or momentum decay near TP
                                    recent_trades = trade_market_data.get("recent_trades", [])
                                    if recent_trades and len(recent_trades) > 0:
                                        # Look for recent trades that indicate potential reversal
                                        if trade_from_db.direction == 'LONG':
                                            # Look for recent selling pressure near current price
                                            recent_sells = [t for t in recent_trades 
                                                           if t['side'] == 'Sell' and float(t['price']) >= current_price * 0.999]  # Within 0.1% of current price
                                            total_sell_volume = sum(float(t['size']) for t in recent_sells)
                                            
                                            if total_sell_volume > 0:
                                                # Consider more aggressive profit protection
                                                await self._execute_partial_exit(trade_from_db, current_price, "NEAR_TP_HIGH_SELL_PRESSURE", db)
                                        else:  # SHORT
                                            # Look for recent buying pressure near current price
                                            recent_buys = [t for t in recent_trades 
                                                          if t['side'] == 'Buy' and float(t['price']) <= current_price * 1.001]  # Within 0.1% of current price
                                            total_buy_volume = sum(float(t['size']) for t in recent_buys)
                                            
                                            if total_buy_volume > 0:
                                                # Consider more aggressive profit protection
                                                await self._execute_partial_exit(trade_from_db, current_price, "NEAR_TP_HIGH_BUY_PRESSURE", db)
                            
                            # Continue with normal trailing SL logic
                            # Only proceed if no exit is pending to avoid conflicting orders
                            if not session.get('pending_closure', False):
                                klines = trade_market_data.get('klines_5m')
                                if klines and not isinstance(klines, Exception) and len(klines) > 1:
                                    last_closed_candle = klines[-2] # [-1] is the current, unclosed candle
                                    new_stop_price = 0
                                    if trade_from_db.direction == 'LONG':
                                        last_low = float(last_closed_candle[3])
                                        # Ensure new stop is profitable and tighter than current SL
                                        if last_low > trade_from_db.entry_price and last_low > trade_from_db.current_stop_loss:
                                            logger.info(f"[{trade_from_db.trade_id}] Securing profits by trailing SL to last 5m low: ${last_low:.2f}")
                                            await self._move_stop_loss(trade_from_db, last_low, "SECURE_PROFITS_TRAIL", db)
                                    elif trade_from_db.direction == 'SHORT':
                                        last_high = float(last_closed_candle[2])
                                        # Ensure new stop is profitable and tighter than current SL
                                        if last_high < trade_from_db.entry_price and last_high < trade_from_db.current_stop_loss:
                                            logger.info(f"[{trade_from_db.trade_id}] Securing profits by trailing SL to last 5m high: ${last_high:.2f}")
                                            await self._move_stop_loss(trade_from_db, last_high, "SECURE_PROFITS_TRAIL", db)
                        elif verdict == "MOVE_SL_BREAKEVEN":
                            logger.info(f"[{trade_from_db.trade_id}] AEGIS VERDICT: MOVE SL TO BREAKEVEN.")
                            # Check if exit order is already pending to avoid conflicting orders
                            if not session.get('pending_closure', False):
                                await self._move_stop_loss(trade_from_db, trade_from_db.entry_price, "BREAKEVEN", db)
                            else:
                                logger.debug(f"[{trade_from_db.trade_id}] Skipping breakeven move - exit order already pending.")
                    
                    db.commit()

                # --- Emit Health and Balance Status ---
                balance_emit_counter += 1
                if balance_emit_counter >= BALANCE_EMIT_INTERVAL:
                    current_balance = await self.bybit_client.get_available_balance()
                    await self.emitter.emit("account_balance_update", {"balance": current_balance})
                    balance_emit_counter = 0

                # Clean up old signals from recent_signals to prevent memory bloat
                current_time = time.time()
                expired_signals = []
                for fingerprint, timestamp in self.recent_signals.items():
                    if current_time - timestamp > 120:  # 2 minutes in seconds
                        expired_signals.append(fingerprint)
                for fingerprint in expired_signals:
                    del self.recent_signals[fingerprint]

                await self.emitter.emit_health("OK", message="Guardian loop cycle completed.")

                await asyncio.sleep(GUARDIAN_LOOP_INTERVAL)
            except Exception as e:
                logger.error(f"Critical error in guardian loop: {e}", exc_info=True)
                await self.emitter.emit_health("ERROR", message=f"Critical error in guardian loop: {e}", extra_info={"traceback": traceback.format_exc()})
                await asyncio.sleep(20) # Longer sleep on error

    async def _fetch_market_data_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """Fetches all necessary market data for a single symbol."""
        tasks = {
            "klines_1m": self.bybit_client.get_klines(symbol, '1', 10),
            "klines_5m": self.bybit_client.get_klines(symbol, '5', 50),
            "klines_15m": self.bybit_client.get_klines(symbol, '15', 50),
            "recent_trades": self.bybit_client.get_public_trades(symbol, limit=500),
            "orderbook": self.bybit_client.get_orderbook(symbol, limit=100)
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), results))

    def _calculate_arsenal_style_sl(self, direction: str, current_price: float, hotspots: list) -> float:
        """Calculates a stop loss based on Arsenal's logic of finding the nearest liquidity hotspot."""
        if direction == 'LONG':
            # Find nearest support hotspot below the current price
            support_hotspots = [h for h in hotspots if h['side'] == 'bid' and h['price'] < current_price]
            if support_hotspots:
                nearest_hotspot = max(support_hotspots, key=lambda x: x['price'])
                # Place SL 0.2% below the hotspot
                return nearest_hotspot['price'] * 0.998
            else:
                # Fallback to a 1.5% stop loss
                return current_price * 0.985
        else: # SHORT
            # Find nearest resistance hotspot above the current price
            resistance_hotspots = [h for h in hotspots if h['side'] == 'ask' and h['price'] > current_price]
            if resistance_hotspots:
                nearest_hotspot = min(resistance_hotspots, key=lambda x: x['price'])
                # Place SL 0.2% above the hotspot
                return nearest_hotspot['price'] * 1.002
            else:
                # Fallback to a 1.5% stop loss
                return current_price * 1.015

    def _log_liquidity_hotspots(self, symbol: str, analyzer: ArsenalLiquidityAnalyzer):
        """Logs the top liquidity levels from the analyzer's heatmap."""
        if not analyzer or not analyzer.liquidity_heatmap or not analyzer.current_orderbook:
            return

        heatmap = analyzer.liquidity_heatmap
        orderbook = analyzer.current_orderbook

        # Handle both API formats to get mid_price
        if 'b' in orderbook:
            mid_price = (float(orderbook['b'][0][0]) + float(orderbook['a'][0][0])) / 2
        else:
            mid_price = (float(orderbook['bids'][0][0]) + float(orderbook['asks'][0][0])) / 2

        all_levels = sorted(heatmap.items(), key=lambda item: item[1], reverse=True)
        bids = [lvl for lvl in all_levels if lvl[0] < mid_price]
        asks = [lvl for lvl in all_levels if lvl[0] > mid_price]

        logger.info(f"--- Liquidity Hotspots for {symbol} ---")
        if bids:
            logger.info("  - Top BID Hotspots (Support):")
            for price, qty in bids[:3]:
                logger.info(f"      - Level: ${price:<9.2f} | Size: {qty:,.0f}")
        if asks:
            logger.info("  - Top ASK Hotspots (Resistance):")
            for price, qty in asks[:3]:
                logger.info(f"      - Level: ${price:<9.2f} | Size: {qty:,.0f}")

    async def run_aegis_analysis(self, session: dict, market_data: dict, smoothed_price: float) -> tuple[str, str]:
        """The new Aegis consensus engine. Calculates a weighted 'Exit Condition Score'."""
        trade = session['trade']
        exit_condition_score = 0
        reasons = []

        # 1. Gather intelligence and scores from all Aegis modules
        structure_score, structure_reasons = self._aegis_check_structure(session, market_data)
        exit_condition_score += structure_score
        reasons.extend(structure_reasons)

        momentum_score, momentum_reasons = self._aegis_check_momentum(session, smoothed_price, market_data)
        exit_condition_score += momentum_score
        reasons.extend(momentum_reasons)

        orderflow_score, orderflow_reasons = self._aegis_check_orderflow(session, market_data)
        exit_condition_score += orderflow_score
        reasons.extend(orderflow_reasons)

        # --- Consolidation Adjustment ---
        # If we're in a consolidation, be more conservative with exit decisions
        if session.get('consolidation_detected', False):
            # Reduce the exit condition score slightly during consolidation to avoid premature exits
            consolidation_adjustment = 10 if exit_condition_score > 0 else 0
            adjusted_score = max(0, exit_condition_score - consolidation_adjustment)
            reasons.append(f"Consolidation detected, reducing exit score by {consolidation_adjustment} points")
            exit_condition_score = adjusted_score

        # --- Log the detailed analysis ---
        logger.info(f"[{trade.trade_id}] AEGIS ANALYSIS (Exit Score: {exit_condition_score}):")
        for reason in reasons:
            logger.info(f"    - {reason}")

        # --- Final Verdict based on Score Thresholds ---
        # Higher thresholds to reduce sensitivity during consolidations
        exit_threshold = 100 if session.get('consolidation_detected', False) else 90
        
        # Enhanced: Lower threshold when near TP to protect profits from fakeouts
        distance_to_tp = abs(trade.take_profit - smoothed_price) if trade.take_profit else float('inf')
        distance_to_sl = abs(trade.current_stop_loss - smoothed_price) if trade.current_stop_loss else float('inf')
        total_distance = abs(trade.take_profit - trade.entry_price) if trade.take_profit else 1.0
        
        if total_distance > 0:
            progress_to_tp = 1 - (distance_to_tp / total_distance) if distance_to_tp != float('inf') else 0
        else:
            progress_to_tp = 0
            
        # When very close to TP (85%+ of the way), lower the exit threshold to protect from fakeouts
        if progress_to_tp >= 0.85:
            adjusted_exit_threshold = max(60, exit_threshold * 0.7)  # 70% of original threshold, minimum 60
            if exit_condition_score >= adjusted_exit_threshold:
                return "EARLY_EXIT", f"Near-TP Protection: Exit Score {exit_condition_score} >= {adjusted_exit_threshold} threshold."
        elif exit_condition_score >= exit_threshold:
            return "EARLY_EXIT", f"High Exit Score ({exit_condition_score}) - Multiple critical risk factors detected."
        
        # --- Move to Breakeven Logic ---
        # Move to breakeven at 70% progress to TP (before the old 75% threshold)
        # This will help prevent turning winning trades into losing ones
        if not trade.sl_moved_to_breakeven:
            # Calculate progress based on how close we are to the take profit relative to the total distance
            # progress_to_tp was already calculated earlier in the function as the actual distance from TP vs total distance
            if progress_to_tp >= 0.7:  # At least 70% of the way to TP
                return "MOVE_SL_BREAKEVEN", f"Price has achieved {progress_to_tp*100:.0f}% of distance to TP - Moving SL to breakeven"

        # Higher threshold for securing profits during consolidation
        profit_secure_threshold = 70 if session.get('consolidation_detected', False) else 60

        # Enhanced: Lower profit securing threshold when near TP to increase protection
        if progress_to_tp >= 0.8:
            adjusted_profit_threshold = max(40, profit_secure_threshold * 0.7)  # 70% of original threshold, minimum 40
            if exit_condition_score >= adjusted_profit_threshold:
                return "SECURE_PROFITS", f"Near-TP Protection: Moderate Exit Score ({exit_condition_score}) >= {adjusted_profit_threshold} threshold."
        elif exit_condition_score >= profit_secure_threshold:
            return "SECURE_PROFITS", f"Moderate Exit Score ({exit_condition_score}) - Securing profits."

        return "HOLD", "All factors healthy"

    def _aegis_check_structure(self, session: dict, market_data: dict) -> tuple[int, list[str]]:
        """Analyzes market structure for invalidation signals, returning a score."""
        trade = session['trade']
        klines_5m = market_data.get('klines_5m')
        score = 0
        reasons = []

        if not klines_5m or isinstance(klines_5m, Exception) or len(klines_5m) < 2:
            return 0, ["Missing 5m kline data"]

        latest_close = float(klines_5m[-2][4])
        latest_high = float(klines_5m[-2][2])
        latest_low = float(klines_5m[-2][3])
        
        # Calculate distance to target for context
        distance_to_tp = abs(trade.take_profit - latest_close) if trade.take_profit else float('inf')
        distance_to_sl = abs(trade.current_stop_loss - latest_close) if trade.current_stop_loss else float('inf')
        total_distance = abs(trade.take_profit - trade.entry_price) if trade.take_profit else 1.0
        
        if total_distance > 0:
            progress_to_tp = 1 - (distance_to_tp / total_distance) if distance_to_tp != float('inf') else 0
        else:
            progress_to_tp = 0

        if trade.direction == 'LONG' and trade.swing_lows:
            key_structure_lows = [s['price'] for s in trade.swing_lows if s['price'] < trade.entry_price]
            if key_structure_lows:
                key_structure_low = max(key_structure_lows)
                if latest_close < key_structure_low:
                    score += 50 # High score for structure break
                    reasons.append(f"5m candle closed below key swing low {key_structure_low}")
                elif latest_low < key_structure_low and latest_close >= key_structure_low:
                    # Wicked lower shadow testing support - could be concerning if near TP
                    if progress_to_tp >= 0.8:  # Near TP
                        score += 30  # Lower score since it didn't close below
                        reasons.append(f"5m candle tested key support low {key_structure_low} near TP")
        elif trade.direction == 'SHORT' and trade.swing_highs:
            key_structure_highs = [s['price'] for s in trade.swing_highs if s['price'] > trade.entry_price]
            if key_structure_highs:
                key_structure_high = min(key_structure_highs)
                if latest_close > key_structure_high:
                    score += 50 # High score for structure break
                    reasons.append(f"5m candle closed above key swing high {key_structure_high}")
                elif latest_high > key_structure_high and latest_close <= key_structure_high:
                    # Wicked upper shadow testing resistance - could be concerning if near TP
                    if progress_to_tp >= 0.8:  # Near TP
                        score += 30  # Lower score since it didn't close above
                        reasons.append(f"5m candle tested key resistance high {key_structure_high} near TP")
        
        if not reasons:
            reasons.append("Structure intact")

        return score, reasons

    def _aegis_check_momentum(self, session: dict, smoothed_price: float, market_data: dict) -> tuple[int, list[str]]:
        """Analyzes momentum using smoothed RSI and price velocity, returning a score."""
        trade = session['trade']
        klines_15m = market_data.get('klines_15m')
        score = 0
        reasons = []

        if not klines_15m or isinstance(klines_15m, Exception) or len(klines_15m) < 30:
            return 0, ["Missing 15m kline data"]

        closes = [float(k[4]) for k in klines_15m]
        raw_rsi = calculate_rsi(closes, 14)
        if raw_rsi is None or pd.isna(raw_rsi):
            return 0, ["RSI could not be calculated"]

        # Update filter and get smoothed value
        smoothed_rsi = session['kf_rsi'].update(raw_rsi)
        velocity = session['kf_price'].get_velocity()
        
        # Calculate distance to targets for context-aware analysis
        distance_to_tp = abs(trade.take_profit - smoothed_price) if trade.take_profit else float('inf')
        distance_to_sl = abs(trade.current_stop_loss - smoothed_price) if trade.current_stop_loss else float('inf')
        total_distance = abs(trade.take_profit - trade.entry_price) if trade.take_profit else 1.0
        
        if total_distance > 0:
            progress_to_tp = 1 - (distance_to_tp / total_distance) if distance_to_tp != float('inf') else 0
        else:
            progress_to_tp = 0

        if trade.direction == 'LONG':
            if smoothed_rsi > 75:
                score += 25
                reasons.append(f"Smoothed 15m RSI is overbought ({smoothed_rsi:.1f})")
            
            # Enhanced: Be more sensitive to negative velocity when near TP
            if velocity < 0:
                if progress_to_tp >= 0.8:  # Near TP
                    score += 30  # Higher penalty when near TP
                    reasons.append("Price velocity has turned negative near TP (critical)")
                else:
                    score += 15
                    reasons.append("Price velocity has turned negative")
        elif trade.direction == 'SHORT':
            if smoothed_rsi < 25:
                score += 25
                reasons.append(f"Smoothed 15m RSI is oversold ({smoothed_rsi:.1f})")
            
            # Enhanced: Be more sensitive to positive velocity when near TP
            if velocity > 0:
                if progress_to_tp >= 0.8:  # Near TP
                    score += 30  # Higher penalty when near TP
                    reasons.append("Price velocity has turned positive near TP (critical)")
                else:
                    score += 15
                    reasons.append("Price velocity has turned positive")
        
        if not reasons:
            reasons.append("Momentum healthy")

        return score, reasons

    def _aegis_check_orderflow(self, session: dict, market_data: dict) -> tuple[int, list[str]]:
        """Analyzes smoothed order flow pressure with enhanced context to reduce whipsaws."""
        trade = session['trade']
        recent_trades = market_data.get("recent_trades")
        score = 0
        reasons = []
        confirmation_threshold = 8  # Increased from 5 to reduce sensitivity for scalping
        reset_threshold = 2  # Reset counter if we get 2 consecutive non-violations

        if not recent_trades or isinstance(recent_trades, Exception) or len(recent_trades) < 100:
            return 0, ["Not enough recent trade data"]

        buy_vol = sum(float(t['size']) for t in recent_trades if t['side'] == 'Buy')
        sell_vol = sum(float(t['size']) for t in recent_trades if t['side'] == 'Sell')
        if buy_vol == 0 or sell_vol == 0: 
            return 0, ["No buy/sell volume"]

        raw_ratio = buy_vol / sell_vol
        smoothed_ratio = session['kf_orderflow_ratio'].update(raw_ratio)

        # Adaptive threshold based on market conditions
        # In consolidation periods, use a higher threshold to avoid false signals
        base_ratio_threshold = 4.5  # Increased from 3.0 to reduce sensitivity for scalping
        
        # Enhanced: Adjust threshold based on how close we are to TP/SL
        distance_to_tp = abs(trade.take_profit - session.get('last_price', trade.entry_price)) if trade.take_profit else float('inf')
        distance_to_sl = abs(trade.current_stop_loss - session.get('last_price', trade.entry_price)) if trade.current_stop_loss else float('inf')
        total_distance = abs(trade.take_profit - trade.entry_price) if trade.take_profit else 1.0
        
        if total_distance > 0:
            progress_to_tp = 1 - (distance_to_tp / total_distance) if distance_to_tp != float('inf') else 0
        else:
            progress_to_tp = 0
            
        # When near TP (80%+ of the way), be more sensitive to adverse order flow
        if progress_to_tp >= 0.8:
            ratio_threshold = base_ratio_threshold * 0.7  # Lower threshold near TP for higher sensitivity
            reasons.append(f"Near target (progress: {progress_to_tp:.2f}), using lower threshold ({ratio_threshold:.2f})")
        elif session.get('consolidation_detected', False):
            ratio_threshold = base_ratio_threshold * 1.5  # Even higher threshold during consolidation
            reasons.append("In consolidation, using higher threshold for orderflow violations")
        else:
            ratio_threshold = base_ratio_threshold

        violation = False

        # Current price from session data
        current_price = session.get('last_price')
        entry_price = trade.entry_price

        if trade.direction == 'LONG' and (1 / smoothed_ratio) > ratio_threshold:
            violation = True
            reasons.append(f"Sustained sell pressure is {(1/smoothed_ratio):.1f}x buy pressure")
            
            # Check if the sell pressure is confirmed by significant adverse price movement
            if current_price and ((entry_price - current_price) / entry_price) > 0.005:  # 0.5% adverse move
                # Significant adverse price movement confirms the pressure
                reasons.append(f"Price moved {((entry_price - current_price) * 100 / entry_price):.2f}% against trade")
            elif current_price and ((entry_price - current_price) / entry_price) <= 0.002:  # Within 0.2% range
                # Price hasn't moved significantly against the trade, likely temporary pressure
                # Reduce the violation significance during minor retracements
                violation = "minor"  # Mark as minor violation
                
        elif trade.direction == 'SHORT' and smoothed_ratio > ratio_threshold:
            violation = True
            reasons.append(f"Sustained buy pressure is {smoothed_ratio:.1f}x sell pressure")
            
            # Check if the buy pressure is confirmed by significant adverse price movement
            if current_price and ((current_price - entry_price) / entry_price) > 0.005:  # 0.5% adverse move
                # Significant adverse price movement confirms the pressure
                reasons.append(f"Price moved {((current_price - entry_price) * 100 / entry_price):.2f}% against trade")
            elif current_price and ((current_price - entry_price) / entry_price) <= 0.002:  # Within 0.2% range
                # Price hasn't moved significantly against the trade, likely temporary pressure
                # Reduce the violation significance during minor retracements
                violation = "minor"  # Mark as minor violation

        # Update violation count based on enhanced logic
        if violation == True:
            # Increment violation count for true violations
            session['orderflow_violation_count'] = session.get('orderflow_violation_count', 0) + 1
            reasons.append(f"Orderflow violation count: {session['orderflow_violation_count']}/{confirmation_threshold}")
            
            # Apply penalty for each set of violations that reach the threshold
            # If violation count is 5, 10, 15, etc., apply penalty
            current_violations = session['orderflow_violation_count']
            previous_penalty_level = session.get('last_applied_penalty_level', 0)
            current_penalty_level = (current_violations // confirmation_threshold)  # Integer division
            
            if current_penalty_level > previous_penalty_level:
                score += 40  # Standard penalty for each threshold reached
                session['last_applied_penalty_level'] = current_penalty_level
                reasons.append(f"CONFIRMED: Sustained adverse pressure. Applying +40 penalty (level {current_penalty_level}).")
        elif violation == "minor":
            # For minor violations, we increase the count but with less significance
            session['violation_without_price_confirmation'] = session.get('violation_without_price_confirmation', 0) + 1
            
            # Apply penalty based on minor violations when accumulated
            minor_penalty_threshold = 8
            minor_penalty_points = 20  # Lower penalty for minor violations
            
            # Calculate how many full sets of minor violations we have
            current_minor_count = session['violation_without_price_confirmation']
            current_minor_penalty_level = session.get('last_minor_penalty_level', 0)
            new_minor_penalty_level = current_minor_count // minor_penalty_threshold
            
            if new_minor_penalty_level > current_minor_penalty_level:
                # Apply a smaller penalty for accumulated minor violations
                session['orderflow_violation_count'] = session.get('orderflow_violation_count', 0) + 1
                # Don't reset the counter completely, just remove the processed sets
                session['violation_without_price_confirmation'] = current_minor_count % minor_penalty_threshold
                session['last_minor_penalty_level'] = new_minor_penalty_level
                reasons.append(f"Processed {new_minor_penalty_level - current_minor_penalty_level} set(s) of minor violations")
                
                score += minor_penalty_points  # Lower penalty for minor violations that accumulate
                reasons.append(f"CONFIRMED: Accumulated minor violations. Applying +{minor_penalty_points} penalty (level {new_minor_penalty_level}).")
        else:
            # No violation - reset the minor counter, but decay the main counter gradually to avoid sudden drops
            session['violation_without_price_confirmation'] = 0
            
            # Decay the violation count gradually to prevent sudden changes
            current_count = session.get('orderflow_violation_count', 0)
            if current_count > 0:
                # Only reduce the count if there's been a period without violations
                if 'last_violation_decay' not in session or (time.time() - session['last_violation_decay']) > 30:  # 30 seconds since last decay
                    session['orderflow_violation_count'] = max(0, current_count - 1)
                    session['last_violation_decay'] = time.time()
                    # Reset penalty level tracking when count drops significantly
                    if session['orderflow_violation_count'] < confirmation_threshold:
                        session['last_applied_penalty_level'] = 0
                    reasons.append(f"Pressure decreased, reducing violation count to {session['orderflow_violation_count']}")
                    # Log the decay for debugging
                    logger.debug(f"[{trade.trade_id}] Violation count decayed to {session['orderflow_violation_count']}")
            reasons.append("Orderflow supportive")

        return score, reasons



    async def _execute_early_exit(self, trade: ManagedTrade, exit_price: float, reason: str):
        """Closes the entire position with a limit order to reduce fees and slippage."""
        logger.warning(f"[{trade.trade_id}] EXECUTING EARLY EXIT WITH LIMIT ORDER. Reason: {reason}. Exit price: ${exit_price:.2f}")
        
        # Determine the limit price based on direction to improve fill probability while reducing slippage
        if trade.direction == 'LONG':
            # For longs, place limit order slightly below current price to ensure execution
            limit_price = exit_price * 0.9995  # 0.05% below to ensure it's a sell order
        else:  # SHORT
            # For shorts, place limit order slightly above current price to ensure execution  
            limit_price = exit_price * 1.0005  # 0.05% above to ensure it's a buy order
        
        # Place a limit order instead of market order to reduce fees and slippage
        side = "Sell" if trade.direction == "LONG" else "Buy"  # Opposite to close position
        result = await self.bybit_client.place_order(
            symbol=trade.symbol,
            direction=trade.direction,  # This is handled by the side parameter
            qty=str(trade.qty),
            order_type="Limit",
            price=limit_price,
            reduce_only=True,  # Ensure this is a position closing order
            position_idx=0  # For one-way mode
        )

        if result and result.get('retCode') == 0:
            order_id = result['result']['orderId']
            logger.info(f"[{trade.trade_id}] Successfully submitted limit close order {order_id} for {trade.qty} at ${limit_price:.2f}.")
            
            # Instead of immediately deleting the session, track this exit order
            if trade.trade_id in self.managed_sessions:
                session = self.managed_sessions[trade.trade_id]
                if 'exit_orders' not in session:
                    session['exit_orders'] = []
                session['exit_orders'].append({
                    'order_id': order_id,
                    'reason': reason,
                    'qty': trade.qty,
                    'limit_price': limit_price,
                    'timestamp': time.time()
                })
                
                # Mark the trade as pending closure to prevent additional orders
                session['pending_closure'] = True
        else:
            logger.error(f"[{trade.trade_id}] Failed to execute early exit order: {result.get('retMsg')}")
            # Even if the order fails, we should remove the pending closure flag
            if trade.trade_id in self.managed_sessions:
                session = self.managed_sessions[trade.trade_id]
                if 'pending_closure' in session:
                    del session['pending_closure']

    async def _execute_partial_exit(self, trade: ManagedTrade, exit_price: float, reason: str, db_session: Session):
        """Closes half of the position with a limit order to reduce fees and slippage."""
        original_qty = trade.qty
        half_qty = original_qty / 2.0
        logger.warning(f"[{trade.trade_id}] EXECUTING PARTIAL LIMIT EXIT (50%). Reason: {reason}. Exit price: ${exit_price:.2f}")
        
        # Determine the limit price based on direction to improve fill probability while reducing slippage
        if trade.direction == 'LONG':
            # For longs, place limit order slightly below current price to ensure execution
            limit_price = exit_price * 0.9995  # 0.05% below to ensure it's a sell order
        else:  # SHORT
            # For shorts, place limit order slightly above current price to ensure execution  
            limit_price = exit_price * 1.0005  # 0.05% above to ensure it's a buy order
        
        # Place a limit order instead of market order to reduce fees and slippage
        side = "Sell" if trade.direction == "LONG" else "Buy"  # Opposite to close position
        result = await self.bybit_client.place_order(
            symbol=trade.symbol,
            direction=trade.direction,  # This is handled by the side parameter
            qty=str(half_qty),
            order_type="Limit",
            price=limit_price,
            reduce_only=True,  # Ensure this is a position closing order
            position_idx=0  # For one-way mode
        )

        if result and result.get('retCode') == 0:
            order_id = result['result']['orderId']
            logger.info(f"[{trade.trade_id}] Successfully submitted partial limit close order {order_id} for {half_qty}/{original_qty} at ${limit_price:.2f}.")
            # Update the trade quantity in the database
            trade.qty = half_qty  # Reduce the quantity to the remaining amount
            db_session.commit()
            
            # Store the order ID for monitoring
            session = next((s for sid, s in self.managed_sessions.items() if s['trade'].trade_id == trade.trade_id), None)
            if session:
                if 'partial_exit_orders' not in session:
                    session['partial_exit_orders'] = []
                session['partial_exit_orders'].append({
                    'order_id': order_id,
                    'trade_id': trade.trade_id,
                    'qty': half_qty,
                    'limit_price': limit_price,
                    'timestamp': time.time()
                })
        else:
            logger.error(f"[{trade.trade_id}] Failed to execute partial exit order: {result.get('retMsg')}")

    async def _move_stop_loss(self, trade: ManagedTrade, new_sl_price: float, reason: str, db_session: Session):
        """Moves the stop loss using a limit order to reduce fees and slippage, with protection against multiple orders."""
        if new_sl_price == trade.current_stop_loss: 
            return
            
        # Find the session for this trade to check for recent order activity
        session = next((s for sid, s in self.managed_sessions.items() if s['trade'].trade_id == trade.trade_id), None)
        if session:
            # Check if there's a pending stop loss modification to avoid multiple orders
            if session.get('pending_stop_loss_update', False):
                current_time = time.time()
                last_update_time = session.get('last_stop_loss_update_time', 0)
                # Only allow new stop loss update if it's been at least 30 seconds
                if current_time - last_update_time < 30:
                    logger.debug(f"[{trade.trade_id}] Skipping stop loss update - too recent since last update.")
                    return
                session['pending_stop_loss_update'] = True
                session['last_stop_loss_update_time'] = current_time
        
        logger.info(f"[{trade.trade_id}] Moving SL to {new_sl_price:.2f}. Reason: {reason}")
        
        # Use limit order instead of modifying stop loss to reduce fees
        # Determine the limit price based on direction
        if trade.direction == 'LONG':
            # For longs, place a limit sell order slightly above the desired stop loss to ensure execution
            limit_price = new_sl_price * 1.0005  # 0.05% above to ensure it's a sell order
        else:  # SHORT
            # For shorts, place a limit buy order slightly below the desired stop loss to ensure execution
            limit_price = new_sl_price * 0.9995  # 0.05% below to ensure it's a buy order
        
        # Place a limit order instead of modifying stop loss on position
        side = "Sell" if trade.direction == "LONG" else "Buy"  # Opposite to close position
        result = await self.bybit_client.place_order(
            symbol=trade.symbol,
            direction=trade.direction,  # This is handled by the side parameter
            qty=str(trade.qty),
            order_type="Limit",
            price=limit_price,
            reduce_only=True,  # Ensure this is a position closing order
            position_idx=0  # For one-way mode
        )
        
        if result and result.get('retCode') == 0:
            order_id = result['result']['orderId']
            logger.info(f"[{trade.trade_id}] Successfully submitted stop loss limit order {order_id} at ${limit_price:.2f}.")
            
            # Update the trade in the database
            db_session.add(trade)
            trade.current_stop_loss = new_sl_price
            if reason == "BREAKEVEN":
                trade.sl_moved_to_breakeven = True
            logger.info(f"[{trade.trade_id}] Successfully set stop loss.")
            
            # Track this order in the session if available
            if session:
                if 'stop_loss_orders' not in session:
                    session['stop_loss_orders'] = []
                session['stop_loss_orders'].append({
                    'order_id': order_id,
                    'original_sl_price': new_sl_price,
                    'limit_price': limit_price,
                    'timestamp': time.time()
                })
        else:
            logger.error(f"[{trade.trade_id}] Failed to place stop loss order: {result.get('retMsg')}")
        
        # Reset pending flag if session exists
        if session:
            session['pending_stop_loss_update'] = False

    def _update_mae_mfe(self, trade: ManagedTrade, current_price: float):
        """Updates the Maximum Adverse and Favorable Excursion for a trade."""
        if trade.direction == 'LONG':
            adverse_excursion = trade.entry_price - current_price
            favorable_excursion = current_price - trade.entry_price
        else: # SHORT
            adverse_excursion = current_price - trade.entry_price
            favorable_excursion = trade.entry_price - current_price

        trade.max_adverse_excursion = max(trade.max_adverse_excursion, adverse_excursion)
        trade.max_favorable_excursion = max(trade.max_favorable_excursion, favorable_excursion)

    async def _check_near_tp_fakeout_conditions(self, session: dict, trade: ManagedTrade, current_price: float, db_session: Session):
        """Check for conditions that indicate a near-TP fakeout and execute early exit if needed."""
        
        # Check if an exit order is already pending to prevent multiple orders
        if session.get('pending_closure', False):
            logger.debug(f"[{trade.trade_id}] Skipping fakeout check - exit order already pending.")
            return
            
        # Calculate distances to TP and SL to determine if we're in the critical region
        distance_to_tp = abs(trade.take_profit - current_price) if trade.take_profit else float('inf')
        distance_to_sl = abs(trade.current_stop_loss - current_price) if trade.current_stop_loss else float('inf')
        total_target_distance = abs(trade.take_profit - trade.entry_price) if trade.take_profit else 1.0
        
        # Determine if we're in the danger zone near TP (within 20% of target)
        if total_target_distance > 0:
            progress_to_tp = 1 - (distance_to_tp / total_target_distance) if distance_to_tp != float('inf') else 0
        else:
            progress_to_tp = 0
            
        is_near_tp = progress_to_tp >= 0.8  # Within 80% of the way to TP
        
        if not is_near_tp:
            return  # Not in the critical region, no need for enhanced checks
            
        # Get recent market data for this symbol to check for fakeout conditions
        trade_market_data = await self._fetch_market_data_for_symbol(trade.symbol)
        
        # Check 1: Spread widening (liquidity degradation near TP)
        if 'orderbook' in trade_market_data and trade_market_data['orderbook']:
            orderbook = trade_market_data['orderbook']
            if 'b' in orderbook:  # New format
                best_bid = float(orderbook['b'][0][0])
                best_ask = float(orderbook['a'][0][0])
            else:  # Old format
                best_bid = float(orderbook['bids'][0][0])
                best_ask = float(orderbook['asks'][0][0])
                
            current_spread_bps = ((best_ask - best_bid) / best_bid) * 10000  # Convert to basis points
            # If spread has widened significantly compared to normal, consider exit
            # NOTE: In practice, you'd calculate an average spread over time, but using a fixed threshold for now
            if current_spread_bps > 0.2:  # If spread > 0.2 bps (which is already quite wide for normal times)
                logger.info(f"[{trade.trade_id}] Near-TP fakeout detected: Spread widened to {current_spread_bps:.2f} bps")
                await self._execute_early_exit(trade, current_price, "NEAR_TP_SPREAD_WIDENING")
                return
        
        # Check 2: Adverse order flow near TP
        recent_trades = trade_market_data.get("recent_trades", [])
        if recent_trades:
            if trade.direction == 'LONG':
                # For long trades, check if recent trades are heavily weighted towards sales near our TP
                recent_tp_proximity_trades = [
                    t for t in recent_trades 
                    if float(t['price']) >= trade.take_profit * 0.99 and float(t['price']) <= trade.take_profit * 1.01
                ]  # Trades within 1% of TP
                if recent_tp_proximity_trades:
                    sell_volume = sum(float(t['size']) for t in recent_tp_proximity_trades if t['side'] == 'Sell')
                    buy_volume = sum(float(t['size']) for t in recent_tp_proximity_trades if t['side'] == 'Buy')
                    
                    if sell_volume > 0 and (sell_volume / (buy_volume + sell_volume)) > 0.7:  # 70% selling pressure near TP
                        logger.info(f"[{trade.trade_id}] Near-TP fakeout detected: High sell pressure near TP (sell:{sell_volume:.4f}, buy:{buy_volume:.4f})")
                        await self._execute_early_exit(trade, current_price, "NEAR_TP_HIGH_SELL_PRESSURE")
                        return
            else:  # SHORT
                # For short trades, check if recent trades are heavily weighted towards buys near our TP
                recent_tp_proximity_trades = [
                    t for t in recent_trades 
                    if float(t['price']) >= trade.take_profit * 0.99 and float(t['price']) <= trade.take_profit * 1.01
                ]  # Trades within 1% of TP
                if recent_tp_proximity_trades:
                    buy_volume = sum(float(t['size']) for t in recent_tp_proximity_trades if t['side'] == 'Buy')
                    sell_volume = sum(float(t['size']) for t in recent_tp_proximity_trades if t['side'] == 'Sell')
                    
                    if buy_volume > 0 and (buy_volume / (buy_volume + sell_volume)) > 0.7:  # 70% buying pressure near TP
                        logger.info(f"[{trade.trade_id}] Near-TP fakeout detected: High buy pressure near TP (buy:{buy_volume:.4f}, sell:{sell_volume:.4f})")
                        await self._execute_early_exit(trade, current_price, "NEAR_TP_HIGH_BUY_PRESSURE")
                        return
        
        # Check 3: Price momentum decay as we approach TP
        # We'll use the Kalman filter's velocity to detect momentum decay
        velocity = session['kf_price'].get_velocity()
        if trade.direction == 'LONG':
            # For long trades, if we're near TP but velocity is negative or close to zero, that's concerning
            if velocity < 0 and progress_to_tp > 0.9:  # Within 90% of target and going negative
                logger.info(f"[{trade.trade_id}] Near-TP fakeout detected: Negative velocity near TP (velocity: {velocity:.2f})")
                await self._execute_early_exit(trade, current_price, "NEAR_TP_NEGATIVE_MOMENTUM")
                return
        else:  # SHORT
            # For short trades, if we're near TP but velocity is positive or close to zero, that's concerning
            if velocity > 0 and progress_to_tp > 0.9:  # Within 90% of target and going positive
                logger.info(f"[{trade.trade_id}] Near-TP fakeout detected: Positive velocity near TP (velocity: {velocity:.2f})")
                await self._execute_early_exit(trade, current_price, "NEAR_TP_POSITIVE_MOMENTUM")
                return

    async def _close_trade_in_db(self, trade: ManagedTrade, exit_price: float, reason: str, db_session: Session):
        """Marks a trade as closed in the database using the provided session."""
        # First, get the trade ID before potential session issues
        trade_id = trade.trade_id
        symbol = trade.symbol
        
        # Fetch the trade from the session to ensure proper binding
        trade_to_close = db_session.query(ManagedTrade).filter(ManagedTrade.trade_id == trade_id).first()
        if not trade_to_close:
            logger.warning(f"[{trade_id}] Trade not found in session, cannot close.")
            return
        
        # Update the trade properties
        trade_to_close.status = 'closed'
        trade_to_close.exit_reason = reason
        trade_to_close.exit_price = exit_price
        trade_to_close.exit_timestamp = int(time.time() * 1000)
        
        if trade_to_close.direction == 'LONG':
            trade_to_close.pnl = (exit_price - trade_to_close.entry_price) * trade_to_close.qty
        else:
            trade_to_close.pnl = (trade_to_close.entry_price - exit_price) * trade_to_close.qty
        trade_to_close.pnl_percent = (trade_to_close.pnl / (trade_to_close.entry_price * trade_to_close.qty)) * 100 if trade_to_close.entry_price > 0 else 0

        # --- ADAPTIVE RISK MANAGEMENT - RECORD TRADE OUTCOME ---
        now = datetime.now()
        if trade_to_close.pnl < 0:
            # --- RECORD A LOSS ---
            self.consecutive_losses += 1
            logger.warning(f"[RISK MANAGER] Loss recorded. Consecutive losses are now: {self.consecutive_losses}")

            # Check if we are in regime filter mode
            if self.regime_filter_until and now < self.regime_filter_until:
                self.regime_filter_active_losses += 1
                logger.warning(f"[RISK MANAGER] Loss recorded during regime filter. Consecutive filter losses: {self.regime_filter_active_losses}")
                # Check for hyper-conservative mode trigger
                if self.regime_filter_active_losses >= 3:
                    self.hyper_conservative_mode = True
                    logger.critical("[RISK MANAGER] 3 losses during regime filter. HYPER-CONSERVATIVE MODE ACTIVATED.")
            
            # Check for cooldown trigger (applies in any mode)
            if self.consecutive_losses >= 5:
                self._activate_cooldown()

        else:
            # --- RECORD A WIN (or breakeven) ---
            if self.consecutive_losses > 0:
                logger.info(f"[RISK MANAGER] Win recorded. Resetting consecutive loss counter from {self.consecutive_losses} to 0.")
                self.consecutive_losses = 0
            if self.regime_filter_active_losses > 0:
                logger.info(f"[RISK MANAGER] Win recorded during regime filter. Resetting filter loss counter from {self.regime_filter_active_losses} to 0.")
                self.regime_filter_active_losses = 0

        # Save state after every trade outcome
        self._save_state()
        # --- END ADAPTIVE RISK MANAGEMENT ---

        # The commit is handled by the guardian loop
        logger.info(f"[{trade_id}] Trade closed in DB. Reason: {reason}. PnL: ${trade_to_close.pnl:.2f} ({trade_to_close.pnl_percent:.2f}%)")
        
        # Emit trade_closed event
        await self.emitter.emit("trade_closed", {
            "trade_id": trade_to_close.trade_id,
            "symbol": trade_to_close.symbol,
            "direction": trade_to_close.direction,
            "entry_price": trade_to_close.entry_price,
            "exit_price": trade_to_close.exit_price,
            "pnl": trade_to_close.pnl,
            "pnl_percent": trade_to_close.pnl_percent,
            "reason": trade_to_close.exit_reason,
            "timestamp": trade_to_close.exit_timestamp
        })
        
        if trade_id in self.managed_sessions:
            del self.managed_sessions[trade_id]
        
        # NEW: Remove symbol from allocated balance when trade closes
        if symbol in self.symbol_allocated_balance:
            del self.symbol_allocated_balance[symbol]
            logger.info(f"[{trade_id}] Released allocated balance for {symbol}. Total active symbols: {len(self.symbol_allocated_balance)}")

    async def run(self):
        """Starts the Trade Manager and all its background tasks."""
        self.is_running = True
        await self.initialize()
        await self.websocket_server.start()
        await self.emitter.start() # Start the emitter
        # Start the two main background loops
        guardian_loop_task = asyncio.create_task(self.guardian_loop())
        limit_order_monitor_task = asyncio.create_task(self._monitor_pending_orders())
        await asyncio.gather(guardian_loop_task, limit_order_monitor_task)

    async def _monitor_pending_orders(self):
        """Periodically checks the status of pending limit orders and triggers OCO logic."""
        while self.is_running:
            await asyncio.sleep(5) # Check every 5 seconds
            if not self.pending_limit_orders:
                continue

            filled_order = None
            orders_to_remove = []
            
            async with self.pending_orders_lock:
                # Create a copy to avoid issues with modifying dict during iteration
                pending_orders_copy = list(self.pending_limit_orders.items())

                for order_id, order_details in pending_orders_copy:
                    try:
                        # Check for 3-minute timeout
                        order_time = order_details['timestamp']
                        time_elapsed = datetime.now() - order_time
                        
                        if time_elapsed.total_seconds() > 180:  # 3 minutes = 180 seconds
                            logger.info(f"[WARNING] 3-minute timeout reached for order {order_id}. Cancelling order...")
                            cancel_result = await self.bybit_client.cancel_order(order_details['symbol'], order_id)
                            if cancel_result and cancel_result.get('retCode') == 0:
                                logger.info(f"[SUCCESS] Order {order_id} cancelled due to 3-minute timeout.")
                            else:
                                logger.error(f"[ERROR] Failed to cancel order {order_id} due to timeout: {cancel_result}")
                            
                            orders_to_remove.append(order_id)
                            continue

                        status = await self.bybit_client.get_order_status(order_details['symbol'], order_id)
                        if not status:
                            continue

                        if status.get('orderStatus') == 'Filled':
                            logger.info(f"[FILLED] Limit order {order_id} for {order_details['symbol']} has been filled!")
                            filled_order = order_details
                            filled_order['final_status'] = status # Add final status for accurate entry price
                            break # Exit loop to handle the fill
                        elif status.get('orderStatus') in ['Cancelled', 'Rejected', 'Deactivated']:
                            logger.warning(f"Pending order {order_id} for {order_details['symbol']} is now {status.get('orderStatus')}. Removing from list.")
                            orders_to_remove.append(order_id)

                    except Exception as e:
                        logger.error(f"Error checking status for order {order_id}: {e}")
                        # If there's an error checking status, still check for timeout
                        order_time = order_details['timestamp']
                        time_elapsed = datetime.now() - order_time
                        if time_elapsed.total_seconds() > 180:  # 3 minutes
                            logger.info(f"[WARNING] 3-minute timeout reached for order {order_id}. Attempting to cancel...")
                            try:
                                cancel_result = await self.bybit_client.cancel_order(order_details['symbol'], order_id)
                                if cancel_result and cancel_result.get('retCode') == 0:
                                    logger.info(f"[SUCCESS] Order {order_id} cancelled due to timeout after error.")
                                else:
                                    logger.error(f"[ERROR] Failed to cancel order {order_id} due to timeout: {cancel_result}")
                            except Exception as cancel_error:
                                logger.error(f"Error cancelling timed-out order {order_id}: {cancel_error}")
                            orders_to_remove.append(order_id)

            # Remove processed orders outside the lock
            async with self.pending_orders_lock:
                for order_id in orders_to_remove:
                    if order_id in self.pending_limit_orders:
                        del self.pending_limit_orders[order_id]
            
            if filled_order:
                await self._handle_filled_limit_order(filled_order)

    async def _handle_filled_limit_order(self, filled_order: Dict[str, Any]):
        """When one limit order fills, cancel all others and create the managed trade."""
        logger.info("--- OCO LOGIC TRIGGERED ---")
        async with self.pending_orders_lock:
            # 1. Cancel all other pending limit orders
            cancellation_tasks = []
            for order_id, order_details in self.pending_limit_orders.items():
                if order_id != filled_order['orderId']:
                    logger.info(f"Cancelling pending limit order {order_id} for {order_details['symbol']}...")
                    cancellation_tasks.append(
                        self.bybit_client.cancel_order(order_details['symbol'], order_id)
                    )
            
            if cancellation_tasks:
                await asyncio.gather(*cancellation_tasks, return_exceptions=True)
                logger.info("All other pending limit orders have been cancelled.")

            # 2. Clear the pending orders list
            self.pending_limit_orders.clear()

        # 3. Create the managed trade record for the filled position
        try:
            signal_decision = filled_order['signal_decision']
            final_status = filled_order['final_status']
            symbol = filled_order['symbol']

            with get_db_session() as db:
                new_trade = ManagedTrade(
                    trade_id=f"aegis_{int(time.time() * 1000)}",
                    symbol=symbol,
                    status='active',
                    direction=signal_decision['direction'],
                    entry_price=float(final_status['avgPrice']),
                    qty=float(final_status['cumExecQty']),
                    initial_stop_loss=signal_decision['stop_loss'],
                    current_stop_loss=signal_decision['stop_loss'],
                    take_profit=signal_decision['take_profits'][0],
                    entry_reasoning=signal_decision,
                    swing_highs=signal_decision.get('swing_highs', []),
                    swing_lows=signal_decision.get('swing_lows', [])
                )
                db.add(new_trade)
                db.commit()
                db.refresh(new_trade)
                
                # Close the session and re-query the trade to ensure proper session binding
                new_trade_id = new_trade.trade_id
                db.expunge(new_trade)  # Remove from current session
                del new_trade  # Remove reference to detached object
                
                # Now re-fetch the trade to bind it to the session for _initialize_trade_session
                fresh_trade = db.query(ManagedTrade).filter(ManagedTrade.trade_id == new_trade_id).first()
                self._initialize_trade_session(fresh_trade)
                logger.info(f"[{fresh_trade.trade_id}] Successfully created managed trade for filled {symbol} order.")
                # Emit trade_opened event
                await self.emitter.emit("trade_opened", {
                    "trade_id": fresh_trade.trade_id,
                    "symbol": fresh_trade.symbol,
                    "direction": fresh_trade.direction,
                    "entry_price": fresh_trade.entry_price,
                    "qty": fresh_trade.qty,
                    "take_profit": fresh_trade.take_profit,
                    "stop_loss": fresh_trade.current_stop_loss
                })

        except Exception as e:
            logger.error(f"Failed to create managed trade after fill: {e}", exc_info=True)

    async def stop(self):
        """Stops the Trade Manager and its components gracefully."""
        logger.info("Stopping Aegis Trade Manager...")
        self.is_running = False
        if self.websocket_server:
            self.websocket_server.stop()
        if self.bybit_client:
            await self.bybit_client.close()
        await self.emitter.stop() # Stop the emitter
        
        # Save final state on shutdown
        self._save_state()
        
        logger.info("Aegis Trade Manager stopped.")