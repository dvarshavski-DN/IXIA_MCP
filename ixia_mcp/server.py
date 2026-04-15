"""IXIA MCP Server — main entry point.

Initializes FastMCP with configurable transport, manages the
IxNetwork connection pool via lifespan, and registers all tools.
"""

from __future__ import annotations

import argparse
import atexit
import logging
import signal
import sys

from mcp.server.fastmcp import FastMCP

from ixia_mcp.client import ConnectionManager
from ixia_mcp.tools import session, ports, topology, traffic, statistics

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
    p.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio",
                   help="MCP transport (default: stdio)")
    p.add_argument("--server-port", type=int, default=8080,
                   help="HTTP listen port when using streamable-http transport (default: 8080)")

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
    traffic.register(mcp, manager)
    statistics.register(mcp, manager)

    return mcp, manager


def main() -> None:
    """Run the MCP server."""
    args = _parse_args()
    mcp, _ = _build_server(args)

    if args.transport == "streamable-http":
        logger.info("Starting IXIA MCP server on http://0.0.0.0:%d/mcp", args.server_port)
    else:
        logger.info("Starting IXIA MCP server (stdio transport)")

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
