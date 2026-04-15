from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session, always closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Apply lightweight, idempotent migrations needed by the backend."""
    with engine.connect() as conn:
        # Ensure student_email exists for alerting and email sync
        conn.execute(
            text("ALTER TABLE students ADD COLUMN IF NOT EXISTS student_email TEXT")
        )
        conn.commit()
