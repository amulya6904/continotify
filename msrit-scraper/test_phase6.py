"""
test_phase6.py — Phase 6 end-to-end smoke test

Checks every new Phase 6 feature without touching production data.

Run from msrit-scraper/ directory:
    python3 test_phase6.py

    # To also test real student email delivery, pass your email:
    python3 test_phase6.py --student-email you@gmail.com

Requirements: both services must be running
    Backend:              python3 -m uvicorn backend.main:app --port 8000 --reload
    Notification service: python3 -m uvicorn app.main:app --port 8001 --reload  (from notification-service/)
"""

import sys
import json
import argparse
import urllib.request
import urllib.error
from typing import Any

# ── CLI args ──────────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--student-email", default=None,
                     help="Real email address to use for live student email delivery test")
_args, _ = _parser.parse_known_args()
TEST_STUDENT_EMAIL: str | None = _args.student_email

BACKEND   = "http://localhost:8000"
NOTIF_SVC = "http://localhost:8001"

PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"
SKIP = "\033[93m  SKIP\033[0m"
INFO = "\033[94m  INFO\033[0m"

results: list[tuple[str, bool, str]] = []


# ─── helpers ─────────────────────────────────────────────────────────────────

def _request(method: str, url: str, body: dict | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except urllib.error.URLError as e:
        return 0, {"detail": str(e.reason)}


def check(name: str, passed: bool, detail: str = "") -> bool:
    tag = PASS if passed else FAIL
    print(f"{tag}  {name}")
    if detail:
        print(f"       → {detail}")
    results.append((name, passed, detail))
    return passed


def info(msg: str):
    print(f"{INFO}  {msg}")


def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print('─'*60)


# ─── 1. Service health ────────────────────────────────────────────────────────

section("1 · Service health")

status, body = _request("GET", f"{BACKEND}/health")
check(
    "Backend reachable (port 8000)",
    status == 200,
    f"HTTP {status} — {body}" if status != 200 else f"version={body.get('version')} db={body.get('db')}",
)
backend_ok = status == 200

status, body = _request("GET", f"{NOTIF_SVC}/alerts/logs?limit=1")
# Notification service has no /health route — /alerts/logs is its lightest GET endpoint
notif_ok = status == 200
check(
    "Notification service reachable (port 8001)",
    notif_ok,
    f"HTTP {status} — {body}" if not notif_ok else "OK",
)

if not backend_ok:
    print(f"\n{FAIL}  Backend not running — most tests will be skipped.\n")
    print("  Start with:  python3 -m uvicorn backend.main:app --port 8000 --reload")


# ─── 2. Student email in /low-attendance response ─────────────────────────────

section("2 · student_email field in /low-attendance")

if backend_ok:
    status, body = _request("GET", f"{BACKEND}/low-attendance?limit=5")
    if status == 200 and isinstance(body, list):
        if len(body) == 0:
            print(f"{SKIP}  No low-attendance students in DB — run the scraper first")
            results.append(("student_email field present in /low-attendance", True, "skipped — empty list"))
        else:
            first = body[0]
            has_email_key = "student_email" in first
            check(
                "student_email key present in /low-attendance response",
                has_email_key,
                f"keys: {list(first.keys())}",
            )
            # Show a sample
            info(f"Sample student: {first.get('student_name')} | USN: {first.get('usn')} | email: {first.get('student_email')!r}")
    else:
        check("GET /low-attendance returns 200", False, f"HTTP {status}: {body}")
else:
    print(f"{SKIP}  Backend offline")


# ─── 3. Notify flags accepted by backend ─────────────────────────────────────

section("3 · POST /alerts/send/{teacher_id} — notify flags in request body")

teacher_id = None
if backend_ok:
    # Fetch first teacher
    status, body = _request("GET", f"{BACKEND}/teachers")
    if status == 200 and body:
        teacher_id = body[0]["id"]
        info(f"Testing with teacher id={teacher_id}  name={body[0]['name']}")
    else:
        print(f"{SKIP}  No teachers in DB")

if teacher_id is not None:
    # Test 1: notify_teacher=True, notify_student=False
    status, body = _request(
        "POST",
        f"{BACKEND}/alerts/send/{teacher_id}",
        {"notify_teacher": True, "notify_student": False},
    )
    check(
        "POST body with notify_teacher=True, notify_student=False accepted (2xx or 4xx, not 422/500)",
        status in (200, 400, 503),   # 400=no students, 503=notif svc down — all valid; 422/500=bug
        f"HTTP {status}  status={body.get('status')!r}  detail={body.get('detail')!r}",
    )

    # Test 2: notify_teacher=False, notify_student=True
    status, body = _request(
        "POST",
        f"{BACKEND}/alerts/send/{teacher_id}",
        {"notify_teacher": False, "notify_student": True},
    )
    check(
        "POST body with notify_teacher=False, notify_student=True accepted",
        status in (200, 400, 503),
        f"HTTP {status}  status={body.get('status')!r}  detail={body.get('detail')!r}",
    )

    # Test 3: both flags True (default — should always be accepted)
    status, body = _request(
        "POST",
        f"{BACKEND}/alerts/send/{teacher_id}",
        {"notify_teacher": True, "notify_student": True},
    )
    check(
        "POST body with both flags=True accepted",
        status in (200, 400, 503),
        f"HTTP {status}  status={body.get('status')!r}  emails_sent={body.get('emails_sent')}  "
        f"records_logged={body.get('records_logged')}",
    )
    if status == 200 and body.get("status") not in ("skipped",):
        info(f"  emails_sent={body.get('emails_sent')}  records_logged={body.get('records_logged')}")
else:
    if backend_ok:
        print(f"{SKIP}  No teachers in DB")


# ─── 4. Notification service /notify — schema + live delivery ────────────────

section("4 · POST /notify — schema validation")

if notif_ok:
    # 4a. notify_teacher=True, notify_student=False — teacher summary only
    status, body = _request("POST", f"{NOTIF_SVC}/notify", {
        "teacher":        {"name": "Test Teacher", "email": "ranaadiba71@gmail.com"},
        "students":       [{
            "name": "Test Student", "usn": "1MS00TS000", "semester": "6",
            "student_email": None,
            "subjects": [{"subject_name": "Math", "attendance_percentage": 60.0,
                          "attended_classes": 18, "total_classes": 30}],
        }],
        "notify_teacher": True,
        "notify_student": False,
    })
    check(
        "4a. notify_teacher=True, notify_student=False → 200",
        status == 200,
        f"HTTP {status}  status={body.get('status')!r}  emails_sent={body.get('emails_sent')}  detail={body.get('detail')!r}",
    )

    # 4b. notify_student=True but student_email=null → graceful skip, no crash
    status, body = _request("POST", f"{NOTIF_SVC}/notify", {
        "teacher":        {"name": "Test Teacher", "email": "ranaadiba71@gmail.com"},
        "students":       [{
            "name": "Student No Email", "usn": "1MS00TS001", "semester": "6",
            "student_email": None,
            "subjects": [{"subject_name": "OS", "attendance_percentage": 55.0,
                          "attended_classes": 11, "total_classes": 20}],
        }],
        "notify_teacher": False,
        "notify_student": True,
    })
    check(
        "4b. notify_student=True + student_email=null → 200 (graceful skip)",
        status == 200,
        f"HTTP {status}  status={body.get('status')!r}  emails_sent={body.get('emails_sent')}  detail={body.get('detail')!r}",
    )
    if status == 200:
        info(f"emails_sent={body.get('emails_sent')} (expected 0 — no student email address)")

    # 4c. Both flags False → 400 validation guard
    status, body = _request("POST", f"{NOTIF_SVC}/notify", {
        "teacher":  {"name": "X", "email": "ranaadiba71@gmail.com"},
        "students": [{"name": "Y", "usn": "Z", "semester": "1",
                      "subjects": [{"subject_name": "S", "attendance_percentage": 50.0,
                                    "attended_classes": 5, "total_classes": 10}]}],
        "notify_teacher": False,
        "notify_student": False,
    })
    check(
        "4c. Both flags False → 400 Bad Request",
        status == 400,
        f"HTTP {status}  detail={body.get('detail')!r}",
    )
else:
    print(f"{SKIP}  Notification service offline")


# ─── 4d. LIVE student email delivery test ────────────────────────────────────

section("4d · Live student email delivery (notify_student=True with real email)")

if not notif_ok:
    print(f"{SKIP}  Notification service offline")
elif not TEST_STUDENT_EMAIL:
    print(f"{SKIP}  No --student-email provided")
    print(f"       Re-run with:  python3 test_phase6.py --student-email yourname@gmail.com")
else:
    info(f"Sending live student email to: {TEST_STUDENT_EMAIL}")
    info("Payload: 2 low-attendance subjects, notify_teacher=False, notify_student=True")

    live_payload = {
        "teacher": {"name": "Brunda G", "email": "ranaadiba71@gmail.com"},
        "students": [{
            "name":          "Test Student (Phase 6 Smoke Test)",
            "usn":           "1MS23CS000",
            "semester":      "6",
            "student_email": TEST_STUDENT_EMAIL,
            "subjects": [
                {
                    "subject_name":          "Design & Analysis of Algorithms",
                    "attendance_percentage": 62.5,
                    "attended_classes":      25,
                    "total_classes":         40,
                },
                {
                    "subject_name":          "Operating Systems",
                    "attendance_percentage": 70.0,
                    "attended_classes":      35,
                    "total_classes":         50,
                },
            ],
        }],
        "notify_teacher": False,
        "notify_student": True,
    }

    status, body = _request("POST", f"{NOTIF_SVC}/notify", live_payload)

    email_actually_sent = status == 200 and body.get("emails_sent", 0) >= 1

    check(
        f"Student email delivered → {TEST_STUDENT_EMAIL}",
        email_actually_sent,
        f"HTTP {status}  status={body.get('status')!r}  emails_sent={body.get('emails_sent')}  "
        f"records_logged={body.get('records_logged')}  detail={body.get('detail')!r}",
    )

    if email_actually_sent:
        print(f"\033[92m       ✉  Email sent! Check inbox at {TEST_STUDENT_EMAIL}\033[0m")
        info("Expected subject: 'Attendance Warning — 2 subject(s) below threshold | 1MS23CS000'")

        # Verify it was logged with recipient_type='student'
        status2, logs = _request("GET", f"{NOTIF_SVC}/alerts/logs?limit=5")
        if status2 == 200 and logs:
            latest = logs[0]
            check(
                "Log entry for student email has recipient_type='student'",
                latest.get("recipient_type") == "student",
                f"recipient_type={latest.get('recipient_type')!r}  usn={latest.get('usn')!r}",
            )
        else:
            check("Could not fetch logs to verify recipient_type", False, f"HTTP {status2}")
    else:
        info("Email not sent — check SMTP config in notification-service/.env")


# ─── 5. Alert logs — recipient_type field ────────────────────────────────────

section("5 · GET /alerts/logs — recipient_type column")

if backend_ok:
    status, body = _request("GET", f"{BACKEND}/alerts/logs?limit=20")
    if status == 200 and isinstance(body, list):
        if len(body) == 0:
            print(f"{SKIP}  No logs yet — send an alert first")
        else:
            first = body[0]
            has_rt = "recipient_type" in first
            check(
                "recipient_type key present in /alerts/logs response",
                has_rt,
                f"keys: {list(first.keys())}",
            )
            if has_rt:
                types = {r.get("recipient_type") for r in body}
                info(f"recipient_type values seen in last 20 logs: {types}")
    else:
        check("GET /alerts/logs returns 200", False, f"HTTP {status}: {body}")
else:
    print(f"{SKIP}  Backend offline")

if notif_ok:
    status, body = _request("GET", f"{NOTIF_SVC}/alerts/logs?limit=20")
    if status == 200 and isinstance(body, list) and body:
        first = body[0]
        check(
            "recipient_type field present in notification service /alerts/logs",
            "recipient_type" in first,
            f"keys: {list(first.keys())}",
        )
else:
    print(f"{SKIP}  Notification service offline")


# ─── 6. emails.csv sync (dry-run via import script) ──────────────────────────

section("6 · emails.csv / import_emails.py")

import os, subprocess
csv_path = os.path.join(os.path.dirname(__file__), "emails.csv")
check(
    "emails.csv exists at msrit-scraper/emails.csv",
    os.path.exists(csv_path),
    csv_path,
)

if os.path.exists(csv_path):
    result = subprocess.run(
        [sys.executable, "-m", "backend.scripts.import_emails", "--csv", csv_path, "--dry-run"],
        capture_output=True, text=True,
        cwd=os.path.dirname(__file__),
    )
    check(
        "import_emails.py --dry-run exits cleanly (code 0)",
        result.returncode == 0,
        result.stderr.strip()[:200] if result.returncode != 0 else "OK",
    )
    if result.stdout.strip():
        info(f"Dry-run output:\n{result.stdout.strip()}")


# ─── Summary ──────────────────────────────────────────────────────────────────

section("Summary")

passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total  = len(results)

print(f"\n  Total: {total}  |  {PASS}: {passed}  |  {FAIL}: {failed}\n")

if failed == 0:
    print("\033[92m  ✓ All checks passed — Phase 6 is wired up correctly.\033[0m\n")
else:
    print("\033[91m  ✗ Some checks failed — see details above.\033[0m\n")
    sys.exit(1)
