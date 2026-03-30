
import sqlite3

# --- Configuration ---
AEGIS_DB_PATH = "G:/python files/precision9/Simulation Environment/Trendline_Detectory/eyes_of_horus/eyes_of_horus.db"

def get_table_schema(db_path, table_name):
    """Prints the schema of a specific table in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        schema = cursor.fetchall()
        conn.close()
        
        if schema:
            print(f"Schema for table '{table_name}':")
            for column in schema:
                print(f"  - Column {column[0]}: {column[1]} (Name: {column[2]})")
        else:
            print(f"Table '{table_name}' not found in the database.")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    get_table_schema(AEGIS_DB_PATH, "managed_trades")
