# dashboard_client.py
# Author: Gemini
# Description: Client-side module for emitting data to the central dashboard server via WebSockets.

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class Emitter:
    """
    A client for emitting data to the central dashboard server via WebSockets.
    Handles connection management, queuing messages, and sending heartbeats.
    """

    def __init__(self, client_type: str, client_id: str, uri: str = "ws://localhost:8000/ws"):
        self.client_type = client_type
        self.client_id = client_id
        self.uri = f"{uri}/{client_type}/{client_id}"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.message_queue = asyncio.Queue()
        self.send_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None

        logger.info(f"Emitter initialized for {self.client_type}:{self.client_id} to {self.uri}")

    async def connect(self):
        """Establishes a WebSocket connection to the server."""
        while True:
            try:
                logger.info(f"Attempting to connect emitter {self.client_id} to {self.uri}...")
                self.websocket = await websockets.connect(self.uri)
                self.is_connected = True
                logger.info(f"Emitter {self.client_id} connected.")
                
                # Start sending queued messages
                self.send_task = asyncio.create_task(self._send_messages_loop())
                # Start sending heartbeats
                self.heartbeat_task = asyncio.create_task(self._send_heartbeat_loop())

                # Process any messages that were queued while disconnected
                while not self.message_queue.empty():
                    message = await self.message_queue.get()
                    await self._send_message(message)
                
                return # Connection successful
            except (websockets.exceptions.ConnectionClosedOK,
                    websockets.exceptions.ConnectionClosedError,
                    ConnectionRefusedError) as e:
                self.is_connected = False
                logger.warning(f"Emitter connection failed for {self.client_id}: {e}. Retrying in 5 seconds...")
                await self._cleanup_tasks() # Ensure tasks are stopped before retrying
                await asyncio.sleep(5)
            except Exception as e:
                self.is_connected = False
                logger.error(f"Unexpected error during emitter connection for {self.client_id}: {e}", exc_info=True)
                await self._cleanup_tasks() # Ensure tasks are stopped before retrying
                await asyncio.sleep(10) # Longer delay for unexpected errors

    async def _cleanup_tasks(self):
        """Cancels and awaits internal tasks."""
        if self.send_task and not self.send_task.done():
            self.send_task.cancel()
            try: await self.send_task
            except asyncio.CancelledError: pass
            self.send_task = None
        
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try: await self.heartbeat_task
            except asyncio.CancelledError: pass
            self.heartbeat_task = None

    async def _send_messages_loop(self):
        """Continuously sends messages from the queue when connected."""
        while self.is_connected:
            try:
                message = await self.message_queue.get()
                await self._send_message(message)
            except asyncio.CancelledError:
                break # Task cancelled
            except Exception as e:
                logger.error(f"Error in send messages loop for {self.client_id}: {e}", exc_info=True)
                await asyncio.sleep(1) # Prevent busy loop on persistent errors

    async def _send_message(self, message: Dict[str, Any]):
        """Sends a single message over the WebSocket."""
        try:
            if self.websocket and self.is_connected:
                message_str = json.dumps(message, default=str) # default=str to handle datetimes
                await self.websocket.send(message_str)
                # logger.debug(f"Emitter {self.client_id} sent: {message['event']}")
            else:
                await self.message_queue.put(message) # Re-queue if not connected
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"Emitter connection lost for {self.client_id} during send. Re-queueing message.")
            self.is_connected = False
            await self.message_queue.put(message) # Re-queue
            asyncio.create_task(self.connect()) # Attempt reconnect
        except Exception as e:
            logger.error(f"Error sending message for {self.client_id}: {e}", exc_info=True)

    async def _send_heartbeat_loop(self):
        """Sends periodic heartbeats to maintain connection and signal liveness."""
        while True:
            await asyncio.sleep(10) # Send heartbeat every 10 seconds
            if self.is_connected:
                await self.emit("heartbeat", {"timestamp": datetime.now()})
            elif not self.reconnect_task or self.reconnect_task.done():
                self.reconnect_task = asyncio.create_task(self.connect()) # Ensure reconnect is running

    async def emit(self, event: str, data: Dict[str, Any]):
        """Adds a message to the queue to be sent."""
        message = {
            "source_type": self.client_type,
            "source_id": self.client_id,
            "event": event,
            "timestamp": datetime.now(),
            "data": data
        }
        await self.message_queue.put(message)

    async def emit_health(self, status: str, message: str = "OK", extra_info: Optional[Dict] = None):
        """Emits a standard health status message."""
        health_data = {
            "status": status, # "OK", "WARNING", "ERROR"
            "message": message,
            "timestamp": datetime.now()
        }
        if extra_info:
            health_data.update(extra_info)
        await self.emit("health", health_data)

    async def start(self):
        """Starts the emitter's connection and message sending loops."""
        self.reconnect_task = asyncio.create_task(self.connect())
        # Keep the main coroutine running, but don't block
        # The internal loops handle reconnection and sending

    async def stop(self):
        """Stops the emitter and closes the WebSocket connection."""
        logger.info(f"Stopping Emitter for {self.client_id}...")
        if self.reconnect_task:
            self.reconnect_task.cancel()
            try: await self.reconnect_task
            except asyncio.CancelledError: pass
        await self._cleanup_tasks()
        if self.websocket:
            await self.websocket.close()
        self.is_connected = False
        logger.info(f"Emitter {self.client_id} stopped.")

# Example Usage (for testing)
async def main():
    # Example bot emitter
    bot_emitter = Emitter("arsenal", "SOLUSDT")
    await bot_emitter.start()

    # Example dashboard emitter (usually dashboard doesn't emit, but for testing)
    # dashboard_emitter = Emitter("dashboard", "my_dashboard")
    # await dashboard_emitter.start()

    # Simulate sending data
    for i in range(10):
        await asyncio.sleep(2)
        await bot_emitter.emit("market_intelligence", {"price": 100 + i, "volume": 1000 + i})
        await bot_emitter.emit_health("OK", message=f"Analysis cycle {i} complete")
    
    await asyncio.sleep(5)
    await bot_emitter.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
