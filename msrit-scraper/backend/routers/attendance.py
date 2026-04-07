from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import (
    AttendanceRecordOut,
    LowAttendanceStudentOut,
    SummaryOut,
)
from backend import crud
from backend.config import ATTENDANCE_THRESHOLD

router = APIRouter(tags=["Attendance"])


@router.get(
    "/attendance/{usn}",
    response_model=list[AttendanceRecordOut],
    summary="Get latest attendance records for a student by USN",
)
def get_attendance(usn: str, db: Session = Depends(get_db)):
    student = crud.get_student_by_usn(db, usn.upper())
    if not student:
        raise HTTPException(status_code=404, detail=f"Student USN '{usn}' not found")

    records = crud.get_latest_attendance_for_usn(db, usn.upper())
    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No attendance records found for USN '{usn}'",
        )
    return records


@router.get(
    "/low-attendance",
    response_model=list[LowAttendanceStudentOut],
    summary="Students with at least one subject below the attendance threshold",
)
def low_attendance(
    threshold:  Optional[float] = Query(
        None,
        description=f"Override threshold (default: {ATTENDANCE_THRESHOLD}%)",
        ge=0, le=100,
    ),
    teacher_id: Optional[int]   = Query(None, description="Filter by teacher id"),
    db: Session = Depends(get_db),
):
    results = crud.get_low_attendance_students(
        db, threshold=threshold, teacher_id=teacher_id
    )
    return results


@router.get(
    "/summary",
    response_model=SummaryOut,
    summary="Aggregate statistics across all teachers and students",
)
def summary(
    threshold: Optional[float] = Query(
        None,
        description=f"Override threshold for low-attendance count (default: {ATTENDANCE_THRESHOLD}%)",
        ge=0, le=100,
    ),
    db: Session = Depends(get_db),
):
    return crud.get_summary(db, threshold=threshold)
