# ARSENAL QUICK START GUIDE

##  Run Tests (Choose One)

### Option 1: Complete Arsenal Test
```bash
cd "G:\python files\precision9\Simulation Environment\Trendline_Detectory"
python test_ultimate_arsenal.py
```
**What it does**: Tests all 11 modules with intelligent brain (no memory)

---

### Option 2: Arsenal With Memory (RECOMMENDED)
```bash
cd "G:\python files\precision9\Simulation Environment\Trendline_Detectory"
python test_arsenal_with_memory.py
```
**What it does**: Full arsenal + persistent memory that survives restarts

**Run it twice to see memory in action!**

---

### Option 3: Liquidity Sweeps Only
```bash
python test_liquidity_sweeps.py
```
**What it does**: Tests stop hunt detection and safe stop placement

---

##  Code Usage

### Without Memory
```python
from intelligent_strategy_brain import IntelligentStrategyBrain, MarketIntelligence

# Create brain
brain = IntelligentStrategyBrain()

# Create market intelligence (gather from all modules)
market_intel = MarketIntelligence(
    current_price=219.50,
    trend_direction='uptrend',
    trend_strength=0.65,
    swing_highs=[...],
    swing_lows=[...],
    candle_patterns=[...],
    fvgs=[...],
    order_blocks=[...],
    liquidity_sweeps=[...],
    liquidity_pools=[...],
    range_trap_analysis=trap_analysis,
    stop_hunt_warning=stop_hunt_warning,
    confluence_score=85,
    timestamp=datetime.utcnow()
)

# Analyze
decision = brain.analyze(market_intel)

# Use decision
if decision.should_trade:
    print(f"TRADE {decision.direction} @ {decision.entry_zone}")
    print(f"Stop: ${decision.stop_loss:.2f}")
    print(f"Targets: {decision.take_profits}")
else:
    print(f"BLOCKED: {decision.blockers}")
```

---

### With Memory (RECOMMENDED)
```python
from intelligent_strategy_brain_with_memory import IntelligentStrategyBrainWithMemory

# Create brain with memory (loads history automatically)
brain = IntelligentStrategyBrainWithMemory("my_memory.db")

# Show what it remembers
brain.show_memory_summary()

# Analyze (same as before)
decision = brain.analyze(market_intel)

# Print with memory context
brain.print_enhanced_decision(decision)

# Always close when done
brain.close()
```

---

##  Key Outputs

### Decision Object
```python
decision.direction           # 'LONG', 'SHORT', 'NEUTRAL'
decision.confidence         # 0.0 - 1.0
decision.signal_strength    # 'WEAK', 'MODERATE', 'STRONG', 'VERY_STRONG', 'BLOCKED'
decision.should_trade       # True/False
decision.urgency           # 'IMMEDIATE', 'SETUP_FORMING', 'WAIT', 'DO_NOT_TRADE'

# Entry/Exit
decision.entry_zone        # (low, high) tuple
decision.stop_loss         # Float
decision.take_profits      # [tp1, tp2, tp3]
decision.risk_reward       # Float (e.g., 2.5 = 2.5:1 RR)

# Position Sizing
decision.position_size_multiplier  # 0.25 - 1.0 (% of normal size)
decision.max_risk_percent         # 0.5 - 2.0 (% of capital)

# Reasoning
decision.reasoning_chain   # List of reasoning steps
decision.blockers         # List of critical blocks
decision.warnings         # List of warnings
decision.opportunities    # List of opportunities

# Meta
decision.analysis_quality  # 0.0 - 1.0
decision.decision_timestamp  # DateTime
```

---

##  What Gets Blocked

### Critical Blockers (Confidence → 0%)
1. **Range Trap >70%** - Market stuck in tight range
2. **Stop Hunt Mode** - Market actively hunting stops

### Warning Levels (Reduces Confidence)
- **High Warning** (-50%): Multiple severe issues
- **Medium Warning** (-25%): Some concerning patterns
- **Low Warning** (-10%): Minor cautions

---

##  Memory System

### Check Memory Stats
```python
stats = brain.memory.get_memory_stats()
print(f"Events: {stats['total_events']}")
print(f"Decisions: {stats['total_decisions']}")
print(f"Days: {stats['days_of_history']:.1f}")
```

### Query Recent Events
```python
# Get sweeps from last 24 hours
sweeps = brain.memory.get_recent_events(hours=24, event_type='sweep')

# Check if trapped
active_range = brain.memory.get_active_range_period()
if active_range:
    print(f"Trapped for {active_range['duration']} hours")

# Check regime
regime = brain.memory.get_current_regime()
print(f"Current: {regime['regime_type']}")
```

### Get Context Summary
```python
context = brain.memory.get_market_context_summary(lookback_hours=24)
print(context['context_summary'])  # Natural language summary
```

---

##  Typical Workflow

### 1. Initialize (Once)
```python
brain = IntelligentStrategyBrainWithMemory("sol_memory.db")
```

### 2. Every Analysis Cycle
```python
# Gather all module data
swing_highs = find_swing_highs(df)
swing_lows = find_swing_lows(df)
patterns = detect_candle_close_patterns(df)
fvgs = fvg_detector.detect(df, current_price)
obs = ob_detector.detect(df, current_price)
sweeps = liquidity_detector.detect_sweeps(df, swing_highs, swing_lows)
pools = liquidity_detector.map_liquidity_pools(swing_highs, swing_lows, sweeps, current_price)
stop_hunt = liquidity_detector.detect_stop_hunt_mode(sweeps, pools)
trap = trap_detector.analyze(swing_highs, swing_lows, patterns, current_price)
confluence = analyzer.calculate_confluence_points(...)

# Create intelligence
market_intel = MarketIntelligence(...)

# Analyze
decision = brain.analyze(market_intel)

# Act on decision
if decision.should_trade:
    execute_trade(decision)
else:
    log_blocked(decision.blockers)
```

### 3. Cleanup (On Exit)
```python
brain.close()
```

---

##  Interpreting Results

### Example: Blocked Decision
```
[BLOCKED] TRADE SIGNAL: NEUTRAL
Confidence: 0%
Signal Strength: BLOCKED

Blockers:
- RANGE TRAP DETECTED: 88% severity
```
**Action**: DO NOT TRADE. Market is dangerous.

---

### Example: Weak Signal
```
[GO] TRADE SIGNAL: LONG
Confidence: 48%
Signal Strength: WEAK

Warnings:
- Elevated stop hunt activity (40%)
- Weak trend (52%)
```
**Action**: Can trade but use smaller position size (50%).

---

### Example: Strong Signal
```
[GO] TRADE SIGNAL: LONG
Confidence: 78%
Signal Strength: STRONG

Opportunities:
- Strong uptrend (85%)
- High-quality Order Block nearby
- Excellent confluence (95 points)
```
**Action**: TRADE with full position size.

---

##  Configuration

### Adjust Thresholds (Optional)
```python
brain = IntelligentStrategyBrain()

# Confidence thresholds
brain.min_confidence_to_trade = 0.45  # Default: 0.45 (45%)
brain.strong_confidence = 0.65        # Default: 0.65
brain.very_strong_confidence = 0.75   # Default: 0.75

# Risk thresholds
brain.max_acceptable_trap_severity = 0.70  # Default: 0.70 (70%)
brain.max_acceptable_stop_hunt_severity = 0.65  # Default: 0.65

# Confluence requirements
brain.min_confluence_points = 30  # Default: 30
brain.good_confluence = 50        # Default: 50
brain.excellent_confluence = 70   # Default: 70
```

---

##  Important Files

### You Need
- `intelligent_strategy_brain_with_memory.py` - Brain
- `market_memory.py` - Memory system
- All detector modules (fvg, order_block, liquidity, range_trap, etc.)

### Tests
- `test_arsenal_with_memory.py` - Complete test
- `test_ultimate_arsenal.py` - No memory test

### Documentation
- `ARSENAL_COMPLETE_SUMMARY.md` - Full overview
- `MEMORY_SYSTEM_GUIDE.md` - Memory details
- `QUICK_START.md` - This file

---

##  Troubleshooting

### "Module not found"
```bash
# Make sure you're in the right directory
cd "G:\python files\precision9\Simulation Environment\Trendline_Detectory"
```

### "Database locked"
```python
# Always close properly
brain.close()
```

### "No data in memory"
Run the test multiple times to build history.

### Unicode errors on Windows
Already fixed - uses `[BLOCKED]` instead of emojis.

---

##  Best Practices

1. **Start Fresh**: Run tests first to understand output
2. **Build Memory**: Let it run for days/weeks to build intelligence
3. **Trust Blocks**: When it blocks, there's a good reason
4. **Review Reasoning**: Read the reasoning_chain to understand why
5. **Track Outcomes**: Update decision outcomes to improve learning
6. **One DB Per Symbol**: Separate memory for BTC, SOL, etc.
7. **Backup Memory**: Copy .db files regularly

---

##  Learn More

- Read `ARSENAL_COMPLETE_SUMMARY.md` for full system overview
- Read `MEMORY_SYSTEM_GUIDE.md` for memory capabilities
- Study test output to understand reasoning
- Review decision reasoning_chain for transparency

---

##  Quick Commands

```bash
# Run complete test
python test_arsenal_with_memory.py

# Run multiple times to see memory grow
python test_arsenal_with_memory.py  # Run 1
python test_arsenal_with_memory.py  # Run 2 - loads memory from Run 1
python test_arsenal_with_memory.py  # Run 3 - even more memory

# Test individual modules
python liquidity_sweep_detector.py
python range_trap_detector.py
python bos_choch_detector.py
```

---

##  Remember

### The Arsenal's Job
-  Detect danger
-  Block bad trades
-  Preserve capital
-  Learn from history

### Your Job
-  Trust the system
-  Don't override blocks
-  Let memory build
-  Review reasoning

---

**When in doubt, let the arsenal decide. It remembers what Horus forgot.** 
