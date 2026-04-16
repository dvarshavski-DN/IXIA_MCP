"""IxNetwork connection manager.

Manages a pool of IxNetwork sessions keyed by connection ID.
Each user/agent gets their own connection to a separate IxNetwork session.
"""

from __future__ import annotations

import os
import time
import uuid
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from ixnetwork_restpy import SessionAssistant

from ixia_mcp.request_context import request_headers_var

logger = logging.getLogger("ixia_mcp")


@dataclass
class IxNetworkConnection:
    """Wraps a single IxNetwork session."""

    connection_id: str
    host: str
    rest_port: int
    session_id: int
    session_assistant: SessionAssistant
    ixnetwork: Any = field(init=False)
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.ixnetwork = self.session_assistant.Ixnetwork


class ConnectionManager:
    """Pool of IxNetwork connections."""

    def __init__(
        self,
        *,
        default_host: str | None = None,
        default_port: int | None = None,
        default_session_id: int | None = None,
        default_user: str | None = None,
        default_password: str | None = None,
        max_idle_seconds: int | None = None,
    ) -> None:
        self._connections: dict[str, IxNetworkConnection] = {}
        self._lock = threading.Lock()
        self.max_idle_seconds = max_idle_seconds if max_idle_seconds is not None else int(os.environ.get("IXIA_MAX_IDLE_SECONDS", "3600"))
        # CLI args > env vars > hardcoded defaults
        self._default_host = default_host if default_host is not None else os.environ.get("IXIA_HOST", "127.0.0.1")
        self._default_port = default_port if default_port is not None else int(os.environ.get("IXIA_PORT", "11009"))
        self._default_session_id = default_session_id if default_session_id is not None else int(os.environ.get("IXIA_SESSION_ID", "1"))
        self._default_user = default_user if default_user is not None else os.environ.get("IXIA_USER", "admin")
        self._default_password = default_password if default_password is not None else os.environ.get("IXIA_PASSWORD", "admin")

    def connect(
        self,
        host: str | None = None,
        rest_port: int | None = None,
        session_id: int | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> IxNetworkConnection:
        """Connect to an existing IxNetwork session.

        Resolution order for each parameter:
            1. Explicit value passed to this call
            2. Per-user HTTP header (X-IXIA-HOST, etc.) from MCP client config
            3. Server-side default from CLI args / environment variable
            4. Hardcoded fallback
        """
        def _first_not_none(*values):
            for v in values:
                if v is not None:
                    return v
            return None

        rh = request_headers_var.get()
        host = _first_not_none(host, rh.ixia_host, self._default_host)
        rest_port = _first_not_none(rest_port, rh.ixia_port, self._default_port)
        session_id = _first_not_none(session_id, rh.ixia_session_id, self._default_session_id)
        username = _first_not_none(username, rh.ixia_user, self._default_user)
        password = _first_not_none(password, rh.ixia_password, self._default_password)

        logger.info("Connecting to IxNetwork at %s:%d session %d", host, rest_port, session_id)

        session_assistant = SessionAssistant(
            IpAddress=host,
            RestPort=rest_port,
            UserName=username,
            Password=password,
            SessionId=session_id,
            LogLevel=SessionAssistant.LOGLEVEL_WARNING,
        )

        connection_id = uuid.uuid4().hex[:12]
        conn = IxNetworkConnection(
            connection_id=connection_id,
            host=host,
            rest_port=rest_port,
            session_id=session_id,
            session_assistant=session_assistant,
        )
        with self._lock:
            self._connections[connection_id] = conn
        logger.info("Connected — connection_id=%s", connection_id)
        return conn

    def get(self, connection_id: str) -> IxNetworkConnection:
        """Retrieve an active connection by ID."""
        with self._lock:
            conn = self._connections.get(connection_id)
            if conn is not None:
                conn.last_used_at = time.time()
        if conn is None:
            raise KeyError(
                f"No active connection with id '{connection_id}'. "
                "Use ixia_connect first to establish a connection."
            )
        return conn

    def disconnect(self, connection_id: str) -> None:
        """Remove a connection from the pool."""
        with self._lock:
            conn = self._connections.pop(connection_id, None)
        if conn is None:
            raise KeyError(
                f"No active connection with id '{connection_id}'. Nothing to disconnect."
            )
        logger.info("Disconnected connection_id=%s", connection_id)

    def disconnect_all(self) -> None:
        """Disconnect all active connections (used during shutdown)."""
        with self._lock:
            ids = list(self._connections.keys())
            for cid in ids:
                self._connections.pop(cid, None)
        logger.info("Disconnected all connections (%d)", len(ids))

    def disconnect_stale(self, max_idle_seconds: int | None = None) -> list[str]:
        """Remove connections idle longer than *max_idle_seconds*.

        Returns list of reaped connection IDs.
        """
        threshold = max_idle_seconds if max_idle_seconds is not None else self.max_idle_seconds
        now = time.time()
        reaped: list[str] = []
        with self._lock:
            for cid, conn in list(self._connections.items()):
                if now - conn.last_used_at > threshold:
                    del self._connections[cid]
                    reaped.append(cid)
        if reaped:
            logger.info("Reaped %d stale connection(s): %s", len(reaped), reaped)
        return reaped

    def list_connections(self) -> list[dict[str, Any]]:
        """Return summary of all active connections."""
        with self._lock:
            return [
                {
                    "connection_id": c.connection_id,
                    "host": c.host,
                    "rest_port": c.rest_port,
                    "session_id": c.session_id,
                }
                for c in self._connections.values()
            ]
