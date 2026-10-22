"""
Client for Tel Aviv University's course catalog and classroom schedule system
(https://www.ims.tau.ac.il/tal/kr/Search_L.aspx).
Provides room numbers, buildings, session times, days, and lecturers for ANY course.
"""

import re
import logging
import urllib3
import requests
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

from tau_mcp.storage import CacheManager
from tau_mcp.core.models import CourseInstance, CourseSession

# Suppress insecure HTTPS warning for internal TAU servers if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("tau_mcp.catalog")

class TAUCourseCatalogClient:
    SEARCH_PAGE_URL = "https://www.ims.tau.ac.il/tal/kr/search_p.aspx"
    SEARCH_ACTION_URL = "https://www.ims.tau.ac.il/tal/kr/Search_L.aspx"

    def __init__(self, cache: Optional[CacheManager] = None):
        self.cache = cache or CacheManager()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.SEARCH_PAGE_URL
        })

    def _ensure_session(self) -> None:
        try:
            self.session.get(self.SEARCH_PAGE_URL, verify=False, timeout=10)
        except Exception:
            pass

    def get_course_instances(self, course_number: str, year: str = "2026") -> List[CourseInstance]:
        """Retrieves all groups/instances of a course by course number with caching."""
        clean_course = re.sub(r"[^\d]", "", str(course_number)).zfill(8)
        cache_key = f"catalog:course:{clean_course}:{year}"

        cached = self.cache.get(cache_key, max_age=3600)  # 1 hour TTL
        if cached is not None:
            return cached

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

        instances = self._parse_search_results(resp.text, clean_course, year)
        self.cache.set(cache_key, instances)
        return instances

    def search_by_name_or_lecturer(
        self,
        course_name: str = "",
        lecturer_name: str = "",
        year: str = "2026"
    ) -> List[CourseInstance]:
        """Searches courses by title or lecturer name."""
        cache_key = f"catalog:search:{course_name}:{lecturer_name}:{year}"
        cached = self.cache.get(cache_key, max_age=3600)
        if cached is not None:
            return cached

        self._ensure_session()
        resp = self.session.post(
            self.SEARCH_ACTION_URL,
            data={
                "txtShemKurs": course_name,
                "txtShemMore": lecturer_name,
                "lstYear1": str(year),
                "search1": "חיפוש"
            },
            headers={"Referer": self.SEARCH_PAGE_URL},
            verify=False,
            timeout=15
        )
        instances = self._parse_search_results(resp.text, "", year)
        self.cache.set(cache_key, instances)
        return instances

    def get_room_number(
        self,
        course_number: str,
        group: Optional[str] = None,
        day: Optional[str] = None,
        hour: Optional[str] = None,
        lesson_type: Optional[str] = None,
        year: str = "2026"
    ) -> List[Dict[str, Any]]:
        """
        Looks up room numbers and buildings for any course, filtering by group, day, or hour.
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
                if hour and not self._is_hour_matching(hour, sess.time):
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

    @staticmethod
    def _is_hour_matching(target_hour: str, session_time: str) -> bool:
        """Checks if a target hour (e.g. '12:00' or '13') falls within session_time (e.g. '12:00-14:00')."""
        target = target_hour.strip().replace(" ", "")
        time_slot = session_time.strip().replace(" ", "")

        if target in time_slot:
            return True

        # Parse ranges like "12:00-14:00"
        match = re.match(r"(\d{1,2})(?::(\d{2}))?-(\d{1,2})(?::(\d{2}))?", time_slot)
        t_match = re.match(r"(\d{1,2})(?::(\d{2}))?", target)
        if match and t_match:
            try:
                start_h = int(match.group(1))
                end_h = int(match.group(3))
                cur_h = int(t_match.group(1))
                return start_h <= cur_h < end_h or (cur_h == end_h and t_match.group(2) == "00")
            except Exception:
                pass
        return False

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

            if len(cells) >= 2 and cells[0] == "מספר קורס" and cells[1] == "שם קורס":
                if current_instance:
                    instances.append(current_instance)
                    current_instance = None
                    last_lecturer = ""

                i += 1
                if i >= len(rows):
                    break

                info_row = [c.get_text(strip=True) for c in rows[i].find_all(["th", "td"])]
                course_str = info_row[0] if len(info_row) > 0 else ""
                course_name = info_row[1] if len(info_row) > 1 else ""

                course_match = re.search(r"(\d{4}-?\d{4})", course_str)
                c_num = course_match.group(1).replace("-", "") if course_match else default_course_num

                grp_match = re.search(r"קב'?:?\s*(\d+)", course_str)
                grp_num = grp_match.group(1).zfill(2) if grp_match else "01"

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

                i += 1
                if i < len(rows):
                    col_cells = [c.get_text(strip=True) for c in rows[i].find_all(["th", "td"])]
                    if "בניין" in col_cells or "חדר" in col_cells:
                        i += 1

                while i < len(rows):
                    s_row = rows[i]
                    s_cells = [c.get_text(strip=True) for c in s_row.find_all(["th", "td"])]

                    if not any(s_cells) or "מספר קורס" in s_cells or "סילבוס" in "".join(s_cells):
                        break

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
