import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Copy the encoder from helios_server.py to test it
import json
from typing import Any
import numpy as np
import pandas as pd
from datetime import datetime, date, time


class ComprehensiveEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')  # Convert DataFrame to list of dictionaries
        if isinstance(obj, pd.Series):
            return obj.to_dict()  # Convert Series to dictionary
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        return super(ComprehensiveEncoder, self).default(obj)


class ComprehensiveJSONResponse:
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=ComprehensiveEncoder,
        ).encode("utf-8")


def test_market_intelligence_serialization():
    print("Testing MarketIntelligence-like serialization...")
    
    # Create a sample DataFrame like the one in MarketIntelligence
    df = pd.DataFrame({
        'open': [100.1, 100.2, 100.3],
        'high': [100.5, 100.6, 100.7],
        'low': [99.9, 100.0, 100.1],
        'close': [100.4, 100.5, 100.2],
        'volume': [1000.0, 1200.0, 1100.0],
        'kf_close': [100.39, 100.49, 100.21],  # Kalman filtered close
        'timestamp': pd.date_range(start='2023-01-01', periods=3)
    })
    
    # Simulate various objects that could be in MarketIntelligence
    fvgs = [{'gap_type': 'bullish', 'gap_start': 99.0, 'gap_end': 99.2}]  # Simplified FVG objects
    obs = [{'type': 'bullish', 'entry_zone_low': 98.5, 'entry_zone_high': 98.7}]  # Simplified OB objects
    sweeps = [{'type': 'bullish_sweep', 'swept_level': 98.0, 'timestamp': datetime.now()}]  # Simplified sweep objects
    
    # Create a sample market intelligence object structure similar to what's in the actual code
    market_intel_dict = {
        'current_price': 100.4,
        'trend_direction': 'uptrend',
        'trend_strength': 0.75,
        'swing_highs': [{'price': 100.5, 'timestamp': '2023-01-01T10:00:00'}],
        'swing_lows': [{'price': 99.9, 'timestamp': '2023-01-01T08:00:00'}],
        'candle_patterns': [{'type': 'BULLISH_BREAK', 'current_close': 100.4, 'timestamp': datetime.now()}],
        'fvgs': fvgs,
        'order_blocks': obs,
        'liquidity_sweeps': sweeps,
        'liquidity_pools': [],
        'range_trap_analysis': {'is_trapped': False, 'trap_severity': 0.1},
        'stop_hunt_warning': {'stop_hunt_probability': 0.1, 'severity': 0.05, 'is_stop_hunt_mode': False},
        'confluence_score': 5,
        'timestamp': datetime.utcnow(),
        'structural_integrity_score': 78.5,
        'structural_integrity_reasons': ['Strong trend structure', 'Low volatility environment'],
        'htf_context': {
            'htf_swing_high': 102.0,
            'htf_swing_low': 98.0,
            'fib_levels': {'ote_high': 101.5, 'ote_low': 98.5}
        },
        'htf2_context': {
            'htf2_swing_high': 105.0,
            'htf2_swing_low': 95.0,
            'price_location': 'Mid Range',
            'fib_levels': {'ote_high': 104.0, 'ote_low': 96.0}
        },
        'volume_profile_zones': {
            'poc': 100.1,
            'hvns': [99.5, 100.8]
        },
        'price_data': df  # This is what was causing the original issue
    }
    
    try:
        # This should work now with our fix
        response = ComprehensiveJSONResponse()
        result = response.render(market_intel_dict)
        print("SUCCESS: MarketIntelligence-like structure serialized to JSON without error!")
        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)} bytes")
        print("Serialization successful - the Helios server should now work properly!")
        return True
    except Exception as e:
        print(f"FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_market_intelligence_serialization()
    if success:
        print("\nSUCCESS: The fix properly handles complex MarketIntelligence objects!")
    else:
        print("\nFAILURE: There are still serialization issues to resolve.")