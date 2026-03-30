#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Project Helios: The Master Market Guidance Server
================================================

This microservice IS a full, dedicated, non-trading Arsenal instance for BTCUSDT.
It runs the complete analysis loop and serves the resulting MarketIntelligence
object via a high-performance REST API.

This provides all other bots with a master source of truth for market context.

"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, time

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
import pandas as pd
import json
from typing import Any
import os # NEW
from dotenv import load_dotenv # NEW
from scipy.stats import percentileofscore # NEW

from fvg_detector import FairValueGap
from order_block_detector import OrderBlock
from liquidity_sweep_detector import LiquiditySweep, LiquidityPool, StopHuntWarning
from rre_common_types import RangeAnalysis, RangeGeometry
from trend_continuation_brain import MarketIntelligence
from dashboard_client import Emitter # NEW: Emitter for dashboard integration

# NEW: Import OI/Funding Engine components
from binance_data_engine import BinanceDataEngine, compute_gls, compute_lci

# Custom JSON encoder to handle numpy types and custom dataclasses
class ComprehensiveEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (FairValueGap, OrderBlock, LiquiditySweep, LiquidityPool, StopHuntWarning, RangeAnalysis, RangeGeometry)):
            return obj.__dict__
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            val = float(obj)
            if np.isnan(val):
                return None  # or "NaN" if you prefer string representation
            elif np.isinf(val):
                return "Infinity" if val > 0 else "-Infinity"
            return val
        if isinstance(obj, float):
            # Handle regular Python float values that might be nan or inf
            if obj != obj:  # NaN check: NaN is not equal to itself
                return None  # or "NaN" if you prefer string representation
            elif obj == float('inf'):
                return "Infinity"
            elif obj == float('-inf'):
                return "-Infinity"
            return obj
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')  # Convert DataFrame to list of dictionaries
        if isinstance(obj, pd.Series):
            return obj.to_dict()  # Convert Series to dictionary
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        return super(ComprehensiveEncoder, self).default(obj)

class ComprehensiveJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=True,  # Now handled by the encoder
            indent=None,
            separators=(",", ":"),
            cls=ComprehensiveEncoder,
        ).encode("utf-8")

# Import the complete Arsenal system
from live_arsenal_horus_integrated import LiveArsenalHorusSystem
from realtime_swing_detector import fetch_binance_data

# --- Globals --- 
app_state = {}

# --- Logging ---
def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    
    logger = logging.getLogger("helios_master_server")
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()


import traceback # NEW: Import for detailed error reporting

# --- Background Task: The BTC Arsenal Engine ---
async def run_btc_arsenal_engine(emitter: Emitter):
    """The background task that runs the full BTC analysis loop."""
    logger.info("Initializing Master BTC Arsenal Engine for Helios...")
    await emitter.emit_health("OK", message="Helios Master Server started.")

    # Load API keys from .env for Horus initialization
    load_dotenv()
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')

    if not api_key or not api_secret:
        logger.critical("BINANCE_API_KEY or BINANCE_API_SECRET not found in .env. Helios BTC Engine cannot be initialized.")
        await emitter.emit_health("ERROR", message="API keys missing. Cannot initialize.", extra_info={"details": "BINANCE_API_KEY or BINANCE_API_SECRET not found in .env."})
        return # Exit if keys are missing

    # --- NEW: Create centralized AsyncClient ---
    from binance import AsyncClient
    try:
        client = await AsyncClient.create(api_key, api_secret)
    except Exception as e:
        logger.critical(f"Failed to create Binance AsyncClient: {e}", exc_info=True)
        await emitter.emit_health("ERROR", message=f"Failed to create Binance AsyncClient: {e}")
        return

    # Initialize Arsenal for BTC, but with live_execution=False
    btc_arsenal = LiveArsenalHorusSystem(
        symbol="BTCUSDT", 
        timeframe="5m", 
        live_execution=False, # CRITICAL: This instance does not trade
        fast_start=True, # Use fast start for the server
        client=client # Pass the centralized client
    )
    app_state['btc_arsenal_instance'] = btc_arsenal

    # Run the main analysis loop of the bot
    # We need to adapt the original run_async loop to work as a background task
    logger.info("Helios BTC Engine: Starting Horus initialization...")
    await emitter.emit_health("OK", message="Horus initialization started.")
    try:
        await btc_arsenal.initialize_horus(client=client)
        logger.info("Helios BTC Engine: Horus initialization complete.")
        await emitter.emit_health("OK", message="Horus initialization complete.")
    except Exception as e:
        logger.error(f"Helios BTC Engine: Horus initialization failed: {e}", exc_info=True)
        await emitter.emit_health("ERROR", message=f"Horus initialization failed: {e}")
        return

    # NEW: Initialize OI/Funding Engine for BTC with a live client
    data_engine = BinanceDataEngine(symbol="BTCUSDT", client=btc_arsenal.horus.client)
    
    logger.info("BTC Arsenal Engine is running. Starting continuous analysis...")
    await emitter.emit_health("OK", message="Continuous analysis started.")
    while True:
        try:
            logger.info("Helios BTC Engine: Top of the analysis loop.")
            
            # Correctly fetch data using the imported function
            df_check = await fetch_binance_data(btc_arsenal.client, btc_arsenal.symbol, btc_arsenal.timeframe, 200)

            # --- FIX: Apply Kalman Filter to the data before analysis ---
            if df_check is not None and not df_check.empty:
                df_check['kf_close'] = df_check['close'].apply(btc_arsenal.price_filter.update)

            if btc_arsenal.has_new_candle(df_check):
                logger.info("Helios BTC Engine: New candle detected, running analysis.")
                
                # --- NEW: Fetch data for LCI and GLS ---
                long_short_ratios = await data_engine.get_long_short_ratios()
                global_ls_ratio = long_short_ratios.get('global') if long_short_ratios else None
                lci_score = compute_lci("BTCUSDT", global_ls_ratio)
                logger.info(f"BTC Local Crowd Index (LCI) calculated: {lci_score:.2f}")

                # GLS still needs historical data
                historical_oi_fr = await data_engine.get_historical_data(limit=100)
                oi_history = historical_oi_fr["oi_history"]
                fr_history = historical_oi_fr["fr_history"] # FIXED: Corrected typo

                # Fetch Taker Ratio and 24h Volume for run_arsenal_analysis
                taker_ratio_analysis = await data_engine.get_taker_ratio_analysis()
                taker_ratio = taker_ratio_analysis.get('latest_ratio') if taker_ratio_analysis else None
                taker_ratio_ma = taker_ratio_analysis.get('ratio_ma') if taker_ratio_analysis else None

                # Fetch 24h Volume for dynamic thresholds
                symbol_24h_volume = 0.0
                try:
                    ticker_data = await data_engine.client.get_ticker(symbol=btc_arsenal.symbol)
                    symbol_24h_volume = float(ticker_data['quoteVolume'])
                    logger.info(f"Helios BTC Engine: Symbol 24h Volume: ${symbol_24h_volume:,.0f}")
                except Exception as e:
                    logger.error(f"Helios BTC Engine: Could not fetch 24h volume for {btc_arsenal.symbol}: {e}")
                    await emitter.emit_health("WARNING", message=f"Could not fetch 24h volume for {btc_arsenal.symbol}: {e}")

                # --- NEW: Calculate ATR Percentile ---
                # Calculate ATR for volatility
                high_low = df_check['high'] - df_check['low']
                high_close = np.abs(df_check['high'] - df_check['close'].shift())
                low_close = np.abs(df_check['low'] - df_check['close'].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = np.max(ranges, axis=1)
                
                # Calculate ATR Percentile
                atr_series = true_range.rolling(14).mean().dropna()
                if not atr_series.empty:
                    current_atr = atr_series.iloc[-1]
                    atr_percentile = percentileofscore(atr_series, current_atr) / 100.0
                else:
                    atr_percentile = 0.5 # Default if not enough data
                logger.info(f"Helios BTC Engine: ATR Percentile calculated: {atr_percentile:.2f}")

                # --- NEW: Calculate CVD Slope ---
                cvd_slope = 0.0
                if btc_arsenal.horus:
                    cvd_history = btc_arsenal.horus.get_recent_cvd_history()
                    if len(cvd_history) > 10:
                        # Use the last 20 minutes of CVD data for slope
                        recent_cvd = cvd_history[-20:]
                        # Create a time index for the regression
                        x = np.arange(len(recent_cvd))
                        # Fit a linear model
                        try:
                            slope, _ = np.polyfit(x, recent_cvd, 1)
                            cvd_slope = slope
                        except np.linalg.LinAlgError:
                            cvd_slope = 0.0 # Handle potential errors in polyfit
                        logger.info(f"Helios BTC Engine: CVD Slope (last 20 mins): {cvd_slope:.2f}")
                    else:
                        logger.info("Helios BTC Engine: Not enough CVD history to calculate slope.")

                market_intel, _, _ = await btc_arsenal.run_arsenal_analysis(
                    df_check, 
                    lci_score=lci_score,
                    taker_ratio=taker_ratio,
                    taker_ratio_ma=taker_ratio_ma,
                    symbol_24h_volume=symbol_24h_volume,
                    atr_percentile=atr_percentile,
                    cvd_slope=cvd_slope
                )

                gls_score = compute_gls(btc_oi_history=oi_history, btc_fr_history=fr_history)
                logger.info(f"Global Leverage Stress (GLS) calculated: {gls_score:.2f}")

                # Format the market intelligence to match Helios context expectations
                helios_context = {
                    'gls_score': gls_score, # NEW
                    'btc_trend': market_intel.trend_direction if hasattr(market_intel, 'trend_direction') else 'UNKNOWN',
                    'sentiment': 'RISK_ON' if market_intel.trend_direction == 'uptrend' else 'RISK_OFF' if market_intel.trend_direction == 'downtrend' else 'NEUTRAL',
                    'current_price': market_intel.current_price if hasattr(market_intel, 'current_price') else None,
                    'trend_strength': market_intel.trend_strength if hasattr(market_intel, 'trend_strength') else 0.0,
                    'swing_highs_count': len(market_intel.swing_highs) if hasattr(market_intel, 'swing_highs') else 0,
                    'swing_lows_count': len(market_intel.swing_lows) if hasattr(market_intel, 'swing_lows') else 0,
                    'fvg_count': len(market_intel.fvgs) if hasattr(market_intel, 'fvgs') else 0,
                    'order_block_count': len(market_intel.order_blocks) if hasattr(market_intel, 'order_blocks') else 0,
                    'liquidity_sweep_count': len(market_intel.liquidity_sweeps) if hasattr(market_intel, 'liquidity_sweeps') else 0,
                    'confluence_score': market_intel.confluence_score if hasattr(market_intel, 'confluence_score') else 0,
                    'timestamp': market_intel.timestamp.isoformat() if hasattr(market_intel, 'timestamp') else None,
                    # Include original market intelligence for backward compatibility
                    'market_intel': market_intel.__dict__
                }
                
                # Store the formatted Helios context
                app_state['latest_context'] = helios_context
                logger.info("Helios Master Context Updated.")
                await emitter.emit("helios_context_update", helios_context) # Emit to dashboard
                await emitter.emit_health("OK", message="Helios analysis cycle complete.") # Emit health
            
            # Analysis interval from the bot's config
            await asyncio.sleep(btc_arsenal.analysis_interval)

        except Exception as e:
            logger.error(f"Error in Helios BTC engine loop: {e}", exc_info=True)
            await emitter.emit_health("ERROR", message=f"Error in Helios BTC engine loop: {e}", extra_info={"traceback": traceback.format_exc()})
            await asyncio.sleep(60)


# --- FastAPI Lifespan & API --- 
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Helios Master Server starting up...")
    
    # Create the emitter here and pass it to the background task
    emitter = Emitter("helios", "master_server")
    app_state['helios_emitter'] = emitter # Store in app_state for shutdown
    
    task = asyncio.create_task(run_btc_arsenal_engine(emitter)) # Pass emitter to the task
    yield
    logger.info("Helios Master Server shutting down...")
    task.cancel()
    await task
    
    # Gracefully stop the emitter
    if 'helios_emitter' in app_state:
        await app_state['helios_emitter'].stop()
    logger.info("Helios Master Server stopped.")

app = FastAPI(lifespan=lifespan, title="Helios Master Context API")

@app.get("/api/v1/helios/context")
async def get_helios_context():
    if 'latest_context' not in app_state or app_state['latest_context'] is None:
        raise HTTPException(status_code=503, detail="Market context is not yet available.")
    
    # Use the custom NumpyJSONResponse to handle special numpy types
    return ComprehensiveJSONResponse(content=app_state['latest_context'])

@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    logger.info("Launching Helios Master Server...")
    uvicorn.run(app, host="0.0.0.0", port=8009)
