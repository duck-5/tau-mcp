"""Core TAU Portal and Course Catalog components."""

from .models import (
    CourseInstance,
    CourseSession,
    PersonalScheduleEvent,
    GradeRecord,
    GPAStats,
    StudentMessage,
    ExamRecord,
    RoomLookupResult
)
from .auth import TAUAuthManager, TAUAuthError
from .catalog import TAUCourseCatalogClient
from .portal import TAUPortalClient
from .room_finder import RoomFinder

__all__ = [
    "CourseInstance",
    "CourseSession",
    "PersonalScheduleEvent",
    "GradeRecord",
    "GPAStats",
    "StudentMessage",
    "ExamRecord",
    "RoomLookupResult",
    "TAUAuthManager",
    "TAUAuthError",
    "TAUCourseCatalogClient",
    "TAUPortalClient",
    "RoomFinder"
]
