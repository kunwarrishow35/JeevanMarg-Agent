"""WebSocket connection manager for real-time mission streaming."""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("jeevanmarg.ws")


class ConnectionManager:
    """Manages WebSocket connections for mission event streaming."""

    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}  # mission_id -> websockets
        self._global_connections: list[WebSocket] = []  # connections listening to all

    async def connect(self, websocket: WebSocket, mission_id: int = 0) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if mission_id > 0:
            if mission_id not in self._connections:
                self._connections[mission_id] = []
            self._connections[mission_id].append(websocket)
        else:
            self._global_connections.append(websocket)
        logger.info(f"WebSocket connected for mission {mission_id}")

    def disconnect(self, websocket: WebSocket, mission_id: int = 0) -> None:
        """Remove a WebSocket connection."""
        if mission_id > 0 and mission_id in self._connections:
            self._connections[mission_id] = [
                ws for ws in self._connections[mission_id] if ws != websocket
            ]
        self._global_connections = [
            ws for ws in self._global_connections if ws != websocket
        ]

    async def broadcast_to_mission(self, mission_id: int, data: dict) -> None:
        """Send an event to all WebSocket connections for a specific mission."""
        message = json.dumps(data, default=str)
        dead_connections = []

        # Send to mission-specific connections
        for ws in self._connections.get(mission_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append((mission_id, ws))

        # Send to global connections
        for ws in self._global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append((0, ws))

        # Clean up dead connections
        for mid, ws in dead_connections:
            self.disconnect(ws, mid)

    async def disconnect_all_for_mission(self, mission_id: int) -> None:
        """Close and remove all WebSocket connections for a specific mission."""
        if mission_id in self._connections:
            websockets = list(self._connections[mission_id])
            for ws in websockets:
                try:
                    await ws.close()
                except Exception:
                    pass
            self._connections[mission_id] = []
            logger.info(f"Disconnected all WebSockets for mission {mission_id}")

    async def broadcast_global(self, data: dict) -> None:
        """Send an event to all connected WebSocket clients."""
        message = json.dumps(data, default=str)
        dead_connections = []

        for ws in self._global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(ws)

        for mid, connections in self._connections.items():
            for ws in connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead_connections.append(ws)


# Global singleton
ws_manager = ConnectionManager()
