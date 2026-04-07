import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

from app.config import PORTAL_URL, LOGIN_TIMEOUT
from app.models import LoginFailedException, PortalNotReachableError

logger = logging.getLogger(__name__)


def login(driver, username: str, password: str):
    """
    Navigate to PORTAL_URL, fill login form, submit, and confirm success
    by waiting for the PROCTORSHIP nav link.
    """
    try:
        driver.get(PORTAL_URL)
    except WebDriverException as e:
        raise PortalNotReachableError(f"Cannot reach portal at {PORTAL_URL}: {e}")

    try:
        username_field = WebDriverWait(driver, LOGIN_TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "myInput"))
        )
        password_field = driver.find_element(By.ID, "mypass")
        submit_btn = driver.find_element(
            By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
        )

        username_field.clear()
        username_field.send_keys(username)
        password_field.clear()
        password_field.send_keys(password)
        submit_btn.click()
    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        raise LoginFailedException(f"Error interacting with login form: {e}")

    try:
        WebDriverWait(driver, LOGIN_TIMEOUT).until(
            EC.presence_of_element_located((By.LINK_TEXT, "PROCTORSHIP"))
        )
        logger.info(f"Login successful for user: {username}")
    except TimeoutException:
        raise LoginFailedException(
            f"PROCTORSHIP link not found after login — credentials may be wrong "
            f"or session did not start for user: {username}"
        )


def logout(driver):
    """Attempt graceful logout. Non-fatal — driver.quit() always runs in finally."""
    try:
        logout_link = driver.find_element(By.LINK_TEXT, "LOGOUT")
        logout_link.click()
        logger.info("Logged out successfully.")
    except Exception as e:
        logger.warning(f"Logout failed (non-fatal): {e}")
