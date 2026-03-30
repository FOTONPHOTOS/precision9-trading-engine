
import os
import json
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# --- Configuration ---
CONFIG_FILE = 'leverage_config.json'
# Load environment variables from a .env file if it exists
load_dotenv() 

# --- Load API Credentials ---
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

def load_config():
    """Loads the leverage configuration from the JSON file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f" ERROR: Configuration file not found at {CONFIG_FILE}")
        return None
    except json.JSONDecodeError:
        print(f" ERROR: Could not decode JSON from {CONFIG_FILE}")
        return None

def set_leverage_for_symbols(session, leverage_settings):
    """Iterates through symbols and sets their leverage."""
    print("Setting leverage for symbols...")
    for symbol, leverage in leverage_settings.items():
        try:
            leverage_str = str(leverage)
            session.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=leverage_str,
                sellLeverage=leverage_str,
            )
            print(f" Successfully set leverage for {symbol} to {leverage}x")
        except Exception as e:
            print(f" ERROR setting leverage for {symbol}: {e}")
            # Optionally, decide if you want to stop the script on failure
            # raise e 

def main():
    """Main function to set leverage."""
    # --- Check for API Keys ---
    if not API_KEY or not API_SECRET:
        print(" ERROR: Make sure BYBIT_API_KEY and BYBIT_API_SECRET are set as environment variables.")
        return

    # --- Load Configuration ---
    config = load_config()
    if not config or "leverage_settings" not in config:
        print(" ERROR: Invalid or missing 'leverage_settings' in config file.")
        return

    leverage_settings = config["leverage_settings"]

    # --- Initialize Bybit Session ---
    try:
        session = HTTP(
            testnet=False, # Set to False for live trading
            api_key=API_KEY,
            api_secret=API_SECRET,
        )
        print(" Successfully connected to Bybit API.")
    except Exception as e:
        print(f" ERROR: Failed to connect to Bybit API: {e}")
        return

    # --- Set Leverage ---
    set_leverage_for_symbols(session, leverage_settings)
    print("\n Leverage setting process complete.")

if __name__ == "__main__":
    main()
