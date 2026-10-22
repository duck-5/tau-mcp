import re
import urllib3
import requests
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

from .models import CourseInstance, CourseSession

# Suppress insecure HTTPS warning for internal TAU servers if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TAUCourseCatalogClient:
    """
    Communicates with Tel Aviv University's course catalog and schedule system
    (https://www.ims.tau.ac.il/tal/kr/Search_L.aspx).
    
    Can retrieve room numbers, sessions, lecturers, and times for ANY course and any
    instance (group) at TAU, even courses the student is not enrolled in.
    """

    SEARCH_PAGE_URL = "https://www.ims.tau.ac.il/tal/kr/search_p.aspx"
    SEARCH_ACTION_URL = "https://www.ims.tau.ac.il/tal/kr/Search_L.aspx"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.SEARCH_PAGE_URL
        })

    def _ensure_session(self):
        """Warm up the session with cookies from search_p.aspx."""
        try:
            self.session.get(self.SEARCH_PAGE_URL, verify=False, timeout=10)
        except Exception:
            pass

    def get_course_instances(self, course_number: str, year: str = "2026") -> List[CourseInstance]:
        """
        Retrieves all groups/instances of a course by course number.
        
        Args:
            course_number: Course number (e.g. '03212130' or '0321-2130')
            year: Academic year (e.g. '2026' for 2026/2027 תשפ"ז, '2025' for תשפ"ו)
            
        Returns:
            List of CourseInstance objects containing groups, sessions, rooms, lecturers, and days.
        """
        clean_course = re.sub(r"[^\d]", "", str(course_number)).zfill(8)
        self._ensure_session()

        resp = self.session.post(
            self.SEARCH_ACTION_URL,
            data={
                "txtKurs": clean_course,
                "lstYear": str(year),
                "search": "חיפוש"
            },
            headers={"Referer": self.SEARCH_PAGE_URL},
            verify=False,
            timeout=15
        )

        return self._parse_search_results(resp.text, clean_course, year)

    def search_by_name_or_lecturer(self, course_name: str = "", lecturer_name: str = "", year: str = "2026") -> List[CourseInstance]:
        """
        Searches for courses by course name or lecturer name.
        """
        self._ensure_session()
        data = {
            "txtShemKurs": course_name,
            "txtShemMore": lecturer_name,
            "lstYear1": str(year),
            "search1": "חיפוש"
        }
        resp = self.session.post(
            self.SEARCH_ACTION_URL,
            data=data,
            headers={"Referer": self.SEARCH_PAGE_URL},
            verify=False,
            timeout=15
        )
        return self._parse_search_results(resp.text, "", year)

    def get_room_number(
        self,
        course_number: str,
        group: Optional[str] = None,
        day: Optional[str] = None,
        lesson_type: Optional[str] = None,
        year: str = "2026"
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to look up room number and building for any course instance.
        
        Args:
            course_number: 8-digit TAU course ID (e.g. "03212130" or "03682158")
            group: Optional group number (e.g. "01", "02")
            day: Optional day filter (e.g. "א", "ב", "ג", "ד", "ה")
            lesson_type: Optional filter (e.g. "שיעור" or "תרגיל")
            year: Academic year (default "2026")
            
        Returns:
            List of dictionaries with room details:
            [
                {
                    "course_number": "03212130",
                    "course_name": "שיטות בפיזיקה עיונית 1",
                    "group": "01",
                    "lesson_type": "שיעור",
                    "building": "אודיטור' לב",
                    "room": "009",
                    "day": "ד",
                    "time": "12:00-14:00",
                    "semester": "א'",
                    "lecturer": "פרופ' אופנהימר נעמי"
                },
                ...
            ]
        """
        instances = self.get_course_instances(course_number, year=year)
        results = []

        clean_group = str(group).zfill(2) if group else None

        for inst in instances:
            if clean_group and inst.group != clean_group:
                continue

            for sess in inst.sessions:
                if day and sess.day.strip() != day.strip():
                    continue
                if lesson_type and lesson_type.strip() not in sess.lesson_type:
                    continue

                results.append({
                    "course_number": inst.course_number,
                    "course_name": inst.course_name,
                    "group": inst.group,
                    "faculty_dept": inst.faculty_dept,
                    "lesson_type": sess.lesson_type,
                    "building": sess.building,
                    "room": sess.room,
                    "day": sess.day,
                    "time": sess.time,
                    "semester": sess.semester,
                    "lecturer": sess.lecturer
                })

        return results

    def _parse_search_results(self, html_content: str, default_course_num: str, year: str) -> List[CourseInstance]:
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")
        if len(tables) < 3:
            return []

        main_table = tables[2]
        rows = main_table.find_all("tr")

        instances: List[CourseInstance] = []
        current_instance: Optional[CourseInstance] = None
        last_lecturer = ""

        i = 0
        while i < len(rows):
            row = rows[i]
            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
            
            # Check for header row of a new group: ['מספר קורס', 'שם קורס']
            if len(cells) >= 2 and cells[0] == "מספר קורס" and cells[1] == "שם קורס":
                # Save previous instance
                if current_instance:
                    instances.append(current_instance)
                    current_instance = None
                    last_lecturer = ""

                i += 1
                if i >= len(rows):
                    break
                    
                # Next row: ["0321-2130קב':01", 'שיטות בפיזיקה עיונית 1']
                info_row = [c.get_text(strip=True) for c in rows[i].find_all(["th", "td"])]
                course_str = info_row[0] if len(info_row) > 0 else ""
                course_name = info_row[1] if len(info_row) > 1 else ""

                # Extract course and group
                course_match = re.search(r"(\d{4}-?\d{4})", course_str)
                c_num = course_match.group(1).replace("-", "") if course_match else default_course_num
                
                grp_match = re.search(r"קב'?:?\s*(\d+)", course_str)
                grp_num = grp_match.group(1).zfill(2) if grp_match else "01"

                # Next row usually has faculty / department: ['', 'מדעים מדויקים/פיזיקה']
                i += 1
                dept = ""
                if i < len(rows):
                    dept_cells = [c.get_text(strip=True) for c in rows[i].find_all(["th", "td"])]
                    if len(dept_cells) >= 2:
                        dept = dept_cells[1]
                    elif len(dept_cells) == 1:
                        dept = dept_cells[0]

                current_instance = CourseInstance(
                    course_number=c_num,
                    group=grp_num,
                    course_name=course_name,
                    faculty_dept=dept,
                    year=year,
                    sessions=[]
                )
                
                # Next row might be table column headers:
                # ['שם מרצה', 'אופן הוראה', 'בניין', 'חדר', 'יום', 'שעה', 'סמסטר']
                i += 1
                if i < len(rows):
                    col_cells = [c.get_text(strip=True) for c in rows[i].find_all(["th", "td"])]
                    if "בניין" in col_cells or "חדר" in col_cells:
                        # Move to session rows
                        i += 1

                # Parse subsequent session rows until links row or next group
                while i < len(rows):
                    s_row = rows[i]
                    s_cells = [c.get_text(strip=True) for c in s_row.find_all(["th", "td"])]

                    # Stop conditions
                    if not any(s_cells) or "מספר קורס" in s_cells or "סילבוס" in "".join(s_cells):
                        break

                    # A session row typically has:
                    # [lecturer, lesson_type, building, room, day, time, semester] (7 cells)
                    if len(s_cells) >= 6:
                        lecturer = s_cells[0].strip() or last_lecturer
                        if s_cells[0].strip():
                            last_lecturer = s_cells[0].strip()

                        lesson_type = s_cells[1].strip()
                        building = s_cells[2].strip()
                        room = s_cells[3].strip()
                        day = s_cells[4].strip()
                        time_str = s_cells[5].strip()
                        semester = s_cells[6].strip() if len(s_cells) > 6 else ""

                        current_instance.sessions.append(
                            CourseSession(
                                day=day,
                                time=time_str,
                                lesson_type=lesson_type,
                                building=building,
                                room=room,
                                lecturer=lecturer,
                                semester=semester
                            )
                        )
                    i += 1
                continue

            i += 1

        if current_instance:
            instances.append(current_instance)

        return instances
