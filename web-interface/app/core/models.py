#!/usr/bin/env python3
"""
Data models for the MCP server composition system.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

@dataclass
class IServer(ABC):
    """An abstract base class for any type of server (real or virtual)."""
    name: str

@dataclass
class ServerInfo(IServer):
    """Information about a discovered MCP server."""
    path: str
    description: str
    transport: str  # 'stdio', 'http', 'sse', 'docker'
    command: List[str]
    tools: List[Dict[str, Any]]
    status: str  # 'running', 'stopped', 'error', 'discovered'
    discovery_method: str  # 'auto', 'manual', 'config', 'docker'
    last_discovered: str
    port: Optional[int] = None
    health_check_url: Optional[str] = None


@dataclass
class VirtualServer(IServer):
    """Represents a composed server with a specific set of tools and rules."""
    description: str
    selected_tools: List[Dict[str, Any]]
    rules: List[Dict[str, Any]]
    created_at: str
    updated_at: str
    enabled: bool = True
    port: Optional[int] = None
    status: str = 'stopped'  # 'running', 'stopped', 'error'
    api_key: Optional[str] = None
    selected_prompts: List[str] = None  # List of CustomPrompt IDs