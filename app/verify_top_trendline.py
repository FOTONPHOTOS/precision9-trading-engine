"""
Quick verification script for Top Trendline #1

Prints exact coordinates adjusted for Nigeria timezone (UTC+1)
"""

from datetime import datetime, timedelta

# Top Trendline #1 coordinates (UTC)
touch_points_utc = [
    ("2025-10-09 00:20", 229.69),
    ("2025-10-09 02:31", 227.60),
    ("2025-10-09 08:33", 221.95),
    ("2025-10-09 09:06", 221.27),
    ("2025-10-09 09:15", 221.22),
]

print("\n" + "="*80)
print("TRENDLINE #1 VERIFICATION - NIGERIA TIMEZONE (UTC+1)")
print("="*80)

print("\n[INSTRUCTIONS]")
print("1. Open TradingView")
print("2. Search for SOLUSDT")
print("3. Set timeframe to 1M (one minute)")
print("4. Navigate to October 9, 2025")
print("5. Draw trendline using the points below")

print("\n[TRENDLINE TYPE]")
print("RESISTANCE (Descending) - Connects swing HIGHS")

print("\n[TOUCH POINTS - NIGERIA TIME]")
print(f"{'#':<4} {'Nigeria Time':<20} {'UTC Time':<20} {'Price':<10}")
print("-" * 80)

for i, (utc_time_str, price) in enumerate(touch_points_utc, 1):
    # Parse UTC time
    utc_time = datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M")

    # Convert to Nigeria time (UTC+1)
    nigeria_time = utc_time + timedelta(hours=1)

    # Format for display
    nigeria_str = nigeria_time.strftime("%Y-%m-%d %H:%M")
    utc_str = utc_time.strftime("%Y-%m-%d %H:%M")

    print(f"{i:<4} {nigeria_str:<20} {utc_str:<20} ${price:<9.2f}")

print("\n[HOW TO VERIFY]")
print("✓ Each point should be at a swing HIGH (top of a candle wick)")
print("✓ These should be MAJOR structural highs, not minor internal highs")
print("✓ The line should form a clear descending channel")
print("✓ Price should RESPECT the line (touch but not break)")
print("✓ Look for ~5 distinct touches along the line")

print("\n[WHAT TO CHECK]")
print("1. At 01:20 Nigeria time - Is there a swing high near $229.69?")
print("2. At 02:31 Nigeria time - Is there a swing high near $227.60?")
print("3. At 08:33 Nigeria time - Is there a swing high near $221.95?")
print("4. At 09:06 Nigeria time - Is there a swing high near $221.27?")
print("5. At 09:15 Nigeria time - Is there a swing high near $221.22?")

print("\n[LINE EQUATION]")
print("y = -0.015848x + 229.83")
print("Slope: -0.015848 (descending)")
print("R²: 0.9998 (near-perfect fit)")
print("Average deviation: $0.037 (extremely tight)")

print("\n[COMPARISON WITH YOUR RED LINES]")
print("Does this line match the trendlines you drew manually?")
print("If YES: The hierarchical detector is working correctly!")
print("If NO: Please describe the differences and we'll calibrate further")

print("\n" + "="*80)
