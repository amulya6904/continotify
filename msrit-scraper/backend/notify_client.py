import logging
import httpx

from backend.config import NOTIFICATION_SERVICE_URL

logger = logging.getLogger(__name__)

TIMEOUT     = 10   # seconds per attempt
MAX_RETRIES = 1    # retry once on timeout


def send_alert_to_service(payload: dict) -> dict:
    """
    POST payload to the notification service.
    Retries once on timeout.
    Returns the JSON response dict, or raises on unrecoverable failure.
    """
    url = f"{NOTIFICATION_SERVICE_URL}/notify"
    last_error = None

    for attempt in range(1, MAX_RETRIES + 2):  # attempts: 1, 2
        try:
            logger.info(f"Calling notification service (attempt {attempt}): {url}")
            logger.info(f"Payload — teacher: {payload['teacher']['email']}, "
                        f"students: {len(payload['students'])}")

            response = httpx.post(url, json=payload, timeout=TIMEOUT)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Notification service response: {result}")
            return result

        except httpx.TimeoutException as e:
            last_error = f"Timeout on attempt {attempt}: {e}"
            logger.warning(last_error)
            if attempt <= MAX_RETRIES:
                logger.info("Retrying once...")
                continue
            break

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code} from notification service: {e.response.text}"
            logger.error(last_error)
            break

        except httpx.ConnectError as e:
            last_error = f"Notification service is down or unreachable at {url}: {e}"
            logger.error(last_error)
            break

        except Exception as e:
            last_error = f"Unexpected error calling notification service: {e}"
            logger.error(last_error)
            break

    raise RuntimeError(last_error)
