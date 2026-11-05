"""Personal schedule tools for Tel Aviv University."""

import datetime
from typing import Any, Dict, List, Optional
from tau_mcp.core.portal import TAUPortalClient

def register_schedule_tools(server: Any, portal: TAUPortalClient) -> None:
    @server.tool(
        name="tau_get_daily_agenda",
        description=(
            "Get the student's unified daily or multi-day agenda: aggregates all scheduled university classes, "
            "physical buildings and classrooms, cross-references announcements for active room changes, "
            "and includes Moodle homework assignments due. Query a single day (default) or a multi-day range (e.g. 7 days for the full week)."
        )
    )
    def tau_get_daily_agenda(
        date: Optional[str] = None,
        days_ahead: int = 1
    ) -> Dict[str, Any]:
        """
        Args:
            date: Start date in 'YYYY-MM-DD' format (e.g. '2026-11-05'). Defaults to today.
            days_ahead: Number of days to include in the agenda (default: 1 for single-day agenda, or up to 14 for a full week/period).
        """
        try:
            from zoneinfo import ZoneInfo
            now_dt = datetime.datetime.now(ZoneInfo("Asia/Jerusalem"))
        except Exception:
            now_dt = datetime.datetime.now()

        if date and date.strip():
            start_date_str = date.strip()
            try:
                start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
            except Exception:
                start_dt = now_dt
                start_date_str = now_dt.strftime("%Y-%m-%d")
        else:
            start_dt = now_dt
            start_date_str = now_dt.strftime("%Y-%m-%d")

        num_days = max(1, min(days_ahead, 30))

        # 1. Fetch personal schedule from portal
        all_events = portal.get_personal_schedule(from_date=start_date_str)

        # 2. Fetch room change notices from portal messages
        all_messages = []
        try:
            all_messages = portal.get_messages(include_earlier=True)
        except Exception:
            pass

        # 3. Fetch Moodle assignments due in this window
        all_upcoming_assignments = []
        try:
            from moodle_mcp.client import MoodleClient
            from moodle_mcp.config import get_primary_profile
            m_client = MoodleClient(profile=get_primary_profile())
            all_upcoming_assignments = m_client.get_upcoming_assignments(days_ahead=num_days + 1)
        except Exception:
            pass

        day_hebrew_map = ["ב", "ג", "ד", "ה", "ו", "שבת", "א"]
        day_names_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        days_list = []
        all_classes_flat = []
        all_alerts_flat = []
        all_due_flat = []

        for offset in range(num_days):
            current_dt = start_dt + datetime.timedelta(days=offset)
            current_date_str = current_dt.strftime("%Y-%m-%d")
            weekday = current_dt.weekday()
            cur_day_he = day_hebrew_map[weekday]
            cur_day_en = day_names_en[weekday]

            # Matching classes on current_date_str
            day_classes = [e for e in all_events if (e.date or "") == current_date_str]

            # Matching alerts
            room_change_alerts = []
            for e in day_classes:
                c_clean = e.course_number.replace("-", "").strip()
                for m in all_messages:
                    text = f"{m.subject} {m.message}"
                    if (c_clean in text or e.title in text) and any(w in text for w in ("חדר", "שינוי", "כיתה", "room")):
                        room_change_alerts.append({
                            "course": e.title,
                            "course_number": e.course_number,
                            "alert_date": m.start_date,
                            "subject": m.subject,
                            "message": m.message
                        })

            # Matching assignments due on current_date_str
            assignments_due = []
            for a in all_upcoming_assignments:
                due_str = a.get("due_date", "")
                if due_str.startswith(current_date_str):
                    assignments_due.append({
                        "id": a.get("id"),
                        "course_name": a.get("course_name"),
                        "name": a.get("name"),
                        "due_date": due_str,
                        "time_remaining": a.get("time_remaining"),
                        "status": a.get("status")
                    })

            # Classes payload for this day
            classes_payload = [
                {
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
                }
                for c in day_classes
            ]

            days_list.append({
                "date": current_date_str,
                "day_of_week": cur_day_he,
                "day_of_week_en": cur_day_en,
                "total_classes": len(classes_payload),
                "classes": classes_payload,
                "room_change_alerts": room_change_alerts,
                "assignments_due": assignments_due
            })

            all_classes_flat.extend(classes_payload)
            all_alerts_flat.extend(room_change_alerts)
            all_due_flat.extend(assignments_due)

        # For single day (num_days == 1), return direct day dict with standard keys
        if num_days == 1:
            first_day = days_list[0]
            return {
                "date": first_day["date"],
                "day_of_week": first_day["day_of_week"],
                "day_of_week_en": first_day["day_of_week_en"],
                "total_classes": first_day["total_classes"],
                "days": days_list,
                "classes": first_day["classes"],
                "room_change_alerts": first_day["room_change_alerts"],
                "assignments_due": first_day["assignments_due"]
            }

        # For multi-day, return comprehensive aggregated range
        return {
            "start_date": start_date_str,
            "days_ahead": num_days,
            "total_classes": len(all_classes_flat),
            "days": days_list,
            "classes": all_classes_flat,
            "room_change_alerts": all_alerts_flat,
            "assignments_due": all_due_flat
        }
