"""
Script to update the volatility section in trend_continuation_brain.py

This script will replace the problematic volatility calculation section
with the improved trend-aware logic that prevents missing strong trending moves.
"""
import os

def update_volatility_section():
    file_path = r"G:\python files\precision9\Simulation Environment\Trendline_Detectory\trend_continuation_brain.py"
    
    # Read the current file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # The old volatility section that needs to be replaced
    old_volatility_section = """        # NEW: Volatility warning - adjust for extreme conditions
        # Calculate volatility from recent swing movements since candle_patterns don't contain OHLC data
        if market_intel.swing_highs or market_intel.swing_lows:
            # Calculate average range from recent swings if available
            recent_swings = []

            # Get recent swing highs and lows (up to last 5 of each)
            recent_highs = market_intel.swing_highs[-5:] if len(market_intel.swing_highs) > 0 else []
            recent_lows = market_intel.swing_lows[-5:] if len(market_intel.swing_lows) > 0 else []

            # Calculate ranges from swings
            for swing in recent_highs:
                if 'high' in swing and 'low' in swing:
                    recent_swings.append(swing['high'] - swing['low'])
                elif 'price' in swing and 'low' in swing:
                    recent_swings.append(swing['price'] - swing['low'])
                elif 'high' in swing and 'price' in swing:
                    recent_swings.append(swing['high'] - swing['price'])
                elif 'price' in swing and 'close' in swing:
                    recent_swings.append(abs(swing['price'] - swing['close']))

            for swing in recent_lows:
                if 'high' in swing and 'low' in swing:
                    recent_swings.append(swing['high'] - swing['low'])
                elif 'price' in swing and 'high' in swing:
                    recent_swings.append(swing['high'] - swing['price'])
                elif 'price' in swing and 'close' in swing:
                    recent_swings.append(abs(swing['close'] - swing['price']))

            # If we don't have swings with proper high/low data, try to get from recent candle_patterns (for break distances)
            if not recent_swings and market_intel.candle_patterns and len(market_intel.candle_patterns) >= 3:
                recent_patterns = market_intel.candle_patterns[-5:]
                for p in recent_patterns:
                    if 'break_distance' in p:
                        recent_swings.append(p['break_distance'])
                    elif 'break_pct' in p and market_intel.current_price:
                        # Calculate approximate range from percentage
                        recent_swings.append((p['break_pct'] / 100) * market_intel.current_price)

            if recent_swings:
                avg_range = sum(recent_swings) / len(recent_swings)
                current_price = market_intel.current_price
                if current_price > 0:
                    volatility_pct = (avg_range / current_price) * 100
                    if volatility_pct > 5.0:  # Very high volatility
                        self.reasoning_chain.append(f"  - [VOLATILITY WARNING] Very high volatility ({volatility_pct:.2f}%), reducing confidence for scalp")
                        self.confidence = max(0.10, self.confidence - 0.10)  # Reduce by 10%
                    elif volatility_pct < 0.5:  # Extremely low volatility
                        self.reasoning_chain.append(f"  - [VOLATILITY WARNING] Extremely low volatility ({volatility_pct:.2f}%), reducing confidence")
                        self.confidence = max(0.15, self.confidence - 0.10)  # Reduce by 10%
                    elif volatility_pct < 1.0:  # Low volatility (new threshold)
                        self.reasoning_chain.append(f"  - [VOLATILITY INFO] Low volatility ({volatility_pct:.2f}%), adjusting approach")
                        self.confidence = max(0.15, self.confidence - 0.05)  # Reduce by 5%"""
    
    # The new improved volatility section
    new_volatility_section = """        # NEW: Advanced volatility analysis using trend-aware assessment
        # Instead of simple range calculations, use context-aware volatility assessment
        recent_swings = []
        
        # Get recent swing highs and lows (up to last 5 of each)
        recent_highs = market_intel.swing_highs[-5:] if len(market_intel.swing_highs) > 0 else []
        recent_lows = market_intel.swing_lows[-5:] if len(market_intel.swing_lows) > 0 else []

        # Calculate ranges from swings
        for swing in recent_highs:
            if 'high' in swing and 'low' in swing:
                recent_swings.append(swing['high'] - swing['low'])
            elif 'price' in swing and 'low' in swing:
                recent_swings.append(swing['price'] - swing['low'])
            elif 'high' in swing and 'price' in swing:
                recent_swings.append(swing['high'] - swing['price'])
            elif 'price' in swing and 'close' in swing:
                recent_swings.append(abs(swing['price'] - swing['close']))

        for swing in recent_lows:
            if 'high' in swing and 'low' in swing:
                recent_swings.append(swing['high'] - swing['low'])
            elif 'price' in swing and 'high' in swing:
                recent_swings.append(swing['high'] - swing['price'])
            elif 'price' in swing and 'close' in swing:
                recent_swings.append(abs(swing['close'] - swing['price']))

        # If we don't have swings with proper high/low data, try to get from recent candle_patterns (for break distances)
        if not recent_swings and market_intel.candle_patterns and len(market_intel.candle_patterns) >= 3:
            recent_patterns = market_intel.candle_patterns[-5:]
            for p in recent_patterns:
                if 'break_distance' in p:
                    recent_swings.append(p['break_distance'])
                elif 'break_pct' in p and market_intel.current_price:
                    # Calculate approximate range from percentage
                    recent_swings.append((p['break_pct'] / 100) * market_intel.current_price)

        if recent_swings:
            avg_range = sum(recent_swings) / len(recent_swings)
            current_price = market_intel.current_price
            if current_price > 0:
                volatility_pct = (avg_range / current_price) * 100
                
                # Use trend-aware logic instead of blanket confidence reduction
                if volatility_pct > 5.0:  # Very high volatility
                    self.reasoning_chain.append(f"  - [VOLATILITY ASSESSMENT] Very high volatility ({volatility_pct:.2f}%), checking trend context...")
                    # High volatility might be good or bad depending on trend alignment
                    if market_intel.trend_strength > 0.7:  # Strong trend with high volatility = momentum opportunity
                        self.reasoning_chain.append(f"  - [VOLATILITY OPPORTUNITY] Strong trend ({market_intel.trend_strength:.0%}) with high volatility = good momentum scalp")
                        self.confidence = min(1.0, self.confidence + 0.05)  # Slight boost for momentum opportunity
                    else:  # High volatility without strong trend = dangerous
                        self.reasoning_chain.append(f"  - [VOLATILITY WARNING] High volatility without strong trend = dangerous")
                        self.confidence = max(0.10, self.confidence - 0.10)  # Reduce by 10%
                elif volatility_pct < 0.5:  # Extremely low volatility
                    self.reasoning_chain.append(f"  - [VOLATILITY ASSESSMENT] Extremely low volatility ({volatility_pct:.2f}%), checking trend context...")
                    # CRITICAL FIX: In a strong trend, low volatility often indicates a pullback opportunity, not danger!
                    if market_intel.trend_strength > 0.6 and market_intel.trend_direction in ['uptrend', 'downtrend']:
                        self.reasoning_chain.append(f"  - [VOLATILITY OPPORTUNITY] Strong trend ({market_intel.trend_strength:.0%}) with low volatility = pullback opportunity!")
                        self.confidence = min(1.0, self.confidence + 0.08)  # Boost confidence for pullback opportunity
                    elif market_intel.trend_strength < 0.4:  # Weak trend + low volatility = truly stagnant
                        self.reasoning_chain.append(f"  - [VOLATILITY WARNING] Weak trend with low volatility = ranging/market may be stagnant")
                        self.confidence = max(0.15, self.confidence - 0.05)  # Reduce by 5%
                    else:
                        # Moderate trend + low volatility = either continuation pullback or weakening trend
                        self.reasoning_chain.append(f"  - [VOLATILITY INFO] Moderate trend with low volatility, monitoring for continuation signals")
                        # No adjustment needed, let other factors determine
                elif volatility_pct < 1.0:  # Low volatility (new threshold)
                    self.reasoning_chain.append(f"  - [VOLATILITY ASSESSMENT] Low volatility ({volatility_pct:.2f}%), checking trend context...")
                    # Similar logic for low but not extremely low volatility
                    if market_intel.trend_strength > 0.6 and market_intel.trend_direction in ['uptrend', 'downtrend']:
                        self.reasoning_chain.append(f"  - [VOLATILITY OPPORTUNITY] Strong trend with low volatility = potential pullback/retracement opportunity")
                        self.confidence = min(1.0, self.confidence + 0.05)  # Small boost
                    else:
                        self.reasoning_chain.append(f"  - [VOLATILITY INFO] Low volatility without strong trend, adjusting approach")
                        self.confidence = max(0.15, self.confidence - 0.03)  # Smaller reduction"""
    
    # Replace the old section with the new one
    if old_volatility_section in content:
        updated_content = content.replace(old_volatility_section, new_volatility_section)
        
        # Write the updated content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print("SUCCESS: Updated the volatility section in trend_continuation_brain.py")
        print("SUCCESS: Low volatility in strong trends will now be treated as pullback opportunities")
        print("SUCCESS: The system should now properly identify trending moves instead of missing them")
    else:
        print("ERROR: Could not find the exact volatility section to replace")
        print("  The file may have already been modified or has different formatting")

if __name__ == "__main__":
    update_volatility_section()