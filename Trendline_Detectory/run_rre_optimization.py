
import optuna
import pandas as pd
import logging
from typing import Dict, Any, List
from dataclasses import asdict
import numpy as np

# --- Imports from the existing framework ---
from simulation_framework.data_fetcher import DataFetcher
from simulation_framework.engine import Simulator
from range_regime_engine import RREngine, RangeAnalysis

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger("RRE_Optimizer")


# --- Data Fetching ---
# Fetch data once to be used by all trials
try:
    fetcher = DataFetcher()
    # Fetch a large dataset for robust optimization (e.g., 14 days of 5m data)
    full_data = fetcher.fetch_and_enrich_data("SOLUSDT", "5m", limit=4032)
    if full_data is None:
        raise ValueError("Data fetching returned None.")
    # Pre-calculate ATR Percentile for speed
    atr_series = full_data['ATR_14'].dropna()
    full_data['atr_percentile'] = full_data['ATR_14'].apply(lambda x: np.nan if pd.isna(x) else (atr_series < x).mean())
    logger.info("Successfully fetched and prepared data for optimization.")
except Exception as e:
    logger.critical(f"FATAL: Failed to fetch data. Optimizer cannot run. Error: {e}")
    full_data = None


# --- Parameter Space Definition ---
# The parameters we want to optimize, informed by our analysis
param_space = {
    "structural_weight": {"type": "float", "low": 0.2, "high": 0.6},
    "boundary_weight": {"type": "float", "low": 0.1, "high": 0.4},
    "vol_weight": {"type": "float", "low": 0.05, "high": 0.3},
    "trend_weight": {"type": "float", "low": 0.1, "high": 0.4}, # Increased lower bound
    "micro_weight": {"type": "float", "low": 0.05, "high": 0.3},
    "adx_threshold": {"type": "int", "low": 22, "high": 35},
    "min_range_size_pct": {"type": "float", "low": 0.5, "high": 1.5},
    "range_score_promote_threshold": {"type": "int", "low": 50, "high": 75},
    "tight_range_score_threshold": {"type": "int", "low": 75, "high": 95},
}

def get_params(trial: optuna.Trial) -> Dict[str, Any]:
    """Suggests parameters for a trial from the defined param_space."""
    params = {}
    for name, p_info in param_space.items():
        if p_info["type"] == "float":
            params[name] = trial.suggest_float(name, p_info["low"], p_info["high"])
        elif p_info["type"] == "int":
            params[name] = trial.suggest_int(name, p_info["low"], p_info["high"])
    return params

def objective(trial: optuna.Trial) -> float:
    """
    The objective function for Optuna to optimize.
    A trial consists of:
    1. Suggesting a set of hyperparameters.
    2. Running a simulation with those hyperparameters.
    3. Calculating and returning a "fitness score".
    """
    if full_data is None:
        return -1000.0

    try:
        params = get_params(trial)
        
        rre_config = {
            'weights': {
                'structural': params['structural_weight'],
                'boundary': params['boundary_weight'],
                'vol': params['vol_weight'],
                'trend': params['trend_weight'],
                'micro': params['micro_weight'],
            },
            'adx_threshold': params['adx_threshold'],
            'min_range_size_pct': params['min_range_size_pct'],
        }
        rre_engine = RREngine(symbol="SOLUSDT", config=rre_config)
        
        results: List[RangeAnalysis] = []

        def simulation_callback(df: pd.DataFrame):
            current_price = df['close'].iloc[-1]
            adx_value = df['ADX_14'].iloc[-1] if 'ADX_14' in df.columns and not pd.isna(df['ADX_14'].iloc[-1]) else 50
            atr_percentile = df['atr_percentile'].iloc[-1] if 'atr_percentile' in df.columns and not pd.isna(df['atr_percentile'].iloc[-1]) else 0.5
            
            analysis = rre_engine.analyze(
                swings=[], hvn_zones=[], order_blocks=[], # Dummy values for speed
                atr_percentile=atr_percentile,
                adx_value=adx_value,
                taker_ratio=None, cvd_slope=None, stop_hunt_prob=0.0,
                current_price=current_price
            )
            analysis.timestamp = df.index[-1]
            results.append(analysis)
            return analysis

        simulator = Simulator(data=full_data)
        simulator.run(
            scenario_start_time=full_data.index[200], # Start after a warmup
            scenario_end_time=full_data.index[-1],
            callback=simulation_callback
        )

        # --- Scoring Logic (Fitness Function) ---
        score = 0.0
        if not results:
            return -1000.0

        results_df = pd.DataFrame([asdict(r) for r in results])
        results_df.set_index('timestamp', inplace=True)
        
        results_df = results_df.join(full_data[['close', 'ADX_14']], how='inner')
        results_df['future_price_change_abs'] = results_df['close'].shift(-30).rolling(30).std().shift(-30) # Future 2.5hr volatility
        results_df.dropna(inplace=True)

        is_range_state = results_df['range_state'].isin(['ESTABLISHED_RANGE', 'TIGHT_RANGE'])
        
        # 1. Reward for identifying ranges that are actually low volatility
        in_range_df = results_df[is_range_state]
        if not in_range_df.empty:
            # Lower future volatility during a range is good.
            # We invert the volatility so a lower number gives a higher score.
            consolidation_score = 1 / (1 + in_range_df['future_price_change_abs'].mean())
            score += consolidation_score * 100

        # 2. Penalize heavily for calling a range when ADX is high
        # This directly addresses the issue from the live signal analysis
        high_adx_in_range = in_range_df[in_range_df['ADX_14'] > params['adx_threshold']].shape[0]
        penalty = high_adx_in_range * 5 # Heavy penalty for each wrong candle
        score -= penalty

        # 3. Reward for identifying breakouts (i.e., exiting the range state before a big move)
        not_in_range_df = results_df[~is_range_state]
        if not not_in_range_df.empty:
            breakout_score = not_in_range_df['future_price_change_abs'].mean()
            score += breakout_score * 50

        # 4. Encourage a healthy ratio of range detection
        range_ratio = is_range_state.mean()
        if not (0.10 < range_ratio < 0.50):
            score *= 0.7 # 30% penalty if it's detecting too many or too few ranges
            
        return score if not pd.isna(score) else -1000.0

    except Exception as e:
        logger.error(f"An error occurred in trial #{trial.number}: {e}", exc_info=True)
        return -1000.0


# --- Main Execution Block ---
if __name__ == "__main__":
    if full_data is None:
        logger.critical("Cannot start optimization because data loading failed.")
    else:
        study_name = "rre_optimization_v2"
        storage_name = f"sqlite:///{study_name}.db"
        
        study = optuna.create_study(
            study_name=study_name,
            storage=storage_name,
            direction="maximize",
            load_if_exists=True
        )
        
        logger.info(f"Optuna study '{study_name}' created/loaded with {len(study.trials)} existing trials.")
        logger.info("Starting optimization... Press Ctrl+C to stop.")
        
        try:
            study.optimize(objective, n_trials=200)
        except KeyboardInterrupt:
            logger.info("Optimization stopped by user.")
        
        print("\n==========================================")
        print("Optimization Complete")
        print(f"Number of finished trials: {len(study.trials)}")
        
        print("\n--- Best Trial ---")
        try:
            best_trial = study.best_trial
            print(f"Value (Score): {best_trial.value}")
            
            print("\n--- Best Parameters ---")
            for key, value in best_trial.params.items():
                print(f"{key}: {value}")
        except ValueError:
            print("No trials were completed. Cannot show best parameters.")
        print("==========================================")
