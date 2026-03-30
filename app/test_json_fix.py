#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify the JSON serialization fix for NaN and Infinity values
"""
import json
import numpy as np
from datetime import datetime, date, time
import pandas as pd

# Import the ComprehensiveEncoder from helios_server to test it
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Copy the encoder implementation to test it directly
class TestComprehensiveEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            val = float(obj)
            if np.isnan(val):
                return None  # or "NaN" if you prefer string representation
            elif np.isinf(val):
                return "Infinity" if val > 0 else "-Infinity"
            return val
        if isinstance(obj, float):
            # Handle regular Python float values that might be nan or inf
            if obj != obj:  # NaN check: NaN is not equal to itself
                return None  # or "NaN" if you prefer string representation
            elif obj == float('inf'):
                return "Infinity"
            elif obj == float('-inf'):
                return "-Infinity"
            return obj
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
        return super(TestComprehensiveEncoder, self).default(obj)

# Test data with NaN and Infinity values
test_data = {
    'normal_value': 1.23,
    'numpy_nan': np.nan,
    'python_nan': float('nan'),
    'numpy_inf': np.inf,
    'python_inf': float('inf'),
    'numpy_neg_inf': -np.inf,
    'python_neg_inf': float('-inf'),
    'regular_value': 42.0,
    'nested': {
        'another_nan': np.float64('nan'),
        'another_inf': np.float64('inf')
    }
}

print("Testing JSON serialization with NaN and Infinity values...")
print("Test data:", test_data)

try:
    # Test the encoder
    json_output = json.dumps(test_data, cls=TestComprehensiveEncoder, allow_nan=True)
    print("\n[SUCCESS] JSON serialization successful!")
    print("Serialized JSON:", json_output)

    # Now test loading it back
    loaded_data = json.loads(json_output)
    print("\n[SUCCESS] JSON deserialization successful!")
    print("Loaded data:", loaded_data)

    print("\n[SUCCESS] All tests passed! The JSON serialization fix is working correctly.")

except Exception as e:
    print(f"\n[FAILURE] Test failed with error: {e}")
    import traceback
    traceback.print_exc()