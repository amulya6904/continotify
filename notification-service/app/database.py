from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create alert_logs table if it doesn't exist, and migrate any missing columns."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alert_logs (
                id                    SERIAL PRIMARY KEY,
                teacher_email         TEXT,
                student_name          TEXT,
                usn                   TEXT,
                subject_name          TEXT,
                attendance_percentage FLOAT,
                status                TEXT,
                error_message         TEXT,
                recipient_type        TEXT,
                created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Idempotent migration — safe to re-run on existing tables
        conn.execute(text(
            "ALTER TABLE alert_logs ADD COLUMN IF NOT EXISTS recipient_type TEXT"
        ))
        conn.commit()
