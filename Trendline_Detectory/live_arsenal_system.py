"""
LIVE ARSENAL + EXECUTION SYSTEM
Runs continuously, analyzing market in real-time and managing trades

This system can run in two modes:
1. MONITORING MODE - Analyzes and shows what it would do (no real execution)
2. LIVE EXECUTION MODE - Executes real trades on Bybit with full risk management
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional

# Arsenal modules
from realtime_swing_detector import fetch_binance_data, detect_candle_close_patterns
from fvg_detector import FVGDetector
from order_block_detector import OrderBlockDetector
from liquidity_sweep_detector import LiquiditySweepDetector
from range_trap_detector import RangeTrapDetector
from trendline_confluence_module import get_trendline_analyzer
from test_ultimate_arsenal import find_swing_highs, find_swing_lows, analyze_trend_structure, MarketIntelligence

# Intelligence layer
from intelligent_strategy_brain import IntelligentStrategyBrain

# Market Reasoning Dictionary - Detailed breakdown
from market_reasoning_dictionary import MarketReasoningDictionary, print_detailed_analysis

# Precision execution system
from precision_tp_sl_calculator import PrecisionTPSLCalculator
from trade_scenario_planner import TradeScenarioPlanner
from realtime_trade_monitor import RealtimeTradeMonitor

# Bybit execution integration
from bybit_arsenal_executor import ArsenalBybitExecutor

# Real-time price monitoring
from realtime_price_monitor import RealtimePriceMonitor

# Hybrid validation
from arsenal_data_collector import ArsenalDataCollector


class LiveArsenalSystem:
    """
    Main live trading system

    Continuously monitors market and manages trades with full arsenal
    """

    def __init__(self, symbol: str = "SOLUSDT", timeframe: str = "5m", live_execution: bool = False):
        self.symbol = symbol
        self.timeframe = timeframe
        self.live_execution = live_execution

        # Analysis config
        self.lookback_hours = 4.0
        self.analysis_interval = 15  # Check for new data every 15 seconds (responsive)

        # Timeframe to seconds mapping
        self.timeframe_seconds = {
            '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '4h': 14400, '1d': 86400
        }

        # Components
        self.brain = IntelligentStrategyBrain()
        self.reasoning_dict = MarketReasoningDictionary()  # Detailed market breakdown
        self.precision_calculator = PrecisionTPSLCalculator()
        self.scenario_planner = TradeScenarioPlanner()
        self.trade_monitor = RealtimeTradeMonitor()

        # Detectors
        self.fvg_detector = FVGDetector()
        self.ob_detector = OrderBlockDetector()
        self.liquidity_detector = LiquiditySweepDetector()
        self.trap_detector = RangeTrapDetector()
        self.trendline_analyzer = get_trendline_analyzer()

        # Real-time price monitoring
        self.price_monitor = RealtimePriceMonitor(symbol)

        # Arsenal data collector for hybrid validation
        self.arsenal_collector = ArsenalDataCollector()
        self.arsenal_collector.start_collection()

        # Bybit executor (only in live mode)
        self.bybit_executor = None
        if live_execution:
            self.bybit_executor = ArsenalBybitExecutor(symbol)

        # State
        self.current_trade_id: Optional[str] = None
        self.last_analysis_time = None
        self.last_candle_time = None
        self.analysis_count = 0

        # Real-time monitoring state
        self.last_swing_highs = []
        self.last_swing_lows = []
        self.realtime_update_interval = 3  # Update real-time view every 3 seconds

    def print_header(self):
        """Print system header"""
        print("\n" + "="*100)
        print("   PRECISION9 ARSENAL - LIVE TRADING SYSTEM")
        print("="*100)
        print(f"\n  Symbol: {self.symbol}")
        print(f"  Timeframe: {self.timeframe}")
        print(f"  Check Interval: {self.analysis_interval}s (analyzes on new candles)")
        print(f"  Lookback: {self.lookback_hours} hours")

        if self.live_execution:
            print(f"\n  Mode: LIVE EXECUTION (Real trades on Bybit)")
            print(f"  Position Size: $100 with 10x leverage")
            print(f"  Max Daily Drawdown: $20")
            print(f"  Min Risk/Reward: 1.2:1")
        else:
            print(f"\n  Mode: MONITORING (No live execution - shows what it would do)")

        print("="*100)
        print("\n[SYSTEM INITIALIZED]")
        print("  Intelligent Strategy Brain")
        print("  Precision TP/SL Calculator")
        print("  Trade Scenario Planner")
        print("  Real-Time Trade Monitor")
        print("  All 11 Arsenal Modules")
        print("  Arsenal Data Collector (Hybrid Validation)")

        if self.live_execution and self.bybit_executor:
            print("  Bybit Execution Engine")

        print("\n" + "="*100)

    def has_new_candle(self, df) -> bool:
        """Check if a new candle has closed since last analysis"""
        if df is None or len(df) == 0:
            return False

        latest_candle_time = df.iloc[-1]['timestamp']

        # First run
        if self.last_candle_time is None:
            self.last_candle_time = latest_candle_time
            return True

        # New candle detected
        if latest_candle_time > self.last_candle_time:
            self.last_candle_time = latest_candle_time
            return True

        return False

    def run_arsenal_analysis(self) -> tuple:
        """Run complete arsenal analysis"""

        print("\n" + "="*100)
        print(f"[ARSENAL ANALYSIS #{self.analysis_count + 1}] {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("="*100)

        # Fetch fresh data
        print("\n[1/11] Fetching live market data from Binance...")
        df = fetch_binance_data(self.symbol, self.timeframe, 200)
        current_price = float(df.iloc[-1]['close'])
        print(f"  Current Price: ${current_price:.2f}")
        print(f"  Latest Candle: {df.iloc[-1]['timestamp'].strftime('%H:%M:%S')}")

        # Time filter
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=self.lookback_hours)
        recent = df[df['timestamp'] >= cutoff].copy()

        # Swing structure
        print("\n[2/11] Analyzing swing structure...")
        swing_highs = find_swing_highs(recent, lookback=2)
        swing_lows = find_swing_lows(recent, lookback=2)
        print(f"  Found {len(swing_highs)} swing highs, {len(swing_lows)} swing lows")

        # Trend
        print("\n[3/11] Determining trend...")
        trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
        print(f"  Trend: {trend_analysis['trend_direction'].upper()} ({trend_analysis['trend_strength']:.0%} strength)")

        # Patterns
        print("\n[4/11] Detecting candle patterns...")
        patterns = detect_candle_close_patterns(recent, lookback_bars=20)
        bullish_patterns = [p for p in patterns if p['type'] == 'BULLISH_BREAK']
        bearish_patterns = [p for p in patterns if p['type'] == 'BEARISH_BREAK']
        print(f"  Found {len(patterns)} patterns ({len(bullish_patterns)} bullish, {len(bearish_patterns)} bearish)")

        if patterns:
            recent_patterns = patterns[-5:]  # Last 5 patterns
            print(f"  Recent Pattern Activity:")
            for pattern in recent_patterns:
                print(f"    - {pattern['type']}: ${pattern['current_close']:.2f} (strength: {pattern.get('break_pct', 0):.2f}%)")

        # FVGs
        print("\n[5/11] Detecting Fair Value Gaps...")
        fvgs = self.fvg_detector.detect(df, current_price)
        active_fvgs = self.fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)
        bullish_fvgs = [f for f in fvgs if f.gap_type == 'bullish']
        bearish_fvgs = [f for f in fvgs if f.gap_type == 'bearish']
        print(f"  Total FVGs: {len(fvgs)} ({len(bullish_fvgs)} bullish, {len(bearish_fvgs)} bearish)")
        print(f"  Active within 5%: {len(active_fvgs)}")

        if active_fvgs:
            print(f"  Nearest FVG Details:")
            for fvg in active_fvgs[:3]:  # Show top 3
                distance_pct = ((fvg.gap_end - current_price) / current_price) * 100
                print(f"    - {fvg.gap_type.upper()}: ${fvg.gap_start:.2f}-${fvg.gap_end:.2f} ({distance_pct:+.2f}% away)")

        # Order Blocks
        print("\n[6/11] Detecting Order Blocks...")
        obs = self.ob_detector.detect(df, current_price)
        active_obs = self.ob_detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)
        bullish_obs = [ob for ob in obs if ob.type == 'bullish']
        bearish_obs = [ob for ob in obs if ob.type == 'bearish']
        print(f"  Total OBs: {len(obs)} ({len(bullish_obs)} bullish, {len(bearish_obs)} bearish)")
        print(f"  Active within 3%: {len(active_obs)}")

        if active_obs:
            print(f"  Nearest OB Details:")
            for ob in active_obs[:3]:  # Show top 3
                distance_pct = ((ob.high - current_price) / current_price) * 100
                quality = ob.quality_score if hasattr(ob, 'quality_score') else 0
                print(f"    - {ob.type.upper()}: ${ob.low:.2f}-${ob.high:.2f}, Quality: {quality:.0%} ({distance_pct:+.2f}% away)")

        # Liquidity sweeps
        print("\n[7/11] Detecting liquidity sweeps...")
        sweeps = self.liquidity_detector.detect_sweeps(recent, swing_highs, swing_lows)
        print(f"  Found {len(sweeps)} liquidity sweeps")

        if sweeps:
            print(f"  Recent Sweep Details:")
            for sweep in sweeps[-3:]:  # Show last 3
                print(f"    - {sweep.type.upper()} sweep @ ${sweep.swept_level:.2f}, Intent: {sweep.smart_money_intent}, Danger: {sweep.danger_level}")

        # Liquidity pools
        print("\n[8/11] Mapping liquidity pools...")
        pools = self.liquidity_detector.map_liquidity_pools(swing_highs, swing_lows, sweeps, current_price)
        print(f"  Mapped {len(pools)} liquidity pools")

        if pools:
            untapped_pools = [p for p in pools if p.recent_sweeps == 0]
            print(f"  Untapped pools: {len(untapped_pools)}")
            print(f"  Nearest Pools:")
            # Sort by distance from current price
            sorted_pools = sorted(pools, key=lambda p: abs(p.level - current_price))
            for pool in sorted_pools[:3]:  # Show top 3
                distance_pct = ((pool.level - current_price) / current_price) * 100
                status = "TAPPED" if pool.recent_sweeps > 0 else "UNTAPPED"
                print(f"    - ${pool.level:.2f} ({distance_pct:+.2f}% away) - {status}, {pool.pool_size} pool, Sweep prob: {pool.sweep_probability:.0%}")

        # Stop hunt mode
        print("\n[9/11] Checking stop hunt mode...")
        stop_hunt_warning = self.liquidity_detector.detect_stop_hunt_mode(
            sweeps, pools, current_price, df=recent, lookback_hours=self.lookback_hours
        )
        print(f"  Stop Hunt Mode: {'ACTIVE' if stop_hunt_warning.is_stop_hunt_mode else 'INACTIVE'}")
        print(f"  Hunt Type: {stop_hunt_warning.hunt_type}")
        print(f"  Range Context: {stop_hunt_warning.range_context}")
        print(f"  Tradeable Directional: {'YES' if stop_hunt_warning.is_tradeable_directional else 'NO'}")
        print(f"  Severity: {stop_hunt_warning.severity:.0%}")

        if stop_hunt_warning.is_stop_hunt_mode:
            print(f"  WARNING: {stop_hunt_warning.recommendation}")
            if stop_hunt_warning.evidence:
                print(f"  Evidence:")
                for evidence in stop_hunt_warning.evidence[:3]:  # Show top 3
                    print(f"    - {evidence}")

        # Range trap
        print("\n[10/11] Detecting range traps...")
        trap_analysis = self.trap_detector.analyze(swing_highs, swing_lows, patterns, current_price, self.lookback_hours)
        print(f"  Range Trap Detected: {'YES' if trap_analysis.is_trapped else 'NO'}")
        print(f"  Trap Severity: {trap_analysis.trap_severity:.0%}")
        print(f"  Danger Level: {trap_analysis.danger_level}")

        if trap_analysis.is_trapped:
            print(f"  Trap Indicators:")
            if hasattr(trap_analysis, 'range_size_pct'):
                print(f"    - Range Size: {trap_analysis.range_size_pct:.2f}%")
            if hasattr(trap_analysis, 'conflicting_signals'):
                print(f"    - Conflicting Signals: {trap_analysis.conflicting_signals}")
            if hasattr(trap_analysis, 'price_oscillations'):
                print(f"    - Price Oscillations: {trap_analysis.price_oscillations}")
            print(f"  Recommendation: {trap_analysis.recommendation}")

        # Trendline Analysis
        print("\n[11/11] Running trendline detection & confluence analysis...")
        trendline_data = self.trendline_analyzer.get_comprehensive_analysis(
            symbol=self.symbol,
            timeframe=self.timeframe,
            lookback_hours=self.lookback_hours
        )

        if trendline_data.get('success'):
            print(f"  Trendline Analysis Complete")

            # Swing levels
            swing_info = trendline_data['swing_analysis']
            if swing_info['most_recent_resistance']:
                print(f"    Resistance: ${swing_info['most_recent_resistance']:.2f} ({swing_info['resistance_distance_pct']:+.2f}% away)")
            if swing_info['most_recent_support']:
                print(f"    Support: ${swing_info['most_recent_support']:.2f} ({swing_info['support_distance_pct']:+.2f}% away)")

            # Trend structure
            trend_info = trendline_data['trend_analysis']
            print(f"    Structure: {trend_info['structure_type']} (strength: {trend_info['trend_strength']:.0%})")

            # Patterns
            pattern_info = trendline_data['pattern_analysis']
            print(f"    Recent Breaks: {pattern_info['bullish_breaks']} bullish, {pattern_info['bearish_breaks']} bearish")

            # Confluence
            confluence = trendline_data['confluence_points']
            print(f"    Confluence: {confluence['total_points']} points (Bullish: {confluence['bullish_points']}, Bearish: {confluence['bearish_points']})")
            print(f"    Suggested Direction: {trendline_data['suggested_direction']}")
        else:
            # Fallback to simple confluence
            confluence = self.trendline_analyzer.calculate_confluence_points(
                swing_highs, swing_lows, patterns, current_price,
                'LONG' if trend_analysis['trend_direction'] == 'uptrend' else 'SHORT'
            )
            print(f"  Confluence Score: {confluence['total_points']} points")

        # Create market intelligence
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
            range_trap_analysis=trap_analysis,
            stop_hunt_warning=stop_hunt_warning,
            confluence_score=confluence['total_points'],
            timestamp=now
        )

        # Print analysis summary
        print("\n" + "="*100)
        print("[ARSENAL ANALYSIS SUMMARY]")
        print("="*100)
        print(f"\n  Price: ${current_price:.2f}")
        print(f"  Trend: {trend_analysis['trend_direction'].upper()} ({trend_analysis['trend_strength']:.0%})")

        if trendline_data.get('success'):
            swing_info = trendline_data['swing_analysis']
            if swing_info['most_recent_resistance']:
                dist = swing_info['resistance_distance_pct']
                status = "TESTING" if abs(dist) < 0.5 else ("BELOW" if dist > 0 else "BROKEN ABOVE")
                print(f"  Resistance: ${swing_info['most_recent_resistance']:.2f} - {status}")
            if swing_info['most_recent_support']:
                dist = swing_info['support_distance_pct']
                status = "TESTING" if abs(dist) < 0.5 else ("ABOVE" if dist > 0 else "BROKEN BELOW")
                print(f"  Support: ${swing_info['most_recent_support']:.2f} - {status}")

            pattern_info = trendline_data['pattern_analysis']
            if pattern_info['recent_patterns'] > 0:
                print(f"  Recent Activity: {pattern_info['bullish_breaks']} bullish breaks, {pattern_info['bearish_breaks']} bearish breaks")

            print(f"  Trendline Confluence: {confluence['total_points']} points")
            print(f"  Suggested Direction: {trendline_data['suggested_direction']}")

        print(f"  Active FVGs: {len(active_fvgs)}")
        print(f"  Active Order Blocks: {len(active_obs)}")
        print(f"  Liquidity Pools: {len(pools)}")
        print(f"  Range Trap Risk: {trap_analysis.trap_severity:.0%}")
        print("="*100)

        # Store swing data for real-time monitoring
        self.last_swing_highs = swing_highs
        self.last_swing_lows = swing_lows

        # Collect Arsenal snapshot for hybrid validation
        swing_analysis = {
            'swing_high': swing_highs[0]['price'] if swing_highs else None,
            'swing_low': swing_lows[0]['price'] if swing_lows else None,
            'bars_since_high': len(recent) - swing_highs[0]['index'] if swing_highs else 0,
            'bars_since_low': len(recent) - swing_lows[0]['index'] if swing_lows else 0
        }

        # Extract confluence score from trendline data or use fallback
        if trendline_data.get('success'):
            confluence_data = trendline_data['confluence_points']
        else:
            confluence_data = confluence

        snapshot = self.arsenal_collector.collect_snapshot(
            current_price=current_price,
            current_candle_timestamp=df.iloc[-1]['timestamp'].timestamp(),
            swing_analysis=swing_analysis,
            patterns=patterns,
            fvgs=fvgs,
            order_blocks=obs,
            liquidity_sweeps=sweeps,
            liquidity_pools=pools,
            stop_hunt_warning=stop_hunt_warning,
            range_trap=trap_analysis,
            confluence=confluence_data,
            brain_decision=None  # Brain decision happens later in check_for_trade_setup
        )

        return market_intel, df, current_price, trendline_data

    def display_realtime_price_action(self):
        """Show live price action monitoring between full analyses"""
        # Analyze current live price action
        live_action = self.price_monitor.analyze_live_price_action(
            self.last_swing_highs,
            self.last_swing_lows
        )

        if not live_action:
            return

        # Detect breakouts
        breakout = self.price_monitor.detect_breakout(live_action)

        # Display compact real-time view
        current_time = datetime.utcnow().strftime('%H:%M:%S')

        # Build status line
        status_parts = []

        # Price and change
        price_change_str = f"{live_action.price_change_1min:+.2f}%/1m" if live_action.price_change_1min != 0 else "~"
        status_parts.append(f"${live_action.current_price:.2f} ({price_change_str})")

        # Momentum indicator
        if live_action.momentum_score > 50:
            status_parts.append("STRONG BUY")
        elif live_action.momentum_score > 20:
            status_parts.append("BULLISH")
        elif live_action.momentum_score < -50:
            status_parts.append("STRONG SELL")
        elif live_action.momentum_score < -20:
            status_parts.append("BEARISH")
        else:
            status_parts.append("NEUTRAL")

        # Volume surge
        if live_action.volume_surge > 2.0:
            status_parts.append(f"VOL SURGE {live_action.volume_surge:.1f}x")

        # Level interaction
        if live_action.testing_resistance:
            status_parts.append(f"TESTING RES ${live_action.nearest_resistance:.2f}")
        elif live_action.testing_support:
            status_parts.append(f"TESTING SUP ${live_action.nearest_support:.2f}")
        elif live_action.breaking_above:
            status_parts.append(f"BREAKING ABOVE ${live_action.nearest_resistance:.2f}!")
        elif live_action.breaking_below:
            status_parts.append(f"BREAKING BELOW ${live_action.nearest_support:.2f}!")
        elif live_action.rejecting_from_resistance:
            status_parts.append(f"REJECTED FROM RES")
        elif live_action.rejecting_from_support:
            status_parts.append(f"REJECTED FROM SUP")

        # Breakout alert
        if breakout:
            if breakout.is_loading:
                status_parts.append(f">>> {breakout.direction} BREAKOUT LOADING (str:{breakout.strength:.0f})")
            elif breakout.is_breaking:
                status_parts.append(f">>> {breakout.direction} BREAKOUT IN PROGRESS (str:{breakout.strength:.0f})")
            elif breakout.is_broken:
                status_parts.append(f">>> {breakout.direction} BREAKOUT CONFIRMED! (str:{breakout.strength:.0f})")
            elif breakout.is_fake:
                status_parts.append(f">>> FAKE BREAKOUT WARNING")

        # Print compact status
        status = " | ".join(status_parts)
        print(f"[{current_time}] {status}")

    async def check_for_trade_setup(self, market_intel, current_price, df):
        """Check if there's a valid trade setup"""

        print("\n" + "="*100)
        print("[INTELLIGENT BRAIN ANALYSIS - DETAILED REASONING]")
        print("="*100)

        # Get brain decision
        decision = self.brain.analyze(market_intel)

        # ====== COMPREHENSIVE REASONING DICTIONARY ======
        # Build detailed analysis for manual following
        print("\n[GENERATING COMPREHENSIVE MARKET BREAKDOWN...]")

        # Analyze swing structure
        swing_analysis = self.reasoning_dict.analyze_swing_structure(
            market_intel.swing_highs,
            market_intel.swing_lows,
            current_price,
            df
        )

        # Analyze patterns
        pattern_analysis = self.reasoning_dict.analyze_patterns(
            market_intel.candle_patterns,
            current_price,
            df
        )

        # Analyze smart money zones
        smart_money_analysis = self.reasoning_dict.analyze_smart_money_zones(
            market_intel.fvgs,
            market_intel.order_blocks,
            current_price
        )

        # Analyze liquidity landscape
        liquidity_analysis = self.reasoning_dict.analyze_liquidity_landscape(
            market_intel.liquidity_pools,
            market_intel.liquidity_sweeps,
            current_price
        )

        # Create trade reasoning
        trade_reasoning = self.reasoning_dict.create_trade_reasoning(
            decision.direction,
            decision.confidence,
            swing_analysis,
            pattern_analysis,
            smart_money_analysis,
            liquidity_analysis,
            market_intel.stop_hunt_warning,
            market_intel.range_trap_analysis
        )

        # Print comprehensive detailed analysis
        print_detailed_analysis(
            self.reasoning_dict,
            swing_analysis,
            pattern_analysis,
            smart_money_analysis,
            liquidity_analysis,
            trade_reasoning
        )

        # ====== END COMPREHENSIVE REASONING DICTIONARY ======

        # Print full reasoning chain from brain
        print("\n" + "="*100)
        print("CHAIN OF THOUGHT REASONING (Brain's Internal Logic)")
        print("="*100)
        for line in decision.reasoning_chain:
            print(line)

        print("\n" + "="*100)
        print("[FINAL DECISION SUMMARY]")
        print("="*100)
        print(f"  Direction: {decision.direction}")
        print(f"  Confidence: {decision.confidence:.0%}")
        print(f"  Signal Strength: {decision.signal_strength}")
        print(f"  Should Trade: {'YES' if decision.should_trade else 'NO'}")
        print(f"  Urgency: {decision.urgency}")
        print(f"  Analysis Quality: {decision.analysis_quality:.0%}")

        if decision.should_trade:
            print(f"\n[TRADE PARAMETERS]")
            print(f"  Entry Zone: ${decision.entry_zone[0]:.2f} - ${decision.entry_zone[1]:.2f}")
            print(f"  Stop Loss: ${decision.stop_loss:.2f}")
            print(f"  Take Profits: {', '.join([f'${tp:.2f}' for tp in decision.take_profits])}")
            print(f"  Risk/Reward: {decision.risk_reward:.2f}:1")
            print(f"  Position Size: {decision.position_size_multiplier:.0%}")
            print(f"  Max Risk: {decision.max_risk_percent:.1f}%")

        if decision.blockers:
            print(f"\n[BLOCKERS] ({len(decision.blockers)})")
            for i, blocker in enumerate(decision.blockers, 1):
                print(f"  {i}. {blocker}")

        if decision.warnings:
            print(f"\n[WARNINGS] ({len(decision.warnings)})")
            for i, warning in enumerate(decision.warnings, 1):
                print(f"  {i}. {warning}")

        if decision.opportunities:
            print(f"\n[OPPORTUNITIES] ({len(decision.opportunities)})")
            for i, opportunity in enumerate(decision.opportunities, 1):
                print(f"  {i}. {opportunity}")

        if not decision.should_trade:
            print("\n" + "="*100)
            print("[NO TRADE] Conditions not met - continuing to monitor...")
            print("="*100)
            return None

        # Check if we can get better RR with precision calculator
        print("\n" + "="*100)
        print("[PRECISION TP/SL OPTIMIZATION]")
        print("="*100)
        print(f"\nBrain suggested RR: {decision.risk_reward:.2f}:1")
        print("Checking if we can improve with smart money logic...")

        # Try to find better setup
        precision_setup = self.precision_calculator.calculate_optimal_setup(
            decision.direction, current_price, market_intel
        )

        if precision_setup and precision_setup.risk_reward_ratio > decision.risk_reward:
            print(f"\n[IMPROVED SETUP FOUND]")
            print(f"  Old RR: {decision.risk_reward:.2f}:1")
            print(f"  New RR: {precision_setup.risk_reward_ratio:.2f}:1")
            print(f"  Improvement: +{((precision_setup.risk_reward_ratio - decision.risk_reward) / decision.risk_reward * 100):.0f}%")

            # Update decision with precision levels
            decision.entry_zone = precision_setup.entry_zone
            decision.stop_loss = precision_setup.stop_loss
            decision.take_profits = [precision_setup.primary_target] + precision_setup.secondary_targets
            decision.risk_reward = precision_setup.risk_reward_ratio

        # Execute on Bybit if live mode
        if self.live_execution and self.bybit_executor:
            print("\n" + "="*100)
            print("[EXECUTING ON BYBIT]")
            print("="*100)

            success = await self.bybit_executor.execute_arsenal_decision(decision, current_price)

            if success:
                print("\n[TRADE EXECUTED SUCCESSFULLY]")
                print("System will monitor position outcome via Bybit executor...")
                # In live mode, Bybit executor handles position monitoring
                return None  # Don't use local trade monitor in live mode
            else:
                print("\n[TRADE EXECUTION FAILED]")
                print("Continuing to monitor for next opportunity...")
                return None

        return decision

    def create_trade_plan(self, decision, market_intel, current_price):
        """Create complete trade plan"""

        print("\n" + "="*100)
        print("[CREATING TRADE PLAN]")
        print("="*100)

        trade_plan = self.scenario_planner.create_trade_plan(decision, market_intel, current_price)

        return trade_plan

    def monitor_active_trade(self, trade_id, trade_plan, df, market_intel):
        """Monitor active trade"""

        print("\n" + "="*100)
        print(f"[MONITORING ACTIVE TRADE: {trade_id}]")
        print("="*100)

        trade = self.trade_monitor.active_trades.get(trade_id)
        if not trade:
            print("[ERROR] Trade not found in monitor")
            return

        current_price = float(df.iloc[-1]['close'])
        current_candle = df.iloc[-1]

        # Check trade
        result = self.trade_monitor.check_trade(
            trade_id, current_price, current_candle, market_intel, df
        )

        print(f"\n[MONITORING RESULT]")
        print(f"  Action: {result['action']}")
        print(f"  Reason: {result['reason']}")

        if result['action'] == 'EXIT':
            print(f"\n[EXITING TRADE]")
            print(f"  Exit Price: ${current_price:.2f}")
            print(f"  Final P&L: {trade.unrealized_pnl_pct*100:+.2f}%")
            print(f"  Use Market Order: {result.get('use_market_order', False)}")
            self.current_trade_id = None
            print("\n[TRADE CLOSED] - Returning to monitoring mode...")

        elif result['action'] == 'ADJUST_STOP':
            print(f"\n[ADJUSTING STOP]")
            print(f"  Old Stop: ${trade.current_stop:.2f}")
            print(f"  New Stop: ${result['new_stop']:.2f}")
            trade.current_stop = result['new_stop']
            trade.stop_adjustments_count += 1

        elif result['action'] == 'EXECUTE_TP':
            print(f"\n[EXECUTING TAKE PROFIT]")
            print(f"  TP Level: ${result.get('tp_to_execute', 0):.2f}")
            print(f"  Partial Exit: {result.get('partial_pct', 1.0)*100:.0f}%")
            print(f"  Use Market Order: {result['use_market_order']}")
            # Remove TP from targets
            if trade.current_targets:
                trade.current_targets.pop(0)
                trade.partial_exits.append(current_price)
            if not trade.current_targets:
                print("\n[ALL TARGETS HIT] - Trade complete!")
                self.current_trade_id = None

    async def run_async(self):
        """Main async run loop"""

        self.print_header()

        # Initialize Bybit executor if in live mode
        if self.live_execution and self.bybit_executor:
            print("\n[INITIALIZING BYBIT EXECUTOR]")
            await self.bybit_executor.initialize()
            print("[OK] Bybit connection established\n")

            # Start position monitoring task
            monitor_task = asyncio.create_task(self.bybit_executor.start())

        print("\n[STARTING CONTINUOUS MONITORING]")
        print(f"Full analysis on new {self.timeframe} candles | Real-time monitoring every {self.realtime_update_interval}s")
        print("Press Ctrl+C to stop\n")

        last_realtime_update = datetime.utcnow()

        try:
            while True:
                # Fetch latest data to check for new candle
                df_check = fetch_binance_data(self.symbol, self.timeframe, 200)

                # Only run full analysis if new candle available
                if self.has_new_candle(df_check):
                    self.analysis_count += 1

                    print(f"\n[NEW CANDLE DETECTED] Running full arsenal analysis #{self.analysis_count}...")

                    # Run arsenal analysis
                    market_intel, df, current_price, trendline_data = self.run_arsenal_analysis()

                    # If we have an active trade (monitoring mode only), monitor it
                    if self.current_trade_id and not self.live_execution:
                        self.monitor_active_trade(self.current_trade_id,
                                                 self.trade_monitor.trade_plans[self.current_trade_id],
                                                 df, market_intel)
                    else:
                        # Check for new trade setup
                        decision = await self.check_for_trade_setup(market_intel, current_price, df)

                        # In monitoring mode, simulate trade
                        if decision and not self.live_execution:
                            # Create trade plan
                            trade_plan = self.create_trade_plan(decision, market_intel, current_price)

                            # Start monitoring (simulation only)
                            print("\n" + "="*100)
                            print("[TRADE SETUP FOUND - WOULD EXECUTE ON BYBIT]")
                            print("="*100)
                            print(f"\nFor now, simulating trade monitoring...")

                            trade_id = f"trade_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                            entry_price = trade_plan.entry_price
                            position_size = 100.0  # $100 for simulation

                            self.trade_monitor.start_monitoring_trade(
                                trade_id, trade_plan, entry_price, position_size
                            )
                            self.current_trade_id = trade_id

                    print(f"\n[MONITORING] Checking for next candle in {self.analysis_interval}s...")
                    print(f"[REAL-TIME] Live price action updates every {self.realtime_update_interval}s")
                    print("="*100 + "\n")

                    # Reset real-time update timer after full analysis
                    last_realtime_update = datetime.utcnow()

                # REAL-TIME MONITORING between candles
                now = datetime.utcnow()
                time_since_last_update = (now - last_realtime_update).total_seconds()

                if time_since_last_update >= self.realtime_update_interval:
                    # Show real-time price action if we have swing data
                    if self.last_swing_highs or self.last_swing_lows:
                        self.display_realtime_price_action()
                    last_realtime_update = now

                # Wait before checking again (shorter interval for responsiveness)
                await asyncio.sleep(self.realtime_update_interval)

        except KeyboardInterrupt:
            print("\n\n" + "="*100)
            print("[SYSTEM SHUTDOWN]")
            print("="*100)
            print(f"\nTotal analyses performed: {self.analysis_count}")

            # Shutdown Bybit executor if active
            if self.live_execution and self.bybit_executor:
                await self.bybit_executor.shutdown()

            if self.current_trade_id and not self.live_execution:
                trade = self.trade_monitor.active_trades[self.current_trade_id]
                print(f"\nActive trade status:")
                print(f"  Trade ID: {self.current_trade_id}")
                print(f"  P&L: {trade.unrealized_pnl_pct*100:+.2f}%")
                print(f"  Status: {trade.status.value}")

            print("\n[ARSENAL SYSTEM STOPPED]")
            print("="*100 + "\n")

    def run(self):
        """Synchronous wrapper for async run loop"""
        asyncio.run(self.run_async())


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    live_mode = False
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['--live', '-l', 'live']:
        live_mode = True
        print("\n" + "="*100)
        print("WARNING: LIVE EXECUTION MODE ENABLED")
        print("="*100)
        print("\nThis will execute REAL trades on Bybit with REAL money.")
        print("Position size: $100 with 10x leverage")
        print("Max daily drawdown: $20")
        print("\nPress Ctrl+C within 5 seconds to cancel...")
        print("="*100 + "\n")

        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[CANCELLED] Exiting...")
            sys.exit(0)

        print("[CONFIRMED] Starting live execution system...\n")

    # Create and run system
    system = LiveArsenalSystem(symbol="SOLUSDT", timeframe="5m", live_execution=live_mode)
    system.run()
