"""
Horus Data Collector
====================
Connects to the running Unified Oracle Processor and collects all raw data:
- HTF Structure (FVGs, Order Blocks, BOS, CHoCH, Structure)
- Spectra Liquidity (CVD, Volume Delta, Liquidity Zones)
- Heatmap (Liquidity concentration, walls, POC)
- Exhaustion Analysis
- Calibration Data

This data will be used for hybrid validation with Arsenal system.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('HORUS_COLLECTOR')


@dataclass
class HorusDataSnapshot:
    """Complete snapshot of Horus system data at a point in time"""
    timestamp: float

    # HTF Structure Data
    htf_structure: Dict[str, Any]
    htf_available: bool

    # Spectra Liquidity Data
    spectra_liquidity: Dict[str, Any]
    spectra_available: bool
    cvd: float
    delta: float
    liquidity_score: float

    # Heatmap Data
    heatmap_data: Dict[str, Any]
    heatmap_available: bool
    liquidity_zones: List[Dict]
    point_of_control: float
    value_area_high: float
    value_area_low: float

    # Exhaustion Analysis
    exhaustion_analysis: Dict[str, Any]
    exhaustion_available: bool
    exhaustion_score: float
    exhaustion_type: str

    # Calibration
    calibration: Dict[str, Any]
    calibration_available: bool

    # Data Quality
    data_freshness_score: float
    sync_quality: float

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class HorusDataCollector:
    """
    Collects real-time data from Horus Unified Oracle Processor
    """

    def __init__(self):
        self.url = 'ws://localhost:8899/integrator'
        self.ws = None
        self.session = None
        self.connected = False

        # Data storage
        self.latest_snapshot: Optional[HorusDataSnapshot] = None
        self.snapshot_history = deque(maxlen=1000)  # Keep last 1000 snapshots

        # Statistics
        self.snapshots_received = 0
        self.connection_time = None

    async def collect_data(self, duration_seconds: Optional[int] = None):
        """
        Connect to Unified Processor and collect data

        Uses the same proven connection pattern as the dashboard backend.

        Args:
            duration_seconds: How long to collect (None = forever)
        """
        logger.info("="*80)
        logger.info("HORUS DATA COLLECTOR - STARTING")
        logger.info("="*80)

        if duration_seconds:
            logger.info(f"Will collect for {duration_seconds} seconds")
        else:
            logger.info("Collecting indefinitely (Ctrl+C to stop)")

        start_time = time.time()
        self.connection_time = start_time

        try:
            # Use context managers like the working dashboard backend
            async with aiohttp.ClientSession() as session:
                logger.info(f"Connecting to Unified Processor at {self.url}...")

                async with session.ws_connect(self.url) as ws:
                    logger.info("✓ Connected to Unified Processor!")
                    self.connected = True

                    # Send authentication
                    auth = {
                        "type": "authenticate",
                        "client_type": "hybrid_validator",
                        "timestamp": time.time()
                    }
                    await ws.send_str(json.dumps(auth))
                    logger.info("✓ Authenticated as hybrid_validator client")
                    logger.info("="*80)
                    logger.info("Listening for data...")

                    # Message loop - exactly like dashboard backend
                    message_count = 0
                    async for msg in ws:
                        message_count += 1

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            msg_type = data.get('type', 'unknown')

                            # Debug: Log first 5 messages to see what we're getting
                            if message_count <= 5:
                                logger.info(f"[DEBUG] Message #{message_count}: type='{msg_type}', keys={list(data.keys())[:10]}")

                            await self._process_message(data)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f'WebSocket error: {ws.exception()}')
                            break

                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logger.warning("WebSocket closed by server")
                            break

                        # Check duration
                        if duration_seconds:
                            elapsed = time.time() - start_time
                            if elapsed >= duration_seconds:
                                logger.info(f"Collection duration reached ({duration_seconds}s)")
                                logger.info(f"Total messages received: {message_count}")
                                break

        except KeyboardInterrupt:
            logger.info("\nCollection stopped by user")
        except Exception as e:
            logger.error(f"Error during collection: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            self.connected = False

    async def _process_message(self, message: Dict):
        """Process incoming message from Unified Processor"""
        try:
            # Check if this is a unified data message
            # The Unified Processor sends messages with oracle data fields directly,
            # not with a 'type' field like the dashboard expected
            has_oracle_data = (
                'htf_structure' in message or
                'spectra_liquidity' in message or
                'heatmap_data' in message or
                'calibration_analysis' in message
            )

            if has_oracle_data:
                # Extract all data
                htf_data = message.get('htf_structure', {})
                spectra_data = message.get('spectra_liquidity', {})
                heatmap_data = message.get('heatmap_data', {})
                exhaustion_data = message.get('exhaustion_analysis', {})
                calibration_data = message.get('calibration_analysis', {})

                snapshot = HorusDataSnapshot(
                    timestamp=message.get('timestamp', time.time()),

                    # HTF Structure
                    htf_structure=htf_data,
                    htf_available=bool(htf_data and htf_data.get('timestamp')),

                    # Spectra Liquidity
                    spectra_liquidity=spectra_data,
                    spectra_available=bool(spectra_data and spectra_data.get('timestamp')),
                    cvd=self._extract_cvd(spectra_data),
                    delta=self._extract_delta(spectra_data),
                    liquidity_score=self._extract_liquidity_score(spectra_data),

                    # Heatmap
                    heatmap_data=heatmap_data,
                    heatmap_available=bool(heatmap_data and heatmap_data.get('timestamp')),
                    liquidity_zones=self._extract_liquidity_zones(heatmap_data),
                    point_of_control=self._extract_poc(heatmap_data),
                    value_area_high=self._extract_vah(heatmap_data),
                    value_area_low=self._extract_val(heatmap_data),

                    # Exhaustion
                    exhaustion_analysis=exhaustion_data,
                    exhaustion_available=bool(exhaustion_data and exhaustion_data.get('timestamp')),
                    exhaustion_score=self._extract_exhaustion_score(exhaustion_data),
                    exhaustion_type=self._extract_exhaustion_type(exhaustion_data),

                    # Calibration
                    calibration=calibration_data,
                    calibration_available=bool(calibration_data and calibration_data.get('timestamp')),

                    # Quality - calculate from available data
                    data_freshness_score=self._calculate_freshness(message),
                    sync_quality=self._calculate_sync_quality(message)
                )

                # Store snapshot
                self.latest_snapshot = snapshot
                self.snapshot_history.append(snapshot)
                self.snapshots_received += 1

                # Log every 10 snapshots
                if self.snapshots_received % 10 == 0:
                    logger.info(f"Collected {self.snapshots_received} snapshots | "
                              f"CVD: {snapshot.cvd:.2f} | "
                              f"Liquidity Zones: {len(snapshot.liquidity_zones)} | "
                              f"Quality: {snapshot.data_freshness_score:.0%}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _extract_cvd(self, spectra_data: Dict) -> float:
        """Extract CVD strength from Spectra data"""
        if 'cvd' in spectra_data:
            cvd_obj = spectra_data['cvd']
            if isinstance(cvd_obj, dict):
                # Try strength first (0-1 scale)
                return cvd_obj.get('strength', cvd_obj.get('cumulative_value', 0.0))
            return cvd_obj  # If it's already a float
        return 0.0

    def _extract_delta(self, spectra_data: Dict) -> float:
        """Extract volume delta from Spectra data"""
        if 'cvd' in spectra_data:
            cvd_obj = spectra_data['cvd']
            if isinstance(cvd_obj, dict):
                # Get 1h volume delta
                return cvd_obj.get('volume_delta_1h', cvd_obj.get('volume_delta_4h', 0.0))
        return 0.0

    def _extract_liquidity_score(self, spectra_data: Dict) -> float:
        """Extract liquidity score from Spectra data"""
        # Try multiple possible locations
        if 'liquidity_heatmap' in spectra_data:
            heatmap = spectra_data['liquidity_heatmap']
            if isinstance(heatmap, dict):
                return heatmap.get('liquidity_score', 0.0)
        if 'analysis_confidence' in spectra_data:
            return spectra_data['analysis_confidence']
        return 0.0

    def _extract_liquidity_zones(self, heatmap_data: Dict) -> List[Dict]:
        """Extract liquidity zones from heatmap"""
        # Try multiple possible keys
        zones = heatmap_data.get('liquidity_zones', [])
        if not zones and 'liquidity_heatmap' in heatmap_data:
            heatmap = heatmap_data['liquidity_heatmap']
            if isinstance(heatmap, dict):
                zones = heatmap.get('zones', [])
        return zones if zones else []

    def _extract_poc(self, heatmap_data: Dict) -> float:
        """Extract Point of Control from liquidity heatmap"""
        # Try direct field
        poc = heatmap_data.get('point_of_control', 0.0)
        if poc == 0.0 and 'liquidity_heatmap' in heatmap_data:
            heatmap = heatmap_data.get('liquidity_heatmap', {})
            if isinstance(heatmap, dict):
                poc = heatmap.get('poc', heatmap.get('point_of_control', 0.0))
        return poc

    def _extract_vah(self, heatmap_data: Dict) -> float:
        """Extract Value Area High"""
        vah = heatmap_data.get('value_area_high', 0.0)
        if vah == 0.0 and 'liquidity_heatmap' in heatmap_data:
            heatmap = heatmap_data.get('liquidity_heatmap', {})
            if isinstance(heatmap, dict):
                vah = heatmap.get('vah', heatmap.get('value_area_high', 0.0))
        return vah

    def _extract_val(self, heatmap_data: Dict) -> float:
        """Extract Value Area Low"""
        val = heatmap_data.get('value_area_low', 0.0)
        if val == 0.0 and 'liquidity_heatmap' in heatmap_data:
            heatmap = heatmap_data.get('liquidity_heatmap', {})
            if isinstance(heatmap, dict):
                val = heatmap.get('val', heatmap.get('value_area_low', 0.0))
        return val

    def _extract_exhaustion_score(self, exhaustion_data: Dict) -> float:
        """Extract exhaustion score"""
        return exhaustion_data.get('score', 0.0)

    def _extract_exhaustion_type(self, exhaustion_data: Dict) -> str:
        """Extract exhaustion type"""
        return exhaustion_data.get('type', 'none')

    def _calculate_freshness(self, message: Dict) -> float:
        """Calculate data freshness score based on available timestamps"""
        current_time = time.time()
        freshness_scores = []

        # Check each data source's timestamp
        for key in ['htf_timestamp', 'spectra_timestamp', 'heatmap_timestamp',
                    'exhaustion_timestamp', 'calibration_timestamp']:
            if key in message:
                timestamp = message[key]
                age = current_time - timestamp
                # Fresh if less than 60 seconds old
                freshness = max(0.0, 1.0 - (age / 60.0))
                freshness_scores.append(freshness)

        return sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.0

    def _calculate_sync_quality(self, message: Dict) -> float:
        """Calculate synchronization quality across all data sources"""
        timestamps = []

        for key in ['htf_timestamp', 'spectra_timestamp', 'heatmap_timestamp',
                    'exhaustion_timestamp', 'calibration_timestamp']:
            if key in message:
                timestamps.append(message[key])

        if len(timestamps) < 2:
            return 0.0

        # Calculate spread of timestamps
        spread = max(timestamps) - min(timestamps)
        # Good sync if all within 5 seconds
        sync_quality = max(0.0, 1.0 - (spread / 5.0))

        return sync_quality

    def get_collection_summary(self):
        """Get summary of data collection"""
        logger.info("="*80)
        logger.info("COLLECTION COMPLETE")
        logger.info("="*80)
        logger.info(f"Total snapshots collected: {self.snapshots_received}")

        if self.connection_time:
            duration = time.time() - self.connection_time
            logger.info(f"Collection duration: {duration:.1f}s")
            if duration > 0:
                rate = self.snapshots_received / duration
                logger.info(f"Average rate: {rate:.2f} snapshots/second")

    def get_latest_snapshot(self) -> Optional[HorusDataSnapshot]:
        """Get the most recent data snapshot"""
        return self.latest_snapshot

    def get_snapshot_history(self, count: int = 100) -> List[HorusDataSnapshot]:
        """Get recent snapshot history"""
        return list(self.snapshot_history)[-count:]

    def export_data(self, filepath: str):
        """Export collected data to JSON file"""
        try:
            data = {
                'collection_info': {
                    'total_snapshots': self.snapshots_received,
                    'connection_time': self.connection_time,
                    'collection_duration': time.time() - self.connection_time if self.connection_time else 0
                },
                'latest_snapshot': self.latest_snapshot.to_dict() if self.latest_snapshot else None,
                'snapshot_history': [s.to_dict() for s in self.snapshot_history]
            }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"✓ Data exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"✗ Export failed: {e}")
            return False


async def main():
    """Main entry point for standalone collection"""
    collector = HorusDataCollector()

    # Collect data for 60 seconds (or until Ctrl+C)
    # Connection happens automatically inside collect_data()
    try:
        await collector.collect_data(duration_seconds=60)
    except KeyboardInterrupt:
        logger.info("\nStopped by user")

    # Show collection summary
    collector.get_collection_summary()

    # Export data
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"horus_data_{timestamp}.json"
    collector.export_data(filename)

    # Show detailed snapshot summary
    logger.info("="*80)
    logger.info("LATEST SNAPSHOT DETAILS")
    logger.info("="*80)

    if collector.latest_snapshot:
        snapshot = collector.latest_snapshot
        logger.info(f"CVD: {snapshot.cvd:.2f}")
        logger.info(f"Delta: {snapshot.delta:.2f}")
        logger.info(f"Liquidity Score: {snapshot.liquidity_score:.2f}")
        logger.info(f"Liquidity Zones: {len(snapshot.liquidity_zones)}")
        logger.info(f"POC: ${snapshot.point_of_control:.2f}")
        logger.info(f"VAH: ${snapshot.value_area_high:.2f}")
        logger.info(f"VAL: ${snapshot.value_area_low:.2f}")
        logger.info(f"Exhaustion: {snapshot.exhaustion_type} ({snapshot.exhaustion_score:.0%})")
        logger.info(f"Data Quality: {snapshot.data_freshness_score:.0%}")
        logger.info(f"Sync Quality: {snapshot.sync_quality:.0%}")
    else:
        logger.warning("No snapshots collected!")


if __name__ == "__main__":
    asyncio.run(main())
