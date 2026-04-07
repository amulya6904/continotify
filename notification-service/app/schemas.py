from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


# ── Inbound request ───────────────────────────────────────────────────────────

class SubjectAlert(BaseModel):
    subject_name:           str
    attendance_percentage:  float
    attended_classes:       int
    total_classes:          int


class StudentAlert(BaseModel):
    name:           str
    usn:            str
    semester:       str
    student_email:  Optional[str] = None   # populated from emails.csv sync
    subjects:       list[SubjectAlert]


class TeacherInfo(BaseModel):
    name:   str
    email:  EmailStr


class NotifyRequest(BaseModel):
    teacher:        TeacherInfo
    students:       list[StudentAlert]
    notify_teacher: bool = True    # send summary email to teacher
    notify_student: bool = True    # send personalized email to each student


# ── Outbound response ─────────────────────────────────────────────────────────

class NotifyResponse(BaseModel):
    status:         str     # "success" | "partial" | "failed"
    emails_sent:    int
    records_logged: int
    detail:         Optional[str] = None


# ── Alert log ─────────────────────────────────────────────────────────────────

class AlertLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                     int
    teacher_email:          Optional[str]
    student_name:           Optional[str]
    usn:                    Optional[str]
    subject_name:           Optional[str]
    attendance_percentage:  Optional[float]
    status:                 Optional[str]
    error_message:          Optional[str]
    recipient_type:         Optional[str] = None
    created_at:             datetime
