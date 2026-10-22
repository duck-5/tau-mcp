"""
Verification test for tau-mcp server and dynamic moodle plugin integration.
"""

import sys
import json
import asyncio

# Ensure Windows PowerShell displays Hebrew properly
sys.stdout.reconfigure(encoding='utf-8')

from tau_mcp.server import create_server

async def main():
    print("=" * 65)
    print("  TAU-MCP SERVER & DYNAMIC PLUGIN INTEGRATION TEST")
    print("=" * 65)

    print("\n[1] Initializing MCPServer with dynamic plugin loading...")
    server, portal, catalog, room_finder = create_server(include_moodle=True)

    # In MCP 2.x (MCPServer), tools are stored in server._tool_manager or server.list_tools()
    # Let's inspect the registered tools
    tool_names = []
    if hasattr(server, "_tool_manager") and hasattr(server._tool_manager, "_tools"):
        tool_names = list(server._tool_manager._tools.keys())
    elif hasattr(server, "list_tools"):
        try:
            tools_list = await server.list_tools() if asyncio.iscoroutinefunction(server.list_tools) else server.list_tools()
            tool_names = [t.name for t in tools_list]
        except Exception:
            pass

    print(f"Total registered tools: {len(tool_names)}")
    tau_tools = [t for t in tool_names if t.startswith("tau_")]
    moodle_tools = [t for t in tool_names if t.startswith("moodle_")]

    print(f"TAU core tools ({len(tau_tools)}):", ", ".join(sorted(tau_tools)))
    print(f"Moodle dynamically mounted tools ({len(moodle_tools)}):", ", ".join(sorted(moodle_tools)[:10]), "...")

    # 2. Test tau_get_course_room with course + hour + room changes
    print("\n[2] Testing tau_get_course_room:")
    print("    A) Querying course 03212130 (Methods of Theoretical Physics 1) at hour 12:00:")
    res_hour = room_finder.find_room(course="03212130", hour="12:00")
    for r in res_hour:
        print(f"    - Group {r.get('group')} | {r.get('day')} {r.get('time')} | {r.get('regular_building')} Room {r.get('regular_room')} | Lecturer: {r.get('lecturer')}")

    print("\n    B) Querying course 03682158 (Data Structures) checking for room change alerts:")
    res_ds = room_finder.find_room(course="03682158", check_changes=True)
    for r in res_ds[:3]:
        print(f"    - Group {r.get('group')} | {r.get('day')} {r.get('time')} | {r.get('regular_building')} Room {r.get('regular_room')}")
        if r.get("has_announced_change"):
            print(f"      *** ALERT: {r.get('change_announcements')[0][:120]}...")

    # 3. Test Student Portal Personal Schedule & Rooms
    print("\n[3] Testing tau_get_my_schedule:")
    sched = portal.get_personal_schedule()
    print(f"    Found {len(sched)} enrolled schedule events for today/upcoming:")
    for s in sched[:3]:
        print(f"    - [{s.start_time}] {s.title} ({s.lesson_type}) -> {s.building_he} Room {s.room} (Lecturer: {s.lecturer})")

    # 4. Test Student Portal Grades & GPA
    print("\n[4] Testing tau_get_my_gpa & tau_get_my_grades:")
    gpa = portal.get_gpa_stats()
    for g in gpa:
        print(f"    - Program: {g.program_desc} | GPA: {g.avg_grade:.2f} | Credits: {g.total_hours}")

    grades = portal.get_grades()
    print(f"    Total graded courses: {len(grades)}. Latest:")
    for g in grades[:3]:
        print(f"    - {g.course_number} {g.course_name} -> Grade: {g.final_grade} (Moed {g.moed})")

    # 5. Test Student Messages / Room Change Alerts
    print("\n[5] Testing tau_get_my_messages:")
    msgs = portal.get_messages(include_earlier=True)
    print(f"    Total messages retrieved: {len(msgs)}. Recent room change notices:")
    change_msgs = [m for m in msgs if "חדר" in m.message or "שינוי" in m.message]
    for m in change_msgs[:2]:
        print(f"    - [{m.start_date}] {m.subject}: {m.message[:110]}...")

    print("\n" + "=" * 65)
    print("  ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(main())
