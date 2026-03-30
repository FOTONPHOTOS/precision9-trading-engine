#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Project Helios: The Market Guidance System
=========================================

This module provides a high-level, contextual understanding of the entire crypto market
by focusing on Bitcoin (BTC) as the primary indicator.

It produces a `HeliosContext` object that other parts of the system can use to make
more intelligent, market-aware decisions.

"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any

from realtime_swing_detector import fetch_binance_data
from test_ultimate_arsenal import analyze_trend_structure, find_swing_highs, find_swing_lows

logger = logging.getLogger(__name__)

class HeliosBTC_Engine:
    """Analyzes BTC data to provide a macro market context."""

    def __init__(self, symbol: str = "BTCUSDT", timeframe: str = "15m"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.context: Dict[str, Any] = {
            "btc_trend": "SIDEWAYS",
            "volatility_regime": "STABLE",
            "dominance_trend": "STABLE",
            "sentiment": "NEUTRAL",
            "last_updated": None
        }

    async def analyze(self) -> Dict[str, Any]:
        """Performs a full, multi-timeframe analysis of BTC and returns the HeliosContext."""
        logger.info("[HELIOS] Analyzing BTC for macro and micro context...")
        try:
            # 1. Fetch Data for both timeframes
            df_btc_htf = fetch_binance_data(self.symbol, "15m", 500)
            df_btc_ltf = fetch_binance_data(self.symbol, "5m", 200)

            if df_btc_htf.empty or df_btc_ltf.empty:
                logger.warning("[HELIOS] Could not fetch BTC data for one or more timeframes.")
                return self.context # Return last known context

            # --- Enhanced Trend Analysis (for both timeframes) ---
            self.context['macro_trend'] = self._get_consensus_trend(df_btc_htf)
            self.context['micro_trend'] = self._get_consensus_trend(df_btc_ltf)

            # 4. Analyze Volatility (using HTF)
            high_low = df_btc_htf['high'] - df_btc_htf['low']
            high_close = np.abs(df_btc_htf['high'] - df_btc_htf['close'].shift())
            low_close = np.abs(df_btc_htf['low'] - df_btc_htf['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = true_range.rolling(14).mean()
            
            if atr.iloc[-1] > atr.rolling(100).mean().iloc[-1] * 1.5:
                self.context['volatility_regime'] = "EXPANDING"
            elif atr.iloc[-1] < atr.rolling(100).mean().iloc[-1] * 0.7:
                self.context['volatility_regime'] = "CONTRACTING"
            else:
                self.context['volatility_regime'] = "STABLE"

            # 5. Synthesize Sentiment (based on Macro trend)
            if self.context['macro_trend'] == 'UPTREND' and self.context['volatility_regime'] != 'EXPANDING':
                self.context['sentiment'] = "RISK_ON"
            elif self.context['macro_trend'] == 'DOWNTREND':
                self.context['sentiment'] = "RISK_OFF"
            else:
                self.context['sentiment'] = "NEUTRAL"

            self.context['last_updated'] = pd.Timestamp.utcnow()
            logger.info(f"[HELIOS] Context Updated: Macro Trend={self.context['macro_trend']}, Micro Trend={self.context['micro_trend']}, Sentiment={self.context['sentiment']}")

        except Exception as e:
            logger.error(f"[HELIOS] Error during BTC analysis: {e}", exc_info=True)
        
        return self.context

    def _get_consensus_trend(self, df: pd.DataFrame) -> str:
        """Determines trend based on a consensus of structure, MA slope, and volume."""
        # 1. Structure Analysis
        swing_highs = find_swing_highs(df)
        swing_lows = find_swing_lows(df)
        structure_trend = analyze_trend_structure(swing_highs, swing_lows).get('trend_direction', 'SIDEWAYS').upper()

        # 2. Moving Average Slope Analysis
        ema = df['close'].ewm(span=21, adjust=False).mean()
        slope = (ema.iloc[-1] - ema.iloc[-5]) / 5 # Slope over last 5 periods
        price_percent_slope = (slope / ema.iloc[-1]) * 100

        ma_trend = "SIDEWAYS"
        if price_percent_slope > 0.05: # Threshold for significant upward slope
            ma_trend = "UPTREND"
        elif price_percent_slope < -0.05: # Threshold for significant downward slope
            ma_trend = "DOWNTREND"

        # 3. Volume Analysis
        volume_ma_short = df['volume'].rolling(window=10).mean().iloc[-1]
        volume_ma_long = df['volume'].rolling(window=50).mean().iloc[-1]
        volume_confirms = volume_ma_short > volume_ma_long * 1.2 # Recent volume is 20% higher than average

        # Consensus Logic
        if ma_trend == structure_trend and volume_confirms:
            return ma_trend # High confidence trend
        
        if ma_trend != "SIDEWAYS" and ma_trend != structure_trend:
            return "CONFLICT" # MA and structure disagree

        if ma_trend != "SIDEWAYS":
            return ma_trend # Default to faster MA trend if structure is lagging
        
        return structure_trend # Default to structure if MA is flat
