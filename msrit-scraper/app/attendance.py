import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from app.config import SCRAPE_TIMEOUT
from app.models import AttendanceParseError

logger = logging.getLogger(__name__)

# Column index mapping (confirmed from live portal, PRD Section 5)
COL_SUBJECT_NAME        = 0
COL_FACULTY             = 1   # not stored
COL_COURSE_TYPE         = 2
COL_ATTENDANCE_PCT      = 3
COL_PRESENT_TOTAL       = 4
COL_CIE_NAME            = 5   # not stored
COL_CIE_MAX             = 6
COL_CIE_OBTAINED        = 7


def extract_attendance_from_modal(driver) -> list:
    """
    Wait for the Course wise - Status thickbox modal to appear,
    parse every row in table.cn-table tbody, close the modal,
    and return a list of record dicts.
    """
    try:
        WebDriverWait(driver, SCRAPE_TIMEOUT).until(
            EC.visibility_of_element_located((By.ID, "TB_ajaxContent"))
        )
    except TimeoutException:
        raise AttendanceParseError(
            "#TB_ajaxContent not visible within timeout — modal may not have opened"
        )

    records = []
    try:
        content = driver.find_element(By.ID, "TB_ajaxContent")

        try:
            table = content.find_element(
                By.CSS_SELECTOR, "table.uk-table.uk-table-middle.cn-table"
            )
        except NoSuchElementException:
            raise AttendanceParseError(
                "table.cn-table not found inside #TB_ajaxContent"
            )

        rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
        if not rows:
            raise AttendanceParseError("table.cn-table tbody has no rows")

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 8:
                logger.warning(f"Skipping row — only {len(cells)} cells (expected ≥8)")
                continue

            subject_name = cells[COL_SUBJECT_NAME].text.strip()
            course_type  = cells[COL_COURSE_TYPE].text.strip()

            # Attendance percentage — strip trailing '%'
            att_pct_text = cells[COL_ATTENDANCE_PCT].text.strip().rstrip('%').strip()
            try:
                attendance_percentage = float(att_pct_text) if att_pct_text else None
            except ValueError:
                attendance_percentage = None

            # Present / Total — parse "21/26"; edge case "/0"
            present_total_text = cells[COL_PRESENT_TOTAL].text.strip()
            attended_classes = None
            total_classes    = None
            if '/' in present_total_text:
                left, right = present_total_text.split('/', 1)
                try:
                    attended_classes = int(left.strip()) if left.strip() else None
                except ValueError:
                    attended_classes = None
                try:
                    total_classes = int(right.strip()) if right.strip() else None
                except ValueError:
                    total_classes = None

            # CIE marks — NULL when "Marks Not Entered" appears anywhere in the row
            row_text = row.text
            marks_not_entered = "Marks Not Entered" in row_text

            cie_max_marks      = None
            cie_obtained_marks = None

            if not marks_not_entered:
                max_text = cells[COL_CIE_MAX].text.strip()
                try:
                    cie_max_marks = int(float(max_text)) if max_text else None
                except ValueError:
                    cie_max_marks = None

                obtained_text = cells[COL_CIE_OBTAINED].text.strip()
                try:
                    cie_obtained_marks = int(float(obtained_text)) if obtained_text else None
                except ValueError:
                    cie_obtained_marks = None

            records.append({
                'subject_name':         subject_name,
                'course_type':          course_type,
                'attendance_percentage': attendance_percentage,
                'total_classes':        total_classes,
                'attended_classes':     attended_classes,
                'cie_max_marks':        cie_max_marks,
                'cie_obtained_marks':   cie_obtained_marks,
            })

    except AttendanceParseError:
        raise
    except Exception as e:
        raise AttendanceParseError(f"Unexpected error parsing attendance table: {e}")
    finally:
        _close_modal(driver)

    return records


def _close_modal(driver):
    """Close the thickbox modal — three fallback strategies."""
    # Strategy 1: dedicated close div
    try:
        btn = driver.find_element(By.ID, "TB_closeAjaxWindow")
        btn.click()
        time.sleep(0.4)
        return
    except (NoSuchElementException, WebDriverException):
        pass

    # Strategy 2: anchor close button
    try:
        btn = driver.find_element(By.ID, "TB_closeWindowButton")
        btn.click()
        time.sleep(0.4)
        return
    except (NoSuchElementException, WebDriverException):
        pass

    # Strategy 3: Escape key
    try:
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.4)
    except Exception as e:
        logger.warning(f"All modal close strategies failed: {e}")
