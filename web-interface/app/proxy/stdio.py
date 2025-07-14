import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

from app.core.models import ServerInfo
from app.proxy.base import ITransportHandler

logger = logging.getLogger(__name__)

class StdioTransportHandler(ITransportHandler):
    """Handles tool execution proxying over stdio."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def proxy_list_tools(self, server: ServerInfo) -> list:
        """Proxy a tools/list request to a stdio-based MCP server."""
        try:
            cmd = self._build_command(server)
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.workspace_root
            )
            
            requests_data = self._build_list_tools_mcp_request()
            stdout, stderr = process.communicate(input=requests_data, timeout=30)
            
            if process.returncode != 0:
                logger.error(f"Stdio server '{server.name}' failed on tools/list with code {process.returncode}: {stderr}")
                return []
            
            return self._parse_list_tools_mcp_response(stdout)

        except subprocess.TimeoutExpired:
            logger.error(f"Stdio server '{server.name}' timed out during tools/list.")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in stdio proxy for {server.name} during tools/list: {e}")
            return []

    def proxy_request(self, server: ServerInfo, tool_name: str, arguments: dict) -> dict:
        """Proxy request to a stdio-based MCP server."""
        try:
            cmd = self._build_command(server)
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.workspace_root
            )
            
            requests_data = self._build_mcp_requests(tool_name, arguments)
            stdout, stderr = process.communicate(input=requests_data, timeout=30)
            
            if process.returncode != 0:
                logger.error(f"Stdio server '{server.name}' failed with code {process.returncode}: {stderr}")
                return {'status': 'error', 'message': f'MCP server failed: {stderr}'}
            
            return self._parse_mcp_response(stdout)

        except subprocess.TimeoutExpired:
            logger.error(f"Stdio server '{server.name}' timed out.")
            return {'status': 'error', 'message': 'Tool execution timed out'}
        except Exception as e:
            logger.error(f"Unexpected error in stdio proxy for {server.name}: {e}")
            return {'status': 'error', 'message': f'An unexpected stdio proxy error occurred: {str(e)}'}

    def _build_command(self, server: ServerInfo) -> list[str]:
        """Build the execution command for the stdio server."""
        if not server.command:
            raise ValueError(f"No command specified for stdio server '{server.name}'")
        
        cmd = server.command.copy()
        # Resolve relative script path to be absolute
        if len(cmd) > 1 and not Path(cmd[1]).is_absolute():
            script_path = self.workspace_root / cmd[1]
            if not script_path.exists():
                raise FileNotFoundError(f"Server script not found for '{server.name}' at {script_path}")
            cmd[1] = str(script_path.resolve())
            
        return cmd

    def _build_list_tools_mcp_request(self) -> str:
        """Build the sequence of JSON-RPC messages for a tools/list request."""
        init_request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "mcp-proxy"}}
        }
        initialized_notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        list_tools_request = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
        }
        
        return (
            json.dumps(init_request) + "\n" +
            json.dumps(initialized_notification) + "\n" +
            json.dumps(list_tools_request) + "\n"
        )

    def _build_mcp_requests(self, tool_name: str, arguments: dict) -> str:
        """Build the sequence of JSON-RPC messages for the stdio server."""
        init_request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "mcp-proxy"}}
        }
        initialized_notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        tool_request = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        
        return (
            json.dumps(init_request) + "\n" +
            json.dumps(initialized_notification) + "\n" +
            json.dumps(tool_request) + "\n"
        )

    def _parse_list_tools_mcp_response(self, stdout: str) -> list:
        """Parse the stdout from the MCP server to find the tools/list response."""
        for line in stdout.strip().split('\n'):
            if not line.strip():
                continue
            try:
                response = json.loads(line)
                if response.get('id') == 2:  # Corresponds to the list_tools_request id
                    if 'error' in response:
                        logger.error(f"MCP server returned an error for tools/list: {response['error']}")
                        return []
                    
                    result = response.get('result', {})
                    # The actual list of tools is nested inside the 'tools' key.
                    return result.get('tools', [])
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode JSON response line: {line}")
                continue
        
        logger.error('No valid tools/list response received from MCP server')
        return []

    def _parse_mcp_response(self, stdout: str) -> dict:
        """Parse the stdout from the MCP server to find the tool call response."""
        for line in stdout.strip().split('\n'):
            if not line.strip():
                continue
            try:
                response = json.loads(line)
                if response.get('id') == 2:  # Corresponds to the tool_request id
                    if 'error' in response:
                        return {'status': 'error', 'message': response['error'].get('message', 'Tool execution failed')}
                    return {'status': 'success', 'result': response.get('result', {})}
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode JSON response line: {line}")
                continue
        
        return {'status': 'error', 'message': 'No valid tool response received from MCP server'} 