import asyncio
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

from exchange_client import BybitClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MarketDataCapture:
    def __init__(self, symbols=['BTCUSDT']):
        self.client = BybitClient()
        self.symbols = symbols
        self.data_buffer = {}
        self.captured_data = []
        self.start_time = None
        self.five_min_candle_start_time = None
        self.signal_received = False
        self.signal_data = None
        self.is_running = False

    async def initialize(self):
        await self.client.initialize()
        logger.info("Market data capture initialized")

    async def start_capture(self):
        """Start capturing market data for a signal cycle until a 5m candle closes"""
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        logger.info(f"Starting market data capture for symbols: {self.symbols}")
        
        # Get initial 5m candle to establish baseline
        initial_5m_kline = await self.client.get_klines('BTCUSDT', '5', 1)
        if initial_5m_kline:
            # Get the start time of the current 5m candle (timestamp at the beginning of the candle)
            self.five_min_candle_start_time = int(initial_5m_kline[0][0])
            logger.info(f"Current 5m candle started at: {datetime.fromtimestamp(self.five_min_candle_start_time/1000, tz=timezone.utc)}")

        # Start data collection
        tasks = []
        for symbol in self.symbols:
            tasks.append(self.capture_for_symbol(symbol))
        
        await asyncio.gather(*tasks)

    async def capture_for_symbol(self, symbol):
        """Main capture loop for a single symbol"""
        logger.info(f"Starting capture for {symbol}")
        
        while self.is_running:
            try:
                # Capture all market data
                snapshot = await self.capture_single_snapshot(symbol)
                self.captured_data.append({
                    'timestamp': time.time(),
                    'utc_time': datetime.now(timezone.utc).isoformat(),
                    'symbol': symbol,
                    'data': snapshot
                })
                
                # Check if 5m candle has closed since we started
                if await self.has_five_min_candle_closed():
                    logger.info("5-minute candle has closed. Stopping capture.")
                    self.is_running = False
                    break
                
                # Sleep for a short interval (e.g., 100ms) to avoid overwhelming the API
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error capturing data for {symbol}: {e}")
                await asyncio.sleep(1)  # Brief pause on error

    async def capture_single_snapshot(self, symbol):
        """Capture all relevant market data for a single moment in time"""
        snapshot = {}
        
        try:
            # Get kline data (1m, 5m)
            snapshot['klines_1m'] = await self.client.get_klines(symbol, '1', 10)  # Last 10 minutes
            snapshot['klines_5m'] = await self.client.get_klines(symbol, '5', 5)   # Last 5 5m candles
            
            # Get orderbook
            snapshot['orderbook'] = await self.client.get_orderbook(symbol, 100)
            
            # Get recent trades
            snapshot['recent_trades'] = await self.client.get_public_trades(symbol, 200)
            
            # Get current price and market data
            snapshot['current_price'] = await self.client.get_current_price(symbol)
            
            # Additional market data
            snapshot['ticker'] = await self.client._send_request("GET", "/v5/market/tickers", {
                "category": "linear", 
                "symbol": symbol
            })
            
        except Exception as e:
            logger.error(f"Error in single snapshot for {symbol}: {e}")
            # Return empty snapshot on error to avoid breaking the capture
            snapshot = {
                'klines_1m': None,
                'klines_5m': None,
                'orderbook': None,
                'recent_trades': None,
                'current_price': None,
                'ticker': None
            }
        
        return snapshot

    async def has_five_min_candle_closed(self):
        """Check if the current 5-minute candle has closed"""
        if not self.five_min_candle_start_time:
            return False
            
        current_time_ms = int(time.time() * 1000)
        expected_candle_end_time = self.five_min_candle_start_time + (5 * 60 * 1000)  # 5 minutes in milliseconds
        
        return current_time_ms > expected_candle_end_time

    async def inject_signal(self, signal_data):
        """Method to inject a signal and start capture from that point"""
        self.signal_received = True
        self.signal_data = signal_data
        logger.info(f"Signal received: {signal_data}")
        # Could also reset the start time to when the signal is received
        # self.start_time = datetime.now(timezone.utc)

    def save_data(self, filename=None):
        """Save captured data to a file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"market_data_capture_{timestamp}.json"
        
        filepath = Path(filename)
        with open(filepath, 'w') as f:
            json.dump(self.captured_data, f, indent=2, default=str)
        
        logger.info(f"Captured {len(self.captured_data)} snapshots saved to {filename}")
        return filepath

    async def stop_capture(self):
        """Stop the capture and save data"""
        self.is_running = False
        filepath = self.save_data()
        await self.client.close()
        logger.info(f"Capture stopped. Data saved to {filepath}")


async def main():
    """Example usage"""
    capture = MarketDataCapture(['BTCUSDT'])  # Starting with BTC as requested
    
    try:
        await capture.initialize()
        logger.info("Starting market data capture for BTC...")
        
        # Start the capture (runs for up to 5 minutes or until 5m candle closes)
        await capture.start_capture()
        
        # Save the captured data
        await capture.stop_capture()
        
    except KeyboardInterrupt:
        logger.info("Capture interrupted by user")
        await capture.stop_capture()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        await capture.stop_capture()


if __name__ == "__main__":
    asyncio.run(main())