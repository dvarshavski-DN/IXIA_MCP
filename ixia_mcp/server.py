"""IXIA MCP Server — main entry point.

Initializes FastMCP with configurable transport, manages the
IxNetwork connection pool via lifespan, and registers all tools.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import logging
import os
import signal
import sys

from starlette.types import ASGIApp, Receive, Scope, Send

from mcp.server.fastmcp import FastMCP

from ixia_mcp.client import ConnectionManager
from ixia_mcp.request_context import RequestHeaders, request_headers_var
from ixia_mcp.tools import session, ports, topology, protocols, traffic, statistics, config


class _IxiaHeaderMiddleware:
    """ASGI middleware that extracts X-IXIA-* headers into a contextvars token.

    Cursor (or any MCP client) sends these headers on every HTTP request,
    allowing per-user IxNetwork connection defaults.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            raw_headers = dict(scope.get("headers", []))
            rh = RequestHeaders(
                ixia_host=self._str(raw_headers, b"x-ixia-host"),
                ixia_port=self._int(raw_headers, b"x-ixia-port"),
                ixia_session_id=self._int(raw_headers, b"x-ixia-session-id"),
                ixia_user=self._str(raw_headers, b"x-ixia-user"),
                ixia_password=self._str(raw_headers, b"x-ixia-password"),
            )
            token = request_headers_var.set(rh)
            try:
                await self.app(scope, receive, send)
            finally:
                request_headers_var.reset(token)
        else:
            await self.app(scope, receive, send)

    @staticmethod
    def _str(headers: dict[bytes, bytes], key: bytes) -> str | None:
        val = headers.get(key)
        return val.decode() if val is not None else None

    @staticmethod
    def _int(headers: dict[bytes, bytes], key: bytes) -> int | None:
        val = headers.get(key)
        if val is None:
            return None
        try:
            return int(val.decode())
        except ValueError:
            return None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ixia_mcp")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ixia-mcp",
        description="MCP server for Keysight IxNetwork",
    )
    p.add_argument("--transport", choices=["stdio", "streamable-http"],
                   default=os.environ.get("MCP_TRANSPORT", "stdio"),
                   help="MCP transport (env: MCP_TRANSPORT, default: stdio)")
    p.add_argument("--server-port", type=int,
                   default=int(os.environ.get("PORT", "8080")),
                   help="HTTP listen port when using streamable-http transport (env: PORT, default: 8080)")

    g = p.add_argument_group("IxNetwork connection defaults",
                             "Pre-configure so agents don't need to pass these to ixia_connect")
    g.add_argument("--ixia-host", default=None,
                   help="IxNetwork API server IP or hostname")
    g.add_argument("--ixia-port", type=int, default=None,
                   help="IxNetwork REST API port (default: 11009)")
    g.add_argument("--ixia-session-id", type=int, default=None,
                   help="IxNetwork session ID to attach to")
    g.add_argument("--ixia-user", default=None,
                   help="IxNetwork username")
    g.add_argument("--ixia-password", default=None,
                   help="IxNetwork password")

    return p.parse_args(argv)


def _build_server(args: argparse.Namespace) -> tuple[FastMCP, ConnectionManager]:
    manager = ConnectionManager(
        default_host=args.ixia_host,
        default_port=args.ixia_port,
        default_session_id=args.ixia_session_id,
        default_user=args.ixia_user,
        default_password=args.ixia_password,
    )

    def _shutdown_handler(*_args) -> None:
        logger.info("Shutting down — disconnecting all IxNetwork sessions")
        manager.disconnect_all()
        sys.exit(0)

    atexit.register(manager.disconnect_all)
    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    mcp_kwargs: dict = {"name": "ixia_mcp"}
    if args.transport == "streamable-http":
        mcp_kwargs.update(host="0.0.0.0", port=args.server_port, stateless_http=True)

    mcp = FastMCP(**mcp_kwargs)

    # Register all tool modules
    session.register(mcp, manager)
    ports.register(mcp, manager)
    topology.register(mcp, manager)
    protocols.register(mcp, manager)
    traffic.register(mcp, manager)
    statistics.register(mcp, manager)
    config.register(mcp, manager)

    return mcp, manager


def main() -> None:
    """Run the MCP server."""
    args = _parse_args()
    mcp, _ = _build_server(args)

    if args.transport == "streamable-http":
        logger.info("Starting IXIA MCP server on http://0.0.0.0:%d/mcp", args.server_port)
        app = mcp.streamable_http_app()
        app = _IxiaHeaderMiddleware(app)

        async def _run_with_reaper() -> None:
            async def _reap_stale() -> None:
                while True:
                    await asyncio.sleep(300)
                    manager.disconnect_stale()

            reaper_task = asyncio.create_task(_reap_stale())

            import uvicorn
            config = uvicorn.Config(app, host="0.0.0.0", port=args.server_port)
            server = uvicorn.Server(config)
            try:
                await server.serve()
            finally:
                reaper_task.cancel()

        asyncio.run(_run_with_reaper())
    else:
        logger.info("Starting IXIA MCP server (stdio transport)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
