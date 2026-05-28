"""
WebSocket Handler - Real-time event broadcasting
Forwards UI signals to connected WebSocket clients
"""
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

from api.schemas import WebSocketEvent


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, event: WebSocketEvent):
        """Broadcast an event to all connected clients"""
        message = json.dumps(event.model_dump())
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.append(connection)

            # Clean up disconnected clients
            for conn in disconnected:
                self.active_connections.remove(conn)


# Global connection manager
manager = ConnectionManager()
_broadcast_loop: Optional[asyncio.AbstractEventLoop] = None
_signal_forwarding_initialized = False


async def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Broadcast an event to all connected WebSocket clients"""
    event = WebSocketEvent(
        type=event_type,
        data=data,
        timestamp=datetime.now().isoformat(),
    )
    await manager.broadcast(event)


def _report_broadcast_result(future):
    try:
        future.result()
    except Exception as exc:
        print(f"WebSocket broadcast error: {exc}")


def _schedule_broadcast(event_type: str, data: Dict[str, Any]):
    loop = _broadcast_loop
    if loop is None or loop.is_closed():
        return

    future = asyncio.run_coroutine_threadsafe(
        broadcast_event(event_type, data),
        loop,
    )
    future.add_done_callback(_report_broadcast_result)


def setup_signal_forwarding(loop: Optional[asyncio.AbstractEventLoop] = None):
    """Connect UI signals to WebSocket broadcasting"""
    global _broadcast_loop, _signal_forwarding_initialized

    _broadcast_loop = loop or asyncio.get_running_loop()
    if _signal_forwarding_initialized:
        return
    _signal_forwarding_initialized = True

    from ui.signals import signals

    def make_sync_handler(event_type: str):
        """Create a signal handler that schedules async broadcast"""
        def handler(*args, **kwargs):
            # Build data from signal arguments
            data = {}
            if args:
                if len(args) == 1:
                    if isinstance(args[0], str):
                        if event_type in ("memory_saved", "memory_deleted"):
                            data["memory_id"] = args[0]
                        elif event_type == "screenshot_completed":
                            data["image_path"] = args[0]
                        elif event_type in ("status_updated", "error_occurred"):
                            data["message"] = args[0]
                    elif isinstance(args[0], dict):
                        data = args[0]
                else:
                    # Multiple arguments - use positional keys
                    if event_type == "progress_updated":
                        data["progress"] = args[0] if len(args) > 0 else 0
                        data["message"] = args[1] if len(args) > 1 else ""
                    else:
                        data["args"] = [str(a) for a in args]

            _schedule_broadcast(event_type, data)

        return handler

    # Connect signals
    signals.screenshot_completed.connect(make_sync_handler("screenshot_completed"))
    signals.memory_saved.connect(make_sync_handler("memory_saved"))
    signals.memory_deleted.connect(make_sync_handler("memory_deleted"))
    signals.search_completed.connect(make_sync_handler("search_completed"))
    signals.error_occurred.connect(make_sync_handler("error_occurred"))
    signals.status_updated.connect(make_sync_handler("status_updated"))
    signals.progress_updated.connect(make_sync_handler("progress_updated"))

    # Cluster buffer signals (if available)
    try:
        from container import container
        cluster_buffer = container.get("cluster_buffer")

        def on_cluster_state_changed(state: str, count: int, max_count: int):
            data = {"state": state, "count": count, "max_count": max_count}
            _schedule_broadcast("cluster_state_changed", data)

        def on_cluster_countdown(seconds: int):
            data = {"remaining_seconds": seconds}
            _schedule_broadcast("cluster_countdown", data)

        def on_cluster_flushed(image_paths: list):
            data = {"images": image_paths}
            _schedule_broadcast("cluster_flushed", data)

        def on_cluster_discarded():
            data = {}
            _schedule_broadcast("cluster_discarded", data)

        cluster_buffer.state_changed.connect(on_cluster_state_changed)
        cluster_buffer.countdown_changed.connect(on_cluster_countdown)
        cluster_buffer.flushed.connect(on_cluster_flushed)
        cluster_buffer.discarded.connect(on_cluster_discarded)

    except Exception as e:
        print(f"Warning: Could not connect cluster buffer signals: {e}")


async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connection lifecycle"""
    await manager.connect(websocket)
    try:
        while True:
            # Wait for any message (or just keep connection alive)
            data = await websocket.receive_text()
            # Echo back for keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
