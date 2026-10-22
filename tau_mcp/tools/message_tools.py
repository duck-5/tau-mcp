"""Messages, announcements, and student profile tools for Tel Aviv University."""

from typing import Any, Dict, List, Optional
from tau_mcp.core.portal import TAUPortalClient

def register_message_tools(server: Any, portal: TAUPortalClient) -> None:
    @server.tool(
        name="tau_get_my_messages",
        description="Get the authenticated student's portal messages, alerts, and course room change announcements."
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

    @server.tool(
        name="tau_get_user_profile",
        description="Get the authenticated student's personal information and enrolled academic degree details."
    )
    def tau_get_user_profile() -> Dict[str, Any]:
        return portal.get_user_profile()
