"""
LIVE ARSENAL + HORUS INTEGRATED SYSTEM
======================================
Enhanced version with Horus order flow intelligence for:
- Precision entry timing (CVD + orderbook confirmation)
- Tighter stop placement (liquidity-based)
- Better win rate (multiple confirmations required)

ALL EXISTING RISK MANAGEMENT PRESERVED:
- 3m candle closure exit (heightened security mode)
- Breakeven movement at 75% to TP1
- Reversal detection with volume confirmation
- Real-time stop trailing
- No TP1 if no impact zone confirmed

Author: Arsenal + Horus Integration
"""

import time
import asyncio
from datetime import datetime, timedelta
from timezone_utils import get_utc_now
from typing import Optional
import logging
import pandas as pd
import numpy as np
import requests
import websockets
import json
import aiohttp
import os # NEW
from dotenv import load_dotenv # NEW
from scipy.stats import percentileofscore # NEW
from binance import AsyncClient # NEW: For centralized client
import traceback # NEW: For detailed error reporting

# Arsenal modules (unchanged)
from realtime_swing_detector import fetch_binance_data, detect_candle_close_patterns
from fvg_detector import FVGDetector
from order_block_detector import OrderBlockDetector
from liquidity_sweep_detector import LiquiditySweepDetector, StopHuntWarning # MODIFIED
from range_breakout_detector import RangeBreakoutDetector, BreakoutSignal # NEW
from trendline_confluence_module import get_trendline_analyzer
from test_ultimate_arsenal import find_swing_highs, find_swing_lows, analyze_trend_structure

# Intelligence layer
from trend_continuation_brain import TrendContinuationBrain, IntelligentDecision, MarketIntelligence
from market_regime_engine.classifier import MasterRegimeClassifier
from market_regime_engine.definitions import MarketRegime
# NEW: Import the new Range Regime Engine and Mean Reversion Brain
from range_regime_engine import RREngine, MeanReversionBrain
# NEW: Import the Historical Analyzer
from rre_historical_analyzer import RREHistoricalAnalyzer

# Precision execution (Arsenal original)
from precision_tp_sl_calculator import PrecisionTPSLCalculator
from trade_scenario_planner import TradeScenarioPlanner
from realtime_trade_monitor import RealtimeTradeMonitor

# Bybit execution
from bybit_arsenal_executor import ArsenalBybitExecutor

# Real-time price monitoring
from realtime_price_monitor import RealtimePriceMonitor

# PRESERVED: Real-time risk manager with all features
from real_time_risk_manager import RealTimeRiskManager

# NEW: Horus integration
from arsenal_horus_unified import ArsenalHorusUnified
from horus_precision_entry_system import HorusPrecisionEntrySystem
from horus_high_frequency_sampler import HorusSampler
from horus_liquidity_analyzer import ArsenalLiquidityAnalyzer
from structural_integrity_analyzer import StructuralIntegrityAnalyzer # NEW
from volume_profile_detector import VolumeProfileDetector # NEW

# NEW: Kalman Filter for smoothing
from kalman_filter import KalmanFilter
from binance_data_engine import BinanceDataEngine, compute_lci # NEW
from helios_btc_engine import HeliosBTC_Engine
from liquidation_monitor import LiquidationMonitor # NEW
from signal_logger import SignalLogger # NEW

# Import pandas_ta with error handling for systems where it might not be available
try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
    print("pandas_ta library loaded successfully")
except ImportError:
    ta = None
    PANDAS_TA_AVAILABLE = False
    print("Warning: pandas_ta library not available. Some technical analysis features may be limited.")
from dashboard_client import Emitter # NEW: Emitter for dashboard integration
from session_manager import get_current_session, is_asian_session, is_session_transition_blackout

# Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('ARSENAL_HORUS')


class LiveArsenalHorusSystem:
    """
    Arsenal trading system with Horus order flow intelligence and Market Regime Engine.
    """

    def __init__(self, symbol: str = "SOLUSDT", timeframe: str = "5m", live_execution: bool = False, fast_start: bool = False, client: Optional[AsyncClient] = None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.live_execution = live_execution
        self.fast_start = fast_start # New flag

        # Dashboard Emitter for this Arsenal instance
        self.emitter = Emitter("arsenal", self.symbol)

        # --- NEW: Centralized Binance AsyncClient ---
        self.client = client

        # Analysis config
        self.lookback_hours = 24.0 # Increased lookback to 24 hours as per user suggestion
        self.analysis_interval = 15  # Check every 15 seconds

        # --- NEW: Kalman Filters for smoothing ---
        # Q/R values are initial estimates and will be tuned dynamically.
        self.price_filter = KalmanFilter(process_variance=1e-5, measurement_variance=1e-4)
        self.cvd_filter = KalmanFilter(process_variance=1e-5, measurement_variance=1e-3)
        self.confidence_filter = KalmanFilter(process_variance=1e-2, measurement_variance=1e-1)
        logger.info(" Kalman Filters Initialized (Price, CVD, Confidence)")

        # --- NEW: Binance Data Engine ---
        # Initialize with the centralized client
        self.data_engine = BinanceDataEngine(symbol=self.symbol, client=self.client) if self.client else None
        self.liquidation_monitor: Optional[LiquidationMonitor] = None # Will be initialized later with the client
        logger.info(" Binance Data Engine Initialized")

        # --- NEW: Helios client placeholder ---
        self.helios_context: Optional[dict] = None
        self.correlation_filter = KalmanFilter(process_variance=1e-3, measurement_variance=1e-2, initial_value=0.5)

        # --- NEW: Market Regime Engine ---
        self.regime_classifier = MasterRegimeClassifier()
        self.rre_engine = RREngine(symbol=self.symbol)
        self.mrb = MeanReversionBrain(symbol=self.symbol, config={'min_boundary_quality': 0.4})
        self.tc_brain = TrendContinuationBrain(symbol=self.symbol) # Initialize TrendContinuationBrain with dynamic symbol
        logger.info(" Market Regime Engine Initialized")
        logger.info("   - Master Classifier: ACTIVE")
        logger.info("   - Trend-Continuation Brain: ACTIVE")
        logger.info("   - RRE/Mean-Reversion Brain: ARMED")

        # Arsenal components (unchanged)
        self.precision_calculator = PrecisionTPSLCalculator()
        self.scenario_planner = TradeScenarioPlanner()
        self.trade_monitor = RealtimeTradeMonitor()

        # Detectors
        self.fvg_detector = FVGDetector()
        self.ob_detector = OrderBlockDetector()
        self.liquidity_detector = LiquiditySweepDetector()
        self.breakout_detector = RangeBreakoutDetector() # NEW
        self.trendline_analyzer = get_trendline_analyzer()
        self.integrity_analyzer: Optional[StructuralIntegrityAnalyzer] = None
        if self.client:
            self.integrity_analyzer = StructuralIntegrityAnalyzer(client=self.client)
        self.volume_profile_detector = VolumeProfileDetector() # NEW

        # Real-time price monitoring
        self.price_monitor = RealtimePriceMonitor(symbol)

        # PRESERVED: Real-time risk manager (all features intact)
        self.risk_manager = None  # Initialize later

        # NEW: Horus components
        self.horus: Optional[ArsenalHorusUnified] = None
        self.horus_entry_system: Optional[HorusPrecisionEntrySystem] = None
        self.sampler: Optional[HorusSampler] = None # For HF sampling
        self.horus_initialized = False

        # NEW: Each Arsenal instance gets its own liquidity analyzer
        self.liquidity_analyzer: Optional[ArsenalLiquidityAnalyzer] = None

        # Bybit executor (only in live mode)
        self.bybit_executor = None
        if live_execution:
            self.bybit_executor = ArsenalBybitExecutor(symbol)

        # State
        self.current_trade_id: Optional[str] = None
        self.last_analysis_time = None
        self.last_candle_time = None
        self.analysis_count = 0
        self.current_session = "inter-session" 

        # NEW: Signal Logger for persistent memory
        self.signal_logger = SignalLogger(self.symbol)

        # Real-time monitoring
        self.last_swing_highs = []

        self.last_swing_lows = []
        self.realtime_update_interval = 3

        # Make logger an instance attribute for accessibility in tasks
        self.logger = logger

    async def initialize_horus(self, client: AsyncClient):
        """
        Initialize Horus system with historical context.
        Uses "fast start" to reduce snapshot count if enabled.
        """
        print("\n" + "=" * 100)
        print("INITIALIZING HORUS ORDER FLOW INTELLIGENCE")
        print("=" * 100)

        snapshot_count = 10 if self.fast_start else 20 # Reduced from 200
        if self.fast_start:
            print("\nFAST START ENABLED: Using reduced historical context (10 snapshots). Startup will be < 30s.")
        else:
            print(f"\nStandard historical context enabled ({snapshot_count} snapshots). This will take ~1-2 minutes...")
        print("Please wait - this ensures optimal entry precision\n")

        try:
            self.horus = ArsenalHorusUnified(symbol=self.symbol, client=client) # Pass the centralized client
            # Pass the snapshot count to the initializer
            await self.horus.initialize(snapshot_count=snapshot_count)
            self.horus_entry_system = HorusPrecisionEntrySystem(self.horus)
            # NEW: Initialize Binance Data Engine with the live client from Horus
            self.data_engine = BinanceDataEngine(symbol=self.symbol, client=self.horus.client)
            self.sampler = HorusSampler(data_engine=self.data_engine, symbol=self.symbol, entry_system=self.horus_entry_system)
            self.horus_initialized = True
            print("\n" + "=" * 100)
            print("HORUS INITIALIZATION COMPLETE!")
            print("=" * 100)

        except Exception as e:
            self.logger.error(f"Failed to initialize Horus: {e}", exc_info=True)
            self.logger.warning("Continuing without Horus intelligence...")
            self.horus_initialized = False
            await self.emitter.emit_health("ERROR", message=f"Horus initialization failed: {e}", extra_info={"traceback": traceback.format_exc()})

    def print_header(self):
        """Print system header"""
        print("\n" + "=" * 100)
        print("   PRECISION9 ARSENAL - MARKET REGIME ENGINE")
        print("=" * 100)
        # ... (rest of header printing is fine)

    async def run_arsenal_analysis(self, df_full: pd.DataFrame, lci_score: float, taker_ratio: Optional[float], taker_ratio_ma: Optional[float], symbol_24h_volume: Optional[float], atr_percentile: float, cvd_slope: float) -> tuple:
        """Run complete arsenal analysis with detailed educational logging."""
        print("\n" + "=" * 100)
        print(f"[ARSENAL ANALYSIS #{self.analysis_count}] {get_utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("=" * 100)

        # 1. Data Ingestion
        print("\n[1/11] Data Ingestion & Preparation")
        current_price = float(df_full.iloc[-1]['kf_close'])
        print(f"  - Current Price (Kalman Smoothed): ${current_price:.2f}")
        now = get_utc_now()
        cutoff = now - timedelta(hours=self.lookback_hours)
        df_full.index = pd.to_datetime(df_full.index)

        # --- NEW: Use Kalman Filtered Price for Analysis ---
        df_filtered = df_full.copy()
        df_filtered['close'] = df_full['kf_close']
        # Also filter open, high, low for consistency in detectors
        df_filtered['open'] = df_full['open'].apply(self.price_filter.update)
        df_filtered['high'] = df_full['high'].apply(self.price_filter.update)
        df_filtered['low'] = df_full['low'].apply(self.price_filter.update)
        self.logger.debug("Using Kalman-smoothed OHLC data for all detectors.")

        # Convert cutoff to timezone-naive to match DataFrame index timezone-naive state
        cutoff_naive = cutoff.replace(tzinfo=None)
        recent = df_filtered[df_filtered.index >= cutoff_naive].copy()
        print(f"  - Analyzing last {self.lookback_hours} hours of data ({len(recent)} candles).")

        # 2. Swing Structure
        print("\n[2/11] Swing Structure Analysis")
        swing_highs = find_swing_highs(recent, lookback=2)
        swing_lows = find_swing_lows(recent, lookback=2)
        print(f"  - Found {len(swing_highs)} swing highs and {len(swing_lows)} swing lows.")
        if swing_highs:
            for i, sh in enumerate(swing_highs[-2:], 1):
                try:
                    print(f"    - Recent High #{i}: ${sh['price']:.2f} at {pd.to_datetime(sh['timestamp'], unit='ms').strftime('%H:%M')}")
                except KeyError:
                    logger.warning(f"[LOGGING ERROR] Could not parse swing high. Available keys: {sh.keys()}")
        if swing_lows:
            for i, sl in enumerate(swing_lows[-2:], 1):
                try:
                    print(f"    - Recent Low #{i}: ${sl['price']:.2f} at {pd.to_datetime(sl['timestamp'], unit='ms').strftime('%H:%M')}")
                except KeyError:
                    logger.warning(f"[LOGGING ERROR] Could not parse swing low. Available keys: {sl.keys()}")

        # 3. Primary Trend
        print("\n[3/11] Primary Trend Assessment")
        trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
        print(f"  - Trend: {trend_analysis['trend_direction'].upper()} (Strength: {trend_analysis['trend_strength']:.0%})")
        if trend_analysis['trend_strength'] < 0.6:
            print("  - Implication: Weak or neutral trend. System will be cautious.")
        else:
            print(f"  - Implication: Strong {trend_analysis['trend_direction']} in effect. System will favor with-trend setups.")

        # 4. Candle Patterns
        print("\n[4/11] Momentum Pattern Analysis")
        patterns = detect_candle_close_patterns(recent, lookback_bars=20)
        bullish_breaks = sum(1 for p in patterns if p['type'] == 'BULLISH_BREAK')
        bearish_breaks = sum(1 for p in patterns if p['type'] == 'BEARISH_BREAK')
        
        # NEW: Analyze recent momentum patterns for trend contradiction
        recent_patterns = patterns[-5:] if len(patterns) >= 5 else patterns
        if len(recent_patterns) >= 3:
            recent_bullish_count = sum(1 for p in recent_patterns if p.get('type') == 'BULLISH_BREAK')
            recent_bearish_count = sum(1 for p in recent_patterns if p.get('type') == 'BEARISH_BREAK')
        else:
            recent_bullish_count = sum(1 for p in patterns if p.get('type') == 'BULLISH_BREAK')
            recent_bearish_count = sum(1 for p in patterns if p.get('type') == 'BEARISH_BREAK')
        
        print(f"  - Found {len(patterns)} momentum patterns ({bullish_breaks} bullish, {bearish_breaks} bearish).")
        
                # NEW: Check for momentum contradiction with trend - and identify reversal opportunities
                # momentum_reversal_signals = []
                # if trend_analysis['trend_direction'] == 'downtrend' and recent_bullish_count >= 2:
                #     print(f"  - [WARNING] Recent momentum ({recent_bullish_count} bullish breaks) contradicts downtrend!")
                #     print(f"  - [IMPLICATION] Trend may be losing momentum, trade with caution.")
                #     # NEW: This could be a bullish reversal opportunity
                #     momentum_reversal_signals.append({
                #         'condition': 'BULLISH_COUNTER_MOMENTUM',
                #         'strength': recent_bullish_count,
                #         'implication': 'Potential bullish reversal setup after downtrend exhaustion'
                #     })
                #     print(f"  - [REVERSAL OPPORTUNITY] Potential bullish reversal setup detected after downtrend exhaustion")
                # elif trend_analysis['trend_direction'] == 'uptrend' and recent_bearish_count >= 2:
                #     print(f"  - [WARNING] Recent momentum ({recent_bearish_count} bearish breaks) contradicts uptrend!")
                #     print(f"  - [IMPLICATION] Trend may be losing momentum, trade with caution.")
                #     # NEW: This could be a bearish reversal opportunity
                #     momentum_reversal_signals.append({
                #         'condition': 'BEARISH_COUNTER_MOMENTUM',
                #         'strength': recent_bearish_count,
                #         'implication': 'Potential bearish reversal setup after uptrend exhaustion'
                #     })
                #     print(f"  - [REVERSAL OPPORTUNITY] Potential bearish reversal setup detected after uptrend exhaustion")        
        # NEW: Identify and log reversal patterns
        reversal_patterns = [p for p in patterns if p.get('type') in ['MOMENTUM_REVERSAL_BULLISH', 'MOMENTUM_REVERSAL_BEARISH']]
        if reversal_patterns:
            print(f"  - [REVERSAL PATTERNS] Detected {len(reversal_patterns)} potential reversal pattern(s)")
            for rev_pat in reversal_patterns:
                print(f"    - {rev_pat['type']}: {rev_pat['description']} ({rev_pat['timestamp'].strftime('%H:%M')})")

        if patterns:
            for p in patterns[-3:]:
                if p.get('type') in ['MOMENTUM_REVERSAL_BULLISH', 'MOMENTUM_REVERSAL_BEARISH']:
                    print(f"    - Recent Pattern: {p['type']} - {p['description']} ({p['timestamp'].strftime('%H:%M')})")
                elif 'current_close' in p:  # Check if the key exists
                    print(f"    - Recent Pattern: {p['type']} at ${p['current_close']:.2f} ({p['timestamp'].strftime('%H:%M')})")
                else:
                    print(f"    - Recent Pattern: {p.get('type', 'UNKNOWN')} - timestamp: {p.get('timestamp', 'N/A')}")

        # 5. Fair Value Gaps (FVGs)
        print("\n[5/11] Fair Value Gap (FVG) Analysis")
        fvgs = self.fvg_detector.detect(df_filtered, current_price)
        active_fvgs = self.fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)
        print(f"  - Found {len(active_fvgs)} active FVGs acting as price magnets.")
        if active_fvgs:
            for fvg in active_fvgs[:3]: # Log top 3 most significant
                try:
                    print(f"    - Active FVG ({fvg.gap_type}): ${fvg.gap_start:.2f} to ${fvg.gap_end:.2f}")
                except (AttributeError, KeyError):
                    self.logger.warning(f"[LOGGING ERROR] Could not parse FVG object: {fvg}")

        # 6. Order Blocks (OBs)
        print("\n[6/11] Order Block Analysis")
        obs = self.ob_detector.detect(df_filtered, current_price)
        active_obs = self.ob_detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)
        print(f"  - Found {len(active_obs)} active Order Blocks (institutional zones).")
        if active_obs:
            for ob in active_obs[:3]: # Log top 3 most significant
                try:
                    print(f"    - Active OB ({ob.type}): ${ob.entry_zone_low:.2f} to ${ob.entry_zone_high:.2f} (Quality: {ob.quality_score:.0%})")
                except (AttributeError, KeyError):
                    self.logger.warning(f"[LOGGING ERROR] Could not parse Order Block object: {ob}")

        # 7. Liquidity Sweeps
        print("\n[7/11] Liquidity Sweep Analysis")
        sweeps = self.liquidity_detector.detect_sweeps(recent, swing_highs, swing_lows)
        bullish_sweeps = sum(1 for s in sweeps if s.type == 'bullish_sweep')
        bearish_sweeps = sum(1 for s in sweeps if s.type == 'bearish_sweep')
        print(f"  - Detected {len(sweeps)} liquidity sweeps in the lookback period ({bullish_sweeps} bullish, {bearish_sweeps} bearish).")
        if sweeps:
            for sweep in sweeps[-3:]:
                try:
                    print(f"    - Recent Sweep: {sweep.type} of ${sweep.swept_level:.2f} at {sweep.timestamp.strftime('%H:%M')}")
                except (AttributeError, KeyError):
                    self.logger.warning(f"[LOGGING ERROR] Could not parse Liquidity Sweep object: {sweep}")

        # 8. Liquidity Pool Mapping (NOW USING INTERNAL HOTSPOT ANALYZER)
        print("\n[8/11] Liquidity Hotspot Mapping (from Internal Analyzer)...")
        pools = [] # Initialize pools at the start of the block
        if self.liquidity_analyzer and self.liquidity_analyzer.liquidity_heatmap:
            heatmap = self.liquidity_analyzer.liquidity_heatmap
            mid_price = current_price
            all_levels = sorted(heatmap.items(), key=lambda item: item[1], reverse=True)
            bids = [lvl for lvl in all_levels if lvl[0] < mid_price]
            asks = [lvl for lvl in all_levels if lvl[0] > mid_price]

            print(f"  - Analyzed {len(heatmap)} liquidity levels in heatmap.")
            if bids:
                print("    - Top BID Hotspots (Support):")
                for price, qty in bids[:3]:
                    print(f"      - Level: ${price:<9.2f} | Size: {qty:,}")
            if asks:
                print("    - Top ASK Hotspots (Resistance):")
                for price, qty in asks[:3]:
                    print(f"      - Level: ${price:<9.2f} | Size: {qty:,}")
            
            # Still populate the 'pools' for the brain, using the old logic for now
            if self.liquidity_analyzer.detected_walls:
                hotspots = self.liquidity_analyzer.detected_walls
                for spot in hotspots:
                    pools.append({
                        'level': spot.price_level,
                        'type': 'hotspot_' + spot.side,
                        'size': spot.total_liquidity,
                        'confidence': spot.confidence,
                        'distance_from_price': spot.distance_from_mid
                    })
        else:
            print("  - Liquidity heatmap is still building or no hotspots detected.")

        # 9. Stop Hunt Detection
        print("\n[9/13] Stop Hunt Risk Assessment")
        stop_hunt_warning = self.liquidity_detector.detect_stop_hunt_mode(
            sweeps, pools, current_price, lci_score, taker_ratio, symbol_24h_volume, df=recent, lookback_hours=self.lookback_hours
        )
        if stop_hunt_warning is None:
            logger.warning("Liquidity detector returned None. Using safe default StopHuntWarning.")
            stop_hunt_warning = StopHuntWarning(
                stop_hunt_probability=0.0, severity=0.0, evidence=["Detector failed"],
                recommendation="SAFE DEFAULT", safe_to_trade=True, hunt_type='NONE',
                range_context='NONE', is_tradeable_directional=False
            )

        print(f"  - Stop Hunt Mode: {'ACTIVE' if stop_hunt_warning.stop_hunt_probability > 0.5 else 'INACTIVE'} (Probability: {stop_hunt_warning.stop_hunt_probability:.0%})")
        print(f"    - Hunt Type: {stop_hunt_warning.hunt_type}")
        if stop_hunt_warning.evidence:
            for reason in stop_hunt_warning.evidence:
                print(f"    - {reason}")
        if stop_hunt_warning.stop_hunt_probability > 0.5:
            print(f"  - Implication: High risk of manipulation. System will be highly cautious.")

        # 10. Volume Profile Analysis (NEW)
        print("\n[10/13] Volume Profile Analysis (Daily)")
        volume_profile_zones = self.volume_profile_detector.analyze(df_filtered)
        if volume_profile_zones:
            print(f"  - Point of Control (POC): ${volume_profile_zones['poc']:.2f}")
            print(f"  - High-Volume Nodes (HVNs): {len(volume_profile_zones['hvns'])}")
        else:
            print("  - Could not generate Volume Profile.")

        # 11. Range Regime Engine (RRE) Analysis
        print("\n[11/13] Range Regime Engine Analysis")
        
        all_swings = swing_highs + swing_lows
        
        # Calculate ADX
        adx_value = 0  # Default value if pandas_ta is not available
        if PANDAS_TA_AVAILABLE and ta is not None:
            df_filtered.ta.adx(length=14, append=True)
            adx_value = df_filtered['ADX_14'].iloc[-1] if 'ADX_14' in df_filtered.columns and not pd.isna(df_filtered['ADX_14'].iloc[-1]) else 0

        range_analysis = self.rre_engine.analyze(
            swings=all_swings,
            hvn_zones=volume_profile_zones.get('hvns', []) if volume_profile_zones else [],
            order_blocks=active_obs,
            atr_percentile=atr_percentile,
            adx_value=adx_value,
            taker_ratio=taker_ratio,
            cvd_slope=cvd_slope,
            stop_hunt_prob=stop_hunt_warning.stop_hunt_probability if stop_hunt_warning else 0.0,
            current_price=current_price
        )
        print(f"  - RRE Score: {range_analysis.range_score:.1f}/100")
        print(f"  - RRE State: {range_analysis.range_state}")
        evidence = range_analysis.evidence
        print(f"    - Evidence: Structural={evidence.get('structural', 0):.2f}, Boundary={evidence.get('boundary', 0):.2f}, Volatility={evidence.get('vol', 0):.2f}, Trend={evidence.get('trend', 0):.2f}")
        if range_analysis.geometry:
            print(f"    - Range Boundaries: ${range_analysis.geometry.low:.2f} to ${range_analysis.geometry.high:.2f} ({range_analysis.geometry.width_pct:.2f}%)")
        if range_analysis.is_trapped:
            print(f"    - TRAP DETECTED: {range_analysis.trap_reason}")
            print(f"  - Implication: Market is consolidating and unsafe. Directional trades will be blocked.")

        # 12. Structural Integrity Analysis
        print("\n[12/13] Structural Integrity Analysis (4-Hour Lookback)")
        structural_integrity_analysis = await self.integrity_analyzer.analyze(
            self.symbol, trend_analysis['trend_direction'], current_price
        )
        print(f"  - Integrity Score: {structural_integrity_analysis['integrity_score']}/100")
        for reason in structural_integrity_analysis['reasons']:
            print(f"    - {reason}")
        if structural_integrity_analysis['integrity_score'] < 60:
            print("  - Implication: Significant structural weakness detected. System will heavily penalize with-trend setups.")

        # 13. Confluence & Final Assembly
        print("\n[13/13] Confluence & Final Assembly")
        trendline_data = self.trendline_analyzer.get_comprehensive_analysis(
            symbol=self.symbol, timeframe=self.timeframe, lookback_hours=self.lookback_hours
        )
        print(f"  - Trendline analysis complete.")

        market_intel = MarketIntelligence(
            current_price=current_price,
            trend_direction=trend_analysis['trend_direction'],
            trend_strength=trend_analysis['trend_strength'],
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            candle_patterns=patterns,
            fvgs=active_fvgs,
            order_blocks=active_obs,
            liquidity_sweeps=sweeps,
            liquidity_pools=pools,
            range_trap_analysis=range_analysis,
            stop_hunt_warning=stop_hunt_warning,
            confluence_score=trendline_data.get('confluence_points', {}).get('total_points', 0),
            timestamp=now,
            structural_integrity_score=structural_integrity_analysis['integrity_score'],
            structural_integrity_reasons=structural_integrity_analysis['reasons'],
            htf_context=structural_integrity_analysis['htf_context'],
            htf2_context=structural_integrity_analysis.get('htf2_context', None),  # NEW: Add HTF2 context
            volume_profile_zones=volume_profile_zones,
            price_data=df_filtered  # NEW: Add price data for enhanced volatility calculations
        )
        print("  - Market Intelligence report assembled.")
        # Emit market intelligence update
        await self.emitter.emit("market_intelligence_update", market_intel.__dict__)

        # NEW: Call the breakout detector
        breakout_signal = self.breakout_detector.detect_breakout(
            current_price=current_price,
            current_volume=recent.iloc[-1]['volume'],
            taker_ratio=taker_ratio,
            taker_ratio_ma=taker_ratio_ma,
            range_high=range_analysis.geometry.high if range_analysis.geometry else 0,
            range_low=range_analysis.geometry.low if range_analysis.geometry else 0,
            recent_highs=[sh['price'] for sh in swing_highs],
            recent_lows=[sl['price'] for sl in swing_lows],
            candle_closes=recent['close'].tail(5).tolist()
        )

        return market_intel, current_price, breakout_signal

    async def send_signal_to_aegis(self, decision: IntelligentDecision, max_retries: int = 3):
        """Formats the trade decision and sends it to the Aegis Risk Manager via WebSocket with retry logic."""
        aegis_uri = "ws://localhost:8765"
        self.logger.info("=" * 100)
        self.logger.info(f" DISPATCHING SIGNAL TO AEGIS RISK MANAGER at {aegis_uri}")
        self.logger.info("=" * 100)

        for attempt in range(max_retries):
            try:
                # The RM expects swing highs/lows as a list of dicts with price and time
                simplified_highs = [{'price': sh['price'], 'time': pd.to_datetime(sh['index'], unit='ms').isoformat()} for sh in decision.market_intel.swing_highs]
                simplified_lows = [{'price': sl['price'], 'time': pd.to_datetime(sl['index'], unit='ms').isoformat()} for sl in decision.market_intel.swing_lows]

                payload = {
                    "symbol": self.symbol,
                    "decision": {
                        "direction": decision.direction,
                        "confidence": decision.confidence,
                        "entry_zone": decision.entry_zone, # ADDED THIS LINE
                        "stop_loss": decision.stop_loss,
                        "take_profits": decision.take_profits,
                        "position_size_multiplier": decision.position_size_multiplier,
                        "reasoning_chain": decision.reasoning_chain,
                        "swing_highs": simplified_highs,
                        "swing_lows": simplified_lows,
                        "liquidity_hotspots": decision.market_intel.liquidity_pools # NEW
                    }
                }
                
                async with websockets.connect(aegis_uri, open_timeout=10) as websocket:
                    self.logger.info(" Connected to Aegis.")
                    await websocket.send(json.dumps(payload, default=str))
                    
                    response = await asyncio.wait_for(websocket.recv(), timeout=10)
                    self.logger.info(f" Aegis Acknowledged Signal: {response}")
                    print("\n[ SIGNAL DISPATCHED] Aegis Risk Manager has accepted the trade for execution and management.\n")
                    return True

            except websockets.exceptions.ConnectionClosedError as e:
                self.logger.error(f" WebSocket connection closed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in 2 seconds... (Attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(2)
                else:
                    self.logger.error(f" FAILED TO DISPATCH SIGNAL TO AEGIS after {max_retries} attempts: {e}")
            except asyncio.TimeoutError:
                self.logger.error(" Timeout waiting for response from Aegis")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in 2 seconds... (Attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(2)
                else:
                    self.logger.error(f" FAILED TO DISPATCH SIGNAL TO AEGIS after {max_retries} attempts: Timeout")
            except Exception as e:
                self.logger.error(f" FAILED TO DISPATCH SIGNAL TO AEGIS: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in 2 seconds... (Attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(2)
                else:
                    self.logger.error(f" FAILED TO DISPATCH SIGNAL TO AEGIS after {max_retries} attempts: {e}")
                    print(f"\n[ CRITICAL ERROR] Could not send trade signal to Aegis Risk Manager. The trade was NOT executed.\n")
                    return False

        print(f"\n[ CRITICAL ERROR] Could not send trade signal to Aegis Risk Manager after {max_retries} attempts. The trade was NOT executed.\n")
        return False

    async def check_for_trade_setup_with_horus(self, df_history: pd.DataFrame, market_intel: MarketIntelligence, current_price: float, lci_score: float, gls_score: float, correlation_score: float, breakout_signal: Optional[BreakoutSignal], top_trader_ratio: Optional[float], taker_ratio: Optional[float], taker_ratio_ma: Optional[float]):
        """
        The main analysis loop, now with Helios context and persistent signal logging.
        """
        print("\n" + "=" * 100)
        print("[HELIOS & REGIME ANALYSIS]")
        print("=" * 100)

        if market_intel is None or self.helios_context is None:
            self.logger.warning("Skipping analysis due to missing Market Intel or Helios context.")
            return None

        # 1. Display Correlation & Helios Context
        smoothed_correlation = self.correlation_filter.update(correlation_score)
        print(f"  - BTC Correlation: {correlation_score:.2f} (Smoothed: {smoothed_correlation:.2f})")

        btc_trend = self.helios_context.get('btc_trend', 'UNKNOWN')
        sentiment = self.helios_context.get('sentiment', 'UNKNOWN')
        print(f"  - Helios Context: BTC Trend is {btc_trend}, Sentiment is {sentiment}")
        print(f"  - LCI: {lci_score:.2f}, GLS: {gls_score:.2f}")

        # 2. Classify Market Regime
        regime_classification = self.regime_classifier.analyze(df_history, market_intel)
        print(f"  - {self.symbol} Regime: {regime_classification.message}")

        # 3. Make a decision using the brain, now with full context
        tc_decision = self.tc_brain.analyze(
            market_intel,
            btc_context=self.helios_context,
            correlation_score=smoothed_correlation,
            lci_score=lci_score,
            gls_score=gls_score,
            breakout_signal=breakout_signal,
            top_trader_ls_ratio=top_trader_ratio,
            taker_ratio=taker_ratio,
            taker_ratio_ma=taker_ratio_ma # NEW
        )

        # --- NEW: MEAN REVERSION BRAIN (MRB) OVERRIDE LOGIC ---
        self.logger.info("[MRB] Checking for Mean Reversion opportunities...")
        range_analysis = market_intel.range_trap_analysis
        
        # For now, we assume Horus confirmation is true for the MRB logic.
        # This should be replaced with actual Horus confirmation for MRB trades.
        horus_mrb_confirmation = True 

        mrb_decision = self.mrb.decide(range_analysis, current_price, horus_mrb_confirmation)

        decision = None
        if is_asian_session():
            # During Asian session, ONLY the MRB can make decisions.
            if mrb_decision.should_trade:
                self.logger.warning(f"[ASIAN SESSION OVERRIDE] Mean Reversion Brain has generated a trade signal.")
                decision = IntelligentDecision(
                    direction=mrb_decision.side,
                    confidence=mrb_decision.confidence,
                    signal_strength='STRONG' if mrb_decision.confidence > 0.7 else 'MODERATE',
                    entry_zone=(mrb_decision.entry, mrb_decision.entry),
                    stop_loss=mrb_decision.sl,
                    take_profits=[mrb_decision.tp1, mrb_decision.tp2],
                    risk_reward=abs(mrb_decision.tp1 - mrb_decision.entry) / abs(mrb_decision.entry - mrb_decision.sl) if abs(mrb_decision.entry - mrb_decision.sl) > 0 else 0,
                    position_size_multiplier=0.5,
                    max_risk_percent=0.5,
                    reasoning_chain=[f"ASIAN SESSION MRB Override: {mrb_decision.reason}"],
                    blockers=[],
                    warnings=[],
                    opportunities=[f"Mean reversion opportunity in {range_analysis.range_state}"],
                    should_trade=True,
                    urgency='IMMEDIATE',
                    analysis_quality=range_analysis.range_score / 100.0,
                    decision_timestamp=get_utc_now(),
                    market_intel=market_intel
                )
            else:
                self.logger.info(f"[ASIAN SESSION] No Mean Reversion trade found. Reason: {mrb_decision.reason}. No trend trades will be considered.")
                decision = tc_decision #This will be a "do not trade" decision because the TCB is disabled
        else:
            # Standard logic for London/NY sessions
            if mrb_decision.should_trade:
                self.logger.warning(f"[MRB OVERRIDE] Mean Reversion Brain has generated a trade signal, overriding Trend Continuation brain.")
                decision = IntelligentDecision(
                    direction=mrb_decision.side,
                    confidence=mrb_decision.confidence,
                    signal_strength='STRONG' if mrb_decision.confidence > 0.7 else 'MODERATE',
                    entry_zone=(mrb_decision.entry, mrb_decision.entry),
                    stop_loss=mrb_decision.sl,
                    take_profits=[mrb_decision.tp1, mrb_decision.tp2],
                    risk_reward=abs(mrb_decision.tp1 - mrb_decision.entry) / abs(mrb_decision.entry - mrb_decision.sl) if abs(mrb_decision.entry - mrb_decision.sl) > 0 else 0,
                    position_size_multiplier=0.5,
                    max_risk_percent=0.5,
                    reasoning_chain=[f"MRB Override: {mrb_decision.reason}"],
                    blockers=[],
                    warnings=[],
                    opportunities=[f"Mean reversion opportunity in {range_analysis.range_state}"],
                    should_trade=True,
                    urgency='IMMEDIATE',
                    analysis_quality=range_analysis.range_score / 100.0,
                    decision_timestamp=get_utc_now(),
                    market_intel=market_intel
                )
            else:
                self.logger.info(f"[MRB] No Mean Reversion trade found. Reason: {mrb_decision.reason}. Proceeding with Trend Continuation logic.")
                decision = tc_decision
        # --- END OF MRB LOGIC ---

        # Emit the decision (even if should_trade is false)
        await self.emitter.emit("decision_update", decision.__dict__)

        # 4. Handle Brain's Decision (NO TRADE)
        if decision is None or not decision.should_trade:
            self.logger.info(f"[BRAIN DECISION] Brain returned should_trade={decision.should_trade if decision else 'None'}. No trade signal generated.")
            if decision and decision.reasoning_chain:
                print("\n" + "=" * 80)
                print(f"REASONING FROM BRAIN")
                print("=" * 80)
                for line in decision.reasoning_chain:
                    print(line)
                print("=" * 80)
            return None

        # 5. Handle Brain's Decision (YES TRADE) -> Proceed to Horus Confirmation
        print("\n" + "=" * 80)
        print(f"DECISION FROM BRAIN (should_trade={decision.should_trade})")
        print("=" * 80)
        for line in decision.reasoning_chain:
            print(line)
        print("=" * 100)

        horus_confirmed = False
        horus_reason = "Horus not initialized"
        if self.horus_initialized and self.sampler:
            horus_confirmed, horus_reason = await self.sampler.sample_and_evaluate(
                arsenal_direction=decision.direction,
                trend_direction=market_intel.trend_direction,
                trend_strength=market_intel.trend_strength
            )
            self.logger.info(f"[HORUS CONFIRMATION] Horus sampler returned: {horus_confirmed} | Reason: {horus_reason}")
        else:
            self.logger.warning("Horus sampler not initialized. Skipping confirmation.")
            horus_reason = "Horus sampler not initialized. Trade blocked for safety."


        # --- NEW: PERSISTENT MEMORY LOGGING ---
        # Log every signal that makes it to Horus, regardless of confirmation.
        await self.signal_logger.log_signal(
            decision=decision,
            horus_confirmation=horus_confirmed,
            horus_rejection_reason=horus_reason
        )
        # --- END OF LOGGING ---


        if not horus_confirmed:
            # Horus rejected the trade, stop here.
            self.logger.warning(f"Horus rejected the trade: {horus_reason}. Blocking dispatch.")
            return None

        # 6. Dispatch to Aegis Risk Manager
        if self.live_execution and decision.should_trade:
            self.logger.info(f"[DISPATCH] Live execution enabled and brain decision is should_trade={decision.should_trade}. Attempting to dispatch to Aegis.")
            decision.market_intel = market_intel # Attach market intel for the RM
            await self.send_signal_to_aegis(decision, max_retries=3)
        elif not self.live_execution:
            self.logger.info(f"[DISPATCH] Monitoring mode. Would have dispatched to Aegis: {decision.direction} at ${current_price:.2f}")
            print(f"\n[MONITORING MODE] Would have dispatched to Aegis: {decision.direction} at ${current_price:.2f}")
        
        return decision

    async def fetch_helios_context(self):
        """Fetches the latest market context from the central Helios server."""
        try:
            helios_uri = "http://localhost:8009/api/v1/helios/context"
            async with aiohttp.ClientSession() as session:
                async with session.get(helios_uri, timeout=5) as response:
                    if response.status == 200:
                        self.helios_context = await response.json()
                        self.logger.info("[HELIOS CLIENT] Successfully fetched context.")
                    else:
                        self.logger.warning(f"[HELIOS CLIENT] Failed to fetch context, status: {response.status}. Using last known context.")
        except Exception as e:
            self.logger.error(f"[HELIOS CLIENT] Error connecting to Helios server: {e}. Using last known context.")
            await self.emitter.emit_health("WARNING", message=f"Failed to connect to Helios server: {e}", extra_info={"details": "Using last known context."})

    async def run_async(self):
        """Main async run loop"""

        self.print_header()

        # Load API keys from .env for Horus initialization
        load_dotenv()
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')

        if not api_key or not api_secret:
            self.logger.critical("BINANCE_API_KEY or BINANCE_API_SECRET not found in .env. Horus cannot be initialized.")
            return # Exit if keys are missing

        # --- NEW: Create centralized AsyncClient ---
        try:
            self.client = await AsyncClient.create(api_key, api_secret)
            self.logger.info(" Centralized Binance AsyncClient created.")
        except Exception as e:
            self.logger.critical(f" Failed to create centralized Binance AsyncClient: {e}", exc_info=True)
            return # Exit if client cannot be created

        # --- NEW: Initialize components that require the client ---
        self.data_engine = BinanceDataEngine(symbol=self.symbol, client=self.client)
        if not self.integrity_analyzer:
            self.integrity_analyzer = StructuralIntegrityAnalyzer(client=self.client)

        try:
            # Start the emitter for dashboard communication
            await self.emitter.start()

            # Initialize Horus (takes ~15 minutes)
            print("\n[STARTUP] Initializing Horus order flow intelligence...")
            await self.initialize_horus(client=self.client) # Pass the centralized client

            # --- NEW: Initialize and start self-sufficient liquidity analysis ---
            try:
                self.liquidity_analyzer = ArsenalLiquidityAnalyzer(self.client, self.symbol)
                print("\n[STARTUP] Initializing Arsenal's internal liquidity hotspot analyzer...")
                await self.liquidity_analyzer.initialize_historical_context(snapshot_count=10) # Fast init
                asyncio.create_task(self._run_liquidity_monitor())
                print("[OK] Internal liquidity hotspot analysis is now running in the background.")

                # --- NEW: Initialize and start Liquidation Monitor ---
                self.liquidation_monitor = LiquidationMonitor(client=self.client, symbol=self.symbol)
                asyncio.create_task(self.liquidation_monitor.run())

            except Exception as e:
                logger.error(f"Failed to initialize auxiliary services (Liquidity/Liquidation): {e}")

            # Initialize Bybit executor if in live mode
            if self.live_execution and self.bybit_executor:
                print("\n[INITIALIZING BYBIT]")
                await self.bybit_executor.initialize()
                print("[OK] Bybit connected\n")

            # Start Horus real-time monitoring in the background
            if self.horus_initialized:
                print("\n[STARTUP] Starting Horus real-time data streams...")
                asyncio.create_task(self.horus.start_real_time_monitoring())
                print("[OK] Horus is now monitoring in the background.")

            # --- NEW: Wait for Helios Context to be available ---
            print("\n[STARTUP] Waiting for Helios Master Server context...")
            helios_ready = False
            while not helios_ready:
                try:
                    helios_uri = "http://localhost:8009/api/v1/helios/context"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(helios_uri, timeout=5) as response:
                            if response.status == 200:
                                self.helios_context = await response.json()
                                self.logger.info("[HELIOS CLIENT] Helios context is now available.")
                                helios_ready = True
                            else:
                                self.logger.warning(f"[HELIOS CLIENT] Helios context not yet available (status: {response.status}). Retrying in 5 seconds...")
                                await asyncio.sleep(5)
                except Exception as e:
                    self.logger.warning(f"[HELIOS CLIENT] Error connecting to Helios server: {e}. Retrying in 5 seconds...")
                    await asyncio.sleep(5)
            print("[OK] Helios Master Server context received.")

            # --- DISABLED: RUN HISTORICAL RRE ANALYSIS ON STARTUP (per user request) ---
            # try:
            #     historical_analyzer = RREHistoricalAnalyzer(self.rre_engine, self.client, self.symbol, self.timeframe)
            #     await historical_analyzer.run_analysis()
            # except Exception as e:
            #     logger.error(f"[RRE-Hist] The historical analysis failed to run: {e}", exc_info=True)


            print("\n[STARTING CONTINUOUS MONITORING]")
            print(f"Press Ctrl+C to stop\n")

            while True:
                # --- NEW: SESSION TRANSITION BLACKOUT ---
                if is_session_transition_blackout():
                    logger.warning("[BLACKOUT] In session transition blackout period. Pausing analysis.")
                    await asyncio.sleep(self.analysis_interval)
                    continue

                # --- NEW: SESSION MANAGEMENT ---
                self.current_session = get_current_session()
                logger.info(f"Current trading session: {self.current_session.upper()}")

                # --- SESSION-BASED STRATEGY ADJUSTMENT ---
                if is_asian_session():
                    if self.rre_engine.sensitivity_level != 'high':
                        logger.info("ASIAN SESSION DETECTED: Switching to high-sensitivity mean reversion mode.")
                        self.rre_engine.set_sensitivity('high')
                        self.mrb.set_active(True)
                        self.tc_brain.set_active(False)
                else:
                    if self.rre_engine.sensitivity_level != 'default':
                        logger.info("LONDON/NY SESSION DETECTED: Operating in standard trend-following mode.")
                        self.rre_engine.set_sensitivity('default')
                        self.mrb.set_active(False)
                        self.tc_brain.set_active(True)


                # --- NEW: LIQUIDATION CIRCUIT BREAKER ---
                if self.liquidation_monitor and self.liquidation_monitor.is_emergency_stop_active():
                    logger.critical("[CIRCUIT BREAKER] EMERGENCY STOP ACTIVE due to high market-wide liquidations. Pausing all analysis for 60 seconds.")
                    await asyncio.sleep(60)
                    continue # Skip to the next loop iteration

                try:
                    # Fetch latest data
                    df_check = await fetch_binance_data(self.client, self.symbol, self.timeframe, 200)
                    if df_check.empty:
                        self.logger.error("Failed to fetch primary data for main symbol after multiple retries. Skipping this analysis cycle.")
                        await self.emitter.emit_health("ERROR", message=f"Failed to fetch primary data for {self.symbol}.", extra_info={"details": "df_check is empty"})
                        await asyncio.sleep(self.analysis_interval)
                        continue

                    # --- NEW: Fetch BTC data for correlation ---
                    df_btc = await fetch_binance_data(self.client, "BTCUSDT", self.timeframe, 200)
                    if df_btc.empty:
                        self.logger.warning("Failed to fetch BTC data. Correlation will be set to 0.")
                        correlation = 0.0
                    else:
                        correlation = df_check['close'].rolling(100).corr(df_btc['close']).iloc[-1] if not df_btc.empty else 0.0

                    # --- NEW: Kalman Filter on Price Data ---
                    # 1. Calculate ATR for volatility
                    high_low = df_check['high'] - df_check['low']
                    high_close = np.abs(df_check['high'] - df_check['close'].shift())
                    low_close = np.abs(df_check['low'] - df_check['close'].shift())
                    ranges = pd.concat([high_low, high_close, low_close], axis=1)
                    true_range = np.max(ranges, axis=1)
                    atr = true_range.rolling(14).mean().iloc[-1]
                    normalized_atr = (atr / df_check['close'].iloc[-1]) * 100

                    # 2. Dynamically set process variance (Q) based on volatility
                    # Higher volatility = higher Q = more responsive filter
                    process_variance = 1e-5 * (1 + normalized_atr * 10)
                    self.price_filter.set_process_variance(process_variance)

                    # 3. Apply the filter
                    df_check['kf_close'] = df_check['close'].apply(self.price_filter.update)
                    self.logger.debug(f"Kalman filter applied to price. Last raw: {df_check['close'].iloc[-1]:.2f}, Last kf: {df_check['kf_close'].iloc[-1]:.2f}")

                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Failed to fetch primary data after multiple retries: {e}")
                    await self.emitter.emit_health("ERROR", message=f"API Request Error: {e}", extra_info={"details": str(e)})
                    self.logger.info(f"Waiting for {self.analysis_interval} seconds before next attempt...")
                    await asyncio.sleep(self.analysis_interval)
                    continue

                # Only run full analysis on new candles
                if self.has_new_candle(df_check):
                    self.analysis_count += 1

                    print(f"\n[NEW CANDLE] Running analysis #{self.analysis_count}...")

                    # --- NEW: Fetch Symbol-Dynamic Data ---
                    lci_score = 0.5
                    top_trader_ratio = None
                    taker_ratio = None
                    taker_ratio_ma = None
                    symbol_24h_volume = None

                    if not self.data_engine:
                        logger.error("Binance Data Engine not available, cannot calculate sentiment or fetch dynamic data.")
                        await self.emitter.emit_health("WARNING", message="Binance Data Engine not available.")
                    else:
                        # Fetch L/S ratios for LCI
                        ls_ratios = await self.data_engine.get_long_short_ratios(period="5m")
                        if ls_ratios and ls_ratios.get('global') is not None:
                            lci_score = compute_lci(self.symbol, ls_ratios.get('global'))
                            top_trader_ratio = ls_ratios.get('top_trader')
                        else:
                            logger.warning("Could not fetch Long/Short ratios for LCI calculation.")
                        
                        # Fetch Taker Volume Ratio Analysis for aggression check
                        taker_analysis = await self.data_engine.get_taker_ratio_analysis(period="5m")
                        if taker_analysis:
                            taker_ratio = taker_analysis['latest_ratio']
                            taker_ratio_ma = taker_analysis['ratio_ma']
                        
                        # Fetch 24h Volume for dynamic thresholds
                        try:
                            ticker_data = await self.data_engine.client.get_ticker(symbol=self.symbol)
                            symbol_24h_volume = float(ticker_data['quoteVolume'])
                            logger.info(f"Symbol 24h Volume: ${symbol_24h_volume:,.0f}")
                        except Exception as e:
                            logger.error(f"Could not fetch 24h volume for {self.symbol}: {e}")
                            await self.emitter.emit_health("WARNING", message=f"Could not fetch 24h volume for {self.symbol}: {e}")

                    # --- NEW: Calculate ATR Percentile ---
                    atr_series = true_range.rolling(14).mean().dropna()
                    if not atr_series.empty:
                        current_atr = atr_series.iloc[-1]
                        atr_percentile = percentileofscore(atr_series, current_atr) / 100.0
                    else:
                        atr_percentile = 0.5 # Default if not enough data
                    logger.info(f"ATR Percentile: {atr_percentile:.2f}")

                    # --- NEW: Calculate CVD Slope ---
                    cvd_slope = 0.0
                    if self.horus:
                        cvd_history = self.horus.get_recent_cvd_history()
                        if len(cvd_history) > 10:
                            # Use the last 20 minutes of CVD data for slope
                            recent_cvd = cvd_history[-20:]
                            # Create a time index for the regression
                            x = np.arange(len(recent_cvd))
                            # Fit a linear model
                            try:
                                slope, _ = np.polyfit(x, recent_cvd, 1)
                                cvd_slope = slope
                            except np.linalg.LinAlgError:
                                cvd_slope = 0.0 # Handle potential errors in polyfit
                            logger.info(f"CVD Slope (last 20 mins): {cvd_slope:.2f}")
                        else:
                            logger.info("Not enough CVD history to calculate slope.")
                    
                    # Update breakout detector with latest data
                    self.breakout_detector.update_market_data(df_check.iloc[-1]['kf_close'], df_check.iloc[-1]['volume'], df_check.index[-1].timestamp())

                    # Run Arsenal analysis, now with dynamic data
                    market_intel, current_price, breakout_signal = await self.run_arsenal_analysis(
                        df_check, lci_score, taker_ratio, taker_ratio_ma, symbol_24h_volume,
                        atr_percentile=atr_percentile, cvd_slope=cvd_slope
                    )

                    # --- ROBUSTNESS FIX: Check for failed analysis ---
                    if market_intel is None:
                        self.logger.warning("Arsenal analysis failed, waiting for next candle.")
                        await self.emitter.emit_health("WARNING", message="Arsenal analysis failed (MarketIntel is None).")
                        continue
                    # --- END ROBUSTNESS FIX ---

                    # --- NEW: Fetch Helios context before analysis ---
                    await self.fetch_helios_context()

                    # --- NEW: Get GLS score from Helios context ---
                    gls_score = self.helios_context.get('gls_score', 0.5) if self.helios_context else 0.5

                    # Check for trade setup (with Horus confirmation)
                    decision = await self.check_for_trade_setup_with_horus(
                        df_history=df_check, 
                        market_intel=market_intel, 
                        current_price=current_price, 
                        lci_score=lci_score, 
                        gls_score=gls_score, 
                        correlation_score=correlation, 
                        breakout_signal=breakout_signal, 
                        top_trader_ratio=top_trader_ratio, 
                        taker_ratio=taker_ratio,
                        taker_ratio_ma=taker_ratio_ma
                    )

                    # --- ROBUSTNESS FIX: Check for decision ---
                    if not decision:
                        self.logger.warning("Trade setup analysis completed but no decision made, waiting for next candle.")
                        await self.emitter.emit_health("OK", message="Analysis completed. No trade decision.")
                        continue
                    # --- END ROBUSTNESS FIX ---

                    print(f"\n[MONITORING] Waiting for next candle...")
                    await self.emitter.emit_health("OK", message=f"Analysis cycle {self.analysis_count} completed. Decision: {decision.should_trade}")

                # Wait before checking again
                await asyncio.sleep(self.analysis_interval)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch primary data after multiple retries: {e}")
            await self.emitter.emit_health("ERROR", message=f"API Request Error: {e}", extra_info={"details": str(e)})
            self.logger.info(f"Waiting for {self.analysis_interval} seconds before next attempt...")
            await asyncio.sleep(self.analysis_interval)
        # The main `try...except` in run_async already handles general exceptions, so this is just for API errors.

        except KeyboardInterrupt:
            print("\n\n[SYSTEM SHUTDOWN REQUESTED BY USER]")
            await self.emitter.emit_health("WARNING", message="System shutdown requested by user.")
        except Exception as e:
            self.logger.critical(f"CRITICAL UNHANDLED EXCEPTION IN MAIN LOOP: {e}", exc_info=True)
            print("\n\n[SYSTEM CRASHED DUE TO AN UNEXPECTED ERROR]")
            await self.emitter.emit_health("ERROR", message=f"Critical error in main loop: {e}", extra_info={"traceback": traceback.format_exc()})
        finally:
            print("\n\n[SYSTEM SHUTDOWN] Cleaning up resources...")
            print(f"Total analyses: {self.analysis_count}")

            if self.horus:
                print("  - Closing Horus connections...")
                await self.horus.cleanup()
                print("  - Horus connections closed.")
            
            if self.liquidation_monitor:
                print("  - Stopping Liquidation Monitor...")
                await self.liquidation_monitor.stop()
                print("  - Liquidation Monitor stopped.")

            if self.live_execution and self.bybit_executor:
                print("  - Shutting down Bybit executor...")
                await self.bybit_executor.shutdown()
                print("  - Bybit executor shut down.")

            if self.client:
                print("  - Closing centralized Binance AsyncClient connection...")
                await self.client.close_connection()
                print("  - Centralized Binance AsyncClient connection closed.")

            # Stop the emitter for dashboard communication
            await self.emitter.stop()

            print("\n[SYSTEM STOPPED]")

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

    async def _run_liquidity_monitor(self):
        """Background task to continuously update the liquidity heatmap."""
        while True:
            try:
                # Make the client call compatible with both Aegis' custom client and the raw binance client
                if hasattr(self.liquidity_analyzer.client, 'get_orderbook'):
                    orderbook = await self.liquidity_analyzer.client.get_orderbook(self.symbol, limit=100)
                else:
                    orderbook = await self.liquidity_analyzer.client.futures_order_book(symbol=self.symbol, limit=100)

                if orderbook:
                    self.liquidity_analyzer.update_with_orderbook(orderbook)
                await asyncio.sleep(5) # Update every 5 seconds
            except Exception as e:
                self.logger.error(f"[LiquidityMonitor] Error: {e}")
                await asyncio.sleep(20) # Wait longer on error


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Arsenal + Horus Live Trading System')
    parser.add_argument('--live', action='store_true', help='Enable live trading mode.')
    parser.add_argument('--fast', action='store_true', help='Enable fast start mode (reduced historical context).')
    parser.add_argument('--symbol', type=str, default='SOLUSDT', help='The trading symbol to use (e.g., SOLUSDT, DOGEUSDT).')
    args = parser.parse_args()

    if args.live:
        print("\n" + "=" * 100)
        print("WARNING: LIVE EXECUTION MODE")
        print("=" * 100)
        print("\nThis will execute REAL trades with REAL money.")
        print("Press Ctrl+C within 5 seconds to cancel...")
        print("=" * 100 + "\n")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[CANCELLED]")
            sys.exit(0)
        print("[CONFIRMED] Starting live system...\n")

    # Create and run
    system = LiveArsenalHorusSystem(
        symbol=args.symbol, 
        timeframe="5m", 
        live_execution=args.live,
        fast_start=args.fast,
        client=None # Will be set in run_async
    )
    system.run()