"""Topology & protocol tools: list, details, status, start, stop."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from ixia_mcp.models import (
    ListTopologiesInput,
    GetTopologyDetailsInput,
    ProtocolStatusInput,
    StartProtocolsInput,
    StopProtocolsInput,
    ResponseFormat,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ixia_mcp.client import ConnectionManager


def _handle_error(e: Exception) -> str:
    return f"Error: {type(e).__name__}: {e}"


def _topo_summary(topo) -> dict[str, Any]:
    """Extract summary info from a Topology object."""
    device_groups = topo.DeviceGroup.find()
    return {
        "name": getattr(topo, "Name", ""),
        "status": getattr(topo, "Status", "unknown"),
        "ports": getattr(topo, "Ports", []),
        "device_group_count": len(device_groups),
    }


def _device_group_detail(dg) -> dict[str, Any]:
    """Extract detail from a DeviceGroup."""
    result: dict[str, Any] = {
        "name": getattr(dg, "Name", ""),
        "status": getattr(dg, "Status", "unknown"),
        "multiplier": getattr(dg, "Multiplier", 1),
        "enabled": getattr(dg, "Enabled", True),
    }

    protocols: list[str] = []
    for attr in ("Ethernet", "Ipv4", "Ipv6", "BgpIpv4Peer", "BgpIpv6Peer",
                 "Ospfv2", "Ospfv3", "IsisL3", "Ldp", "Igmp", "Pim"):
        try:
            stack = getattr(dg, attr, None)
            if stack is not None:
                found = stack.find()
                if len(found) > 0:
                    protocols.append(attr)
        except Exception:
            pass
    result["protocols"] = protocols
    return result


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register topology and protocol tools."""

    @mcp.tool(
        name="ixia_list_topologies",
        annotations={
            "title": "List IxNetwork Topologies",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_list_topologies(params: ListTopologiesInput) -> str:
        """List all topologies in the IxNetwork session.

        Shows topology name, status, assigned ports, and device group count.

        Returns:
            str: Topology listing in markdown table or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                topos = conn.ixnetwork.Topology.find()
                return [_topo_summary(t) for t in topos]

            summaries = await asyncio.to_thread(_fetch)

            if not summaries:
                return "No topologies configured in this session."

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(summaries), "topologies": summaries}, indent=2)

            lines = [
                "# Topologies",
                "",
                f"**{len(summaries)}** topology(ies) configured.",
                "",
                "| Name | Status | Ports | Device Groups |",
                "|------|--------|-------|---------------|",
            ]
            for s in summaries:
                ports_str = ", ".join(s["ports"]) if s["ports"] else "—"
                lines.append(f"| {s['name']} | {s['status']} | {ports_str} | {s['device_group_count']} |")

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_get_topology_details",
        annotations={
            "title": "Get Topology Details",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_get_topology_details(params: GetTopologyDetailsInput) -> str:
        """Get detailed information about topologies including device groups and protocols.

        If topology_name is provided, returns details for that topology only.

        Returns:
            str: Topology details with device groups and protocol stacks.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                if params.topology_name:
                    topos = conn.ixnetwork.Topology.find(Name=params.topology_name)
                    if len(topos) == 0:
                        return None
                else:
                    topos = conn.ixnetwork.Topology.find()

                details = []
                for topo in topos:
                    dgs = topo.DeviceGroup.find()
                    details.append({
                        **_topo_summary(topo),
                        "device_groups": [_device_group_detail(dg) for dg in dgs],
                    })
                return details

            all_details = await asyncio.to_thread(_fetch)

            if all_details is None:
                return (
                    f"Error: No topology named '{params.topology_name}' found. "
                    "Use ixia_list_topologies to see available topologies."
                )

            if not all_details:
                return "No topologies configured in this session."

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(all_details), "topologies": all_details}, indent=2)

            lines = ["# Topology Details", ""]
            for d in all_details:
                lines.extend([
                    f"## {d['name']}",
                    f"- **Status**: {d['status']}",
                    f"- **Ports**: {', '.join(d['ports']) if d['ports'] else '—'}",
                    f"- **Device Groups**: {d['device_group_count']}",
                    "",
                ])
                for dg in d["device_groups"]:
                    lines.extend([
                        f"### Device Group: {dg['name']}",
                        f"- **Status**: {dg['status']}",
                        f"- **Multiplier**: {dg['multiplier']}",
                        f"- **Enabled**: {dg['enabled']}",
                        f"- **Protocols**: {', '.join(dg['protocols']) if dg['protocols'] else 'None'}",
                        "",
                    ])

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_get_protocol_status",
        annotations={
            "title": "Get Protocol Session Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_get_protocol_status(params: ProtocolStatusInput) -> str:
        """Get the status of all protocol sessions across all topologies.

        Shows per-topology, per-device-group protocol session counts
        (up, down, not started).

        Returns:
            str: Protocol status summary in markdown or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork
                topos = ix.Topology.find()
                topo_data = []
                for topo in topos:
                    topo_info: dict[str, Any] = {
                        "name": getattr(topo, "Name", ""),
                        "status": getattr(topo, "Status", "unknown"),
                        "device_groups": [],
                    }
                    for dg in topo.DeviceGroup.find():
                        topo_info["device_groups"].append({
                            "name": getattr(dg, "Name", ""),
                            "status": getattr(dg, "Status", "unknown"),
                        })
                    topo_data.append(topo_info)
                return topo_data

            topo_data = await asyncio.to_thread(_fetch)

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"topologies": topo_data}, indent=2)

            lines = ["# Protocol Status", ""]
            for t in topo_data:
                lines.append(f"## {t['name']} — {t['status']}")
                if not t["device_groups"]:
                    lines.append("  No device groups.")
                for dg in t["device_groups"]:
                    lines.append(f"- **{dg['name']}**: {dg['status']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_start_protocols",
        annotations={
            "title": "Start Protocols",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_start_protocols(params: StartProtocolsInput) -> str:
        """Start all protocols, or protocols for a specific topology.

        If topology_name is provided, starts only that topology's protocols.
        Otherwise starts all protocols globally.

        Returns:
            str: Confirmation message or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                if params.topology_name:
                    topos = conn.ixnetwork.Topology.find(Name=params.topology_name)
                    if len(topos) == 0:
                        return None
                    for topo in topos:
                        for dg in topo.DeviceGroup.find():
                            dg.Start()
                    return params.topology_name
                else:
                    conn.ixnetwork.StartAllProtocols(Arg1="sync")
                    return "__all__"

            result = await asyncio.to_thread(_run)

            if result is None:
                return (
                    f"Error: No topology named '{params.topology_name}' found. "
                    "Use ixia_list_topologies to see available topologies."
                )
            if result == "__all__":
                return "Started all protocols."
            return f"Started protocols for topology '{result}'."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_stop_protocols",
        annotations={
            "title": "Stop Protocols",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_stop_protocols(params: StopProtocolsInput) -> str:
        """Stop all protocols, or protocols for a specific topology.

        If topology_name is provided, stops only that topology's protocols.
        Otherwise stops all protocols globally.

        Returns:
            str: Confirmation message or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                if params.topology_name:
                    topos = conn.ixnetwork.Topology.find(Name=params.topology_name)
                    if len(topos) == 0:
                        return None
                    for topo in topos:
                        for dg in topo.DeviceGroup.find():
                            dg.Stop()
                    return params.topology_name
                else:
                    conn.ixnetwork.StopAllProtocols(Arg1="sync")
                    return "__all__"

            result = await asyncio.to_thread(_run)

            if result is None:
                return (
                    f"Error: No topology named '{params.topology_name}' found. "
                    "Use ixia_list_topologies to see available topologies."
                )
            if result == "__all__":
                return "Stopped all protocols."
            return f"Stopped protocols for topology '{result}'."

        except Exception as e:
            return _handle_error(e)
