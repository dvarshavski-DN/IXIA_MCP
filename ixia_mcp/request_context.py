"""Per-request context for HTTP headers passed by MCP clients.

Starlette middleware populates these values from X-IXIA-* headers on each
incoming request so that tool handlers (and ConnectionManager) can read
per-user IxNetwork defaults without explicit parameters.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass


@dataclass
class RequestHeaders:
    """IxNetwork connection defaults extracted from HTTP request headers."""

    ixia_host: str | None = None
    ixia_port: int | None = None
    ixia_session_id: int | None = None
    ixia_user: str | None = None
    ixia_password: str | None = None


request_headers_var: contextvars.ContextVar[RequestHeaders] = contextvars.ContextVar(
    "request_headers", default=RequestHeaders()
)
