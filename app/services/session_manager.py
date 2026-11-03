import asyncio
import time
from typing import Dict, Set
from fastapi import WebSocket
from app.core.logger import logger


class SessionManager:
    """
    Manages active WebSocket client sessions, enforces concurrency limits,
    tracks session lifetimes, and provides health telemetry.
    """

    def __init__(self, max_concurrent: int = 50):
        self.max_concurrent = max_concurrent
        self._active_sessions: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        self.start_time = time.time()

    @property
    def active_count(self) -> int:
        return len(self._active_sessions)

    @property
    def uptime_seconds(self) -> float:
        return round(time.time() - self.start_time, 2)

    async def can_accept(self) -> bool:
        async with self._lock:
            return len(self._active_sessions) < self.max_concurrent

    async def register(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._active_sessions[session_id] = websocket
            logger.info(f"Registered session [{session_id}]. Total active: {len(self._active_sessions)}")

    async def unregister(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self._active_sessions:
                del self._active_sessions[session_id]
                logger.info(f"Unregistered session [{session_id}]. Total active: {len(self._active_sessions)}")

    async def close_all(self, reason: str = "Server shutdown") -> None:
        async with self._lock:
            sessions = list(self._active_sessions.values())
            self._active_sessions.clear()

        for ws in sessions:
            try:
                await ws.close(code=1001, reason=reason)
            except Exception:
                pass
        logger.info(f"Closed all active sessions with reason: {reason}")

