"""
Real-Time Trade Monitor - Watches and Executes Scenarios

Monitors active trades in REAL-TIME and executes planned scenarios:
- Detects invalidations and exits
- Adjusts stops dynamically
- Executes TPs intelligently
- Predicts reversals before they happen

Fixes Horus failures:
- Doesn't close on minor pullbacks (smart invalidation)
- Exits before TP if reversal detected (prevents $206 TP miss scenario)
- Trails stops intelligently (knows when to stop trailing back)
- Uses market orders when needed (no unfilled limits)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from enum import Enum

from trade_scenario_planner import (
    TradePlan, InvalidationScenario, StopAdjustmentScenario,
    TPExecutionScenario, InvalidationReason, StopAdjustmentTrigger
)


class TradeStatus(Enum):
    """Current trade status"""
    WAITING_ENTRY = "waiting_entry"
    ACTIVE = "active"
    STOP_ADJUSTED = "stop_adjusted"
    PARTIAL_TP = "partial_tp"
    CLOSED_TP = "closed_tp"
    CLOSED_SL = "closed_sl"
    CLOSED_INVALIDATION = "closed_invalidation"
    CANCELLED = "cancelled"


@dataclass
class TradeState:
    """Current state of active trade"""

    # Trade basics
    trade_id: str
    entry_price: float
    entry_time: datetime
    direction: str
    position_size: float
    current_stop: float
    current_targets: List[float]

    # Status
    status: TradeStatus
    unrealized_pnl_pct: float
    unrealized_pnl_usd: float

    # Scenario tracking
    breakeven_hit: bool
    trailing_active: bool
    stop_adjustments_count: int
    partial_exits: List[float]  # Prices where partial exits occurred

    # Context
    entry_candle_close: float
    highest_price_seen: float  # For LONG
    lowest_price_seen: float   # For SHORT

    # Invalidation monitoring
    structure_intact: bool
    last_candle_direction: str  # 'bullish', 'bearish', 'neutral'
    candles_against_position: int

    # TP monitoring
    tp_attempts: Dict[float, int]  # TP level → attempt count
    reversal_signals_at_tp: List[str]


class RealtimeTradeMonitor:
    """
    Real-time monitoring and execution of trade scenarios

    This is the "brain" that watches the trade and makes decisions
    """

    def __init__(self):
        self.active_trades: Dict[str, TradeState] = {}
        self.trade_plans: Dict[str, TradePlan] = {}

        # Monitoring config
        self.candle_check_interval = 60  # Check every 60 seconds
        self.price_check_interval = 5    # Check price every 5 seconds

        # Invalidation thresholds (Horus fix)
        self.min_pullback_for_invalidation = 0.40  # 40% retracement = real problem
        self.consecutive_candles_for_invalidation = 2  # 2 against us = warning
        self.max_candles_against_before_exit = 3  # 3 = exit

        # TP execution thresholds
        self.tp_attempt_limit = 3  # After 3 attempts, use market
        self.reversal_signal_threshold = 2  # 2 reversal signals = exit now

    def start_monitoring_trade(
        self,
        trade_id: str,
        trade_plan: TradePlan,
        entry_price: float,
        position_size: float
    ):
        """Start monitoring a new trade"""

        self.trade_plans[trade_id] = trade_plan

        self.active_trades[trade_id] = TradeState(
            trade_id=trade_id,
            entry_price=entry_price,
            entry_time=datetime.utcnow(),
            direction=trade_plan.direction,
            position_size=position_size,
            current_stop=trade_plan.initial_stop,
            current_targets=trade_plan.targets.copy(),
            status=TradeStatus.ACTIVE,
            unrealized_pnl_pct=0.0,
            unrealized_pnl_usd=0.0,
            breakeven_hit=False,
            trailing_active=False,
            stop_adjustments_count=0,
            partial_exits=[],
            entry_candle_close=trade_plan.entry_candle_close,
            highest_price_seen=entry_price,
            lowest_price_seen=entry_price,
            structure_intact=True,
            last_candle_direction='neutral',
            candles_against_position=0,
            tp_attempts={tp: 0 for tp in trade_plan.targets},
            reversal_signals_at_tp=[]
        )

        print(f"\n[TRADE MONITOR] Started monitoring trade {trade_id}")
        print(f"  Direction: {trade_plan.direction}")
        print(f"  Entry: ${entry_price:.2f}")
        print(f"  Stop: ${trade_plan.initial_stop:.2f}")
        print(f"  Targets: {[f'${tp:.2f}' for tp in trade_plan.targets]}")
        print(f"  Planned scenarios: {len(trade_plan.invalidation_scenarios)} invalidations, {len(trade_plan.stop_adjustment_plan)} stop adjustments")

    def check_trade(
        self,
        trade_id: str,
        current_price: float,
        current_candle: pd.Series,
        market_intel,
        df: pd.DataFrame
    ) -> Dict:
        """
        Main monitoring function - checks everything in real-time

        Returns: {
            'action': 'HOLD', 'EXIT', 'ADJUST_STOP', 'EXECUTE_TP', 'CANCEL',
            'reason': 'Description of why',
            'new_stop': Optional[float],
            'tp_to_execute': Optional[float],
            'use_market_order': bool
        }
        """

        if trade_id not in self.active_trades:
            return {'action': 'NONE', 'reason': 'Trade not found'}

        trade = self.active_trades[trade_id]
        plan = self.trade_plans[trade_id]

        # Update trade state
        self._update_trade_state(trade, current_price, current_candle)

        # Check in priority order:

        # 1. INVALIDATION CHECK (highest priority)
        print(f"    [1/4] Checking invalidation scenarios... ({len(plan.invalidation_scenarios)} scenarios)")
        invalidation = self._check_invalidations(trade, plan, current_price, current_candle, market_intel, df)
        if invalidation['action'] != 'HOLD':
            print(f"    [INVALIDATION TRIGGERED] {invalidation['reason']}")
            return invalidation
        print(f"    [OK] No invalidation detected")

        # 2. TP EXECUTION CHECK
        next_tp_str = f"${trade.current_targets[0]:.2f}" if trade.current_targets else "None"
        print(f"    [2/4] Checking TP execution... (Next TP: {next_tp_str})")
        tp_execution = self._check_tp_execution(trade, plan, current_price, current_candle, df)
        if tp_execution['action'] != 'HOLD':
            print(f"    [TP EXECUTION] {tp_execution['reason']}")
            return tp_execution
        print(f"    [OK] Not at TP yet")

        # 3. STOP ADJUSTMENT CHECK
        print(f"    [3/4] Checking stop adjustments... (Current stop: ${trade.current_stop:.2f})")
        stop_adjustment = self._check_stop_adjustments(trade, plan, current_price, df)
        if stop_adjustment['action'] != 'HOLD':
            print(f"    [STOP ADJUSTMENT] {stop_adjustment['reason']}")
            print(f"    [NEW STOP] ${stop_adjustment['new_stop']:.2f}")
            return stop_adjustment
        print(f"    [OK] No stop adjustment needed")

        # 4. REVERSAL PREDICTION (before it happens)
        print(f"    [4/4] Predicting potential reversals...")
        reversal_warning = self._predict_reversal(trade, plan, current_price, df)
        if reversal_warning['action'] != 'HOLD':
            print(f"    [REVERSAL PREDICTED] {reversal_warning['reason']}")
            return reversal_warning
        print(f"    [OK] No reversal predicted")

        return {'action': 'HOLD', 'reason': 'All conditions OK'}

    def _update_trade_state(self, trade: TradeState, current_price: float, candle: pd.Series):
        """Update trade state with current data"""

        # Update P&L
        if trade.direction == 'LONG':
            pnl_pct = (current_price - trade.entry_price) / trade.entry_price
            trade.highest_price_seen = max(trade.highest_price_seen, current_price)
        else:  # SHORT
            pnl_pct = (trade.entry_price - current_price) / trade.entry_price
            trade.lowest_price_seen = min(trade.lowest_price_seen, current_price)

        trade.unrealized_pnl_pct = pnl_pct
        trade.unrealized_pnl_usd = pnl_pct * trade.position_size

        # Update candle direction
        if candle['close'] > candle['open']:
            trade.last_candle_direction = 'bullish'
        elif candle['close'] < candle['open']:
            trade.last_candle_direction = 'bearish'
        else:
            trade.last_candle_direction = 'neutral'

        # Count candles against position
        if trade.direction == 'LONG' and trade.last_candle_direction == 'bearish':
            trade.candles_against_position += 1
        elif trade.direction == 'SHORT' and trade.last_candle_direction == 'bullish':
            trade.candles_against_position += 1
        else:
            trade.candles_against_position = 0  # Reset if candle goes our way

        # Log trade state
        print(f"    [TRADE STATE UPDATE]")
        print(f"      Price: ${current_price:.2f} | P&L: {pnl_pct*100:+.2f}% (${trade.unrealized_pnl_usd:+.2f})")
        print(f"      Candle: {trade.last_candle_direction.upper()} | Against position: {trade.candles_against_position}")
        if trade.direction == 'LONG':
            print(f"      Highest seen: ${trade.highest_price_seen:.2f}")
        else:
            print(f"      Lowest seen: ${trade.lowest_price_seen:.2f}")

    def _check_invalidations(
        self,
        trade: TradeState,
        plan: TradePlan,
        current_price: float,
        candle: pd.Series,
        market_intel,
        df: pd.DataFrame
    ) -> Dict:
        """Check all invalidation scenarios (Horus fix - smart invalidation)"""

        for scenario in plan.invalidation_scenarios:
            # Structure broken check
            if scenario.scenario_type == InvalidationReason.STRUCTURE_BROKEN:
                if scenario.requires_candle_close:
                    # Check if candle CLOSED beyond the level
                    if plan.direction == 'LONG' and candle['close'] < scenario.trigger_level:
                        # But is it a REAL break or just a pullback?
                        retracement_from_high = (trade.highest_price_seen - candle['close']) / (trade.highest_price_seen - trade.entry_price)

                        if retracement_from_high > self.min_pullback_for_invalidation:
                            return {
                                'action': 'EXIT',
                                'reason': f"Structure broken: Close below ${scenario.trigger_level:.2f} with {retracement_from_high*100:.0f}% retracement",
                                'use_market_order': True,
                                'severity': scenario.severity
                            }

                    elif plan.direction == 'SHORT' and candle['close'] > scenario.trigger_level:
                        retracement_from_low = (candle['close'] - trade.lowest_price_seen) / (trade.entry_price - trade.lowest_price_seen)

                        if retracement_from_low > self.min_pullback_for_invalidation:
                            return {
                                'action': 'EXIT',
                                'reason': f"Structure broken: Close above ${scenario.trigger_level:.2f} with {retracement_from_low*100:.0f}% retracement",
                                'use_market_order': True,
                                'severity': scenario.severity
                            }

            # Candle close invalidation (bearish close below entry in LONG)
            elif scenario.scenario_type == InvalidationReason.CANDLE_CLOSE_INVALIDATION:
                if plan.direction == 'LONG':
                    if (candle['close'] < candle['open'] and  # Bearish candle
                        candle['close'] < scenario.trigger_level):  # Below threshold

                        # Extra check: Is this a STRONG rejection or minor pullback?
                        candle_size = abs(candle['close'] - candle['open']) / candle['open']

                        if candle_size > 0.003:  # 0.3% candle = meaningful
                            return {
                                'action': 'EXIT',
                                'reason': f"Strong bearish rejection: {candle_size*100:.2f}% candle closed below entry",
                                'use_market_order': True,
                                'severity': scenario.severity
                            }

                elif plan.direction == 'SHORT':
                    if (candle['close'] > candle['open'] and  # Bullish candle
                        candle['close'] > scenario.trigger_level):

                        candle_size = abs(candle['close'] - candle['open']) / candle['open']

                        if candle_size > 0.003:
                            return {
                                'action': 'EXIT',
                                'reason': f"Strong bullish rejection: {candle_size*100:.2f}% candle closed above entry",
                                'use_market_order': True,
                                'severity': scenario.severity
                            }

            # Range trap check
            elif scenario.scenario_type == InvalidationReason.RANGE_TRAP_DETECTED:
                trap_analysis = market_intel.range_trap_analysis
                if trap_analysis.is_trapped and trap_analysis.trap_severity > 0.70:
                    # Wait for confirmation (2 candles)
                    if trade.candles_against_position >= scenario.confirmation_bars:
                        return {
                            'action': 'EXIT',
                            'reason': f"Range trap detected ({trap_analysis.trap_severity:.0%} severity) - chopping expected",
                            'use_market_order': True,
                            'severity': scenario.severity
                        }

            # Stop hunt mode check
            elif scenario.scenario_type == InvalidationReason.STOP_HUNT_MODE:
                stop_hunt = market_intel.stop_hunt_warning
                if stop_hunt.is_stop_hunt_mode:
                    return {
                        'action': 'REDUCE_SIZE',
                        'reason': f"Stop hunt mode active ({stop_hunt.severity:.0%}) - reduce exposure by 50%",
                        'use_market_order': False,
                        'severity': scenario.severity
                    }

        # Check for too many candles against us (Horus fix)
        if trade.candles_against_position >= self.max_candles_against_before_exit:
            return {
                'action': 'EXIT',
                'reason': f"{trade.candles_against_position} consecutive candles against position - trend may be reversing",
                'use_market_order': True,
                'severity': 0.70
            }

        return {'action': 'HOLD'}

    def _check_tp_execution(
        self,
        trade: TradeState,
        plan: TradePlan,
        current_price: float,
        candle: pd.Series,
        df: pd.DataFrame
    ) -> Dict:
        """Check TP execution scenarios (Horus fix - smart TP execution)"""

        if not trade.current_targets:
            return {'action': 'HOLD'}  # All TPs hit

        next_tp = trade.current_targets[0]
        tp_scenario = None

        # Find the TP scenario for this target
        for scenario in plan.tp_execution_plan:
            if abs(scenario.tp_level - next_tp) < 0.01:
                tp_scenario = scenario
                break

        if not tp_scenario:
            return {'action': 'HOLD'}

        # Check if price is near TP
        if plan.direction == 'LONG':
            distance_to_tp_pct = (next_tp - current_price) / current_price
            at_tp = current_price >= next_tp
            close_to_tp = distance_to_tp_pct < tp_scenario.use_market_if_close_pct
        else:  # SHORT
            distance_to_tp_pct = (current_price - next_tp) / current_price
            at_tp = current_price <= next_tp
            close_to_tp = distance_to_tp_pct < tp_scenario.use_market_if_close_pct

        # Increment TP attempt counter if at TP
        if at_tp:
            trade.tp_attempts[next_tp] += 1

        # SCENARIO 1: Price hit TP but reversal detected (Horus $206 fix)
        if at_tp:
            reversal_detected, reversal_signals = self._detect_reversal_at_tp(
                plan.direction, current_price, next_tp, candle, df
            )

            if reversal_detected:
                trade.reversal_signals_at_tp.extend(reversal_signals)

                if len(trade.reversal_signals_at_tp) >= self.reversal_signal_threshold:
                    return {
                        'action': 'EXECUTE_TP',
                        'reason': f"At TP ${next_tp:.2f} but reversal detected ({', '.join(reversal_signals)}) - use MARKET ORDER",
                        'tp_to_execute': next_tp,
                        'use_market_order': True,  # Critical: Don't wait for limit fill
                        'partial_pct': tp_scenario.partial_exit_pct
                    }

        # SCENARIO 2: Very close to TP - use market to ensure fill
        if close_to_tp and not at_tp:
            return {
                'action': 'EXECUTE_TP',
                'reason': f"Within {distance_to_tp_pct*100:.2f}% of TP ${next_tp:.2f} - use market order to ensure fill",
                'tp_to_execute': next_tp,
                'use_market_order': True,
                'partial_pct': tp_scenario.partial_exit_pct
            }

        # SCENARIO 3: Hit TP multiple times but not filling (Horus fix)
        if trade.tp_attempts[next_tp] >= self.tp_attempt_limit:
            return {
                'action': 'EXECUTE_TP',
                'reason': f"TP ${next_tp:.2f} touched {trade.tp_attempts[next_tp]} times but not filled - use MARKET",
                'tp_to_execute': next_tp,
                'use_market_order': True,
                'partial_pct': tp_scenario.partial_exit_pct
            }

        # SCENARIO 4: TP hit and reversing (missed and coming back)
        if plan.direction == 'LONG' and current_price < next_tp * 0.998:  # Pulled back 0.2%
            if trade.tp_attempts[next_tp] > 0:  # We were at TP before
                return {
                    'action': 'EXIT',
                    'reason': f"TP ${next_tp:.2f} missed and price reversing - exit now at market",
                    'use_market_order': True,
                    'severity': 0.80
                }

        elif plan.direction == 'SHORT' and current_price > next_tp * 1.002:
            if trade.tp_attempts[next_tp] > 0:
                return {
                    'action': 'EXIT',
                    'reason': f"TP ${next_tp:.2f} missed and price reversing - exit now at market",
                    'use_market_order': True,
                    'severity': 0.80
                }

        return {'action': 'HOLD'}

    def _check_stop_adjustments(
        self,
        trade: TradeState,
        plan: TradePlan,
        current_price: float,
        df: pd.DataFrame
    ) -> Dict:
        """Check stop adjustment scenarios"""

        for scenario in plan.stop_adjustment_plan:
            # Skip if already adjusted too many times
            if trade.stop_adjustments_count >= scenario.max_times_to_adjust:
                continue

            # Check if trigger condition met
            triggered = False
            if scenario.trigger_price:
                if plan.direction == 'LONG':
                    triggered = current_price >= scenario.trigger_price
                else:
                    triggered = current_price <= scenario.trigger_price

            if not triggered:
                continue

            # Check minimum profit requirement
            if trade.unrealized_pnl_pct < scenario.min_profit_pct:
                continue

            # Calculate new stop
            new_stop = self._calculate_new_stop(
                trade, plan, scenario, current_price, df
            )

            # Validate new stop
            if plan.direction == 'LONG':
                # Stop must be below current price
                if new_stop >= current_price:
                    continue
                # Stop must be better than current stop (higher)
                if new_stop <= trade.current_stop:
                    continue
            else:  # SHORT
                # Stop must be above current price
                if new_stop <= current_price:
                    continue
                # Stop must be better than current stop (lower)
                if new_stop >= trade.current_stop:
                    continue

            # Check if we should allow trailing back
            if not scenario.allow_trailing_back and new_stop != trade.entry_price:
                # Once profit locked, don't trail back
                if trade.unrealized_pnl_pct > scenario.stop_trailing_back_at_profit_pct:
                    if plan.direction == 'LONG' and new_stop < trade.current_stop:
                        continue  # Don't trail back
                    elif plan.direction == 'SHORT' and new_stop > trade.current_stop:
                        continue

            return {
                'action': 'ADJUST_STOP',
                'reason': scenario.description,
                'new_stop': new_stop,
                'trigger': scenario.trigger.value
            }

        return {'action': 'HOLD'}

    def _calculate_new_stop(
        self,
        trade: TradeState,
        plan: TradePlan,
        scenario: StopAdjustmentScenario,
        current_price: float,
        df: pd.DataFrame
    ) -> float:
        """Calculate new stop based on scenario"""

        if "breakeven" in scenario.new_stop_calculation.lower():
            return trade.entry_price * (1 + scenario.buffer_pct if plan.direction == 'LONG' else 1 - scenario.buffer_pct)

        elif "last_swing_low" in scenario.new_stop_calculation.lower():
            # Find most recent swing low from df
            recent_lows = df['low'].tail(20).min()
            return recent_lows * (1 + scenario.buffer_pct)

        elif "last_swing_high" in scenario.new_stop_calculation.lower():
            recent_highs = df['high'].tail(20).max()
            return recent_highs * (1 - scenario.buffer_pct)

        elif "candle_low" in scenario.new_stop_calculation.lower():
            last_candle_low = df.iloc[-1]['low']
            return last_candle_low * (1 + scenario.buffer_pct)

        elif "candle_high" in scenario.new_stop_calculation.lower():
            last_candle_high = df.iloc[-1]['high']
            return last_candle_high * (1 - scenario.buffer_pct)

        else:
            # Default: current stop
            return trade.current_stop

    def _detect_reversal_at_tp(
        self,
        direction: str,
        current_price: float,
        tp_level: float,
        candle: pd.Series,
        df: pd.DataFrame
    ) -> Tuple[bool, List[str]]:
        """Detect if reversal is happening at TP (Horus fix)"""

        signals = []

        # Signal 1: Wick rejection at TP
        if direction == 'LONG':
            wick_size = candle['high'] - candle['close']
            body_size = abs(candle['close'] - candle['open'])

            if wick_size > body_size * 2 and candle['high'] >= tp_level:
                signals.append("Long wick rejection at TP")

        else:  # SHORT
            wick_size = candle['close'] - candle['low']
            body_size = abs(candle['close'] - candle['open'])

            if wick_size > body_size * 2 and candle['low'] <= tp_level:
                signals.append("Long wick rejection at TP")

        # Signal 2: Reversal candle pattern at TP
        if direction == 'LONG' and candle['close'] < candle['open']:
            if current_price >= tp_level * 0.999:  # Within 0.1% of TP
                signals.append("Bearish reversal candle at TP")

        elif direction == 'SHORT' and candle['close'] > candle['open']:
            if current_price <= tp_level * 1.001:
                signals.append("Bullish reversal candle at TP")

        # Signal 3: Failed to break TP after multiple attempts
        recent_highs = df['high'].tail(5).values
        if direction == 'LONG':
            tp_touches = sum(1 for h in recent_highs if h >= tp_level * 0.999)
            if tp_touches >= 3:
                signals.append("Failed to break TP after 3 attempts")

        else:
            recent_lows = df['low'].tail(5).values
            tp_touches = sum(1 for l in recent_lows if l <= tp_level * 1.001)
            if tp_touches >= 3:
                signals.append("Failed to break TP after 3 attempts")

        return len(signals) >= 1, signals

    def _predict_reversal(
        self,
        trade: TradeState,
        plan: TradePlan,
        current_price: float,
        df: pd.DataFrame
    ) -> Dict:
        """Predict reversal BEFORE it happens"""

        # Get last 3 candles
        last_3 = df.tail(3)

        # Pattern: Diminishing momentum near TP
        if trade.current_targets:
            next_tp = trade.current_targets[0]

            if plan.direction == 'LONG':
                distance_to_tp = (next_tp - current_price) / current_price

                if 0.001 < distance_to_tp < 0.005:  # 0.1-0.5% from TP
                    # Check if momentum is dying
                    candle_sizes = [abs(c['close'] - c['open']) / c['open'] for _, c in last_3.iterrows()]

                    if candle_sizes[-1] < candle_sizes[0] * 0.5:  # Last candle 50% smaller
                        if last_3.iloc[-1]['close'] < last_3.iloc[-1]['open']:  # And bearish
                            return {
                                'action': 'EXECUTE_TP',
                                'reason': "Momentum dying near TP - likely reversal imminent",
                                'tp_to_execute': next_tp,
                                'use_market_order': True,
                                'partial_pct': 1.0
                            }

        return {'action': 'HOLD'}


if __name__ == "__main__":
    print("Real-Time Trade Monitor")
    print("Watches trades and executes planned scenarios")
    print("Learns from Horus to avoid his mistakes")
