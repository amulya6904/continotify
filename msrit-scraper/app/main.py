import logging
import sys

from app.config import FERNET_KEY
from app.db import init_db, get_all_teachers
from app.scraper import scrape_teacher
from app.models import PortalNotReachableError, LoginFailedException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    if not FERNET_KEY:
        logger.error("FERNET_KEY not set in .env — cannot decrypt passwords. Exiting.")
        sys.exit(1)

    logger.info("Initializing database...")
    init_db()

    teachers = get_all_teachers()
    if not teachers:
        logger.warning(
            "No teachers found in database. "
            "Run `python scripts/add_teacher.py` to add a teacher first."
        )
        return

    logger.info(f"Starting scrape for {len(teachers)} teacher(s).")
    success_count = 0
    fail_count    = 0

    for teacher in teachers:
        teacher_name = teacher['name']
        logger.info(f"{'─' * 60}")
        logger.info(f"Teacher: {teacher_name}")
        try:
            scrape_teacher(teacher, FERNET_KEY)
            success_count += 1
        except PortalNotReachableError as e:
            logger.error(f"Portal not reachable for {teacher_name}: {e}")
            fail_count += 1
        except LoginFailedException as e:
            logger.error(f"Login failed for {teacher_name}: {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Unexpected error for {teacher_name}: {e}")
            fail_count += 1

    logger.info(f"{'─' * 60}")
    logger.info(f"Scrape complete — {success_count} succeeded, {fail_count} failed.")


if __name__ == "__main__":
    main()
