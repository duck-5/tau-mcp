"""Academic records, grades, and exams tools for Tel Aviv University."""

from typing import Any, Dict, List, Optional
from tau_mcp.core.portal import TAUPortalClient

def register_academic_tools(server: Any, portal: TAUPortalClient) -> None:
    @server.tool(
        name="tau_get_my_grades",
        description="Get the authenticated student's full course grade records across all semesters, with credit weights, passing status, and notes."
    )
    def tau_get_my_grades() -> List[Dict[str, Any]]:
        grades = portal.get_grades()
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

    @server.tool(
        name="tau_get_my_gpa",
        description="Get the authenticated student's cumulative grade point average (GPA) and total credit points per degree program/major."
    )
    def tau_get_my_gpa() -> List[Dict[str, Any]]:
        stats = portal.get_gpa_stats()
        return [
            {
                "program": s.program_desc,
                "program_en": s.program_desc_en,
                "avg_grade": s.avg_grade,
                "total_hours": s.total_hours,
                "final_weight": s.final_weight
            }
            for s in stats
        ]

    @server.tool(
        name="tau_get_my_exams",
        description="Get the authenticated student's exam dates (Moed A & Moed B), start times, exam grades, and notebook scan statuses."
    )
    def tau_get_my_exams() -> List[Dict[str, Any]]:
        exams = portal.get_exams()
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
