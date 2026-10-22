"""
MCP / Gemini Tool Definitions for Tel Aviv University (TAU).
These functions and schemas are ready to be plugged directly into:
- FastMCP / MCP Server
- Gemini Function Calling (google-genai / google-generativeai)
- LangChain / LlamaIndex / OpenAI Tool Calling
"""

from typing import Dict, Any, Optional, List
from .client import TAUClient

_client_instance: Optional[TAUClient] = None

def get_client() -> TAUClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = TAUClient()
    return _client_instance

# -------------------------------------------------------------
# Tool Implementations
# -------------------------------------------------------------

def get_course_room_number(
    course_number: str,
    group: Optional[str] = None,
    day: Optional[str] = None,
    year: str = "2026"
) -> List[Dict[str, Any]]:
    """
    Look up the room number and building for ANY Tel Aviv University course and instance/group,
    including courses the student is NOT enrolled in.

    Args:
        course_number: 8-digit TAU course ID (e.g. '03212130' or '03682158').
        group: Optional group/instance number (e.g. '01', '02'). If omitted, all groups are returned.
        day: Optional day of the week ('א', 'ב', 'ג', 'ד', 'ה', 'ו').
        year: Academic year (defaults to '2026' for 2026/2027 תשפ"ז).

    Returns:
        A list of sessions with course number, name, group, building, room number, day, time, and lecturer.
    """
    client = get_client()
    return client.get_room_number(
        course_number=course_number,
        group=group,
        day=day,
        year=year
    )

def get_my_schedule(from_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get the authenticated student's personal schedule and upcoming classes with room numbers,
    buildings, and GPS coordinates.

    Args:
        from_date: Optional start date in 'YYYY-MM-DD' format. Defaults to today.

    Returns:
        List of personal schedule events including course name, room, building, start/end time, and lecturer.
    """
    client = get_client()
    events = client.get_personal_schedule(from_date=from_date)
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
            "room": e.room,
            "lecturer": e.lecturer,
            "gps_coordinates": {"lat": e.lat, "lon": e.lon} if e.lat and e.lon else None
        }
        for e in events
    ]

def get_my_grades() -> List[Dict[str, Any]]:
    """
    Get the authenticated student's grades across all semesters.

    Returns:
        List of grade records with course ID, course description, final grade, credits, year, and semester.
    """
    client = get_client()
    grades = client.get_grades()
    return [
        {
            "course_number": g.course_number,
            "course_name": g.course_name,
            "final_grade": g.final_grade,
            "weight": g.weight,
            "year_he": g.year_he,
            "semester_he": g.semester_he,
            "moed": g.moed,
            "is_finished": g.is_finished,
            "remarks": g.remarks
        }
        for g in grades
    ]

def get_my_gpa() -> List[Dict[str, Any]]:
    """
    Get the authenticated student's cumulative grade point average (GPA) and total credit points.

    Returns:
        List of GPA stats per degree/program of study.
    """
    client = get_client()
    stats = client.get_gpa()
    return [
        {
            "program": s.program_desc,
            "avg_grade": s.avg_grade,
            "total_hours": s.total_hours,
            "final_weight": s.final_weight
        }
        for s in stats
    ]

def get_my_messages(include_earlier: bool = True) -> List[Dict[str, Any]]:
    """
    Get the authenticated student's portal messages, alerts, and course room change announcements.

    Args:
        include_earlier: Whether to include earlier historical messages (default: True).

    Returns:
        List of messages with subject, full message text, start date, and urgency status.
    """
    client = get_client()
    msgs = client.get_messages(include_earlier=include_earlier)
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

def get_my_exams() -> List[Dict[str, Any]]:
    """
    Get the authenticated student's exam dates, Moed A/B schedule, and scanned notebook status.

    Returns:
        List of exams with course ID, name, date, time, moed, grade, and scan status.
    """
    client = get_client()
    exams = client.get_exams()
    return [
        {
            "course_number": ex.course_number,
            "course_name": ex.course_name,
            "assignment_type": ex.assignment_type,
            "due_date": ex.due_date,
            "start_time": ex.start_time,
            "moed": ex.moed,
            "final_grade": ex.final_grade,
            "scan_status": ex.scan_status,
            "appeal_status": ex.appeal_status
        }
        for ex in exams
    ]

def search_university_courses(query: str, by_lecturer: bool = False, year: str = "2026") -> List[Dict[str, Any]]:
    """
    Search the Tel Aviv University course catalog by course title or lecturer name.

    Args:
        query: Course name or lecturer name to search.
        by_lecturer: Set to True to search by lecturer name instead of course title.
        year: Academic year (default '2026').

    Returns:
        List of matched course instances with their group numbers and session counts.
    """
    client = get_client()
    courses = client.search_courses(query=query, by_lecturer=by_lecturer, year=year)
    return [
        {
            "course_number": c.course_number,
            "course_name": c.course_name,
            "group": c.group,
            "faculty_dept": c.faculty_dept,
            "session_count": len(c.sessions),
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

# -------------------------------------------------------------
# MCP / Gemini Function Declaration Registry
# -------------------------------------------------------------
TAU_MCP_TOOLS = {
    "get_course_room_number": get_course_room_number,
    "get_my_schedule": get_my_schedule,
    "get_my_grades": get_my_grades,
    "get_my_gpa": get_my_gpa,
    "get_my_messages": get_my_messages,
    "get_my_exams": get_my_exams,
    "search_university_courses": search_university_courses
}
