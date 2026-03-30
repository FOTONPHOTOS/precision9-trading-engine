#!/usr/bin/env python3
"""
SOL Market Data Collector - Standalone Version
This version works independently without requiring the Precision9 system
"""

import asyncio
import json
import csv
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
from typing import Dict, List, Optional, Tuple
import numpy as np
import logging
from dataclasses import dataclass, asdict
import signal
import sys

# Try to import Redis, but work without it if needed
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Warning: Redis not available. Will use simulated data mode.")

# Import config
try:
    from config import *
except ImportError:
    # Use defaults if config not found
    REDIS_CONFIG = {'host': 'localhost', 'port': 6379}
    COLLECTION_CONFIG = {'symbol': 'SOLUSDT', 'data_dir': 'sol_training_data', 'rotation_hours': 6}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class MarketDataPoint:
    """Comprehensive market data point for training"""
    timestamp: float
    datetime_utc: str
    price: float
    price_change_1s: float
    price_change_5s: float
    price_change_30s: float
    price_change_1m: float
    price_change_5m: float
    volume_1s: float
    volume_5s: float
    volume_30s: float
    volume_1m: float
    buy_volume_1m: float
    sell_volume_1m: float
    cvd: float
    cvd_change_1m: float
    cvd_change_5m: float
    cvd_velocity: float
    cvd_acceleration: float
    trade_count_1m: int
    avg_trade_size: float
    large_trade_count: int
    buy_sell_ratio: float
    order_flow_imbalance: float
    bid_price: float
    ask_price: float
    spread: float
    spread_percentage: float
    bid_volume: float
    ask_volume: float
    book_imbalance: float
    momentum_1m: float
    momentum_5m: float
    momentum_15m: float
    rsi_14: float
    volatility_1m: float
    volatility_5m: float
    volatility_15m: float
    high_1m: float
    low_1m: float
    range_1m: float
    trend_strength: float
    regime: str
    volume_regime: str
    tick_direction: int
    uptick_count_1m: int
    downtick_count_1m: int
    zero_tick_count_1m: int
    vwap_1m: float
    vwap_deviation: float
    trade_intensity: float
    dollar_volume_1m: float
    resistance_level: float
    support_level: float
    distance_to_resistance: float
    distance_to_support: float
    is_breakout: bool
    is_breakdown: bool
    is_accumulation: bool
    is_distribution: bool
    unusual_volume: bool
    unusual_cvd: bool

class DataSimulator:
    """Simulates market data when Redis is not available"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.base_price = 100.0
        self.last_update = time.time()
        self.cvd = 0.0
        
    def get_next_data(self) -> Dict:
        """Generate simulated market data"""
        current_time = time.time()
        
        # Random walk for price
        price_change = np.random.normal(0, 0.001)
        self.base_price *= (1 + price_change)
        
        # Simulated volume
        volume = abs(np.random.normal(1000, 200))
        
        # Simulated side
        side = 'buy' if np.random.random() > 0.5 else 'sell'
        
        # Update CVD
        if side == 'buy':
            self.cvd += volume
        else:
            self.cvd -= volume
        
        return {
            'type': 'trade',
            'symbol': self.symbol,
            'price': self.base_price,
            'volume': volume,
            'side': side,
            'timestamp': current_time
        }

class SOLMarketDataCollector:
    """Standalone market data collector"""
    
    def __init__(self):
        """Initialize the collector with config settings"""
        self.symbol = COLLECTION_CONFIG.get('symbol', 'SOLUSDT').lower()
        self.output_dir = Path(COLLECTION_CONFIG.get('data_dir', 'sol_training_data'))
        self.output_dir.mkdir(exist_ok=True)
        self.rotation_hours = COLLECTION_CONFIG.get('rotation_hours', 6)
        
        # Redis connection
        self.redis_client = None
        self.pubsub = None
        self.simulator = None
        
        # Data storage
        self.price_history = deque(maxlen=10000)
        self.volume_history = deque(maxlen=10000)
        self.cvd_history = deque(maxlen=10000)
        self.trade_history = deque(maxlen=10000)
        self.spread_history = deque(maxlen=1000)
        
        # Current state
        self.current_cvd = 0.0
        self.last_price = 0.0
        self.session_start = time.time()
        
        # CSV management
        self.csv_file = None
        self.csv_writer = None
        self.last_rotation = time.time()
        self.data_points_collected = 0
        
        # Calculation caches
        self.resistance_levels = []
        self.support_levels = []
        self.last_level_update = 0
        
        # Statistics
        self.stats = {
            'total_points': 0,
            'errors': 0,
            'last_save': time.time(),
            'uptime_start': time.time()
        }
        
        self.is_running = True
        
    def connect_redis(self) -> bool:
        """Connect to Redis if available"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis module not available, using simulation mode")
            self.simulator = DataSimulator(self.symbol)
            return True
            
        try:
            self.redis_client = redis.Redis(
                host=REDIS_CONFIG.get('host', 'localhost'),
                port=REDIS_CONFIG.get('port', 6379),
                decode_responses=True
            )
            
            # Test connection
            self.redis_client.ping()
            
            # Subscribe to channels
            self.pubsub = self.redis_client.pubsub()
            channels = [
                f'trades:{self.symbol}',
                f'analytics:trade:{self.symbol}',
                f'orderbook:{self.symbol}',
                f'analytics:{self.symbol}'
            ]
            
            for channel in channels:
                self.pubsub.subscribe(channel)
                
            logger.info(f"Connected to Redis and subscribed to channels")
            return True
            
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}")
            logger.info("Falling back to simulation mode")
            self.simulator = DataSimulator(self.symbol)
            return True
    
    def _init_csv(self):
        """Initialize new CSV file with headers"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sol_market_data_{timestamp}.csv"
        filepath = self.output_dir / filename
        
        self.csv_file = open(filepath, 'w', newline='', buffering=1)
        self.csv_writer = csv.DictWriter(
            self.csv_file,
            fieldnames=[field.name for field in MarketDataPoint.__dataclass_fields__.values()],
            delimiter=','
        )
        self.csv_writer.writeheader()
        self.last_rotation = time.time()
        
        logger.info(f"Created new CSV file: {filename}")
        return filepath
    
    def _rotate_csv_if_needed(self):
        """Rotate CSV file if needed"""
        if time.time() - self.last_rotation > (self.rotation_hours * 3600):
            if self.csv_file:
                self.csv_file.close()
                logger.info(f"Rotated CSV after {self.rotation_hours} hours")
            self._init_csv()
    
    def process_message(self, message: Dict):
        """Process incoming market data message"""
        try:
            current_time = time.time()
            msg_type = message.get('type', '')
            
            if msg_type == 'trade' or 'trade' in str(message.get('channel', '')):
                # Extract trade data
                price = float(message.get('price', 0))
                volume = float(message.get('volume', 0) or message.get('quantity', 0))
                side = message.get('side', '').lower()
                
                if price > 0 and volume > 0:
                    # Update CVD
                    if side == 'buy':
                        self.current_cvd += volume
                    elif side == 'sell':
                        self.current_cvd -= volume
                    
                    # Store trade
                    self.trade_history.append({
                        'timestamp': current_time,
                        'price': price,
                        'volume': volume,
                        'side': side
                    })
                    
                    # Update price history
                    self.price_history.append((current_time, price))
                    self.volume_history.append((current_time, volume))
                    self.cvd_history.append((current_time, self.current_cvd))
                    
                    self.last_price = price
                    
            elif 'orderbook' in str(message.get('channel', '')):
                # Process orderbook data
                bids = message.get('bids', [])
                asks = message.get('asks', [])
                
                if bids and asks:
                    bid_price = float(bids[0][0]) if bids else 0
                    bid_volume = sum(float(b[1]) for b in bids[:5]) if bids else 0
                    ask_price = float(asks[0][0]) if asks else 0
                    ask_volume = sum(float(a[1]) for a in asks[:5]) if asks else 0
                    
                    self.spread_history.append({
                        'timestamp': current_time,
                        'bid_price': bid_price,
                        'ask_price': ask_price,
                        'bid_volume': bid_volume,
                        'ask_volume': ask_volume,
                        'spread': ask_price - bid_price if bid_price and ask_price else 0
                    })
                    
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.stats['errors'] += 1
    
    def calculate_metrics(self) -> Optional[MarketDataPoint]:
        """Calculate all metrics for current data point"""
        try:
            current_time = time.time()
            
            if not self.price_history or self.last_price == 0:
                return None
            
            # Get price changes
            price_changes = self._calculate_price_changes(self.last_price, current_time)
            
            # Get volume metrics
            volume_metrics = self._calculate_volume_metrics(current_time)
            
            # Get CVD metrics
            cvd_metrics = self._calculate_cvd_metrics(current_time)
            
            # Get other metrics
            momentum = self._calculate_momentum(self.last_price, current_time)
            volatility = self._calculate_volatility(current_time)
            
            # Get spread data
            spread_data = self.spread_history[-1] if self.spread_history else {
                'bid_price': self.last_price * 0.9999,
                'ask_price': self.last_price * 1.0001,
                'bid_volume': 0,
                'ask_volume': 0,
                'spread': self.last_price * 0.0002
            }
            
            # Calculate derived metrics
            buy_sell_ratio = (volume_metrics['buy_volume_1m'] / max(volume_metrics['sell_volume_1m'], 0.001))
            order_flow_imbalance = (volume_metrics['buy_volume_1m'] - volume_metrics['sell_volume_1m']) / max(volume_metrics['volume_1m'], 0.001)
            book_imbalance = (spread_data['bid_volume'] - spread_data['ask_volume']) / max(spread_data['bid_volume'] + spread_data['ask_volume'], 0.001)
            
            # Support/Resistance
            resistance = self.last_price * 1.01
            support = self.last_price * 0.99
            
            # Market regime
            regime = 'ranging'
            if abs(price_changes['price_change_1m']) > 0.3:
                regime = 'trending_up' if price_changes['price_change_1m'] > 0 else 'trending_down'
            
            # Create data point
            return MarketDataPoint(
                timestamp=current_time,
                datetime_utc=datetime.utcnow().isoformat(),
                price=self.last_price,
                **price_changes,
                **volume_metrics,
                **cvd_metrics,
                **momentum,
                **volatility,
                bid_price=spread_data['bid_price'],
                ask_price=spread_data['ask_price'],
                spread=spread_data['spread'],
                spread_percentage=(spread_data['spread'] / self.last_price * 100) if self.last_price > 0 else 0,
                bid_volume=spread_data['bid_volume'],
                ask_volume=spread_data['ask_volume'],
                book_imbalance=book_imbalance,
                buy_sell_ratio=buy_sell_ratio,
                order_flow_imbalance=order_flow_imbalance,
                trend_strength=min(abs(price_changes['price_change_1m']), 1.0) * (1 if price_changes['price_change_1m'] > 0 else -1),
                regime=regime,
                volume_regime='normal',
                tick_direction=0,
                uptick_count_1m=0,
                downtick_count_1m=0,
                zero_tick_count_1m=0,
                vwap_1m=self.last_price,
                vwap_deviation=0,
                trade_intensity=volume_metrics['trade_count_1m'] / 60.0,
                dollar_volume_1m=volume_metrics['volume_1m'] * self.last_price,
                resistance_level=resistance,
                support_level=support,
                distance_to_resistance=((resistance - self.last_price) / self.last_price * 100),
                distance_to_support=((self.last_price - support) / self.last_price * 100),
                is_breakout=False,
                is_breakdown=False,
                is_accumulation=False,
                is_distribution=False,
                unusual_volume=False,
                unusual_cvd=False
            )
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return None
    
    def _calculate_price_changes(self, current_price: float, current_time: float) -> Dict:
        """Calculate price changes over multiple timeframes"""
        changes = {
            'price_change_1s': 0.0,
            'price_change_5s': 0.0,
            'price_change_30s': 0.0,
            'price_change_1m': 0.0,
            'price_change_5m': 0.0
        }
        
        if not self.price_history:
            return changes
        
        for hist_time, hist_price in reversed(self.price_history):
            time_diff = current_time - hist_time
            
            if time_diff >= 1 and changes['price_change_1s'] == 0:
                changes['price_change_1s'] = ((current_price - hist_price) / hist_price) * 100
            if time_diff >= 5 and changes['price_change_5s'] == 0:
                changes['price_change_5s'] = ((current_price - hist_price) / hist_price) * 100
            if time_diff >= 30 and changes['price_change_30s'] == 0:
                changes['price_change_30s'] = ((current_price - hist_price) / hist_price) * 100
            if time_diff >= 60 and changes['price_change_1m'] == 0:
                changes['price_change_1m'] = ((current_price - hist_price) / hist_price) * 100
            if time_diff >= 300 and changes['price_change_5m'] == 0:
                changes['price_change_5m'] = ((current_price - hist_price) / hist_price) * 100
                break
        
        return changes
    
    def _calculate_volume_metrics(self, current_time: float) -> Dict:
        """Calculate volume metrics"""
        metrics = {
            'volume_1s': 0.0,
            'volume_5s': 0.0,
            'volume_30s': 0.0,
            'volume_1m': 0.0,
            'buy_volume_1m': 0.0,
            'sell_volume_1m': 0.0,
            'trade_count_1m': 0,
            'avg_trade_size': 0.0,
            'large_trade_count': 0
        }
        
        if not self.trade_history:
            return metrics
        
        volumes_1m = []
        
        for trade in reversed(self.trade_history):
            time_diff = current_time - trade['timestamp']
            
            if time_diff <= 60:
                metrics['volume_1m'] += trade['volume']
                metrics['trade_count_1m'] += 1
                volumes_1m.append(trade['volume'])
                
                if trade.get('side') == 'buy':
                    metrics['buy_volume_1m'] += trade['volume']
                else:
                    metrics['sell_volume_1m'] += trade['volume']
            else:
                break
        
        if volumes_1m:
            metrics['avg_trade_size'] = np.mean(volumes_1m)
            large_threshold = metrics['avg_trade_size'] * 10
            metrics['large_trade_count'] = sum(1 for v in volumes_1m if v > large_threshold)
        
        return metrics
    
    def _calculate_cvd_metrics(self, current_time: float) -> Dict:
        """Calculate CVD metrics"""
        metrics = {
            'cvd': self.current_cvd,
            'cvd_change_1m': 0.0,
            'cvd_change_5m': 0.0,
            'cvd_velocity': 0.0,
            'cvd_acceleration': 0.0
        }
        
        if len(self.cvd_history) < 2:
            return metrics
        
        for hist_time, hist_cvd in reversed(self.cvd_history):
            time_diff = current_time - hist_time
            
            if time_diff >= 60:
                metrics['cvd_change_1m'] = self.current_cvd - hist_cvd
                metrics['cvd_velocity'] = metrics['cvd_change_1m'] / 60
            if time_diff >= 300:
                metrics['cvd_change_5m'] = self.current_cvd - hist_cvd
                break
        
        return metrics
    
    def _calculate_momentum(self, current_price: float, current_time: float) -> Dict:
        """Calculate momentum indicators"""
        metrics = {
            'momentum_1m': 0.0,
            'momentum_5m': 0.0,
            'momentum_15m': 0.0,
            'rsi_14': 50.0
        }
        
        if not self.price_history:
            return metrics
        
        for hist_time, hist_price in reversed(self.price_history):
            time_diff = current_time - hist_time
            
            if time_diff >= 60 and metrics['momentum_1m'] == 0:
                metrics['momentum_1m'] = current_price - hist_price
            if time_diff >= 300 and metrics['momentum_5m'] == 0:
                metrics['momentum_5m'] = current_price - hist_price
            if time_diff >= 900 and metrics['momentum_15m'] == 0:
                metrics['momentum_15m'] = current_price - hist_price
                break
        
        return metrics
    
    def _calculate_volatility(self, current_time: float) -> Dict:
        """Calculate volatility metrics"""
        metrics = {
            'volatility_1m': 0.0,
            'volatility_5m': 0.0,
            'volatility_15m': 0.0,
            'high_1m': 0.0,
            'low_1m': 0.0,
            'range_1m': 0.0
        }
        
        if not self.price_history:
            return metrics
        
        prices_1m = []
        
        for hist_time, hist_price in reversed(self.price_history):
            if current_time - hist_time <= 60:
                prices_1m.append(hist_price)
            else:
                break
        
        if prices_1m:
            metrics['volatility_1m'] = np.std(prices_1m) if len(prices_1m) > 1 else 0
            metrics['high_1m'] = max(prices_1m)
            metrics['low_1m'] = min(prices_1m)
            metrics['range_1m'] = metrics['high_1m'] - metrics['low_1m']
        
        return metrics
    
    def save_data_point(self, data_point: MarketDataPoint):
        """Save data point to CSV"""
        try:
            self._rotate_csv_if_needed()
            
            if self.csv_writer:
                self.csv_writer.writerow(asdict(data_point))
                self.csv_file.flush()
                
                self.data_points_collected += 1
                self.stats['total_points'] += 1
                
                # Log progress
                if self.data_points_collected % 100 == 0:
                    uptime = (time.time() - self.stats['uptime_start']) / 3600
                    logger.info(f"Collected {self.data_points_collected} points | Uptime: {uptime:.2f}h | Errors: {self.stats['errors']}")
                    
        except Exception as e:
            logger.error(f"Error saving data point: {e}")
            self.stats['errors'] += 1
    
    async def collection_loop(self):
        """Main collection loop"""
        logger.info("Starting collection loop...")
        
        # Initialize CSV
        self._init_csv()
        
        while self.is_running:
            try:
                # Get data (from Redis or simulator)
                if self.simulator:
                    # Simulated data
                    message = self.simulator.get_next_data()
                    self.process_message(message)
                elif self.pubsub:
                    # Real data from Redis
                    message = self.pubsub.get_message(timeout=0.1)
                    if message and message['type'] == 'message':
                        data = json.loads(message['data'])
                        self.process_message(data)
                
                # Calculate and save metrics every second
                if time.time() - self.stats.get('last_collection', 0) >= 1:
                    data_point = self.calculate_metrics()
                    if data_point:
                        self.save_data_point(data_point)
                    self.stats['last_collection'] = time.time()
                
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop the collector"""
        logger.info("Stopping collector...")
        self.is_running = False
        
        if self.csv_file:
            self.csv_file.close()
        
        # Print statistics
        uptime = (time.time() - self.stats['uptime_start']) / 3600
        logger.info(f"""
        ==================================================
        COLLECTION COMPLETE
        Total points: {self.stats['total_points']}
        Total errors: {self.stats['errors']}
        Uptime: {uptime:.2f} hours
        Data saved to: {self.output_dir}
        ==================================================
        """)
    
    async def run(self):
        """Main run method"""
        logger.info("""
        ==================================================
        SOL MARKET DATA COLLECTOR (Standalone)
        Symbol: {}
        Output: {}
        Rotation: {} hours
        ==================================================
        """.format(self.symbol.upper(), self.output_dir, self.rotation_hours))
        
        # Connect to Redis
        self.connect_redis()
        
        # Start collection
        await self.collection_loop()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    if collector:
        collector.stop()
    sys.exit(0)

# Global collector instance
collector = None

async def main():
    """Main entry point"""
    global collector
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run collector
    collector = SOLMarketDataCollector()
    
    try:
        await collector.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        collector.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        collector.stop()

if __name__ == "__main__":
    asyncio.run(main())