import asyncio
import logging
import signal
import sys
import os
from logging.handlers import RotatingFileHandler

# Add parent directory to Python path to allow module imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from eyes_of_horus.config import LOG_FILE, LOG_LEVEL
from eyes_of_horus.database import init_db
from eyes_of_horus.trade_manager import TradeManager

def setup_logging():
    """Configures logging to both console and a rotating file."""
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.stream.reconfigure(encoding='utf-8') # NEW: Set encoding on the stream
    console_handler.setFormatter(log_formatter)
    
    # File handler
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5) # 10 MB per file
    file_handler.setFormatter(log_formatter)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    logging.info("Logging initialized.")

async def main():
    """The main entry point for the application."""
    setup_logging()
    
    logging.info("--- Starting Eyes of Horus --- ")
    
    # Initialize the database and create tables
    try:
        init_db()
        logging.info("Database initialization complete.")
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        return # Exit if DB can't be initialized

    # Create and run the Trade Manager
    manager = TradeManager(host="localhost", port=8765)

    try:
        await manager.run()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received.")
    except asyncio.CancelledError:
        logging.info("Main task cancelled.")
    except OSError as e:
        logging.error(f"Failed to start Aegis server (port may be in use): {e}", exc_info=True)
    except Exception as e:
        logging.error(f"An unhandled exception occurred in the Trade Manager: {e}", exc_info=True)
    finally:
        await shutdown(manager)

async def shutdown(manager: TradeManager):
    """Gracefully shuts down the application."""
    logging.info("Initiating graceful shutdown...")
    await manager.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application interrupted by user.")
