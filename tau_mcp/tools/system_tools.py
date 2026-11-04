"""System, cache, and plugin management tools for tau_mcp."""

from typing import Any, Dict, Optional
from tau_mcp.storage import CacheManager

def register_system_tools(server: Any, cache: CacheManager, plugin_names: list) -> None:
    @server.tool(
        name="tau_get_server_status",
        description="Get tau-mcp server operational status, active profile, and loaded plugins."
    )
    def tau_get_server_status() -> Dict[str, Any]:
        return {
            "server": "tau_mcp",
            "profile": cache.profile,
            "plugins_loaded": plugin_names,
            "status": "healthy"
        }
