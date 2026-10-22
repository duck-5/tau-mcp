"""
Moodle Plugin Bridge for tau_mcp.
Dynamically mounts moodle-mcp tools, resources, and prompts onto tau_mcp.
"""

import logging
from tau_mcp.plugin_manager import PluginManager

logger = logging.getLogger("tau_mcp.plugins.moodle")


def register_plugin(server, config, cache):
    """Dynamically initializes moodle_mcp and registers all its tools onto the central server."""
    pm = PluginManager(server, config, cache)
    return pm._mount_moodle_package()
