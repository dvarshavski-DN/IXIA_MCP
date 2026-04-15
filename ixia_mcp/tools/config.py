"""Config management tools: save and load IxNetwork configurations."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ixia_mcp.models import SaveConfigInput, LoadConfigInput

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ixia_mcp.client import ConnectionManager


def _handle_error(e: Exception) -> str:
    return f"Error: {type(e).__name__}: {e}"


def register(mcp: "FastMCP", manager: "ConnectionManager") -> None:
    """Register config management tools."""

    @mcp.tool(
        name="ixia_save_config",
        annotations={
            "title": "Save IxNetwork Config",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_save_config(params: SaveConfigInput) -> str:
        """Save the current IxNetwork configuration to a file.

        Saves as an .ixncfg file on the IxNetwork API server machine.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                from ixnetwork_restpy.files import Files
                conn.ixnetwork.SaveAs(Files(params.file_path))
                return None

            result = await asyncio.to_thread(_run)

            if result:
                return f"Error: {result}"
            return f"Configuration saved to `{params.file_path}`."

        except Exception as e:
            return _handle_error(e)

    @mcp.tool(
        name="ixia_load_config",
        annotations={
            "title": "Load IxNetwork Config",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ixia_load_config(params: LoadConfigInput) -> str:
        """Load an IxNetwork configuration from a file.

        Replaces the current session configuration with the contents of the
        .ixncfg file. All existing topologies, traffic items, etc. will be
        replaced.

        Returns:
            str: Confirmation or error.
        """
        try:
            def _run():
                conn = manager.get(params.connection_id)
                from ixnetwork_restpy.files import Files
                conn.ixnetwork.NewConfig()
                conn.ixnetwork.LoadConfig(Files(params.file_path, local_file=False))
                return None

            result = await asyncio.to_thread(_run)

            if result:
                return f"Error: {result}"
            return f"Configuration loaded from `{params.file_path}`."

        except Exception as e:
            return _handle_error(e)
