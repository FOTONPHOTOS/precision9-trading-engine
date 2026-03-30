# dashboard_server.py
# Author: Gemini
# Description: The central WebSocket Hub, API, and Prometheus Metrics Exporter for the Mission Control Dashboard.

import asyncio
import json
import logging
import subprocess
from typing import Dict, List

import pandas as pd
import sqlite3
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from starlette.websockets import WebSocketState
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from prometheus_client import make_asgi_app, Counter, Gauge

# --- Configuration ---
AEGIS_DB_PATH = "G:/python files/precision9/Simulation Environment/Trendline_Detectory/eyes_of_horus/eyes_of_horus.db"
LAUNCH_SCRIPT_PATH = "G:/python files/precision9/launch_all_bots.ps1"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Prometheus Metrics ---
metrics = {
    "bot_health": Gauge("p9_bot_health", "Health status of a bot (1=OK, 2=WARNING, 3=ERROR)", ["bot_id"]),
    "account_balance": Gauge("p9_account_balance_usd", "Total account balance in USD"),
    "trades_total": Counter("p9_trades_total", "Total number of trades", ["symbol", "direction", "status"]),
    "active_trades": Gauge("p9_active_trades", "Number of currently active trades", ["symbol"]),
    "stop_hunt_probability": Gauge("p9_stop_hunt_probability", "Stop hunt probability for a symbol", ["symbol"]),
    "market_confidence": Gauge("p9_market_confidence", "Arsenal brain confidence score for a symbol", ["symbol"]),
    "btc_trend_strength": Gauge("p9_btc_trend_strength", "Helios BTC trend strength"),
    "global_leverage_stress": Gauge("p9_global_leverage_stress", "Helios Global Leverage Stress (GLS) score"),
}

# --- FastAPI App ---
app = FastAPI(title="P9 Mission Control Hub")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Add CORS Middleware
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Connection Management ---
class ConnectionManager:
    def __init__(self):
        self.bot_clients: Dict[str, WebSocket] = {}
        self.dashboard_clients: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, client_type: str, client_id: str):
        await websocket.accept()
        if client_type != "dashboard":
            self.bot_clients[client_id] = websocket
            logger.info(f"Bot client connected: {client_type}:{client_id}")
            metrics["bot_health"].labels(bot_id=f"{client_type}:{client_id}").set(1) # Set initial health to OK
        else:
            self.dashboard_clients.append(websocket)
            logger.info(f"Dashboard client connected: {websocket.client.host}")

    def disconnect(self, websocket: WebSocket, client_type: str, client_id: str):
        if client_type != "dashboard" and client_id in self.bot_clients:
            del self.bot_clients[client_id]
            logger.info(f"Bot client disconnected: {client_type}:{client_id}")
            metrics["bot_health"].labels(bot_id=f"{client_type}:{client_id}").set(0) # Set health to 0 (stale)
        elif websocket in self.dashboard_clients:
            self.dashboard_clients.remove(websocket)
            logger.info(f"Dashboard client disconnected: {websocket.client.host}")

    async def broadcast_to_dashboards(self, message: str):
        # ... (broadcast logic remains the same)
        send_tasks = []
        clients_to_remove = []
        for websocket in self.dashboard_clients:
            if websocket.client_state == WebSocketState.CONNECTED:
                send_tasks.append(websocket.send_text(message))
            else:
                clients_to_remove.append(websocket)
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
        for client in clients_to_remove:
            self.dashboard_clients.remove(client)
            logger.info(f"Stale dashboard client removed: {client.client.host}")

manager = ConnectionManager()


# --- Metrics Parsing Logic ---
def update_metrics(message: dict):
    try:
        source_type = message.get("source_type")
        source_id = message.get("source_id")
        event = message.get("event")
        data = message.get("data", {})

        if not all([source_type, source_id, event]):
            return

        bot_id = f"{source_type}:{source_id}"

        if event == "health" or event == "heartbeat":
            status_map = {"OK": 1, "WARNING": 2, "ERROR": 3}
            metrics["bot_health"].labels(bot_id=bot_id).set(status_map.get(data.get("status"), 0))

        elif event == "account_balance_update":
            metrics["account_balance"].set(data.get("balance", 0))

        elif event == "trade_opened":
            metrics["trades_total"].labels(symbol=data.get("symbol"), direction=data.get("direction"), status="opened").inc()
            metrics["active_trades"].labels(symbol=data.get("symbol")).inc()

        elif event == "trade_closed":
            # We don't have a separate "closed" status in the counter, but we could add it
            metrics["active_trades"].labels(symbol=data.get("symbol")).dec()

        elif event == "market_intelligence_update":
            if source_type == "arsenal":
                symbol = source_id
                if data.get("stop_hunt_warning"):
                    prob = data["stop_hunt_warning"].get("stop_hunt_probability", 0)
                    metrics["stop_hunt_probability"].labels(symbol=symbol).set(prob)
                if data.get("decision_update"): # Check if decision is nested
                    conf = data["decision_update"].get("confidence", 0)
                    metrics["market_confidence"].labels(symbol=symbol).set(conf)

        elif event == "decision_update":
             if source_type == "arsenal":
                symbol = source_id
                conf = data.get("confidence", 0)
                metrics["market_confidence"].labels(symbol=symbol).set(conf)


        elif event == "helios_context_update":
            metrics["global_leverage_stress"].set(data.get("gls_score", 0))
            metrics["btc_trend_strength"].set(data.get("trend_strength", 0))

    except Exception as e:
        logger.error(f"Failed to update Prometheus metrics: {e}", exc_info=True)


# --- API Endpoints ---
@app.get("/api/history/trades")
async def get_trade_history():
    logger.info("Received request for /api/history/trades")
    db_path = AEGIS_DB_PATH
    logger.info(f"Connecting to database at: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Log all tables in the database for debugging
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logger.info(f"Tables in database: {[table[0] for table in tables]}")

        # Corrected to use 'created_at' for ordering
        cursor.execute("SELECT * FROM managed_trades ORDER BY created_at DESC LIMIT 100")
        trades = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Successfully fetched {len(trades)} trades.")
        conn.close()
        return trades
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching trade history: {e}", exc_info=True)
        return Response(content=json.dumps({"error": f"Database error: {e}"}), status_code=500, media_type="application/json")
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching trade history: {e}", exc_info=True)
        return Response(content=json.dumps({"error": f"An unexpected error occurred: {e}"}), status_code=500, media_type="application/json")


@app.post("/api/system/start")
async def start_system():
    """
    Launches the entire trading bot ecosystem by executing the launch script.
    """
    logger.info("Received request to start the system.")
    try:
        # Use Popen to run the script in a new non-blocking process
        subprocess.Popen(["powershell.exe", "-File", LAUNCH_SCRIPT_PATH], start_new_session=True)
        logger.info(f"Successfully executed launch script: {LAUNCH_SCRIPT_PATH}")
        return {"status": "success", "message": "System launch command issued."}
    except Exception as e:
        logger.error(f"Failed to execute launch script: {e}", exc_info=True)
        return Response(content=json.dumps({"error": f"Failed to start system: {e}"}), status_code=500, media_type="application/json")


# --- WebSocket Endpoint ---
@app.websocket("/ws/{client_type}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_type: str, client_id: str):
    await manager.connect(websocket, client_type, client_id)
    try:
        while True:
            data_str = await websocket.receive_text()
            # Any client that is not a dashboard is a bot/data provider
            if client_type != "dashboard":
                # Log that a message from a bot is being processed
                logger.info(f"Received message from {client_type}:{client_id}, broadcasting to dashboards.")
                # Update metrics
                try:
                    message = json.loads(data_str)
                    # Use the full client_type:client_id for the bot_id metric
                    full_bot_id = f"{client_type}:{client_id}"
                    # This part needs to be refactored to pass the full_bot_id to update_metrics
                    # For now, let's assume update_metrics can handle it or we add it to the message
                    # A better approach would be to parse and enrich the message here.
                    update_metrics(message) # Prometheus metrics will still use source_type from message content
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON in WebSocket.")
                # Broadcast to dashboards
                await manager.broadcast_to_dashboards(data_str)
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_type, client_id)
    except Exception as e:
        logger.error(f"An error occurred in the websocket endpoint for {client_id}: {e}")
        manager.disconnect(websocket, client_type, client_id)

# ... (rest of the file remains the same)

