"""
Arsenal CVD Collector - Hybrid Real-time + Historical
=====================================================
Maintains historical CVD context for intelligent entry decisions
"""

import asyncio
import time
import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional
from binance import AsyncClient, BinanceSocketManager
import logging

logger = logging.getLogger(__name__)


@dataclass
class HistoricalCVDContext:
    """Historical CVD baseline"""
    avg_cvd_24h: float
    std_dev_cvd: float
    max_cvd_24h: float
    min_cvd_24h: float
    avg_buy_ratio: float
    buy_ratio_trend: str
    avg_cvd_change_1h: float
    cvd_velocity: float
    cvd_regime: str
    regime_strength: float
    recent_divergences: List[Dict]
    divergence_reliability: float
    calculated_at: float
    data_points: int


class ArsenalCVDCollector:
    """
    Real-time CVD calculation with historical context

    Initialization:
    1. Fetch 500 candles from Binance REST API (1m, 5m)
    2. Calculate historical CVD baseline
    3. Build context for anomaly detection

    Real-time:
    1. Subscribe to Binance WebSocket (aggTrade)
    2. Update CVD on every trade
    3. Compare vs historical baseline
    4. Detect anomalies and divergences
    """

    def __init__(self, binance_client: AsyncClient, symbol: str = "SOLUSDT"):
        self.client = binance_client
        self.symbol = symbol

        # Real-time CVD tracking
        self.cvd = 0.0
        self.buy_volume_24h = 0.0
        self.sell_volume_24h = 0.0
        self.delta_buffer = deque(maxlen=100)  # Last 100 trades
        self.raw_trade_buffer = deque(maxlen=1000) # NEW: Store raw trades
        self.is_receiving_data = False # NEW: Health status flag

        # Historical context (built at startup)
        self.historical_context: Optional[HistoricalCVDContext] = None

        # Price tracking for divergence detection
        self.price_buffer = deque(maxlen=100)
        self.cvd_buffer = deque(maxlen=100)  # CVD snapshots every minute

        # WebSocket
        self.ws_task = None

    async def initialize_historical_context(self):
        """
        INITIALIZATION PHASE: Build historical context

        Fetches 500 1-minute candles and calculates:
        - Average CVD over 24h
        - CVD volatility (std dev)
        - Buy/Sell ratio trends
        - CVD momentum patterns
        """
        print("Fetching historical data for CVD context...")

        # Fetch 500 1-minute candles (8+ hours of data)
        klines_1m = await self.client.futures_klines(
            symbol=self.symbol,
            interval='1m',
            limit=500
        )

        # Calculate historical CVD from klines
        historical_cvd = []
        historical_prices = []
        historical_buy_ratios = []

        cumulative_cvd = 0.0

        for kline in klines_1m:
            close_price = float(kline[4])
            volume = float(kline[5])
            taker_buy_volume = float(kline[9])  # Volume bought by takers

            # Estimate buy/sell split
            buy_volume = taker_buy_volume
            sell_volume = volume - taker_buy_volume

            # Update CVD
            cvd_delta = buy_volume - sell_volume
            cumulative_cvd += cvd_delta

            historical_cvd.append(cumulative_cvd)
            historical_prices.append(close_price)
            historical_buy_ratios.append(buy_volume / volume if volume > 0 else 0.5)

        # Calculate statistics
        avg_cvd = np.mean(historical_cvd)
        std_dev = np.std(historical_cvd)
        max_cvd = max(historical_cvd)
        min_cvd = min(historical_cvd)

        avg_buy_ratio = np.mean(historical_buy_ratios)

        # Detect buy ratio trend
        first_half_ratio = np.mean(historical_buy_ratios[:250])
        second_half_ratio = np.mean(historical_buy_ratios[250:])

        if second_half_ratio > first_half_ratio * 1.05:
            buy_ratio_trend = 'increasing'
        elif second_half_ratio < first_half_ratio * 0.95:
            buy_ratio_trend = 'decreasing'
        else:
            buy_ratio_trend = 'stable'

        # Calculate CVD velocity (change per hour)
        cvd_changes_1h = []
        for i in range(60, len(historical_cvd)):
            change = historical_cvd[i] - historical_cvd[i-60]
            cvd_changes_1h.append(change)

        avg_cvd_change_1h = np.mean(cvd_changes_1h) if cvd_changes_1h else 0.0
        cvd_velocity = avg_cvd_change_1h / 60 if avg_cvd_change_1h != 0 else 0.0

        # Determine CVD regime
        if avg_cvd > std_dev:
            cvd_regime = 'accumulation'
            regime_strength = min(avg_cvd / (std_dev * 2), 1.0)
        elif avg_cvd < -std_dev:
            cvd_regime = 'distribution'
            regime_strength = min(abs(avg_cvd) / (std_dev * 2), 1.0)
        else:
            cvd_regime = 'neutral'
            regime_strength = 0.5

        # Detect recent divergences
        recent_divergences = self._detect_historical_divergences(
            historical_prices, historical_cvd
        )

        # Calculate divergence reliability
        divergence_reliability = 0.75  # Default (would need more data for accuracy)

        # Store context
        self.historical_context = HistoricalCVDContext(
            avg_cvd_24h=avg_cvd,
            std_dev_cvd=std_dev,
            max_cvd_24h=max_cvd,
            min_cvd_24h=min_cvd,
            avg_buy_ratio=avg_buy_ratio,
            buy_ratio_trend=buy_ratio_trend,
            avg_cvd_change_1h=avg_cvd_change_1h,
            cvd_velocity=cvd_velocity,
            cvd_regime=cvd_regime,
            regime_strength=regime_strength,
            recent_divergences=recent_divergences,
            divergence_reliability=divergence_reliability,
            calculated_at=time.time(),
            data_points=len(historical_cvd)
        )

        # Initialize real-time CVD from latest historical value
        self.cvd = cumulative_cvd

        print(f"Historical context built:")
        print(f"   24h Avg CVD: {avg_cvd:,.0f}")
        print(f"   CVD Range: {min_cvd:,.0f} to {max_cvd:,.0f}")
        print(f"   Regime: {cvd_regime} (strength: {regime_strength:.1%})")
        print(f"   Buy Ratio: {avg_buy_ratio:.1%} ({buy_ratio_trend})")
        print(f"   Data Points: {len(historical_cvd)}")

    def _detect_historical_divergences(self, prices: List[float],
                                       cvds: List[float]) -> List[Dict]:
        """Detect divergences in historical data"""
        divergences = []

        # Look for divergences in 20-candle windows
        for i in range(20, len(prices) - 20, 20):
            window_prices = prices[i-20:i+20]
            window_cvds = cvds[i-20:i+20]

            # Price trend
            price_slope = np.polyfit(range(len(window_prices)), window_prices, 1)[0]
            cvd_slope = np.polyfit(range(len(window_cvds)), window_cvds, 1)[0]

            # Normalize
            price_trend = price_slope / np.mean(window_prices) if np.mean(window_prices) != 0 else 0
            cvd_trend = cvd_slope / (np.std(window_cvds) + 1e-8)

            # Detect divergence
            if price_trend > 0.001 and cvd_trend < -0.1:
                divergences.append({
                    'type': 'bearish',
                    'timestamp': i,
                    'strength': abs(cvd_trend)
                })
            elif price_trend < -0.001 and cvd_trend > 0.1:
                divergences.append({
                    'type': 'bullish',
                    'timestamp': i,
                    'strength': abs(cvd_trend)
                })

        return divergences[-10:]  # Last 10 divergences

    async def update_from_trade(self, trade: Dict):
        """
        REAL-TIME PHASE: Update CVD from WebSocket trade

        Called for every trade from Binance WebSocket
        """
        if not self.is_receiving_data:
            self.is_receiving_data = True

        # Extract trade data from the nested 'data' dictionary
        trade_data = trade.get('data', {})
        is_buyer_maker = trade_data.get('m', False)
        quantity = float(trade_data.get('q', 0))
        price = float(trade_data.get('p', 0))

        # Update CVD
        if is_buyer_maker:
            # Sell (taker sold to maker's buy order)
            self.cvd -= quantity
            self.sell_volume_24h += quantity
        else:
            # Buy (taker bought from maker's sell order)
            self.cvd += quantity
            self.buy_volume_24h += quantity

        # Update buffers
        delta = quantity if not is_buyer_maker else -quantity
        self.delta_buffer.append(delta)
        self.price_buffer.append(price)
        self.raw_trade_buffer.append(trade) # NEW: Store the raw trade

    def get_recent_trades(self, since_timestamp: float) -> List[Dict]:
        """Filters the raw trade buffer for trades since a given timestamp."""
        return [t for t in self.raw_trade_buffer if t.get('data', {}).get('T', 0) > since_timestamp]

    def get_contextual_snapshot(self) -> Dict:
        """
        Get current CVD with historical context analysis using Z-Score.

        Returns enriched snapshot comparing current vs historical baseline
        """
        if not self.historical_context:
            # No context yet, return basic snapshot
            return self._get_basic_snapshot()

        # Current values
        recent_delta = sum(list(self.delta_buffer)[-20:])  # Last 20 trades
        total_volume = self.buy_volume_24h + self.sell_volume_24h
        buy_ratio = self.buy_volume_24h / total_volume if total_volume > 0 else 0.5

        # Contextual analysis
        ctx = self.historical_context

        # --- Z-Score Calculation ---
        # This is a normalized score of how far the current CVD is from its historical average.
        if ctx.std_dev_cvd > 0:
            cvd_z_score = (self.cvd - ctx.avg_cvd_24h) / ctx.std_dev_cvd
        else:
            cvd_z_score = 0.0

        # Momentum detection
        cvd_momentum = self._detect_momentum()

        # Divergence detection
        has_divergence, div_type, div_strength = self._detect_real_time_divergence()

        return {
            'timestamp': time.time(),

            # Current CVD
            'cvd_value': self.cvd,
            'delta_flow': recent_delta,
            'buy_volume': self.buy_volume_24h,
            'sell_volume': self.sell_volume_24h,
            'buy_ratio': buy_ratio,

            # Contextual analysis (Z-Score)
            'cvd_z_score': cvd_z_score,
            'cvd_momentum': cvd_momentum,

            # Divergence
            'has_divergence': has_divergence,
            'divergence_type': div_type,
            'divergence_strength': div_strength,

            # Historical baseline
            'historical_avg_cvd': ctx.avg_cvd_24h,
            'historical_regime': ctx.cvd_regime,
            'historical_regime_strength': ctx.regime_strength,

            # Quality indicator
            'data_quality': 'excellent' if len(self.delta_buffer) > 50 else 'good'
        }

    def _get_basic_snapshot(self) -> Dict:
        """Fallback when no historical context yet"""
        recent_delta = sum(list(self.delta_buffer)[-20:]) if self.delta_buffer else 0
        total_volume = self.buy_volume_24h + self.sell_volume_24h
        buy_ratio = self.buy_volume_24h / total_volume if total_volume > 0 else 0.5

        return {
            'timestamp': time.time(),
            'cvd_value': self.cvd,
            'delta_flow': recent_delta,
            'buy_volume': self.buy_volume_24h,
            'sell_volume': self.sell_volume_24h,
            'buy_ratio': buy_ratio,
            'cvd_vs_average': 1.0,
            'cvd_percentile': 50.0,
            'cvd_is_anomaly': False,
            'cvd_momentum': 'unknown',
            'has_divergence': False,
            'divergence_type': 'none',
            'divergence_strength': 0.0,
            'data_quality': 'initializing'
        }

    def _calculate_percentile(self, value: float, min_val: float, max_val: float) -> float:
        """Calculate where value sits in min-max range (0-100)"""
        if max_val == min_val:
            return 50.0

        percentile = ((value - min_val) / (max_val - min_val)) * 100
        return max(0, min(100, percentile))

    def _detect_momentum(self) -> str:
        """Detect if CVD is accelerating, stable, or decelerating"""
        if len(self.cvd_buffer) < 10:
            return 'unknown'

        # Compare recent vs older CVD changes
        recent_cvds = list(self.cvd_buffer)[-5:]
        older_cvds = list(self.cvd_buffer)[-10:-5]

        recent_change = recent_cvds[-1] - recent_cvds[0]
        older_change = older_cvds[-1] - older_cvds[0]

        if recent_change > older_change * 1.2:
            return 'accelerating'
        elif recent_change < older_change * 0.8:
            return 'decelerating'
        else:
            return 'stable'

    def _detect_real_time_divergence(self) -> tuple:
        """Detect divergence between price and CVD"""
        if len(self.price_buffer) < 20 or len(self.cvd_buffer) < 20:
            return False, 'none', 0.0

        # Get recent data
        recent_prices = list(self.price_buffer)[-20:]
        recent_cvds = list(self.cvd_buffer)[-20:]

        # Calculate trends
        price_slope = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
        cvd_slope = np.polyfit(range(len(recent_cvds)), recent_cvds, 1)[0]

        # Normalize
        price_trend = price_slope / np.mean(recent_prices) if np.mean(recent_prices) != 0 else 0
        cvd_trend_norm = cvd_slope / (np.std(recent_cvds) + 1e-8)

        # Check for divergence
        if price_trend > 0.001 and cvd_trend_norm < -0.1:
            # Price rising but CVD falling = bearish divergence
            return True, 'bearish', abs(cvd_trend_norm)
        elif price_trend < -0.001 and cvd_trend_norm > 0.1:
            # Price falling but CVD rising = bullish divergence
            return True, 'bullish', abs(cvd_trend_norm)
        else:
            return False, 'none', 0.0

    def get_recent_cvd_history(self) -> List[float]:
        """Returns the recent history of CVD snapshots."""
        return list(self.cvd_buffer)

    async def start_websocket(self):
        """Start Binance WebSocket for real-time CVD with auto-reconnection."""
        while True: # Outer loop for reconnection
            try:
                bsm = BinanceSocketManager(self.client)
                trade_socket = bsm.aggtrade_futures_socket(symbol=self.symbol)
                
                logger.info(f"Connecting to futures aggregate trade stream for {self.symbol}...")
                async with trade_socket as stream:
                    logger.info(f" WebSocket connection established for {self.symbol}.")
                    while True: # Inner loop for receiving messages
                        trade = await stream.recv()
                        await self.update_from_trade(trade)

                        # Every minute, snapshot CVD for momentum tracking
                        current_time = int(time.time())
                        if current_time % 60 == 0:
                            if not hasattr(self, '_last_append_time') or self._last_append_time != current_time:
                                self.cvd_buffer.append(self.cvd)
                                self._last_append_time = current_time
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                logger.warning("Connection lost. Attempting to reconnect in 30 seconds...")
                await asyncio.sleep(30)
