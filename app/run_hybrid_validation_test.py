"""
Comprehensive Hybrid Validation Test
Demonstrates Arsenal + Horus complementary analysis
"""

import asyncio
import time
from datetime import datetime

# Import collectors
from horus_data_collector import HorusDataCollector
from arsenal_data_collector import ArsenalDataCollector

# Import validator
from hybrid_validator import HybridValidator

# Arsenal components for mock data
from liquidity_sweep_detector import StopHuntWarning
from range_trap_detector import RangeTrapAnalysis


async def run_hybrid_test():
    print('='*100)
    print('HYBRID VALIDATION TEST - COMPREHENSIVE DEMONSTRATION')
    print('='*100)
    print()

    # Step 1: Collect Horus Data
    print('[STEP 1/4] Collecting Horus Data from Unified Processor')
    print('-'*100)

    horus_collector = HorusDataCollector()

    print('Connecting to Unified Processor and collecting data for 20 seconds...')
    print()
    await horus_collector.collect_data(duration_seconds=20)

    horus_collector.get_collection_summary()

    # Export Horus data
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    horus_file = f'horus_test_{timestamp_str}.json'
    horus_collector.export_data(horus_file)
    print(f'\n[OK] Horus data saved: {horus_file}')

    # Step 2: Create Arsenal Snapshot
    print()
    print('[STEP 2/4] Creating Arsenal Data Snapshot')
    print('-'*100)
    print('NOTE: Using simulated Arsenal data for demonstration.')
    print('      In production, Arsenal collector would be integrated into live_arsenal_system.py')
    print()

    arsenal_collector = ArsenalDataCollector()
    arsenal_collector.start_collection()

    # Create realistic mock snapshot based on current market
    mock_snapshot = arsenal_collector.collect_snapshot(
        current_price=211.81,
        current_candle_timestamp=time.time(),
        swing_analysis={
            'swing_high': 213.57,
            'swing_low': 210.33,
            'bars_since_high': 5,
            'bars_since_low': 2
        },
        patterns=[
            {'type': 'BULLISH_BREAK', 'current_close': 212.17, 'break_pct': 0.14, 'timestamp': time.time()},
            {'type': 'BEARISH_BREAK', 'current_close': 211.39, 'break_pct': 4.84, 'timestamp': time.time()}
        ],
        fvgs=[],  # Empty for this demo
        order_blocks=[],  # Empty for this demo
        liquidity_sweeps=[],
        liquidity_pools=[],
        stop_hunt_warning=StopHuntWarning(
            is_stop_hunt_mode=True,
            severity=0.6,
            recommendation='Caution: Stop hunt activity detected',
            evidence=['Multiple liquidity sweeps detected', 'High sweep probability zones identified']
        ),
        range_trap=RangeTrapAnalysis(
            is_trapped=False,
            trap_severity=0.2,
            danger_level='LOW',
            recommendation='No range trap detected - safe to trade'
        ),
        confluence={'bullish_score': 45, 'bearish_score': 32},
        brain_decision=None
    )

    arsenal_file = f'arsenal_test_{timestamp_str}.json'
    arsenal_collector.export_data(arsenal_file)
    print(f'[OK] Arsenal data saved: {arsenal_file}')

    # Step 3: Run Validation
    print()
    print('[STEP 3/4] Running Hybrid Validation Analysis')
    print('-'*100)
    print()

    validator = HybridValidator()

    horus_snapshot = horus_collector.get_latest_snapshot()
    arsenal_snapshot = mock_snapshot

    if not horus_snapshot:
        print('ERROR: No Horus snapshot available - is Unified Processor running?')
        return None

    # Display snapshot info
    print(f'Horus Snapshot (from Unified Processor):')
    print(f'  Timestamp: {datetime.fromtimestamp(horus_snapshot.timestamp).strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  HTF Structure: {"Available" if horus_snapshot.htf_available else "Not Available"}')
    print(f'  Spectra Liquidity: {"Available" if horus_snapshot.spectra_available else "Not Available"}')
    print(f'  Heatmap Data: {"Available" if horus_snapshot.heatmap_available else "Not Available"}')
    print(f'  CVD: {horus_snapshot.cvd:.2f}')
    print(f'  Delta: {horus_snapshot.delta:.2f}')
    print(f'  Liquidity Score: {horus_snapshot.liquidity_score:.2f}')
    print(f'  Liquidity Zones: {len(horus_snapshot.liquidity_zones)}')
    print(f'  POC: ${horus_snapshot.point_of_control:.2f}')
    print(f'  Data Quality: {horus_snapshot.data_freshness_score:.0%}')
    print()

    print(f'Arsenal Snapshot (from Trendline System):')
    print(f'  Timestamp: {datetime.fromtimestamp(arsenal_snapshot.timestamp).strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  Price: ${arsenal_snapshot.current_price:.2f}')
    print(f'  Swing High: ${arsenal_snapshot.swing_high:.2f} ({arsenal_snapshot.swing_high_age} bars ago)')
    print(f'  Swing Low: ${arsenal_snapshot.swing_low:.2f} ({arsenal_snapshot.swing_low_age} bars ago)')
    print(f'  Patterns: {arsenal_snapshot.pattern_count}')
    print(f'  FVGs: {arsenal_snapshot.fvg_count}')
    print(f'  Order Blocks: {arsenal_snapshot.ob_count}')
    print(f'  Liquidity Pools: {arsenal_snapshot.untapped_pools_count}U / {arsenal_snapshot.tapped_pools_count}T')
    print(f'  Stop Hunt: {"ACTIVE" if arsenal_snapshot.stop_hunt_active else "INACTIVE"} ({arsenal_snapshot.stop_hunt_severity:.0%})')
    print(f'  Bias: {arsenal_snapshot.dominant_bias}')
    print()

    print('Performing 5-dimensional complementary analysis...')
    print()

    # Generate validation report
    report = validator.generate_validation_report(arsenal_snapshot, horus_snapshot)

    # Step 4: Display Results
    print()
    print('[STEP 4/4] VALIDATION RESULTS')
    print('='*100)
    print()

    # Overall result with visual indicator
    complementary_symbol = '[+]' if report.complementary else '[-]'
    print(f'{complementary_symbol} COMPLEMENTARY: {"YES" if report.complementary else "NO"}')
    print(f'  OVERALL SCORE: {report.overall_score:.1f}/100')
    print(f'  CONFIDENCE IN HYBRID: {report.confidence_in_hybrid:.0f}%')
    print(f'  RECOMMENDATION: {report.recommendation}')
    print()

    # Dimensional breakdown
    print('DETAILED BREAKDOWN (5 Validation Dimensions):')
    print('-'*100)
    print()

    dimensions = [
        ('1. FVG-Liquidity Alignment', report.fvg_liquidity_score),
        ('2. OB-Heatmap Alignment', report.ob_heatmap_score),
        ('3. Liquidity-CVD Correlation', report.liquidity_cvd_score),
        ('4. Pattern-Volume Correlation', report.pattern_volume_score),
        ('5. Bias Alignment', report.bias_score)
    ]

    for name, score in dimensions:
        symbol = '[+]' if score.is_complementary else '[-]'
        status = 'COMPLEMENTARY' if score.is_complementary else 'NOT COMPLEMENTARY'
        print(f'{symbol} {name}: {score.score:.1f}/100 [{status}]')
        print(f'   {score.details}')
        if score.findings:
            for finding in score.findings[:2]:  # Show top 2 findings
                print(f'   - {finding}')
        print()

    # Time synchronization
    print(f'Time Sync Quality: {report.time_sync_quality:.0%}')
    print(f'  Horus: {datetime.fromtimestamp(horus_snapshot.timestamp).strftime("%H:%M:%S")}')
    print(f'  Arsenal: {datetime.fromtimestamp(arsenal_snapshot.timestamp).strftime("%H:%M:%S")}')
    print(f'  Delta: {abs(horus_snapshot.timestamp - arsenal_snapshot.timestamp):.1f}s')
    print()

    # Export report
    report_file = f'hybrid_validation_report_{timestamp_str}.json'
    validator.export_report(report, report_file)
    print(f'[OK] Validation report saved: {report_file}')
    print()

    # Final summary
    print('='*100)
    print('HYBRID VALIDATION TEST COMPLETE')
    print('='*100)
    print()
    print(f'Files Generated:')
    print(f'  1. {horus_file} - Horus oracle data ({horus_collector.snapshots_received} snapshots)')
    print(f'  2. {arsenal_file} - Arsenal trendline data')
    print(f'  3. {report_file} - Comprehensive validation report')
    print()

    # Interpretation guidance
    print('INTERPRETATION:')
    print('-'*100)

    if report.overall_score >= 75:
        print('[EXCELLENT] Systems highly complementary')
        print('   Strong confidence in hybrid approach. Arsenal and Horus validate each other well.')
        print('   Recommended: Proceed with hybrid integration.')
    elif report.overall_score >= 60:
        print('[GOOD] Systems are complementary')
        print('   Hybrid approach recommended. Most validation dimensions align.')
        print('   Recommended: Use hybrid with standard confidence thresholds.')
    elif report.overall_score >= 45:
        print('[MODERATE] Partial complementarity')
        print('   Hybrid possible with caution. Review individual dimension scores.')
        print('   Recommended: Use hybrid with conservative position sizing.')
    else:
        print('[WEAK] Limited complementarity')
        print('   Systems show divergence. Further investigation needed.')
        print('   Recommended: Review why systems disagree before hybrid use.')

    print()
    print(f'Key Insight: {"These systems work well together!" if report.complementary else "These systems need alignment review."}')
    print()

    return report


if __name__ == '__main__':
    # Run the hybrid validation test
    print('\n')
    report = asyncio.run(run_hybrid_test())

    if report:
        print('\n[OK] Test completed successfully')
        print(f'  Overall complementary score: {report.overall_score:.0f}/100')
        print(f'  Hybrid confidence: {report.confidence_in_hybrid:.0f}%')
    else:
        print('\n[FAIL] Test failed - check if Unified Processor is running')
