"""Analyze Horus CVD data extraction"""
import json

# Load the data
with open('horus_sync_20251010_202755.json', 'r') as f:
    data = json.load(f)

snapshot = data['latest_snapshot']

print("="*100)
print("HORUS CVD DATA ANALYSIS")
print("="*100)

print("\n[DIRECT FIELDS]")
print(f"CVD (direct): {snapshot['cvd']}")
print(f"Delta (direct): {snapshot['delta']}")
print(f"Liquidity Score: {snapshot['liquidity_score']}")

print("\n[SPECTRA LIQUIDITY]")
if snapshot['spectra_liquidity']:
    print(f"Available: YES")
    print(f"Keys: {list(snapshot['spectra_liquidity'].keys())}")

    # Check CVD field
    cvd_data = snapshot['spectra_liquidity'].get('cvd', {})
    print(f"\nCVD Type: {type(cvd_data)}")

    if isinstance(cvd_data, dict):
        print(f"CVD is dictionary with {len(cvd_data)} fields")
        print("\nCVD Fields:")
        for key, value in cvd_data.items():
            if isinstance(value, (int, float)):
                print(f"  {key}: {value}")
            elif isinstance(value, str):
                print(f"  {key}: '{value}'")
            elif isinstance(value, dict):
                print(f"  {key}: [dict with {len(value)} items]")
            else:
                print(f"  {key}: {type(value)}")
    else:
        print(f"CVD Value: {cvd_data}")
else:
    print("Not available")

print("\n[HEATMAP DATA]")
if snapshot['heatmap_data']:
    print(f"Available: YES")
    print(f"POC: ${snapshot['point_of_control']:.2f}")
    print(f"VAH: ${snapshot['value_area_high']:.2f}")
    print(f"VAL: ${snapshot['value_area_low']:.2f}")
    print(f"Liquidity Zones: {len(snapshot['liquidity_zones'])}")
else:
    print("Not available")

print("\n[HTF STRUCTURE]")
if snapshot['htf_structure']:
    print(f"Available: YES")
    htf = snapshot['htf_structure']
    print(f"Keys: {list(htf.keys())[:10]}")
else:
    print("Not available")

print("\n[DATA QUALITY]")
print(f"Freshness Score: {snapshot['data_freshness_score']:.0%}")
print(f"Sync Quality: {snapshot['sync_quality']:.0%}")

print("\n" + "="*100)
print("CHECKING ALL SNAPSHOTS FOR CVD VALUES")
print("="*100)

all_snapshots = data.get('snapshots', [])
print(f"\nTotal snapshots: {len(all_snapshots)}")

if all_snapshots:
    cvd_values = []
    for i, snap in enumerate(all_snapshots[:5]):
        cvd = snap.get('cvd', 0)
        delta = snap.get('delta', 0)
        cvd_values.append(cvd)
        print(f"Snapshot {i+1}: CVD={cvd:.2f}, Delta={delta:.2f}")

    if all(v == 0 for v in cvd_values):
        print("\n[PROBLEM] All CVD values are 0.00!")
        print("Checking if data is in spectra_liquidity.cvd instead...")

        for i, snap in enumerate(all_snapshots[:3]):
            if snap.get('spectra_liquidity'):
                cvd_obj = snap['spectra_liquidity'].get('cvd', {})
                if isinstance(cvd_obj, dict):
                    print(f"\nSnapshot {i+1} - CVD dict fields:")
                    for key in ['trend', 'strength', 'volume_delta_1h', 'buy_ratio', 'cumulative_value']:
                        val = cvd_obj.get(key, 'N/A')
                        print(f"  {key}: {val}")
