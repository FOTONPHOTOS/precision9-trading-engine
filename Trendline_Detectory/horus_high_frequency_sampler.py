'''
Horus High-Frequency Sampler - TAKER VOLUME EDITION
==================================================

This module provides a high-confidence entry confirmation by using the
Binance Taker Buy/Sell Volume Ratio, a direct measure of market aggression.

This REPLACES the previous CVD slope calculation with a clearer, more robust
signal directly from the exchange.
'''

import asyncio
import logging
from typing import Optional

from binance_data_engine import BinanceDataEngine

logger = logging.getLogger(__name__)

class HorusSampler:
    '''
    Confirms trade direction using the Taker Buy/Sell Volume ratio.
    '''

    def __init__(self, data_engine: BinanceDataEngine, symbol: str, entry_system: any = None):
        '''
        Args:
            data_engine: The instance of the BinanceDataEngine.
            symbol: The trading symbol (e.g., 'SOLUSDT').
            entry_system: Kept for compatibility, but unused.
        '''
        self.data_engine = data_engine
        self.symbol = symbol
        # Thresholds for confirmation
        self.long_confirmation_threshold = 1.05 # Taker buys must be at least 5% greater than sells
        self.short_confirmation_threshold = 0.95 # Taker sells must be at least 5% greater than buys

    async def sample_and_evaluate(
        self,
        arsenal_direction: str,
        trend_direction: str, # Unused, for compatibility
        trend_strength: float, # Unused, for compatibility
    ) -> tuple[bool, str]:
        '''
        Fetches the Taker Buy/Sell ratio and evaluates it against the trade direction.
        Returns a tuple of (bool, str) for confirmation and reason.
        '''
        logger.info("[HORUS TAKER CHECK] Fetching 5m Taker Buy/Sell Ratio...")

        # Fetch the latest 5-minute taker volume ratio
        taker_ratio = await self.data_engine.get_taker_long_short_ratio(period="5m")

        if taker_ratio is None:
            reason = "Could not retrieve Taker Buy/Sell Ratio."
            logger.error(f"[HORUS TAKER CHECK] {reason} Blocking trade for safety.")
            return False, reason

        logger.info(f"[HORUS TAKER CHECK] Analysis Result: Taker Buy/Sell Ratio = {taker_ratio:.4f}")

        # Final High-Confidence Confirmation based on market aggression
        if arsenal_direction in ['LONG', 'UPTREND']:
            if taker_ratio > self.long_confirmation_threshold:
                reason = f"Ratio ({taker_ratio:.2f}) > threshold ({self.long_confirmation_threshold}), confirming aggressive buying."
                logger.info(f" [HORUS TAKER CHECK] {reason}")
                logger.info(f" [HORUS CONFIRMATION] Horus CONFIRMS {arsenal_direction} trade.")
                return True, reason
            else:
                reason = f"Taker ratio ({taker_ratio:.2f}) is not above the confirmation threshold ({self.long_confirmation_threshold})."
                logger.warning(f" [HORUS TAKER CHECK] {reason} Horus REJECTS.")
                logger.warning(f" [HORUS CONFIRMATION] Horus REJECTS {arsenal_direction} trade.")
                return False, reason
        
        elif arsenal_direction in ['SHORT', 'DOWNTREND']:
            if taker_ratio < self.short_confirmation_threshold:
                reason = f"Ratio ({taker_ratio:.2f}) < threshold ({self.short_confirmation_threshold}), confirming aggressive selling."
                logger.info(f" [HORUS TAKER CHECK] {reason}")
                logger.info(f" [HORUS CONFIRMATION] Horus CONFIRMS {arsenal_direction} trade.")
                return True, reason
            else:
                reason = f"Taker ratio ({taker_ratio:.2f}) is not below the confirmation threshold ({self.short_confirmation_threshold})."
                logger.warning(f" [HORUS TAKER CHECK] {reason} Horus REJECTS.")
                logger.warning(f" [HORUS CONFIRMATION] Horus REJECTS {arsenal_direction} trade.")
                return False, reason

        # Fallback for unknown direction
        reason = f"Unknown direction '{arsenal_direction}' provided to Horus Sampler."
        logger.error(reason)
        return False, reason