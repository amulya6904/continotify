import logging
import re
import time
from pathlib import Path

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.attendance import extract_attendance_from_modal
from app.config import DEBUG_CARD_DUMP, DEBUG_CARD_DUMP_PATH, SCRAPE_TIMEOUT
from app.db import save_attendance_records, upsert_student
from app.models import AttendanceParseError, StudentParseError

logger = logging.getLogger(__name__)

CARD_SELECTOR = "div.uk-card.cn-classcard"
CARD_SELECTOR_FALLBACK = "div.cn-padleft-zero div.uk-card.cn-classcard, div.cn-padleft-zero"
IDENTITY_SELECTOR = "div.uk-width-2-5.uk-flex"
USN_RE = re.compile(r"\b\d[A-Z]{2}\d{2}[A-Z]{2}\d{3}\b", re.IGNORECASE)
_debug_card_dumped = False


def navigate_to_proctorship(driver):
    """Click the PROCTORSHIP nav link and wait for student cards to load."""
    proctorship_link = driver.find_element(By.LINK_TEXT, "PROCTORSHIP")
    proctorship_link.click()
    try:
        WebDriverWait(driver, SCRAPE_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SELECTOR))
        )
    except TimeoutException:
        raise TimeoutException(
            "Proctorship page did not load student cards within timeout"
        )
    logger.info("Navigated to Proctorship page; student cards loaded.")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _get_outer_html(element) -> str:
    try:
        return element.get_attribute("outerHTML") or ""
    except Exception:
        return ""


def _outer_html_snippet(element, limit: int = 1000) -> str:
    return _normalize_text(_get_outer_html(element))[:limit]


def _maybe_dump_debug_card(card, index: int, field: str):
    global _debug_card_dumped
    if not DEBUG_CARD_DUMP or _debug_card_dumped:
        return

    try:
        Path(DEBUG_CARD_DUMP_PATH).write_text(_get_outer_html(card), encoding="utf-8")
        _debug_card_dumped = True
        logger.info(
            "Dumped failing card %s (%s) outerHTML to %s",
            index,
            field,
            DEBUG_CARD_DUMP_PATH,
        )
    except OSError as e:
        logger.warning("Failed to dump debug card %s to %s: %s", index, DEBUG_CARD_DUMP_PATH, e)


def _raise_card_parse_error(card, index: int, field: str, message: str):
    logger.warning(
        "Card %s parse failed while reading %s: %s | outerHTML[:1000]=%s",
        index,
        field,
        message,
        _outer_html_snippet(card),
    )
    _maybe_dump_debug_card(card, index, field)
    raise StudentParseError(f"{field}: {message}")


def _find_student_cards(driver):
    cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR)
    if cards:
        return cards
    return driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR_FALLBACK)


def _find_pink_dot(card):
    """
    Locate the attendance/performance thickbox link inside a student card.
    Returns the anchor element or None.
    """
    selectors = [
        "a.thickbox[href*='task=performance']",
        "a[href*='task=performance']",
        "a.thickbox[href*='course']",
        "a[href*='course'][href*='tmpl=component']",
        "a.thickbox[href*='com_dbvisuals']",
        "a[href*='com_dbvisuals'][href*='tmpl=component']",
        "a[href*='task=report']",
    ]

    candidates = []
    for selector in selectors:
        candidates.extend(card.find_elements(By.CSS_SELECTOR, selector))

    if candidates:
        return _best_attendance_link(candidates)

    try:
        img = card.find_element(By.CSS_SELECTOR, "img.cn-option-img[title='Performance']")
        return img.find_element(By.XPATH, "./..")
    except NoSuchElementException:
        pass

    try:
        img = card.find_element(By.CSS_SELECTOR, "img.cn-option-img[src*='pink']")
        return img.find_element(By.XPATH, "./..")
    except NoSuchElementException:
        pass

    try:
        dots = card.find_elements(By.CSS_SELECTOR, "a.thickbox")
        if len(dots) >= 2:
            return dots[1]
        if dots:
            return dots[0]
    except NoSuchElementException:
        pass

    return None


def _best_attendance_link(links):
    weighted = []
    for index, link in enumerate(links):
        href = (link.get_attribute("href") or "").lower()
        title = (link.get_attribute("title") or "").lower()
        text = (link.text or "").lower()
        img_title = ""
        try:
            img_title = (link.find_element(By.CSS_SELECTOR, "img").get_attribute("title") or "").lower()
        except NoSuchElementException:
            pass

        haystack = " ".join([href, title, text, img_title])
        score = 0
        for keyword, weight in (
            ("performance", 100),
            ("attendance", 90),
            ("course", 70),
            ("status", 50),
            ("report", 25),
            ("com_dbvisuals", 10),
        ):
            if keyword in haystack:
                score += weight
        weighted.append((score, -index, link))

    weighted.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return weighted[0][2]


def _wait_for_popup_table(driver, usn: str):
    wait = WebDriverWait(driver, SCRAPE_TIMEOUT)
    wait.until(
        lambda d: (
            d.find_elements(By.CSS_SELECTOR, "#TB_window")
            or d.find_elements(By.CSS_SELECTOR, "#TB_ajaxContent")
        )
    )
    wait.until(
        EC.presence_of_element_located(
            (
                By.CSS_SELECTOR,
                "#TB_ajaxContent table.uk-table.uk-table-middle.cn-table, "
                "#TB_ajaxContent table.cn-table, "
                "#TB_ajaxContent table",
            )
        )
    )
    logger.info("  Popup table found for %s", usn)


def _click_attendance_trigger(driver, trigger, usn: str) -> bool:
    href = trigger.get_attribute("href") or ""
    logger.info("  Opening attendance popup for %s via href=%s", usn, href[:250])

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            trigger,
        )
        WebDriverWait(driver, SCRAPE_TIMEOUT).until(lambda _driver: trigger.is_displayed())
        try:
            trigger.click()
            logger.info("  Normal click succeeded for %s", usn)
        except WebDriverException as click_error:
            logger.info("  Normal click failed for %s; using JS click: %s", usn, click_error)
            driver.execute_script("arguments[0].click();", trigger)

        _wait_for_popup_table(driver, usn)
        return True
    except TimeoutException as e:
        logger.warning("  Popup/table did not load for %s: %s", usn, e)
    except WebDriverException as e:
        logger.warning("  Popup click failed for %s: %s", usn, e)

    return False


def _extract_name(card, identity, index: int) -> str:
    selectors = [
        "h4 > span[title]",
        "h4 span[title]",
        "h4 span",
        "h4",
        "a",
    ]

    search_root = identity if identity is not None else card
    for selector in selectors:
        try:
            elem = search_root.find_element(By.CSS_SELECTOR, selector)
            text = _normalize_text(elem.get_attribute("title") or elem.text)
            if text:
                return text
        except NoSuchElementException:
            continue

    if identity is not None:
        for line in identity.text.splitlines():
            text = _normalize_text(line)
            if text and not USN_RE.search(text) and "|" not in text and "SEM" not in text.upper():
                return text

    _raise_card_parse_error(card, index, "student name", "student name element not found in card")


def _extract_usn_semester(card, identity, name: str, index: int) -> tuple[str, str]:
    roots = [identity, card] if identity is not None else [card]
    candidate_texts = []

    for root in roots:
        try:
            candidate_texts.extend(_normalize_text(p.text) for p in root.find_elements(By.TAG_NAME, "p"))
        except NoSuchElementException:
            pass

    if identity is not None:
        candidate_texts.extend(_normalize_text(line) for line in identity.text.splitlines())

    usn = ""
    semester = ""
    for text in candidate_texts:
        if not text or text == name:
            continue

        if "|" in text:
            left, right = text.split("|", 1)
            usn = _normalize_text(left)
            semester = _normalize_text(right)
            break

        match = USN_RE.search(text)
        if match:
            usn = match.group(0)
            sem_match = re.search(r"\bSEM\s*[-:]?\s*\d+\b|\bSEM\d+\b", text, re.IGNORECASE)
            semester = _normalize_text(sem_match.group(0)) if sem_match else ""
            break

    if not usn:
        _raise_card_parse_error(card, index, "USN/semester", f"USN not found in card for student: {name}")

    return usn.upper(), semester.upper()


def _extract_card_data(card, index: int):
    """
    Extract name, USN, semester, registration_status, backlogs_status
    from a div.uk-card.cn-classcard student card.
    Raises StudentParseError if required identity fields cannot be found.
    """
    identity = None
    try:
        identity = card.find_element(By.CSS_SELECTOR, IDENTITY_SELECTOR)
    except NoSuchElementException:
        logger.warning("Card %s identity section not found; trying card-wide fallbacks", index)

    name = _extract_name(card, identity, index)
    usn, semester = _extract_usn_semester(card, identity, name, index)

    registration_status = ""
    try:
        reg_elem = card.find_element(
            By.XPATH,
            ".//*[contains(text(),'Fees Status') or contains(text(),'Registration')]",
        )
        registration_status = _normalize_text(reg_elem.text)
    except NoSuchElementException:
        pass

    backlogs_status = ""
    try:
        backlog_elem = card.find_element(
            By.XPATH,
            ".//*[contains(text(),'No Backlogs') or contains(text(),'Backlog')]",
        )
        backlogs_status = _normalize_text(backlog_elem.text)
    except NoSuchElementException:
        pass

    return name, usn, semester, registration_status, backlogs_status


def scrape_all_students(driver, teacher_id: int):
    """
    Iterate all student cards on the Proctorship page.
    For each card: extract metadata, upsert student, click attendance link,
    parse modal, and save attendance records.
    """
    WebDriverWait(driver, SCRAPE_TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SELECTOR))
    )

    student_blocks = _find_student_cards(driver)
    total = len(student_blocks)
    parsed_students = 0
    popup_opened = 0
    attendance_rows = 0
    success = 0

    logger.info("Found %s student cards for teacher_id=%s", total, teacher_id)

    for i in range(total):
        try:
            student_blocks = _find_student_cards(driver)
            if i >= len(student_blocks):
                logger.warning("Card index %s out of range after re-fetch; stopping.", i)
                break

            card = student_blocks[i]

            try:
                name, usn, semester, reg_status, backlog_status = _extract_card_data(card, i)
            except StudentParseError as e:
                logger.warning("StudentParseError at card %s: %s", i, e)
                continue

            logger.info("  [%s/%s] %s | %s | %s", i + 1, total, name, usn, semester)
            if i == 0:
                logger.info("First card extracted: name=%s, usn=%s, semester=%s", name, usn, semester)
            parsed_students += 1

            student_id = upsert_student(
                teacher_id, name, usn, semester, reg_status, backlog_status
            )

            student_blocks = _find_student_cards(driver)
            card = student_blocks[i]
            pink_dot = _find_pink_dot(card)

            if not pink_dot:
                logger.warning(
                    "Card %s attendance/detail link not found for %s; outerHTML[:1000]=%s",
                    i,
                    usn,
                    _outer_html_snippet(card),
                )
                _maybe_dump_debug_card(card, i, "attendance/detail link")
                continue

            if not _click_attendance_trigger(driver, pink_dot, usn):
                logger.warning(
                    "Card %s popup open failed for %s; outerHTML[:1000]=%s",
                    i,
                    usn,
                    _outer_html_snippet(card),
                )
                _maybe_dump_debug_card(card, i, "attendance popup")
                continue

            popup_opened += 1

            try:
                records = extract_attendance_from_modal(driver)
                logger.info("  Parsed %s attendance rows for %s", len(records), usn)
                save_attendance_records(student_id, records)
                logger.info("  Stored %s attendance records for %s", len(records), usn)
                attendance_rows += len(records)
                success += 1
            except AttendanceParseError as e:
                logger.error("  AttendanceParseError for %s: %s", usn, e)
                continue

            time.sleep(0.5)

        except StaleElementReferenceException:
            logger.warning("StaleElementReferenceException at card %s; re-fetching.", i)
            continue
        except Exception as e:
            logger.error("Unexpected error at card %s: %s", i, e)
            continue

    logger.info(
        "teacher_id=%s complete; cards=%s, parsed_students=%s, popup_opened=%s, "
        "students_with_attendance=%s, attendance_rows=%s.",
        teacher_id,
        total,
        parsed_students,
        popup_opened,
        success,
        attendance_rows,
    )
