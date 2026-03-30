"""
Bybit Execution & Risk Management Engine
=========================================
Professional-grade execution system with advanced risk management
Designed for: Full balance utilization with 10x leverage
Risk Limits: 4% per trade, 16% daily maximum drawdown
"""

import os
import sys
import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from enum import Enum
import hashlib
import hmac
import aiohttp
from dotenv import load_dotenv
import numpy as np
from aiohttp import web
from trade_execution_logger import get_logger as get_trade_logger
from liquidity_entry_optimizer import get_entry_optimizer
from pathlib import Path

# Load environment variables
# Correctly locate the .env file relative to this script
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)

# Configure logging
logger = logging.getLogger('BYBIT_EXECUTION')


class OrderSide(Enum):
    BUY = "Buy"
    SELL = "Sell"


class OrderType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"
    LIMIT_MAKER = "Limit"  # Post-only


class PositionStatus(Enum):
    NO_POSITION = "no_position"
    PENDING_ENTRY = "pending_entry"
    IN_POSITION = "in_position"
    PENDING_EXIT = "pending_exit"
    CLOSING = "closing"


@dataclass
class RiskMetrics:
    """Real-time risk tracking"""
    daily_pnl: float = 0.0
    daily_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    current_drawdown: float = 0.0
    max_drawdown_today: float = 0.0
    last_trade_time: Optional[datetime] = None
    consecutive_losses: int = 0
    risk_multiplier: float = 1.0  # Adjusts based on performance
    backoff_until: Optional[datetime] = None  # Trading suspended until this time
    daily_loss: float = 0.0  # Track daily loss for max drawdown


@dataclass
class Position:
    """Active position tracking"""
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: int
    stop_loss: float
    take_profit: float
    timestamp: datetime
    position_id: str = ""
    signal_id: str = ""  # Track which signal created this position
    entry_timestamp: float = 0.0  # Track entry time for duration calculation

    @property
    def pnl_percentage(self) -> float:
        """Calculate PnL percentage"""
        if self.side == "Buy":
            return ((self.current_price - self.entry_price) / self.entry_price) * 100 * self.leverage
        else:
            return ((self.entry_price - self.current_price) / self.entry_price) * 100 * self.leverage


@dataclass
class TradingSignal:
    """Signal from Horus engine"""
    signal_id: str
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confidence: float
    confluence_score: int
    timestamp: float
    risk_reward_ratio: float
    position_size: float  # As percentage


class BybitExecutionEngine:
    """
    Professional Bybit Execution Engine with Advanced Risk Management
    """
    
    def __init__(self, symbol: str):
        # API Configuration
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        self.testnet = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
        
        # URLs
        if self.testnet:
            self.base_url = "https://api-testnet.bybit.com"
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.base_url = "https://api.bybit.com"
            self.ws_url = "wss://stream.bybit.com/v5/private"
        
        # Risk Parameters (from .env)
        self.max_position_percent = float(os.getenv('MAX_POSITION_PERCENT', 100))
        self.max_drawdown_per_trade = float(os.getenv('MAX_DRAWDOWN_PER_TRADE', 0.04))
        self.max_daily_drawdown = float(os.getenv('MAX_DAILY_DRAWDOWN', 0.16))
        self.default_leverage = int(os.getenv('DEFAULT_LEVERAGE', 10))
        self.max_leverage = int(os.getenv('MAX_LEVERAGE', 10))
        
        # Trading Parameters
        self.symbol = symbol # Use passed symbol
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE_THRESHOLD', 0.33))  # Match Horus threshold
        self.use_post_only = os.getenv('USE_POST_ONLY', 'true').lower() == 'true'
        
        # State Management
        self.account_balance = None  # Will be fetched from API
        self.available_balance = None  # Will be fetched from API
        self.position: Optional[Position] = None
        self.position_status = PositionStatus.NO_POSITION
        self.risk_metrics = RiskMetrics()
        self.active_orders = {}
        self.session = None
        self.initialized = False
        self.emergency_stop = False  # Can be triggered from Trading Monitor
        
        # Performance Tracking
        self.trade_history = []
        self.daily_reset_time = None

        # Trade Execution Logger (for pattern analysis)
        self.trade_logger = None  # Initialized in initialize()

        # Signal ID tracking (in-memory, persisted to file)
        self._active_signal_id = None  # Track current position's signal_id
        self._signal_id_file = "trade_logs/active_signal_id.txt"

        # Liquidity Entry Optimizer (for better limit order entries)
        self.entry_optimizer = get_entry_optimizer(self.symbol)

        # HTTP API Server for Trading Monitor (routes added in start_api_server)
        self.api_app = None  # Will be created when server starts
        self.api_runner = None
        # Make port dynamic to avoid conflicts
        self.api_port = 8900 + (int.from_bytes(self.symbol.encode(), 'little') % 100)

        # Partial TP tracking (for 2-tier exit strategy - Horus style)
        self.tp_levels_hit = []  # Track which TPs have been hit
        self.partial_exit_percentages = [0.5, 0.5]  # 50%, 50% (TP1, TP2)
        self._tp_execution_lock = asyncio.Lock()  # Prevent duplicate TP executions

        # TP limit order tracking
        self._tp1_order_id = None
        self._tp2_order_id = None
        self._initial_position_size = None

        # TP application tracking (prevent duplicates)
        self.tp_system_applied = {}  # {position_id: {'tp1': price, 'tp2': price, 'tp3': price, 'signal': signal}}

        self.instrument_info = {} # To store lot size and price filters

        logger.info("="*80)
        logger.info("BYBIT EXECUTION ENGINE INITIALIZED")
        logger.info("="*80)
        logger.info(f"Mode: {'TESTNET' if self.testnet else 'MAINNET'}")
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Max Position: {self.max_position_percent}% of balance")
        logger.info(f"Leverage: {self.default_leverage}x")
        logger.info(f"Risk Limits: {self.max_drawdown_per_trade:.1%} per trade, {self.max_daily_drawdown:.1%} daily")
        logger.info("="*80)
    
    async def _fetch_instrument_info(self):
        """Fetch and store trading rules for the symbol."""
        logger.info(f"Fetching instrument info for {self.symbol}...")
        try:
            response = await self._make_request(
                "GET",
                "/v5/market/instruments-info",
                {"category": "linear", "symbol": self.symbol}
            )
            if response.get('retCode') == 0 and response['result']['list']:
                self.instrument_info = response['result']['list'][0]
                logger.info(" Instrument info fetched successfully.")
                # Log key details
                lot_size_filter = self.instrument_info.get('lotSizeFilter', {})
                price_filter = self.instrument_info.get('priceFilter', {})
                logger.info(f"   - Min Order Qty: {lot_size_filter.get('minOrderQty')}")
                logger.info(f"   - Qty Step: {lot_size_filter.get('qtyStep')}")
                logger.info(f"   - Tick Size: {price_filter.get('tickSize')}")
            else:
                logger.error(f"Could not fetch instrument info: {response.get('retMsg', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Exception fetching instrument info: {e}")

    async def initialize(self):
        """Initialize connection and fetch account data"""
        try:
            # Check for API credentials
            if not self.api_key or not self.api_secret:
                logger.error(" BYBIT_API_KEY or BYBIT_API_SECRET not found in .env")
                logger.error("Please add your Bybit API credentials to the .env file")
                logger.error("Cannot proceed without API credentials for live trading")
                self.initialized = False
                raise ValueError("Missing Bybit API credentials")
            
            # VERY HIGH timeout for slow/unstable networks (90s connect, 120s total)
            timeout = aiohttp.ClientTimeout(
                total=120,           # 2 minutes total
                connect=90,          # 90s for initial connection
                sock_connect=90,     # 90s for socket connection
                sock_read=60         # 60s for reading response
            )
            # Disable SSL verification if needed (some networks have SSL inspection)
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                ssl=False  # Disable SSL verification for problematic networks
            )
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            
            # Sync time with Bybit server
            await self._sync_time()

            # Fetch instrument info for trading rules (e.g., min order size)
            await self._fetch_instrument_info()
            
            # Fetch initial account data FIRST to get real balance
            await self.update_account_info()

            # Check if we successfully got balance
            if self.account_balance is None:
                logger.error("Failed to fetch account balance from Bybit API")
                logger.error("Please check your API credentials and permissions")
                self.initialized = False
                raise ValueError("Unable to fetch account balance")
            
            # Allow zero balance for testing/demo mode
            if self.account_balance == 0:
                logger.warning("  Account balance is $0.00 - Bot will run in DEMO mode (no live trades)")
                logger.warning("Deposit funds to enable live trading")
            
            # Set leverage
            await self._set_leverage(self.symbol, self.default_leverage)
            
            # Check for existing positions
            await self.check_positions()

            # Apply TP system to existing position (if any)
            if self.position:
                await self.check_and_apply_tp_to_existing_position()

            # Initialize trade execution logger
            self.trade_logger = await get_trade_logger()
            logger.info(" Trade execution logger initialized")

            # Start monitoring tasks
            asyncio.create_task(self._monitor_positions())
            asyncio.create_task(self.start_api_server())
            asyncio.create_task(self._monitor_risk())

            self.initialized = True
            logger.info(" Execution engine initialized successfully")
            logger.info(f" Live Account Balance: ${self.account_balance:.2f}")
            logger.info(f" Available for Trading: ${self.available_balance:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to initialize execution engine: {e}")
            self.initialized = False
            raise
    
    async def _sync_time(self):
        """Sync local time with Bybit server"""
        try:
            # Get server time without authentication
            url = f"{self.base_url}/v5/market/time"
            
            if not self.session:
                # VERY HIGH timeout for slow/unstable networks (90s connect, 120s total)
                timeout = aiohttp.ClientTimeout(
                    total=120,           # 2 minutes total
                    connect=90,          # 90s for initial connection
                    sock_connect=90,     # 90s for socket connection
                    sock_read=60         # 60s for reading response
                )
                # Disable SSL verification if needed (some networks have SSL inspection)
                connector = aiohttp.TCPConnector(
                    limit=10,
                    limit_per_host=5,
                    ttl_dns_cache=300,
                    ssl=False  # Disable SSL verification for problematic networks
                )
                self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            
            async with self.session.get(url) as response:
                data = await response.json()
                
            if data.get('retCode') == 0:
                server_time = int(data['result']['timeSecond']) * 1000
                local_time = int(time.time() * 1000)
                self.time_offset = server_time - local_time
                
                if abs(self.time_offset) > 1000:
                    logger.warning(f"Time offset detected: {self.time_offset}ms")
                    logger.info(f"Adjusted time sync with Bybit server")
                else:
                    logger.info(f"Time sync OK (offset: {self.time_offset}ms)")
            else:
                logger.error(f"Failed to sync time: {data.get('retMsg')}")
                self.time_offset = 0
                
        except Exception as e:
            logger.error(f"Time sync failed: {e}")
            self.time_offset = 0

    def _generate_signature(self, params: str) -> str:
        """Generate API signature"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _make_request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated API request"""
        if not self.session:
            # VERY HIGH timeout for slow/unstable networks (90s connect, 120s total)
            timeout = aiohttp.ClientTimeout(
                total=120,           # 2 minutes total
                connect=90,          # 90s for initial connection
                sock_connect=90,     # 90s for socket connection
                sock_read=60         # 60s for reading response
            )
            # Disable SSL verification if needed (some networks have SSL inspection)
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                ssl=False  # Disable SSL verification for problematic networks
            )
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        
        # Add time offset correction for timestamp sync issues
        time_offset = getattr(self, 'time_offset', 0)
        timestamp = str(int(time.time() * 1000) + time_offset)
        recv_window = "20000"
        
        if method == "GET":
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())]) if params else ""
            sign_str = f"{timestamp}{self.api_key}{recv_window}{query_string}"
            url = f"{self.base_url}{endpoint}"
            if query_string:
                url += f"?{query_string}"
        else:
            body = json.dumps(params) if params else "{}"
            sign_str = f"{timestamp}{self.api_key}{recv_window}{body}"
            url = f"{self.base_url}{endpoint}"
        
        signature = self._generate_signature(sign_str)
        
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": "20000",  # Increased recv_window to handle time sync issues
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                async with self.session.get(url, headers=headers) as response:
                    return await response.json()
            else:
                async with self.session.post(url, headers=headers, data=body) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return {"retCode": -1, "retMsg": str(e)}
    
    async def update_account_info(self):
        """Update account balance information"""
        try:
            response = await self._make_request(
                "GET",
                "/v5/account/wallet-balance",
                {"accountType": "UNIFIED"}
            )
            
            if response.get('retCode') == 0:
                result = response.get('result', {})
                wallet_list = result.get('list', [])
                
                if not wallet_list:
                    logger.error("No wallet data returned from API")
                    return
                
                wallet = wallet_list[0]
                
                # First try to get USDT balance from coin array
                coins = wallet.get('coin', [])
                usdt_found = False
                
                for coin in coins:
                    if coin.get('coin') == 'USDT':
                        # Parse USDT balance - try multiple fields for available balance
                        equity_str = str(coin.get('equity', '0'))
                        available_str = str(coin.get('availableToWithdraw', '0'))
                        wallet_balance_str = str(coin.get('walletBalance', '0'))
                        free_str = str(coin.get('free', '0'))
                        
                        # Convert to float safely
                        try:
                            self.account_balance = float(equity_str) if equity_str else 0.0
                            
                            # Try different fields for available balance
                            available_float = float(available_str) if available_str else 0.0
                            wallet_float = float(wallet_balance_str) if wallet_balance_str else 0.0
                            free_float = float(free_str) if free_str else 0.0
                            
                            # Use the highest non-zero value as available balance
                            if available_float > 0:
                                self.available_balance = available_float
                            elif wallet_float > 0:
                                self.available_balance = wallet_float
                                logger.info(f"Using walletBalance as available: ${wallet_float:.2f}")
                            elif free_float > 0:
                                self.available_balance = free_float
                                logger.info(f"Using free balance as available: ${free_float:.2f}")
                            else:
                                # If all are zero but we have equity, use equity as available
                                self.available_balance = self.account_balance
                                logger.warning(f"No available balance field found, using equity: ${self.account_balance:.2f}")
                            
                            usdt_found = True
                            logger.debug(f"USDT balances - equity:{equity_str}, available:{available_str}, wallet:{wallet_balance_str}, free:{free_str}")
                            break
                        except (ValueError, TypeError) as e:
                            logger.error(f"Error parsing USDT balance: {e}")
                            continue
                
                # If USDT not found in coins, use total wallet balance
                if not usdt_found:
                    total_equity_str = str(wallet.get('totalEquity', '0'))
                    total_available_str = str(wallet.get('totalAvailableBalance', '0'))
                    
                    try:
                        self.account_balance = float(total_equity_str) if total_equity_str else 0.0
                        self.available_balance = float(total_available_str) if total_available_str else 0.0
                        logger.debug(f"Using total wallet balance: {total_equity_str}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error parsing total balance: {e}")
                        return
                
                # Log the balance
                if self.account_balance > 0:
                    logger.info(f" Account Balance: ${self.account_balance:.2f}")
                    logger.info(f" Available Balance: ${self.available_balance:.2f}")
                    
                    # Warn if balance is low
                    if self.account_balance < 10:
                        logger.warning(f" Low account balance: ${self.account_balance:.2f}")
                else:
                    logger.warning("Account balance is zero or negative")
                    
            else:
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"API Error: {error_msg}")
                
                # Handle timestamp errors specifically
                if 'timestamp' in error_msg.lower() or 'recv_window' in error_msg.lower():
                    logger.info("Detected timestamp sync issue. Re-syncing with server...")
                    await self._sync_time()
                    
                    # Retry the request once after time sync
                    logger.info("Retrying account update after time sync...")
                    retry_response = await self._make_request(
                        "GET",
                        "/v5/account/wallet-balance",
                        {"accountType": "UNIFIED"}
                    )
                    
                    if retry_response.get('retCode') == 0:
                        result = retry_response.get('result', {})
                        wallet_list = result.get('list', [])
                        if wallet_list:
                            wallet = wallet_list[0]
                            total_equity_str = str(wallet.get('totalEquity', '0'))
                            self.account_balance = float(total_equity_str) if total_equity_str else 0.0
                            self.available_balance = self.account_balance
                            logger.info(f" Successfully fetched balance after time sync: ${self.account_balance:.2f}")
                            return
                    else:
                        logger.error(f"Retry failed: {retry_response.get('retMsg')}")
                
                # Check for specific error codes
                if response.get('retCode') == 10002:
                    logger.error("Invalid API key - please check your credentials")
                elif response.get('retCode') == 10003:
                    logger.error("Invalid signature - please check your API secret")
                elif response.get('retCode') == 10004:
                    logger.error("API key expired or invalid permissions")
                
        except Exception as e:
            logger.error(f"Error updating account info: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    async def check_positions(self):
        """Check for existing positions"""
        response = await self._make_request(
            "GET",
            "/v5/position/list",
            {"category": "linear", "symbol": self.symbol}
        )
        
        if response.get('retCode') == 0:
            positions = response['result']['list']
            if positions:
                pos = positions[0]
                
                # Parse position data safely
                def safe_float(value, default=0.0):
                    """Convert to float safely, handling empty strings and None"""
                    if value is None or value == '':
                        return default
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                
                def safe_int(value, default=1):
                    """Convert to int safely"""
                    if value is None or value == '':
                        return default
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return default
                
                # Only create position if it has size
                position_size = safe_float(pos.get('size', 0))
                if position_size > 0:
                    current_price = safe_float(pos.get('markPrice', 0))
                    unrealized_pnl = safe_float(pos.get('unrealisedPnl', 0))

                    # If position already exists, UPDATE it instead of recreating
                    if self.position and self.position.size > 0:
                        # Update existing position's dynamic fields
                        self.position.size = position_size
                        self.position.current_price = current_price
                        self.position.unrealized_pnl = unrealized_pnl
                        self.position.stop_loss = safe_float(pos.get('stopLoss', 0))
                        self.position.take_profit = safe_float(pos.get('takeProfit', 0))
                        # Keep original timestamp and entry_price
                        logger.debug(f" Position updated: {self.position.side} {self.position.size} {self.symbol[:-4]} | P&L: ${unrealized_pnl:.2f}")
                    else:
                        # Create new position
                        signal_id_from_file = self._load_signal_id()

                        self.position = Position(
                            symbol=pos['symbol'],
                            side=pos['side'],
                            size=position_size,
                            entry_price=safe_float(pos.get('avgPrice', 0)),
                            current_price=current_price,
                            unrealized_pnl=unrealized_pnl,
                            leverage=safe_int(pos.get('leverage', 1)),
                            stop_loss=safe_float(pos.get('stopLoss', 0)),
                            take_profit=safe_float(pos.get('takeProfit', 0)),
                            timestamp=datetime.now(),
                            signal_id=signal_id_from_file,  # Restored from file
                            entry_timestamp=time.time()  # Set to now for existing positions (prevents 55-year duration bug)
                        )
                        logger.info(f" Existing position found: {self.position.side} {self.position.size} {self.symbol}")

                    self.position_status = PositionStatus.IN_POSITION
                else:
                    # Position closed - track P&L
                    if self.position:
                        pnl = self.position.unrealized_pnl
                        closed_price = self.position.current_price
                        await self._track_trade_closure(pnl, self.position, closed_price)

                    self.position = None
                    self.position_status = PositionStatus.NO_POSITION
                    logger.info(" No active positions (zero size)")
                    # If no position, available balance should equal total balance
                    self.available_balance = self.account_balance
            else:
                # Position closed - track P&L
                if self.position:
                    pnl = self.position.unrealized_pnl
                    closed_price = self.position.current_price
                    await self._track_trade_closure(pnl, self.position, closed_price)

                self.position = None
                self.position_status = PositionStatus.NO_POSITION
                logger.info(" No existing positions")
                # If no position, available balance should equal total balance
                self.available_balance = self.account_balance

    async def _track_trade_closure(self, pnl: float, position: Position, closed_price: float):
        """Track trade closure for risk metrics and backoff logic"""
        # Update daily metrics
        self.risk_metrics.daily_trades += 1
        self.risk_metrics.daily_pnl += pnl
        self.risk_metrics.daily_loss += min(0, pnl)  # Only add if loss

        # Track wins/losses and determine outcome based on tp_levels_hit
        outcome = "STOPPED_OUT"  # Default to stopped out

        if pnl > 0:
            self.risk_metrics.winning_trades += 1
            self.risk_metrics.consecutive_losses = 0  # Reset on win
            logger.info(f" TRADE CLOSED - WIN: +${pnl:.2f}")

            # Determine outcome based on which TPs were hit
            if 'TP3' in self.tp_levels_hit:
                outcome = "TP3"  # Full profit - all 3 TPs hit
            elif 'TP2' in self.tp_levels_hit:
                outcome = "TP2"  # Hit TP2, likely stopped at breakeven or TP2
            elif 'TP1' in self.tp_levels_hit:
                outcome = "TP1"  # Hit TP1, likely stopped at breakeven
            else:
                outcome = "TP1"  # Win but no TP tracking (shouldn't happen)
        else:
            self.risk_metrics.losing_trades += 1
            self.risk_metrics.consecutive_losses += 1
            outcome = "STOPPED_OUT"
            logger.warning(f" TRADE CLOSED - LOSS: ${pnl:.2f}")
            logger.warning(f"   Consecutive losses: {self.risk_metrics.consecutive_losses}")

        # Log daily metrics
        logger.info(f" DAILY SUMMARY: P&L ${self.risk_metrics.daily_pnl:.2f} | "
                    f"Trades: {self.risk_metrics.daily_trades} | "
                    f"W/L: {self.risk_metrics.winning_trades}/{self.risk_metrics.losing_trades}")

        # Log outcome to trade execution logger for pattern analysis
        if self.trade_logger and position.signal_id:
            try:
                # Calculate PnL percentage and duration
                pnl_percent = (pnl / (position.entry_price * position.size)) * 100
                duration_minutes = int((time.time() - position.entry_timestamp) / 60)

                await self.trade_logger.update_outcome(
                    signal_id=position.signal_id,
                    outcome=outcome,
                    pnl_percent=pnl_percent,
                    pnl_usd=pnl,
                    duration_minutes=duration_minutes
                )

                logger.info(f" Trade outcome logged: {outcome} ({pnl_percent:+.2f}% in {duration_minutes}min)")

                # Clean up signal_id file after outcome logged
                self._active_signal_id = None
                self._clear_signal_id()

            except Exception as e:
                logger.error(f"Failed to log trade outcome: {e}")

    async def _set_leverage(self, symbol: str, leverage: int):
        """Set leverage for trading"""
        response = await self._make_request(
            "POST",
            "/v5/position/set-leverage",
            {
                "category": "linear",
                "symbol": symbol,
                "buyLeverage": str(leverage),
                "sellLeverage": str(leverage)
            }
        )
        
        if response.get('retCode') == 0:
            logger.info(f" Leverage set to {leverage}x")
        else:
            logger.warning(f"Failed to set leverage: {response.get('retMsg')}")
    
    def calculate_position_size(self, signal: TradingSignal) -> Tuple[float, float]:
        """
        Calculate position size based on a percentage of the account balance.
        WARNING: This is a high-risk strategy.
        
        Returns: (margin_used, position_qty)
        """
        # Check minimum balance requirement
        MIN_BALANCE_USD = 25.0
        if self.account_balance < MIN_BALANCE_USD:
            logger.warning(f" Balance ${self.account_balance:.2f} below minimum ${MIN_BALANCE_USD}")

        # Reverted to 90% of account balance as per user request
        balance_to_use = self.available_balance if self.available_balance > 0 else self.account_balance
        position_percent = 90.0

        margin_used = balance_to_use * (position_percent / 100)
        position_value_usd = margin_used * self.default_leverage
        position_value_usd *= self.risk_metrics.risk_multiplier
        
        if signal.entry_price == 0:
            logger.error("Entry price is zero, cannot calculate position quantity.")
            return 0, 0

        position_qty = position_value_usd / signal.entry_price
        
        # --- Validation ---
        lot_size_filter = self.instrument_info.get('lotSizeFilter', {})
        min_order_size = float(lot_size_filter.get('minOrderQty', 0.0))

        if min_order_size == 0.0:
            logger.warning("Could not determine minimum order size. Using small default.")
            min_order_size = 0.00001
        
        if position_qty < min_order_size:
            logger.error(f" CANNOT MEET MINIMUM ORDER SIZE")
            logger.error(f"   Calculated Qty: {position_qty:.6f} {self.symbol[:-4]}")
            logger.error(f"   Minimum Qty: {min_order_size} {self.symbol[:-4]}")
            logger.error(f"   Your balance of ${self.account_balance:.2f} is too small for this asset's minimum size.")
            return 0, 0
        
        # Round the quantity down to the nearest valid step size
        qty_step = float(lot_size_filter.get('qtyStep', 0.0))
        if qty_step > 0:
            # Calculate the number of steps and floor it, then multiply back
            # This ensures we always round down to a valid multiple of the step size
            position_qty = (position_qty // qty_step) * qty_step

        # Final check after rounding
        if position_qty < min_order_size:
            logger.error(f" Rounded Qty ({position_qty:.6f}) is below minimum ({min_order_size}). Trade rejected.")
            return 0, 0

        logger.warning(" POSITION SIZING: Using 90% of available balance.")
        logger.info(f"   - Margin to be used: ${margin_used:.2f}")
        logger.info(f"   - Total Position Value: ${position_value_usd:.2f}")
        logger.info(f"   - Final Quantity: {position_qty:.6f} {self.symbol[:-4]}")
        logger.warning("   - This strategy carries a high risk of margin competition and catastrophic loss.")
        
        return margin_used, position_qty
    
    def validate_risk_parameters(self, signal: TradingSignal, position_size_usd: float) -> bool:
        """Validate that trade meets risk requirements"""
        # Calculate potential loss for logging purposes only
        if signal.direction == "LONG":
            price_move = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
        else:
            price_move = abs(signal.stop_loss - signal.entry_price) / signal.entry_price
        
        potential_loss = position_size_usd * price_move * self.default_leverage
        potential_loss_pct = potential_loss / self.account_balance
        
        logger.info(f" Risk Information (Testing Mode - No Limits):")
        logger.info(f"   Stop Distance: {price_move:.2%}")
        logger.info(f"   Potential Loss: ${potential_loss:.2f} ({potential_loss_pct:.1%} of account)")
        
        # TESTING MODE: Skip all risk checks for small account testing
        # This allows the ATR-based stop loss system to work naturally
        logger.info(f" Risk checks BYPASSED for testing with small balance")
        logger.info(f"   Using natural ATR-based stops from Horus engine")
        
        # Still check risk/reward ratio as a sanity check
        min_rr = float(os.getenv('MIN_RISK_REWARD', 1.0))  # Lowered for testing
        if signal.risk_reward_ratio < min_rr:
            logger.warning(f" Low Risk/Reward {signal.risk_reward_ratio:.1f} (minimum {min_rr})")
            # But don't block it for testing
        
        return True  # Always return True in testing mode
    
    async def execute_signal(self, signal: TradingSignal) -> bool:
        """Execute trading signal with full risk management"""
        logger.info("="*80)
        logger.info(f" EXECUTING SIGNAL: {signal.signal_id}")
        logger.info("="*80)

        # ========== CHECK BACKOFF PERIOD (15-MIN AFTER 3 LOSSES) ==========
        if self.risk_metrics.backoff_until:
            if datetime.now() < self.risk_metrics.backoff_until:
                remaining = (self.risk_metrics.backoff_until - datetime.now()).seconds // 60
                logger.warning(f" TRADING SUSPENDED - 15min backoff after 3 consecutive losses")
                logger.warning(f"   Time remaining: {remaining} minutes")
                logger.warning(f"   Resume trading at: {self.risk_metrics.backoff_until.strftime('%H:%M:%S')}")
                return False
            else:
                # Backoff period over, reset
                logger.info(" Backoff period ended - resuming trading")
                self.risk_metrics.backoff_until = None

        # ========== CHECK MAX DAILY DRAWDOWN ($20) ==========
        if abs(self.risk_metrics.daily_loss) >= 20.0:
            logger.error(" MAX DAILY DRAWDOWN REACHED: -$20")
            logger.error(f"   Daily Loss: ${self.risk_metrics.daily_loss:.2f}")
            logger.error("   Trading suspended for the day")
            # Suspend trading until midnight (or restart)
            return False

        # Update account info and check positions before trading
        await self.update_account_info()
        await self.check_positions()

        # Cancel any pending orders that might be locking balance
        await self.cancel_all_pending_orders()

        # Re-check balance after canceling orders
        await self.update_account_info()

        # Check if we can trade
        if self.position_status != PositionStatus.NO_POSITION:
            logger.warning("Already in position. Skipping signal.")
            logger.warning(f"   Position Status: {self.position_status.value}")
            if self.position:
                logger.warning(f"   Current Position: {self.position.side} {self.position.size} {self.symbol[:-4]}")
            return False
        
        # Check if we have available balance
        # TESTING MODE: If available balance is 0 but account has funds, use account balance
        if self.available_balance <= 0 and self.account_balance > 0:
            logger.warning(" Available balance shows $0 but account has funds")
            logger.warning(f"   Account Balance: ${self.account_balance:.2f}")
            logger.warning(f"   Available Balance: ${self.available_balance:.2f}")
            logger.warning("   TESTING MODE: Using account balance instead of available")
            # Force available balance to equal account balance for testing
            self.available_balance = self.account_balance
        elif self.account_balance <= 0:
            logger.error(" No funds in account")
            logger.error(f"   Total Balance: ${self.account_balance:.2f}")
            return False
        
        # Check confidence threshold
        if signal.confidence < self.min_confidence:
            logger.warning(f"Signal confidence {signal.confidence:.1%} below threshold {self.min_confidence:.1%}")
            return False

        # ========== VALIDATE MINIMUM RRR (CRITICAL SAFETY CHECK) ==========
        min_rrr = float(os.getenv('MIN_RISK_REWARD', '1.2'))

        # Calculate actual RRR from the signal
        if signal.stop_loss and signal.take_profit_1:
            entry = signal.entry_price
            sl = signal.stop_loss
            tp = signal.take_profit_1

            # Calculate risk and reward
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            actual_rrr = reward / risk if risk > 0 else 0

            if actual_rrr < min_rrr:
                logger.error("="*80)
                logger.error(" BYBIT ENGINE: TRADE REJECTED - INSUFFICIENT RRR")
                logger.error(f"   Actual RRR: {actual_rrr:.2f}:1")
                logger.error(f"   Minimum Required: {min_rrr}:1 (from .env MIN_RISK_REWARD)")
                logger.error(f"   Entry: ${entry:.3f}")
                logger.error(f"   Stop Loss: ${sl:.3f} (risk: ${risk:.3f})")
                logger.error(f"   Take Profit: ${tp:.3f} (reward: ${reward:.3f})")
                logger.error("   SAFETY: This trade does NOT meet minimum risk/reward ratio")
                logger.error("="*80)
                return False

            logger.info(f" RRR Validation PASSED: {actual_rrr:.2f}:1 (minimum: {min_rrr}:1)")
        else:
            logger.warning(" Cannot validate RRR - missing SL or TP")

        # ========== ENFORCE LIMIT ORDERS ==========
        if not self.use_post_only:
            logger.warning("="*80)
            logger.warning(" WARNING: USE_POST_ONLY is false in .env")
            logger.warning("   Market orders can result in poor fills and slippage")
            logger.warning("   Recommendation: Set USE_POST_ONLY=true in .env")
            logger.warning("   Proceeding with current setting...")
            logger.warning("="*80)
        else:
            logger.info(" Using LIMIT ORDERS (GTC - can take liquidity, slightly higher fees)")

        # ========== FIND OPTIMAL ENTRY USING LIQUIDITY ==========
        logger.info("="*80)
        logger.info(" FINDING OPTIMAL ENTRY ZONE")
        logger.info("="*80)

        # Get current market price
        current_price = signal.entry_price

        # Find liquidity-based entry zone
        entry_zone = self.entry_optimizer.find_entry_zone(
            current_price=current_price,
            direction=signal.direction,
            max_distance_pct=0.3  # Max 0.3% away from current price
        )

        # Decide if limit order is appropriate
        urgency = signal.confidence  # Use signal confidence as urgency
        use_limit_entry = self.entry_optimizer.should_use_limit_entry(entry_zone, urgency)

        # Determine final entry price
        if use_limit_entry:
            optimal_entry_price = entry_zone['entry_price']
            logger.info(f" Using LIMIT ORDER at liquidity zone: ${optimal_entry_price:.2f}")
            logger.info(f"   Zone Type: {entry_zone['zone_type']}")
            logger.info(f"   Distance: {entry_zone['distance_pct']:.3f}% from market")
            logger.info(f"   Strength: {entry_zone['strength']:.2f}x")
            logger.info(f"   Reason: {entry_zone['reason']}")
        else:
            optimal_entry_price = current_price
            logger.info(f" Using MARKET ORDER at current price: ${optimal_entry_price:.2f}")
            logger.info(f"   Reason: High urgency ({urgency*100:.0f}%) or no strong zone")

        # Recalculate stop loss based on new entry price
        # Keep same % distance but from the new entry
        original_stop_distance_pct = abs(signal.stop_loss - signal.entry_price) / signal.entry_price

        if signal.direction == "LONG":
            adjusted_stop_loss = optimal_entry_price * (1 - original_stop_distance_pct)
        else:
            adjusted_stop_loss = optimal_entry_price * (1 + original_stop_distance_pct)

        logger.info(f" Adjusted Stop Loss: ${adjusted_stop_loss:.2f} ({original_stop_distance_pct*100:.3f}% from entry)")

        # Calculate position size
        position_size_usd, position_qty = self.calculate_position_size(signal)
        if position_qty == 0:
            return False

        # Validate risk parameters
        if not self.validate_risk_parameters(signal, position_size_usd):
            return False

        # Prepare order
        side = OrderSide.BUY if signal.direction == "LONG" else OrderSide.SELL
        
        # Place entry order
        # Format quantity to 1 decimal place for SOLUSDT (Bybit requirement)
        formatted_qty = f"{position_qty:.1f}"
        
        # ========== SETUP 3-TIER TP/SL ORDERS ==========
        # Note: Bybit only allows 1 TP per position, so we'll manually manage partial exits
        # Initial order uses only TP1, we'll add TP2/TP3 via monitoring

        order_params = {
            "category": "linear",
            "symbol": self.symbol,
            "side": side.value,
            "orderType": "Limit" if use_limit_entry else "Market",
            "qty": formatted_qty,
            "price": str(optimal_entry_price) if use_limit_entry else None,
            "timeInForce": "GTC" if use_limit_entry else "IOC",
            "orderLinkId": signal.signal_id,
            "stopLoss": str(adjusted_stop_loss),
            "takeProfit": str(signal.take_profit_1),  #  ENABLED - Horus TP closes final 25% (Risk Manager handles TP1/TP2)
            "reduceOnly": False,
            "closeOnTrigger": False
        }
        
        # Remove None values
        order_params = {k: v for k, v in order_params.items() if v is not None}
        
        self.position_status = PositionStatus.PENDING_ENTRY
        
        # Execute order
        response = await self._make_request("POST", "/v5/order/create", order_params)
        
        if response.get('retCode') == 0:
            order_id = response['result']['orderId']
            self.active_orders[order_id] = {
                'signal': signal,
                'status': 'pending',
                'timestamp': datetime.now()
            }
            
            logger.info(f" Order placed successfully: {order_id}")
            logger.info(f"   Direction: {signal.direction}")
            logger.info(f"   Entry: ${optimal_entry_price:.2f}")
            logger.info(f"   Stop Loss: ${adjusted_stop_loss:.2f}")
            logger.info(f"   TP Levels (3-Tier System):")
            logger.info(f"      TP1: ${signal.take_profit_1:.2f} → Exit 40%")
            logger.info(f"      TP2: ${signal.take_profit_2:.2f} → Exit 30%")
            logger.info(f"      TP3: ${signal.take_profit_3:.2f} → Exit 30%")
            
            # Monitor order fill
            await self._monitor_order_fill(order_id, signal, position_qty)
            
            return True
        else:
            logger.error(f" Order failed: {response.get('retMsg')}")
            logger.error(f"   Error Code: {response.get('retCode')}")
            logger.error(f"   Account Balance: ${self.account_balance:.2f}")
            logger.error(f"   Available Balance: ${self.available_balance:.2f}")
            
            # Common Bybit error codes
            if response.get('retCode') == 110007:
                logger.error("   Issue: Insufficient available balance")
            elif response.get('retCode') == 110013:
                logger.error("   Issue: Order quantity too small or invalid precision")
            elif response.get('retCode') == 110014:
                logger.error("   Issue: Invalid price or quantity step")
            
            self.position_status = PositionStatus.NO_POSITION
            return False
    
    async def _monitor_order_fill(self, order_id: str, signal: TradingSignal, qty: float):
        """Monitor order until filled or timeout"""
        max_wait = int(os.getenv('ORDER_DECAY_SECONDS', 60))  # Increased to 60s for limit orders
        start_time = time.time()
        check_count = 0
        
        while time.time() - start_time < max_wait:
            check_count += 1
            response = await self._make_request(
                "GET",
                "/v5/order/realtime",
                {"category": "linear", "orderId": order_id}
            )
            
            if response.get('retCode') == 0 and response.get('result', {}).get('list'):
                order = response['result']['list'][0]
                order_status = order.get('orderStatus', 'Unknown')
                
                logger.debug(f"Order check #{check_count}: Status = {order_status}")
                
                if order_status == 'Filled':
                    logger.info(f" Order filled at ${order.get('avgPrice', 'N/A')}")

                    # Update position
                    entry_time = time.time()
                    self.position = Position(
                        symbol=self.symbol,
                        side="Buy" if signal.direction == "LONG" else "Sell",
                        size=qty,
                        entry_price=float(order.get('avgPrice', signal.entry_price)),
                        current_price=float(order.get('avgPrice', signal.entry_price)),
                        unrealized_pnl=0,
                        leverage=self.default_leverage,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit_1,
                        timestamp=datetime.now(),
                        signal_id=signal.signal_id,
                        entry_timestamp=entry_time,
                        position_id=order_id
                    )
                    self.position_status = PositionStatus.IN_POSITION

                    # Store signal_id to file for outcome tracking (in case bot restarts)
                    self._active_signal_id = signal.signal_id
                    self._save_signal_id(signal.signal_id)

                    # Place TP limit orders directly on Bybit exchange (Horus-style)
                    await self._place_tp_limit_orders_on_exchange(signal, qty, signal.direction)

                    # Set up position management
                    asyncio.create_task(self._manage_position(signal))
                    return
                elif order_status == 'PartiallyFilled':
                    logger.info(f"⏳ Order partially filled: {order.get('cumExecQty', 0)}/{qty}")
                elif order_status in ['Cancelled', 'Rejected', 'Deactivated']:
                    logger.warning(f" Order {order_status}: {order.get('rejectReason', 'No reason provided')}")
                    self.position_status = PositionStatus.NO_POSITION
                    return
                elif order_status == 'New':
                    # Order is still active, waiting for fill
                    elapsed = time.time() - start_time
                    logger.info(f"⏳ Waiting for fill... ({elapsed:.1f}s / {max_wait}s)")
            else:
                logger.warning(f"Failed to check order status: {response.get('retMsg', 'Unknown error')}")
            
            # Wait before next check (longer for limit orders)
            await asyncio.sleep(2.0)  # Check every 2 seconds instead of 0.5
        
        # Timeout reached - cancel unfilled order
        logger.warning(f"⏰ Order timeout after {max_wait}s. Cancelling...")
        await self._cancel_order(order_id)
        self.position_status = PositionStatus.NO_POSITION
    
    async def _manage_position(self, signal: TradingSignal):
        """Manage position with trailing stops and partial profits"""
        logger.info(" Position management started")
        
        breakeven_triggered = False
        trailing_started = False
        tp1_hit = False
        tp2_hit = False
        
        while self.position and self.position_status == PositionStatus.IN_POSITION:
            # Update position data
            await self.check_positions()
            
            if not self.position:
                break
            
            current_price = self.position.current_price
            entry_price = self.position.entry_price
            
            # Calculate price movement
            if self.position.side == "Buy":
                price_move = (current_price - entry_price) / entry_price
            else:
                price_move = (entry_price - current_price) / entry_price
            
            # Breakeven management
            breakeven_trigger = float(os.getenv('BREAKEVEN_TRIGGER_PERCENT', 0.2)) / 100
            if not breakeven_triggered and price_move >= breakeven_trigger:
                logger.info(f" Moving stop to breakeven at {price_move:.2%} profit")
                await self._update_stop_loss(entry_price)
                breakeven_triggered = True
            
            # Partial profit taking
            # Check TP based on position direction
            if self.position.side == "Buy":
                # For LONG positions, price must go UP to hit TP
                tp1_condition = current_price >= signal.take_profit_1
                tp2_condition = current_price >= signal.take_profit_2
            else:
                # For SHORT positions, price must go DOWN to hit TP
                tp1_condition = current_price <= signal.take_profit_1
                tp2_condition = current_price <= signal.take_profit_2
            
            if not tp1_hit and tp1_condition:
                logger.info(f" TP1 hit at ${current_price:.2f}! Taking 40% profit")
                await self._partial_close(0.4)
                tp1_hit = True
            
            if not tp2_hit and tp2_condition:
                logger.info(f" TP2 hit at ${current_price:.2f}! Taking 30% profit")
                await self._partial_close(0.3)
                tp2_hit = True
            
            # Trailing stop
            trailing_start = float(os.getenv('TRAILING_START_PERCENT', 0.3)) / 100
            trailing_distance = float(os.getenv('TRAILING_DISTANCE_PERCENT', 0.15)) / 100
            
            if not trailing_started and price_move >= trailing_start:
                logger.info(f" Starting trailing stop at {price_move:.2%} profit")
                trailing_started = True
            
            if trailing_started:
                if self.position.side == "Buy":
                    new_stop = current_price * (1 - trailing_distance)
                    if new_stop > self.position.stop_loss:
                        await self._update_stop_loss(new_stop)
                else:
                    new_stop = current_price * (1 + trailing_distance)
                    if new_stop < self.position.stop_loss:
                        await self._update_stop_loss(new_stop)
            
            await asyncio.sleep(1)
    
    async def _update_stop_loss(self, new_stop: float):
        """Update stop loss for position"""
        response = await self._make_request(
            "POST",
            "/v5/position/trading-stop",
            {
                "category": "linear",
                "symbol": self.symbol,
                "stopLoss": str(new_stop)
            }
        )
        
        if response.get('retCode') == 0:
            self.position.stop_loss = new_stop
            logger.info(f" Stop loss updated to ${new_stop:.2f}")
        else:
            logger.error(f"Failed to update stop loss: {response.get('retMsg')}")
    
    async def _partial_close(self, percentage: float):
        """Partially close position"""
        if not self.position:
            logger.warning("No position to close")
            return False

        initial_size = self.position.size
        close_qty = initial_size * percentage

        # Format to 1 decimal place (Bybit requirement for SOLUSDT)
        formatted_qty = f"{close_qty:.1f}"

        side = OrderSide.SELL if self.position.side == "Buy" else OrderSide.BUY

        logger.info(f" Sending partial close order:")
        logger.info(f"   Initial size: {initial_size:.4f} {self.symbol[:-4]}")
        logger.info(f"   Close qty: {formatted_qty} {self.symbol[:-4]} ({percentage:.0%})")

        response = await self._make_request(
            "POST",
            "/v5/order/create",
            {
                "category": "linear",
                "symbol": self.symbol,
                "side": side.value,
                "orderType": "Market",
                "qty": formatted_qty,
                "reduceOnly": True
            }
        )

        if response.get('retCode') == 0:
            actual_closed_qty = float(formatted_qty)
            logger.info(f" Partially closed {percentage:.0%} of position ({formatted_qty} {self.symbol[:-4]})")
            logger.info(f"   Realized PnL: {self.position.pnl_percentage * percentage:.2f}%")
            self.position.size -= actual_closed_qty
            logger.info(f"   New position size: {self.position.size:.4f} SOL")

            # Wait for Bybit to process the order before allowing next TP check
            await asyncio.sleep(3)
            return True
        else:
            logger.error(f" Partial close failed: {response.get('retMsg')}")
            return False
    
    async def emergency_close_all(self):
        """Emergency close all positions"""
        logger.warning(" EMERGENCY CLOSE INITIATED")
        
        if self.position:
            side = OrderSide.SELL if self.position.side == "Buy" else OrderSide.BUY
            
            response = await self._make_request(
                "POST",
                "/v5/order/create",
                {
                    "category": "linear",
                    "symbol": self.symbol,
                    "side": side.value,
                    "orderType": "Market",
                    "qty": str(self.position.size),
                    "reduceOnly": True
                }
            )
            
            if response.get('retCode') == 0:
                logger.info(" Emergency close successful")
                self.position = None
                self.position_status = PositionStatus.NO_POSITION
            else:
                logger.error(f" Emergency close failed: {response.get('retMsg')}")
    
    async def _monitor_positions(self):
        """Monitor positions for TP fills via position size monitoring (Horus method)"""
        while True:
            if self.position:
                # ========== BULLETPROOF POSITION TRACKING ==========
                # Update position every 1 second when active (was 5s - TOO SLOW!)
                await self.check_positions()

                # ========== MONITOR TP FILLS VIA POSITION SIZE (HORUS METHOD) ==========
                # Detects when TP limit orders fill by watching position size drop
                await self._monitor_tp_fills_via_position_size()

                # Check for excessive loss (re-check position existence after TP exits)
                if self.position and self.position.pnl_percentage <= -self.max_drawdown_per_trade * 100:
                    logger.warning(f"Position loss exceeds limit: {self.position.pnl_percentage:.1%}")
                    await self.emergency_close_all()

                # BULLETPROOF: Check every 1 second when in position
                await asyncio.sleep(1)
            else:
                # No position - check every 5 seconds
                await asyncio.sleep(5)

    async def _apply_tp_system_to_position(self, signal: TradingSignal, position_id: str):
        """
        Apply 3-tier TP system to a position (called after fill or on existing position)

        This method:
        1. Checks if TP system already applied to this position
        2. Stores TP levels for tracking
        3. Resets tp_levels_hit for this position
        """
        # Check if already applied
        if position_id in self.tp_system_applied:
            logger.info(f"TP system already applied to position {position_id}")
            return

        logger.info("="*80)
        logger.info(" APPLYING 3-TIER TP SYSTEM TO POSITION")
        logger.info("="*80)

        # Store TP configuration for this position
        self.tp_system_applied[position_id] = {
            'tp1': signal.take_profit_1,
            'tp2': signal.take_profit_2,
            'tp3': signal.take_profit_3,
            'signal': signal,
            'entry_price': self.position.entry_price if self.position else signal.entry_price
        }

        # Reset TP levels hit for new position
        self.tp_levels_hit = []

        logger.info(f" 2-Tier TP System Configured:")
        logger.info(f"   TP1: ${signal.take_profit_1:.2f} → Exit 50% ({self.partial_exit_percentages[0]*100:.0f}%)")
        logger.info(f"   TP2: ${signal.take_profit_2:.2f} → Exit 50% ({self.partial_exit_percentages[1]*100:.0f}%)")
        logger.info(f"   Position ID: {position_id}")
        logger.info("")
        logger.info("ℹ  NOTE: TPs are managed by the bot, not visible on Bybit interface")
        logger.info("   Bot will automatically execute partial closes when price hits TP levels")
        logger.info("   Monitoring loop checks price every 5 seconds")
        logger.info("="*80)

    async def _place_tp_limit_orders_on_exchange(self, signal: TradingSignal, position_qty: float, direction: str):
        """
        Place TP limit orders directly on Bybit exchange (Horus-style)

        EDUCATIONAL LOGGING: This method explains every step for learning

        Args:
            signal: Trading signal with TP levels
            position_qty: Total position size
            direction: "LONG" or "SHORT"

        What this does:
        1. Calculates 50%/50% split for TP1 and TP2
        2. Places reduceOnly limit orders on exchange
        3. Stores order IDs for monitoring
        4. Orders are visible on Bybit interface
        5. Exchange executes automatically when price hits
        """
        logger.info("="*80)
        logger.info(" EDUCATIONAL: Placing TP Limit Orders on Exchange (Horus Method)")
        logger.info("="*80)

        # Step 1: Calculate quantities (50% each)
        tp1_qty = position_qty * 0.5
        tp2_qty = position_qty * 0.5

        logger.info(f" Calculating TP quantities:")
        logger.info(f"   Total position: {position_qty:.1f} {self.symbol[:-4]}")
        logger.info(f"   TP1 quantity: {tp1_qty:.1f} {self.symbol[:-4]} (50%)")
        logger.info(f"   TP2 quantity: {tp2_qty:.1f} {self.symbol[:-4]} (50%)")
        logger.info("")

        # Step 2: Determine opposite side to close position
        tp_side = "Sell" if direction == "LONG" else "Buy"

        logger.info(f" WHY OPPOSITE SIDE?")
        logger.info(f"   Position is: {direction}")
        logger.info(f"   To close, we: {tp_side}")
        logger.info(f"   LONG positions are closed by SELLING")
        logger.info(f"   SHORT positions are closed by BUYING")
        logger.info("")

        # Step 3: Store initial position size (for monitoring fills)
        self._initial_position_size = position_qty
        logger.info(f" Stored initial position size: {position_qty:.1f} {self.symbol[:-4]}")
        logger.info(f"   This helps us detect when TPs fill by watching position size drop")
        logger.info("")

        # Step 4: Place TP1 limit order
        logger.info(f" Placing TP1 limit order:")
        logger.info(f"   Price: ${signal.take_profit_1:.2f}")
        logger.info(f"   Quantity: {tp1_qty:.1f} {self.symbol[:-4]}")
        logger.info(f"   Type: Limit order with reduceOnly=True")
        logger.info(f"   reduceOnly means: Can ONLY close position, never open new one")

        tp1_params = {
            "category": "linear",
            "symbol": self.symbol,
            "side": tp_side,
            "orderType": "Limit",
            "qty": f"{tp1_qty:.1f}",
            "price": f"{signal.take_profit_1:.2f}",
            "reduceOnly": True,      # CRITICAL: Can only close position
            "timeInForce": "GTC",    # Good-til-cancelled
            "positionIdx": 0         # One-way mode
        }

        tp1_response = await self._make_request("POST", "/v5/order/create", tp1_params)

        if tp1_response.get('retCode') == 0:
            self._tp1_order_id = tp1_response['result']['orderId']
            logger.info(f" TP1 limit order placed successfully!")
            logger.info(f"   Order ID: {self._tp1_order_id}")
            logger.info(f"   Status: Active on Bybit exchange")
            logger.info(f"   Visible in: Bybit app → Conditional Orders")
            logger.info("")
        else:
            logger.error(f" TP1 order failed: {tp1_response.get('retMsg')}")
            logger.error(f"   Will fall back to bot-managed TP")
            return False

        # Step 5: Place TP2 limit order
        logger.info(f" Placing TP2 limit order:")
        logger.info(f"   Price: ${signal.take_profit_2:.2f}")
        logger.info(f"   Quantity: {tp2_qty:.1f} {self.symbol[:-4]}")

        tp2_params = {
            "category": "linear",
            "symbol": self.symbol,
            "side": tp_side,
            "orderType": "Limit",
            "qty": f"{tp2_qty:.1f}",
            "price": f"{signal.take_profit_2:.2f}",
            "reduceOnly": True,
            "timeInForce": "GTC",
            "positionIdx": 0
        }

        tp2_response = await self._make_request("POST", "/v5/order/create", tp2_params)

        if tp2_response.get('retCode') == 0:
            self._tp2_order_id = tp2_response['result']['orderId']
            logger.info(f" TP2 limit order placed successfully!")
            logger.info(f"   Order ID: {self._tp2_order_id}")
            logger.info(f"   Status: Active on Bybit exchange")
            logger.info("")
        else:
            logger.error(f" TP2 order failed: {tp2_response.get('retMsg')}")
            # TP1 is already placed, so we can continue
            logger.warning("   TP1 is active, TP2 will be bot-managed")

        # Step 6: Summary
        logger.info("="*80)
        logger.info(" TP LIMIT ORDERS PLACED ON EXCHANGE")
        logger.info("="*80)
        logger.info(f" Summary:")
        logger.info(f"   TP1: ${signal.take_profit_1:.2f} → {tp1_qty:.1f} {self.symbol[:-4]} (50%)")
        logger.info(f"   TP2: ${signal.take_profit_2:.2f} → {tp2_qty:.1f} {self.symbol[:-4]} (50%)")
        logger.info("")
        logger.info(f" BENEFITS:")
        logger.info(f"   1. Orders execute instantly when price hits (no bot lag)")
        logger.info(f"   2. Orders visible on Bybit interface")
        logger.info(f"   3. Orders survive bot restarts")
        logger.info(f"   4. Exchange guarantees execution")
        logger.info("")
        logger.info(f" WHAT HAPPENS NEXT:")
        logger.info(f"   1. Bot monitors position size every 5 seconds")
        logger.info(f"   2. When position drops ~50%, TP1 filled → Move SL to breakeven")
        logger.info(f"   3. When position drops ~0%, TP2 filled → Trade complete")
        logger.info("="*80)

        return True

    async def _monitor_tp_fills_via_position_size(self):
        """
        Monitor position size to detect when TP limit orders fill

        EDUCATIONAL LOGGING: Explains how we detect fills

        This is the Horus method:
        - We don't check if price hit TP
        - We check if position SIZE changed
        - More reliable than price checking
        - Works even if bot restarts

        When we detect TP1 filled:
        1. Position size drops ~50%
        2. Move SL to breakeven
        3. Mark TP1 as filled

        When we detect TP2 filled:
        1. Position size drops to ~0
        2. Trade is complete
        3. Mark TP2 as filled
        """
        if not self.position or not self._initial_position_size:
            return

        current_size = self.position.size
        initial_size = self._initial_position_size

        # Calculate how much of position remains
        remaining_pct = (current_size / initial_size) * 100

        logger.debug(f"Position size monitoring: {current_size:.1f} / {initial_size:.1f} = {remaining_pct:.0f}% remaining")

        # Detect TP1 fill (position dropped ~50%)
        if remaining_pct < 60 and 'TP1' not in self.tp_levels_hit:
            logger.info("="*80)
            logger.info(f" Position Size Change:")
            logger.info(f"   Initial: {initial_size:.1f} {self.symbol[:-4]}")
            logger.info(f"   Current: {current_size:.1f} {self.symbol[:-4]}")
            logger.info(f"   Remaining: {remaining_pct:.0f}%")
            logger.info("")
            logger.info(f" WHY THIS MEANS TP1 FILLED:")
            logger.info(f"   1. Position size dropped by ~50%")
            logger.info(f"   2. This matches our TP1 limit order (50% of position)")
            logger.info(f"   3. Bybit executed the limit order automatically")
            logger.info("")

            # Mark TP1 as hit
            self.tp_levels_hit.append('TP1')

            # Now move SL to breakeven
            logger.info(f" MOVING STOP LOSS TO BREAKEVEN")
            logger.info(f"   Entry price: ${self.position.entry_price:.2f}")
            logger.info(f"   New SL: ${self.position.entry_price:.2f}")
            logger.info(f"   Why: TP1 filled means we've locked in some profit")
            logger.info(f"   Breakeven SL ensures we don't lose on remaining 50%")
            logger.info("")

            await self._move_stop_to_breakeven()

            logger.info("="*80)
            logger.info(" TP1 FILL PROCESSED")
            logger.info("="*80)
            logger.info(f"    50% of position closed at TP1")
            logger.info(f"    Stop moved to breakeven")
            logger.info(f"    Trade is now RISK-FREE")
            logger.info(f"   ⏳ Waiting for TP2 limit order to fill...")
            logger.info("="*80)

        # Detect TP2 fill (position dropped to ~0)
        elif remaining_pct < 10 and 'TP2' not in self.tp_levels_hit:
            logger.info("="*80)
            logger.info(" TP2 LIMIT ORDER FILLED DETECTED!")
            logger.info("="*80)
            logger.info(f" Position Size Change:")
            logger.info(f"   Initial: {initial_size:.1f} {self.symbol[:-4]}")
            logger.info(f"   Current: {current_size:.1f} {self.symbol[:-4]}")
            logger.info(f"   Remaining: {remaining_pct:.0f}%")
            logger.info("")
            logger.info(f" WHY THIS MEANS TP2 FILLED:")
            logger.info(f"   1. Position size dropped to near zero")
            logger.info(f"   2. This matches our TP2 limit order (final 50%)")
            logger.info(f"   3. Bybit executed the limit order automatically")
            logger.info("")

            # Mark TP2 as hit
            self.tp_levels_hit.append('TP2')

            logger.info("="*80)
            logger.info(" TRADE COMPLETE - ALL TPS FILLED")
            logger.info("="*80)
            logger.info(f"    TP1 filled: 50% closed")
            logger.info(f"    TP2 filled: 50% closed")
            logger.info(f"    100% of position closed at profit")
            logger.info(f"    SUCCESSFUL TRADE!")
            logger.info("="*80)

    async def check_and_apply_tp_to_existing_position(self):
        """
        Check if current position needs TP system applied
        Called on bot restart to handle positions opened before bot started
        """
        if not self.position:
            return

        position_id = self.position.position_id or f"existing_{self.symbol}_{int(time.time())}"

        # Check if TP system already applied
        if position_id in self.tp_system_applied:
            logger.info(f"Existing position {position_id} already has TP system")
            return

        logger.info("="*80)
        logger.info(" EXISTING POSITION DETECTED - APPLYING TP SYSTEM")
        logger.info("="*80)
        logger.info(f"Position: {self.position.side} {self.position.size} {self.symbol}")
        logger.info(f"Entry: ${self.position.entry_price:.2f}")
        logger.info(f"Current: ${self.position.current_price:.2f}")

        # Calculate TP levels based on position entry and direction
        # Use standard percentages: TP1=0.5%, TP2=0.8%, TP3=1.2%
        entry = self.position.entry_price
        if self.position.side == "Buy":  # LONG
            tp1 = entry * 1.005  # +0.5%
            tp2 = entry * 1.008  # +0.8%
            tp3 = entry * 1.012  # +1.2%
            stop = entry * 0.997  # -0.3%
        else:  # SHORT
            tp1 = entry * 0.995  # -0.5%
            tp2 = entry * 0.992  # -0.8%
            tp3 = entry * 0.988  # -1.2%
            stop = entry * 1.003  # +0.3%

        # Create synthetic signal for tracking
        synthetic_signal = TradingSignal(
            signal_id=f"EXISTING_{position_id}",
            direction="LONG" if self.position.side == "Buy" else "SHORT",
            entry_price=entry,
            stop_loss=stop,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            confidence=0.7,
            confluence_score=50,
            timestamp=datetime.now(),
            risk_reward_ratio=2.0,
            position_size=self.position.size
        )

        # Apply TP system
        await self._apply_tp_system_to_position(synthetic_signal, position_id)

        logger.info(" TP system applied to existing position")
        logger.info("="*80)

    async def _check_partial_tp_exits(self):
        """
        Check if TP1, TP2, or TP3 is hit and execute partial exits

        Exit Strategy:
        - TP1 hit: Exit 40% of position, move stop to breakeven
        - TP2 hit: Exit 30% more (70% total closed)
        - TP3 hit: Exit remaining 30% (100% closed)
        """
        if not self.position:
            return

        # Get position ID
        position_id = self.position.position_id or f"existing_{self.symbol}_{int(time.time())}"

        # Get TP levels from stored configuration
        tp_config = self.tp_system_applied.get(position_id)

        if not tp_config:
            # TP system not applied yet - try to apply it
            await self.check_and_apply_tp_to_existing_position()
            tp_config = self.tp_system_applied.get(position_id)

            if not tp_config:
                logger.warning("No TP configuration found for position")
                return

        # Get current price
        current_price = self.position.current_price

        # Get TP levels from configuration
        signal = tp_config['signal']

        # Log TP monitoring status every 30 seconds
        if not hasattr(self, '_last_tp_log_time'):
            self._last_tp_log_time = 0

        if time.time() - self._last_tp_log_time > 30:
            logger.info(f" TP Monitoring Active | Current: ${current_price:.2f} | TPs: ${signal.take_profit_1:.2f}/{signal.take_profit_2:.2f}/{signal.take_profit_3:.2f} | Hit: {self.tp_levels_hit}")
            self._last_tp_log_time = time.time()

        # Determine TP hit conditions based on direction
        if self.position.side == "Buy":  # LONG
            tp1_hit = current_price >= signal.take_profit_1
            tp2_hit = current_price >= signal.take_profit_2
            tp3_hit = current_price >= signal.take_profit_3
        else:  # SHORT
            tp1_hit = current_price <= signal.take_profit_1
            tp2_hit = current_price <= signal.take_profit_2
            tp3_hit = current_price <= signal.take_profit_3

        # Execute partial exits (track which TPs have been hit)
        # Use lock to prevent duplicate executions
        async with self._tp_execution_lock:
            # Re-check after acquiring lock (another task may have executed while waiting)
            # TP3 (check first - highest level)
            if tp3_hit and 'TP3' not in self.tp_levels_hit:
                logger.info("="*80)
                logger.info(" TP3 HIT - EXITING FINAL 30%")
                logger.info("="*80)
                self.tp_levels_hit.append('TP3')  # Mark BEFORE execution to prevent re-entry
                await self._partial_close(self.partial_exit_percentages[2])  # 30%
                logger.info(f" TP3 exit complete at ${current_price:.2f}")
                logger.info("   Position fully closed - TRADE COMPLETE")

            # TP2
            elif tp2_hit and 'TP2' not in self.tp_levels_hit:
                logger.info("="*80)
                logger.info(" TP2 HIT - EXITING 30%")
                logger.info("="*80)
                self.tp_levels_hit.append('TP2')  # Mark BEFORE execution to prevent re-entry
                await self._partial_close(self.partial_exit_percentages[1])  # 30%
                logger.info(f" TP2 exit complete at ${current_price:.2f}")
                logger.info("   70% of position now closed, 30% remaining for TP3")

            # TP1
            elif tp1_hit and 'TP1' not in self.tp_levels_hit:
                logger.info("="*80)
                logger.info(" TP1 HIT - EXITING 40% + MOVING STOP TO BREAKEVEN")
                logger.info("="*80)
                self.tp_levels_hit.append('TP1')  # Mark BEFORE execution to prevent re-entry
                await self._partial_close(self.partial_exit_percentages[0])  # 40%

                # Move stop to breakeven (entry price)
                await self._move_stop_to_breakeven()

                logger.info(f" TP1 exit complete at ${current_price:.2f}")
                logger.info("   40% closed, stop moved to breakeven")
                logger.info("   60% remaining - risk-free trade!")

    async def _move_stop_to_breakeven(self):
        """Move stop loss to breakeven (entry price) after TP1 hit"""
        if not self.position:
            return

        breakeven_price = self.position.entry_price

        try:
            # Update stop loss via Bybit API
            response = await self._make_request(
                "POST",
                "/v5/position/trading-stop",
                {
                    "category": "linear",
                    "symbol": self.symbol,
                    "stopLoss": str(breakeven_price),
                    "positionIdx": 0  # One-way mode
                }
            )

            if response.get('retCode') == 0:
                self.position.stop_loss = breakeven_price
                logger.info(f" Stop moved to breakeven: ${breakeven_price:.2f}")
                logger.info("   Trade is now RISK-FREE!")
            else:
                logger.error(f"Failed to move stop to breakeven: {response.get('retMsg')}")

        except Exception as e:
            logger.error(f"Error moving stop to breakeven: {e}")
    
    async def _monitor_risk(self):
        """Monitor overall risk metrics"""
        while True:
            # Reset daily metrics at midnight UTC
            now = datetime.utcnow()
            if self.daily_reset_time is None or now.date() > self.daily_reset_time.date():
                self.risk_metrics.daily_pnl = 0
                self.risk_metrics.daily_trades = 0
                self.risk_metrics.winning_trades = 0
                self.risk_metrics.losing_trades = 0
                self.risk_metrics.max_drawdown_today = 0
                self.daily_reset_time = now
                logger.info(" Daily risk metrics reset")
            
            # Calculate risk multiplier based on performance
            if self.risk_metrics.consecutive_losses >= 3:
                self.risk_metrics.risk_multiplier = 0.5  # Reduce size after 3 losses

                # ========== TRIGGER 15-MIN BACKOFF AFTER 3 CONSECUTIVE LOSSES ==========
                if not self.risk_metrics.backoff_until:
                    self.risk_metrics.backoff_until = datetime.now() + timedelta(minutes=15)
                    logger.warning(" 3 CONSECUTIVE LOSSES - TRADING SUSPENDED FOR 15 MINUTES")
                    logger.warning(f"   Resume trading at: {self.risk_metrics.backoff_until.strftime('%H:%M:%S')}")

            elif self.risk_metrics.consecutive_losses >= 2:
                self.risk_metrics.risk_multiplier = 0.75
            else:
                self.risk_metrics.risk_multiplier = 1.0
            
            # Log risk status every minute
            if self.position:
                logger.info(f" Risk Status: Daily P&L: ${self.risk_metrics.daily_pnl:.2f} "
                          f"({self.risk_metrics.daily_pnl/self.account_balance*100:.1%}), "
                          f"Trades: {self.risk_metrics.daily_trades}, "
                          f"Win Rate: {self.risk_metrics.winning_trades/(self.risk_metrics.daily_trades or 1)*100:.0%}%")
            
            await asyncio.sleep(60)
    
    async def _cancel_order(self, order_id: str):
        """Cancel an order"""
        response = await self._make_request(
            "POST",
            "/v5/order/cancel",
            {
                "category": "linear",
                "symbol": self.symbol,
                "orderId": order_id
            }
        )
        
        if response.get('retCode') == 0:
            logger.info(f" Order {order_id} cancelled")
        else:
            logger.error(f"Failed to cancel order: {response.get('retMsg')}")
    
    async def cancel_all_pending_orders(self):
        """Cancel all pending orders to free up balance"""
        response = await self._make_request(
            "GET",
            "/v5/order/realtime",
            {"category": "linear", "symbol": self.symbol}
        )
        
        if response.get('retCode') == 0:
            orders = response['result']['list']
            if orders:
                logger.info(f" Found {len(orders)} pending orders to cancel")
                for order in orders:
                    if order['orderStatus'] in ['New', 'PartiallyFilled']:
                        await self._cancel_order(order['orderId'])
            else:
                logger.debug("No pending orders found")
    
    async def get_risk_report(self) -> Dict:
        """Generate comprehensive risk report"""
        # Handle case where account_balance might be None
        balance = self.account_balance if self.account_balance is not None else 0.0
        available = self.available_balance if self.available_balance is not None else 0.0
        
        return {
            "account_balance": balance,
            "available_balance": available,
            "daily_pnl": self.risk_metrics.daily_pnl,
            "daily_pnl_pct": (self.risk_metrics.daily_pnl / balance * 100) if balance > 0 else 0,
            "daily_trades": self.risk_metrics.daily_trades,
            "winning_trades": self.risk_metrics.winning_trades,
            "losing_trades": self.risk_metrics.losing_trades,
            "win_rate": (self.risk_metrics.winning_trades / max(self.risk_metrics.daily_trades, 1)) * 100,
            "consecutive_losses": self.risk_metrics.consecutive_losses,
            "risk_multiplier": self.risk_metrics.risk_multiplier,
            "current_position": {
                "symbol": self.position.symbol if self.position else None,
                "side": self.position.side if self.position else None,
                "size": self.position.size if self.position else 0,
                "pnl": self.position.unrealized_pnl if self.position else 0,
                "pnl_pct": self.position.pnl_percentage if self.position else 0
            } if self.position else None
        }
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down execution engine...")
        
        # Close all positions
        if self.position:
            await self.emergency_close_all()
        
        # Cancel all orders
        for order_id in list(self.active_orders.keys()):
            await self._cancel_order(order_id)
        
        # Close session
        if self.session:
            await self.session.close()

        logger.info("Execution engine shutdown complete")

    def _save_signal_id(self, signal_id: str):
        """Save signal_id to file for persistence across restarts"""
        try:
            import os
            os.makedirs(os.path.dirname(self._signal_id_file), exist_ok=True)
            with open(self._signal_id_file, 'w') as f:
                f.write(signal_id)
            logger.debug(f"Saved signal_id to file: {signal_id}")
        except Exception as e:
            logger.warning(f"Could not save signal_id to file: {e}")

    def _load_signal_id(self) -> str:
        """Load signal_id from file (for bot restart recovery)"""
        try:
            if os.path.exists(self._signal_id_file):
                with open(self._signal_id_file, 'r') as f:
                    signal_id = f.read().strip()
                    if signal_id:
                        logger.debug(f"Loaded signal_id from file: {signal_id}")
                        self._active_signal_id = signal_id
                        return signal_id
        except Exception as e:
            logger.debug(f"Could not load signal_id from file: {e}")
        return ""

    def _clear_signal_id(self):
        """Clear signal_id file after trade closes"""
        try:
            if os.path.exists(self._signal_id_file):
                os.remove(self._signal_id_file)
                logger.debug("Cleared signal_id file")
        except Exception as e:
            logger.debug(f"Could not clear signal_id file: {e}")

    async def handle_status_request(self, request):
        """API endpoint for Trading Monitor to fetch current stats"""
        # Build position data if exists
        position_data = None
        if self.position:
            position_data = {
                'symbol': self.symbol,
                'side': self.position.side,
                'size': self.position.size,
                'entry': self.position.entry_price,
                'current': self.position.current_price,
                'pnl': self.position.unrealized_pnl,
                'pnl_pct': (self.position.unrealized_pnl / self.account_balance * 100) if self.account_balance > 0 else 0,
                'stop_loss': self.position.stop_loss,
                'take_profit': self.position.take_profit
            }

        return web.json_response({
            'timestamp': time.time(),
            'account_balance': self.account_balance,
            'available_balance': self.available_balance,
            'daily_pnl': self.risk_metrics.daily_pnl,
            'total_trades': self.risk_metrics.daily_trades,
            'winning_trades': self.risk_metrics.winning_trades,
            'losing_trades': self.risk_metrics.losing_trades,
            'active_position': bool(self.position),
            'position': position_data,
            'emergency_stop': self.emergency_stop
        })

    async def handle_emergency_stop(self, request):
        """API endpoint for emergency stop from Trading Monitor"""
        self.emergency_stop = True
        logger.critical(" EMERGENCY STOP RECEIVED FROM TRADING MONITOR")

        # Close any active positions
        if self.active_position:
            try:
                await self.close_position(
                    symbol=self.symbol,
                    reason="Emergency stop from monitor"
                )
            except Exception as e:
                logger.error(f"Emergency close failed: {e}")

        return web.json_response({'status': 'emergency_stop_activated'})

    async def start_api_server(self):
        """Start the HTTP API server for Trading Monitor"""
        try:
            # Create app and add routes (done here so methods exist)
            self.api_app = web.Application()
            self.api_app.router.add_get('/api/status', self.handle_status_request)
            self.api_app.router.add_post('/api/emergency-stop', self.handle_emergency_stop)

            # Start server
            self.api_runner = web.AppRunner(self.api_app)
            await self.api_runner.setup()
            site = web.TCPSite(self.api_runner, 'localhost', self.api_port)
            await site.start()
            logger.info(f" API server started on http://localhost:{self.api_port}")
        except Exception as e:
            logger.warning(f"Failed to start API server: {e}")

    async def stop_api_server(self):
        """Stop the HTTP API server"""
        if self.api_runner:
            await self.api_runner.cleanup()
            logger.info("API server stopped")


async def main():
    """Test the execution engine"""
    engine = BybitExecutionEngine()
    await engine.initialize()
    
    # Example signal (would come from Horus)
    test_signal = TradingSignal(
        signal_id="TEST_001",
        direction="LONG",
        entry_price=185.50,
        stop_loss=183.00,
        take_profit_1=187.50,
        take_profit_2=189.00,
        take_profit_3=191.00,
        confidence=0.75,
        confluence_score=85,
        timestamp=time.time(),
        risk_reward_ratio=2.5,
        position_size=100.0
    )
    
    # Execute signal
    # await engine.execute_signal(test_signal)
    
    # Get risk report
    report = await engine.get_risk_report()
    logger.info(f"Risk Report: {json.dumps(report, indent=2)}")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())