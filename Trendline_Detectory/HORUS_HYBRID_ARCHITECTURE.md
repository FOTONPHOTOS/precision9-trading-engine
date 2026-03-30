# HORUS HYBRID ARCHITECTURE - Real-time + Historical Context
**Date:** 2025-10-11
**Purpose:** Design for Arsenal integration using direct Binance with historical analysis
**Strategy:** Best of both worlds - standalone + context-aware

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARSENAL HORUS INTEGRATION                     │
│                     (Hybrid Architecture)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  INITIALIZATION PHASE (Once at startup)                 │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │  Binance REST API                                       │    │
│  │  ↓                                                       │    │
│  │  Fetch Last 500 Candles (1m, 5m, 15m)                  │    │
│  │  ↓                                                       │    │
│  │  Calculate Historical CVD Baseline                      │    │
│  │  - Average CVD over 24h                                 │    │
│  │  - CVD volatility/standard deviation                    │    │
│  │  - Buy/Sell ratio trends                                │    │
│  │  ↓                                                       │    │
│  │  Calculate Historical Exhaustion Baseline               │    │
│  │  - RSI distribution (5m, 15m, 1h)                       │    │
│  │  - Recent exhaustion events                             │    │
│  │  - Typical reversal patterns                            │    │
│  │                                                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  REAL-TIME PHASE (Continuous)                           │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │  Binance WebSocket (aggTrade stream)                    │    │
│  │  ↓                                                       │    │
│  │  Every Trade: Update Real-time CVD                      │    │
│  │  ↓                                                       │    │
│  │  Every 60s: Refresh Exhaustion (via REST)               │    │
│  │  ↓                                                       │    │
│  │  CONTEXTUAL ANALYSIS                                    │    │
│  │  - Compare current CVD vs 24h average                   │    │
│  │  - Detect CVD anomalies (>2 std dev)                    │    │
│  │  - Identify divergences (price vs CVD)                  │    │
│  │  - Check exhaustion vs historical patterns              │    │
│  │                                                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  ARSENAL PRECISION ENTRY                                │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │  Arsenal Detects Setup (Confluence 85+)                 │    │
│  │  ↓                                                       │    │
│  │  Wait for Horus Confirmation:                           │    │
│  │  ✓ CVD above 24h average (strong flow)                 │    │
│  │  ✓ CVD accelerating (not decelerating)                 │    │
│  │  ✓ No CVD divergence detected                          │    │
│  │  ✓ Exhaustion < historical average                     │    │
│  │  ✓ RSI in healthy range (30-70)                        │    │
│  │  ↓                                                       │    │
│  │  ENTER at optimal price                                 │    │
│  │                                                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## DATA STRUCTURES

### 1. Historical Context (Built at startup)

```python
@dataclass
class HistoricalCVDContext:
    """Historical CVD baseline for contextual analysis"""

    # 24-hour statistics
    avg_cvd_24h: float  # Average CVD over last 24h
    std_dev_cvd: float  # Standard deviation (for anomaly detection)
    max_cvd_24h: float  # Highest CVD in 24h
    min_cvd_24h: float  # Lowest CVD in 24h

    # Buy/Sell ratio trends
    avg_buy_ratio: float  # Typical buy ratio (0.5 = balanced)
    buy_ratio_trend: str  # 'increasing', 'stable', 'decreasing'

    # CVD momentum
    avg_cvd_change_1h: float  # Typical CVD change per hour
    cvd_velocity: float  # Rate of CVD acceleration

    # Market regime
    cvd_regime: str  # 'accumulation', 'distribution', 'neutral'
    regime_strength: float  # 0-1, how strong is the regime

    # Divergence history
    recent_divergences: List[Dict]  # Last 10 divergence events
    divergence_reliability: float  # How often divergences led to reversals

    # Timestamp
    calculated_at: float
    data_points: int  # Number of candles used


@dataclass
class HistoricalExhaustionContext:
    """Historical exhaustion baseline for contextual analysis"""

    # RSI distribution (what's "normal" for this symbol)
    avg_rsi_5m: float  # Average RSI on 5m
    avg_rsi_15m: float  # Average RSI on 15m
    avg_rsi_1h: float  # Average RSI on 1h

    # Exhaustion patterns
    typical_exhaustion_score: float  # What's a "normal" exhaustion level
    exhaustion_events_24h: int  # How many times exhausted in 24h
    avg_exhaustion_duration: float  # How long exhaustion lasts (minutes)

    # Reversal patterns
    exhaustion_reversal_rate: float  # % of exhaustions that led to reversals
    avg_reversal_magnitude: float  # Average price move after exhaustion

    # Market characteristics
    volatility_regime: str  # 'high', 'medium', 'low'
    typical_range_percent: float  # Normal 1h range as %

    # Timestamp
    calculated_at: float
    data_points: int


@dataclass
class RealTimeSnapshot:
    """Current real-time data with historical context"""

    timestamp: float

    # Current CVD
    current_cvd: float
    current_delta_flow: float  # Last 20 trades
    current_buy_ratio: float

    # CVD contextual analysis
    cvd_vs_average: float  # Current CVD / 24h average (1.0 = average)
    cvd_percentile: float  # Where is current CVD in 24h distribution (0-100)
    cvd_is_anomaly: bool  # Is CVD >2 std dev from average?
    cvd_momentum: str  # 'accelerating', 'stable', 'decelerating'

    # Divergence detection
    has_divergence: bool
    divergence_type: str  # 'bullish', 'bearish', 'none'
    divergence_strength: float  # 0-1

    # Current exhaustion
    current_exhaustion_score: float
    current_rsi_5m: float
    current_rsi_15m: float
    current_rsi_1h: float

    # Exhaustion contextual analysis
    exhaustion_vs_average: float  # Current / typical
    exhaustion_is_abnormal: bool  # Is exhaustion unusually high?
    rsi_in_healthy_range: bool  # All RSIs between 30-70

    # Entry recommendation
    order_flow_quality: str  # 'excellent', 'good', 'fair', 'poor'
    entry_confidence: float  # 0-1 based on all factors
    recommendation: str  # 'ENTER', 'WAIT', 'SKIP'
    reasons: List[str]  # Why this recommendation
```

---

## COMPONENT 1: CVD COLLECTOR WITH HISTORICAL CONTEXT

### File: `horus_cvd_collector.py`

```python
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
from binance.client import AsyncClient


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
        print("🔄 Fetching historical data for CVD context...")

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

        print(f"✅ Historical context built:")
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
        # Extract trade data
        is_buyer_maker = trade.get('m', False)  # True = sell, False = buy
        quantity = float(trade.get('q', 0))
        price = float(trade.get('p', 0))

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

    def get_contextual_snapshot(self) -> Dict:
        """
        Get current CVD with historical context analysis

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

        # CVD vs average
        cvd_vs_average = self.cvd / ctx.avg_cvd_24h if ctx.avg_cvd_24h != 0 else 1.0

        # CVD percentile (where in distribution)
        cvd_percentile = self._calculate_percentile(
            self.cvd, ctx.min_cvd_24h, ctx.max_cvd_24h
        )

        # Anomaly detection (>2 std dev)
        cvd_is_anomaly = abs(self.cvd - ctx.avg_cvd_24h) > (ctx.std_dev_cvd * 2)

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

            # Contextual analysis
            'cvd_vs_average': cvd_vs_average,
            'cvd_percentile': cvd_percentile,
            'cvd_is_anomaly': cvd_is_anomaly,
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
        recent_delta = sum(list(self.delta_buffer)[-20:])
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

    async def start_websocket(self):
        """Start Binance WebSocket for real-time CVD"""
        # Create WebSocket manager
        bsm = self.client.streams.get_stream('aggTrade', self.symbol.lower())

        async with bsm as stream:
            while True:
                trade = await stream.recv()
                await self.update_from_trade(trade)

                # Every minute, snapshot CVD for momentum tracking
                if int(time.time()) % 60 == 0:
                    self.cvd_buffer.append(self.cvd)
```

### Key Features

1. **Historical Context at Startup**
   - Fetches 500 candles (8+ hours of data)
   - Calculates CVD baseline, volatility, trends
   - Builds anomaly detection thresholds

2. **Real-time Updates**
   - WebSocket trade stream for instant CVD updates
   - Compares every update vs historical baseline
   - Detects anomalies and divergences

3. **Contextual Intelligence**
   - "Is current CVD abnormal for this symbol?"
   - "Is CVD accelerating or decelerating?"
   - "Is there a divergence forming?"

This gives Arsenal the **context** to understand:
- ✅ "CVD is 2.5x higher than 24h average = VERY strong flow"
- ✅ "CVD is accelerating = momentum building"
- ✅ "No divergence detected = price action confirmed by flow"

---

---

## COMPONENT 2: LIQUIDITY ANALYZER WITH HISTORICAL CONTEXT

### File: `horus_liquidity_analyzer.py`

```python
"""
Arsenal Liquidity Analyzer - Hybrid Real-time + Historical
==========================================================
Detects liquidity walls, absorption, and concentration zones with historical context
"""

import asyncio
import time
import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from binance.client import AsyncClient


@dataclass
class HistoricalLiquidityContext:
    """Historical liquidity baseline for contextual analysis"""

    # Typical orderbook characteristics
    avg_total_liquidity: float  # Average total liquidity (bid + ask sum)
    avg_bid_liquidity: float  # Average bid side liquidity
    avg_ask_liquidity: float  # Average ask side liquidity
    avg_bid_ask_ratio: float  # Typical bid/ask ratio (1.0 = balanced)

    # Spread characteristics
    avg_spread_bps: float  # Average spread in basis points
    avg_spread_usd: float  # Average spread in USD
    tight_spread_threshold: float  # What's considered "tight" for this symbol
    wide_spread_threshold: float  # What's considered "wide"

    # Liquidity concentration
    typical_wall_size: float  # What's a "normal" large order size
    large_wall_threshold: float  # Size that indicates institutional activity
    avg_liquidity_clusters: int  # How many price clusters typically exist

    # Market depth
    avg_depth_1pct: float  # Average liquidity within 1% of mid
    avg_depth_2pct: float  # Average liquidity within 2% of mid
    depth_imbalance_threshold: float  # When to consider depth "imbalanced"

    # Absorption patterns
    absorption_events_24h: int  # How many times large orders absorbed
    avg_absorption_size: float  # Typical size of absorbed orders
    absorption_reaction_time: float  # How fast market reacts (seconds)

    # Liquidity regime
    liquidity_regime: str  # 'deep', 'moderate', 'shallow'
    regime_stability: float  # How stable is the liquidity (0-1)

    # Wall behavior
    fake_wall_frequency: float  # How often walls get pulled (spoofing)
    wall_persistence_avg: float  # How long walls stay (seconds)

    # Timestamp
    calculated_at: float
    snapshots_analyzed: int


@dataclass
class LiquidityZone:
    """Identified liquidity concentration zone"""
    price_level: float
    total_liquidity: float
    side: str  # 'bid' or 'ask'
    cluster_size: int  # Number of orders in cluster
    distance_from_mid: float  # Distance in %
    is_wall: bool  # Is this a significant wall?
    wall_type: str  # 'support', 'resistance', 'institutional', 'fake'
    confidence: float  # 0-1, based on historical patterns


class ArsenalLiquidityAnalyzer:
    """
    Real-time liquidity analysis with historical context

    Initialization:
    1. Fetch 200 orderbook snapshots (every 3 seconds = 10 minutes)
    2. Calculate typical liquidity patterns
    3. Build wall detection thresholds

    Real-time:
    1. Monitor orderbook via REST polling (every 1 second)
    2. Detect liquidity walls and absorption
    3. Compare vs historical baseline
    4. Identify institutional activity
    """

    def __init__(self, binance_client: AsyncClient, symbol: str = "SOLUSDT"):
        self.client = binance_client
        self.symbol = symbol

        # Historical context
        self.historical_context: Optional[HistoricalLiquidityContext] = None

        # Real-time orderbook tracking
        self.current_orderbook: Optional[Dict] = None
        self.orderbook_history = deque(maxlen=60)  # Last 60 snapshots (1 minute)

        # Liquidity zone tracking
        self.detected_walls: List[LiquidityZone] = []
        self.absorption_events: List[Dict] = []

        # Wall persistence tracking
        self.wall_tracker: Dict[float, Dict] = {}  # price -> wall info

    async def initialize_historical_context(self):
        """
        INITIALIZATION PHASE: Build liquidity baseline

        Fetches 200 orderbook snapshots and calculates:
        - Typical liquidity depth
        - Average spread characteristics
        - Normal wall sizes
        - Absorption patterns
        """
        print("🔄 Fetching historical orderbook data...")

        orderbook_snapshots = []
        spreads = []
        bid_ask_ratios = []
        total_liquidities = []
        wall_sizes = []

        # Fetch 200 snapshots (one every 3 seconds for 10 minutes of data)
        for i in range(200):
            orderbook = await self.client.futures_order_book(
                symbol=self.symbol,
                limit=100  # Top 100 levels each side
            )

            # Calculate metrics for this snapshot
            bids = [(float(p), float(q)) for p, q in orderbook['bids']]
            asks = [(float(p), float(q)) for p, q in orderbook['asks']]

            bid_liquidity = sum(q for _, q in bids)
            ask_liquidity = sum(q for _, q in asks)
            total_liquidity = bid_liquidity + ask_liquidity

            mid_price = (float(orderbook['bids'][0][0]) + float(orderbook['asks'][0][0])) / 2
            spread = float(orderbook['asks'][0][0]) - float(orderbook['bids'][0][0])
            spread_bps = (spread / mid_price) * 10000

            bid_ask_ratio = bid_liquidity / ask_liquidity if ask_liquidity > 0 else 1.0

            orderbook_snapshots.append(orderbook)
            spreads.append(spread_bps)
            bid_ask_ratios.append(bid_ask_ratio)
            total_liquidities.append(total_liquidity)

            # Detect large orders (walls)
            max_bid_order = max(q for _, q in bids) if bids else 0
            max_ask_order = max(q for _, q in asks) if asks else 0
            wall_sizes.append(max(max_bid_order, max_ask_order))

            # Wait 3 seconds between snapshots
            if i < 199:
                await asyncio.sleep(3)

        # Calculate statistics
        avg_spread_bps = np.mean(spreads)
        avg_total_liquidity = np.mean(total_liquidities)
        avg_bid_liquidity = np.mean([sum(float(q) for _, q in ob['bids']) for ob in orderbook_snapshots])
        avg_ask_liquidity = np.mean([sum(float(q) for _, q in ob['asks']) for ob in orderbook_snapshots])
        avg_bid_ask_ratio = np.mean(bid_ask_ratios)

        # Spread thresholds (percentiles)
        tight_spread_threshold = np.percentile(spreads, 25)
        wide_spread_threshold = np.percentile(spreads, 75)

        # Wall size thresholds
        typical_wall_size = np.median(wall_sizes)
        large_wall_threshold = np.percentile(wall_sizes, 90)

        # Calculate depth at 1% and 2%
        depths_1pct = []
        depths_2pct = []

        for ob in orderbook_snapshots:
            mid = (float(ob['bids'][0][0]) + float(ob['asks'][0][0])) / 2

            depth_1pct = sum(
                float(q) for p, q in ob['bids'] if float(p) >= mid * 0.99
            ) + sum(
                float(q) for p, q in ob['asks'] if float(p) <= mid * 1.01
            )

            depth_2pct = sum(
                float(q) for p, q in ob['bids'] if float(p) >= mid * 0.98
            ) + sum(
                float(q) for p, q in ob['asks'] if float(p) <= mid * 1.02
            )

            depths_1pct.append(depth_1pct)
            depths_2pct.append(depth_2pct)

        avg_depth_1pct = np.mean(depths_1pct)
        avg_depth_2pct = np.mean(depths_2pct)

        # Determine liquidity regime
        if avg_depth_1pct > avg_total_liquidity * 0.6:
            liquidity_regime = 'deep'
            regime_stability = 0.8
        elif avg_depth_1pct < avg_total_liquidity * 0.3:
            liquidity_regime = 'shallow'
            regime_stability = 0.4
        else:
            liquidity_regime = 'moderate'
            regime_stability = 0.6

        # Store context
        self.historical_context = HistoricalLiquidityContext(
            avg_total_liquidity=avg_total_liquidity,
            avg_bid_liquidity=avg_bid_liquidity,
            avg_ask_liquidity=avg_ask_liquidity,
            avg_bid_ask_ratio=avg_bid_ask_ratio,
            avg_spread_bps=avg_spread_bps,
            avg_spread_usd=avg_spread_bps / 10000 * mid_price,
            tight_spread_threshold=tight_spread_threshold,
            wide_spread_threshold=wide_spread_threshold,
            typical_wall_size=typical_wall_size,
            large_wall_threshold=large_wall_threshold,
            avg_liquidity_clusters=5,  # Estimate
            avg_depth_1pct=avg_depth_1pct,
            avg_depth_2pct=avg_depth_2pct,
            depth_imbalance_threshold=1.5,  # 50% imbalance
            absorption_events_24h=0,  # Need longer history
            avg_absorption_size=0,
            absorption_reaction_time=5.0,
            liquidity_regime=liquidity_regime,
            regime_stability=regime_stability,
            fake_wall_frequency=0.15,  # Estimate 15% of walls are fake
            wall_persistence_avg=30.0,  # Average 30 seconds
            calculated_at=time.time(),
            snapshots_analyzed=len(orderbook_snapshots)
        )

        print(f"✅ Liquidity context built:")
        print(f"   Avg Liquidity: {avg_total_liquidity:,.0f}")
        print(f"   Avg Spread: {avg_spread_bps:.2f} bps")
        print(f"   Regime: {liquidity_regime} (stability: {regime_stability:.1%})")
        print(f"   Large Wall Threshold: {large_wall_threshold:,.0f}")
        print(f"   Snapshots: {len(orderbook_snapshots)}")

    async def update_from_orderbook(self):
        """
        REAL-TIME PHASE: Analyze current orderbook vs historical baseline

        Detects:
        - Liquidity walls (support/resistance)
        - Absorption events (large orders getting filled)
        - Spoofing (fake walls that get pulled)
        - Institutional activity
        """
        orderbook = await self.client.futures_order_book(
            symbol=self.symbol,
            limit=100
        )

        self.current_orderbook = orderbook
        self.orderbook_history.append(orderbook)

        # Analyze current orderbook
        bids = [(float(p), float(q)) for p, q in orderbook['bids']]
        asks = [(float(p), float(q)) for p, q in orderbook['asks']]

        mid_price = (bids[0][0] + asks[0][0]) / 2

        # Detect liquidity zones
        self.detected_walls = self._detect_liquidity_zones(bids, asks, mid_price)

        # Track wall persistence
        self._track_wall_persistence()

        # Detect absorption events
        self._detect_absorption()

    def _detect_liquidity_zones(self, bids: List[Tuple[float, float]],
                                 asks: List[Tuple[float, float]],
                                 mid_price: float) -> List[LiquidityZone]:
        """Identify significant liquidity concentration zones"""
        if not self.historical_context:
            return []

        zones = []
        ctx = self.historical_context

        # Check bid side for support walls
        for price, qty in bids[:20]:  # Top 20 bid levels
            if qty >= ctx.large_wall_threshold:
                distance_pct = ((mid_price - price) / mid_price) * 100

                # Determine wall type
                if qty >= ctx.large_wall_threshold * 2:
                    wall_type = 'institutional'
                    confidence = 0.85
                elif distance_pct < 0.5:
                    wall_type = 'support'
                    confidence = 0.75
                else:
                    wall_type = 'support'
                    confidence = 0.65

                zones.append(LiquidityZone(
                    price_level=price,
                    total_liquidity=qty,
                    side='bid',
                    cluster_size=1,
                    distance_from_mid=distance_pct,
                    is_wall=True,
                    wall_type=wall_type,
                    confidence=confidence
                ))

        # Check ask side for resistance walls
        for price, qty in asks[:20]:  # Top 20 ask levels
            if qty >= ctx.large_wall_threshold:
                distance_pct = ((price - mid_price) / mid_price) * 100

                # Determine wall type
                if qty >= ctx.large_wall_threshold * 2:
                    wall_type = 'institutional'
                    confidence = 0.85
                elif distance_pct < 0.5:
                    wall_type = 'resistance'
                    confidence = 0.75
                else:
                    wall_type = 'resistance'
                    confidence = 0.65

                zones.append(LiquidityZone(
                    price_level=price,
                    total_liquidity=qty,
                    side='ask',
                    cluster_size=1,
                    distance_from_mid=distance_pct,
                    is_wall=True,
                    wall_type=wall_type,
                    confidence=confidence
                ))

        return zones

    def _track_wall_persistence(self):
        """Track how long walls persist (detect spoofing)"""
        if not self.detected_walls:
            return

        current_time = time.time()

        # Update existing walls
        for price_level, info in list(self.wall_tracker.items()):
            # Check if wall still exists
            wall_exists = any(
                abs(zone.price_level - price_level) < 0.01
                for zone in self.detected_walls
            )

            if wall_exists:
                info['last_seen'] = current_time
                info['duration'] = current_time - info['first_seen']
            else:
                # Wall disappeared - was it absorbed or pulled?
                duration = current_time - info['first_seen']

                if duration < 5:
                    info['likely_fake'] = True  # Pulled quickly = spoofing

                # Remove from tracker
                del self.wall_tracker[price_level]

        # Add new walls
        for zone in self.detected_walls:
            if zone.price_level not in self.wall_tracker:
                self.wall_tracker[zone.price_level] = {
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'duration': 0,
                    'side': zone.side,
                    'size': zone.total_liquidity,
                    'likely_fake': False
                }

    def _detect_absorption(self):
        """Detect large order absorption events"""
        if len(self.orderbook_history) < 2:
            return

        prev_orderbook = self.orderbook_history[-2]
        current_orderbook = self.orderbook_history[-1]

        # Compare bid side
        prev_bid_liquidity = sum(float(q) for _, q in prev_orderbook['bids'][:10])
        curr_bid_liquidity = sum(float(q) for _, q in current_orderbook['bids'][:10])

        # Compare ask side
        prev_ask_liquidity = sum(float(q) for _, q in prev_orderbook['asks'][:10])
        curr_ask_liquidity = sum(float(q) for _, q in current_orderbook['asks'][:10])

        # Detect significant liquidity decrease (absorption)
        if prev_bid_liquidity > 0:
            bid_decrease_pct = (prev_bid_liquidity - curr_bid_liquidity) / prev_bid_liquidity

            if bid_decrease_pct > 0.2:  # 20% decrease
                self.absorption_events.append({
                    'timestamp': time.time(),
                    'side': 'bid',
                    'amount_absorbed': prev_bid_liquidity - curr_bid_liquidity,
                    'decrease_pct': bid_decrease_pct
                })

        if prev_ask_liquidity > 0:
            ask_decrease_pct = (prev_ask_liquidity - curr_ask_liquidity) / prev_ask_liquidity

            if ask_decrease_pct > 0.2:  # 20% decrease
                self.absorption_events.append({
                    'timestamp': time.time(),
                    'side': 'ask',
                    'amount_absorbed': prev_ask_liquidity - curr_ask_liquidity,
                    'decrease_pct': ask_decrease_pct
                })

    def get_contextual_snapshot(self) -> Dict:
        """Get current liquidity analysis with historical context"""
        if not self.current_orderbook or not self.historical_context:
            return self._get_basic_snapshot()

        ctx = self.historical_context
        ob = self.current_orderbook

        # Current metrics
        bids = [(float(p), float(q)) for p, q in ob['bids']]
        asks = [(float(p), float(q)) for p, q in ob['asks']]

        bid_liquidity = sum(q for _, q in bids)
        ask_liquidity = sum(q for _, q in asks)
        total_liquidity = bid_liquidity + ask_liquidity

        mid_price = (bids[0][0] + asks[0][0]) / 2
        spread = asks[0][0] - bids[0][0]
        spread_bps = (spread / mid_price) * 10000

        bid_ask_ratio = bid_liquidity / ask_liquidity if ask_liquidity > 0 else 1.0

        # Contextual analysis
        liquidity_vs_avg = total_liquidity / ctx.avg_total_liquidity
        spread_vs_avg = spread_bps / ctx.avg_spread_bps

        # Depth analysis
        depth_1pct = sum(
            q for p, q in bids if p >= mid_price * 0.99
        ) + sum(
            q for p, q in asks if p <= mid_price * 1.01
        )

        depth_imbalance = bid_liquidity / ask_liquidity if ask_liquidity > 0 else 1.0

        # Wall analysis
        significant_walls = [w for w in self.detected_walls if w.confidence > 0.7]
        institutional_walls = [w for w in self.detected_walls if w.wall_type == 'institutional']

        # Recent absorption
        recent_absorption = [
            e for e in self.absorption_events
            if time.time() - e['timestamp'] < 60
        ]

        return {
            'timestamp': time.time(),

            # Current liquidity
            'total_liquidity': total_liquidity,
            'bid_liquidity': bid_liquidity,
            'ask_liquidity': ask_liquidity,
            'bid_ask_ratio': bid_ask_ratio,
            'spread_bps': spread_bps,

            # Contextual analysis
            'liquidity_vs_avg': liquidity_vs_avg,
            'spread_vs_avg': spread_vs_avg,
            'depth_1pct': depth_1pct,
            'depth_imbalance': depth_imbalance,

            # Liquidity zones
            'detected_walls': len(self.detected_walls),
            'significant_walls': len(significant_walls),
            'institutional_walls': len(institutional_walls),
            'wall_details': [
                {
                    'price': w.price_level,
                    'size': w.total_liquidity,
                    'side': w.side,
                    'type': w.wall_type,
                    'distance_pct': w.distance_from_mid
                }
                for w in significant_walls
            ],

            # Absorption events
            'recent_absorption_events': len(recent_absorption),
            'absorption_details': recent_absorption[-3:],  # Last 3

            # Historical baseline
            'historical_regime': ctx.liquidity_regime,
            'historical_avg_liquidity': ctx.avg_total_liquidity,
            'historical_avg_spread': ctx.avg_spread_bps,

            # Quality indicators
            'liquidity_quality': 'excellent' if liquidity_vs_avg > 1.2 else 'good' if liquidity_vs_avg > 0.8 else 'poor',
            'spread_quality': 'tight' if spread_bps < ctx.tight_spread_threshold else 'wide' if spread_bps > ctx.wide_spread_threshold else 'normal'
        }

    def _get_basic_snapshot(self) -> Dict:
        """Fallback when no context yet"""
        return {
            'timestamp': time.time(),
            'total_liquidity': 0,
            'liquidity_vs_avg': 1.0,
            'detected_walls': 0,
            'data_quality': 'initializing'
        }

    async def monitor_liquidity(self, update_interval: int = 1):
        """Monitor liquidity continuously (every 1 second)"""
        while True:
            await self.update_from_orderbook()
            await asyncio.sleep(update_interval)
```

### Key Features

1. **Historical Liquidity Baseline**
   - Fetches 200 orderbook snapshots (10 minutes of data)
   - Calculates typical spread, depth, wall sizes
   - Identifies normal vs abnormal liquidity patterns

2. **Real-time Wall Detection**
   - Detects support/resistance walls
   - Identifies institutional-sized orders
   - Tracks wall persistence (spoofing detection)

3. **Absorption Analysis**
   - Detects when large orders get filled
   - Monitors liquidity disappearance
   - Signals potential momentum shifts

4. **Contextual Intelligence**
   - "Is this wall abnormally large for this symbol?"
   - "Is liquidity deeper or shallower than usual?"
   - "Is this wall likely to be fake (spoofing)?"

---

## COMPONENT 3: ORDERBOOK DEPTH ANALYZER

### File: `horus_orderbook_analyzer.py`

```python
"""
Arsenal Orderbook Depth Analyzer - Hybrid Real-time + Historical
================================================================
Analyzes orderbook imbalances, depth shifts, and market maker behavior
"""

import asyncio
import time
import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from binance.client import AsyncClient


@dataclass
class HistoricalDepthContext:
    """Historical orderbook depth baseline"""

    # Typical depth distribution
    avg_depth_5_levels: float  # Average liquidity in top 5 levels
    avg_depth_10_levels: float  # Average liquidity in top 10 levels
    avg_depth_20_levels: float  # Average liquidity in top 20 levels

    # Imbalance patterns
    avg_imbalance_ratio: float  # Typical bid/ask imbalance (1.0 = balanced)
    imbalance_std_dev: float  # Volatility of imbalance
    strong_imbalance_threshold: float  # When imbalance is significant

    # Depth shift patterns
    depth_shift_frequency: float  # How often depth shifts significantly
    avg_shift_magnitude: float  # Typical size of depth shifts
    shift_reaction_time: float  # Market reaction time (seconds)

    # Order size distribution
    avg_order_size: float  # Typical order size
    large_order_percentile_90: float  # 90th percentile order size
    large_order_percentile_95: float  # 95th percentile (institutional)

    # Market maker behavior
    mm_presence_score: float  # 0-1, how active are MMs
    avg_quote_spread_layers: int  # How many layers MMs typically quote
    mm_update_frequency: float  # How often MMs update quotes (per minute)

    # Depth concentration
    top_5_concentration: float  # % of liquidity in top 5 levels
    top_10_concentration: float  # % of liquidity in top 10 levels
    depth_is_concentrated: bool  # Is depth concentrated or distributed

    # Regime
    depth_regime: str  # 'balanced', 'bid_heavy', 'ask_heavy'
    regime_persistence: float  # How long regimes last (minutes)

    # Timestamp
    calculated_at: float
    snapshots_analyzed: int


class ArsenalOrderbookAnalyzer:
    """
    Real-time orderbook depth analysis with historical context

    Initialization:
    1. Fetch 200 orderbook snapshots (every 3 seconds = 10 minutes)
    2. Calculate typical depth distribution
    3. Build imbalance detection thresholds

    Real-time:
    1. Monitor orderbook via REST polling (every 1 second)
    2. Detect depth imbalances and shifts
    3. Identify market maker activity
    4. Signal potential price movements
    """

    def __init__(self, binance_client: AsyncClient, symbol: str = "SOLUSDT"):
        self.client = binance_client
        self.symbol = symbol

        # Historical context
        self.historical_context: Optional[HistoricalDepthContext] = None

        # Real-time tracking
        self.current_orderbook: Optional[Dict] = None
        self.orderbook_history = deque(maxlen=60)  # Last 60 snapshots
        self.imbalance_history = deque(maxlen=100)  # Imbalance over time

        # Depth shift detection
        self.last_significant_shift: Optional[Dict] = None
        self.shift_events: List[Dict] = []

    async def initialize_historical_context(self):
        """
        INITIALIZATION PHASE: Build orderbook depth baseline

        Fetches 200 snapshots and calculates:
        - Typical depth distribution (5, 10, 20 levels)
        - Imbalance patterns and thresholds
        - Order size distribution
        - Market maker behavior
        """
        print("🔄 Fetching historical orderbook depth data...")

        depth_5_levels = []
        depth_10_levels = []
        depth_20_levels = []
        imbalance_ratios = []
        order_sizes = []
        top_5_concentrations = []
        top_10_concentrations = []

        # Fetch 200 snapshots
        for i in range(200):
            orderbook = await self.client.futures_order_book(
                symbol=self.symbol,
                limit=100
            )

            bids = [(float(p), float(q)) for p, q in orderbook['bids']]
            asks = [(float(p), float(q)) for p, q in orderbook['asks']]

            # Depth at different levels
            depth_5 = sum(q for _, q in bids[:5]) + sum(q for _, q in asks[:5])
            depth_10 = sum(q for _, q in bids[:10]) + sum(q for _, q in asks[:10])
            depth_20 = sum(q for _, q in bids[:20]) + sum(q for _, q in asks[:20])
            total_depth = sum(q for _, q in bids) + sum(q for _, q in asks)

            depth_5_levels.append(depth_5)
            depth_10_levels.append(depth_10)
            depth_20_levels.append(depth_20)

            # Imbalance
            bid_liquidity = sum(q for _, q in bids[:20])
            ask_liquidity = sum(q for _, q in asks[:20])
            imbalance_ratio = bid_liquidity / ask_liquidity if ask_liquidity > 0 else 1.0
            imbalance_ratios.append(imbalance_ratio)

            # Order sizes
            all_orders = [q for _, q in bids] + [q for _, q in asks]
            order_sizes.extend(all_orders)

            # Concentration
            top_5_pct = (depth_5 / total_depth * 100) if total_depth > 0 else 0
            top_10_pct = (depth_10 / total_depth * 100) if total_depth > 0 else 0
            top_5_concentrations.append(top_5_pct)
            top_10_concentrations.append(top_10_pct)

            if i < 199:
                await asyncio.sleep(3)

        # Calculate statistics
        avg_depth_5 = np.mean(depth_5_levels)
        avg_depth_10 = np.mean(depth_10_levels)
        avg_depth_20 = np.mean(depth_20_levels)

        avg_imbalance = np.mean(imbalance_ratios)
        imbalance_std = np.std(imbalance_ratios)
        strong_imbalance_threshold = avg_imbalance + (imbalance_std * 2)

        avg_order_size = np.mean(order_sizes)
        large_order_p90 = np.percentile(order_sizes, 90)
        large_order_p95 = np.percentile(order_sizes, 95)

        top_5_concentration = np.mean(top_5_concentrations)
        top_10_concentration = np.mean(top_10_concentrations)

        # Determine if depth is concentrated
        depth_is_concentrated = top_5_concentration > 50  # >50% in top 5 levels

        # Determine depth regime
        if avg_imbalance > 1.2:
            depth_regime = 'bid_heavy'
        elif avg_imbalance < 0.8:
            depth_regime = 'ask_heavy'
        else:
            depth_regime = 'balanced'

        # Store context
        self.historical_context = HistoricalDepthContext(
            avg_depth_5_levels=avg_depth_5,
            avg_depth_10_levels=avg_depth_10,
            avg_depth_20_levels=avg_depth_20,
            avg_imbalance_ratio=avg_imbalance,
            imbalance_std_dev=imbalance_std,
            strong_imbalance_threshold=strong_imbalance_threshold,
            depth_shift_frequency=0.1,  # Estimate: 10% of time
            avg_shift_magnitude=0.3,  # 30% change
            shift_reaction_time=5.0,  # 5 seconds
            avg_order_size=avg_order_size,
            large_order_percentile_90=large_order_p90,
            large_order_percentile_95=large_order_p95,
            mm_presence_score=0.7,  # Estimate
            avg_quote_spread_layers=5,
            mm_update_frequency=12,  # 12 updates/min
            top_5_concentration=top_5_concentration,
            top_10_concentration=top_10_concentration,
            depth_is_concentrated=depth_is_concentrated,
            depth_regime=depth_regime,
            regime_persistence=15.0,  # 15 minutes
            calculated_at=time.time(),
            snapshots_analyzed=len(depth_5_levels)
        )

        print(f"✅ Orderbook depth context built:")
        print(f"   Avg Depth (5 levels): {avg_depth_5:,.0f}")
        print(f"   Avg Depth (20 levels): {avg_depth_20:,.0f}")
        print(f"   Depth Regime: {depth_regime}")
        print(f"   Top 5 Concentration: {top_5_concentration:.1f}%")
        print(f"   Strong Imbalance Threshold: {strong_imbalance_threshold:.2f}")
        print(f"   Snapshots: {len(depth_5_levels)}")

    async def update_from_orderbook(self):
        """
        REAL-TIME PHASE: Analyze current orderbook depth

        Detects:
        - Depth imbalances (bid vs ask)
        - Depth shifts (sudden changes)
        - Market maker activity
        - Potential price direction signals
        """
        orderbook = await self.client.futures_order_book(
            symbol=self.symbol,
            limit=100
        )

        self.current_orderbook = orderbook
        self.orderbook_history.append(orderbook)

        # Calculate current imbalance
        bids = [(float(p), float(q)) for p, q in orderbook['bids']]
        asks = [(float(p), float(q)) for p, q in orderbook['asks']]

        bid_liquidity_20 = sum(q for _, q in bids[:20])
        ask_liquidity_20 = sum(q for _, q in asks[:20])

        imbalance_ratio = bid_liquidity_20 / ask_liquidity_20 if ask_liquidity_20 > 0 else 1.0
        self.imbalance_history.append(imbalance_ratio)

        # Detect depth shifts
        self._detect_depth_shifts()

    def _detect_depth_shifts(self):
        """Detect significant changes in orderbook depth"""
        if len(self.orderbook_history) < 10 or not self.historical_context:
            return

        # Compare recent vs older depth
        recent_ob = self.orderbook_history[-1]
        older_ob = self.orderbook_history[-10]

        # Calculate depth change
        recent_bids = sum(float(q) for _, q in recent_ob['bids'][:20])
        older_bids = sum(float(q) for _, q in older_ob['bids'][:20])

        recent_asks = sum(float(q) for _, q in recent_ob['asks'][:20])
        older_asks = sum(float(q) for _, q in older_ob['asks'][:20])

        if older_bids > 0:
            bid_change_pct = (recent_bids - older_bids) / older_bids
        else:
            bid_change_pct = 0

        if older_asks > 0:
            ask_change_pct = (recent_asks - older_asks) / older_asks
        else:
            ask_change_pct = 0

        # Significant shift if >30% change
        if abs(bid_change_pct) > 0.3 or abs(ask_change_pct) > 0.3:
            self.last_significant_shift = {
                'timestamp': time.time(),
                'bid_change_pct': bid_change_pct,
                'ask_change_pct': ask_change_pct,
                'direction': 'bid_increase' if bid_change_pct > ask_change_pct else 'ask_increase'
            }

            self.shift_events.append(self.last_significant_shift)

    def get_contextual_snapshot(self) -> Dict:
        """Get current depth analysis with historical context"""
        if not self.current_orderbook or not self.historical_context:
            return self._get_basic_snapshot()

        ctx = self.historical_context
        ob = self.current_orderbook

        # Current metrics
        bids = [(float(p), float(q)) for p, q in ob['bids']]
        asks = [(float(p), float(q)) for p, q in ob['asks']]

        depth_5 = sum(q for _, q in bids[:5]) + sum(q for _, q in asks[:5])
        depth_10 = sum(q for _, q in bids[:10]) + sum(q for _, q in asks[:10])
        depth_20 = sum(q for _, q in bids[:20]) + sum(q for _, q in asks[:20])

        bid_liquidity = sum(q for _, q in bids[:20])
        ask_liquidity = sum(q for _, q in asks[:20])
        imbalance_ratio = bid_liquidity / ask_liquidity if ask_liquidity > 0 else 1.0

        # Contextual analysis
        depth_vs_avg = depth_20 / ctx.avg_depth_20_levels
        imbalance_vs_avg = imbalance_ratio / ctx.avg_imbalance_ratio

        # Imbalance strength
        imbalance_strength = abs(imbalance_ratio - 1.0)
        is_strong_imbalance = imbalance_ratio > ctx.strong_imbalance_threshold or imbalance_ratio < (2 - ctx.strong_imbalance_threshold)

        # Recent shift
        has_recent_shift = self.last_significant_shift and (time.time() - self.last_significant_shift['timestamp'] < 30)

        # Predict direction based on imbalance
        if imbalance_ratio > 1.3:
            predicted_direction = 'LONG'  # Bid heavy = bullish
            direction_confidence = min((imbalance_ratio - 1.0) / 0.5, 1.0)
        elif imbalance_ratio < 0.7:
            predicted_direction = 'SHORT'  # Ask heavy = bearish
            direction_confidence = min((1.0 - imbalance_ratio) / 0.5, 1.0)
        else:
            predicted_direction = 'NEUTRAL'
            direction_confidence = 0.0

        return {
            'timestamp': time.time(),

            # Current depth
            'depth_5_levels': depth_5,
            'depth_10_levels': depth_10,
            'depth_20_levels': depth_20,
            'bid_liquidity': bid_liquidity,
            'ask_liquidity': ask_liquidity,
            'imbalance_ratio': imbalance_ratio,

            # Contextual analysis
            'depth_vs_avg': depth_vs_avg,
            'imbalance_vs_avg': imbalance_vs_avg,
            'imbalance_strength': imbalance_strength,
            'is_strong_imbalance': is_strong_imbalance,

            # Direction prediction
            'predicted_direction': predicted_direction,
            'direction_confidence': direction_confidence,

            # Depth shifts
            'has_recent_shift': has_recent_shift,
            'last_shift_details': self.last_significant_shift if has_recent_shift else None,
            'shift_events_5min': len([e for e in self.shift_events if time.time() - e['timestamp'] < 300]),

            # Historical baseline
            'historical_regime': ctx.depth_regime,
            'historical_avg_imbalance': ctx.avg_imbalance_ratio,
            'depth_is_concentrated': ctx.depth_is_concentrated,

            # Quality indicators
            'depth_quality': 'excellent' if depth_vs_avg > 1.2 else 'good' if depth_vs_avg > 0.8 else 'poor',
            'signal_strength': 'strong' if is_strong_imbalance and has_recent_shift else 'moderate' if is_strong_imbalance else 'weak'
        }

    def _get_basic_snapshot(self) -> Dict:
        """Fallback when no context yet"""
        return {
            'timestamp': time.time(),
            'depth_20_levels': 0,
            'imbalance_ratio': 1.0,
            'predicted_direction': 'NEUTRAL',
            'data_quality': 'initializing'
        }

    async def monitor_depth(self, update_interval: int = 1):
        """Monitor orderbook depth continuously (every 1 second)"""
        while True:
            await self.update_from_orderbook()
            await asyncio.sleep(update_interval)
```

### Key Features

1. **Historical Depth Baseline**
   - Analyzes 200 orderbook snapshots (10 minutes)
   - Calculates typical depth distribution
   - Identifies normal imbalance patterns

2. **Real-time Imbalance Detection**
   - Monitors bid/ask ratio continuously
   - Detects strong imbalances (>1.3 or <0.7)
   - Predicts price direction from imbalance

3. **Depth Shift Detection**
   - Identifies sudden depth changes (>30%)
   - Tracks bid vs ask depth shifts
   - Signals potential price movements

4. **Contextual Intelligence**
   - "Is this imbalance abnormal for this symbol?"
   - "Is depth concentrated or distributed?"
   - "Has there been a recent significant shift?"

---

## NEXT STEPS

Ready to implement:
1. ✅ **horus_cvd_collector.py** (CVD with historical context)
2. ✅ **horus_liquidity_analyzer.py** (Liquidity walls with historical context)
3. ✅ **horus_orderbook_analyzer.py** (Depth analysis with historical context)
4. ⏳ **horus_exhaustion_collector.py** (RSI exhaustion with historical context)
5. ⏳ **horus_data_collector.py** (unified interface)
6. ⏳ **precision_entry_system.py** (contextual entry logic)

All three analyzers follow the same hybrid pattern:
- **Initialization**: Fetch historical data, build baseline
- **Real-time**: Monitor current vs historical
- **Context**: Detect anomalies and patterns

Should I proceed with creating the actual Python files?
