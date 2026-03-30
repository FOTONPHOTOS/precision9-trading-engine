# Arsenal Strategy Router - Integration Guide

## Overview

This module adds intelligent strategy switching to Arsenal, solving the problem:
- **Before**: Arsenal blocks all trades during ranging markets (missed opportunities)
- **After**: Arsenal switches to mean reversion during ranges, then back to directional on breakout

## Components Created

### 1. `range_breakout_detector.py`
**Purpose**: Detect REAL breakouts with fakeout filtering

**Key Features**:
- Volume expansion validation (1.5x minimum)
- Body close confirmation (not just wicks)
- Follow-through candle requirement
- Multiple level test tracking
- Fakeout probability scoring

**Thresholds** (tunable):
```python
min_volume_expansion = 1.5          # 1.5x average volume required
min_body_close_beyond = 0.003       # 0.3% body close beyond level
confirmation_candles = 2            # Require 2 candles confirming
max_immediate_reversal_pct = 0.002  # If reverses >0.2% = fake
```

### 2. `mean_reversion_engine.py`
**Purpose**: Generate signals during ranging markets (FIXED VERSION)

**Key Fixes Applied**:
-  Lowered Z-score threshold from 2.0 → 1.2 (more sensitive)
-  Lowered VWAP deviation from 1.5% → 0.8% (catches smaller moves)
-  Changed conditions from AND → OR (either triggers signal)
-  Added diagnostic logging to debug signal generation

**Why It Never Traded Before**:
```python
# OLD (Horus version):
z_score_threshold = 2.0     # Too strict (price 2 std devs from mean)
vwap_deviation = 0.015      # 1.5% deviation required
if z_score AND deviation:   # Both must be met (too strict!)

# NEW (Arsenal version):
z_score_threshold = 1.2     # More realistic (1.2 std devs)
vwap_deviation = 0.008      # 0.8% deviation (tighter ranges)
if z_score OR deviation:    # Either condition triggers
```

**TP/SL Logic**:
- Tight ranges = Tight stops (0.26%-0.46% based on confidence)
- 1:1 Risk/Reward ratio (quick in, quick out)
- Single TP exit (no TP1/TP2 splits)

### 3. `arsenal_strategy_router.py`
**Purpose**: Main orchestrator - switches between strategies

**Strategy Flow**:
```
1. Normal Market
    Range Trap Detector analyzes structure
    If trapped → Activate Mean Reversion
    If clear → Continue Directional

2. Range Detected
    Mean Reversion Engine activated
    Block directional signals
    Generate mean reversion signals
    Monitor for breakout

3. Breakout Confirmed
    Deactivate Mean Reversion
    Enable Directional Trading
    Follow breakout direction
```

**Cooldown System**:
- 60 seconds between strategy switches (prevents whipsaws)
- Emergency override for standby mode

## Integration into `intelligent_strategy_brain.py`

### Step 1: Import the Router

Add to imports section:
```python
from arsenal_strategy_router import ArsenalStrategyRouter, StrategyDecision
```

### Step 2: Initialize in `__init__`

```python
class IntelligentStrategyBrain:
    def __init__(self):
        # ... existing code ...

        # Initialize strategy router (NEW)
        self.strategy_router = ArsenalStrategyRouter(symbol="SOLUSDT")

        logger.info(" Arsenal Strategy Router initialized")
        logger.info("   - Range detection active")
        logger.info("   - Mean reversion standby")
        logger.info("   - Breakout detection armed")
```

### Step 3: Update Market Data

In your main data processing loop (wherever you update prices):
```python
def process_market_data(self, price: float, volume: float, timestamp: float):
    # Update strategy router with latest data
    self.strategy_router.update_market_data(price, volume, timestamp)

    # ... rest of your processing ...
```

### Step 4: Modify Signal Generation

In your `analyze()` method (before creating signals):

```python
def analyze(self, market_intel: MarketIntelligence) -> IntelligentDecision:
    # ... existing analysis code ...

    # STEP X: STRATEGY ROUTING (NEW)
    reasoning_chain.append("\n[STRATEGY ROUTING]")

    strategy_decision = self.strategy_router.analyze_and_route(
        current_price=current_price,
        current_volume=current_volume,
        swing_highs=trendlines.swing_highs if trendlines else [],
        swing_lows=trendlines.swing_lows if trendlines else [],
        patterns=trendlines.patterns if trendlines else [],
        candle_closes=recent_closes,  # Last 5 candle closes
        chop_confidence=trap.trap_severity if trap else 0.0
    )

    reasoning_chain.append(f"  Active Strategy: {strategy_decision.active_strategy}")
    reasoning_chain.append(f"  Should Trade: {strategy_decision.should_trade}")
    reasoning_chain.append(f"  Reason: {strategy_decision.reason}")

    # Handle strategy-specific logic
    if strategy_decision.active_strategy == "MEAN_REVERSION":
        # MEAN REVERSION MODE
        if strategy_decision.mean_reversion_signal:
            mr_signal = strategy_decision.mean_reversion_signal

            reasoning_chain.append(f"\n   MEAN REVERSION SIGNAL:")
            reasoning_chain.append(f"     Direction: {mr_signal.direction}")
            reasoning_chain.append(f"     Entry: ${mr_signal.entry_price:.2f}")
            reasoning_chain.append(f"     TP: ${mr_signal.take_profit:.2f}")
            reasoning_chain.append(f"     SL: ${mr_signal.stop_loss:.2f}")
            reasoning_chain.append(f"     Confidence: {mr_signal.confidence:.1%}")

            # CREATE MEAN REVERSION TRADE DECISION
            return IntelligentDecision(
                should_trade=True,
                direction=mr_signal.direction,
                confidence=mr_signal.confidence,
                signal_strength='MEAN_REVERSION',
                primary_reason=mr_signal.reason,
                entry_price=mr_signal.entry_price,
                stop_loss=mr_signal.stop_loss,
                take_profit_1=mr_signal.take_profit,
                take_profit_2=mr_signal.mean_price,  # Secondary at actual mean
                take_profit_3=mr_signal.mean_price,
                position_multiplier=0.75,  # Reduce size for MR trades
                max_risk=0.5,  # Lower risk for MR
                # ... rest of fields ...
            )
        else:
            # No MR signal yet, wait
            reasoning_chain.append("  ⏳ Waiting for mean reversion setup...")
            return self._create_no_trade_decision("Mean reversion mode - waiting for signal")

    elif strategy_decision.active_strategy == "STANDBY":
        # STANDBY MODE - Don't trade
        reasoning_chain.append("   STANDBY MODE - Market conditions unclear")
        return self._create_no_trade_decision(strategy_decision.reason)

    elif strategy_decision.active_strategy == "DIRECTIONAL":
        # DIRECTIONAL MODE - Continue with normal Arsenal logic
        reasoning_chain.append("   DIRECTIONAL MODE - Normal Arsenal analysis")

        # ... continue with existing Arsenal signal generation ...
        # Your existing code for trendline breaks, patterns, etc.

    # ... rest of existing analyze() code ...
```

### Step 5: Handle Breakout Signals

After a breakout is confirmed, you may want to immediately look for directional entries:

```python
if strategy_decision.is_breaking_out:
    reasoning_chain.append(f"\n   BREAKOUT CONFIRMED")
    reasoning_chain.append(f"     Boost directional confidence by +15%")

    # Increase confidence for directional trades following breakout
    if direction_matches_breakout:
        confidence = min(1.0, confidence + 0.15)
```

## Testing

### Unit Test
```python
# Test mean reversion signal generation
from mean_reversion_engine import MeanReversionEngine

engine = MeanReversionEngine("SOLUSDT")
engine.activate("Test")

# Simulate prices deviating from mean
for i in range(30):
    price = 200 + (i % 10) * 0.5  # Oscillating prices
    volume = 1000
    engine.update_price(price, volume)

# Try to generate signal
market_mean = engine.calculate_market_mean()
if market_mean:
    signal = engine.generate_signal(205, market_mean, chop_confidence=0.6)
    if signal:
        print(f" Signal generated: {signal.direction} at ${signal.entry_price:.2f}")
    else:
        print(" No signal (conditions not met)")
```

### Integration Test
```bash
# Run Arsenal with new router
python intelligent_strategy_brain.py

# Look for these log messages:
# "ARSENAL STRATEGY ROUTER INITIALIZED"
# "STRATEGY SWITCH" (when switching modes)
# "MEAN REVERSION SIGNAL" (when MR triggers)
# "BREAKOUT DETECTED" (when range breaks)
```

## Configuration Tuning

### If Too Many Mean Reversion Signals:
```python
# In mean_reversion_engine.py, increase thresholds:
self.z_score_threshold = 1.5  # From 1.2
self.vwap_deviation_threshold = 0.010  # From 0.008 (1.0% instead of 0.8%)
```

### If Mean Reversion Still Not Triggering:
```python
# In mean_reversion_engine.py, decrease further:
self.z_score_threshold = 1.0  # From 1.2
self.vwap_deviation_threshold = 0.006  # From 0.008 (0.6% instead of 0.8%)
```

### If Too Many False Breakouts:
```python
# In range_breakout_detector.py, increase requirements:
self.min_volume_expansion = 2.0  # From 1.5 (require 2x volume)
self.confirmation_candles = 3  # From 2 (require 3 candles)
```

### If Missing Real Breakouts:
```python
# In range_breakout_detector.py, decrease requirements:
self.min_volume_expansion = 1.3  # From 1.5 (allow 1.3x volume)
self.min_body_close_beyond = 0.002  # From 0.003 (0.2% instead of 0.3%)
```

## Expected Behavior

### Scenario 1: Tight Range (0.8% range size)
```
1. Range Trap Detector: "TRAPPED - 0.8% range"
2. Strategy Router: "Switching to MEAN_REVERSION"
3. Mean Reversion Engine: Activated
4. Arsenal: Blocks directional signals
5. Mean Reversion: Generates SHORT at deviation
6. Trade executed with tight TP/SL
```

### Scenario 2: Range Breakout (Bullish)
```
1. Price breaks above range_high
2. Breakout Detector: "Volume 2.1x, body close 0.4% above"
3. Follow-through candle confirms
4. Strategy Router: "BREAKOUT CONFIRMED - Switching to DIRECTIONAL"
5. Mean Reversion: Deactivated
6. Arsenal: Resumes normal directional trading
```

### Scenario 3: Fake Breakout
```
1. Price breaks above range_high (wick)
2. Breakout Detector: "No volume, wick only, no body close"
3. Fakeout probability: 75%
4. Breakout NOT confirmed
5. Strategy Router: Stays in MEAN_REVERSION
6. Arsenal: Continues range trading
```

## Performance Metrics

Track these via `strategy_router.get_status()`:
- `current_strategy`: Active strategy name
- `strategy_switches`: Total switches (should be low, <10/day)
- `mean_reversion_signals`: Signals generated in MR mode
- `time_since_last_switch`: Cooldown tracking

## Troubleshooting

### Problem: Mean reversion never activates
**Check**:
1. Is range trap detector finding ranges? (check `trap_analysis.is_trapped`)
2. Are swing highs/lows being passed correctly?
3. Enable debug logging: `logging.getLogger('ARSENAL_ROUTER').setLevel(logging.DEBUG)`

### Problem: Mean reversion active but no signals
**Check**:
1. Is `mean_reversion.is_active == True`?
2. Check Z-score and deviation in logs
3. Lower thresholds if market ranges are too tight

### Problem: Too many strategy switches
**Solution**:
- Increase `switch_cooldown` from 60s to 120s
- Increase trap severity threshold before switching

## Files Modified

### New Files (Created):
-  `range_breakout_detector.py` (338 lines)
-  `mean_reversion_engine.py` (442 lines, FIXED)
-  `arsenal_strategy_router.py` (469 lines)

### Files to Modify:
- `intelligent_strategy_brain.py` (add routing logic)

### Files Copied to VPS:
-  All 3 modules copied to `Trendline_Arsenal_VPS/`

## Next Steps

1.  Create all modules
2.  Copy to VPS folder
3. ⏳ Integrate into `intelligent_strategy_brain.py`
4. ⏳ Test in simulation mode
5. ⏳ Monitor for 24 hours
6. ⏳ Tune thresholds based on results
7. ⏳ Deploy to production

## Summary

**Problem Solved**: Arsenal was missing opportunities by blocking all trades in ranging markets.

**Solution Implemented**:
- Robust range detection (existing)
- Intelligent mean reversion trading (NEW, FIXED)
- Validated breakout detection (NEW)
- Automatic strategy switching (NEW)

**Expected Impact**:
- More trades during range-bound markets
- Reduced drawdown from false breakouts
- Better adaptation to changing market conditions
- Profitable both in trends AND ranges

**Key Innovation**: Arsenal now has TWO profit modes instead of ONE:
1. Directional Trading (trends)
2. Mean Reversion (ranges)

This creates a true all-weather trading system. 
