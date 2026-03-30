#!/usr/bin/env python3
"""
SOL Market Data Collector for Bot Training
==========================================
Collects comprehensive market data for SOL to understand price movements,
CVD correlations, and market microstructure for bot calibration.

Features:
- Real-time price tracking with microsecond precision
- CVD (Cumulative Volume Delta) calculation and tracking
- Volume profile analysis
- Order flow imbalance detection
- Bid/Ask spread dynamics
- Trade size distribution
- Momentum indicators
- Volatility measurements
- Market regime detection
- Automatic CSV rotation for long-term collection
"""

import asyncio
import aioredis
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
    
    # Price metrics
    price: float
    price_change_1s: float
    price_change_5s: float
    price_change_30s: float
    price_change_1m: float
    price_change_5m: float
    
    # Volume metrics
    volume_1s: float
    volume_5s: float
    volume_30s: float
    volume_1m: float
    buy_volume_1m: float
    sell_volume_1m: float
    
    # CVD metrics
    cvd: float
    cvd_change_1m: float
    cvd_change_5m: float
    cvd_velocity: float  # Rate of CVD change
    cvd_acceleration: float  # Acceleration of CVD
    
    # Order flow metrics
    trade_count_1m: int
    avg_trade_size: float
    large_trade_count: int  # Trades > 10x average
    buy_sell_ratio: float
    order_flow_imbalance: float
    
    # Spread and liquidity
    bid_price: float
    ask_price: float
    spread: float
    spread_percentage: float
    bid_volume: float
    ask_volume: float
    book_imbalance: float
    
    # Momentum indicators
    momentum_1m: float
    momentum_5m: float
    momentum_15m: float
    rsi_14: float
    
    # Volatility metrics
    volatility_1m: float
    volatility_5m: float
    volatility_15m: float
    high_1m: float
    low_1m: float
    range_1m: float
    
    # Market regime
    trend_strength: float  # -1 to 1 (strong down to strong up)
    regime: str  # 'trending_up', 'trending_down', 'ranging', 'volatile'
    volume_regime: str  # 'high', 'normal', 'low'
    
    # Microstructure
    tick_direction: int  # -1, 0, 1
    uptick_count_1m: int
    downtick_count_1m: int
    zero_tick_count_1m: int
    
    # Advanced metrics
    vwap_1m: float
    vwap_deviation: float
    trade_intensity: float  # Trades per second
    dollar_volume_1m: float
    
    # Price levels
    resistance_level: float
    support_level: float
    distance_to_resistance: float
    distance_to_support: float
    
    # Market state flags
    is_breakout: bool
    is_breakdown: bool
    is_accumulation: bool
    is_distribution: bool
    unusual_volume: bool
    unusual_cvd: bool

class SOLMarketDataCollector:
    """Collects and logs comprehensive SOL market data for training"""
    
    def __init__(self, 
                 output_dir: str = "market_data",
                 rotation_hours: int = 6,
                 symbol: str = "SOLUSDT"):
        """
        Initialize the market data collector
        
        Args:
            output_dir: Directory to save CSV files
            rotation_hours: Hours before rotating to new CSV file
            symbol: Trading symbol to track
        """
        self.symbol = symbol.lower()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.rotation_hours = rotation_hours
        
        # Redis connection
        self.redis = None
        
        # Data storage
        self.price_history = deque(maxlen=10000)  # ~2.7 hours at 1/sec
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
        
        # Running calculations
        self.rsi_values = deque(maxlen=14)
        
        # Statistics for monitoring
        self.stats = {
            'total_points': 0,
            'errors': 0,
            'last_save': time.time(),
            'uptime_start': time.time()
        }
        
        self.is_running = True
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = await aioredis.create_redis_pool(
                'redis://localhost:6379',
                encoding='utf-8'
            )
            logger.info("Connected to Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
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
    
    async def _subscribe_to_data(self):
        """Subscribe to Redis channels for market data"""
        pubsub = self.redis.pubsub()
        
        channels = [
            f'trades:{self.symbol}',
            f'analytics:trade:{self.symbol}',
            f'orderbook:{self.symbol}',
            f'analytics:{self.symbol}'
        ]
        
        for channel in channels:
            await pubsub.subscribe(channel)
            
        logger.info(f"Subscribed to channels: {channels}")
        return pubsub
    
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
        """Calculate volume metrics over multiple timeframes"""
        metrics = {
            'volume_1s': 0.0,
            'volume_5s': 0.0,
            'volume_30s': 0.0,
            'volume_1m': 0.0,
            'buy_volume_1m': 0.0,
            'sell_volume_1m': 0.0,
            'trade_count_1m': 0,
            'avg_trade_size': 0.0,
            'large_trade_count': 0,
            'dollar_volume_1m': 0.0
        }
        
        if not self.trade_history:
            return metrics
        
        volumes_1m = []
        
        for trade in reversed(self.trade_history):
            time_diff = current_time - trade['timestamp']
            
            if time_diff <= 1:
                metrics['volume_1s'] += trade['volume']
            if time_diff <= 5:
                metrics['volume_5s'] += trade['volume']
            if time_diff <= 30:
                metrics['volume_30s'] += trade['volume']
            if time_diff <= 60:
                metrics['volume_1m'] += trade['volume']
                metrics['trade_count_1m'] += 1
                volumes_1m.append(trade['volume'])
                metrics['dollar_volume_1m'] += trade['volume'] * trade['price']
                
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
        """Calculate CVD-related metrics"""
        metrics = {
            'cvd': self.current_cvd,
            'cvd_change_1m': 0.0,
            'cvd_change_5m': 0.0,
            'cvd_velocity': 0.0,
            'cvd_acceleration': 0.0
        }
        
        if len(self.cvd_history) < 2:
            return metrics
        
        # Find CVD values at different timeframes
        cvd_1m_ago = None
        cvd_5m_ago = None
        cvd_30s_ago = None
        
        for hist_time, hist_cvd in reversed(self.cvd_history):
            time_diff = current_time - hist_time
            
            if time_diff >= 30 and cvd_30s_ago is None:
                cvd_30s_ago = hist_cvd
            if time_diff >= 60 and cvd_1m_ago is None:
                cvd_1m_ago = hist_cvd
            if time_diff >= 300 and cvd_5m_ago is None:
                cvd_5m_ago = hist_cvd
                break
        
        if cvd_1m_ago is not None:
            metrics['cvd_change_1m'] = self.current_cvd - cvd_1m_ago
            metrics['cvd_velocity'] = metrics['cvd_change_1m'] / 60  # CVD per second
        
        if cvd_5m_ago is not None:
            metrics['cvd_change_5m'] = self.current_cvd - cvd_5m_ago
        
        if cvd_30s_ago is not None and cvd_1m_ago is not None:
            velocity_30s = (self.current_cvd - cvd_30s_ago) / 30
            velocity_1m = (cvd_30s_ago - cvd_1m_ago) / 30
            metrics['cvd_acceleration'] = (velocity_30s - velocity_1m) / 30
        
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
        
        # Calculate RSI
        if len(self.price_history) >= 14:
            prices = [p for _, p in list(self.price_history)[-14:]]
            gains = []
            losses = []
            
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            if gains and losses:
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    metrics['rsi_14'] = 100 - (100 / (1 + rs))
        
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
        prices_5m = []
        prices_15m = []
        
        for hist_time, hist_price in reversed(self.price_history):
            time_diff = current_time - hist_time
            
            if time_diff <= 60:
                prices_1m.append(hist_price)
            if time_diff <= 300:
                prices_5m.append(hist_price)
            if time_diff <= 900:
                prices_15m.append(hist_price)
            else:
                break
        
        if prices_1m:
            metrics['volatility_1m'] = np.std(prices_1m) if len(prices_1m) > 1 else 0
            metrics['high_1m'] = max(prices_1m)
            metrics['low_1m'] = min(prices_1m)
            metrics['range_1m'] = metrics['high_1m'] - metrics['low_1m']
        
        if len(prices_5m) > 1:
            metrics['volatility_5m'] = np.std(prices_5m)
        
        if len(prices_15m) > 1:
            metrics['volatility_15m'] = np.std(prices_15m)
        
        return metrics
    
    def _detect_market_regime(self, price_change_1m: float, volatility_1m: float, 
                            volume_1m: float, avg_volume: float) -> Tuple[str, str, float]:
        """Detect current market regime"""
        # Trend detection
        if abs(price_change_1m) < 0.1:
            regime = 'ranging'
            trend_strength = 0.0
        elif price_change_1m > 0.3:
            regime = 'trending_up'
            trend_strength = min(price_change_1m / 1.0, 1.0)
        elif price_change_1m < -0.3:
            regime = 'trending_down'
            trend_strength = max(price_change_1m / 1.0, -1.0)
        else:
            regime = 'volatile' if volatility_1m > 0.5 else 'ranging'
            trend_strength = price_change_1m / 1.0
        
        # Volume regime
        if volume_1m > avg_volume * 2:
            volume_regime = 'high'
        elif volume_1m < avg_volume * 0.5:
            volume_regime = 'low'
        else:
            volume_regime = 'normal'
        
        return regime, volume_regime, trend_strength
    
    def _update_support_resistance(self, current_price: float, current_time: float):
        """Update support and resistance levels"""
        # Update every 5 minutes
        if current_time - self.last_level_update < 300:
            return
        
        if len(self.price_history) < 100:
            return
        
        prices = [p for _, p in list(self.price_history)[-500:]]
        
        # Simple peak/trough detection for support/resistance
        self.resistance_levels = []
        self.support_levels = []
        
        for i in range(10, len(prices) - 10):
            # Check for local maximum (resistance)
            if all(prices[i] >= prices[i-j] for j in range(1, 6)) and \
               all(prices[i] >= prices[i+j] for j in range(1, 6)):
                self.resistance_levels.append(prices[i])
            
            # Check for local minimum (support)
            if all(prices[i] <= prices[i-j] for j in range(1, 6)) and \
               all(prices[i] <= prices[i+j] for j in range(1, 6)):
                self.support_levels.append(prices[i])
        
        # Keep only significant levels
        if self.resistance_levels:
            self.resistance_levels = sorted(set(self.resistance_levels))[-3:]
        if self.support_levels:
            self.support_levels = sorted(set(self.support_levels))[:3]
        
        self.last_level_update = current_time
    
    def _get_nearest_levels(self, current_price: float) -> Tuple[float, float, float, float]:
        """Get nearest support and resistance levels"""
        resistance = current_price * 1.01  # Default 1% above
        support = current_price * 0.99  # Default 1% below
        
        # Find nearest resistance above current price
        for level in self.resistance_levels:
            if level > current_price:
                resistance = level
                break
        
        # Find nearest support below current price
        for level in reversed(self.support_levels):
            if level < current_price:
                support = level
                break
        
        distance_to_resistance = ((resistance - current_price) / current_price) * 100
        distance_to_support = ((current_price - support) / current_price) * 100
        
        return resistance, support, distance_to_resistance, distance_to_support
    
    def _detect_market_conditions(self, data_point: MarketDataPoint) -> Dict[str, bool]:
        """Detect special market conditions"""
        conditions = {
            'is_breakout': False,
            'is_breakdown': False,
            'is_accumulation': False,
            'is_distribution': False,
            'unusual_volume': False,
            'unusual_cvd': False
        }
        
        # Breakout/breakdown detection
        if data_point.distance_to_resistance < 0.1 and data_point.momentum_1m > 0:
            conditions['is_breakout'] = True
        if data_point.distance_to_support < 0.1 and data_point.momentum_1m < 0:
            conditions['is_breakdown'] = True
        
        # Accumulation/distribution
        if data_point.cvd_change_1m > 0 and data_point.price_change_1m < 0.1:
            conditions['is_accumulation'] = True
        if data_point.cvd_change_1m < 0 and data_point.price_change_1m > -0.1:
            conditions['is_distribution'] = True
        
        # Unusual activity
        avg_volume = np.mean([v for _, v in list(self.volume_history)[-100:]]) if self.volume_history else 0
        if data_point.volume_1m > avg_volume * 3:
            conditions['unusual_volume'] = True
        
        avg_cvd_change = np.mean([abs(c) for _, c in list(self.cvd_history)[-100:]]) if self.cvd_history else 0
        if abs(data_point.cvd_change_1m) > avg_cvd_change * 3:
            conditions['unusual_cvd'] = True
        
        return conditions
    
    async def process_trade(self, message: Dict):
        """Process incoming trade data"""
        try:
            current_time = time.time()
            
            # Extract trade data
            price = float(message.get('price', 0))
            volume = float(message.get('volume', 0) or message.get('quantity', 0))
            side = message.get('side', '').lower()
            
            if price == 0 or volume == 0:
                return
            
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
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
    
    async def process_orderbook(self, message: Dict):
        """Process orderbook data"""
        try:
            current_time = time.time()
            
            # Extract orderbook data
            bids = message.get('bids', [])
            asks = message.get('asks', [])
            
            if not bids or not asks:
                return
            
            bid_price = float(bids[0][0]) if bids else 0
            bid_volume = sum(float(b[1]) for b in bids[:5]) if bids else 0
            
            ask_price = float(asks[0][0]) if asks else 0
            ask_volume = sum(float(a[1]) for a in asks[:5]) if asks else 0
            
            spread = ask_price - bid_price if bid_price and ask_price else 0
            
            self.spread_history.append({
                'timestamp': current_time,
                'bid_price': bid_price,
                'ask_price': ask_price,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'spread': spread
            })
            
        except Exception as e:
            logger.error(f"Error processing orderbook: {e}")
    
    async def collect_data_point(self) -> Optional[MarketDataPoint]:
        """Collect a complete data point"""
        try:
            current_time = time.time()
            
            if not self.price_history or self.last_price == 0:
                return None
            
            # Get latest spread data
            spread_data = self.spread_history[-1] if self.spread_history else {
                'bid_price': self.last_price * 0.9999,
                'ask_price': self.last_price * 1.0001,
                'bid_volume': 0,
                'ask_volume': 0,
                'spread': self.last_price * 0.0002
            }
            
            # Calculate all metrics
            price_changes = self._calculate_price_changes(self.last_price, current_time)
            volume_metrics = self._calculate_volume_metrics(current_time)
            cvd_metrics = self._calculate_cvd_metrics(current_time)
            momentum = self._calculate_momentum(self.last_price, current_time)
            volatility = self._calculate_volatility(current_time)
            
            # Update support/resistance
            self._update_support_resistance(self.last_price, current_time)
            resistance, support, dist_resistance, dist_support = self._get_nearest_levels(self.last_price)
            
            # Detect market regime
            avg_volume = np.mean([v for _, v in list(self.volume_history)[-100:]]) if self.volume_history else volume_metrics['volume_1m']
            regime, volume_regime, trend_strength = self._detect_market_regime(
                price_changes['price_change_1m'],
                volatility['volatility_1m'],
                volume_metrics['volume_1m'],
                avg_volume
            )
            
            # Calculate additional metrics
            buy_sell_ratio = (volume_metrics['buy_volume_1m'] / volume_metrics['sell_volume_1m']) if volume_metrics['sell_volume_1m'] > 0 else 1
            order_flow_imbalance = (volume_metrics['buy_volume_1m'] - volume_metrics['sell_volume_1m']) / (volume_metrics['volume_1m'] + 0.001)
            book_imbalance = (spread_data['bid_volume'] - spread_data['ask_volume']) / (spread_data['bid_volume'] + spread_data['ask_volume'] + 0.001)
            
            # VWAP calculation
            vwap_1m = volume_metrics['dollar_volume_1m'] / (volume_metrics['volume_1m'] + 0.001)
            vwap_deviation = ((self.last_price - vwap_1m) / vwap_1m) * 100 if vwap_1m > 0 else 0
            
            # Trade intensity
            trade_intensity = volume_metrics['trade_count_1m'] / 60.0
            
            # Tick analysis
            upticks = sum(1 for t in self.trade_history if current_time - t['timestamp'] <= 60 and t.get('side') == 'buy')
            downticks = sum(1 for t in self.trade_history if current_time - t['timestamp'] <= 60 and t.get('side') == 'sell')
            zeroticks = volume_metrics['trade_count_1m'] - upticks - downticks
            
            # Create data point
            data_point = MarketDataPoint(
                timestamp=current_time,
                datetime_utc=datetime.utcnow().isoformat(),
                
                # Price metrics
                price=self.last_price,
                **price_changes,
                
                # Volume metrics
                **volume_metrics,
                
                # CVD metrics
                **cvd_metrics,
                
                # Order flow
                buy_sell_ratio=buy_sell_ratio,
                order_flow_imbalance=order_flow_imbalance,
                
                # Spread and liquidity
                bid_price=spread_data['bid_price'],
                ask_price=spread_data['ask_price'],
                spread=spread_data['spread'],
                spread_percentage=(spread_data['spread'] / self.last_price) * 100 if self.last_price > 0 else 0,
                bid_volume=spread_data['bid_volume'],
                ask_volume=spread_data['ask_volume'],
                book_imbalance=book_imbalance,
                
                # Momentum
                **momentum,
                
                # Volatility
                **volatility,
                
                # Market regime
                trend_strength=trend_strength,
                regime=regime,
                volume_regime=volume_regime,
                
                # Microstructure
                tick_direction=1 if upticks > downticks else (-1 if downticks > upticks else 0),
                uptick_count_1m=upticks,
                downtick_count_1m=downticks,
                zero_tick_count_1m=zeroticks,
                
                # Advanced metrics
                vwap_1m=vwap_1m,
                vwap_deviation=vwap_deviation,
                trade_intensity=trade_intensity,
                
                # Price levels
                resistance_level=resistance,
                support_level=support,
                distance_to_resistance=dist_resistance,
                distance_to_support=dist_support,
                
                # Market conditions (will be set below)
                is_breakout=False,
                is_breakdown=False,
                is_accumulation=False,
                is_distribution=False,
                unusual_volume=False,
                unusual_cvd=False
            )
            
            # Detect market conditions
            conditions = self._detect_market_conditions(data_point)
            for key, value in conditions.items():
                setattr(data_point, key, value)
            
            return data_point
            
        except Exception as e:
            logger.error(f"Error collecting data point: {e}")
            self.stats['errors'] += 1
            return None
    
    async def save_data_point(self, data_point: MarketDataPoint):
        """Save data point to CSV"""
        try:
            self._rotate_csv_if_needed()
            
            if self.csv_writer:
                self.csv_writer.writerow(asdict(data_point))
                self.csv_file.flush()  # Ensure data is written
                
                self.data_points_collected += 1
                self.stats['total_points'] += 1
                
                # Log progress every 100 points
                if self.data_points_collected % 100 == 0:
                    uptime = (time.time() - self.stats['uptime_start']) / 3600
                    logger.info(f"Collected {self.data_points_collected} data points | Uptime: {uptime:.2f} hours | Errors: {self.stats['errors']}")
                    
        except Exception as e:
            logger.error(f"Error saving data point: {e}")
            self.stats['errors'] += 1
    
    async def data_collection_loop(self):
        """Main data collection loop"""
        logger.info("Starting data collection loop")
        
        # Initialize CSV
        self._init_csv()
        
        # Subscribe to data
        pubsub = await self._subscribe_to_data()
        
        # Start collecting
        collection_task = asyncio.create_task(self._collect_loop())
        listener_task = asyncio.create_task(self._listen_loop(pubsub))
        
        try:
            await asyncio.gather(collection_task, listener_task)
        except Exception as e:
            logger.error(f"Collection loop error: {e}")
        finally:
            if self.csv_file:
                self.csv_file.close()
    
    async def _collect_loop(self):
        """Loop to collect data points at regular intervals"""
        while self.is_running:
            try:
                # Collect data point every second
                data_point = await self.collect_data_point()
                
                if data_point:
                    await self.save_data_point(data_point)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Collection error: {e}")
                await asyncio.sleep(1)
    
    async def _listen_loop(self, pubsub):
        """Listen to Redis messages"""
        async for message in pubsub.listen():
            try:
                if message['type'] != 'message':
                    continue
                
                data = json.loads(message['data'])
                channel = message['channel']
                
                if 'trade' in channel:
                    await self.process_trade(data)
                elif 'orderbook' in channel:
                    await self.process_orderbook(data)
                    
            except Exception as e:
                logger.error(f"Message processing error: {e}")
    
    def stop(self):
        """Stop the collector"""
        logger.info("Stopping collector...")
        self.is_running = False
        
        # Print final statistics
        uptime = (time.time() - self.stats['uptime_start']) / 3600
        logger.info(f"""
        ==================================================
        COLLECTION STATISTICS
        ==================================================
        Total data points: {self.stats['total_points']}
        Total errors: {self.stats['errors']}
        Uptime: {uptime:.2f} hours
        Success rate: {(1 - self.stats['errors'] / max(self.stats['total_points'], 1)) * 100:.2f}%
        ==================================================
        """)
    
    async def run(self):
        """Main run method"""
        logger.info("""
        ==================================================
        SOL MARKET DATA COLLECTOR
        ==================================================
        Symbol: SOLUSDT
        Output directory: {}
        Rotation interval: {} hours
        Starting collection...
        ==================================================
        """.format(self.output_dir, self.rotation_hours))
        
        # Connect to Redis
        if not await self.connect():
            logger.error("Failed to connect to Redis. Exiting.")
            return
        
        # Start collection
        await self.data_collection_loop()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    if collector:
        collector.stop()
    sys.exit(0)

# Global collector instance for signal handler
collector = None

async def main():
    """Main entry point"""
    global collector
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create collector
    collector = SOLMarketDataCollector(
        output_dir="sol_training_data",
        rotation_hours=6,  # Rotate every 6 hours
        symbol="SOLUSDT"
    )
    
    # Run collector
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