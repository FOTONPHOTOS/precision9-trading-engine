#!/usr/bin/env python3
"""
Fix for structural integrity analyzer to handle ranging markets properly
"""

def fix_structural_analyzer():
    file_path = "G:\\python files\\precision9\\Simulation Environment\\Trendline_Detectory\\structural_integrity_analyzer.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the problematic section and replace it
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for the start of the problematic section
        if 'if not htf_swing_highs.empty and not htf_swing_lows.empty:' in line:
            # Add this line and start replacing the following logic
            new_lines.append(line)
            i += 1
            
            # Skip the old logic and replace with new logic
            # First, skip to the end of the old if block
            indent_level = len(line) - len(line.lstrip())
            inside_block = True
            
            # Find the lines to skip
            old_block_lines = []
            while i < len(lines):
                current_line = lines[i]
                
                # Check if we're still inside the block by indentation
                if current_line.strip() == "":
                    new_lines.append(current_line)
                    i += 1
                    continue
                    
                current_indent = len(current_line) - len(current_line.lstrip())
                
                # If indentation is less than original, we're out of the block
                if current_indent < indent_level and current_line.strip():
                    break
                    
                old_block_lines.append(current_line)
                i += 1
                
                # Check if this is the last line of the old block
                if 'Invalid HTF context: high ({high_level}) <= low ({low_level})' in current_line:
                    break
            
            # Add the new logic with proper indentation
            # Determine indentation from the original code
            new_indent = "        "  # Standard indentation level
            
            new_logic = [
                f'{new_indent}        # Get recent swings (last 5) to find valid high/low range in ranging markets\n',
                f'{new_indent}        recent_highs = htf_swing_highs.tail(5) if len(htf_swing_highs) > 5 else htf_swing_highs\n',
                f'{new_indent}        recent_lows = htf_swing_lows.tail(5) if len(htf_swing_lows) > 5 else htf_swing_lows\n',
                f'{new_indent}        \n',
                f'{new_indent}        # Find the highest high and lowest low among recent swings to form a valid range\n',
                f'{new_indent}        if not recent_highs.empty and not recent_lows.empty:\n',
                f'{new_indent}            highest_high = recent_highs[\'Level\'].max()\n',
                f'{new_indent}            lowest_low = recent_lows[\'Level\'].min()\n',
                f'{new_indent}            \n',
                f'{new_indent}            # Validate that we have a valid range where high > low\n',
                f'{new_indent}            if highest_high > lowest_low:\n',
                f'{new_indent}                htf_context[\"htf_swing_high\"] = highest_high\n',
                f'{new_indent}                htf_context[\"htf_swing_low\"] = lowest_low\n',
                f'{new_indent}\n',
                f'{new_indent}                fib_levels = _calculate_fibonacci_levels(highest_high, lowest_low)\n',
                f'{new_indent}                htf_context[\"fib_levels\"] = fib_levels\n',
                f'{new_indent}                htf_context[\"price_location\"] = self._get_price_location(current_price, fib_levels, highest_high, lowest_low)\n',
                f'{new_indent}            else:\n',
                f'{new_indent}                # Fallback: use the most recent swing and create a minimal valid range if needed\n',
                f'{new_indent}                latest_high = htf_swing_highs.iloc[-1]\n',
                f'{new_indent}                latest_low = htf_swing_lows.iloc[-1]\n',
                f'{new_indent}                high_level = latest_high[\'Level\']\n',
                f'{new_indent}                low_level = latest_low[\'Level\']\n',
                f'{new_indent}                \n',
                f'{new_indent}                if high_level > low_level:\n',
                f'{new_indent}                    htf_context[\"htf_swing_high\"] = high_level\n',
                f'{new_indent}                    htf_context[\"htf_swing_low\"] = low_level\n',
                f'{new_indent}                    \n',
                f'{new_indent}                    fib_levels = _calculate_fibonacci_levels(high_level, low_level)\n',
                f'{new_indent}                    htf_context[\"fib_levels\"] = fib_levels\n',
                f'{new_indent}                    htf_context[\"price_location\"] = self._get_price_location(current_price, fib_levels, high_level, low_level)\n',
                f'{new_indent}                else:\n',
                f'{new_indent}                    # If everything fails, create a small range around current price\n',
                f'{new_indent}                    print(f\"[INFO] Creating fallback HTF context. Using current price {current_price} as basis\")\n',
                f'{new_indent}                    price_buffer = current_price * 0.01  # 1% buffer\n',
                f'{new_indent}                    fallback_high = current_price * 1.005  # 0.5% above\n',
                f'{new_indent}                    fallback_low = current_price * 0.995   # 0.5% below\n',
                f'{new_indent}                    \n',
                f'{new_indent}                    htf_context[\"htf_swing_high\"] = fallback_high\n',
                f'{new_indent}                    htf_context[\"htf_swing_low\"] = fallback_low\n',
                f'{new_indent}                    \n',
                f'{new_indent}                    fib_levels = _calculate_fibonacci_levels(fallback_high, fallback_low)\n',
                f'{new_indent}                    htf_context[\"fib_levels\"] = fib_levels\n',
                f'{new_indent}                    htf_context[\"price_location\"] = self._get_price_location(current_price, fib_levels, fallback_high, fallback_low)\n',
                f'{new_indent}                    print(f\"[INFO] Fallback HTF context: ${{fallback_low:.4f}} to ${{fallback_high:.4f}}\")\n',
                f'{new_indent}        else:\n',
                f'{new_indent}            # If we don\'t have enough recent swings, use the most recent ones\n',
                f'{new_indent}            latest_high = htf_swing_highs.iloc[-1]\n',
                f'{new_indent}            latest_low = htf_swing_lows.iloc[-1]\n',
                f'{new_indent}            \n',
                f'{new_indent}            high_level = latest_high[\'Level\']\n',
                f'{new_indent}            low_level = latest_low[\'Level\']\n',
                f'{new_indent}            \n',
                f'{new_indent}            if high_level > low_level:\n',
                f'{new_indent}                htf_context[\"htf_swing_high\"] = high_level\n',
                f'{new_indent}                htf_context[\"htf_swing_low\"] = low_level\n',
                f'{new_indent}                \n',
                f'{new_indent}                fib_levels = _calculate_fibonacci_levels(high_level, low_level)\n',
                f'{new_indent}                htf_context[\"fib_levels\"] = fib_levels\n',
                f'{new_indent}                htf_context[\"price_location\"] = self._get_price_location(current_price, fib_levels, high_level, low_level)\n',
                f'{new_indent}            else:\n',
                f'{new_indent}                # If still invalid, use fallback\n',
                f'{new_indent}                print(f\"[INFO] Using fallback for HTF context. Current price: {current_price}\")\n',
                f'{new_indent}                price_buffer = current_price * 0.005  # 0.5% buffer\n',
                f'{new_indent}                fallback_high = current_price * 1.005\n',
                f'{new_indent}                fallback_low = current_price * 0.995\n',
                f'{new_indent}                \n',
                f'{new_indent}                htf_context[\"htf_swing_high\"] = fallback_high\n',
                f'{new_indent}                htf_context[\"htf_swing_low\"] = fallback_low\n',
                f'{new_indent}                \n',
                f'{new_indent}                fib_levels = _calculate_fibonacci_levels(fallback_high, fallback_low)\n',
                f'{new_indent}                htf_context[\"fib_levels\"] = fib_levels\n',
                f'{new_indent}                htf_context[\"price_location\"] = self._get_price_location(current_price, fib_levels, fallback_high, fallback_low)\n'
            ]
            
            new_lines.extend(new_logic)
        else:
            new_lines.append(line)
            i += 1
    
    # Write the modified content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("Fix applied successfully!")

if __name__ == "__main__":
    fix_structural_analyzer()