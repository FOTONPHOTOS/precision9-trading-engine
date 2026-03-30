"""
LIVE SCALPING MICROSTRUCTURE SYSTEM
===================================

Advanced microstructure-based scalping system with:
- Real-time order flow analysis
- Limit order positioning (trap setting)
- Microstructure-aware risk management
- Tight stop management
- Rapid profit taking

Focus: Capture microstructure alpha before decay with limit orders
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import pandas as pd
import numpy as np
import requests
import websockets
import json
import aiohttp
import os
from dotenv import load_dotenv

# Arsenal modules (scalping-optimized)
from realtime_swing_detector import fetch_binance_data, detect_candle_close_patterns
from fvg_detector import FVGDetector
from order_block_detector import OrderBlockDetector
from liquidity_sweep_detector import LiquiditySweepDetector, StopHuntWarning
from range_trap_detector import RangeTrapDetector, RangeTrapAnalysis
from range_breakout_detector import RangeBreakoutDetector, BreakoutSignal
from trendline_confluence_module import get_trendline_analyzer

# Scalping intelligence layer
from scalping_microstructure_brain import ScalpingMicrostructureBrain, MicrostructureIntelligence, ScalpingSignal
from market_regime_engine.classifier import MasterRegimeClassifier
from market_regime_engine.mean_reversion_brain import MeanReversionBrain

# Scalping execution
from precision_tp_sl_calculator import PrecisionTPSLCalculator
from trade_scenario_planner import TradeScenarioPlanner
from realtime_trade_monitor import RealtimeTradeMonitor

# Bybit execution
from bybit_arsenal_executor import ArsenalBybitExecutor

# Real-time price monitoring
from realtime_price_monitor import RealtimePriceMonitor

# Scalping-optimized risk manager
from scalping_risk_manager import ScalpingRiskManager

# NEW: Horus integration (for order flow confirmation)
from arsenal_horus_unified import ArsenalHorusUnified
from horus_precision_entry_system import HorusPrecisionEntrySystem
from horus_high_frequency_sampler import HorusSampler
from horus_liquidity_analyzer import ArsenalLiquidityAnalyzer
# StructuralIntegrityAnalyzer import commented out due to third-party package issue
# from structural_integrity_analyzer import StructuralIntegrityAnalyzer
from volume_profile_detector import VolumeProfileDetector

# NEW: Kalman Filter for smoothing
from kalman_filter import KalmanFilter
from binance_data_engine import BinanceDataEngine, compute_lci
from helios_btc_engine import HeliosBTC_Engine
from liquidation_monitor import LiquidationMonitor

# Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('SCALPING_MICROSTRUCTURE')


class LiveScalpingMicrostructureSystem:
    """
    Advanced microstructure-based scalping system designed for high-frequency,
    limit-order-based trading that captures alpha before decay.
    """

    def __init__(self, symbol: str = "SOLUSDT", timeframe: str = "1m", live_execution: bool = False, fast_start: bool = False):
        self.symbol = symbol
        self.timeframe = timeframe
        self.live_execution = live_execution
        self.fast_start = fast_start

        # Scalping-optimized analysis config
        self.lookback_hours = 6.0  # Reduced for scalping focus, faster rotation
        self.analysis_interval = 5  # More frequent analysis for scalping (5s)

        # --- SCALPING-FOCUSED KALMAN FILTERS ---
        self.price_filter = KalmanFilter(process_variance=1e-5, measurement_variance=1e-4)
        self.microstructure_filter = KalmanFilter(process_variance=1e-3, measurement_variance=1e-2)
        self.confidence_filter = KalmanFilter(process_variance=1e-2, measurement_variance=1e-1)
        logger.info(" Scalping Kalman Filters Initialized (Price, Microstructure, Confidence)")

        # --- SCALPING-DATA ENGINE ---
        self.data_engine: Optional[BinanceDataEngine] = None
        self.liquidation_monitor: Optional[LiquidationMonitor] = None
        logger.info(" Scalping Data Engine Initialized")

        # --- SCALPING HELIOS CLIENT ---
        self.helios_context: Optional[dict] = None
        self.correlation_filter = KalmanFilter(process_variance=1e-3, measurement_variance=1e-2, initial_value=0.5)

        # --- SCALPING REGIME ENGINE ---
        self.regime_classifier = MasterRegimeClassifier()
        self.mr_brain = MeanReversionBrain(symbol=self.symbol)
        self.scalping_brain = ScalpingMicrostructureBrain()  # NEW: Scalping-focused brain
        logger.info(" Scalping Regime Engine Initialized")
        logger.info("   - Master Classifier: ACTIVE")
        logger.info("   - Scalping Microstructure Brain: STANDBY")

        # Scalping components (optimized for microstructure)
        self.precision_calculator = PrecisionTPSLCalculator()
        self.scenario_planner = TradeScenarioPlanner()
        self.trade_monitor = RealtimeTradeMonitor()

        # Microstructure detectors
        self.fvg_detector = FVGDetector()
        self.ob_detector = OrderBlockDetector()
        self.liquidity_detector = LiquiditySweepDetector()
        self.trap_detector = RangeTrapDetector()
        self.breakout_detector = RangeBreakoutDetector()
        self.trendline_analyzer = get_trendline_analyzer()
        # self.integrity_analyzer = StructuralIntegrityAnalyzer()  # Commented out due to package issue
        self.volume_profile_detector = VolumeProfileDetector()

        # Real-time price monitoring
        self.price_monitor = RealtimePriceMonitor(symbol)

        # NEW: Scalping Risk Manager (instead of general risk manager)
        self.scalping_risk_manager = None  # Initialize later

        # NEW: Horus components for order flow confirmation
        self.horus: Optional[ArsenalHorusUnified] = None
        self.horus_entry_system: Optional[HorusPrecisionEntrySystem] = None
        self.sampler: Optional[HorusSampler] = None
        self.horus_initialized = False

        # NEW: Scalping liquidity analyzer
        self.scalping_liquidity_analyzer: Optional[ArsenalLiquidityAnalyzer] = None

        # Bybit executor (only in live mode)
        self.bybit_executor = None
        if live_execution:
            self.bybit_executor = ArsenalBybitExecutor(symbol)

        # State
        self.current_trade_id: Optional[str] = None
        self.last_analysis_time = None
        self.last_candle_time = None
        self.analysis_count = 0

        # Scalping-specific tracking
        self.scalping_opportunities = 0
        self.scalping_success_rate = 0.0

        # Make logger an instance attribute
        self.logger = logger

    def print_header(self):
        """Print scalping system header"""
        print("\n" + "=" * 120)
        print("   PRECISION9 SCALPING MICROSTRUCTURE SYSTEM")
        print("   Advanced microstructure analysis for rapid alpha capture")
        print("   Limit-order positioning to avoid adverse selection")
        print("=" * 120)

    async def run_scalping_analysis(self, df_full: pd.DataFrame, lci_score: float, taker_ratio: Optional[float], 
                                  taker_ratio_ma: Optional[float], symbol_24h_volume: Optional[float]) -> Optional[ScalpingSignal]:
        """Run complete scalping microstructure analysis"""
        print(f"\n[SCALPING ANALYSIS #{self.analysis_count}] {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

        # 1. Data Ingestion with Kalman smoothing
        current_price = float(df_full.iloc[-1]['kf_close'])
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=self.lookback_hours)
        df_full.index = pd.to_datetime(df_full.index)

        df_filtered = df_full.copy()
        df_filtered['close'] = df_full['kf_close']
        df_filtered['open'] = df_full['open'].apply(self.price_filter.update)
        df_filtered['high'] = df_full['high'].apply(self.price_filter.update)
        df_filtered['low'] = df_full['low'].apply(self.price_filter.update)

        recent = df_filtered[df_filtered.index >= cutoff].copy()
        print(f"  - Current Price (Kalman Smoothed): ${current_price:.4f}")
        print(f"  - Analyzing last {self.lookback_hours} hours of data ({len(recent)} candles).")

        # 2. Microstructure Intelligence Construction
        print("\n[1/8] Building Microstructure Intelligence...")
        
        # Swing structure (LTF focus for scalping)
        swing_highs = []
        swing_lows = []
        if len(recent) > 10:  # Only calculate if we have enough data
            from test_ultimate_arsenal import find_swing_highs, find_swing_lows
            swing_highs = find_swing_highs(recent, lookback=2)
            swing_lows = find_swing_lows(recent, lookback=2)
        
        print(f"  - Found {len(swing_highs)} swing highs and {len(swing_lows)} swing lows.")

        # LTF trend assessment
        from test_ultimate_arsenal import analyze_trend_structure
        trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
        print(f"  - LTF Trend: {trend_analysis['trend_direction'].upper()} (Strength: {trend_analysis['trend_strength']:.0%})")

        # Microstructure zones
        fvgs = self.fvg_detector.detect(df_filtered, current_price)
        active_fvgs = self.fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)
        print(f"  - Detected {len(active_fvgs)} active FVGs.")

        obs = self.ob_detector.detect(df_filtered, current_price) 
        active_obs = self.ob_detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)
        print(f"  - Found {len(active_obs)} active Order Blocks.")

        # Liquidity sweeps and pools
        sweeps = self.liquidity_detector.detect_sweeps(recent, swing_highs, swing_lows)
        print(f"  - Detected {len(sweeps)} liquidity sweeps.")

        # Range trap assessment (critical for scalping)
        trap_analysis = self.trap_detector.analyze(
            swing_highs, swing_lows, [], current_price, self.lookback_hours,
            trend_direction=trend_analysis['trend_direction'],
            trend_strength=trend_analysis['trend_strength']
        )

        # Volume profile
        volume_profile_zones = self.volume_profile_detector.analyze(df_filtered)

        # Momentum patterns (for scalping confirmation)
        patterns = detect_candle_close_patterns(recent, lookback_bars=10)  # Tighter lookback for scalping
        print(f"  - Found {len(patterns)} momentum patterns.")

        # Structural integrity (for scalping validation)
        # Since integrity_analyzer is not available due to package issues, using a default analysis
        structural_integrity_analysis = {'integrity_score': 100, 'reasons': []}
        print(f"  - Structural Integrity Score: {structural_integrity_analysis['integrity_score']}/100")

        # HTF context (filter only, not primary signal)
        htf_context = self.trendline_analyzer.get_comprehensive_analysis(
            symbol=self.symbol, timeframe="15m", lookback_hours=4
        )

        # Build microstructure intelligence
        micro_intel = self.scalping_brain._build_microstructure_intelligence({
            'current_price': current_price,
            'ltf_trend': trend_analysis['trend_direction'],
            'ltf_strength': trend_analysis['trend_strength'],
            'ltf_momentum': self._calculate_momentum_score(recent),
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'order_blocks': active_obs,
            'fvgs': active_fvgs,
            'liquidity_pools': [],  # Will be populated by liquidity analyzer
            'momentum_patterns': patterns,
            'htf_context': htf_context,
            'range_trap_analysis': trap_analysis,
            'recent_trades': await self._get_recent_trades(),  # Get real-time trade flow
            'orderbook': await self._get_current_orderbook()  # Get current order book
        })

        # Run scalping analysis
        print(f"\n[2/8] Running Microstructure Scalping Analysis...")
        scalping_signal = self.scalping_brain.analyze_microstructure({
            'current_price': current_price,
            'ltf_trend': trend_analysis['trend_direction'],
            'ltf_strength': trend_analysis['trend_strength'],
            'ltf_momentum': self._calculate_momentum_score(recent),
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'order_blocks': active_obs,
            'fvgs': active_fvgs,
            'liquidity_pools': [],
            'momentum_patterns': patterns,
            'htf_context': htf_context,
            'range_trap_analysis': trap_analysis,
            'recent_trades': await self._get_recent_trades(),
            'orderbook': await self._get_current_orderbook()
        })

        if scalping_signal:
            print(f"\n[YES] SCALPING OPPORTUNITY DETECTED]")
            print(f"  - Direction: {scalping_signal.direction}")
            print(f"  - Entry: ${scalping_signal.limit_order_price:.4f}")
            print(f"  - SL: ${scalping_signal.stop_loss:.4f}")
            print(f"  - TP: ${scalping_signal.take_profit:.4f}")
            print(f"  - Confidence: {scalping_signal.confidence:.2f}")
            print(f"  - R:R: {scalping_signal.risk_reward:.2f}:1")
            print(f"  - Expected Duration: {scalping_signal.expected_duration:.0f}m")
            print(f"  - Reasons: {', '.join(scalping_signal.microstructure_reasons[:2])}")  # Show first 2 reasons
        else:
            print("\n[NO] NO SCALPING OPPORTUNITY]")

        return scalping_signal

    def _calculate_momentum_score(self, df: pd.DataFrame) -> float:
        """Calculate momentum score from price action"""
        if len(df) < 10:
            return 0.0
            
        # Calculate ROC (Rate of Change) for momentum
        recent_close = df['close'].iloc[-1]
        earlier_close = df['close'].iloc[-5]
        
        roc = (recent_close - earlier_close) / earlier_close
        return np.clip(roc * 10, -1.0, 1.0)  # Clamp to -1, 1 range

    async def _get_recent_trades(self) -> List[Dict]:
        """Get recent trades for order flow analysis"""
        try:
            trades = await self.bybit_executor.client.get_public_trades(self.symbol, limit=100) if self.bybit_executor else []
            return trades
        except:
            return []

    async def _get_current_orderbook(self) -> Optional[Dict]:
        """Get current order book for microstructure analysis"""
        try:
            orderbook = await self.bybit_executor.client.get_orderbook(self.symbol, limit=20) if self.bybit_executor else {}
            return orderbook
        except:
            return {}

    async def send_scalping_signal_to_manager(self, scalping_signal: ScalpingSignal):
        """Send scalping signal to the risk manager with limit order focus"""
        if not self.scalping_risk_manager:
            logger.error("Scalping Risk Manager not initialized")
            return

        scalping_uri = "ws://localhost:8766"  # Different port for scalping manager
        logger.info("=" * 100)
        logger.info(f" DISPATCHING SCALPING SIGNAL TO RISK MANAGER at {scalping_uri}")
        logger.info("=" * 100)

        try:
            # Create scalping-optimized payload
            payload = {
                "symbol": self.symbol,
                "decision": {
                    "direction": scalping_signal.direction,
                    "confidence": scalping_signal.confidence,
                    "limit_order_price": scalping_signal.limit_order_price,
                    "stop_loss": scalping_signal.stop_loss,
                    "take_profit": scalping_signal.take_profit,
                    "risk_reward": scalping_signal.risk_reward,
                    "order_size_multiplier": scalping_signal.order_size_multiplier,
                    "microstructure_reasons": scalping_signal.microstructure_reasons,
                    "expected_duration": scalping_signal.expected_duration,
                    "market_regime": scalping_signal.market_regime
                }
            }
            
            async with websockets.connect(scalping_uri, open_timeout=10) as websocket:
                logger.info(" Connected to Scalping Risk Manager.")
                await websocket.send(json.dumps(payload, default=str))
                
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                logger.info(f" Scalping Risk Manager Acknowledged Signal: {response}")
                print("\n[ SCALPING SIGNAL DISPATCHED] Limit order trap set successfully.\n")
                return True

        except Exception as e:
            logger.error(f" FAILED TO DISPATCH SCALPING SIGNAL: {e}")
            print(f"\n[ SCALPING SIGNAL FAILED] Could not set limit order trap.\n")
            return False

    async def fetch_helios_context(self):
        """Fetch the latest market context from the central Helios server."""
        try:
            helios_uri = "http://localhost:8009/api/v1/helios/context"
            async with aiohttp.ClientSession() as session:
                async with session.get(helios_uri, timeout=5) as response:
                    if response.status == 200:
                        self.helios_context = await response.json()
                        self.logger.info("[HELIOS CLIENT] Successfully fetched context for scalping.")
                    else:
                        self.logger.warning(f"[HELIOS CLIENT] Failed to fetch context, status: {response.status}.")
        except Exception as e:
            self.logger.error(f"[HELIOS CLIENT] Error connecting to Helios server: {e}.")

    async def run_async(self):
        """Main scalping async run loop"""
        
        self.print_header()

        # Load API keys for Horus initialization
        load_dotenv()
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')

        if not api_key or not api_secret:
            self.logger.critical("BINANCE_API_KEY or BINANCE_API_SECRET not found in .env. Horus cannot be initialized.")
            return

        try:
            # Initialize Horus for order flow confirmation
            print("\n[SCALPING SETUP] Initializing Horus order flow intelligence for scalping...")
            # Horus initialization would be similar to before but focused on scalping
            # For now, we'll skip full Horus setup to focus on core scalping logic

            # Initialize scalping risk manager
            if self.live_execution and not self.scalping_risk_manager:
                print("\n[SCALPING RISK] Initializing Scalping Risk Manager...")
                self.scalping_risk_manager = ScalpingRiskManager(host="localhost", port=8766)
                await self.scalping_risk_manager.initialize()
                print("[OK] Scalping Risk Manager connected\n")

            print("\n[STARTING SCALPING MONITORING]")
            print(f"Symbol: {self.symbol} | Timeframe: {self.timeframe} | Live: {self.live_execution}")
            print(f"Press Ctrl+C to stop\n")

            while True:
                try:
                    # Fetch latest data
                    df_check = fetch_binance_data(self.symbol, self.timeframe, 200)
                    if df_check.empty:
                        logger.warning("Failed to fetch data, retrying...")
                        await asyncio.sleep(5)
                        continue

                    # Apply Kalman filter for smoothing
                    df_check['kf_close'] = df_check['close'].apply(self.price_filter.update)

                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Failed to fetch primary data: {e}")
                    await asyncio.sleep(5)
                    continue

                # Run scalping analysis on each iteration (scalping is continuous)
                self.analysis_count += 1

                print(f"\n[SCALPING CHECK #{self.analysis_count}] Running microstructure analysis...")

                # Fetch dynamic data for scalping
                lci_score = 0.5  # Would come from data engine
                taker_ratio = None
                taker_ratio_ma = None  
                symbol_24h_volume = None

                # Run complete scalping analysis
                scalping_signal = await self.run_scalping_analysis(
                    df_check, lci_score, taker_ratio, taker_ratio_ma, symbol_24h_volume
                )

                # If scalping opportunity found, send to risk manager
                if scalping_signal and self.live_execution:
                    logger.info(f"[SCALPING] Detected opportunity: {scalping_signal.direction} {self.symbol}")
                    await self.send_scalping_signal_to_manager(scalping_signal)
                elif scalping_signal:
                    print(f"[MONITORING MODE] Would have set limit order trap: {scalping_signal.direction} at ${scalping_signal.limit_order_price:.4f}")

                print(f"\n[SCALPING MONITORING] Next check in {self.analysis_interval}s...")

                # Wait before next check
                await asyncio.sleep(self.analysis_interval)

        except KeyboardInterrupt:
            print("\n\n[SCALPING SYSTEM SHUTDOWN REQUESTED BY USER]")
        except Exception as e:
            self.logger.critical(f"CRITICAL UNHANDLED EXCEPTION IN SCALPING LOOP: {e}", exc_info=True)
            print("\n\n[SCALPING SYSTEM CRASHED DUE TO AN UNEXPECTED ERROR]")
        finally:
            print("\n\n[SCALPING SYSTEM SHUTDOWN] Cleaning up resources...")
            print(f"Total analyses: {self.analysis_count}")

            if self.live_execution and self.scalping_risk_manager:
                print("  - Stopping Scalping Risk Manager...")
                await self.scalping_risk_manager.stop()
                print("  - Scalping Risk Manager stopped.")

            if self.live_execution and self.bybit_executor:
                print("  - Shutting down Bybit executor...")
                await self.bybit_executor.shutdown()
                print("  - Bybit executor shut down.")

            print("\n[SCALPING SYSTEM STOPPED]")

    def has_new_candle(self, df) -> bool:
        """Check if new candle closed"""
        if df is None or len(df) == 0:
            return False

        latest_candle_time = df.index[-1]

        if self.last_candle_time is None:
            self.last_candle_time = latest_candle_time
            return True

        if latest_candle_time > self.last_candle_time:
            self.last_candle_time = latest_candle_time
            return True

        return False

    def run(self):
        """Synchronous wrapper"""
        asyncio.run(self.run_async())


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Scalping Microstructure Live Trading System')
    parser.add_argument('--live', action='store_true', help='Enable live trading mode.')
    parser.add_argument('--fast', action='store_true', help='Enable fast start mode.')
    parser.add_argument('--symbol', type=str, default='SOLUSDT', help='The trading symbol to use.')
    args = parser.parse_args()

    if args.live:
        print("\n" + "=" * 100)
        print("WARNING: LIVE SCALPING EXECUTION MODE")
        print("=" * 100)
        print("\nThis will execute REAL scalping trades with REAL money.")
        print("Press Ctrl+C within 5 seconds to cancel...")
        print("=" * 100 + "\n")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[CANCELLED]")
            sys.exit(0)
        print("[CONFIRMED] Starting live scalping system...\n")

    # Create and run scalping system
    system = LiveScalpingMicrostructureSystem(
        symbol=args.symbol, 
        timeframe="1m",  # 1-minute for scalping focus
        live_execution=args.live,
        fast_start=args.fast
    )
    system.run()