"""Generic resource handlers for MCP server - fully modular with no hardcoded data."""

import json
import yaml
from urllib.parse import unquote
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone


def format_timestamp() -> str:
    """Generate current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def load_resource_config(tool_dir: Path) -> Optional[Dict[str, Any]]:
    """Load resource configuration for a tool."""
    config_path = tool_dir / "resource_config.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return None


def discover_resource_configs(tools_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Discover resource configurations from all tool directories."""
    configs = {}
    for tool_dir in tools_dir.iterdir():
        if tool_dir.is_dir():
            config = load_resource_config(tool_dir)
            if config:
                # Map by URI prefix from config
                for handler in config.get("handlers", []):
                    uri_prefix = handler["uri_prefix"]
                    configs[uri_prefix] = {
                        "tool_dir": tool_dir.name,
                        "config": handler
                    }
    return configs


def extract_parameters(uri: str, uri_pattern: str) -> Dict[str, str]:
    """Extract parameters from URI based on pattern."""
    # Simple parameter extraction - split by / and match against pattern
    uri_parts = uri.split("/")
    pattern_parts = uri_pattern.split("/")
    
    params = {}
    for i, (uri_part, pattern_part) in enumerate(zip(uri_parts, pattern_parts)):
        if pattern_part.startswith("{") and pattern_part.endswith("}"):
            param_name = pattern_part[1:-1]  # Remove { }
            params[param_name] = unquote(uri_part)
    
    return params


def format_template(template: str, variables: Dict[str, Any]) -> str:
    """Format template string with variables."""
    result = template
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        if isinstance(value, (dict, list)):
            result = result.replace(placeholder, json.dumps(value, indent=2))
        else:
            result = result.replace(placeholder, str(value))
    return result


def execute_resource_handler(
    uri: str,
    handler_config: Dict[str, Any], 
    loaded_tools: Dict[str, Any],
    execute_tool_func
) -> str:
    """Execute a resource handler based on configuration."""
    config = handler_config["config"]
    tool_dir_name = handler_config["tool_dir"]
    
    # Extract parameters from URI
    params = extract_parameters(uri, config["uri_pattern"])
    
    # Prepare variables for template
    variables = {
        "timestamp": format_timestamp(),
        **params  # Add all extracted parameters
    }
    
    # Handle different handler types
    if config["type"] == "single_tool":
        # Single tool execution
        tool_name = config["tool_name"]
        tool_info = loaded_tools.get(tool_name)
        
        if not tool_info:
            raise ValueError(f"Tool {tool_name} not available")
        
        # Execute tool with mapped parameters
        tool_params = {}
        for param_name, uri_param in config.get("parameter_mapping", {}).items():
            if uri_param in params:
                tool_params[param_name] = params[uri_param]
        
        result = execute_tool_func(tool_info, tool_params)
        variables["tool_result"] = result
        
        # Add any configured metadata
        for key, value in config.get("metadata", {}).items():
            variables[key] = value
    
    elif config["type"] == "multi_tool":
        # Multi-tool execution
        sections = []
        
        for tool_config in config.get("tools", []):
            tool_name = tool_config["name"]
            tool_info = loaded_tools.get(tool_name)
            
            if tool_info:
                # Execute tool
                tool_params = {}
                for param_name, uri_param in tool_config.get("parameter_mapping", {}).items():
                    if uri_param in params:
                        tool_params[param_name] = params[uri_param]
                
                result = execute_tool_func(tool_info, tool_params)
                
                # Format result based on configuration
                if tool_config.get("format") == "json_code_block":
                    formatted_result = f"```json\n{json.dumps(result, indent=2)}\n```"
                elif tool_config.get("format") == "text":
                    formatted_result = result.get("instructions", str(result))
                else:
                    formatted_result = str(result)
                
                # Add section
                section_header = tool_config.get("section_header", f"## {tool_name.title()}")
                sections.append(f"{section_header}\n{formatted_result}")
        
        variables["sections"] = "\n\n".join(sections)
    
    # Format final response using template
    return format_template(config["response_template"], variables)


def handle_generic_resource(uri: str, tools_dir: Path, loaded_tools: Dict[str, Any], execute_tool_func) -> str:
    """Handle resource requests using generic configuration-driven approach."""
    # Discover all resource configurations
    resource_configs = discover_resource_configs(tools_dir)
    
    # Find matching handler
    for uri_prefix, handler_config in resource_configs.items():
        if uri.startswith(uri_prefix):
            return execute_resource_handler(uri, handler_config, loaded_tools, execute_tool_func)
    
    raise ValueError(f"No resource handler found for: {uri}") 