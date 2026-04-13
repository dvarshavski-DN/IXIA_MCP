"""Session management tools: connect, disconnect, get_session_info."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from ixia_mcp.models import ConnectInput, ConnectionIdInput, SessionInfoInput, ResponseFormat

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ixia_mcp.client import ConnectionManager


def _handle_error(e: Exception) -> str:
    return f"Error: {type(e).__name__}: {e}"


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register session tools on the MCP server."""

    @mcp.tool(
        name="ixia_connect",
        annotations={
            "title": "Connect to IxNetwork",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_connect(params: ConnectInput) -> str:
        """Connect to an existing IxNetwork session on a Windows GUI or API server.

        Returns a connection_id that must be passed to all subsequent tools.
        Connection parameters fall back to environment variables if not provided.

        Returns:
            str: JSON with connection_id, host, rest_port, session_id on success,
                 or an error message.
        """
        try:
            conn = await asyncio.to_thread(
                manager.connect,
                host=params.host,
                rest_port=params.rest_port,
                session_id=params.session_id,
                username=params.username,
                password=params.password,
            )
            return json.dumps(
                {
                    "status": "connected",
                    "connection_id": conn.connection_id,
                    "host": conn.host,
                    "rest_port": conn.rest_port,
                    "session_id": conn.session_id,
                },
                indent=2,
            )
        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_disconnect",
        annotations={
            "title": "Disconnect from IxNetwork",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_disconnect(params: ConnectionIdInput) -> str:
        """Disconnect from an IxNetwork session and release the connection.

        Returns:
            str: Confirmation message or error.
        """
        try:
            manager.disconnect(params.connection_id)
            return f"Disconnected from connection {params.connection_id}."
        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_get_session_info",
        annotations={
            "title": "Get IxNetwork Session Info",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_get_session_info(params: SessionInfoInput) -> str:
        """Get details about the connected IxNetwork session.

        Returns platform, build number, virtual port count, topology count,
        and traffic item count.

        Returns:
            str: Session information in markdown or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork
                return {
                    "connection_id": conn.connection_id,
                    "host": conn.host,
                    "session_id": conn.session_id,
                    "build_number": getattr(ix, "BuildNumber", "N/A"),
                    "virtual_ports": len(ix.Vport.find()),
                    "topologies": len(ix.Topology.find()),
                    "traffic_items": len(ix.Traffic.TrafficItem.find()),
                }

            info = await asyncio.to_thread(_fetch)

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(info, indent=2)

            lines = [
                "# IxNetwork Session Info",
                "",
                f"- **Connection ID**: {info['connection_id']}",
                f"- **Host**: {info['host']}",
                f"- **Session ID**: {info['session_id']}",
                f"- **Build**: {info['build_number']}",
                f"- **Virtual Ports**: {info['virtual_ports']}",
                f"- **Topologies**: {info['topologies']}",
                f"- **Traffic Items**: {info['traffic_items']}",
            ]
            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)
