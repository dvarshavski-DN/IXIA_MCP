"""Protocol stack tools: add, remove, configure Ethernet/IPv4/IPv6/BGP."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ixia_mcp.models import (
    AddProtocolInput,
    RemoveProtocolInput,
    ConfigureEthernetInput,
    ConfigureIpv4Input,
    ConfigureIpv6Input,
    ConfigureBgpInput,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ixia_mcp.client import ConnectionManager


def _handle_error(e: Exception) -> str:
    return f"Error: {type(e).__name__}: {e}"


def _find_device_group(ix, topology_name: str, device_group_name: str):
    """Find a device group by topology + DG name."""
    topos = ix.Topology.find(Name=topology_name)
    if len(topos) == 0:
        return None, f"No topology named '{topology_name}' found."
    dgs = topos[0].DeviceGroup.find(Name=device_group_name)
    if len(dgs) == 0:
        return None, f"No device group named '{device_group_name}' in topology '{topology_name}'."
    return dgs[0], None


# Maps user-friendly protocol names to (parent_attr, child_attr) tuples.
# parent_attr is what we look for on the device group (or its child) to
# find the parent stack; child_attr is what we call .add() on.
_PROTOCOL_MAP = {
    "ethernet":  ("__dg__", "Ethernet"),
    "ipv4":      ("Ethernet", "Ipv4"),
    "ipv6":      ("Ethernet", "Ipv6"),
    "bgpv4":     ("Ipv4", "BgpIpv4Peer"),
    "bgpv6":     ("Ipv6", "BgpIpv6Peer"),
    "ospfv2":    ("Ipv4", "Ospfv2"),
    "ospfv3":    ("Ipv6", "Ospfv3"),
    "isis":      ("Ethernet", "IsisL3"),
    "ldp":       ("Ipv4", "LdpBasicRouter"),
    "igmp":      ("Ipv4", "Igmp"),
    "pim":       ("Ipv4", "Pim"),
}

# For removal, map protocol name -> the attribute on the device group
# that we traverse to find() and then remove().
_PROTOCOL_DG_ATTR = {
    "ethernet":  "Ethernet",
    "ipv4":      "Ipv4",
    "ipv6":      "Ipv6",
    "bgpv4":     "BgpIpv4Peer",
    "bgpv6":     "BgpIpv6Peer",
    "ospfv2":    "Ospfv2",
    "ospfv3":    "Ospfv3",
    "isis":      "IsisL3",
    "ldp":       "LdpBasicRouter",
    "igmp":      "Igmp",
    "pim":       "Pim",
}


def _resolve_parent(dg, parent_attr: str):
    """Walk the protocol stack to find the parent for a new protocol."""
    if parent_attr == "__dg__":
        return dg

    # Walk the stack: Ethernet lives on the DG, IPv4 lives on Ethernet, etc.
    stack_chain = {
        "Ethernet": [dg],
        "Ipv4": [dg, "Ethernet"],
        "Ipv6": [dg, "Ethernet"],
    }

    if parent_attr in stack_chain:
        obj = stack_chain[parent_attr][0]
        for attr in stack_chain[parent_attr][1:]:
            found = getattr(obj, attr).find()
            if len(found) == 0:
                return None
            obj = found[0]
        # Now obj is the device group or the Ethernet; get parent_attr from it
        if parent_attr == "Ethernet":
            found = obj.Ethernet.find() if hasattr(obj, "Ethernet") and obj is dg else [obj]
        else:
            found = getattr(obj, parent_attr).find()
        return found[0] if len(found) > 0 else None

    # For protocols directly on Ethernet / IPv4 / IPv6
    # Try to find the parent by walking: dg -> Ethernet -> parent_attr
    eth_stack = dg.Ethernet.find()
    if len(eth_stack) == 0:
        return None

    if parent_attr == "Ethernet":
        return eth_stack[0]

    parent_stack = getattr(eth_stack[0], parent_attr, None)
    if parent_stack is None:
        return None
    found = parent_stack.find()
    return found[0] if len(found) > 0 else None


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register protocol stack configuration tools."""

    @mcp.tool(
        name="ixia_add_protocol",
        annotations={
            "title": "Add Protocol Stack",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_add_protocol(params: AddProtocolInput) -> str:
        """Add a protocol stack to a device group.

        Protocols are stacked automatically on their parent:
        - Ethernet is added directly to the device group.
        - IPv4/IPv6 are added on top of Ethernet.
        - BGP, OSPF, ISIS, LDP, IGMP, PIM are added on top of their IP layer.

        The parent protocol must already exist (e.g. add Ethernet before IPv4).

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

                protocol = params.protocol.lower().strip()
                if protocol not in _PROTOCOL_MAP:
                    supported = ", ".join(sorted(_PROTOCOL_MAP.keys()))
                    return f"Unknown protocol '{params.protocol}'. Supported: {supported}"

                parent_attr, child_attr = _PROTOCOL_MAP[protocol]

                if parent_attr == "__dg__":
                    parent = dg
                else:
                    parent = _resolve_parent(dg, parent_attr)
                    if parent is None:
                        return (
                            f"Cannot add '{protocol}': parent protocol '{parent_attr}' "
                            f"not found on device group '{params.device_group_name}'. "
                            f"Add '{parent_attr.lower()}' first."
                        )

                getattr(parent, child_attr).add()
                return None

            result = await asyncio.to_thread(_run)

            if result:
                return f"Error: {result}"

            return (
                f"Protocol **{params.protocol}** added to device group "
                f"'{params.device_group_name}' in topology '{params.topology_name}'."
            )

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_remove_protocol",
        annotations={
            "title": "Remove Protocol Stack",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_remove_protocol(params: RemoveProtocolInput) -> str:
        """Remove a protocol stack from a device group.

        Removing a lower-layer protocol (e.g. Ethernet) will also remove
        all protocols stacked on top of it (IPv4, BGP, etc.).

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

                protocol = params.protocol.lower().strip()
                if protocol not in _PROTOCOL_DG_ATTR:
                    supported = ", ".join(sorted(_PROTOCOL_DG_ATTR.keys()))
                    return f"Unknown protocol '{params.protocol}'. Supported: {supported}"

                # Walk to the protocol: for L2 it's on the DG,
                # for L3+ we need to traverse through Ethernet
                attr_name = _PROTOCOL_DG_ATTR[protocol]

                # Try direct on DG first (Ethernet)
                if protocol == "ethernet":
                    found = dg.Ethernet.find()
                else:
                    # Walk through Ethernet
                    eth = dg.Ethernet.find()
                    if len(eth) == 0:
                        return f"No Ethernet stack found — protocol '{protocol}' cannot exist."
                    # For IPv4/IPv6 it's on Ethernet; for BGP etc. it's on IPv4/IPv6
                    found = None
                    # Try on Ethernet first
                    stack = getattr(eth[0], attr_name, None)
                    if stack is not None:
                        found = stack.find()
                    # If not found on Ethernet, try on IPv4/IPv6
                    if found is None or len(found) == 0:
                        for ip_layer in ("Ipv4", "Ipv6"):
                            ip_stack = getattr(eth[0], ip_layer, None)
                            if ip_stack is None:
                                continue
                            ip_found = ip_stack.find()
                            if len(ip_found) == 0:
                                continue
                            stack = getattr(ip_found[0], attr_name, None)
                            if stack is not None:
                                found = stack.find()
                                if found is not None and len(found) > 0:
                                    break

                if found is None or len(found) == 0:
                    return f"Protocol '{protocol}' not found on device group '{params.device_group_name}'."

                for item in found:
                    item.remove()
                return None

            result = await asyncio.to_thread(_run)

            if result:
                return f"Error: {result}"

            return (
                f"Protocol **{params.protocol}** removed from device group "
                f"'{params.device_group_name}' in topology '{params.topology_name}'."
            )

        except Exception as e:
            return _handle_error(e)

    # ------------------------------------------------------------------
    # Protocol configuration tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="ixia_configure_ethernet",
        annotations={
            "title": "Configure Ethernet",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_configure_ethernet(params: ConfigureEthernetInput) -> str:
        """Configure Ethernet properties on a device group.

        Sets MAC address, MTU, and VLAN parameters. Only provided fields
        are modified; omitted fields remain unchanged.

        Returns:
            str: Summary of configured properties or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                dg, err = _find_device_group(
                    conn.ixnetwork, params.topology_name, params.device_group_name
                )
                if err:
                    return err

                eth = dg.Ethernet.find()
                if len(eth) == 0:
                    return "No Ethernet stack found. Use ixia_add_protocol to add 'ethernet' first."
                eth = eth[0]

                changes = []

                if params.mac_address is not None:
                    step = params.mac_step or "00:00:00:00:00:01"
                    eth.Mac.Increment(start_value=params.mac_address, step_value=step)
                    changes.append(f"MAC: {params.mac_address} (step: {step})")

                if params.mtu is not None:
                    eth.Mtu.Single(params.mtu)
                    changes.append(f"MTU: {params.mtu}")

                if params.vlan_enabled is not None:
                    eth.EnableVlans.Single(params.vlan_enabled)
                    changes.append(f"VLAN enabled: {params.vlan_enabled}")

                if params.vlan_id is not None:
                    eth.EnableVlans.Single(True)
                    vlan = eth.Vlan.find()
                    if len(vlan) > 0:
                        step = params.vlan_id_step if params.vlan_id_step is not None else 0
                        vlan[0].VlanId.Increment(start_value=params.vlan_id, step_value=step)
                        changes.append(f"VLAN ID: {params.vlan_id} (step: {step})")

                if params.vlan_priority is not None:
                    vlan = eth.Vlan.find()
                    if len(vlan) > 0:
                        vlan[0].Priority.Single(params.vlan_priority)
                        changes.append(f"VLAN priority: {params.vlan_priority}")

                if not changes:
                    return "nothing"
                return changes

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                if result == "nothing":
                    return "No changes specified."
                return f"Error: {result}"

            return f"Ethernet configured: {'; '.join(result)}."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_configure_ipv4",
        annotations={
            "title": "Configure IPv4",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_configure_ipv4(params: ConfigureIpv4Input) -> str:
        """Configure IPv4 properties on a device group.

        Sets IP address, gateway, and prefix length. Only provided fields
        are modified; omitted fields remain unchanged.

        Returns:
            str: Summary of configured properties or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                dg, err = _find_device_group(
                    conn.ixnetwork, params.topology_name, params.device_group_name
                )
                if err:
                    return err

                eth = dg.Ethernet.find()
                if len(eth) == 0:
                    return "No Ethernet stack found. Add 'ethernet' first."
                ipv4 = eth[0].Ipv4.find()
                if len(ipv4) == 0:
                    return "No IPv4 stack found. Use ixia_add_protocol to add 'ipv4' first."
                ipv4 = ipv4[0]

                changes = []

                if params.address is not None:
                    step = params.address_step or "0.0.0.1"
                    ipv4.Address.Increment(start_value=params.address, step_value=step)
                    changes.append(f"address: {params.address} (step: {step})")

                if params.gateway is not None:
                    step = params.gateway_step or "0.0.0.0"
                    ipv4.GatewayIp.Increment(start_value=params.gateway, step_value=step)
                    changes.append(f"gateway: {params.gateway} (step: {step})")

                if params.prefix_length is not None:
                    ipv4.Prefix.Single(params.prefix_length)
                    changes.append(f"prefix: /{params.prefix_length}")

                if not changes:
                    return "nothing"
                return changes

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                if result == "nothing":
                    return "No changes specified."
                return f"Error: {result}"

            return f"IPv4 configured: {'; '.join(result)}."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_configure_ipv6",
        annotations={
            "title": "Configure IPv6",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_configure_ipv6(params: ConfigureIpv6Input) -> str:
        """Configure IPv6 properties on a device group.

        Sets IP address, gateway, and prefix length. Only provided fields
        are modified; omitted fields remain unchanged.

        Returns:
            str: Summary of configured properties or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                dg, err = _find_device_group(
                    conn.ixnetwork, params.topology_name, params.device_group_name
                )
                if err:
                    return err

                eth = dg.Ethernet.find()
                if len(eth) == 0:
                    return "No Ethernet stack found. Add 'ethernet' first."
                ipv6 = eth[0].Ipv6.find()
                if len(ipv6) == 0:
                    return "No IPv6 stack found. Use ixia_add_protocol to add 'ipv6' first."
                ipv6 = ipv6[0]

                changes = []

                if params.address is not None:
                    step = params.address_step or "::1"
                    ipv6.Address.Increment(start_value=params.address, step_value=step)
                    changes.append(f"address: {params.address} (step: {step})")

                if params.gateway is not None:
                    step = params.gateway_step or "::0"
                    ipv6.GatewayIp.Increment(start_value=params.gateway, step_value=step)
                    changes.append(f"gateway: {params.gateway} (step: {step})")

                if params.prefix_length is not None:
                    ipv6.Prefix.Single(params.prefix_length)
                    changes.append(f"prefix: /{params.prefix_length}")

                if not changes:
                    return "nothing"
                return changes

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                if result == "nothing":
                    return "No changes specified."
                return f"Error: {result}"

            return f"IPv6 configured: {'; '.join(result)}."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_configure_bgp",
        annotations={
            "title": "Configure BGP",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_configure_bgp(params: ConfigureBgpInput) -> str:
        """Configure BGP peer properties on a device group.

        Sets DUT IP, local AS, BGP type, hold timer, and update interval.
        Only provided fields are modified; omitted fields remain unchanged.

        Use ip_version='ipv4' for BgpIpv4Peer or 'ipv6' for BgpIpv6Peer.

        Returns:
            str: Summary of configured properties or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                dg, err = _find_device_group(
                    conn.ixnetwork, params.topology_name, params.device_group_name
                )
                if err:
                    return err

                eth = dg.Ethernet.find()
                if len(eth) == 0:
                    return "No Ethernet stack found."

                ip_ver = params.ip_version.lower().strip()
                if ip_ver == "ipv4":
                    ip_stack = eth[0].Ipv4.find()
                    if len(ip_stack) == 0:
                        return "No IPv4 stack found. Add 'ipv4' first."
                    bgp = ip_stack[0].BgpIpv4Peer.find()
                    bgp_label = "BgpIpv4Peer"
                elif ip_ver == "ipv6":
                    ip_stack = eth[0].Ipv6.find()
                    if len(ip_stack) == 0:
                        return "No IPv6 stack found. Add 'ipv6' first."
                    bgp = ip_stack[0].BgpIpv6Peer.find()
                    bgp_label = "BgpIpv6Peer"
                else:
                    return f"Invalid ip_version '{params.ip_version}'. Use 'ipv4' or 'ipv6'."

                if len(bgp) == 0:
                    return f"No {bgp_label} found. Use ixia_add_protocol to add 'bgpv4' or 'bgpv6' first."
                bgp = bgp[0]

                changes = []

                if params.dut_ip is not None:
                    step = params.dut_ip_step or ("0.0.0.0" if ip_ver == "ipv4" else "::0")
                    bgp.DutIp.Increment(start_value=params.dut_ip, step_value=step)
                    changes.append(f"DUT IP: {params.dut_ip} (step: {step})")

                if params.local_as is not None:
                    bgp.LocalAs2Bytes.Single(params.local_as)
                    changes.append(f"local AS: {params.local_as}")

                if params.bgp_type is not None:
                    bgp.Type.Single(params.bgp_type)
                    changes.append(f"type: {params.bgp_type}")

                if params.hold_timer is not None:
                    bgp.HoldTimer.Single(params.hold_timer)
                    changes.append(f"hold timer: {params.hold_timer}s")

                if params.update_interval is not None:
                    bgp.UpdateInterval.Single(params.update_interval)
                    changes.append(f"update interval: {params.update_interval}s")

                if not changes:
                    return "nothing"
                return changes

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                if result == "nothing":
                    return "No changes specified."
                return f"Error: {result}"

            return f"BGP configured: {'; '.join(result)}."

        except Exception as e:
            return _handle_error(e)
