from typing import Dict
import logging

from app.core.models import ServerInfo
from app.proxy.base import ITransportHandler

logger = logging.getLogger(__name__)

class ToolProxyRouter:
    """Routes tool execution requests to the appropriate transport handler."""

    def __init__(self, transport_handlers: Dict[str, ITransportHandler]):
        self.handlers = transport_handlers

    def list_tools(self, server: ServerInfo) -> list:
        """
        List tools by routing the request to the correct handler based on the server's transport.
        """
        handler = self.handlers.get(server.transport)
        if not handler:
            message = f"Unsupported transport '{server.transport}' for proxying."
            logger.error(message)
            return []
        
        return handler.proxy_list_tools(server)

    def get_tool(self, server: ServerInfo, tool_name: str) -> dict:
        """
        Get a single tool's details by listing all tools and finding the one with the matching name.
        """
        all_tools = self.list_tools(server)
        return next((tool for tool in all_tools if tool.get('name') == tool_name), None)

    def execute_tool(self, server: ServerInfo, tool_name: str, arguments: dict) -> dict:
        """
        Execute a tool by routing the request to the correct handler based on the server's transport.
        """
        handler = self.handlers.get(server.transport)
        if not handler:
            message = f"Unsupported transport '{server.transport}' for proxying."
            logger.error(message)
            return {'status': 'error', 'message': message}
        
        return handler.proxy_request(server, tool_name, arguments) 