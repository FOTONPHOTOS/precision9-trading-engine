import os
import json
from dotenv import load_dotenv

# Define the path to the central .env file
DOTENV_PATH = "G:/python files/precision9/Simulation Environment/.env"

# Load environment variables from the specified .env file
load_dotenv(dotenv_path=DOTENV_PATH)

# --- Bybit API Credentials ---
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
# Use "bybit" for mainnet, "bybit_test" for testnet
BYBIT_SESSION = os.getenv("BYBIT_SESSION", "bybit")

# --- Redis Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
# Channel for receiving new trade signals from Arsenal bots
REDIS_SIGNAL_CHANNEL = "eoh:signals"

# --- Database Configuration ---
# The database will be created in the same directory as the project
DATABASE_URL = "sqlite:///eyes_of_horus.db"

# --- Leverage Configuration ---
LEVERAGE_CONFIG_PATH = "G:/python files/precision9/config_tuning/leverage_config.json"
LEVERAGE_SETTINGS = {}
try:
    with open(LEVERAGE_CONFIG_PATH, 'r') as f:
        config = json.load(f)
        LEVERAGE_SETTINGS = config.get("leverage_settings", {})
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f" WARNING: Could not load leverage config from {LEVERAGE_CONFIG_PATH}. Reason: {e}. Using default leverage.")


# --- Trading Parameters ---
# Symbols are now derived from the leverage config file.
SYMBOLS = list(LEVERAGE_SETTINGS.keys())


# --- Logging ---
LOG_FILE = "logs/eoh.log"
LOG_LEVEL = "INFO"

# --- Internal Settings ---
# How often the main guardian loop runs (in seconds)
GUARDIAN_LOOP_INTERVAL = 5
