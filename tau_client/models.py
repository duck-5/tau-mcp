from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class CourseSession:
    """Represents a specific teaching session (e.g. Tuesday lecture or Wednesday tutorial)"""
    day: str  # e.g. "א", "ב", "ג", "ד", "ה", "ו"
    time: str  # e.g. "12:00-14:00"
    lesson_type: str  # e.g. "שיעור", "תרגיל", "מעבדה"
    building: str  # e.g. "לב אודיטוריום", "שרייבר- מתמטיקה"
    room: str  # e.g. "009", "006"
    lecturer: str  # e.g. "פרופ' אופנהימר נעמי"
    semester: str  # e.g. "א'", "ב'", "קיץ"

@dataclass
class CourseInstance:
    """Represents a group/instance of a course in the university catalog"""
    course_number: str  # e.g. "03212130"
    group: str  # e.g. "01"
    course_name: str  # e.g. "שיטות בפיזיקה עיונית 1"
    faculty_dept: str  # e.g. "מדעים מדויקים/פיזיקה"
    year: str  # e.g. "2026"
    sessions: List[CourseSession] = field(default_factory=list)
    syllabus_url: Optional[str] = None
    moodle_url: Optional[str] = None
    exam_url: Optional[str] = None

@dataclass
class PersonalScheduleEvent:
    """Represents an event on the student's personal schedule/calendar"""
    date: str  # e.g. "2026-10-21"
    start_time: str  # e.g. "2026-10-21 12:00:00"
    end_time: str  # e.g. "2026-10-21 14:00:00"
    title: str  # e.g. "שיטות בפיזיקה עיונית 1"
    title_en: str
    course_number: str
    group: str
    lesson_type: str
    building_he: str
    building_en: str
    room: str
    lecturer: str
    lat: Optional[str] = None
    lon: Optional[str] = None
    event_type: str = "course"

@dataclass
class GradeRecord:
    """Represents a course grade record"""
    course_number: str
    group: str
    course_name: str
    course_name_en: str
    final_grade: Optional[str]
    weight: str  # Credit points (נקודות זכות / שעות)
    year_semester: str  # e.g. "20251"
    semester_he: str  # e.g. "א'"
    year_he: str  # e.g. "תשפ\"ו"
    moed: str  # e.g. "א", "ב"
    is_finished: bool
    remarks: str = ""

@dataclass
class GPAStats:
    """Represents degree GPA and credit statistics"""
    program_desc: str
    program_desc_en: str
    avg_grade: float
    total_hours: float
    final_weight: float

@dataclass
class StudentMessage:
    """Represents a message/announcement from the portal"""
    id: str
    subject: str
    subject_en: str
    message: str
    message_en: str
    start_date: str
    due_date: str
    is_urgent: bool
    source: str = ""

@dataclass
class ExamRecord:
    """Represents an exam or assignment"""
    course_number: str
    group: str
    course_name: str
    assignment_type: str  # e.g. "בחינה סופית"
    due_date: str  # e.g. "2026-02-15"
    start_time: str  # e.g. "0900"
    moed: str  # e.g. "א", "ב"
    final_grade: Optional[str] = None
    scan_file_name: Optional[str] = None
    scan_status: Optional[str] = None
    appeal_status: Optional[str] = None
