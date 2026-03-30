"""
Test Liquidity Sweep Detection on Current Market
"""

from realtime_swing_detector import fetch_binance_data
from test_complete_arsenal import find_swing_highs, find_swing_lows
from liquidity_sweep_detector import LiquiditySweepDetector, print_liquidity_analysis
from datetime import datetime, timedelta

print("="*80)
print("LIQUIDITY SWEEP DETECTION - HORUS PROTECTION TEST")
print("="*80)

# Fetch data
symbol = "SOLUSDT"
timeframe = "5m"  # Use 5m to catch more sweeps
limit = 200

print(f"\nFetching {symbol} {timeframe} data...")
df = fetch_binance_data(symbol, timeframe, limit)
current_price = float(df.iloc[-1]['close'])

print(f"Current Price: ${current_price:.2f}")

# Filter to recent data (last 6 hours)
now = datetime.utcnow()
cutoff = now - timedelta(hours=6)
recent = df[df['timestamp'] >= cutoff].copy()

print(f"Analyzing last 6 hours ({len(recent)} candles)...")

# Find swings
swing_highs = find_swing_highs(recent, lookback=2)
swing_lows = find_swing_lows(recent, lookback=2)

print(f"Found {len(swing_highs)} swing highs, {len(swing_lows)} swing lows")

# Detect liquidity sweeps
detector = LiquiditySweepDetector()

print("\nDetecting liquidity sweeps...")
sweeps = detector.detect_sweeps(recent, swing_highs, swing_lows)

print(f"Detected {len(sweeps)} liquidity sweeps")

# Map liquidity pools
print("\nMapping liquidity pools (stop clusters)...")
pools = detector.map_liquidity_pools(swing_highs, swing_lows, sweeps, current_price)

print(f"Identified {len(pools)} liquidity pools")

# Check for stop hunt mode
print("\nChecking for stop hunt mode...")
warning = detector.detect_stop_hunt_mode(sweeps, pools, lookback_hours=6.0)

# Print complete analysis
print_liquidity_analysis(sweeps, pools, warning, current_price)

# Summary
print("\n" + "="*80)
print("HORUS PROTECTION SUMMARY")
print("="*80)

if warning.is_stop_hunt_mode:
    print("\n[CRITICAL] STOP HUNT MODE ACTIVE!")
    print("This is the condition that killed Horus.")
    print("Recommendation: DO NOT TRADE until market exits stop hunt mode")
    print(f"\nSeverity: {warning.severity:.0%}")
elif warning.severity > 0.3:
    print("\n[WARNING] Elevated stop hunt activity")
    print("Use caution - place stops beyond liquidity pools")
    print(f"Severity: {warning.severity:.0%}")
else:
    print("\n[OK] Normal market conditions")
    print("Standard stop placement acceptable")

# Show safe stop zones
print("\n[SAFE STOP PLACEMENT]")
if pools:
    print("If trading LONG, place stops BELOW these levels:")
    support_pools = [p for p in pools if p.type == 'support'][:3]
    for pool in support_pools:
        print(f"  - Liquidity at ${pool.level:.2f}")
        print(f"    SAFE ZONE: ${pool.safe_stop_zone[0]:.2f} - ${pool.safe_stop_zone[1]:.2f}")

    print("\nIf trading SHORT, place stops ABOVE these levels:")
    resistance_pools = [p for p in pools if p.type == 'resistance'][:3]
    for pool in resistance_pools:
        print(f"  - Liquidity at ${pool.level:.2f}")
        print(f"    SAFE ZONE: ${pool.safe_stop_zone[0]:.2f} - ${pool.safe_stop_zone[1]:.2f}")

print("\n" + "="*80)
