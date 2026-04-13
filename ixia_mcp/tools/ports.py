"""Port management tools: list_ports, get_port_status."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from ixia_mcp.models import ListPortsInput, GetPortStatusInput, ResponseFormat

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ixia_mcp.client import ConnectionManager


def _handle_error(e: Exception) -> str:
    return f"Error: {type(e).__name__}: {e}"


def _vport_to_dict(vport) -> dict:
    """Extract useful fields from a Vport object."""
    return {
        "name": getattr(vport, "Name", ""),
        "state": getattr(vport, "State", "unknown"),
        "type": getattr(vport, "Type", ""),
        "connection_state": getattr(vport, "ConnectionState", ""),
        "assigned_to": getattr(vport, "AssignedTo", ""),
        "is_connected": getattr(vport, "IsConnected", False),
    }


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register port tools on the MCP server."""

    @mcp.tool(
        name="ixia_list_ports",
        annotations={
            "title": "List IxNetwork Virtual Ports",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_list_ports(params: ListPortsInput) -> str:
        """List all virtual ports (Vports) configured in the IxNetwork session.

        Shows port name, state, connection status, and assigned hardware.

        Returns:
            str: Port listing in markdown table or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                vports = conn.ixnetwork.Vport.find()
                return [_vport_to_dict(v) for v in vports]

            ports = await asyncio.to_thread(_fetch)

            if not ports:
                return "No virtual ports configured in this session."

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(ports), "ports": ports}, indent=2)

            lines = [
                "# Virtual Ports",
                "",
                f"**{len(ports)}** port(s) configured.",
                "",
                "| Name | State | Connected | Assigned To |",
                "|------|-------|-----------|-------------|",
            ]
            for p in ports:
                connected = "Yes" if p["is_connected"] else "No"
                assigned = p["assigned_to"] or "—"
                lines.append(f"| {p['name']} | {p['state']} | {connected} | {assigned} |")

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_get_port_status",
        annotations={
            "title": "Get Port Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_get_port_status(params: GetPortStatusInput) -> str:
        """Get detailed status of virtual ports.

        If port_name is provided, returns status for that specific port.
        Otherwise returns status for all ports.

        Returns:
            str: Detailed port status in markdown or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                if params.port_name:
                    vports = conn.ixnetwork.Vport.find(Name=params.port_name)
                    if len(vports) == 0:
                        return None
                else:
                    vports = conn.ixnetwork.Vport.find()
                return [_vport_to_dict(v) for v in vports]

            ports = await asyncio.to_thread(_fetch)

            if ports is None:
                return f"Error: No port named '{params.port_name}' found. Use ixia_list_ports to see available ports."

            if not ports:
                return "No virtual ports configured in this session."

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(ports), "ports": ports}, indent=2)

            lines = ["# Port Status Detail", ""]
            for p in ports:
                lines.extend([
                    f"## {p['name']}",
                    f"- **State**: {p['state']}",
                    f"- **Type**: {p['type']}",
                    f"- **Connected**: {'Yes' if p['is_connected'] else 'No'}",
                    f"- **Connection State**: {p['connection_state']}",
                    f"- **Assigned To**: {p['assigned_to'] or '—'}",
                    "",
                ])

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)
