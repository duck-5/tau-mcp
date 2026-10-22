"""
Intelligent classroom and room finder for Tel Aviv University.
Resolves room numbers for any course by course number or name, hour, and day,
and cross-references announcements/messages to detect any room changes or cancellations.
"""

import re
import datetime
from typing import List, Dict, Optional, Any

from tau_mcp.core.catalog import TAUCourseCatalogClient
from tau_mcp.core.portal import TAUPortalClient
from tau_mcp.core.models import RoomLookupResult

# Map English day names to Hebrew
DAY_MAP = {
    "sunday": "א", "sun": "א", "1": "א",
    "monday": "ב", "mon": "ב", "2": "ב",
    "tuesday": "ג", "tue": "ג", "3": "ג",
    "wednesday": "ד", "wed": "ד", "4": "ד",
    "thursday": "ה", "thu": "ה", "5": "ה",
    "friday": "ו", "fri": "ו", "6": "ו"
}

class RoomFinder:
    def __init__(self, catalog_client: TAUCourseCatalogClient, portal_client: Optional[TAUPortalClient] = None):
        self.catalog = catalog_client
        self.portal = portal_client

    def find_room(
        self,
        course: str,
        hour: Optional[str] = None,
        day: Optional[str] = None,
        group: Optional[str] = None,
        date: Optional[str] = None,
        year: str = "2026",
        check_changes: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Looks up the classroom and building for a course, matching the specified hour and day,
        and cross-references university announcements for any temporary or permanent room changes.

        Args:
            course: Course number (e.g. '03682158') or course name (e.g. 'מבני נתונים' or 'Data Structures').
            hour: Optional target hour (e.g. '12:00', '13', '14:30').
            day: Optional day ('א', 'ב', 'ג', 'ד', 'ה', 'ו' or 'Sunday', 'Mon', etc.).
            group: Optional group number ('01', '02', etc.).
            date: Optional date ('YYYY-MM-DD'). Used to infer day and filter change alerts.
            year: Academic year (default '2026').
            check_changes: Whether to check portal announcements for room changes (default True).
        """
        # 1. Resolve day from date if day not provided
        if not day and date:
            try:
                dt = datetime.datetime.strptime(date.strip(), "%Y-%m-%d")
                weekday = dt.weekday()  # Monday is 0, Sunday is 6 in Python
                day_keys = ["ב", "ג", "ד", "ה", "ו", "שבת", "א"]
                day = day_keys[weekday]
            except Exception:
                pass

        if day:
            day_clean = day.strip().lower()
            day = DAY_MAP.get(day_clean, day.strip())

        # 2. Resolve course number
        course_str = course.strip()
        course_number = None

        digits = re.sub(r"[^\d]", "", course_str)
        if len(digits) >= 6:
            course_number = digits.zfill(8)
        else:
            # Search catalog by name
            matches = self.catalog.search_by_name_or_lecturer(course_name=course_str, year=year)
            if matches:
                course_number = matches[0].course_number

        if not course_number:
            return [{"error": f"Could not find course '{course}'. Please provide a valid course number or name."}]

        # 3. Fetch scheduled rooms from catalog
        scheduled_rooms = self.catalog.get_room_number(
            course_number=course_number,
            group=group,
            day=day,
            hour=hour,
            year=year
        )

        # 4. Check for room change alerts from portal announcements
        change_alerts = []
        if check_changes and self.portal:
            try:
                messages = self.portal.get_messages(include_earlier=True)
                c_no_hyphen = course_number.replace("-", "")
                c_with_hyphen = f"{c_no_hyphen[:4]}-{c_no_hyphen[4:]}"

                for m in messages:
                    text = f"{m.subject} {m.message}"
                    # Check if message pertains to this course
                    if (c_no_hyphen in text or c_with_hyphen in text or (course_str in text and len(course_str) > 3)):
                        if "חדר" in text or "שינוי" in text or "כיתה" in text or "room" in text.lower():
                            change_alerts.append({
                                "date": m.start_date,
                                "subject": m.subject,
                                "message": m.message
                            })
            except Exception:
                pass

        # 5. Format results combining scheduled room + change notices
        results = []
        for r in scheduled_rooms:
            # Check if this specific group has a matching change alert
            grp = r.get("group", "")
            grp_alerts = []
            for ca in change_alerts:
                msg = ca["message"]
                # Match group in message (e.g. 03682158-14 or קבוצה 14 or קב' 01)
                if f"-{grp}" in msg or f"-{int(grp)}" in msg or f"קב' {grp}" in msg or f"קבוצה {grp}" in msg:
                    grp_alerts.append(ca["message"])
                elif f"{course_number}" in msg:
                    # General course change
                    grp_alerts.append(ca["message"])

            res = {
                "course_number": r["course_number"],
                "course_name": r["course_name"],
                "group": r["group"],
                "day": r["day"],
                "time": r["time"],
                "lesson_type": r["lesson_type"],
                "regular_building": r["building"],
                "regular_room": r["room"],
                "lecturer": r["lecturer"],
                "has_announced_change": len(grp_alerts) > 0,
                "change_announcements": grp_alerts if grp_alerts else None
            }
            results.append(res)

        # If no scheduled session matched the strict filters, but we have change alerts, return them
        if not results and change_alerts:
            results.append({
                "course_number": course_number,
                "note": "No scheduled sessions matched the exact hour/day filter, but active change notices were found.",
                "has_announced_change": True,
                "change_announcements": [ca["message"] for ca in change_alerts]
            })

        return results
