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

## Available Tools (16)

### Session Management
| Tool | Description |
|------|-------------|
| `ixia_connect` | Connect to an IxNetwork session (returns `connection_id`) |
| `ixia_disconnect` | Disconnect from a session |
| `ixia_get_session_info` | Get session details (build, port/topology/traffic counts) |

### Ports (read-only)
| Tool | Description |
|------|-------------|
| `ixia_list_ports` | List all virtual ports with state and assignment |
| `ixia_get_port_status` | Detailed status for one or all ports |

### Topologies & Protocols
| Tool | Description |
|------|-------------|
| `ixia_list_topologies` | List topologies with device group counts |
| `ixia_get_topology_details` | Device groups, protocols per topology |
| `ixia_get_protocol_status` | Protocol session status (up/down/not started) |
| `ixia_start_protocols` | Start all or per-topology protocols |
| `ixia_stop_protocols` | Stop all or per-topology protocols |

### Traffic
| Tool | Description |
|------|-------------|
| `ixia_list_traffic_items` | List traffic items with state and type |
| `ixia_get_traffic_item_details` | Frame rate, transmission control, frame size |
| `ixia_start_traffic` | Apply config and start traffic |
| `ixia_stop_traffic` | Stop traffic |

### Statistics (read-only)
| Tool | Description |
|------|-------------|
| `ixia_get_port_statistics` | Port TX/RX counters and rates |
| `ixia_get_traffic_statistics` | Traffic item level counters and loss |
| `ixia_get_flow_statistics` | Per-flow granular statistics |

## Setup (Server Side)

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

### Environment Variables (optional defaults)

Set these so agents don't need to pass credentials every time:

```bash
export IXIA_HOST="10.x.x.x"        # IxNetwork API server IP
export IXIA_PORT="11009"            # REST API port (default: 11009 for Windows GUI)
export IXIA_SESSION_ID="1"          # Default session ID
export IXIA_USER="admin"            # Username
export IXIA_PASSWORD="admin"        # Password
```

### Run the Server

```bash
# Using uv
uv run ixia-mcp

# Or directly
python -m ixia_mcp.server

# Or using the installed script
ixia-mcp
```

The server starts on `http://0.0.0.0:8080/mcp` with Streamable HTTP transport.

## Setup (Client Side — Cursor)

Each user adds this to their Cursor MCP configuration (Settings > MCP Servers, or `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "ixia": {
      "url": "http://<server-ip>:8080/mcp"
    }
  }
}
```

Replace `<server-ip>` with the IP or hostname of the machine running the MCP server.

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
    ├── server.py               # FastMCP server, lifespan, entry point
    ├── client.py               # IxNetwork connection manager
    ├── models.py               # Pydantic input models
    └── tools/
        ├── __init__.py
        ├── session.py          # connect, disconnect, get_session_info
        ├── ports.py            # list_ports, get_port_status
        ├── topology.py         # list/get topologies, protocol status, start/stop
        ├── traffic.py          # list/get traffic items, start/stop traffic
        └── statistics.py       # port, traffic, flow statistics
```
