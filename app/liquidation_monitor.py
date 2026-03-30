import asyncio
import logging
import time
from collections import deque
import websockets
import json
from binance import AsyncClient

logger = logging.getLogger(__name__)

class LiquidationMonitor:
    """
    Connects to Binance's all-market liquidation stream, filters for a specific
    symbol, and triggers a circuit breaker if the symbol's liquidation volume
    exceeds a dynamic, volume-based threshold.
    """

    def __init__(self, client: AsyncClient, symbol: str, window_seconds: int = 10, threshold_percent: float = 0.01):
        """
        Args:
            client: An authenticated Binance AsyncClient (used for REST API calls).
            symbol: The trading symbol to monitor (e.g., 'SOLUSDT').
            window_seconds: The rolling time window in seconds to aggregate liquidation volume.
            threshold_percent: The percentage of 24h volume to use as the trigger threshold.
        """
        self.client = client
        self.symbol = symbol
        self.window_seconds = window_seconds
        self.threshold_percent = threshold_percent
        
        self.threshold_usd: Optional[float] = None # Will be set asynchronously
        
        self.liquidation_events = deque()
        self._is_emergency_stop_active = False
        self._current_window_volume = 0.0
        self._websocket = None # Renamed from _socket to avoid confusion

    async def _initialize_threshold(self):
        """Fetches 24h volume for the symbol and calculates the dynamic threshold."""
        try:
            logger.info(f"[LiquidationMonitor] Fetching 24h data for {self.symbol} to set dynamic threshold...")
            ticker_data = await self.client.get_ticker(symbol=self.symbol)
            quote_volume = float(ticker_data['quoteVolume'])
            
            self.threshold_usd = quote_volume * self.threshold_percent
            
            logger.info(f"[LiquidationMonitor]  Dynamic threshold for {self.symbol} set to ${self.threshold_usd:,.0f} ({self.threshold_percent:.2%} of 24h volume ${quote_volume:,.0f})")

        except Exception as e:
            logger.error(f"[LiquidationMonitor] CRITICAL: Could not set dynamic liquidation threshold for {self.symbol}. Error: {e}", exc_info=True)
            # Fallback to a reasonable default, but log it as a critical failure
            self.threshold_usd = 2_000_000 # A more conservative default
            logger.warning(f"[LiquidationMonitor] Using a conservative fallback threshold of ${self.threshold_usd:,.0f}")

    def is_emergency_stop_active(self) -> bool:
        """Public method to check if the circuit breaker is active."""
        return self._is_emergency_stop_active

    def get_current_window_volume(self) -> float:
        """Public method to get the current aggregated volume in the window."""
        return self._current_window_volume

    async def _process_message(self, msg_str: str):
        """Callback function to handle incoming liquidation messages."""
        try:
            msg = json.loads(msg_str)
        except json.JSONDecodeError:
            logger.warning(f"[LiquidationMonitor] Could not decode JSON message: {msg_str}")
            return

        if msg.get('e') == 'error':
            logger.error(f"[LiquidationMonitor] Received an error from the stream: {msg['m']}")
            return

        if msg.get('e') == 'forceOrder':
            order_data = msg.get('o')
            if not order_data:
                return

            # --- SYMBOL-DYNAMIC FILTER --- #
            if order_data.get('s') != self.symbol:
                return # Ignore liquidations for other symbols

            try:
                price = float(order_data['p'])
                quantity = float(order_data['q'])
                usd_value = price * quantity
                current_time = time.time()

                self.liquidation_events.append((current_time, usd_value))
                self._current_window_volume += usd_value

                # Educational logging for significant liquidations for THIS symbol
                if self.threshold_usd and usd_value > self.threshold_usd * 0.1: # Log any single liquidation > 10% of our threshold
                    logger.info(f"[Liquidation] DETECTED >10% threshold LIQUIDATION: {order_data['S']} {order_data['s']} for ${usd_value:,.0f}")

            except (KeyError, ValueError) as e:
                logger.warning(f"[LiquidationMonitor] Could not parse liquidation message: {msg}. Error: {e}")

    def _prune_old_events(self):
        """Removes events from the deque that are outside the time window."""
        cutoff_time = time.time() - self.window_seconds
        while self.liquidation_events and self.liquidation_events[0][0] < cutoff_time:
            _, old_value = self.liquidation_events.popleft()
            self._current_window_volume -= old_value

    async def run(self):
        """
        Starts the monitor and runs the main processing loop.
        Uses websockets directly to connect to the Binance Futures liquidation stream.
        """
        await self._initialize_threshold()
        if self.threshold_usd is None:
            logger.critical("[LiquidationMonitor] Could not start, threshold was not initialized.")
            return

        liquidation_ws_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
        logger.info(f"[LiquidationMonitor] Starting... Connecting to {liquidation_ws_url} to filter for {self.symbol}.")

        while True:
            try:
                async with websockets.connect(liquidation_ws_url) as ws:
                    self._websocket = ws
                    logger.info("[LiquidationMonitor]  Successfully connected to liquidation stream.")

                    while True:
                        self._prune_old_events()

                        if self._current_window_volume > self.threshold_usd:
                            if not self._is_emergency_stop_active:
                                logger.critical(f"[EMERGENCY STOP ACTIVATED] {self.symbol} liquidation volume exceeded threshold! Volume: ${self._current_window_volume:,.0f} in {self.window_seconds}s > Threshold: ${self.threshold_usd:,.0f}")
                                self._is_emergency_stop_active = True
                        else:
                            if self._is_emergency_stop_active:
                                logger.info(f"[EMERGENCY STOP DEACTIVATED] {self.symbol} liquidation volume has subsided.")
                                self._is_emergency_stop_active = False

                        try:
                            msg = await asyncio.wait_for(self._websocket.recv(), timeout=1.0)
                            await self._process_message(msg)
                        except asyncio.TimeoutError:
                            continue # No message in 1 second, continue loop to prune old events
                        except websockets.exceptions.ConnectionClosedOK:
                            logger.warning("[LiquidationMonitor] WebSocket connection closed gracefully. Attempting to reconnect...")
                            break # Break inner loop to reconnect
                        except Exception as e:
                            logger.error(f"[LiquidationMonitor] Error receiving message: {e}", exc_info=True)
                            break # Break inner loop to reconnect

            except websockets.exceptions.ConnectionClosedOK:
                logger.warning("[LiquidationMonitor] WebSocket connection closed gracefully. Attempting to reconnect...")
                await asyncio.sleep(5) # Wait before reconnecting
            except Exception as e:
                logger.error(f"[LiquidationMonitor] An error occurred in the main loop: {e}", exc_info=True)
                await asyncio.sleep(10) # Wait before retrying connection

    async def stop(self):
        """Stops the WebSocket connection gracefully."""
        if self._websocket and not self._websocket.closed:
            logger.info("[LiquidationMonitor] Stopping connection...")
            await self._websocket.close()
            self._websocket = None
            logger.info("[LiquidationMonitor] Connection stopped.")

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    async def main():
        load_dotenv()
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')

        if not api_key or not api_secret:
            print("Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables.")
            return

        client = await AsyncClient.create(api_key, api_secret)
        
        # Initialize for a specific symbol (e.g., SOLUSDT)
        # The threshold will be calculated automatically.
        symbol_to_test = "SOLUSDT"
        monitor = LiquidationMonitor(client, symbol=symbol_to_test)
        
        monitor_task = asyncio.create_task(monitor.run())

        try:
            for i in range(120):
                print(f"Checking {symbol_to_test} status... Emergency Stop: {monitor.is_emergency_stop_active()}, Current Window Volume: ${monitor.get_current_window_volume():,.0f} / ${monitor.threshold_usd or 0:,.0f}")
                await asyncio.sleep(1)
        finally:
            await monitor.stop()
            monitor_task.cancel()
            await client.close_connection()

    asyncio.run(main())