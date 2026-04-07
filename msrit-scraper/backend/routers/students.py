from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import StudentOut, StudentWithAttendanceOut
from backend import crud

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", response_model=list[StudentOut], summary="List all students")
def list_students(
    teacher_id: Optional[int]  = Query(None, description="Filter by teacher"),
    semester:   Optional[str]  = Query(None, description="Filter by semester e.g. SEM06"),
    skip:       int            = Query(0,    ge=0),
    limit:      int            = Query(200,  ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return crud.get_all_students(db, teacher_id=teacher_id, semester=semester,
                                 skip=skip, limit=limit)


@router.get(
    "/{usn}",
    response_model=StudentWithAttendanceOut,
    summary="Get a student by USN with their latest attendance records",
)
def get_student_by_usn(usn: str, db: Session = Depends(get_db)):
    student = crud.get_student_by_usn(db, usn.upper())
    if not student:
        raise HTTPException(status_code=404, detail=f"Student USN '{usn}' not found")

    records = crud.get_latest_attendance_for_usn(db, usn.upper())
    student.attendance_records = records
    return student
