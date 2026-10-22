import sys
from tau_client import (
    TAUClient,
    get_course_room_number,
    get_my_schedule,
    get_my_grades,
    get_my_gpa,
    get_my_messages,
    get_my_exams
)

# Ensure proper Hebrew output in Windows console
sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=" * 60)
    print("  TAU PYTHON COMMUNICATION CHANNEL - DEMONSTRATION")
    print("=" * 60)

    client = TAUClient()

    # 1. Room number of ANY course and ANY instance (not necessarily enrolled)
    print("\n[1] ROOM LOOKUP FOR ANY COURSE & INSTANCE")
    print("    Querying Course 03212130 (שיטות בפיזיקה עיונית 1) - All Groups:")
    rooms_all = get_course_room_number("03212130")
    for r in rooms_all:
        print(f"    - Group {r['group']} | {r['day']} {r['time']} | {r['lesson_type']} | {r['building']} חדר {r['room']} | מרצה: {r['lecturer']}")

    print("\n    Querying Course 03682158 (Data Structures - קבוצה 01 בלבד):")
    rooms_ds = get_course_room_number("03682158", group="01")
    for r in rooms_ds:
        print(f"    - Group {r['group']} | {r['day']} {r['time']} | {r['lesson_type']} | {r['building']} חדר {r['room']} | מרצה: {r['lecturer']}")

    # 2. Personal schedule and enrolled courses
    print("\n[2] PERSONAL ENROLLED SCHEDULE & ROOMS")
    schedule = get_my_schedule()
    print(f"    Found {len(schedule)} schedule items for upcoming date:")
    for item in schedule[:5]:
        print(f"    - [{item['date']} {item['start'].split()[1] if ' ' in item['start'] else item['start']}] {item['title']} ({item['lesson_type']}) | {item['building']} חדר {item['room']} | מרצה: {item['lecturer']}")

    # 3. Personal Grades and GPA
    print("\n[3] PERSONAL GRADES & GPA STATS")
    gpa_list = get_my_gpa()
    for gpa in gpa_list:
        print(f"    - Program: {gpa['program']} | Avg Grade (GPA): {gpa['avg_grade']:.2f} | Credits: {gpa['total_hours']}")

    grades = get_my_grades()
    print(f"\n    Latest 5 Completed Courses:")
    for g in grades[:5]:
        print(f"    - [{g['course_number']}] {g['course_name']} | Grade: {g['final_grade']} | Weight: {g['weight']} | Moed: {g['moed']} ({g['year_he']} סמסטר {g['semester_he']})")

    # 4. Messages & Announcements (including room changes)
    print("\n[4] MESSAGES & ANNOUNCEMENTS (Room changes / Portal updates)")
    messages = get_my_messages()
    print(f"    Found {len(messages)} messages:")
    for m in messages[:4]:
        print(f"    - [{m['start_date']}] {m['subject']}")
        print(f"      {m['message'][:110]}...")

    # 5. Exam Schedule
    print("\n[5] EXAMS & ASSIGNMENTS")
    exams = get_my_exams()
    print(f"    Found {len(exams)} exam records:")
    for ex in exams[:4]:
        print(f"    - [{ex['course_number']}] {ex['course_name']} | {ex['assignment_type']} Moed {ex['moed']} | Date: {ex['due_date']} {ex['start_time']} | Grade: {ex['final_grade']}")

    print("\n" + "=" * 60)
    print("  DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 60)

if __name__ == "__main__":
    main()
