"""Pydantic input models for all IXIA MCP tools."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class AddPortsInput(ConnectionIdInput):
    """Parameters for adding virtual ports with chassis assignment.

    Next step: use ixia_create_topology to group these ports into topologies.
    """

    chassis_ip: str = Field(
        ...,
        description="IP address of the Ixia chassis.",
    )
    card_port_pairs: list[list[int]] = Field(
        ...,
        description=(
            "List of [card, port] pairs to assign. "
            "Example: [[1, 3], [1, 4]] for card 1 ports 3 and 4."
        ),
    )
    port_names: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional names for each port. Must match length of card_port_pairs. "
            "If omitted, ports are named 'Port 1', 'Port 2', etc."
        ),
    )
    force_ownership: bool = Field(
        default=True,
        description="Force take ownership of ports if already owned by another user.",
    )


class ReleasePortsInput(ConnectionIdInput):
    """Parameters for releasing hardware ports."""

    port_names: Optional[list[str]] = Field(
        default=None,
        description="Port names to release. If omitted, releases all ports.",
    )


class RemovePortsInput(ConnectionIdInput):
    """Parameters for removing virtual ports from the config."""

    port_names: Optional[list[str]] = Field(
        default=None,
        description="Port names to remove. If omitted, removes all virtual ports.",
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


class CreateTopologyInput(ConnectionIdInput):
    """Parameters for creating a topology."""

    name: str = Field(
        ...,
        description="Name for the new topology.",
    )
    port_names: list[str] = Field(
        ...,
        description="Virtual port name(s) to assign to this topology.",
    )


class DeleteTopologyInput(ConnectionIdInput):
    """Parameters for deleting a topology."""

    topology_name: str = Field(
        ...,
        description="Name of the topology to delete.",
    )


class UpdateTopologyInput(ConnectionIdInput):
    """Parameters for updating a topology."""

    topology_name: str = Field(
        ...,
        description="Name of the topology to update.",
    )
    new_name: Optional[str] = Field(
        default=None,
        description="New name for the topology.",
    )
    port_names: Optional[list[str]] = Field(
        default=None,
        description="New list of virtual port names to assign (replaces existing).",
    )


# ---------------------------------------------------------------------------
# Device group tools
# ---------------------------------------------------------------------------


class CreateDeviceGroupInput(ConnectionIdInput):
    """Parameters for creating a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    name: str = Field(
        ...,
        description="Name for the new device group.",
    )
    multiplier: int = Field(
        default=1,
        description="Number of simulated devices (default: 1).",
        ge=1,
    )


class DeleteDeviceGroupInput(ConnectionIdInput):
    """Parameters for deleting a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group to delete.",
    )


class UpdateDeviceGroupInput(ConnectionIdInput):
    """Parameters for updating a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group to update.",
    )
    new_name: Optional[str] = Field(
        default=None,
        description="New name for the device group.",
    )
    multiplier: Optional[int] = Field(
        default=None,
        description="New multiplier (number of simulated devices).",
        ge=1,
    )
    enabled: Optional[bool] = Field(
        default=None,
        description="Enable or disable the device group.",
    )


class CreateNetworkGroupInput(ConnectionIdInput):
    """Parameters for creating a network group (route advertisement)."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the parent device group.",
    )
    name: str = Field(
        default="Network Group 1",
        description="Name for the network group.",
    )
    multiplier: int = Field(
        default=1,
        description="Number of route prefixes to advertise.",
        ge=1,
    )
    ipv4_network_address: Optional[str] = Field(
        default=None,
        description="Starting IPv4 network address (e.g. '200.1.0.0').",
    )
    ipv4_prefix_length: Optional[int] = Field(
        default=None,
        description="IPv4 prefix length (e.g. 24).",
        ge=1,
        le=32,
    )
    ipv4_prefix_step: Optional[str] = Field(
        default=None,
        description="IPv4 prefix step between routes (e.g. '0.1.0.0').",
    )


# ---------------------------------------------------------------------------
# Protocol stack tools
# ---------------------------------------------------------------------------


class AddProtocolInput(ConnectionIdInput):
    """Parameters for adding a protocol stack to a device group.

    Next step: use ixia_configure_ethernet / ixia_configure_ipv4 / ixia_configure_bgp
    to set addresses and parameters on the new stack, then ixia_start_protocols.
    """

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group.",
    )
    protocol: str = Field(
        ...,
        description=(
            "Protocol to add. Supported: 'ethernet', 'ipv4', 'ipv6', "
            "'bgpv4' (BGP IPv4 peer), 'bgpv6' (BGP IPv6 peer), "
            "'ospfv2', 'ospfv3', 'isis', 'ldp', 'igmp', 'pim'."
        ),
    )


class RemoveProtocolInput(ConnectionIdInput):
    """Parameters for removing a protocol stack from a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group.",
    )
    protocol: str = Field(
        ...,
        description=(
            "Protocol to remove. Same names as ixia_add_protocol: "
            "'ethernet', 'ipv4', 'ipv6', 'bgpv4', 'bgpv6', "
            "'ospfv2', 'ospfv3', 'isis', 'ldp', 'igmp', 'pim'."
        ),
    )


class ConfigureEthernetInput(ConnectionIdInput):
    """Parameters for configuring Ethernet on a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group.",
    )
    mac_address: Optional[str] = Field(
        default=None,
        description="Starting MAC address (e.g. '00:11:22:33:44:55').",
    )
    mac_step: Optional[str] = Field(
        default=None,
        description="MAC increment step (default: '00:00:00:00:00:01').",
    )
    mtu: Optional[int] = Field(
        default=None,
        description="MTU size.",
        ge=64,
        le=14000,
    )
    vlan_enabled: Optional[bool] = Field(
        default=None,
        description="Enable or disable VLAN tagging.",
    )
    vlan_id: Optional[int] = Field(
        default=None,
        description="VLAN ID (1-4094).",
        ge=1,
        le=4094,
    )
    vlan_id_step: Optional[int] = Field(
        default=None,
        description="VLAN ID increment step (default: 0 = same VLAN for all).",
        ge=0,
    )
    vlan_priority: Optional[int] = Field(
        default=None,
        description="VLAN priority (0-7).",
        ge=0,
        le=7,
    )


class ConfigureIpv4Input(ConnectionIdInput):
    """Parameters for configuring IPv4 on a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group.",
    )
    address: Optional[str] = Field(
        default=None,
        description="Starting IPv4 address (e.g. '1.1.1.1').",
    )
    address_step: Optional[str] = Field(
        default=None,
        description="Address increment step (default: '0.0.0.1').",
    )
    gateway: Optional[str] = Field(
        default=None,
        description="Gateway IPv4 address (e.g. '1.1.1.254').",
    )
    gateway_step: Optional[str] = Field(
        default=None,
        description="Gateway increment step (default: '0.0.0.0').",
    )
    prefix_length: Optional[int] = Field(
        default=None,
        description="Subnet prefix length (e.g. 24).",
        ge=1,
        le=32,
    )


class ConfigureIpv6Input(ConnectionIdInput):
    """Parameters for configuring IPv6 on a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group.",
    )
    address: Optional[str] = Field(
        default=None,
        description="Starting IPv6 address (e.g. '2001:db8::1').",
    )
    address_step: Optional[str] = Field(
        default=None,
        description="Address increment step (default: '::1').",
    )
    gateway: Optional[str] = Field(
        default=None,
        description="Gateway IPv6 address.",
    )
    gateway_step: Optional[str] = Field(
        default=None,
        description="Gateway increment step (default: '::0').",
    )
    prefix_length: Optional[int] = Field(
        default=None,
        description="Subnet prefix length (e.g. 64).",
        ge=1,
        le=128,
    )


class ConfigureBgpInput(ConnectionIdInput):
    """Parameters for configuring BGP on a device group."""

    topology_name: str = Field(
        ...,
        description="Name of the parent topology.",
    )
    device_group_name: str = Field(
        ...,
        description="Name of the device group.",
    )
    ip_version: str = Field(
        default="ipv4",
        description="IP version: 'ipv4' or 'ipv6'.",
    )
    dut_ip: Optional[str] = Field(
        default=None,
        description="DUT (neighbor) IP address.",
    )
    dut_ip_step: Optional[str] = Field(
        default=None,
        description="DUT IP increment step.",
    )
    local_as: Optional[int] = Field(
        default=None,
        description="Local AS number, 2-byte range only (1-65535). For 4-byte AS numbers use the IxNetwork GUI.",
        ge=1,
        le=65535,
    )
    bgp_type: Optional[str] = Field(
        default=None,
        description="BGP type: 'internal' or 'external'.",
    )
    hold_timer: Optional[int] = Field(
        default=None,
        description="BGP hold timer in seconds.",
        ge=0,
    )
    update_interval: Optional[int] = Field(
        default=None,
        description="BGP update interval in seconds.",
        ge=0,
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


class CreateTrafficItemInput(ConnectionIdInput):
    """Parameters for creating a traffic item.

    Next step: use ixia_configure_traffic_item to set rate/size/duration,
    then ixia_generate_traffic and ixia_start_traffic.
    """

    name: str = Field(
        ...,
        description="Name for the new traffic item.",
    )
    traffic_type: str = Field(
        default="ipv4",
        description=(
            "Traffic type that determines the protocol layer for the flow. "
            "Allowed values: 'ipv4', 'ipv6', 'ethernet', 'raw', 'ethernetVlan'. "
            "Must match a protocol stack already configured on the endpoints."
        ),
    )
    source: str = Field(
        ...,
        description=(
            "Name of the source topology or device group. "
            "Traffic flows originate from the endpoints in this group. "
            "The name must exactly match an existing topology or device group."
        ),
    )
    destination: str = Field(
        ...,
        description=(
            "Name of the destination topology or device group. "
            "Traffic flows are addressed to the endpoints in this group. "
            "The name must exactly match an existing topology or device group."
        ),
    )
    bidirectional: bool = Field(
        default=False,
        description="Create bidirectional traffic flow.",
    )


class DeleteTrafficItemInput(ConnectionIdInput):
    """Parameters for deleting a traffic item."""

    traffic_item_name: Optional[str] = Field(
        default=None,
        description="Name of the traffic item to delete.",
    )
    traffic_item_index: Optional[int] = Field(
        default=None,
        description="1-based index of the traffic item to delete.",
        ge=1,
    )

    @model_validator(mode="after")
    def check_identifier(self):
        if self.traffic_item_name is None and self.traffic_item_index is None:
            raise ValueError("Provide either traffic_item_name or traffic_item_index.")
        return self


class ConfigureTrafficItemInput(ConnectionIdInput):
    """Parameters for configuring a traffic item's rate, size, and transmission."""

    traffic_item_name: Optional[str] = Field(
        default=None,
        description="Traffic item name to configure.",
    )
    traffic_item_index: Optional[int] = Field(
        default=None,
        description="1-based traffic item index. Alternative to traffic_item_name.",
        ge=1,
    )

    @model_validator(mode="after")
    def check_identifier(self):
        if self.traffic_item_name is None and self.traffic_item_index is None:
            raise ValueError("Provide either traffic_item_name or traffic_item_index.")
        return self

    frame_rate: Optional[float] = Field(
        default=None,
        description="Frame rate value (interpretation depends on frame_rate_type).",
    )
    frame_rate_type: Optional[str] = Field(
        default=None,
        description="Rate type: 'percentLineRate', 'framesPerSecond', or 'bitsPerSecond'.",
    )
    frame_size: Optional[int] = Field(
        default=None,
        description="Fixed frame size in bytes.",
        ge=64,
        le=16383,
    )
    transmission_type: Optional[str] = Field(
        default=None,
        description="Transmission control: 'continuous', 'fixedFrameCount', or 'fixedDuration'.",
    )
    frame_count: Optional[int] = Field(
        default=None,
        description="Number of frames (for fixedFrameCount transmission).",
        ge=1,
    )
    duration: Optional[int] = Field(
        default=None,
        description="Duration in seconds (for fixedDuration transmission).",
        ge=1,
    )


class AddTrackingInput(ConnectionIdInput):
    """Parameters for adding flow tracking to a traffic item."""

    traffic_item_name: Optional[str] = Field(
        default=None,
        description="Traffic item name.",
    )
    traffic_item_index: Optional[int] = Field(
        default=None,
        description="1-based traffic item index. Alternative to traffic_item_name.",
        ge=1,
    )

    @model_validator(mode="after")
    def check_identifier(self):
        if self.traffic_item_name is None and self.traffic_item_index is None:
            raise ValueError("Provide either traffic_item_name or traffic_item_index.")
        return self

    tracking_fields: list[str] = Field(
        ...,
        description=(
            "Tracking field names to enable. Common values: "
            "'trackerName', 'sourceDestEndpointPair0', "
            "'sourceDestValuePair0', 'flowGroup0'."
        ),
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


# ---------------------------------------------------------------------------
# Config management tools
# ---------------------------------------------------------------------------


class SaveConfigInput(ConnectionIdInput):
    """Parameters for saving the IxNetwork config."""

    file_path: str = Field(
        ...,
        description="File path on the IxNetwork server to save to (e.g. 'C:/configs/my_test.ixncfg').",
    )


class LoadConfigInput(ConnectionIdInput):
    """Parameters for loading an IxNetwork config."""

    file_path: str = Field(
        ...,
        description="File path on the IxNetwork server to load from (e.g. 'C:/configs/my_test.ixncfg').",
    )
