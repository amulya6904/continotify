from typing import Optional
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from backend.models import Teacher, Student, AttendanceRecord
from backend.config import ATTENDANCE_THRESHOLD


# ── Teachers ──────────────────────────────────────────────────────────────────

def get_all_teachers(db: Session) -> list[Teacher]:
    return db.query(Teacher).order_by(Teacher.name).all()


def get_teacher_by_id(db: Session, teacher_id: int) -> Optional[Teacher]:
    return db.query(Teacher).filter(Teacher.id == teacher_id).first()


# ── Students ──────────────────────────────────────────────────────────────────

def get_all_students(
    db: Session,
    teacher_id: Optional[int] = None,
    semester: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
) -> list[Student]:
    q = db.query(Student)
    if teacher_id is not None:
        q = q.filter(Student.teacher_id == teacher_id)
    if semester:
        q = q.filter(Student.semester == semester)
    return q.order_by(Student.name).offset(skip).limit(limit).all()


def get_student_by_usn(db: Session, usn: str) -> Optional[Student]:
    return db.query(Student).filter(Student.usn == usn).first()


# ── Attendance ────────────────────────────────────────────────────────────────

def get_latest_attendance_for_usn(
    db: Session, usn: str
) -> list[AttendanceRecord]:
    """
    Return the most recently scraped attendance records for a student.
    Filters to only today's records if they exist; otherwise latest available date.
    """
    student = get_student_by_usn(db, usn)
    if not student:
        return []

    # Find the most recent scrape date for this student
    latest_date = (
        db.query(func.max(func.date(AttendanceRecord.scraped_at)))
        .filter(AttendanceRecord.student_id == student.id)
        .scalar()
    )
    if not latest_date:
        return []

    return (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.student_id == student.id,
            func.date(AttendanceRecord.scraped_at) == latest_date,
        )
        .order_by(AttendanceRecord.subject_name)
        .all()
    )


# ── Low Attendance ────────────────────────────────────────────────────────────

def get_low_attendance_students(
    db: Session,
    threshold: Optional[float] = None,
    teacher_id: Optional[int] = None,
) -> list[dict]:
    """
    Returns students who have at least one subject below the threshold.
    Groups low-attendance subjects per student.
    """
    if threshold is None:
        threshold = ATTENDANCE_THRESHOLD

    # Subquery: find most recent scrape date per student
    latest_subq = (
        db.query(
            AttendanceRecord.student_id,
            func.max(func.date(AttendanceRecord.scraped_at)).label("latest_date"),
        )
        .group_by(AttendanceRecord.student_id)
        .subquery()
    )

    q = (
        db.query(AttendanceRecord, Student, Teacher)
        .join(Student, AttendanceRecord.student_id == Student.id)
        .join(Teacher, Student.teacher_id == Teacher.id)
        .join(
            latest_subq,
            (AttendanceRecord.student_id == latest_subq.c.student_id)
            & (func.date(AttendanceRecord.scraped_at) == latest_subq.c.latest_date),
        )
        .filter(AttendanceRecord.attendance_percentage < threshold)
    )

    if teacher_id is not None:
        q = q.filter(Student.teacher_id == teacher_id)

    rows = q.order_by(Student.name, AttendanceRecord.attendance_percentage).all()

    # Group by student
    grouped: dict[int, dict] = {}
    for record, student, teacher in rows:
        sid = student.id
        if sid not in grouped:
            grouped[sid] = {
                "student_id":   student.id,
                "student_name": student.name,
                "usn":          student.usn,
                "semester":     student.semester,
                "teacher_name": teacher.name,
                "student_email": student.student_email,
                "low_subjects": [],
            }
        grouped[sid]["low_subjects"].append({
            "subject_name":          record.subject_name,
            "course_type":           record.course_type,
            "attendance_percentage": float(record.attendance_percentage) if record.attendance_percentage is not None else None,
            "attended_classes":      record.attended_classes,
            "total_classes":         record.total_classes,
            "scraped_at":            record.scraped_at,
        })

    return list(grouped.values())


# ── Summary ───────────────────────────────────────────────────────────────────

def get_summary(db: Session, threshold: Optional[float] = None) -> dict:
    if threshold is None:
        threshold = ATTENDANCE_THRESHOLD

    total_teachers = db.query(func.count(Teacher.id)).scalar() or 0
    total_students = db.query(func.count(Student.id)).scalar() or 0
    total_records  = db.query(func.count(AttendanceRecord.id)).scalar() or 0

    avg_raw = db.query(func.avg(AttendanceRecord.attendance_percentage)).scalar()
    average_attendance = float(round(avg_raw, 2)) if avg_raw is not None else None

    last_scraped_at = db.query(func.max(AttendanceRecord.scraped_at)).scalar()

    # Count distinct students with at least one record below threshold
    low_student_count = (
        db.query(func.count(func.distinct(AttendanceRecord.student_id)))
        .filter(AttendanceRecord.attendance_percentage < threshold)
        .scalar()
        or 0
    )

    return {
        "total_teachers":           total_teachers,
        "total_students":           total_students,
        "total_attendance_records": total_records,
        "low_attendance_students":  low_student_count,
        "threshold":                threshold,
        "average_attendance":       average_attendance,
        "last_scraped_at":          last_scraped_at,
    }
