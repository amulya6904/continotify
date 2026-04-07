import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

from app.config import HEADLESS, CHROME_DRIVER_PATH
from app.models import PortalNotReachableError, LoginFailedException
from app.login import login, logout
from app.proctorship import navigate_to_proctorship, scrape_all_students

logger = logging.getLogger(__name__)


def build_driver():
    """
    Build a headless (or visible) Chrome WebDriver.
    Set HEADLESS=false in .env to see the browser during debugging.
    """
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if CHROME_DRIVER_PATH:
        service = Service(executable_path=CHROME_DRIVER_PATH)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=options)


def scrape_teacher(teacher: dict, fernet_key: str):
    """
    Full per-teacher lifecycle:
      1. Decrypt password
      2. Build driver
      3. Login
      4. Navigate to Proctorship
      5. Scrape all students
      6. Logout
      7. Quit driver (always, in finally)

    Raises PortalNotReachableError or LoginFailedException — caller handles these.
    """
    from app.encryption import decrypt_password

    teacher_id   = teacher['id']
    username     = teacher['portal_username']
    teacher_name = teacher['name']

    plain_password = decrypt_password(teacher['portal_password_encrypted'], fernet_key)

    driver = build_driver()
    try:
        login(driver, username, plain_password)
        navigate_to_proctorship(driver)
        scrape_all_students(driver, teacher_id)
        logout(driver)
    except (PortalNotReachableError, LoginFailedException):
        raise
    finally:
        driver.quit()
        plain_password = None  # clear from local scope
        logger.info(f"Browser closed for teacher: {teacher_name}")
