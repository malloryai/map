#!/usr/bin/env python3
"""
MCP Server with stdio transport
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
from importlib.metadata import version as pkg_version

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent

from dotenv import load_dotenv

from internal_tool_executor import InternalToolExecutor

load_dotenv()

SERVER_ROOT = Path(__file__).parent.resolve()
WORKSPACE_ROOT = SERVER_ROOT.parent.parent
SERVER_NAME = "mallory-intel-server"

server = Server(SERVER_NAME)
executor = InternalToolExecutor(workspace_root=WORKSPACE_ROOT, server_name=SERVER_NAME)

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available tools from the executor, ensuring the correct response format."""
    discovered_tools = []
    for tool_config in executor.get_tools():
        properties = {}
        required = []
        for input_def in tool_config.get("inputs", []):
            param_schema = {"type": input_def.get("type", "string")}
            if "description" in input_def:
                param_schema["description"] = input_def["description"]
            properties[input_def["name"]] = param_schema
            if input_def.get("required", False):
                required.append(input_def["name"])

        inputSchema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        tool_obj = Tool(
            name=tool_config["name"],
            description=tool_config["description"],
            inputSchema=inputSchema,
            data=tool_config
        )
        discovered_tools.append(tool_obj)

    return discovered_tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool using the executor."""
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"Received call for tool '{name}' with arguments: {arguments}")
    try:
        result = executor.call_tool(tool_name=name, params=arguments)
        
        if isinstance(result, (dict, list, str, int, float, bool, type(None))):
            content = json.dumps(result, indent=2)
        else:
            content = str(result)
            
        return [TextContent(type='text', text=content)]
    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
        return [TextContent(type='text', text=f"Error executing tool '{name}': {e}")]


async def main():
    """Start the MCP server using the stdio transport."""
    from mcp.server.stdio import stdio_server

    capabilities = server.get_capabilities(
        notification_options=NotificationOptions(),
        experimental_capabilities={}
    )

    init_options = InitializationOptions(
        server_name=SERVER_NAME,
        server_version="0.1.0",  # Replace with your server's version
        mcp_version=pkg_version("fastmcp"),
        capabilities=capabilities,
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
