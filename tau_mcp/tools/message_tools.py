"""Messages, announcements, and student profile tools for Tel Aviv University."""

from typing import Any, Dict, List, Optional
from tau_mcp.core.portal import TAUPortalClient

def register_message_tools(server: Any, portal: TAUPortalClient) -> None:
    @server.tool(
        name="tau_get_my_messages",
        description="Get personal notifications, administrative messages, and active classroom change alerts sent by university administration via the TAU Student Portal. For course-specific forum announcements, use Moodle tools."
    )
    def tau_get_my_messages(include_earlier: bool = True) -> List[Dict[str, Any]]:
        """
        Args:
            include_earlier: Whether to include historical messages (defaults to True, where room change notices are stored).
        """
        msgs = portal.get_messages(include_earlier=include_earlier)
        return [
            {
                "id": m.id,
                "subject": m.subject,
                "message": m.message,
                "start_date": m.start_date,
                "is_urgent": m.is_urgent
            }
            for m in msgs
        ]
