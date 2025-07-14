import json
from flask import jsonify

from app.virtual.manager import VirtualServerManager
from app.discovery.base import IServerDiscoverer
from app.prompts.manager import PromptManager

def handle_initialize(server, params, request_id):
    """Handles the 'initialize' MCP method."""
    return {
        'jsonrpc': '2.0',
        'result': {
            'protocolVersion': '2024-11-05',
            'capabilities': {
                'tools': {'listChanged': False},
                'prompts': {'listChanged': False},
                'resources': {'subscribe': False, 'listChanged': False}
            },
            'serverInfo': {
                'name': f'MCP Proxy - {server.name}',
                'version': '1.0.0'
            }
        },
        'id': request_id
    }

def handle_tools_list(server, params, request_id, vsm: VirtualServerManager, prompt_manager: PromptManager, tool_proxy_router: 'ToolProxyRouter'):
    """Handles the 'tools/list' MCP method."""
    # For virtual servers, we need to synthesize the tool list
    if hasattr(server, 'selected_tools'):
        tools = []
        # 1. Add real tools from the selection
        for tool_config in server.selected_tools:
            # The full tool config, including input schema, is nested under the 'config' key
            full_config = tool_config.get('config', {})
            tools.append({
                'name': tool_config.get('tool_name'),
                'description': full_config.get('description'),
                'inputSchema': full_config.get('inputSchema', {'type': 'object', 'properties': {}})
            })

        # 2. Add synthesized tools from custom prompts
        if server.selected_prompts:
            for prompt_id in server.selected_prompts:
                prompt = prompt_manager.get_prompt(prompt_id)
                if prompt:
                    prompt_schema = {
                        'name': prompt.id,
                        'description': f"[PROMPT] {prompt.description}",
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                var_name: {
                                    'type': 'string',
                                    'description': f"Input for the '{var_name}' variable in the prompt."
                                } for var_name in prompt.input_variables
                            },
                            'required': prompt.input_variables
                        }
                    }
                    tools.append(prompt_schema)
    else:
        # For real servers, proxy the request to get the tool list
        tools = tool_proxy_router.list_tools(server)

    return {'jsonrpc': '2.0', 'result': {'tools': tools}, 'id': request_id}

def handle_tools_call(server, params, request_id, vsm: VirtualServerManager, discoverer: IServerDiscoverer, tool_proxy_router: 'ToolProxyRouter', prompt_manager: PromptManager):
    """Handles the 'tools/call' MCP method."""
    tool_name = params.get('name')
    arguments = params.get('arguments', {})

    if not tool_name:
        return {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': 'Missing tool name'}, 'id': request_id}

    try:
        # Check if the tool is a custom prompt
        is_prompt = hasattr(server, 'selected_prompts') and server.selected_prompts and tool_name in server.selected_prompts
        
        if is_prompt:
            prompt = prompt_manager.get_prompt(tool_name)
            if not prompt:
                 return {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': f'Prompt-based tool "{tool_name}" not found'}, 'id': request_id}

            # Render the prompt template
            rendered_text = prompt.prompt_template
            for var, value in arguments.items():
                rendered_text = rendered_text.replace(f'{{{{{var}}}}}', str(value))
            
            result = {"rendered_prompt": rendered_text}
        else:
            # For standard tools, find the underlying server and proxy the call
            if not hasattr(server, 'selected_tools'):
                 return {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': f'Tool "{tool_name}" cannot be executed on a non-virtual server'}, 'id': request_id}

            tool_config = next((t for t in server.selected_tools if t['tool_name'] == tool_name), None)
            if not tool_config:
                return {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': f'Tool "{tool_name}" not found in this virtual server'}, 'id': request_id}
            
            source_server_name = tool_config.get('server_name')
            source_server = vsm.get_server(source_server_name, discoverer)
            if not source_server:
                return {'jsonrpc': '2.0', 'error': {'code': -32603, 'message': f'Underlying server "{source_server_name}" not found'}, 'id': request_id}
            
            result = tool_proxy_router.execute_tool(source_server, tool_config['tool_name'], arguments)
        
        content = [{'type': 'text', 'text': json.dumps(result, indent=2) if isinstance(result, dict) else str(result)}]
        is_error = result.get('status') == 'error' if isinstance(result, dict) else False
        return {'jsonrpc': '2.0', 'result': {'content': content, 'isError': is_error}, 'id': request_id}

    except Exception as e:
        return {'jsonrpc': '2.0', 'error': {'code': -32603, 'message': f'Tool execution failed: {str(e)}'}, 'id': request_id}

def handle_prompts_list(server, params, request_id, vsm: VirtualServerManager, discoverer: IServerDiscoverer, prompt_manager: PromptManager):
    """Handles the 'prompts/list' MCP method by aggregating from all sources."""
    prompts = []
    
    # For virtual servers, aggregate prompts from underlying servers and custom prompts
    if hasattr(server, 'selected_tools'):
        # 1. Get prompts from all unique underlying real servers
        underlying_server_names = {t.get('server_name') for t in server.selected_tools if t.get('server_name')}
        
        for server_name in underlying_server_names:
            # Use the existing capability fetching logic which proxies the request
            server_prompts = vsm.fetch_server_capabilities(server_name, 'prompts', discoverer)
            if server_prompts:
                prompts.extend(server_prompts)

        # 2. Add selected custom prompts
        if server.selected_prompts:
            for prompt_id in server.selected_prompts:
                prompt = prompt_manager.get_prompt(prompt_id)
                if prompt:
                    prompts.append({
                        'name': prompt.id,
                        'description': prompt.description,
                        'inputVariables': prompt.input_variables,
                    })
    # For real servers, just proxy the request
    else:
        prompts = vsm.fetch_server_capabilities(server.name, 'prompts', discoverer)
        
    return {'jsonrpc': '2.0', 'result': {'prompts': prompts}, 'id': request_id}


def handle_prompts_get(server, params, request_id, vsm: VirtualServerManager, discoverer: IServerDiscoverer):
    """Handles the 'prompts/get' MCP method."""
    prompt_name = params.get('name')
    arguments = params.get('arguments', {})
    if not prompt_name:
        return {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': 'Missing required parameter: name'}, 'id': request_id}
    
    prompt_content = vsm.get_prompt_content(server.name, prompt_name, arguments, discoverer)
    if prompt_content is None:
        return {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': f"Prompt '{prompt_name}' not found"}, 'id': request_id}
    
    return {
        'jsonrpc': '2.0',
        'result': {
            'description': prompt_content.get('description', ''),
            'messages': [{'role': 'user', 'content': {'type': 'text', 'text': prompt_content.get('content', '')}}]
        },
        'id': request_id
    }

def handle_resources_list(server, params, request_id, vsm: VirtualServerManager, discoverer: IServerDiscoverer):
    """Handles the 'resources/list' MCP method by aggregating from all sources."""
    resources = []
    
    # For virtual servers, aggregate resources from underlying servers
    if hasattr(server, 'selected_tools'):
        underlying_server_names = {t.get('server_name') for t in server.selected_tools if t.get('server_name')}
        
        for server_name in underlying_server_names:
            server_resources = vsm.fetch_server_capabilities(server_name, 'resources', discoverer)
            if server_resources:
                resources.extend(server_resources)
    # For real servers, just proxy the request
    else:
        resources = vsm.fetch_server_capabilities(server.name, 'resources', discoverer)
        
    return {'jsonrpc': '2.0', 'result': {'resources': resources}, 'id': request_id}

def handle_resources_read(server, params, request_id):
    """Handles the 'resources/read' MCP method."""
    return {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': 'Resource reading not yet implemented'}, 'id': request_id}

def handle_resource_templates_list(server, params, request_id, vsm: VirtualServerManager, discoverer: IServerDiscoverer):
    """Handles the 'resources/templates/list' MCP method by aggregating from all sources."""
    templates = []

    # For virtual servers, aggregate templates from underlying servers
    if hasattr(server, 'selected_tools'):
        underlying_server_names = {t.get('server_name') for t in server.selected_tools if t.get('server_name')}
        
        for server_name in underlying_server_names:
            server_templates = vsm.fetch_server_capabilities(server_name, 'resource_templates', discoverer)
            if server_templates:
                templates.extend(server_templates)
    # For real servers, just proxy the request
    else:
        templates = vsm.fetch_server_capabilities(server.name, 'resource_templates', discoverer)

    return {'jsonrpc': '2.0', 'result': {'resourceTemplates': templates}, 'id': request_id}

def handle_ping(server, params, request_id):
    """Handles the 'ping' MCP method."""
    return {'jsonrpc': '2.0', 'result': {}, 'id': request_id}

# Dispatcher for MCP methods
MCP_METHOD_HANDLERS = {
    'initialize': handle_initialize,
    'tools/list': handle_tools_list,
    'tools/call': handle_tools_call,
    'prompts/list': handle_prompts_list,
    'prompts/get': handle_prompts_get,
    'resources/list': handle_resources_list,
    'resources/read': handle_resources_read,
    'resources/templates/list': handle_resource_templates_list,
    'ping': handle_ping,
}
