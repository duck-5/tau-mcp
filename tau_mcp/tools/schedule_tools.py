"""Personal schedule tools for Tel Aviv University."""

import datetime
from typing import Any, Dict, List, Optional
from tau_mcp.core.portal import TAUPortalClient

def register_schedule_tools(server: Any, portal: TAUPortalClient) -> None:
    @server.tool(
        name="tau_get_daily_agenda",
        description=(
            "Get a unified single-call daily agenda for any date: aggregates all scheduled university classes, "
            "physical buildings and classrooms, cross-references announcements for active room changes, "
            "and includes Moodle homework assignments due on that day."
        )
    )
    def tau_get_daily_agenda(date: Optional[str] = None) -> Dict[str, Any]:
        """
        Args:
            date: Target date in 'YYYY-MM-DD' format (e.g. '2026-11-05'). Defaults to today.
        """
        try:
            from zoneinfo import ZoneInfo
            now_dt = datetime.datetime.now(ZoneInfo("Asia/Jerusalem"))
        except Exception:
            now_dt = datetime.datetime.now()

        if date and date.strip():
            target_date_str = date.strip()
            try:
                target_dt = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
            except Exception:
                target_dt = now_dt
                target_date_str = now_dt.strftime("%Y-%m-%d")
        else:
            target_dt = now_dt
            target_date_str = now_dt.strftime("%Y-%m-%d")

        weekday = target_dt.weekday()  # Monday=0 ... Sunday=6
        day_hebrew_map = ["ב", "ג", "ד", "ה", "ו", "שבת", "א"]
        day_names_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        target_day_he = day_hebrew_map[weekday]
        target_day_en = day_names_en[weekday]

        # 1. Fetch personal schedule
        all_events = portal.get_personal_schedule(from_date=target_date_str)
        day_classes = []
        for e in all_events:
            # Check date match or inferred weekday
            e_date = e.date or ""
            if e_date == target_date_str:
                day_classes.append(e)

        # 2. Check room change alerts for today's classes
        room_change_alerts = []
        try:
            messages = portal.get_messages(include_earlier=True)
            for e in day_classes:
                c_clean = e.course_number.replace("-", "").strip()
                for m in messages:
                    text = f"{m.subject} {m.message}"
                    if (c_clean in text or e.title in text) and any(w in text for w in ("חדר", "שינוי", "כיתה", "room")):
                        room_change_alerts.append({
                            "course": e.title,
                            "course_number": e.course_number,
                            "alert_date": m.start_date,
                            "subject": m.subject,
                            "message": m.message
                        })
        except Exception:
            pass

        # 3. Check Moodle assignments due on this day
        assignments_due = []
        try:
            from moodle_mcp.client import MoodleClient
            from moodle_mcp.config import get_primary_profile
            m_client = MoodleClient(profile=get_primary_profile())
            all_upcoming = m_client.get_upcoming_assignments(days_ahead=30)
            for a in all_upcoming:
                due_str = a.get("due_date", "")
                if due_str.startswith(target_date_str):
                    assignments_due.append({
                        "id": a.get("id"),
                        "course_name": a.get("course_name"),
                        "name": a.get("name"),
                        "due_date": due_str,
                        "time_remaining": a.get("time_remaining"),
                        "status": a.get("status")
                    })
        except Exception:
            pass

        # 4. Format classes payload
        classes_payload = []
        for c in day_classes:
            classes_payload.append({
                "title": c.title,
                "course_number": c.course_number,
                "group": c.group,
                "start": c.start_time,
                "end": c.end_time,
                "building": c.building_he,
                "room": c.room,
                "lecturer": c.lecturer,
                "lesson_type": c.lesson_type,
                "gps": {"lat": c.lat, "lon": c.lon} if c.lat and c.lon else None
            })

        return {
            "date": target_date_str,
            "day_of_week": target_day_he,
            "day_of_week_en": target_day_en,
            "total_classes": len(classes_payload),
            "classes": classes_payload,
            "room_change_alerts": room_change_alerts,
            "assignments_due": assignments_due
        }

    @server.tool(
        name="tau_get_my_schedule",
        description=(
            "Get the student's enrolled weekly class schedule with physical classrooms, buildings, lecturer names, "
            "and campus map GPS coordinates from the TAU Student Portal. For homework deadlines and submission due dates, use Moodle tools."
        )
    )
    def tau_get_my_schedule(from_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Args:
            from_date: Optional start date in 'YYYY-MM-DD' format. Defaults to today.
        """
        events = portal.get_personal_schedule(from_date=from_date)
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
                "building_en": e.building_en,
                "room": e.room,
                "lecturer": e.lecturer,
                "gps": {"lat": e.lat, "lon": e.lon} if e.lat and e.lon else None
            }
            for e in events
        ]
