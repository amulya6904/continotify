import logging
import re
import time
from pathlib import Path

from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.config import DEBUG_POPUP_DUMP, DEBUG_POPUP_DUMP_PATH, SCRAPE_TIMEOUT
from app.models import AttendanceParseError

logger = logging.getLogger(__name__)
_debug_popup_dumped = False


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _outer_html(element) -> str:
    try:
        return element.get_attribute("outerHTML") or ""
    except Exception:
        return ""


def _snippet(element, limit: int = 1000) -> str:
    return _normalize_text(_outer_html(element))[:limit]


def _popup_html(driver) -> str:
    for selector in ("#TB_window", "#TB_ajaxContent"):
        try:
            elem = driver.find_element(By.CSS_SELECTOR, selector)
            html = _outer_html(elem)
            if html:
                return html
        except NoSuchElementException:
            pass
    return driver.page_source or ""


def _maybe_dump_debug_popup(driver, reason: str):
    global _debug_popup_dumped
    if not DEBUG_POPUP_DUMP or _debug_popup_dumped:
        return

    try:
        Path(DEBUG_POPUP_DUMP_PATH).write_text(_popup_html(driver), encoding="utf-8")
        _debug_popup_dumped = True
        logger.info("Dumped failing popup HTML (%s) to %s", reason, DEBUG_POPUP_DUMP_PATH)
    except OSError as e:
        logger.warning("Failed to dump popup HTML to %s: %s", DEBUG_POPUP_DUMP_PATH, e)


def _raise_attendance_parse_error(driver, message: str):
    _maybe_dump_debug_popup(driver, message)
    raise AttendanceParseError(message)


def _cell_texts(row, tag_name: str) -> list[str]:
    return [_normalize_text(cell.text) for cell in row.find_elements(By.TAG_NAME, tag_name)]


def _header_key(value: str) -> str:
    value = _normalize_text(value).lower()
    return re.sub(r"[^a-z0-9/]+", " ", value).strip()


def _build_column_map(table) -> dict[str, int]:
    """
    Build a tolerant column map for the current Continueo attendance table.
    The live table uses rowspans/colspans, so this falls back to the known
    visual order when header flattening cannot fully resolve columns.
    """
    rows = table.find_elements(By.CSS_SELECTOR, "thead tr")
    first = _cell_texts(rows[0], "th") if rows else []
    second = _cell_texts(rows[1], "th") if len(rows) > 1 else []

    column_map = {
        "subject": 0,
        "faculty": 1,
        "course_type": 2,
        "attendance_percentage": 3,
        "present_total": 4,
        "cie_name": 5,
        "cie_max": 6,
        "cie_obtained": 7,
        "cie_total": 8,
    }

    header_text = " ".join(first + second)
    if not header_text:
        return column_map

    flat_headers = [
        " ".join(part for part in [first[0] if len(first) > 0 else "course code/name"] if part),
        " ".join(part for part in [first[1] if len(first) > 1 else "faculty"] if part),
        " ".join(part for part in [first[2] if len(first) > 2 else "course type"] if part),
        " ".join(part for part in ["attendance", second[0] if len(second) > 0 else "total %"] if part),
        " ".join(part for part in ["attendance", second[1] if len(second) > 1 else "present /total"] if part),
        " ".join(part for part in ["cie", second[2] if len(second) > 2 else "name"] if part),
        " ".join(part for part in ["cie", second[3] if len(second) > 3 else "max marks"] if part),
        " ".join(part for part in ["cie", second[4] if len(second) > 4 else "obtained marks"] if part),
        " ".join(part for part in ["cie", second[5] if len(second) > 5 else "total"] if part),
    ]

    for idx, header in enumerate(flat_headers):
        key = _header_key(header)
        if "course code" in key or "course name" in key:
            column_map["subject"] = idx
        elif "faculty" in key:
            column_map["faculty"] = idx
        elif "course type" in key:
            column_map["course_type"] = idx
        elif "present" in key:
            column_map["present_total"] = idx
        elif "attendance" in key and ("total" in key or "%" in key):
            column_map["attendance_percentage"] = idx
        elif "cie" in key and "max" in key:
            column_map["cie_max"] = idx
        elif "cie" in key and "obtained" in key:
            column_map["cie_obtained"] = idx

    return column_map


def _value(cells: list, column_map: dict[str, int], key: str) -> str:
    idx = column_map[key]
    if idx >= len(cells):
        return ""
    return _normalize_text(cells[idx].text)


def _parse_float(value: str):
    text = value.replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: str):
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def extract_attendance_from_modal(driver) -> list:
    """
    Wait for the Course wise - Status thickbox modal, parse attendance rows,
    close the modal, and return DB-ready record dictionaries.
    """
    try:
        WebDriverWait(driver, SCRAPE_TIMEOUT).until(
            lambda d: (
                d.find_elements(By.CSS_SELECTOR, "#TB_window")
                or d.find_elements(By.CSS_SELECTOR, "#TB_ajaxContent")
            )
        )
        WebDriverWait(driver, SCRAPE_TIMEOUT).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "#TB_ajaxContent table.uk-table.uk-table-middle.cn-table, "
                    "#TB_ajaxContent table.cn-table, "
                    "#TB_ajaxContent table",
                )
            )
        )
    except TimeoutException:
        _raise_attendance_parse_error(
            driver,
            "#TB_ajaxContent table not visible within timeout; modal may not have opened"
        )

    records = []
    try:
        content = driver.find_element(By.ID, "TB_ajaxContent")

        tables = content.find_elements(By.CSS_SELECTOR, "table.uk-table, table.cn-table, table")
        table = None
        for candidate in tables:
            text = _normalize_text(candidate.text).lower()
            if "course" in text and "attendance" in text:
                table = candidate
                break

        if table is None:
            _raise_attendance_parse_error(driver, "attendance table not found inside #TB_ajaxContent")

        logger.info("  Attendance table found; parsing rows")

        column_map = _build_column_map(table)
        rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
        if not rows:
            rows = table.find_elements(By.CSS_SELECTOR, "tr")
        logger.info("  Attendance table has %s candidate rows", len(rows))

        parsed_rows = 0
        for row_index, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "td")
            if not cells:
                continue

            if len(cells) < 5:
                logger.warning(
                    "Skipping attendance row %s; only %s cells; row outerHTML[:1000]=%s",
                    row_index,
                    len(cells),
                    _snippet(row),
                )
                continue

            subject_name = _value(cells, column_map, "subject")
            if not subject_name:
                logger.warning(
                    "Skipping attendance row %s; missing course code/name; row outerHTML[:1000]=%s",
                    row_index,
                    _snippet(row),
                )
                continue

            course_type = _value(cells, column_map, "course_type")
            attendance_percentage = _parse_float(_value(cells, column_map, "attendance_percentage"))

            present_total_text = _value(cells, column_map, "present_total")
            attended_classes = None
            total_classes = None
            if "/" in present_total_text:
                left, right = present_total_text.split("/", 1)
                attended_classes = _parse_int(left.strip())
                total_classes = _parse_int(right.strip())

            row_text = _normalize_text(row.text)
            marks_not_entered = "marks not entered" in row_text.lower()

            cie_max_marks = None
            cie_obtained_marks = None
            if not marks_not_entered:
                cie_max_marks = _parse_int(_value(cells, column_map, "cie_max"))
                cie_obtained_marks = _parse_int(_value(cells, column_map, "cie_obtained"))

            records.append({
                "subject_name": subject_name,
                "course_type": course_type,
                "attendance_percentage": attendance_percentage,
                "total_classes": total_classes,
                "attended_classes": attended_classes,
                "cie_max_marks": cie_max_marks,
                "cie_obtained_marks": cie_obtained_marks,
            })
            parsed_rows += 1

        if parsed_rows == 0:
            _raise_attendance_parse_error(driver, "attendance table had no parseable data rows")

    except AttendanceParseError:
        raise
    except Exception as e:
        raise AttendanceParseError(f"Unexpected error parsing attendance table: {e}")
    finally:
        _close_modal(driver)

    return records


def _close_modal(driver):
    """Close the thickbox modal with fallback strategies."""
    try:
        btn = driver.find_element(By.ID, "TB_closeAjaxWindow")
        btn.click()
        time.sleep(0.4)
        return
    except (NoSuchElementException, WebDriverException):
        pass

    try:
        btn = driver.find_element(By.ID, "TB_closeWindowButton")
        btn.click()
        time.sleep(0.4)
        return
    except (NoSuchElementException, WebDriverException):
        pass

    try:
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.4)
    except Exception as e:
        logger.warning("All modal close strategies failed: %s", e)
