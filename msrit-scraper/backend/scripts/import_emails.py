"""
import_emails.py — One-shot CLI to bulk-load student emails from a CSV file.

Usage (from msrit-scraper/ directory):
    python3 -m backend.scripts.import_emails --csv emails.csv

CSV format (header row required):
    USN,Email
    1MS23CS211,student@gmail.com
    1MS23CS212,another@gmail.com
"""

import csv
import sys
import argparse
import logging

import psycopg2
from backend.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def import_emails(csv_path: str, dry_run: bool = False) -> None:
    # ── Read CSV ──────────────────────────────────────────────────────────────
    rows: list[tuple[str, str]] = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or "USN" not in reader.fieldnames or "Email" not in reader.fieldnames:
                logger.error("CSV must have 'USN' and 'Email' columns in the header row.")
                sys.exit(1)
            for line_no, row in enumerate(reader, start=2):
                usn   = row.get("USN", "").strip().upper()
                email = row.get("Email", "").strip().lower()
                if not usn or not email:
                    logger.warning(f"Line {line_no}: skipping blank USN or Email")
                    continue
                rows.append((usn, email))
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    logger.info(f"Loaded {len(rows)} valid rows from {csv_path}")

    if dry_run:
        for usn, email in rows:
            print(f"  DRY-RUN  {usn}  →  {email}")
        return

    # ── Connect to DB ─────────────────────────────────────────────────────────
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD or None,
    )
    conn.autocommit = False
    cur = conn.cursor()

    updated = skipped = 0
    try:
        for usn, email in rows:
            cur.execute(
                "UPDATE students SET student_email = %s WHERE usn = %s",
                (email, usn),
            )
            if cur.rowcount > 0:
                updated += 1
            else:
                skipped += 1
                logger.debug(f"USN not in DB — skipped: {usn}")

        conn.commit()
        logger.info(f"Done — {updated} rows updated, {skipped} USNs not found in DB")
    except Exception as e:
        conn.rollback()
        logger.error(f"DB update failed — rolled back: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk-import student emails from CSV into PostgreSQL")
    parser.add_argument("--csv",     default="emails.csv", help="Path to the CSV file (default: emails.csv)")
    parser.add_argument("--dry-run", action="store_true",  help="Preview rows without writing to DB")
    args = parser.parse_args()
    import_emails(args.csv, dry_run=args.dry_run)
