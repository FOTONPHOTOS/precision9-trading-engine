import sqlite3
import json
import pandas as pd
import os
import glob

# --- Configuration ---
AEGIS_DB_PATH = os.path.join(os.path.dirname(__file__), 'eyes_of_horus', 'eyes_of_horus.db')
SIGNAL_DIR = os.path.dirname(__file__)
SYMBOLS = ["ETHUSDT", "BTCUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "LINKUSDT"]
OUTPUT_FILE = "analysis_results.txt"


def load_aegis_trades():
    """Loads all trades from the Aegis SQLite database."""
    print(f"Loading trades from {AEGIS_DB_PATH}...")
    if not os.path.exists(AEGIS_DB_PATH):
        print(f"ERROR: Aegis database not found at {AEGIS_DB_PATH}")
        return pd.DataFrame()
        
    try:
        con = sqlite3.connect(AEGIS_DB_PATH)
        # Query only closed trades with a recorded PnL
        query = "SELECT * FROM managed_trades WHERE status = 'closed' AND pnl IS NOT NULL"
        df = pd.read_sql_query(query, con)
        con.close()
        
        # Convert timestamps from ms to datetime objects
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
                    # Add symbol to the record, as it's not in the signal log itself
                    signal['symbol'] = symbol
                    all_signals.append(signal)
                except json.JSONDecodeError:
                    print(f"Skipping corrupted line in {file_path}")
    
    if not all_signals:
        print("ERROR: No signal files found or all were empty/corrupt.")
        return pd.DataFrame()

    # Flatten the nested JSON structure
    df = pd.json_normalize(all_signals, sep='_')
    
    # Rename columns for clarity and consistency
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
    
    # Convert timestamp to datetime object
    df['signal_datetime'] = pd.to_datetime(df['signal_datetime'])
    
    # Select only the columns we need for the analysis
    required_cols = [
        'symbol', 'signal_datetime', 'signal_direction', 'signal_confidence', 
        'range_score', 'range_state', 'stop_hunt_prob', 'stop_hunt_type', 'horus_confirmed'
    ]
    
    # Add missing columns with default values if they don't exist
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
        
    print("Correlating trades with signals (robust, per-symbol method)...")

    # --- Robustness Fix v3: Clean data and process per symbol ---
    trades_df.dropna(subset=['entry_datetime', 'symbol'], inplace=True)
    signals_df.dropna(subset=['signal_datetime', 'symbol'], inplace=True)
    
    trades_df['symbol'] = trades_df['symbol'].astype(str)
    signals_df['symbol'] = signals_df['symbol'].astype(str)

    all_correlated_dfs = []
    unique_symbols = trades_df['symbol'].unique()

    for symbol in unique_symbols:
        print(f"  - Processing symbol: {symbol}")
        
        # Create subsets for the current symbol
        trades_subset = trades_df[trades_df['symbol'] == symbol].copy()
        signals_subset = signals_df[signals_df['symbol'] == symbol].copy()

        # Sort each subset by its datetime column
        trades_subset.sort_values(by='entry_datetime', inplace=True)
        signals_subset.sort_values(by='signal_datetime', inplace=True)

        # Perform the merge on the single-symbol, sorted dataframes
        correlated_subset = pd.merge_asof(
            left=trades_subset,
            right=signals_subset,
            left_on='entry_datetime',
            right_on='signal_datetime',
            direction='backward',
            tolerance=pd.Timedelta('5min')
        )
        all_correlated_dfs.append(correlated_subset)

    if not all_correlated_dfs:
        print("No correlations found after processing all symbols.")
        return pd.DataFrame()

    # Combine all the results
    final_correlated_df = pd.concat(all_correlated_dfs).reset_index(drop=True)
    
    # Filter out trades that couldn't be matched with a signal
    final_correlated_df.dropna(subset=['signal_datetime'], inplace=True)
    
    print(f"Successfully correlated {len(final_correlated_df)} trades with a preceding signal.")
    return final_correlated_df


def analyze_performance(df):
    """Analyzes the performance of losing trades based on signal data."""
    if df.empty:
        print("No correlated data to analyze.")
        return

    # --- Setup Output ---
    original_stdout = sys.stdout
    with open(OUTPUT_FILE, 'w') as f:
        sys.stdout = f

        print("="*80)
        print("ARSENAL PERFORMANCE ANALYSIS")
        print("="*80)

        # --- High-Level Overview ---
        total_trades = len(df)
        winning_trades = df[df['pnl'] > 0]
        losing_trades = df[df['pnl'] <= 0]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        total_pnl = df['pnl'].sum()

        print("\n--- OVERALL PERFORMANCE ---")
        print(f"Total Correlated Trades: {total_trades}")
        print(f"Winning Trades: {len(winning_trades)}")
        print(f"Losing Trades: {len(losing_trades)}")
        print(f"Win Rate: {win_rate:.2%}")
        print(f"Total PnL: {total_pnl:,.2f}")
        print("-"*80)

        # --- Analysis of Losing Trades ---
        print("\n--- DEEP DIVE: ANALYSIS OF LOSING TRADES ---")
        if losing_trades.empty:
            print("No losing trades to analyze. Good job!")
            return
            
        # 1. Analysis by Market Range State
        print("\n[1] Performance by Market Range State at Time of Signal:")
        loss_by_range_state = losing_trades.groupby('range_state')['pnl'].agg(['count', 'sum']).sort_values(by='count', ascending=False)
        print(loss_by_range_state)
        print("\n   Interpretation:")
        print("   - This shows which 'range_state' the market was in when the signals for losing trades were generated.")
        print("   - High loss counts in 'RANGE_BOUND' or 'CHOPPY' states suggest the range detection is working, but the bot is still trading and losing.")

        # 2. Analysis of Range Score in Losing Trades
        print("\n[2] Distribution of 'Range Score' for Losing Trades:")
        print(losing_trades['range_score'].describe(percentiles=[.25, .50, .75, .90]))
        print("\n   Interpretation:")
        print("   - 'range_score' quantifies how 'rangey' the market is (higher score = more ranging).")
        print("   - If the mean/median score for losses is high, it confirms the bot loses money in ranging conditions.")
        print("   - The 75% and 90% percentile values are good candidates for new, stricter filter thresholds.")

        # 3. Analysis of Stop Hunt Probability in Losing Trades
        print("\n[3] Distribution of 'Stop Hunt Probability' for Losing Trades:")
        print(losing_trades['stop_hunt_prob'].describe(percentiles=[.25, .50, .75, .90]))
        print("\n   Interpretation:")
        print("   - 'stop_hunt_prob' estimates the risk of market manipulation.")
        print("   - If the mean/median for losses is high, it suggests the bot is getting caught in liquidity grabs/manipulation.")
        print("   - A high 75% or 90% percentile could be a new threshold to filter out risky trades.")
        
        # 4. Horus Confirmation on Losing Trades
        print("\n[4] Horus Confirmation on Losing Trades:")
        horus_rejection_losses = losing_trades[losing_trades['horus_confirmed'] == False]
        print(f"   Losing trades where Horus rejected the signal: {len(horus_rejection_losses)} (This should be 0 if correlation logic is correct)")

        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print(f"Results saved to {OUTPUT_FILE}")
        print("="*80)

    # --- Restore stdout ---
    sys.stdout = original_stdout
    # Also print to console
    with open(OUTPUT_FILE, 'r') as f:
        print(f.read())


if __name__ == "__main__":
    import sys
    # Load Aegis trades
    trades = load_aegis_trades()
    if not trades.empty:
        print("\n--- Aegis Trades (first 5 rows) ---")
        print(trades.head())
    
    # Load Arsenal signals
    signals = load_arsenal_signals()
    if not signals.empty:
        print("\n--- Arsenal Signals (first 5 rows) ---")
        print(signals.head())

    # Correlate and Analyze
    correlated_data = correlate_data(trades, signals)
    if not correlated_data.empty:
        print("\n--- Correlated Data (first 5 rows) ---")
        print(correlated_data.head())
        analyze_performance(correlated_data)
