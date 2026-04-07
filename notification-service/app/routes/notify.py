from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AlertLog
from app.schemas import NotifyRequest, NotifyResponse, AlertLogOut
from app.email_service import send_email, send_student_email
from app.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/notify",
    response_model=NotifyResponse,
    summary="Send attendance alert emails to teacher and/or students",
)
def notify(req: NotifyRequest, db: Session = Depends(get_db)):
    if not req.students:
        raise HTTPException(status_code=400, detail="students list cannot be empty")

    if not req.notify_teacher and not req.notify_student:
        raise HTTPException(
            status_code=400,
            detail="At least one of notify_teacher or notify_student must be true",
        )

    logger.info(
        f"Notify request — teacher: {req.teacher.email}, "
        f"students: {len(req.students)}, "
        f"notify_teacher={req.notify_teacher}, notify_student={req.notify_student}"
    )

    emails_sent = 0
    log_entries: list[AlertLog] = []

    # ── 1. Send teacher summary email ─────────────────────────────────────────
    teacher_ok = False
    teacher_err = ""
    if req.notify_teacher:
        teacher_ok, teacher_err = send_email(req)
        if teacher_ok:
            emails_sent += 1

        # Log one row per (student, subject) for the teacher email
        for student in req.students:
            for subj in student.subjects:
                log_entries.append(AlertLog(
                    teacher_email         = req.teacher.email,
                    student_name          = student.name,
                    usn                   = student.usn,
                    subject_name          = subj.subject_name,
                    attendance_percentage = subj.attendance_percentage,
                    status                = "success" if teacher_ok else "failed",
                    error_message         = teacher_err if not teacher_ok else None,
                    recipient_type        = "teacher",
                ))

    # ── 2. Send personalized email to each student ────────────────────────────
    if req.notify_student:
        for student in req.students:
            student_ok, student_err = send_student_email(student, req.teacher.name)

            # Only log if the student had an email address (i.e. an actual send attempt)
            if student.student_email:
                if student_ok:
                    emails_sent += 1
                for subj in student.subjects:
                    log_entries.append(AlertLog(
                        teacher_email         = req.teacher.email,
                        student_name          = student.name,
                        usn                   = student.usn,
                        subject_name          = subj.subject_name,
                        attendance_percentage = subj.attendance_percentage,
                        status                = "success" if student_ok else "failed",
                        error_message         = student_err if not student_ok else None,
                        recipient_type        = "student",
                    ))

    # ── 3. Persist log entries ────────────────────────────────────────────────
    records_logged = 0
    try:
        db.add_all(log_entries)
        db.commit()
        records_logged = len(log_entries)
        logger.info(f"Logged {records_logged} alert records to DB")
    except Exception as e:
        logger.error(f"DB logging failed: {e}")
        db.rollback()

    # ── 4. Determine overall status ───────────────────────────────────────────
    # An attempt is considered successful if at least one email was sent
    any_sent = emails_sent > 0
    detail: Optional[str] = None

    if any_sent and records_logged > 0:
        status = "success"
    elif any_sent and records_logged == 0:
        status = "partial"
        detail = "Email(s) sent but DB logging failed"
    elif not any_sent and records_logged > 0:
        status = "partial"
        errors = []
        if req.notify_teacher and not teacher_ok:
            errors.append(f"Teacher email failed: {teacher_err}")
        if req.notify_student:
            errors.append("No student emails sent (missing email addresses or SMTP error)")
        detail = " | ".join(errors) if errors else "No emails sent"
    else:
        status = "failed"
        errors = []
        if req.notify_teacher and not teacher_ok:
            errors.append(f"Teacher email: {teacher_err}")
        detail = "; ".join(errors) if errors else "All email attempts failed"

    return NotifyResponse(
        status         = status,
        emails_sent    = emails_sent,
        records_logged = records_logged,
        detail         = detail,
    )


@router.get(
    "/alerts/logs",
    response_model=list[AlertLogOut],
    summary="Query alert log history",
)
def get_alert_logs(
    teacher_email:  Optional[str] = Query(None, description="Filter by teacher email"),
    usn:            Optional[str] = Query(None, description="Filter by student USN"),
    status:         Optional[str] = Query(None, description="Filter by status: success | failed"),
    recipient_type: Optional[str] = Query(None, description="Filter by recipient: teacher | student"),
    limit:          int           = Query(100, ge=1, le=1000),
    skip:           int           = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(AlertLog)
    if teacher_email:
        q = q.filter(AlertLog.teacher_email == teacher_email)
    if usn:
        q = q.filter(AlertLog.usn == usn.upper())
    if status:
        q = q.filter(AlertLog.status == status)
    if recipient_type:
        q = q.filter(AlertLog.recipient_type == recipient_type)
    return q.order_by(AlertLog.created_at.desc()).offset(skip).limit(limit).all()
