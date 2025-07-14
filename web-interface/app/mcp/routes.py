import uuid
import json
import queue
import secrets
import threading
import hmac
from flask import Blueprint, request, jsonify, g, Response, stream_with_context
from .handlers import MCP_METHOD_HANDLERS

mcp_bp = Blueprint('mcp', __name__)
mcp_sse_bp = Blueprint('mcp_sse', __name__)

# In-memory queues for SSE transport, should be replaced with a more robust solution like Redis in production
sse_queues = {}
sse_queues_lock = threading.Lock()

def _validate_server(server_name):
    """Helper to find and validate a virtual server."""
    server = g.virtual_server_manager.get_virtual_server(server_name)
    if not server:
        return None, jsonify({'error': f'Server {server_name} not found.'}), 404
    if not server.enabled:
        err = {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': f'Server "{server_name}" is disabled'}, 'id': None}
        return None, jsonify(err), 403
    return server, None, None

def _process_json_rpc_request(server, data):
    """Processes a single JSON-RPC request object using the handler dispatch."""
    # Basic validation
    if not all(k in data for k in ['jsonrpc', 'method', 'id']):
        return {'jsonrpc': '2.0', 'error': {'code': -32600, 'message': 'Invalid Request'}, 'id': None}

    method = data['method']
    params = data.get('params', {})
    request_id = data['id']

    handler = MCP_METHOD_HANDLERS.get(method)
    if not handler:
        return {'jsonrpc': '2.0', 'error': {'code': -32601, 'message': 'Method not found'}, 'id': request_id}

    # Build a dictionary of dependencies to inject into the handler
    kwargs = {}
    handler_params = handler.__code__.co_varnames
    
    if 'vsm' in handler_params:
        kwargs['vsm'] = g.virtual_server_manager
    if 'discoverer' in handler_params:
        kwargs['discoverer'] = g.server_discovery
    if 'tool_proxy_router' in handler_params:
        kwargs['tool_proxy_router'] = g.tool_proxy_router
    if 'prompt_manager' in handler_params:
        kwargs['prompt_manager'] = g.prompt_manager
        
    result = handler(server, params, request_id, **kwargs)
    return result

def _get_server_from_name(server_name: str):
    """Helper to get a server by name, checking both virtual and registry."""
    server = g.virtual_server_manager.get_virtual_server(server_name)
    if not server:
        # If not a virtual server, check registry entries
        server = g.virtual_server_manager.get_server(server_name, g.server_discovery)
    return server

def get_auth_key(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None, {'jsonrpc': '2.0', 'error': {'code': -32000, 'message': 'Authentication error: Missing Authorization header'}, 'id': None}

    if not auth_header.startswith('Bearer '):
        return None, {'jsonrpc': '2.0', 'error': {'code': -32000, 'message': 'Authentication error: Invalid token type, expected Bearer'}, 'id': None}
    
    return auth_header[len('Bearer '):], None

# --- MCP Endpoints ---

@mcp_bp.route('/<server_name>', methods=['GET', 'POST', 'HEAD'])
def mcp_transport(server_name: str):
    """Handles standard MCP requests (single or batch)."""
    server = _get_server_from_name(server_name)
    if not server:
        return jsonify({'error': 'Server not found'}), 404

    # --- Authentication Check ---
    if hasattr(server, 'config') and server.config:
        required_key = server.config.get('api_key')
    else:
        required_key = getattr(server, 'api_key', None)

    if required_key:
        provided_key, err = get_auth_key(request)
        if err:
            return jsonify(err), 401
        
        if not provided_key or not hmac.compare_digest(provided_key, required_key):
            err = {'jsonrpc': '2.0', 'error': {'code': -32001, 'message': 'Authentication error: Invalid API Key'}, 'id': None}
            return jsonify(err), 401
    # If server has no key, allow request for backward compatibility.
        
    if request.method == 'GET' or request.method == 'HEAD':
        # Handle HEAD requests for capability checks
        return '', 200

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    if isinstance(data, list):
        # Batch request
        responses = [_process_json_rpc_request(server, req) for req in data]
        return jsonify(responses)
    else:
        # Single request
        response = _process_json_rpc_request(server, data)
        return jsonify(response)

@mcp_sse_bp.route('/<server_name>', methods=['POST'])
def mcp_streamable_transport(server_name: str):
    """Handles MCP requests using SSE for streaming responses."""
    server = _get_server_from_name(server_name)
    if not server:
        # SSE needs a response object to report the error
        return Response(json.dumps({'error': 'Server not found'}), status=404, mimetype='application/json')

    # --- Authentication Check ---
    if hasattr(server, 'config') and server.config:
        required_key = server.config.get('api_key')
    else:
        required_key = getattr(server, 'api_key', None)
        
    if required_key:
        provided_key, err = get_auth_key(request)
        if err:
            return Response(json.dumps(err), status=401, mimetype='application/json')

        if not provided_key or not hmac.compare_digest(provided_key, required_key):
            err = {'jsonrpc': '2.0', 'error': {'code': -32001, 'message': 'Authentication error: Invalid API Key'}, 'id': None}
            return Response(json.dumps(err), status=401, mimetype='application/json')

    data = request.get_json()
    if not data:
        return Response(json.dumps({'error': 'Invalid JSON body'}), status=400, mimetype='application/json')

    def stream():
        """Generator function for the SSE stream."""
        response_dict = _process_json_rpc_request(server, data)
        yield f"data: {json.dumps(response_dict)}\n\n"
    
    return Response(stream(), mimetype='text/event-stream')
