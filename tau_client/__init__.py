"""
Tel Aviv University (TAU) Python Communication Channel.
Provides unified access to:
1. Public course catalog (lookup room numbers of ANY course and any group instance).
2. Authenticated student personal portal (personal schedule, grades, GPA, messages, exams).
"""

from .client import TAUClient
from .catalog import TAUCourseCatalogClient
from .portal import TAUPortalClient
from .auth import TAUAuthManager
from .models import (
    CourseInstance,
    CourseSession,
    PersonalScheduleEvent,
    GradeRecord,
    GPAStats,
    StudentMessage,
    ExamRecord
)
from .tools import (
    get_course_room_number,
    get_my_schedule,
    get_my_grades,
    get_my_gpa,
    get_my_messages,
    get_my_exams,
    search_university_courses,
    TAU_MCP_TOOLS
)

__all__ = [
    "TAUClient",
    "TAUCourseCatalogClient",
    "TAUPortalClient",
    "TAUAuthManager",
    "CourseInstance",
    "CourseSession",
    "PersonalScheduleEvent",
    "GradeRecord",
    "GPAStats",
    "StudentMessage",
    "ExamRecord",
    "get_course_room_number",
    "get_my_schedule",
    "get_my_grades",
    "get_my_gpa",
    "get_my_messages",
    "get_my_exams",
    "search_university_courses",
    "TAU_MCP_TOOLS"
]
