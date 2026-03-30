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
from binance import AsyncClient


@dataclass
class HistoricalDepthContext:
    """Historical orderbook depth baseline"""

    # Typical depth distribution
    avg_depth_5_levels: float
    avg_depth_10_levels: float
    avg_depth_20_levels: float

    # Imbalance patterns
    avg_imbalance_ratio: float
    imbalance_std_dev: float
    strong_imbalance_threshold: float

    # Depth shift patterns
    depth_shift_frequency: float
    avg_shift_magnitude: float
    shift_reaction_time: float

    # Order size distribution
    avg_order_size: float
    large_order_percentile_90: float
    large_order_percentile_95: float

    # Market maker behavior
    mm_presence_score: float
    avg_quote_spread_layers: int
    mm_update_frequency: float

    # Depth concentration
    top_5_concentration: float
    top_10_concentration: float
    depth_is_concentrated: bool

    # Regime
    depth_regime: str
    regime_persistence: float

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
        self.orderbook_history = deque(maxlen=60)
        self.imbalance_history = deque(maxlen=100)

        # Depth shift detection
        self.last_significant_shift: Optional[Dict] = None
        self.shift_events: List[Dict] = []

    async def initialize_historical_context(self, snapshot_count: int = 200):
        """
        INITIALIZATION PHASE: Build orderbook depth baseline

        Fetches N snapshots and calculates:
        - Typical depth distribution (5, 10, 20 levels)
        - Imbalance patterns and thresholds
        - Order size distribution
        - Market maker behavior
        """
        print(f"Fetching {snapshot_count} historical orderbook depth snapshots...")

        depth_5_levels = []
        depth_10_levels = []
        depth_20_levels = []
        imbalance_ratios = []
        order_sizes = []
        top_5_concentrations = []
        top_10_concentrations = []

        # Fetch N snapshots
        for i in range(snapshot_count):
            orderbook = await self.client.futures_order_book(
                symbol=self.symbol,
                limit=100
            )

            bids = [(float(p), float(q)) for p, q in orderbook['bids']]
            asks = [(float(p), float(q)) for p, q in orderbook['asks']]

            # Convert to USD value for normalization
            bids_usd = [(p * q) for p, q in bids]
            asks_usd = [(p * q) for p, q in asks]

            # Depth at different levels (in USD)
            depth_5 = sum(bids_usd[:5]) + sum(asks_usd[:5])
            depth_10 = sum(bids_usd[:10]) + sum(asks_usd[:10])
            depth_20 = sum(bids_usd[:20]) + sum(asks_usd[:20])
            total_depth = sum(bids_usd) + sum(asks_usd)

            depth_5_levels.append(depth_5)
            depth_10_levels.append(depth_10)
            depth_20_levels.append(depth_20)

            # Imbalance (based on USD value)
            bid_liquidity = sum(bids_usd[:20])
            ask_liquidity = sum(asks_usd[:20])
            imbalance_ratio = bid_liquidity / ask_liquidity if ask_liquidity > 0 else 1.0
            imbalance_ratios.append(imbalance_ratio)

            # Order sizes (still in base asset quantity)
            all_orders = [q for _, q in bids] + [q for _, q in asks]
            order_sizes.extend(all_orders)

            # Concentration (based on USD value)
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
        depth_is_concentrated = top_5_concentration > 50

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
            depth_shift_frequency=0.1,
            avg_shift_magnitude=0.3,
            shift_reaction_time=5.0,
            avg_order_size=avg_order_size,
            large_order_percentile_90=large_order_p90,
            large_order_percentile_95=large_order_p95,
            mm_presence_score=0.7,
            avg_quote_spread_layers=5,
            mm_update_frequency=12,
            top_5_concentration=top_5_concentration,
            top_10_concentration=top_10_concentration,
            depth_is_concentrated=depth_is_concentrated,
            depth_regime=depth_regime,
            regime_persistence=15.0,
            calculated_at=time.time(),
            snapshots_analyzed=len(depth_5_levels)
        )

        print(f"Orderbook depth context built:")
        print(f"   Avg Depth (5 levels): {avg_depth_5:,.0f}")
        print(f"   Avg Depth (20 levels): {avg_depth_20:,.0f}")
        print(f"   Depth Regime: {depth_regime}")
        print(f"   Top 5 Concentration: {top_5_concentration:.1f}%")
        print(f"   Strong Imbalance Threshold: {strong_imbalance_threshold:.2f}")
        print(f"   Snapshots: {len(depth_5_levels)}")

    def update_with_orderbook(self, orderbook: dict):
        """
        REAL-TIME PHASE: Analyze a given orderbook vs historical baseline.
        This method no longer fetches data itself.
        """
        if not orderbook:
            return

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
            predicted_direction = 'LONG'
            direction_confidence = min((imbalance_ratio - 1.0) / 0.5, 1.0)
        elif imbalance_ratio < 0.7:
            predicted_direction = 'SHORT'
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
        """This method is now disabled. Polling is replaced by on-demand fetching."""
        pass
