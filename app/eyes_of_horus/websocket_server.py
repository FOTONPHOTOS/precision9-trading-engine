import asyncio
import json
import logging
import websockets
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

class WebSocketServer:
    """A WebSocket server to receive trade signals from Arsenal bots."""

    def __init__(self, host: str, port: int, message_handler: Callable[[dict], Awaitable[None]]):
        self.host = host
        self.port = port
        self.message_handler = message_handler
        self.server = None

    async def _handler(self, websocket):
        """Handles a new client connection and processes incoming messages."""
        client_address = websocket.remote_address
        logger.info(f"Arsenal bot connected from {client_address}")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info(f"Received signal from {client_address}: {data.get('decision', {}).get('direction')}, {data.get('decision', {}).get('confidence')}")
                    # Pass the validated data to the trade manager
                    await self.message_handler(data)
                    # Acknowledge receipt
                    await websocket.send(json.dumps({"status": "received", "trade_id": data.get('trade_id')}))
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received from {client_address}: {message}")
                    await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON"}))
                except Exception as e:
                    logger.error(f"Error processing message from {client_address}: {e}")
                    await websocket.send(json.dumps({"status": "error", "message": str(e)}))
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection from {client_address} closed: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred with client {client_address}: {e}")

    async def start(self):
        """Starts the WebSocket server."""
        logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")
        self.server = await websockets.serve(self._handler, self.host, self.port)
        logger.info("WebSocket server is running and waiting for signals.")

    def stop(self):
        """Stops the WebSocket server."""
        if self.server:
            self.server.close()
            logger.info("WebSocket server stopped.")
