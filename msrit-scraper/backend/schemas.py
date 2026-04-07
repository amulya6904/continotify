from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ── Attendance Record ─────────────────────────────────────────────────────────

class AttendanceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                     int
    student_id:             Optional[int]
    subject_name:           Optional[str]
    course_type:            Optional[str]
    attendance_percentage:  Optional[float]
    total_classes:          Optional[int]
    attended_classes:       Optional[int]
    cie_max_marks:          Optional[int]
    cie_obtained_marks:     Optional[int]
    scraped_at:             datetime


# ── Student ───────────────────────────────────────────────────────────────────

class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                     int
    teacher_id:             Optional[int]
    name:                   Optional[str]
    usn:                    Optional[str]
    semester:               Optional[str]
    registration_status:    Optional[str]
    backlogs_status:        Optional[str]
    created_at:             datetime


class StudentWithAttendanceOut(StudentOut):
    attendance_records: list[AttendanceRecordOut] = []


# ── Teacher ───────────────────────────────────────────────────────────────────

class TeacherOut(BaseModel):
    """portal_password_encrypted is structurally absent — never in this schema."""
    model_config = ConfigDict(from_attributes=True)

    id:               int
    name:             str
    email:            Optional[str]
    portal_username:  Optional[str]
    created_at:       datetime


class TeacherWithStudentsOut(TeacherOut):
    students: list[StudentOut] = []


# ── Low Attendance ────────────────────────────────────────────────────────────

class LowAttendanceSubject(BaseModel):
    subject_name:           Optional[str]
    course_type:            Optional[str]
    attendance_percentage:  Optional[float]
    attended_classes:       Optional[int]
    total_classes:          Optional[int]
    scraped_at:             datetime


class LowAttendanceStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id:             int
    student_name:           Optional[str]
    usn:                    Optional[str]
    semester:               Optional[str]
    teacher_name:           Optional[str]
    student_email:          Optional[str] = None
    low_subjects:           list[LowAttendanceSubject]


# ── Summary ───────────────────────────────────────────────────────────────────

class SummaryOut(BaseModel):
    total_teachers:             int
    total_students:             int
    total_attendance_records:   int
    low_attendance_students:    int
    threshold:                  float
    average_attendance:         Optional[float]
    last_scraped_at:            Optional[datetime]


# ── Health ────────────────────────────────────────────────────────────────────

class HealthOut(BaseModel):
    status:     str
    db:         str
    version:    str = "2.0.0"
