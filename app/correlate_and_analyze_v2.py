import sqlite3
import json
import pandas as pd
import os
import sys

# --- Configuration ---
AEGIS_DB_PATH = os.path.join(os.path.dirname(__file__), 'eyes_of_horus', 'eyes_of_horus.db')
SIGNAL_DIR = os.path.dirname(__file__)
SYMBOLS = ["ETHUSDT", "BTCUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "LINKUSDT"]
OUTPUT_FILE = "analysis_results_v2.txt"
# NEW: Increased tolerance for correlation
CORRELATION_TOLERANCE = pd.Timedelta('30min')


def load_aegis_trades():
    """Loads all trades from the Aegis SQLite database."""
    print(f"Loading trades from {AEGIS_DB_PATH}...")
    if not os.path.exists(AEGIS_DB_PATH):
        print(f"ERROR: Aegis database not found at {AEGIS_DB_PATH}")
        return pd.DataFrame()
        
    try:
        con = sqlite3.connect(AEGIS_DB_PATH)
        query = "SELECT * FROM managed_trades WHERE status = 'closed' AND pnl IS NOT NULL"
        df = pd.read_sql_query(query, con)
        con.close()
        
        df['entry_datetime'] = pd.to_datetime(df['entry_timestamp'], unit='ms')
        df['exit_datetime'] = pd.to_datetime(df['exit_timestamp'], unit='ms')
        
        print(f"Loaded {len(df)} completed trades from Aegis.")
        return df
    except Exception as e:
        print(f"ERROR: Failed to load trades from Aegis DB: {e}")
        return pd.DataFrame()

def load_arsenal_signals():
    """Loads and parses all Arsenal signal logs from .jsonl files."""
    print(f"Loading Arsenal signals from {SIGNAL_DIR}...")
    all_signals = []
    
    for symbol in SYMBOLS:
        file_path = os.path.join(SIGNAL_DIR, f'arsenal_signals_{symbol}.jsonl')
        if not os.path.exists(file_path):
            print(f"WARNING: Signal log not found for {symbol} at {file_path}")
            continue
            
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    signal = json.loads(line)
                    signal['symbol'] = symbol
                    all_signals.append(signal)
                except json.JSONDecodeError:
                    print(f"Skipping corrupted line in {file_path}")
    
    if not all_signals:
        print("ERROR: No signal files found or all were empty/corrupt.")
        return pd.DataFrame()

    df = pd.json_normalize(all_signals, sep='_')
    
    df = df.rename(columns={
        'decision_decision_timestamp': 'signal_datetime',
        'decision_direction': 'signal_direction',
        'decision_confidence': 'signal_confidence',
        'decision_market_intel_range_trap_analysis_range_score': 'range_score',
        'decision_market_intel_range_trap_analysis_range_state': 'range_state',
        'decision_market_intel_stop_hunt_warning_stop_hunt_probability': 'stop_hunt_prob',
        'decision_market_intel_stop_hunt_warning_hunt_type': 'stop_hunt_type',
        'horus_confirmation': 'horus_confirmed'
    })
    
    df['signal_datetime'] = pd.to_datetime(df['signal_datetime'])
    
    required_cols = [
        'symbol', 'signal_datetime', 'signal_direction', 'signal_confidence', 
        'range_score', 'range_state', 'stop_hunt_prob', 'stop_hunt_type', 'horus_confirmed'
    ]
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df = df[required_cols]

    print(f"Loaded {len(df)} signals from {len(SYMBOLS)} symbols.")
    return df


def correlate_data(trades_df, signals_df):
    """Correlates trades with the signals that preceded them using a robust, per-symbol method."""
    if trades_df.empty or signals_df.empty:
        print("Cannot correlate data, one of the dataframes is empty.")
        return pd.DataFrame()
        
    print(f"Correlating trades with signals (tolerance: {CORRELATION_TOLERANCE})...")

    trades_df.dropna(subset=['entry_datetime', 'symbol'], inplace=True)
    signals_df.dropna(subset=['signal_datetime', 'symbol'], inplace=True)
    
    trades_df['symbol'] = trades_df['symbol'].astype(str)
    signals_df['symbol'] = signals_df['symbol'].astype(str)

    all_correlated_dfs = []
    unique_symbols = trades_df['symbol'].unique()

    for symbol in unique_symbols:
        trades_subset = trades_df[trades_df['symbol'] == symbol].copy()
        signals_subset = signals_df[signals_df['symbol'] == symbol].copy()

        trades_subset.sort_values(by='entry_datetime', inplace=True)
        signals_subset.sort_values(by='signal_datetime', inplace=True)

        correlated_subset = pd.merge_asof(
            left=trades_subset,
            right=signals_subset,
            left_on='entry_datetime',
            right_on='signal_datetime',
            direction='backward',
            tolerance=CORRELATION_TOLERANCE
        )
        all_correlated_dfs.append(correlated_subset)

    if not all_correlated_dfs:
        print("No correlations found after processing all symbols.")
        return pd.DataFrame()

    final_correlated_df = pd.concat(all_correlated_dfs).reset_index(drop=True)
    final_correlated_df.dropna(subset=['signal_datetime'], inplace=True)
    
    print(f"Successfully correlated {len(final_correlated_df)} trades with a preceding signal.")
    return final_correlated_df


def analyze_performance_v2(raw_trades_df, correlated_df):
    """Analyzes and compares the performance of winning vs. losing trades."""
    if correlated_df.empty:
        print("No correlated data to analyze.")
        return

    original_stdout = sys.stdout
    with open(OUTPUT_FILE, 'w') as f:
        sys.stdout = f

        print("="*80)
        print("ARSENAL PERFORMANCE ANALYSIS (V2)")
        print("="*80)

        # --- NEW: Preliminary analysis of ALL trades from Aegis DB ---
        print("\n--- PRELIMINARY: AEGIS DATABASE OVERVIEW ---")
        total_raw_trades = len(raw_trades_df)
        raw_wins = raw_trades_df[raw_trades_df['pnl'] > 0]
        raw_losses = raw_trades_df[raw_trades_df['pnl'] <= 0]
        print(f"Total Trades in DB: {total_raw_trades}")
        print(f"Total Wins in DB: {len(raw_wins)}")
        print(f"Total Losses in DB: {len(raw_losses)}")
        print(f"DB Win Rate: {len(raw_wins) / total_raw_trades:.2%}" if total_raw_trades > 0 else "N/A")
        print(f"DB Total PnL: {raw_trades_df['pnl'].sum():,.2f}")
        print("-" * 80)

        print("\n--- CORRELATED TRADES PERFORMANCE ---")
        total_corr_trades = len(correlated_df)
        winning_trades = correlated_df[correlated_df['pnl'] > 0]
        losing_trades = correlated_df[correlated_df['pnl'] <= 0]
        win_rate = len(winning_trades) / total_corr_trades if total_corr_trades > 0 else 0
        total_pnl = correlated_df['pnl'].sum()
        print(f"Total Correlated Trades: {total_corr_trades}")
        print(f"Correlated Winning Trades: {len(winning_trades)}")
        print(f"Correlated Losing Trades: {len(losing_trades)}")
        print(f"Correlated Win Rate: {win_rate:.2%}")
        print(f"Correlated Total PnL: {total_pnl:,.2f}")
        print("-" * 80)

        if winning_trades.empty:
            print("\nNo winning trades were found in the correlated data. Cannot perform comparative analysis.")
        else:
            print("\n--- COMPARATIVE ANALYSIS: WINS VS. LOSSES ---")
            
            print("\n[1] Distribution of 'Range Score':")
            print("    Losing Trades:")
            print(losing_trades['range_score'].describe().to_string())
            print("\n    Winning Trades:")
            print(winning_trades['range_score'].describe().to_string())
            print("\n   Interpretation:")
            print("   - Compare the 'mean' and '75%' values. If winning trades have a lower range_score, it confirms that avoiding ranges is profitable.")

            print("\n[2] Distribution of 'Stop Hunt Probability':")
            print("    Losing Trades:")
            print(losing_trades['stop_hunt_prob'].describe().to_string())
            print("\n    Winning Trades:")
            print(winning_trades['stop_hunt_prob'].describe().to_string())
            print("\n   Interpretation:")
            print("   - Compare the 'mean' and '75%' values. If winning trades have a significantly lower stop_hunt_prob, it's a strong signal for filtering trades.")

            print("\n[3] Performance by Market Range State:")
            print("    Losing Trades:")
            print(losing_trades.groupby('range_state')['pnl'].agg(['count', 'sum']).sort_values(by='count', ascending=False))
            print("\n    Winning Trades:")
            print(winning_trades.groupby('range_state')['pnl'].agg(['count', 'sum']).sort_values(by='count', ascending=False))
            print("\n   Interpretation:")
            print("   - Look for where the majority of wins vs losses are. If wins are mostly in 'NOT_RANGE' and losses are higher in other states, it validates the range detector.")

        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print(f"Results saved to {OUTPUT_FILE}")
        print("="*80)

    sys.stdout = original_stdout
    with open(OUTPUT_FILE, 'r') as f:
        print(f.read())

if __name__ == "__main__":
    print("--- SCRIPT START ---")
    trades = load_aegis_trades()
    signals = load_arsenal_signals()

    print(f"DEBUG: Loaded {len(trades)} trades.")
    print(f"DEBUG: Loaded {len(signals)} signals.")
    
    if not trades.empty and not signals.empty:
        print("DEBUG: Both dataframes are not empty. Proceeding with correlation.")
        correlated_data = correlate_data(trades, signals)
        print(f"DEBUG: Correlated {len(correlated_data)} trades.")
        analyze_performance_v2(trades, correlated_data)
    else:
        print("--- SCRIPT STOPPED ---")
        print("Reason: Could not proceed with analysis because either the trades dataframe or the signals dataframe was empty.")

    print("--- SCRIPT END ---")
