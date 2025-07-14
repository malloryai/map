from flask import Blueprint, render_template, g, current_app
import yaml
from pathlib import Path
import logging

ui_bp = Blueprint('ui', __name__)
logger = logging.getLogger(__name__)

@ui_bp.route('/')
def index():
    """Main dashboard showing platform overview."""
    registry_entries = g.server_discovery.discover()
    servers = g.virtual_server_manager.list_virtual_servers()
    
    # Extract all tools from all registry entries for the dashboard
    all_tools = []
    for entry in registry_entries:
        # Get full tool details via proxy
        tools_details = g.tool_proxy_router.list_tools(entry)
        for tool in tools_details:
            # Add registry entry context to each tool
            tool_with_context = tool.copy()
            
            # Unpack custom data FIRST
            if 'data' in tool and tool['data']:
                tool_with_context.update(tool['data'])

            # Set the correct directory path LAST, overwriting any incorrect path
            server_name_cleaned = entry.name.split('/')[-1]
            tool_with_context['server_name'] = server_name_cleaned
            tool_with_context['directory'] = f"{server_name_cleaned}/{tool['name']}"
            
            all_tools.append(tool_with_context)
    
    # Calculate statistics
    total_tools = len(all_tools)
    enabled_tools = len([tool for tool in all_tools if tool.get('enabled', True)])
    standby_tools = total_tools - enabled_tools
    
    return render_template('index.html',
                         total_count=total_tools,
                         enabled_count=enabled_tools,
                         standby_count=standby_tools,
                         server_count=len(servers),
                         registry_entries=registry_entries,
                         servers=servers,
                         tools=all_tools)

@ui_bp.route('/tools/<path:tool_directory>')
def tool_details(tool_directory):
    """Show detailed information about a specific tool."""
    if '/' in tool_directory:
        server_name, tool_name = tool_directory.split('/', 1)
    else:
        return "Invalid tool directory format", 400
    
    target_server = g.virtual_server_manager.get_server(server_name, g.server_discovery)
    
    if not target_server:
        return f"Server not found: {server_name}", 404
        
    # Get all tools from the server via proxy
    all_tools_details = g.tool_proxy_router.list_tools(target_server)
    
    # Find the specific tool we need
    enhanced_tool = next((t for t in all_tools_details if t['name'] == tool_name), None)

    if not enhanced_tool:
        return f"Tool not found: {tool_directory}", 404

    # Add context for the template
    enhanced_tool['server_name'] = server_name
    enhanced_tool['directory'] = tool_directory
    
    # Unpack custom data
    if 'data' in enhanced_tool and enhanced_tool['data']:
        enhanced_tool.update(enhanced_tool['data'])

    logger.info(f"DEBUG: Data for tool '{tool_name}': {enhanced_tool}")

    return render_template('tool_details.html', 
                         tool=enhanced_tool, 
                         tool_directory=tool_directory,
                         server=target_server)

@ui_bp.route('/registry')
def registry_dashboard():
    """Dashboard showing all discovered registry entries."""
    registry_entries = g.server_discovery.discover()
    servers = g.virtual_server_manager.list_virtual_servers()
    
    return render_template('registry.html', 
                         registry_entries=registry_entries, 
                         servers=servers,
                         total_registry_entries=len(registry_entries),
                         server_count=len(servers))

@ui_bp.route('/registry/<server_name>')
def registry_entry_details(server_name):
    """Show detailed information about a specific registry entry."""
    target_entry = g.virtual_server_manager.get_server(server_name, g.server_discovery)
    
    if not target_entry:
        return f"Registry entry not found: {server_name}", 404
    
    # Enhance with full tool details from the proxy
    target_entry.tools = g.tool_proxy_router.list_tools(target_entry)
    
    return render_template('registry_entry_details.html', 
                         server=target_entry,
                         server_name=server_name)

@ui_bp.route('/servers')
def servers_list():
    """List all virtual servers."""
    servers = g.virtual_server_manager.list_virtual_servers()
    return render_template('servers.html', virtual_servers=servers)

@ui_bp.route('/servers/create')
def create_server():
    """Render the page to create a new virtual server."""
    registry_entries = g.server_discovery.discover()
    prompts = g.prompt_manager.get_all_prompts()

    # Enhance with full tool details and unpack data
    for entry in registry_entries:
        full_tools = g.tool_proxy_router.list_tools(entry)
        unpacked_tools = []
        for tool in full_tools:
            if 'data' in tool and tool['data']:
                tool.update(tool['data'])
            unpacked_tools.append(tool)
        entry.tools = unpacked_tools
    return render_template('create_server.html', servers=registry_entries, prompts=prompts)

@ui_bp.route('/servers/create/<server_name>')
def create_server_with_preselection(server_name):
    """Render the create page with a pre-selected server."""
    registry_entries = g.server_discovery.discover()
    prompts = g.prompt_manager.get_all_prompts()
    # Enhance with full tool details and unpack data
    for entry in registry_entries:
        full_tools = g.tool_proxy_router.list_tools(entry)
        unpacked_tools = []
        for tool in full_tools:
            if 'data' in tool and tool['data']:
                tool.update(tool['data'])
            unpacked_tools.append(tool)
        entry.tools = unpacked_tools
    return render_template('create_server.html', servers=registry_entries, prompts=prompts, preselected_server=server_name)

@ui_bp.route('/servers/<server_name>')
def server_details(server_name):
    """Show detailed information about a specific virtual server."""
    server = g.virtual_server_manager.get_virtual_server(server_name)
    if not server:
        return f"Server not found: {server_name}", 404

    # To enrich the tool details, we first need a map of all possible source servers.
    all_source_servers = g.server_discovery.discover()
    source_server_map = {s.name: s for s in all_source_servers}

    enriched_tools = []
    for tool_ref in server.selected_tools:
        source_server_name = tool_ref.get('server_name')
        tool_name = tool_ref.get('tool_name')
        source_server = source_server_map.get(source_server_name)

        # Ensure we have a valid source server for the tool
        if not source_server or not tool_name:
            continue
            
        # Fetch the full, live details for the tool via the proxy
        full_tool_details = g.tool_proxy_router.get_tool(source_server, tool_name)
        if full_tool_details:
            # The template expects a 'config' key containing the tool's details
            enriched_tools.append({
                'server_name': source_server_name,
                'tool_name': tool_name,
                'config': full_tool_details
            })

    # Replace the server's stored tools with the fully enriched list for rendering
    server.selected_tools = enriched_tools

    return render_template('server_details.html', server=server)


@ui_bp.route('/servers/<server_name>/edit')
def edit_server(server_name):
    """Render the page to edit an existing virtual server."""
    server = g.virtual_server_manager.get_virtual_server(server_name)
    if not server:
        return f"Server not found: {server_name}", 404
    
    registry_entries = g.server_discovery.discover()
    prompts = g.prompt_manager.get_all_prompts()

    # Load full tool details for all available tools using the proxy
    for entry in registry_entries:
        entry.tools = g.tool_proxy_router.list_tools(entry)

    return render_template('edit_server.html',
                         server=server,
                         servers=registry_entries,
                         prompts=prompts,
                         server_name=server_name)
