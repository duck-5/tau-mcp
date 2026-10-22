from typing import List, Dict, Optional, Any
from .catalog import TAUCourseCatalogClient
from .portal import TAUPortalClient
from .auth import TAUAuthManager
from .models import (
    CourseInstance,
    PersonalScheduleEvent,
    GradeRecord,
    GPAStats,
    StudentMessage,
    ExamRecord
)

class TAUClient:
    """
    Unified client for Tel Aviv University services.
    Provides complete access to:
    1. Public course catalog (room lookup for any course and any instance).
    2. Authenticated student personal portal (schedule, grades, GPA, messages, exams).
    """

    def __init__(
        self,
        username: Optional[str] = None,
        id_number: Optional[str] = None,
        password: Optional[str] = None,
        env_file: str = ".env"
    ):
        self.catalog = TAUCourseCatalogClient()
        self.auth_manager = TAUAuthManager(
            username=username,
            id_number=id_number,
            password=password,
            env_file=env_file
        )
        self._portal: Optional[TAUPortalClient] = None

    @property
    def portal(self) -> TAUPortalClient:
        """Lazy-loaded portal client (authenticates on first use)."""
        if self._portal is None:
            self._portal = TAUPortalClient(self.auth_manager)
        return self._portal

    # ---------------------------------------------------------
    # 1. Course Room & Schedule Lookup (ANY Course & ANY Group)
    # ---------------------------------------------------------
    def get_room_number(
        self,
        course_number: str,
        group: Optional[str] = None,
        day: Optional[str] = None,
        lesson_type: Optional[str] = None,
        year: str = "2026"
    ) -> List[Dict[str, Any]]:
        """
        Get room number and building for ANY course and ANY instance at TAU,
        even if the student is not enrolled in it.
        
        Args:
            course_number: 8-digit TAU course ID (e.g. '03212130' or '03682158')
            group: Optional group number (e.g. '01', '02')
            day: Optional day of week ('א', 'ב', 'ג', 'ד', 'ה')
            lesson_type: Optional type ('שיעור' or 'תרגיל')
            year: Academic year (default '2026' for 2026/2027 תשפ"ז)
        """
        return self.catalog.get_room_number(
            course_number=course_number,
            group=group,
            day=day,
            lesson_type=lesson_type,
            year=year
        )

    def get_course_details(self, course_number: str, year: str = "2026") -> List[CourseInstance]:
        """
        Get all groups, sessions, lecturers, and times for any course in the catalog.
        """
        return self.catalog.get_course_instances(course_number=course_number, year=year)

    def search_courses(self, query: str, by_lecturer: bool = False, year: str = "2026") -> List[CourseInstance]:
        """
        Search catalog courses by name or lecturer name.
        """
        if by_lecturer:
            return self.catalog.search_by_name_or_lecturer(lecturer_name=query, year=year)
        else:
            return self.catalog.search_by_name_or_lecturer(course_name=query, year=year)

    # ---------------------------------------------------------
    # 2. Personal Student Data (Authenticated)
    # ---------------------------------------------------------
    def get_personal_schedule(self, from_date: Optional[str] = None) -> List[PersonalScheduleEvent]:
        """
        Get student's enrolled courses and schedule with room numbers and GPS coordinates.
        """
        return self.portal.get_personal_schedule(from_date=from_date)

    def get_grades(self) -> List[GradeRecord]:
        """
        Get student's grades across all semesters.
        """
        return self.portal.get_grades()

    def get_gpa(self) -> List[GPAStats]:
        """
        Get student's cumulative GPA and credit points per study program.
        """
        return self.portal.get_gpa_stats()

    def get_messages(self, include_earlier: bool = True) -> List[StudentMessage]:
        """
        Get student messages, announcements, and course room change updates.
        """
        return self.portal.get_messages(include_earlier=include_earlier)

    def get_exams(self) -> List[ExamRecord]:
        """
        Get exam dates, start times, assignment types, and scan status.
        """
        return self.portal.get_exams()

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get student profile details.
        """
        return self.portal.get_user_data()
