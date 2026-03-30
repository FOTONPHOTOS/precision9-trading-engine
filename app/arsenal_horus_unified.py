"""Arsenal Horus Unified Interface
================================
Brings together CVD, Liquidity, and Orderbook analysis with historical context

This is a NEW implementation using direct Binance data + historical context,
separate from the existing Horus system that uses WebSocket to unified_oracle_processor.

Usage:
    collector = ArsenalHorusUnified(symbol="SOLUSDT")
    await collector.initialize()

    # Get complete market intelligence
    snapshot = await collector.get_full_snapshot()

    # Check entry conditions
    entry_signal = collector.should_enter_trade(arsenal_setup)
"""

import asyncio
import time # NEW
import logging # NEW
from dataclasses import dataclass
from typing import Dict, Optional, List
from binance import AsyncClient

from horus_cvd_collector import ArsenalCVDCollector
from horus_liquidity_analyzer import ArsenalLiquidityAnalyzer
from horus_orderbook_analyzer import ArsenalOrderbookAnalyzer
from kalman_filter import KalmanFilter

logger = logging.getLogger(__name__) # NEW


@dataclass
class MarketIntelligence:
    """Complete market intelligence snapshot"""

    # CVD Intelligence
    cvd_value: float
    cvd_z_score: float
    cvd_momentum: str
    has_divergence: bool
    divergence_type: str

    # Liquidity Intelligence
    total_liquidity: float
    liquidity_vs_avg: float
    detected_walls: int
    institutional_walls: int
    recent_absorption: int
    liquidity_quality: str

    # Orderbook Depth Intelligence
    imbalance_ratio: float
    is_strong_imbalance: bool
    predicted_direction: str
    direction_confidence: float
    has_recent_shift: bool
    signal_strength: str

    # Overall Assessment
    overall_quality: str
    entry_recommendation: str
    confidence_score: float
    risk_factors: list


class ArsenalHorusUnified:
    """
    Unified data collector for Arsenal

    Combines:
    - CVD analysis with historical context
    - Liquidity wall detection
    - Orderbook depth imbalance

    Provides:
    - Complete market intelligence snapshots
    - Entry timing recommendations
    - Risk assessment
    """

    def __init__(self, symbol: str = "SOLUSDT", client: Optional[AsyncClient] = None):
        self.symbol = symbol
        self.client = client # Centralized AsyncClient

        # Components (initialized later)
        self.cvd_collector: Optional[ArsenalCVDCollector] = None
        self.liquidity_analyzer: Optional[ArsenalLiquidityAnalyzer] = None
        self.orderbook_analyzer: Optional[ArsenalOrderbookAnalyzer] = None

        # Kalman filter for CVD smoothing
        self.cvd_filter = KalmanFilter(process_variance=1e-5, measurement_variance=1e-2)

        self.is_initialized = False
        self.time_offset = 0 # NEW: For server time synchronization

    @property
    def is_receiving_trades(self) -> bool:
        """Returns True if the CVD collector is actively receiving trades from the WebSocket."""
        if self.cvd_collector:
            return self.cvd_collector.is_receiving_data
        return False

    async def _sync_server_time(self):
        """Synchronizes local time with Binance server time to account for clock skew."""
        try:
            server_time_response = await self.client.get_server_time()
            server_time_ms = server_time_response['serverTime']
            local_time_ms = int(time.time() * 1000)
            self.time_offset = server_time_ms - local_time_ms
            logger.info(f"Binance server time synchronized. Offset: {self.time_offset}ms")
        except Exception as e:
            logger.error(f"Failed to synchronize time with Binance server: {e}")
            self.time_offset = 0 # Default to no offset on failure

    async def initialize(self, snapshot_count: int = 200):
        """
        Initialize all components with historical context.

        Args:
            snapshot_count: The number of historical orderbook snapshots to fetch.
                            Default is 200 for full context, 10 for fast start.
        """
        print("=" * 60)
        print("Arsenal Horus Unified Collector - Initialization")
        print("=" * 60)

        # Ensure client is provided
        if not self.client:
            raise RuntimeError("AsyncClient not provided to ArsenalHorusUnified constructor.")

        # NEW: Synchronize time with Binance server
        await self._sync_server_time()

        # Initialize CVD collector (always fetches 500 candles, which is fast)
        print("\n[1/3] Initializing CVD Collector...")
        self.cvd_collector = ArsenalCVDCollector(self.client, self.symbol)
        await self.cvd_collector.initialize_historical_context()

        # Initialize Liquidity and Orderbook analyzers in parallel
        print(f"\n[2/3] Initializing Liquidity Analyzer ({snapshot_count} snapshots)...")
        print(f"[3/3] Initializing Orderbook Analyzer ({snapshot_count} snapshots)...")
        if snapshot_count > 10:
            print("(Running in parallel - this will take a few minutes)")

        self.liquidity_analyzer = ArsenalLiquidityAnalyzer(self.client, self.symbol)
        self.orderbook_analyzer = ArsenalOrderbookAnalyzer(self.client, self.symbol)

        await asyncio.gather(
            self.liquidity_analyzer.initialize_historical_context(snapshot_count=snapshot_count),
            self.orderbook_analyzer.initialize_historical_context(snapshot_count=snapshot_count)
        )

        self.is_initialized = True

        print("\n" + "=" * 60)
        print("Initialization Complete!")
        print("=" * 60)
        print(f"Symbol: {self.symbol}")
        print(f"CVD Context: {self.cvd_collector.historical_context.data_points} candles")
        print(f"Liquidity Context: {self.liquidity_analyzer.historical_context.snapshots_analyzed} snapshots")
        print(f"Orderbook Context: {self.orderbook_analyzer.historical_context.snapshots_analyzed} snapshots")
        print("=" * 60 + "\n")

    async def start_real_time_monitoring(self):
        """
        Start real-time monitoring of all components

        CVD: WebSocket trade stream
        Liquidity: Polling every 1 second
        Orderbook: Polling every 1 second
        """
        if not self.is_initialized:
            raise RuntimeError("Must call initialize() before starting real-time monitoring")

        # Only the CVD WebSocket needs to run continuously in the background.
        # The other analyzers will be updated on-demand.
        await asyncio.gather(
            self.cvd_collector.start_websocket()
            # self.liquidity_analyzer.monitor_liquidity(), # DISABLED
            # self.orderbook_analyzer.monitor_depth()      # DISABLED
        )

    async def get_full_snapshot(self, orderbook: dict = None) -> MarketIntelligence:
        """
        Get complete market intelligence snapshot.
        Now fetches the orderbook on-demand if not provided.
        """
        if not self.is_initialized:
            raise RuntimeError("Must call initialize() first")

        # If no orderbook is passed in, fetch it once.
        if orderbook is None:
            try:
                orderbook = await self.client.futures_order_book(
                    symbol=self.symbol,
                    limit=100
                )
            except Exception as e:
                logger.error(f"Failed to fetch orderbook on-demand: {e}")
                # Return a basic snapshot or re-raise?
                # For now, let's allow it to fail and be caught by the sampler.
                raise

        # Update analyzers with the single, fresh orderbook snapshot
        self.liquidity_analyzer.update_with_orderbook(orderbook)
        self.orderbook_analyzer.update_with_orderbook(orderbook)

        # Get snapshots from each component
        cvd_data = self.cvd_collector.get_contextual_snapshot()
        liquidity_data = self.liquidity_analyzer.get_contextual_snapshot()
        orderbook_data = self.orderbook_analyzer.get_contextual_snapshot()

        # --- NEW: Apply Kalman Filter to CVD ---
        smoothed_cvd = self.cvd_filter.update(cvd_data['cvd_value'])
        cvd_data['cvd_value'] = smoothed_cvd

        # Calculate overall assessment
        overall_quality, entry_rec, confidence, risks = self._assess_market_conditions(
            cvd_data, liquidity_data, orderbook_data
        )

        return MarketIntelligence(
            # CVD
            cvd_value=cvd_data['cvd_value'],
            cvd_z_score=cvd_data.get('cvd_z_score', 0.0), # Use .get for safety
            cvd_momentum=cvd_data['cvd_momentum'],
            has_divergence=cvd_data['has_divergence'],
            divergence_type=cvd_data['divergence_type'],

            # Liquidity
            total_liquidity=liquidity_data['total_liquidity'],
            liquidity_vs_avg=liquidity_data['liquidity_vs_avg'],
            detected_walls=liquidity_data['detected_walls'],
            institutional_walls=liquidity_data['institutional_walls'],
            recent_absorption=liquidity_data['recent_absorption_events'],
            liquidity_quality=liquidity_data['liquidity_quality'],

            # Orderbook
            imbalance_ratio=orderbook_data['imbalance_ratio'],
            is_strong_imbalance=orderbook_data['is_strong_imbalance'],
            predicted_direction=orderbook_data['predicted_direction'],
            direction_confidence=orderbook_data['direction_confidence'],
            has_recent_shift=orderbook_data['has_recent_shift'],
            signal_strength=orderbook_data['signal_strength'],

            # Overall
            overall_quality=overall_quality,
            entry_recommendation=entry_rec,
            confidence_score=confidence,
            risk_factors=risks
        )

    def _assess_market_conditions(self, cvd_data: Dict, liquidity_data: Dict,
                                   orderbook_data: Dict) -> tuple:
        """
        Assess overall market conditions and generate entry recommendation

        Returns: (overall_quality, entry_recommendation, confidence_score, risk_factors)
        """
        risk_factors = []
        quality_score = 0
        cvd_z_score = cvd_data.get('cvd_z_score', 0.0)

        # CVD Assessment (0-30 points) using Z-Score
        if abs(cvd_z_score) > 2.0: # Strong signal
            quality_score += 20
        elif abs(cvd_z_score) > 1.0: # Moderate signal
            quality_score += 10

        if cvd_data['cvd_momentum'] == 'accelerating':
            quality_score += 10
        elif cvd_data['cvd_momentum'] == 'decelerating':
            risk_factors.append("CVD decelerating")

        if cvd_data['has_divergence']:
            risk_factors.append(f"{cvd_data['divergence_type']} divergence detected")
            quality_score -= 10

        # Liquidity Assessment (0-35 points)
        if liquidity_data['liquidity_quality'] == 'excellent':
            quality_score += 15
        elif liquidity_data['liquidity_quality'] == 'good':
            quality_score += 8

        if liquidity_data['institutional_walls'] > 0:
            risk_factors.append(f"{liquidity_data['institutional_walls']} institutional walls detected")

        if liquidity_data['recent_absorption_events'] > 0:
            quality_score += 10  # Absorption = momentum

        if liquidity_data.get('spread_quality') == 'tight': # Use .get for safety
            quality_score += 10
        elif liquidity_data.get('spread_quality') == 'wide':
            risk_factors.append("Wide spread - low liquidity")
            quality_score -= 5

        # Orderbook Assessment (0-35 points)
        if orderbook_data['signal_strength'] == 'strong':
            quality_score += 20
        elif orderbook_data['signal_strength'] == 'moderate':
            quality_score += 10

        if orderbook_data['is_strong_imbalance']:
            quality_score += 15

        if orderbook_data['has_recent_shift']:
            risk_factors.append("Recent depth shift detected")

        # Calculate overall quality (0-100)
        quality_score = max(0, min(100, quality_score))

        if quality_score >= 80:
            overall_quality = 'EXCELLENT'
            entry_recommendation = 'STRONG_ENTER'
        elif quality_score >= 60:
            overall_quality = 'GOOD'
            entry_recommendation = 'ENTER'
        elif quality_score >= 40:
            overall_quality = 'FAIR'
            entry_recommendation = 'WAIT'
        else:
            overall_quality = 'POOR'
            entry_recommendation = 'SKIP'

        confidence_score = quality_score / 100

        return overall_quality, entry_recommendation, confidence_score, risk_factors

    def should_enter_trade(self, arsenal_direction: str, arsenal_confidence: float) -> Dict:
        """
        Final entry decision combining Arsenal setup with Horus intelligence

        Args:
            arsenal_direction: 'LONG' or 'SHORT' from Arsenal
            arsenal_confidence: 0-1 confidence from Arsenal

        Returns:
            {
                'should_enter': bool,
                'final_confidence': float,
                'horus_confirmation': bool,
                'reasons': list,
                'warnings': list
            }
        """
        if not self.is_initialized:
            return {
                'should_enter': False,
                'final_confidence': 0.0,
                'horus_confirmation': False,
                'reasons': ['Horus not initialized'],
                'warnings': []
            }

        # Get current snapshot (blocking - should be called from async context)
        import asyncio
        loop = asyncio.get_event_loop()
        snapshot = loop.run_until_complete(self.get_full_snapshot())

        reasons = []
        warnings = []
        horus_confirmation = False

        # Check CVD confirmation using Z-Score
        if arsenal_direction == 'LONG':
            if snapshot.cvd_z_score > 1.5 and snapshot.cvd_momentum == 'accelerating':
                reasons.append("Strong bullish CVD flow (Z-Score > 1.5)")
                horus_confirmation = True
            elif snapshot.cvd_z_score < -1.0:
                warnings.append(f"Bearish CVD (Z-Score: {snapshot.cvd_z_score:.2f}) contradicts LONG setup")

        elif arsenal_direction == 'SHORT':
            if snapshot.cvd_z_score < -1.5 and snapshot.cvd_momentum == 'accelerating':
                reasons.append("Strong bearish CVD flow (Z-Score < -1.5)")
                horus_confirmation = True
            elif snapshot.cvd_z_score > 1.0:
                warnings.append(f"Bullish CVD (Z-Score: {snapshot.cvd_z_score:.2f}) contradicts SHORT setup")

        # Check orderbook confirmation
        if snapshot.predicted_direction == arsenal_direction and snapshot.direction_confidence > 0.7:
            reasons.append(f"Orderbook imbalance confirms {arsenal_direction}")
            horus_confirmation = True
        elif snapshot.predicted_direction != arsenal_direction and snapshot.direction_confidence > 0.5:
            warnings.append(f"Orderbook suggests {snapshot.predicted_direction}, not {arsenal_direction}")

        # Check liquidity
        if snapshot.liquidity_quality in ['excellent', 'good']:
            reasons.append("Healthy liquidity environment")
        else:
            warnings.append("Poor liquidity - higher slippage risk")

        # Add risk factors
        warnings.extend(snapshot.risk_factors)

        # Final decision
        final_confidence = (arsenal_confidence + snapshot.confidence_score) / 2

        should_enter = (
            horus_confirmation and
            final_confidence > 0.6 and
            len(warnings) < 3 and
            snapshot.entry_recommendation in ['ENTER', 'STRONG_ENTER']
        )

        return {
            'should_enter': should_enter,
            'final_confidence': final_confidence,
            'horus_confirmation': horus_confirmation,
            'reasons': reasons,
            'warnings': warnings
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self.client:
            await self.client.close_connection()

    def get_raw_trades(self, since_timestamp: float) -> List[Dict]:
        """Pass-through method to get recent raw trades from the CVD collector."""
        if self.cvd_collector:
            return self.cvd_collector.get_recent_trades(since_timestamp)
        return []

    def get_current_server_time(self) -> int:
        """Returns the current server time in milliseconds, adjusted by the time offset."""
        return int(time.time() * 1000) + self.time_offset

    def get_recent_cvd_history(self) -> List[float]:
        """Pass-through method to get recent CVD history from the collector."""
        if self.cvd_collector:
            return self.cvd_collector.get_recent_cvd_history()
        return []


# Example usage
async def main():
    """Example: Initialize and use the unified collector"""

    # Initialize collector
    collector = ArsenalHorusUnified(symbol="SOLUSDT")
    await collector.initialize()

    # Get market intelligence
    snapshot = await collector.get_full_snapshot()

    print("\nMarket Intelligence Snapshot:")
    print(f"CVD Z-Score: {snapshot.cvd_z_score:.2f}")
    print(f"CVD Momentum: {snapshot.cvd_momentum}")
    print(f"Liquidity Quality: {snapshot.liquidity_quality}")
    print(f"Orderbook Direction: {snapshot.predicted_direction} ({snapshot.direction_confidence:.1%})")
    print(f"Overall Quality: {snapshot.overall_quality}")
    print(f"Entry Recommendation: {snapshot.entry_recommendation}")
    print(f"Confidence Score: {snapshot.confidence_score:.1%}")

    if snapshot.risk_factors:
        print(f"\nRisk Factors:")
        for risk in snapshot.risk_factors:
            print(f"  - {risk}")

    # Simulate Arsenal sending a setup
    arsenal_direction = "LONG"
    arsenal_confidence = 0.85

    decision = collector.should_enter_trade(arsenal_direction, arsenal_confidence)

    print(f"\nEntry Decision:")
    print(f"Should Enter: {decision['should_enter']}")
    print(f"Final Confidence: {decision['final_confidence']:.1%}")
    print(f"Horus Confirmation: {decision['horus_confirmation']}")

    if decision['reasons']:
        print(f"\nReasons:")
        for reason in decision['reasons']:
            print(f"  + {reason}")

    if decision['warnings']:
        print(f"\nWarnings:")
        for warning in decision['warnings']:
            print(f"  ! {warning}")

    await collector.cleanup()


if __name__ == "__main__":
    asyncio.run(main())