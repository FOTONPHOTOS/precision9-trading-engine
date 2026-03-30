import sqlite3
import pandas as pd
import os

# --- Configuration ---
AEGIS_DB_PATH = os.path.join(os.path.dirname(__file__), 'eyes_of_horus', 'eyes_of_horus.db')

def investigate_status():
    """Connects to the Aegis DB and investigates the status of all trades."""
    print(f"--- AEGIS TRADE STATUS INVESTIGATOR ---")
    print(f"Connecting to {AEGIS_DB_PATH}...")
    
    if not os.path.exists(AEGIS_DB_PATH):
        print(f"ERROR: Database not found at {AEGIS_DB_PATH}")
        return
        
    try:
        con = sqlite3.connect(AEGIS_DB_PATH)
        query = "SELECT id, symbol, status, direction, entry_price, pnl, created_at FROM managed_trades ORDER BY id DESC"
        df = pd.read_sql_query(query, con)
        con.close()
        
        if df.empty:
            print("The 'managed_trades' table is completely empty.")
            return

        print(f"\nSuccessfully loaded {len(df)} total trade entries.")
        
        # --- 1. Group by Status ---
        print("\n[1] Trade Count by Status:")
        status_counts = df['status'].value_counts()
        print(status_counts.to_markdown(headers=['Status', 'Count']))
        
        # --- 2. Investigate Non-Closed Trades ---
        active_trades = df[df['status'] == 'active']
        if not active_trades.empty:
            print("\n[2] Found Active Trades:")
            print(f"   There are {len(active_trades)} trades currently in 'active' status.")
            print("   These trades have not been closed yet. Any 'wins' the user is seeing might be among these.")
            print("   Showing the 10 most recent active trades:")
            print(active_trades.head(10).to_markdown(index=False))
        else:
            print("\n[2] No trades are currently in 'active' status.")

        closing_trades = df[df['status'] == 'closing']
        if not closing_trades.empty:
            print("\n[3] Found Trades Stuck in 'Closing' Status:")
            print(f"   WARNING: There are {len(closing_trades)} trades stuck in 'closing' status.")
            print("   This could indicate a bug where the system fails to confirm a trade has been closed.")
            print("   Showing the 10 most recent stuck trades:")
            print(closing_trades.head(10).to_markdown(index=False))
        else:
            print("\n[3] No trades are stuck in 'closing' status.")

        print("\n--- ANALYSIS ---")
        if not active_trades.empty or not closing_trades.empty:
            print("The user's observation of winning trades is likely correct.")
            print("The issue is that these trades are NOT being moved to the 'closed' status in the database.")
            print("This could be due to several reasons:")
            print("  - A bug in the trade closing logic in 'trade_manager.py'.")
            print("  - A loss of connection to the exchange before the trade's final status could be saved.")
            print("  - The trades are genuinely still open and have not hit their Take Profit or Stop Loss yet.")
            print("\nRECOMMENDATION: The primary focus should be to debug 'trade_manager.py' in the 'eyes_of_horus' directory to understand why trades are not being correctly closed and updated in the database.")
        else:
            print("No 'active' or 'closing' trades were found.")
            print("This deepens the mystery. If the trades are not in the database as 'active' or 'closed', then there is a fundamental disconnect between what the user is observing and what Aegis is recording.")

        print("\n--- INVESTIGATION COMPLETE ---")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    investigate_status()
