"""Unified tool registration for tau_mcp."""

from typing import Any
from .room_tools import register_room_tools
from .schedule_tools import register_schedule_tools
from .academic_tools import register_academic_tools
from .message_tools import register_message_tools
from .system_tools import register_system_tools

def register_all_tau_tools(
    server: Any,
    portal: Any,
    catalog: Any,
    room_finder: Any,
    cache: Any,
    plugin_names: list
) -> None:
    """Registers all core TAU tools onto the MCPServer."""
    register_room_tools(server, catalog, room_finder)
    register_schedule_tools(server, portal)
    register_academic_tools(server, portal)
    register_message_tools(server, portal)
    register_system_tools(server, cache, plugin_names)
