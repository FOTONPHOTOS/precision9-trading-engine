import asyncio
import pandas as pd
import sys
from typing import List, Dict, Tuple, Optional

# Add the path to the cloned library
SMC_LIB_PATH = "G:/python files/precision9/Simulation Environment/Trendline_Detectory/libs/smart-money-concepts"
sys.path.append(SMC_LIB_PATH)

# Import from the cloned library
from smartmoneyconcepts.smc import smc

from binance import AsyncClient

# Assuming fetch_binance_data is in the parent directory
from realtime_swing_detector import fetch_binance_data, detect_candlestick_patterns

# --- Helper function for Fibonacci Levels (remains the same) ---
def _calculate_fibonacci_levels(high: float, low: float) -> Dict[str, float]:
    """Calculates Fibonacci retracement levels for a given high-low range."""
    levels = [0.236, 0.382, 0.5, 0.618, 0.786]
    fib_levels = {}
    for level in levels:
        fib_levels[f"fib_{level}"] = high - (high - low) * level
    fib_levels["ote_low"] = high - (high - low) * 0.786
    fib_levels["ote_high"] = high - (high - low) * 0.618
    return fib_levels

class StructuralIntegrityAnalyzer:
    """
    Analyzes price action across multiple timeframes, incorporating HTF context
    and Fibonacci levels to generate a sophisticated market structure analysis.
    NOW POWERED BY A DEDICATED SMC LIBRARY.
    """

    def __init__(self, client: AsyncClient, timeframes: List[str] = ['5m', '15m', '30m', '1h', '4h'], lookback_hours: int = 4):
        self.client = client
        self.timeframes = timeframes
        self.lookback_hours = lookback_hours
        self.limit_map = {
            '5m': int((lookback_hours * 60) / 5),
            '15m': int((lookback_hours * 60) / 15),
            '30m': int((lookback_hours * 60) / 30),
            '1h': lookback_hours,
            '4h': int(lookback_hours / 4) + 20
        }

    async def _fetch_data(self, symbol: str) -> Dict[str, pd.DataFrame]:
        tasks = []
        htf_lookback_map = {'15m': 200, '1h': 24*7, '4h': 24*30}
        for tf in self.timeframes:
            limit = htf_lookback_map.get(tf, self.limit_map.get(tf, 200))
            tasks.append(fetch_binance_data(self.client, symbol, tf, limit))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        data = {}
        for i, tf in enumerate(self.timeframes):
            result = results[i]
            if isinstance(result, pd.DataFrame) and not result.empty:
                df = result.copy()
                df.columns = [col.lower() for col in df.columns]
                data[tf] = df
            elif isinstance(result, Exception):
                # You might want to log this error
                # logger.error(f"Failed to fetch data for timeframe {tf}: {result}")
                pass
        return data

    def _get_price_location(self, price: float, fib_levels: Dict, htf_high: float, htf_low: float) -> str:
        mid_point = (htf_high + htf_low) / 2
        ote_high = fib_levels.get('ote_high', mid_point)
        ote_low = fib_levels.get('ote_low', mid_point)

        if price > ote_high:
            return "Premium (High probability for SHORTS)"
        elif price < ote_low:
            return "Discount (High probability for LONGS)"
        else:
            return "Equilibrium"

    def analyze_single_timeframe(self, df: pd.DataFrame, primary_trend: str, swing_length: int) -> Tuple[int, List[str]]:
        if df.empty or len(df) < (swing_length * 2):
            return 0, []

        score_change = 0  # Can be positive or negative
        reasons = []

        # 1. Use the SMC library for robust detection
        swing_highs_lows = smc.swing_highs_lows(df, swing_length=swing_length)
        bos_choch = smc.bos_choch(df, swing_highs_lows)

        if bos_choch.empty or bos_choch is None:
            return score_change, []

        # 2. Enhanced interpretation of BOS/CHOCH results
        recent_events = bos_choch[bos_choch['BOS'].notna() | bos_choch['CHOCH'].notna()].tail(5)

        for _, event in recent_events.iterrows():
            # Check for BOS (Break of Structure)
            is_bos = event.get('BOS', 0) != 0 and not pd.isna(event.get('BOS', 0))
            # Check for CHOCH (Change of Character)
            is_choch = event.get('CHOCH', 0) != 0 and not pd.isna(event.get('CHOCH', 0))
            level = event.get('Level', 0)

            # Handle BOS patterns that support continuation
            if is_bos:
                bos_value = event['BOS']
                if primary_trend == 'uptrend' and bos_value == 1:  # Bullish BOS - supports continuation
                    score_change += 25
                    reasons.append(f"Bullish Break of Structure confirmed at ${level:.2f} - supports continuation")
                elif primary_trend == 'downtrend' and bos_value == -1:  # Bearish BOS - supports continuation
                    score_change += 25
                    reasons.append(f"Bearish Break of Structure confirmed at ${level:.2f} - supports continuation")

            # Handle CHOCH patterns that support reversal
            if is_choch:
                choch_value = event['CHOCH']
                if primary_trend == 'uptrend' and choch_value == -1:  # Bearish CHOCH - supports reversal from uptrend
                    score_change += 25
                    reasons.append(f"Bearish Change of Character confirmed at ${level:.2f} - supports reversal")
                elif primary_trend == 'downtrend' and choch_value == 1:  # Bullish CHOCH - supports reversal from downtrend
                    score_change += 25
                    reasons.append(f"Bullish Change of Character confirmed at ${level:.2f} - supports reversal")

        # If no specific patterns were found that match the primary trend, 
        # still report any BOS/CHOCH patterns that were detected
        if not reasons:
            for _, event in recent_events.iterrows():
                is_bos = event.get('BOS', 0) != 0
                is_choch = event.get('CHOCH', 0) != 0
                level = event.get('Level', 0)

                if is_bos and event['BOS'] == 1:  # Bullish BOS
                    reasons.append(f"Bullish BOS detected at ${level:.2f}")
                elif is_bos and event['BOS'] == -1:  # Bearish BOS
                    reasons.append(f"Bearish BOS detected at ${level:.2f}")
                elif is_choch and event['CHOCH'] == 1:  # Bullish CHOCH
                    reasons.append(f"Bullish CHOCH detected at ${level:.2f}")
                elif is_choch and event['CHOCH'] == -1:  # Bearish CHOCH
                    reasons.append(f"Bearish CHOCH detected at ${level:.2f}")

        return score_change, reasons

    async def analyze(self, symbol: str, primary_trend: str, current_price: float) -> Dict:
        multi_tf_data = await self._fetch_data(symbol)
        
        # 1. Establish HTF Context using the 15m chart
        htf_df = multi_tf_data.get('15m')
        htf_context = {"fib_levels": None, "price_location": "Unknown", "htf_swing_high": None, "htf_swing_low": None}
        if htf_df is not None and not htf_df.empty:
            # Use a larger swing length for the HTF context
            htf_swings = smc.swing_highs_lows(htf_df, swing_length=20)
            htf_swing_highs = htf_swings[htf_swings['HighLow'] == 1]
            htf_swing_lows = htf_swings[htf_swings['HighLow'] == -1]

            if not htf_swing_highs.empty and not htf_swing_lows.empty:
                # Get recent swings (last 5) to find valid high/low range in ranging markets
                recent_highs = htf_swing_highs.tail(5) if len(htf_swing_highs) > 5 else htf_swing_highs
                recent_lows = htf_swing_lows.tail(5) if len(htf_swing_lows) > 5 else htf_swing_lows
                
                # Find the highest high and lowest low among recent swings to form a valid range
                if not recent_highs.empty and not recent_lows.empty:
                    highest_high = recent_highs['Level'].max()
                    lowest_low = recent_lows['Level'].min()
                    
                    # Validate that we have a valid range where high > low
                    if highest_high > lowest_low:
                        htf_context["htf_swing_high"] = highest_high
                        htf_context["htf_swing_low"] = lowest_low

                        fib_levels = _calculate_fibonacci_levels(highest_high, lowest_low)
                        htf_context["fib_levels"] = fib_levels
                        htf_context["price_location"] = self._get_price_location(current_price, fib_levels, highest_high, lowest_low)
                    else:
                        # Fallback: use the most recent swing and create a minimal valid range if needed
                        latest_high = htf_swing_highs.iloc[-1]
                        latest_low = htf_swing_lows.iloc[-1]
                        high_level = latest_high['Level']
                        low_level = latest_low['Level']
                        
                        if high_level > low_level:
                            htf_context["htf_swing_high"] = high_level
                            htf_context["htf_swing_low"] = low_level
                            
                            fib_levels = _calculate_fibonacci_levels(high_level, low_level)
                            htf_context["fib_levels"] = fib_levels
                            htf_context["price_location"] = self._get_price_location(current_price, fib_levels, high_level, low_level)
                        else:
                            # If everything fails, create a small range around current price
                            print(f"[INFO] Creating fallback HTF context. Using current price {current_price} as basis")
                            price_buffer = current_price * 0.01  # 1% buffer
                            fallback_high = current_price * 1.005  # 0.5% above
                            fallback_low = current_price * 0.995   # 0.5% below
                            
                            htf_context["htf_swing_high"] = fallback_high
                            htf_context["htf_swing_low"] = fallback_low
                            
                            fib_levels = _calculate_fibonacci_levels(fallback_high, fallback_low)
                            htf_context["fib_levels"] = fib_levels
                            htf_context["price_location"] = self._get_price_location(current_price, fib_levels, fallback_high, fallback_low)
                            print(f"[INFO] Fallback HTF context: ${{fallback_low:.4f}} to ${{fallback_high:.4f}}")
                else:
                    # If we don't have enough recent swings, use the most recent ones
                    latest_high = htf_swing_highs.iloc[-1]
                    latest_low = htf_swing_lows.iloc[-1]
                    
                    high_level = latest_high['Level']
                    low_level = latest_low['Level']
                    
                    if high_level > low_level:
                        htf_context["htf_swing_high"] = high_level
                        htf_context["htf_swing_low"] = low_level
                        
                        fib_levels = _calculate_fibonacci_levels(high_level, low_level)
                        htf_context["fib_levels"] = fib_levels
                        htf_context["price_location"] = self._get_price_location(current_price, fib_levels, high_level, low_level)
                    else:
                        # If still invalid, use fallback
                        print(f"[INFO] Using fallback for HTF context. Current price: {current_price}")
                        price_buffer = current_price * 0.005  # 0.5% buffer
                        fallback_high = current_price * 1.005
                        fallback_low = current_price * 0.995
                        
                        htf_context["htf_swing_high"] = fallback_high
                        htf_context["htf_swing_low"] = fallback_low
                        
                        fib_levels = _calculate_fibonacci_levels(fallback_high, fallback_low)
                        htf_context["fib_levels"] = fib_levels
                        htf_context["price_location"] = self._get_price_location(current_price, fib_levels, fallback_high, fallback_low)
        # 2. Analyze LTF Structure with tuned sensitivity
        total_score = 100
        all_reasons = []
        # Define swing lengths for each LTF to tune sensitivity (more responsive)
        ltf_configs = {'5m': 2}  # Even more reduced swing lengths for maximum sensitivity

        for tf, swing_len in ltf_configs.items():
            df = multi_tf_data.get(tf)
            if df is None: continue
            
            # Get both positive and negative analysis
            score_change, reasons = self.analyze_single_timeframe(df, primary_trend, swing_length=swing_len)
            
            if reasons:
                tf_reasons = [f"[{tf.upper()}] {r}" for r in reasons]
                # Weight reasons from higher timeframes more heavily
                weight = 1.5 if tf == '30m' else 1.2 if tf == '15m' else 1.0
                total_score += (score_change * weight)
                all_reasons.extend(tf_reasons)

        # 3. Add candlestick pattern analysis as a fallback when no BOS/CHOCH patterns found
        if not any('BOS' in reason or 'CHOCH' in reason for reason in all_reasons):
            for tf in ltf_configs.keys():
                df = multi_tf_data.get(tf)
                if df is None or df.empty: continue
                
                candle_patterns = detect_candlestick_patterns(df)
                
                # Look for recent candlestick patterns that align with the trend
                recent_patterns = candle_patterns[-5:] if len(candle_patterns) >= 5 else candle_patterns  # Last 5 patterns
                
                for pattern in recent_patterns:
                    pattern_type = pattern['type']
                    pattern_timestamp = pattern['timestamp']
                    pattern_close = pattern['candle_close'] if 'candle_close' in pattern else df.loc[pattern_timestamp]['close']
                    
                    # Look for engulfing patterns which are strong reversal indicators
                    if 'ENGULFING' in pattern_type:
                        if primary_trend == 'uptrend' and 'BEARISH' in pattern_type:
                            # Bearish engulfing in uptrend - potential reversal signal
                            all_reasons.append(f"[{tf.upper()}] Bearish Engulfing pattern detected at ${pattern_close:.2f} - potential reversal from uptrend")
                        elif primary_trend == 'downtrend' and 'BULLISH' in pattern_type:
                            # Bullish engulfing in downtrend - potential reversal signal
                            all_reasons.append(f"[{tf.upper()}] Bullish Engulfing pattern detected at ${pattern_close:.2f} - potential reversal from downtrend")
                    
                    # Look for other reversal patterns like doji
                    elif 'DOJI' in pattern_type:
                        all_reasons.append(f"[{tf.upper()}] Doji pattern detected at ${pattern_close:.2f} - potential indecision/market turning point")
                    
                    # Look for star patterns (morning/evening star)
                    elif 'STAR' in pattern_type:
                        if primary_trend == 'uptrend' and 'EVENING' in pattern_type:
                            all_reasons.append(f"[{tf.upper()}] Evening Star pattern detected at ${pattern_close:.2f} - potential bearish reversal from uptrend")
                        elif primary_trend == 'downtrend' and 'MORNING' in pattern_type:
                            all_reasons.append(f"[{tf.upper()}] Morning Star pattern detected at ${pattern_close:.2f} - potential bullish reversal from downtrend")
                    
                    # Look for piercing/dark cloud cover
                    elif 'PIERCING' in pattern_type:
                        if primary_trend == 'downtrend':
                            all_reasons.append(f"[{tf.upper()}] Piercing pattern detected at ${pattern_close:.2f} - potential bullish reversal during downtrend")
                    elif 'DARK_CLOUD' in pattern_type:
                        if primary_trend == 'uptrend':
                            all_reasons.append(f"[{tf.upper()}] Dark Cloud Cover pattern detected at ${pattern_close:.2f} - potential bearish reversal during uptrend")

        final_score = max(0, min(100, total_score))  # Clamp between 0 and 100
        if not all_reasons:
            # Add positive reasons when no specific patterns are found
            all_reasons.append("No structural weaknesses detected on LTF.")
            # More importantly, look for positive BOS/CHOCH patterns
            for tf, swing_len in ltf_configs.items():
                df = multi_tf_data.get(tf)
                if df is None: continue
                
                # Check for any positive BOS/CHOCH patterns that support the trend
                swing_highs_lows = smc.swing_highs_lows(df, swing_length=swing_len)
                bos_choch = smc.bos_choch(df, swing_highs_lows)
                
                if not bos_choch.empty and bos_choch is not None:
                    recent_events = bos_choch.dropna().tail(3)  # Look for recent positive events
                    for _, event in recent_events.iterrows():
                        is_bos = event.get('BOS', 0) != 0
                        is_choch = event.get('CHOCH', 0) != 0
                        level = event.get('Level', 0)

                        if primary_trend == 'uptrend':
                            if is_bos and event['BOS'] == 1:  # Bullish BOS in uptrend - continuation
                                all_reasons.append(f"[{tf.upper()}] Bullish Break of Structure confirmed at ${level:.2f} - supports continuation")
                            elif is_choch and event['CHOCH'] == -1:  # Bearish CHOCH after downtrend - reversal setup
                                all_reasons.append(f"[{tf.upper()}] Bearish Change of Character confirmed at ${level:.2f} - supports reversal")
                        elif primary_trend == 'downtrend':
                            if is_bos and event['BOS'] == -1:  # Bearish BOS in downtrend - continuation
                                all_reasons.append(f"[{tf.upper()}] Bearish Break of Structure confirmed at ${level:.2f} - supports continuation")
                            elif is_choch and event['CHOCH'] == 1:  # Bullish CHOCH after uptrend - reversal setup
                                all_reasons.append(f"[{tf.upper()}] Bullish Change of Character confirmed at ${level:.2f} - supports reversal")

        # 2. Establish HTF2 Context using the 4h chart for broader perspective
        htf2_df = multi_tf_data.get('4h')
        htf2_context = {"fib_levels": None, "price_location": "Unknown", "htf2_swing_high": None, "htf2_swing_low": None}
        if htf2_df is not None and not htf2_df.empty:
            # Use a larger swing length for the HTF2 context
            htf2_swings = smc.swing_highs_lows(htf2_df, swing_length=10)  # Different swing length for 4h
            htf2_swing_highs = htf2_swings[htf2_swings['HighLow'] == 1]
            htf2_swing_lows = htf2_swings[htf2_swings['HighLow'] == -1]

            if not htf2_swing_highs.empty and not htf2_swing_lows.empty:
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
        # 4. Add HTF2 context information to reasons for better understanding
        if htf2_context["htf2_swing_high"] and htf2_context["htf2_swing_low"]:
            htf2_high = htf2_context["htf2_swing_high"]
            htf2_low = htf2_context["htf2_swing_low"]
            all_reasons.append(f"[4H HTF2] 4H Range: ${htf2_low:.2f} - ${htf2_high:.2f}, Current Price Location: {htf2_context['price_location']}")
            
            # Check if current price is near important 4H levels (FVGs, OTE levels, etc.)
            fib_levels = htf2_context.get("fib_levels", {})
            ote_high = fib_levels.get("ote_high")
            ote_low = fib_levels.get("ote_low")
            
            if ote_high and abs(current_price - ote_high) / current_price < 0.02:  # Within 2% of OTE high
                all_reasons.append(f"[4H HTF2] Price near 4H OTE High (${ote_high:.2f}) - Potential reversal area")
            elif ote_low and abs(current_price - ote_low) / current_price < 0.02:  # Within 2% of OTE low
                all_reasons.append(f"[4H HTF2] Price near 4H OTE Low (${ote_low:.2f}) - Potential reversal area")

        return {
            "integrity_score": final_score,
            "reasons": all_reasons,
            "htf_context": htf_context,
            "htf2_context": htf2_context
        }