#!/usr/bin/env python3
"""
Fix for HTF2 context in structural integrity analyzer to handle ranging markets properly
"""

def fix_htf2_context():
    file_path = "G:\\python files\\precision9\\Simulation Environment\\Trendline_Detectory\\structural_integrity_analyzer.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Build the exact original HTF2 block with proper indentation and spacing
    old_code = """            if not htf2_swing_highs.empty and not htf2_swing_lows.empty:
                latest_high = htf2_swing_highs.iloc[-1]
                latest_low = htf2_swing_lows.iloc[-1]

                # Validate that we have valid swing values and that high > low
                high_level = latest_high['Level']
                low_level = latest_low['Level']

                # Ensure the swing high is actually higher than the swing low
                if high_level > low_level:
                    htf2_context["htf2_swing_high"] = high_level
                    htf2_context["htf2_swing_low"] = low_level

                    fib_levels = _calculate_fibonacci_levels(high_level, low_level)
                    htf2_context["fib_levels"] = fib_levels
                    htf2_context["price_location"] = self._get_price_location(current_price, fib_levels, high_level, low_level)
                else:
                    # This is the problematic case - set to None to indicate invalid HTF2 context
                    htf2_context["htf2_swing_high"] = None
                    htf2_context["htf2_swing_low"] = None
                    htf2_context["fib_levels"] = None
                    htf2_context["price_location"] = "Invalid HTF2 Context - No Valid Swing Range"
                    print(f"[ERROR] Invalid HTF2 context: high ({{high_level}}) <= low ({{low_level}})")
"""
    
    new_code = """            if not htf2_swing_highs.empty and not htf2_swing_lows.empty:
                # Get recent swings (last 5) to find valid high/low range in ranging markets
                recent_highs = htf2_swing_highs.tail(5) if len(htf2_swing_highs) > 5 else htf2_swing_highs
                recent_lows = htf2_swing_lows.tail(5) if len(htf2_swing_lows) > 5 else htf2_swing_lows
                
                # Find the highest high and lowest low among recent swings to form a valid range
                if not recent_highs.empty and not recent_lows.empty:
                    highest_high = recent_highs['Level'].max()
                    lowest_low = recent_lows['Level'].min()
                    
                    # Validate that we have a valid range where high > low
                    if highest_high > lowest_low:
                        htf2_context["htf2_swing_high"] = highest_high
                        htf2_context["htf2_swing_low"] = lowest_low

                        fib_levels = _calculate_fibonacci_levels(highest_high, lowest_low)
                        htf2_context["fib_levels"] = fib_levels
                        htf2_context["price_location"] = self._get_price_location(current_price, fib_levels, highest_high, lowest_low)
                    else:
                        # Fallback: use the most recent swing and create a minimal valid range if needed
                        latest_high = htf2_swing_highs.iloc[-1]
                        latest_low = htf2_swing_lows.iloc[-1]
                        high_level = latest_high['Level']
                        low_level = latest_low['Level']
                        
                        if high_level > low_level:
                            htf2_context["htf2_swing_high"] = high_level
                            htf2_context["htf2_swing_low"] = low_level
                            
                            fib_levels = _calculate_fibonacci_levels(high_level, low_level)
                            htf2_context["fib_levels"] = fib_levels
                            htf2_context["price_location"] = self._get_price_location(current_price, fib_levels, high_level, low_level)
                        else:
                            # If everything fails, create a small range around current price
                            print(f"[INFO] Creating fallback HTF2 context. Using current price {current_price} as basis")
                            price_buffer = current_price * 0.01  # 1% buffer
                            fallback_high = current_price * 1.005  # 0.5% above
                            fallback_low = current_price * 0.995   # 0.5% below
                            
                            htf2_context["htf2_swing_high"] = fallback_high
                            htf2_context["htf2_swing_low"] = fallback_low
                            
                            fib_levels = _calculate_fibonacci_levels(fallback_high, fallback_low)
                            htf2_context["fib_levels"] = fib_levels
                            htf2_context["price_location"] = self._get_price_location(current_price, fib_levels, fallback_high, fallback_low)
                            print(f"[INFO] Fallback HTF2 context: ${{fallback_low:.4f}} to ${{fallback_high:.4f}}")
                else:
                    # If we don't have enough recent swings, use the most recent ones
                    latest_high = htf2_swing_highs.iloc[-1]
                    latest_low = htf2_swing_lows.iloc[-1]
                    
                    high_level = latest_high['Level']
                    low_level = latest_low['Level']
                    
                    if high_level > low_level:
                        htf2_context["htf2_swing_high"] = high_level
                        htf2_context["htf2_swing_low"] = low_level
                        
                        fib_levels = _calculate_fibonacci_levels(high_level, low_level)
                        htf2_context["fib_levels"] = fib_levels
                        htf2_context["price_location"] = self._get_price_location(current_price, fib_levels, high_level, low_level)
                    else:
                        # If still invalid, use fallback
                        print(f"[INFO] Using fallback for HTF2 context. Current price: {current_price}")
                        price_buffer = current_price * 0.005  # 0.5% buffer
                        fallback_high = current_price * 1.005
                        fallback_low = current_price * 0.995
                        
                        htf2_context["htf2_swing_high"] = fallback_high
                        htf2_context["htf2_swing_low"] = fallback_low
                        
                        fib_levels = _calculate_fibonacci_levels(fallback_high, fallback_low)
                        htf2_context["fib_levels"] = fib_levels
                        htf2_context["price_location"] = self._get_price_location(current_price, fib_levels, fallback_high, fallback_low)
"""
    
    # Perform the replacement
    if old_code in content:
        new_content = content.replace(old_code, new_code)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("HTF2 fix applied successfully!")
    else:
        print("Could not find the exact HTF2 pattern to replace.")
        print("Let's try a more flexible approach...")
        
        # Find the starting pattern and replace from there
        start_pattern = "if not htf2_swing_highs.empty and not htf2_swing_lows.empty:"
        start_idx = content.find(start_pattern)
        
        if start_idx != -1:
            # Find the end of the problematic block
            lines = content.split('\n')
            # Find which line contains our start pattern
            start_line_num = -1
            for i, line in enumerate(lines):
                if start_pattern in line:
                    start_line_num = i
                    break
            
            if start_line_num != -1:
                # Find the end of the block by looking for the next line with less indentation
                base_indent = len(lines[start_line_num]) - len(lines[start_line_num].lstrip())
                
                end_line_num = start_line_num
                for i in range(start_line_num, len(lines)):
                    line = lines[i]
                    if line.strip() == "":
                        end_line_num = i
                        continue
                    
                    indent = len(line) - len(line.lstrip())
                    if indent < base_indent and line.strip():
                        end_line_num = i - 1  # The line before this one is the end
                        break
                    end_line_num = i
                
                # Extract the problematic block
                problematic_block = "\n".join(lines[start_line_num:end_line_num+1]) + "\n"
                
                print(f"Found HTF2 block from line {start_line_num+1} to {end_line_num+1}")
                print("Original HTF2 block:")
                print(repr(problematic_block))
                
                # Replace the block
                new_content = content.replace(problematic_block, new_code)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print("HTF2 flexible replacement applied successfully!")
        else:
            print("Could not locate the HTF2 pattern to replace.")

if __name__ == "__main__":
    fix_htf2_context()