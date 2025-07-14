import logging
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.models import ServerInfo
from app.discovery.base import IServerDiscoverer
from app.discovery.scm import GitManager

logger = logging.getLogger(__name__)

class RegistryDiscoverer(IServerDiscoverer):
    """Discovers MCP servers from a YAML-based registry."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.registry_path = workspace_root / "registry"
        self.git_manager = GitManager()

    def discover(self) -> List[ServerInfo]:
        """Discover all MCP servers from the registry/ folder."""
        servers = []
        try:
            if self.registry_path.exists():
                servers.extend(self._discover_from_registry(self.registry_path))
            
            unique_servers = {f"{s.name}_{s.path}": s for s in servers}
            servers_list = list(unique_servers.values())
            
            self._resolve_port_collisions(servers_list)
            
            logger.info(f"Discovered {len(unique_servers)} unique servers in registry/")
            return servers_list
        except Exception as e:
            logger.error(f"Error during server discovery: {e}")
            return []

    def _discover_from_registry(self, registry_dir: Path) -> List[ServerInfo]:
        """Discover servers by reading all YAML files in the registry folder."""
        servers = []
        for entry in registry_dir.glob("*.yaml"):
            try:
                with open(entry, "r") as f:
                    config = yaml.safe_load(f)
                
                server_type = config.get("type", "local")
                if server_type == "github":
                    servers.append(self._process_github_server(config))
                elif server_type == "local":
                    servers.append(self._process_local_server(config))
                elif server_type == "remote":
                    servers.append(self._process_remote_server(config))

            except Exception as e:
                logger.warning(f"Error loading registry entry {entry}: {e}")
        
        return [s for s in servers if s]

    def _process_github_server(self, config: Dict[str, Any]) -> Optional[ServerInfo]:
        """Process a server of type 'github'."""
        name = config.get("name")
        repo = config.get("repo")
        if not name or not repo:
            logger.warning(f"GitHub server config missing 'name' or 'repo'.")
            return None

        branch = config.get("branch", "main")
        subdir = config.get("subdir", "")
        repo_name = repo.split("/")[-1].replace(".git", "")
        local_base = self.workspace_root / "servers" / "github" / repo_name
        local_path = local_base / subdir if subdir else local_base

        command, tools, status = [], [], "github_error"
        if self.git_manager.ensure_repo(repo, branch, local_base):
            command = self._find_server_command(local_path)
            # Tools will be fetched via proxy on-demand, not during discovery.
            tools = []
            status = "discovered" if config.get("enabled", True) else "disabled"

        return ServerInfo(
            name=name,
            path=str(local_path.relative_to(self.workspace_root)),
            description=f"[GitHub] {config.get('description', '')}",
            transport=config.get("transport", "stdio"),
            command=command,
            tools=tools,
            status=status,
            discovery_method="github",
            last_discovered=datetime.now().isoformat(),
            port=config.get("port"),
            health_check_url=config.get("health_check_url")
        )

    def _process_local_server(self, config: Dict[str, Any]) -> Optional[ServerInfo]:
        """Process a server of type 'local'."""
        name = config.get("name")
        path = config.get("path")
        if not name or not path:
            return None

        server_dir = self.workspace_root / path
        command = self._find_server_command(server_dir)
        # Tools will be fetched via proxy on-demand, not during discovery.
        tools = []

        return ServerInfo(
            name=name,
            path=path,
            description=config.get("description", ""),
            transport=config.get("transport", "stdio"),
            command=command,
            tools=tools,
            status="discovered" if config.get("enabled", True) else "disabled",
            discovery_method="registry",
            last_discovered=datetime.now().isoformat(),
            port=config.get("port"),
            health_check_url=config.get("health_check_url")
        )

    def _process_remote_server(self, config: Dict[str, Any]) -> Optional[ServerInfo]:
        """Process a server of type 'remote'."""
        name = config.get("name")
        url = config.get("url")
        if not name or not url:
            return None
            
        return ServerInfo(
            name=name,
            path=url,
            description=config.get("description", ""),
            transport=config.get("transport", "http"),
            command=[url],
            tools=[], # Tools will be fetched via proxy on-demand.
            status="discovered" if config.get("enabled", True) else "disabled",
            discovery_method="registry",
            last_discovered=datetime.now().isoformat(),
            port=config.get("port"),
            health_check_url=config.get("health_check_url")
        )
    
    def _find_server_command(self, server_dir: Path) -> List[str]:
        """Find the primary server script in a directory."""
        for script_name in ["server_stdio.py", "server.py", "server_http.py", "main.py"]:
            script_path = server_dir / script_name
            if script_path.exists():
                return ["python", str(script_path.relative_to(self.workspace_root))]
        return []

    def _merge_tool_states(self, discovered_tools: List[Dict], registry_tools: List[Dict]) -> List[Dict]:
        """
        Merges the 'enabled' and 'description' fields from the registry file into the 
        fully discovered tool information. This is a surgical operation to prevent
        the complex discovered objects from being overwritten by simple registry entries.
        """
        registry_states = {rt.get("name"): rt for rt in registry_tools if rt.get("name")}
        merged_tools = []

        for tool in discovered_tools:
            name = tool.get("name")
            if name in registry_states:
                # Use the discovered tool as the base (it's the source of truth)
                merged_tool = tool
                
                # Surgically update only specific fields from the registry
                registry_version = registry_states[name]
                if 'enabled' in registry_version:
                    merged_tool['enabled'] = registry_version['enabled']
                if 'description' in registry_version:
                    merged_tool['description'] = registry_version['description']
                
                merged_tools.append(merged_tool)
            else:
                # This tool was discovered on disk but not listed in the registry file.
                # We can assume it's enabled by default.
                tool["enabled"] = tool.get("enabled", True)
                merged_tools.append(tool)

        return merged_tools

    def _resolve_port_collisions(self, servers: List[ServerInfo]) -> None:
        """Detect and resolve port collisions among servers."""
        port_usage = {}
        for server in servers:
            if server.port and server.status != "disabled":
                port_usage.setdefault(server.port, []).append(server)

        for port, server_list in port_usage.items():
            if len(server_list) > 1:
                logger.warning(f"Port collision on {port} for servers: {[s.name for s in server_list]}")
                for i, server in enumerate(server_list[1:], 1):
                    new_port = self._find_free_port(port_usage, port + i)
                    if new_port:
                        logger.info(f"Reassigning server '{server.name}' from port {port} to {new_port}")
                        self._assign_port_to_server(server, new_port)
                        port_usage[new_port] = [server]
                    else:
                        logger.error(f"Could not find free port for server '{server.name}'")
                        server.status = "port_collision_error"
    
    def _find_free_port(self, port_usage: Dict[int, List], start_port: int = 8000) -> Optional[int]:
        """Find a free port."""
        port = start_port
        while port in port_usage:
            port += 1
        return port

    def _assign_port_to_server(self, server: ServerInfo, new_port: int) -> None:
        """Assign a new port to a server, updating its registry file."""
        server.port = new_port
        registry_file = self.registry_path / f"{server.discovery_method}-{server.name}.yaml" # This assumes a file naming convention that may not exist. A better approach would be to find file by name property
        
        # A better approach
        found_file = None
        for entry in self.registry_path.glob("*.yaml"):
             with open(entry, "r") as f:
                config = yaml.safe_load(f)
                if config.get("name") == server.name:
                    found_file = entry
                    break
        
        if not found_file:
            logger.warning(f"Could not find registry file for server '{server.name}' to update port.")
            return

        with open(found_file, 'r') as f:
            config = yaml.safe_load(f)
        
        config["port"] = new_port
        
        with open(found_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Updated port for '{server.name}' to {new_port} in {found_file.name}") 