"""Classroom and course catalog tools for Tel Aviv University."""

from typing import Any, Dict, List, Optional
from tau_mcp.core.catalog import TAUCourseCatalogClient
from tau_mcp.core.room_finder import RoomFinder

def register_room_tools(server: Any, catalog: TAUCourseCatalogClient, room_finder: RoomFinder) -> None:
    @server.tool(
        name="tau_get_course_room",
        description=(
            "Look up the classroom room number and building for ANY course and optional hour, day, or group, "
            "and cross-references announcements for any one-time or permanent room changes. "
            "Can be called for any course at Tel Aviv University, including courses you are NOT enrolled in."
        )
    )
    def tau_get_course_room(
        course: str,
        hour: Optional[str] = None,
        day: Optional[str] = None,
        group: Optional[str] = None,
        date: Optional[str] = None,
        year: str = "2026",
        check_changes: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Args:
            course: Course number (e.g. '03682158') or course name (e.g. 'מבני נתונים' or 'Data Structures').
            hour: Optional target hour (e.g. '12:00', '13', '14:30').
            day: Optional day of the week ('א', 'ב', 'ג', 'ד', 'ה', 'ו' or 'Sunday', 'Wednesday').
            group: Optional group number ('01', '02', '14', etc.).
            date: Optional date ('YYYY-MM-DD'). Inferred to determine weekday and match temporary notices.
            year: Academic year (default '2026' for 2026/2027 תשפ"ז).
            check_changes: Whether to cross-reference university announcements for room changes (default True).
        """
        return room_finder.find_room(
            course=course,
            hour=hour,
            day=day,
            group=group,
            date=date,
            year=year,
            check_changes=check_changes
        )

    @server.tool(
        name="tau_search_courses",
        description="Search the Tel Aviv University course catalog by course title or lecturer name to find course IDs, groups, and schedules."
    )
    def tau_search_courses(query: str, by_lecturer: bool = False, year: str = "2026") -> List[Dict[str, Any]]:
        """
        Args:
            query: Course title or lecturer name to search.
            by_lecturer: Set to True to search by lecturer name instead of course title.
            year: Academic year (default '2026').
        """
        if by_lecturer:
            courses = catalog.search_by_name_or_lecturer(lecturer_name=query, year=year)
        else:
            courses = catalog.search_by_name_or_lecturer(course_name=query, year=year)

        return [
            {
                "course_number": c.course_number,
                "course_name": c.course_name,
                "group": c.group,
                "faculty_dept": c.faculty_dept,
                "sessions_count": len(c.sessions),
                "sessions": [
                    {
                        "day": s.day,
                        "time": s.time,
                        "lesson_type": s.lesson_type,
                        "building": s.building,
                        "room": s.room,
                        "lecturer": s.lecturer
                    }
                    for s in c.sessions
                ]
            }
            for c in courses
        ]
