"""
ARSENAL WITH MEMORY TEST

Demonstrates persistent memory capabilities:
- Records market events as they happen
- Remembers decisions across restarts
- Uses historical context for better decisions
- Learns from past patterns

Run this twice to see memory in action:
1. First run: Creates memories
2. Second run: Loads memories and uses them
"""

from datetime import datetime, timedelta
import pandas as pd
import time

# Import all modules
from realtime_swing_detector import fetch_binance_data, get_current_price, detect_candle_close_patterns
from fvg_detector import FVGDetector
from order_block_detector import OrderBlockDetector
from liquidity_sweep_detector import LiquiditySweepDetector
from range_trap_detector import RangeTrapDetector
from bos_choch_detector import BOSCHoCHDetector
from trendline_confluence_module import get_trendline_analyzer

# Helper functions
from test_ultimate_arsenal import find_swing_highs, find_swing_lows, analyze_trend_structure, MarketIntelligence

# Memory-enhanced brain
from intelligent_strategy_brain_with_memory import IntelligentStrategyBrainWithMemory


print("="*80)
print("ARSENAL WITH MEMORY - PERSISTENT INTELLIGENCE TEST")
print("="*80)
print("\nTesting memory system capabilities...")
print("This arsenal remembers market context and learns from history\n")

# Configuration
symbol = "SOLUSDT"
timeframe = "5m"
lookback_hours = 4.0
memory_db = "market_arsenal_memory.db"

print(f"Symbol: {symbol}")
print(f"Timeframe: {timeframe}")
print(f"Memory Database: {memory_db}")
print(f"Analysis Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

# ========================================================================
# INITIALIZE BRAIN WITH MEMORY
# ========================================================================
print("="*80)
print("INITIALIZING BRAIN WITH MEMORY")
print("="*80)

brain = IntelligentStrategyBrainWithMemory(memory_db)

# Show memory summary
print("\n" + "="*80)
print("HISTORICAL MEMORY LOADED")
print("="*80)
brain.show_memory_summary()

# ========================================================================
# GATHER ALL MARKET DATA
# ========================================================================
print("\n" + "="*80)
print("GATHERING CURRENT MARKET INTELLIGENCE")
print("="*80)

print("\n[1/11] Fetching market data...")
df = fetch_binance_data(symbol, timeframe, 200)
current_price = float(df.iloc[-1]['close'])
print(f"   Current Price: ${current_price:.2f}")

# Filter to recent data
now = datetime.utcnow()
cutoff = now - timedelta(hours=lookback_hours)
recent = df[df['timestamp'] >= cutoff].copy()
print(f"   Recent candles: {len(recent)}")

# Swing structure
print("\n[2/11] Analyzing swing structure...")
swing_highs = find_swing_highs(recent, lookback=2)
swing_lows = find_swing_lows(recent, lookback=2)
print(f"   Swing Highs: {len(swing_highs)}")
print(f"   Swing Lows: {len(swing_lows)}")

# Trend analysis
print("\n[3/11] Determining trend...")
trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
print(f"   Trend: {trend_analysis['trend_direction'].upper()}")
print(f"   Strength: {trend_analysis['trend_strength']:.0%}")

# Candle patterns
print("\n[4/11] Detecting candle patterns...")
patterns = detect_candle_close_patterns(recent, lookback_bars=20)
print(f"   Patterns detected: {len(patterns)}")

# FVGs
print("\n[5/11] Detecting Fair Value Gaps...")
fvg_detector = FVGDetector()
fvgs = fvg_detector.detect(df, current_price)
active_fvgs = fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)
print(f"   Total FVGs: {len(fvgs)}")
print(f"   Active FVGs: {len(active_fvgs)}")

# Order Blocks
print("\n[6/11] Detecting Order Blocks...")
ob_detector = OrderBlockDetector()
obs = ob_detector.detect(df, current_price)
active_obs = ob_detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)
print(f"   Total Order Blocks: {len(obs)}")
print(f"   Active Order Blocks: {len(active_obs)}")

# Liquidity Sweeps
print("\n[7/11] Detecting liquidity sweeps...")
liquidity_detector = LiquiditySweepDetector()
sweeps = liquidity_detector.detect_sweeps(recent, swing_highs, swing_lows)
print(f"   Sweeps detected: {len(sweeps)}")

# Liquidity Pools
print("\n[8/11] Mapping liquidity pools...")
pools = liquidity_detector.map_liquidity_pools(swing_highs, swing_lows, sweeps, current_price)
print(f"   Liquidity pools: {len(pools)}")

# Stop Hunt Check
print("\n[9/11] Checking stop hunt mode...")
stop_hunt_warning = liquidity_detector.detect_stop_hunt_mode(sweeps, pools, lookback_hours=lookback_hours)
print(f"   Stop Hunt Mode: {'ACTIVE' if stop_hunt_warning.is_stop_hunt_mode else 'INACTIVE'}")
print(f"   Severity: {stop_hunt_warning.severity:.0%}")

# Range Trap Detection
print("\n[10/11] Detecting range traps...")
trap_detector = RangeTrapDetector()
trap_analysis = trap_detector.analyze(swing_highs, swing_lows, patterns, current_price, lookback_hours)
print(f"   Range Trap: {'YES' if trap_analysis.is_trapped else 'NO'}")
print(f"   Trap Severity: {trap_analysis.trap_severity:.0%}")
print(f"   Danger Level: {trap_analysis.danger_level}")

# Confluence Scoring
print("\n[11/11] Calculating confluence...")
analyzer = get_trendline_analyzer()
trendline_data = analyzer.get_comprehensive_analysis(symbol, timeframe, lookback_hours)
confluence = analyzer.calculate_confluence_points(
    swing_highs,
    swing_lows,
    patterns,
    current_price,
    'LONG' if trend_analysis['trend_direction'] == 'uptrend' else 'SHORT'
)
print(f"   Confluence Score: {confluence['total_points']} points")
print(f"   Bullish: {confluence['bullish_points']} | Bearish: {confluence['bearish_points']}")

# ========================================================================
# CREATE MARKET INTELLIGENCE
# ========================================================================
print("\n" + "="*80)
print("CREATING MARKET INTELLIGENCE REPORT")
print("="*80)

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

print("Market Intelligence compiled successfully")

# ========================================================================
# MEMORY-ENHANCED ANALYSIS
# ========================================================================
print("\n" + "="*80)
print("ACTIVATING MEMORY-ENHANCED BRAIN")
print("="*80)
print("Analyzing with historical context...")
print("Using past patterns to improve decision...\n")

decision = brain.analyze(market_intel)

# ========================================================================
# PRINT DECISION WITH MEMORY CONTEXT
# ========================================================================
brain.print_enhanced_decision(decision)

# ========================================================================
# SUMMARY
# ========================================================================
print("\n" + "="*80)
print("MEMORY-ENHANCED ARSENAL TEST COMPLETE")
print("="*80)

print(f"\n[SYSTEM STATUS]")
print(f"  All 11 modules: OPERATIONAL")
print(f"  Memory System: ACTIVE")
print(f"  Intelligence Quality: {decision.analysis_quality:.0%}")

# Memory stats
stats = brain.memory.get_memory_stats()
print(f"\n[MEMORY STATISTICS]")
print(f"  Total events recorded: {stats['total_events']}")
print(f"  Decisions tracked: {stats['total_decisions']}")
print(f"  Range periods logged: {stats['range_periods']}")
print(f"  Days of history: {stats['days_of_history']:.1f}")

print(f"\n[DECISION]")
print(f"  Direction: {decision.direction}")
print(f"  Confidence: {decision.confidence:.0%}")
print(f"  Signal Strength: {decision.signal_strength}")
print(f"  Should Trade: {'YES' if decision.should_trade else 'NO'}")
print(f"  Urgency: {decision.urgency}")

if decision.blockers:
    print(f"\n[BLOCKERS]")
    for blocker in decision.blockers:
        print(f"  - {blocker}")

if decision.warnings:
    print(f"\n[WARNINGS]")
    for warning in decision.warnings[:5]:
        print(f"  - {warning}")

print(f"\n[KEY FEATURES]")
print(f"  - Remembers market events across restarts")
print(f"  - Learns from historical patterns")
print(f"  - Tracks regime changes and range periods")
print(f"  - Uses memory to enhance decision quality")
print(f"  - Builds long-term market intelligence")

print("\n" + "="*80)
print("RUN THIS TEST AGAIN TO SEE MEMORY IN ACTION")
print("="*80)
print("The second run will load today's events and use them for better decisions!")

# Close memory
brain.close()

print("\n" + "="*80)
print("MEMORY SAVED - ARSENAL REMEMBERS")
print("="*80)
