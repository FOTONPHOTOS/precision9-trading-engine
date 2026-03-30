"""
Script to update both instances of the volatility logic in trend_continuation_brain.py
"""
import os

def update_both_volatility_sections():
    file_path = r"G:\python files\precision9\Simulation Environment\Trendline_Detectory\trend_continuation_brain.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content into parts to handle both instances
    # The first instance was already updated, now update the second
    
    # Find the second instance - the one starting at line ~1085
    old_pattern_2 = '''                    elif volatility_pct < 0.5:  # Extremely low volatility
                        self.reasoning_chain.append(f"  - [VOLATILITY WARNING] Extremely low volatility ({volatility_pct:.2f}%), reducing confidence")
                        self.confidence = max(0.15, self.confidence - 0.10)  # Reduce by 10%
                    elif volatility_pct < 1.0:  # Low volatility (new threshold)
                        self.reasoning_chain.append(f"  - [VOLATILITY INFO] Low volatility ({volatility_pct:.2f}%), adjusting approach")
                        self.confidence = max(0.15, self.confidence - 0.05)  # Reduce by 5%'''
    
    new_pattern_2 = '''                    elif volatility_pct < 0.5:  # Extremely low volatility
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
                            self.confidence = max(0.15, self.confidence - 0.03)  # Smaller reduction'''
    
    # Replace the second occurrence
    updated_content = content.replace(old_pattern_2, new_pattern_2)
    
    if updated_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print("SUCCESS: Updated both volatility sections in trend_continuation_brain.py")
        print("SUCCESS: Both instances of problematic low volatility logic have been fixed")
    else:
        print("INFO: Second volatility section not found or already updated")

if __name__ == "__main__":
    update_both_volatility_sections()