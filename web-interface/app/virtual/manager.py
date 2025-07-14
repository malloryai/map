#!/usr/bin/env python3
"""
Manages the lifecycle of virtual servers.
"""
import os
import sys
import yaml
import json
import asyncio
import subprocess
import socket
import concurrent.futures
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from app.core.models import IServer, ServerInfo, VirtualServer
from app.discovery.base import IServerDiscoverer


# Add mcp-proxy-server to path to import ToolExecutor
sys.path.append(str(Path(__file__).parent.parent.parent / "mcp-proxy-server"))

try:
    from tool_executor import ToolExecutor
    REAL_TOOL_EXECUTION = True
except ImportError as e:
    print(f"Warning: Could not import real tool executor: {e}")
    REAL_TOOL_EXECUTION = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VirtualServerManager:
    """Manages the lifecycle of virtual servers."""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.virtual_servers_path = workspace_root / "servers-configs"
        self.virtual_servers_path.mkdir(exist_ok=True)
        self.tool_executor = ToolExecutor(workspace_root) if REAL_TOOL_EXECUTION else None

    def create_virtual_server(self, name: str, description: str, selected_tools: List[Dict], selected_prompts: List[str], enabled: bool = True, api_key: str = None) -> VirtualServer:
        """Create and save a new virtual server."""
        # Check for name collisions
        if self.get_virtual_server(name):
            raise ValueError(f"A virtual server with the name '{name}' already exists.")

        virtual_server = VirtualServer(
            name=name,
            description=description,
            selected_tools=selected_tools,
            selected_prompts=selected_prompts,
            rules=[],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            status='ready',  # Ready to be accessed via proxy
            api_key=api_key,
            enabled=enabled
        )
        
        self._save_virtual_server(virtual_server)
        return virtual_server
    
    def list_virtual_servers(self) -> List[VirtualServer]:
        """Load all virtual servers from the configuration directory."""
        virtual_servers = []
        
        for config_file in self.virtual_servers_path.glob("*.yaml"):
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                
                virtual_server = VirtualServer(**config)
                virtual_servers.append(virtual_server)
            except Exception as e:
                logger.warning(f"Error loading virtual server {config_file}: {e}")
        
        return sorted(virtual_servers, key=lambda vs: vs.name)
    
    def get_virtual_server(self, name: str) -> Optional[VirtualServer]:
        """Load a single virtual server by name."""
        config_file = self.virtual_servers_path / f"{name}.yaml"
        
        if not config_file.exists():
            return None
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            return VirtualServer(**config)
        except Exception as e:
            logger.warning(f"Error loading virtual server {name}: {e}")
            return None
    
    def get_server(self, name: str, discoverer: IServerDiscoverer) -> Optional[IServer]:
        """Gets any server (virtual or real) by its name."""
        server = self.get_virtual_server(name)
        if server:
            return server
        
        registry_entries = discoverer.discover()
        return next((entry for entry in registry_entries if entry.name == name), None)

    def update_virtual_server(self, virtual_server: VirtualServer, updates: Dict[str, Any]) -> None:
        """
        Update and save a virtual server dynamically from a dictionary of updates.
        This method iterates through a list of explicitly allowed fields to provide
        a balance of dynamism and security, preventing unwanted updates.
        """
        updatable_fields = [
            "description",
            "enabled",
            "selected_tools",
            "selected_prompts",
            "api_key",
        ]
        
        for key in updatable_fields:
            if key in updates:
                setattr(virtual_server, key, updates[key])

        virtual_server.updated_at = datetime.now().isoformat()
        self._save_virtual_server(virtual_server)
    
    def delete_virtual_server(self, name: str) -> bool:
        """Delete a virtual server by name."""
        config_file = self.virtual_servers_path / f"{name}.yaml"
        
        if config_file.exists():
            config_file.unlink()
            return True
        
        return False

    def _save_virtual_server(self, virtual_server: VirtualServer) -> None:
        """Save a virtual server's configuration to a YAML file."""
        config_file = self.virtual_servers_path / f"{virtual_server.name}.yaml"
        
        with open(config_file, 'w') as f:
            # Convert dataclass to dict, but handle nested dataclasses if any
            data = asdict(virtual_server)
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        # Ensure custom prompts directory exists
        prompts_dir = self.virtual_servers_path / "prompts"
        prompts_dir.mkdir(exist_ok=True)
    
    def get_available_ports(self, start_port: int = 8000, count: int = 10) -> List[int]:
        """
        Get a list of available network ports.
        """
        
        available_ports = []
        for port in range(start_port, start_port + count * 10):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    available_ports.append(port)
                    if len(available_ports) >= count:
                        break
            except OSError:
                continue
        
        return available_ports
    
    # --- Moved from app.py ---

    def fetch_server_capabilities(self, server_name: str, capability_type: str, discoverer: IServerDiscoverer):
        """Fetch capabilities (resources, prompts, templates) from underlying MCP registry entries."""
        try:
            source_server = self.get_server(server_name, discoverer)
            
            if not source_server:
                return []
            
            # For now, we'll read the capabilities directly from the registry entry's tool configs
            # This is a simplified approach - in a full implementation we'd use MCP client calls
            
            if capability_type == 'prompts':
                return self._extract_prompts_from_server(source_server, discoverer)
            elif capability_type == 'resources':
                return self._extract_resources_from_server(source_server) if isinstance(source_server, ServerInfo) else []
            elif capability_type == 'resource_templates':
                return self._extract_resource_templates_from_server(source_server) if isinstance(source_server, ServerInfo) else []
            
            return []
        except Exception as e:
            logger.error(f"Error fetching {capability_type} from {server_name}: {e}")
            return []

    def _extract_prompts_from_server(self, server: IServer, discoverer: IServerDiscoverer):
        """
        Extracts all prompts for a given server, dispatching polymorphically.
        """
        if isinstance(server, VirtualServer):
            return self._get_prompts_for_virtual_server(server, discoverer)
        elif isinstance(server, ServerInfo):
            return self._extract_prompts_from_actual_server(server)
        return []

    def _get_prompts_for_virtual_server(self, server: VirtualServer, discoverer: IServerDiscoverer) -> List[Dict[str, Any]]:
        """Gathers prompts for a virtual server from its constituent parts."""
        prompts = []
        registry_entries = discoverer.discover()
        processed_entries = set()
        
        for tool_config in server.selected_tools:
            source_server_name = tool_config.get('server_name')
            if source_server_name and source_server_name not in processed_entries:
                source_entry = next((entry for entry in registry_entries if entry.name == source_server_name), None)
                if source_entry:
                    prompts.extend(self._extract_prompts_from_actual_server(source_entry))
                    processed_entries.add(source_server_name)
        
        # Add custom prompts for virtual servers
        custom_prompts = self.get_custom_prompts(server.name)
        for custom_prompt in custom_prompts:
            prompts.append({
                'name': custom_prompt['name'],
                'description': custom_prompt['description'],
                'arguments': [
                    {
                        'name': arg['name'],
                        'description': arg['description'],
                        'required': arg.get('required', False)
                    }
                    for arg in custom_prompt.get('arguments', [])
                ]
            })
        return prompts

    def _extract_prompts_from_actual_server(self, server: ServerInfo):
        """Extract prompts from an actual registry entry directory."""
        prompts = []
        try:
            server_dir = self.workspace_root / server.path
            tools_dir = server_dir / "tools"
            
            if tools_dir.exists():
                for tool_dir in tools_dir.iterdir():
                    if tool_dir.is_dir():
                        config_path = tool_dir / "config.yaml"
                        if config_path.exists():
                            with open(config_path, 'r') as f:
                                tool_config = yaml.safe_load(f)
                            
                            for prompt_config in tool_config.get('prompts', []):
                                prompts.append({
                                    'name': prompt_config['name'],
                                    'description': prompt_config['description'],
                                    'arguments': [
                                        {
                                            'name': arg['name'],
                                            'description': arg['description'],
                                            'required': arg.get('required', False)
                                        }
                                        for arg in prompt_config.get('arguments', [])
                                    ]
                                })
        except Exception as e:
            logger.error(f"Error extracting prompts from actual registry entry {server.name}: {e}")
        
        return prompts

    def _extract_resources_from_server(self, server: ServerInfo):
        """Extract actual resources from server tool configs."""
        resources = []
        try:
            server_dir = self.workspace_root / server.path
            resources_dir = server_dir / "resources" / "static"
            
            if resources_dir.exists():
                for config_file in resources_dir.glob("*.yaml"):
                    with open(config_file, 'r') as f:
                        resource_config = yaml.safe_load(f)
                    
                    resources.append({
                        'uri': resource_config['uri'],
                        'name': resource_config['name'],
                        'description': resource_config['description'],
                        'mimeType': resource_config['mimeType']
                    })
        except Exception as e:
            logger.error(f"Error extracting resources from {server.name}: {e}")
        
        return resources

    def _extract_resource_templates_from_server(self, server: ServerInfo):
        """Extract actual resource templates from server tool configs."""
        templates = []
        try:
            server_dir = self.workspace_root / server.path
            tools_dir = server_dir / "tools"
            
            if tools_dir.exists():
                for tool_dir in tools_dir.iterdir():
                    if tool_dir.is_dir():
                        config_path = tool_dir / "config.yaml"
                        if config_path.exists():
                            with open(config_path, 'r') as f:
                                tool_config = yaml.safe_load(f)
                            
                            for template_config in tool_config.get('resource_templates', []):
                                templates.append({
                                    'uriTemplate': template_config['uriTemplate'],
                                    'name': template_config['name'],
                                    'description': template_config['description'],
                                    'mimeType': template_config['mimeType']
                                })
        except Exception as e:
            logger.error(f"Error extracting resource templates from {server.name}: {e}")
        
        return templates

    def get_prompt_content(self, server_name: str, prompt_name: str, arguments: dict, discoverer: IServerDiscoverer):
        """Get the actual prompt content from registry entry tool configs or custom prompts."""
        try:
            target_server = self.get_server(server_name, discoverer)
            if not target_server:
                return None

            if isinstance(target_server, VirtualServer):
                # Virtual Server - first check for custom prompts
                custom_prompt = self.get_custom_prompt(server_name, prompt_name)
                if custom_prompt:
                    return self._process_custom_prompt(custom_prompt, arguments)
                
                # Then look through selected tools to find source registry entries
                registry_entries = discoverer.discover()
                for tool_config in target_server.selected_tools:
                    source_server_name = tool_config.get('server_name')
                    if source_server_name:
                        source_entry = next((entry for entry in registry_entries if entry.name == source_server_name), None)
                        if source_entry:
                            prompt_content = self._search_prompt_in_server(source_entry, prompt_name, arguments)
                            if prompt_content:
                                return prompt_content
            elif isinstance(target_server, ServerInfo):
                # Registry entry - search directly
                return self._search_prompt_in_server(target_server, prompt_name, arguments)
            
            return None
        except Exception as e:
            logger.error(f"Error getting prompt content for {prompt_name}: {e}")
            return None

    def _process_custom_prompt(self, custom_prompt: Dict[str, Any], arguments: dict) -> Dict[str, Any]:
        """Process a custom prompt with argument substitution."""
        try:
            content = custom_prompt.get('content', '')
            
            # Simple template processing - replace {{arg_name}} with argument values
            processed_content = content
            for arg_name, arg_value in arguments.items():
                processed_content = processed_content.replace(f'{{{{{arg_name}}}}}', str(arg_value))
            
            # Set default values for missing arguments
            for arg_config in custom_prompt.get('arguments', []):
                arg_name = arg_config.get('name')
                default_value = arg_config.get('default', '')
                if arg_name and arg_name not in arguments and default_value:
                    processed_content = processed_content.replace(f'{{{{{arg_name}}}}}', str(default_value))
            
            return {
                'description': custom_prompt.get('description', ''),
                'content': processed_content
            }
        except Exception as e:
            logger.error(f"Error processing custom prompt: {e}")
            return {
                'description': custom_prompt.get('description', ''),
                'content': custom_prompt.get('content', '')
            }

    def _search_prompt_in_server(self, server: ServerInfo, prompt_name: str, arguments: dict):
        """Search for a prompt in a specific server's tool configs."""
        try:
            server_dir = self.workspace_root / server.path
            tools_dir = server_dir / "tools"
            
            if not tools_dir.exists():
                return None
            
            # Search through tool configs for the prompt
            for tool_dir in tools_dir.iterdir():
                if tool_dir.is_dir():
                    config_path = tool_dir / "config.yaml"
                    if config_path.exists():
                        with open(config_path, 'r') as f:
                            tool_config = yaml.safe_load(f)
                        
                        for prompt_config in tool_config.get('prompts', []):
                            if prompt_config['name'] == prompt_name:
                                # Process the template with arguments
                                template = prompt_config.get('template', '')
                                
                                # Simple template processing - replace {arg_name} with argument values
                                processed_template = template
                                for arg_name, arg_value in arguments.items():
                                    processed_template = processed_template.replace(f'{{{arg_name}}}', str(arg_value))
                                
                                return {
                                    'description': prompt_config.get('description', ''),
                                    'content': processed_template
                                }
            
            return None
        except Exception as e:
            logger.error(f"Error searching prompt in server {server.name}: {e}")
            return None 