"""
Real-Time Price Action Monitor
===============================
Continuously monitors live price action across multiple timeframes
Detects breakouts, tests, rejections as they happen - not just on candle close
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd


@dataclass
class LivePriceAction:
    """Current live price action snapshot"""
    current_price: float
    price_1min_ago: float
    price_5min_ago: float
    price_change_1min: float
    price_change_5min: float

    # Volume surge detection
    current_volume: float
    avg_volume_5min: float
    volume_surge: float  # Ratio of current to average

    # Momentum
    momentum_score: float  # -100 to +100
    velocity: float  # Price change per second

    # Level interaction
    nearest_resistance: Optional[float]
    nearest_support: Optional[float]
    distance_to_resistance_pct: float
    distance_to_support_pct: float

    # Real-time status
    testing_resistance: bool
    testing_support: bool
    breaking_above: bool
    breaking_below: bool
    rejecting_from_resistance: bool
    rejecting_from_support: bool

    timestamp: datetime


@dataclass
class BreakoutSignal:
    """Real-time breakout detection"""
    direction: str  # 'LONG' or 'SHORT'
    level: float
    current_price: float
    strength: float  # 0-100
    volume_confirmation: bool
    momentum_confirmation: bool

    # Breakout quality
    is_loading: bool  # Building up to break
    is_breaking: bool  # Currently breaking
    is_broken: bool  # Clean break confirmed
    is_fake: bool  # Likely false breakout

    confidence: float
    timestamp: datetime


class RealtimePriceMonitor:
    """
    Monitors live price action in real-time
    Tracks multiple timeframes simultaneously
    Detects breakouts, tests, rejections as they happen
    """

    def __init__(self, symbol: str = "SOLUSDT"):
        self.symbol = symbol

        # Price history for multiple timeframes
        self.price_history_1s = []  # Last 60 seconds (real-time)
        self.price_history_1m = []  # Last 60 minutes
        self.price_history_5m = []  # Last 200 candles

        # Key levels from analysis
        self.resistance_levels = []
        self.support_levels = []

        # Breakout tracking
        self.active_breakouts = []

    def get_current_price(self) -> float:
        """Get current live price from Binance"""
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={self.symbol}"
            response = requests.get(url, timeout=2)
            data = response.json()
            return float(data['price'])
        except Exception as e:
            print(f"Error fetching price: {e}")
            return None

    def get_recent_trades(self, limit: int = 100) -> List[Dict]:
        """Get recent trades for volume/momentum analysis"""
        try:
            url = f"https://api.binance.com/api/v3/trades?symbol={self.symbol}&limit={limit}"
            response = requests.get(url, timeout=2)
            return response.json()
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []

    def fetch_kline_data(self, interval: str, limit: int = 200) -> pd.DataFrame:
        """Fetch kline/candle data for any timeframe"""
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={self.symbol}&interval={interval}&limit={limit}"
            response = requests.get(url, timeout=5)
            data = response.json()

            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df
        except Exception as e:
            print(f"Error fetching kline data: {e}")
            return pd.DataFrame()

    def update_key_levels(self, resistance_levels: List[float], support_levels: List[float]):
        """Update key price levels from arsenal analysis"""
        self.resistance_levels = sorted(resistance_levels, reverse=True)
        self.support_levels = sorted(support_levels)

    def calculate_momentum(self, prices: List[Tuple[float, float]]) -> float:
        """
        Calculate momentum score from recent price action
        Returns: -100 to +100 (negative = bearish, positive = bullish)
        """
        if len(prices) < 10:
            return 0.0

        # Look at last 30 seconds
        recent = prices[-30:] if len(prices) >= 30 else prices

        # Count up vs down moves
        up_moves = sum(1 for i in range(1, len(recent)) if recent[i][1] > recent[i-1][1])
        down_moves = sum(1 for i in range(1, len(recent)) if recent[i][1] < recent[i-1][1])

        total_moves = up_moves + down_moves
        if total_moves == 0:
            return 0.0

        # Calculate momentum score
        momentum = ((up_moves - down_moves) / total_moves) * 100

        return momentum

    def detect_volume_surge(self, current_trades: List[Dict], lookback_minutes: int = 5) -> float:
        """
        Detect if current volume is surging
        Returns: Ratio of current to average (1.0 = normal, 2.0 = 2x surge)
        """
        if not current_trades:
            return 1.0

        # Calculate recent volume
        recent_volume = sum(float(t['qty']) for t in current_trades)

        # Get historical average
        df_5m = self.fetch_kline_data('1m', limit=lookback_minutes)
        if df_5m.empty:
            return 1.0

        avg_volume = df_5m['volume'].mean()

        if avg_volume == 0:
            return 1.0

        # Current volume vs average
        surge_ratio = (recent_volume / avg_volume) * (60 / len(current_trades))  # Normalize to 1 minute

        return surge_ratio

    def find_nearest_levels(self, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        """Find nearest resistance above and support below"""
        # Find nearest resistance (above current price)
        resistance = None
        for level in self.resistance_levels:
            if level > current_price:
                resistance = level
                break

        # Find nearest support (below current price)
        support = None
        for level in reversed(self.support_levels):
            if level < current_price:
                support = level
                break

        return resistance, support

    def is_testing_level(self, current_price: float, level: float, threshold_pct: float = 0.15) -> bool:
        """Check if price is testing a key level"""
        distance_pct = abs((current_price - level) / level) * 100
        return distance_pct <= threshold_pct

    def detect_breakout_loading(self, current_price: float, level: float, direction: str) -> bool:
        """
        Detect if a breakout is "loading" (building up to break)

        Signs of loading:
        - Price consolidating near level
        - Volume building
        - Multiple tests of level
        - Momentum in breakout direction
        """
        # Check if price is near the level (within 0.3%)
        distance_pct = abs((current_price - level) / level) * 100
        if distance_pct > 0.3:
            return False

        # Check if we have enough history
        if len(self.price_history_1s) < 30:
            return False

        # Count tests in last 60 seconds
        tests = 0
        for timestamp, price in self.price_history_1s[-60:]:
            if self.is_testing_level(price, level, threshold_pct=0.2):
                tests += 1

        # Multiple tests indicate loading
        return tests >= 3

    def analyze_live_price_action(self, swing_highs: List[Dict], swing_lows: List[Dict]) -> LivePriceAction:
        """Analyze current live price action in real-time"""
        current_price = self.get_current_price()
        if current_price is None:
            return None

        # Record price
        now = datetime.utcnow()
        self.price_history_1s.append((now, current_price))

        # Keep only last 300 seconds (5 minutes)
        cutoff = now - timedelta(seconds=300)
        self.price_history_1s = [(t, p) for t, p in self.price_history_1s if t >= cutoff]

        # Get recent trades for volume analysis
        recent_trades = self.get_recent_trades(limit=50)

        # Calculate metrics
        price_1min_ago = None
        price_5min_ago = None

        if len(self.price_history_1s) >= 60:
            price_1min_ago = self.price_history_1s[-60][1]

        if len(self.price_history_1s) >= 300:
            price_5min_ago = self.price_history_1s[-300][1]

        # Price changes
        price_change_1min = ((current_price - price_1min_ago) / price_1min_ago * 100) if price_1min_ago else 0
        price_change_5min = ((current_price - price_5min_ago) / price_5min_ago * 100) if price_5min_ago else 0

        # Momentum
        momentum = self.calculate_momentum(self.price_history_1s)

        # Velocity (price change per second)
        velocity = price_change_1min / 60 if price_1min_ago else 0

        # Volume surge
        volume_surge = self.detect_volume_surge(recent_trades)

        # Extract levels from swings
        resistance_levels = [h['price'] for h in swing_highs] if swing_highs else []
        support_levels = [l['price'] for l in swing_lows] if swing_lows else []
        self.update_key_levels(resistance_levels, support_levels)

        # Find nearest levels
        nearest_resistance, nearest_support = self.find_nearest_levels(current_price)

        # Calculate distances
        dist_to_resistance = ((nearest_resistance - current_price) / current_price * 100) if nearest_resistance else 999
        dist_to_support = ((current_price - nearest_support) / current_price * 100) if nearest_support else 999

        # Detect level interactions
        testing_resistance = self.is_testing_level(current_price, nearest_resistance) if nearest_resistance else False
        testing_support = self.is_testing_level(current_price, nearest_support) if nearest_support else False

        # Breakout detection
        breaking_above = (current_price > nearest_resistance and dist_to_resistance < 0.3) if nearest_resistance else False
        breaking_below = (current_price < nearest_support and dist_to_support < 0.3) if nearest_support else False

        # Rejection detection (price moved away from level after test)
        rejecting_from_resistance = False
        rejecting_from_support = False

        if testing_resistance and momentum < -20:
            rejecting_from_resistance = True
        if testing_support and momentum > 20:
            rejecting_from_support = True

        return LivePriceAction(
            current_price=current_price,
            price_1min_ago=price_1min_ago or current_price,
            price_5min_ago=price_5min_ago or current_price,
            price_change_1min=price_change_1min,
            price_change_5min=price_change_5min,
            current_volume=sum(float(t['qty']) for t in recent_trades) if recent_trades else 0,
            avg_volume_5min=0,  # Calculated separately
            volume_surge=volume_surge,
            momentum_score=momentum,
            velocity=velocity,
            nearest_resistance=nearest_resistance,
            nearest_support=nearest_support,
            distance_to_resistance_pct=dist_to_resistance,
            distance_to_support_pct=dist_to_support,
            testing_resistance=testing_resistance,
            testing_support=testing_support,
            breaking_above=breaking_above,
            breaking_below=breaking_below,
            rejecting_from_resistance=rejecting_from_resistance,
            rejecting_from_support=rejecting_from_support,
            timestamp=now
        )

    def detect_breakout(self, live_action: LivePriceAction) -> Optional[BreakoutSignal]:
        """Detect if a breakout is happening right now"""
        if not live_action:
            return None

        breakout = None

        # Check for bullish breakout above resistance
        if live_action.breaking_above and live_action.nearest_resistance:
            is_loading = self.detect_breakout_loading(
                live_action.current_price,
                live_action.nearest_resistance,
                'LONG'
            )

            # Calculate strength
            strength = min(100, (
                (abs(live_action.momentum_score) * 0.4) +
                (min(live_action.volume_surge, 5) * 20) +
                20  # Base strength for being at level
            ))

            # Confirmations
            volume_conf = live_action.volume_surge > 1.5
            momentum_conf = live_action.momentum_score > 30

            # Is it broken cleanly?
            is_broken = live_action.distance_to_resistance_pct < -0.5 and momentum_conf

            breakout = BreakoutSignal(
                direction='LONG',
                level=live_action.nearest_resistance,
                current_price=live_action.current_price,
                strength=strength,
                volume_confirmation=volume_conf,
                momentum_confirmation=momentum_conf,
                is_loading=is_loading and not is_broken,
                is_breaking=not is_loading and not is_broken,
                is_broken=is_broken,
                is_fake=not volume_conf and not momentum_conf,
                confidence=strength,
                timestamp=live_action.timestamp
            )

        # Check for bearish breakout below support
        elif live_action.breaking_below and live_action.nearest_support:
            is_loading = self.detect_breakout_loading(
                live_action.current_price,
                live_action.nearest_support,
                'SHORT'
            )

            strength = min(100, (
                (abs(live_action.momentum_score) * 0.4) +
                (min(live_action.volume_surge, 5) * 20) +
                20
            ))

            volume_conf = live_action.volume_surge > 1.5
            momentum_conf = live_action.momentum_score < -30

            is_broken = live_action.distance_to_support_pct < -0.5 and momentum_conf

            breakout = BreakoutSignal(
                direction='SHORT',
                level=live_action.nearest_support,
                current_price=live_action.current_price,
                strength=strength,
                volume_confirmation=volume_conf,
                momentum_confirmation=momentum_conf,
                is_loading=is_loading and not is_broken,
                is_breaking=not is_loading and not is_broken,
                is_broken=is_broken,
                is_fake=not volume_conf and not momentum_conf,
                confidence=strength,
                timestamp=live_action.timestamp
            )

        return breakout
