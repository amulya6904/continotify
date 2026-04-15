import csv
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.database import engine, Base, SessionLocal, init_db
from backend.models import Student
from backend.routers import health, teachers, students, attendance, alerts
from backend.config import API_HOST, API_PORT, ATTENDANCE_THRESHOLD, EMAILS_CSV_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _sync_student_emails() -> None:
    """
    Read emails.csv (USN,Email) and update student_email for matching USNs.
    Runs once at startup. Safe to re-run — idempotent UPDATE.
    """
    if not os.path.exists(EMAILS_CSV_PATH):
        logger.warning(
            f"emails.csv not found at '{EMAILS_CSV_PATH}' — skipping student email sync. "
            f"Create the file or set EMAILS_CSV_PATH env var."
        )
        return

    rows: list[tuple[str, str]] = []
    try:
        with open(EMAILS_CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                usn   = (row.get("USN")   or "").strip().upper()
                email = (row.get("Email") or "").strip().lower()
                if usn and email:
                    rows.append((usn, email))
    except Exception as e:
        logger.error(f"Failed to read {EMAILS_CSV_PATH}: {e}")
        return

    if not rows:
        logger.info("emails.csv is empty or has no valid rows — nothing to sync")
        return

    db = SessionLocal()
    updated = skipped = 0
    try:
        for usn, email in rows:
            student = db.query(Student).filter(Student.usn == usn).first()
            if student:
                student.student_email = email
                updated += 1
            else:
                skipped += 1
        db.commit()
        logger.info(
            f"Student email sync complete — {updated} updated, {skipped} USNs not found in DB"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Student email sync DB error — rolled back: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MSRIT Attendance API...")
    logger.info(f"Attendance threshold: {ATTENDANCE_THRESHOLD}%")
    init_db()
    _sync_student_emails()
    yield
    logger.info("Shutting down MSRIT Attendance API.")


app = FastAPI(
    title="MSRIT Attendance API",
    description=(
        "Phase 2 backend — reads scraper data from PostgreSQL and exposes "
        "attendance analytics. portal_password_encrypted is structurally "
        "absent from all responses."
    ),
    version="4.0.0",
    lifespan=lifespan,
)

# ── CORS — allow all origins (internal college LAN tool) ─────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(teachers.router)
app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(alerts.router)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=API_HOST, port=API_PORT, reload=True)
