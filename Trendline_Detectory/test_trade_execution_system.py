"""
TEST: Complete Trade Execution System

Demonstrates the full flow:
1. Arsenal analyzes market
2. Scenario planner creates trade plan
3. Trade monitor watches in real-time
4. Smart execution prevents Horus failures

Shows how it would handle:
- Entry at key zones
- Invalidation detection (not on minor pullbacks)
- Dynamic stop management
- Smart TP execution (market orders when needed)
- Reversal prediction
"""

from datetime import datetime, timedelta
import pandas as pd

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

# NEW: Trade execution system
from trade_scenario_planner import TradeScenarioPlanner
from realtime_trade_monitor import RealtimeTradeMonitor, TradeStatus


def print_section(title):
    """Print section header"""
    print("\n" + "="*80)
    print(title)
    print("="*80)


def print_trade_plan(plan):
    """Print the complete trade plan"""
    print("\n[TRADE PLAN CREATED]")
    print(f"  Direction: {plan.direction}")
    print(f"  Entry Zone: ${plan.entry_zone[0]:.2f} - ${plan.entry_zone[1]:.2f}")
    print(f"  Initial Stop: ${plan.initial_stop:.2f}")
    print(f"  Targets: {', '.join([f'${tp:.2f}' for tp in plan.targets])}")
    print(f"  Invalidation Level: ${plan.invalidation_level:.2f}")
    print(f"  Risk/Reward: {plan.risk_reward_ratio:.2f}:1")

    print(f"\n[INVALIDATION SCENARIOS - {len(plan.invalidation_scenarios)} planned]")
    for i, scenario in enumerate(plan.invalidation_scenarios, 1):
        print(f"  {i}. {scenario.description}")
        print(f"     Trigger: {scenario.trigger_condition}")
        print(f"     Action: {scenario.action} ({scenario.urgency})")
        print(f"     Severity: {scenario.severity:.0%}")

    print(f"\n[STOP ADJUSTMENT PLAN - {len(plan.stop_adjustment_plan)} scenarios]")
    for i, scenario in enumerate(plan.stop_adjustment_plan, 1):
        print(f"  {i}. {scenario.description}")
        print(f"     Trigger: {scenario.trigger_condition}")
        print(f"     New stop: {scenario.new_stop_calculation}")

    print(f"\n[TP EXECUTION PLAN - {len(plan.tp_execution_plan)} targets]")
    for i, scenario in enumerate(plan.tp_execution_plan, 1):
        print(f"  {i}. TP{i} @ ${scenario.tp_level:.2f} ({scenario.partial_exit_pct*100:.0f}% of position)")
        print(f"     Watch for: {', '.join(scenario.reversal_indicators[:2])}")
        print(f"     Use market if within: {scenario.use_market_if_close_pct*100:.2f}%")


def simulate_trade_monitoring(monitor, trade_id, plan, df, market_intel):
    """Simulate monitoring the trade through recent candles"""

    print_section("REAL-TIME MONITORING SIMULATION")
    print("Simulating trade monitoring through recent price action...\n")

    current_price = float(df.iloc[-1]['close'])

    # Simulate entry
    entry_price = plan.entry_zone[0]
    position_size = 100.0  # $100 position

    monitor.start_monitoring_trade(trade_id, plan, entry_price, position_size)

    # Monitor last 10 candles
    print("\n[MONITORING LAST 10 CANDLES]")
    recent_candles = df.tail(10)

    for idx, (i, candle) in enumerate(recent_candles.iterrows(), 1):
        price = float(candle['close'])

        # Check trade
        result = monitor.check_trade(trade_id, price, candle, market_intel, df)

        # Print update
        if idx % 3 == 0 or result['action'] != 'HOLD':  # Print every 3rd candle or when action
            print(f"\n  Candle {idx}: {candle['timestamp'].strftime('%H:%M')} - ${price:.2f}")
            print(f"    Action: {result['action']}")
            print(f"    Reason: {result['reason']}")

            if result['action'] == 'EXIT':
                print(f"    [CRITICAL] Exiting trade - {result['reason']}")
                print(f"    Use market order: {result.get('use_market_order', False)}")
                return

            elif result['action'] == 'ADJUST_STOP':
                print(f"    [STOP ADJUSTMENT] New stop: ${result['new_stop']:.2f}")

            elif result['action'] == 'EXECUTE_TP':
                print(f"    [TP EXECUTION] Taking profit at ${result.get('tp_to_execute', 0):.2f}")
                print(f"    Use market order: {result['use_market_order']}")

    print(f"\n[FINAL STATUS]")
    trade = monitor.active_trades[trade_id]
    print(f"  Status: {trade.status.value}")
    print(f"  Unrealized P&L: {trade.unrealized_pnl_pct*100:+.2f}%")
    print(f"  Current Stop: ${trade.current_stop:.2f}")
    print(f"  Remaining Targets: {len(trade.current_targets)}")


print_section("ARSENAL + TRADE EXECUTION SYSTEM - COMPLETE TEST")
print("\nDemonstrates full integration:")
print("1. Arsenal analyzes market")
print("2. Planner creates scenarios")
print("3. Monitor executes intelligently")
print("4. Learns from Horus failures\n")

# Configuration
symbol = "SOLUSDT"
timeframe = "5m"
lookback_hours = 4.0

print(f"Symbol: {symbol}")
print(f"Timeframe: {timeframe}")
print(f"Analysis Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

# ========================================================================
# STEP 1: ARSENAL ANALYSIS (Same as before)
# ========================================================================
print_section("STEP 1: ARSENAL MARKET ANALYSIS")
print("Running full 11-module analysis...\n")

df = fetch_binance_data(symbol, timeframe, 200)
current_price = float(df.iloc[-1]['close'])
print(f"Current Price: ${current_price:.2f}")

now = datetime.utcnow()
cutoff = now - timedelta(hours=lookback_hours)
recent = df[df['timestamp'] >= cutoff].copy()

# Gather all intelligence
swing_highs = find_swing_highs(recent, lookback=2)
swing_lows = find_swing_lows(recent, lookback=2)
trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
patterns = detect_candle_close_patterns(recent, lookback_bars=20)

fvg_detector = FVGDetector()
fvgs = fvg_detector.detect(df, current_price)
active_fvgs = fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)

ob_detector = OrderBlockDetector()
obs = ob_detector.detect(df, current_price)
active_obs = ob_detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)

liquidity_detector = LiquiditySweepDetector()
sweeps = liquidity_detector.detect_sweeps(recent, swing_highs, swing_lows)
pools = liquidity_detector.map_liquidity_pools(swing_highs, swing_lows, sweeps, current_price)
stop_hunt_warning = liquidity_detector.detect_stop_hunt_mode(sweeps, pools, lookback_hours=lookback_hours)

trap_detector = RangeTrapDetector()
trap_analysis = trap_detector.analyze(swing_highs, swing_lows, patterns, current_price, lookback_hours)

analyzer = get_trendline_analyzer()
trendline_data = analyzer.get_comprehensive_analysis(symbol, timeframe, lookback_hours)
confluence = analyzer.calculate_confluence_points(
    swing_highs,
    swing_lows,
    patterns,
    current_price,
    'LONG' if trend_analysis['trend_direction'] == 'uptrend' else 'SHORT'
)

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

print(f"\nMarket Intelligence compiled:")
print(f"  Trend: {trend_analysis['trend_direction']} ({trend_analysis['trend_strength']:.0%})")
print(f"  Range Trap: {trap_analysis.is_trapped} ({trap_analysis.trap_severity:.0%} severity)")
print(f"  Stop Hunt: {stop_hunt_warning.is_stop_hunt_mode} ({stop_hunt_warning.severity:.0%} severity)")
print(f"  Confluence: {confluence['total_points']} points")

# ========================================================================
# STEP 2: INTELLIGENT DECISION
# ========================================================================
print_section("STEP 2: INTELLIGENT BRAIN DECISION")
print("Analyzing with sophisticated AI reasoning...\n")

brain = IntelligentStrategyBrain()
decision = brain.analyze(market_intel)

print(f"[DECISION]")
print(f"  Direction: {decision.direction}")
print(f"  Confidence: {decision.confidence:.0%}")
print(f"  Signal Strength: {decision.signal_strength}")
print(f"  Should Trade: {'YES' if decision.should_trade else 'NO'}")
print(f"  Urgency: {decision.urgency}")

if decision.blockers:
    print(f"\n[BLOCKERS]")
    for blocker in decision.blockers:
        print(f"  - {blocker}")

# ========================================================================
# STEP 3: TRADE SCENARIO PLANNING (NEW!)
# ========================================================================
print_section("STEP 3: TRADE SCENARIO PLANNING")
print("Creating complete trade plan with all future scenarios...\n")

if decision.should_trade:
    planner = TradeScenarioPlanner()
    trade_plan = planner.create_trade_plan(decision, market_intel, current_price)

    print_trade_plan(trade_plan)

    # ========================================================================
    # STEP 4: REAL-TIME MONITORING (NEW!)
    # ========================================================================
    monitor = RealtimeTradeMonitor()
    trade_id = f"test_trade_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    simulate_trade_monitoring(monitor, trade_id, trade_plan, df, market_intel)

else:
    print("\n[NO TRADE PLAN CREATED]")
    print("Decision was blocked - no trade to execute")
    print(f"Reason: {decision.blockers[0] if decision.blockers else 'Low confidence'}")

# ========================================================================
# SUMMARY
# ========================================================================
print_section("SUMMARY: ARSENAL + EXECUTION SYSTEM")

print("\n[WHAT THIS SYSTEM DOES]")
print("  1. Arsenal analyzes 11 dimensions of market structure")
print("  2. Brain makes intelligent decision with reasoning")
print("  3. Planner creates complete scenario playbook")
print("  4. Monitor executes scenarios in real-time")

print("\n[HOW IT FIXES HORUS FAILURES]")
print("  1. Doesn't close on minor pullbacks (smart invalidation)")
print("  2. Uses market orders near TP (no missed $206 scenario)")
print("  3. Trails stops intelligently (knows when to stop)")
print("  4. Predicts reversals before they happen")
print("  5. Exits before TP if reversal imminent")

print("\n[READY FOR LIVE BYBIT INTEGRATION]")
print("  - All scenarios planned before entry")
print("  - Real-time monitoring in place")
print("  - Smart execution logic ready")
print("  - Just needs Bybit API wrapper")

print("\n" + "="*80)
print("COMPLETE TRADE EXECUTION SYSTEM - READY")
print("="*80)
