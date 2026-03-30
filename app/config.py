"""
Main configuration file for the Arsenal VPS system.
This file provides central access to all configuration settings.
"""
import os
import json
from dotenv import load_dotenv

# Define the path to the central .env file - use project root directory
DOTENV_PATH = "../.env"  # Go up 1 level to reach project root where .env is located

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
LOG_FILE = "logs/eoh.log"  # Store in logs folder in project root
LOG_LEVEL = "INFO"

# --- Leverage Configuration ---
# Import leverage settings from the eyes_of_horus config to maintain consistency
try:
    from eyes_of_horus.config import LEVERAGE_SETTINGS
except ImportError:
    # Fallback leverage settings if the eyes_of_horus config fails
    # Note: The structure should be symbol -> leverage_number, not symbol -> {"leverage": number}
    LEVERAGE_SETTINGS_RAW = {
        "BTCUSDT": {"leverage": 3},
        "ETHUSDT": {"leverage": 2},
        "SOLUSDT": {"leverage": 2},
        "XRPUSDT": {"leverage": 2},
        "BNBUSDT": {"leverage": 2},
        "LINKUSDT": {"leverage": 2},
        "DOGEUSDT": {"leverage": 2}
    }
    # Extract just the leverage numbers to match expected format
    LEVERAGE_SETTINGS = {symbol: settings["leverage"] for symbol, settings in LEVERAGE_SETTINGS_RAW.items()}

# --- Trading Parameters ---
# Symbols are now derived from the leverage config file.
SYMBOLS = list(LEVERAGE_SETTINGS.keys())

# --- Internal Settings ---
# How often the main guardian loop runs (in seconds)
GUARDIAN_LOOP_INTERVAL = 5