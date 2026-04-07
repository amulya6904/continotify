from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.schemas import HealthOut

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthOut, summary="Service health check")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"

    return HealthOut(status="ok", db=db_status, version="4.0.0")
