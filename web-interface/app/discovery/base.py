from abc import ABC, abstractmethod
from typing import List
from app.core.models import ServerInfo

class IServerDiscoverer(ABC):
    @abstractmethod
    def discover(self) -> List[ServerInfo]:
        """Discover all MCP servers."""
        pass 