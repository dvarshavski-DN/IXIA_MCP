"""Unit tests for ConnectionManager (no IxNetwork hardware required)."""

import pytest
from unittest.mock import patch, MagicMock

from ixia_mcp.client import ConnectionManager, IxNetworkConnection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager():
    """ConnectionManager with default settings."""
    return ConnectionManager()


@pytest.fixture
def mock_session_assistant():
    """Patch SessionAssistant so connect() never hits the network."""
    with patch("ixia_mcp.client.SessionAssistant") as mock_cls:
        sa_instance = MagicMock()
        sa_instance.Ixnetwork = MagicMock()
        mock_cls.return_value = sa_instance
        yield mock_cls


# ---------------------------------------------------------------------------
# ConnectionManager.__init__ defaults
# ---------------------------------------------------------------------------


class TestConnectionManagerDefaults:
    def test_default_host_from_env(self, monkeypatch):
        monkeypatch.setenv("IXIA_HOST", "192.168.1.1")
        m = ConnectionManager()
        assert m._default_host == "192.168.1.1"

    def test_default_port_from_env(self, monkeypatch):
        monkeypatch.setenv("IXIA_PORT", "443")
        m = ConnectionManager()
        assert m._default_port == 443

    def test_default_session_id_from_env(self, monkeypatch):
        monkeypatch.setenv("IXIA_SESSION_ID", "5")
        m = ConnectionManager()
        assert m._default_session_id == 5

    def test_cli_args_override_env(self, monkeypatch):
        monkeypatch.setenv("IXIA_HOST", "env-host")
        m = ConnectionManager(default_host="cli-host")
        assert m._default_host == "cli-host"

    def test_hardcoded_fallbacks(self, monkeypatch):
        monkeypatch.delenv("IXIA_HOST", raising=False)
        monkeypatch.delenv("IXIA_PORT", raising=False)
        monkeypatch.delenv("IXIA_SESSION_ID", raising=False)
        monkeypatch.delenv("IXIA_USER", raising=False)
        monkeypatch.delenv("IXIA_PASSWORD", raising=False)
        m = ConnectionManager()
        assert m._default_host == "127.0.0.1"
        assert m._default_port == 11009
        assert m._default_session_id == 1
        assert m._default_user == "admin"
        assert m._default_password == "admin"


# ---------------------------------------------------------------------------
# connect / get / disconnect
# ---------------------------------------------------------------------------


class TestConnectGetDisconnect:
    def test_connect_returns_connection(self, manager, mock_session_assistant):
        conn = manager.connect()
        assert isinstance(conn, IxNetworkConnection)
        assert len(conn.connection_id) == 12

    def test_get_returns_same_connection(self, manager, mock_session_assistant):
        conn = manager.connect()
        assert manager.get(conn.connection_id) is conn

    def test_get_unknown_id_raises(self, manager):
        with pytest.raises(KeyError, match="No active connection"):
            manager.get("nonexistent")

    def test_disconnect_removes_connection(self, manager, mock_session_assistant):
        conn = manager.connect()
        manager.disconnect(conn.connection_id)
        with pytest.raises(KeyError):
            manager.get(conn.connection_id)

    def test_disconnect_unknown_id_raises(self, manager):
        with pytest.raises(KeyError, match="Nothing to disconnect"):
            manager.disconnect("nonexistent")

    def test_connect_uses_explicit_params(self, manager, mock_session_assistant):
        conn = manager.connect(
            host="10.0.0.5", rest_port=8080, session_id=3
        )
        assert conn.host == "10.0.0.5"
        assert conn.rest_port == 8080
        assert conn.session_id == 3

    def test_connect_falls_back_to_defaults(self, manager, mock_session_assistant):
        conn = manager.connect()
        assert conn.host == manager._default_host
        assert conn.rest_port == manager._default_port
        assert conn.session_id == manager._default_session_id


# ---------------------------------------------------------------------------
# disconnect_all / list_connections
# ---------------------------------------------------------------------------


class TestBulkOperations:
    def test_disconnect_all(self, manager, mock_session_assistant):
        manager.connect()
        manager.connect()
        assert len(manager.list_connections()) == 2
        manager.disconnect_all()
        assert len(manager.list_connections()) == 0

    def test_list_connections_empty(self, manager):
        assert manager.list_connections() == []

    def test_list_connections_contents(self, manager, mock_session_assistant):
        conn = manager.connect()
        items = manager.list_connections()
        assert len(items) == 1
        assert items[0]["connection_id"] == conn.connection_id
        assert items[0]["host"] == conn.host


# ---------------------------------------------------------------------------
# IxNetworkConnection
# ---------------------------------------------------------------------------


class TestIxNetworkConnection:
    def test_post_init_sets_ixnetwork(self):
        sa = MagicMock()
        sa.Ixnetwork = MagicMock(name="ix_obj")
        conn = IxNetworkConnection(
            connection_id="test123",
            host="localhost",
            rest_port=11009,
            session_id=1,
            session_assistant=sa,
        )
        assert conn.ixnetwork is sa.Ixnetwork


# ---------------------------------------------------------------------------
# Multiple concurrent connections
# ---------------------------------------------------------------------------


class TestMultipleConnections:
    def test_unique_connection_ids(self, manager, mock_session_assistant):
        c1 = manager.connect()
        c2 = manager.connect()
        assert c1.connection_id != c2.connection_id

    def test_disconnect_one_keeps_other(self, manager, mock_session_assistant):
        c1 = manager.connect()
        c2 = manager.connect()
        manager.disconnect(c1.connection_id)
        assert manager.get(c2.connection_id) is c2
        with pytest.raises(KeyError):
            manager.get(c1.connection_id)
