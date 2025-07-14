"""Tool execution module for MCP server."""

import importlib.util
import sys
import json
from typing import Dict, Any, List
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)

def execute_tool(tool: Dict[str, Any], params: Dict[str, Any], workspace_root: Path) -> Any:
    """Dynamically load and execute a tool's entry point."""
    try:
        # Ensure the module path is absolute
        relative_path = Path(tool['directory']) / tool['module']
        module_path = workspace_root / relative_path
        
        if not module_path.exists():
            raise FileNotFoundError(f"Tool module not found at {module_path}")

        spec = importlib.util.spec_from_file_location(tool['name'], module_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not create module spec for {module_path}")
            
        tool_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool_module)
        
        entry_point = getattr(tool_module, tool['entry_point'])
        return entry_point(**params)
    except Exception as e:
        logger.error(f"Failed to execute tool '{tool['name']}': {e}", exc_info=True)
        # Re-raise to be caught by the server's top-level error handler
        raise  

def validate_tool_params(tool: Dict[str, Any], params: Dict[str, Any]):
    """Validate parameters against the tool's input schema."""
    required_inputs = {p['name'] for p in tool.get('inputs', []) if p.get('required', False)}
    provided_params = set(params.keys())
    
    missing_params = required_inputs - provided_params
    if missing_params:
        raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")

class InternalToolExecutor:
    """
    Manages the discovery and execution of internal tools for a specific server.
    """
    def __init__(self, workspace_root: Path, server_name: str):
        self.workspace_root = workspace_root
        self.server_name = server_name
        self.tools_path = workspace_root / "servers" / server_name / "tools"
        self.tools = self._discover_tools()

    def _discover_tools(self) -> List[Dict[str, Any]]:
        """Discover tools by reading and merging their config.yaml and resource_config.yaml files."""
        discovered_tools = []
        for tool_dir in self.tools_path.iterdir():
            if tool_dir.is_dir():
                config_path = tool_dir / "config.yaml"
                resource_config_path = tool_dir / "resource_config.yaml"
                
                if not config_path.exists():
                    continue

                try:
                    with open(config_path, "r") as f:
                        config = yaml.safe_load(f) or {}

                    if resource_config_path.exists():
                        with open(resource_config_path, "r") as f:
                            resource_config = yaml.safe_load(f) or {}
                        config.update(resource_config)

                    config.setdefault('inputs', [])
                    config.setdefault('outputs', [])
                    config['directory'] = str(tool_dir.relative_to(self.workspace_root))
                    discovered_tools.append(config)

                except Exception as e:
                    logger.error(f"Error loading tool from {tool_dir.name}: {e}")
        
        return discovered_tools

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return the list of discovered tools."""
        return self.tools

    def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Find a tool by name, validate parameters, and execute it."""
        tool = next((t for t in self.tools if t['name'] == tool_name), None)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found.")
        
        validate_tool_params(tool, params)
        return execute_tool(tool, params, self.workspace_root) 