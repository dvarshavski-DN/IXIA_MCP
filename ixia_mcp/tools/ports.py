"""Port management tools: list, status, add, release, remove."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from ixia_mcp.models import (
    ListPortsInput,
    GetPortStatusInput,
    AddPortsInput,
    ReleasePortsInput,
    RemovePortsInput,
    ResponseFormat,
)

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

    # ------------------------------------------------------------------
    # Read tools
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Configuration tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="ixia_add_ports",
        annotations={
            "title": "Add and Assign Ports",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_add_ports(params: AddPortsInput) -> str:
        """Add virtual ports and assign them to chassis hardware ports.

        Creates virtual ports in IxNetwork and maps them to physical
        chassis/card/port locations. Ports become available for use in
        topologies after assignment.

        Returns:
            str: Summary of added ports or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork
                count = len(params.card_port_pairs)
                names = params.port_names or [f"Port {i + 1}" for i in range(count)]
                if len(names) != count:
                    return f"port_names length ({len(names)}) must match card_port_pairs length ({count})."

                # Create virtual ports
                vports = []
                for name in names:
                    vports.append(ix.Vport.add(Name=name))

                # Build chassis port map and vport href list
                port_map = []
                vport_hrefs = []
                for i, (card, port) in enumerate(params.card_port_pairs):
                    port_map.append({
                        "Arg1": params.chassis_ip,
                        "Arg2": int(card),
                        "Arg3": int(port),
                    })
                    vport_hrefs.append(vports[i].href)

                # Assign physical ports to virtual ports
                ix.AssignPorts(port_map, [], vport_hrefs, params.force_ownership)

                return [
                    {
                        "name": names[i],
                        "location": f"{params.chassis_ip}/{card}/{port}",
                    }
                    for i, (card, port) in enumerate(params.card_port_pairs)
                ]

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            lines = [f"Added and assigned **{len(result)}** port(s):", ""]
            for p in result:
                lines.append(f"- **{p['name']}** -> `{p['location']}`")
            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_release_ports",
        annotations={
            "title": "Release Hardware Ports",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_release_ports(params: ReleasePortsInput) -> str:
        """Release hardware port assignments from virtual ports.

        The virtual ports remain in the config but are no longer mapped
        to physical chassis ports.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork
                if params.port_names:
                    released = []
                    for name in params.port_names:
                        vports = ix.Vport.find(Name=name)
                        if len(vports) == 0:
                            return f"No port named '{name}' found."
                        for v in vports:
                            v.ReleasePort()
                            released.append(name)
                    return released
                else:
                    vports = ix.Vport.find()
                    names = [getattr(v, "Name", "") for v in vports]
                    for v in vports:
                        v.ReleasePort()
                    return names

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            if not result:
                return "No ports to release."
            return f"Released {len(result)} port(s): {', '.join(result)}."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_remove_ports",
        annotations={
            "title": "Remove Virtual Ports",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_remove_ports(params: RemovePortsInput) -> str:
        """Remove virtual ports from the IxNetwork configuration.

        This also removes any topology or traffic references that depend
        on these ports. Use with caution.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork
                if params.port_names:
                    removed = []
                    for name in params.port_names:
                        vports = ix.Vport.find(Name=name)
                        if len(vports) == 0:
                            return f"No port named '{name}' found."
                        for v in vports:
                            v.remove()
                            removed.append(name)
                    return removed
                else:
                    vports = ix.Vport.find()
                    names = [getattr(v, "Name", "") for v in vports]
                    for v in vports:
                        v.remove()
                    return names

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            if not result:
                return "No ports to remove."
            return f"Removed {len(result)} port(s): {', '.join(result)}."

        except Exception as e:
            return _handle_error(e)
