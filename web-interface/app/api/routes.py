from flask import Blueprint, jsonify, request, g
import secrets

api_bp = Blueprint('api', __name__)

@api_bp.route('/tools/<path:tool_directory>/toggle', methods=['POST'])
def toggle_tool(tool_directory):
    """API endpoint to toggle a tool's enabled status."""
    try:
        if '/' in tool_directory:
            server_name, tool_name = tool_directory.split('/', 1)
        else:
            return jsonify({'error': 'Invalid tool directory format'}), 400
        
        servers = g.server_discovery.discover()
        server = next((s for s in servers if s.name == server_name), None)
        if not server:
            return jsonify({'error': f'Server {server_name} not found'}), 404
        
        tool_found = False
        for tool in server.tools:
            if tool.get('name') == tool_name:
                current_status = tool.get('enabled', True)
                tool['enabled'] = not current_status
                tool_found = True
                break
        
        if not tool_found:
            return jsonify({'error': f'Tool {tool_name} not found in server {server_name}'}), 404
        
        # This is a bit tricky, as we'd need to save back to the registry file.
        # The storage_backend is for virtual servers, not registry entries.
        # For now, this change is in-memory only for the lifetime of the app instance.
        # A more robust solution would be needed to persist this.
        
        new_status = tool.get('enabled', True)
        return jsonify({
            'success': True,
            'message': f'Tool {tool_name} {"enabled" if new_status else "disabled"} successfully (in-memory)',
            'tool_directory': tool_directory,
            'enabled': new_status
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to toggle tool: {str(e)}'}), 500

@api_bp.route('/registry', methods=['GET'])
def list_registry_entries():
    """API endpoint to list all registry entries."""
    registry_entries = g.server_discovery.discover()
    return jsonify([{
        'name': entry.name,
        'description': entry.description,
        'path': entry.path,
        'status': entry.status,
        'discovery_method': entry.discovery_method,
        'tools': entry.tools
    } for entry in registry_entries])

@api_bp.route('/registry/refresh', methods=['POST'])
def refresh_registry():
    """API endpoint to refresh registry discovery."""
    try:
        g.server_discovery.discover() # The new discover method inherently refreshes
        return jsonify({'message': 'Registry refreshed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/servers', methods=['GET'])
def list_servers():
    """API endpoint to list all virtual servers."""
    servers = g.virtual_server_manager.list_virtual_servers()
    return jsonify([{
        'name': server.name,
        'description': server.description,
        'enabled': server.enabled,
        'created_at': server.created_at,
        'proxy_url': f'/mcp/{server.name}',
        'sse_url': f'/mcp-sse/{server.name}'
    } for server in servers])

@api_bp.route('/servers', methods=['POST'])
def create_server():
    """API endpoint to create a new virtual server."""
    try:
        data = request.get_json()
        required_fields = ['name', 'description', 'selected_tools']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        api_key = secrets.token_hex(32)

        server = g.virtual_server_manager.create_virtual_server(
            name=data['name'],
            description=data['description'],
            selected_tools=data['selected_tools'],
            selected_prompts=data.get('selected_prompts', []),
            enabled=data.get('enabled', True),
            api_key=api_key
        )
        
        return jsonify({
            'success': True,
            'message': 'Server created successfully',
            'server': {
                'name': server.name,
                'description': server.description,
                'enabled': server.enabled,
                'proxy_url': f'/mcp/{server.name}',
                'sse_url': f'/mcp-sse/{server.name}'
            }
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 409 # Conflict
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/servers/<server_name>', methods=['PUT'])
def update_server(server_name):
    """API endpoint to update a virtual server."""
    try:
        data = request.get_json()
        server = g.virtual_server_manager.get_virtual_server(server_name)
        
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        # The manager will handle the update logic. We just pass the data.
        g.virtual_server_manager.update_virtual_server(server, data)
        
        return jsonify({
            'success': True,
            'message': 'Server updated successfully',
            'server': {
                'name': server.name,
                'description': server.description,
                'enabled': server.enabled
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/servers/<server_name>/regenerate-key', methods=['POST'])
def regenerate_api_key(server_name):
    """API endpoint to regenerate the API key for a virtual server."""
    try:
        server = g.virtual_server_manager.get_virtual_server(server_name)
        if not server:
            return jsonify({'error': 'Server not found'}), 404
            
        new_key = secrets.token_hex(32)
        g.virtual_server_manager.update_virtual_server(server, {'api_key': new_key})
        
        return jsonify({
            'success': True,
            'message': 'API key regenerated successfully',
            'api_key': new_key
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/servers/<server_name>', methods=['DELETE'])
def delete_server(server_name):
    """API endpoint to delete a virtual server."""
    try:
        success = g.virtual_server_manager.delete_virtual_server(server_name)
        if success:
            return jsonify({'success': True, 'message': 'Server deleted successfully'})
        else:
            return jsonify({'error': 'Server not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/servers/<server_name>/status', methods=['GET'])
def server_status(server_name):
    """API endpoint to get virtual server status."""
    try:
        server = g.virtual_server_manager.get_virtual_server(server_name)
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        return jsonify({
            'name': server.name,
            'status': server.status,
            'enabled': server.enabled,
            'tools_count': len(server.selected_tools)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
