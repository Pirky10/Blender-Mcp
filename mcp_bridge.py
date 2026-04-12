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
    instructions="""You are connected to a Blender 3D instance through this MCP bridge.

IMPORTANT USAGE RULES:
1. ALWAYS call 'list_blender_tools' first to discover available Blender tools.
2. To invoke any Blender tool, use 'call_blender_tool' and pass the Blender
   tool name (e.g. 'get_scene_info', 'create_mesh_object') as the 'name' parameter.
3. The 'name' parameter must be one of the tool names returned by 'list_blender_tools'.
   Do NOT pass 'call_blender_tool' or 'list_blender_tools' as the 'name' — those
   are bridge tools, not Blender tools.

EXAMPLE — Get scene info:
    call_blender_tool(name="get_scene_info", arguments="{}")

EXAMPLE — Create a cube:
    call_blender_tool(name="create_mesh_object", arguments='{"name": "MyCube", "type": "CUBE", "location": [0, 0, 0]}')

EXAMPLE — Delete objects:
    call_blender_tool(name="delete_objects", arguments='{"names": ["Cube"]}')
""",
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


@mcp.tool()
def list_blender_tools() -> str:
    """List all tools available on the Blender MCP server.

    Call this FIRST to discover what Blender tools you can invoke.
    Returns the name and description of every available tool.
    Use the returned tool names as the 'name' parameter in call_blender_tool.
    """
    try:
        data = _blender_get("/mcp/list_tools")
        tools = data.get("tools", [])
        lines = [f"Available Blender tools ({len(tools)} total):\n"]
        for t in tools:
            name = t.get("name", "?")
            desc = t.get("description", "")
            params = t.get("inputSchema", t.get("input_schema", {}))
            required = params.get("required", [])
            props = params.get("properties", {})
            param_summary = ", ".join(
                f"{p}{'*' if p in required else ''}"
                for p in props.keys()
            )
            lines.append(f"  - {name}({param_summary}): {desc}")
        return "\n".join(lines)
    except httpx.ConnectError:
        return "Error: Cannot connect to Blender MCP server at http://localhost:8000. Make sure Blender is open and the MCP Server is started (N-Panel > MCP Server > Start Server)."
    except Exception as e:
        return f"Error listing tools: {e}"


@mcp.tool()
def call_blender_tool(name: str, arguments: str = "{}") -> str:
    """Invoke a Blender tool by name. This is the main way to control Blender.

    IMPORTANT: 'name' must be a BLENDER tool name like 'get_scene_info',
    'create_mesh_object', 'transform_object', etc. Get valid names from
    list_blender_tools. Do NOT pass 'call_blender_tool' as the name.

    Args:
        name: The exact Blender tool name to invoke. Examples:
              'get_scene_info', 'create_mesh_object', 'create_material',
              'transform_object', 'delete_objects', 'render_image'.
              Must be one of the names returned by list_blender_tools.
        arguments: A JSON string of arguments for the tool. Defaults to '{}'.
                   Example: '{"name": "MyCube", "type": "CUBE"}'

    Returns:
        JSON string with the tool result or error details.

    Usage examples:
        call_blender_tool(name="get_scene_info", arguments="{}")
        call_blender_tool(name="create_mesh_object", arguments='{"name": "Sphere", "type": "UV_SPHERE"}')
        call_blender_tool(name="create_light", arguments='{"name": "Sun", "type": "SUN"}')
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON in arguments: {e}"

    try:
        result = _blender_post(f"/mcp/invoke/{name}", args)
        return json.dumps(result, indent=2, default=str)
    except httpx.ConnectError:
        return "Error: Cannot connect to Blender MCP server at http://localhost:8000. Make sure Blender is open and the MCP Server is started."
    except httpx.HTTPStatusError as e:
        return f"Error calling {name}: HTTP {e.response.status_code} — {e.response.text}"
    except Exception as e:
        return f"Error calling {name}: {e}"


@mcp.tool()
def blender_health_check() -> str:
    """Check if the Blender MCP server is running and responsive.
    Returns the server status and number of registered tools.
    """
    try:
        data = _blender_get("/health")
        return json.dumps(data, indent=2)
    except httpx.ConnectError:
        return "Blender MCP server is NOT running. Ask the user to open Blender and start the MCP server from the N-Panel."
    except Exception as e:
        return f"Health check failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
