import requests
import logging
from datetime import datetime
import json

from app.core.models import ServerInfo
from app.proxy.base import ITransportHandler

logger = logging.getLogger(__name__)

class HttpTransportHandler(ITransportHandler):
    """Handles tool execution proxying over HTTP."""

    def proxy_list_tools(self, server: ServerInfo) -> list:
        """Proxy a tools/list request to an HTTP-based MCP server."""
        try:
            base_url = server.health_check_url or f"http://localhost:{server.port}"
            if not base_url.startswith('http'):
                base_url = f"http://{base_url}"

            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"list_tools_{datetime.now().timestamp()}",
                "method": "tools/list",
                "params": {}
            }

            response = requests.post(
                f"{base_url}/mcp",
                json=mcp_request,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            result = response.json()

            if 'result' in result:
                tool_data = result['result']
                # The actual list of tools is nested inside the 'tools' key.
                if isinstance(tool_data, dict):
                    return tool_data.get('tools', [])
                
                logger.error(f"MCP result for tools/list was not a dictionary: {tool_data}")
                return []
            elif 'error' in result:
                logger.error(f"MCP server {server.name} returned an error for tools/list: {result['error']}")
                return []
            else:
                logger.error(f"Invalid tools/list response from server {server.name}")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP proxy error for {server.name} during tools/list: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in HTTP proxy for {server.name} during tools/list: {e}")
            return []

    def proxy_request(self, server: ServerInfo, tool_name: str, arguments: dict) -> dict:
        """Proxy request to an HTTP-based MCP server."""
        try:
            base_url = server.health_check_url or f"http://localhost:{server.port}"
            if not base_url.startswith('http'):
                base_url = f"http://{base_url}"
            
            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"{tool_name}_{datetime.now().timestamp()}",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments}
            }
            
            response = requests.post(
                f"{base_url}/mcp",
                json=mcp_request,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            result = response.json()

            if 'result' in result:
                return {'status': 'success', 'result': result['result']}
            elif 'error' in result:
                return {'status': 'error', 'message': result.get('error', 'Unknown error')}
            else:
                return {'status': 'error', 'message': 'Invalid response from server'}

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP proxy error for {server.name}: {e}")
            return {'status': 'error', 'message': f'HTTP proxy error: {str(e)}'}
        except Exception as e:
            logger.error(f"Unexpected error in HTTP proxy for {server.name}: {e}")
            return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'} 