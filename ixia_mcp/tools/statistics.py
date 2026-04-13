"""Statistics tools: port, traffic item, and flow statistics."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from ixia_mcp.models import (
    PortStatisticsInput,
    TrafficStatisticsInput,
    FlowStatisticsInput,
    ClearStatisticsInput,
    ResponseFormat,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ixia_mcp.client import ConnectionManager


def _handle_error(e: Exception) -> str:
    return f"Error: {type(e).__name__}: {e}"


def _stat_view_to_records(session_assistant, view_name: str) -> list[dict[str, Any]]:
    """Read a StatViewAssistant and return rows as list of dicts.

    Takes a single CSV snapshot and builds records from the in-memory
    RawData/Columns instead of re-triggering a snapshot per row.
    """
    sv = session_assistant.StatViewAssistant(view_name)
    snapshot = sv.Rows  # single CSV snapshot round-trip
    columns = snapshot.Columns
    return [dict(zip(columns, raw_row)) for raw_row in snapshot.RawData]


def _records_to_markdown_table(records: list[dict[str, Any]], title: str) -> str:
    """Convert a list of dicts to a markdown table."""
    if not records:
        return f"# {title}\n\nNo data available."

    columns = list(records[0].keys())

    lines = [
        f"# {title}",
        "",
        f"**{len(records)}** row(s).",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for rec in records:
        vals = [str(rec.get(c, "")) for c in columns]
        lines.append("| " + " | ".join(vals) + " |")

    return "\n".join(lines)


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register statistics tools."""

    @mcp.tool(
        name="ixia_get_port_statistics",
        annotations={
            "title": "Get Port Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_get_port_statistics(params: PortStatisticsInput) -> str:
        """Get port-level TX/RX statistics from the IxNetwork session.

        Returns counters like Frames Tx, Frames Rx, Bytes Tx, Bytes Rx,
        Tx Rate, Rx Rate for each port.

        Returns:
            str: Port statistics table in markdown or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                return _stat_view_to_records(conn.session_assistant, "Port Statistics")

            records = await asyncio.to_thread(_fetch)

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(records), "rows": records}, indent=2)

            return _records_to_markdown_table(records, "Port Statistics")

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_get_traffic_statistics",
        annotations={
            "title": "Get Traffic Item Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_get_traffic_statistics(params: TrafficStatisticsInput) -> str:
        """Get traffic item level statistics.

        Returns per-traffic-item counters like Tx Frames, Rx Frames,
        Frames Delta, Loss %, Tx Rate, Rx Rate.

        Returns:
            str: Traffic statistics table in markdown or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                return _stat_view_to_records(conn.session_assistant, "Traffic Item Statistics")

            records = await asyncio.to_thread(_fetch)

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(records), "rows": records}, indent=2)

            return _records_to_markdown_table(records, "Traffic Item Statistics")

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_clear_statistics",
        annotations={
            "title": "Clear Statistics Counters",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_clear_statistics(params: ClearStatisticsInput) -> str:
        """Clear statistics counters on the IxNetwork session.

        Resets all counters to zero. Use scope to control what is cleared:
        'all' clears everything, 'traffic' clears port and traffic stats,
        'protocol' clears protocol stats only.

        Returns:
            str: Confirmation message or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                ix = conn.ixnetwork
                scope = params.scope.lower().strip()
                if scope == "all":
                    ix.ClearStats(["waitForPortStatsRefresh", "waitForTrafficStatsRefresh"])
                    return "all"
                elif scope == "traffic":
                    ix.ClearPortsAndTrafficStats(["waitForPortStatsRefresh", "waitForTrafficStatsRefresh"])
                    return "port and traffic"
                elif scope == "protocol":
                    ix.ClearProtocolStats()
                    return "protocol"
                else:
                    return None

            result = await asyncio.to_thread(_run)

            if result is None:
                return (
                    f"Error: Unknown scope '{params.scope}'. "
                    "Use 'all', 'traffic', or 'protocol'."
                )
            return f"Statistics cleared successfully (scope: {result})."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_get_flow_statistics",
        annotations={
            "title": "Get Flow Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ixia_get_flow_statistics(params: FlowStatisticsInput) -> str:
        """Get per-flow statistics for granular traffic analysis.

        Returns per-flow counters including tracking values, Tx/Rx frames,
        loss percentage, and rates.

        Returns:
            str: Flow statistics table in markdown or JSON format.
        """
        try:
            def _fetch():
                conn = manager.get(params.connection_id)
                return _stat_view_to_records(conn.session_assistant, "Flow Statistics")

            records = await asyncio.to_thread(_fetch)

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"count": len(records), "rows": records}, indent=2)

            return _records_to_markdown_table(records, "Flow Statistics")

        except Exception as e:
            return _handle_error(e)
