import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)

from app.config import SCRAPE_TIMEOUT
from app.models import StudentParseError, AttendanceParseError
from app.attendance import extract_attendance_from_modal
from app.db import upsert_student, save_attendance_records

logger = logging.getLogger(__name__)


def navigate_to_proctorship(driver):
    """Click the PROCTORSHIP nav link and wait for student cards to load."""
    proctorship_link = driver.find_element(By.LINK_TEXT, "PROCTORSHIP")
    proctorship_link.click()
    try:
        WebDriverWait(driver, SCRAPE_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.uk-card.cn-classcard"))
        )
    except TimeoutException:
        raise TimeoutException(
            "Proctorship page did not load student cards within timeout"
        )
    logger.info("Navigated to Proctorship page — student cards loaded.")


def _find_pink_dot(card):
    """
    4-level fallback strategy to locate the Performance (pink) dot anchor.
    Returns the anchor element or None.
    """
    # Primary: href contains task=performance — most reliable
    try:
        return card.find_element(By.CSS_SELECTOR, "a.thickbox[href*='task=performance']")
    except NoSuchElementException:
        pass

    # Fallback 1: img title attribute 'Performance' → parent anchor
    try:
        img = card.find_element(By.CSS_SELECTOR, "img.cn-option-img[title='Performance']")
        return img.find_element(By.XPATH, "./..")
    except NoSuchElementException:
        pass

    # Fallback 2: img src filename contains 'pink' → parent anchor
    try:
        img = card.find_element(By.CSS_SELECTOR, "img.cn-option-img[src*='pink']")
        return img.find_element(By.XPATH, "./..")
    except NoSuchElementException:
        pass

    # Fallback 3: positional — 2nd thickbox anchor (index 1)
    try:
        dots = card.find_elements(By.CSS_SELECTOR, "a.thickbox")
        if len(dots) >= 2:
            return dots[1]
    except NoSuchElementException:
        pass

    return None


def _extract_card_data(card):
    """
    Extract name, USN, semester, registration_status, backlogs_status
    from a div.cn-padleft-zero student card.
    Raises StudentParseError if USN cannot be found.
    """
    # Student name
    try:
        name_elem = card.find_element(By.CSS_SELECTOR, "div.uk-width-2-5.uk-flex > a")
        name = name_elem.text.strip()
    except NoSuchElementException:
        raise StudentParseError("Student name element not found in card")

    # USN and Semester — card text contains "1MS23CS211 | SEM06"
    usn = ""
    semester = ""
    try:
        container = card.find_element(By.CSS_SELECTOR, "div.uk-width-2-5.uk-flex")
        full_text = container.text.strip()
        for line in full_text.splitlines():
            line = line.strip()
            if not line or line == name:
                continue
            if '|' in line:
                parts = line.split('|', 1)
                usn      = parts[0].strip()
                semester = parts[1].strip()
                break
            elif line:
                usn = line  # USN without semester separator
    except NoSuchElementException as e:
        raise StudentParseError(f"Error reading USN/semester container: {e}")

    if not usn:
        raise StudentParseError(f"USN not found in card for student: {name}")

    # Registration status
    registration_status = ""
    try:
        reg_elem = card.find_element(
            By.XPATH,
            ".//*[contains(text(),'Fees Status') or contains(text(),'Registration')]"
        )
        registration_status = reg_elem.text.strip()
    except NoSuchElementException:
        pass

    # Backlogs status
    backlogs_status = ""
    try:
        backlog_elem = card.find_element(
            By.XPATH,
            ".//*[contains(text(),'No Backlogs') or contains(text(),'Backlog')]"
        )
        backlogs_status = backlog_elem.text.strip()
    except NoSuchElementException:
        pass

    return name, usn, semester, registration_status, backlogs_status


def scrape_all_students(driver, teacher_id: int):
    """
    Iterate all student cards on the Proctorship page.
    For each card: extract metadata → upsert student → click pink dot
    → parse modal → save attendance records.
    Re-fetches student_blocks each iteration to avoid StaleElementReferenceException.
    """
    student_blocks = driver.find_elements(By.CSS_SELECTOR, "div.cn-padleft-zero")
    total   = len(student_blocks)
    success = 0

    logger.info(f"Found {total} student cards for teacher_id={teacher_id}")

    for i in range(total):
        try:
            # Always re-fetch the full list before accessing by index
            student_blocks = driver.find_elements(By.CSS_SELECTOR, "div.cn-padleft-zero")
            if i >= len(student_blocks):
                logger.warning(f"Card index {i} out of range after re-fetch — stopping.")
                break

            card = student_blocks[i]

            # ── 1. Extract student metadata ──────────────────────────────────
            try:
                name, usn, semester, reg_status, backlog_status = _extract_card_data(card)
            except StudentParseError as e:
                logger.warning(f"StudentParseError at card {i}: {e}")
                continue

            logger.info(f"  [{i + 1}/{total}] {name} | {usn} | {semester}")

            # ── 2. Upsert student row ────────────────────────────────────────
            student_id = upsert_student(
                teacher_id, name, usn, semester, reg_status, backlog_status
            )

            # ── 3. Re-fetch card reference, find pink dot ────────────────────
            student_blocks = driver.find_elements(By.CSS_SELECTOR, "div.cn-padleft-zero")
            card           = student_blocks[i]
            pink_dot       = _find_pink_dot(card)

            if not pink_dot:
                logger.warning(f"  Pink dot not found for {usn} — skipping attendance.")
                continue

            # JS click avoids element-not-interactable on thickbox anchors
            driver.execute_script("arguments[0].click();", pink_dot)

            # ── 4. Extract attendance from modal ─────────────────────────────
            try:
                records = extract_attendance_from_modal(driver)
                save_attendance_records(student_id, records)
                logger.info(f"  Stored {len(records)} attendance records for {usn}")
                success += 1
            except AttendanceParseError as e:
                logger.error(f"  AttendanceParseError for {usn}: {e}")
                continue

            time.sleep(0.5)  # brief pause between students

        except StaleElementReferenceException:
            logger.warning(f"StaleElementReferenceException at card {i} — re-fetching.")
            continue
        except Exception as e:
            logger.error(f"Unexpected error at card {i}: {e}")
            continue

    logger.info(
        f"teacher_id={teacher_id} complete — {success}/{total} students scraped successfully."
    )
