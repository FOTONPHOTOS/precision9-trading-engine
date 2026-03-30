import sqlite3
import pandas as pd
import numpy as np
import os
import sys

# --- Configuration ---
AEGIS_DB_PATH = os.path.join(os.path.dirname(__file__), 'eyes_of_horus', 'eyes_of_horus.db')

def debug_database():
    """Connects to the Aegis DB and inspects the raw trade data to find PnL discrepancies."""
    print(f"--- AEGIS DATABASE DEBUGGER ---")
    print(f"Connecting to {AEGIS_DB_PATH}...")
    
    if not os.path.exists(AEGIS_DB_PATH):
        print(f"ERROR: Database not found at {AEGIS_DB_PATH}")
        return
        
    try:
        con = sqlite3.connect(AEGIS_DB_PATH)
        # Get all closed trades, ordering by the most recent first
        query = "SELECT id, symbol, direction, qty, entry_price, exit_price, pnl FROM managed_trades WHERE status = 'closed' ORDER BY id DESC"
        df = pd.read_sql_query(query, con)
        con.close()
        
        if df.empty:
            print("No 'closed' trades found in the database.")
            return

        print(f"\nSuccessfully loaded {len(df)} closed trades. Analyzing the 20 most recent trades for PnL discrepancies...")
        
        # --- Manual PnL Calculation Check ---
        # Focus on the most recent trades as mentioned by the user
        sample = df.head(20)
        
        results = []
        
        for _, row in sample.iterrows():
            calculated_pnl = 0
            is_win = False
            
            # Check if data is valid for calculation
            if row['direction'] and row['exit_price'] is not None and row['entry_price'] is not None and row['qty'] is not None:
                if row['direction'] == 'LONG':
                    calculated_pnl = (row['exit_price'] - row['entry_price']) * row['qty']
                elif row['direction'] == 'SHORT':
                    calculated_pnl = (row['entry_price'] - row['exit_price']) * row['qty']
                
                is_win = calculated_pnl > 0
            
            results.append({
                "ID": row['id'],
                "Symbol": row['symbol'],
                "Direction": row['direction'],
                "DB PnL": f"{row['pnl']:.4f}" if row['pnl'] is not None else "NULL",
                "Calculated PnL": f"{calculated_pnl:.4f}",
                "Is Win?": "YES" if is_win else "NO",
                "Discrepancy": "!!!!" if row['pnl'] is None or not np.isclose(row['pnl'], calculated_pnl) else ""
            })

        # --- Print Results in a Clear Table ---
        if results:
            results_df = pd.DataFrame(results)
            print("\n--- PNL ANALYSIS OF 20 MOST RECENT TRADES ---")
            print(results_df.to_markdown(index=False))
        else:
            print("Could not generate PnL analysis for recent trades.")

        print("\n--- ANALYSIS ---")
        discrepancies = sum(1 for r in results if r["Discrepancy"] == "!!!!")
        wins_found = sum(1 for r in results if r["Is Win?"] == "YES")
        
        print(f"Found {wins_found} winning trade(s) in the last 20 trades based on manual calculation.")
        
        if discrepancies > 0:
            print(f"\nCRITICAL FINDING: Found {discrepancies} discrepancies between the stored 'pnl' in the database and the manually calculated PnL.")
            print("This confirms the 'pnl' column is being saved incorrectly in the Aegis system.")
            print("The analysis scripts should use a manually calculated PnL value until the Aegis bug is fixed.")
        else:
            print("No discrepancies found. The 'pnl' column appears to be correct for the most recent trades.")

        print("\n--- DEBUG COMPLETE ---")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    debug_database()
