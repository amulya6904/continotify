import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "msrit_attendance")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))

ATTENDANCE_THRESHOLD = float(os.getenv("ATTENDANCE_THRESHOLD", 75.0))

NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8001")

EMAILS_CSV_PATH = os.getenv("EMAILS_CSV_PATH", "emails.csv")

# URL-encode password to safely handle special characters like @
_db_password_escaped = quote_plus(DB_PASSWORD)
DATABASE_URL = (
    f"postgresql://{DB_USER}:{_db_password_escaped}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
