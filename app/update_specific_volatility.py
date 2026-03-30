"""
Script to update just the specific problematic volatility lines in trend_continuation_brain.py
This addresses the specific issue where low volatility reduces confidence even in strong trends.
"""
import os
import re

def update_specific_volatility_logic():
    file_path = r"G:\python files\precision9\Simulation Environment\Trendline_Detectory\trend_continuation_brain.py"
    
    # Read the current file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define the pattern to replace - the problem section that reduces confidence on low volatility
    old_pattern_1 = '''                    elif volatility_pct < 0.5:  # Extremely low volatility
                        self.reasoning_chain.append(f"  - [VOLATILITY WARNING] Extremely low volatility ({volatility_pct:.2f}%), reducing confidence")
                        self.confidence = max(0.15, self.confidence - 0.10)  # Reduce by 10%
                    elif volatility_pct < 1.0:  # Low volatility (new threshold)
                        self.reasoning_chain.append(f"  - [VOLATILITY INFO] Low volatility ({volatility_pct:.2f}%), adjusting approach")
                        self.confidence = max(0.15, self.confidence - 0.05)  # Reduce by 5%'''
    
    new_pattern_1 = '''                    elif volatility_pct < 0.5:  # Extremely low volatility
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
    
    # Check if the first occurrence exists and replace it
    if old_pattern_1 in content:
        content = content.replace(old_pattern_1, new_pattern_1, 1)  # Only replace first occurrence
        print("SUCCESS: First volatility section updated")
    else:
        print("INFO: First volatility section not found, checking for similar patterns")
        
        # Try to find and replace by matching the key elements
        # Look for the pattern that contains 'Extremely low volatility' and reduces confidence
        pattern = r'elif volatility_pct < 0\.5:  # Extremely low volatility\s*.*?self\.reasoning_chain\.append\(f"  - \[VOLATILITY WARNING\] Extremely low volatility \({volatility_pct:.2f}%\), reducing confidence"\)\s*.*?self\.confidence = max\(0\.15, self\.confidence - 0\.10\)  # Reduce by 10%\s*.*?elif volatility_pct < 1\.0:  # Low volatility \(new threshold\)\s*.*?self\.reasoning_chain\.append\(f"  - \[VOLATILITY INFO\] Low volatility \({volatility_pct:.2f}%\), adjusting approach"\)\s*.*?self\.confidence = max\(0\.15, self\.confidence - 0\.05\)  # Reduce by 5%'
        
        # Since regex replacement is complex, let's try a different approach
        # Replace just the key lines that reduce confidence
        content = content.replace(
            'self.confidence = max(0.15, self.confidence - 0.10)  # Reduce by 10%',
            '# CRITICAL FIX: Check trend context before reducing confidence\n                        if market_intel.trend_strength > 0.6 and market_intel.trend_direction in [\'uptrend\', \'downtrend\']:\n                            self.reasoning_chain.append(f"  - [VOLATILITY OPPORTUNITY] Strong trend ({market_intel.trend_strength:.0%}) with low volatility = pullback opportunity!")\n                            self.confidence = min(1.0, self.confidence + 0.08)  # Boost confidence for pullback opportunity\n                        else:\n                            self.confidence = max(0.15, self.confidence - 0.05)  # Reduce by 5%',
            1  # Only replace first occurrence
        )
    
    # Write the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Updated trend_continuation_brain.py with trend-aware volatility logic")
    print("The system will now consider trend strength when evaluating low volatility")

if __name__ == "__main__":
    update_specific_volatility_logic()