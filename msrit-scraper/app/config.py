import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PORTAL_URL = os.getenv("PORTAL_URL", "https://staff.msrit.edu")
LOGIN_TIMEOUT = int(os.getenv("LOGIN_TIMEOUT", 15))
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", 10))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
DEBUG_CARD_DUMP = os.getenv("DEBUG_CARD_DUMP", "false").lower() == "true"
DEBUG_CARD_DUMP_PATH = os.getenv("DEBUG_CARD_DUMP_PATH", "debug_card.html")
DEBUG_POPUP_DUMP = os.getenv("DEBUG_POPUP_DUMP", "false").lower() == "true"
DEBUG_POPUP_DUMP_PATH = os.getenv("DEBUG_POPUP_DUMP_PATH", "debug_popup.html")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "msrit_attendance")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

FERNET_KEY = os.getenv("FERNET_KEY")
CHROME_DRIVER_PATH = os.getenv("CHROME_DRIVER_PATH", "")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
ATTENDANCE_THRESHOLD = float(os.getenv("ATTENDANCE_THRESHOLD", 75.0))
