import logging
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx

from backend.database import get_db
from backend.config import ATTENDANCE_THRESHOLD, NOTIFICATION_SERVICE_URL
from backend import crud
from backend.notify_client import send_alert_to_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["Alerts"])


class AlertSendRequest(BaseModel):
    notify_teacher: bool = True
    notify_student: bool = True


class AlertSendResponse(BaseModel):
    teacher_id:       int
    teacher_name:     str
    teacher_email:    str
    students_alerted: int
    status:           str           # "success" | "partial" | "failed" | "skipped"
    emails_sent:      int
    records_logged:   int
    detail:           Optional[str] = None


def _build_notify_payload(
    teacher,
    low_attendance_students: list,
    notify_teacher: bool = True,
    notify_student: bool = True,
) -> dict:
    """
    Convert crud.get_low_attendance_students() output into the
    notification service's nested payload format.
    """
    students_payload = []
    for entry in low_attendance_students:
        subjects = [
            {
                "subject_name":          s["subject_name"],
                "attendance_percentage": s["attendance_percentage"],
                "attended_classes":      s["attended_classes"] or 0,
                "total_classes":         s["total_classes"] or 0,
            }
            for s in entry["low_subjects"]
        ]
        students_payload.append({
            "name":          entry["student_name"],
            "usn":           entry["usn"],
            "semester":      entry["semester"] or "",
            "student_email": entry.get("student_email"),
            "subjects":      subjects,
        })

    return {
        "teacher": {
            "name":  teacher.name,
            "email": teacher.email,
        },
        "students":       students_payload,
        "notify_teacher": notify_teacher,
        "notify_student": notify_student,
    }


@router.post(
    "/send/{teacher_id}",
    response_model=AlertSendResponse,
    summary="Send attendance alert email for a specific teacher's low-attendance students",
)
def send_alert(
    teacher_id: int,
    body:       AlertSendRequest = AlertSendRequest(),
    threshold:  Optional[float] = Query(
        None,
        description=f"Override attendance threshold (default: {ATTENDANCE_THRESHOLD}%)",
        ge=0, le=100,
    ),
    db: Session = Depends(get_db),
):
    # ── 1. Validate teacher exists and has an email ───────────────────────────
    teacher = crud.get_teacher_by_id(db, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail=f"Teacher id={teacher_id} not found")

    if not teacher.email:
        raise HTTPException(
            status_code=422,
            detail=f"Teacher '{teacher.name}' has no email address in the database",
        )

    logger.info(
        f"Alert send requested — teacher: {teacher.name} (id={teacher_id}), "
        f"notify_teacher={body.notify_teacher}, notify_student={body.notify_student}"
    )

    # ── 2. Fetch low-attendance students for this teacher ────────────────────
    low_students = crud.get_low_attendance_students(
        db, threshold=threshold, teacher_id=teacher_id
    )

    if not low_students:
        logger.info(f"No low-attendance students found for teacher id={teacher_id} — skipping")
        return AlertSendResponse(
            teacher_id       = teacher_id,
            teacher_name     = teacher.name,
            teacher_email    = teacher.email,
            students_alerted = 0,
            status           = "skipped",
            emails_sent      = 0,
            records_logged   = 0,
            detail           = "No students below attendance threshold — no email sent",
        )

    # ── 3. Build payload ──────────────────────────────────────────────────────
    payload = _build_notify_payload(
        teacher, low_students,
        notify_teacher=body.notify_teacher,
        notify_student=body.notify_student,
    )

    logger.info(
        f"Sending alert for {len(low_students)} student(s) to "
        f"notification service → {teacher.email}"
    )

    # ── 4. Call notification service ─────────────────────────────────────────
    try:
        result = send_alert_to_service(payload)
        return AlertSendResponse(
            teacher_id       = teacher_id,
            teacher_name     = teacher.name,
            teacher_email    = teacher.email,
            students_alerted = len(low_students),
            status           = result.get("status", "unknown"),
            emails_sent      = result.get("emails_sent", 0),
            records_logged   = result.get("records_logged", 0),
            detail           = result.get("detail"),
        )

    except RuntimeError as e:
        logger.error(f"Notification service call failed for teacher id={teacher_id}: {e}")
        return AlertSendResponse(
            teacher_id       = teacher_id,
            teacher_name     = teacher.name,
            teacher_email    = teacher.email,
            students_alerted = len(low_students),
            status           = "failed",
            emails_sent      = 0,
            records_logged   = 0,
            detail           = str(e),
        )


@router.get(
    "/logs",
    summary="Alert log history — proxied from notification service",
)
def get_alert_logs(
    teacher_email: Optional[str] = Query(None),
    usn:           Optional[str] = Query(None),
    status:        Optional[str] = Query(None),
    limit:         int           = Query(100, ge=1, le=1000),
    skip:          int           = Query(0, ge=0),
) -> Any:
    params: dict = {"limit": limit, "skip": skip}
    if teacher_email:
        params["teacher_email"] = teacher_email
    if usn:
        params["usn"] = usn
    if status:
        params["status"] = status

    try:
        response = httpx.get(
            f"{NOTIFICATION_SERVICE_URL}/alerts/logs",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Notification service is unavailable — is it running on port 8001?",
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Notification service timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
