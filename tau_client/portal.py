import json
import datetime
import requests
from typing import List, Dict, Optional, Any

from .auth import TAUAuthManager
from .models import (
    PersonalScheduleEvent,
    GradeRecord,
    GPAStats,
    StudentMessage,
    ExamRecord
)

class TAUPortalClient:
    """
    Communicates with Tel Aviv University's student personal portal
    (https://my.tau.ac.il/TAU_Student/) via OutSystems Reactive screen services.
    """

    BASE_URL = "https://my.tau.ac.il/TAU_Student/screenservices"
    MODULE_VERSION = "Yx_Lnh4Gkv3UQSOjVN7SHw"

    def __init__(self, auth_manager: Optional[TAUAuthManager] = None):
        self.auth_manager = auth_manager or TAUAuthManager()
        self.session = requests.Session()
        self.cookies: Dict[str, str] = {}
        self.csrf_token: str = ""
        self._load_session()

    def _load_session(self, force_refresh: bool = False):
        self.cookies, self.csrf_token = self.auth_manager.get_authenticated_session(force_refresh=force_refresh)

    def _call_screenservice(
        self,
        path: str,
        api_version: str,
        view_name: str = "",
        screen_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Sends an authenticated POST request to an OutSystems screen service endpoint.
        Automatically retries on session expiration.
        """
        v_name = view_name or kwargs.get("viewName", "")
        url = f"{self.BASE_URL}/{path}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": "https://my.tau.ac.il/TAU_Student/",
            "outsystems-locale": "he-IL",
            "x-csrftoken": self.csrf_token
        }

        payload = {
            "versionInfo": {
                "moduleVersion": self.MODULE_VERSION,
                "apiVersion": api_version
            },
            "viewName": v_name,
            "screenData": screen_data or {"variables": {}}
        }

        resp = self.session.post(url, headers=headers, cookies=self.cookies, json=payload, timeout=20)

        # Check for expired session
        if resp.status_code in (401, 403) or (resp.status_code == 200 and "Invalid Login" in resp.text):
            print("[TAUPortalClient] Session expired. Re-authenticating...")
            self._load_session(force_refresh=True)
            headers["x-csrftoken"] = self.csrf_token
            resp = self.session.post(url, headers=headers, cookies=self.cookies, json=payload, timeout=20)

        if resp.status_code != 200:
            raise RuntimeError(f"TAU API error ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        if "exception" in res_json and res_json["exception"]:
            err_msg = res_json["exception"].get("message", "Unknown OutSystems exception")
            raise RuntimeError(f"TAU OutSystems error: {err_msg}")

        return res_json.get("data", {})

    def get_grades(self) -> List[GradeRecord]:
        """
        Retrieves all course grades for the student across all semesters.
        """
        data = self._call_screenservice(
            path="TAU_Student/StudentMainFlow/CourseGrades/DataActionGetCourseGradesList",
            api_version="fDJ257L+MkP9mHb8zhzdnA",
            viewName="StudentMainFlow.CourseGrades"
        )

        grades_raw = data.get("CourseGradesList", {}).get("List", [])
        records = []
        for g in grades_raw:
            records.append(
                GradeRecord(
                    course_number=g.get("CourseNumber", ""),
                    group=g.get("CourseGroup", ""),
                    course_name=g.get("CourseDescription", ""),
                    course_name_en=g.get("CourseDescriptionEng", ""),
                    final_grade=g.get("FinalGrade") if g.get("FinalGrade") != "" else None,
                    weight=g.get("Weight", ""),
                    year_semester=g.get("YearAndSemester", ""),
                    semester_he=g.get("SemesterHeb", ""),
                    year_he=g.get("YearHeb", ""),
                    moed=g.get("DueInHeb", ""),
                    is_finished=g.get("CourseFinished", "") == "1",
                    remarks=g.get("Remarks", "")
                )
            )
        return records

    def get_gpa_stats(self) -> List[GPAStats]:
        """
        Retrieves degree average (GPA) and total credit hours per study program.
        """
        data = self._call_screenservice(
            path="TAU_Block/TAUBlocks/BlackGradesStats/DataActionGetProgramStudyGradesStats",
            api_version="qHMHE6fwWYAXzgwUnpFKYQ",
            view_name="StudentMainFlow.CourseGrades"
        )

        stats_raw = data.get("GetProgramStudyGradesStatsList", {}).get("List", [])
        results = []
        for s in stats_raw:
            try:
                avg = float(s.get("AvgGrade", 0))
            except (ValueError, TypeError):
                avg = 0.0
            try:
                hours = float(s.get("TotalHours", 0))
            except (ValueError, TypeError):
                hours = 0.0
            try:
                weight = float(s.get("FinalWeight", 0))
            except (ValueError, TypeError):
                weight = 0.0

            results.append(
                GPAStats(
                    program_desc=s.get("ProgramStudyDesc", ""),
                    program_desc_en=s.get("ProgramStudyDescEn", ""),
                    avg_grade=avg,
                    total_hours=hours,
                    final_weight=weight
                )
            )
        return results

    def get_personal_schedule(self, from_date: Optional[str] = None) -> List[PersonalScheduleEvent]:
        """
        Retrieves student's schedule and classes (dates, times, buildings, rooms, lecturers).
        
        Args:
            from_date: Date string formatted as 'YYYY-MM-DD'. Defaults to today.
        """
        if not from_date:
            from_date = datetime.date.today().strftime("%Y-%m-%d")

        data = self._call_screenservice(
            path="TAU_Student/Blocks/EventsBlock/DataActionGetDashboardSchedulesList",
            api_version="+_Req5UHxUR+oQOGjlE6uA",
            viewName="StudentMainFlow.Dashboard",
            screen_data={
                "variables": {
                    "FromDate": from_date,
                    "FromDashboard": True
                }
            }
        )

        days_raw = data.get("SchedulesList", {}).get("List", [])
        events = []
        for day in days_raw:
            sched_items = day.get("SchedulesList", {}).get("List", [])
            for item in sched_items:
                events.append(
                    PersonalScheduleEvent(
                        date=day.get("Date", ""),
                        start_time=item.get("start", ""),
                        end_time=item.get("end", ""),
                        title=item.get("title", ""),
                        title_en=item.get("TitleEng", ""),
                        course_number=item.get("CourseNumber", ""),
                        group=item.get("Group", ""),
                        lesson_type=item.get("LessonTypeHeb", ""),
                        building_he=item.get("BuildingNameHeb", ""),
                        building_en=item.get("BuildingNameEng", ""),
                        room=item.get("Room", ""),
                        lecturer=f"{item.get('LecturerFirstNameHeb', '')} {item.get('LecturerLastNameHeb', '')}".strip(),
                        lat=item.get("BuildingLocationLength"),
                        lon=item.get("BuildingLocationWidth"),
                        event_type=item.get("EventType", "course")
                    )
                )
        return events

    def get_messages(self, include_earlier: bool = True) -> List[StudentMessage]:
        """
        Retrieves student messages and announcements (including course room changes).
        """
        messages_dict = {}

        # 1. Important / Dashboard messages
        try:
            data_imp = self._call_screenservice(
                path="TAU_Student/Blocks/MessageSliderBlock/DataActionGetImportantMessages",
                api_version="y1fjjHXkDwMoXwy91HAIDA",
                viewName="StudentMainFlow.Dashboard"
            )
            for m in data_imp.get("UserMessageList", {}).get("List", []):
                m_id = m.get("Id", "")
                if m_id and m_id not in messages_dict:
                    messages_dict[m_id] = StudentMessage(
                        id=m_id,
                        subject=m.get("Subject", ""),
                        subject_en=m.get("SubjectEn", ""),
                        message=m.get("Message", ""),
                        message_en=m.get("MessageEn", ""),
                        start_date=m.get("StartDate", ""),
                        due_date=m.get("DueDate", ""),
                        is_urgent=m.get("IsPush", False),
                        source=m.get("Source", "")
                    )
        except Exception as e:
            print(f"[TAUPortalClient] Failed fetching important messages: {e}")

        # 2. Earlier / Historical messages (where course changes are recorded)
        if include_earlier:
            try:
                data_earlier = self._call_screenservice(
                    path="TAU_Student/Blocks/EarlierMessagesBlock/DataActionGetEarlierMessageData",
                    api_version="ZOvyt3NRI2A7Y5O8OC83Wg",
                    viewName="StudentMainFlow.Messages",
                    screen_data={
                        "variables": {
                            "FromDate": "2026-01-01",
                            "HideExpiredMessages": False
                        }
                    }
                )
                for m in data_earlier.get("MessageList", {}).get("List", []):
                    m_id = m.get("Id", "")
                    if m_id and m_id not in messages_dict:
                        messages_dict[m_id] = StudentMessage(
                            id=m_id,
                            subject=m.get("Subject", ""),
                            subject_en=m.get("SubjectEn", ""),
                            message=m.get("Message", ""),
                            message_en=m.get("MessageEn", ""),
                            start_date=m.get("StartDate", ""),
                            due_date=m.get("DueDate", ""),
                            is_urgent=m.get("IsPush", False),
                            source=m.get("Source", "")
                        )
            except Exception as e:
                print(f"[TAUPortalClient] Failed fetching earlier messages: {e}")

        return list(messages_dict.values())

    def get_exams(self) -> List[ExamRecord]:
        """
        Retrieves exam schedules, assignment dates, and grades.
        """
        data = self._call_screenservice(
            path="TAU_Student/StudentMainFlow/ExamsAndTasks/DataActionGetExamsAndTasks",
            api_version="hcTqpPBc3elcIIz_NydUgQ",
            viewName="StudentMainFlow.ExamsAndTasks"
        )

        exams_raw = data.get("ExamsAndTasksLis", {}).get("List", [])
        records = []
        for ex in exams_raw:
            records.append(
                ExamRecord(
                    course_number=ex.get("Course", ""),
                    group=ex.get("Group", ""),
                    course_name=ex.get("CourseDescription", ""),
                    assignment_type=ex.get("AssignmentDescription", ""),
                    due_date=ex.get("DueDate", ""),
                    start_time=ex.get("FromTime", ""),
                    moed=ex.get("DueDescription", ""),
                    final_grade=ex.get("FinalGrade") if ex.get("FinalGrade") != "" else None,
                    scan_file_name=ex.get("ScanFileName"),
                    scan_status=ex.get("ScanStatus"),
                    appeal_status=ex.get("AppealStatus")
                )
            )
        return records

    def get_user_data(self) -> Dict[str, Any]:
        """
        Retrieves student personal information (Name, ID, Degree status).
        """
        data = self._call_screenservice(
            path="TAU_Student/LayoutStudent/NewCustomMenuLayout/DataActionGetTauUserData",
            api_version="x_zV_Xw2e0K+h37aI_1pUg",
            viewName="StudentMainFlow.Dashboard"
        )
        return data.get("TauUserData", {})
