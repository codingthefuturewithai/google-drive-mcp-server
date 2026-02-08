"""MCP server package initialization"""

from google_drive.config import load_config
from google_drive.server.app import create_mcp_server

# Create server instance with default configuration
server = create_mcp_server(load_config())

__all__ = ["server", "create_mcp_server"]
