"""Traffic tools: list, details, generate, start, stop."""

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


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register traffic tools."""

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
