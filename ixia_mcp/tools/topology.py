"""Topology & device group tools: list, details, create, update, delete."""

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
    CreateTopologyInput,
    DeleteTopologyInput,
    UpdateTopologyInput,
    CreateDeviceGroupInput,
    DeleteDeviceGroupInput,
    UpdateDeviceGroupInput,
    CreateNetworkGroupInput,
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


def _find_topo(ix, name: str):
    """Find a topology by name. Returns (topo, None) or (None, error_msg)."""
    topos = ix.Topology.find(Name=name)
    if len(topos) == 0:
        return None, f"No topology named '{name}' found. Use ixia_list_topologies to see available topologies."
    return topos[0], None


def _find_device_group(ix, topology_name: str, device_group_name: str):
    """Find a device group by topology + DG name.
    Returns (dg, None) or (None, error_msg).
    """
    topo, err = _find_topo(ix, topology_name)
    if err:
        return None, err
    dgs = topo.DeviceGroup.find(Name=device_group_name)
    if len(dgs) == 0:
        return None, (
            f"No device group named '{device_group_name}' in topology '{topology_name}'. "
            "Use ixia_get_topology_details to see available device groups."
        )
    return dgs[0], None


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register topology, device group, and protocol start/stop tools."""

    # ------------------------------------------------------------------
    # Read tools
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Protocol start/stop
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Topology create / update / delete
    # ------------------------------------------------------------------

    @mcp.tool(
        name="ixia_create_topology",
        annotations={
            "title": "Create Topology",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_create_topology(params: CreateTopologyInput) -> str:
        """Create a new topology and assign it to one or more virtual ports.

        The ports must already exist (use ixia_add_ports first).

        Returns:
            str: Confirmation with topology details or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork

                # Resolve port names to vport hrefs
                vport_hrefs = []
                for pname in params.port_names:
                    vports = ix.Vport.find(Name=pname)
                    if len(vports) == 0:
                        return f"No virtual port named '{pname}' found. Use ixia_add_ports or ixia_list_ports."
                    vport_hrefs.append(vports[0].href)

                topo = ix.Topology.add(Name=params.name, Ports=vport_hrefs)
                return {
                    "name": getattr(topo, "Name", params.name),
                    "ports": params.port_names,
                }

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            return (
                f"Topology **{result['name']}** created "
                f"with ports: {', '.join(result['ports'])}."
            )

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_delete_topology",
        annotations={
            "title": "Delete Topology",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_delete_topology(params: DeleteTopologyInput) -> str:
        """Delete a topology and all its device groups and protocol stacks.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                topo, err = _find_topo(conn.ixnetwork, params.topology_name)
                if err:
                    return err
                topo.remove()
                return None

            result = await asyncio.to_thread(_run)

            if result:
                return f"Error: {result}"
            return f"Topology '{params.topology_name}' deleted."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_update_topology",
        annotations={
            "title": "Update Topology",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_update_topology(params: UpdateTopologyInput) -> str:
        """Update a topology's name or port assignments.

        Returns:
            str: Confirmation with changes or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork
                topo, err = _find_topo(ix, params.topology_name)
                if err:
                    return err

                changes = []
                if params.new_name is not None:
                    topo.Name = params.new_name
                    changes.append(f"name -> '{params.new_name}'")

                if params.port_names is not None:
                    vport_hrefs = []
                    for pname in params.port_names:
                        vports = ix.Vport.find(Name=pname)
                        if len(vports) == 0:
                            return f"No virtual port named '{pname}' found."
                        vport_hrefs.append(vports[0].href)
                    topo.Ports = vport_hrefs
                    changes.append(f"ports -> {params.port_names}")

                if not changes:
                    return "nothing"
                return changes

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                if result == "nothing":
                    return "No changes specified. Provide new_name or port_names."
                return f"Error: {result}"

            return f"Topology '{params.topology_name}' updated: {'; '.join(result)}."

        except Exception as e:
            return _handle_error(e)

    # ------------------------------------------------------------------
    # Device group create / update / delete
    # ------------------------------------------------------------------

    @mcp.tool(
        name="ixia_create_device_group",
        annotations={
            "title": "Create Device Group",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_create_device_group(params: CreateDeviceGroupInput) -> str:
        """Create a new device group inside a topology.

        A device group represents a set of emulated devices. After creation,
        use ixia_add_protocol to add protocol stacks (Ethernet, IPv4, BGP, etc.).

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                topo, err = _find_topo(conn.ixnetwork, params.topology_name)
                if err:
                    return err
                dg = topo.DeviceGroup.add(Name=params.name, Multiplier=params.multiplier)
                return {
                    "name": getattr(dg, "Name", params.name),
                    "multiplier": getattr(dg, "Multiplier", params.multiplier),
                }

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            return (
                f"Device group **{result['name']}** created in topology "
                f"'{params.topology_name}' with multiplier {result['multiplier']}."
            )

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_delete_device_group",
        annotations={
            "title": "Delete Device Group",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_delete_device_group(params: DeleteDeviceGroupInput) -> str:
        """Delete a device group and all its protocol stacks.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                dg, err = _find_device_group(
                    conn.ixnetwork, params.topology_name, params.device_group_name
                )
                if err:
                    return err
                dg.remove()
                return None

            result = await asyncio.to_thread(_run)

            if result:
                return f"Error: {result}"
            return (
                f"Device group '{params.device_group_name}' deleted "
                f"from topology '{params.topology_name}'."
            )

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_update_device_group",
        annotations={
            "title": "Update Device Group",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_update_device_group(params: UpdateDeviceGroupInput) -> str:
        """Update a device group's name, multiplier, or enabled state.

        Returns:
            str: Confirmation with changes or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                dg, err = _find_device_group(
                    conn.ixnetwork, params.topology_name, params.device_group_name
                )
                if err:
                    return err

                changes = []
                if params.new_name is not None:
                    dg.Name = params.new_name
                    changes.append(f"name -> '{params.new_name}'")
                if params.multiplier is not None:
                    dg.Multiplier = params.multiplier
                    changes.append(f"multiplier -> {params.multiplier}")
                if params.enabled is not None:
                    dg.Enabled = params.enabled
                    changes.append(f"enabled -> {params.enabled}")

                if not changes:
                    return "nothing"
                return changes

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                if result == "nothing":
                    return "No changes specified. Provide new_name, multiplier, or enabled."
                return f"Error: {result}"

            return (
                f"Device group '{params.device_group_name}' updated: "
                f"{'; '.join(result)}."
            )

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_create_network_group",
        annotations={
            "title": "Create Network Group",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_create_network_group(params: CreateNetworkGroupInput) -> str:
        """Create a network group under a device group for route advertisement.

        Network groups are used to advertise route prefixes (e.g. via BGP or OSPF).
        Optionally configure IPv4 prefix pool parameters at creation time.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                dg, err = _find_device_group(
                    conn.ixnetwork, params.topology_name, params.device_group_name
                )
                if err:
                    return err

                ng = dg.NetworkGroup.add(Name=params.name, Multiplier=params.multiplier)

                pool_info = None
                if params.ipv4_network_address:
                    pool = ng.Ipv4PrefixPools.add(NumberOfAddresses=1)
                    pool.NetworkAddress.Increment(
                        start_value=params.ipv4_network_address,
                        step_value=params.ipv4_prefix_step or "0.1.0.0",
                    )
                    if params.ipv4_prefix_length:
                        pool.PrefixLength.Single(params.ipv4_prefix_length)
                    pool_info = {
                        "network_address": params.ipv4_network_address,
                        "prefix_length": params.ipv4_prefix_length or 24,
                    }

                return {
                    "name": getattr(ng, "Name", params.name),
                    "multiplier": params.multiplier,
                    "ipv4_pool": pool_info,
                }

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            lines = [
                f"Network group **{result['name']}** created "
                f"(multiplier: {result['multiplier']})."
            ]
            if result["ipv4_pool"]:
                p = result["ipv4_pool"]
                lines.append(
                    f"IPv4 prefix pool: {p['network_address']}/{p['prefix_length']}"
                )
            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)
