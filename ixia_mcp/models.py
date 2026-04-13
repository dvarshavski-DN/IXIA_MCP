"""Pydantic input models for all IXIA MCP tools."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


# ---------------------------------------------------------------------------
# Session tools
# ---------------------------------------------------------------------------


class ConnectInput(BaseModel):
    """Parameters for connecting to an IxNetwork session."""

    model_config = ConfigDict(str_strip_whitespace=True)

    host: Optional[str] = Field(
        default=None,
        description=(
            "IxNetwork API server IP or hostname. "
            "Falls back to IXIA_HOST env var if omitted."
        ),
    )
    rest_port: Optional[int] = Field(
        default=None,
        description="REST API port (default 11009 for Windows GUI). Falls back to IXIA_PORT env var.",
        ge=1,
        le=65535,
    )
    session_id: Optional[int] = Field(
        default=None,
        description=(
            "Existing IxNetwork session ID to attach to. "
            "Falls back to IXIA_SESSION_ID env var."
        ),
        ge=1,
    )
    username: Optional[str] = Field(
        default=None,
        description="Username for authentication. Falls back to IXIA_USER env var.",
    )
    password: Optional[str] = Field(
        default=None,
        description="Password for authentication. Falls back to IXIA_PASSWORD env var.",
    )


class ConnectionIdInput(BaseModel):
    """Base model for tools that require an active connection."""

    model_config = ConfigDict(str_strip_whitespace=True)

    connection_id: str = Field(
        ...,
        description="Connection ID returned by ixia_connect.",
        min_length=1,
    )


class SessionInfoInput(ConnectionIdInput):
    """Parameters for getting session info."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


# ---------------------------------------------------------------------------
# Port tools
# ---------------------------------------------------------------------------


class ListPortsInput(ConnectionIdInput):
    """Parameters for listing virtual ports."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class GetPortStatusInput(ConnectionIdInput):
    """Parameters for getting detailed port status."""

    port_name: Optional[str] = Field(
        default=None,
        description="Virtual port name to query. If omitted, returns all ports.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


# ---------------------------------------------------------------------------
# Topology & protocol tools
# ---------------------------------------------------------------------------


class ListTopologiesInput(ConnectionIdInput):
    """Parameters for listing topologies."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class GetTopologyDetailsInput(ConnectionIdInput):
    """Parameters for getting topology details."""

    topology_name: Optional[str] = Field(
        default=None,
        description="Topology name. If omitted, returns details for all topologies.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class ProtocolStatusInput(ConnectionIdInput):
    """Parameters for getting protocol session status."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class StartProtocolsInput(ConnectionIdInput):
    """Parameters for starting protocols."""

    topology_name: Optional[str] = Field(
        default=None,
        description=(
            "Start protocols only for this topology. "
            "If omitted, starts all protocols."
        ),
    )


class StopProtocolsInput(ConnectionIdInput):
    """Parameters for stopping protocols."""

    topology_name: Optional[str] = Field(
        default=None,
        description=(
            "Stop protocols only for this topology. "
            "If omitted, stops all protocols."
        ),
    )


# ---------------------------------------------------------------------------
# Traffic tools
# ---------------------------------------------------------------------------


class ListTrafficItemsInput(ConnectionIdInput):
    """Parameters for listing traffic items."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class GetTrafficItemDetailsInput(ConnectionIdInput):
    """Parameters for getting traffic item details."""

    traffic_item_name: Optional[str] = Field(
        default=None,
        description="Traffic item name. If omitted, returns details for all items.",
    )
    traffic_item_index: Optional[int] = Field(
        default=None,
        description="1-based traffic item index (e.g. 100 for the 100th item). Alternative to traffic_item_name.",
        ge=1,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class GenerateTrafficInput(ConnectionIdInput):
    """Parameters for regenerating traffic items."""

    pass


class StartTrafficInput(ConnectionIdInput):
    """Parameters for starting traffic."""

    traffic_item_name: Optional[str] = Field(
        default=None,
        description=(
            "Traffic item name to start (resume). "
            "If omitted, starts all traffic items."
        ),
    )
    traffic_item_index: Optional[int] = Field(
        default=None,
        description="1-based traffic item index (e.g. 100 for the 100th item). Alternative to traffic_item_name.",
        ge=1,
    )


class StopTrafficInput(ConnectionIdInput):
    """Parameters for stopping traffic."""

    traffic_item_name: Optional[str] = Field(
        default=None,
        description=(
            "Traffic item name to stop (suspend). "
            "If omitted, stops all traffic items."
        ),
    )
    traffic_item_index: Optional[int] = Field(
        default=None,
        description="1-based traffic item index (e.g. 100 for the 100th item). Alternative to traffic_item_name.",
        ge=1,
    )


# ---------------------------------------------------------------------------
# Statistics tools
# ---------------------------------------------------------------------------


class PortStatisticsInput(ConnectionIdInput):
    """Parameters for getting port statistics."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class TrafficStatisticsInput(ConnectionIdInput):
    """Parameters for getting traffic item statistics."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class FlowStatisticsInput(ConnectionIdInput):
    """Parameters for getting per-flow statistics."""

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


class ClearStatisticsInput(ConnectionIdInput):
    """Parameters for clearing statistics counters."""

    scope: str = Field(
        default="all",
        description=(
            "What to clear: 'all' (port + traffic + protocol), "
            "'traffic' (port and traffic stats only), "
            "or 'protocol' (protocol stats only)."
        ),
    )
