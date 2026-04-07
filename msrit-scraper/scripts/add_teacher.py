"""
Utility to add (or update) a teacher in the database.

Usage:
    python scripts/add_teacher.py

The script will prompt for:
  - Teacher full name
  - Email address (used as unique key)
  - Portal login username
  - Portal login password (input hidden)

The password is Fernet-encrypted before storage — never written as plaintext.
"""

import sys
import os
import getpass

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import FERNET_KEY
from app.db import init_db, upsert_teacher
from app.encryption import encrypt_password


def main():
    if not FERNET_KEY:
        print("ERROR: FERNET_KEY not set in .env — cannot encrypt password.")
        sys.exit(1)

    print("=== Add / Update Teacher ===")
    name             = input("Full name         : ").strip()
    email            = input("Email address     : ").strip()
    portal_username  = input("Portal username   : ").strip()
    plain_password   = getpass.getpass("Portal password   : ")

    if not all([name, email, portal_username, plain_password]):
        print("ERROR: All fields are required.")
        sys.exit(1)

    encrypted = encrypt_password(plain_password, FERNET_KEY)
    plain_password = None  # clear from memory

    init_db()
    teacher_id = upsert_teacher(name, email, portal_username, encrypted)
    print(f"\nTeacher '{name}' saved with id={teacher_id}.")
    print("Password stored encrypted — plaintext never written to disk.")


if __name__ == "__main__":
    main()
