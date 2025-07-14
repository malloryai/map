import logging
from pathlib import Path
from flask import Flask, g
from config import config_by_name
from app.virtual.manager import VirtualServerManager
from app.discovery.registry import RegistryDiscoverer
from app.proxy.router import ToolProxyRouter
from app.proxy.http import HttpTransportHandler
from app.proxy.stdio import StdioTransportHandler
from app.prompts.manager import PromptManager
from app.prompts.storage import YAMLPromptStorage
from storage_backend import StorageConfig
from yaml_backend import YAMLBackend

# Set up logging
logger = logging.getLogger(__name__)

def create_app(config_name: str) -> Flask:
    """
    Creates and configures a Flask application using the app factory pattern.
    """
    web_interface_root = Path(__file__).parent.parent
    app = Flask(
        __name__,
        template_folder=web_interface_root / "templates",
        static_folder=web_interface_root / "static",
    )
    app.config.from_object(config_by_name[config_name])
    
    # Initialize services and store them for access within the application context
    @app.before_request
    def before_request():
        if 'server_discovery' not in g:
            g.server_discovery = RegistryDiscoverer(app.config['WORKSPACE_ROOT'])
        if 'virtual_server_manager' not in g:
            g.virtual_server_manager = VirtualServerManager(app.config['WORKSPACE_ROOT'])
        if 'prompt_manager' not in g:
            prompt_storage = YAMLPromptStorage(str(Path(app.config['WORKSPACE_ROOT']) / 'web-interface' / 'custom-prompts'))
            g.prompt_manager = PromptManager(prompt_storage)
        if 'storage_backend' not in g:
            storage_config = StorageConfig(
                backend_type="yaml",
                backup_enabled=True,
                backup_count=5,
                encryption_enabled=False,
                validation_enabled=True
            )
            g.storage_backend = YAMLBackend(storage_config, app.config['WORKSPACE_ROOT'])
        if 'tool_proxy_router' not in g:
            http_handler = HttpTransportHandler()
            stdio_handler = StdioTransportHandler(app.config['WORKSPACE_ROOT'])
            transport_handlers = {
                "http": http_handler,
                "stdio": stdio_handler,
            }
            g.tool_proxy_router = ToolProxyRouter(transport_handlers)

    # Register Blueprints
    from .ui.routes import ui_bp
    app.register_blueprint(ui_bp)

    from .ui.routes_prompts import prompts_bp
    app.register_blueprint(prompts_bp, url_prefix='/prompts')

    from .api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from .mcp.routes import mcp_bp
    app.register_blueprint(mcp_bp, url_prefix='/mcp')
    
    from .mcp.routes import mcp_sse_bp
    app.register_blueprint(mcp_sse_bp, url_prefix='/mcp-sse')

    logger.info(f"Flask App created with '{config_name}' config.")
    
    return app
