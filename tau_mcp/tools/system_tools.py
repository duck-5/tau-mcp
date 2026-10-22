"""System, cache, and plugin management tools for tau_mcp."""

from typing import Any, Dict, Optional
from tau_mcp.storage import CacheManager

def register_system_tools(server: Any, cache: CacheManager, plugin_names: list) -> None:
    @server.tool(
        name="tau_get_cache_stats",
        description="Get statistics and entry details on the active in-memory API response cache."
    )
    def tau_get_cache_stats() -> Dict[str, Any]:
        return cache.get_stats()

    @server.tool(
        name="tau_clear_cache",
        description="Clear in-memory cached API and catalog responses."
    )
    def tau_clear_cache(prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Args:
            prefix: Optional cache key prefix to clear (e.g. 'portal' or 'catalog').
        """
        cleared = cache.clear(prefix=prefix)
        return {"cleared_entries": cleared, "prefix": prefix or "all"}

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
