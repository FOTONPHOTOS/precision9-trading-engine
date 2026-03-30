"""
Trade Scenario Planner - Future Projection & Planning

Predicts future scenarios BEFORE they happen:
- "If price reaches X, enter at Y targeting Z"
- "If price breaks A, cancel order B"
- "If candle closes below C, exit trade"
- "If D happens, move stop to breakeven"

Learns from Horus failures:
1. Don't close on minor pullbacks (distinguish pullback from invalidation)
2. Don't use limit orders at TP if reversal imminent
3. Trail stops intelligently (know when to stop trailing back)
4. Exit before TP if reversal detected
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class ScenarioType(Enum):
    """Types of scenarios to plan for"""
    ENTRY_SCENARIO = "entry"
    EXIT_SCENARIO = "exit"
    INVALIDATION_SCENARIO = "invalidation"
    STOP_ADJUSTMENT = "stop_adjustment"
    TP_EXECUTION = "tp_execution"


class InvalidationReason(Enum):
    """Why a trade setup is no longer valid"""
    STRUCTURE_BROKEN = "structure_broken"  # Key level broken against us
    CANDLE_CLOSE_INVALIDATION = "candle_close_invalidation"  # Bearish close below bullish in long
    LIQUIDITY_SWEEP_REVERSAL = "liquidity_sweep_reversal"  # Swept and reversing
    RANGE_TRAP_DETECTED = "range_trap_detected"  # Entered range trap
    STOP_HUNT_MODE = "stop_hunt_mode"  # Market hunting stops
    TREND_REVERSAL = "trend_reversal"  # Trend changed against us
    TIME_INVALIDATION = "time_invalidation"  # Setup too old
    FAILED_BREAKOUT = "failed_breakout"  # Breakout attempt failed


class StopAdjustmentTrigger(Enum):
    """When to adjust stops"""
    MOVE_TO_BREAKEVEN = "move_to_breakeven"  # When profit threshold hit
    TRAIL_TO_STRUCTURE = "trail_to_structure"  # Trail to last swing
    TRAIL_TO_CANDLE = "trail_to_candle"  # Trail to candle low/high
    LOCK_PROFIT = "lock_profit"  # Lock in partial profit
    WIDEN_FOR_VOLATILITY = "widen_for_volatility"  # Give more room
    TIGHTEN_FOR_REVERSAL = "tighten_for_reversal"  # Reversal imminent


@dataclass
class TradePlan:
    """Complete trade plan with all scenarios"""

    # Entry planning
    entry_price: float
    entry_zone: Tuple[float, float]  # (min, max) for limit orders
    direction: str  # 'LONG' or 'SHORT'

    # Initial stops and targets
    initial_stop: float
    targets: List[float]  # Multiple TP levels

    # Key levels for monitoring
    key_support_levels: List[float]
    key_resistance_levels: List[float]
    invalidation_level: float  # If hit, setup is dead

    # Structure context
    last_swing_high: float
    last_swing_low: float
    entry_candle_close: float  # Close of candle we entered on

    # Invalidation scenarios
    invalidation_scenarios: List['InvalidationScenario']

    # Stop adjustment plan
    stop_adjustment_plan: List['StopAdjustmentScenario']

    # TP execution plan
    tp_execution_plan: List['TPExecutionScenario']

    # Risk parameters
    position_size: float
    risk_amount: float
    risk_reward_ratio: float


@dataclass
class InvalidationScenario:
    """Specific scenario that invalidates the trade"""

    scenario_type: InvalidationReason
    trigger_condition: str  # Natural language description
    trigger_level: Optional[float]  # Price level if applicable
    action: str  # "EXIT_MARKET", "CANCEL_ORDER", "REDUCE_SIZE"
    urgency: str  # "IMMEDIATE", "ON_CANDLE_CLOSE", "WAIT_FOR_CONFIRMATION"

    # Detailed conditions
    requires_candle_close: bool
    confirmation_bars: int  # How many bars to confirm

    # Context awareness
    severity: float  # 0-1, how bad this invalidation is
    description: str


@dataclass
class StopAdjustmentScenario:
    """When and how to adjust stops"""

    trigger: StopAdjustmentTrigger
    trigger_condition: str
    trigger_price: Optional[float]

    # New stop calculation
    new_stop_calculation: str  # "last_swing_low", "breakeven", "candle_low + buffer"
    buffer_pct: float  # Buffer to add (e.g., 0.003 = 0.3%)

    # Conditions
    min_profit_pct: float  # Minimum profit before adjusting
    max_times_to_adjust: int  # Don't adjust forever

    # Anti-Horus protection
    allow_trailing_back: bool  # Can we move stop back (away from entry)?
    max_trail_back_distance: float  # Max distance to trail back
    stop_trailing_back_at_profit_pct: float  # Once this profit hit, never trail back

    description: str


@dataclass
class TPExecutionScenario:
    """How to execute take profit"""

    tp_level: float
    tp_type: str  # "LIMIT", "MARKET", "DYNAMIC"

    # Reversal detection
    watch_for_reversal: bool
    reversal_indicators: List[str]  # What signals reversal

    # Smart execution
    use_market_if_close_pct: float  # If within X% of TP, use market order
    use_market_if_reversal_imminent: bool

    # Partial exits
    partial_exit_pct: float  # Take 50% at TP1, 50% at TP2, etc.

    # Failed TP scenario
    if_missed_and_reversing: str  # "EXIT_MARKET", "HOLD", "TRAIL_STOP"

    description: str


class TradeScenarioPlanner:
    """
    Plans all future scenarios for a trade

    Creates complete battle plan BEFORE entering:
    - Where to enter
    - Where to exit if wrong
    - When to adjust stops
    - How to take profit
    - What invalidates the setup
    """

    def __init__(self):
        # Configuration for invalidation sensitivity
        self.min_pullback_for_invalidation_pct = 0.40  # 40% of range = real invalidation
        self.candle_close_invalidation_threshold = 0.005  # 0.5% below entry

        # Stop adjustment config - MODIFIED FOR SCALPING
        self.breakeven_profit_threshold = 0.003  # 0.3% profit = move to BE
        self.trail_profit_threshold = 0.005  # 0.5% profit = start trailing
        self.stop_trailing_back_at_profit = 0.012  # 1.2% profit = never trail back

        # TP execution config
        self.use_market_within_pct = 0.003  # Within 0.3% of TP = use market
        self.reversal_detection_lookback = 3  # Last 3 candles

    def create_trade_plan(
        self,
        decision,  # IntelligentDecision from brain
        market_intel,  # MarketIntelligence
        current_price: float
    ) -> TradePlan:
        """
        Create complete trade plan with all scenarios

        This is the master plan that monitors everything
        """

        print("\n[TRADE SCENARIO PLANNER - CREATING BATTLE PLAN]")
        print("="*80)

        direction = decision.direction
        entry_zone = decision.entry_zone
        initial_stop = decision.stop_loss
        targets = decision.take_profits

        print(f"\n[TRADE PARAMETERS]")
        print(f"  Direction: {direction}")
        print(f"  Entry Zone: ${entry_zone[0]:.2f} - ${entry_zone[1]:.2f}")
        print(f"  Initial Stop: ${initial_stop:.2f}")
        print(f"  Targets: {', '.join([f'${tp:.2f}' for tp in targets])}")
        print(f"  Risk/Reward: {decision.risk_reward:.2f}:1")

        # Extract key levels
        print(f"\n[EXTRACTING KEY MARKET LEVELS]")
        key_supports = [s['price'] for s in market_intel.swing_lows] if market_intel.swing_lows else []
        key_resistances = [r['price'] for r in market_intel.swing_highs] if market_intel.swing_highs else []
        print(f"  Support levels: {len(key_supports)} found")
        if key_supports:
            print(f"    Strongest: ${min(key_supports):.2f}")
        print(f"  Resistance levels: {len(key_resistances)} found")
        if key_resistances:
            print(f"    Strongest: ${max(key_resistances):.2f}")

        # Determine invalidation level
        print(f"\n[CALCULATING INVALIDATION LEVELS]")
        if direction == 'LONG':
            invalidation = min(key_supports) if key_supports else initial_stop * 0.995
            last_swing_low = min(key_supports) if key_supports else current_price * 0.99
            last_swing_high = max(key_resistances) if key_resistances else current_price * 1.01
            print(f"  Invalidation level: ${invalidation:.2f} (key support)")
            print(f"  Last swing low: ${last_swing_low:.2f}")
            print(f"  Last swing high: ${last_swing_high:.2f}")
        else:  # SHORT
            invalidation = max(key_resistances) if key_resistances else initial_stop * 1.005
            last_swing_high = max(key_resistances) if key_resistances else current_price * 1.01
            last_swing_low = min(key_supports) if key_supports else current_price * 0.99
            print(f"  Invalidation level: ${invalidation:.2f} (key resistance)")
            print(f"  Last swing high: ${last_swing_high:.2f}")
            print(f"  Last swing low: ${last_swing_low:.2f}")

        # Create invalidation scenarios
        print(f"\n[PLANNING INVALIDATION SCENARIOS]")
        print("  Learning from Horus: Don't close on minor pullbacks!")
        invalidation_scenarios = self._plan_invalidation_scenarios(
            direction, current_price, initial_stop, invalidation,
            last_swing_low, last_swing_high, market_intel
        )

        # Create stop adjustment plan
        print(f"\n[PLANNING STOP ADJUSTMENTS]")
        print("  Learning from Horus: Smart trailing, know when to stop!")
        stop_adjustment_plan = self._plan_stop_adjustments(
            direction, entry_zone[0], initial_stop, targets,
            last_swing_low, last_swing_high
        )

        # Create TP execution plan
        print(f"\n[PLANNING TP EXECUTION]")
        print("  Learning from Horus: Use market orders when needed!")
        tp_execution_plan = self._plan_tp_execution(
            direction, targets, current_price
        )

        print(f"\n[BATTLE PLAN COMPLETE]")
        print(f"  {len(invalidation_scenarios)} invalidation scenarios planned")
        print(f"  {len(stop_adjustment_plan)} stop adjustment triggers set")
        print(f"  {len(tp_execution_plan)} TP execution plans ready")
        print("="*80)

        return TradePlan(
            entry_price=entry_zone[0],
            entry_zone=entry_zone,
            direction=direction,
            initial_stop=initial_stop,
            targets=targets,
            key_support_levels=key_supports,
            key_resistance_levels=key_resistances,
            invalidation_level=invalidation,
            last_swing_high=last_swing_high,
            last_swing_low=last_swing_low,
            entry_candle_close=current_price,
            invalidation_scenarios=invalidation_scenarios,
            stop_adjustment_plan=stop_adjustment_plan,
            tp_execution_plan=tp_execution_plan,
            position_size=decision.position_size_multiplier,
            risk_amount=decision.max_risk_percent,
            risk_reward_ratio=decision.risk_reward
        )

    def _plan_invalidation_scenarios(
        self,
        direction: str,
        entry: float,
        stop: float,
        invalidation_level: float,
        last_swing_low: float,
        last_swing_high: float,
        market_intel
    ) -> List[InvalidationScenario]:
        """Plan all invalidation scenarios"""

        print(f"  Creating invalidation scenarios for {direction} trade...")
        scenarios = []

        if direction == 'LONG':
            print(f"  [LONG Invalidation Logic]")
            # Scenario 1: Structure broken (key support violated)
            scenarios.append(InvalidationScenario(
                scenario_type=InvalidationReason.STRUCTURE_BROKEN,
                trigger_condition=f"Candle closes below ${last_swing_low:.2f} (last swing low)",
                trigger_level=last_swing_low,
                action="EXIT_MARKET",
                urgency="ON_CANDLE_CLOSE",
                requires_candle_close=True,
                confirmation_bars=1,
                severity=0.90,
                description="Key support structure broken - setup invalidated"
            ))

            # Scenario 2: Bearish candle closes below entry (Horus fix)
            candle_invalidation = entry * (1 - self.candle_close_invalidation_threshold)
            scenarios.append(InvalidationScenario(
                scenario_type=InvalidationReason.CANDLE_CLOSE_INVALIDATION,
                trigger_condition=f"Bearish candle closes below ${candle_invalidation:.2f} ({self.candle_close_invalidation_threshold*100:.1f}% below entry)",
                trigger_level=candle_invalidation,
                action="EXIT_MARKET",
                urgency="ON_CANDLE_CLOSE",
                requires_candle_close=True,
                confirmation_bars=1,
                severity=0.75,
                description="Strong bearish rejection at entry - likely failed"
            ))

            # Scenario 3: Invalidation level hit
            scenarios.append(InvalidationScenario(
                scenario_type=InvalidationReason.STRUCTURE_BROKEN,
                trigger_condition=f"Price hits ${invalidation_level:.2f} (setup invalidation level)",
                trigger_level=invalidation_level,
                action="EXIT_MARKET",
                urgency="IMMEDIATE",
                requires_candle_close=False,
                confirmation_bars=0,
                severity=1.0,
                description="Trade thesis completely invalidated"
            ))

        else:  # SHORT
            # Scenario 1: Structure broken (key resistance violated)
            scenarios.append(InvalidationScenario(
                scenario_type=InvalidationReason.STRUCTURE_BROKEN,
                trigger_condition=f"Candle closes above ${last_swing_high:.2f} (last swing high)",
                trigger_level=last_swing_high,
                action="EXIT_MARKET",
                urgency="ON_CANDLE_CLOSE",
                requires_candle_close=True,
                confirmation_bars=1,
                severity=0.90,
                description="Key resistance structure broken - setup invalidated"
            ))

            # Scenario 2: Bullish candle closes above entry
            candle_invalidation = entry * (1 + self.candle_close_invalidation_threshold)
            scenarios.append(InvalidationScenario(
                scenario_type=InvalidationReason.CANDLE_CLOSE_INVALIDATION,
                trigger_condition=f"Bullish candle closes above ${candle_invalidation:.2f} ({self.candle_close_invalidation_threshold*100:.1f}% above entry)",
                trigger_level=candle_invalidation,
                action="EXIT_MARKET",
                urgency="ON_CANDLE_CLOSE",
                requires_candle_close=True,
                confirmation_bars=1,
                severity=0.75,
                description="Strong bullish rejection at entry - likely failed"
            ))

            # Scenario 3: Invalidation level hit
            scenarios.append(InvalidationScenario(
                scenario_type=InvalidationReason.STRUCTURE_BROKEN,
                trigger_condition=f"Price hits ${invalidation_level:.2f} (setup invalidation level)",
                trigger_level=invalidation_level,
                action="EXIT_MARKET",
                urgency="IMMEDIATE",
                requires_candle_close=False,
                confirmation_bars=0,
                severity=1.0,
                description="Trade thesis completely invalidated"
            ))

        # Common scenarios for both directions

        # Scenario: Range trap detected
        scenarios.append(InvalidationScenario(
            scenario_type=InvalidationReason.RANGE_TRAP_DETECTED,
            trigger_condition="Range trap severity >70% detected while in trade",
            trigger_level=None,
            action="EXIT_MARKET",
            urgency="ON_CANDLE_CLOSE",
            requires_candle_close=True,
            confirmation_bars=2,
            severity=0.85,
            description="Entered range trap - likely to get chopped"
        ))

        # Scenario: Stop hunt mode activated
        scenarios.append(InvalidationScenario(
            scenario_type=InvalidationReason.STOP_HUNT_MODE,
            trigger_condition="Stop hunt mode activated (market hunting stops)",
            trigger_level=None,
            action="REDUCE_SIZE",
            urgency="WAIT_FOR_CONFIRMATION",
            requires_candle_close=True,
            confirmation_bars=1,
            severity=0.70,
            description="Stop hunt mode - reduce exposure"
        ))

        print(f"  [CREATED {len(scenarios)} INVALIDATION SCENARIOS]")
        for i, scenario in enumerate(scenarios, 1):
            print(f"    {i}. {scenario.description}")
            print(f"       Trigger: {scenario.trigger_condition}")
            print(f"       Action: {scenario.action} ({scenario.urgency})")
            print(f"       Severity: {scenario.severity*100:.0f}%")

        return scenarios

    def _plan_stop_adjustments(
        self,
        direction: str,
        entry: float,
        initial_stop: float,
        targets: List[float],
        last_swing_low: float,
        last_swing_high: float
    ) -> List[StopAdjustmentScenario]:
        """Plan stop adjustment scenarios"""

        print(f"  Creating stop adjustment scenarios for {direction} trade...")
        adjustments = []

        # Calculate profit thresholds
        if direction == 'LONG':
            breakeven_price = entry * (1 + self.breakeven_profit_threshold)
            trail_start_price = entry * (1 + self.trail_profit_threshold)
            stop_trailing_back_price = entry * (1 + self.stop_trailing_back_at_profit)
            print(f"  [LONG Stop Logic]")
            print(f"    Breakeven trigger: ${breakeven_price:.2f} ({self.breakeven_profit_threshold*100:.1f}% profit)")
            print(f"    Trail start: ${trail_start_price:.2f} ({self.trail_profit_threshold*100:.1f}% profit)")
            print(f"    Stop trailing back at: ${stop_trailing_back_price:.2f} ({self.stop_trailing_back_at_profit*100:.1f}% profit)")
        else:
            breakeven_price = entry * (1 - self.breakeven_profit_threshold)
            trail_start_price = entry * (1 - self.trail_profit_threshold)
            stop_trailing_back_price = entry * (1 - self.stop_trailing_back_at_profit)
            print(f"  [SHORT Stop Logic]")
            print(f"    Breakeven trigger: ${breakeven_price:.2f} ({self.breakeven_profit_threshold*100:.1f}% profit)")
            print(f"    Trail start: ${trail_start_price:.2f} ({self.trail_profit_threshold*100:.1f}% profit)")
            print(f"    Stop trailing back at: ${stop_trailing_back_price:.2f} ({self.stop_trailing_back_at_profit*100:.1f}% profit)")

        # Adjustment 1: Move to breakeven
        adjustments.append(StopAdjustmentScenario(
            trigger=StopAdjustmentTrigger.MOVE_TO_BREAKEVEN,
            trigger_condition=f"Price reaches ${breakeven_price:.2f} ({self.breakeven_profit_threshold*100:.1f}% profit)",
            trigger_price=breakeven_price,
            new_stop_calculation="entry + spread",
            buffer_pct=0.001,  # 0.1% buffer for fees
            min_profit_pct=self.breakeven_profit_threshold,
            max_times_to_adjust=1,
            allow_trailing_back=False,
            max_trail_back_distance=0,
            stop_trailing_back_at_profit_pct=self.stop_trailing_back_at_profit,
            description="Move stop to breakeven (protect capital)"
        ))

        # Adjustment 2: Trail to structure
        if direction == 'LONG':
            trail_stop_calc = "last_swing_low + 0.3% buffer"
        else:
            trail_stop_calc = "last_swing_high - 0.3% buffer"

        adjustments.append(StopAdjustmentScenario(
            trigger=StopAdjustmentTrigger.TRAIL_TO_STRUCTURE,
            trigger_condition=f"Price reaches ${trail_start_price:.2f} ({self.trail_profit_threshold*100:.1f}% profit)",
            trigger_price=trail_start_price,
            new_stop_calculation=trail_stop_calc,
            buffer_pct=0.003,
            min_profit_pct=self.trail_profit_threshold,
            max_times_to_adjust=5,  # Can trail multiple times
            allow_trailing_back=True,  # Initially yes
            max_trail_back_distance=0.005,  # Max 0.5% back
            stop_trailing_back_at_profit_pct=self.stop_trailing_back_at_profit,
            description="Trail stop to last swing structure"
        ))

        # Adjustment 3: Lock profit at TP1
        if targets:
            tp1_trigger = targets[0] * 0.9 if direction == 'LONG' else targets[0] * 1.1  # 90% of way to TP1

            adjustments.append(StopAdjustmentScenario(
                trigger=StopAdjustmentTrigger.LOCK_PROFIT,
                trigger_condition=f"Price reaches 90% of TP1 (${tp1_trigger:.2f})",
                trigger_price=tp1_trigger,
                new_stop_calculation="entry + 50% of current profit",
                buffer_pct=0.002,
                min_profit_pct=0.01,  # 1% minimum
                max_times_to_adjust=1,
                allow_trailing_back=False,  # Never trail back from here
                max_trail_back_distance=0,
                stop_trailing_back_at_profit_pct=0.01,
                description="Lock in partial profit before TP1"
            ))

        print(f"  [CREATED {len(adjustments)} STOP ADJUSTMENT SCENARIOS]")
        for i, adj in enumerate(adjustments, 1):
            print(f"    {i}. {adj.description}")
            print(f"       Trigger: {adj.trigger_condition}")
            print(f"       New stop: {adj.new_stop_calculation}")
            if adj.allow_trailing_back:
                print(f"       Can trail back: YES (until {adj.stop_trailing_back_at_profit_pct*100:.1f}% profit)")
            else:
                print(f"       Can trail back: NO (locked)")

        return adjustments

    def _plan_tp_execution(
        self,
        direction: str,
        targets: List[float],
        entry: float
    ) -> List[TPExecutionScenario]:
        """Plan TP execution scenarios"""

        print(f"  Creating TP execution scenarios for {len(targets)} targets...")
        scenarios = []

        for i, tp in enumerate(targets):
            print(f"  [TP{i+1} @ ${tp:.2f}]")
            # Partial exit percentages
            if len(targets) == 1:
                partial_pct = 1.0  # 100% at single TP
            elif i == 0:
                partial_pct = 0.5  # 50% at TP1
            elif i == len(targets) - 1:
                partial_pct = 1.0  # Remaining 50% at final TP
            else:
                partial_pct = 0.3  # 30% at middle TPs

            # Calculate "close enough" threshold
            close_enough_price = tp * (1 - self.use_market_within_pct) if direction == 'LONG' else tp * (1 + self.use_market_within_pct)

            scenarios.append(TPExecutionScenario(
                tp_level=tp,
                tp_type="DYNAMIC",  # Smart switching between limit/market
                watch_for_reversal=True,
                reversal_indicators=[
                    "Bearish engulfing at TP" if direction == 'LONG' else "Bullish engulfing at TP",
                    "Wick rejection at TP level",
                    "Volume spike with reversal",
                    "Failed to break TP after 3 attempts"
                ],
                use_market_if_close_pct=self.use_market_within_pct,
                use_market_if_reversal_imminent=True,
                partial_exit_pct=partial_pct,
                if_missed_and_reversing="EXIT_MARKET",  # Don't wait - get out
                description=f"TP{i+1} @ ${tp:.2f} - {partial_pct*100:.0f}% of position"
            ))
            print(f"    Exit {partial_pct*100:.0f}% of position at ${tp:.2f}")
            print(f"    Use market if within {self.use_market_within_pct*100:.2f}% of TP")
            print(f"    Watch for reversal signals: {len(scenarios[i].reversal_indicators)} indicators")
            print(f"    If missed and reversing: {scenarios[i].if_missed_and_reversing}")

        print(f"  [CREATED {len(scenarios)} TP EXECUTION SCENARIOS]")

        return scenarios


if __name__ == "__main__":
    print("Trade Scenario Planner - Future Projection System")
    print("Plans all scenarios BEFORE entering trade")
    print("Learns from Horus failures to execute intelligently")
