import hmac
import hashlib
import time
import json
import logging
from typing import Optional, Dict, Any, Tuple

import aiohttp

from config import BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_SESSION

logger = logging.getLogger(__name__)

class BybitClient:
    """A dedicated client for all Bybit API interactions."""

    def __init__(self):
        self.api_key = BYBIT_API_KEY
        self.api_secret = BYBIT_API_SECRET
        self.is_testnet = BYBIT_SESSION == "bybit_test"
        self.base_url = "https://api-testnet.bybit.com" if self.is_testnet else "https://api.bybit.com"
        self.session: Optional[aiohttp.ClientSession] = None
        self.time_offset = 0

    async def initialize(self):
        """Initializes the aiohttp session and syncs server time."""
        self.session = aiohttp.ClientSession()
        await self._sync_server_time()
        logger.info(f"Bybit Client initialized for {'Testnet' if self.is_testnet else 'Mainnet'}.")

    async def close(self):
        """Closes the aiohttp session."""
        if self.session:
            await self.session.close()
            logger.info("Bybit Client session closed.")

    def _generate_signature(self, timestamp: str, recv_window: str, payload: str) -> str:
        """Generates the API signature for a request."""
        param_str = f"{timestamp}{self.api_key}{recv_window}{payload}"
        return hmac.new(self.api_secret.encode('utf-8'), param_str.encode('utf-8'), hashlib.sha256).hexdigest()

    async def _sync_server_time(self):
        """Syncs local time with Bybit server time to prevent timestamp errors."""
        try:
            async with self.session.get(f"{self.base_url}/v5/market/time") as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} error when syncing time: {response.reason}")
                    return
                result = await response.json()
                if result and result.get('retCode') == 0:
                    server_time_info = result.get('result', {})
                    time_nano = server_time_info.get('timeNano')
                    if time_nano:
                        server_time = int(time_nano) // 1000000
                        local_time = int(time.time() * 1000)
                        self.time_offset = server_time - local_time
                        logger.info(f"Bybit server time offset is {self.time_offset}ms.")
                    else:
                        logger.error("Invalid time response format from Bybit")
                else:
                    if result:
                        logger.error(f"Failed to sync time with Bybit: {result.get('retMsg')}")
                    else:
                        logger.error("Failed to sync time with Bybit: Response is None")
        except Exception as e:
            logger.error(f"Error syncing Bybit time: {e}")

    async def _send_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Sends an authenticated request to the Bybit API."""
        if not self.session:
            raise RuntimeError("Client session not initialized. Call initialize() first.")

        timestamp = str(int(time.time() * 1000) + self.time_offset)
        recv_window = "20000" # Recommended by Bybit

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }

        try:
            if method == "GET":
                query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())]) if params else ""
                signature = self._generate_signature(timestamp, recv_window, query_string)
                headers["X-BAPI-SIGN"] = signature
                url = f"{self.base_url}{endpoint}?{query_string}" if query_string else f"{self.base_url}{endpoint}"
                async with self.session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"HTTP {response.status} error for {method} {endpoint}: {response.reason}")
                        return None
                    return await response.json()
            else: # POST
                body = json.dumps(params) if params else "{}"
                signature = self._generate_signature(timestamp, recv_window, body)
                headers["X-BAPI-SIGN"] = signature
                url = f"{self.base_url}{endpoint}"
                async with self.session.post(url, data=body, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"HTTP {response.status} error for {method} {endpoint}: {response.reason}")
                        return None
                    return await response.json()
        except Exception as e:
            logger.error(f"Error sending request to {endpoint}: {e}")
            return None

    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetches the current position for a given symbol."""
        params = {"category": "linear", "symbol": symbol}
        response = await self._send_request("GET", "/v5/position/list", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                position_list = result.get('list', [])
                if position_list:
                    position_data = position_list[0]
                    if float(position_data.get('size', 0)) > 0:
                        return position_data
        return None

    async def get_all_open_positions(self) -> list[Dict[str, Any]]:
        """Fetches all open positions across the account."""
        params = {"category": "linear", "settleCoin": "USDT"}
        response = await self._send_request("GET", "/v5/position/list", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                all_positions = result.get('list', [])
                # Filter for positions that actually have a size
                open_positions = [p for p in all_positions if float(p.get('size', 0)) > 0]
                return open_positions
        return []

    async def get_leverage(self, symbol: str) -> Optional[float]:
        """Fetches the current leverage for a given symbol."""
        params = {"category": "linear", "symbol": symbol}
        response = await self._send_request("GET", "/v5/position/list", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                position_list = result.get('list', [])
                if position_list:
                    # Leverage is the same for both long and short in one-way mode
                    leverage = position_list[0].get('leverage')
                    if leverage:
                        return float(leverage)
        logger.warning(f"Could not fetch leverage for {symbol}, response: {response}")
        return None

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Sets the leverage for a given symbol."""
        # According to Bybit API, leverage can be set with these parameters
        params = {
            "category": "linear",
            "symbol": symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage),
        }
        response = await self._send_request("POST", "/v5/position/set-leverage", params)

        if response and response.get('retCode') == 0:
            logger.info(f"Successfully set leverage for {symbol} to {leverage}x")
            return True
        else:
            ret_msg = response.get('retMsg', 'No response') if response else 'No response'

            # Handle common scenarios where leverage setting isn't critical
            if ("leverage not modified" in ret_msg.lower() or
                "same value" in ret_msg.lower() or
                "reduce-only" in ret_msg.lower() or
                "position" in ret_msg.lower() or
                "invalid" in ret_msg.lower()):

                # These are typically not fatal errors and may happen under certain conditions
                # For example, if there's an open position, leverage cannot be changed
                logger.warning(f"Note: Could not set leverage for {symbol} ({leverage}x): {ret_msg}. This is normal if positions exist or settings are already configured.")
                return True  # Return True to allow trading to continue

            else:
                logger.error(f"Failed to set leverage for {symbol} after retries: {ret_msg}")
                return False

    async def place_order(self, symbol: str, direction: str, qty: float, order_type: str = "Market", price: Optional[float] = None, stop_loss: Optional[float] = None, take_profit: Optional[float] = None, reduce_only: Optional[bool] = None, position_idx: Optional[int] = None) -> Dict[str, Any]:
        """Places an order on Bybit."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "orderType": order_type,
            "qty": str(qty),
        }

        # Determine side based on direction and if it's a closing order
        side = "Buy" if direction == "LONG" else "Sell"
        if reduce_only:
            side = "Sell" if side == "Buy" else "Buy"
        params["side"] = side

        if order_type == "Limit":
            params["price"] = str(price)
        if stop_loss:
            params["stopLoss"] = str(stop_loss)
        if take_profit:
            params["takeProfit"] = str(take_profit)
        if reduce_only is not None:
            params["reduceOnly"] = reduce_only
        if position_idx is not None:
            # Bybit API expects positionIdx as 0 for one-way mode, or 1/2 for hedge mode
            params["positionIdx"] = position_idx
        
        return await self._send_request("POST", "/v5/order/create", params)

    async def modify_stop_loss(self, symbol: str, new_sl_price: float) -> Dict[str, Any]:
        """Modifies the stop loss for an open position."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "stopLoss": str(new_sl_price),
            "positionIdx": 0 # For one-way mode
        }
        return await self._send_request("POST", "/v5/position/trading-stop", params)

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancels an active order."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
        }
        logger.info(f"Attempting to cancel order {order_id} for {symbol}")
        return await self._send_request("POST", "/v5/order/cancel", params)

    async def get_order_status(self, symbol: str, order_id: str) -> Optional[Dict[str, Any]]:
        """Fetches the real-time status of a single order."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
        }
        response = await self._send_request("GET", "/v5/order/realtime", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                order_list = result.get('list', [])
                if order_list:
                    return order_list[0]
        return None

    async def close_position_market(self, symbol: str, direction: str, qty: float) -> Dict[str, Any]:
        """Closes a portion or all of a position at market price."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": "Sell" if direction == "LONG" else "Buy", # Opposite side to close
            "orderType": "Market",
            "qty": str(qty),
            "reduceOnly": True
        }
        return await self._send_request("POST", "/v5/order/create", params)

    async def get_klines(self, symbol: str, interval: str, limit: int = 200) -> Optional[list]:
        """Fetches k-line (candle) data from Bybit."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        response = await self._send_request("GET", "/v5/market/kline", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                kline_list = result.get('list', [])
                if kline_list:
                    return kline_list
        else:
            if response:
                logger.error(f"Failed to fetch k-lines for {symbol} {interval}: {response.get('retMsg')}")
            else:
                logger.error(f"Failed to fetch k-lines for {symbol} {interval}: Response is None")

        return None

    async def get_public_trades(self, symbol: str, limit: int = 200) -> Optional[list]:
        """Fetches recent public trade data from Bybit."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "limit": limit
        }
        response = await self._send_request("GET", "/v5/market/recent-trade", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                trade_list = result.get('list', [])
                if trade_list:
                    return trade_list
        else:
            if response:
                logger.error(f"Failed to fetch recent trades for {symbol}: {response.get('retMsg')}")
            else:
                logger.error(f"Failed to fetch recent trades for {symbol}: Response is None")

        return None

    async def get_orderbook(self, symbol: str, limit: int = 100) -> Optional[dict]:
        """Fetches the order book for a given symbol."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "limit": str(limit)
        }
        response = await self._send_request("GET", "/v5/market/orderbook", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                return result
        else:
            if response:
                logger.error(f"Failed to fetch orderbook for {symbol}: {response.get('retMsg')}")
            else:
                logger.error(f"Failed to fetch orderbook for {symbol}: Response is None")

        return None

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Fetches the current mark price for a given symbol."""
        params = {"category": "linear", "symbol": symbol}
        response = await self._send_request("GET", "/v5/market/tickers", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                ticker_list = result.get('list', [])
                if ticker_list:
                    mark_price = ticker_list[0].get('markPrice')
                    if mark_price is not None:
                        return float(mark_price)
        return None

    async def get_closed_pnl_history(self, symbol: str, limit: int = 50) -> list[Dict[str, Any]]:
        """Fetches the closed PnL history for a symbol to reconcile offline trades."""
        params = {
            "category": "linear",
            "symbol": symbol,
            "limit": limit
        }
        response = await self._send_request("GET", "/v5/position/closed-pnl", params)
        if response and response.get('retCode') == 0:
            result = response.get('result')
            if result:
                pnl_list = result.get('list', [])
                if pnl_list:
                    return pnl_list
        else:
            if response:
                logger.error(f"Failed to fetch closed PnL history for {symbol}: {response.get('retMsg')}")
            else:
                logger.error(f"Failed to fetch closed PnL history for {symbol}: Response is None")

        return []

    async def get_available_balance(self) -> float:
        """Fetches the available balance for trading using a robust method."""
        params = {"accountType": "UNIFIED"}
        response = await self._send_request("GET", "/v5/account/wallet-balance", params)

        if response is None:
            logger.error("API Error fetching balance: Response is None. Please check your API key permissions and connectivity.")
            return 0.0

        if response.get('retCode') != 0:
            logger.error(f"API Error fetching balance: {response.get('retMsg', 'Unknown error')}")
            return 0.0

        result = response.get('result', {})
        wallet_list = result.get('list', [])
        
        if not wallet_list:
            logger.error("No wallet data returned from API in get_available_balance")
            return 0.0
        
        wallet = wallet_list[0]
        
        # First, try to get USDT balance from the 'coin' array
        coins = wallet.get('coin', [])
        for coin in coins:
            if coin.get('coin') == 'USDT':
                try:
                    # For position sizing, we want the available balance for new orders
                    # availableToWithdraw represents free cash that can be withdrawn or used for new positions
                    available_to_withdraw_str = str(coin.get('availableToWithdraw', '0'))
                    # availableBalance represents the amount available for new orders
                    available_balance_str = str(coin.get('availableBalance', '0'))  # Newer API field
                    # walletBalance is the total wallet balance (including used margin)
                    wallet_balance_str = str(coin.get('walletBalance', '0'))
                    # equity shows the total equity of the account
                    equity_str = str(coin.get('equity', '0'))

                    # Prioritize availableToWithdraw as it represents truly free margin for new positions
                    available_to_withdraw_float = float(available_to_withdraw_str) if available_to_withdraw_str and available_to_withdraw_str != '0' else 0.0
                    available_balance_float = float(available_balance_str) if available_balance_str and available_balance_str != '0' else available_to_withdraw_float  # Fallback to availableToWithdraw if availableBalance is 0
                    wallet_float = float(wallet_balance_str) if wallet_balance_str else 0.0
                    equity_float = float(equity_str) if equity_str else 0.0

                    # Use availableToWithdraw first (truly free margin), then availableBalance if that's higher
                    if available_to_withdraw_float > 0:
                        balance = available_to_withdraw_float
                    elif available_balance_float > 0:
                        balance = available_balance_float
                    else:
                        # Fallback to wallet balance if neither available field is populated correctly
                        balance = wallet_float

                    if balance > 0:
                        logger.info(f"Found USDT available balance: ${balance:.4f}")
                        return balance
                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing USDT coin balance: {e}")
                    continue
        
        # If USDT not found in coins or has zero balance, use total wallet balance as a fallback
        try:
            total_equity_str = str(wallet.get('totalEquity', '0'))
            total_available_str = str(wallet.get('totalAvailableBalance', '0'))

            total_equity = float(total_equity_str) if total_equity_str else 0.0
            total_available = float(total_available_str) if total_available_str else 0.0
            
            balance = max(total_equity, total_available)
            if balance > 0:
                logger.info(f"Using total wallet balance as fallback: ${balance:.4f}")
                return balance
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing total wallet balance: {e}")

        logger.warning("Could not determine a non-zero available balance.")
        return 0.0

    async def _calculate_and_validate_qty(self, symbol: str, current_price: float, allocated_balance: float) -> str:
        """Calculates and validates the quantity for an order, returning a formatted string to avoid float errors."""
        # 1. Get instrument info (min_qty, qty_step)
        params = {"category": "linear", "symbol": symbol}
        response = await self._send_request("GET", "/v5/market/instruments-info", params)
        if not response or response.get('retCode') != 0:
            if response:
                logger.error(f"Failed to get instrument info for {symbol}: {response.get('retMsg')}")
            else:
                logger.error(f"Failed to get instrument info for {symbol}: Response is None")
            return "0.0"

        result = response.get('result')
        if not result:
            logger.error(f"Invalid response format for instrument info for {symbol}")
            return "0.0"

        instrument_list = result.get('list', [])
        if not instrument_list:
            logger.error(f"No instrument info found for {symbol}")
            return "0.0"

        instrument_info = instrument_list[0]
        lot_size_filter = instrument_info.get('lotSizeFilter')
        if not lot_size_filter:
            logger.error(f"Lot size filter not found in instrument info for {symbol}")
            return "0.0"

        min_qty = float(lot_size_filter['minOrderQty'])
        qty_step = float(lot_size_filter['qtyStep'])

        # 2. Use the provided allocated_balance
        if allocated_balance == 0:
            logger.warning("Allocated balance is zero. Cannot calculate position size.")
            return "0.0"

        # 3. Calculate desired quantity with leverage awareness
        leverage = await self.get_leverage(symbol)
        if leverage is None:
            logger.warning(f"Could not fetch leverage for {symbol}. Defaulting to 2x.")
            leverage = 2.0 # Default to 2x as per user's current setting
        percentage_of_balance = 0.9 # Use 90% of the allocated chunk
        margin_to_use = allocated_balance * percentage_of_balance  # This is the actual margin we're committing from account
        # Calculate the quantity based on the margin we're committing and the leverage
        # With leverage, we can control a larger position with our margin
        # Quantity = (margin_to_use * leverage) / current_price
        raw_qty = (margin_to_use * leverage) / current_price

        logger.info(f"[SIZE_CALC] Allocated Balance: ${allocated_balance:.2f}, Margin: ${margin_to_use:.2f}, Leverage: {leverage}x, Raw Qty: {raw_qty:.4f}")

        # 4. Adjust to min_qty and round DOWN to the nearest valid qty_step
        if raw_qty < min_qty:
            logger.warning(f"Calculated quantity {raw_qty:.4f} is less than min_qty {min_qty}. Using min_qty.")
            final_qty = min_qty
        else:
            # Use floor division to always round down to a valid lot size
            final_qty = (raw_qty // qty_step) * qty_step

        # 5. Format the quantity to a string with the correct number of decimal places
        qty_step_str = str(qty_step)
        if '.' in qty_step_str:
            decimal_places = len(qty_step_str.split('.')[1])
            formatted_qty = f"{final_qty:.{decimal_places}f}"
        else:
            formatted_qty = f"{final_qty:.0f}"

        # 6. Final check after formatting
        if float(formatted_qty) < min_qty:
            logger.error(f"Formatted quantity {formatted_qty} is below minimum {min_qty}. Trade rejected.")
            return "0.0"

        logger.info(f"[CALCULATE_SIZE] Symbol: {symbol}, Price: {current_price:.4f}, Multiplier: {percentage_of_balance:.1f}, Final Qty: {formatted_qty}")
        return formatted_qty
