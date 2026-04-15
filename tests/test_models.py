"""Pydantic validation tests for IXIA MCP input models."""

import pytest
from pydantic import ValidationError

from ixia_mcp.models import (
    ConnectInput,
    ConnectionIdInput,
    SessionInfoInput,
    ResponseFormat,
    AddPortsInput,
    ListPortsInput,
    GetPortStatusInput,
    ReleasePortsInput,
    RemovePortsInput,
    CreateTopologyInput,
    DeleteTopologyInput,
    UpdateTopologyInput,
    CreateDeviceGroupInput,
    DeleteDeviceGroupInput,
    UpdateDeviceGroupInput,
    CreateNetworkGroupInput,
    AddProtocolInput,
    RemoveProtocolInput,
    ConfigureEthernetInput,
    ConfigureIpv4Input,
    ConfigureIpv6Input,
    ConfigureBgpInput,
    ListTrafficItemsInput,
    GetTrafficItemDetailsInput,
    CreateTrafficItemInput,
    DeleteTrafficItemInput,
    ConfigureTrafficItemInput,
    AddTrackingInput,
    GenerateTrafficInput,
    StartTrafficInput,
    StopTrafficInput,
    PortStatisticsInput,
    TrafficStatisticsInput,
    FlowStatisticsInput,
    ClearStatisticsInput,
    SaveConfigInput,
    LoadConfigInput,
)


# ---------------------------------------------------------------------------
# ConnectInput
# ---------------------------------------------------------------------------


class TestConnectInput:
    def test_all_defaults(self):
        m = ConnectInput()
        assert m.host is None
        assert m.rest_port is None
        assert m.session_id is None
        assert m.username is None
        assert m.password is None

    def test_explicit_values(self):
        m = ConnectInput(
            host="10.0.0.1",
            rest_port=443,
            session_id=2,
            username="user",
            password="pass",
        )
        assert m.host == "10.0.0.1"
        assert m.rest_port == 443
        assert m.session_id == 2

    def test_strips_whitespace(self):
        m = ConnectInput(host="  10.0.0.1  ")
        assert m.host == "10.0.0.1"

    def test_port_range_low(self):
        with pytest.raises(ValidationError):
            ConnectInput(rest_port=0)

    def test_port_range_high(self):
        with pytest.raises(ValidationError):
            ConnectInput(rest_port=70000)

    def test_session_id_must_be_positive(self):
        with pytest.raises(ValidationError):
            ConnectInput(session_id=0)


# ---------------------------------------------------------------------------
# ConnectionIdInput
# ---------------------------------------------------------------------------


class TestConnectionIdInput:
    def test_requires_connection_id(self):
        with pytest.raises(ValidationError):
            ConnectionIdInput()

    def test_empty_connection_id_rejected(self):
        with pytest.raises(ValidationError):
            ConnectionIdInput(connection_id="")

    def test_valid_connection_id(self):
        m = ConnectionIdInput(connection_id="abc123")
        assert m.connection_id == "abc123"

    def test_strips_whitespace(self):
        m = ConnectionIdInput(connection_id="  abc123  ")
        assert m.connection_id == "abc123"


# ---------------------------------------------------------------------------
# SessionInfoInput / ResponseFormat
# ---------------------------------------------------------------------------


class TestSessionInfoInput:
    def test_default_format_is_markdown(self):
        m = SessionInfoInput(connection_id="c1")
        assert m.response_format == ResponseFormat.MARKDOWN

    def test_json_format(self):
        m = SessionInfoInput(connection_id="c1", response_format="json")
        assert m.response_format == ResponseFormat.JSON

    def test_invalid_format_rejected(self):
        with pytest.raises(ValidationError):
            SessionInfoInput(connection_id="c1", response_format="xml")


# ---------------------------------------------------------------------------
# AddPortsInput
# ---------------------------------------------------------------------------


class TestAddPortsInput:
    def test_minimal(self):
        m = AddPortsInput(
            connection_id="c1",
            chassis_ip="10.0.0.2",
            card_port_pairs=[[1, 3], [1, 4]],
        )
        assert m.chassis_ip == "10.0.0.2"
        assert m.card_port_pairs == [[1, 3], [1, 4]]
        assert m.port_names is None
        assert m.force_ownership is True

    def test_with_port_names(self):
        m = AddPortsInput(
            connection_id="c1",
            chassis_ip="10.0.0.2",
            card_port_pairs=[[1, 1]],
            port_names=["Tx"],
        )
        assert m.port_names == ["Tx"]

    def test_missing_chassis_ip(self):
        with pytest.raises(ValidationError):
            AddPortsInput(connection_id="c1", card_port_pairs=[[1, 1]])

    def test_missing_card_port_pairs(self):
        with pytest.raises(ValidationError):
            AddPortsInput(connection_id="c1", chassis_ip="10.0.0.2")


# ---------------------------------------------------------------------------
# CreateTopologyInput
# ---------------------------------------------------------------------------


class TestCreateTopologyInput:
    def test_valid(self):
        m = CreateTopologyInput(
            connection_id="c1", name="Topo1", port_names=["Port 1"]
        )
        assert m.name == "Topo1"
        assert m.port_names == ["Port 1"]

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            CreateTopologyInput(connection_id="c1", port_names=["Port 1"])

    def test_missing_ports(self):
        with pytest.raises(ValidationError):
            CreateTopologyInput(connection_id="c1", name="Topo1")


# ---------------------------------------------------------------------------
# CreateDeviceGroupInput
# ---------------------------------------------------------------------------


class TestCreateDeviceGroupInput:
    def test_defaults(self):
        m = CreateDeviceGroupInput(
            connection_id="c1", topology_name="T1", name="DG1"
        )
        assert m.multiplier == 1

    def test_custom_multiplier(self):
        m = CreateDeviceGroupInput(
            connection_id="c1", topology_name="T1", name="DG1", multiplier=10
        )
        assert m.multiplier == 10

    def test_multiplier_must_be_positive(self):
        with pytest.raises(ValidationError):
            CreateDeviceGroupInput(
                connection_id="c1", topology_name="T1", name="DG1", multiplier=0
            )


# ---------------------------------------------------------------------------
# AddProtocolInput
# ---------------------------------------------------------------------------


class TestAddProtocolInput:
    def test_valid(self):
        m = AddProtocolInput(
            connection_id="c1",
            topology_name="T1",
            device_group_name="DG1",
            protocol="ipv4",
        )
        assert m.protocol == "ipv4"

    def test_missing_protocol(self):
        with pytest.raises(ValidationError):
            AddProtocolInput(
                connection_id="c1",
                topology_name="T1",
                device_group_name="DG1",
            )


# ---------------------------------------------------------------------------
# ConfigureEthernetInput
# ---------------------------------------------------------------------------


class TestConfigureEthernetInput:
    def test_all_optional(self):
        m = ConfigureEthernetInput(
            connection_id="c1", topology_name="T1", device_group_name="DG1"
        )
        assert m.mac_address is None
        assert m.vlan_enabled is None

    def test_vlan_id_range(self):
        with pytest.raises(ValidationError):
            ConfigureEthernetInput(
                connection_id="c1",
                topology_name="T1",
                device_group_name="DG1",
                vlan_id=0,
            )

    def test_vlan_id_max(self):
        with pytest.raises(ValidationError):
            ConfigureEthernetInput(
                connection_id="c1",
                topology_name="T1",
                device_group_name="DG1",
                vlan_id=4095,
            )

    def test_mtu_range(self):
        with pytest.raises(ValidationError):
            ConfigureEthernetInput(
                connection_id="c1",
                topology_name="T1",
                device_group_name="DG1",
                mtu=10,
            )


# ---------------------------------------------------------------------------
# ConfigureIpv4Input
# ---------------------------------------------------------------------------


class TestConfigureIpv4Input:
    def test_all_optional(self):
        m = ConfigureIpv4Input(
            connection_id="c1", topology_name="T1", device_group_name="DG1"
        )
        assert m.address is None
        assert m.prefix_length is None

    def test_prefix_length_range(self):
        with pytest.raises(ValidationError):
            ConfigureIpv4Input(
                connection_id="c1",
                topology_name="T1",
                device_group_name="DG1",
                prefix_length=33,
            )


# ---------------------------------------------------------------------------
# ConfigureBgpInput
# ---------------------------------------------------------------------------


class TestConfigureBgpInput:
    def test_defaults(self):
        m = ConfigureBgpInput(
            connection_id="c1", topology_name="T1", device_group_name="DG1"
        )
        assert m.ip_version == "ipv4"
        assert m.local_as is None

    def test_local_as_range(self):
        with pytest.raises(ValidationError):
            ConfigureBgpInput(
                connection_id="c1",
                topology_name="T1",
                device_group_name="DG1",
                local_as=0,
            )


# ---------------------------------------------------------------------------
# CreateTrafficItemInput
# ---------------------------------------------------------------------------


class TestCreateTrafficItemInput:
    def test_valid(self):
        m = CreateTrafficItemInput(
            connection_id="c1",
            name="Flow1",
            source="Topo1",
            destination="Topo2",
        )
        assert m.traffic_type == "ipv4"
        assert m.bidirectional is False

    def test_missing_source(self):
        with pytest.raises(ValidationError):
            CreateTrafficItemInput(
                connection_id="c1", name="Flow1", destination="Topo2"
            )

    def test_missing_destination(self):
        with pytest.raises(ValidationError):
            CreateTrafficItemInput(
                connection_id="c1", name="Flow1", source="Topo1"
            )


# ---------------------------------------------------------------------------
# ConfigureTrafficItemInput
# ---------------------------------------------------------------------------


class TestConfigureTrafficItemInput:
    def test_frame_size_range(self):
        with pytest.raises(ValidationError):
            ConfigureTrafficItemInput(
                connection_id="c1",
                traffic_item_name="TI1",
                frame_size=10,
            )

    def test_frame_size_upper(self):
        with pytest.raises(ValidationError):
            ConfigureTrafficItemInput(
                connection_id="c1",
                traffic_item_name="TI1",
                frame_size=20000,
            )


# ---------------------------------------------------------------------------
# AddTrackingInput
# ---------------------------------------------------------------------------


class TestAddTrackingInput:
    def test_valid(self):
        m = AddTrackingInput(
            connection_id="c1",
            traffic_item_name="TI1",
            tracking_fields=["trackerName"],
        )
        assert m.tracking_fields == ["trackerName"]

    def test_missing_tracking_fields(self):
        with pytest.raises(ValidationError):
            AddTrackingInput(connection_id="c1", traffic_item_name="TI1")


# ---------------------------------------------------------------------------
# ClearStatisticsInput
# ---------------------------------------------------------------------------


class TestClearStatisticsInput:
    def test_default_scope(self):
        m = ClearStatisticsInput(connection_id="c1")
        assert m.scope == "all"


# ---------------------------------------------------------------------------
# SaveConfigInput / LoadConfigInput
# ---------------------------------------------------------------------------


class TestConfigInputs:
    def test_save_config(self):
        m = SaveConfigInput(connection_id="c1", file_path="C:/test.ixncfg")
        assert m.file_path == "C:/test.ixncfg"

    def test_load_config(self):
        m = LoadConfigInput(connection_id="c1", file_path="C:/test.ixncfg")
        assert m.file_path == "C:/test.ixncfg"

    def test_save_missing_path(self):
        with pytest.raises(ValidationError):
            SaveConfigInput(connection_id="c1")

    def test_load_missing_path(self):
        with pytest.raises(ValidationError):
            LoadConfigInput(connection_id="c1")


# ---------------------------------------------------------------------------
# CreateNetworkGroupInput
# ---------------------------------------------------------------------------


class TestCreateNetworkGroupInput:
    def test_defaults(self):
        m = CreateNetworkGroupInput(
            connection_id="c1",
            topology_name="T1",
            device_group_name="DG1",
        )
        assert m.name == "Network Group 1"
        assert m.multiplier == 1
        assert m.ipv4_network_address is None

    def test_ipv4_prefix_length_range(self):
        with pytest.raises(ValidationError):
            CreateNetworkGroupInput(
                connection_id="c1",
                topology_name="T1",
                device_group_name="DG1",
                ipv4_prefix_length=33,
            )
