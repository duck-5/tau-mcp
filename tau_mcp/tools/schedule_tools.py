"""Personal schedule tools for Tel Aviv University."""

from typing import Any, Dict, List, Optional
from tau_mcp.core.portal import TAUPortalClient

def register_schedule_tools(server: Any, portal: TAUPortalClient) -> None:
    @server.tool(
        name="tau_get_my_schedule",
        description=(
            "Get the authenticated student's enrolled schedule and upcoming classes with classroom room numbers, "
            "building names, lecturers, and campus map GPS coordinates."
        )
    )
    def tau_get_my_schedule(from_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Args:
            from_date: Optional start date in 'YYYY-MM-DD' format. Defaults to today.
        """
        events = portal.get_personal_schedule(from_date=from_date)
        return [
            {
                "date": e.date,
                "start": e.start_time,
                "end": e.end_time,
                "title": e.title,
                "course_number": e.course_number,
                "group": e.group,
                "lesson_type": e.lesson_type,
                "building": e.building_he,
                "building_en": e.building_en,
                "room": e.room,
                "lecturer": e.lecturer,
                "gps": {"lat": e.lat, "lon": e.lon} if e.lat and e.lon else None
            }
            for e in events
        ]
