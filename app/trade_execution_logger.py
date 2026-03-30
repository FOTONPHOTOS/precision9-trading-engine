"""
Trade Execution Logger - Comprehensive Signal Detail Capture
Records all confluence factors, market data, and reasoning at trade execution for pattern analysis

Purpose:
- Track winning vs losing trade patterns
- Identify high-probability confluence combinations
- Enable data-driven calibration improvements over time
"""

import json
import csv
import redis.asyncio as redis
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import aiofiles


@dataclass
class TradeExecutionSnapshot:
    """Complete snapshot of all data at trade execution moment"""

    # Trade Identity
    signal_id: str
    timestamp: float
    symbol: str
    direction: str  # LONG or SHORT

    # Entry Details
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    position_size: float
    leverage: int
    risk_reward_ratio: float

    # Signal Quality
    confidence: float  # 0.0 to 1.0
    confluence_score: int  # Out of 100
    primary_reason: str
    supporting_factors: List[str]
    risk_factors: List[str]

    # Confluence Breakdown (showing exact points from each factor)
    confluence_breakdown: Dict[str, int]  # e.g., {"choch_detection": 25, "liquidity_bias": 15, ...}

    # Liquidity Analysis at Execution
    liquidity_snapshot: Dict[str, Any]  # From liquidity_directional_analyzer
    # Contains: buy_liquidity, sell_liquidity, imbalance, walls, voids, confidence

    # Structural Analysis at Execution
    structural_snapshot: Dict[str, Any]
    # Contains: choch_age, bos_status, trend, market_regime, structure_bias

    # CVD Analysis at Execution (Multi-Timeframe)
    cvd_snapshot: Dict[str, Any]
    # Contains: cvd_15m, cvd_1h, cvd_4h, cvd_trend, divergence_detected

    # Exhaustion Analysis
    exhaustion_snapshot: Dict[str, Any]
    # Contains: exhaustion_score, reversal_probability, risk_multiplier

    # Market Conditions
    market_conditions: Dict[str, Any]
    # Contains: volatility, liquidity_quality, session, price_action

    # Trade Outcome (updated after closure)
    outcome: Optional[str] = None  # "TP1", "TP2", "TP3", "STOPPED_OUT", "PENDING"
    pnl_percent: Optional[float] = None
    pnl_usd: Optional[float] = None
    duration_minutes: Optional[int] = None
    closed_at: Optional[float] = None

    # Pattern Analysis Metadata
    win_probability: Optional[float] = None  # Calculated from historical patterns
    similar_trades_count: Optional[int] = None
    pattern_match_score: Optional[float] = None


class TradeExecutionLogger:
    """
    Logs comprehensive trade execution details for pattern analysis

    Storage Strategy:
    1. Redis: Real-time access, recent trades (7 days)
    2. JSON File: Long-term storage, all trades
    3. Analysis Cache: Pre-computed pattern statistics
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_client: Optional[redis.Redis] = None

        # Storage paths
        self.log_dir = Path(__file__).parent / "trade_logs"
        self.log_dir.mkdir(exist_ok=True)

        self.trades_file = self.log_dir / "trade_executions.jsonl"  # JSON Lines format
        self.json_file = self.log_dir / "trade_executions.json"  # Standard JSON array
        self.csv_file = self.log_dir / "trade_executions.csv"  # CSV format for Excel
        self.csv_detailed_file = self.log_dir / "trade_executions_detailed.csv"  # Detailed CSV
        self.analysis_cache = self.log_dir / "pattern_analysis_cache.json"

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = await redis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            print("[TradeLogger] Connected to Redis")
        except Exception as e:
            print(f"[TradeLogger] Redis connection failed: {e}")
            self.redis_client = None

    async def log_execution(self, snapshot: TradeExecutionSnapshot) -> bool:
        """
        Log trade execution snapshot

        Stores to:
        1. Redis key: horus:trade:{signal_id} (expires in 7 days)
        2. JSON Lines file for permanent storage

        Returns: True if logged successfully
        """
        try:
            snapshot_dict = asdict(snapshot)
            snapshot_json = json.dumps(snapshot_dict, indent=2)

            # Store to Redis (7 day expiry)
            if self.redis_client:
                redis_key = f"horus:trade:{snapshot.signal_id}"
                await self.redis_client.setex(
                    redis_key,
                    7 * 24 * 60 * 60,  # 7 days
                    snapshot_json
                )

                # Add to sorted set for time-based queries
                await self.redis_client.zadd(
                    "horus:trade_timeline",
                    {snapshot.signal_id: snapshot.timestamp}
                )

                print(f"[TradeLogger] Logged to Redis: {snapshot.signal_id}")

            # 1. Append to JSON Lines file (permanent storage - one line per trade)
            async with aiofiles.open(self.trades_file, mode='a') as f:
                await f.write(snapshot_json + '\n')

            # 2. Update standard JSON array file (for offline analysis tools)
            await self._update_json_array(snapshot_dict)

            # 3. Append to CSV file (for Excel/spreadsheet analysis)
            await self._append_to_csv(snapshot_dict)

            # 4. Append to detailed CSV (flattened nested data)
            await self._append_to_detailed_csv(snapshot_dict)

            print(f"[TradeLogger] Logged trade execution: {snapshot.direction} @ ${snapshot.entry_price:.2f}")
            print(f"  Confluence: {snapshot.confluence_score}/100, Confidence: {snapshot.confidence*100:.1f}%")
            print(f"  Primary Reason: {snapshot.primary_reason}")
            print(f"  Files: JSON, JSONL, CSV, Detailed CSV")

            return True

        except Exception as e:
            print(f"[TradeLogger] Error logging execution: {e}")
            return False

    async def _update_json_array(self, snapshot_dict: Dict):
        """Update standard JSON array file (for offline tools)"""
        try:
            # Read existing trades
            trades = []
            if self.json_file.exists():
                async with aiofiles.open(self.json_file, mode='r') as f:
                    content = await f.read()
                    if content.strip():
                        trades = json.loads(content)

            # Append new trade
            trades.append(snapshot_dict)

            # Write back
            async with aiofiles.open(self.json_file, mode='w') as f:
                await f.write(json.dumps(trades, indent=2))

        except Exception as e:
            print(f"[TradeLogger] Error updating JSON array: {e}")

    async def _append_to_csv(self, snapshot_dict: Dict):
        """Append to simple CSV file (main fields only)"""
        try:
            # Define main CSV columns (simple, flat fields)
            fieldnames = [
                'signal_id', 'timestamp', 'symbol', 'direction',
                'entry_price', 'stop_loss', 'take_profit_1', 'take_profit_2', 'take_profit_3',
                'position_size', 'leverage', 'risk_reward_ratio',
                'confidence', 'confluence_score', 'primary_reason',
                'outcome', 'pnl_percent', 'pnl_usd', 'duration_minutes'
            ]

            # Check if file exists to write header
            file_exists = self.csv_file.exists()

            # Write to CSV (synchronously for reliability)
            with open(self.csv_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')

                if not file_exists:
                    writer.writeheader()

                # Extract only the fields we want
                row = {k: snapshot_dict.get(k, '') for k in fieldnames}

                # Format timestamp as readable date
                if row['timestamp']:
                    row['timestamp'] = datetime.fromtimestamp(row['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

                writer.writerow(row)

        except Exception as e:
            print(f"[TradeLogger] Error appending to CSV: {e}")

    async def _append_to_detailed_csv(self, snapshot_dict: Dict):
        """Append to detailed CSV with flattened nested data"""
        try:
            # Flatten nested dictionaries for CSV
            flat_row = {
                # Basic trade info
                'signal_id': snapshot_dict.get('signal_id', ''),
                'timestamp': datetime.fromtimestamp(snapshot_dict['timestamp']).strftime('%Y-%m-%d %H:%M:%S') if snapshot_dict.get('timestamp') else '',
                'symbol': snapshot_dict.get('symbol', ''),
                'direction': snapshot_dict.get('direction', ''),

                # Entry details
                'entry_price': snapshot_dict.get('entry_price', ''),
                'stop_loss': snapshot_dict.get('stop_loss', ''),
                'take_profit_1': snapshot_dict.get('take_profit_1', ''),
                'take_profit_2': snapshot_dict.get('take_profit_2', ''),
                'take_profit_3': snapshot_dict.get('take_profit_3', ''),
                'position_size': snapshot_dict.get('position_size', ''),
                'leverage': snapshot_dict.get('leverage', ''),
                'risk_reward_ratio': snapshot_dict.get('risk_reward_ratio', ''),

                # Signal quality
                'confidence': snapshot_dict.get('confidence', ''),
                'confluence_score': snapshot_dict.get('confluence_score', ''),
                'primary_reason': snapshot_dict.get('primary_reason', ''),

                # Confluence breakdown (flatten to individual columns)
                **{f'confluence_{k}': v for k, v in snapshot_dict.get('confluence_breakdown', {}).items()},

                # Liquidity snapshot
                'liq_direction': snapshot_dict.get('liquidity_snapshot', {}).get('direction', ''),
                'liq_confidence': snapshot_dict.get('liquidity_snapshot', {}).get('confidence', ''),
                'liq_strength': snapshot_dict.get('liquidity_snapshot', {}).get('strength', ''),
                'liq_imbalance': snapshot_dict.get('liquidity_snapshot', {}).get('imbalance', ''),

                # Structural snapshot
                'struct_trend': snapshot_dict.get('structural_snapshot', {}).get('trend', ''),
                'struct_strength': snapshot_dict.get('structural_snapshot', {}).get('strength', ''),
                'struct_choch': snapshot_dict.get('structural_snapshot', {}).get('choch_detected', ''),
                'struct_bos': snapshot_dict.get('structural_snapshot', {}).get('bos_detected', ''),

                # CVD snapshot
                'cvd_15m': snapshot_dict.get('cvd_snapshot', {}).get('cvd_15m', ''),
                'cvd_15m_trend': snapshot_dict.get('cvd_snapshot', {}).get('cvd_15m_trend', ''),
                'cvd_1h': snapshot_dict.get('cvd_snapshot', {}).get('cvd_1h', ''),
                'cvd_1h_trend': snapshot_dict.get('cvd_snapshot', {}).get('cvd_1h_trend', ''),
                'cvd_4h': snapshot_dict.get('cvd_snapshot', {}).get('cvd_4h', ''),
                'cvd_4h_trend': snapshot_dict.get('cvd_snapshot', {}).get('cvd_4h_trend', ''),

                # Market conditions
                'market_regime': snapshot_dict.get('market_conditions', {}).get('regime', ''),
                'market_momentum': snapshot_dict.get('market_conditions', {}).get('momentum', ''),
                'market_liquidity': snapshot_dict.get('market_conditions', {}).get('liquidity_quality', ''),
                'market_session': snapshot_dict.get('market_conditions', {}).get('session', ''),

                # Outcome
                'outcome': snapshot_dict.get('outcome', ''),
                'pnl_percent': snapshot_dict.get('pnl_percent', ''),
                'pnl_usd': snapshot_dict.get('pnl_usd', ''),
                'duration_minutes': snapshot_dict.get('duration_minutes', ''),
            }

            # Check if file exists to write header
            file_exists = self.csv_detailed_file.exists()

            # Write to CSV
            with open(self.csv_detailed_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=flat_row.keys())

                if not file_exists:
                    writer.writeheader()

                writer.writerow(flat_row)

        except Exception as e:
            print(f"[TradeLogger] Error appending to detailed CSV: {e}")

    async def update_outcome(self, signal_id: str, outcome: str, pnl_percent: float,
                            pnl_usd: float, duration_minutes: int) -> bool:
        """
        Update trade outcome after closure

        Args:
            signal_id: Trade signal ID
            outcome: "TP1", "TP2", "TP3", or "STOPPED_OUT"
            pnl_percent: Profit/loss percentage
            pnl_usd: Profit/loss in USD
            duration_minutes: Trade duration in minutes
        """
        try:
            # Update Redis
            if self.redis_client:
                redis_key = f"horus:trade:{signal_id}"
                trade_data = await self.redis_client.get(redis_key)

                if trade_data:
                    trade_dict = json.loads(trade_data)
                    trade_dict['outcome'] = outcome
                    trade_dict['pnl_percent'] = pnl_percent
                    trade_dict['pnl_usd'] = pnl_usd
                    trade_dict['duration_minutes'] = duration_minutes
                    trade_dict['closed_at'] = datetime.now().timestamp()

                    # Update Redis with outcome
                    await self.redis_client.setex(
                        redis_key,
                        7 * 24 * 60 * 60,
                        json.dumps(trade_dict, indent=2)
                    )

                    # Add to outcome-specific sets
                    outcome_key = f"horus:trades_{outcome.lower()}"
                    await self.redis_client.sadd(outcome_key, signal_id)

            # Update all file formats
            await self._update_jsonl_outcome(signal_id, outcome, pnl_percent, pnl_usd, duration_minutes)
            await self._update_json_array_outcome(signal_id, outcome, pnl_percent, pnl_usd, duration_minutes)
            await self._update_csv_outcome(signal_id, outcome, pnl_percent, pnl_usd, duration_minutes)

            print(f"[TradeLogger] Updated outcome for {signal_id}: {outcome} ({pnl_percent:+.2f}%)")
            print(f"  Updated: JSONL, JSON, CSV, Detailed CSV")

            # Trigger pattern analysis cache update
            await self._update_pattern_cache()

            return True

        except Exception as e:
            print(f"[TradeLogger] Error updating outcome: {e}")
            return False

    async def _update_jsonl_outcome(self, signal_id: str, outcome: str, pnl_percent: float,
                                   pnl_usd: float, duration_minutes: int):
        """Update outcome in JSON Lines file"""
        if not self.trades_file.exists():
            return

        # Read all lines
        async with aiofiles.open(self.trades_file, mode='r') as f:
            lines = await f.readlines()

        # Update matching line
        updated_lines = []
        for line in lines:
            trade_dict = json.loads(line.strip())
            if trade_dict['signal_id'] == signal_id:
                trade_dict['outcome'] = outcome
                trade_dict['pnl_percent'] = pnl_percent
                trade_dict['pnl_usd'] = pnl_usd
                trade_dict['duration_minutes'] = duration_minutes
                trade_dict['closed_at'] = datetime.now().timestamp()
            updated_lines.append(json.dumps(trade_dict) + '\n')

        # Rewrite file
        async with aiofiles.open(self.trades_file, mode='w') as f:
            await f.writelines(updated_lines)

    async def _update_json_array_outcome(self, signal_id: str, outcome: str, pnl_percent: float,
                                        pnl_usd: float, duration_minutes: int):
        """Update outcome in JSON array file"""
        if not self.json_file.exists():
            return

        try:
            # Read all trades
            async with aiofiles.open(self.json_file, mode='r') as f:
                content = await f.read()
                if not content.strip():
                    return
                trades = json.loads(content)

            # Update matching trade
            for trade in trades:
                if trade['signal_id'] == signal_id:
                    trade['outcome'] = outcome
                    trade['pnl_percent'] = pnl_percent
                    trade['pnl_usd'] = pnl_usd
                    trade['duration_minutes'] = duration_minutes
                    trade['closed_at'] = datetime.now().timestamp()
                    break

            # Write back
            async with aiofiles.open(self.json_file, mode='w') as f:
                await f.write(json.dumps(trades, indent=2))

        except Exception as e:
            print(f"[TradeLogger] Error updating JSON array outcome: {e}")

    async def _update_csv_outcome(self, signal_id: str, outcome: str, pnl_percent: float,
                                  pnl_usd: float, duration_minutes: int):
        """Update outcome in CSV files (requires rewriting entire file)"""
        # For CSV, we need to rewrite the entire file since we can't update in place
        # Read from JSON source and regenerate CSVs
        try:
            if not self.json_file.exists():
                return

            # Read all trades from JSON
            async with aiofiles.open(self.json_file, mode='r') as f:
                content = await f.read()
                if not content.strip():
                    return
                trades = json.loads(content)

            # Regenerate simple CSV
            fieldnames = [
                'signal_id', 'timestamp', 'symbol', 'direction',
                'entry_price', 'stop_loss', 'take_profit_1', 'take_profit_2', 'take_profit_3',
                'position_size', 'leverage', 'risk_reward_ratio',
                'confidence', 'confluence_score', 'primary_reason',
                'outcome', 'pnl_percent', 'pnl_usd', 'duration_minutes'
            ]

            with open(self.csv_file, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()

                for trade in trades:
                    row = {k: trade.get(k, '') for k in fieldnames}
                    if row['timestamp']:
                        row['timestamp'] = datetime.fromtimestamp(row['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    writer.writerow(row)

            # Regenerate detailed CSV
            with open(self.csv_detailed_file, mode='w', newline='', encoding='utf-8') as f:
                if trades:
                    # Build flat rows
                    flat_rows = []
                    for trade in trades:
                        flat_row = {
                            'signal_id': trade.get('signal_id', ''),
                            'timestamp': datetime.fromtimestamp(trade['timestamp']).strftime('%Y-%m-%d %H:%M:%S') if trade.get('timestamp') else '',
                            'symbol': trade.get('symbol', ''),
                            'direction': trade.get('direction', ''),
                            'entry_price': trade.get('entry_price', ''),
                            'stop_loss': trade.get('stop_loss', ''),
                            'take_profit_1': trade.get('take_profit_1', ''),
                            'take_profit_2': trade.get('take_profit_2', ''),
                            'take_profit_3': trade.get('take_profit_3', ''),
                            'position_size': trade.get('position_size', ''),
                            'leverage': trade.get('leverage', ''),
                            'risk_reward_ratio': trade.get('risk_reward_ratio', ''),
                            'confidence': trade.get('confidence', ''),
                            'confluence_score': trade.get('confluence_score', ''),
                            'primary_reason': trade.get('primary_reason', ''),
                            **{f'confluence_{k}': v for k, v in trade.get('confluence_breakdown', {}).items()},
                            'liq_direction': trade.get('liquidity_snapshot', {}).get('direction', ''),
                            'liq_confidence': trade.get('liquidity_snapshot', {}).get('confidence', ''),
                            'liq_strength': trade.get('liquidity_snapshot', {}).get('strength', ''),
                            'liq_imbalance': trade.get('liquidity_snapshot', {}).get('imbalance', ''),
                            'struct_trend': trade.get('structural_snapshot', {}).get('trend', ''),
                            'struct_strength': trade.get('structural_snapshot', {}).get('strength', ''),
                            'struct_choch': trade.get('structural_snapshot', {}).get('choch_detected', ''),
                            'struct_bos': trade.get('structural_snapshot', {}).get('bos_detected', ''),
                            'cvd_15m': trade.get('cvd_snapshot', {}).get('cvd_15m', ''),
                            'cvd_15m_trend': trade.get('cvd_snapshot', {}).get('cvd_15m_trend', ''),
                            'cvd_1h': trade.get('cvd_snapshot', {}).get('cvd_1h', ''),
                            'cvd_1h_trend': trade.get('cvd_snapshot', {}).get('cvd_1h_trend', ''),
                            'cvd_4h': trade.get('cvd_snapshot', {}).get('cvd_4h', ''),
                            'cvd_4h_trend': trade.get('cvd_snapshot', {}).get('cvd_4h_trend', ''),
                            'market_regime': trade.get('market_conditions', {}).get('regime', ''),
                            'market_momentum': trade.get('market_conditions', {}).get('momentum', ''),
                            'market_liquidity': trade.get('market_conditions', {}).get('liquidity_quality', ''),
                            'market_session': trade.get('market_conditions', {}).get('session', ''),
                            'outcome': trade.get('outcome', ''),
                            'pnl_percent': trade.get('pnl_percent', ''),
                            'pnl_usd': trade.get('pnl_usd', ''),
                            'duration_minutes': trade.get('duration_minutes', ''),
                        }
                        flat_rows.append(flat_row)

                    # Write with all possible columns
                    all_columns = set()
                    for row in flat_rows:
                        all_columns.update(row.keys())

                    writer = csv.DictWriter(f, fieldnames=sorted(all_columns))
                    writer.writeheader()
                    writer.writerows(flat_rows)

        except Exception as e:
            print(f"[TradeLogger] Error updating CSV outcome: {e}")

    async def _update_pattern_cache(self):
        """Update pattern analysis cache with latest statistics"""
        try:
            stats = await self.calculate_pattern_statistics()

            async with aiofiles.open(self.analysis_cache, mode='w') as f:
                await f.write(json.dumps(stats, indent=2))

            print(f"[TradeLogger] Pattern cache updated: {stats.get('total_trades', 0)} trades analyzed")

        except Exception as e:
            print(f"[TradeLogger] Error updating pattern cache: {e}")

    async def calculate_pattern_statistics(self) -> Dict[str, Any]:
        """
        Calculate pattern statistics from all closed trades

        Returns comprehensive analysis including:
        - Win rate by confluence score ranges
        - Win rate by confidence ranges
        - Most profitable confluence combinations
        - Best performing primary reasons
        - Optimal market conditions
        """
        if not self.trades_file.exists():
            return {"error": "No trades logged yet"}

        # Read all trades
        trades = []
        async with aiofiles.open(self.trades_file, mode='r') as f:
            async for line in f:
                trade = json.loads(line.strip())
                if trade.get('outcome'):  # Only analyze closed trades
                    trades.append(trade)

        if not trades:
            return {"error": "No closed trades yet"}

        # Calculate statistics
        total = len(trades)
        winners = [t for t in trades if t['pnl_percent'] > 0]
        losers = [t for t in trades if t['pnl_percent'] <= 0]

        stats = {
            "total_trades": total,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": len(winners) / total if total > 0 else 0,
            "avg_winner_pnl": sum(t['pnl_percent'] for t in winners) / len(winners) if winners else 0,
            "avg_loser_pnl": sum(t['pnl_percent'] for t in losers) / len(losers) if losers else 0,

            # Confluence analysis
            "win_rate_by_confluence": self._analyze_by_ranges(
                trades, "confluence_score", [(0, 30), (30, 40), (40, 50), (50, 60), (60, 100)]
            ),

            # Confidence analysis
            "win_rate_by_confidence": self._analyze_by_ranges(
                trades, "confidence", [(0, 0.25), (0.25, 0.35), (0.35, 0.45), (0.45, 0.60), (0.60, 1.0)]
            ),

            # Best confluence factors
            "top_confluence_factors": self._analyze_confluence_factors(trades),

            # Best primary reasons
            "best_primary_reasons": self._analyze_primary_reasons(trades),

            # Direction performance
            "long_win_rate": self._calculate_direction_win_rate(trades, "LONG"),
            "short_win_rate": self._calculate_direction_win_rate(trades, "SHORT"),

            # Outcome distribution
            "outcome_distribution": self._analyze_outcomes(trades),

            # Average trade duration
            "avg_duration_winners": sum(t['duration_minutes'] for t in winners) / len(winners) if winners else 0,
            "avg_duration_losers": sum(t['duration_minutes'] for t in losers) / len(losers) if losers else 0,

            "last_updated": datetime.now().isoformat()
        }

        return stats

    def _analyze_by_ranges(self, trades: List[Dict], field: str, ranges: List[tuple]) -> Dict:
        """Analyze win rate by value ranges"""
        results = {}
        for low, high in ranges:
            range_trades = [t for t in trades if low <= t.get(field, 0) < high]
            if range_trades:
                winners = [t for t in range_trades if t['pnl_percent'] > 0]
                results[f"{low}-{high}"] = {
                    "count": len(range_trades),
                    "win_rate": len(winners) / len(range_trades),
                    "avg_pnl": sum(t['pnl_percent'] for t in range_trades) / len(range_trades)
                }
        return results

    def _analyze_confluence_factors(self, trades: List[Dict]) -> Dict[str, float]:
        """Find which confluence factors appear most in winning trades"""
        factor_stats = {}

        for trade in trades:
            is_winner = trade['pnl_percent'] > 0
            breakdown = trade.get('confluence_breakdown', {})

            for factor, points in breakdown.items():
                if factor not in factor_stats:
                    factor_stats[factor] = {"total": 0, "winners": 0, "total_points": 0}

                factor_stats[factor]["total"] += 1
                factor_stats[factor]["total_points"] += points
                if is_winner:
                    factor_stats[factor]["winners"] += 1

        # Calculate win rate for each factor
        results = {}
        for factor, stats in factor_stats.items():
            results[factor] = {
                "win_rate": stats["winners"] / stats["total"] if stats["total"] > 0 else 0,
                "appearances": stats["total"],
                "avg_points": stats["total_points"] / stats["total"] if stats["total"] > 0 else 0
            }

        # Sort by win rate
        return dict(sorted(results.items(), key=lambda x: x[1]["win_rate"], reverse=True))

    def _analyze_primary_reasons(self, trades: List[Dict]) -> Dict[str, float]:
        """Analyze win rate by primary reason"""
        reason_stats = {}

        for trade in trades:
            reason = trade.get('primary_reason', 'unknown')
            is_winner = trade['pnl_percent'] > 0

            if reason not in reason_stats:
                reason_stats[reason] = {"total": 0, "winners": 0}

            reason_stats[reason]["total"] += 1
            if is_winner:
                reason_stats[reason]["winners"] += 1

        results = {}
        for reason, stats in reason_stats.items():
            results[reason] = {
                "win_rate": stats["winners"] / stats["total"] if stats["total"] > 0 else 0,
                "count": stats["total"]
            }

        return dict(sorted(results.items(), key=lambda x: x[1]["win_rate"], reverse=True))

    def _calculate_direction_win_rate(self, trades: List[Dict], direction: str) -> float:
        """Calculate win rate for specific direction"""
        direction_trades = [t for t in trades if t['direction'] == direction]
        if not direction_trades:
            return 0.0
        winners = [t for t in direction_trades if t['pnl_percent'] > 0]
        return len(winners) / len(direction_trades)

    def _analyze_outcomes(self, trades: List[Dict]) -> Dict[str, int]:
        """Count outcome distribution"""
        outcomes = {}
        for trade in trades:
            outcome = trade.get('outcome', 'unknown')
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        return outcomes

    async def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """Get most recent trades from Redis"""
        if not self.redis_client:
            return []

        try:
            # Get recent signal IDs from sorted set
            signal_ids = await self.redis_client.zrevrange("horus:trade_timeline", 0, limit - 1)

            trades = []
            for signal_id in signal_ids:
                redis_key = f"horus:trade:{signal_id}"
                trade_data = await self.redis_client.get(redis_key)
                if trade_data:
                    trades.append(json.loads(trade_data))

            return trades

        except Exception as e:
            print(f"[TradeLogger] Error getting recent trades: {e}")
            return []

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()
            print("[TradeLogger] Redis connection closed")


# Global logger instance
_logger: Optional[TradeExecutionLogger] = None


async def get_logger() -> TradeExecutionLogger:
    """Get or create global logger instance"""
    global _logger
    if _logger is None:
        _logger = TradeExecutionLogger()
        await _logger.connect()
    return _logger
