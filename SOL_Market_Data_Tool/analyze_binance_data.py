#!/usr/bin/env python3
"""
Simple Binance Historical Data Analyzer
Analyzes your CSV files and compares with recent 5-hour tracking
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

def load_binance_csv(filepath):
    """Load Binance CSV with proper handling"""
    df = pd.read_csv(filepath, skiprows=1)  # Skip the URL line
    
    # Parse date column
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Ensure numeric columns
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

def analyze_data():
    """Main analysis function"""
    print("="*70)
    print("BINANCE HISTORICAL DATA ANALYSIS FOR SOL")
    print("="*70)
    print()
    
    # Your recent 5-hour tracking results
    recent_tracking = {
        'duration_hours': 5.33,
        'start_price': 176.41,
        'end_price': 180.16,
        'price_change': 3.75,
        'price_change_pct': 2.13,
        'buy_sell_ratio': 1.472,
        'volatility': 0.88,
        'low': 175.88,
        'high': 181.69,
        'best_hour_utc': 4,
        'peak_volume': 7238
    }
    
    # Load hourly data (most relevant for comparison)
    hourly_file = Path(r"G:\python files\precision9\claude\SOLUSDT_Binance_futures_UM_hour.csv")
    
    if not hourly_file.exists():
        print("Error: SOLUSDT hourly file not found")
        return
    
    print("Loading SOLUSDT hourly data...")
    df = load_binance_csv(hourly_file)
    
    # Sort by date
    df = df.sort_values('Date')
    
    print(f"Loaded {len(df)} hourly records")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
    print()
    
    # Calculate metrics
    df['price_change'] = df['Close'] - df['Open']
    df['price_change_pct'] = (df['price_change'] / df['Open']) * 100
    df['range'] = df['High'] - df['Low']
    df['range_pct'] = (df['range'] / df['Open']) * 100
    df['hour'] = df['Date'].dt.hour
    
    print("="*70)
    print("KEY FINDINGS")
    print("="*70)
    print()
    
    # 1. Overall Statistics
    print("1. OVERALL PRICE STATISTICS:")
    print("-"*40)
    print(f"   Current Price: ${df['Close'].iloc[-1]:.2f}")
    print(f"   Average Price: ${df['Close'].mean():.2f}")
    print(f"   Price Range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")
    print(f"   Total Range: ${df['High'].max() - df['Low'].min():.2f}")
    print()
    
    # 2. Volatility Analysis
    df['returns'] = df['Close'].pct_change()
    hourly_volatility = df['returns'].std() * 100
    
    print("2. VOLATILITY ANALYSIS:")
    print("-"*40)
    print(f"   Historical Hourly Volatility: {hourly_volatility:.2f}%")
    print(f"   Your 5h Tracking Volatility: {recent_tracking['volatility']:.2f}%")
    
    if recent_tracking['volatility'] < hourly_volatility:
        print(f"   -> Your tracking shows LOWER volatility (good for trending)")
    else:
        print(f"   -> Your tracking shows HIGHER volatility (increased risk)")
    print()
    
    # 3. Find similar 5-hour periods
    print("3. SIMILAR 5-HOUR PERIODS IN HISTORY:")
    print("-"*40)
    
    similar_periods = []
    window = 5
    
    for i in range(len(df) - window - 24):
        period = df.iloc[i:i+window]
        period_change = ((period['Close'].iloc[-1] - period['Close'].iloc[0]) / period['Close'].iloc[0]) * 100
        period_range = ((period['High'].max() - period['Low'].min()) / period['Close'].iloc[0]) * 100
        
        # Check if similar to recent tracking (within 50% tolerance)
        if abs(period_change - recent_tracking['price_change_pct']) < 1.0:
            # What happened in next 24 hours?
            next_24h = df.iloc[i+window:min(i+window+24, len(df))]
            if len(next_24h) > 0:
                next_move = ((next_24h['Close'].iloc[-1] - period['Close'].iloc[-1]) / period['Close'].iloc[-1]) * 100
                
                similar_periods.append({
                    'date': period['Date'].iloc[0],
                    'change': period_change,
                    'next_24h': next_move
                })
    
    if similar_periods:
        print(f"   Found {len(similar_periods)} similar periods")
        
        # Calculate statistics
        next_moves = [p['next_24h'] for p in similar_periods]
        avg_next = np.mean(next_moves)
        win_rate = sum(1 for m in next_moves if m > 0) / len(next_moves) * 100
        
        print(f"   Average next 24h move: {avg_next:+.2f}%")
        print(f"   Win rate (positive moves): {win_rate:.1f}%")
        
        # Show recent examples
        print("\n   Recent Examples:")
        for period in similar_periods[-3:]:
            print(f"   - {period['date'].strftime('%Y-%m-%d')}: "
                  f"+{period['change']:.1f}% -> Next 24h: {period['next_24h']:+.1f}%")
    else:
        print("   No similar periods found")
    print()
    
    # 4. Hourly Pattern Analysis
    print("4. HOURLY PATTERN ANALYSIS:")
    print("-"*40)
    
    hourly_stats = df.groupby('hour').agg({
        'price_change_pct': 'mean',
        'Volume': 'mean',
        'range_pct': 'mean'
    })
    
    # Best hours for positive moves
    best_hours = hourly_stats.nlargest(5, 'price_change_pct')
    
    print("   Best Hours for Gains (UTC):")
    for hour in best_hours.index[:3]:
        avg_gain = best_hours.loc[hour, 'price_change_pct']
        avg_vol = best_hours.loc[hour, 'Volume']
        print(f"   - {hour:02d}:00: Avg gain {avg_gain:+.3f}%, Volume {avg_vol:,.0f}")
    
    # Check if your best hour matches
    if recent_tracking['best_hour_utc'] in hourly_stats.index:
        hour_stats = hourly_stats.loc[recent_tracking['best_hour_utc']]
        print(f"\n   Your Best Hour ({recent_tracking['best_hour_utc']:02d}:00 UTC):")
        print(f"   - Historical avg gain: {hour_stats['price_change_pct']:+.3f}%")
        print(f"   - Matches historical pattern: {'YES' if recent_tracking['best_hour_utc'] in best_hours.index[:3] else 'NO'}")
    print()
    
    # 5. Current Market Context
    print("5. CURRENT MARKET CONTEXT:")
    print("-"*40)
    
    recent_price = df['Close'].iloc[-1]
    recent_30d = df.tail(30*24) if len(df) > 30*24 else df  # Last 30 days
    
    # Support and resistance
    recent_high = recent_30d['High'].max()
    recent_low = recent_30d['Low'].min()
    position_in_range = (recent_price - recent_low) / (recent_high - recent_low) * 100
    
    print(f"   Current Price: ${recent_price:.2f}")
    print(f"   30-day Range: ${recent_low:.2f} - ${recent_high:.2f}")
    print(f"   Position in Range: {position_in_range:.1f}%")
    
    if position_in_range > 70:
        print("   -> Near resistance, watch for breakout or reversal")
    elif position_in_range < 30:
        print("   -> Near support, potential bounce area")
    else:
        print("   -> Middle of range, follow momentum")
    print()
    
    # 6. Trading Recommendations
    print("="*70)
    print("TRADING RECOMMENDATIONS BASED ON ANALYSIS")
    print("="*70)
    print()
    
    print("INSIGHTS FROM YOUR 5-HOUR TRACKING:")
    print("-"*40)
    print(f"[OK] Strong bullish move: +{recent_tracking['price_change_pct']:.2f}% in 5 hours")
    print(f"[OK] Buy/Sell ratio of {recent_tracking['buy_sell_ratio']:.2f} shows buyer dominance")
    print(f"[OK] Low volatility ({recent_tracking['volatility']:.2f}%) indicates trending market")
    print()
    
    print("HISTORICAL CONTEXT:")
    print("-"*40)
    
    # Calculate percentile of recent performance
    all_5h_changes = []
    for i in range(len(df) - 5):
        change = ((df['Close'].iloc[i+5] - df['Close'].iloc[i]) / df['Close'].iloc[i]) * 100
        all_5h_changes.append(change)
    
    if all_5h_changes:
        percentile = sum(1 for c in all_5h_changes if c < recent_tracking['price_change_pct']) / len(all_5h_changes) * 100
        print(f"Your +{recent_tracking['price_change_pct']:.2f}% move is in the {percentile:.0f}th percentile")
        
        if percentile > 80:
            print("-> This is an EXCEPTIONALLY strong move")
            print("-> Consider taking partial profits")
            print("-> Watch for potential exhaustion/reversal")
        elif percentile > 60:
            print("-> Above average performance")
            print("-> Momentum likely to continue short-term")
            print("-> Use trailing stops to protect gains")
        else:
            print("-> Normal market movement")
            print("-> Follow standard trading plan")
    print()
    
    print("ACTION ITEMS:")
    print("-"*40)
    print("1. ENTRY STRATEGY:")
    print(f"   - Best hours: {', '.join([f'{h:02d}:00' for h in best_hours.index[:3]])} UTC")
    print(f"   - Wait for pullbacks to ${recent_price * 0.99:.2f} (1% below current)")
    print(f"   - Set stops at ${recent_price * 0.97:.2f} (3% risk)")
    print()
    
    print("2. POSITION MANAGEMENT:")
    volatility_position_size = 1 / (hourly_volatility * 2)
    print(f"   - Recommended position size: {volatility_position_size:.2f}x base")
    print(f"   - Take profit levels: ${recent_price * 1.02:.2f}, ${recent_price * 1.05:.2f}")
    print(f"   - Maximum leverage: {min(10, 1/hourly_volatility):.1f}x")
    print()
    
    print("3. RISK WARNINGS:")
    print("   [WARNING] CVD data shows anomaly (103,458) - likely calculation error")
    print("   [WARNING] After strong moves like yours, expect consolidation")
    print("   [WARNING] Watch for volume confirmation on any breakout")
    print()
    
    print("4. NEXT 24H OUTLOOK:")
    if similar_periods and avg_next > 0:
        print(f"   - Historical precedent suggests {avg_next:+.2f}% move")
        print(f"   - {win_rate:.0f}% probability of positive continuation")
    else:
        print("   - Limited historical precedent for prediction")
    
    if position_in_range > 70:
        print("   - Near resistance, expect potential pullback")
    elif position_in_range < 30:
        print("   - Near support, good risk/reward for longs")
    
    print()
    print("="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)

if __name__ == "__main__":
    analyze_data()