from abc import ABC, abstractmethod
from app.core.models import ServerInfo

class ITransportHandler(ABC):
    """An abstract base class for handling tool execution proxying over a specific transport."""

    @abstractmethod
    def proxy_list_tools(self, server: ServerInfo) -> list:
        """Proxy a tools/list request to the underlying server."""
        pass

    @abstractmethod
    def proxy_request(self, server: ServerInfo, tool_name: str, arguments: dict) -> dict:
        """Proxy a tool execution request to the underlying server."""
        pass 