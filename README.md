# IXIA MCP Server

MCP (Model Context Protocol) server for **Keysight IxNetwork**. Enables AI agents in Cursor, Claude, and other MCP-compatible tools to interact with IxNetwork sessions — querying ports, topologies, protocols, traffic items, statistics, and controlling protocol/traffic start/stop.

## Architecture

```
┌──────────────────┐     HTTP      ┌────────────────────┐   ixnetwork_restpy   ┌──────────────────┐
│  Cursor Agent 1  │──────────────▶│                    │◀────────────────────▶│                  │
│  Cursor Agent 2  │──────────────▶│  ixia_mcp server   │                     │  IxNetwork GUI   │
│  Claude / other  │──────────────▶│  (port 8080)       │                     │  (Windows)       │
└──────────────────┘               └────────────────────┘                     └──────────────────┘
```

The server runs on a remote machine accessible to all users. Each user's agent connects to the server over HTTP and operates on their own IxNetwork session.

## Available Tools (41)

### Session Management (3)
| Tool | Description |
|------|-------------|
| `ixia_connect` | Connect to an IxNetwork session (returns `connection_id`) |
| `ixia_disconnect` | Disconnect from a session |
| `ixia_get_session_info` | Get session details (build, port/topology/traffic counts) |

### Ports (5)
| Tool | Description |
|------|-------------|
| `ixia_list_ports` | List all virtual ports with state and assignment |
| `ixia_get_port_status` | Detailed status for one or all ports |
| `ixia_add_ports` | Add virtual ports and assign to chassis hardware (card/port) |
| `ixia_release_ports` | Release hardware port assignments |
| `ixia_remove_ports` | Remove virtual ports from the config |

### Topologies (6)
| Tool | Description |
|------|-------------|
| `ixia_list_topologies` | List topologies with device group counts |
| `ixia_get_topology_details` | Device groups, protocols per topology |
| `ixia_get_protocol_status` | Protocol session status (up/down/not started) |
| `ixia_create_topology` | Create a topology and assign ports |
| `ixia_delete_topology` | Delete a topology |
| `ixia_update_topology` | Rename or reassign ports on a topology |

### Device Groups (4)
| Tool | Description |
|------|-------------|
| `ixia_create_device_group` | Create a device group under a topology (set multiplier) |
| `ixia_delete_device_group` | Delete a device group |
| `ixia_update_device_group` | Update multiplier, enabled state, or name |
| `ixia_create_network_group` | Create a network group for route advertisement |

### Protocol Stacks (6)
| Tool | Description |
|------|-------------|
| `ixia_add_protocol` | Add a protocol to a device group (Ethernet, IPv4, IPv6, BGP, OSPF, ISIS, LDP, IGMP, PIM) |
| `ixia_remove_protocol` | Remove a protocol from a device group |
| `ixia_configure_ethernet` | Set MAC address, MTU, VLAN ID/priority |
| `ixia_configure_ipv4` | Set IP address, gateway, prefix length |
| `ixia_configure_ipv6` | Set IP address, gateway, prefix length |
| `ixia_configure_bgp` | Set DUT IP, local AS, BGP type, hold timer |

### Protocol Control (2)
| Tool | Description |
|------|-------------|
| `ixia_start_protocols` | Start all or per-topology protocols |
| `ixia_stop_protocols` | Stop all or per-topology protocols |

### Traffic (9)
| Tool | Description |
|------|-------------|
| `ixia_list_traffic_items` | List traffic items with state and type |
| `ixia_get_traffic_item_details` | Frame rate, transmission control, frame size |
| `ixia_create_traffic_item` | Create a traffic item with source/destination endpoints |
| `ixia_delete_traffic_item` | Delete a traffic item |
| `ixia_configure_traffic_item` | Set frame rate, frame size, transmission type |
| `ixia_add_tracking` | Add flow tracking fields to a traffic item |
| `ixia_generate_traffic` | Regenerate traffic items after config changes |
| `ixia_start_traffic` | Apply config and start traffic |
| `ixia_stop_traffic` | Stop traffic |

### Statistics (4)
| Tool | Description |
|------|-------------|
| `ixia_get_port_statistics` | Port TX/RX counters and rates |
| `ixia_get_traffic_statistics` | Traffic item level counters and loss |
| `ixia_get_flow_statistics` | Per-flow granular statistics |
| `ixia_clear_statistics` | Clear statistics counters |

### Config Management (2)
| Tool | Description |
|------|-------------|
| `ixia_save_config` | Save config to .ixncfg file |
| `ixia_load_config` | Load config from .ixncfg file |

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Network access to the IxNetwork Windows GUI machine

### Install

```bash
# Clone or copy the project
cd IXIA_MCP

# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### IDE Configuration (Cursor / Claude Code / Windsurf)

Add the IXIA MCP server to your IDE's MCP configuration. The IxNetwork connection details are set once here — agents never need to specify them manually.

**Cursor** — `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ixia": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/IXIA_MCP",
        "ixia-mcp",
        "--ixia-host", "10.x.x.x",
        "--ixia-port", "11009",
        "--ixia-session-id", "1"
      ]
    }
  }
}
```

**Claude Code** — `~/.claude/settings.json` or project `.mcp.json`:

```json
{
  "mcpServers": {
    "ixia": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/IXIA_MCP",
        "ixia-mcp",
        "--ixia-host", "10.x.x.x",
        "--ixia-port", "11009",
        "--ixia-session-id", "1"
      ]
    }
  }
}
```

Replace `/path/to/IXIA_MCP` with the actual path and `10.x.x.x` with your IxNetwork API server IP.

#### All CLI options

| Flag | Description | Default |
|------|-------------|---------|
| `--ixia-host` | IxNetwork API server IP | `IXIA_HOST` env var or `127.0.0.1` |
| `--ixia-port` | REST API port | `IXIA_PORT` env var or `11009` |
| `--ixia-session-id` | Session ID to attach to | `IXIA_SESSION_ID` env var or `1` |
| `--ixia-user` | Username | `IXIA_USER` env var or `admin` |
| `--ixia-password` | Password | `IXIA_PASSWORD` env var or `admin` |
| `--transport` | `stdio` (default) or `streamable-http` | `stdio` |
| `--server-port` | HTTP listen port (only for `streamable-http`) | `8080` |

### Alternative: Shared HTTP Server

For a shared server that multiple users connect to over the network:

```bash
uv run ixia-mcp --transport streamable-http --ixia-host 10.x.x.x --ixia-port 11009
```

Then in each user's IDE config:

```json
{
  "mcpServers": {
    "ixia": {
      "url": "http://<server-ip>:8080/mcp"
    }
  }
}
```

## Usage Example

Once configured, an AI agent in Cursor can:

1. **Connect** to IxNetwork:
   > "Connect to IxNetwork at 10.36.74.26 session 1"
   
   The agent calls `ixia_connect` and receives a `connection_id`.

2. **Query** the session:
   > "Show me all ports and their status"
   
   The agent calls `ixia_list_ports` with the `connection_id`.

3. **Start protocols and traffic**:
   > "Start all protocols and then start traffic"
   
   The agent calls `ixia_start_protocols` then `ixia_start_traffic`.

4. **Check statistics**:
   > "Show me the traffic statistics — any packet loss?"
   
   The agent calls `ixia_get_traffic_statistics` and interprets the results.

5. **Stop and disconnect**:
   > "Stop traffic and disconnect"
   
   The agent calls `ixia_stop_traffic` then `ixia_disconnect`.

## Project Structure

```
IXIA_MCP/
├── pyproject.toml              # Project config and dependencies
├── README.md                   # This file
└── ixia_mcp/
    ├── __init__.py
    ├── server.py               # FastMCP server, CLI args, entry point
    ├── client.py               # IxNetwork connection manager
    ├── models.py               # Pydantic input models
    └── tools/
        ├── __init__.py
        ├── session.py          # connect, disconnect, get_session_info
        ├── ports.py            # list, status, add, release, remove ports
        ├── topology.py         # topologies + device groups CRUD, protocol start/stop
        ├── protocols.py        # add/remove/configure protocol stacks
        ├── traffic.py          # traffic items CRUD, generate, start/stop, tracking
        ├── statistics.py       # port, traffic, flow statistics
        └── config.py           # save/load IxNetwork config files
```
