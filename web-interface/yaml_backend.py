#!/usr/bin/env python3
"""
Enhanced YAML Storage Backend
Provides robust YAML-based storage with validation, atomic writes, and backup functionality
"""
import os
import yaml
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict
import logging

from storage_backend import StorageBackend, StorageConfig, CredentialInfo, StorageError, ValidationError, BackupError
from app.core.models import ServerInfo, VirtualServer

logger = logging.getLogger(__name__)


class YAMLBackend(StorageBackend):
    """Enhanced YAML storage backend with validation and atomic writes."""
    
    def __init__(self, config: StorageConfig, workspace_root: Path):
        super().__init__(config)
        self.workspace_root = workspace_root
        self.registry_path = workspace_root / "registry"
        self.virtual_servers_path = workspace_root / "servers-configs"
        self.credentials_path = workspace_root / "credentials"
        self.config_path = workspace_root / "storage-config.yaml"
        self.backup_path = workspace_root / "backups"
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        self.registry_path.mkdir(exist_ok=True)
        self.virtual_servers_path.mkdir(exist_ok=True)
        self.credentials_path.mkdir(exist_ok=True)
        if self.config.backup_enabled:
            self.backup_path.mkdir(exist_ok=True)
    
    def _atomic_write(self, file_path: Path, data: Any, format: str = "yaml") -> bool:
        """Write data atomically to prevent corruption."""
        try:
            # Create backup if file exists
            if file_path.exists() and self.config.backup_enabled:
                self._create_file_backup(file_path)
            
            # Write to temporary file first
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{format}', delete=False) as tmp_file:
                if format == "yaml":
                    yaml.dump(data, tmp_file, default_flow_style=False, sort_keys=False)
                elif format == "json":
                    json.dump(data, tmp_file, indent=2)
                
                tmp_path = Path(tmp_file.name)
            
            # Atomic rename
            shutil.move(str(tmp_path), str(file_path))
            self.logger.debug(f"Atomically wrote {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing {file_path}: {e}")
            # Clean up temp file if it exists
            if 'tmp_path' in locals() and tmp_path.exists():
                tmp_path.unlink()
            return False
    
    def _create_file_backup(self, file_path: Path):
        """Create a timestamped backup of a file."""
        if not file_path.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_path / f"{file_path.stem}_{timestamp}{file_path.suffix}"
        
        try:
            shutil.copy2(file_path, backup_file)
            self.logger.debug(f"Created backup: {backup_file}")
            
            # Clean up old backups
            self._cleanup_old_backups(file_path.stem, file_path.suffix)
            
        except Exception as e:
            self.logger.warning(f"Failed to create backup for {file_path}: {e}")
    
    def _cleanup_old_backups(self, file_stem: str, file_suffix: str):
        """Remove old backup files, keeping only the most recent ones."""
        if not self.config.backup_enabled:
            return
        
        pattern = f"{file_stem}_*{file_suffix}"
        backup_files = list(self.backup_path.glob(pattern))
        backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Keep only the most recent backups
        for old_backup in backup_files[self.config.backup_count:]:
            try:
                old_backup.unlink()
                self.logger.debug(f"Removed old backup: {old_backup}")
            except Exception as e:
                self.logger.warning(f"Failed to remove old backup {old_backup}: {e}")
    
    def _validate_server(self, server_data: Dict[str, Any]) -> bool:
        """Validate server data structure."""
        if not self.config.validation_enabled:
            return True
        
        required_fields = ["name", "type", "transport"]
        for field in required_fields:
            if field not in server_data:
                raise ValidationError(f"Missing required field: {field}")
        
        valid_types = ["local", "remote", "github"]
        if server_data["type"] not in valid_types:
            raise ValidationError(f"Invalid server type: {server_data['type']}")
        
        valid_transports = ["stdio", "http", "sse"]
        if server_data["transport"] not in valid_transports:
            raise ValidationError(f"Invalid transport: {server_data['transport']}")
        
        return True
    
    def _validate_virtual_server(self, vs_data: Dict[str, Any]) -> bool:
        """Validate virtual server data structure."""
        if not self.config.validation_enabled:
            return True
        
        required_fields = ["name", "description", "selected_tools"]
        for field in required_fields:
            if field not in vs_data:
                raise ValidationError(f"Missing required field: {field}")
        
        return True
    
    # Server Management Implementation
    def get_servers(self) -> List[ServerInfo]:
        """Retrieve all servers from registry YAML files."""
        servers = []
        
        if not self.registry_path.exists():
            return servers
        
        for file_path in self.registry_path.glob("*.yaml"):
            try:
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                if data and self._validate_server(data):
                    # Convert to ServerInfo object
                    server = ServerInfo(
                        name=data.get("name", ""),
                        path=data.get("path", ""),
                        description=data.get("description", ""),
                        transport=data.get("transport", "stdio"),
                        command=data.get("command", []),
                        tools=data.get("tools", []),
                        status=data.get("status", "discovered"),
                        discovery_method=data.get("discovery_method", "registry"),
                        last_discovered=data.get("last_discovered", datetime.now().isoformat()),
                        port=data.get("port"),
                        health_check_url=data.get("health_check_url")
                    )
                    servers.append(server)
                    
            except Exception as e:
                self.logger.warning(f"Error loading server from {file_path}: {e}")
        
        return servers
    
    def get_server(self, name: str) -> Optional[ServerInfo]:
        """Retrieve a specific server by name."""
        servers = self.get_servers()
        for server in servers:
            if server.name == name:
                return server
        return None
    
    def save_server(self, server: ServerInfo) -> bool:
        """Save or update a server."""
        try:
            # Convert ServerInfo to dict
            server_data = asdict(server)
            
            # Check if this server already exists in registry to preserve fields
            registry_file = self.registry_path / f"{server.name}.yaml"
            if registry_file.exists():
                # Load existing registry data to preserve fields like 'type'
                with open(registry_file, 'r') as f:
                    existing_data = yaml.safe_load(f) or {}
                
                # Merge existing data with new data, preserving registry-specific fields
                merged_data = existing_data.copy()
                
                # Update with new data from ServerInfo, but preserve certain fields
                for key, value in server_data.items():
                    if value is not None:  # Only update non-None values
                        merged_data[key] = value
                
                # Ensure required registry fields are present
                if 'type' not in merged_data:
                    merged_data['type'] = 'local'  # Default type
                
                server_data = merged_data
            else:
                # New server, ensure required fields are present
                if 'type' not in server_data:
                    server_data['type'] = 'local'  # Default type
            
            # Validate data
            self._validate_server(server_data)
            
            # Write to registry file
            return self._atomic_write(registry_file, server_data)
            
        except Exception as e:
            self.logger.error(f"Error saving server {server.name}: {e}")
            return False
    
    def delete_server(self, name: str) -> bool:
        """Delete a server."""
        try:
            file_path = self.registry_path / f"{name}.yaml"
            if file_path.exists():
                # Create backup before deletion
                if self.config.backup_enabled:
                    self._create_file_backup(file_path)
                
                file_path.unlink()
                self.logger.info(f"Deleted server: {name}")
                return True
            else:
                self.logger.warning(f"Server {name} not found for deletion")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting server {name}: {e}")
            return False
    
    # Virtual Server Management Implementation
    def get_virtual_servers(self) -> List[VirtualServer]:
        """Retrieve all virtual servers from YAML files."""
        virtual_servers = []
        
        if not self.virtual_servers_path.exists():
            return virtual_servers
        
        for file_path in self.virtual_servers_path.glob("*.yaml"):
            try:
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                if data and self._validate_virtual_server(data):
                    # Convert to VirtualServer object
                    vs = VirtualServer(
                        name=data.get("name", ""),
                        description=data.get("description", ""),
                        selected_tools=data.get("selected_tools", []),
                        rules=data.get("rules", []),
                        created_at=data.get("created_at", datetime.now().isoformat()),
                        updated_at=data.get("updated_at", datetime.now().isoformat()),
                        enabled=data.get("enabled", True),
                        port=data.get("port"),
                        status=data.get("status", "stopped")
                    )
                    virtual_servers.append(vs)
                    
            except Exception as e:
                self.logger.warning(f"Error loading virtual server from {file_path}: {e}")
        
        return virtual_servers
    
    def get_virtual_server(self, name: str) -> Optional[VirtualServer]:
        """Retrieve a specific virtual server by name."""
        virtual_servers = self.get_virtual_servers()
        for vs in virtual_servers:
            if vs.name == name:
                return vs
        return None
    
    def save_virtual_server(self, virtual_server: VirtualServer) -> bool:
        """Save or update a virtual server."""
        try:
            # Convert VirtualServer to dict
            vs_data = asdict(virtual_server)
            vs_data["updated_at"] = datetime.now().isoformat()
            
            # Validate data
            self._validate_virtual_server(vs_data)
            
            # Write to virtual servers file
            file_path = self.virtual_servers_path / f"{virtual_server.name}.yaml"
            return self._atomic_write(file_path, vs_data)
            
        except Exception as e:
            self.logger.error(f"Error saving virtual server {virtual_server.name}: {e}")
            return False
    
    def delete_virtual_server(self, name: str) -> bool:
        """Delete a virtual server."""
        try:
            file_path = self.virtual_servers_path / f"{name}.yaml"
            if file_path.exists():
                # Create backup before deletion
                if self.config.backup_enabled:
                    self._create_file_backup(file_path)
                
                file_path.unlink()
                self.logger.info(f"Deleted virtual server: {name}")
                return True
            else:
                self.logger.warning(f"Virtual server {name} not found for deletion")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting virtual server {name}: {e}")
            return False
    
    # Credential Management Implementation
    def get_credentials(self, scope: str = "global") -> List[CredentialInfo]:
        """Retrieve credentials for a specific scope."""
        credentials = []
        scope_file = self.credentials_path / f"{scope}.yaml"
        
        if scope_file.exists():
            try:
                with open(scope_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                for key, cred_data in data.items():
                    credential = CredentialInfo(
                        key=key,
                        value=cred_data.get("value", ""),
                        scope=scope,
                        description=cred_data.get("description", ""),
                        created_at=cred_data.get("created_at", ""),
                        updated_at=cred_data.get("updated_at", "")
                    )
                    credentials.append(credential)
                    
            except Exception as e:
                self.logger.warning(f"Error loading credentials for scope {scope}: {e}")
        
        return credentials
    
    def get_credential(self, key: str, scope: str = "global") -> Optional[CredentialInfo]:
        """Retrieve a specific credential."""
        credentials = self.get_credentials(scope)
        for cred in credentials:
            if cred.key == key:
                return cred
        return None
    
    def save_credential(self, credential: CredentialInfo) -> bool:
        """Save or update a credential."""
        try:
            scope_file = self.credentials_path / f"{credential.scope}.yaml"
            
            # Load existing credentials
            data = {}
            if scope_file.exists():
                with open(scope_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
            
            # Update credential
            data[credential.key] = {
                "value": credential.value,
                "description": credential.description,
                "created_at": credential.created_at or datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Write atomically
            return self._atomic_write(scope_file, data)
            
        except Exception as e:
            self.logger.error(f"Error saving credential {credential.key}: {e}")
            return False
    
    def delete_credential(self, key: str, scope: str = "global") -> bool:
        """Delete a credential."""
        try:
            scope_file = self.credentials_path / f"{scope}.yaml"
            
            if scope_file.exists():
                with open(scope_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                if key in data:
                    del data[key]
                    return self._atomic_write(scope_file, data)
                else:
                    self.logger.warning(f"Credential {key} not found in scope {scope}")
                    return False
            else:
                self.logger.warning(f"Credential scope {scope} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting credential {key}: {e}")
            return False
    
    # Configuration Management Implementation
    def get_config(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                return data.get(key, default)
            else:
                return default
        except Exception as e:
            self.logger.warning(f"Error loading config {key}: {e}")
            return default
    
    def save_config(self, key: str, value: Any) -> bool:
        """Save a configuration value."""
        try:
            # Load existing config
            data = {}
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
            
            # Update config
            data[key] = value
            
            # Write atomically
            return self._atomic_write(self.config_path, data)
            
        except Exception as e:
            self.logger.error(f"Error saving config {key}: {e}")
            return False
    
    def delete_config(self, key: str) -> bool:
        """Delete a configuration value."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                if key in data:
                    del data[key]
                    return self._atomic_write(self.config_path, data)
                else:
                    self.logger.warning(f"Config {key} not found")
                    return False
            else:
                self.logger.warning(f"Config file not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting config {key}: {e}")
            return False
    
    # Backup and Maintenance Implementation
    def backup(self, backup_path: Optional[Path] = None) -> bool:
        """Create a backup of all storage."""
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.backup_path / f"full_backup_{timestamp}"
            
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Backup registry
            if self.registry_path.exists():
                shutil.copytree(self.registry_path, backup_path / "registry", dirs_exist_ok=True)
            
            # Backup virtual servers
            if self.virtual_servers_path.exists():
                shutil.copytree(self.virtual_servers_path, backup_path / "servers-configs", dirs_exist_ok=True)
            
            # Backup credentials
            if self.credentials_path.exists():
                shutil.copytree(self.credentials_path, backup_path / "credentials", dirs_exist_ok=True)
            
            # Backup config
            if self.config_path.exists():
                shutil.copy2(self.config_path, backup_path / "storage-config.yaml")
            
            self.logger.info(f"Created full backup at {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return False
    
    def restore(self, backup_path: Path) -> bool:
        """Restore from a backup."""
        try:
            if not backup_path.exists():
                raise BackupError(f"Backup path {backup_path} does not exist")
            
            # Restore registry
            registry_backup = backup_path / "registry"
            if registry_backup.exists():
                if self.registry_path.exists():
                    shutil.rmtree(self.registry_path)
                shutil.copytree(registry_backup, self.registry_path)
            
            # Restore virtual servers
            vs_backup = backup_path / "servers-configs"
            if vs_backup.exists():
                if self.virtual_servers_path.exists():
                    shutil.rmtree(self.virtual_servers_path)
                shutil.copytree(vs_backup, self.virtual_servers_path)
            
            # Restore credentials
            cred_backup = backup_path / "credentials"
            if cred_backup.exists():
                if self.credentials_path.exists():
                    shutil.rmtree(self.credentials_path)
                shutil.copytree(cred_backup, self.credentials_path)
            
            # Restore config
            config_backup = backup_path / "storage-config.yaml"
            if config_backup.exists():
                shutil.copy2(config_backup, self.config_path)
            
            self.logger.info(f"Restored from backup {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring backup: {e}")
            return False
    
    def validate(self) -> Dict[str, Any]:
        """Validate storage integrity."""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {}
        }
        
        try:
            # Validate servers
            servers = self.get_servers()
            results["stats"]["servers_count"] = len(servers)
            
            # Validate virtual servers
            virtual_servers = self.get_virtual_servers()
            results["stats"]["virtual_servers_count"] = len(virtual_servers)
            
            # Validate credentials
            credentials = self.get_credentials()
            results["stats"]["credentials_count"] = len(credentials)
            
            # Check for orphaned files
            # ... additional validation logic
            
        except Exception as e:
            results["valid"] = False
            results["errors"].append(str(e))
        
        return results
    
    def migrate_from(self, other_backend: 'StorageBackend') -> bool:
        """Migrate data from another backend."""
        try:
            # Migrate servers
            servers = other_backend.get_servers()
            for server in servers:
                if not self.save_server(server):
                    self.logger.error(f"Failed to migrate server {server.name}")
                    return False
            
            # Migrate virtual servers
            virtual_servers = other_backend.get_virtual_servers()
            for vs in virtual_servers:
                if not self.save_virtual_server(vs):
                    self.logger.error(f"Failed to migrate virtual server {vs.name}")
                    return False
            
            # Migrate credentials
            credentials = other_backend.get_credentials()
            for cred in credentials:
                if not self.save_credential(cred):
                    self.logger.error(f"Failed to migrate credential {cred.key}")
                    return False
            
            self.logger.info("Successfully migrated data from other backend")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during migration: {e}")
            return False 