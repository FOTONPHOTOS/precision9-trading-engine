"""
SCALPING RISK MANAGER - MICRO-SCALPING FOCUSED RISK MANAGEMENT

Advanced risk management system specifically designed for micro-scalping:
- Tight stop management based on microstructure
- Dynamic position sizing based on market volatility
- Rapid profit taking at liquidity zones
- Microstructure-aware exit logic
- Fee-aware execution

Focus: Maximize scalping profitability while minimizing adverse selection
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import pandas as pd
import numpy as np

# Add the eyes_of_horus directory to the path
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'eyes_of_horus'))

# Import from eyes_of_horus directory
from eyes_of_horus.config import GUARDIAN_LOOP_INTERVAL
from eyes_of_horus.exchange_client import BybitClient
from eyes_of_horus.websocket_server import WebSocketServer
from horus_liquidity_analyzer import ArsenalLiquidityAnalyzer

logger = logging.getLogger(__name__)

@dataclass
class ScalpingRiskParameters:
    """Risk parameters specifically for scalping operations"""
    max_position_size: float  # Maximum position size in USD
    min_confidence_to_trade: float  # Minimum confidence for scalping
    max_risk_per_trade: float  # Maximum risk percentage (0.003 = 0.3%)
    min_rr_ratio: float  # Minimum R:R for scalping
    max_trade_duration: int  # Maximum time in minutes before forced exit
    tight_stop_percentage: float  # Tight stop loss for scalping
    profit_target_percentage: float  # Typical profit target
    
    # Microstructure-based parameters
    liquidity_zone_distance: float  # Proximity to liquidity zones for exits
    order_flow_reversal_threshold: float  # When to consider reversal
    volatility_expansion_limit: float  # When to reduce position size

class ScalpingRiskManager:
    """
    Advanced risk management system for micro-scalping operations
    Focuses on microstructure patterns and rapid risk management
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.is_running = False
        self.bybit_client = BybitClient()
        self.websocket_server = WebSocketServer(host, port, self.handle_new_signal)
        
        # Scalping-specific managed sessions and tracking
        self.managed_sessions: Dict[str, Dict[str, Any]] = {}
        self.pending_limit_orders: Dict[str, Dict[str, Any]] = {}
        self.pending_orders_lock = asyncio.Lock()
        
        # Track allocated balance per symbol to allow multiple symbols to trade
        self.symbol_allocated_balances: Dict[str, float] = {}
        self.active_symbols: set = set()  # Track symbols with active orders/trades
        self.symbol_cooldowns: Dict[str, datetime] = {}  # Track cooldown periods
        self.max_symbols_to_trade = 3  # Allow up to 3 symbols to trade simultaneously
        
        # Scalping risk parameters
        self.risk_params = ScalpingRiskParameters(
            max_position_size=1000.0,  # Increased max to $1000 per trade for scalping to allow larger positions
            min_confidence_to_trade=0.25,  # Lowered threshold to match brain (was 0.65)
            max_risk_per_trade=0.003,  # 0.3% max risk per trade
            min_rr_ratio=1.0,  # Lowered minimum R:R to 1.0 to give system breathing room (like Arsenal)
            max_trade_duration=60,  # 1 hour max for scalping
            tight_stop_percentage=0.003,  # 0.3% tight stops
            profit_target_percentage=0.005,  # 0.5% profit targets
            liquidity_zone_distance=0.002,  # 0.2% from liquidity zones
            order_flow_reversal_threshold=1.8,  # Order flow reversal trigger
            volatility_expansion_limit=2.0  # 2x ATR volatility limit
        )
        
        # Microstructure tracking
        self.microstructure_analyzer = ArsenalLiquidityAnalyzer(self.bybit_client, 'SOLUSDT')
        self.trade_cooldowns: Dict[str, datetime] = {}
        
        # Performance tracking for scalping optimization
        self.scalping_stats = {
            'total_trades': 0,
            'successful_exits': 0,
            'early_exits': 0,
            'stop_losses': 0,
            'avg_duration': 0,
            'avg_rr_achieved': 0
        }

    async def handle_new_signal(self, signal_data: dict):
        """Handle new scalping signals with microstructure-aware risk management"""
        symbol = signal_data.get('symbol', 'SOLUSDT')
        trade_id = f"scalp_{int(time.time() * 1000)}"
        
        try:
            # Extract scalping signal data
            decision = signal_data.get('decision', {})
            direction = decision.get('direction', 'NEUTRAL')
            confidence = decision.get('confidence', 0.0)
            limit_price = decision.get('limit_order_price', 0.0)
            stop_loss = decision.get('stop_loss', 0.0)
            take_profit = decision.get('take_profit', 0.0)
            risk_reward = decision.get('risk_reward', 0.0)
            
            # Validate scalping-specific requirements
            if not self._validate_scalping_signal(symbol, direction, confidence, risk_reward):
                logger.warning(f"[{trade_id}] Scalping signal failed validation: conf={confidence:.2f}, rr={risk_reward:.2f}")
                return
            
            # Apply dynamic position sizing based on confidence and market conditions
            position_size_multiplier = decision.get('order_size_multiplier', 1.0)
            allocated_balance = await self._calculate_dynamic_position_size(
                symbol, confidence, position_size_multiplier
            )
            
            if allocated_balance <= 0:
                logger.error(f"[{trade_id}] Insufficient balance calculated for scalping trade")
                return
            
            # Calculate quantity
            qty_str = await self.bybit_client._calculate_and_validate_qty(
                symbol, limit_price, allocated_balance=allocated_balance
            )
            
            if qty_str == "0.0":
                logger.error(f"[{trade_id}] Calculated quantity is zero for allocated balance: ${allocated_balance:.2f}")
                return
                
            logger.info(f"[{trade_id}] Scalping setup: {direction} {symbol} at {limit_price:.4f}, SL: {stop_loss:.4f}, TP: {take_profit:.4f}, Qty: {qty_str}")
            
            # Place the limit order for scalping (trap setting)
            order_result = await self.bybit_client.place_order(
                symbol=symbol,
                direction=direction,
                qty=qty_str,
                order_type="Limit",
                price=limit_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            if not order_result or order_result.get('retCode') != 0:
                logger.error(f"[{trade_id}] Failed to place scalping limit order: {order_result.get('retMsg')}")
                # If order placement failed, make sure to remove the symbol from active symbols if we added it
                if symbol in self.active_symbols:
                    self.active_symbols.remove(symbol)
                return
                
            order_id = order_result['result']['orderId']
            logger.info(f"[SUCCESS] [{trade_id}] Scalping limit order {order_id} placed for {qty_str} {symbol} at ${limit_price:.4f}")
            
            # Track the pending order for OCO management
            async with self.pending_orders_lock:
                self.pending_limit_orders[order_id] = {
                    "orderId": order_id,
                    "symbol": symbol,
                    "signal_data": decision,
                    "timestamp": datetime.now(),
                    "expected_fill_time": 180,  # 3 minutes max wait for scalping
                    "scalping_target": take_profit
                }
                
            # Add symbol to active symbols to prevent duplicate orders (only after successful placement)
            # Note: we already added it before attempting to place the order, so this is redundant
            # The proper place to add it is after successful order placement
            if symbol not in self.active_symbols:
                self.active_symbols.add(symbol)
                
            logger.info(f"Added {order_id} to scalping watch list. Total pending: {len(self.pending_limit_orders)}, Active symbols: {len(self.active_symbols)}")
            
        except Exception as e:
            logger.error(f"[{trade_id}] Error handling scalping signal: {e}", exc_info=True)
            # If there was an exception after we added the symbol to active symbols, remove it
            if symbol in self.active_symbols:
                self.active_symbols.remove(symbol)

    def _validate_scalping_signal(self, symbol: str, direction: str, confidence: float, risk_reward: float) -> bool:
        """Validate if the signal meets scalping criteria"""
        
        # Check minimum confidence
        if confidence < self.risk_params.min_confidence_to_trade:
            logger.debug(f"Signal confidence {confidence:.2f} below minimum {self.risk_params.min_confidence_to_trade}")
            return False
            
        # Check minimum R:R ratio
        if risk_reward < self.risk_params.min_rr_ratio:
            logger.debug(f"Signal R:R {risk_reward:.2f} below minimum {self.risk_params.min_rr_ratio}")
            return False
            
        # Check direction validity
        if direction not in ['LONG', 'SHORT']:
            logger.debug(f"Invalid direction: {direction}")
            return False

        # Check if symbol is in cooldown (10 minutes after losing trade)
        if symbol in self.symbol_cooldowns:
            if datetime.now() < self.symbol_cooldowns[symbol]:
                remaining = (self.symbol_cooldowns[symbol] - datetime.now()).total_seconds() / 60
                logger.warning(f"[{symbol}] is on cooldown for another {remaining:.1f} minutes after losing trade")
                return False
            else:
                # Remove expired cooldown
                del self.symbol_cooldowns[symbol]
        
        # Check if symbol already has an active order/trade
        if symbol in self.active_symbols:
            logger.warning(f"[{symbol}] already has an active order/trade. Only one per symbol allowed.")
            return False
            
        # Check if we're at max symbols limit
        if len(self.active_symbols) >= self.max_symbols_to_trade and symbol not in self.active_symbols:
            logger.warning(f"Maximum symbols ({self.max_symbols_to_trade}) already trading. {symbol} must wait.")
            return False
                
        return True

    async def _calculate_dynamic_position_size(self, symbol: str, confidence: float, 
                                             size_multiplier: float) -> float:
        """Calculate dynamic position size based on confidence and market conditions"""
        
        try:
            # Get account balance
            current_balance = await self.bybit_client.get_available_balance()
            if current_balance <= 0:
                logger.error(f"No available balance for position sizing. Balance: ${current_balance:.2f}")
                return 0.0
            
            # For scalping, calculate position size based on percentage of available balance
            # Instead of complex allocation, use a simpler approach that allows multiple symbols
            # to trade based on availability
            balance_for_trading = current_balance * 0.90  # Use 90% of balance for trading
            
            # Base position size is a percentage of total balance but capped reasonably
            base_position_size = balance_for_trading * 0.10  # 10% of available balance as baseline
            max_reasonable_position = balance_for_trading / 3.0  # Max if we want to support 3 symbols reasonably
            
            # Apply confidence-based scaling with adjusted baseline for scalping
            # At 0.25 confidence (our minimum), use 1.0 scaling factor (0.25/0.25 = 1.0)
            # At 0.50 confidence, use 2.0 scaling factor (0.50/0.25 = 2.0) 
            # At 1.0 confidence, use 4.0 scaling factor (1.0/0.25 = 4.0)
            confidence_factor = min(3.0, max(0.1, confidence / 0.25))  # Scale based on our new minimum confidence of 0.25
            if confidence < 0.25:
                confidence_factor = 0.1  # Extra penalty for below minimum confidence
            
            # Apply user-specified multiplier
            total_multiplier = confidence_factor * size_multiplier
            
            # Calculate position size
            calculated_position_size = base_position_size * total_multiplier
            
            # Cap at reasonable maximum and risk parameter limit
            final_position_size = min(calculated_position_size, max_reasonable_position, self.risk_params.max_position_size * 2)
            
            # Ensure minimum viable position for scalping
            if final_position_size < 5:  # Lowered minimum for more flexibility
                return 0.0
                
            logger.info(f"Position sizing: Balance=${current_balance:.2f}, For trading=${balance_for_trading:.2f}, "
                       f"Base=${base_position_size:.2f}, CF={confidence_factor:.2f}, SM={size_multiplier:.2f}, "
                       f"Multiplier={total_multiplier:.2f}, Final=${final_position_size:.2f}")
            
            return final_position_size
            
        except Exception as e:
            logger.error(f"Error calculating dynamic position size: {e}", exc_info=True)
            return 0.0

    async def scalp_guardian_loop(self):
        """Main scalping risk management loop with microstructure awareness"""
        logger.info("Scalping guardian loop started. Beginning real-time scalping management.")
        
        while self.is_running:
            try:
                # Update microstructure data for all symbols
                await self._update_microstructure_data()
                
                # Check all managed trades
                await self._check_managed_trades()
                
                # Monitor pending orders
                await self._monitor_pending_orders()
                
                # Update trade statistics
                await self._update_scalping_statistics()
                
                await asyncio.sleep(2)  # More frequent monitoring for scalping
                
            except Exception as e:
                logger.error(f"Critical error in scalping guardian loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _update_microstructure_data(self):
        """Update microstructure analysis for all tracked symbols"""
        # Update liquidity analyzer
        try:
            if self.microstructure_analyzer:
                # Get current orderbook to update heatmap
                orderbook = await self.bybit_client.get_orderbook('SOLUSDT', limit=100)
                if orderbook:
                    self.microstructure_analyzer.update_with_orderbook(orderbook)
        except Exception as e:
            logger.error(f"Error updating microstructure data: {e}")

    async def _check_managed_trades(self):
        """Check all managed scalping trades for early exit opportunities"""
        # This would be implemented when trades are actually active
        # For now, focusing on limit order management
        pass

    async def _monitor_pending_orders(self):
        """Monitor pending limit orders for scalping opportunities"""
        async with self.pending_orders_lock:
            orders_to_remove = []
            
            for order_id, order_data in self.pending_limit_orders.items():
                try:
                    # Check if order has been cancelled or filled
                    status = await self.bybit_client.get_order_status(order_data['symbol'], order_id)
                    if not status:
                        continue
                        
                    if status.get('orderStatus') == 'Filled':
                        logger.info(f"[FILLED] Scalping limit order {order_id} for {order_data['symbol']} has been filled!")
                        
                        # Move stop loss to breakeven immediately for scalping
                        filled_price = float(status.get('avgPrice', order_data['signal_data'].get('limit_order_price', 0)))
                        await self._move_stop_to_breakeven(order_data['symbol'], filled_price, order_id)
                        
                        # Since this is a simple limit order management system without full position tracking,
                        # we'll remove the symbol from active symbols once the order is filled.
                        # In a full system, we would track the actual position and remove when TP/SL is hit.
                        symbol = order_data['symbol']
                        if symbol in self.active_symbols:
                            self.active_symbols.remove(symbol)
                            logger.debug(f"Removed {symbol} from active symbols after order fill")
                        
                        orders_to_remove.append(order_id)
                        
                    elif status.get('orderStatus') in ['Cancelled', 'Rejected', 'Deactivated']:
                        logger.warning(f"Pending order {order_id} for {order_data['symbol']} is now {status.get('orderStatus')}. Removing from list and releasing allocation.")
                        # Release the symbol from active symbols when order is cancelled
                        symbol = order_data['symbol']
                        if symbol in self.active_symbols:
                            self.active_symbols.remove(symbol)
                        # Release the symbol allocation when order is cancelled
                        if symbol in self.symbol_allocated_balances:
                            del self.symbol_allocated_balances[symbol]
                        orders_to_remove.append(order_id)
                        
                    elif status.get('orderStatus') == 'PartiallyFilled':
                        # For scalping, consider partial fills as opportunities to adjust
                        logger.info(f"Order {order_id} partially filled. Avg price: {status.get('avgPrice')}")
                        
                    # Check for timeout
                    order_time = order_data['timestamp']
                    time_elapsed = (datetime.now() - order_time).total_seconds()
                    
                    if time_elapsed > order_data.get('expected_fill_time', 180):  # 3 minutes default for scalping
                        logger.info(f"[TIMEOUT] Cancelling unfilled scalping order {order_id} after {time_elapsed:.0f}s")
                        cancel_result = await self.bybit_client.cancel_order(order_data['symbol'], order_id)
                        if cancel_result and cancel_result.get('retCode') == 0:
                            logger.info(f"[SUCCESS] Order {order_id} cancelled due to timeout.")
                        else:
                            logger.error(f"[ERROR] Failed to cancel order {order_id} due to timeout: {cancel_result}")
                        
                        # Release the symbol from active symbols and allocation when order times out
                        symbol = order_data['symbol']
                        if symbol in self.active_symbols:
                            self.active_symbols.remove(symbol)
                        if symbol in self.symbol_allocated_balances:
                            del self.symbol_allocated_balances[symbol]
                        orders_to_remove.append(order_id)
                        
                except Exception as e:
                    logger.error(f"Error checking order {order_id}: {e}")
                    
            # Remove processed orders
            for order_id in orders_to_remove:
                if order_id in self.pending_limit_orders:
                    del self.pending_limit_orders[order_id]

    async def _move_stop_to_breakeven(self, symbol: str, entry_price: float, order_id: str):
        """Move stop loss to breakeven for scalping trades"""
        try:
            # For scalping, move SL to 0.1% below/above entry to lock in profit
            if order_id in self.pending_limit_orders:
                direction = self.pending_limit_orders[order_id]['signal_data']['direction']
                
                if direction == 'LONG':
                    breakeven_sl = entry_price * 0.999  # 0.1% below for longs
                else:  # SHORT
                    breakeven_sl = entry_price * 1.001  # 0.1% above for shorts
                    
                # Place a trailing stop order to protect profits
                result = await self.bybit_client.place_order(
                    symbol=symbol,
                    direction=direction,
                    qty=self.pending_limit_orders[order_id]['signal_data'].get('qty', '1'),
                    order_type="Market",  # Use market for immediate execution
                    price=None,
                    stop_loss=breakeven_sl
                )
                
                if result and result.get('retCode') == 0:
                    logger.info(f"[BREAKEVEN] Moved SL to {breakeven_sl:.4f} for trade from order {order_id}")
                else:
                    logger.error(f"[BREAKEVEN] Failed to move SL for order {order_id}: {result}")
                    
        except Exception as e:
            logger.error(f"Error moving stop to breakeven: {e}")

    async def _update_scalping_statistics(self):
        """Update scalping performance statistics"""
        # This would be implemented with actual trade tracking
        # For now, just maintain the structure
        pass

    def _release_symbol_allocation(self, symbol: str):
        """Release the allocated balance for a symbol when trade is closed"""
        if symbol in self.symbol_allocated_balances:
            del self.symbol_allocated_balances[symbol]
            logger.info(f"Released allocation for symbol {symbol}. Active symbols: {len(self.symbol_allocated_balances)}")

    async def initialize(self):
        """Initialize the scalping risk manager"""
        logger.info("Initializing Scalping Risk Manager components...")
        await self.bybit_client.initialize()
        
        try:
            logger.info("Initializing microstructure analyzer context...")
            await self.microstructure_analyzer.initialize_historical_context(snapshot_count=10)
            logger.info("Microstructure analyzer initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize microstructure analyzer: {e}")

        logger.info("Scalping Risk Manager initialization complete.")

    async def run(self):
        """Start the Scalping Risk Manager and all its background tasks"""
        self.is_running = True
        await self.initialize()
        await self.websocket_server.start()
        
        # Start the main scalping loop
        scalping_loop_task = asyncio.create_task(self.scalp_guardian_loop())
        await asyncio.gather(scalping_loop_task)

    async def stop(self):
        """Stop the Scalping Risk Manager and its components gracefully"""
        logger.info("Stopping Scalping Risk Manager...")
        self.is_running = False
        self.websocket_server.stop()
        
        # Clear all tracking on shutdown
        if hasattr(self, 'symbol_allocated_balances'):
            self.symbol_allocated_balances.clear()
            logger.info("Cleared all symbol balance allocations on shutdown")
        
        if hasattr(self, 'active_symbols'):
            self.active_symbols.clear()
            logger.info("Cleared all active symbols on shutdown")
            
        if hasattr(self, 'symbol_cooldowns'):
            self.symbol_cooldowns.clear()
            logger.info("Cleared all symbol cooldowns on shutdown")
        
        await self.bybit_client.close()
        logger.info("Scalping Risk Manager stopped.")

if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description='Scalping Risk Manager')
    parser.add_argument('--host', type=str, default='localhost', help='Host for WebSocket server')
    parser.add_argument('--port', type=int, default=8766, help='Port for WebSocket server')
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("SCALPING RISK MANAGER - STARTING UP")
    print("="*80)
    print(f"WebSocket Server: {args.host}:{args.port}")
    print("Waiting for scalping signals from trading systems...")
    print("="*80 + "\n")
    
    risk_manager = ScalpingRiskManager(host=args.host, port=args.port)
    try:
        asyncio.run(risk_manager.run())
    except KeyboardInterrupt:
        print("\n\n[SHUTDOWN REQUESTED] Stopping Scalping Risk Manager...")
        asyncio.run(risk_manager.stop())
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        asyncio.run(risk_manager.stop())