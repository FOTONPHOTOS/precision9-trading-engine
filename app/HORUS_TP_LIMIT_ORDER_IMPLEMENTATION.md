# Horus TP Limit Order Implementation
## Complete Guide to Fixing TP System

**Date:** 2025-10-11
**Status:** IMPLEMENTATION REQUIRED

---

## Problem Summary

### Current Issues:
1. **Bot manages TPs internally** instead of using exchange limit orders
2. **Wrong allocation**: 40%/30%/30% (3-tier) instead of 50%/50% (2-tier)
3. **No visibility on exchange**: TPs show as "All" on Bybit interface
4. **Breakeven triggers too early**: Should wait for TP1 limit order to fill

### Required Changes:
1. Place **reduceOnly limit orders** on Bybit for each TP level
2. Fix allocation to **50%/50%** for TP1/TP2
3. Monitor position size changes to detect TP fills
4. Move SL to breakeven **only after TP1 fills** (not before)
5. Add detailed educational logging

---

## Horus's Approach (From CRITICAL_RISK_MANAGER_FIXES.md)

### How Horus Places TP Limit Orders:

```python
# trade_risk_manager.py:563-643
await self._make_request(
    "POST",
    "/v5/order/create",
    {
        "category": "linear",
        "symbol": self.symbol,
        "side": "Sell" if direction == "LONG" else "Buy",  # Opposite to close
        "orderType": "Limit",                               # Limit order at TP price
        "qty": str(partial_qty),                            # 50% of position
        "price": f"{tp1_price:.1f}",                        # TP1 price
        "reduceOnly": True,                                 # Can ONLY close position
        "timeInForce": "GTC",                              # Good-til-cancelled
        "positionIdx": 0                                    # One-way mode
    }
)
```

### Why This Is Superior:

1. **Exchange executes automatically** - No bot required to be online
2. **Visible on interface** - Shows up on Bybit as actual limit order
3. **Can't double-trigger** - Exchange fills once and removes order
4. **Better fills** - Limit order at exact TP price (not market order slippage)
5. **Position reduction is atomic** - No race conditions

---

## Implementation Plan

### File: `bybit_execution_engine.py`

#### Change 1: Fix TP Allocation (Line 182)

**Before:**
```python
self.partial_exit_percentages = [0.4, 0.3, 0.3]  # 40%, 30%, 30%
```

**After:**
```python
self.partial_exit_percentages = [0.5, 0.5]  # 50%, 50% (2-tier system)
```

#### Change 2: Add Method to Place TP Limit Orders

**Add new method after line 1290:**

```python
async def _place_tp_limit_orders_on_exchange(self, signal: TradingSignal, position_qty: float, direction: str):
    """
    Place TP limit orders directly on Bybit exchange (Horus approach)

    Instead of bot managing TPs internally, we place reduceOnly limit orders
    that execute automatically when price hits TP levels.

    Args:
        signal: Trading signal with TP levels
        position_qty: Full position size
        direction: 'LONG' or 'SHORT'

    Returns:
        dict: {
            'tp1_order_id': str,
            'tp2_order_id': str,
            'success': bool
        }
    """
    logger.info("="*80)
    logger.info("📊 PLACING TP LIMIT ORDERS ON BYBIT")
    logger.info("="*80)
    logger.info(f"")
    logger.info(f"Educational Note:")
    logger.info(f"  We're placing LIMIT ORDERS directly on the exchange for each TP level.")
    logger.info(f"  These are 'reduceOnly' orders which means they can ONLY close the position.")
    logger.info(f"  When price reaches TP1 (${{signal.take_profit_1:.2f}}), Bybit automatically fills 50%.")
    logger.info(f"  When price reaches TP2 (${{signal.take_profit_2:.2f}}), Bybit automatically fills remaining 50%.")
    logger.info(f"  The bot monitors position size to detect when these orders fill.")
    logger.info(f"")

    try:
        # Calculate quantities for each TP level
        tp1_qty = position_qty * 0.5  # 50% of position
        tp2_qty = position_qty * 0.5  # Remaining 50%

        # Format quantities
        tp1_qty_str = f"{tp1_qty:.1f}"
        tp2_qty_str = f"{tp2_qty:.1f}"

        # Determine side for TP orders (opposite to entry)
        tp_side = "Sell" if direction == "LONG" else "Buy"

        logger.info(f"Position Details:")
        logger.info(f"  Full Size: {position_qty:.1f} SOLUSDT")
        logger.info(f"  TP1 Size: {tp1_qty:.1f} SOLUSDT (50%)")
        logger.info(f"  TP2 Size: {tp2_qty:.1f} SOLUSDT (50%)")
        logger.info(f"  TP Side: {tp_side} (opposite to entry)")
        logger.info(f"")

        # Place TP1 limit order
        logger.info(f"[TP1] Placing limit order at ${signal.take_profit_1:.2f}...")
        tp1_params = {
            "category": "linear",
            "symbol": self.symbol,
            "side": tp_side,
            "orderType": "Limit",
            "qty": tp1_qty_str,
            "price": f"{signal.take_profit_1:.2f}",
            "reduceOnly": True,      # CRITICAL: Can only close, not open
            "timeInForce": "GTC",    # Good-til-cancelled
            "positionIdx": 0,         # One-way mode
            "orderLinkId": f"{signal.signal_id}_TP1"
        }

        tp1_response = await self._make_request("POST", "/v5/order/create", tp1_params)

        if tp1_response and 'result' in tp1_response:
            tp1_order_id = tp1_response['result'].get('orderId', 'unknown')
            logger.info(f"✅ TP1 Limit Order Placed: {tp1_order_id}")
            logger.info(f"   Price: ${signal.take_profit_1:.2f}")
            logger.info(f"   Size: {tp1_qty:.1f} SOLUSDT (50%)")
            logger.info(f"   Status: Active on exchange, waiting for price to hit")
        else:
            logger.error(f"❌ TP1 order placement failed: {tp1_response}")
            return {'success': False}

        # Place TP2 limit order
        logger.info(f"")
        logger.info(f"[TP2] Placing limit order at ${signal.take_profit_2:.2f}...")
        tp2_params = {
            "category": "linear",
            "symbol": self.symbol,
            "side": tp_side,
            "orderType": "Limit",
            "qty": tp2_qty_str,
            "price": f"{signal.take_profit_2:.2f}",
            "reduceOnly": True,
            "timeInForce": "GTC",
            "positionIdx": 0,
            "orderLinkId": f"{signal.signal_id}_TP2"
        }

        tp2_response = await self._make_request("POST", "/v5/order/create", tp2_params)

        if tp2_response and 'result' in tp2_response:
            tp2_order_id = tp2_response['result'].get('orderId', 'unknown')
            logger.info(f"✅ TP2 Limit Order Placed: {tp2_order_id}")
            logger.info(f"   Price: ${signal.take_profit_2:.2f}")
            logger.info(f"   Size: {tp2_qty:.1f} SOLUSDT (50%)")
            logger.info(f"   Status: Active on exchange, waiting for price to hit")
        else:
            logger.error(f"❌ TP2 order placement failed: {tp2_response}")
            # Cancel TP1 if TP2 fails
            logger.warning(f"⚠️ Canceling TP1 order since TP2 failed...")
            await self._cancel_order(tp1_order_id)
            return {'success': False}

        logger.info(f"")
        logger.info(f"="*80)
        logger.info(f"✅ BOTH TP LIMIT ORDERS ACTIVE ON BYBIT")
        logger.info(f"="*80)
        logger.info(f"What happens next:")
        logger.info(f"  1. Orders are now visible on Bybit interface")
        logger.info(f"  2. When price hits ${signal.take_profit_1:.2f}, TP1 fills automatically (50% closes)")
        logger.info(f"  3. Bot detects position size reduction and moves SL to breakeven")
        logger.info(f"  4. When price hits ${signal.take_profit_2:.2f}, TP2 fills automatically (remaining 50% closes)")
        logger.info(f"  5. Position fully closed, trade complete")
        logger.info(f"")
        logger.info(f"Benefits:")
        logger.info(f"  ✓ No bot required to be online for TPs to execute")
        logger.info(f"  ✓ Better fill prices (limit orders, not market orders)")
        logger.info(f"  ✓ Visible on exchange interface")
        logger.info(f"  ✓ Can't double-trigger (exchange handles)")
        logger.info(f"="*80)

        return {
            'tp1_order_id': tp1_order_id,
            'tp2_order_id': tp2_order_id,
            'success': True
        }

    except Exception as e:
        logger.error(f"❌ Failed to place TP limit orders: {e}")
        return {'success': False}


async def _cancel_order(self, order_id: str):
    """Cancel an order"""
    try:
        params = {
            "category": "linear",
            "symbol": self.symbol,
            "orderId": order_id
        }
        await self._make_request("POST", "/v5/order/cancel", params)
        logger.info(f"✅ Order cancelled: {order_id}")
    except Exception as e:
        logger.error(f"❌ Failed to cancel order {order_id}: {e}")
```

#### Change 3: Replace Internal TP Management with Exchange Orders

**Find line 1046** where it calls `_apply_tp_system_to_position` and replace with:

```python
# BEFORE (line 1045-1046):
# Apply 3-tier TP system to this position
await self._apply_tp_system_to_position(signal, order_id)

# AFTER:
# Place TP limit orders on exchange (Horus approach)
tp_result = await self._place_tp_limit_orders_on_exchange(
    signal,
    position_qty=float(formatted_qty),
    direction=signal.direction
)

if not tp_result['success']:
    logger.error("❌ Failed to place TP limit orders")
    logger.warning("   Position opened but TPs not set - MANUAL MANAGEMENT REQUIRED")
else:
    # Store TP order IDs for monitoring
    self._tp1_order_id = tp_result['tp1_order_id']
    self._tp2_order_id = tp_result['tp2_order_id']
    self._initial_position_size = float(formatted_qty)
    logger.info(f"✅ TP limit orders tracked: TP1={self._tp1_order_id}, TP2={self._tp2_order_id}")
```

#### Change 4: Add Position Size Monitoring to Detect TP Fills

**Add new method after the TP limit order placement method:**

```python
async def _monitor_tp_fills_via_position_size(self):
    """
    Monitor position size changes to detect when TP limit orders fill

    Educational Note:
    When TP1 limit order fills on Bybit, position size reduces by 50%.
    We detect this change and trigger breakeven move.
    This is more reliable than price monitoring.
    """
    if not hasattr(self, '_initial_position_size'):
        return  # No position to monitor

    while self.position:
        try:
            await self.check_positions()

            if not self.position:
                break  # Position closed

            current_size = abs(self.position.size)
            initial_size = self._initial_position_size

            # Calculate percentage of position remaining
            size_remaining = (current_size / initial_size) * 100

            # TP1 Detection: Size reduced to ~50%
            if 'TP1' not in self.tp_levels_hit and 40 < size_remaining < 60:
                logger.info("="*80)
                logger.info("✅ TP1 LIMIT ORDER FILLED!")
                logger.info("="*80)
                logger.info(f"")
                logger.info(f"Position Size Change Detected:")
                logger.info(f"  Initial: {initial_size:.1f} SOLUSDT")
                logger.info(f"  Current: {current_size:.1f} SOLUSDT")
                logger.info(f"  Reduction: {100 - size_remaining:.1f}%")
                logger.info(f"")
                logger.info(f"This means:")
                logger.info(f"  • TP1 limit order at ${self._signal_tp1:.2f} was filled")
                logger.info(f"  • 50% of position closed automatically by exchange")
                logger.info(f"  • Profit secured on first half")
                logger.info(f"")
                logger.info(f"Next Step:")
                logger.info(f"  → Moving Stop Loss to BREAKEVEN")
                logger.info(f"  → Remaining 50% is now RISK-FREE")
                logger.info(f"  → If price reverses, we exit at entry (no loss)")
                logger.info(f"  → If price continues, TP2 will hit for more profit")
                logger.info(f"")

                self.tp_levels_hit.append('TP1')

                # Trigger breakeven move via Risk Manager
                if hasattr(self, '_risk_manager_callback'):
                    await self._risk_manager_callback('tp1_filled', current_size)

                logger.info(f"="*80)

            # TP2 Detection: Size reduced to ~0% (position closed)
            elif 'TP2' not in self.tp_levels_hit and size_remaining < 10:
                logger.info("="*80)
                logger.info("✅ TP2 LIMIT ORDER FILLED!")
                logger.info("="*80)
                logger.info(f"")
                logger.info(f"Position Fully Closed:")
                logger.info(f"  • TP2 limit order at ${self._signal_tp2:.2f} was filled")
                logger.info(f"  • Remaining 50% closed automatically")
                logger.info(f"  • Trade complete!")
                logger.info(f"")

                self.tp_levels_hit.append('TP2')
                logger.info(f"="*80)
                break  # Position fully closed

            await asyncio.sleep(2)  # Check every 2 seconds

        except Exception as e:
            logger.error(f"Error monitoring TP fills: {e}")
            await asyncio.sleep(5)
```

#### Change 5: Update real_time_risk_manager.py

**Add callback registration and TP1 detection:**

```python
# In real_time_risk_manager.py, add new method:

async def on_tp1_filled(self, current_position_size: float):
    """
    Called when TP1 limit order fills (detected by position size reduction)

    This is when we move SL to breakeven.
    """
    if not self.active_trades:
        return

    trade = list(self.active_trades.values())[0]

    if trade.breakeven_triggered:
        return  # Already moved to breakeven

    logger.info("="*80)
    logger.info("🛡️ BREAKEVEN TRIGGER - TP1 FILLED")
    logger.info("="*80)
    logger.info(f"")
    logger.info(f"Educational Explanation:")
    logger.info(f"  TP1 just filled, meaning 50% of position closed at profit.")
    logger.info(f"  We now move Stop Loss to entry price (breakeven).")
    logger.info(f"")
    logger.info(f"Why this matters:")
    logger.info(f"  • If price reverses now, we exit at breakeven (no loss)")
    logger.info(f"  • First half already secured profit")
    logger.info(f"  • Second half is now RISK-FREE")
    logger.info(f"  • Worst case: Break even. Best case: TP2 hits for more profit")
    logger.info(f"")

    # Move SL to entry (breakeven)
    new_sl = trade.entry_price

    try:
        await self._update_stop_loss_on_exchange(trade.trade_id, new_sl)
        trade.stop_loss = new_sl
        trade.breakeven_triggered = True

        logger.info(f"✅ Stop Loss Moved to BREAKEVEN: ${new_sl:.2f}")
        logger.info(f"   Previous SL: ${trade.stop_loss:.2f}")
        logger.info(f"   New SL: ${new_sl:.2f} (entry price)")
        logger.info(f"   Trade is now RISK-FREE!")
        logger.info(f"")
        logger.info(f"="*80)

    except Exception as e:
        logger.error(f"❌ Failed to move SL to breakeven: {e}")
```

---

## Testing Checklist

After implementing changes:

1. **✅ TP Orders Visible on Bybit**
   - Open Bybit interface
   - Check "Open Orders" tab
   - Should see 2 reduceOnly limit orders at TP1 and TP2 prices

2. **✅ TP1 Allocation is 50%**
   - Check position size after TP1 hits
   - Should be exactly 50% of original

3. **✅ TP2 Allocation is 50%**
   - Check remaining position after TP1
   - TP2 should close remaining 50%

4. **✅ Breakeven Triggers AFTER TP1**
   - TP1 fills → Wait 2-5 seconds → SL moves to entry
   - NOT before TP1 fills

5. **✅ Educational Logging**
   - Logs explain what's happening
   - Logs explain why it's happening
   - Logs show current state and next actions

---

## Benefits of This Implementation

### Before (Current):
- ❌ Bot manages TPs internally
- ❌ 40%/30%/30% allocation (not what user wants)
- ❌ TPs show as "All" on exchange
- ❌ Bot must be online for TPs to execute
- ❌ Breakeven triggers based on price proximity (can be too early)

### After (Horus Approach):
- ✅ Exchange manages TPs via limit orders
- ✅ 50%/50% allocation (user's request)
- ✅ TPs visible on exchange as actual orders
- ✅ TPs execute even if bot offline
- ✅ Breakeven triggers ONLY when TP1 actually fills

---

## Summary of Changes

1. **Line 182**: Change to `[0.5, 0.5]` for 50%/50% split
2. **Add Method**: `_place_tp_limit_orders_on_exchange()` - Places reduceOnly limit orders
3. **Add Method**: `_monitor_tp_fills_via_position_size()` - Detects TP fills
4. **Add Method**: `_cancel_order()` - Cancels orders if needed
5. **Line 1046**: Replace `_apply_tp_system_to_position()` with limit order placement
6. **Risk Manager**: Add `on_tp1_filled()` callback for breakeven trigger
7. **All Methods**: Add detailed educational logging explaining every step

---

**Status:** Ready for implementation
**Priority:** HIGH (user explicitly requested this)
**Complexity:** Medium (well-defined changes, Horus pattern to follow)
