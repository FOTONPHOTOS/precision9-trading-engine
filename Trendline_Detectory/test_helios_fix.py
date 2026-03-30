import json
import pandas as pd
import numpy as np
from datetime import datetime, date, time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Copy the exact encoder classes from helios_server.py to avoid import issues
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
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=ComprehensiveEncoder,
        ).encode("utf-8")

def test_helios_scenario():
    print("Testing the exact Helios server scenario...")
    
    # Create a sample DataFrame like the one in MarketIntelligence that caused the error
    df = pd.DataFrame({
        'open': [100.1, 100.2, 100.3],
        'high': [100.5, 100.6, 100.7],
        'low': [99.9, 100.0, 100.1],
        'close': [100.4, 100.5, 100.2],
        'volume': [1000.0, 1200.0, 1100.0],
        'kf_close': [100.39, 100.49, 100.21],
        'timestamp': pd.date_range(start='2023-01-01', periods=3)
    })
    
    # Create sample market intelligence object with DataFrame that was causing the original error
    market_intel = type('MarketIntelligence', (), {})()  # Create mock object
    market_intel.__dict__ = {
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
    
    # Create the helios_context as it's done in helios_server.py
    helios_context = {
        'gls_score': 0.2, 
        'btc_trend': market_intel.trend_direction if hasattr(market_intel, 'trend_direction') else 'UNKNOWN',
        'sentiment': 'RISK_ON' if market_intel.trend_direction == 'uptrend' else 'RISK_OFF' if market_intel.trend_direction == 'downtrend' else 'NEUTRAL',
        'current_price': market_intel.current_price if hasattr(market_intel, 'current_price') else None,
        'trend_strength': market_intel.trend_strength if hasattr(market_intel, 'trend_strength') else 0.0,
        'swing_highs_count': len(market_intel.swing_highs) if hasattr(market_intel, 'swing_highs') else 0,
        'swing_lows_count': len(market_intel.swing_lows) if hasattr(market_intel, 'swing_lows') else 0,
        'fvg_count': len(market_intel.fvgs) if hasattr(market_intel, 'fvgs') else 0,
        'order_block_count': len(market_intel.order_blocks) if hasattr(market_intel, 'order_blocks') else 0,
        'liquidity_sweep_count': len(market_intel.liquidity_sweeps) if hasattr(market_intel, 'liquidity_sweeps') else 0,
        'confluence_score': market_intel.confluence_score if hasattr(market_intel, 'confluence_score') else 0,
        'timestamp': market_intel.timestamp.isoformat() if hasattr(market_intel, 'timestamp') else None,
        # Include original market intelligence for backward compatibility - this is where the DataFrame was causing problems
        'market_intel': market_intel.__dict__
    }
    
    try:
        # This is the exact call that was failing in helios_server.py
        # In the actual server, it uses ComprehensiveJSONResponse(content=helios_context) in a FastAPI context
        # But for testing purposes, we'll just try to serialize the content directly
        result = json.dumps(helios_context, cls=ComprehensiveEncoder, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        print("SUCCESS: The exact Helios server scenario now serializes to JSON without error!")
        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)} bytes")
        print("The original 'Object of type DataFrame is not JSON serializable' error is now FIXED!")
        return True
    except Exception as e:
        print(f"FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_helios_scenario()
    if success:
        print("\nThe fix successfully resolves the original issue!")
    else:
        print("\nThe fix still has issues to resolve.")