"""Shared helpers used across all tool modules."""

from __future__ import annotations


def _handle_error(e: Exception) -> str:
    """Format an exception into a user-facing error string."""
    return f"Error: {type(e).__name__}: {e}"


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
