"""Consistent copy of the database while the service runs: python -m app.backup <destination>"""
import sys

from app.config import Settings
from app.db import Database

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m app.backup <destination file>")
    db = Database(Settings.from_env().db_path)
    db.backup(sys.argv[1])
    db.close()
    print(f"Backup written to {sys.argv[1]}")
