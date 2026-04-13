"""IXIA MCP Server — main entry point.

Initializes FastMCP with Streamable HTTP transport, manages the
IxNetwork connection pool via lifespan, and registers all tools.
"""

from __future__ import annotations

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

_manager = ConnectionManager()


def _shutdown_handler(*_args) -> None:
    logger.info("Shutting down — disconnecting all IxNetwork sessions")
    _manager.disconnect_all()
    sys.exit(0)


atexit.register(_manager.disconnect_all)
signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)

mcp = FastMCP(
    "ixia_mcp",
    host="0.0.0.0",
    port=8080,
    stateless_http=True,
)

# Register all tool modules
session.register(mcp, _manager)
ports.register(mcp, _manager)
topology.register(mcp, _manager)
traffic.register(mcp, _manager)
statistics.register(mcp, _manager)


def main() -> None:
    """Run the MCP server with Streamable HTTP transport on port 8080."""
    logger.info("Starting IXIA MCP server on http://0.0.0.0:8080/mcp")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
