#!/usr/bin/env python3
"""
Blender MCP Bridge — stdio MCP server that proxies to the Blender HTTP server.

This script is launched by MCP clients (like Antigravity) as a stdio server.
It forwards tool list/call requests to the FastAPI server running inside Blender
at http://localhost:8000.

Usage via uvx:
    uvx --from mcp --with httpx mcp run mcp_bridge.py
"""

import json
import httpx
from mcp.server.fastmcp import FastMCP

BLENDER_URL = "http://localhost:8000"

mcp = FastMCP(
    "Blender MCP Bridge",
    dependencies=["httpx"],
)


def _blender_get(path: str) -> dict:
    """Synchronous GET to the Blender HTTP server."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{BLENDER_URL}{path}")
        resp.raise_for_status()
        return resp.json()


def _blender_post(path: str, payload: dict | None = None) -> dict:
    """Synchronous POST to the Blender HTTP server."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{BLENDER_URL}{path}", json=payload or {})
        resp.raise_for_status()
        return resp.json()


# We dynamically fetch and register tools from the Blender server at startup.
# But since FastMCP needs tools defined at import time, we use a single
# dispatcher tool that forwards any call.

@mcp.tool()
def list_blender_tools() -> str:
    """List all tools available on the Blender MCP server.
    Call this first to discover what tools are available."""
    try:
        data = _blender_get("/mcp/list_tools")
        tools = data.get("tools", [])
        lines = [f"Available Blender tools ({len(tools)} total):\n"]
        for t in tools:
            name = t.get("name", "?")
            desc = t.get("description", "")
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)
    except httpx.ConnectError:
        return "Error: Cannot connect to Blender MCP server at http://localhost:8000. Make sure Blender is open and the MCP Server is started (N-Panel > MCP Server > Start Server)."
    except Exception as e:
        return f"Error listing tools: {e}"


@mcp.tool()
def call_blender_tool(tool_name: str, arguments: str = "{}") -> str:
    """Call a specific tool on the Blender MCP server.

    Parameters:
    - tool_name: The exact name of the Blender tool to invoke (from list_blender_tools)
    - arguments: JSON string of arguments to pass to the tool. Example: '{"name": "Cube", "type": "CUBE"}'
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON in arguments: {e}"

    try:
        result = _blender_post(f"/mcp/invoke/{tool_name}", args)
        return json.dumps(result, indent=2, default=str)
    except httpx.ConnectError:
        return "Error: Cannot connect to Blender MCP server at http://localhost:8000. Make sure Blender is open and the MCP Server is started."
    except httpx.HTTPStatusError as e:
        return f"Error calling {tool_name}: HTTP {e.response.status_code} — {e.response.text}"
    except Exception as e:
        return f"Error calling {tool_name}: {e}"


@mcp.tool()
def blender_health_check() -> str:
    """Check if the Blender MCP server is running and responsive."""
    try:
        data = _blender_get("/health")
        return json.dumps(data, indent=2)
    except httpx.ConnectError:
        return "Blender MCP server is NOT running. Ask the user to open Blender and start the MCP server from the N-Panel."
    except Exception as e:
        return f"Health check failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
