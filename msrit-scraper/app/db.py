import logging
import psycopg2
import psycopg2.extras
from app.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

logger = logging.getLogger(__name__)


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def init_db():
    """Create all three tables if they do not exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS teachers (
                    id                          SERIAL PRIMARY KEY,
                    name                        VARCHAR(255) NOT NULL,
                    email                       VARCHAR(255) UNIQUE,
                    portal_username             VARCHAR(255),
                    portal_password_encrypted   TEXT,
                    created_at                  TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id                      SERIAL PRIMARY KEY,
                    teacher_id              INTEGER REFERENCES teachers(id) ON DELETE CASCADE,
                    name                    VARCHAR(255),
                    usn                     VARCHAR(50),
                    semester                VARCHAR(20),
                    registration_status     VARCHAR(255),
                    backlogs_status         VARCHAR(255),
                    created_at              TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(teacher_id, usn)
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_students_usn ON students(usn)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS attendance_records (
                    id                      SERIAL PRIMARY KEY,
                    student_id              INTEGER REFERENCES students(id) ON DELETE CASCADE,
                    subject_name            VARCHAR(255),
                    course_type             VARCHAR(100),
                    attendance_percentage   NUMERIC(5,2),
                    total_classes           INTEGER,
                    attended_classes        INTEGER,
                    cie_max_marks           INTEGER,
                    cie_obtained_marks      INTEGER,
                    scraped_at              TIMESTAMPTZ DEFAULT NOW()
                )
            """)

        conn.commit()
        logger.info("Database initialized successfully.")
    finally:
        conn.close()


def get_all_teachers():
    """Return all teachers from DB as a list of dicts."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, email, portal_username, portal_password_encrypted
                FROM teachers
            """)
            return cur.fetchall()
    finally:
        conn.close()


def upsert_teacher(name: str, email: str, portal_username: str,
                   portal_password_encrypted: str) -> int:
    """Insert or update a teacher record. Returns teacher id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO teachers (name, email, portal_username, portal_password_encrypted)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE
                    SET name                      = EXCLUDED.name,
                        portal_username           = EXCLUDED.portal_username,
                        portal_password_encrypted = EXCLUDED.portal_password_encrypted
                RETURNING id
            """, (name, email, portal_username, portal_password_encrypted))
            teacher_id = cur.fetchone()[0]
        conn.commit()
        return teacher_id
    finally:
        conn.close()


def upsert_student(teacher_id: int, name: str, usn: str, semester: str,
                   registration_status: str, backlogs_status: str) -> int:
    """Insert or update a student record. Returns student id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO students
                    (teacher_id, name, usn, semester, registration_status, backlogs_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (teacher_id, usn) DO UPDATE
                    SET name                = EXCLUDED.name,
                        semester            = EXCLUDED.semester,
                        registration_status = EXCLUDED.registration_status,
                        backlogs_status     = EXCLUDED.backlogs_status
                RETURNING id
            """, (teacher_id, name, usn, semester, registration_status, backlogs_status))
            student_id = cur.fetchone()[0]
        conn.commit()
        return student_id
    finally:
        conn.close()


def save_attendance_records(student_id: int, records: list):
    """
    Delete today's records for this student then insert fresh ones.
    This ensures re-scraping on the same day reflects the latest portal data.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM attendance_records
                WHERE student_id = %s AND scraped_at::date = CURRENT_DATE
            """, (student_id,))

            for r in records:
                cur.execute("""
                    INSERT INTO attendance_records (
                        student_id, subject_name, course_type,
                        attendance_percentage, total_classes, attended_classes,
                        cie_max_marks, cie_obtained_marks
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    student_id,
                    r['subject_name'],
                    r['course_type'],
                    r['attendance_percentage'],
                    r['total_classes'],
                    r['attended_classes'],
                    r['cie_max_marks'],
                    r['cie_obtained_marks'],
                ))
        conn.commit()
    finally:
        conn.close()
