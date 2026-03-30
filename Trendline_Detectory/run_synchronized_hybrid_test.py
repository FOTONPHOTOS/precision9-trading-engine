"""
SYNCHRONIZED HYBRID VALIDATION TEST
Runs Arsenal and Horus collection at SAME TIME for exact comparison
Focus: Horus (Liquidity/Flow) vs Arsenal (Structure/Trendlines)
"""

import asyncio
import time
from datetime import datetime
import json

# Collectors
from horus_data_collector import HorusDataCollector
from arsenal_data_collector import ArsenalDataCollector

# Arsenal components
from realtime_swing_detector import fetch_binance_data, detect_candle_close_patterns
from fvg_detector import FVGDetector
from order_block_detector import OrderBlockDetector
from liquidity_sweep_detector import LiquiditySweepDetector
from range_trap_detector import RangeTrapDetector
from trendline_confluence_module import get_trendline_analyzer
from test_ultimate_arsenal import find_swing_highs, find_swing_lows, analyze_trend_structure, MarketIntelligence
from intelligent_strategy_brain import IntelligentStrategyBrain

from datetime import timedelta


async def run_synchronized_test():
    print("\n" + "="*100)
    print("SYNCHRONIZED HYBRID VALIDATION TEST")
    print("="*100)
    print("\nCollecting BOTH systems at SAME TIME for exact comparison")
    print("Focus: Horus (Liquidity/Flow) vs Arsenal (Structure/Trendlines)\n")

    # Initialize collectors
    horus_collector = HorusDataCollector()
    arsenal_collector = ArsenalDataCollector()
    arsenal_collector.start_collection()

    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Start Horus collection in background
    print("[STEP 1/3] Starting Horus data collection (20 seconds)...")
    horus_task = asyncio.create_task(horus_collector.collect_data(duration_seconds=20))

    # Small delay to ensure Horus starts
    await asyncio.sleep(2)

    # Run Arsenal analysis NOW (same time as Horus)
    print("[STEP 2/3] Running Arsenal analysis NOW (synchronized with Horus)...\n")

    # Fetch market data
    symbol = "SOLUSDT"
    timeframe = "5m"
    lookback_hours = 4.0

    df = fetch_binance_data(symbol, timeframe, 200)
    current_price = float(df.iloc[-1]['close'])

    # Time filter
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=lookback_hours)
    recent = df[df['timestamp'] >= cutoff].copy()

    # ARSENAL STRUCTURAL ANALYSIS
    print("="*100)
    print("ARSENAL STRUCTURAL ANALYSIS (Trendlines + Ranging System)")
    print("="*100)

    # 1. Swing Structure (Multi-timeframe detection)
    print("\n[1/7] Multi-Timeframe Swing Detection...")
    swing_highs = find_swing_highs(recent, lookback=2)
    swing_lows = find_swing_lows(recent, lookback=2)
    print(f"  Swing Highs: {len(swing_highs)} detected")
    print(f"  Swing Lows: {len(swing_lows)} detected")

    # 2. Trend Analysis
    print("\n[2/7] Trend Structure Analysis...")
    trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
    print(f"  Trend: {trend_analysis['trend_direction'].upper()}")
    print(f"  Strength: {trend_analysis['trend_strength']:.0%}")
    print(f"  Structure Type: {trend_analysis['structure_type']}")

    # 3. Trendline Detection (Geometric algorithms)
    print("\n[3/7] Trendline Detection (Geometric Collinearity)...")
    analyzer = get_trendline_analyzer()
    trendline_data = analyzer.get_comprehensive_analysis(symbol, timeframe, lookback_hours)

    if trendline_data.get('success'):
        swing_info = trendline_data['swing_analysis']
        pattern_info = trendline_data['pattern_analysis']
        confluence = trendline_data['confluence_points']

        print(f"  Resistance: ${swing_info['most_recent_resistance']:.2f} ({swing_info['resistance_distance_pct']:+.2f}%)")
        print(f"  Support: ${swing_info['most_recent_support']:.2f} ({swing_info['support_distance_pct']:+.2f}%)")
        print(f"  Trendline Quality: {trendline_data['trend_analysis']['trend_strength']:.0%}")
        print(f"  Confluence Score: {confluence['total_points']} points")
    else:
        print("  Trendline analysis unavailable")
        confluence = {'bullish_points': 0, 'bearish_points': 0, 'total_points': 0}

    # 4. Ranging System Detection
    print("\n[4/7] Ranging Detection System...")
    trap_detector = RangeTrapDetector()
    patterns = detect_candle_close_patterns(recent, lookback_bars=20)
    trap_analysis = trap_detector.analyze(swing_highs, swing_lows, patterns, current_price, lookback_hours)

    print(f"  Range Detected: {'YES' if trap_analysis.is_trapped else 'NO'}")
    print(f"  Range Severity: {trap_analysis.trap_severity:.0%}")
    print(f"  Danger Level: {trap_analysis.danger_level}")
    if hasattr(trap_analysis, 'range_size_pct'):
        print(f"  Range Size: {trap_analysis.range_size_pct:.2f}%")

    # 5. Smart Money Concepts
    print("\n[5/7] Smart Money Concepts (FVGs + OBs)...")
    fvg_detector = FVGDetector()
    ob_detector = OrderBlockDetector()

    fvgs = fvg_detector.detect(df, current_price)
    active_fvgs = fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)

    obs = ob_detector.detect(df, current_price)
    active_obs = ob_detector.get_active_order_blocks(obs, current_price, max_distance_pct=3.0)

    print(f"  Fair Value Gaps: {len(fvgs)} total ({len(active_fvgs)} active)")
    print(f"  Order Blocks: {len(obs)} total ({len(active_obs)} active)")

    # 6. Liquidity Analysis
    print("\n[6/7] Liquidity Sweep Detection...")
    liquidity_detector = LiquiditySweepDetector()
    sweeps = liquidity_detector.detect_sweeps(recent, swing_highs, swing_lows)
    pools = liquidity_detector.map_liquidity_pools(swing_highs, swing_lows, sweeps, current_price)
    stop_hunt = liquidity_detector.detect_stop_hunt_mode(sweeps, pools, lookback_hours)

    print(f"  Liquidity Sweeps: {len(sweeps)} detected")
    print(f"  Liquidity Pools: {len(pools)} mapped")
    print(f"  Stop Hunt Mode: {'ACTIVE' if stop_hunt.is_stop_hunt_mode else 'INACTIVE'} ({stop_hunt.severity:.0%})")

    # 7. Brain Decision
    print("\n[7/7] Intelligent Strategy Brain Analysis...")
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
        stop_hunt_warning=stop_hunt,
        confluence_score=confluence['total_points'],
        timestamp=now
    )

    brain = IntelligentStrategyBrain()
    decision = brain.analyze(market_intel)

    print(f"  Direction: {decision.direction}")
    print(f"  Confidence: {decision.confidence:.0%}")
    print(f"  Signal Strength: {decision.signal_strength}")
    print(f"  Should Trade: {'YES' if decision.should_trade else 'NO'}")

    # Collect Arsenal snapshot
    swing_analysis = {
        'swing_high': swing_highs[0]['price'] if swing_highs else None,
        'swing_low': swing_lows[0]['price'] if swing_lows else None,
        'bars_since_high': len(recent) - swing_highs[0]['index'] if swing_highs else 0,
        'bars_since_low': len(recent) - swing_lows[0]['index'] if swing_lows else 0
    }

    arsenal_snapshot = arsenal_collector.collect_snapshot(
        current_price=current_price,
        current_candle_timestamp=df.iloc[-1]['timestamp'].timestamp(),
        swing_analysis=swing_analysis,
        patterns=patterns,
        fvgs=fvgs,
        order_blocks=obs,
        liquidity_sweeps=sweeps,
        liquidity_pools=pools,
        stop_hunt_warning=stop_hunt,
        range_trap=trap_analysis,
        confluence=confluence,
        brain_decision=decision
    )

    # Wait for Horus to finish
    print("\n" + "="*100)
    print("Waiting for Horus collection to complete...")
    await horus_task

    # Get Horus data
    horus_snapshot = horus_collector.get_latest_snapshot()

    # Export both
    horus_file = f'horus_sync_{timestamp_str}.json'
    arsenal_file = f'arsenal_sync_{timestamp_str}.json'

    horus_collector.export_data(horus_file)
    arsenal_collector.export_data(arsenal_file)

    print("\n" + "="*100)
    print("[STEP 3/3] SYNCHRONIZED DATA COMPARISON")
    print("="*100)

    # HORUS LIQUIDITY/FLOW ANALYSIS
    print("\n" + "="*100)
    print("HORUS (ORDER FLOW & LIQUIDITY)")
    print("="*100)

    if horus_snapshot:
        print(f"\nData Quality:")
        print(f"  Snapshots Collected: {horus_collector.snapshots_received}")
        print(f"  Data Freshness: {horus_snapshot.data_freshness_score:.0%}")
        print(f"  Sync Quality: {horus_snapshot.sync_quality:.0%}")

        print(f"\n[ORDER FLOW]")
        print(f"  CVD (Cumulative Volume Delta): {horus_snapshot.cvd:.2f}")
        print(f"  Delta: {horus_snapshot.delta:.2f}")
        print(f"  Liquidity Score: {horus_snapshot.liquidity_score:.2f}")

        print(f"\n[HEATMAP DATA]")
        print(f"  Point of Control (POC): ${horus_snapshot.point_of_control:.2f}")
        print(f"  Value Area High (VAH): ${horus_snapshot.value_area_high:.2f}")
        print(f"  Value Area Low (VAL): ${horus_snapshot.value_area_low:.2f}")
        print(f"  Liquidity Zones: {len(horus_snapshot.liquidity_zones)}")

        if horus_snapshot.liquidity_zones:
            print(f"\n  Top Liquidity Zones:")
            for i, zone in enumerate(horus_snapshot.liquidity_zones[:5], 1):
                level = zone.get('level', zone.get('center', 'N/A'))
                strength = zone.get('strength', 0)
                zone_type = zone.get('type', 'unknown')
                print(f"    {i}. ${level} (strength: {strength:.2f}, type: {zone_type})")

        print(f"\n[STRUCTURAL DATA] (HTF Oracle)")
        if horus_snapshot.htf_available:
            print(f"  HTF Structure: AVAILABLE")
            # Note: Detailed OB/FVG data in JSON export
        else:
            print(f"  HTF Structure: NOT AVAILABLE")

    # ARSENAL STRUCTURAL ANALYSIS SUMMARY
    print("\n" + "="*100)
    print("ARSENAL (STRUCTURAL ANALYSIS & TRENDLINES)")
    print("="*100)

    print(f"\nCurrent Price: ${current_price:.2f}")

    print(f"\n[TRENDLINE SYSTEM]")
    if trendline_data.get('success'):
        print(f"  Resistance: ${swing_info['most_recent_resistance']:.2f}")
        print(f"  Support: ${swing_info['most_recent_support']:.2f}")
        print(f"  Structure: {trendline_data['trend_analysis']['structure_type']}")
        print(f"  Quality: {trendline_data['trend_analysis']['trend_strength']:.0%}")

    print(f"\n[RANGING SYSTEM]")
    print(f"  In Range: {'YES' if trap_analysis.is_trapped else 'NO'}")
    print(f"  Severity: {trap_analysis.trap_severity:.0%}")
    print(f"  Safe to Trade: {trap_analysis.danger_level != 'EXTREME'}")

    print(f"\n[SWING STRUCTURE]")
    print(f"  Swing Highs: {len(swing_highs)}")
    print(f"  Swing Lows: {len(swing_lows)}")
    print(f"  Trend: {trend_analysis['trend_direction'].upper()} ({trend_analysis['trend_strength']:.0%})")

    print(f"\n[LIQUIDITY DETECTION]")
    print(f"  Sweeps: {len(sweeps)}")
    print(f"  Pools: {len(pools)} ({len([p for p in pools if p.recent_sweeps == 0])} untapped)")
    print(f"  Stop Hunt: {'ACTIVE' if stop_hunt.is_stop_hunt_mode else 'INACTIVE'}")

    print(f"\n[CONFLUENCE]")
    print(f"  Total Score: {confluence['total_points']} points")
    print(f"  Bullish: {confluence['bullish_points']}")
    print(f"  Bearish: {confluence['bearish_points']}")

    print(f"\n[DECISION]")
    print(f"  Direction: {decision.direction}")
    print(f"  Confidence: {decision.confidence:.0%}")
    print(f"  Should Trade: {'YES' if decision.should_trade else 'NO'}")

    # COMPLEMENTARY ANALYSIS
    print("\n" + "="*100)
    print("COMPLEMENTARY ANALYSIS")
    print("="*100)

    print("\n[LIQUIDITY ALIGNMENT]")
    if horus_snapshot:
        print(f"  Horus POC: ${horus_snapshot.point_of_control:.2f}")
        print(f"  Arsenal Nearest Pool: ${pools[0].level:.2f}" if pools else "  Arsenal: No pools")

        # Check alignment
        if pools and abs(horus_snapshot.point_of_control - pools[0].level) / current_price < 0.01:
            print(f"  [+] ALIGNED within 1%")
        else:
            print(f"  [-] Different focus areas")

    print(f"\n[DIRECTIONAL AGREEMENT]")
    if horus_snapshot:
        horus_bias = "BULLISH" if horus_snapshot.cvd > 0 else "BEARISH" if horus_snapshot.cvd < 0 else "NEUTRAL"
        arsenal_bias = decision.direction

        print(f"  Horus (CVD): {horus_bias} (CVD: {horus_snapshot.cvd:.2f})")
        print(f"  Arsenal (Brain): {arsenal_bias} ({decision.confidence:.0%})")

        if (horus_bias == "BULLISH" and arsenal_bias == "LONG") or (horus_bias == "BEARISH" and arsenal_bias == "SHORT"):
            print(f"  [+] PERFECT ALIGNMENT")
        elif horus_bias == "NEUTRAL" or arsenal_bias == "NEUTRAL":
            print(f"  [~] One system neutral")
        else:
            print(f"  [-] DIVERGENCE - Review carefully")

    print(f"\n[VOLUME vs STRUCTURE]")
    if horus_snapshot:
        print(f"  Horus Delta: {horus_snapshot.delta:.2f}")
        print(f"  Arsenal Trend: {trend_analysis['trend_direction']} ({trend_analysis['trend_strength']:.0%})")

        if (horus_snapshot.delta > 0 and trend_analysis['trend_direction'] == 'uptrend') or \
           (horus_snapshot.delta < 0 and trend_analysis['trend_direction'] == 'downtrend'):
            print(f"  [+] FLOW CONFIRMS STRUCTURE")
        else:
            print(f"  [-] Flow and structure diverging")

    print(f"\n[RANGE vs LIQUIDITY ZONES]")
    if horus_snapshot and trap_analysis.is_trapped:
        zone_count = len(horus_snapshot.liquidity_zones)
        print(f"  Arsenal: Range detected ({trap_analysis.trap_severity:.0%} severity)")
        print(f"  Horus: {zone_count} liquidity zones")
        print(f"  [!] High liquidity + ranging = Possible consolidation breakout setup")

    # FILES
    print("\n" + "="*100)
    print("EXPORTED FILES")
    print("="*100)
    print(f"  Horus Data: {horus_file}")
    print(f"  Arsenal Data: {arsenal_file}")

    # FINAL VERDICT
    print("\n" + "="*100)
    print("VALIDATION VERDICT")
    print("="*100)

    systems_agree = False
    if horus_snapshot:
        horus_bias = "BULLISH" if horus_snapshot.cvd > 0 else "BEARISH"
        arsenal_bias = "BULLISH" if decision.direction == "LONG" else "BEARISH"
        systems_agree = (horus_bias == arsenal_bias)

    if systems_agree:
        print("\n  [EXCELLENT] Both systems AGREE on direction")
        print("  Recommendation: HIGH CONFIDENCE trade setup")
    else:
        print("\n  [CAUTION] Systems show divergence")
        print("  Recommendation: Wait for alignment or reduce position size")

    print("\n" + "="*100)
    print("TEST COMPLETE")
    print("="*100)

    return horus_snapshot, arsenal_snapshot


if __name__ == '__main__':
    print("\n")
    asyncio.run(run_synchronized_test())
    print("\n[DONE] Synchronized hybrid test complete\n")
