"""Traffic tools: list, details, generate, start, stop, create, delete, configure, tracking."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from ixia_mcp.models import (
    ListTrafficItemsInput,
    GetTrafficItemDetailsInput,
    GenerateTrafficInput,
    StartTrafficInput,
    StopTrafficInput,
    CreateTrafficItemInput,
    DeleteTrafficItemInput,
    ConfigureTrafficItemInput,
    AddTrackingInput,
    ResponseFormat,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ixia_mcp.client import ConnectionManager


def _handle_error(e: Exception) -> str:
    return f"Error: {type(e).__name__}: {e}"


def _traffic_item_summary(ti) -> dict[str, Any]:
    """Extract summary from a TrafficItem object."""
    return {
        "name": getattr(ti, "Name", ""),
        "state": getattr(ti, "State", "unknown"),
        "enabled": getattr(ti, "Enabled", False),
        "traffic_type": getattr(ti, "TrafficType", ""),
        "suspend": getattr(ti, "Suspend", False),
    }


def _traffic_item_detail(ti) -> dict[str, Any]:
    """Extract detailed info from a TrafficItem (deep REST traversal)."""
    summary = _traffic_item_summary(ti)

    config_elements = []
    for ce in ti.ConfigElement.find():
        ce_info: dict[str, Any] = {
            "endpoint_set_id": getattr(ce, "EndpointSetId", ""),
        }
        fr = ce.FrameRate
        ce_info["frame_rate"] = {
            "type": getattr(fr, "Type", ""),
            "rate": getattr(fr, "Rate", ""),
        }
        tc = ce.TransmissionControl
        ce_info["transmission_control"] = {
            "type": getattr(tc, "Type", ""),
            "frame_count": getattr(tc, "FrameCount", 0),
            "duration": getattr(tc, "Duration", 0),
        }
        fs = ce.FrameSize
        ce_info["frame_size"] = {
            "type": getattr(fs, "Type", ""),
            "fixed_size": getattr(fs, "FixedSize", 0),
        }
        config_elements.append(ce_info)

    summary["config_elements"] = config_elements
    return summary


def _find_traffic_item(traffic, *, name: str | None = None, index: int | None = None):
    """Find a single TrafficItem by name or 1-based index.

    Uses client-side matching because the REST API's server-side Name
    filter chokes on special characters (parentheses, ==>).
    Returns (traffic_item, display_label) or (None, error_message).
    """
    items = traffic.TrafficItem.find()
    if name:
        for ti in items:
            if getattr(ti, "Name", "") == name:
                return ti, name
        return None, f"No traffic item named '{name}' found."
    if index is not None:
        if index < 1 or index > len(items):
            return None, f"Traffic item index {index} out of range (1-{len(items)})."
        ti = items[index - 1]
        return ti, f"#{index} ({getattr(ti, 'Name', '')})"
    return None, "No traffic_item_name or traffic_item_index provided."


def _find_endpoint_href(ix, name: str) -> str | None:
    """Resolve a topology or device group name to its href for traffic endpoints."""
    # Try topology first
    topos = ix.Topology.find(Name=name)
    if len(topos) > 0:
        return topos[0].href

    # Try device group inside any topology
    for topo in ix.Topology.find():
        dgs = topo.DeviceGroup.find(Name=name)
        if len(dgs) > 0:
            return dgs[0].href

    return None


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register traffic tools."""

    # ------------------------------------------------------------------
    # Read tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="ixia_list_traffic_items",
        annotations={
            "title": "List Traffic Items",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_list_traffic_items(params: ListTrafficItemsInput) -> str:
        """List all traffic items in the IxNetwork session.

        Shows name, state, type, and whether enabled.

        Returns:
            str: Traffic items listing in markdown table or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                items = conn.ixnetwork.Traffic.TrafficItem.find()
                return [_traffic_item_summary(ti) for ti in items]

            summaries = await asyncio.to_thread(_fetch)

            if not summaries:
                return "No traffic items configured in this session."

            if params.response_format == ResponseFormat.JSON:
                for i, s in enumerate(summaries, 1):
                    s["index"] = i
                return json.dumps({"count": len(summaries), "traffic_items": summaries}, indent=2)

            lines = [
                "# Traffic Items",
                "",
                f"**{len(summaries)}** traffic item(s) configured.",
                "",
                "| # | Name | State | Type | Enabled | Suspended |",
                "|---|------|-------|------|---------|-----------|",
            ]
            for i, s in enumerate(summaries, 1):
                enabled = "Yes" if s["enabled"] else "No"
                suspended = "Yes" if s["suspend"] else "No"
                lines.append(f"| {i} | {s['name']} | {s['state']} | {s['traffic_type']} | {enabled} | {suspended} |")

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_get_traffic_item_details",
        annotations={
            "title": "Get Traffic Item Details",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_get_traffic_item_details(params: GetTrafficItemDetailsInput) -> str:
        """Get detailed configuration for traffic items.

        When traffic_item_name is provided, returns deep detail (frame rate,
        transmission control, frame size) for that single item.
        When omitted, returns a summary of all items (no deep REST traversal).

        Returns:
            str: Traffic item config in markdown or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                if params.traffic_item_name or params.traffic_item_index:
                    traffic = conn.ixnetwork.Traffic
                    ti, label = _find_traffic_item(
                        traffic, name=params.traffic_item_name, index=params.traffic_item_index
                    )
                    if ti is None:
                        return label  # error message
                    return [_traffic_item_detail(ti)]
                else:
                    items = conn.ixnetwork.Traffic.TrafficItem.find()
                    return [_traffic_item_summary(ti) for ti in items]

            details = await asyncio.to_thread(_fetch)

            if isinstance(details, str):
                return f"Error: {details}"

            if not details:
                return "No traffic items configured in this session."

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(details), "traffic_items": details}, indent=2)

            lines = ["# Traffic Item Details", ""]
            for d in details:
                lines.extend([
                    f"## {d['name']}",
                    f"- **State**: {d['state']}",
                    f"- **Type**: {d['traffic_type']}",
                    f"- **Enabled**: {'Yes' if d['enabled'] else 'No'}",
                    f"- **Suspended**: {'Yes' if d['suspend'] else 'No'}",
                    "",
                ])
                for i, ce in enumerate(d.get("config_elements", []), 1):
                    fr = ce.get("frame_rate", {})
                    tc = ce.get("transmission_control", {})
                    fs = ce.get("frame_size", {})
                    lines.extend([
                        f"### Config Element {i}",
                        f"- **Frame Rate**: {fr.get('rate', 'N/A')} ({fr.get('type', '')})",
                        f"- **Transmission**: {tc.get('type', 'N/A')}"
                        + (f", count={tc.get('frame_count')}" if tc.get("frame_count") else "")
                        + (f", duration={tc.get('duration')}s" if tc.get("duration") else ""),
                        f"- **Frame Size**: {fs.get('fixed_size', 'N/A')} bytes ({fs.get('type', '')})",
                        "",
                    ])

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    # ------------------------------------------------------------------
    # Action tools (existing)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="ixia_generate_traffic",
        annotations={
            "title": "Generate (Regenerate) All Traffic Items",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_generate_traffic(params: GenerateTrafficInput) -> str:
        """Regenerate all traffic items.

        Calls Generate() on every traffic item, pushing ConfigElement
        settings down to HighLevelStream resources. This must be done
        after any config change and before Apply + Start.

        Returns:
            str: Summary of how many items were regenerated, or an error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                items = conn.ixnetwork.Traffic.TrafficItem.find()
                if len(items) == 0:
                    return 0, 0, []
                count = 0
                errors = []
                for ti in items:
                    try:
                        ti.Generate()
                        count += 1
                    except Exception as e:
                        errors.append(f"{getattr(ti, 'Name', '?')}: {e}")
                return count, len(items), errors

            count, total, errors = await asyncio.to_thread(_run)

            if total == 0:
                return "No traffic items to generate."

            lines = [f"Regenerated {count}/{total} traffic item(s)."]
            if errors:
                lines.append("")
                lines.append(f"**{len(errors)} error(s):**")
                for err in errors:
                    lines.append(f"- {err}")

            return "\n".join(lines)

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_start_traffic",
        annotations={
            "title": "Start Traffic",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_start_traffic(params: StartTrafficInput) -> str:
        """Apply and start traffic on the IxNetwork session.

        When traffic_item_name is provided, resumes (unsuspends) only that
        item.  When omitted, applies config and starts all traffic items.

        Returns:
            str: Confirmation message or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                traffic = conn.ixnetwork.Traffic
                if params.traffic_item_name or params.traffic_item_index:
                    ti, label = _find_traffic_item(
                        traffic, name=params.traffic_item_name, index=params.traffic_item_index
                    )
                    if ti is None:
                        return None, label
                    was_suspended = getattr(ti, "Suspend", False)
                    ti.Suspend = False
                    return label, was_suspended
                else:
                    traffic.Apply()
                    traffic.StartStatelessTrafficBlocking()
                    return "__all__", None

            label, was_suspended = await asyncio.to_thread(_run)

            if label is None:
                return f"Error: {was_suspended}"
            if label == "__all__":
                return "Traffic applied and started successfully (all items)."
            if was_suspended:
                return f"Traffic item '{label}' resumed (unsuspended) successfully."
            return f"Traffic item '{label}' is already running (was not suspended)."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_stop_traffic",
        annotations={
            "title": "Stop Traffic",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_stop_traffic(params: StopTrafficInput) -> str:
        """Stop traffic on the IxNetwork session.

        When traffic_item_name is provided, suspends only that item while
        all other items continue transmitting.
        When omitted, stops all traffic items.

        Returns:
            str: Confirmation message or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                traffic = conn.ixnetwork.Traffic
                if params.traffic_item_name or params.traffic_item_index:
                    ti, label = _find_traffic_item(
                        traffic, name=params.traffic_item_name, index=params.traffic_item_index
                    )
                    if ti is None:
                        return None, label
                    was_suspended = getattr(ti, "Suspend", False)
                    ti.Suspend = True
                    return label, was_suspended
                else:
                    traffic.StopStatelessTrafficBlocking()
                    return "__all__", None

            label, was_suspended = await asyncio.to_thread(_run)

            if label is None:
                return f"Error: {was_suspended}"
            if label == "__all__":
                return "All traffic stopped successfully."
            if was_suspended:
                return f"Traffic item '{label}' was already suspended."
            return f"Traffic item '{label}' suspended successfully."

        except Exception as e:
            return _handle_error(e)

    # ------------------------------------------------------------------
    # Configuration tools (new)
    # ------------------------------------------------------------------

    @mcp.tool(
        name="ixia_create_traffic_item",
        annotations={
            "title": "Create Traffic Item",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_create_traffic_item(params: CreateTrafficItemInput) -> str:
        """Create a new traffic item with source and destination endpoints.

        Endpoints can be topology names or device group names. The traffic
        type determines the layer (ipv4, ipv6, ethernet, etc.).

        Returns:
            str: Confirmation with traffic item name or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork

                src_href = _find_endpoint_href(ix, params.source)
                if src_href is None:
                    return f"Source '{params.source}' not found as topology or device group."

                dst_href = _find_endpoint_href(ix, params.destination)
                if dst_href is None:
                    return f"Destination '{params.destination}' not found as topology or device group."

                ti = ix.Traffic.TrafficItem.add(
                    Name=params.name,
                    TrafficType=params.traffic_type,
                    BiDirectional=params.bidirectional,
                )
                ti.EndpointSet.add(
                    Sources=src_href,
                    Destinations=dst_href,
                )
                return {
                    "name": getattr(ti, "Name", params.name),
                    "type": params.traffic_type,
                    "bidirectional": params.bidirectional,
                }

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            bidir = " (bidirectional)" if result["bidirectional"] else ""
            return (
                f"Traffic item **{result['name']}** created "
                f"(type: {result['type']}{bidir}), "
                f"source: '{params.source}' -> destination: '{params.destination}'."
            )

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_delete_traffic_item",
        annotations={
            "title": "Delete Traffic Item",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_delete_traffic_item(params: DeleteTrafficItemInput) -> str:
        """Delete a traffic item by name or index.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                traffic = conn.ixnetwork.Traffic
                ti, label = _find_traffic_item(
                    traffic, name=params.traffic_item_name, index=params.traffic_item_index
                )
                if ti is None:
                    return label
                ti.remove()
                return None, label

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            _, label = result
            return f"Traffic item '{label}' deleted."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_configure_traffic_item",
        annotations={
            "title": "Configure Traffic Item",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_configure_traffic_item(params: ConfigureTrafficItemInput) -> str:
        """Configure frame rate, frame size, and transmission control on a traffic item.

        Only provided fields are modified; omitted fields remain unchanged.
        After configuring, use ixia_generate_traffic then ixia_start_traffic.

        Returns:
            str: Summary of configured properties or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                traffic = conn.ixnetwork.Traffic
                ti, label = _find_traffic_item(
                    traffic, name=params.traffic_item_name, index=params.traffic_item_index
                )
                if ti is None:
                    return label

                ce_list = ti.ConfigElement.find()
                if len(ce_list) == 0:
                    return f"Traffic item '{label}' has no config elements."
                ce = ce_list[0]

                changes = []

                if params.frame_rate_type is not None:
                    ce.FrameRate.Type = params.frame_rate_type
                    changes.append(f"rate type: {params.frame_rate_type}")

                if params.frame_rate is not None:
                    ce.FrameRate.Rate = params.frame_rate
                    changes.append(f"rate: {params.frame_rate}")

                if params.frame_size is not None:
                    ce.FrameSize.Type = "fixed"
                    ce.FrameSize.FixedSize = params.frame_size
                    changes.append(f"frame size: {params.frame_size} bytes")

                if params.transmission_type is not None:
                    ce.TransmissionControl.Type = params.transmission_type
                    changes.append(f"transmission: {params.transmission_type}")

                if params.frame_count is not None:
                    ce.TransmissionControl.FrameCount = params.frame_count
                    changes.append(f"frame count: {params.frame_count}")

                if params.duration is not None:
                    ce.TransmissionControl.Duration = params.duration
                    changes.append(f"duration: {params.duration}s")

                if not changes:
                    return "nothing"
                return label, changes

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                if result == "nothing":
                    return "No changes specified."
                return f"Error: {result}"

            label, changes = result
            return f"Traffic item '{label}' configured: {'; '.join(changes)}."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_add_tracking",
        annotations={
            "title": "Add Flow Tracking",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_add_tracking(params: AddTrackingInput) -> str:
        """Add flow tracking fields to a traffic item.

        Tracking enables per-flow statistics in the Flow Statistics view.
        Must be set before starting traffic.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                traffic = conn.ixnetwork.Traffic
                ti, label = _find_traffic_item(
                    traffic, name=params.traffic_item_name, index=params.traffic_item_index
                )
                if ti is None:
                    return label

                tracking = ti.Tracking.find()
                if len(tracking) == 0:
                    return f"Traffic item '{label}' has no tracking object."

                tracking[0].TrackBy = params.tracking_fields
                return label, params.tracking_fields

            result = await asyncio.to_thread(_run)

            if isinstance(result, str):
                return f"Error: {result}"

            label, fields = result
            return (
                f"Tracking set on traffic item '{label}': "
                f"{', '.join(fields)}."
            )

        except Exception as e:
            return _handle_error(e)
