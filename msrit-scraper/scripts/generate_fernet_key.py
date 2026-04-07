"""
Run this ONCE to generate your FERNET_KEY and print it.
Copy the output into your .env file.

WARNING: Never regenerate after teachers have been added to the DB —
existing encrypted passwords will become unreadable.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.encryption import generate_key

key = generate_key()
print(f"\nFERNET_KEY={key}")
print("\nCopy the line above into your .env file.")
print("Keep this key secret — losing it makes all stored passwords unrecoverable.")
