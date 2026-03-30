#!/usr/bin/env python3
"""
Fix for variable name error in trend_continuation_brain.py
"""

def fix_variable_name():
    file_path = "G:\\python files\\precision9\\Simulation Environment\\Trendline_Detectory\\trend_continuation_brain.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the variable name from htf2_context to htf2
    # Replace the incorrect variable name in our logic
    content = content.replace(
        "htf2_context and (\"Equilibrium\" in htf2_context.get('price_location', '') or",
        "htf2 and (\"Equilibrium\" in htf2.get('price_location', '') or"
    ).replace(
        "(htf2_context.get('htf2_swing_high') and htf2_context.get('htf2_swing_low') and",
        "(htf2.get('htf2_swing_high') and htf2.get('htf2_swing_low') and"
    ).replace(
        "(htf2_context['htf2_swing_high'] - htf2_context['htf2_swing_low'])",
        "(htf2['htf2_swing_high'] - htf2['htf2_swing_low'])"
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Variable name fix applied successfully!")

if __name__ == "__main__":
    fix_variable_name()