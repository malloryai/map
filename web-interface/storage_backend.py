#!/usr/bin/env python3
"""
Pluggable Storage Backend Interface
Provides abstract interface for different storage backends (YAML, SQLite, PostgreSQL, etc.)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass
import json
import logging

# Import the existing data models
from app.core.models import ServerInfo, VirtualServer

logger = logging.getLogger(__name__)


@dataclass
class CredentialInfo:
    """Information about stored credentials."""
    key: str
    value: str  # Will be encrypted in storage
    scope: str  # 'global', 'server:<name>', 'virtual:<name>'
    description: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StorageConfig:
    """Configuration for storage backends."""
    backend_type: str  # 'yaml', 'sqlite', 'postgresql'
    connection_string: str = ""
    backup_enabled: bool = True
    backup_count: int = 5
    encryption_enabled: bool = True
    validation_enabled: bool = True


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    # Server Management
    @abstractmethod
    def get_servers(self) -> List[ServerInfo]:
        """Retrieve all servers from storage."""
        pass
    
    @abstractmethod
    def get_server(self, name: str) -> Optional[ServerInfo]:
        """Retrieve a specific server by name."""
        pass
    
    @abstractmethod
    def save_server(self, server: ServerInfo) -> bool:
        """Save or update a server. Returns True on success."""
        pass
    
    @abstractmethod
    def delete_server(self, name: str) -> bool:
        """Delete a server. Returns True on success."""
        pass
    
    # Virtual Server Management
    @abstractmethod
    def get_virtual_servers(self) -> List[VirtualServer]:
        """Retrieve all virtual servers from storage."""
        pass
    
    @abstractmethod
    def get_virtual_server(self, name: str) -> Optional[VirtualServer]:
        """Retrieve a specific virtual server by name."""
        pass
    
    @abstractmethod
    def save_virtual_server(self, virtual_server: VirtualServer) -> bool:
        """Save or update a virtual server. Returns True on success."""
        pass
    
    @abstractmethod
    def delete_virtual_server(self, name: str) -> bool:
        """Delete a virtual server. Returns True on success."""
        pass
    
    # Credential Management
    @abstractmethod
    def get_credentials(self, scope: str = "global") -> List[CredentialInfo]:
        """Retrieve credentials for a specific scope."""
        pass
    
    @abstractmethod
    def get_credential(self, key: str, scope: str = "global") -> Optional[CredentialInfo]:
        """Retrieve a specific credential."""
        pass
    
    @abstractmethod
    def save_credential(self, credential: CredentialInfo) -> bool:
        """Save or update a credential. Returns True on success."""
        pass
    
    @abstractmethod
    def delete_credential(self, key: str, scope: str = "global") -> bool:
        """Delete a credential. Returns True on success."""
        pass
    
    # Configuration Management
    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value."""
        pass
    
    @abstractmethod
    def save_config(self, key: str, value: Any) -> bool:
        """Save a configuration value. Returns True on success."""
        pass
    
    @abstractmethod
    def delete_config(self, key: str) -> bool:
        """Delete a configuration value. Returns True on success."""
        pass
    
    # Backup and Maintenance
    @abstractmethod
    def backup(self, backup_path: Optional[Path] = None) -> bool:
        """Create a backup of the storage. Returns True on success."""
        pass
    
    @abstractmethod
    def restore(self, backup_path: Path) -> bool:
        """Restore from a backup. Returns True on success."""
        pass
    
    @abstractmethod
    def validate(self) -> Dict[str, Any]:
        """Validate storage integrity. Returns validation results."""
        pass
    
    @abstractmethod
    def migrate_from(self, other_backend: 'StorageBackend') -> bool:
        """Migrate data from another backend. Returns True on success."""
        pass
    
    # Utility Methods
    def health_check(self) -> Dict[str, Any]:
        """Check the health of the storage backend."""
        try:
            # Basic connectivity test
            servers = self.get_servers()
            virtual_servers = self.get_virtual_servers()
            
            return {
                "status": "healthy",
                "backend_type": self.config.backend_type,
                "servers_count": len(servers),
                "virtual_servers_count": len(virtual_servers),
                "last_check": "now"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend_type": self.config.backend_type,
                "error": str(e),
                "last_check": "now"
            }


class StorageError(Exception):
    """Base exception for storage-related errors."""
    pass


class ValidationError(StorageError):
    """Exception raised when data validation fails."""
    pass


class MigrationError(StorageError):
    """Exception raised during data migration."""
    pass


class BackupError(StorageError):
    """Exception raised during backup operations."""
    pass 