import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Copy the encoder from helios_server.py to test it
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
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        return super(ComprehensiveEncoder, self).default(obj)


class ComprehensiveJSONResponse:
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=ComprehensiveEncoder,
        ).encode("utf-8")


def test_encoder():
    print("Testing DataFrame JSON serialization fix...")
    
    # Create a sample DataFrame like the one in MarketIntelligence
    df = pd.DataFrame({
        'open': [100.1, 100.2, 100.3],
        'high': [100.5, 100.6, 100.7],
        'low': [99.9, 100.0, 100.1],
        'close': [100.4, 100.5, 100.2],
        'volume': [1000.0, 1200.0, 1100.0],
        'timestamp': pd.date_range(start='2023-01-01', periods=3)
    })
    
    # Create a sample market intelligence object structure
    market_intel_dict = {
        'current_price': 100.4,
        'trend_direction': 'uptrend',
        'trend_strength': 0.75,
        'swing_highs': [{'price': 100.5, 'timestamp': '2023-01-01T10:00:00'}],
        'swing_lows': [{'price': 99.9, 'timestamp': '2023-01-01T08:00:00'}],
        'fvgs': [],
        'order_blocks': [],
        'liquidity_sweeps': [],
        'liquidity_pools': [],
        'range_trap_analysis': {'is_trapped': False},
        'stop_hunt_warning': {'stop_hunt_probability': 0.1},
        'confluence_score': 5,
        'timestamp': datetime.utcnow(),
        'price_data': df  # This is what was causing the issue
    }
    
    try:
        # This should work now with our fix
        response = ComprehensiveJSONResponse()
        result = response.render(market_intel_dict)
        print("SUCCESS: DataFrame serialized to JSON without error!")
        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)} bytes")
        print("First 100 chars:", result.decode('utf-8')[:100] + "...")
        return True
    except Exception as e:
        print(f"FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_encoder()
    if success:
        print("\nSUCCESS: The fix should work in the Helios server!")
    else:
        print("\nFAILURE: The fix needs more work.")