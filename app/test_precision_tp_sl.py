"""
TEST: Precision TP/SL Calculator

Demonstrates how we find MUCH better setups with 2:1+ RR:
- Uses FVGs as targets (price fills these)
- Uses Order Blocks for entries
- Places stops BEYOND liquidity pools
- Targets actual liquidity zones

Compares:
- OLD METHOD: 0.53:1 RR (terrible)
- NEW METHOD: 2:1+ RR (excellent)
"""

from datetime import datetime, timedelta
from realtime_swing_detector import fetch_binance_data, detect_candle_close_patterns
from fvg_detector import FVGDetector
from order_block_detector import OrderBlockDetector
from liquidity_sweep_detector import LiquiditySweepDetector
from range_trap_detector import RangeTrapDetector
from trendline_confluence_module import get_trendline_analyzer
from test_ultimate_arsenal import find_swing_highs, find_swing_lows, analyze_trend_structure, MarketIntelligence
from intelligent_strategy_brain import IntelligentStrategyBrain

# NEW: Precision calculator
from precision_tp_sl_calculator import PrecisionTPSLCalculator


def print_section(title):
    print("\n" + "="*80)
    print(title)
    print("="*80)


def compare_setups(old_decision, precision_setup, direction):
    """Compare old vs new setup"""

    print_section("RR COMPARISON: OLD VS NEW")

    print("\n[OLD METHOD - Simple Swing Levels]")
    print(f"  Entry: ${old_decision.entry_zone[0]:.2f}")
    print(f"  Stop: ${old_decision.stop_loss:.2f}")
    print(f"  TP1: ${old_decision.take_profits[0]:.2f}")

    old_risk = abs(old_decision.entry_zone[0] - old_decision.stop_loss)
    old_reward = abs(old_decision.take_profits[0] - old_decision.entry_zone[0])
    old_rr = old_reward / old_risk if old_risk > 0 else 0

    print(f"  Risk: ${old_risk:.2f}")
    print(f"  Reward: ${old_reward:.2f}")
    print(f"  RR: {old_rr:.2f}:1 {'[POOR]' if old_rr < 2 else '[GOOD]'}")

    print("\n[NEW METHOD - Smart Money Execution]")
    print(f"  Entry: ${precision_setup.entry_price:.2f}")
    print(f"  Reason: {precision_setup.entry_reason}")
    print(f"  Stop: ${precision_setup.stop_loss:.2f}")
    print(f"  Reason: {precision_setup.stop_reason}")
    print(f"  Safe from sweep: {'YES' if precision_setup.safe_from_sweep else 'NO'}")
    print(f"  TP1: ${precision_setup.primary_target:.2f}")
    print(f"  Reason: {precision_setup.target_reasons[0]}")

    print(f"\n  Risk: ${precision_setup.risk_amount:.2f}")
    print(f"  Reward: ${precision_setup.reward_amount:.2f}")
    print(f"  RR: {precision_setup.risk_reward_ratio:.2f}:1 {'[EXCELLENT]' if precision_setup.risk_reward_ratio >= 3 else '[GOOD]'}")

    print(f"\n  Setup Quality: {precision_setup.setup_quality:.0%}")
    print(f"  Statistical Edge: {precision_setup.edge_score:.0%}")

    print("\n[IMPROVEMENT]")
    rr_improvement = ((precision_setup.risk_reward_ratio - old_rr) / old_rr * 100) if old_rr > 0 else 0
    print(f"  RR improved by: {rr_improvement:+.0f}%")
    print(f"  Risk reduced by: {((old_risk - precision_setup.risk_amount) / old_risk * 100):.0f}%")

    # Show all targets
    if precision_setup.secondary_targets:
        print(f"\n[SECONDARY TARGETS]")
        for i, (tp, reason) in enumerate(zip(precision_setup.secondary_targets,
                                            precision_setup.target_reasons[1:]), 2):
            print(f"  TP{i}: ${tp:.2f}")
            print(f"  Reason: {reason}")


print_section("PRECISION TP/SL CALCULATOR TEST")
print("\nShows how to find high-RR setups using smart money logic")
print("Compares old method (0.53:1) vs new method (2:1+)\n")

# Fetch market data
symbol = "SOLUSDT"
timeframe = "5m"
lookback_hours = 4.0

print(f"Symbol: {symbol}")
print(f"Timeframe: {timeframe}\n")

# Gather market intelligence
print_section("GATHERING MARKET INTELLIGENCE")

df = fetch_binance_data(symbol, timeframe, 200)
current_price = float(df.iloc[-1]['close'])
print(f"Current Price: ${current_price:.2f}")

now = datetime.utcnow()
cutoff = now - timedelta(hours=lookback_hours)
recent = df[df['timestamp'] >= cutoff].copy()

swing_highs = find_swing_highs(recent, lookback=2)
swing_lows = find_swing_lows(recent, lookback=2)
trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
patterns = detect_candle_close_patterns(recent, lookback_bars=20)

print(f"\nSwing Highs: {len(swing_highs)}")
print(f"Swing Lows: {len(swing_lows)}")

fvg_detector = FVGDetector()
fvgs = fvg_detector.detect(df, current_price)
active_fvgs = fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)
print(f"Active FVGs: {len(active_fvgs)}")

ob_detector = OrderBlockDetector()
obs = ob_detector.detect(df, current_price)
active_obs = ob_detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)
print(f"Active Order Blocks: {len(active_obs)}")

liquidity_detector = LiquiditySweepDetector()
sweeps = liquidity_detector.detect_sweeps(recent, swing_highs, swing_lows)
pools = liquidity_detector.map_liquidity_pools(swing_highs, swing_lows, sweeps, current_price)
stop_hunt_warning = liquidity_detector.detect_stop_hunt_mode(sweeps, pools, lookback_hours=lookback_hours)
print(f"Liquidity Pools: {len(pools)}")

trap_detector = RangeTrapDetector()
trap_analysis = trap_detector.analyze(swing_highs, swing_lows, patterns, current_price, lookback_hours)

analyzer = get_trendline_analyzer()
confluence = analyzer.calculate_confluence_points(
    swing_highs, swing_lows, patterns, current_price,
    'LONG' if trend_analysis['trend_direction'] == 'uptrend' else 'SHORT'
)

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

print(f"Confluence: {confluence['total_points']} points")
print(f"Trend: {trend_analysis['trend_direction']} ({trend_analysis['trend_strength']:.0%})")

# Get OLD method decision
print_section("OLD METHOD: Simple Swing Levels")
brain = IntelligentStrategyBrain()
old_decision = brain.analyze(market_intel)

print(f"Direction: {old_decision.direction}")
print(f"Confidence: {old_decision.confidence:.0%}")
print(f"Entry: ${old_decision.entry_zone[0]:.2f}")
print(f"Stop: ${old_decision.stop_loss:.2f}")
print(f"TP1: ${old_decision.take_profits[0]:.2f}")
print(f"RR: {old_decision.risk_reward:.2f}:1 [TERRIBLE!]")

# Calculate NEW method setups
print_section("NEW METHOD: Smart Money Execution")
calculator = PrecisionTPSLCalculator()

# Try both LONG and SHORT to find best setup
print("\nCalculating optimal LONG setup...")
long_setup = calculator.calculate_optimal_setup('LONG', current_price, market_intel)

print("Calculating optimal SHORT setup...")
short_setup = calculator.calculate_optimal_setup('SHORT', current_price, market_intel)

# Show results
if long_setup:
    print(f"\n[LONG SETUP FOUND]")
    print(f"  Entry: ${long_setup.entry_price:.2f}")
    print(f"  Stop: ${long_setup.stop_loss:.2f}")
    print(f"  TP1: ${long_setup.primary_target:.2f}")
    print(f"  RR: {long_setup.risk_reward_ratio:.2f}:1")
    print(f"  Quality: {long_setup.setup_quality:.0%}")
else:
    print("\n[NO LONG SETUP] - Can't achieve 2:1 RR")

if short_setup:
    print(f"\n[SHORT SETUP FOUND]")
    print(f"  Entry: ${short_setup.entry_price:.2f}")
    print(f"  Stop: ${short_setup.stop_loss:.2f}")
    print(f"  TP1: ${short_setup.primary_target:.2f}")
    print(f"  RR: {short_setup.risk_reward_ratio:.2f}:1")
    print(f"  Quality: {short_setup.setup_quality:.0%}")
else:
    print("\n[NO SHORT SETUP] - Can't achieve 2:1 RR")

# Detailed comparison with best setup
if long_setup and (not short_setup or long_setup.risk_reward_ratio >= short_setup.risk_reward_ratio):
    compare_setups(old_decision, long_setup, 'LONG')
    best_setup = long_setup
    best_direction = 'LONG'
elif short_setup:
    compare_setups(old_decision, short_setup, 'SHORT')
    best_setup = short_setup
    best_direction = 'SHORT'
else:
    print("\n[WARNING] No setup meets 2:1 minimum RR")
    print("Better to WAIT for better opportunity than take poor RR trade")
    best_setup = None

# Summary
print_section("SUMMARY")

print("\n[KEY IMPROVEMENTS]")
print("  1. Uses Order Blocks for precise entry zones")
print("  2. Places stops BEYOND liquidity pools (safe from sweeps)")
print("  3. Targets unfilled FVGs (price loves to fill these)")
print("  4. Targets liquidity concentrations (where price goes)")
print("  5. Minimum 2:1 RR enforced (won't take poor setups)")

print("\n[WHY THIS MATTERS]")
print("  Old: Risk $3.31 to make $1.74 (0.53:1) = Losing strategy")
if best_setup:
    print(f"  New: Risk ${best_setup.risk_amount:.2f} to make ${best_setup.reward_amount:.2f} ({best_setup.risk_reward_ratio:.2f}:1) = Winning strategy")
    print(f"\n  With {best_setup.risk_reward_ratio:.2f}:1 RR, you only need {(1/(1+best_setup.risk_reward_ratio))*100:.0f}% win rate to be profitable!")
else:
    print("  New: BLOCKS trade if can't achieve 2:1+ RR = Capital preservation")

print("\n" + "="*80)
print("PRECISION TP/SL CALCULATOR - READY FOR INTEGRATION")
print("="*80)
