import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

def find_db():
    """
    Searches through all found 'eyes_of_horus.db' files to find the one
    containing the recent winning trades mentioned by the user.
    """
    print("--- CORRECT DATABASE LOCATOR ---")

    # This list is from the previous 'glob' command, including unique entries
    db_paths = [
        "G:/python files/precision9/Simulation Environment/Trendline_Detectory/eyes_of_horus/eyes_of_horus.db",
        "G:/python files/precision9/Simulation Environment/backups/nov 5 29% win ate/Simulation Environment/Trendline_Detectory/eyes_of_horus.db",
        "G:/python files/precision9/Simulation Environment/backups/nov 5 29% win ate/Simulation Environment/Trendline_Detectory/eyes_of_horus/eyes_of_horus.db",
        "G:/python files/precision9/Simulation Environment/Trendline_Detectory/eyes_of_horus.db"
    ]
    
    # Filter out duplicate paths and non-existent files
    unique_db_paths = []
    for path in db_paths:
        if os.path.exists(path) and path not in unique_db_paths:
            unique_db_paths.append(path)

    # --- Define the "Golden" Trade ID to search for from Aegis logs ---
    target_trade_id = "rec_1763574096143"
    
    print(f"Searching for trade ID '{target_trade_id}' across all potential databases...")

    correct_db_path = None

    for db_path in unique_db_paths:
        print(f"\n--- Checking database: {db_path} ---")
        
        try:
            con = sqlite3.connect(db_path)
            # Query for the specific trade ID, regardless of status for now
            query = f"SELECT id, trade_id, symbol, direction, qty, entry_price, exit_price, pnl, entry_timestamp, status FROM managed_trades WHERE trade_id = '{target_trade_id}'"
            df = pd.read_sql_query(query, con)
            con.close()

            if not df.empty:
                print(f"  -> SUCCESS: Found trade ID '{target_trade_id}' in this database!")
                print(df.to_markdown(index=False)) # Print the found trade details
                correct_db_path = db_path
                break # Found the correct DB, stop searching
            else:
                print(f"  -> Trade ID '{target_trade_id}' not found in this database.")

        except pd.io.sql.DatabaseError as e:
            # Catch specific error if 'managed_trades' table does not exist
            if "no such table: managed_trades" in str(e):
                print(f"  -> WARNING: Database at {db_path} does not contain the 'managed_trades' table. (Likely uninitialized)")
            else:
                print(f"  -> An error occurred while checking this database: {e}")
        except Exception as e:
            print(f"  -> An unexpected error occurred: {e}")

    print("\n--- SEARCH COMPLETE ---")
    if correct_db_path:
        print(f"\nCONCLUSION: The correct 'live' database is located at:")
        print(correct_db_path)
        print("\nAll future analysis should be pointed to this file.")
    else:
        print("\nCONCLUSION: Could not locate the correct database containing the trade ID '{target_trade_id}'.")
        print("This suggests the live Aegis instance might be logging to a location not covered by the glob search, or that the table initialization is still failing.")

if __name__ == "__main__":
    find_db()
