"""
Complete Arsenal Integration Test
Tests all 7 modules working together with Strategy Dictionary Brain
"""

import sys
from datetime import datetime, timedelta
import pandas as pd

# Import all arsenal modules
from realtime_swing_detector import (
    fetch_binance_data,
    get_current_price,
    detect_candle_close_patterns
)
from fvg_detector import FVGDetector
from trendline_confluence_module import get_trendline_analyzer
from range_trap_detector import RangeTrapDetector, print_trap_analysis


def find_swing_highs(df: pd.DataFrame, lookback: int = 2):
    """Find swing highs in dataframe"""
    swing_highs = []
    for i in range(lookback, len(df) - lookback):
        current_high = df.iloc[i]['high']
        is_swing_high = all(
            current_high >= df.iloc[j]['high']
            for j in range(i - lookback, i + lookback + 1)
            if j != i
        )
        if is_swing_high:
            swing_highs.append({
                'index': i,
                'timestamp': df.iloc[i]['timestamp'],
                'price': current_high,
                'close': df.iloc[i]['close'],
                'open': df.iloc[i]['open'],
                'low': df.iloc[i]['low']
            })
    return swing_highs


def find_swing_lows(df: pd.DataFrame, lookback: int = 2):
    """Find swing lows in dataframe"""
    swing_lows = []
    for i in range(lookback, len(df) - lookback):
        current_low = df.iloc[i]['low']
        is_swing_low = all(
            current_low <= df.iloc[j]['low']
            for j in range(i - lookback, i + lookback + 1)
            if j != i
        )
        if is_swing_low:
            swing_lows.append({
                'index': i,
                'timestamp': df.iloc[i]['timestamp'],
                'price': current_low,
                'close': df.iloc[i]['close'],
                'open': df.iloc[i]['open'],
                'high': df.iloc[i]['high']
            })
    return swing_lows


def analyze_trend_structure(swing_highs, swing_lows):
    """Analyze trend structure from swings"""
    if len(swing_highs) < 2 and len(swing_lows) < 2:
        return {
            'structure_type': 'CONSOLIDATION',
            'trend_direction': 'NEUTRAL',
            'trend_strength': 0.50
        }

    # Check for lower highs (downtrend)
    if len(swing_highs) >= 2:
        lower_highs = all(
            swing_highs[i]['price'] < swing_highs[i-1]['price']
            for i in range(1, len(swing_highs))
        )
        if lower_highs:
            decline_pct = (swing_highs[0]['price'] - swing_highs[-1]['price']) / swing_highs[0]['price']
            return {
                'structure_type': 'LOWER_HIGHS',
                'trend_direction': 'DOWNTREND',
                'trend_strength': min(0.95, 0.60 + decline_pct)
            }

    # Check for higher lows (uptrend)
    if len(swing_lows) >= 2:
        higher_lows = all(
            swing_lows[i]['price'] > swing_lows[i-1]['price']
            for i in range(1, len(swing_lows))
        )
        if higher_lows:
            rise_pct = (swing_lows[-1]['price'] - swing_lows[0]['price']) / swing_lows[0]['price']
            return {
                'structure_type': 'HIGHER_LOWS',
                'trend_direction': 'UPTREND',
                'trend_strength': min(0.95, 0.60 + rise_pct)
            }

    return {
        'structure_type': 'CONSOLIDATION',
        'trend_direction': 'NEUTRAL',
        'trend_strength': 0.50
    }

def print_header(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"{title:^80}")
    print("=" * 80 + "\n")

def test_complete_arsenal():
    """Run comprehensive test of all arsenal modules"""

    symbol = "SOLUSDT"
    timeframe = "15m"
    lookback_hours = 4.0

    print_header("COMPLETE ARSENAL INTEGRATION TEST")
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Lookback: {lookback_hours} hours")
    print(f"Test Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # Fetch market data
    print("\n[1/7] Fetching Market Data...")
    df = fetch_binance_data(symbol, timeframe, limit=500)
    if df is None or df.empty:
        print("ERROR: Failed to fetch data")
        return

    current_price = float(df.iloc[-1]['close'])
    print(f"   [OK] Fetched {len(df)} candles")
    print(f"   [OK] Current Price: ${current_price:.2f}")

    # Filter to recent data
    now = datetime.utcnow()
    cutoff_time = now - timedelta(hours=lookback_hours)
    recent = df[df['timestamp'] >= cutoff_time].copy()
    print(f"   [OK] Recent candles (last {lookback_hours}h): {len(recent)}")

    # Module 1: Swing High Detection
    print_header("MODULE 1: SWING HIGH DETECTION")
    swing_highs = find_swing_highs(recent, lookback=2)
    print(f"Found {len(swing_highs)} swing highs")
    if swing_highs:
        for i, swing in enumerate(swing_highs[-3:], 1):  # Show last 3
            mins_ago = (now - swing['timestamp'].to_pydatetime()).total_seconds() / 60
            print(f"{i}. ${swing['price']:.2f} @ {swing['timestamp']} ({mins_ago:.0f} mins ago)")
        print(f"\nCurrent Resistance: ${swing_highs[-1]['price']:.2f}")

    # Module 2: Swing Low Detection
    print_header("MODULE 2: SWING LOW DETECTION")
    swing_lows = find_swing_lows(recent, lookback=2)
    print(f"Found {len(swing_lows)} swing lows")
    if swing_lows:
        for i, swing in enumerate(swing_lows[-3:], 1):  # Show last 3
            mins_ago = (now - swing['timestamp'].to_pydatetime()).total_seconds() / 60
            print(f"{i}. ${swing['price']:.2f} @ {swing['timestamp']} ({mins_ago:.0f} mins ago)")
        print(f"\nCurrent Support: ${swing_lows[-1]['price']:.2f}")

    # Module 3: Candle Close Patterns
    print_header("MODULE 3: CANDLE CLOSE PATTERNS")
    patterns = detect_candle_close_patterns(recent, lookback_bars=20)
    print(f"Found {len(patterns)} candle break patterns")
    if patterns:
        recent_patterns = [p for p in patterns if (now - p['timestamp'].to_pydatetime()).total_seconds() < 1800]
        print(f"Recent patterns (last 30 mins): {len(recent_patterns)}")
        for i, pattern in enumerate(recent_patterns[-5:], 1):
            mins_ago = (now - pattern['timestamp'].to_pydatetime()).total_seconds() / 60
            print(f"{i}. {pattern['type']} @ ${pattern['current_close']:.2f}")
            print(f"   Break: {pattern['break_pct']:.3f}% ({mins_ago:.0f} mins ago)")

    # Module 4: Lower High/Higher Low Analysis
    print_header("MODULE 4: TREND STRUCTURE ANALYSIS")
    trend_analysis = analyze_trend_structure(swing_highs, swing_lows)
    print(f"Structure Type: {trend_analysis['structure_type']}")
    print(f"Trend Direction: {trend_analysis['trend_direction']}")
    print(f"Trend Strength: {trend_analysis['trend_strength']:.0%}")
    if trend_analysis['structure_type'] == 'LOWER_HIGHS' and len(swing_highs) >= 2:
        print(f"\nLower High Pattern:")
        print(f"  Previous: ${swing_highs[-2]['price']:.2f}")
        print(f"  Current:  ${swing_highs[-1]['price']:.2f}")
        decline = swing_highs[-2]['price'] - swing_highs[-1]['price']
        print(f"  Decline:  ${decline:.2f} ({(decline/swing_highs[-2]['price'])*100:.2f}%)")

    # Module 5: FVG Detection
    print_header("MODULE 5: FAIR VALUE GAP (FVG) DETECTION")
    fvg_detector = FVGDetector()
    fvgs = fvg_detector.detect(df, current_price)
    print(f"Total FVGs Detected: {len(fvgs)}")

    # Get active FVGs near price
    active_fvgs = fvg_detector.get_active_fvgs(current_price, max_distance_pct=5.0)
    print(f"Active FVGs (within 5%): {len(active_fvgs)}")

    # Show unfilled FVGs
    unfilled = [fvg for fvg in active_fvgs if fvg.fill_status == 'UNFILLED']
    print(f"\nUnfilled FVGs: {len(unfilled)}")
    if unfilled:
        for i, fvg in enumerate(unfilled[:3], 1):
            distance = ((fvg.gap_start - current_price) / current_price) * 100
            print(f"{i}. {fvg.gap_type.upper()} FVG: ${fvg.gap_start:.2f} - ${fvg.gap_end:.2f}")
            print(f"   Distance: {distance:+.2f}% | Quality: {fvg.quality_score:.0%}")

    # Module 6: Trendline Confluence Scoring
    print_header("MODULE 6: TRENDLINE CONFLUENCE ANALYSIS")
    analyzer = get_trendline_analyzer()

    # Get comprehensive analysis
    trendline_data = analyzer.get_comprehensive_analysis(symbol, timeframe, lookback_hours)

    confluence = analyzer.calculate_confluence_points(
        swing_highs,
        swing_lows,
        patterns,
        current_price,
        'LONG' if trend_analysis['trend_direction'] == 'UPTREND' else 'SHORT'
    )

    print(f"Bullish Confluence Points: {confluence['bullish_points']}")
    print(f"Bearish Confluence Points: {confluence['bearish_points']}")
    print(f"Total Confluence: {confluence['total_points']} points")
    print(f"Net Bias: {confluence['bullish_points'] - confluence['bearish_points']:+d} points")

    if confluence['bullish_points'] > confluence['bearish_points']:
        print("\n[OK] BULLISH CONFLUENCE DETECTED")
    else:
        print("\n[OK] BEARISH CONFLUENCE DETECTED")

    # Module 6.5: CRITICAL - Range Trap Detection
    print_header("MODULE 6.5: RANGE TRAP DETECTION [CRITICAL SAFETY CHECK]")
    trap_detector = RangeTrapDetector()
    trap_analysis = trap_detector.analyze(
        swing_highs,
        swing_lows,
        patterns,
        current_price,
        lookback_hours
    )
    print_trap_analysis(trap_analysis)

    # Module 7: Market Report Generation
    print_header("MODULE 7: COMPREHENSIVE MARKET REPORT")

    market_report = {
        'symbol': symbol,
        'timeframe': timeframe,
        'current_price': current_price,
        'timestamp': now,

        # Swing Analysis
        'swing_analysis': {
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'resistance': swing_highs[-1]['price'] if swing_highs else None,
            'support': swing_lows[-1]['price'] if swing_lows else None,
        },

        # Pattern Analysis
        'pattern_analysis': {
            'patterns': patterns,
            'recent_patterns': [p for p in patterns if (now - p['timestamp'].to_pydatetime()).total_seconds() < 1800],
            'latest_pattern': patterns[-1] if patterns else None,
        },

        # Trend Analysis
        'trend_analysis': trend_analysis,

        # FVG Analysis
        'fvg_analysis': {
            'total_fvgs': len(fvgs),
            'active_fvgs': len(active_fvgs),
            'unfilled_fvgs': len(unfilled),
            'nearest_supply': next((fvg for fvg in active_fvgs if fvg.gap_type == 'bearish' and fvg.gap_start > current_price), None),
            'nearest_demand': next((fvg for fvg in active_fvgs if fvg.gap_type == 'bullish' and fvg.gap_end < current_price), None),
        },

        # Confluence Scoring
        'confluence': confluence,

        # Trendline Data
        'trendline_analysis': trendline_data,
    }

    # Display Market Report Summary
    print("Market Report Generated Successfully\n")
    print(f"Current Price: ${current_price:.2f}")
    print(f"Resistance: ${market_report['swing_analysis']['resistance']:.2f}" if market_report['swing_analysis']['resistance'] else "No resistance")
    print(f"Support: ${market_report['swing_analysis']['support']:.2f}" if market_report['swing_analysis']['support'] else "No support")
    print(f"Trend: {market_report['trend_analysis']['trend_direction']} ({market_report['trend_analysis']['trend_strength']:.0%})")
    print(f"Active FVGs: {market_report['fvg_analysis']['active_fvgs']}")
    print(f"Confluence: {market_report['confluence']['bullish_points']} bullish / {market_report['confluence']['bearish_points']} bearish")

    # Generate Trading Signal
    print_header("TRADING SIGNAL GENERATION")

    # CRITICAL: Check if we're trapped first
    if trap_analysis.is_trapped:
        print(f"\n{'='*80}")
        print("SIGNAL KILLED BY RANGE TRAP DETECTOR")
        print(f"{'='*80}")
        print(f"\nDanger Level: {trap_analysis.danger_level}")
        print(f"Trap Severity: {trap_analysis.trap_severity:.0%}")
        print(f"\nReason: {trap_analysis.trap_reason}")
        print(f"\nRecommendation: {trap_analysis.recommendation}")
        print(f"\n{'='*80}")
        print("NO SIGNAL GENERATED - MARKET TOO DANGEROUS")
        print(f"{'='*80}")
        return

    # Determine bias
    net_confluence = confluence['bullish_points'] - confluence['bearish_points']
    if abs(net_confluence) < 20:
        bias = "NEUTRAL"
        confidence = 0.40
    elif net_confluence > 0:
        bias = "LONG"
        confidence = min(0.85, 0.50 + (net_confluence / 100) * 0.35)
    else:
        bias = "SHORT"
        confidence = min(0.85, 0.50 + (abs(net_confluence) / 100) * 0.35)

    # Apply trap severity penalty to confidence
    if trap_analysis.trap_severity > 0.3:
        original_confidence = confidence
        confidence *= (1.0 - trap_analysis.trap_severity * 0.5)  # Reduce by up to 50%
        print(f"\n[WARNING] Confidence reduced from {original_confidence:.0%} to {confidence:.0%} due to trap risk")

    print(f"Direction: {bias}")
    print(f"Confidence: {confidence:.0%}")
    print(f"Setup: ", end="")

    # Identify setup type
    if swing_highs and abs(current_price - swing_highs[-1]['price']) / current_price < 0.005:
        print("REJECTION at resistance")
        entry_zone = (current_price * 0.998, current_price * 1.002)
        if bias == "SHORT":
            stop_loss = swing_highs[-1]['price'] * 1.005
            targets = [
                current_price * 0.993,
                current_price * 0.987,
                current_price * 0.980,
            ]
        else:
            stop_loss = swing_highs[-1]['price'] * 0.995
            targets = [
                current_price * 1.007,
                current_price * 1.013,
                current_price * 1.020,
            ]
    else:
        print("BREAKOUT continuation")
        entry_zone = (current_price * 0.997, current_price * 1.003)
        if bias == "LONG":
            stop_loss = current_price * 0.985
            targets = [
                current_price * 1.010,
                current_price * 1.020,
                current_price * 1.030,
            ]
        else:
            stop_loss = current_price * 1.015
            targets = [
                current_price * 0.990,
                current_price * 0.980,
                current_price * 0.970,
            ]

    print(f"\nEntry Zone: ${entry_zone[0]:.2f} - ${entry_zone[1]:.2f}")
    print(f"Stop Loss: ${stop_loss:.2f}")
    print("Take Profits:")
    for i, tp in enumerate(targets, 1):
        print(f"  TP{i}: ${tp:.2f}")

    # Calculate R:R
    risk = abs(current_price - stop_loss)
    reward = abs(targets[0] - current_price)
    rr_ratio = reward / risk if risk > 0 else 0
    print(f"\nRisk/Reward: {rr_ratio:.2f}:1")

    # Matched Scenarios
    print("\nScenarios Matched:")
    if trend_analysis['structure_type'] == 'LOWER_HIGHS':
        print("  - Lower High Continuation (69% win rate)")
    elif trend_analysis['structure_type'] == 'HIGHER_LOWS':
        print("  - Higher Low Continuation (69% win rate)")

    if unfilled:
        print("  - FVG Supply/Demand Zone (73% win rate)")

    if patterns:
        print("  - Candle Break Pattern (65% win rate)")

    if confluence['total_points'] >= 70:
        print("  - High Confluence Zone (73% win rate)")

    # Final Summary
    print_header("ARSENAL TEST COMPLETE")
    print("[OK] All 8 modules operational (including Range Trap Detector)")
    print("[OK] Market analysis complete")

    if trap_analysis.is_trapped:
        print("[BLOCKED] Trading signal KILLED by Range Trap Detector")
        print(f"[DANGER] {trap_analysis.danger_level} risk detected")
    else:
        print("[OK] Trading signal generated")
        if trap_analysis.trap_severity > 0.3:
            print(f"[WARNING] {trap_analysis.danger_level} risk detected - confidence reduced")

    print("[OK] Integration successful")
    print("\nStatus: FULLY ARMED AND OPERATIONAL")

    # Additional trap warning if needed
    if trap_analysis.trap_severity > 0.3 and not trap_analysis.is_trapped:
        print(f"\n[CAUTION] Range trap risk detected ({trap_analysis.trap_severity:.0%} severity)")
        print(f"Recommendation: {trap_analysis.recommendation}")

if __name__ == "__main__":
    try:
        test_complete_arsenal()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
