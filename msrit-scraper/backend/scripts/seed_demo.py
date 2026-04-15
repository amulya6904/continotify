import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import func

# Ensure repo root is on sys.path when running as a script
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.database import SessionLocal, init_db
from backend.models import Teacher, Student, AttendanceRecord
from backend.config import ATTENDANCE_THRESHOLD


def _pick_demo_email() -> str:
    # Prefer explicit DEMO_EMAIL, then SMTP_USER, then ALERT_SENDER
    return (
        os.getenv("DEMO_EMAIL")
        or os.getenv("SMTP_USER")
        or os.getenv("ALERT_SENDER")
        or "test@example.com"
    )


def seed_demo(force: bool = False) -> None:
    init_db()
    demo_email = _pick_demo_email().strip().lower()
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        teacher = db.query(Teacher).filter(Teacher.email == demo_email).first()
        if not teacher:
            if not force:
                # If any teacher exists and we are not forcing, keep DB intact
                existing = db.query(func.count(Teacher.id)).scalar() or 0
                if existing > 0:
                    print("Demo seed skipped: teachers already exist. Use --force to add demo data.")
                    return
            teacher = Teacher(
                name="Demo Teacher",
                email=demo_email,
                portal_username="demo_teacher",
            )
            db.add(teacher)
            db.flush()

        # Create demo students if missing
        students = []
        for i in range(1, 3):
            usn = f"DEMO00{i}"
            student = db.query(Student).filter(Student.usn == usn).first()
            if not student:
                student = Student(
                    teacher_id=teacher.id,
                    name=f"Demo Student {i}",
                    usn=usn,
                    semester="5",
                    registration_status="Active",
                    backlogs_status="None",
                    student_email=demo_email,
                )
                db.add(student)
                db.flush()
            students.append(student)

        # Add low-attendance records for each student (idempotent per day+subject)
        subjects = [
            ("Data Structures", 62.5, 25, 40),
            ("Operating Systems", 58.0, 29, 50),
        ]
        for student in students:
            latest_date = (
                db.query(func.max(func.date(AttendanceRecord.scraped_at)))
                .filter(AttendanceRecord.student_id == student.id)
                .scalar()
            )
            for subject_name, pct, attended, total in subjects:
                # Skip if a record for this subject already exists for the latest date
                if latest_date:
                    exists = (
                        db.query(AttendanceRecord.id)
                        .filter(
                            AttendanceRecord.student_id == student.id,
                            AttendanceRecord.subject_name == subject_name,
                            func.date(AttendanceRecord.scraped_at) == latest_date,
                        )
                        .first()
                    )
                    if exists:
                        continue
                db.add(
                    AttendanceRecord(
                        student_id=student.id,
                        subject_name=subject_name,
                        course_type="Theory",
                        attendance_percentage=pct,
                        total_classes=total,
                        attended_classes=attended,
                        cie_max_marks=50,
                        cie_obtained_marks=30,
                        scraped_at=now,
                    )
                )

        db.commit()
        print(
            f"Demo seed complete. Teacher={teacher.name} email={teacher.email}, "
            f"students={len(students)}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    load_dotenv()
    force = "--force" in os.sys.argv
    seed_demo(force=force)
