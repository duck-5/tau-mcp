"""
tau_mcp: Tel Aviv University (TAU) Model Context Protocol (MCP) Server.
Connects AI assistants to student portal, course catalog, classroom finder, and Moodle.
"""

from tau_mcp.server import create_server, main

__version__ = "1.0.0"

__all__ = ["create_server", "main", "__version__"]
