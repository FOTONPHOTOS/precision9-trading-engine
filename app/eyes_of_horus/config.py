import os
import json
from dotenv import load_dotenv

# Define the path to the central .env file - use project root directory
DOTENV_PATH = "../../.env"  # Go up 2 levels to reach project root where .env is located

# Load environment variables from the specified .env file
load_dotenv(dotenv_path=DOTENV_PATH)

# --- Bybit API Credentials ---
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Check the BYBIT_TESTNET setting and set session accordingly
bybit_testnet_str = os.getenv("BYBIT_TESTNET", "false").lower()
if bybit_testnet_str in ["true", "1", "yes"]:
    BYBIT_SESSION = "bybit_test"
else:
    BYBIT_SESSION = "bybit"  # Use "bybit" for mainnet

# --- Redis Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
# Channel for receiving new trade signals from Arsenal bots
REDIS_SIGNAL_CHANNEL = "eoh:signals"

# --- Database Configuration ---
# The database will be created in the same directory as the project
DATABASE_URL = "sqlite:///eyes_of_horus.db"

# --- Logging Configuration ---
LOG_FILE = "../logs/eoh.log"  # Go up 1 level to project root where logs folder is
LOG_LEVEL = "INFO"

# --- Leverage Configuration ---
LEVERAGE_CONFIG_PATH = "../config_tuning/leverage_config.json"  # Go up 1 level to main Arsenal VPS dir, then into config_tuning
LEVERAGE_SETTINGS = {}
try:
    with open(LEVERAGE_CONFIG_PATH, 'r') as f:
        config = json.load(f)
        # Get the raw settings from the config
        raw_settings = config.get("leverage_settings", {})

        # Handle both possible formats:
        # Format 1: {"BTCUSDT": 3, "ETHUSDT": 2, ...}
        # Format 2: {"BTCUSDT": {"leverage": 3}, "ETHUSDT": {"leverage": 2}, ...}

        LEVERAGE_SETTINGS = {}
        for symbol, leverage_val in raw_settings.items():
            if isinstance(leverage_val, dict):
                # Format 2: leverage is nested inside a dictionary
                LEVERAGE_SETTINGS[symbol] = leverage_val.get("leverage", 1)  # Default to 1 if not found
            else:
                # Format 1: leverage is a direct value
                LEVERAGE_SETTINGS[symbol] = leverage_val

except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f" WARNING: Could not load leverage config from {LEVERAGE_CONFIG_PATH}. Reason: {e}. Using default leverage.")
    # Use default leverage settings if file is not found
    LEVERAGE_SETTINGS = {
        "BTCUSDT": 3,  # 3x leverage
        "ETHUSDT": 2,  # 2x leverage
        "SOLUSDT": 2,  # 2x leverage
        "XRPUSDT": 2,  # 2x leverage
        "BNBUSDT": 2,  # 2x leverage
        "LINKUSDT": 2, # 2x leverage
        "DOGEUSDT": 2 # 2x leverage
    }
except Exception as e:
    print(f" ERROR: Unexpected error loading leverage config: {e}. Using default leverage.")
    LEVERAGE_SETTINGS = {
        "BTCUSDT": 3,  # 3x leverage
        "ETHUSDT": 2,  # 2x leverage
        "SOLUSDT": 2,  # 2x leverage
        "XRPUSDT": 2,  # 2x leverage
        "BNBUSDT": 2,  # 2x leverage
        "LINKUSDT": 2, # 2x leverage
        "DOGEUSDT": 2 # 2x leverage
    }

# --- Trading Parameters ---
# Symbols are now derived from the leverage config file.
SYMBOLS = list(LEVERAGE_SETTINGS.keys())

# --- Internal Settings ---
# How often the main guardian loop runs (in seconds)
GUARDIAN_LOOP_INTERVAL = 5