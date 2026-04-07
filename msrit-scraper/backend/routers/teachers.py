from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import TeacherOut, TeacherWithStudentsOut
from backend import crud

router = APIRouter(prefix="/teachers", tags=["Teachers"])


@router.get("", response_model=list[TeacherOut], summary="List all teachers")
def list_teachers(db: Session = Depends(get_db)):
    return crud.get_all_teachers(db)


@router.get(
    "/{teacher_id}",
    response_model=TeacherWithStudentsOut,
    summary="Get a teacher with their student list",
)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    teacher = crud.get_teacher_by_id(db, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail=f"Teacher id={teacher_id} not found")
    return teacher
