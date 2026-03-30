"""
Hybrid Validator
================
Performs thorough side-by-side analysis of Arsenal and Horus systems
to determine if they complement each other.

Checks:
- Do Arsenal's FVG zones align with Horus liquidity zones?
- Do Arsenal's Order Blocks match Horus heatmap POC/walls?
- Does Arsenal's liquidity detection match Horus CVD/delta signals?
- Do patterns correlate with volume/exhaustion indicators?
- Overall complementary validation

They don't need to match 100%, just "almost match" to confirm they complement each other.
"""

import asyncio
import time
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

from horus_data_collector import HorusDataCollector, HorusDataSnapshot
from arsenal_data_collector import ArsenalDataSnapshot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('HYBRID_VALIDATOR')


@dataclass
class ValidationScore:
    """Score for a validation dimension"""
    dimension: str
    score: float  # 0-100
    details: str
    complementary: bool  # True if systems complement each other


@dataclass
class HybridValidationReport:
    """Complete validation report"""
    timestamp: float

    # Overall
    overall_complementary: bool
    overall_score: float  # 0-100

    # Individual validations
    fvg_liquidity_validation: ValidationScore
    ob_heatmap_validation: ValidationScore
    liquidity_cvd_validation: ValidationScore
    pattern_volume_validation: ValidationScore
    bias_alignment_validation: ValidationScore

    # Recommendations
    recommendation: str
    confidence_in_hybrid: float  # 0-100

    # Raw data references
    arsenal_snapshot_time: float
    horus_snapshot_time: float
    time_sync_quality: float  # How well synchronized the snapshots are


class HybridValidator:
    """
    Validates if Arsenal and Horus systems complement each other
    """

    def __init__(self):
        self.horus_collector = HorusDataCollector()

        # Validation thresholds
        self.COMPLEMENTARY_THRESHOLD = 60.0  # 60% match = complementary
        self.PRICE_TOLERANCE_PERCENT = 0.5  # 0.5% price difference acceptable

    async def initialize(self):
        """Initialize connection to Horus"""
        logger.info("="*80)
        logger.info("HYBRID VALIDATOR - INITIALIZING")
        logger.info("="*80)

        # Connect to Horus Unified Processor
        success = await self.horus_collector.connect()
        if not success:
            logger.error("Failed to connect to Horus system")
            return False

        logger.info("Hybrid validator initialized successfully")
        return True

    async def collect_horus_snapshot(self, duration_seconds: int = 5) -> Optional[HorusDataSnapshot]:
        """Collect a fresh Horus snapshot"""
        logger.info("Collecting Horus data snapshot...")

        # Start collecting
        start_time = time.time()

        # Give it some time to receive data
        await asyncio.sleep(duration_seconds)

        # Get latest snapshot
        snapshot = self.horus_collector.get_latest_snapshot()

        if snapshot:
            logger.info(f"Horus snapshot collected (age: {time.time() - snapshot.timestamp:.1f}s)")
        else:
            logger.warning("No Horus snapshot available")

        return snapshot

    def validate_fvg_liquidity_alignment(self,
                                        arsenal: ArsenalDataSnapshot,
                                        horus: HorusDataSnapshot) -> ValidationScore:
        """
        Check if Arsenal's FVG zones align with Horus liquidity zones
        """
        score = 0.0
        matches = []

        # Get Arsenal FVGs
        all_fvgs = arsenal.bullish_fvgs + arsenal.bearish_fvgs

        if not all_fvgs:
            return ValidationScore(
                dimension="FVG-Liquidity Alignment",
                score=50.0,  # Neutral - no FVGs to validate
                details="No Arsenal FVGs detected to validate",
                complementary=True  # Not contradictory
            )

        # Get Horus liquidity zones
        horus_zones = horus.liquidity_zones

        if not horus_zones:
            return ValidationScore(
                dimension="FVG-Liquidity Alignment",
                score=50.0,
                details="No Horus liquidity zones detected to validate",
                complementary=True
            )

        # Check each FVG against liquidity zones
        for fvg in all_fvgs[:5]:  # Check top 5 FVGs
            fvg_mid = (fvg['gap_start'] + fvg['gap_end']) / 2

            for zone in horus_zones:
                zone_level = zone.get('level', zone.get('price', 0))
                if zone_level == 0:
                    continue

                # Check if zone is within FVG range
                tolerance = fvg_mid * (self.PRICE_TOLERANCE_PERCENT / 100)

                if abs(zone_level - fvg_mid) <= tolerance:
                    matches.append(f"FVG @ ${fvg_mid:.2f} matches Horus zone @ ${zone_level:.2f}")
                    score += 20.0  # Each match adds 20 points

        # Cap at 100
        score = min(100.0, score)

        # Complementary if score > threshold
        complementary = score >= self.COMPLEMENTARY_THRESHOLD

        details = f"{len(matches)} FVG-liquidity alignments found. " + "; ".join(matches[:3])

        return ValidationScore(
            dimension="FVG-Liquidity Alignment",
            score=score,
            details=details,
            complementary=complementary
        )

    def validate_ob_heatmap_alignment(self,
                                     arsenal: ArsenalDataSnapshot,
                                     horus: HorusDataSnapshot) -> ValidationScore:
        """
        Check if Arsenal's Order Blocks match Horus heatmap POC/walls
        """
        score = 0.0
        matches = []

        # Get Arsenal OBs
        all_obs = arsenal.bullish_obs + arsenal.bearish_obs

        if not all_obs:
            return ValidationScore(
                dimension="OB-Heatmap Alignment",
                score=50.0,
                details="No Arsenal Order Blocks detected",
                complementary=True
            )

        # Get Horus heatmap key levels
        poc = horus.point_of_control
        vah = horus.value_area_high
        val = horus.value_area_low

        heatmap_levels = [level for level in [poc, vah, val] if level > 0]

        if not heatmap_levels:
            return ValidationScore(
                dimension="OB-Heatmap Alignment",
                score=50.0,
                details="No Horus heatmap levels detected",
                complementary=True
            )

        # Check each OB against heatmap levels
        for ob in all_obs[:5]:  # Check top 5 OBs
            ob_mid = (ob['low'] + ob['high']) / 2
            tolerance = ob_mid * (self.PRICE_TOLERANCE_PERCENT / 100)

            for level in heatmap_levels:
                if abs(level - ob_mid) <= tolerance:
                    level_name = "POC" if level == poc else "VAH" if level == vah else "VAL"
                    matches.append(f"OB @ ${ob_mid:.2f} matches {level_name} @ ${level:.2f}")
                    score += 25.0

        score = min(100.0, score)
        complementary = score >= self.COMPLEMENTARY_THRESHOLD

        details = f"{len(matches)} OB-heatmap alignments found. " + "; ".join(matches[:3])

        return ValidationScore(
            dimension="OB-Heatmap Alignment",
            score=score,
            details=details,
            complementary=complementary
        )

    def validate_liquidity_cvd_correlation(self,
                                          arsenal: ArsenalDataSnapshot,
                                          horus: HorusDataSnapshot) -> ValidationScore:
        """
        Check if Arsenal's liquidity detection correlates with Horus CVD/delta
        """
        score = 50.0  # Start neutral
        details = []

        # Arsenal liquidity analysis
        arsenal_bullish_bias = arsenal.bullish_confluence > arsenal.bearish_confluence
        arsenal_bias_strength = abs(arsenal.bullish_confluence - arsenal.bearish_confluence)

        # Horus CVD analysis
        horus_cvd = horus.cvd
        horus_delta = horus.delta
        horus_bullish_bias = horus_delta > 0

        # Check if biases align
        biases_align = arsenal_bullish_bias == horus_bullish_bias

        if biases_align:
            score += 30.0
            bias_dir = "BULLISH" if arsenal_bullish_bias else "BEARISH"
            details.append(f"Both systems show {bias_dir} bias")
        else:
            score -= 20.0
            details.append(f"Arsenal: {'BULLISH' if arsenal_bullish_bias else 'BEARISH'}, "
                         f"Horus CVD: {'BULLISH' if horus_bullish_bias else 'BEARISH'}")

        # Check liquidity pools vs CVD
        if arsenal.untapped_pools_count > 0:
            # More untapped pools above = bullish target, should see buying pressure
            if horus.delta > 0:
                score += 20.0
                details.append("Untapped pools correlate with positive delta")

        # Cap score
        score = max(0.0, min(100.0, score))
        complementary = score >= self.COMPLEMENTARY_THRESHOLD

        details_str = "; ".join(details) if details else "Limited correlation data"

        return ValidationScore(
            dimension="Liquidity-CVD Correlation",
            score=score,
            details=details_str,
            complementary=complementary
        )

    def validate_pattern_volume_correlation(self,
                                           arsenal: ArsenalDataSnapshot,
                                           horus: HorusDataSnapshot) -> ValidationScore:
        """
        Check if Arsenal patterns correlate with Horus volume/exhaustion
        """
        score = 50.0
        details = []

        # Check if Arsenal detected any breakout patterns
        patterns = arsenal.patterns
        has_breakout_pattern = any('break' in p.get('type', '').lower() for p in patterns)

        # Check Horus exhaustion
        exhaustion_score = horus.exhaustion_score
        exhaustion_type = horus.exhaustion_type

        if has_breakout_pattern:
            if exhaustion_type in ['bullish_exhaustion', 'bearish_exhaustion']:
                # Pattern at exhaustion = potential reversal
                score += 25.0
                details.append(f"Pattern detected at {exhaustion_type} zone")
            else:
                # Pattern with no exhaustion = momentum continuation
                score += 15.0
                details.append("Pattern detected with momentum")

        # Check liquidity score
        liquidity_score = horus.liquidity_score
        if liquidity_score > 0.7:
            score += 15.0
            details.append(f"High liquidity ({liquidity_score:.0%}) supports moves")

        score = min(100.0, score)
        complementary = score >= self.COMPLEMENTARY_THRESHOLD

        details_str = "; ".join(details) if details else "Limited pattern-volume data"

        return ValidationScore(
            dimension="Pattern-Volume Correlation",
            score=score,
            details=details_str,
            complementary=complementary
        )

    def validate_bias_alignment(self,
                               arsenal: ArsenalDataSnapshot,
                               horus: HorusDataSnapshot) -> ValidationScore:
        """
        Overall bias alignment check
        """
        score = 50.0
        details = []

        # Arsenal bias
        arsenal_bias = arsenal.dominant_bias
        arsenal_has_decision = arsenal.brain_should_trade

        # Horus structure (if available)
        horus_available = horus.htf_available and horus.spectra_available

        if not horus_available:
            return ValidationScore(
                dimension="Bias Alignment",
                score=50.0,
                details="Horus data not fully available",
                complementary=True
            )

        # Check CVD direction
        horus_bias = "BULLISH" if horus.delta > 0 else "BEARISH" if horus.delta < 0 else "NEUTRAL"

        if arsenal_bias == horus_bias:
            score += 40.0
            details.append(f"Both systems agree: {arsenal_bias}")
        elif arsenal_bias == "NEUTRAL" or horus_bias == "NEUTRAL":
            score += 10.0
            details.append("One system neutral, not contradictory")
        else:
            score -= 20.0
            details.append(f"Bias disagreement: Arsenal={arsenal_bias}, Horus={horus_bias}")

        # Check quality
        if horus.sync_quality > 0.8 and arsenal.analysis_quality > 0.8:
            score += 10.0
            details.append("Both systems high quality")

        score = max(0.0, min(100.0, score))
        complementary = score >= self.COMPLEMENTARY_THRESHOLD

        return ValidationScore(
            dimension="Bias Alignment",
            score=score,
            details="; ".join(details),
            complementary=complementary
        )

    def generate_validation_report(self,
                                  arsenal: ArsenalDataSnapshot,
                                  horus: HorusDataSnapshot) -> HybridValidationReport:
        """
        Generate complete validation report
        """
        logger.info("="*80)
        logger.info("GENERATING VALIDATION REPORT")
        logger.info("="*80)

        # Run all validations
        fvg_liquidity = self.validate_fvg_liquidity_alignment(arsenal, horus)
        ob_heatmap = self.validate_ob_heatmap_alignment(arsenal, horus)
        liquidity_cvd = self.validate_liquidity_cvd_correlation(arsenal, horus)
        pattern_volume = self.validate_pattern_volume_correlation(arsenal, horus)
        bias_alignment = self.validate_bias_alignment(arsenal, horus)

        # Calculate overall score
        all_scores = [
            fvg_liquidity.score,
            ob_heatmap.score,
            liquidity_cvd.score,
            pattern_volume.score,
            bias_alignment.score
        ]

        overall_score = sum(all_scores) / len(all_scores)

        # Overall complementary if most dimensions are complementary
        complementary_count = sum([
            fvg_liquidity.complementary,
            ob_heatmap.complementary,
            liquidity_cvd.complementary,
            pattern_volume.complementary,
            bias_alignment.complementary
        ])

        overall_complementary = complementary_count >= 3  # At least 3 of 5

        # Generate recommendation
        if overall_score >= 75:
            recommendation = "EXCELLENT - Systems highly complementary. Strong confidence in hybrid approach."
            confidence = 90.0
        elif overall_score >= 60:
            recommendation = "GOOD - Systems complement each other well. Hybrid approach recommended."
            confidence = 75.0
        elif overall_score >= 45:
            recommendation = "MODERATE - Systems show some complementary signals. Hybrid approach possible with caution."
            confidence = 55.0
        else:
            recommendation = "WEAK - Systems show limited complementary behavior. Further investigation needed."
            confidence = 30.0

        # Time sync quality
        time_diff = abs(arsenal.timestamp - horus.timestamp)
        time_sync_quality = max(0, 100 - (time_diff * 10))  # 10% penalty per second

        report = HybridValidationReport(
            timestamp=time.time(),
            overall_complementary=overall_complementary,
            overall_score=overall_score,
            fvg_liquidity_validation=fvg_liquidity,
            ob_heatmap_validation=ob_heatmap,
            liquidity_cvd_validation=liquidity_cvd,
            pattern_volume_validation=pattern_volume,
            bias_alignment_validation=bias_alignment,
            recommendation=recommendation,
            confidence_in_hybrid=confidence,
            arsenal_snapshot_time=arsenal.timestamp,
            horus_snapshot_time=horus.timestamp,
            time_sync_quality=time_sync_quality
        )

        return report

    def print_validation_report(self, report: HybridValidationReport):
        """Print detailed validation report"""
        logger.info("="*80)
        logger.info("HYBRID VALIDATION REPORT")
        logger.info("="*80)
        logger.info(f"Timestamp: {datetime.fromtimestamp(report.timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Time Sync Quality: {report.time_sync_quality:.0f}%")
        logger.info("")

        logger.info(f"OVERALL SCORE: {report.overall_score:.1f}/100")
        logger.info(f"COMPLEMENTARY: {'YES' if report.overall_complementary else 'NO'}")
        logger.info(f"CONFIDENCE IN HYBRID: {report.confidence_in_hybrid:.0f}%")
        logger.info("")

        logger.info("DETAILED VALIDATION:")
        logger.info("-" * 80)

        validations = [
            report.fvg_liquidity_validation,
            report.ob_heatmap_validation,
            report.liquidity_cvd_validation,
            report.pattern_volume_validation,
            report.bias_alignment_validation
        ]

        for val in validations:
            status = "COMPLEMENTARY" if val.complementary else "NOT COMPLEMENTARY"
            logger.info(f"\n{val.dimension}: {val.score:.1f}/100 [{status}]")
            logger.info(f"  {val.details}")

        logger.info("")
        logger.info("="*80)
        logger.info("RECOMMENDATION:")
        logger.info(report.recommendation)
        logger.info("="*80)

    def export_report(self, report: HybridValidationReport, filepath: str):
        """Export report to JSON"""
        try:
            # Convert to dict
            report_dict = {
                'timestamp': report.timestamp,
                'overall_complementary': report.overall_complementary,
                'overall_score': report.overall_score,
                'confidence_in_hybrid': report.confidence_in_hybrid,
                'recommendation': report.recommendation,
                'time_sync_quality': report.time_sync_quality,
                'validations': {
                    'fvg_liquidity': {
                        'score': report.fvg_liquidity_validation.score,
                        'complementary': report.fvg_liquidity_validation.complementary,
                        'details': report.fvg_liquidity_validation.details
                    },
                    'ob_heatmap': {
                        'score': report.ob_heatmap_validation.score,
                        'complementary': report.ob_heatmap_validation.complementary,
                        'details': report.ob_heatmap_validation.details
                    },
                    'liquidity_cvd': {
                        'score': report.liquidity_cvd_validation.score,
                        'complementary': report.liquidity_cvd_validation.complementary,
                        'details': report.liquidity_cvd_validation.details
                    },
                    'pattern_volume': {
                        'score': report.pattern_volume_validation.score,
                        'complementary': report.pattern_volume_validation.complementary,
                        'details': report.pattern_volume_validation.details
                    },
                    'bias_alignment': {
                        'score': report.bias_alignment_validation.score,
                        'complementary': report.bias_alignment_validation.complementary,
                        'details': report.bias_alignment_validation.details
                    }
                }
            }

            with open(filepath, 'w') as f:
                json.dump(report_dict, f, indent=2)

            logger.info(f"Report exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            return False


async def main():
    """
    Main validation workflow

    NOTE: This script expects:
    1. Horus Unified Processor running on ws://localhost:8899/integrator
    2. Arsenal system running and collecting data via arsenal_data_collector

    For this test, you'll need to integrate arsenal_data_collector into
    the live Arsenal system to provide snapshots.
    """

    validator = HybridValidator()

    # Initialize
    if not await validator.initialize():
        logger.error("Failed to initialize validator")
        return

    logger.info("")
    logger.info("="*80)
    logger.info("NOTE: This validation requires:")
    logger.info("1. Horus Unified Processor running (ws://localhost:8899/integrator)")
    logger.info("2. Arsenal system running with data collection enabled")
    logger.info("="*80)
    logger.info("")

    # Start Horus collection
    asyncio.create_task(validator.horus_collector.collect_data())

    # Wait for some data
    logger.info("Waiting for data collection (30 seconds)...")
    await asyncio.sleep(30)

    # Get Horus snapshot
    horus_snapshot = validator.horus_collector.get_latest_snapshot()

    if not horus_snapshot:
        logger.error("No Horus data available")
        return

    logger.info(f"Horus snapshot collected: {horus_snapshot.htf_available=}, {horus_snapshot.spectra_available=}")

    # For this demo, we need an Arsenal snapshot
    # In production, this would come from the integrated Arsenal collector
    logger.info("")
    logger.info("="*80)
    logger.info("TO COMPLETE VALIDATION:")
    logger.info("Arsenal snapshot needs to be provided by integrated collector")
    logger.info("See arsenal_data_collector.py for integration instructions")
    logger.info("="*80)

    # Export Horus data
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    horus_file = f"horus_data_{timestamp}.json"
    validator.horus_collector.export_data(horus_file)

    logger.info(f"\nHorus data exported to: {horus_file}")
    logger.info("Once Arsenal collector is integrated, run validation again")


if __name__ == "__main__":
    asyncio.run(main())
