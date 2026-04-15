"""IxNetwork connection manager.

Manages a pool of IxNetwork sessions keyed by connection ID.
Each user/agent gets their own connection to a separate IxNetwork session.
"""

from __future__ import annotations

import os
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any

from ixnetwork_restpy import SessionAssistant

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
    ) -> None:
        self._connections: dict[str, IxNetworkConnection] = {}
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
            2. Default from CLI args (set at server startup via MCP config)
            3. Environment variable (IXIA_HOST, IXIA_PORT, etc.)
            4. Hardcoded fallback
        """
        host = host if host is not None else self._default_host
        rest_port = rest_port if rest_port is not None else self._default_port
        session_id = session_id if session_id is not None else self._default_session_id
        username = username if username is not None else self._default_user
        password = password if password is not None else self._default_password

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
        self._connections[connection_id] = conn
        logger.info("Connected — connection_id=%s", connection_id)
        return conn

    def get(self, connection_id: str) -> IxNetworkConnection:
        """Retrieve an active connection by ID."""
        conn = self._connections.get(connection_id)
        if conn is None:
            raise KeyError(
                f"No active connection with id '{connection_id}'. "
                "Use ixia_connect first to establish a connection."
            )
        return conn

    def disconnect(self, connection_id: str) -> None:
        """Remove a connection from the pool."""
        conn = self._connections.pop(connection_id, None)
        if conn is None:
            raise KeyError(
                f"No active connection with id '{connection_id}'. Nothing to disconnect."
            )
        logger.info("Disconnected connection_id=%s", connection_id)

    def disconnect_all(self) -> None:
        """Disconnect all active connections (used during shutdown)."""
        ids = list(self._connections.keys())
        for cid in ids:
            self._connections.pop(cid, None)
        logger.info("Disconnected all connections (%d)", len(ids))

    def list_connections(self) -> list[dict[str, Any]]:
        """Return summary of all active connections."""
        return [
            {
                "connection_id": c.connection_id,
                "host": c.host,
                "rest_port": c.rest_port,
                "session_id": c.session_id,
            }
            for c in self._connections.values()
        ]
