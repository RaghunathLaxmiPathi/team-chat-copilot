"""Who did what, written in the caller's transaction (DD-19, SEC-05)."""
import json

from app import clock


class AuditLog:
    def __init__(self, db):
        self.db = db

    def record(self, actor_id: str, action: str, target_type: str, target_id: str, detail: dict | None = None) -> None:
        self.db.exec(
            "INSERT INTO audit_log (ts, actor_id, action, target_type, target_id, detail) VALUES (?, ?, ?, ?, ?, ?)",
            (clock.iso(), actor_id, action, target_type, target_id, json.dumps(detail or {})),
        )
