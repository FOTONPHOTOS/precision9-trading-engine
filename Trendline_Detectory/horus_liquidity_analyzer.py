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
from binance import AsyncClient
import logging

logger = logging.getLogger(__name__)


@dataclass
class HistoricalLiquidityContext:
    """Historical liquidity baseline for contextual analysis"""

    # Typical orderbook characteristics
    avg_total_liquidity: float
    avg_bid_liquidity: float
    avg_ask_liquidity: float
    avg_bid_ask_ratio: float

    # Spread characteristics
    avg_spread_bps: float
    avg_spread_usd: float
    tight_spread_threshold: float
    wide_spread_threshold: float

    # Liquidity concentration
    typical_wall_size: float
    large_wall_threshold: float
    avg_liquidity_clusters: int

    # Market depth
    avg_depth_1pct: float
    avg_depth_2pct: float
    depth_imbalance_threshold: float

    # Absorption patterns
    absorption_events_24h: int
    avg_absorption_size: float
    absorption_reaction_time: float

    # Liquidity regime
    liquidity_regime: str
    regime_stability: float

    # Wall behavior
    fake_wall_frequency: float
    wall_persistence_avg: float

    # Timestamp
    calculated_at: float
    snapshots_analyzed: int


@dataclass
class LiquidityZone:
    """Identified liquidity concentration zone"""
    price_level: float
    total_liquidity: float
    side: str  # 'bid' or 'ask'
    cluster_size: int
    distance_from_mid: float
    is_wall: bool
    wall_type: str  # 'support', 'resistance', 'institutional', 'fake'
    confidence: float


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
        self.orderbook_history = deque(maxlen=60)

        # Liquidity zone tracking
        self.detected_walls: List[LiquidityZone] = []
        self.absorption_events: List[Dict] = []

        # Wall persistence tracking
        self.wall_tracker: Dict[float, Dict] = {}

        # NEW: Time-aggregated liquidity heatmap
        self.liquidity_heatmap: Dict[float, float] = {}

    async def initialize_historical_context(self, snapshot_count: int = 200):
        """
        INITIALIZATION PHASE: Build liquidity baseline
        """
        print(f"Fetching {snapshot_count} historical orderbook snapshots for liquidity context...")

        orderbook_snapshots = []
        spreads = []
        bid_ask_ratios = []
        total_liquidities_usd = []
        wall_sizes = []

        for i in range(snapshot_count):
            if hasattr(self.client, 'get_orderbook'):
                orderbook = await self.client.get_orderbook(symbol=self.symbol, limit=100)
            else:
                orderbook = await self.client.futures_order_book(symbol=self.symbol, limit=100)

            if not orderbook or (not orderbook.get('b') and not orderbook.get('bids')):
                continue # Skip corrupted or empty snapshot

            bids_key = 'b' if 'b' in orderbook else 'bids'
            asks_key = 'a' if 'a' in orderbook else 'asks'

            bids = [(float(p), float(q)) for p, q in orderbook[bids_key]]
            asks = [(float(p), float(q)) for p, q in orderbook[asks_key]]

            if not bids or not asks:
                continue

            bid_liquidity_usd = sum(p * q for p, q in bids)
            ask_liquidity_usd = sum(p * q for p, q in asks)
            total_liquidity_usd = bid_liquidity_usd + ask_liquidity_usd

            mid_price = (bids[0][0] + asks[0][0]) / 2
            spread = asks[0][0] - bids[0][0]
            spread_bps = (spread / mid_price) * 10000

            bid_ask_ratio = bid_liquidity_usd / ask_liquidity_usd if ask_liquidity_usd > 0 else 1.0

            orderbook_snapshots.append(orderbook)
            spreads.append(spread_bps)
            bid_ask_ratios.append(bid_ask_ratio)
            total_liquidities_usd.append(total_liquidity_usd)

            max_bid_order = max(q for _, q in bids) if bids else 0
            max_ask_order = max(q for _, q in asks) if asks else 0
            wall_sizes.append(max(max_bid_order, max_ask_order))

            if i < snapshot_count - 1:
                await asyncio.sleep(3)

        if not orderbook_snapshots:
            logger.error("Could not build historical liquidity context, no valid snapshots found.")
            return

        # Calculate statistics with bilingual support
        def get_bids(ob): return ob.get('b') or ob.get('bids', [])
        def get_asks(ob): return ob.get('a') or ob.get('asks', [])

        avg_spread_bps = np.mean(spreads)
        avg_total_liquidity = np.mean(total_liquidities_usd)
        avg_bid_liquidity = np.mean([sum(float(p) * float(q) for p, q in get_bids(ob)) for ob in orderbook_snapshots])
        avg_ask_liquidity = np.mean([sum(float(p) * float(q) for p, q in get_asks(ob)) for ob in orderbook_snapshots])
        avg_bid_ask_ratio = np.mean(bid_ask_ratios)

        tight_spread_threshold = np.percentile(spreads, 25)
        wide_spread_threshold = np.percentile(spreads, 75)

        typical_wall_size = np.median(wall_sizes)
        large_wall_threshold = np.percentile(wall_sizes, 90)

        depths_1pct_usd = []
        depths_2pct_usd = []

        for ob in orderbook_snapshots:
            bids = get_bids(ob)
            asks = get_asks(ob)
            if not bids or not asks: continue
            mid = (float(bids[0][0]) + float(asks[0][0])) / 2

            depth_1pct = sum(float(p) * float(q) for p, q in bids if float(p) >= mid * 0.99) + \
                         sum(float(p) * float(q) for p, q in asks if float(p) <= mid * 1.01)

            depth_2pct = sum(float(p) * float(q) for p, q in bids if float(p) >= mid * 0.98) + \
                         sum(float(p) * float(q) for p, q in asks if float(p) <= mid * 1.02)

            depths_1pct_usd.append(depth_1pct)
            depths_2pct_usd.append(depth_2pct)

        avg_depth_1pct = np.mean(depths_1pct_usd) if depths_1pct_usd else 0
        avg_depth_2pct = np.mean(depths_2pct_usd) if depths_2pct_usd else 0

        if avg_depth_1pct > avg_total_liquidity * 0.6:
            liquidity_regime = 'deep'
            regime_stability = 0.8
        elif avg_depth_1pct < avg_total_liquidity * 0.3:
            liquidity_regime = 'shallow'
            regime_stability = 0.4
        else:
            liquidity_regime = 'moderate'
            regime_stability = 0.6

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
            avg_liquidity_clusters=5,
            avg_depth_1pct=avg_depth_1pct,
            avg_depth_2pct=avg_depth_2pct,
            depth_imbalance_threshold=1.5,
            absorption_events_24h=0,
            avg_absorption_size=0,
            absorption_reaction_time=5.0,
            liquidity_regime=liquidity_regime,
            regime_stability=regime_stability,
            fake_wall_frequency=0.15,
            wall_persistence_avg=30.0,
            calculated_at=time.time(),
            snapshots_analyzed=len(orderbook_snapshots)
        )

        print(f"Liquidity context built:")
        print(f"   Avg Liquidity: {avg_total_liquidity:,.0f}")
        print(f"   Avg Spread: {avg_spread_bps:.2f} bps")
        print(f"   Regime: {liquidity_regime} (stability: {regime_stability:.1%})")
        print(f"   Large Wall Threshold: {large_wall_threshold:,.0f}")
        print(f"   Snapshots: {len(orderbook_snapshots)}")

    def update_with_orderbook(self, orderbook: dict):
        """
        REAL-TIME PHASE: Analyze a given orderbook vs historical baseline.
        This method no longer fetches data itself.
        """
        if not orderbook:
            return

        self.current_orderbook = orderbook
        self.orderbook_history.append(orderbook)

        # NEW: Update the liquidity heatmap
        self._update_heatmap(orderbook)

        # Analyze current orderbook
        if 'b' in orderbook:
            bid_data = orderbook.get('b', [])
            ask_data = orderbook.get('a', [])
            bids = [(float(p), float(q)) for p, q in bid_data if len(str(p)) > 0 and len(str(q)) > 0]
            asks = [(float(p), float(q)) for p, q in ask_data if len(str(p)) > 0 and len(str(q)) > 0]
        else:
            bid_data = orderbook.get('bids', [])
            ask_data = orderbook.get('asks', [])
            bids = [(float(p), float(q)) for p, q in bid_data if len(str(p)) > 0 and len(str(q)) > 0]
            asks = [(float(p), float(q)) for p, q in ask_data if len(str(p)) > 0 and len(str(q)) > 0]

        mid_price = (bids[0][0] + asks[0][0]) / 2

        # Detect liquidity zones (now using the heatmap)
        self.detected_walls = self._detect_liquidity_hotspots(mid_price) # CHANGED

        # Track wall persistence
        self._track_wall_persistence()

        # Detect absorption events
        self._detect_absorption()

    def _update_heatmap(self, orderbook: dict, decay_factor: float = 0.95, prune_threshold: float = 0.1):
        """Updates the time-aggregated liquidity heatmap with a new orderbook."""
        # Check if orderbook is a valid dictionary before processing
        if not isinstance(orderbook, dict) or 'b' not in orderbook and 'bids' not in orderbook:
            # Log the error but don't crash the entire system
            if hasattr(orderbook, '__class__'):
                logger.warning(f"[{self.symbol}] Received non-dictionary orderbook object: {type(orderbook).__name__}. Skipping heatmap update.")
            else:
                logger.warning(f"[{self.symbol}] Invalid orderbook format. Skipping heatmap update.")
            return

        # 1. Apply decay to existing liquidity
        for price_level in self.liquidity_heatmap:
            self.liquidity_heatmap[price_level] *= decay_factor

        # 2. Add new liquidity from the current orderbook
        bids = []
        asks = []
        
        if 'b' in orderbook:  # New API format
            bid_data = orderbook.get('b', [])
            ask_data = orderbook.get('a', [])
            bids = [(float(p), float(q)) for p, q in bid_data if len(str(p)) > 0 and len(str(q)) > 0]
            asks = [(float(p), float(q)) for p, q in ask_data if len(str(p)) > 0 and len(str(q)) > 0]
        elif 'bids' in orderbook:  # Old API format
            bid_data = orderbook.get('bids', [])
            ask_data = orderbook.get('asks', [])
            bids = [(float(p), float(q)) for p, q in bid_data if len(str(p)) > 0 and len(str(q)) > 0]
            asks = [(float(p), float(q)) for p, q in ask_data if len(str(p)) > 0 and len(str(q)) > 0]
        
        for price, qty in bids + asks:
            # Round price to a certain precision to cluster levels
            rounded_price = round(price, 1) # Adjust precision as needed
            self.liquidity_heatmap[rounded_price] = self.liquidity_heatmap.get(rounded_price, 0) + qty

        # 3. Prune old/insignificant entries
        min_liquidity = max(self.liquidity_heatmap.values()) * prune_threshold if self.liquidity_heatmap else 0
        self.liquidity_heatmap = {
            price: qty for price, qty in self.liquidity_heatmap.items() if qty > min_liquidity
        }

    def _detect_liquidity_hotspots(self, mid_price: float, std_dev_threshold: float = 3.0) -> List[LiquidityZone]:
        """Identifies significant liquidity hotspots from the time-aggregated heatmap."""
        if not self.liquidity_heatmap or len(self.liquidity_heatmap) < 10:
            return []

        zones = []
        ctx = self.historical_context
        
        liquidity_values = list(self.liquidity_heatmap.values())
        avg_liquidity = np.mean(liquidity_values)
        std_dev_liquidity = np.std(liquidity_values)
        
        hotspot_threshold = avg_liquidity + (std_dev_liquidity * std_dev_threshold)

        for price, qty in self.liquidity_heatmap.items():
            if qty > hotspot_threshold:
                side = 'bid' if price < mid_price else 'ask'
                distance_pct = (abs(price - mid_price) / mid_price) * 100

                # Determine wall type based on significance
                if qty > avg_liquidity + (std_dev_liquidity * 5.0): # 5+ std devs
                    wall_type = 'institutional'
                    confidence = 0.9
                else:
                    wall_type = 'resistance' if side == 'ask' else 'support'
                    confidence = 0.8

                zones.append(LiquidityZone(
                    price_level=price,
                    total_liquidity=qty,
                    side=side,
                    cluster_size=1, # Cluster concept is now handled by aggregation
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
                    info['likely_fake'] = True

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

        # Handle both Bybit ('b') and Binance ('bids') formats
        prev_bids_key = 'b' if 'b' in prev_orderbook else 'bids'
        prev_asks_key = 'a' if 'a' in prev_orderbook else 'asks'
        curr_bids_key = 'b' if 'b' in current_orderbook else 'bids'
        curr_asks_key = 'a' if 'a' in current_orderbook else 'asks'

        # Compare bid side
        prev_bid_liquidity = sum(float(q) for _, q in prev_orderbook[prev_bids_key][:10])
        curr_bid_liquidity = sum(float(q) for _, q in current_orderbook[curr_bids_key][:10])

        # Compare ask side
        prev_ask_liquidity = sum(float(q) for _, q in prev_orderbook[prev_asks_key][:10])
        curr_ask_liquidity = sum(float(q) for _, q in current_orderbook[curr_asks_key][:10])

        # Detect significant liquidity decrease (absorption)
        if prev_bid_liquidity > 0:
            bid_decrease_pct = (prev_bid_liquidity - curr_bid_liquidity) / prev_bid_liquidity

            if bid_decrease_pct > 0.2:
                self.absorption_events.append({
                    'timestamp': time.time(),
                    'side': 'bid',
                    'amount_absorbed': prev_bid_liquidity - curr_bid_liquidity,
                    'decrease_pct': bid_decrease_pct
                })

        if prev_ask_liquidity > 0:
            ask_decrease_pct = (prev_ask_liquidity - curr_ask_liquidity) / prev_ask_liquidity

            if ask_decrease_pct > 0.2:
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
        bids_key = 'b' if 'b' in ob else 'bids'
        asks_key = 'a' if 'a' in ob else 'asks'

        bids = [(float(p), float(q)) for p, q in ob[bids_key]]
        asks = [(float(p), float(q)) for p, q in ob[asks_key]]

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
            'absorption_details': recent_absorption[-3:],

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
        """This method is now disabled. Polling is replaced by on-demand fetching."""
        pass
